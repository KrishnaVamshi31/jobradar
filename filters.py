"""
filters.py - Decides which jobs are worth your time, and ranks them.

Scraping gives you hundreds of jobs. Most of them are irrelevant. This file
is what turns "300 random jobs" into "12 jobs I should actually look at".

The logic has three steps:

    1. SCORE   - award points when a job matches your keywords
    2. BLOCK   - throw out jobs containing words you never want to see
    3. RANK    - sort what is left, best score first

All the keywords and blocked words live in config.py, so you can tune your
job search without touching any code in here.
"""

import re


def matches(word, text):
    """
    Check whether `word` appears in `text` as a WHOLE word.

    Why not just write `word in text`? Because plain substring matching is a
    trap for short keywords, and we hit it for real:

        "ai"   is inside "em-ai-l", "tr-ai-ning", "m-ai-ntenance"
        "ml"   is inside "HT-ML"
        "java" is inside "javascript"
        "go"   is inside "algorithm"

    An "Email Developer" job was already showing up in the results, and
    adding "ai" as a keyword would have scored it as an AI role.

    \\b means "word boundary" - the edge between a letter and a non-letter.
    So \\bai\\b matches "AI Engineer" but not "Email Developer", and
    \\bjava\\b matches "Java Developer" but not "JavaScript Developer".

    re.escape() is there so that keywords containing punctuation, like
    "node.js", are treated as literal text rather than regex symbols.

    One wrinkle, found the hard way. A \\b boundary only exists next to a
    LETTER or DIGIT. So keywords that start or end with punctuation were
    silently never matching anything:

        "c++"   ended with "+"  ->  never matched "C++ Developer"
        "c#"    ended with "#"  ->  never matched "C# Developer"
        ".net"  started with "." ->  never matched ".NET Developer"

    They failed quietly, which is the worst way to fail - no error, the jobs
    just never scored. So we only add \\b on an edge that is actually a
    letter or digit.
    """
    prefix = r"\b" if word[:1].isalnum() else ""
    suffix = r"\b" if word[-1:].isalnum() else ""

    pattern = prefix + re.escape(word) + suffix
    return re.search(pattern, text) is not None


def score_job(job, keywords):
    """
    Give one job a score based on how many of your keywords it matches.

    Returns two things:
        - the total score (a number)
        - the list of words that matched (so we can show you WHY it scored)

    A match in the TITLE is worth full points. A match only in the tags or
    location is worth HALF points.

    Why the difference? Some job boards tag their listings very loosely.
    A warehouse "Laborer" job on RemoteOK came back tagged with "engineer",
    "data" and 18 other words, which made it outrank real Python jobs. The
    title is the honest signal, so we trust it more than the tags.

    Example: "Junior Python Developer" tagged "django, api" scores
    python(10) + junior(6) + developer(4) from the title, plus half points
    for django(2) and api(1) from the tags, giving 23.
    """
    title = job.get("title", "").lower()

    # Everything else we are willing to search, as one lowercase blob.
    extra = (job.get("tags", "") + " " + job.get("location", "")).lower()

    total = 0
    matched = []
    counted = []      # the keyword texts we have already scored

    # Longest keywords first. That order is what makes the overlap check
    # below work: "software engineer" gets considered before "software".
    for word in sorted(keywords, key=len, reverse=True):
        points = keywords[word]
        word = word.lower()

        # Skip a keyword that is just a piece of one we already counted.
        #
        # Without this, the title "Software Engineer" scores three times for
        # a single phrase - once for "software engineer", again for
        # "software", again for "engineer". That inflation made
        # "Java Software Engineer" outrank "Machine Learning Engineer",
        # which is backwards if AI is what you actually want.
        if any(word in bigger for bigger in counted):
            continue

        # Whole-word match, so "ai" cannot match "email". See matches().
        if matches(word, title):
            total += points
            matched.append(word)
            counted.append(word)
        elif matches(word, extra):
            total += points // 2      # // divides and rounds down
            matched.append(word + " (tag)")
            counted.append(word)

    return total, matched


def is_blocked(job, blocklist):
    """
    Return True if this job contains a word you never want to see.

    We only check the TITLE here, on purpose. If we searched the whole job
    the word "senior" would appear in loads of postings that are actually
    fine (for example "you will report to a senior engineer").
    """
    title = job.get("title", "").lower()

    for word in blocklist:
        if matches(word.lower(), title):
            return True

    return False


