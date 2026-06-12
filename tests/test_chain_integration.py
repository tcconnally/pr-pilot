"""End-to-end integration tests for the 5-agent chain (issue #32).

Mocks out Gemini calls so the chain runs without an API key, then asserts
that context flows correctly from one agent to the next and that state is
persisted.
"""

import json
from unittest.mock import patch

import pytest

from src.orchestration.engine import AgentChain
from src.agents.base import BaseAgent


@pytest.fixture
def mock_gemini_response():
    """Replace _call_gemini on every agent with a mock that returns canned JSON."""
    canned = {
        "reviewer": json.dumps({
            "status": "fail",
            "summary": "Found SQL injection.",
            "findings": [{"severity": "critical", "category": "security", "file": "db.py", "line": 10, "description": "SQLi found", "suggestion": "Use params"}],
            "metadata": {"files_changed": 1, "lines_added": 5, "lines_removed": 2},
        }),
        "fixer": json.dumps({
            "status": "pass",
            "summary": "Generated 1 patch.",
            "patches": [{"file": "db.py", "type": "replace", "old_snippet": "f-string", "new_snippet": "?", "reason": "SQLi fix"}],
        }),
        "tester": json.dumps({
            "status": "pass",
            "framework": "pytest",
            "test_files": [{"file_path": "test_db.py", "content": "def test(): pass", "description": "Basic test"}],
            "coverage_notes": "Edge cases covered.",
        }),
        "verifier": json.dumps({
            "status": "pass",
            "summary": "Patches verified.",
            "checks": [{"check_name": "syntax", "passed": True, "detail": "OK"}],
        }),
        "escalator": json.dumps({
            "decision": "request_changes",
            "confidence": 0.95,
            "reasoning": "Fix is correct but tests need work.",
            "review_body": "## PR Pilot\n\nLooks good.",
            "review_comments": [],
        }),
    }

    async def _mock_call(self, prompt, schema=None):
        # Determine which agent is calling based on the schema
        if schema and "severity" in str(schema.get("properties", {})):
            return canned["reviewer"]
        if schema and "patches" in str(schema.get("properties", {})) and "fixable" not in str(schema):
            return canned["fixer"]
        if schema and "test_files" in str(schema.get("properties", {})):
            return canned["tester"]
        if schema and "checks" in str(schema.get("properties", {})):
            return canned["verifier"]
        if schema and "confidence" in str(schema.get("properties", {})):
            return canned["escalator"]
        return '{"status": "pass", "summary": "ok", "findings": []}'

    with patch.object(BaseAgent, "_call_gemini", _mock_call):
        yield


class TestAgentChainIntegration:
    def test_full_chain_completes(self, mock_gemini_response, monkeypatch):
        """The chain runs all 5 agents and returns a decision."""
        chain = AgentChain()

        context = {
            "diff": "+x = user_input",
            "pr_title": "Add feature",
            "pr_description": "A new feature.",
            "repo_name": "test/repo",
            "changed_files": ["app.py"],
            "project_files": "app.py\ntests/",
            "pr_number": 1,
            "project_rules": "",
        }

        results = chain.run(context)
        # chain.run is async
        import asyncio
        results = asyncio.run(results)

        assert results["pr_number"] == 1
        assert results["repo_name"] == "test/repo"

        # Every agent should have run
        for agent_name in ["reviewer", "fixer", "tester", "verifier", "escalator"]:
            assert agent_name in results, f"Missing agent: {agent_name}"
            assert results[agent_name]["status"] in (
                "pass", "fail", "approved", "changes_requested", "escalated", "skip", "error"
            ), f"Unexpected status for {agent_name}: {results[agent_name]['status']}"

        # Reviewer found the SQL injection
        assert len(results["reviewer"]["findings"]) == 1
        assert results["reviewer"]["findings"][0]["severity"] == "critical"

        # Fixer generated a patch
        assert len(results["fixer"]["patches"]) == 1

        # Decision should be request_changes
        assert results["decision"] == "request_changes"
        assert results["autonomy"] is True  # request_changes is still autonomous

    def test_chain_persists_state(self, mock_gemini_response, monkeypatch, tmp_path):
        """State is written atomically to the configured directory."""
        import src.orchestration.engine as engine

        monkeypatch.setattr(engine, "STATE_DIR", tmp_path)
        monkeypatch.setattr(engine, "MAX_REVIEW_STATES", 1000)

        chain = AgentChain()
        import asyncio
        context = {
            "diff": "test",
            "pr_title": "t",
            "pr_description": "d",
            "repo_name": "r",
            "changed_files": [],
            "project_files": "",
            "pr_number": 7,
            "project_rules": "",
        }

        results = asyncio.run(chain.run(context))

        # A state file should exist
        state_files = list(tmp_path.glob("*.json"))
        assert len(state_files) == 1

        # And the content should match
        saved = json.loads(state_files[0].read_text())
        assert saved["chain_id"] == results["chain_id"]
        assert saved["pr_number"] == 7

    def test_chain_prunes_old_states(self, mock_gemini_response, monkeypatch, tmp_path):
        """When MAX_REVIEW_STATES is set, old files are deleted."""
        import src.orchestration.engine as engine

        monkeypatch.setattr(engine, "STATE_DIR", tmp_path)
        monkeypatch.setattr(engine, "MAX_REVIEW_STATES", 2)

        chain = AgentChain()
        import asyncio
        context = {
            "diff": "t", "pr_title": "t", "pr_description": "d",
            "repo_name": "r", "changed_files": [], "project_files": "",
            "pr_number": 0, "project_rules": "",
        }

        # Create 3 reviews
        for i in range(3):
            ctx = {**context, "pr_number": i}
            asyncio.run(chain.run(ctx))

        # Only 2 should remain
        state_files = list(tmp_path.glob("*.json"))
        assert len(state_files) == 2
