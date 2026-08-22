"""
notify.py - Sends job alerts to your phone via Telegram.

Why Telegram rather than WhatsApp: WhatsApp needs Meta business verification
or a paid Twilio account whose free sandbox disconnects every 72 hours.
Telegram bots are free, take about five minutes to set up, and just keep
working. The push notification lands on your phone exactly the same.

SETTING IT UP (once, about five minutes)
----------------------------------------
1. Open Telegram and search for  @BotFather
2. Send him:  /newbot
   Pick any name, then a username ending in "bot".
3. He replies with a token that looks like
       8123456789:AAF1a2B3c4D5e6F7g8H9i0J1k2L3m4N5o6P
4. Send any message ("hi") to YOUR new bot, so it is allowed to reply.
5. Run:  python notify.py --setup
   That reads your chat id and prints both values for you.
6. Save them - see load_credentials() below for where they go.

You can then test it with:  python notify.py --test
"""

import argparse
import html
import os
import sys

import requests

# Telegram limits one message to 4096 characters.
MAX_MESSAGE = 4000


def load_credentials():
    """
    Read the Telegram bot token and chat id.

    Two places are checked, so the same code works on your laptop and on
    GitHub's servers:

        1. environment variables TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID
           (this is how GitHub Actions passes in repository secrets)
        2. a plain text file telegram_key.txt, token on line 1, chat id on
           line 2 (this is the easy way on your own machine)

    Like the Adzuna key, these never go in the code itself - telegram_key.txt
    is in .gitignore, because anything pushed to GitHub is public forever.
    """
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
    chat_id = os.environ.get("TELEGRAM_CHAT_ID", "").strip()

    if token and chat_id:
        return token, chat_id

    if os.path.exists("telegram_key.txt"):
        with open("telegram_key.txt", encoding="utf-8") as file:
            lines = [line.strip() for line in file if line.strip()]
        if len(lines) >= 2:
            return lines[0], lines[1]

    return "", ""


def is_configured():
    """True if we have both credentials, so callers can skip quietly."""
    token, chat_id = load_credentials()
    return bool(token and chat_id)


def check_credentials(token, chat_id):
    """
    Catch the mistakes that are easy to make and hard to diagnose.

    Returns a problem description, or "" if everything looks right.

    The @ one is the common trap. A chat id is a NUMBER, like 987654321.
    An "@name" is a username, and Telegram only accepts those for public
    channels - never for messaging a person. Without this check you get a
    bare "Bad Request: chat not found" and no clue why.
    """
    if not token:
        return "No bot token. Run: python notify.py --setup"

    if not chat_id:
        return "No chat id. Run: python notify.py --setup"

    if chat_id.startswith("@"):
        return (
            "Your chat id starts with '@'. It should be a plain number like "
            "987654321 - '@name' is a username, which only works for public "
            "channels, not for messaging you. Run: python notify.py --setup"
        )

    # A negative id is fine - that is what group chats look like.
    if not chat_id.lstrip("-").isdigit():
        return (
            "Your chat id should be only digits (a leading minus is fine for "
            "groups), but it is: " + chat_id
        )

    # Tokens look like  8123456789:AAF1a2B3...
    if ":" not in token:
        return (
            "That does not look like a bot token. BotFather gives you "
            "something like 8123456789:AAF1a2B3c4D5e6F7g8H9i0"
        )

    return ""


def send(text):
    """
    Send one message to your Telegram.

    Returns True if it went, False if it did not. It deliberately does NOT
    raise on failure: a job scan that found work should not be reported as
    a total failure just because the notification did not go out.
    """
    token, chat_id = load_credentials()

    if not token or not chat_id:
        return False

    # Telegram rejects anything over 4096 characters.
    if len(text) > MAX_MESSAGE:
        text = text[:MAX_MESSAGE] + "\n\n... (trimmed)"

    try:
        response = requests.post(
            "https://api.telegram.org/bot" + token + "/sendMessage",
            data={
                "chat_id": chat_id,
                "text": text,
                "parse_mode": "HTML",
                # Without this Telegram pastes a big preview card of the
                # first link, which makes the message enormous.
                "disable_web_page_preview": "true",
            },
            timeout=20,
        )
        return response.ok
    except requests.RequestException:
        return False


def escape(text):
    """
    Make text safe to put inside a Telegram HTML message.

    Job titles genuinely contain "&" (think "R&D Engineer"), and an
    unescaped "&" makes Telegram reject the whole message.
    """
    return html.escape(str(text))


