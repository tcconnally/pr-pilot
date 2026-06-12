"""
Orchestration engine — manages the full 5-agent chain lifecycle.
Event → spawn chain → collect results → post to GitHub.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

import structlog

from src.agents.base import AgentResult
from src.agents.reviewer import ReviewerAgent
from src.agents.fixer import FixerAgent
from src.agents.tester import TesterAgent
from src.agents.verifier import VerifierAgent
from src.agents.escalator import EscalatorAgent
from src.config import STATE_DIR

logger = structlog.get_logger(__name__)


class AgentChain:
    """Orchestrates the 5-agent PR review pipeline."""

    def __init__(self) -> None:
        self.reviewer = ReviewerAgent()
        self.fixer = FixerAgent()
        self.tester = TesterAgent()
        self.verifier = VerifierAgent()
        self.escalator = EscalatorAgent()
        self.agents_in_order = [
            self.reviewer,
            self.fixer,
            self.tester,
            self.verifier,
            self.escalator,
        ]

    async def run(self, pr_context: dict[str, Any]) -> dict[str, Any]:
        """Run the full agent chain on a pull request.

        Args:
            pr_context: Dict with keys:
                - diff: str (the PR diff)
                - pr_title: str
                - pr_description: str
                - repo_name: str
                - changed_files: list[str]
                - project_files: str (file listing)
                - project_rules: str (custom rules if any)
                - pr_number: int

        Returns:
            Dict with all agent results and the final decision.
        """
        chain_id = f"pr-{pr_context.get('pr_number', 'unknown')}-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S')}"
        logger.info("chain_started", chain_id=chain_id, repo=pr_context.get("repo_name"))

        results: dict[str, Any] = {
            "chain_id": chain_id,
            "started_at": datetime.now(timezone.utc).isoformat(),
            "pr_number": pr_context.get("pr_number"),
            "repo_name": pr_context.get("repo_name"),
        }

        # ── Agent 1: Reviewer ──────────────────────────────────────
        reviewer_result = await self.reviewer.run(pr_context)
        results["reviewer"] = self._serialize_result(reviewer_result)
        logger.info("agent_done", agent="reviewer", status=reviewer_result.status)

        # ── Agent 2: Fixer ────────────────────────────────────────
        fixer_context = {
            **pr_context,
            "findings": reviewer_result.findings,
        }
        fixer_result = await self.fixer.run(fixer_context)
        results["fixer"] = self._serialize_result(fixer_result)
        logger.info("agent_done", agent="fixer", status=fixer_result.status)

        # ── Agent 3: Tester ───────────────────────────────────────
        tester_context = {
            **pr_context,
            "patches": fixer_result.patches,
        }
        tester_result = await self.tester.run(tester_context)
        results["tester"] = self._serialize_result(tester_result)
        logger.info("agent_done", agent="tester", status=tester_result.status)

        # ── Agent 4: Verifier ─────────────────────────────────────
        verifier_context = {
            **pr_context,
            "patches": fixer_result.patches,
            "test_files": tester_result.patches,
            "findings": reviewer_result.findings,
        }
        verifier_result = await self.verifier.run(verifier_context)
        results["verifier"] = self._serialize_result(verifier_result)
        logger.info("agent_done", agent="verifier", status=verifier_result.status)

        # ── Agent 5: Escalator ────────────────────────────────────
        escalator_context = {
            "reviewer_result": results["reviewer"],
            "fixer_result": results["fixer"],
            "tester_result": results["tester"],
            "verifier_result": results["verifier"],
        }
        escalator_result = await self.escalator.run(escalator_context)
        results["escalator"] = self._serialize_result(escalator_result)
        logger.info(
            "chain_complete",
            chain_id=chain_id,
            decision=escalator_result.metadata.get("decision", "unknown"),
        )

        results["completed_at"] = datetime.now(timezone.utc).isoformat()
        results["decision"] = escalator_result.metadata.get("decision", "escalate_to_human")
        results["autonomy"] = results["decision"] != "escalate_to_human"

        # Persist review state
        self._save_state(chain_id, results)

        return results

    def _serialize_result(self, result: AgentResult) -> dict[str, Any]:
        """Convert AgentResult to a JSON-safe dict."""
        return {
            "agent_name": result.agent_name,
            "status": result.status,
            "summary": result.summary,
            "findings": result.findings,
            "patches": result.patches,
            "metadata": result.metadata,
            "started_at": result.started_at,
            "completed_at": result.completed_at,
            "duration_seconds": result.duration_seconds,
        }

    def _save_state(self, chain_id: str, results: dict[str, Any]) -> None:
        """Persist review session state to disk for audit trail."""
        STATE_DIR.mkdir(parents=True, exist_ok=True)
        state_path = STATE_DIR / f"{chain_id}.json"
        state_path.write_text(json.dumps(results, indent=2, default=str))
        logger.info("state_saved", path=str(state_path))
