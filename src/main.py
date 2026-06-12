"""
PR Pilot — Main FastAPI application entrypoint.
Receives GitHub webhooks and triggers the 5-agent review chain.
"""

from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.config import HOST, PORT
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