def score_location(job, location_keywords):
    """
    Score a job on WHERE it is, separately from what it is.

    A remote job is only useful if the company will hire from your country.
    Real examples pulled from these APIs:

        "Anywhere in the World"          -> great, you can apply
        "APAC"                           -> includes India, fine
        "Bengaluru, Karnataka"           -> an actual job in India
        "Americas, Europe, Israel"       -> quietly means no India
        "United States"                  -> no

    Returns the points earned and the words that matched. Zero points means
    the location did not mention anywhere you can work from.
    """
    if not location_keywords:
        return 0, []

    location = job.get("location", "").lower()

    total = 0
    matched = []

    for word, points in location_keywords.items():
        if matches(word.lower(), location):
            total += points
            matched.append(word)

    return total, matched


def location_is_usable(job, location_keywords):
    """
    Decide whether a job is somewhere you could actually work.

    Note the deliberate choice about missing data: if a site gave us no
    location at all, we say YES and keep the job. Unknown is not the same
    as "no", and throwing away a job because a website left a field blank
    would lose you real opportunities.
    """
    location = job.get("location", "").strip().lower()

    # "Not listed" is what make_job() fills in when a site gives us nothing.
    if not location or location == "not listed":
        return True

    points, _ = score_location(job, location_keywords)
    return points > 0


# Matches a number of years, optionally as a range:
#   "5 years"  "5+ years"  "2-3 years"  "1 to 3 years"  "3–5 yrs"
YEARS_PATTERN = re.compile(
    r"(\d{1,3})\s*\+?\s*"                 # the first number, maybe with a +
    r"(?:(?:[-–—]|to|and)\s*(\d{1,3})\s*\+?\s*)?"   # optionally "-5" or "to 5"
    r"(?:years?|yrs?)\b",
    re.IGNORECASE,
)

# A personal experience requirement is realistically under this. Anything
# larger is the company talking about itself - a real listing said
# "over 130 years of baking experience", which is heritage, not a demand.
MAX_PLAUSIBLE_YEARS = 20

# How far either side of a "N years" phrase we look for the word
# "experience". Without this check, "2 years" in any context would count.
EXPERIENCE_WINDOW = 60


def required_years(description):
    """
    Work out the minimum years of experience a job description asks for.

    Returns a number, or None when the description does not mention any
    requirement. None means "we do not know" - and unknown is NOT the same
    as "too senior", so those jobs are kept. Same principle as a missing
    location.

    Real phrasings this handles, all taken from actual listings:

        "Experience: 5+ Years"                  -> 5
        "6+ years of proven experience in GRC"  -> 6
        "2-3 years of experience in retail"     -> 2   (the lower bound)
        "1 to 3 years of Technician experience" -> 1
        "At least 5 years of sales experience"  -> 5
        "Experience 1 year to less than 2 years"-> 1

    Two deliberate choices:

    Ranges take the LOWER number, because "2-3 years" means they will look
    at you with two.

    When several requirements appear, we take the SMALLEST. A posting
    saying "2+ years with Python, 5+ years leadership preferred" really
    has a bar of two, and over-filtering costs you real opportunities.
    """
    if not description:
        return None

    text = str(description)
    found = []

    for match in YEARS_PATTERN.finditer(text):
        # Look at the words around this phrase. If nobody mentions
        # experience nearby, this is some other use of "years".
        start = max(0, match.start() - EXPERIENCE_WINDOW)
        end = min(len(text), match.end() + EXPERIENCE_WINDOW)
        context = text[start:end].lower()

        if "experien" not in context and "exp." not in context:
            continue

        low = int(match.group(1))

        # For a range, the lower bound is the real bar. The pattern puts
        # the second number in group(2) when there is one.
        if match.group(2):
            low = min(low, int(match.group(2)))

        # Skip company-history numbers like "130 years of experience".
        if low > MAX_PLAUSIBLE_YEARS:
            continue

        found.append(low)

    return min(found) if found else None


