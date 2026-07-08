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
    Read the report's header block and work out how much of the month has
    actually elapsed. Two lines matter:

        row 2:  Period : DD/MM/YYYY - DD/MM/YYYY
        row 3:  Generated On : DD/MM/YYYY HH:MM:SS

    The period range is what the manager *selected* in the portal. It is NOT
    the same as how much data the file contains. If he selects the whole month
    (01/07 - 30/07) but downloads on the 8th, the file only holds 8 days of
    sales — there is no data for days 9-30 yet, because they haven't happened.

    Trusting `period_end` in that case makes the tool believe 30 of 31 days
    have elapsed, so it expects ~97% achievement instead of ~26%, and every
    pace verdict comes out wrong.

    So the data really runs through `min(period_end, generated_on)`, and
    `days_elapsed` is counted from the first of the month up to that date
    (targets are monthly, so the month start is the right anchor).
    """
    raw = pd.read_excel(path, sheet_name=0, header=None, nrows=4)
    header_lines = [str(v) for v in raw.iloc[:, 0].dropna()]

    period_text = next((v for v in header_lines if "Period" in v), "")
    generated_text = next((v for v in header_lines if "Generated On" in v), "")

    match = re.search(r"(\d{2}/\d{2}/\d{4})\s*-\s*(\d{2}/\d{2}/\d{4})", period_text)
    if not match:
        raise ValueError(f"Could not parse period from report: {period_text!r}")

    start = datetime.strptime(match.group(1), "%d/%m/%Y")
    end = datetime.strptime(match.group(2), "%d/%m/%Y")

    # When the report was pulled. Optional — older exports may omit it.
    generated_on = None
    gen_match = re.search(r"(\d{2}/\d{2}/\d{4})", generated_text)
    if gen_match:
        generated_on = datetime.strptime(gen_match.group(1), "%d/%m/%Y")

    # The last day the file can possibly hold data for.
    #   - Report pulled mid-period  -> generated_on caps it.
    #   - Report pulled after the period closed (e.g. last month's report,
    #     downloaded this month) -> period_end caps it.
    data_through = min(end, generated_on) if generated_on else end
    # Guard against a nonsensical header (generated before the period began).
    data_through = max(data_through, start)

    # Total days in the target month (targets are monthly).
    month_start = start.replace(day=1)
    if start.month == 12:
        next_month = start.replace(year=start.year + 1, month=1, day=1)
    else:
        next_month = start.replace(month=start.month + 1, day=1)
    total_days_in_month = (next_month - month_start).days

    # Days of the month covered by this data, inclusive of both ends.
    # Anchored to the 1st because the target being measured against is monthly.
    days_elapsed = (data_through - month_start).days + 1
    days_elapsed = max(1, min(days_elapsed, total_days_in_month))

    days_remaining = max(total_days_in_month - days_elapsed, 0)

    return {
        "period_start": start.strftime("%d/%m/%Y"),
        "period_end": end.strftime("%d/%m/%Y"),
        "generated_on": generated_on.strftime("%d/%m/%Y") if generated_on else None,
        "data_through": data_through.strftime("%d/%m/%Y"),
        "days_elapsed": days_elapsed,
        "total_days_in_month": total_days_in_month,
        "days_remaining": days_remaining,
        # True when the manager selected a range that doesn't start on the 1st.
        # Sales are then partial-month while targets stay monthly, so the
        # achievement % will understate reality. Surface this, don't hide it.
        "partial_month_selection": start != month_start,
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


def breakdown_route_by_segment(df: pd.DataFrame, days_elapsed: int, days_remaining: int) -> list[dict]:
    """
    For each route, break performance down by segment.

    Returns a list of routes, each containing its overall pace metrics
    plus a per-segment breakdown. This shows, e.g., that KOHAT ROUTE A's
    gap is mostly in CSD and Sting — far more actionable than a single
    route-level number.
    """
    df = df.copy()
    df["Route Name"] = df["Route Name"].fillna("(blank)")
    df["Product Group"] = df["Product Group"].fillna("(blank)")

    routes = []
    for route_name, route_group in df.groupby("Route Name"):
        route_metrics = compute_pace_metrics(route_group, days_elapsed, days_remaining)

        segments = []
        for seg_name, seg_group in route_group.groupby("Product Group"):
            seg_metrics = compute_pace_metrics(seg_group, days_elapsed, days_remaining)
            segments.append({"name": str(seg_name), **seg_metrics})

        # Sort segments by target size (biggest opportunity first).
        segments.sort(key=lambda s: s["target"], reverse=True)

        routes.append({
            "name": str(route_name),
            **route_metrics,
            "segments": segments,
        })

    # Sort routes by target size (most important routes first).
    routes.sort(key=lambda r: r["target"], reverse=True)
    return routes


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
        "route_segment_breakdown": breakdown_route_by_segment(df, days_elapsed, days_remaining),
        "by_distributor": breakdown_by(df, "Distributor Name", days_elapsed, days_remaining),
        "by_mde": breakdown_by(df, "MDE Name", days_elapsed, days_remaining),
        "zero_sale_with_target": find_zero_sale_with_target(df),
    }