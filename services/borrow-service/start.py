"""Start borrow-service with its local environment configuration."""

import os
from pathlib import Path

import uvicorn
from dotenv import load_dotenv


load_dotenv(Path(__file__).resolve().parent / ".env")


if __name__ == "__main__":
    uvicorn.run(
        "config.asgi:application",
        host=os.getenv("DJANGO_HOST", "127.0.0.1"),
        port=int(os.getenv("DJANGO_PORT", "8003")),
    )
