"""
Saves and loads Playwright browser storage state (cookies + localStorage) per retailer.
Each retailer gets its own JSON file in data/sessions/.
"""
import json
from pathlib import Path
from datetime import datetime, timedelta

from config.settings import SESSIONS_DIR
from src.utils.logger import logger


class SessionManager:
    def __init__(self, retailer: str):
        self.retailer = retailer
        self.path: Path = SESSIONS_DIR / f"{retailer}.json"

    def exists(self) -> bool:
        return self.path.exists() and self.path.stat().st_size > 100

    def is_fresh(self, max_age_hours: int = 20) -> bool:
        """True if session file was saved within max_age_hours."""
        if not self.exists():
            return False
        mtime = datetime.fromtimestamp(self.path.stat().st_mtime)
        return datetime.now() - mtime < timedelta(hours=max_age_hours)

    def save(self, storage_state: dict):
        self.path.write_text(json.dumps(storage_state, ensure_ascii=False), encoding="utf-8")
        logger.info(f"[{self.retailer}] Session saved → {self.path.name}")

    def load(self) -> dict | None:
        if not self.exists():
            return None
        try:
            return json.loads(self.path.read_text(encoding="utf-8"))
        except Exception as e:
            logger.warning(f"[{self.retailer}] Could not read session: {e}")
            return None

    def delete(self):
        if self.path.exists():
            self.path.unlink()
            logger.debug(f"[{self.retailer}] Session file deleted")
