import os

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.auth import router as auth_router
from app.api.chat import router as chat_router
from app.api.events import router as events_router
from app.api.retrieval import router as retrieval_router
from app.api.slack import router as slack_router
from app.api.workspaces import router as workspaces_router

load_dotenv()

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


app.include_router(auth_router)
app.include_router(chat_router)
app.include_router(events_router)
app.include_router(retrieval_router)
app.include_router(slack_router)
app.include_router(workspaces_router)


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