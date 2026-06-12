"""
GitHub App webhook handler.
Receives PR events, triggers the agent chain, and posts results back to GitHub.
"""

from __future__ import annotations

import hashlib
import hmac
from typing import Any

import structlog
from fastapi import APIRouter, Header, HTTPException, Request

from src.orchestration.engine import AgentChain
from src.github_app.client import GitHubClient
from src.config import (
    ALLOW_UNSIGNED_WEBHOOKS,
    GITHUB_WEBHOOK_SECRET,
    GITHUB_APP_ID,
    GITHUB_APP_PRIVATE_KEY,
)

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/webhook", tags=["github"])


def verify_signature(payload: bytes, signature: str) -> bool:
    """Verify GitHub webhook signature.

    Fails closed: if no secret is configured we reject the request unless the
    operator has explicitly opted into an unsigned-dev bypass via
    ALLOW_UNSIGNED_WEBHOOKS=true. This must never be set in production.
    """
    if not GITHUB_WEBHOOK_SECRET:
        if ALLOW_UNSIGNED_WEBHOOKS:
            logger.warning("webhook_secret_not_configured_dev_bypass")
            return True
        logger.error("webhook_secret_not_configured_rejecting")
        return False

    if not signature:
        return False

    mac = hmac.new(
        GITHUB_WEBHOOK_SECRET.encode(),
        payload,
        hashlib.sha256,
    )
    expected = f"sha256={mac.hexdigest()}"
    return hmac.compare_digest(expected, signature)


@router.post("/github")
async def github_webhook(
    request: Request,
    x_github_event: str = Header(default=""),
    x_hub_signature_256: str = Header(default=""),
) -> dict[str, Any]:
    """Receive GitHub webhook events and trigger PR review."""
    body = await request.body()

    # Verify signature
    if not verify_signature(body, x_hub_signature_256):
        logger.error("invalid_signature")
        raise HTTPException(status_code=401, detail="Invalid signature")

    payload = await request.json()
    logger.info("webhook_received", event=x_github_event, action=payload.get("action", ""))

    # Only handle PR events
    if x_github_event not in ("pull_request",):
        return {"status": "ignored", "event": x_github_event}

    action = payload.get("action", "")
    if action not in ("opened", "synchronize", "reopened"):
        logger.info("action_ignored", action=action)
        return {"status": "ignored", "action": action}

    # Extract PR info
    pr = payload.get("pull_request", {})
    repo = payload.get("repository", {})
    installation = payload.get("installation", {})

    pr_number = pr.get("number")
    owner = repo.get("owner", {}).get("login", "")
    repo_name = repo.get("full_name", "")
    pr_title = pr.get("title", "")
    pr_description = pr.get("body", "") or ""

    if not pr_number or not owner:
        logger.error("missing_pr_info")
        return {"status": "error", "detail": "Missing PR number or owner"}

    logger.info("pr_event", owner=owner, repo=repo_name, pr=pr_number, action=action)

    # Get installation token for this repo
    try:
        gh_client = GitHubClient(token="")  # will be replaced
        installation_id = installation.get("id", 0)
        if installation_id and GITHUB_APP_ID and GITHUB_APP_PRIVATE_KEY:
            token = await gh_client.get_installation_token(
                installation_id, GITHUB_APP_ID, GITHUB_APP_PRIVATE_KEY
            )
            gh_client = GitHubClient(token=token)
        else:
            logger.warning("no_installation_token — using webhook context only")
            return {"status": "skipped", "detail": "GitHub App not configured"}
    except Exception as exc:
        logger.error("token_error", error=str(exc))
        return {"status": "error", "detail": f"Failed to get installation token: {exc}"}

    # Fetch PR diff and files
    try:
        diff_text, pr_data = await gh_client.get_pr_diff(owner, repo_name.split("/")[-1], pr_number)
        changed_files = [f["filename"] for f in await gh_client.get_pr_files(owner, repo_name.split("/")[-1], pr_number)]
        project_files_list = await gh_client.get_repo_file_listing(owner, repo_name.split("/")[-1])
    except Exception as exc:
        logger.error("fetch_error", error=str(exc))
        return {"status": "error", "detail": f"Failed to fetch PR data: {exc}"}

    # Build context for the agent chain
    pr_context = {
        "diff": diff_text,
        "pr_title": pr_title,
        "pr_description": pr_description,
        "repo_name": repo_name,
        "changed_files": changed_files,
        "project_files": "\n".join(project_files_list),
        "pr_number": pr_number,
        "project_rules": "",  # Could be loaded from .pr-pilot/config.yaml in the repo
    }

    # Run the agent chain
    chain = AgentChain()
    results = await chain.run(pr_context)

    # Post results to GitHub
    decision = results.get("decision", "escalate_to_human")
    escalator = results.get("escalator", {})
    review_body = ""
    review_comments = []

    if escalator.get("findings"):
        finding = escalator["findings"][0] if escalator["findings"] else {}
        review_body = finding.get("review_body", _build_fallback_review(results))
        review_comments = finding.get("review_comments", [])
    else:
        review_body = _build_fallback_review(results)

    github_event_map = {
        "auto_approve": "APPROVE",
        "request_changes": "REQUEST_CHANGES",
        "escalate_to_human": "COMMENT",
    }
    github_event = github_event_map.get(decision, "COMMENT")

    try:
        await gh_client.post_review(
            owner,
            repo_name.split("/")[-1],
            pr_number,
            body=review_body,
            event=github_event,
            comments=review_comments if review_comments else None,
        )
        logger.info("review_posted", pr=pr_number, decision=decision, event=github_event)
    except Exception as exc:
        logger.error("post_review_error", error=str(exc))
        # Fallback: post a simple comment
        try:
            await gh_client.post_comment(owner, repo_name.split("/")[-1], pr_number, review_body)
        except Exception:
            pass

    return {
        "status": "complete",
        "chain_id": results.get("chain_id"),
        "decision": decision,
        "autonomy": results.get("autonomy"),
    }


def _build_fallback_review(results: dict[str, Any]) -> str:
    """Build a review body from chain results when the escalator output is missing."""
    reviewer = results.get("reviewer", {})
    fixer = results.get("fixer", {})
    verifier = results.get("verifier", {})

    body = "## PR Pilot Review\n\n"
    body += f"**Reviewer (Agent 1):** {reviewer.get('summary', 'No findings.')}\n\n"

    findings = reviewer.get("findings", [])
    if findings:
        body += "### Issues Found\n\n"
        for f in findings:
            body += f"- **[{f.get('severity', '?')}]** {f.get('description', 'Issue')} "
            body += f"(`{f.get('file', '?')}:{f.get('line', '?')}`)\n"

    body += f"\n**Fixer (Agent 2):** {fixer.get('summary', 'No fixes generated.')}\n"
    body += f"\n**Verifier (Agent 4):** {verifier.get('summary', 'Verification skipped.')}\n"

    decision = results.get("decision", "unknown")
    body += f"\n**Decision:** `{decision}`\n"
    body += "\n---\n*Review by PR Pilot — AI-native code quality service.*"

    return body
