"""
report.py - Shows you the results, in the terminal and as a web page.

Two outputs, because they are good at different things:

    print_console_report()  - instant feedback right after a run
    write_html_report()     - a shareable page you can open in a browser

The HTML file is completely self-contained (the styling is baked inside it),
so you can email it to someone or open it offline and it still looks right.
"""

import html
import os
import webbrowser
from datetime import datetime

from rich.console import Console
from rich.table import Table

console = Console()


# ---------------------------------------------------------------------------
# Terminal output
# ---------------------------------------------------------------------------

def print_console_report(jobs, stats, show=15, empty_hint=None):
    """
    Print the top jobs as a colored table in the terminal.

    "rich" is the library doing the pretty printing. It handles the column
    widths, borders and colors for us.

    empty_hint lets the caller explain WHY the list came back empty. An
    empty result after --new-only means something completely different from
    an empty result because your score was set too high, and telling
    someone to lower MIN_SCORE when they are simply up to date is just
    confusing.
    """
    if not jobs:
        if empty_hint:
            console.print("\n" + empty_hint + "\n")
        else:
            console.print("\n[yellow]No jobs matched your filters.[/yellow]")
            console.print(
                "[dim]Try lowering MIN_SCORE in config.py, "
                "or adding more KEYWORDS.[/dim]\n"
            )
        return

    table = Table(
        title=f"Top {min(show, len(jobs))} matches",
        title_style="bold cyan",
        header_style="bold white on dark_blue",
        expand=True,
    )

    table.add_column("Score", justify="right", style="bold", width=6)
    table.add_column("Title", style="cyan", max_width=40, overflow="ellipsis")
    table.add_column("Company", max_width=22, overflow="ellipsis")
    table.add_column("Location", max_width=20, overflow="ellipsis")
    table.add_column("Source", style="dim", width=15)
    table.add_column("New", justify="center", width=4)

    for job in jobs[:show]:
        # Color the score: green for strong matches, yellow for so-so.
        score = job["score"]
        if score >= 20:
            score_text = f"[green]{score}[/green]"
        elif score >= 10:
            score_text = f"[yellow]{score}[/yellow]"
        else:
            score_text = f"[dim]{score}[/dim]"

        table.add_row(
            score_text,
            job["title"],
            job["company"],
            job["location"],
            job["source"],
            "[bold green]NEW[/bold green]" if job.get("is_new") else "",
        )

    console.print()
    console.print(table)

    # A one-line summary under the table.
    new_count = sum(1 for job in jobs if job.get("is_new"))
    console.print(
        f"\n[bold]{stats['kept']}[/bold] jobs matched out of "
        f"[bold]{stats['scraped']}[/bold] scraped  "
        f"([green]{new_count} new since last run[/green])"
    )


def print_status(name, kind, message):
    """Print one line of scraper progress. Passed into scrapers.scrape_all."""
    if kind == "ok":
        console.print(f"  [green]OK[/green]     {name:<16} {message}")
    else:
        console.print(f"  [red]FAILED[/red] {name:<16} [dim]{message}[/dim]")


# ---------------------------------------------------------------------------
# HTML output
# ---------------------------------------------------------------------------

# The styling lives in its own plain string (not an f-string) because CSS is
# full of { } braces, which would confuse Python's f-string formatting.
CSS = """
* { box-sizing: border-box; }
body {
  margin: 0; padding: 32px 20px;
  font-family: -apple-system, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
  background: #0f1420; color: #e6e9f0;
}
.wrap { max-width: 1100px; margin: 0 auto; }
h1 { margin: 0 0 4px; font-size: 26px; letter-spacing: -0.4px; }
.sub { color: #8b93a7; font-size: 13px; margin-bottom: 24px; }
.stats { display: flex; flex-wrap: wrap; gap: 12px; margin-bottom: 26px; }
.stat {
  background: #1a2130; border: 1px solid #263047; border-radius: 10px;
  padding: 12px 18px; min-width: 110px;
}
.stat .n { font-size: 22px; font-weight: 700; }
.stat .l { font-size: 11px; color: #8b93a7; text-transform: uppercase;
           letter-spacing: 0.6px; margin-top: 2px; }
.tablebox { overflow-x: auto; border-radius: 10px; border: 1px solid #263047; }
table { border-collapse: collapse; width: 100%; font-size: 13.5px;
        min-width: 760px; }
th {
  background: #1a2130; text-align: left; padding: 11px 13px;
  font-size: 11px; text-transform: uppercase; letter-spacing: 0.6px;
  color: #8b93a7; border-bottom: 1px solid #263047; white-space: nowrap;
}
td { padding: 11px 13px; border-bottom: 1px solid #1c2436; vertical-align: top; }
tr:last-child td { border-bottom: none; }
tr:hover td { background: #151c29; }
a { color: #6ea8fe; text-decoration: none; }
a:hover { text-decoration: underline; }
.score {
  display: inline-block; min-width: 30px; text-align: center;
  padding: 3px 8px; border-radius: 6px; font-weight: 700; font-size: 12px;
}
.s-hi { background: #16351f; color: #6ee7a0; }
.s-mid { background: #35301a; color: #f0d264; }
.s-lo { background: #232b3d; color: #8b93a7; }
.new {
  background: #6ee7a0; color: #07210f; font-size: 10px; font-weight: 700;
  padding: 2px 6px; border-radius: 4px; letter-spacing: 0.5px;
}
.src { color: #8b93a7; font-size: 12px; }
.matched { color: #7c86a0; font-size: 11.5px; }
.co { color: #c3cade; }
footer { margin-top: 26px; color: #6b7488; font-size: 12px; line-height: 1.7; }
.empty { padding: 40px; text-align: center; color: #8b93a7; }
"""


