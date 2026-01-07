import os
from dotenv import load_dotenv

load_dotenv()

# Telegram
BOT_TOKEN = os.getenv("BOT_TOKEN")
WHITELIST_EMPLOYEES = [int(x) for x in os.getenv("WHITELIST_EMPLOYEES", "").split(",") if x]
ADMIN_IDS = [int(x) for x in os.getenv("ADMIN_IDS", "").split(",") if x]

# Database
DATABASE_URL = os.getenv("DATABASE_URL")

# OpenRouter
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
OPENROUTER_MODEL = os.getenv("OPENROUTER_MODEL", "anthropic/claude-3.5-sonnet")
OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"

# Google Sheets
GOOGLE_SHEETS_ID = os.getenv("GOOGLE_SHEETS_ID")
GOOGLE_CREDENTIALS_PATH = os.getenv("GOOGLE_CREDENTIALS_PATH", "credentials.json")

# Limits
DAILY_COST_LIMIT = float(os.getenv("DAILY_COST_LIMIT", "50"))
MAX_SESSION_DURATION_MINUTES = int(os.getenv("MAX_SESSION_DURATION_MINUTES", "30"))
RATE_LIMIT_SECONDS = int(os.getenv("RATE_LIMIT_SECONDS", "2"))
MAX_MESSAGE_LENGTH = int(os.getenv("MAX_MESSAGE_LENGTH", "500"))

# Validate
if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN не задан в .env")
if not DATABASE_URL:
    raise ValueError("DATABASE_URL не задан в .env")
if not OPENROUTER_API_KEY:
    raise ValueError("OPENROUTER_API_KEY не задан в .env")