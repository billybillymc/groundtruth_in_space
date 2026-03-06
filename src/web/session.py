"""Per-connection terminal session managing state and I/O over WebSocket."""

import asyncio
import json
import random
import time
from typing import Optional

from fastapi import WebSocket

from src.synthesis.chain import query_stream
from src.feedback.store import save_feedback
from src.models import QueryResult

SUGGESTED_QUESTIONS = [
    "How does Adamant's command router dispatch commands to components?",
    "How does cFE Executive Services manage application lifecycle?",
    "How does CubeDOS handle message passing between modules?",
    "How do these frameworks handle telemetry packaging and downlink?",
    "What is the OSAL abstraction layer in cFS and what does it provide?",
    "How does Adamant's fault correction component handle faults?",
    "Compare how Adamant and CubeDOS structure their task/component models.",
]

LAUNCH_PHRASES = [
    "Ignition sequence started",
    "T-minus 10... all systems nominal",
    "Main engine throttle up",
    "Solid rocket boosters engaged",
    "Clearing the tower",
    "Go for throttle up",
    "Staging confirmed, second stage ignition",
    "Telemetry acquisition locked",
    "Vehicle is supersonic",
    "Max Q, standing by",
    "Fairing separation confirmed",
    "Orbital insertion burn in progress",
    "Flight dynamics reports nominal trajectory",
    "MECO. Main engine cutoff confirmed",
    "Payload deploy sequence initiated",
    "Downrange tracking station acquired",
    "Roll program complete",
]

HELP_COMMANDS = [
    {"cmd": "/help", "desc": "Show this help message"},
    {"cmd": "/criticize", "desc": "Submit feedback on the last answer"},
    {"cmd": "/quit", "desc": "Exit GroundTruth"},
]


class TerminalSession:
    """Async state machine for a single WebSocket connection.

    Sends structured JSON messages that the frontend renders as HTML.
    """

    def __init__(self, ws: WebSocket):
        self.ws = ws
        self.last_query: Optional[str] = None
        self.last_answer: Optional[str] = None

    # ── Helpers ────────────────────────────────────────────

    async def send(self, msg_type: str, data=None, **extra):
        msg = {"type": msg_type}
        if data is not None:
            msg["data"] = data
        msg.update(extra)
        await self.ws.send_json(msg)

    async def receive_input(self) -> str:
        raw = await self.ws.receive_text()
        msg = json.loads(raw)
        return msg.get("text", "")

    # ── Main loop ─────────────────────────────────────────

    async def run(self):
        """Entry point -- called once per connection."""
        await self.send("header")
        await self.send("status", "Ready for queries.")
        await self.send("suggestions", SUGGESTED_QUESTIONS)
        await self.send("hint", "Type a number, a question, or /help")
        await self.send("prompt")

        while True:
            text = await self.receive_input()
            text = text.strip()
            if not text:
                await self.send("prompt")
                continue
            await self._handle_input(text)

    # ── Command dispatch ──────────────────────────────────

    async def _handle_input(self, text: str):
        if text == "/quit":
            await self.send("info", "Mission complete. Goodbye!")
            await self.ws.close()
            return
        elif text == "/help":
            await self.send("help", HELP_COMMANDS)
            await self.send("prompt")
        elif text == "/criticize":
            await self._handle_criticize()
        else:
            # Number shortcut
            question = None
            if text.isdigit():
                idx = int(text)
                if 1 <= idx <= len(SUGGESTED_QUESTIONS):
                    question = SUGGESTED_QUESTIONS[idx - 1]
                else:
                    await self.send(
                        "info",
                        f"Pick a number between 1 and {len(SUGGESTED_QUESTIONS)}, or type a question.",
                    )
                    await self.send("prompt")
                    return

            await self._handle_query(question or text)

    # ── Feedback ──────────────────────────────────────────

    async def _handle_criticize(self):
        if self.last_query is None:
            await self.send("info", "No previous query to provide feedback on.")
            await self.send("prompt")
            return

        await self.send("feedback_prompt")
        feedback_text = (await self.receive_input()).strip()

        if feedback_text:
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(
                None, save_feedback, self.last_query, self.last_answer, feedback_text
            )
            await self.send("feedback_ack", "Feedback saved. Thank you!")
        else:
            await self.send("feedback_ack", "Empty feedback, not saved.")
        await self.send("prompt")

    # ── Query with streaming ──────────────────────────────

    async def _handle_query(self, question: str):
        loop = asyncio.get_event_loop()

        # Show loading spinner
        phrase = random.choice(LAUNCH_PHRASES)
        await self.send("loading", True, phrase=phrase)

        # Bridge sync generator to async via queue
        queue: asyncio.Queue = asyncio.Queue()

        def _run_stream():
            for chunk in query_stream(question):
                loop.call_soon_threadsafe(queue.put_nowait, chunk)
            loop.call_soon_threadsafe(queue.put_nowait, None)

        executor_future = loop.run_in_executor(None, _run_stream)

        first_token = True
        result = None

        while True:
            chunk = await queue.get()
            if chunk is None:
                break
            if isinstance(chunk, QueryResult):
                result = chunk
            else:
                if first_token:
                    await self.send("loading", False)
                    await self.send("query", question)
                    await self.send("stream_start")
                    first_token = False
                await self.send("token", chunk)

        if first_token:
            # No tokens received at all
            await self.send("loading", False)

        # Send sources + latency as structured data
        if result:
            self.last_query = question
            self.last_answer = result.answer
            sources = []
            for src in result.sources:
                c = src.chunk
                sources.append({
                    "path": c.file_path,
                    "start_line": c.start_line,
                    "end_line": c.end_line,
                    "chunk_type": c.chunk_type,
                    "codebase": c.codebase,
                    "score": round(src.score, 3),
                })
            await self.send("stream_end", {
                "sources": sources,
                "latency_ms": round(result.latency_ms, 0),
            })

        await self.send("prompt")
        await executor_future
