"""
scrapers.py - The code that visits job sites and reads the listings.

There are six scrapers in here, covering the three formats you meet in the
real world - a JSON API, an RSS feed, and raw HTML:

    1. remoteok        JSON API   global remote jobs
    2. weworkremotely  RSS (XML)  global remote jobs
    3. remotive        JSON API   remote jobs, says which countries can apply
    4. himalayas       JSON API   remote jobs, gives seniority level too
    5. adzuna          JSON API   REAL jobs in Indian cities (needs free key)
    6. fakejobs        raw HTML   practice data, off by default

The important idea: no matter which format a site uses, every scraper here
returns the SAME shape of data (see make_job below). That way the rest of
the program never has to care where a job came from. Adding a seventh
source means writing one function and adding one line to SCRAPERS.

A note on which sites are in this list. Naukri, LinkedIn, Indeed and
Internshala are deliberately absent. Their robots.txt files and terms of
service forbid automated access - Naukri's robots.txt blocks bots by name
with "Disallow: /". Scraping them would get your IP banned and is not
something you would want to defend in an interview. Every source here
either publishes an open API or an RSS feed meant to be read by programs.
"""

import html
import os
import time
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime

import requests
from bs4 import BeautifulSoup

import config


# ---------------------------------------------------------------------------
# Shared helpers - used by all six scrapers
# ---------------------------------------------------------------------------

def make_job(title, company, location, url, source, tags="", posted=""):
    """
    Build one job in the standard shape.

    Every scraper calls this, which guarantees every job has the same keys.
    If a site does not give us a field (say, no location), we just use "".
    """
    return {
        "title": clean(title),
        "company": clean(company),
        "location": clean(location) or "Not listed",
        "url": (url or "").strip(),
        "source": source,
        "tags": clean(tags),
        "posted": posted or "",
    }


def clean(text):
    """
    Tidy up text that came off a web page.

    Scraped text is messy: it has HTML codes like &amp; in it, plus stray
    newlines and double spaces. This fixes both.
    """
    if not text:
        return ""
    text = html.unescape(str(text))   # "H&amp;M" becomes "H&M"
    return " ".join(text.split())     # collapse newlines and extra spaces


def fetch(url):
    """
    Download a web page and hand back the response.

    Networks fail sometimes - a request times out, a site hiccups. So instead
    of giving up on the first error, we try again a few times, waiting a
    little longer each time. This is called "retrying with backoff".
    """
    last_error = None

    for attempt in range(1, config.RETRY_ATTEMPTS + 1):
        try:
            response = requests.get(
                url,
                headers=config.REQUEST_HEADERS,
                timeout=config.TIMEOUT_SECONDS,
            )
            response.raise_for_status()   # turn a 404 or 500 into an error
            return response
        except requests.RequestException as error:
            last_error = error
            if attempt < config.RETRY_ATTEMPTS:
                time.sleep(attempt * 2)   # wait 2s, then 4s, then give up

    # If we get here, every attempt failed. Tell the caller what went wrong.
    raise RuntimeError("Could not reach " + url + " - " + str(last_error))


# ---------------------------------------------------------------------------
# Scraper 1 of 6: RemoteOK  (format: JSON API)
# ---------------------------------------------------------------------------

def scrape_remoteok(limit):
    """
    Read jobs from the public RemoteOK JSON API.

    This is the easy case. The site hands us a list of Python dictionaries
    already - no HTML digging needed. We just pick the fields we want.

    Data provided by RemoteOK (https://remoteok.com), as their API terms ask.
    """
    response = fetch("https://remoteok.com/api")
    records = response.json()

    # Quirk of this API: the very first item is not a job, it is a legal
    # notice. So we skip it with [1:].
    jobs = []
    for record in records[1:]:
        # Some records are missing a title. Skip those rather than crash.
        if not record.get("position"):
            continue

        # "tags" comes back as a list like ["python", "django"].
        # Join it into one string so it is easy to save to a spreadsheet.
        tags = ", ".join(record.get("tags") or [])

        # A date looks like "2026-08-20T14:18:42+00:00".
        # The first 10 characters are the part we want: "2026-08-20".
        posted = (record.get("date") or "")[:10]

        jobs.append(make_job(
            title=record.get("position"),
            company=record.get("company"),
            location=record.get("location"),
            url=record.get("url"),
            source="remoteok",
            tags=tags,
            posted=posted,
        ))

        if len(jobs) >= limit:
            break

    return jobs


