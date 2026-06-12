"""Tests for the shared review_poster module (issue #29)."""



import src.review_poster as rp


class TestDecisionMapping:
    """decision_to_github_event returns the raw GitHub event (no safety gate)."""

    def test_auto_approve_maps_to_approve(self):
        assert rp.decision_to_github_event("auto_approve") == "APPROVE"

    def test_request_changes_maps_to_request_changes(self):
        assert rp.decision_to_github_event("request_changes") == "REQUEST_CHANGES"

    def test_escalate_to_human_maps_to_comment(self):
        assert rp.decision_to_github_event("escalate_to_human") == "COMMENT"

    def test_unknown_maps_to_comment(self):
        assert rp.decision_to_github_event("bogus") == "COMMENT"


class TestSafetyGate:
    """apply_safety_gate downgrades APPROVE when VERIFIED_AUTO_APPROVE is off."""

    def test_approve_downgraded_when_flag_off(self, monkeypatch):
        monkeypatch.setattr(rp, "VERIFIED_AUTO_APPROVE", False)
        assert rp.apply_safety_gate("APPROVE") == "COMMENT"

    def test_approve_passes_through_when_flag_on(self, monkeypatch):
        monkeypatch.setattr(rp, "VERIFIED_AUTO_APPROVE", True)
        assert rp.apply_safety_gate("APPROVE") == "APPROVE"

    def test_request_changes_never_downgraded(self, monkeypatch):
        monkeypatch.setattr(rp, "VERIFIED_AUTO_APPROVE", False)
        assert rp.apply_safety_gate("REQUEST_CHANGES") == "REQUEST_CHANGES"

    def test_comment_never_downgraded(self, monkeypatch):
        monkeypatch.setattr(rp, "VERIFIED_AUTO_APPROVE", False)
        assert rp.apply_safety_gate("COMMENT") == "COMMENT"


class TestSafetyNoteInBody:
    """build_review_body_with_safety_note prepends the note only on downgrade."""

    def _sample_results(self, decision="auto_approve"):
        return {
            "reviewer": {"summary": "Found 1 issue.", "findings": [{"severity": "low", "category": "style", "file": "a.py", "line": 1, "description": "bad", "suggestion": "fix it"}]},
            "fixer": {"summary": "Fixed 1 issue.", "duration_seconds": 1.0},
            "tester": {"summary": "Wrote 2 tests.", "duration_seconds": 2.0},
            "verifier": {"summary": "All good.", "duration_seconds": 3.0},
            "escalator": {"duration_seconds": 4.0},
            "decision": decision,
        }

    def test_safety_note_added_when_downgraded(self, monkeypatch):
        monkeypatch.setattr(rp, "VERIFIED_AUTO_APPROVE", False)
        body = rp.build_review_body_with_safety_note(
            self._sample_results(), original_event="APPROVE"
        )
        assert "disabled until changes are verified in a sandbox" in body
        assert "## 🤖 PR Pilot Review" in body

    def test_safety_note_not_added_when_flag_on(self, monkeypatch):
        monkeypatch.setattr(rp, "VERIFIED_AUTO_APPROVE", True)
        body = rp.build_review_body_with_safety_note(
            self._sample_results(), original_event="APPROVE"
        )
        assert "disabled until changes are verified" not in body

    def test_safety_note_not_added_for_request_changes(self, monkeypatch):
        monkeypatch.setattr(rp, "VERIFIED_AUTO_APPROVE", False)
        body = rp.build_review_body_with_safety_note(
            self._sample_results("request_changes"), original_event="REQUEST_CHANGES"
        )
        assert "disabled until changes are verified" not in body


class TestBuildReviewBody:
    def test_includes_reviewer_finding(self):
        results = {
            "reviewer": {"summary": "SQL injection.", "findings": [{"severity": "critical", "category": "security", "file": "db.py", "line": 42, "description": "SQLi", "suggestion": "Use params"}]},
            "fixer": {"summary": "Patched."},
            "tester": {"summary": "Tests written."},
            "verifier": {"summary": "Verified."},
            "escalator": {},
            "decision": "request_changes",
        }
        body = rp.build_review_body(results)
        assert "[CRITICAL]" in body
        assert "security" in body
        assert "db.py:42" in body

    def test_no_findings_shown_when_empty(self):
        results = {
            "reviewer": {"summary": "Clean."},
            "fixer": {"summary": "N/A."},
            "tester": {"summary": "N/A."},
            "verifier": {"summary": "N/A."},
            "escalator": {},
            "decision": "auto_approve",
        }
        body = rp.build_review_body(results)
        assert "Issues Found" not in body

    def test_shows_correct_decision_header(self):
        for decision, keyword in [("auto_approve", "AUTO APPROVE"), ("request_changes", "REQUEST CHANGES"), ("escalate_to_human", "ESCALATE TO HUMAN")]:
            results = {
                "reviewer": {"summary": "."},
                "fixer": {"summary": "."},
                "tester": {"summary": "."},
                "verifier": {"summary": "."},
                "escalator": {},
                "decision": decision,
            }
            body = rp.build_review_body(results)
            assert keyword in body, f"Expected '{keyword}' in body for decision '{decision}'"
