"""
Entry point — run manually or via Windows Task Scheduler.
Usage:
    python main.py              # full daily run
    python main.py --dry-run    # load products only, no browser
"""
import asyncio
import argparse
import sys

from src.utils.logger import logger
from src.core.orchestrator import Orchestrator


def parse_args():
    parser = argparse.ArgumentParser(description="Price Monitor Agent")
    parser.add_argument("--dry-run", action="store_true", help="Load products only, skip browser")
    parser.add_argument("--retailer", type=str, help="Run only this retailer (e.g. trendyol)")
    return parser.parse_args()


async def main():
    args = parse_args()

    if args.dry_run:
        logger.info("DRY RUN mode — browser steps skipped")

    orchestrator = Orchestrator()

    if args.retailer:
        from config import settings
        # Disable all except the requested one
        for key in settings.ENABLED_RETAILERS:
            settings.ENABLED_RETAILERS[key] = (key == args.retailer)
        logger.info(f"Running single retailer: {args.retailer}")

    await orchestrator.run()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Interrupted by user.")
        sys.exit(0)
