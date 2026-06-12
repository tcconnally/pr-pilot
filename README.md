# PR Pilot — AI-Native Code Quality Service

An autonomous 5-agent pipeline that reviews every pull request, finds bugs, security issues, and performance regressions — then generates and verifies fixes without human intervention.

## How It Works

```
PR Opened → Agent 1: Reviewer → Agent 2: Fixer → Agent 3: Tester → Agent 4: Verifier → Agent 5: Escalator → Review Posted
```

| Agent | Role | Output |
|---|---|---|
| **Reviewer** | Analyzes PR diff for bugs, security, performance, style | Structured findings with severity |
| **Fixer** | Generates minimal code patches for issues found | Git-ready patches with context |
| **Tester** | Detects test framework, generates tests for changed code | Test files with coverage notes |
| **Verifier** | Validates fixes and tests — no regressions | Pass/fail checks with evidence |
| **Escalator** | Decides: auto-approve, request changes, or escalate | Decision with confidence score |

## Quick Start

```bash
# Install
pip install -e ".[dev]"

# Configure
cp .env.example .env
# Fill in GEMINI_API_KEY, GITHUB_APP_ID, etc.

# Run
uvicorn src.main:app --host 0.0.0.0 --port 8080 --reload
```

## Requirements

- Python 3.11+
- Gemini API key (required by XPRIZE rules)
- GitHub App (for webhook events and PR API access)
- Google Cloud Run (for hosting — optional, works locally too)

## XPRIZE Entry

PR Pilot is an entry in the [Build with Gemini XPRIZE](https://xprize.devpost.com/). The service demonstrates AI-native operations: the 5-agent chain IS the business, not just a feature bolted onto one.

- **Category:** Entrepreneurship & Job Creation
- **Differentiator:** 90%+ autonomous code review — no human in the loop for standard reviews
- **License:** MIT
