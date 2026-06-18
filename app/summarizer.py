"""
Sales report summarizer.

Turns raw analyzer output into:
  1. A plain-language overall summary (3-4 sentences).
  2. A prioritized focus list (the few things that matter most).
  3. Ready-to-forward WhatsApp messages for each PSR in Roman Urdu.

Number logic is always rules-based (never hallucinated).
Groq LLM is used only to wrap numbers in natural Roman Urdu language.
If Groq fails for any reason, a safe English template is used as fallback.
"""

import os
from groq import Groq
from dotenv import load_dotenv

load_dotenv()

# Route → PSR mapping. Names must match exact strings in the Excel file.
PSR_ROUTES = {
    "Farhan": "KOHAT ROUTE A",
    "Javaid": "MIRANSHAH ROUTE A",
}

_groq_client = None


def _get_groq_client() -> Groq:
    """Lazy-load the Groq client once."""
    global _groq_client
    if _groq_client is None:
        api_key = os.getenv("GROQ_API_KEY")
        if not api_key:
            raise ValueError("GROQ_API_KEY not found in environment.")
        _groq_client = Groq(api_key=api_key)
    return _groq_client


def _fmt(n: float) -> str:
    """Format number with thousand separators, no decimals."""
    return f"{n:,.0f}"


def build_overall_summary(analysis: dict) -> str:
    """3-4 sentence headline a manager reads in 10 seconds."""
    period = analysis["period"]
    overall = analysis["overall"]

    pct = overall["pct_achieved"]
    expected = overall["expected_pct"]
    status = overall["status"]
    gap = overall["gap"]
    days_left = period["days_remaining"]
    per_day = overall["required_per_day"]

    if status == "ahead":
        verdict = f"You are ahead of pace ({pct}% achieved vs. {expected}% expected)."
    elif status == "on_pace":
        verdict = f"You are on pace ({pct}% achieved vs. {expected}% expected)."
    else:
        verdict = f"You are behind pace ({pct}% achieved vs. {expected}% expected)."

    period_line = (
        f"Reporting period: {period['period_start']} to {period['period_end']} "
        f"({period['days_elapsed']} of {period['total_days_in_month']} days elapsed)."
    )
    gap_line = (
        f"Remaining target: {_fmt(gap)} units over the next {days_left} days "
        f"— that's {_fmt(per_day)} units/day required to hit total target."
    )
    return f"{period_line} {verdict} {gap_line}"


def build_focus_list(analysis: dict, top_n: int = 5) -> list[dict]:
    """Prioritized list of things to act on first."""
    items: list[dict] = []

    routes_behind = [
        r for r in analysis["by_route"]
        if r["status"] == "behind" and r["target"] > 0
    ]
    routes_behind.sort(key=lambda r: r["gap"], reverse=True)
    for r in routes_behind[:3]:
        items.append({
            "type": "route",
            "priority": "high",
            "headline": f"Route {r['name']} is at {r['pct_achieved']}% (gap: {_fmt(r['gap'])})",
            "action": (
                f"Needs {_fmt(r['required_per_day'])}/day "
                f"for {analysis['period']['days_remaining']} days to recover."
            ),
        })

    zero_segments = [
        s for s in analysis["by_segment"]
        if s["sale"] == 0 and s["target"] > 100
    ]
    for s in zero_segments[:2]:
        items.append({
            "type": "segment",
            "priority": "high",
            "headline": (
                f"Segment {s['name']} has zero sales "
                f"against a target of {_fmt(s['target'])}"
            ),
            "action": "Check distribution/stock — entire segment not moving.",
        })

    for f in analysis["zero_sale_with_target"][:3]:
        items.append({
            "type": "flavour",
            "priority": "medium",
            "headline": (
                f"{f['flavour']} has target {_fmt(f['target'])} but zero sales"
            ),
            "action": "Confirm stock availability and PSR coverage for this SKU.",
        })

    return items[:top_n]


