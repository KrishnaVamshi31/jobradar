"""
Tests for filters.py - the scoring and ranking logic.

Run them all with:

    python -m pytest

A test is just a function whose name starts with test_. Inside it you set
up a situation, run your code, and "assert" what you expect to be true.
If an assert is wrong, pytest tells you exactly which line failed.

Why bother? Because the day you tweak the scoring, these tests instantly
tell you whether you broke anything. That is much faster than re-running
the scraper and squinting at the output.
"""

import sys
from pathlib import Path

# Let the tests import the project files from the folder above this one.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import filters


def make_job(title="Some Job", tags="", location="Remote"):
    """
    A tiny helper to build a fake job for testing.

    Using a helper keeps each test short and focused on the one thing it
    is actually checking.
    """
    return {
        "title": title,
        "company": "Test Co",
        "location": location,
        "tags": tags,
        "url": "https://example.com/job/1",
        "source": "test",
        "posted": "2026-01-01",
    }


KEYWORDS = {"python": 10, "junior": 6, "engineer": 4}


# ---------------------------------------------------------------------------
# score_job
# ---------------------------------------------------------------------------

def test_title_match_earns_full_points():
    job = make_job(title="Junior Python Engineer")
    score, matched = filters.score_job(job, KEYWORDS)

    assert score == 20                    # 10 + 6 + 4
    assert set(matched) == {"python", "junior", "engineer"}


def test_no_match_scores_zero():
    score, matched = filters.score_job(make_job(title="Chef"), KEYWORDS)

    assert score == 0
    assert matched == []


def test_matching_is_case_insensitive():
    """A job shouting PYTHON should score the same as one whispering python."""
    loud = filters.score_job(make_job(title="PYTHON DEVELOPER"), KEYWORDS)[0]
    quiet = filters.score_job(make_job(title="python developer"), KEYWORDS)[0]

    assert loud == quiet == 10


def test_tag_match_is_worth_half_points():
    """
    This is the "Laborer bug" test.

    A real RemoteOK listing for a warehouse Laborer job came back tagged
    with "engineer", which made it score as highly as genuine engineering
    roles. Tag matches are now worth half, so junk like this ranks lower.
    """
    job = make_job(title="Laborer", tags="engineer, data, ops")
    score, matched = filters.score_job(job, KEYWORDS)

    assert score == 2                     # engineer is 4, halved to 2
    assert matched == ["engineer (tag)"]


def test_title_beats_tags_for_the_same_word():
    in_title = filters.score_job(make_job(title="Python Dev"), KEYWORDS)[0]
    in_tags = filters.score_job(make_job(title="Dev", tags="python"), KEYWORDS)[0]

    assert in_title > in_tags


# ---------------------------------------------------------------------------
# is_blocked
# ---------------------------------------------------------------------------

def test_blocked_word_in_title_is_caught():
    assert filters.is_blocked(make_job(title="Senior Python Dev"), ["senior"])


def test_clean_title_is_not_blocked():
    assert not filters.is_blocked(make_job(title="Junior Python Dev"), ["senior"])


def test_blocklist_only_looks_at_the_title():
    """
    A job tagged "senior" but titled "Junior Developer" should survive.
    Plenty of junior postings mention senior staff in passing.
    """
    job = make_job(title="Junior Developer", tags="senior, mentoring")

    assert not filters.is_blocked(job, ["senior"])


# ---------------------------------------------------------------------------
# filter_jobs
# ---------------------------------------------------------------------------

def test_low_scoring_jobs_are_dropped():
    jobs = [
        make_job(title="Python Engineer"),   # 14
        make_job(title="Chef"),              # 0
    ]
    kept = filters.filter_jobs(jobs, KEYWORDS, blocklist=[], min_score=5)

    assert len(kept) == 1
    assert kept[0]["title"] == "Python Engineer"


def test_results_are_sorted_best_first():
    jobs = [
        make_job(title="Engineer"),          # 4
        make_job(title="Python Engineer"),   # 14
        make_job(title="Junior Engineer"),   # 10
    ]
    kept = filters.filter_jobs(jobs, KEYWORDS, blocklist=[], min_score=0)

    scores = [job["score"] for job in kept]
    assert scores == [14, 10, 4]
    assert scores == sorted(scores, reverse=True)


def test_blocked_jobs_are_dropped_even_with_a_great_score():
    jobs = [make_job(title="Senior Python Engineer")]   # would score 14
    kept = filters.filter_jobs(jobs, KEYWORDS, ["senior"], min_score=0)

    assert kept == []


def test_original_jobs_are_never_modified():
    """
    filter_jobs copies each job before adding "score" to it.

    If it did not, the caller's own data would get silently changed - the
    kind of bug that takes hours to track down.
    """
    original = make_job(title="Python Engineer")
    filters.filter_jobs([original], KEYWORDS, [], min_score=0)

    assert "score" not in original


def test_empty_input_gives_empty_output():
    """Edge case: no jobs in should mean no jobs out, not a crash."""
    assert filters.filter_jobs([], KEYWORDS, [], min_score=0) == []