def format_new_jobs(jobs):
    """
    Build the alert message for jobs found in this scan.

    Kept deliberately short: this arrives as a phone notification, so the
    important parts are the role, the place, and a tappable link.
    """
    count = len(jobs)
    heading = "<b>%d new job%s</b>" % (count, "" if count == 1 else "s")

    lines = [heading, ""]

    for job in jobs[:15]:      # more than 15 is a wall of text on a phone
        title = escape(job.get("title", ""))
        company = escape(job.get("company", ""))
        location = escape(job.get("location", ""))
        url = job.get("url", "")
        score = job.get("score", 0)

        if url:
            title = '<a href="%s">%s</a>' % (escape(url), title)

        lines.append("%s  <b>%s</b>" % (score, title))
        lines.append("     %s  ·  %s" % (company, location))
        lines.append("")

    if count > 15:
        lines.append("... and %d more in your report." % (count - 15))

    return "\n".join(lines)


def format_daily_summary(applied, not_applied):
    """
    Build the end-of-day message: what you applied for, and what is waiting.

    The "not applied" half is the useful half. It is the nudge.
    """
    lines = ["<b>Today's job summary</b>", ""]

    lines.append("Applied: <b>%d</b>" % len(applied))
    lines.append("Still open: <b>%d</b>" % len(not_applied))
    lines.append("")

    if applied:
        lines.append("<b>You applied to:</b>")
        for job in applied[:10]:
            lines.append("  %s - %s" % (
                escape(job.get("title", "")), escape(job.get("company", "")),
            ))
        lines.append("")

    if not_applied:
        lines.append("<b>Still waiting on you:</b>")
        for job in not_applied[:10]:
            title = escape(job.get("title", ""))
            url = job.get("url", "")
            if url:
                title = '<a href="%s">%s</a>' % (escape(url), title)
            lines.append("  %s  %s" % (job.get("score", 0), title))

        if len(not_applied) > 10:
            lines.append("  ... and %d more." % (len(not_applied) - 10))
    else:
        lines.append("Nothing outstanding. Good work.")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Setup helpers - run this file directly to configure or test
# ---------------------------------------------------------------------------

def find_chat_id():
    """
    Look up your chat id by asking Telegram what messages your bot received.

    This is why step 4 of the setup matters: your bot cannot discover you
    until you have sent it something.
    """
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()

    if not token and os.path.exists("telegram_key.txt"):
        with open("telegram_key.txt", encoding="utf-8") as file:
            lines = [line.strip() for line in file if line.strip()]
        if lines:
            token = lines[0]

    if not token:
        token = input("Paste your bot token from BotFather: ").strip()

    try:
        response = requests.get(
            "https://api.telegram.org/bot" + token + "/getUpdates", timeout=20
        )
        payload = response.json()
    except requests.RequestException as error:
        print("Could not reach Telegram: %s" % error)
        return

    if not payload.get("ok"):
        print("Telegram rejected that token. Check you copied all of it.")
        return

    updates = payload.get("result") or []
    if not updates:
        print(
            "No messages found.\n"
            "Open Telegram, send any message to your bot, then run this again."
        )
        return

    # The most recent message tells us who is talking to the bot.
    chat = updates[-1].get("message", {}).get("chat", {})
    chat_id = chat.get("id")

    print("\nFound you: %s" % (chat.get("first_name") or "your account"))
    print("Your chat id is: %s" % chat_id)
    print("\nNow create a file called telegram_key.txt with two lines:\n")
    print(token)
    print(chat_id)
    print("\nThen test it with:  python notify.py --test")


def main():
    parser = argparse.ArgumentParser(
        prog="notify",
        description="Set up and test Telegram alerts for JobRadar.",
    )
    parser.add_argument(
        "--setup", action="store_true",
        help="Find your Telegram chat id.",
    )
    parser.add_argument(
        "--test", action="store_true",
        help="Send a test message to check it all works.",
    )
    args = parser.parse_args()

    if args.setup:
        find_chat_id()
        return

    if args.test:
        token, chat_id = load_credentials()

        problem = check_credentials(token, chat_id)
        if problem:
            print("\n" + problem + "\n")
            sys.exit(1)

        if send("<b>JobRadar</b>\n\nTelegram alerts are working."):
            print("Sent. Check your phone.")
        else:
            print("Telegram refused the message. Check your token and chat id.")
            sys.exit(1)
        return

    parser.print_help()


if __name__ == "__main__":
    main()
