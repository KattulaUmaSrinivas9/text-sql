import asyncio
import logging

from app.queue_worker import poll_chat_messages

logging.basicConfig(level=logging.INFO)


def main() -> None:
    """Run the continuous queue poller as a Vercel Daemon or local process."""
    asyncio.run(poll_chat_messages())


if __name__ == "__main__":
    main()