# ---------------------------------------------------------------------------
# summarise
# ---------------------------------------------------------------------------

def test_summarise_counts_correctly():
    scraped = [make_job(), make_job(), make_job()]
    kept = filters.filter_jobs(
        [make_job(title="Python Engineer")], KEYWORDS, [], min_score=0
    )

    stats = filters.summarise(scraped, kept)

    assert stats["scraped"] == 3
    assert stats["kept"] == 1
    assert stats["dropped"] == 2
    assert stats["top_score"] == 14
    assert stats["by_source"] == {"test": 1}


def test_summarise_handles_no_matches():
    stats = filters.summarise([make_job()], [])

    assert stats["kept"] == 0
    assert stats["top_score"] == 0


# ---------------------------------------------------------------------------
# Location filtering - the India logic
# ---------------------------------------------------------------------------

# Mirrors LOCATION_KEYWORDS in config.py, trimmed down for testing.
PLACES = {
    "india": 15, "bengaluru": 15,
    "worldwide": 12, "anywhere": 12,   # We Work Remotely says "Anywhere in the World"
    "apac": 10, "remote": 2,
}


def test_indian_city_scores_well():
    score, matched = filters.score_location(
        make_job(location="Bengaluru, Karnataka"), PLACES
    )
    assert score == 15
    assert matched == ["bengaluru"]


def test_us_only_job_scores_nothing_on_location():
    """A real Remotive listing said "USA". That is a dead end from India."""
    score, matched = filters.score_location(make_job(location="USA"), PLACES)

    assert score == 0
    assert matched == []


def test_apac_counts_because_it_includes_india():
    score, _ = filters.score_location(make_job(location="APAC"), PLACES)
    assert score == 10


def test_us_only_job_is_not_usable():
    assert not filters.location_is_usable(make_job(location="United States"), PLACES)


def test_worldwide_job_is_usable():
    assert filters.location_is_usable(
        make_job(location="Anywhere in the World"), PLACES
    )


def test_missing_location_is_kept_not_dropped():
    """
    Unknown is not the same as "no".

    If a site left the location blank we keep the job, because throwing it
    away over a missing field would lose real opportunities.
    """
    assert filters.location_is_usable(make_job(location="Not listed"), PLACES)
    assert filters.location_is_usable(make_job(location=""), PLACES)


def test_require_location_drops_us_only_jobs():
    jobs = [
        make_job(title="Python Engineer", location="United States"),
        make_job(title="Python Engineer", location="Worldwide"),
    ]
    kept = filters.filter_jobs(
        jobs, KEYWORDS, [], min_score=0,
        location_keywords=PLACES, require_location=True,
    )

    assert len(kept) == 1
    assert kept[0]["location"] == "Worldwide"


def test_being_in_india_cannot_rescue_an_irrelevant_job():
    """
    The "Assembly Technician" test.

    A real run put an Assembly Technician job in Chennai near the top,
    because 15 location points beat genuine Python roles. Skills are now
    checked BEFORE the location bonus is added, so this cannot happen.
    """
    jobs = [make_job(title="Assembly Technician", location="Bengaluru")]

    kept = filters.filter_jobs(
        jobs, KEYWORDS, [], min_score=0,
        location_keywords=PLACES, require_location=True,
        min_keyword_score=4,
    )

    assert kept == []


def test_location_still_boosts_a_relevant_job():
    """The flip side: a job you ARE suited for should rank higher in India."""
    jobs = [make_job(title="Python Engineer", location="Bengaluru")]

    kept = filters.filter_jobs(
        jobs, KEYWORDS, [], min_score=0,
        location_keywords=PLACES, require_location=True,
        min_keyword_score=4,
    )

    assert len(kept) == 1
    assert kept[0]["score"] == 29           # 14 for skills + 15 for the city
    assert "bengaluru (place)" in kept[0]["matched"]


# ---------------------------------------------------------------------------
# Whole-word matching - short keywords like "ai" and "ml"
# ---------------------------------------------------------------------------

def test_ai_does_not_match_email():
    """
    The bug this prevents.

    An "Email Developer" job was already in the results. Adding "ai" as a
    keyword with plain substring matching would have scored it as an AI
    role, because "ai" sits inside "em-ai-l".
    """
    assert not filters.matches("ai", "email developer")
    assert not filters.matches("ai", "training specialist")
    assert not filters.matches("ai", "maintenance engineer")


def test_ai_still_matches_a_real_ai_job():
    assert filters.matches("ai", "ai engineer")
    assert filters.matches("ai", "senior ai/ml developer")


def test_java_does_not_match_javascript():
    """Two different languages. Substring matching cannot tell them apart."""
    assert not filters.matches("java", "javascript developer")
    assert filters.matches("java", "java backend developer")


def test_ml_does_not_match_html():
    assert not filters.matches("ml", "html and css developer")
    assert filters.matches("ml", "ml engineer")


