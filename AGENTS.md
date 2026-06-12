# AGENTS.md — PR Pilot

## What This Is

PR Pilot is an AI-native code quality service for the Build with Gemini XPRIZE. A 5-agent autonomous pipeline (Reviewer → Fixer → Tester → Verifier → Escalator) handles the entire PR review lifecycle.

## Project Structure

```
pr-pilot/
├── src/
│   ├── main.py                  # FastAPI entrypoint (Cloud Run deployable)
│   ├── config.py                # Environment-based configuration
│   ├── agents/
│   │   ├── base.py              # Base agent with Gemini API, retry, logging
│   │   ├── reviewer.py          # Agent 1: Code review
│   │   ├── fixer.py             # Agent 2: Patch generation
│   │   ├── tester.py            # Agent 3: Test generation
│   │   ├── verifier.py          # Agent 4: Quality gate
│   │   └── escalator.py         # Agent 5: Decision maker
│   ├── orchestration/
│   │   └── engine.py            # Agent chain (sequential execution)
│   └── github_app/
│       ├── client.py            # GitHub REST API client
│       └── webhook.py           # Webhook receiver + chain trigger
├── tests/                       # Pytest tests
├── docs/                        # Architecture, submission materials
├── assets/                      # Thumbnails, diagrams
├── pyproject.toml               # Dependencies + tool config
└── .env.example                 # Environment template
```

## Key Dependencies

- **FastAPI** + uvicorn — webhook receiver
- **google-generativeai** — Gemini API (XPRIZE requirement)
- **httpx** — async GitHub API calls
- **PyJWT** — GitHub App authentication
- **structlog** — structured agent logging
- **tenacity** — retry logic for API calls

## How The Agents Work

Each agent inherits from `BaseAgent` which provides:
- Gemini API access with structured output support
- Exponential retry on failure
- Structured JSON logging
- Timing and metadata capture

The `AgentChain` in `orchestration/engine.py` runs them sequentially, passing context from each agent to the next. Results are persisted to `data/reviews/` for audit trail.

## Decision Logic (Escalator)

- **auto_approve**: All issues fixed, verifier passed, no critical findings
- **request_changes**: Issues found with fixes attached as review comments
- **escalate_to_human**: Critical security bugs, complex refactors, ambiguous changes

## Running Tests

```bash
pip install -e ".[dev]"
pytest tests/ -v
```

## Deployment (Google Cloud Run)

```bash
gcloud run deploy pr-pilot \
  --source . \
  --region us-central1 \
  --allow-unauthenticated \
  --set-env-vars GEMINI_API_KEY=...,GITHUB_APP_ID=...
```
