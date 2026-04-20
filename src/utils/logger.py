from loguru import logger
from pathlib import Path
import sys

LOGS_DIR = Path(__file__).resolve().parent.parent.parent / "logs"
LOGS_DIR.mkdir(exist_ok=True)

# Remove default handler
logger.remove()

# Console — info level
logger.add(sys.stdout, level="INFO", format="<green>{time:HH:mm:ss}</green> | <level>{level:<8}</level> | {message}")

# File — debug level, rotating daily
logger.add(
    LOGS_DIR / "run_{time:YYYY-MM-DD}.log",
    level="DEBUG",
    rotation="1 day",
    retention="14 days",
    encoding="utf-8",
)

__all__ = ["logger"]
