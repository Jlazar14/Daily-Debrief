# Daily Debrief

Automated daily Telegram brief — weather, class schedule, assignment due dates, and market summary, sent every morning at 8am via GitHub Actions.

## How it works

- `daily_brief.py` — the script that builds and sends the message. Pure standard library, no dependencies.
- `assignments.json` — due-date data, kept in sync with the [Assignment Tracker](https://claude.ai/code/artifact/92a92fb4-0613-4ae2-8554-4034fd5dc4cd) whenever it changes.
- `.github/workflows/daily-brief.yml` — runs the script daily on GitHub's servers, independent of any personal device being on.

## Setup

1. Add a repository secret named `TELEGRAM_BOT_TOKEN` (Settings → Secrets and variables → Actions) with the bot token from @BotFather.
2. That's it — the workflow runs automatically at 8am Central daily.

## Testing it manually

Go to the **Actions** tab → **Daily Debrief** → **Run workflow** → check "force_send" → **Run workflow**. This sends immediately regardless of the time of day, useful for confirming everything works end-to-end.

## Keeping assignments.json in sync

Whenever the Assignment Tracker gets a new class or due date, `assignments.json` here should get the same update.