def _safe_template_message(psr_name: str, route_name: str,
                            route_row: dict, days_left: int) -> str:
    """Fallback English message if Groq fails."""
    return (
        f"Salam {psr_name},\n\n"
        f"Update for your route ({route_name}):\n"
        f"• Target: {_fmt(route_row['target'])} units\n"
        f"• Sold so far: {_fmt(route_row['sale'])} units "
        f"({route_row['pct_achieved']}%)\n"
        f"• Gap: {_fmt(route_row['gap'])} units\n"
        f"• Days remaining: {days_left}\n"
        f"• Required per day: {_fmt(route_row['required_per_day'])} units/day\n\n"
        f"Focus: prioritize high-volume outlets and confirm stock availability."
    )


def _llm_roman_urdu_message(psr_name: str, route_name: str,
                              route_row: dict, days_left: int) -> str:
    """
    Ask Groq to write a natural Roman Urdu WhatsApp message.
    All numbers are passed as hard facts — LLM is instructed never to change them.
    Returns the message string, or raises an exception on failure.
    """
    status_context = {
        "ahead": "woh apne target se aage hain — unhe encourage karo aur momentum maintain karne kaho.",
        "on_pace": "woh bilkul sahi pace pe hain — unhe batao ke yahi tempo rakhein.",
        "behind": "woh target se peeche hain — urgent recovery plan chahiye, tone serious rakho.",
        "no_target": "is period mein koi target set nahi hai.",
    }.get(route_row["status"], "status unclear hai.")

    prompt = f"""
Tu ek sales manager hai jo apne PSR ko WhatsApp message bhej raha hai.
Message Roman Urdu mein likho (English letters mein Urdu words).
Tone friendly but professional rakho.
Message seedha PSR ko address karo.

PSR ka naam: {psr_name}
Route: {route_name}
Kul target: {_fmt(route_row['target'])} units
Ab tak ki sale: {_fmt(route_row['sale'])} units ({route_row['pct_achieved']}%)
Bacha hua gap: {_fmt(route_row['gap'])} units
Bachain hue din: {days_left}
Roz ki zaroorat: {_fmt(route_row['required_per_day'])} units/day
Status: {status_context}

Zaroori hukum:
- Sirf yahi numbers use karo jo upar diye gaye hain. Koi naya number mat banao.
- Message mein sab key numbers zaroor aane chahiye: target, sale, gap, roz ki zaroorat.
- Message 100-150 words ka hona chahiye.
- End mein ek motivational line likho.
- Koi extra heading ya bullet points mat lagao — natural conversation style rakho.
"""

    client = _get_groq_client()
    response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[{"role": "user", "content": prompt}],
        max_tokens=400,
        temperature=0.5,
    )
    return response.choices[0].message.content.strip()


def build_psr_message(psr_name: str, route_name: str, analysis: dict) -> dict:
    """Build a WhatsApp-ready message for one PSR."""
    days_left = analysis["period"]["days_remaining"]

    route_row = next(
        (r for r in analysis["by_route"] if r["name"] == route_name),
        None,
    )

    if route_row is None:
        return {
            "psr": psr_name,
            "route": route_name,
            "found": False,
            "message": (
                f"Note: {psr_name}'s route ({route_name}) was not found "
                f"in this report. It may be filtered out of this export."
            ),
        }

    if route_row["target"] == 0:
        return {
            "psr": psr_name,
            "route": route_name,
            "found": True,
            "message": (
                f"Salam {psr_name},\n\n"
                f"Aapke route ({route_name}) ka is period mein "
                f"koi target set nahi hai. Office se confirm karein."
            ),
        }

    # Try LLM first, fall back to safe template if anything goes wrong.
    try:
        message = _llm_roman_urdu_message(
            psr_name, route_name, route_row, days_left
        )
    except Exception as e:
        print(f"[WARN] Groq failed for {psr_name}: {e}. Using fallback template.")
        message = _safe_template_message(
            psr_name, route_name, route_row, days_left
        )

    return {
        "psr": psr_name,
        "route": route_name,
        "found": True,
        "pct_achieved": route_row["pct_achieved"],
        "status": route_row["status"],
        "message": message,
    }


def summarize(analysis: dict) -> dict:
    """Top-level entry. Returns the full summary package."""
    return {
        "overall_summary": build_overall_summary(analysis),
        "focus_list": build_focus_list(analysis),
        "psr_messages": [
            build_psr_message(psr, route, analysis)
            for psr, route in PSR_ROUTES.items()
        ],
    }