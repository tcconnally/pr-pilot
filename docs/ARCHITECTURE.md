# PR Pilot Architecture

> AI-native code quality service — 5-agent autonomous PR review pipeline

## System Overview

PR Pilot is a serverless application deployed on Google Cloud Run. It receives GitHub webhook events, runs a 5-agent sequential pipeline against pull request diffs using the Gemini API, and posts structured review results back to GitHub.

```
GitHub PR → Cloud Run Webhook → Orchestrator → [R→F→T→V→E] → GitHub Review
                                              ↓
                                         Gemini API
```

## Component Architecture

### 1. Webhook Receiver (`src/github_app/webhook.py`)

**Framework:** FastAPI + uvicorn
**Deployment:** Cloud Run (serverless, scales to zero)

Handles GitHub PR events (`opened`, `synchronize`, `reopened`). Verifies webhook signatures using HMAC-SHA256. Extracts PR metadata, fetches the diff and changed files via the GitHub API, and triggers the agent chain.

**Endpoints:**
- `POST /webhook/github` — Primary webhook receiver
- `GET /` — Service info
- `GET /health` — Health check for load balancers

**Authentication:** GitHub App installation tokens (JWT-based). The app authenticates as an installation to access private repos and post reviews.

### 2. GitHub API Client (`src/github_app/client.py`)

Thin async wrapper around the GitHub REST API using `httpx`. Operations:

| Method | Purpose |
|---|---|
| `get_pr_diff()` | Fetch raw diff + PR metadata |
| `get_pr_files()` | List changed files |
| `get_repo_file_listing()` | Recursive file listing for test framework detection |
| `post_review()` | Post PR review with APPROVE/REQUEST_CHANGES/COMMENT |
| `post_comment()` | Post general comment (fallback) |
| `get_installation_token()` | JWT exchange for installation access token |

### 3. Agent Base Class (`src/agents/base.py`)

All five agents inherit from `BaseAgent`, which provides:

- **Lazy Gemini client initialization:** The client is only created on first API call, allowing unit tests to run without an API key
- **Structured output:** Uses Gemini's `response_schema` feature to enforce typed JSON responses per agent
- **Exponential retry:** Via `tenacity` — up to 3 retries with 2-30s backoff
- **Structured logging:** Via `structlog` — every agent start/complete/gemini_call is logged with timing
- **Standardized results:** `AgentResult` dataclass with status, summary, findings, patches, metadata, timing

**Gemini Configuration:**
```python
config = types.GenerateContentConfig(
    temperature=0.2,          # Low temperature for consistent code review
    max_output_tokens=8192,   # Large enough for full reviews + patches
    system_instruction=...,    # Per-agent system prompt
    response_schema=...,       # Structured JSON output
    response_mime_type="application/json",
)
```

### 4. The 5-Agent Pipeline

#### Agent 1: Reviewer (`src/agents/reviewer.py`)
**Input:** PR diff, title, description, project rules
**Output:** Structured findings with severity (critical/high/medium/low), category (security/performance/style/testing/error_handling/bug), file location, and fix suggestion
**Schema:** `REVIEW_SCHEMA` — enforces typed output with required fields

#### Agent 2: Fixer (`src/agents/fixer.py`)
**Input:** Reviewer findings + original diff
**Output:** Code patches with type (replace/insert/delete), old/new snippets, line numbers, and reasoning
**Logic:** Fixes only what's fixable; escalates complex/risky fixes with reasons

#### Agent 3: Tester (`src/agents/tester.py`)
**Input:** PR diff, changed files, project file listing
**Output:** Detected framework, generated test files with content
**Logic:** Skips non-code changes (docs/config). Detects framework from file listing.

#### Agent 4: Verifier (`src/agents/verifier.py`)
**Input:** Generated patches + tests + original findings
**Output:** Pass/fail checks per patch with evidence
**Logic:** Syntax correctness, issue resolution, regression risk, test validity

#### Agent 5: Escalator (`src/agents/escalator.py`)
**Input:** All four prior agent results
**Output:** Decision (auto_approve/request_changes/escalate_to_human) with confidence score, review body, and inline comments
**Logic:** Auto-approves safe changes. Requests changes when fixes exist. Escalates critical/complex cases.

### 5. Orchestration Engine (`src/orchestration/engine.py`)

The `AgentChain` class manages the sequential execution:

1. Instantiate all 5 agents
2. Run Reviewer → pass findings to Fixer
3. Run Fixer → pass patches to Tester and Verifier
4. Run Tester → pass test files to Verifier
5. Run Verifier → pass all results to Escalator
6. Run Escalator → final decision
7. Persist complete state to `data/reviews/{chain_id}.json`

