# JobRadar

A job board scraper and tracker, built for applying from India.

It pulls listings from five job boards, scores them against keywords you
choose, filters out roles that will not hire from your country, remembers
everything it has seen before, and tells you which jobs are **new since your
last run**.

Python. Roughly 900 lines across five small files, each with one job.

```
JobRadar -- scanning job boards

1. Scraping 5 source(s), up to 50 jobs each
  OK     remoteok         50 jobs
  OK     weworkremotely   50 jobs
  OK     remotive         18 jobs
  OK     himalayas        20 jobs
  OK     adzuna           35 jobs

2. Scoring 173 jobs against 15 keywords
  OK     kept 24, dropped 149 below score 6 or blocklisted

3. Comparing against previous runs
  OK     112 jobs already in history, 9 new

4. Saving results
  OK     added 9 new rows

 Score | Title                        | Location              | Source
-------+------------------------------+-----------------------+---------------
    29 | Python Developer             | Bengaluru, Karnataka  | adzuna
    23 | Backend Engineer (Django)    | Hyderabad, Telangana  | adzuna
    16 | DevOps & Security Engineer   | Anywhere in the World | weworkremotely
    16 | Tier III Service Desk Eng.   | Worldwide             | remotive

24 jobs matched out of 173 scraped  (9 new since last run)
```

---

## What makes it useful

- **Five sources, three formats** — a JSON API, an RSS feed, and raw HTML.
  Each needs a different technique.
- **It knows you are in India.** Most "remote" jobs are not open to
  everyone. A real listing we pulled said *"Americas, Europe, Israel"* —
  which quietly means no India. Those get filtered out before you waste
  time on them.
- **Real Indian jobs**, in Bengaluru, Hyderabad, Pune and Chennai, via the
  official Adzuna API.
- **Scores and ranks** every job, so the best matches float to the top.
- **Tracks what is new** by fingerprinting each job. Run it daily and you
  only read what changed.
- **Exports to CSV, Excel and HTML.**
- **Runs itself.** A GitHub Actions workflow scans every morning at 9am IST
  with your laptop closed.
- **Survives broken websites.** One source down does not stop the run.

---

## Quickstart

**Windows (PowerShell):**
```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python main.py
```

**macOS / Linux:**
```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python main.py
```

Results land in `data/`. Open `data/report.html` in your browser.

---

## Getting real Indian jobs (2 minutes, free)

Four of the five sources work immediately with no setup, but they are all
**global remote** boards. For jobs actually based in Indian cities you need
an Adzuna key, which is free:

