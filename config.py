"""
Configuration loader.
Edit config.json to change settings — no Python knowledge required.
"""
import json
import os
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).parent
load_dotenv(BASE_DIR / ".env")

# These are populated by load_config()
BOT_TOKEN: str = ""
OWNER_TG_ID: int = 0
COACH_TG_IDS: list = []
SPREADSHEET_ID: str = ""
CREDENTIALS_PATH: str = ""
INSTAGRAM_URL: str = "https://www.instagram.com/be_the_best_fitness_studio/"
SCHEDULE_FILE: str = ""
RULES_FILE: str = ""
TIMEZONE: str = "Europe/Kiev"


def load_config() -> dict:
    global BOT_TOKEN, OWNER_TG_ID, COACH_TG_IDS, SPREADSHEET_ID
    global CREDENTIALS_PATH, INSTAGRAM_URL, SCHEDULE_FILE, RULES_FILE, TIMEZONE

    BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()
    if not BOT_TOKEN:
        raise ValueError(
            "BOT_TOKEN is not set. Open the .env file and paste your Telegram bot token."
        )

    config_path = BASE_DIR / "config.json"
    if not config_path.exists():
        raise FileNotFoundError(f"config.json not found at {config_path}")

    with open(config_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    OWNER_TG_ID = int(data.get("owner_telegram_id", 0))
    COACH_TG_IDS = [int(x) for x in data.get("coach_telegram_ids", [])]
    SPREADSHEET_ID = data.get("google_spreadsheet_id", "").strip()
    CREDENTIALS_PATH = str(BASE_DIR / data.get("credentials_file", "credentials.json"))
    INSTAGRAM_URL = data.get("instagram_url", INSTAGRAM_URL)
    TIMEZONE = data.get("timezone", "Europe/Kiev")

    schedule_file = data.get("schedule_file", "files/schedule.pdf")
    SCHEDULE_FILE = str(BASE_DIR / schedule_file)

    rules_file = data.get("rules_file", "files/rules.pdf")
    RULES_FILE = str(BASE_DIR / rules_file)

    if not SPREADSHEET_ID or SPREADSHEET_ID == "your-google-spreadsheet-id-here":
        raise ValueError(
            "google_spreadsheet_id is not set in config.json. "
            "Open config.json and paste your Google Sheet ID."
        )

    return data


def is_coach(user_id: int) -> bool:
    return user_id in COACH_TG_IDS
