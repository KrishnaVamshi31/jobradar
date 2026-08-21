"""
config.py - All of JobRadar's settings live here.

This is the ONLY file you need to edit to change how JobRadar behaves.
You never have to touch the other files to change your job search.

Open this, change the values, save, and re-run `python main.py`.
"""

# ---------------------------------------------------------------------------
# 1. WHICH JOB SITES TO CHECK
# ---------------------------------------------------------------------------
# Each name here matches a scraper in scrapers.py.
# To stop using a site, delete its line (or put a # in front of it).
SOURCES = [
    "remoteok",        # Global remote jobs      - public JSON API
    "weworkremotely",  # Global remote jobs      - public RSS feed
    "remotive",        # Remote jobs, tells us which countries can apply
    "himalayas",       # Remote jobs, includes the seniority level
    "adzuna",          # REAL jobs in Indian cities - needs a free key, see README

    # "fakejobs",      # Practice data from Real Python. Not real jobs - you
                       # cannot apply to them. Turn this on only if you want
                       # to demo the HTML scraping without hitting live sites.
]

# How many jobs to pull from EACH source on every run.
# Keep this small (like 20) while you are testing, then raise it.
JOBS_PER_SOURCE = 60


# ---------------------------------------------------------------------------
# 2. WHAT MAKES A JOB INTERESTING TO YOU
# ---------------------------------------------------------------------------
# A job earns points when one of these words shows up in its title or tags.
# Higher points = higher up in your report.
#
# Edit this dictionary to match YOUR job hunt. That is the whole point.
#   - Words you really want   -> big number  (10)
#   - Words that are a bonus  -> small number (2 or 3)
# Keywords are matched as WHOLE WORDS, so short ones like "ai" and "ml" are
# safe here - "ai" will not match "email" or "training". See matches() in
# filters.py for why that mattered.
KEYWORDS = {
    # --- AI and machine learning ---------------------------------------
    "machine learning": 14,
    "artificial intelligence": 14,
    "ai": 12,
    "genai": 12,
    "generative ai": 12,
    "llm": 12,
    "deep learning": 12,
    "ml": 10,
    "nlp": 10,
    "computer vision": 10,
    "data science": 10,
    "data scientist": 10,
    "pytorch": 10,
    "tensorflow": 10,

    # --- Web development ------------------------------------------------
    "full stack": 13,
    "fullstack": 13,
    "web developer": 13,
    "react": 12,
    "frontend": 11,
    "front end": 11,
    "backend": 11,
    "back end": 11,
    "javascript": 10,
    "typescript": 10,
    "node": 10,
    "nodejs": 10,
    "django": 10,
    "angular": 8,
    "vue": 8,
    "flask": 8,
    "fastapi": 8,
    "api": 5,

    # --- Core software --------------------------------------------------
    "python": 14,
    "software engineer": 13,
    "software developer": 13,
    "software": 8,
    "programmer": 9,
    "developer": 8,
    "java": 8,           # whole-word, so this will NOT match "javascript"
    "sql": 6,
    "aws": 6,
    "docker": 6,
    "engineer": 4,

    # --- Your experience level -------------------------------------------
    # You are early career, so these matter as much as the tech words.
    "fresher": 14,       # very common phrasing in Indian job ads
    "junior": 12,
    "intern": 12,
    "internship": 12,
    "entry level": 12,
    "trainee": 12,
    "graduate": 10,
    "associate": 6,
}

# Words that get a job thrown out no matter how good its score is.
# These are matched as whole words too, so "lead" will not hit "leadership".
BLOCKLIST = [
    # --- too senior for you right now ---
    "senior", "sr", "staff", "principal", "lead", "manager", "director",
    "head of", "vp", "vice president", "chief", "architect",
    "10+ years",

    # --- not software, but kept sneaking into the results ---
    # A "Junior Architect" in Chandigarh scored 36 before this list existed.
    # It was a building architect, not a software one.
    "civil", "mechanical", "electrical", "structural", "precast",
    "costing", "laborer", "welder", "nurse", "teacher", "chef",
    "driver", "accountant", "recruiter", "warehouse",

    # --- tech-adjacent but not writing code ---
    # These slipped in by matching "ai" or "engineer": a "Technical Product
    # Marketer - K0rdent AI" is not a software job, whatever it matches.
    "marketer", "marketing", "sales", "trainer", "scrum master",
    "product manager", "product owner", "customer success",
    "service desk", "help desk", "support specialist",
]

# A job must score AT LEAST this many points from its TITLE AND TAGS before
# we even look at where it is.
#
# This exists because of a real problem. Once location scoring was added, an
# "Assembly Technician" job in Chennai scored 15 points purely for being in
# India, and outranked actual Python roles. Being in the right place does
# not make it the right job.
#
# So skills are the gate, and location is only a bonus on top.
MIN_KEYWORD_SCORE = 4

# The total a job needs (keywords + location) to reach your report.
# Set both of these to 0 to keep everything and see the raw scores first.
MIN_SCORE = 6


# ---------------------------------------------------------------------------
# 2b. WHERE YOU CAN ACTUALLY WORK  (this is the India filter)
# ---------------------------------------------------------------------------
# Most "remote" jobs are not open to everyone. A posting that says
# "Remote - USA" will not hire someone applying from Chennai, and a real
# listing we pulled said "Americas, Europe, Israel" - which quietly means
# no India.
#
# So we score the LOCATION separately from the job title. Places you can
# genuinely work from score points; everywhere else scores nothing.
LOCATION_KEYWORDS = {
    # Jobs physically based in India (these come from Adzuna)
    "india": 15,
    "bengaluru": 15, "bangalore": 15, "hyderabad": 15, "pune": 15,
    "chennai": 15, "mumbai": 15, "delhi": 15, "noida": 15,
    "gurgaon": 15, "gurugram": 15, "kolkata": 15, "ahmedabad": 15,
    "coimbatore": 15, "jaipur": 15, "indore": 15, "chandigarh": 15,

    # Remote jobs that will hire from literally anywhere
    "worldwide": 12,
    "anywhere": 12,
    "global": 10,

    # Regions that include India. APAC means Asia-Pacific, so it counts.
    "apac": 10,
    "asia": 10,

    # Very weak signal - "Remote" on its own tells us nothing about country
    "remote": 2,
}

# When True, a job whose location clearly does NOT include India gets
# dropped, however good the title is. This is what stops your report
# filling up with US-only roles you cannot apply for.
#
# Jobs with no location listed at all are KEPT, because unknown is not the
# same as "no". Set this to False to see everything again.
REQUIRE_LOCATION_MATCH = True


# ---------------------------------------------------------------------------
# 3. WHERE TO SAVE THINGS
# ---------------------------------------------------------------------------
# These files get created automatically inside the data/ folder.
DATA_FOLDER = "data"
CSV_FILE = "data/jobs.csv"        # every job ever seen (your history)
EXCEL_FILE = "data/jobs.xlsx"     # same thing, nicely formatted for Excel
HTML_REPORT = "data/report.html"  # open this in your browser after a run


# ---------------------------------------------------------------------------
# 4. NETWORK SETTINGS (you probably do not need to change these)
# ---------------------------------------------------------------------------
# Some sites block requests that do not look like a real browser, so we send
# a normal-looking User-Agent header.
REQUEST_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) JobRadar/1.0",
    "Accept": "*/*",
}

TIMEOUT_SECONDS = 20  # give up on a slow site after this long
RETRY_ATTEMPTS = 3    # how many times to retry a failed request