Each agent's result is serialized to JSON-safe dicts. The chain ID is a unique identifier (`pr-{number}-{timestamp}`) for audit trail.

### 6. Configuration (`src/config.py`)

All configuration from environment variables with sensible defaults:

| Variable | Default | Purpose |
|---|---|---|
| `GEMINI_API_KEY` | (required) | Gemini API authentication |
| `GEMINI_MODEL` | `gemini-2.5-pro` | Model selection |
| `GITHUB_APP_ID` | (required) | GitHub App identifier |
| `GITHUB_APP_PRIVATE_KEY` | (required) | App private key (PEM or path) |
| `GITHUB_WEBHOOK_SECRET` | (required) | HMAC signature verification |
| `MAX_AGENT_RETRIES` | 3 | Retry count for failed API calls |
| `AGENT_TIMEOUT_SECONDS` | 300 | Per-agent timeout |

## Data Flow

### PR Review Sequence
```
1. GitHub webhook → POST /webhook/github
2. Verify HMAC signature
3. Extract PR number, owner, repo
4. Get GitHub App installation token (JWT exchange)
5. Fetch PR diff via GitHub API
6. Fetch changed files list
7. Fetch repo file listing (for test framework detection)
8. Build pr_context dict
9. Run AgentChain.run(pr_context)
   a. Reviewer.execute(diff, rules) → findings
   b. Fixer.execute(findings, diff) → patches
   c. Tester.execute(diff, files, listing) → test_files
   d. Verifier.execute(patches, test_files, findings) → checks
   e. Escalator.execute(all_results) → decision + review
10. Post review to GitHub API
11. Persist state to data/reviews/
```

### Agent-to-Agent Communication
Each agent receives a context dict with the previous agent's output:
```python
# Example: Fixer receives
context = {
    "findings": reviewer_result.findings,  # List of finding dicts
    "diff": original_diff,                 # The PR diff
    "repo_name": "owner/repo",
    "project_rules": "...",
}
```

Results flow sequentially — no parallelism in the current implementation (by design; each agent needs the previous agent's output).

## Deployment

### Google Cloud Run

```bash
gcloud run deploy pr-pilot \
  --source . \
  --region us-central1 \
  --allow-unauthenticated \
  --set-env-vars GEMINI_API_KEY=...,GI...
```

**Why Cloud Run:**
- Serverless: scales to zero between PRs (cost ~$0 when idle)
- Managed TLS: handles HTTPS termination
- Container-native: Dockerfile-based deployment
- Built-in logging integration with Cloud Logging

### GitHub App Setup

1. Create GitHub App at https://github.com/settings/apps
2. Set webhook URL to Cloud Run endpoint (e.g., `https://pr-pilot-xxx.a.run.app/webhook/github`)
3. Set webhook secret
4. Generate private key
5. Install app on target repos
6. Set environment variables: `GITHUB_APP_ID`, `GITHUB_APP_PRIVATE_KEY`, `GITHUB_WEBHOOK_SECRET`

### CI/CD

GitHub Actions pipeline (`.github/workflows/ci.yml`):
- Lint with ruff
- Run pytest with coverage
- Matrix: Python 3.11 + 3.12
- Triggers on push/PR to main

## Performance

Measured from the end-to-end test (PR with 3 issues):

| Agent | Duration | Notes |
|---|---|---|
| Reviewer | 13.9s | Analyzed diff, found 3 issues |
| Fixer | 28.5s | Generated 3 patches |
| Tester | 15.9s | Generated 4 test files |
| Verifier | 17.2s | Validated patches + tests |
| Escalator | 18.4s | Decision: request_changes |
| **Total** | **93.9s** | Full autonomous pipeline |

**Bottleneck:** Gemini API latency (~15-30s per agent). Could be reduced with:
- Parallel API calls for independent agents
- Streaming responses
- Smaller model for simpler agents (Tester, Verifier)

## Security

- **Webhook verification:** HMAC-SHA256 signature validation on every webhook
- **GitHub App auth:** JWT-based installation tokens (never long-lived PATs)
- **Secret storage:** Google Cloud Secret Manager for API keys and private keys
- **No credential exposure:** `.env` is gitignored; credentials only in environment
- **Input validation:** Diff size limits prevent abuse; JSON schema validation on all structured outputs

## Limitations

1. **Sequential only:** Agents run in sequence, not parallel. Total latency = sum of all agent times.
2. **Text-only diffs:** No binary file analysis, no image diff support.
3. **Single-model:** All agents use Gemini. Specialized agents could use smaller/faster models.
4. **No incremental state:** Each PR run is independent. No learning across PRs.
5. **GitHub-only:** Only GitHub PRs are supported (not GitLab, Bitbucket).
