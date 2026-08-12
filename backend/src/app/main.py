import logging
import os

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.chat import router as chat_router
from app.api.events import router as events_router
from app.api.retrieval import router as retrieval_router
from slack.handler import start_slack

load_dotenv()

logger = logging.getLogger(__name__)

app = FastAPI(
    title="Engineering Memory OS API",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv(
        "CORS_ORIGINS",
        "http://localhost:5173,http://127.0.0.1:5173",
    ).split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


app.include_router(chat_router)
app.include_router(events_router)
app.include_router(retrieval_router)


@app.on_event("startup")
def startup_slack():
    """Launch the Slack SocketMode listener in a background thread.

    If SLACK_BOT_TOKEN / SLACK_APP_TOKEN are not set the call is a no-op
    (start_slack logs a warning and returns None).
    """
    start_slack()
    logger.info("[main] Slack background thread launched (or skipped — check env vars).")


@app.get("/")
async def root():
    return {
        "message": "Engineering Memory OS API",
    }


@app.get("/api/health")
async def health():
    return {
        "server": True,
        "database": True,
        "redis": True,
    }