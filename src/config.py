"""
PR Pilot configuration — loaded from environment variables.
All agent and orchestration settings live here.
"""

import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

# ── GitHub App ──────────────────────────────────────────────────────
GITHUB_APP_ID: str = os.getenv("GITHUB_APP_ID", "")
GITHUB_APP_PRIVATE_KEY: str = os.getenv("GITHUB_APP_PRIVATE_KEY", "")
GITHUB_WEBHOOK_SECRET: str = os.getenv("GITHUB_WEBHOOK_SECRET", "")

# Support private key as path or inline value
if GITHUB_APP_PRIVATE_KEY and os.path.isfile(GITHUB_APP_PRIVATE_KEY):
    GITHUB_APP_PRIVATE_KEY = Path(GITHUB_APP_PRIVATE_KEY).read_text()

# ── LLM Configuration ───────────────────────────────────────────────
GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "")
GEMINI_MODEL: str = os.getenv("GEMINI_MODEL", "gemini-2.5-pro")

# ── Server ──────────────────────────────────────────────────────────
HOST: str = os.getenv("HOST", "0.0.0.0")
PORT: int = int(os.getenv("PORT", "8080"))

# ── Agent Settings ──────────────────────────────────────────────────
MAX_AGENT_RETRIES: int = int(os.getenv("MAX_AGENT_RETRIES", "3"))
AGENT_TIMEOUT_SECONDS: int = int(os.getenv("AGENT_TIMEOUT_SECONDS", "300"))
MAX_DIFF_SIZE_BYTES: int = int(os.getenv("MAX_DIFF_SIZE_BYTES", "500_000"))

# ── Paths ───────────────────────────────────────────────────────────
PROJECT_ROOT: Path = Path(__file__).parent.parent
AGENT_LOG_DIR: Path = Path(os.getenv("AGENT_LOG_DIR", str(PROJECT_ROOT / "logs" / "agents")))
STATE_DIR: Path = Path(os.getenv("STATE_DIR", str(PROJECT_ROOT / "data" / "reviews")))

# ── Review Rules ────────────────────────────────────────────────────
DEFAULT_REVIEW_RULES = {
    "security": True,
    "performance": True,
    "style": True,
    "testing": True,
    "error_handling": True,
}
