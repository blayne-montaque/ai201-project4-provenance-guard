"""Central configuration. Never log this mapping: it contains credentials."""
import os
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
SCOUT_MODEL = "meta-llama/llama-4-scout-17b-16e-instruct"
ALTERNATE_MODEL = "openai/gpt-oss-20b"


def settings():
    load_dotenv(ROOT / ".env", override=False)
    return {
        "GROQ_API_KEY": os.getenv("GROQ_API_KEY", ""),
        "GROQ_MODEL": os.getenv("GROQ_MODEL", SCOUT_MODEL),
        "ALLOW_ALTERNATE_MODEL": os.getenv("ALLOW_ALTERNATE_MODEL", "false").lower() == "true",
        "GROQ_TIMEOUT_SECONDS": float(os.getenv("GROQ_TIMEOUT_SECONDS", "20")),
        "DATABASE": os.getenv("DATABASE", str(ROOT / "instance" / "provenance_guard.sqlite3")),
        "MAX_CONTENT_LENGTH": 128 * 1024,
        "MAX_TEXT_LENGTH": 20_000,
        "SUBMISSION_LIMITS": os.getenv("SUBMISSION_LIMITS", "10 per minute;100 per day"),
        "RATELIMIT_STORAGE_URI": os.getenv("RATELIMIT_STORAGE_URI", "memory://"),
        "RATELIMIT_ENABLED": True,
        "RATELIMIT_HEADERS_ENABLED": True,
    }

