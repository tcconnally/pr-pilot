"""Tests for PR Pilot agents, orchestration, and GitHub client."""

import pytest

from src.agents.base import AgentResult
from src.agents.reviewer import ReviewerAgent, REVIEWER_SYSTEM_PROMPT
from src.agents.fixer import FixerAgent
from src.agents.tester import TesterAgent
from src.agents.verifier import VerifierAgent
from src.agents.escalator import EscalatorAgent
from src.orchestration.engine import AgentChain
from src.github_app.client import GitHubClient


class TestReviewerAgent:
    """Unit tests for the Reviewer agent (no Gemini calls)."""

    def test_build_system_prompt(self):
        agent = ReviewerAgent()
        prompt = agent._build_system_prompt()
        assert "expert code reviewer" in prompt
        assert "security" in prompt.lower()

    def test_agent_name(self):
        agent = ReviewerAgent()
        assert agent.name == "reviewer"

    def test_system_prompt_contains_required_sections(self):
        prompt = REVIEWER_SYSTEM_PROMPT
        required = ["security", "performance", "style", "testing", "error_handling"]
        for term in required:
            assert term in prompt.lower(), f"'{term}' missing from system prompt"


class TestFixerAgent:
    def test_build_system_prompt(self):
        agent = FixerAgent()
        prompt = agent._build_system_prompt()
        assert "minimal" in prompt.lower()
        assert "patch" in prompt.lower()

    def test_agent_name(self):
        agent = FixerAgent()
        assert agent.name == "fixer"

    @pytest.mark.asyncio
    async def test_execute_no_findings(self):
        agent = FixerAgent()
        result = await agent.execute({"findings": [], "repo_name": "test/repo", "diff": ""})
        assert result.status == "pass"
        assert "nothing to do" in result.summary.lower()


class TestTesterAgent:
    def test_build_system_prompt(self):
        agent = TesterAgent()
        prompt = agent._build_system_prompt()
        assert "test framework" in prompt.lower()

    def test_agent_name(self):
        agent = TesterAgent()
        assert agent.name == "tester"

    @pytest.mark.asyncio
    async def test_execute_skip_docs_changes(self):
        agent = TesterAgent()
        result = await agent.execute({
            "diff": "+Some documentation update",
            "changed_files": ["README.md", "CHANGELOG.md", "docs/config.yaml"],
            "repo_name": "test/repo",
        })
        assert result.status == "skip"


class TestVerifierAgent:
    def test_build_system_prompt(self):
        agent = VerifierAgent()
        prompt = agent._build_system_prompt()
        assert "verif" in prompt.lower()

    def test_agent_name(self):
        agent = VerifierAgent()
        assert agent.name == "verifier"

    @pytest.mark.asyncio
    async def test_execute_nothing_to_verify(self):
        agent = VerifierAgent()
        result = await agent.execute({})
        assert result.status == "pass"
        assert "nothing to verify" in result.summary.lower()


class TestEscalatorAgent:
    def test_build_system_prompt(self):
        agent = EscalatorAgent()
        prompt = agent._build_system_prompt()
        assert "auto_approve" in prompt
        assert "request_changes" in prompt
        assert "escalate_to_human" in prompt

    def test_agent_name(self):
        agent = EscalatorAgent()
        assert agent.name == "escalator"


class TestAgentChain:
    def test_chain_instantiation(self):
        chain = AgentChain()
        assert len(chain.agents_in_order) == 5
        names = [a.name for a in chain.agents_in_order]
        assert names == ["reviewer", "fixer", "tester", "verifier", "escalator"]

    def test_serialize_result(self):
        chain = AgentChain()
        result = AgentResult(
            agent_name="test_agent",
            status="pass",
            summary="All good",
            findings=[{"severity": "low", "file": "test.py"}],
        )
        serialized = chain._serialize_result(result)
        assert serialized["agent_name"] == "test_agent"
        assert serialized["status"] == "pass"
        assert len(serialized["findings"]) == 1


class TestGitHubClient:
    def test_client_initialization(self):
        client = GitHubClient(token="test-token")
        assert client.token == "test-token"
        assert "Authorization" in client.headers
        assert "test-token" in client.headers["Authorization"]
