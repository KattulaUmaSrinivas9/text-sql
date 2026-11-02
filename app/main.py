import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.queue_worker import poll_chat_messages

logging.basicConfig(level=logging.INFO)


@asynccontextmanager
async def lifespan(app: FastAPI):
    worker_task = asyncio.create_task(poll_chat_messages(), name="chat-queue-poller")
    app.state.worker_task = worker_task
    try:
        yield
    finally:
        worker_task.cancel()
        try:
            await worker_task
        except asyncio.CancelledError:
            pass


app = FastAPI(title="Next.js Chat Queue Worker", lifespan=lifespan)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}