def test_lead_does_not_match_leadership():
    """
    This used to need a hack: the blocklist stored "lead " with a trailing
    space to avoid hitting "leadership". Whole-word matching removes the
    need for that trick.
    """
    assert not filters.matches("lead", "leadership development program")
    assert filters.matches("lead", "lead engineer")


def test_keywords_with_punctuation_are_safe():
    """
    re.escape means a "." in a keyword is treated as a literal dot, not as
    the regex wildcard that matches any character.
    """
    assert filters.matches("node.js", "node.js developer")
    assert not filters.matches("node.js", "nodexjs developer")


def test_multi_word_keywords_still_work():
    assert filters.matches("machine learning", "machine learning engineer")
    assert filters.matches("full stack", "full stack web developer")


def test_ai_keyword_does_not_inflate_an_email_job():
    """End to end: the Email Developer must not score as an AI role."""
    keywords = {"ai": 12, "developer": 8}
    score, matched = filters.score_job(make_job(title="Email Developer"), keywords)

    assert score == 8
    assert matched == ["developer"]


# ---------------------------------------------------------------------------
# Level keywords - "fresher" is a bonus, never a qualification
# ---------------------------------------------------------------------------

LEVELS = {"fresher": 14, "junior": 12, "entry level": 12}


def test_content_writer_fresher_does_not_qualify():
    """
    The "Content Writer (Fresher)" test.

    A real Adzuna listing titled "Content Writer (Fresher / Entry Level)"
    scored 41 when level words counted towards the skills gate, and a
    "CA Fresher (Stat Audit)" accounting job scored 29. Neither is software.
    Level words are now a bonus applied only after the skills gate.
    """
    jobs = [make_job(title="Content Writer (Fresher / Entry Level)")]

    kept = filters.filter_jobs(
        jobs, KEYWORDS, [], min_score=0,
        min_keyword_score=4, level_keywords=LEVELS,
    )

    assert kept == []


def test_level_still_boosts_a_real_tech_job():
    """The flip side: a junior Python role should rank above a plain one."""
    plain = filters.filter_jobs(
        [make_job(title="Python Engineer")], KEYWORDS, [], min_score=0,
        min_keyword_score=4, level_keywords=LEVELS,
    )[0]["score"]

    junior = filters.filter_jobs(
        [make_job(title="Junior Python Engineer")], KEYWORDS, [], min_score=0,
        min_keyword_score=4, level_keywords=LEVELS,
    )[0]["score"]

    assert junior > plain
    assert junior == plain + 12 + 6   # junior bonus, plus "junior" as a keyword


def test_level_words_are_labelled_in_the_output():
    """So you can see WHY a job scored what it did."""
    kept = filters.filter_jobs(
        [make_job(title="Junior Python Developer")], KEYWORDS, [], min_score=0,
        min_keyword_score=4, level_keywords=LEVELS,
    )

    assert "junior (level)" in kept[0]["matched"]


# ---------------------------------------------------------------------------
# Keywords containing punctuation
# ---------------------------------------------------------------------------

def test_punctuation_edged_keywords_match():
    """
    These failed SILENTLY before, which is the worst kind of failure.

    A \b word boundary only exists next to a letter or digit, so a keyword
    starting or ending with punctuation never matched anything - no error,
    the jobs just quietly scored zero. You already had a ".NET Python - AI
    Developer" job that was affected.
    """
    assert filters.matches("c++", "c++ developer")
    assert filters.matches("c#", "c# developer")
    assert filters.matches(".net", ".net backend developer")
    assert filters.matches("node.js", "node.js developer")


def test_punctuation_fix_did_not_break_normal_words():
    assert not filters.matches("ai", "email developer")
    assert not filters.matches("java", "javascript developer")


# ---------------------------------------------------------------------------
# Overlapping keywords must not stack
# ---------------------------------------------------------------------------

def test_a_phrase_is_not_counted_three_times():
    """
    "Software Engineer" used to score for "software engineer", AND
    "software", AND "engineer" - three hits for one phrase. That inflation
    pushed "Java Software Engineer" above "Machine Learning Engineer",
    which is backwards when AI is the priority.
    """
    keywords = {"software engineer": 14, "software": 10, "engineer": 4}
    score, matched = filters.score_job(
        make_job(title="Software Engineer"), keywords
    )

    assert score == 14
    assert matched == ["software engineer"]


def test_non_overlapping_keywords_still_add_up():
    """The fix must not stop genuinely separate keywords from combining."""
    keywords = {"python": 16, "developer": 10}
    score, _ = filters.score_job(make_job(title="Python Developer"), keywords)

    assert score == 26


def test_ai_roles_outrank_plain_software_roles():
    """The whole point of the retune, locked in as a test."""
    ml = filters.score_job(
        make_job(title="Machine Learning Engineer"), config_keywords()
    )[0]
    java = filters.score_job(
        make_job(title="Java Software Engineer"), config_keywords()
    )[0]
    web = filters.score_job(
        make_job(title="React Frontend Developer"), config_keywords()
    )[0]

    assert ml > java
    assert ml > web


def config_keywords():
    """Read the real KEYWORDS out of config, so this test tracks reality."""
    import config
    return config.KEYWORDS
