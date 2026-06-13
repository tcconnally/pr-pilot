"""
Cloud Logging integration for PR Pilot agent audit trail.

Uses Google Cloud Logging to stream structured agent execution logs.
When running on Cloud Run, logs are automatically ingested by Cloud Logging
via stdout. This module provides a programmatic handler for explicit
structured entries with agent trace context.

Requires: google-cloud-logging (added to dependencies)
"""

from __future__ import annotations

import json
import logging
import os
import sys
from datetime import datetime, timezone
from typing import Any

# Lightweight fallback when google-cloud-logging is not installed
_HAS_CLOUD_LOGGING = False
try:
    import google.cloud.logging
    from google.cloud.logging_v2.handlers import CloudLoggingHandler
    _HAS_CLOUD_LOGGING = True
except ImportError:
    pass


class AgentAuditLogger:
    """Structured audit logger for agent execution traces.

    Writes to Google Cloud Logging when the library is available (GCP
    deployment), falling back to JSON-on-stdout (Cloud Run auto-ingestion)
    and local structlog.

    Each log entry carries:
      - chain_id: the review session identifier
      - agent: the agent name (reviewer, fixer, tester, verifier, escalator)
      - event: lifecycle event (started, completed, error)
      - duration_seconds: agent execution time
      - metadata: arbitrary structured data (findings, patches, decision)
    """

    def __init__(self) -> None:
        self._logger = logging.getLogger("pr-pilot-audit")
        self._logger.setLevel(logging.INFO)
        self._handler: logging.Handler | None = None

        if _HAS_CLOUD_LOGGING and os.getenv("K_SERVICE"):
            # Running on Cloud Run — set up the Cloud Logging handler
            try:
                client = google.cloud.logging.Client()
                self._handler = CloudLoggingHandler(client, name="pr-pilot-agents")
                self._logger.addHandler(self._handler)
                self._logger.propagate = False
            except Exception:
                pass

    def log_agent_event(
        self,
        chain_id: str,
        agent: str,
        event: str,
        duration_seconds: float | None = None,
        metadata: dict[str, Any] | None = None,
        repo_name: str | None = None,
        pr_number: int | None = None,
    ) -> None:
        """Emit a structured agent audit event."""
        entry = {
            "chain_id": chain_id,
            "agent": agent,
            "event": event,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "repo_name": repo_name,
            "pr_number": pr_number,
        }
        if duration_seconds is not None:
            entry["duration_seconds"] = round(duration_seconds, 2)
        if metadata:
            # Sanitize: drop large fields that bloat logs
            sanitized = {}
            for k, v in metadata.items():
                if isinstance(v, str) and len(v) > 2000:
                    sanitized[k] = v[:2000] + "..."
                elif isinstance(v, (list, dict)):
                    raw = json.dumps(v, default=str)
                    sanitized[k] = raw[:2000] if len(raw) > 2000 else json.loads(raw) if isinstance(v, dict) else v
                else:
                    sanitized[k] = v
            entry["metadata"] = sanitized

        # Always emit JSON to stdout (Cloud Run picks this up)
        json.dump(entry, sys.stdout, default=str)
        sys.stdout.write("\n")
        sys.stdout.flush()

        # Also log via the structured handler if available
        self._logger.info(json.dumps(entry, default=str))

    def log_chain_event(
        self,
        chain_id: str,
        event: str,
        decision: str | None = None,
        autonomy: bool | None = None,
        repo_name: str | None = None,
        pr_number: int | None = None,
        total_duration_seconds: float | None = None,
    ) -> None:
        """Emit a chain-level lifecycle event."""
        entry = {
            "chain_id": chain_id,
            "event": event,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "repo_name": repo_name,
            "pr_number": pr_number,
        }
        if decision:
            entry["decision"] = decision
        if autonomy is not None:
            entry["autonomy"] = autonomy
        if total_duration_seconds is not None:
            entry["total_duration_seconds"] = round(total_duration_seconds, 2)

        json.dump(entry, sys.stdout, default=str)
        sys.stdout.write("\n")
        sys.stdout.flush()

        self._logger.info(json.dumps(entry, default=str))


# Module-level singleton
audit_logger = AgentAuditLogger()
