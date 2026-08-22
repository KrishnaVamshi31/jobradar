"""
Tests for storage.py - the IDs, the history file, and saving.

The important thing being tested here is the promise that makes JobRadar a
tracker rather than a scraper:

    the same job must always produce the same ID

If that ever breaks, every job would look brand new on every run, and the
"NEW" badge would become meaningless.

The saving tests use pytest's tmp_path fixture. Writing tmp_path as an
argument to a test function tells pytest to hand you a fresh empty folder
that it deletes afterwards - so tests never touch your real data/ folder.
"""

import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import storage


def make_job(title="Python Dev", url="https://example.com/job/1", score=10):
    return {
        "title": title,
        "company": "Test Co",
        "location": "Remote",
        "url": url,
        "source": "test",
        "tags": "python",
        "posted": "2026-01-01",
        "score": score,
        "matched": "python",
    }


# ---------------------------------------------------------------------------
# make_job_id
# ---------------------------------------------------------------------------

def test_the_same_job_always_gets_the_same_id():
    """The whole tracker depends on this being true."""
    job = make_job()

    assert storage.make_job_id(job) == storage.make_job_id(job)


def test_different_urls_get_different_ids():
    a = storage.make_job_id(make_job(url="https://example.com/job/1"))
    b = storage.make_job_id(make_job(url="https://example.com/job/2"))

    assert a != b


def test_id_ignores_fields_that_change():
    """
    A job board might reword a title or bump the score between runs. As long
    as the URL is the same, it is the same posting and keeps the same ID.
    """
    monday = make_job(title="Python Dev", score=10)
    friday = make_job(title="Python Developer (Updated)", score=25)

    assert storage.make_job_id(monday) == storage.make_job_id(friday)


def test_job_with_no_url_still_gets_an_id():
    """Falls back to source + title + company instead of crashing."""
    job = make_job(url="")
    job_id = storage.make_job_id(job)

    assert isinstance(job_id, str)
    assert len(job_id) == 10


# ---------------------------------------------------------------------------
# load_history and tag_new_jobs
# ---------------------------------------------------------------------------

def test_missing_history_file_is_not_an_error(tmp_path):
    """On your very first run there is no CSV yet. That must not crash."""
    missing = tmp_path / "does_not_exist.csv"

    assert storage.load_history(str(missing)) == set()


def test_everything_is_new_on_the_first_run():
    tagged = storage.tag_new_jobs([make_job()], seen_ids=set())

    assert tagged[0]["is_new"] is True


def test_a_known_job_is_not_marked_new():
    job = make_job()
    known_id = storage.make_job_id(job)

    tagged = storage.tag_new_jobs([job], seen_ids={known_id})

    assert tagged[0]["is_new"] is False


def test_tagging_does_not_modify_the_original_job():
    original = make_job()
    storage.tag_new_jobs([original], set())

    assert "is_new" not in original


# ---------------------------------------------------------------------------
# save_jobs - the round trip
# ---------------------------------------------------------------------------

def test_saving_creates_both_files(tmp_path):
    csv_file = tmp_path / "jobs.csv"
    excel_file = tmp_path / "jobs.xlsx"

    storage.save_jobs([make_job()], str(csv_file), str(excel_file))

    assert csv_file.exists()
    assert excel_file.exists()


def test_saved_jobs_can_be_read_back(tmp_path):
    csv_file = tmp_path / "jobs.csv"
    jobs = storage.tag_new_jobs([make_job()], set())

    storage.save_jobs(jobs, str(csv_file), str(tmp_path / "jobs.xlsx"))

    saved = pd.read_csv(csv_file)
    assert len(saved) == 1
    assert saved.iloc[0]["title"] == "Python Dev"
    # is_new is only true for one run, so it must not be written to history
    assert "is_new" not in saved.columns


def test_saving_the_same_job_twice_does_not_duplicate_it(tmp_path):
    """
    This is the test that proves the history file works.

    Run one, then run two with the same job. We should still have exactly
    one row, and load_history should recognise it the second time.
    """
    csv_file = str(tmp_path / "jobs.csv")
    excel_file = str(tmp_path / "jobs.xlsx")
    job = make_job()

    storage.save_jobs([job], csv_file, excel_file)
    storage.save_jobs([job], csv_file, excel_file)

    assert len(pd.read_csv(csv_file)) == 1
    assert storage.make_job_id(job) in storage.load_history(csv_file)


