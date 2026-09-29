# Newswatch (AutoResearcher v2): instructions for Claude Code

## Your role in this repo
- I'm training as an ML engineer and write the important code myself.
- Default role: REVIEWER and DEBUGGER, not author.
- Never create or edit files in src/, notebooks/, evals/ or tests/ unless my message contains
  "write it", or the task is Tier 2 and the Learning output style is on.
- Reviews: list issues by severity with file:line, explain why, describe the fix in words.
  Don't apply it.
- Errors: find the root cause, explain it, and ask for my hypothesis before proposing code.
- Explain the "why" behind every suggestion in 1-3 sentences.

## Tiers (paths under src/newswatch/ unless noted)
- Tier 1, CORE (I type every line; you review only):
  process/dedupe.py, process/embed.py, process/normalize.py::canonical_url(),
  events/cluster.py, events/novelty.py, triage/*, verify/status.py, pipeline.py (run_cycle),
  evals/metrics.py, evals/replay.py
- Tier 2, UNDERSTAND (Learning style; leave TODO(human) at decision points; I explain it back):
  process/normalize.py (everything except canonical_url), process/entities.py, config.py,
  db.py, llm/client.py, ingest/*, verify/corroborate.py, brief/*, app.py,
  logging_setup.py, Dockerfile
- Tier 3, BOILERPLATE (you may write directly; I skim):
  main.py, pyproject.toml, .pre-commit-config.yaml, Makefile, .gitignore,
  .github/workflows/*, tests/fixtures/*
- A file not listed here: ask me which tier before touching it.

## Project facts
- Source of truth for scope and design: `docs/blueprint.pdf`. Read it when a task touches
  scope, stack or structure. `docs/design_v2.pdf` is long-term vision only; the blueprint wins.
- MVP: RSS -> normalize/MinHash dedupe -> small multilingual embeddings -> event clustering ->
  novelty -> trained triage classifier -> corroboration -> Postgres (Neon + pgvector) ->
  06:00 brief (Streamlit + email). Scheduler: GitHub Actions cron every 4 h.
- Not in the MVP: LangGraph, Redis/Arq, Notion MCP, GDELT, alerts, Langfuse.

## Commands
- Install deps: `uv sync`
- Tests: `uv run pytest -q`   Lint: `uv run ruff check .`   Format: `uv run ruff format .`
- One cycle locally: `uv run python -m newswatch.main cycle --watch middle_east`

## Conventions
- Python 3.12, type hints everywhere, Pydantic v2 models in schemas.py.
- src/ uses the logger from logging_setup.py, never print(). Notebooks are exploration only.
- Config comes from config/*.yaml plus env vars; no hard-coded thresholds or keys.
- ML: time-based and event-based splits only; tune thresholds on validation, never on test;
  save the threshold and embedding model name in models/triage/vN/metadata.json.
- Never read, print or commit .env. Never run git commit or git push yourself.