def experience_is_ok(job, max_years):
    """
    True if this job is open to someone with your level of experience.

    Jobs that never state a requirement are kept. Most listings that want a
    fresher simply do not talk about years at all, so treating silence as
    disqualifying would throw away exactly the jobs you want.
    """
    if max_years is None:
        return True

    needed = required_years(job.get("description", ""))

    if needed is None:
        return True

    return needed <= max_years


def score_level(job, level_keywords):
    """
    Score a job on how junior it is, separately from what it is.

    This is a BONUS, never a qualification. "Fresher" tells you the level of
    a role but nothing about the work - a "Content Writer (Fresher)" and a
    "CA Fresher (Stat Audit)" both scored highly when level words counted
    towards the skills gate, despite neither being a software job.
    """
    if not level_keywords:
        return 0, []

    haystack = (job.get("title", "") + " " + job.get("tags", "")).lower()

    total = 0
    matched = []

    for word, points in level_keywords.items():
        if matches(word.lower(), haystack):
            total += points
            matched.append(word)

    return total, matched


def filter_jobs(jobs, keywords, blocklist, min_score,
                location_keywords=None, require_location=False,
                min_keyword_score=0, level_keywords=None,
                max_years=None):
    """
    Run the whole pipeline: score everything, drop the junk, sort the rest.

    Each job that survives comes back with two NEW keys added to it:
        score    - the number it earned
        matched  - the keywords that got it there

    The order of the checks below matters. Skills are tested BEFORE location
    points get added, so that being in a convenient city can never rescue a
    job you are not suited for. Location can only improve the ranking of a
    job that already passed on merit.

    The location arguments are optional. Leave them out and this behaves
    exactly as it did before, scoring on the title and tags only.

    The jobs come back sorted with the best score first.
    """
    kept = []

    for job in jobs:
        # Step 1: skip anything on the blocklist, no matter how well it scores
        if is_blocked(job, blocklist):
            continue

        # Step 2: skip jobs you could not take because of where they are
        if require_location and not location_is_usable(job, location_keywords):
            continue

        # Step 2b: skip jobs asking for more experience than you have.
        #
        # This reads the DESCRIPTION, not the title. A job called plainly
        # "Software Engineer" can still say "5+ years required" several
        # paragraphs down, and the title-only blocklist never saw it.
        if not experience_is_ok(job, max_years):
            continue

        # Step 3: score the actual job - is this the kind of work you want?
        score, matched = score_job(job, keywords)

        # Step 4: the skills gate. Fail here and no amount of location
        # bonus can save it.
        if score < min_keyword_score:
            continue

        # Step 5: add the bonuses on top - experience level, then location.
        # Both only ever ADD to a job that already passed the skills gate.
        level_points, level_matched = score_level(job, level_keywords)
        score += level_points
        matched.extend(word + " (level)" for word in level_matched)

        location_points, location_matched = score_location(job, location_keywords)
        score += location_points
        matched.extend(place + " (place)" for place in location_matched)

        # Step 6: skip anything that did not clear the overall bar
        if score < min_score:
            continue

        # Copy the job before adding to it, so we never modify the original.
        # This is a good habit - it stops surprise bugs elsewhere.
        scored_job = dict(job)
        scored_job["score"] = score
        scored_job["matched"] = ", ".join(matched)

        # Record what the description asked for, so you can see it in the
        # spreadsheet rather than having to trust the filter blindly.
        # Blank means the posting never mentioned a number.
        years = required_years(job.get("description", ""))
        scored_job["years_required"] = "" if years is None else years

        kept.append(scored_job)

    # Sort by score, highest first.
    # reverse=True means descending. The "key" tells sort what to look at.
    kept.sort(key=lambda job: job["score"], reverse=True)

    return kept


def summarise(all_jobs, kept_jobs):
    """
    Build a small dictionary of stats about the run, for the report.

    Nothing clever here - just counting - but having the numbers in one
    place keeps main.py tidy.
    """
    # Count how many kept jobs came from each source.
    by_source = {}
    for job in kept_jobs:
        source = job.get("source", "unknown")
        by_source[source] = by_source.get(source, 0) + 1

    return {
        "scraped": len(all_jobs),
        "kept": len(kept_jobs),
        "dropped": len(all_jobs) - len(kept_jobs),
        "by_source": by_source,
        "top_score": kept_jobs[0]["score"] if kept_jobs else 0,
    }
