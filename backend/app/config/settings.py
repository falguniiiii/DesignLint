"""
Centralized configuration.

Keeping all environment-driven config in one place (rather than scattered
os.getenv() calls across files) is what makes it easy to add the Gemini
API key in Phase 2 without hunting through the codebase.
"""
import os
from dotenv import load_dotenv

load_dotenv()


class Settings:
    # Required for /api/analyze. Never commit a real key (see .env.example).
    GEMINI_API_KEY: str | None = os.getenv("GEMINI_API_KEY")

    # Comma-separated list in .env, parsed into a list here.
    # Whitespace and empty entries are ignored ("a, b," works as expected).
    CORS_ORIGINS: list[str] = [
        origin.strip()
        for origin in os.getenv("CORS_ORIGINS", "http://localhost:5173").split(",")
        if origin.strip()
    ]

    MAX_UPLOAD_SIZE_MB: int = int(os.getenv("MAX_UPLOAD_SIZE_MB", "10"))


settings = Settings()
