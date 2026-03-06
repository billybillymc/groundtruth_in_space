"""FastAPI WebSocket server for LegacyLens web terminal."""

import asyncio
import logging
from contextlib import asynccontextmanager

from pathlib import Path

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from src.synthesis.chain import (
    _get_embeddings,
    _get_pinecone_indexes,
    _get_llm,
    _get_prompt,
    _get_cohere_client,
)
from src.feedback.store import init_feedback_db
from src.web.session import TerminalSession

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Pre-warm all singletons at server start (not per-connection)."""
    init_feedback_db()
    loop = asyncio.get_event_loop()
    await loop.run_in_executor(None, _get_embeddings)
    await loop.run_in_executor(None, _get_pinecone_indexes)
    await loop.run_in_executor(None, _get_llm)
    await loop.run_in_executor(None, _get_prompt)
    await loop.run_in_executor(None, _get_cohere_client)
    logger.info("All singletons pre-warmed")
    yield


app = FastAPI(title="GroundTruth", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Tighten to your Netlify domain in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


_frontend_dir = Path(__file__).resolve().parent.parent.parent / "frontend"


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    session = TerminalSession(websocket)
    try:
        await session.run()
    except WebSocketDisconnect:
        logger.info("Client disconnected")
    except Exception:
        logger.exception("Session error")


if _frontend_dir.is_dir():
    app.mount("/", StaticFiles(directory=_frontend_dir, html=True), name="frontend")
