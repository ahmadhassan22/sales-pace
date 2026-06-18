"""Sanity test for the analyzer + summarizer — run before wiring up the web app."""

from app.analyzer import analyze_report
from app.summarizer import summarize

REPORT_PATH = "app/data/sample_report.xlsx"


def main():
    analysis = analyze_report(REPORT_PATH)
    summary = summarize(analysis)

    print("=" * 70)
    print("OVERALL SUMMARY")
    print("=" * 70)
    print(summary["overall_summary"])

    print("\n" + "=" * 70)
    print("FOCUS LIST (top priorities)")
    print("=" * 70)
    for i, item in enumerate(summary["focus_list"], start=1):
        print(f"\n{i}. [{item['priority'].upper()}] {item['headline']}")
        print(f"   → {item['action']}")

    print("\n" + "=" * 70)
    print("PSR MESSAGES")
    print("=" * 70)
    for msg in summary["psr_messages"]:
        print(f"\n--- {msg['psr']} ({msg['route']}) ---")
        print(msg["message"])


if __name__ == "__main__":
    main()