# Contributing

Thanks for looking! This is a small personal project open-sourced for anyone who wants to self-host, fork, or send improvements upstream.

## Scope

The project targets a narrow use case: **one-gesture fact-checking of public Instagram reels and photo posts, triggered from iOS's share sheet.** Changes that stay within that scope are welcome. Changes that expand it (Android support, Stories/DMs/IGTV, scheduled background checks, multi-user accounts) are likely to be declined — see [PRD.md §3](PRD.md) and §9 for what's explicitly out of scope.

If you're not sure whether an idea fits, open an issue and ask before coding.

## Before you open a PR

1. **Read [PRD.md](PRD.md) first.** It's the source of truth for design decisions. If your change contradicts it, either update the PRD in the same PR or make the case in the PR description.
2. **Read the DEV WARNING at the top of `backend/pipeline.py`.** If you're touching the Instagram fetch layer, this rule about not batch-testing against real IG URLs is hard-earned — don't regress it.
3. **Don't commit secrets.** `.env`, `cookies.txt`, and anything matching `*secret*` or `*key*` are gitignored; don't work around the ignore.

## How to develop locally

```bash
git clone https://github.com/<your-fork>/ig-fact-checker.git
cd ig-fact-checker/backend
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # fill in your own API keys
uvicorn main:app --reload --port 8765
```

Hit any of the `/preview/*` endpoints to iterate on the UI without burning Claude credits or touching Instagram.

## Testing guidance (important)

- **UI / template changes:** use the `/preview/*` endpoints in [backend/main.py](backend/main.py). No IG call, no Claude call, pure fixtures.
- **Prompt / Claude logic:** hit `/preview/*` endpoints for the visual side; for prompt changes, manually test against ONE real IG URL only (never batch). See PRD §5.5 and §5.6.
- **IG fetch layer (`fetch_ig_metadata`):** this is the most sensitive area. The DEV WARNING comment block explains why. Use fixture `IGMedia` dataclass snapshots for anything broader than one real URL. Exceeding the ~5-URL-per-change budget on real IG traffic has historically tripped multi-hour rate-limits.
- **Automated checks:** pushes and PRs run pip-audit (CVE scan) and Bandit (static security linter) via `.github/workflows/security-scan.yml`. Keep them green.

## Style

- Python: 4-space indent, type hints where they're not painful, no docstring walls of text. Short comments only when the "why" isn't obvious.
- Commits: present-tense imperative ("Add carousel support", not "Added carousel support"). Include a "why" in the commit body if the change is non-obvious.
- PRs: one concern per PR. Describe what changed, why, and how you tested it.

## Things I'd welcome help with

- Custom-domain setup guide (Cloud Run domain mapping walkthrough)
- iCloud-shared Shortcut template (so [SHORTCUT.md](SHORTCUT.md)'s "easy path" actually works)
- More worked examples in the Claude prompt to reduce hedging (PRD §5.5)
- A proper fixture test harness that exercises the full pipeline without touching IG or Claude

## Things I'll probably decline

- Adding a database schema, user accounts, multi-user support
- Android support (no equivalent to iOS Shortcuts share sheet)
- Switching to a different LLM provider as the default (bring your own via env var instead)
- Support for Stories, DMs, carousels-with-video-items (see PRD §3)

## Licence

By submitting a PR you agree your contribution is licensed under the same MIT licence as the rest of the project (see [LICENSE](LICENSE)).
