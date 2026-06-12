"""Sample fixture used by review demos.

This module intentionally contrasts an insecure SQL pattern with a safe,
parameterized one. It is a fixture, not an executable test, so the demo
database handle is a stub to keep it import- and lint-clean.
"""


class _StubDB:
    """Minimal stand-in so the demo functions are well-defined."""

    def execute(self, query, params=None):  # pragma: no cover - demo stub
        return (query, params)


db = _StubDB()


def get_user_bad(user_id):
    """Deliberately insecure — should be caught."""
    query = "SELECT * FROM users WHERE id = " + user_id
    return db.execute(query)


def get_user_good(user_id):
    """Parameterized — correct."""
    query = "SELECT * FROM users WHERE id = ?"
    return db.execute(query, (user_id,))
