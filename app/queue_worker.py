import asyncio
import logging
import os

import httpx
from vercel.queue import ALL_DEPLOYMENTS, QueueClient, subscribe

from app.response_builder import build_demo_response

logger = logging.getLogger(__name__)


@subscribe(topic="chat-messages", consumer_group="chat-python-worker")
async def handle_chat_message(message: dict[str, object]) -> None:
    user_id = message.get("userId")
    message_id = message.get("messageId")
    text = message.get("text")

    if not all(isinstance(value, str) and value for value in (user_id, message_id, text)):
        raise ValueError("Queue message must include userId, messageId, and text.")

    logger.info("Received chat message %s for user %s", message_id, user_id)

    callback_secret = os.getenv("NEXT_CHAT_CALLBACK_SECRET", "")
    if not callback_secret:
        raise RuntimeError("NEXT_CHAT_CALLBACK_SECRET is not configured.")

    base_url = os.getenv("NEXT_API_BASE_URL", "http://localhost:3000").rstrip("/")
    result = {
        "userId": user_id,
        "messageId": message_id,
        "response": build_demo_response(text),
    }

    # A failed callback raises, leaving the queue message available for retry.
    async with httpx.AsyncClient(timeout=20) as client:
        response = await client.post(
            f"{base_url}/api/chat/results",
            json=result,
            headers={"Authorization": f"Bearer {callback_secret}"},
        )
        response.raise_for_status()

    logger.info("Processed chat message %s for user %s", message_id, user_id)


async def poll_chat_messages() -> None:
    """Poll Vercel Queues until the FastAPI app shuts down."""
    region = os.getenv("CHAT_QUEUE_REGION", "iad1")
    os.environ["VERCEL_REGION"] = region
    has_queue_auth = any(
        os.getenv(name)
        for name in ("VERCEL_QUEUE_TOKEN", "VERCEL_OIDC_TOKEN", "VERCEL_OIDC_TOKEN_FILE")
    )
    if not has_queue_auth:
        raise RuntimeError(
            "Provide VERCEL_QUEUE_TOKEN or make a Vercel OIDC token or token file available."
        )

    # Vercel sets VERCEL_DEPLOYMENT_ID automatically for each deployment. The
    # worker and Next.js producer are separate projects, so their IDs differ.
    # Poll all producer partitions unless an operator explicitly pins this
    # worker with the app-specific CHAT_QUEUE_DEPLOYMENT_ID setting.
    deployment = os.getenv("CHAT_QUEUE_DEPLOYMENT_ID") or ALL_DEPLOYMENTS
    deployment_label = deployment if isinstance(deployment, str) else "all deployments"
    logger.info("Starting chat queue polling in region %s (%s)", region, deployment_label)
    client = QueueClient(region=region, deployment=deployment)
    while True:
        try:
            await client.poll_and_handle(handle_chat_message, interval=1.0)
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("Chat queue polling failed; retrying in 5 seconds")
            await asyncio.sleep(5)

