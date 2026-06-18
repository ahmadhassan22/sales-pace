"""
Sales vs Target analyzer.

Pure analysis module: given an Excel report exported from the sales system,
return pace-aware insights (achievement, gap-to-go, required daily run-rate)
sliced by segment, route, MDE, distributor, and flavour.
"""

from datetime import datetime
from pathlib import Path
import re
import pandas as pd


# The report has 4 metadata rows at the top; the real header is row 4 (0-indexed).
HEADER_ROW = 4


def load_report(path: str | Path) -> pd.DataFrame:
    """Load the report into a clean DataFrame with the right header row."""
    df = pd.read_excel(path, sheet_name=0, header=HEADER_ROW)
    df = df.dropna(how="all")
    return df


def extract_period(path: str | Path) -> dict:
    """
    Read the 'Period : DD/MM/YYYY - DD/MM/YYYY' line from row 2 of the file.

    Returns days elapsed (inclusive), total days in the month of the start
    date, and days remaining. These drive all pace calculations.
    """
    raw = pd.read_excel(path, sheet_name=0, header=None, nrows=4)
    period_text = ""
    for val in raw.iloc[:, 0].dropna().astype(str):
        if "Period" in val:
            period_text = val
            break

    match = re.search(r"(\d{2}/\d{2}/\d{4})\s*-\s*(\d{2}/\d{2}/\d{4})", period_text)
    if not match:
        raise ValueError(f"Could not parse period from report: {period_text!r}")

    start = datetime.strptime(match.group(1), "%d/%m/%Y")
    end = datetime.strptime(match.group(2), "%d/%m/%Y")

    # Days elapsed in this period (inclusive of both ends).
    days_elapsed = (end - start).days + 1

    # Total days in the target month (targets are monthly).
    if start.month == 12:
        next_month = start.replace(year=start.year + 1, month=1, day=1)
    else:
        next_month = start.replace(month=start.month + 1, day=1)
    month_start = start.replace(day=1)
    total_days_in_month = (next_month - month_start).days

    days_remaining = total_days_in_month - days_elapsed

    return {
        "period_start": start.strftime("%d/%m/%Y"),
        "period_end": end.strftime("%d/%m/%Y"),
        "days_elapsed": days_elapsed,
        "total_days_in_month": total_days_in_month,
        "days_remaining": max(days_remaining, 0),
    }


def compute_pace_metrics(group: pd.DataFrame, days_elapsed: int, days_remaining: int) -> dict:
    """
    For one slice of the data (one segment, one route, etc.), compute:
        sale, target, % achieved, gap, expected pace %,
        on-pace / behind / ahead, and required daily run-rate.
    """
    sale = float(group["Sale Conv"].sum())
    target = float(group["Target Conv"].sum())
    gap = max(target - sale, 0.0)

    pct = (sale / target * 100) if target > 0 else 0.0

    # If month has N days and X have elapsed, expected pace is X/N of target.
    total_days = days_elapsed + days_remaining
    expected_pct = (days_elapsed / total_days * 100) if total_days > 0 else 0.0

    # Status: behind / on-pace / ahead (with a small tolerance band).
    if target == 0:
        status = "no_target"
    elif pct >= expected_pct + 5:
        status = "ahead"
    elif pct <= expected_pct - 5:
        status = "behind"
    else:
        status = "on_pace"

    # Required daily sales for the remaining days to still hit target.
    if days_remaining > 0 and gap > 0:
        required_per_day = gap / days_remaining
    else:
        required_per_day = 0.0

    return {
        "sale": round(sale, 1),
        "target": round(target, 1),
        "gap": round(gap, 1),
        "pct_achieved": round(pct, 1),
        "expected_pct": round(expected_pct, 1),
        "status": status,
        "required_per_day": round(required_per_day, 1),
    }


def breakdown_by(df: pd.DataFrame, column: str, days_elapsed: int, days_remaining: int) -> list[dict]:
    """Group by a column and compute pace metrics for each group."""
    df = df.copy()
    df[column] = df[column].fillna("(blank)")
    rows = []
    for name, group in df.groupby(column):
        metrics = compute_pace_metrics(group, days_elapsed, days_remaining)
        rows.append({"name": str(name), **metrics})
    rows.sort(key=lambda r: r["target"], reverse=True)
    return rows


def find_zero_sale_with_target(df: pd.DataFrame) -> list[dict]:
    """Products that have a target but zero sales — distribution/stock red flags."""
    grouped = df.groupby("Product Flavour").agg(
        sale=("Sale Conv", "sum"),
        target=("Target Conv", "sum"),
    ).reset_index()
    flagged = grouped[(grouped["sale"] == 0) & (grouped["target"] > 0)]
    flagged = flagged.sort_values("target", ascending=False)
    return [
        {"flavour": row["Product Flavour"], "target": round(row["target"], 1)}
        for _, row in flagged.iterrows()
    ]


def analyze_report(path: str | Path) -> dict:
    """Main entry point. Returns the full analysis as a dict."""
    df = load_report(path)
    period = extract_period(path)

    days_elapsed = period["days_elapsed"]
    days_remaining = period["days_remaining"]

    overall = compute_pace_metrics(df, days_elapsed, days_remaining)

    return {
        "period": period,
        "overall": overall,
        "by_segment": breakdown_by(df, "Product Group", days_elapsed, days_remaining),
        "by_flavour": breakdown_by(df, "Product Flavour", days_elapsed, days_remaining),
        "by_route": breakdown_by(df, "Route Name", days_elapsed, days_remaining),
        "by_distributor": breakdown_by(df, "Distributor Name", days_elapsed, days_remaining),
        "by_mde": breakdown_by(df, "MDE Name", days_elapsed, days_remaining),
        "zero_sale_with_target": find_zero_sale_with_target(df),
    }