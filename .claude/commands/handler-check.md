---
description: Check new or changed Telegram handlers against the project's handler rules (authz, None text, blocking work, callback_data)
argument-hint: "[git ref to diff against, default: origin/main]"
allowed-tools: Grep, Read, Glob, Bash(git diff:*), Bash(git merge-base:*)
---

# /handler-check

## What it does
Reviews every `@bot.message_handler` / `@bot.callback_query_handler` and every
`register_next_step_handler` target that was added or changed since `$ARGUMENTS`
(default `origin/main`) against the rules below. These rules come straight from bugs
found in this repo.

## Based on finding
Handler bugs were the most common category in the review:
- Registration crashed silently.
- An admin callback had no admin check.
- Admin rejections never answered the callback.
- Next-step handlers crash on photos or stickers.
- A full scan ran synchronously inside the polling thread.
- Arı24 buttons exceeded 64 bytes.
- A forged negative index deleted the last course.
- 9 admin commands were never registered.

The global `_BotExceptionHandler` swallows all of these, so they only show up as "the
bot doesn't respond".

## When to call it
Before opening a PR that touches `bot/**`, or when a button or command "does nothing".

## Rules (each violation is a finding)
1. **Registration**: every function meant to be a handler has a decorator or is referenced.
   Report `def admin_*_cmd` / `def handle_*` functions that nothing references.
2. **Authorization**: admin handlers call `is_admin(...)` before any side effect, and on
   rejection they call `bot.answer_callback_query(call.id, ...)` so the button stops spinning.
   `is_admin` must keep checking the **sender** (`from_user.id`) and require a private chat.
   Flag any admin check that falls back to `chat.id`, because that lets any member of an
   admin-configured group act as admin. Flag any admin side effect that is not behind
   `is_admin`.
3. **None text**: next-step handlers and `func=` filters must tolerate `message.text is None`
   (use `(message.text or "")`).
4. **Blocking work**: network scraping, `get_check_callback()()`, broadcast loops or
   `time.sleep` inside a handler must go through `core.scheduler.submit_background_task`.
5. **callback_data**: at most 64 **bytes** (UTF-8). Anything built from names must be
   byte-truncated, like `_club_key` in `ari24_commands.py`. Indices parsed with
   `parse_int_part` must be checked `0 <= idx < len(...)`.
6. **Indices vs. order**: indices must refer to the same ordering the button was built from
   (menus use the order of `load_saved_grades()[chat_id]`). Flag file-download buttons that
   use positional file indices in long-lived notifications.
7. **Data writes**: use the `core.storage` atomic helpers (see `/stale-write-scan`).
8. **Errors to users**: never send `str(e)` to users. Log with `logger.exception`.
9. **main.py access**: handlers must never import `main` (it would run the entry point a
   second time and split the check locks). Check logic lives in `bot/check_service.py`;
   import `check_user_updates` / `check_for_updates` from there.

## Output
For each handler: name, file:line, then PASS or each violated rule with a one-line
fix. Report only.
