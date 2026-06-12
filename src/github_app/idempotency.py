"""
Lightweight idempotency / delivery-dedup store for webhook processing.

GitHub redelivers webhooks (and PR `synchronize` events fire repeatedly), so
the same logical review can arrive multiple times. Processing each one runs the
full multi-agent chain and posts a duplicate review. This module records which
keys have already been accepted so the handler can skip duplicates.

The default backend is an in-process store with a bounded size. It is
single-instance only; a multi-instance deployment should back this with a
shared store (Redis, Firestore, Cloud Tasks dedup, etc.). The interface is
intentionally tiny so that swap is mechanical.
"""

from __future__ import annotations

import threading
from collections import OrderedDict


class InMemoryIdempotencyStore:
    """Bounded, thread-safe set of seen keys with FIFO eviction."""

    def __init__(self, max_size: int = 10_000) -> None:
        self._max_size = max_size
        self._seen: "OrderedDict[str, None]" = OrderedDict()
        self._lock = threading.Lock()

    def seen(self, key: str) -> bool:
        """Return True if the key was already recorded."""
        with self._lock:
            return key in self._seen

    def add(self, key: str) -> bool:
        """Record a key. Returns True if newly added, False if it existed.

        This is the atomic check-and-set callers should use to claim work:
        only the first caller for a given key gets True.
        """
        with self._lock:
            if key in self._seen:
                # refresh recency so active keys are not evicted mid-flight
                self._seen.move_to_end(key)
                return False
            self._seen[key] = None
            while len(self._seen) > self._max_size:
                self._seen.popitem(last=False)
            return True


def build_delivery_key(
    delivery_id: str,
    repo_full_name: str,
    pr_number: int | None,
    head_sha: str,
) -> str:
    """Build a stable dedup key for a webhook delivery.

    Prefer the GitHub delivery id when present (covers exact redeliveries).
    Always include (repo, pr, head_sha) so repeated `synchronize` events for the
    same commit are also collapsed even across distinct delivery ids.
    """
    base = f"{repo_full_name}#{pr_number}@{head_sha}"
    return f"{delivery_id}|{base}" if delivery_id else base


# Module-level default store used by the webhook handler.
default_store = InMemoryIdempotencyStore()