# ---------------------------------------------------------------------------
# Scraper 2 of 6: We Work Remotely  (format: RSS / XML)
# ---------------------------------------------------------------------------

def scrape_weworkremotely(limit):
    """
    Read jobs from the We Work Remotely RSS feed.

    RSS is just XML. Python can read XML without any extra library, using
    ElementTree (imported as ET at the top of this file).

    An RSS feed is a list of <item> blocks, and each <item> is one job.
    """
    response = fetch("https://weworkremotely.com/remote-jobs.rss")
    root = ET.fromstring(response.content)

    jobs = []
    for item in root.findall(".//item"):
        # .findtext() reads the text inside a tag, e.g. <title>...</title>
        raw_title = item.findtext("title") or ""

        # This feed writes titles as "Company Name: Job Title".
        # So we split on the first ":" to pull the two pieces apart.
        if ":" in raw_title:
            company, title = raw_title.split(":", 1)
        else:
            company, title = "", raw_title

        # Combine the category and job type into our single "tags" field.
        # filter(None, ...) drops any pieces that are empty.
        tags = ", ".join(filter(None, [
            item.findtext("category"),
            item.findtext("type"),
        ]))

        jobs.append(make_job(
            title=title,
            company=company,
            location=item.findtext("region"),
            url=item.findtext("link"),
            source="weworkremotely",
            tags=tags,
            posted=parse_rss_date(item.findtext("pubDate")),
        ))

        if len(jobs) >= limit:
            break

    return jobs


def epoch_to_date(value):
    """
    Turn a Unix timestamp into a plain YYYY-MM-DD string.

    Some APIs send dates as text ("2026-08-20"), but others send a Unix
    timestamp - a plain number counting seconds since 1 January 1970.
    So 1787317502 is really 19 August 2026.

    Himalayas does this, and it is a good reminder to always check what
    TYPE a field is before slicing it up like text.
    """
    if not value:
        return ""
    try:
        moment = datetime.fromtimestamp(int(value), tz=timezone.utc)
        return moment.strftime("%Y-%m-%d")
    except (TypeError, ValueError, OSError):
        return ""


def parse_rss_date(raw_date):
    """
    Turn an RSS date into a plain YYYY-MM-DD string.

    RSS dates look like "Fri, 21 Aug 2026 10:40:25 +0000", which is awkward
    to sort. Python's email module happens to know that exact format.
    """
    if not raw_date:
        return ""
    try:
        return parsedate_to_datetime(raw_date).strftime("%Y-%m-%d")
    except (TypeError, ValueError):
        return ""   # an unreadable date is not worth crashing over


# ---------------------------------------------------------------------------
# Scraper 3 of 6: Fake Jobs  (format: raw HTML)
# ---------------------------------------------------------------------------

def scrape_fakejobs(limit):
    """
    Read jobs by scraping raw HTML with BeautifulSoup.

    This is the classic "web scraping" case: there is no API, so we download
    the page and pick the data out of the HTML tags ourselves.

    The site is realpython.github.io/fake-jobs - a practice board built by
    Real Python so people can learn scraping without hammering a real
    company's servers or breaking anyone's terms of service.

    How to work out the tag names yourself: open the page in Chrome,
    right-click on a job card, and choose "Inspect".
    """
    response = fetch("https://realpython.github.io/fake-jobs/")

    # BeautifulSoup turns a wall of HTML text into something searchable.
    soup = BeautifulSoup(response.text, "html.parser")

    jobs = []
    # On this site every job sits inside <div class="card-content">
    for card in soup.select("div.card-content"):
        title_tag = card.select_one("h2.title")
        company_tag = card.select_one("h3.company")
        location_tag = card.select_one("p.location")
        date_tag = card.select_one("time")

        # A card with no title is not a real job card, so skip it.
        if not title_tag:
            continue

        # The "Apply" button is the last link in the card footer.
        apply_links = card.select("footer a")
        url = apply_links[-1].get("href") if apply_links else ""

        jobs.append(make_job(
            title=title_tag.get_text(),
            company=company_tag.get_text() if company_tag else "",
            location=location_tag.get_text() if location_tag else "",
            url=url,
            source="fakejobs",
            tags="",   # this site does not provide tags
            posted=date_tag.get("datetime") if date_tag else "",
        ))

        if len(jobs) >= limit:
            break

    return jobs


