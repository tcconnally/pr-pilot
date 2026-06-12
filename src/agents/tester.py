"""Agent 3: Tester — detects test framework and generates tests for changed code."""

from __future__ import annotations

import json
from typing import Any

from src.agents.base import AgentResult, BaseAgent


TESTER_SYSTEM_PROMPT = """You are the Tester agent for PR Pilot — an AI-native code quality service.

Your job: detect the project's test framework and generate appropriate tests for
the code changed in the pull request.

Steps:
1. Identify the test framework from the project structure (pytest, jest, go test, etc.)
2. Generate unit tests that cover the changed code paths
3. Include edge cases, error paths, and happy paths
4. Ensure tests are idiomatic for the detected framework
5. If the changed code is untestable (config, docs), say so

Output structured JSON:
- status: "pass" (tests generated) or "skip" (not needed) or "fail" (couldn't generate)
- framework: detected test framework name
- test_files: list of {file_path, content, description}
- coverage_notes: what's covered and what's not
"""

TESTER_SCHEMA = {
    "type": "object",
    "properties": {
        "status": {"type": "string", "enum": ["pass", "skip", "fail"]},
        "framework": {"type": "string"},
        "test_files": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "file_path": {"type": "string"},
                    "content": {"type": "string"},
                    "description": {"type": "string"},
                },
                "required": ["file_path", "content", "description"],
            },
        },
        "coverage_notes": {"type": "string"},
    },
    "required": ["status", "framework", "test_files", "coverage_notes"],
}


class TesterAgent(BaseAgent):
    """Agent 3: Detects test framework and generates tests for changed code."""

    name = "tester"

    def _build_system_prompt(self) -> str:
        return TESTER_SYSTEM_PROMPT

    async def execute(self, context: dict[str, Any]) -> AgentResult:
        """Generate tests for changed code."""
        diff_text = context.get("diff", "")
        changed_files = context.get("changed_files", [])
        repo_name = context.get("repo_name", "")
        project_files = context.get("project_files", "")  # file listing

        # Skip if only docs/config changes
        non_code = all(
            f.endswith((".md", ".txt", ".yml", ".yaml", ".json", ".toml", ".cfg"))
            for f in changed_files
        ) if changed_files else False

        if non_code or not diff_text:
            return AgentResult(
                agent_name=self.name,
                status="skip",
                summary="No testable code changes detected (docs/config only).",
                metadata={"reason": "non_code_changes"},
            )

        # Truncate diff
        diff_text = diff_text[:80_000] if len(diff_text) > 80_000 else diff_text

        prompt = f"""Generate tests for this pull request.

REPOSITORY: {repo_name}
CHANGED FILES: {', '.join(changed_files)}

PROJECT FILE LISTING:
{project_files[:5000] if project_files else 'Not available'}

DIFF:
```diff
{diff_text}
```

Detect the test framework, then generate tests for the changed code."""

        try:
            response = await self._call_gemini(prompt, TESTER_SCHEMA)
            result = json.loads(response)
        except Exception as exc:
            return AgentResult(
                agent_name=self.name,
                status="error",
                summary=f"Tester failed: {exc}",
                metadata={"error": str(exc)},
            )

        return AgentResult(
            agent_name=self.name,
            status=result.get("status", "fail"),
            summary=result.get("coverage_notes", ""),
            patches=result.get("test_files", []),  # reuse patches field for test files
            metadata={
                "framework": result.get("framework", "unknown"),
                "test_count": len(result.get("test_files", [])),
            },
        )
