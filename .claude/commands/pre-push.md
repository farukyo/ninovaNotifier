---
description: Run the full local gate that CI + production deploy depend on, before pushing to main
allowed-tools: Bash(uv run ruff:*), Bash(uv run pytest:*), Bash(uv run detect-secrets-hook:*), Bash(uv run python -c:*), Bash(git diff:*), Bash(git status:*), Bash(git ls-files:*)
---

# /pre-push

## What it does
Runs every check that stands between a push to `main` and production, and adds the
checks CI is missing.

## Based on finding
Every push to `main` bumps the version, pushes a commit and deploys straight to the VPS
(`git pull && uv sync && pm2 restart`). There is no backup, no health check and no
rollback. CI's `detect-secrets scan --baseline` can never fail. The import-time crash
(bot is `None` without a token) and the check-loop crash would only have been caught at
runtime.

## When to call it
Before every push or merge to `main`.

## Steps (stop at the first failure and explain it)
1. `uv run ruff check .` and `uv run ruff format --check .`
2. `uv run pytest -q`
3. Secret check that actually fails, run on changed files only:
   `uv run detect-secrets-hook --baseline .secrets.baseline $(git diff --name-only origin/main...HEAD)`
4. Import smoke test, the same imports production does:
   `TELEGRAM_TOKEN=1:x ENCRYPTION_KEY=<generated> uv run python -c "import main"`.
   Generate the key with `Fernet.generate_key()`. Do not use real secrets.
5. Look at the diff for the deploy risks CI can't see:
   - changes to the shape of `data/*.json` (users.json, ninova_data.json) with no
     backward-compatible read path
   - new env vars not added to `secrets/.env.example` and the README
   - new dependencies: `uv.lock` must be updated
   - `.github/workflows/*` changes that touch deploy
   - `git status` must be clean, with no untracked files that were meant to be committed.

## Output
A checklist with pass or fail for each step. For a failure, give the exact command output
excerpt and the suggested fix. Finish with a one-line "safe to push: yes/no".
