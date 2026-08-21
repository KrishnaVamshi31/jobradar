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

    for word, points in keywords.items():
        word = word.lower()

        # "in" checks whether the keyword appears anywhere in that text.
        if word in title:
            total += points
            matched.append(word)
        elif word in extra:
            total += points // 2      # // divides and rounds down
            matched.append(word + " (tag)")

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
        if word.lower() in title:
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
        if word.lower() in location:
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


def filter_jobs(jobs, keywords, blocklist, min_score,
                location_keywords=None, require_location=False,
                min_keyword_score=0):
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

        # Step 3: score the actual job - is this the kind of work you want?
        score, matched = score_job(job, keywords)

        # Step 4: the skills gate. Fail here and no amount of location
        # bonus can save it.
        if score < min_keyword_score:
            continue

        # Step 5: now add the location bonus on top
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