def test_a_second_different_job_is_added(tmp_path):
    csv_file = str(tmp_path / "jobs.csv")
    excel_file = str(tmp_path / "jobs.xlsx")

    storage.save_jobs([make_job(url="https://example.com/a")], csv_file, excel_file)
    storage.save_jobs([make_job(url="https://example.com/b")], csv_file, excel_file)

    assert len(pd.read_csv(csv_file)) == 2


def test_first_seen_date_is_kept_from_the_original_run(tmp_path):
    """
    A job you found last week should still say you found it last week, even
    though today's run saw it again.
    """
    csv_file = str(tmp_path / "jobs.csv")
    excel_file = str(tmp_path / "jobs.xlsx")
    job = make_job()

    storage.save_jobs([job], csv_file, excel_file)

    # Pretend the saved row was found back in January.
    table = pd.read_csv(csv_file)
    table.loc[0, "first_seen"] = "2026-01-15"
    table.to_csv(csv_file, index=False)

    # Seeing the same job again today must not overwrite that date.
    storage.save_jobs([job], csv_file, excel_file)

    assert pd.read_csv(csv_file).iloc[0]["first_seen"] == "2026-01-15"


def test_saving_nothing_is_harmless(tmp_path):
    """An empty run should quietly do nothing rather than blow up."""
    added = storage.save_jobs([], str(tmp_path / "j.csv"), str(tmp_path / "j.xlsx"))

    assert added == 0


# ---------------------------------------------------------------------------
# normalise_url - tracking tokens must not change a job's identity
# ---------------------------------------------------------------------------

def test_adzuna_session_token_does_not_change_the_id():
    """
    The duplicates bug.

    Adzuna returns a different url for the same job on every request - only
    the "se" session token changes. Hashing the whole url made every job
    look new each run, so the history filled up with triplicates and the
    NEW badge stopped meaning anything.
    """
    base = "https://www.adzuna.in/land/ad/5837138847"
    first = make_job(url=base + "?se=cgNb8NWd8RGU&utm_medium=api")
    second = make_job(url=base + "?se=JuFAFNad8RGU&utm_medium=api")
    third = make_job(url=base + "?se=KHzNDnad8RGf&utm_medium=api")

    ids = {
        storage.make_job_id(first),
        storage.make_job_id(second),
        storage.make_job_id(third),
    }

    assert len(ids) == 1


def test_genuinely_different_ads_still_differ():
    """The fix must not go too far and merge two real jobs into one."""
    a = make_job(url="https://www.adzuna.in/land/ad/111?se=x")
    b = make_job(url="https://www.adzuna.in/land/ad/222?se=x")

    assert storage.make_job_id(a) != storage.make_job_id(b)


def test_url_with_no_path_keeps_its_query_string():
    """
    Guard against over-stripping.

    If a site put the job id in the query string, throwing the query away
    would collapse every job on that site into a single ID.
    """
    url = "https://example.com/?id=123"
    assert storage.normalise_url(url) == url


def test_urls_without_a_query_string_are_unchanged():
    url = "https://remoteok.com/remote-jobs/some-job-123"
    assert storage.normalise_url(url) == url


def test_saving_the_same_adzuna_job_twice_makes_one_row(tmp_path):
    """End to end: two runs, same job, one row in the history."""
    csv_file = str(tmp_path / "jobs.csv")
    excel_file = str(tmp_path / "jobs.xlsx")
    base = "https://www.adzuna.in/land/ad/999"

    monday = storage.tag_new_jobs([make_job(url=base + "?se=AAA")], set())
    storage.save_jobs(monday, csv_file, excel_file)

    seen = storage.load_history(csv_file)
    tuesday = storage.tag_new_jobs([make_job(url=base + "?se=BBB")], seen)

    assert tuesday[0]["is_new"] is False      # recognised despite a new token

    storage.save_jobs(tuesday, csv_file, excel_file)
    assert len(pd.read_csv(csv_file)) == 1
