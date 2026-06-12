"""
PR Pilot - Main FastAPI application entrypoint.
Receives GitHub webhooks and triggers the 5-agent review chain.
"""

import json
from contextlib import asynccontextmanager
from pathlib import Path

import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse

from src.config import HOST, PORT, STATE_DIR
from src.github_app.webhook import router as webhook_router

logger = structlog.get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown hooks."""
    logger.info("pr_pilot_starting", host=HOST, port=PORT)
    yield
    logger.info("pr_pilot_shutting_down")


app = FastAPI(
    title="PR Pilot",
    description="AI-native code quality service — 5-agent autonomous PR review pipeline",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(webhook_router)


@app.get("/")
async def root() -> dict:
    """Health check and basic info."""
    return {
        "service": "PR Pilot",
        "version": "0.1.0",
        "status": "running",
        "agents": ["reviewer", "fixer", "tester", "verifier", "escalator"],
    }


@app.get("/health")
async def health() -> dict:
    """Health check endpoint for Cloud Run / load balancers."""
    return {"status": "healthy"}


# ── Dashboard ────────────────────────────────────────────────────────

DASHBOARD_HTML = Path(__file__).parent / "dashboard.html"


@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard():
    """Serve the agent audit dashboard."""
    if DASHBOARD_HTML.exists():
        return DASHBOARD_HTML.read_text()
    return HTMLResponse("<h1>Dashboard not found</h1>", status_code=404)


@app.get("/dashboard/reviews")
async def dashboard_reviews():
    """API: list all review sessions from the state directory."""
    reviews = []
    if STATE_DIR.exists():
        for state_file in sorted(STATE_DIR.glob("*.json"), reverse=True):
            try:
                review = json.loads(state_file.read_text())
                reviews.append(review)
            except Exception:
                pass
    return {"reviews": reviews}
