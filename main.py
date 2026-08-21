"""
main.py - The entry point. This is the file you run.

    python main.py

Everything happens in run() below, in five clear steps. Each step hands its
result to the next one:

    1. SCRAPE  - visit the job sites            (scrapers.py)
    2. FILTER  - score and rank the jobs        (filters.py)
    3. COMPARE - work out which ones are new    (storage.py)
    4. SAVE    - write the CSV and Excel files  (storage.py)
    5. REPORT  - show a table and build a page  (report.py)

If you want to change WHAT it searches for, edit config.py - not this file.
"""

import argparse
import sys

import config
import filters
import report
import scrapers
import storage


def parse_arguments():
    """
    Read the options someone typed after "python main.py".

    argparse is part of Python. It handles --flags, gives you --help for
    free, and shows a friendly error if someone types a flag wrong.

    Every flag here is optional. With no flags at all, we just use whatever
    is set in config.py.
    """
    parser = argparse.ArgumentParser(
        prog="jobradar",
        description="Scrape job boards, score the results, and track what is new.",
        epilog="Tip: edit config.py to change your keywords and filters.",
    )

    parser.add_argument(
        "--source",
        action="append",
        choices=list(scrapers.SCRAPERS.keys()),
        help="Only scrape this source. Repeat the flag to pick several.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        help=f"Jobs to pull per source (config default: {config.JOBS_PER_SOURCE}).",
    )
    parser.add_argument(
        "--min-score",
        type=int,
        help=f"Minimum score to keep a job (config default: {config.MIN_SCORE}).",
    )
    parser.add_argument(
        "--new-only",
        action="store_true",
        help="Only show jobs that were not in the history file.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Run everything but do not write any files.",
    )
    parser.add_argument(
        "--open",
        action="store_true",
        help="Open the HTML report in your browser when finished.",
    )

    return parser.parse_args()


def run(args):
    """Run the whole pipeline once. Returns the number of new jobs found."""

    # Command line flags win over config.py, but if a flag was not given we
    # fall back to the config value. "x if x else y" is doing that choosing.
    sources = args.source or config.SOURCES
    limit = args.limit or config.JOBS_PER_SOURCE
    min_score = args.min_score if args.min_score is not None else config.MIN_SCORE

    report.console.print("\n[bold cyan]JobRadar[/bold cyan] [dim]-- scanning job boards[/dim]\n")

    # --- Step 1: scrape -------------------------------------------------
    report.console.print(f"[bold]1.[/bold] Scraping {len(sources)} source(s), up to {limit} jobs each")
    raw_jobs = scrapers.scrape_all(sources, limit, on_status=report.print_status)

    if not raw_jobs:
        report.console.print(
            "\n[red]No jobs came back from any source.[/red] "
            "[dim]Check your internet connection and try again.[/dim]\n"
        )
        return 0

    # --- Step 2: score and filter ---------------------------------------
    report.console.print(f"\n[bold]2.[/bold] Scoring {len(raw_jobs)} jobs against {len(config.KEYWORDS)} keywords")
    matched = filters.filter_jobs(
        raw_jobs,
        keywords=config.KEYWORDS,
        blocklist=config.BLOCKLIST,
        min_score=min_score,
        location_keywords=config.LOCATION_KEYWORDS,
        require_location=config.REQUIRE_LOCATION_MATCH,
        min_keyword_score=config.MIN_KEYWORD_SCORE,
        level_keywords=config.LEVEL_KEYWORDS,
    )
    report.console.print(
        f"  [green]OK[/green]     kept {len(matched)}, "
        f"dropped {len(raw_jobs) - len(matched)} below score {min_score} or blocklisted"
    )

    # --- Step 3: compare against history --------------------------------
    report.console.print("\n[bold]3.[/bold] Comparing against previous runs")
    seen_ids = storage.load_history(config.CSV_FILE)
    matched = storage.tag_new_jobs(matched, seen_ids)

    new_count = sum(1 for job in matched if job["is_new"])
    report.console.print(
        f"  [green]OK[/green]     {len(seen_ids)} jobs already in history, "
        f"[bold green]{new_count} new[/bold green]"
    )

    # If --new-only was used, throw away everything we have seen before.
    if args.new_only:
        matched = [job for job in matched if job["is_new"]]

    # --- Step 4: save ---------------------------------------------------
    if args.dry_run:
        report.console.print("\n[bold]4.[/bold] [yellow]Skipping save (--dry-run)[/yellow]")
    else:
        report.console.print("\n[bold]4.[/bold] Saving results")
        added = storage.save_jobs(matched, config.CSV_FILE, config.EXCEL_FILE)
        report.console.print(f"  [green]OK[/green]     added {added} new rows")
        report.console.print(f"  [dim]{config.CSV_FILE}[/dim]")
        report.console.print(f"  [dim]{config.EXCEL_FILE}[/dim]")

    # --- Step 5: report -------------------------------------------------
    stats = filters.summarise(raw_jobs, matched)

    # If --new-only emptied the list, say so properly. "No jobs matched"
    # would be misleading here - jobs DID match, you have just seen them all.
    empty_hint = None
    if args.new_only and not matched:
        empty_hint = (
            "[green]Nothing new since your last run.[/green] "
            "[dim]You are up to date.[/dim]"
        )

    report.print_console_report(matched, stats, empty_hint=empty_hint)

    if not args.dry_run:
        path = report.write_html_report(
            matched, stats, config.HTML_REPORT, open_in_browser=args.open
        )
        report.console.print(f"[dim]Full report: {path}[/dim]\n")

    return new_count


def main():
    """
    Wrapper around run() that handles the two ways things go wrong.

    Ctrl+C should quit quietly, not dump a scary red error at you. And any
    unexpected crash should print one clear line instead of a wall of text.
    """
    args = parse_arguments()

    try:
        run(args)
    except KeyboardInterrupt:
        report.console.print("\n[yellow]Stopped by user.[/yellow]\n")
        sys.exit(130)   # 130 is the standard exit code for "Ctrl+C"
    except Exception as error:
        report.console.print(f"\n[red]Something went wrong:[/red] {error}\n")
        sys.exit(1)


# This line means "only run main() if this file was started directly".
# It stops main() from firing if another file ever imports this one.
if __name__ == "__main__":
    main()