def score_class(score):
    """Pick which CSS color class a score gets."""
    if score >= 20:
        return "s-hi"
    if score >= 10:
        return "s-mid"
    return "s-lo"


def write_html_report(jobs, stats, path, open_in_browser=False):
    """
    Build a standalone HTML page showing the matched jobs.

    We build the page by joining strings together. html.escape() is used on
    every piece of scraped text - without it, a job title containing a "<"
    would break the page layout.
    """
    folder = os.path.dirname(path)
    if folder:
        os.makedirs(folder, exist_ok=True)

    new_count = sum(1 for job in jobs if job.get("is_new"))
    generated = datetime.now().strftime("%d %b %Y at %H:%M")

    # --- build the table rows, one job per row --------------------------
    rows = []
    for job in jobs:
        title = html.escape(job.get("title", ""))
        url = html.escape(job.get("url", ""))

        # Only make the title a link if we actually have a URL for it.
        title_html = f'<a href="{url}" target="_blank">{title}</a>' if url else title

        new_badge = '<span class="new">NEW</span>' if job.get("is_new") else ""

        rows.append(f"""      <tr>
        <td><span class="score {score_class(job['score'])}">{job['score']}</span></td>
        <td>{title_html} {new_badge}<div class="matched">{html.escape(job.get('matched', ''))}</div></td>
        <td class="co">{html.escape(job.get('company', ''))}</td>
        <td class="src">{html.escape(job.get('location', ''))}</td>
        <td class="src">{html.escape(job.get('source', ''))}</td>
      </tr>""")

    if rows:
        table_html = f"""<div class="tablebox"><table>
    <thead><tr>
      <th>Score</th><th>Role</th><th>Company</th><th>Location</th><th>Source</th>
    </tr></thead>
    <tbody>
{chr(10).join(rows)}
    </tbody>
  </table></div>"""
    else:
        table_html = (
            '<div class="tablebox"><div class="empty">'
            "No jobs matched your filters. Try lowering MIN_SCORE in config.py."
            "</div></div>"
        )

    # --- the stat cards across the top ----------------------------------
    cards = [
        (stats["scraped"], "Scraped"),
        (stats["kept"], "Matched"),
        (new_count, "New today"),
        (stats["top_score"], "Top score"),
    ]
    cards_html = "\n".join(
        f'    <div class="stat"><div class="n">{value}</div>'
        f'<div class="l">{label}</div></div>'
        for value, label in cards
    )

    page = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>JobRadar report</title>
<style>{CSS}</style>
</head>
<body>
<div class="wrap">
  <h1>JobRadar</h1>
  <div class="sub">Generated {generated}</div>
  <div class="stats">
{cards_html}
  </div>
  {table_html}
  <footer>
    Sources: RemoteOK (remoteok.com), We Work Remotely, and the Real Python
    fake-jobs practice board.<br>
    Job data from <a href="https://remoteok.com" target="_blank">RemoteOK</a>.
    Scores come from the KEYWORDS you set in config.py.
  </footer>
</div>
</body>
</html>"""

    with open(path, "w", encoding="utf-8") as file:
        file.write(page)

    if open_in_browser:
        webbrowser.open("file://" + os.path.abspath(path))

    return path
