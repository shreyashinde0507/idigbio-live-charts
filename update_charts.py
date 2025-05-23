#!/usr/bin/env python3
import os
import argparse
import requests
import pandas as pd
import matplotlib.pyplot as plt
import datetime
import json
from plotly import graph_objects as go  # optional, for interactive extensions
from matplotlib.ticker import LogLocator, NullFormatter, NullLocator

import numpy as np
import pandas as pd
import requests
import matplotlib.pyplot as plt

def fetch_monthly_usage(recordset, min_date):
    """Fetch month-by-month metrics from iDigBio."""
    url = "https://search.idigbio.org/v2/summary/stats/search"
    body = {
        "dateInterval": "month",
        "minDate":      min_date,
        "recordset":    recordset
    }
    r = requests.post(url, json=body)
    r.raise_for_status()

    rows = []
    for dt, recs in r.json()["dates"].items():
        metrics = recs.get(recordset, {})
        row = {"Date": pd.to_datetime(dt)}
        row.update(metrics)
        rows.append(row)

    return pd.DataFrame(rows).sort_values("Date")


def plot_usage_bar(df, outpath):
    """
    Draw a grouped bar chart of search_count vs download (records downloaded) by month,
    and label only the download bars with their numeric value.
    """
    labels = df['Date'].dt.strftime("%Y-%m")
    x      = np.arange(len(labels))
    width  = 0.4

    fig, ax = plt.subplots(figsize=(10, 6))

    # Plot the two bar series
    bars_search = ax.bar(x - width/2, df['search'],   width,
                         label="Search Events",     color='C0', alpha=0.8)
    bars_download = ax.bar(x + width/2, df['download'], width,
                           label="Records Downloaded", color='C1', alpha=0.8)

    # Put the y-axis on a log scale and only show 10⁰,10¹,10²… ticks
    ax.set_yscale('log')
    ax.yaxis.set_major_locator(LogLocator(base=10))
    ax.yaxis.set_minor_locator(NullLocator())     # disable minor ticks
    ax.yaxis.set_minor_formatter(NullFormatter())
    ax.set_ylim(1, df[['search','download']].values.max() * 1.2)

    # ─────────────────────────────────────────────────────────────────────────

    # Show only every 2nd month label to avoid overlap
    skip = 2
    ax.set_xticks(x[::skip])
    ax.set_xticklabels(labels[::skip], rotation=45, ha='right')

    ax.set_ylabel("Count")
    ax.set_title("Monthly Usage (Search vs Download)")
    ax.legend(loc='upper left')

    plt.tight_layout()
    plt.savefig(outpath, dpi=300)
    plt.close()
    
def fetch_ingest_stats(recordset, min_date, max_date):
    """Pull annual ingestion (records only) from iDigBio—skip mediarecords."""
    url = "https://search.idigbio.org/v2/summary/stats/api/"
    params = {
        "dateInterval": "year",
        "minDate":      min_date,
        "maxDate":      max_date,
        "recordset":    recordset
    }
    r = requests.get(url, params=params)
    r.raise_for_status()
    js = r.json()["dates"]

    rows = []
    for dt, rec in js.items():
        metrics = rec.get(recordset, {})
        # only include the 'records' metric
        if 'records' in metrics:
            rows.append({
                "Date":   pd.to_datetime(dt),
                "Metric": 'records',
                "Count":  metrics['records']
            })
    return pd.DataFrame(rows)


def plot_ingest_stats(df, outpath):
    """Plot annual 'records' ingestion on a log‑scaled line chart."""
    df = df[df["Metric"] == "records"]

    plt.figure(figsize=(8, 4))
    plt.plot(df["Date"], df["Count"], 'o-', label="records", color='C1')
    plt.yscale("log")
    plt.title("Data Ingestion Metrics (annual)")
    plt.xlabel("Date")
    plt.ylabel("Count")
    plt.legend()
    plt.tight_layout()
    plt.savefig(outpath)
    plt.close()


def fetch_use_stats(recordset, min_date, max_date):
    """Pull annual usage (search/download/view) from iDigBio."""
    url = "https://search.idigbio.org/v2/summary/stats/search/"
    params = {
        "dateInterval": "year",
        "minDate":      min_date,
        "maxDate":      max_date,
        "recordset":    recordset
    }
    r = requests.get(url, params=params)
    r.raise_for_status()
    js = r.json()["dates"]
    rows = []
    for dt, rec in js.items():
        m = rec.get(recordset, {})
        for metric, cnt in m.items():
            rows.append({
                "Date":   pd.to_datetime(dt),
                "Metric": metric,
                "Count":  cnt
            })
    return pd.DataFrame(rows)

