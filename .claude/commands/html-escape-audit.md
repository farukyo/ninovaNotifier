---
description: Find user/scraped text sent to Telegram with parse_mode="HTML" without escaping, and HTML split mid-tag
argument-hint: "[path or git ref, default: whole repo]"
allowed-tools: Grep, Read, Glob, Bash(git diff:*)
---

# /html-escape-audit

## What it does
Checks every Telegram send that uses `parse_mode="HTML"` (`bot.send_message`,
`reply_to`, `edit_message_text`, `send_photo` captions, `send_telegram_message`,
`send_telegram_document` captions). For each one it verifies that interpolated values
coming from users or scraped pages are passed through `core.utils.escape_html` or
`sanitize_html_for_telegram`.

## Based on finding
The review found more than 25 places that interpolate raw values into HTML messages:
course and assignment names (`grade_commands.py`, `course_functions.py`, `bot/utils.py`),
usernames, SKS meal names, calendar events, Rehber search input, and admin broadcast
and log text. A single `&` or `<` in any of them makes Telegram reject the whole message
("can't parse entities"), so the notification is silently lost. Separately, several
places split long HTML with `split_long_message` or slicing, which can break tags in half.

## When to call it
- After adding or changing any message text or a new scraper field shown to users.
- When logs show `can't parse entities` or a user says "the bot didn't reply".

## Procedure
Scope: `$ARGUMENTS`. If it is a ref, only check changed files.

1. Grep `parse_mode="HTML"` and `send_telegram_message(` / `send_telegram_document(`.
2. For each call, find every `{...}` interpolation in the text (including strings built
   earlier in the function with `+=`). Classify each value's source:
   - constant or number: OK
   - `message.text`, callback data, username, anything from users.json: USER
   - scraper output (course_name, grade keys, assignment/announcement/file names, SKS,
     Arı24, calendar, Rehber fields): SCRAPED
   - exception text `{e}`: EXCEPTION (it also leaks internals to users)
3. USER or SCRAPED values without `escape_html(...)` are findings (HIGH if in a notification
   path under `main.py` or `services/*/announcer.py`, otherwise MEDIUM).
   Values inside attributes (`href='{url}'`) also need quote safety. Note that `escape_html`
   does not escape quotes.
4. Flag any split of an HTML string (`split_long_message`, `[i:i+N]` slicing, manual
   chunking) that is sent with `parse_mode="HTML"` and has no plain-text fallback.

## Output
Findings grouped by file: file:line, value, source, severity, and the fix written as
`escape_html(x)` or a fallback. End with a count per severity. Report only; edit files
only when the user asks.
