"""
Tests for scrapers.py.

These do NOT hit the network. Tests that depend on a live website are slow
and fail for reasons that have nothing to do with your code - if RemoteOK
is down, your test suite should not go red.

So these test the pure helper functions: the text cleaning, the date
parsing, and the credential scrubbing.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import scrapers


# ---------------------------------------------------------------------------
# strip_secrets - keeping API keys out of error messages
# ---------------------------------------------------------------------------

def test_api_key_is_stripped_from_an_error():
    """
    The near-miss this prevents.

    When an Adzuna request failed, the error message contained the full
    request URL - including app_id and app_key - and that got printed to
    the terminal and written into the CI log.
    """
    leaky = (
        "Could not reach https://api.adzuna.com/v1/api/jobs/in/search/1"
        "?app_id=abc123&app_key=SUPERSECRET - 429 Too Many Requests"
    )
    safe = scrapers.strip_secrets(leaky)

    assert "SUPERSECRET" not in safe
    assert "abc123" not in safe
    assert "api.adzuna.com" in safe       # the useful part survives
    assert "429" in safe                  # so does the actual reason


def test_urls_without_a_query_string_are_untouched():
    url = "https://remoteok.com/api"
    assert scrapers.strip_secrets(url) == url


def test_stripping_handles_several_urls_in_one_message():
    """requests puts the URL in twice - once by us, once in its own text."""
    text = ("https://a.com/x?key=SECRET1 and https://b.com/y?key=SECRET2")
    safe = scrapers.strip_secrets(text)

    assert "SECRET1" not in safe
    assert "SECRET2" not in safe


# ---------------------------------------------------------------------------
# clean - tidying up scraped text
# ---------------------------------------------------------------------------

def test_html_entities_are_decoded():
    """A real RemoteOK listing had the company "H&amp;M"."""
    assert scrapers.clean("H&amp;M") == "H&M"


def test_whitespace_is_collapsed():
    assert scrapers.clean("  Python\n\n   Developer  ") == "Python Developer"


def test_clean_handles_nothing():
    assert scrapers.clean(None) == ""
    assert scrapers.clean("") == ""


# ---------------------------------------------------------------------------
# date parsing
# ---------------------------------------------------------------------------

def test_rss_date_becomes_a_sortable_date():
    raw = "Fri, 21 Aug 2026 10:40:25 +0000"
    assert scrapers.parse_rss_date(raw) == "2026-08-21"


def test_unix_timestamp_becomes_a_sortable_date():
    """
    Himalayas sends pubDate as a NUMBER, not text.

    Slicing it like a string with [:10] crashed with "int object is not
    subscriptable" - a good reminder to check a field's type before
    treating it as text.
    """
    assert scrapers.epoch_to_date(1787317502) == "2026-08-21"


def test_bad_dates_return_empty_rather_than_crashing():
    assert scrapers.parse_rss_date("not a date") == ""
    assert scrapers.parse_rss_date(None) == ""
    assert scrapers.epoch_to_date(None) == ""
    assert scrapers.epoch_to_date("banana") == ""


# ---------------------------------------------------------------------------
# make_job - the shared shape
# ---------------------------------------------------------------------------

def test_every_scraper_returns_the_same_keys():
    """
    The whole design rests on this: whatever site a job came from, it has
    the same keys, so nothing downstream needs to care about the source.
    """
    job = scrapers.make_job("T", "C", "L", "https://x.com", "test")

    assert set(job) == {
        "title", "company", "location", "url", "source", "tags", "posted",
        "description",
    }


def test_missing_location_gets_a_readable_default():
    job = scrapers.make_job("T", "C", "", "https://x.com", "test")
    assert job["location"] == "Not listed"


# ---------------------------------------------------------------------------
# Telegram credential checks - catching easy mistakes early
# ---------------------------------------------------------------------------

import notify


def test_chat_id_with_an_at_sign_is_rejected():
    """
    The most likely setup mistake.

    A chat id is a number. "@name" is a username, which Telegram only
    accepts for public channels - never for messaging a person. Telegram
    replies "chat not found" with no explanation, so we catch it first.
    """
    problem = notify.check_credentials("812345:AAF1a2", "@krishnavamshi")

    assert "@" in problem
    assert "number" in problem.lower()


def test_a_normal_chat_id_is_accepted():
    assert notify.check_credentials("812345:AAF1a2", "987654321") == ""


def test_a_group_chat_id_is_accepted():
    """Group chats have negative ids. That is normal, not an error."""
    assert notify.check_credentials("812345:AAF1a2", "-1001234567890") == ""


def test_a_mangled_token_is_rejected():
    problem = notify.check_credentials("notatoken", "987654321")
    assert "token" in problem.lower()


def test_missing_credentials_are_reported():
    assert notify.check_credentials("", "") != ""
