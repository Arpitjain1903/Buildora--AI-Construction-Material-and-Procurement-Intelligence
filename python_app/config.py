"""
Configuration and Environment Settings for Construction Material & Procurement Intelligence Platform.
Loads environment variables from .env if present.
"""

import os
from pathlib import Path
from dataclasses import dataclass
from typing import Optional
from dotenv import load_dotenv

# Load .env from root directory if it exists
ROOT_DIR = Path(__file__).resolve().parent.parent
env_path = ROOT_DIR / ".env"
if env_path.exists():
    load_dotenv(dotenv_path=env_path)
else:
    load_dotenv()

@dataclass
class Settings:
    # LLM Settings (OpenAI-compatible)
    LLM_PROVIDER: str = os.getenv("LLM_PROVIDER", "groq")
    LLM_BASE_URL: str = os.getenv("LLM_BASE_URL", "https://api.groq.com/openai/v1")
    LLM_API_KEY: Optional[str] = os.getenv("LLM_API_KEY", None)
    LLM_MODEL_TEXT: Optional[str] = os.getenv("LLM_MODEL_TEXT", "openai/gpt-oss-20b")
    LLM_MODEL_VISION: Optional[str] = os.getenv("LLM_MODEL_VISION", "llama-3.2-11b-vision-preview")
    LLM_TIMEOUT_SECONDS: int = int(os.getenv("LLM_TIMEOUT_SECONDS", "30"))
    LLM_MAX_RETRIES: int = int(os.getenv("LLM_MAX_RETRIES", "2"))
    LLM_DAILY_TOKEN_BUDGET: int = int(os.getenv("LLM_DAILY_TOKEN_BUDGET", "100000"))

    # Weather
    WEATHER_PROVIDER: str = os.getenv("WEATHER_PROVIDER", "openweathermap")
    WEATHER_API_KEY: Optional[str] = os.getenv("WEATHER_API_KEY", None)
    WEATHER_BASE_URL: Optional[str] = os.getenv("WEATHER_BASE_URL", "https://api.openweathermap.org/data/2.5")

    # Embeddings for material name matching
    EMBEDDING_API_ENDPOINT: Optional[str] = os.getenv("EMBEDDING_API_ENDPOINT", None)
    EMBEDDING_API_KEY: Optional[str] = os.getenv("EMBEDDING_API_KEY", None)

    # Database connection string
    DATABASE_URL: str = os.getenv("DATABASE_URL", "")

    # Backwards compatibility attributes
    @property
    def VISION_LLM_API_KEY(self) -> Optional[str]:
        return self.LLM_API_KEY

    @property
    def TEXT_LLM_API_KEY(self) -> Optional[str]:
        return self.LLM_API_KEY

    @property
    def VISION_LLM_ENDPOINT(self) -> str:
        return f"{self.LLM_BASE_URL.rstrip('/')}/chat/completions"

    @property
    def TEXT_LLM_ENDPOINT(self) -> str:
        return f"{self.LLM_BASE_URL.rstrip('/')}/chat/completions"

    @property
    def VISION_LLM_MODEL(self) -> str:
        return self.LLM_MODEL_VISION or ""

    @property
    def TEXT_LLM_MODEL(self) -> str:
        return self.LLM_MODEL_TEXT or ""

    @property
    def WEATHER_API_ENDPOINT(self) -> Optional[str]:
        return self.WEATHER_BASE_URL

settings = Settings()