# ---------------------------------------------------------------------------
# Scraper 4 of 6: Remotive  (format: JSON API)
# ---------------------------------------------------------------------------

def scrape_remotive(limit):
    """
    Read jobs from the public Remotive API.

    Remotive is worth having because of one field the others do not give us:
    candidate_required_location. It says which countries a company will
    actually hire from - "Worldwide", "USA", "India", and so on.

    That matters a lot when you are applying from India. A brilliant remote
    job that says "USA only" is a dead end, and this field is what lets
    filters.py spot that before you waste time on it.
    """
    response = fetch("https://remotive.com/api/remote-jobs?limit=" + str(limit))
    records = response.json().get("jobs", [])

    jobs = []
    for record in records[:limit]:
        if not record.get("title"):
            continue

        jobs.append(make_job(
            title=record.get("title"),
            company=record.get("company_name"),
            # This is the "who can apply" field, not an office address.
            location=record.get("candidate_required_location"),
            url=record.get("url"),
            source="remotive",
            tags=", ".join(filter(None, [
                record.get("category"),
                record.get("job_type"),
            ])),
            posted=(record.get("publication_date") or "")[:10],
        ))

    return jobs


# ---------------------------------------------------------------------------
# Scraper 5 of 6: Himalayas  (format: JSON API)
# ---------------------------------------------------------------------------

def scrape_himalayas(limit):
    """
    Read jobs from the public Himalayas API.

    Like Remotive, this one tells us who is allowed to apply - here the
    field is called locationRestrictions, and it is a LIST of places rather
    than a single string, so we join it up.

    It also gives us a seniority level, which is useful: it means the
    blocklist in config.py can catch senior roles even when the job title
    does not contain the word "senior".
    """
    url = "https://himalayas.app/jobs/api?limit=" + str(limit)
    records = fetch(url).json().get("jobs", [])

    jobs = []
    for record in records[:limit]:
        if not record.get("title"):
            continue

        # locationRestrictions looks like ["India", "Worldwide"].
        # An empty list means there is no restriction at all.
        restrictions = record.get("locationRestrictions") or []
        location = ", ".join(restrictions) if restrictions else "Worldwide"

        # seniority is also a list, e.g. ["Entry-level", "Mid-level"]
        seniority = record.get("seniority") or []

        jobs.append(make_job(
            title=record.get("title"),
            company=record.get("companyName"),
            location=location,
            url=record.get("applicationLink") or record.get("guid"),
            source="himalayas",
            tags=", ".join(filter(None,
                (record.get("categories") or []) + seniority
            )),
            posted=epoch_to_date(record.get("pubDate")),
        ))

    return jobs


# ---------------------------------------------------------------------------
# Scraper 6 of 6: Adzuna India  (format: JSON API, needs a free key)
# ---------------------------------------------------------------------------

