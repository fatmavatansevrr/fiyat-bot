import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent

# Paths
DATA_DIR = BASE_DIR / "data"
SESSIONS_DIR = DATA_DIR / "sessions"
LOGS_DIR = BASE_DIR / "logs"
DB_PATH = DATA_DIR / "app.db"
INVENTORY_PATH = DATA_DIR / "inventory.xlsx"

# Ensure dirs exist
DATA_DIR.mkdir(exist_ok=True)
SESSIONS_DIR.mkdir(exist_ok=True)
LOGS_DIR.mkdir(exist_ok=True)

# Telegram
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

# Delivery context (Izmir)
DELIVERY_ADDRESS = os.getenv("DELIVERY_ADDRESS", "")
DELIVERY_CITY = os.getenv("DELIVERY_CITY", "İzmir")
DELIVERY_DISTRICT = os.getenv("DELIVERY_DISTRICT", "Konak")

# Agent behavior
DISCOUNT_THRESHOLD = float(os.getenv("DISCOUNT_THRESHOLD", "25"))
ALERT_COOLDOWN_HOURS = int(os.getenv("ALERT_COOLDOWN_HOURS", "24"))

# Which retailers to run (set to False to skip one)
ENABLED_RETAILERS = {
    "trendyol": True,
    "amazon": True,
    "migros": True,
    "carrefour": True,
    "gurmar": True,
}
