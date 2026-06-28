"""Test the 9 PSR messages — verify they're distinct and segment-aware."""

from app.analyzer import analyze_report
from app.summarizer import summarize

REPORT_PATH = "app/data/sample_report.xlsx"


def main():
    analysis = analyze_report(REPORT_PATH)
    summary = summarize(analysis)

    print("=" * 70)
    print(f"GENERATED {len(summary['psr_messages'])} PSR MESSAGES")
    print("=" * 70)

    for msg in summary["psr_messages"]:
        print("\n" + "-" * 70)
        print(f"PSR: {msg['psr']}  |  Route: {msg['route']}", end="")
        if msg.get("status"):
            print(f"  |  {msg['status'].upper()} ({msg.get('pct_achieved', '?')}%)")
        else:
            print()
        print("-" * 70)
        print(msg["message"])


if __name__ == "__main__":
    main()