1. Sign up at [developer.adzuna.com](https://developer.adzuna.com/)
2. Create an app and copy your **Application ID** and **Application Key**
3. Make a file called `adzuna_key.txt` in this folder, two lines:

```
your_app_id_here
your_app_key_here
```

Run again and you will see `adzuna` in the source list. Without it that one
source politely skips and the other four still run.

`adzuna_key.txt` is in `.gitignore`. **Never put a key directly in your
code** — anything you push to GitHub is public forever, even if you delete
it afterwards.

---

## Making it yours

Open **`config.py`**. It is the only file you need to touch.

```python
KEYWORDS = {
    "python": 10,      # words you really want  -> big number
    "junior": 6,
    "sql": 5,
}

BLOCKLIST = ["senior", "manager", "10+ years"]

MIN_KEYWORD_SCORE = 4   # skills bar, checked before location
MIN_SCORE = 6           # total bar, after the location bonus

REQUIRE_LOCATION_MATCH = True   # drop jobs that will not hire from India
```

The default keywords are generic. **Replace them with words from jobs you
would actually apply to** — your languages, your level, your city. That is
what turns this from a demo into a tool.

Too few results? Lower `MIN_SCORE`, or set `REQUIRE_LOCATION_MATCH = False`.

---

## Command line options

| Flag | What it does |
|------|--------------|
| `--source adzuna` | Only scrape one source. Repeat for several. |
| `--limit 20` | Pull fewer jobs per source (faster while testing). |
| `--min-score 10` | Only show strong matches this run. |
| `--new-only` | Hide anything you have already seen. |
| `--dry-run` | Run everything, write nothing. |
| `--open` | Open the HTML report when finished. |

```bash
python main.py --source adzuna --min-score 15 --new-only --open
```

---

## How it works

| Step | File | What happens |
|------|------|--------------|
| 1. Scrape | `scrapers.py` | Visit the sites and read the listings |
| 2. Filter | `filters.py` | Score, blocklist, location check, rank |
| 3. Compare | `storage.py` | Work out which jobs are new |
| 4. Save | `storage.py` | Write the CSV and Excel files |
| 5. Report | `report.py` | Print a table, build the web page |

### The sources

Every site publishes differently, so each scraper reads a different format —
but all of them return **the same shape of dictionary**. That is the design
idea worth noticing: the rest of the program never has to know where a job
came from, and adding a sixth source means writing one function and adding
one line to `SCRAPERS`.

| Source | Format | Gives us |
|--------|--------|----------|
| Adzuna India | JSON API | Real jobs in Indian cities (needs free key) |
| RemoteOK | JSON API | Global remote tech jobs |
| We Work Remotely | RSS (XML) | Global remote jobs |
| Remotive | JSON API | Which countries may apply |
| Himalayas | JSON API | Location limits and seniority |
| Real Python fake-jobs | Raw HTML | Practice data, off by default |

### How "new" is detected

Each job gets a fingerprint made by hashing its URL:

```
https://remoteok.com/jobs/12345   ->   a3f5c9e102
```

Same posting, same fingerprint, every time. Those IDs live in
`data/jobs.csv`. Next run, anything whose ID is missing from that file is
genuinely new and gets a green **NEW** badge.

---

## Running it automatically

`.github/workflows/daily.yml` makes GitHub run the scraper at **9am IST**
every day, on their machines, and commit the results back here. Your laptop
can be closed.

To use the Adzuna source there, add your key under
**Settings → Secrets and variables → Actions** as `ADZUNA_APP_ID` and
`ADZUNA_APP_KEY`. Without them, that source just skips.

You can also trigger it by hand from the **Actions** tab.

---

## Tests

```bash
python -m pytest
```

```
38 passed
```

38 tests covering scoring, the blocklist, the location rules, the ID
fingerprints, and a full save-and-read-back round trip. They use temporary
folders, so running them never touches your real `data/`.

---

## Three problems worth writing about

**Tag spam was ruining the rankings.** The first working version scored a
warehouse **"Laborer"** job as highly as real Python roles, because RemoteOK
had tagged it `engineer`, `data`, `ruby` and eighteen other words. Fix: a
keyword in the **title** earns full points, a keyword only in the tags earns
half. The title is the honest signal. The report now prints `data (tag)` so
you can see why something scored, and there is a regression test named after
that bug.

**Being in the right city is not the same as being the right job.** Adding
location scoring immediately caused a new problem: an **"Assembly
Technician"** role in Chennai scored 15 points just for being in India and
outranked genuine Python jobs. Fix: skills are now a *gate* checked before
the location bonus is added, so a convenient location can improve a job's
ranking but can never rescue one you are not suited for.

**A function was secretly depending on another one.** `save_jobs()` needed
every job to already have an ID, which `main.py` happened to add one step
earlier. It worked — until a test called `save_jobs()` on its own and it
crashed. Functions should not quietly rely on having been called in the
right order.

---

## A note on scraping politely

**Naukri, LinkedIn, Indeed and Internshala are deliberately not in this
project.** Their terms of service forbid automated access, and their
`robots.txt` files say so directly — Naukri's blocks bots by name with
`Disallow: /`, and Internshala disallows `/job/search/` and `/job/details/`,
which is exactly the data a scraper would want.

Scraping them would get your IP banned and is not something you would want
to defend in an interview. So every source here either publishes an **open
API** or an **RSS feed** that exists to be read by programs:

- **Adzuna** offers a free registered API — the key requirement is how they
  keep track of who is using it.
- **RemoteOK** publishes a public JSON API. Their terms ask for credit as a
  source, which the HTML report gives them.
- **Remotive** and **Himalayas** both publish open job APIs.
- **We Work Remotely** publishes an RSS feed.
- **realpython.github.io/fake-jobs** is a practice site built for people
  learning to scrape, so no real company's servers get hit.

Requests are retried with a backoff rather than hammered, and a full run
makes five of them. If you point this at another site, read its terms and
`robots.txt` first.

---

## What I used

`requests` · `BeautifulSoup` · `ElementTree` · `pandas` · `openpyxl` ·
`rich` · `pytest` · `argparse` · `hashlib` · GitHub Actions

And the ideas underneath: normalising messy data from five sources into one
consistent shape, failing gracefully when a network call dies, hashing for
stable identity, keeping secrets out of source control, separating
configuration from code, and writing tests that catch real bugs.
