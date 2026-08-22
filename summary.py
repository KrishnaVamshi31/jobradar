"""
summary.py - The end-of-day round-up.

Run this in the evening and it sends you one Telegram message:

    what you applied to today, and what is still sitting there waiting.

    python summary.py

The second half is the point. It is easy to let a good job sit in a
spreadsheet for a week. This is the nudge.

Where the "applied" information comes from: the status column in
data/jobs.xlsx, which you tick yourself. JobRadar cannot know you applied
to something unless you tell it - nothing it can see from the outside says
whether you filled in a form on a company website.
"""

import argparse
import html
import re
import sys

import pandas as pd

import config
import notify
import report
import storage


def load_jobs():
    """
    Read the saved jobs, newest and highest scoring first.

    Returns an empty DataFrame rather than crashing if there is nothing
    saved yet, so a summary run before your first scan just says so.
    """
    try:
        table = pd.read_csv(config.CSV_FILE)
    except (FileNotFoundError, pd.errors.EmptyDataError):
        return pd.DataFrame()

    if "status" not in table.columns:
        table["status"] = storage.DEFAULT_STATUS

    table["status"] = table["status"].fillna(storage.DEFAULT_STATUS)
    return table


def split_by_status(table):
    """
    Divide the jobs into what you have dealt with and what you have not.

    "skipped" counts as dealt with - you looked at it and decided no, which
    is a real decision. Only "new" is still outstanding.
    """
    applied = table[table["status"] == "applied"]
    waiting = table[table["status"] == storage.DEFAULT_STATUS]

    return applied.to_dict("records"), waiting.to_dict("records")


def main():
    parser = argparse.ArgumentParser(
        prog="summary",
        description="Send an end-of-day summary of applied and outstanding jobs.",
    )
    parser.add_argument(
        "--print", action="store_true",
        help="Print the summary instead of sending it to Telegram.",
    )
    args = parser.parse_args()

    table = load_jobs()

    if table.empty:
        report.console.print(
            "\n[yellow]No jobs saved yet.[/yellow] "
            "[dim]Run python main.py first.[/dim]\n"
        )
        return

    applied, waiting = split_by_status(table)

    # Show the highest scoring outstanding jobs first - those are the ones
    # worth nagging about.
    waiting.sort(key=lambda job: job.get("score", 0), reverse=True)

    message = notify.format_daily_summary(applied, waiting)

    if args.print:
        # The message is built as Telegram HTML, so for the terminal we
        # strip the tags AND turn "&amp;" back into "&" - otherwise an
        # "R&D Engineer" prints as "R&amp;D Engineer".
        plain = re.sub(r"<[^>]+>", "", message)
        report.console.print("\n" + html.unescape(plain) + "\n")
        return

    if not notify.is_configured():
        report.console.print(
            "\n[yellow]Telegram is not set up.[/yellow] "
            "[dim]Run python notify.py --setup, or use --print.[/dim]\n"
        )
        sys.exit(1)

    if notify.send(message):
        report.console.print(
            "\n[green]Summary sent.[/green] "
            f"[dim]{len(applied)} applied, {len(waiting)} still open.[/dim]\n"
        )
    else:
        report.console.print("\n[red]Telegram would not accept the message.[/red]\n")
        sys.exit(1)


if __name__ == "__main__":
    main()
