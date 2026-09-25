---
description: List stub modules, unregistered handlers, shadowed modules and duplicate implementations left over from the unfinished migration
allowed-tools: Grep, Read, Glob, Bash(uv run python:*), Bash(git log:*)
---

# /dead-code-audit

## What it does
Produces an inventory of code that looks alive but isn't. For each item it recommends
**delete**, **wire up** or **merge**, with the evidence behind the call.

## Based on finding
The "Step 5/6 migration" was left half-done. The review found:
- 22 docstring-only stub modules, for example `bot/router.py`, `bot/handlers/*_handler.py`,
  `bot/middlewares/*`, `*/models.py`, `tests/unit/*` (removed in the first cleanup; this
  command keeps new ones from piling up again)
- `AppConfig.from_env` raising `NotImplementedError`
- 9 admin command functions with no decorator
- `bot/keyboards.py` shadowed by the `bot/keyboards/` package
- two `LoginFailedError` classes (`core/exceptions.py` is imported nowhere)
- two encrypt/decrypt implementations
- two atomic-write implementations
- two month maps

Because of these, contributors edit the wrong file, and the README describes a
`common/` directory that no longer exists.

## When to call it
Before a refactor, or when onboarding someone. Re-run it after cleanup to confirm nothing
is left.

## Procedure
1. **Stubs**: files whose body is only a docstring, `from __future__`, `pass`, or
   `NotImplementedError`.
2. **Unreferenced functions and classes**: for each top-level `def` or `class` in
   `bot/`, `core/`, `services/` and `main.py`, grep for references outside its own
   definition. Handlers count as referenced only if they carry a `@bot.*_handler`
   decorator or are passed to `register_next_step_handler` / `submit_background_task`.
3. **Shadowing**: a `x.py` next to an `x/` package.
4. **Duplicates**: same-named or clearly equivalent functions and classes in different
   modules. Compare their bodies and say which one is actually used.
5. **Unreachable branches**: filters that make a branch impossible. For example,
   `kontrol_command_handler` only matches the text "🔄 Kontrol", so `text[1]` can never be
   "force" or "ders".
6. For each item, check `git log -1 --format=%cr -- <file>` to judge how stale it is.

## Output
A table with columns: path:line, kind, evidence (grep result or reason), recommendation.
Delete nothing. This command only reports.
