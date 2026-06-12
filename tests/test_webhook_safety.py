"""Tests for webhook hardening: signature, idempotency, and approve-gating."""

import importlib

from src.github_app.idempotency import (
    InMemoryIdempotencyStore,
    build_delivery_key,
)


class TestIdempotencyStore:
    def test_add_is_check_and_set(self):
        store = InMemoryIdempotencyStore()
        assert store.add("k1") is True   # first caller claims the work
        assert store.add("k1") is False  # duplicate is rejected
        assert store.seen("k1") is True
        assert store.seen("missing") is False

    def test_eviction_is_bounded(self):
        store = InMemoryIdempotencyStore(max_size=2)
        store.add("a")
        store.add("b")
        store.add("c")  # evicts "a"
        assert store.seen("a") is False
        assert store.seen("b") is True
        assert store.seen("c") is True

    def test_delivery_key_prefers_delivery_id_but_includes_commit(self):
        key = build_delivery_key("delivery-1", "org/repo", 7, "abc123")
        assert "delivery-1" in key
        assert "org/repo#7@abc123" in key

    def test_delivery_key_without_delivery_id_collapses_same_commit(self):
        k1 = build_delivery_key("", "org/repo", 7, "abc123")
        k2 = build_delivery_key("", "org/repo", 7, "abc123")
        assert k1 == k2


class TestSignatureFailsClosed:
    def test_missing_secret_rejects_by_default(self, monkeypatch):
        import src.github_app.webhook as webhook

        monkeypatch.setattr(webhook, "GITHUB_WEBHOOK_SECRET", "")
        monkeypatch.setattr(webhook, "ALLOW_UNSIGNED_WEBHOOKS", False)
        assert webhook.verify_signature(b"{}", "sha256=bad") is False

    def test_missing_secret_allows_with_explicit_bypass(self, monkeypatch):
        import src.github_app.webhook as webhook

        monkeypatch.setattr(webhook, "GITHUB_WEBHOOK_SECRET", "")
        monkeypatch.setattr(webhook, "ALLOW_UNSIGNED_WEBHOOKS", True)
        assert webhook.verify_signature(b"{}", "anything") is True

    def test_empty_signature_rejected_when_secret_set(self, monkeypatch):
        import src.github_app.webhook as webhook

        monkeypatch.setattr(webhook, "GITHUB_WEBHOOK_SECRET", "s3cret")
        assert webhook.verify_signature(b"{}", "") is False


class TestVerifiedAutoApproveFlag:
    def test_flag_defaults_off(self, monkeypatch):
        monkeypatch.delenv("VERIFIED_AUTO_APPROVE", raising=False)
        import src.config as config

        importlib.reload(config)
        assert config.VERIFIED_AUTO_APPROVE is False
