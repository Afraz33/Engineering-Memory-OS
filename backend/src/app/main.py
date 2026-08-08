import os
from contextlib import asynccontextmanager

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.dependencies import get_chat_service
from app.api.routes.chat import router as chat_router
from ai.providers.registry import get_registry

load_dotenv()


@asynccontextmanager
async def lifespan(app: FastAPI):
    service = get_chat_service()
    await service.start()
    yield
    await service.stop()
    await get_registry().close_all()


app = FastAPI(title="Engineering Memory OS API", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv("CORS_ORIGINS", "http://localhost:5173").split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(chat_router)


@app.get("/")
async def root():
    return {"message": "Engineering Memory OS API"}


@app.get("/api/health")
async def health():
    registry = get_registry()
    return {
        "status": "ok",
        "ai": {
            "active_provider": registry.active_name,
            "available_providers": registry.available,
        },
    }
