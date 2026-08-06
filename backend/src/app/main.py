from app.dependencies import get_orchestrator
from ai.providers.registry import get_registry

import os

from contextlib import asynccontextmanager

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware


load_dotenv()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize and tear down app-level singletons."""
    # Warm up the orchestrator (registers providers, boots memory manager)
    get_orchestrator()
    
    yield  # App is running
    
    # Shutdown: close all provider HTTP clients
    await get_registry().close_all()


app = FastAPI(
    title="Engineering Memory OS API",
    version="0.1.0",
    lifespan=lifespan,
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

# Register routers
app.include_router()


@app.get("/")
async def root():
    return {
        "message": "Engineering Memory OS API",
    }


@app.get("/api/health")
async def health():
    registry = get_registry()
    
    return {
        "server": True,
        "database": True,
        "redis": True,
        "ai": {
            "active_provider": registry.active_name,
            "available_providers": registry.available,
        }
    }