def plot_ratios(df, outpath):
    """Compute & plot download/download_count, download/search_count, viewed_records/search_count."""
    w = df.pivot(index="Date", columns="Metric", values="Count").fillna(0)
    # avoid division by zero
    w["dlRatio"] = w["download"] / w["download_count"].replace(0,1)
    w["sdRatio"] = w["download"] / w["search_count"].replace(0,1)
    w["vsRatio"] = w["viewed_records"] / w["search_count"].replace(0,1)

    plt.figure(figsize=(8,4))
    for col, fmt in [("dlRatio","o-"),("sdRatio","s--"),("vsRatio","x-.")]:
        plt.plot(w.index, w[col], fmt, label=col)
    plt.yscale("log")
    plt.title("Usage Ratios (annual)")
    plt.xlabel("Date")
    plt.ylabel("Ratio")
    plt.legend()
    plt.tight_layout()
    plt.savefig(outpath)
    plt.close()

def plot_annual_summary(df, outpath):
    """
    Draw a grouped bar chart showing for each year:
      • search  (all search events)
      • download (all records downloaded)
      • seen     (all “seen” events)
      • viewed_records (all records viewed)
    """
    # 1) Prepare a year‐indexed pivot table
    df2 = df.copy()
    df2['Year'] = df2['Date'].dt.year
    # pick only our four metrics
    metrics = ['search', 'download', 'seen', 'viewed_records']
    df2 = df2[df2['Metric'].isin(metrics)]
    pivot = df2.pivot_table(
        index='Year', columns='Metric', values='Count', aggfunc='sum'
    ).fillna(0)

    years = pivot.index.to_list()
    x = np.arange(len(years))
    width = 0.20

    # 2) Plot bars
    fig, ax = plt.subplots(figsize=(10,6))
    bar_containers = []
    for i, metric in enumerate(metrics):
        bar = ax.bar(
            x + (i - 1.5) * width,    # center the 4 bars around each tick
            pivot[metric],
            width,
            label=metric.replace('_',' ').title()
        )
        bar_containers.append(bar)

    # 3) Labels, legend, etc.
    ax.set_xticks(x)
    ax.set_xticklabels(years, rotation=45)

    # --- add log scale + thousand-separator formatting:
    ax.set_yscale('log')
    ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda y, _: f"{int(y):,}"))

    ax.set_ylabel("Count")
    ax.set_title("Annual Activity Summary")
    ax.legend(ncol=2, loc='upper left', bbox_to_anchor=(0,1.1))

    plt.tight_layout()
    plt.savefig(outpath, dpi=300)
    plt.close()

def main():
    parser = argparse.ArgumentParser(
        description="Fetch iDigBio stats and generate charts"
    )
    parser.add_argument(
        "--recordset",
        required=True,
        help="UUID of the iDigBio recordset"
    )
    parser.add_argument(
        "--monthly-min-date",
        default=f"{datetime.date.today().year}-01-01",
        help="Earliest date (YYYY‑MM‑DD) to fetch for MONTHLY stats"
    )
    parser.add_argument(
        "--overall-min-date",
        default="2015-01-16",
        help="Earliest date (YYYY‑MM‑DD) to fetch for all ANNUAL stats"
    )
    parser.add_argument(
        "--max-date",
        default=datetime.date.today().isoformat(),
        help="Latest date (YYYY‑MM‑DD) for ANNUAL stats"
    )
    parser.add_argument(
        "--out-dir",
        default="docs/charts",
        help="Directory to save generated charts"
    )
    args = parser.parse_args()

    # ensure output folder exists
    os.makedirs(args.out_dir, exist_ok=True)

    # 1) Monthly usage
    df_month = fetch_monthly_usage(args.recordset, args.monthly_min_date)
    plot_usage_bar(df_month, os.path.join(args.out_dir, "usage_monthly.png"))

    # 2) Annual ingestion metrics
    df_ing = fetch_ingest_stats(
        args.recordset,
        args.overall_min_date,
        args.max_date
    )
    plot_ingest_stats(df_ing, os.path.join(args.out_dir, "ingest_metrics.png"))

    # 5) Annual usage ratios
    df_use = fetch_use_stats(
        args.recordset,
        args.overall_min_date,
        args.max_date
    )
    plot_ratios(df_use, os.path.join(args.out_dir, "usage_ratios.png"))

    # 6) Annual summary of four key metrics
    plot_annual_summary(
        df_use,
        os.path.join(args.out_dir, "annual_summary.png")
    )


    print(f"✅ All charts generated in {args.out_dir}")

if __name__ == "__main__":
    main()