def scrape_adzuna(limit):
    """
    Read real jobs based in INDIA from the official Adzuna API.

    This is the only source here that returns jobs in actual Indian cities -
    Bengaluru, Hyderabad, Pune, Chennai, Mumbai - rather than global remote
    roles. It is the answer to "show me jobs near me".

    It is also the only source that needs a key, because Adzuna asks you to
    register so they can see who is using their API. It is free and takes
    about two minutes:

        1. Go to https://developer.adzuna.com/
        2. Sign up and create an app
        3. Copy your Application ID and Application Key
        4. Paste them into a file called adzuna_key.txt in this folder,
           on two lines:

               your_app_id
               your_app_key

    If that file is missing we raise a clear message instead of crashing,
    and scrape_all just carries on with the other five sources.
    """
    app_id, app_key = load_adzuna_key()

    # Adzuna wants search terms. Rather than hard-coding any, we send your
    # five highest-scoring keywords from config.py, so this source follows
    # whatever you are actually looking for.
    top_keywords = sorted(config.KEYWORDS, key=config.KEYWORDS.get, reverse=True)
    search_terms = " ".join(top_keywords[:5])

    # The "in" in this URL is the country code for India. Change it to "gb"
    # or "us" if you ever want to search a different country.
    url = (
        "https://api.adzuna.com/v1/api/jobs/in/search/1"
        "?app_id=" + app_id +
        "&app_key=" + app_key +
        "&results_per_page=" + str(min(limit, 50)) +
        "&what_or=" + requests.utils.quote(search_terms) +
        "&content-type=application/json"
    )

    records = fetch(url).json().get("results", [])

    jobs = []
    for record in records[:limit]:
        if not record.get("title"):
            continue

        # company and location arrive as small nested dictionaries,
        # e.g. {"display_name": "Infosys"}
        company = (record.get("company") or {}).get("display_name", "")
        location = (record.get("location") or {}).get("display_name", "")
        category = (record.get("category") or {}).get("label", "")

        jobs.append(make_job(
            title=record.get("title"),
            company=company,
            location=location,
            url=record.get("redirect_url"),
            source="adzuna",
            tags=category,
            posted=(record.get("created") or "")[:10],
        ))

    return jobs


def load_adzuna_key():
    """
    Read the Adzuna app id and key.

    We look in two places, so this works both on your laptop and later on a
    server like GitHub Actions:

        1. environment variables ADZUNA_APP_ID and ADZUNA_APP_KEY
        2. a plain text file called adzuna_key.txt

    Keys go in a file or an environment variable, NEVER typed into the code
    itself - because code gets pushed to GitHub, and anything you commit is
    public forever. adzuna_key.txt is listed in .gitignore for exactly that
    reason.
    """
    app_id = os.environ.get("ADZUNA_APP_ID", "").strip()
    app_key = os.environ.get("ADZUNA_APP_KEY", "").strip()

    if app_id and app_key:
        return app_id, app_key

    key_file = "adzuna_key.txt"
    if os.path.exists(key_file):
        with open(key_file, encoding="utf-8") as file:
            # Ignore blank lines so a stray newline does not break things
            lines = [line.strip() for line in file if line.strip()]
        if len(lines) >= 2:
            return lines[0], lines[1]

    raise RuntimeError(
        "no Adzuna key - add adzuna_key.txt (see README), skipping this source"
    )


# ---------------------------------------------------------------------------
# The registry - connects the names in config.py to the functions above
# ---------------------------------------------------------------------------

SCRAPERS = {
    "remoteok": scrape_remoteok,
    "weworkremotely": scrape_weworkremotely,
    "remotive": scrape_remotive,
    "himalayas": scrape_himalayas,
    "adzuna": scrape_adzuna,
    "fakejobs": scrape_fakejobs,   # practice data - off by default
}


def scrape_all(sources, limit, on_status=None):
    """
    Run several scrapers and glue their results into one big list.

    The key detail here: if one site is down, we do NOT want the whole
    program to crash. So each scraper runs inside try/except. A broken site
    just contributes zero jobs, and we carry on with the rest.

    on_status is an optional function we call with progress messages, so
    main.py can print them however it likes.
    """
    all_jobs = []

    for name in sources:
        scraper = SCRAPERS.get(name)

        if scraper is None:
            if on_status:
                on_status(name, "error", "No scraper named " + name + " exists")
            continue

        try:
            found = scraper(limit)
            all_jobs.extend(found)
            if on_status:
                on_status(name, "ok", str(len(found)) + " jobs")
        except Exception as error:
            # Catching broad Exception on purpose: one misbehaving website
            # should never take down the whole run.
            if on_status:
                on_status(name, "error", str(error)[:80])

    return all_jobs
