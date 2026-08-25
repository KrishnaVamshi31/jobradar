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
    "jobspresso",      # Curated remote jobs     - public RSS feed
    "workingnomads",   # Remote jobs, many categories - open JSON API

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
    # --- AI and machine learning: your top priority ---------------------
    # These are scored roughly double the general software words, so an AI
    # role always outranks an equally good plain-software one.
    "machine learning": 35,
    "artificial intelligence": 35,
    "deep learning": 34,
    "generative ai": 34,
    "data scientist": 34,
    "data science": 34,
    "computer vision": 33,
    "genai": 33,
    "llm": 33,
    "nlp": 32,
    "ai": 30,
    "ml": 28,
    "pytorch": 28,
    "tensorflow": 28,
    "neural": 28,
    "data engineer": 24,
    "prompt engineer": 24,

    # --- Web development ------------------------------------------------
    "full stack": 14,
    "fullstack": 14,
    "web developer": 14,
    "react": 13,
    "frontend": 12,
    "front end": 12,
    "backend": 12,
    "back end": 12,
    "django": 12,
    "javascript": 11,
    "typescript": 11,
    "node.js": 11,
    "nodejs": 11,
    "node": 10,
    "next.js": 10,
    "angular": 10,
    "vue": 10,
    "flask": 10,
    "fastapi": 10,
    "html": 7,
    "css": 7,
    "api": 6,

    # --- Any software job -----------------------------------------------
    # Broad on purpose: you said any software role counts, so most common
    # languages and specialisms are here.
    "python": 16,
    "software engineer": 14,
    "software developer": 14,
    "sde": 14,             # standard Indian job-ad shorthand
    "programmer": 12,
    "software": 10,
    "developer": 10,
    "java": 11,            # whole-word, so this will NOT match "javascript"
    "c++": 11,             # punctuation keywords work - see matches()
    "c#": 11,
    ".net": 11,
    "golang": 11,
    "kotlin": 11,
    "swift": 11,
    "php": 10,
    "ruby": 10,
    "rust": 10,
    "android": 11,
    "ios": 11,
    "mobile developer": 12,
    "devops": 12,
    "cloud": 10,
    "aws": 10,
    "azure": 10,
    "docker": 9,
    "kubernetes": 9,
    "sql": 9,
    "database": 8,
    "automation": 9,
    "qa": 8,
    "testing": 7,
    "git": 6,
    "engineer": 4,
}


# Experience-level words live in their OWN list, not in KEYWORDS above.
#
# Here is why. When "fresher" was a normal keyword, a "Content Writer
# (Fresher / Entry Level)" job scored 41 and a "CA Fresher (Stat Audit)"
# accounting job scored 29 - both purely on level words, with nothing
# technical about them.
#
# Being junior is not a job description. So these are a BONUS applied only
# after a job has already proved it is technical, exactly like the location
# bonus below.
LEVEL_KEYWORDS = {
    "fresher": 20,       # very common phrasing in Indian job ads
    "entry level": 20,
    "graduate trainee": 18,
    "junior": 18,
    "trainee": 16,
    "intern": 16,
    "internship": 16,
    "graduate": 14,
    "0-1 years": 14,
    "0-2 years": 14,
    "associate": 8,
}

# Words that get a job thrown out no matter how good its score is.
# These are matched as whole words too, so "lead" will not hit "leadership".
BLOCKLIST = [
    # --- too senior for you right now ---
    "senior", "sr", "staff", "principal", "lead", "manager", "director",
    "head of", "vp", "avp", "svp", "vice president", "chief", "architect",
    "10+ years",

    # --- not software, but kept sneaking into the results ---
    # A "Junior Architect" in Chandigarh scored 36 before this list existed.
    # It was a building architect, not a software one.
    "civil", "mechanical", "electrical", "structural", "precast",
    "costing", "laborer", "welder", "nurse", "teacher", "chef",
    "driver", "accountant", "recruiter", "warehouse", "maintenance",

    # --- tech-adjacent but not writing code ---
    # These slipped in by matching "ai" or "engineer": a "Technical Product
    # Marketer - K0rdent AI" is not a software job, whatever it matches.
    "marketer", "marketing", "sales", "trainer", "scrum master",
    "product manager", "product owner", "customer success",
    "service desk", "help desk", "support specialist",

    # --- matched level words like "fresher" but are not software ---
    "content writer", "copywriter", "professor", "lecturer", "tutor",
    "audit", "auditor", "chartered accountant", "recruitment",
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
#
# Set to 6 rather than 4 deliberately: "engineer" on its own is worth 4, and
# at 4 that let in "Jr. Engineer Thermo Forming Machine Maintenance" - a
# factory job. One generic word should not be enough to qualify. Anything
# real ("developer" 8, "python" 14, "full stack" 13) still clears it easily.
MIN_KEYWORD_SCORE = 6

# The most years of experience a job may ask for before we drop it.
#
# This one reads the job DESCRIPTION, not the title. A posting called plainly
# "Software Engineer" can still demand "5+ years" three paragraphs down, and
# the blocklist above only ever sees titles.
#
# Jobs that never mention a number are KEPT - most listings aimed at freshers
# simply do not talk about years, so treating silence as a rejection would
# throw away exactly the jobs you want. Set to None to switch this off.
#
# Set to 3 rather than 2 on purpose. Ranges are read at their LOWER bound,
# so a "2-3 years" job already passed at 2. Going to 3 additionally lets
# through postings that ask for "3+ years" or "3-5 years", which routinely
# still interview a strong fresher - the number in an ad is usually a wish,
# not a rule. Raise it further if you want an even wider net.
MAX_YEARS_EXPERIENCE = 3

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
