# JobRadar

A job board scraper and tracker, built for applying from India.

It pulls listings from five job boards, scores them against keywords you
choose, filters out roles that will not hire from your country, remembers
everything it has seen before, and tells you which jobs are **new since your
last run**.

Python. About 1,700 lines across six small files, each with one job.

Real output from a live run:

```
JobRadar -- scanning job boards

1. Scraping 5 source(s), up to 60 jobs each
  OK     remoteok         60 jobs
  OK     weworkremotely   60 jobs
  OK     remotive         18 jobs
  OK     himalayas        20 jobs
  OK     adzuna           50 jobs

2. Scoring 208 jobs against 43 keywords
  OK     kept 13, dropped 195 below score 6 or blocklisted

3. Comparing against previous runs
  OK     0 jobs already in history, 13 new

4. Saving results
  OK     added 13 new rows

 Score | Title                                | Location              | Source
-------+-------------------------------------+-----------------------+---------------
    53 | Full Stack Software Engineer        | India                 | adzuna
    53 | Software Engineer - Full Stack Dev   | Bangalore, Karnataka  | adzuna
    49 | .Net Python - AI Claude Developer   | Mumbai, Maharashtra   | adzuna
    48 | Backend Developer - Python          | Bangalore, Karnataka  | adzuna
    35 | AI and Automation Developer         | Bangalore, Karnataka  | adzuna
    31 | AI Engineer                         | Hyderabad, Telangana  | adzuna
    28 | DevOps & Security Engineer          | Anywhere in the World | weworkremotely

13 jobs matched out of 208 scraped  (13 new since last run)
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
KEYWORDS = {              # the skills gate - only these can qualify a job
    "python": 14,
    "machine learning": 14,
    "full stack": 13,
    "react": 12,
    "ai": 12,             # safe: whole-word, so it will not match "email"
}

LEVEL_KEYWORDS = {        # bonus only, applied after the gate
    "fresher": 14,
    "junior": 12,
}

BLOCKLIST = ["senior", "manager", "architect", "content writer"]

MIN_KEYWORD_SCORE = 4     # skills bar, checked before any bonus
MIN_SCORE = 6             # total bar, after level and location bonuses

REQUIRE_LOCATION_MATCH = True   # drop jobs that will not hire from India
```

Currently tuned for **AI, web development and general software roles**.
Adjust the numbers to match the jobs you actually want — that is what turns
this from a demo into a tool.

Too few results? Lower `MIN_SCORE`, or set `REQUIRE_LOCATION_MATCH = False`.

**After a big retune, reset your history.** `data/jobs.csv` keeps every job
it has ever seen, scored under whatever rules were in force at the time. So
jobs your new filters would reject can linger there. Delete `data/jobs.csv`
and `data/jobs.xlsx` and run again for a clean slate - everything gets
re-scraped and re-scored under the current rules.


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

## Phone alerts and the daily round-up

Two workflows run on GitHub's machines, so your laptop can be closed.

| Workflow | When | What it does |
|----------|------|--------------|
| `scan.yml` | every 2 hours | Scrapes, and pings Telegram **only if something new turned up** |
| `summary.yml` | 9pm IST | Sends what you applied to today, and what is still waiting |

Silence means nothing changed. A "nothing new" message every two hours is
noise you would mute within a day.

Two hours rather than one is deliberate: job boards do not post that
often, so an hourly scan would spend most of its runs finding nothing.

### Setting up Telegram (about five minutes, free)

WhatsApp needs Meta business verification or a paid Twilio account whose
free sandbox disconnects every 72 hours. Telegram bots are free and just
keep working - and the push notification lands on your phone the same way.

1. Open Telegram, search for **@BotFather**, send `/newbot`
2. Pick a name, then a username ending in `bot`
3. Copy the token he gives you
4. Send any message to your new bot, so it is allowed to reply
5. Run `python notify.py --setup` - it finds your chat id for you
6. Save both values in `telegram_key.txt`, token on line 1, chat id on line 2
7. Test with `python notify.py --test`

For the cloud runs, add the same two values as repository secrets named
`TELEGRAM_BOT_TOKEN` and `TELEGRAM_CHAT_ID`, under
**Settings → Secrets and variables → Actions**. Adzuna goes in the same
place as `ADZUNA_APP_ID` and `ADZUNA_APP_KEY`. Anything missing simply
switches that feature off - nothing crashes.

`telegram_key.txt` is gitignored, like the Adzuna key.

---

## Tracking what you have applied to

JobRadar cannot know you applied to something - nothing visible from the
outside says whether you filled in a form on a company website. So you tell
it, and the evening summary reports it back.

Open **`data/jobs.xlsx`**. Column A is **status**, a dropdown with three
choices:

| Status | Meaning |
|--------|---------|
| `new` | where every job starts |
| `applied` | you sent an application |
| `skipped` | you looked and decided no |

Pick one, save, and that is it. Scans rewrite that file every two hours but
your choices are read back first and preserved, so they survive.

Want the cloud summary to know too? Commit and push the file:

```bash
git add -f data/jobs.xlsx data/jobs.csv
git commit -m "Applied to a few"
git push
```

See it any time without waiting for 9pm:

```bash
python summary.py --print
```

---

## Tests

```bash
python -m pytest
```

```
75 passed
```

75 tests covering scoring, whole-word matching, the blocklist, the level and
location rules, the ID fingerprints, and a full save-and-read-back round
trip. They use temporary folders, so running them never touches your real
`data/`. Several are named after bugs that actually happened — see below.

---

## How scoring works: three tiers

The single most important idea in this project. A job is judged on three
separate things, and **only the first one can qualify it**:

| Tier | Source | Role |
|------|--------|------|
| **Skills** | `KEYWORDS` | The gate. Fail here and you are out. |
| **Level** | `LEVEL_KEYWORDS` | Bonus only. Applied after the gate. |
| **Location** | `LOCATION_KEYWORDS` | Bonus, plus a hard filter on countries. |

Both bonus tiers started life inside `KEYWORDS`, and both caused the same
bug: something that was not a software job climbed to the top of the list
by scoring on a tier that says nothing about the work. Being in Bengaluru
is not a skill. Being a fresher is not a skill.

---

## Five problems worth writing about

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

**"Fresher" is not a job description.** Same bug, third appearance. Once
level words like `fresher` and `entry level` were keywords, a **"Content
Writer (Fresher / Entry Level)"** scored 41 and a **"CA Fresher (Stat
Audit)"** — an accounting role — scored 29. Neither involves writing code.
Level words moved into their own tier, applied only after the skills gate.
Noticing it was the *same* mistake as the Chennai one is the useful part:
any tier that describes something other than the work has to be a bonus.

**Substring matching quietly breaks short keywords.** Adding AI keywords
meant adding `"ai"` — which, with plain `in` matching, appears inside
**em*ai*l**, **tr*ai*ning** and **m*ai*ntenance**. There was already an
"Email Developer" in the results that would have scored as an AI role.
`"ml"` matched **HT*ML***, and `"java"` matched **javascript** — two
different languages. Fixed by matching on word boundaries with
`\bword\b`, which also retired an earlier hack where the blocklist stored
`"lead "` with a trailing space to avoid hitting "leadership".

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
