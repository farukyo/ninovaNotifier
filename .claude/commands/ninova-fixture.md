---
description: Turn a real (user-provided) Ninova/ITU HTML page into an anonymized test fixture plus a parser regression test
argument-hint: "<path to saved .html> <page kind: notlar|odevler|odev-detay|dosyalar|duyurular|duyuru-detay|kampus|login>"
allowed-tools: Read, Write, Grep, Glob, Bash(uv run pytest:*), Bash(uv run ruff:*)
---

# /ninova-fixture

## What it does
Takes an HTML page the developer saved from Ninova (or another ITU site) and does three
things:
1. Anonymizes it.
2. Stores it as `tests/fixtures/ninova/<kind>_<short-desc>.html`.
3. Writes a test that runs the matching parser in `services/ninova/scraper.py` on it and
   asserts the extracted values.

## Based on finding
Scraper correctness can't be checked without real pages, and this environment has no
network access to ninova.itu.edu.tr. These parts of the parsing logic are unverified and
have caused wrong or duplicate notifications:
- the submission status heuristics in `get_assignment_detail` / `get_assignments`
- login-page detection (`_looks_like_login_page`)
- redirects for courses the user can no longer access
- date parsing (unknown month becomes January)

## When to call it
Whenever a user reports a wrong notification, a missed notification, or a parse error.
Ask the developer to save the page (browser "Save page as → HTML only") and run this command.

## Procedure
1. Read the file given in `$ARGUMENTS`. **Anonymize** it before writing anything:
   - Replace student names, numbers, e-mails, usernames, grades that identify a person,
     and `__VIEWSTATE` / `__EVENTVALIDATION` values with placeholders.
   - Remove cookies and session tokens from inline scripts.
   - Keep structure, class and id attributes, and date formats exactly as they are.
2. Write the fixture file. Show the developer a short list of what was anonymized.
3. Map the page kind to its parser:
   - notlar: `get_grades`, with `http_request` monkeypatched
   - odevler: `get_assignments`, with `get_assignment_detail` stubbed
   - odev-detay: `get_assignment_detail`
   - dosyalar: `get_class_files`
   - duyurular: `get_announcements`
   - duyuru-detay: `get_announcement_detail`
   - kampus: `get_user_courses`
   - login: `_looks_like_login_page` must be True
4. Write `tests/test_fixture_<kind>_<desc>.py`. It loads the fixture through a monkeypatched
   `http_request` that returns a fake response with `.text`, `.url` and `.status_code`,
   then asserts the concrete values visible in the page, such as counts, names, dates and
   `is_submitted`.
5. Run it. If the parser gets it wrong, keep the test as `xfail(strict=True)` with the
   reason, and report the root cause in the parser.

## Output
The fixture path, the test path, the pass/xfail result, and any parser bug found.
