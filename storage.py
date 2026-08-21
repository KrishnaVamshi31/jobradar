"""
storage.py - Saves jobs to disk and works out which ones are NEW.

This file is what makes JobRadar a *tracker* rather than just a scraper.

The problem it solves: if you run the program every morning, most of the
jobs you see will be the same ones as yesterday. You only care about what
changed. So we keep a history file, and compare against it every run.

The trick is giving every job a stable ID:

    Same job  ->  same ID  ->  we know we have seen it before
    New job   ->  new ID   ->  we flag it for you

We build that ID by hashing the job URL, because a URL is unique to a
posting and does not change between runs.
"""

import hashlib
import os
from datetime import date

import pandas as pd

# The order columns appear in the CSV and Excel file. Putting the useful
# stuff first means you do not have to scroll sideways in Excel.
COLUMNS = [
    "first_seen",
    "score",
    "title",
    "company",
    "location",
    "source",
    "matched",
    "tags",
    "posted",
    "url",
    "id",
]


def make_job_id(job):
    """
    Build a short, stable ID for a job.

    "Stable" means: run this on the same job tomorrow and you get the exact
    same ID back. That is what lets us recognise a job we have seen before.

    We hash the URL when there is one, because URLs are unique per posting.
    If a site gives us no URL, we fall back to source + title + company,
    which is almost always unique enough.

    A hash turns any text into a fixed-length fingerprint, like:
        "https://remoteok.com/jobs/123"  ->  "a3f5c9e102"
    """
    if job.get("url"):
        raw = job["url"]
    else:
        raw = job.get("source", "") + job.get("title", "") + job.get("company", "")

    # .encode() turns text into bytes, which is what hashlib needs.
    # We keep the first 10 characters - plenty to avoid collisions here.
    return hashlib.md5(raw.encode("utf-8")).hexdigest()[:10]


def load_history(csv_file):
    """
    Read the IDs of every job we have already saved.

    Returns a set of ID strings. A set is used instead of a list because
    checking "is this ID in here?" is instant on a set, even with 10,000
    jobs in it.

    If the file does not exist yet (your very first run), we just return an
    empty set - meaning every job found today counts as new.
    """
    if not os.path.exists(csv_file):
        return set()

    try:
        existing = pd.read_csv(csv_file)
    except Exception:
        # An empty or half-written CSV should not crash the program.
        return set()

    if "id" not in existing.columns:
        return set()

    return set(existing["id"].astype(str))


def tag_new_jobs(jobs, seen_ids):
    """
    Give every job an ID, and mark whether we have seen it before.

    Adds two keys to each job:
        id      - the stable fingerprint from make_job_id
        is_new  - True if this ID was not in the history file
    """
    tagged = []

    for job in jobs:
        job_with_id = dict(job)          # copy, do not modify the original
        job_id = make_job_id(job)

        job_with_id["id"] = job_id
        job_with_id["is_new"] = job_id not in seen_ids
        tagged.append(job_with_id)

    return tagged


def save_jobs(jobs, csv_file, excel_file):
    """
    Add today's jobs to the history files (CSV and Excel).

    Jobs we already had keep their ORIGINAL first_seen date, so you can
    always tell how long a posting has been sitting there.

    Returns how many brand new rows were added.
    """
    if not jobs:
        return 0

    # Make sure the data folder exists before we try to write into it.
    folder = os.path.dirname(csv_file)
    if folder:
        os.makedirs(folder, exist_ok=True)

    # Make sure every job has an ID before we go any further, because the
    # duplicate check below relies on it.
    #
    # main.py already adds IDs in step 3, so normally this loop finds
    # nothing to do. We do it anyway so that save_jobs works correctly even
    # if someone calls it on its own - a function should not quietly depend
    # on another one having been called first.
    jobs_with_ids = []
    for job in jobs:
        job = dict(job)
        if not job.get("id"):
            job["id"] = make_job_id(job)
        jobs_with_ids.append(job)

    # Turn our list of dictionaries into a pandas DataFrame - basically a
    # spreadsheet in memory, which makes saving to CSV and Excel one line.
    fresh = pd.DataFrame(jobs_with_ids)
    fresh["first_seen"] = date.today().isoformat()

    # Drop the is_new column - it is only true for THIS run, so saving it
    # into the permanent history would be misleading tomorrow.
    if "is_new" in fresh.columns:
        fresh = fresh.drop(columns=["is_new"])

    # Load whatever we saved on previous runs.
    if os.path.exists(csv_file):
        try:
            old = pd.read_csv(csv_file)
        except Exception:
            old = pd.DataFrame()
    else:
        old = pd.DataFrame()

    before = len(old)

    # Stack the old rows on top of the new ones, then remove duplicates.
    #
    # Order matters here! Old rows come FIRST, and keep="first" means that
    # when a job appears in both, we keep the OLD row - which still has its
    # original first_seen date. That is exactly what we want.
    combined = pd.concat([old, fresh], ignore_index=True)
    combined = combined.drop_duplicates(subset=["id"], keep="first")

    # Put the columns in our preferred order. We only ask for columns that
    # actually exist, so this cannot crash if a field is missing.
    ordered = [c for c in COLUMNS if c in combined.columns]
    combined = combined[ordered]

    # Newest and highest scoring at the top.
    combined = combined.sort_values(
        by=["first_seen", "score"],
        ascending=[False, False],
    )

    combined.to_csv(csv_file, index=False)
    write_excel(combined, excel_file)

    return len(combined) - before


def write_excel(dataframe, excel_file):
    """
    Save the same data as a formatted .xlsx file.

    pandas can write Excel in one line, but the result looks rough - every
    column the same narrow width. So afterwards we reach into the file with
    openpyxl and widen the columns and freeze the header row.

    This is the kind of polish that makes people actually use your tool.
    """
    with pd.ExcelWriter(excel_file, engine="openpyxl") as writer:
        dataframe.to_excel(writer, sheet_name="Jobs", index=False)

        sheet = writer.sheets["Jobs"]

        # Freeze the top row so headers stay visible while you scroll.
        sheet.freeze_panes = "A2"

        # Set a sensible width for each column, based on its name.
        widths = {
            "first_seen": 12, "score": 7, "title": 42, "company": 26,
            "location": 24, "source": 16, "matched": 30, "tags": 30,
            "posted": 12, "url": 50, "id": 12,
        }

        for index, column_name in enumerate(dataframe.columns, start=1):
            # openpyxl numbers columns 1, 2, 3... and names them A, B, C...
            letter = sheet.cell(row=1, column=index).column_letter
            sheet.column_dimensions[letter].width = widths.get(column_name, 18)
