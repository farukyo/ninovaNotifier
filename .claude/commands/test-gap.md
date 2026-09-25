---
description: Find untested high-risk code in a module and draft pytest tests using the repo's existing test patterns
argument-hint: "<module path, e.g. services/ninova/scraper.py or bot/handlers/admin/course_functions.py>"
allowed-tools: Read, Grep, Glob, Write, Bash(uv run pytest:*), Bash(uv run ruff:*)
---

# /test-gap

## What it does
Measures coverage for `$ARGUMENTS`, ranks the uncovered functions by risk, and writes
**draft** tests for the top ones into `tests/` (new files only). Then it runs them.

## Based on finding
Total coverage is 31%. Handlers are at 10–20%, `services/ninova/scraper.py` at 20%,
`services/*` other than ninova at 11–27%. `tests/unit/*` and `tests/integration/*` are
empty stubs. The bugs fixed so far (5-tuple unpack crash, password `TypeError`, stale
saves) would each have been caught by a single test.

## When to call it
- After fixing a bug, to pin it with a regression test.
- Before refactoring a module (for example moving check logic out of `main.py`).

## Procedure
1. Run `uv run pytest -q --cov=<module as dotted path> --cov-report=term-missing` and read
   the missing lines.
2. Rank uncovered functions using these risk signals: writes to storage, sends
   notifications, parses HTML, handles auth or admin, has branches on `status_code` or
   login detection.
3. For the top 3–5 functions, write tests following the existing conventions:
   - `tests/conftest.py` already sets a fake `TELEGRAM_TOKEN` and `ENCRYPTION_KEY`, so
     never require real secrets.
   - Isolate storage with `monkeypatch.setattr(core.storage, "USERS_FILE" / "DATA_FILE", tmp_path/...)`.
     See `tests/test_storage.py`.
   - Fake HTTP by monkeypatching `http_request` in the module under test.
     See `tests/test_ninova_grades_relogin.py`.
   - Fake Telegram by monkeypatching `bot` or `send_telegram_message`, and
     `time.sleep` to a no-op. See `tests/test_check_flow.py`.
   - For HTML parsers, use small inline HTML strings, or a fixture under
     `tests/fixtures/ninova/` if one exists (see `/ninova-fixture`).
   - Name each test after the behavior and add a one-line comment when it pins a
     regression.
4. Run `uv run pytest -q <new files>` and `uv run ruff check <new files>`. If a test fails
   because the code is actually wrong, keep the test, mark it
   `@pytest.mark.xfail(reason="BUG: ...", strict=True)` and report the bug.
   Never weaken an assertion just to get a pass.

## Output
The coverage before and after, the list of tests added and what each one pins, and any
bugs discovered.
