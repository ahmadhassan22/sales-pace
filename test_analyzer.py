"""Sanity test for analyzer + summarizer — run before wiring up the UI."""

from app.analyzer import analyze_report
from app.summarizer import summarize

REPORT_PATH = "app/data/sample_report.xlsx"


def main():
    analysis = analyze_report(REPORT_PATH)

    print("=" * 70)
    print("ROUTE → SEGMENT BREAKDOWN (verifying reconciliation)")
    print("=" * 70)

    for route in analysis["route_segment_breakdown"][:3]:  # first 3 routes
        print(f"\n### {route['name']}")
        print(f"    Route total: Sale {route['sale']:,.0f} / "
              f"Target {route['target']:,.0f} / {route['pct_achieved']}% "
              f"[{route['status']}]")
        print(f"    Segments:")

        seg_sale_sum = 0
        for seg in route["segments"]:
            print(f"      - {seg['name']:<12} "
                  f"Sale {seg['sale']:>9,.0f} | "
                  f"Target {seg['target']:>9,.0f} | "
                  f"{seg['pct_achieved']:>5}% | "
                  f"gap {seg['gap']:>9,.0f} | "
                  f"{seg['status']}")
            seg_sale_sum += seg["sale"]

        # Reconciliation check: segment sales must equal route total.
        match = "✅ MATCH" if abs(seg_sale_sum - route["sale"]) < 0.5 else "❌ MISMATCH"
        print(f"    Segment sale sum: {seg_sale_sum:,.0f} "
              f"vs route total {route['sale']:,.0f}  {match}")


if __name__ == "__main__":
    main()