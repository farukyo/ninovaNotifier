---
description: Scan for read-modify-write races on users.json / ninova_data.json (stale snapshot saves)
argument-hint: "[path or git ref, default: whole repo]"
allowed-tools: Grep, Read, Glob, Bash(git diff:*), Bash(git log:*)
---

# /stale-write-scan

## What it does
Finds code that loads the whole user or course store, keeps it around (often across
network calls or background tasks), and later writes the whole dict back. Any change
made by another thread in between is silently lost.

## Based on finding
The review found this pattern over and over: the "add expired courses" flow lost courses
it had just added, manual checks overwrote users.json, and admin delete/force-otoders still
write stale snapshots (`bot/handlers/admin/callbacks.py`, `course_functions.py`). Atomic
helpers now exist in `core/storage.py`.

## When to call it
- Before merging any change that touches `bot/handlers/**`, `main.py` or `core/storage.py`.
- When a user reports "my change / course / subscription disappeared".

## Procedure
Scope: `$ARGUMENTS`. If a git ref is given, only inspect files changed since that ref
(`git diff --name-only $ARGUMENTS`). Otherwise scan the whole repo, excluding `.venv/` and `tests/`.

1. Grep for writers: `save_all_users(`, `save_grades(`, `atomic_json_write(`, `update_user_data(`.
2. For each hit, read the enclosing function and classify it:
   - **STALE-SNAPSHOT**: the argument comes from an earlier `load_all_users()` or
     `load_saved_grades()` / `load_admin_users()` / `load_admin_grades()` /
     `load_user_snapshot()` in the same function or a closure. HIGH if there is any
     network call, `time.sleep`, `submit_background_task` or user interaction between
     the load and the save. Otherwise MEDIUM.
   - **STALE-FIELD**: `update_user_data(chat_id, "urls", <list built from an earlier snapshot>)`
     after scraping. Also flag if the chat_id might no longer exist, because
     `update_user_data` creates ghost users.
   - **INDEX-MUTATION**: `urls.pop(i)` or `del ...["urls"][i]` on a snapshot. Flag if the
     index is not bounds-checked for negatives.
   - **ORDER-LOSS**: `list(set(...))` applied to URL lists. Menu indices depend on order.
   - OK: the write goes through `modify_user`, `delete_user`, `update_user_grades`,
     `delete_user_grades` or `delete_course_data`.
3. For each finding, propose the concrete replacement using the `core/storage.py` helpers,
   written as a code snippet in the repo's style (Turkish comments are fine).

## Output
A table with columns: severity, file:line, pattern, why it loses data, suggested fix.
Then list the helpers that are missing and would be needed. Do not edit files unless
the user explicitly asks.
