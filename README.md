# Sales Pace Analyzer

An AI-powered sales analytics tool built for a beverage distribution manager in Pakistan.

Turns a raw Excel Sales vs Target report into instant, pace-aware insights —
with per-route segment breakdowns, gap-to-go calculations, and ready-to-forward
WhatsApp messages for each field sales rep (PSR) in Roman Urdu.

---

## The Problem
🎥 **[Watch the 3-minute walkthrough](https://www.loom.com/share/23f545f997264f7b8f578cb242da52e1)**

A sales manager at a beverage distribution company manually analyzes
Sales vs Target Excel reports every 1–2 days.

The process looked like this:
- Download the report from the sales portal (1,000+ rows)
- Build pivot tables by hand for each segment, route, and MDE
- Write custom percentage formulas manually
- Mentally calculate how much needs to be sold per day to still hit
  the monthly target
- Write individual WhatsApp messages to each field sales rep (PSR)
  with their remaining targets and action points

This took 20–30 minutes per cycle, repeated every 1–2 days.

The deeper problem was not the time. It was that mid-month pace was
invisible. Raw numbers (17% achieved) look alarming without context.
But on day 15 of a 30-day month, 17% isn't the right number to look at.
The real question is: **are we selling fast enough today to hit the
target by month end — and where exactly is the gap?**

That question had no easy answer in the manual process.

---

## The Solution

A web app where the manager uploads the Excel export and instantly gets:

- **Pace-aware performance** — achievement % compared against expected
  % based on days elapsed, not just raw numbers
- **Gap-to-go + daily run-rate** — exactly how many units need to be
  sold per day for the remaining days to hit monthly target
- **Per-route segment breakdown** — click any route to see how each
  segment (CSD, Sting, Aquafina, etc.) is performing inside it, so the
  manager knows whether a weak route is one bad segment or all of them
- **Segment, route, MDE, and flavour breakdowns** — all in one view,
  no pivot tables needed
- **Zero-sale alerts** — products with a target but no sales flagged
  automatically (distribution or stock issues, not performance issues)
- **PSR messages in Roman Urdu** — one ready-to-forward WhatsApp message
  per field rep, naming that rep's own weakest segments by gap size,
  with tone that adapts to whether they're ahead or behind pace

---

## Key Design Decisions

**Why rules-based analysis + LLM only for messages?**
All numbers (targets, gaps, run-rates, percentages, per-segment gaps)
are computed in Python — never by the LLM. The LLM only wraps verified
numbers in natural Roman Urdu. This eliminates hallucination risk on
client-facing content. Per-segment figures quoted inside messages are
passed in as hard facts; the model is instructed never to invent numbers.
If the LLM call fails, a safe template is used as fallback. No wrong
number ever reaches a PSR.

**Why per-rep messages grounded in segment data?**
A generic "you're behind, work harder" message gets ignored. Each PSR
message names the rep's two biggest-gap segments with real numbers and
tells them where to focus — so nine messages differ by real content,
not just swapped names. Tone also adapts to severity: an ahead rep gets
encouragement, a deeply-behind rep gets an urgent recovery framing.

**Why pace instead of raw achievement %?**
A report downloaded on day 15 of a 30-day month shows ~50% achievement
if the team is on track. Raw % without context is misleading. The tool
computes expected pace from days elapsed and flags behind / on-pace /
ahead relative to that baseline. The period is read from the file itself,
so any date or month works automatically.

**Why delete uploaded files immediately?**
The reports contain real company sales data. Files are deleted from the
server the moment analysis completes — even if analysis fails. Client
data never sits on disk longer than the processing time.

**Why Roman Urdu for PSR messages?**
Field reps communicate in Roman Urdu on WhatsApp. English messages feel
formal and disconnected. Roman Urdu messages feel like they came from the
manager directly — which means they actually get read and acted on.

---

## Features

- Upload any Sales vs Target Excel export — any date, any month
- Period and pace baseline auto-detected from the file itself
- Overall summary — period, achievement vs expected, gap, run-rate
- Priority focus list — worst routes and zero-sale segments surfaced
- Performance tables — by segment, route, MDE, and flavour
- Expandable route rows — click a route for its per-segment breakdown
- Status badges — Behind / On Pace / Ahead with visual progress bars
- PSR messages — segment-aware Roman Urdu, one per field rep
- Copy to clipboard — one click to copy and forward on WhatsApp
- Zero client data stored — files deleted after analysis

---

## Tech Stack

| Layer | Technology |
|---|---|
| Backend | FastAPI + Uvicorn |
| Analysis | Pandas + custom pace logic |
| LLM (messages) | Groq — LLaMA 3.3 70B |
| Frontend | Vanilla HTML/CSS/JS (single file) |
| File parsing | OpenPyXL |
| Environment | python-dotenv |

---

## Project Structure
sales-pace/

├── app/

│   ├── analyzer.py        # Pace-aware analysis + per-route segment breakdown

│   ├── summarizer.py      # Rules-based insights + 9-PSR message generator

│   ├── static/

│   │   └── index.html     # Frontend (single file, expandable route rows)

│   └── data/

│       └── uploads/       # Temp folder — files deleted after analysis

├── main.py                # FastAPI app + /analyze endpoint

├── test_analyzer.py       # Sanity tests — run before deploying

├── requirements.txt

├── .env.example

└── .gitignore

---

## Quick Start

### 1. Clone the repo

```bash
git clone https://github.com/ahmadhassan22/sales-pace.git
cd sales-pace
```

### 2. Create virtual environment

```bash
python -m venv venv
venv\Scripts\activate        # Windows
source venv/bin/activate     # Mac/Linux
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Set up environment variables

```bash
cp .env.example .env
# Add your GROQ_API_KEY to .env
```

Get a free Groq key at [console.groq.com](https://console.groq.com)

### 5. Run the server

```bash
uvicorn main:app --reload
```

Open [http://127.0.0.1:8000](http://127.0.0.1:8000)

### 6. Upload a report

Upload any Sales vs Target Excel export from the sales portal.
Results appear in under a minute (the 9 PSR messages are generated
by the LLM, which takes ~30 seconds).

---

## How It Works
Excel Upload

│

▼

Period Detection

(reads date range from file → calculates days elapsed + remaining)

│

▼

Pace Analysis

(for each segment / route / MDE / flavour, and for each segment

inside each route: sale, target, % achieved, gap, required run-rate)

│

▼

Summarizer

(priority focus list + overall summary — rules-based, no LLM)

│

▼

PSR Message Generator

(for each of 9 PSRs: pulls their route's two biggest-gap segments,

passes verified numbers to Groq, gets a Roman Urdu message back)

│

▼

Results + 9 PSR Messages

(displayed in browser, expandable route breakdowns, one-click copy)

│

▼

File Deleted

(uploaded report removed from server immediately)
---

## Configuring PSRs and Routes

PSR-to-route mapping lives in one place in `app/summarizer.py`:

```python
PSR_ROUTES = {
    "Muhammad Farhan": "KOHAT ROUTE A",
    "Amir Ullah Khan": "DI KHAN ROUTE B",
    # ... one line per PSR
}
```

Add, remove, or reassign a line for each PSR change. Route names must
match exactly as they appear in the Excel file. Wholesale and vacant-spot
routes are intentionally left out (they have no assigned field rep).

---

## Assumptions

This tool reads a specific report format. It expects:
- The data header on row 4 of the sheet
- Columns named `Sale Conv`, `Target Conv`, `Route Name`,
  `Product Group`, `MDE Name`, `Product Flavour`
- A `Period : DD/MM/YYYY - DD/MM/YYYY` line near the top

If the source portal changes its export layout, the loader needs updating.

---

## Future Work

The current version focuses on the Sales vs Target report. Several
extensions are planned based on the user's described workflow:

- **PJP (Permanent Journey Plan) report analysis** — analyze field-visit
  KPIs (call completion, strike rate, SKUs per bill) per PSR, and generate
  coaching messages the same way Sales vs Target messages are generated now.
- **Master Data analysis** — surface outlet-level insights: coolers per
  outlet, outlets below a sales threshold for the month, and outlets where
  a product hasn't sold yet this month or year.
- **Charts and visualizations** — visual summaries (segment and route
  performance bars, pace-over-time) alongside the existing tables.
- **Self-serve PSR/route management** — let the manager add, remove, or
  reassign PSRs and routes from the interface, instead of editing the code.
- **Optional report auto-fetch** — pull the report directly rather than
  uploading manually, subject to the company's access policy.

Each of these will be prioritized based on real feedback from daily use,
not built speculatively.

## Environment Variables
GROQ_API_KEY=your_groq_api_key_here

---

## Author

**Ahmad Hassan**
Master's Student — AI & NLP, Harbin Institute of Technology Shenzhen

Built as a real client tool — not a portfolio exercise.
The problem, the data, the feedback, and the iteration all came from
an actual user with an actual workflow pain.

[GitHub](https://github.com/ahmadhassan22) ·
[LinkedIn](https://linkedin.com/in/ahmad-hassan7207/)