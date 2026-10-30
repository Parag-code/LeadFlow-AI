
import os
from pathlib import Path

from dotenv import load_dotenv


# ==================================================
# 1. PROJECT CONFIGURATION
# ==================================================

BASE_DIR = Path(__file__).resolve().parent.parent

load_dotenv(BASE_DIR / ".env")


# ==================================================
# 2. SETTINGS
# ==================================================

class Settings:

    # Groq LLM
    GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
    GROQ_MODEL = os.getenv("GROQ_MODEL", "")

    # Gmail SMTP
    GMAIL_ADDRESS = os.getenv("GMAIL_ADDRESS", "")
    GMAIL_APP_PASSWORD = os.getenv("GMAIL_APP_PASSWORD", "")

    # Database
    DATABASE_PATH = os.getenv(
        "DATABASE_PATH",
        "data/leadflow.db"
    )

    @property
    def database_file(self):
        path = Path(self.DATABASE_PATH)

        if not path.is_absolute():
            path = BASE_DIR / path

        return path


settings = Settings()
