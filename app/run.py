"""
Combined launcher: runs the bot with auto-learn scheduler in background.

Usage:
  python -m app.run          # Run bot + background auto-learn
  python -m app.run --bot-only   # Run bot only (original behavior)
  python -m app.run --learn-only # Run auto-learn only
"""
import argparse
import asyncio
import logging
import os
import sys
import threading

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger("launcher")

# Configurable YouTube sources for auto-learning
DEFAULT_SOURCES = [
    # Add Khmer news YouTube channels here:
    # {"url": "https://youtube.com/@channel", "name": "Channel Name"},
]

SOURCES_PATH = os.path.join(os.path.dirname(__file__), "training", "data", "sources.json")


def ensure_sources():
    os.makedirs(os.path.dirname(SOURCES_PATH), exist_ok=True)
    if not os.path.exists(SOURCES_PATH):
        import json
        with open(SOURCES_PATH, "w") as f:
            json.dump(DEFAULT_SOURCES, f, indent=2)


def run_bot():
    from app.main import main
    main()


def run_scheduler():
    async def _run():
        from app.training.auto_scheduler import scheduler
        await scheduler(interval_hours=6)

    asyncio.run(_run())


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--bot-only", action="store_true", help="Run bot only")
    parser.add_argument("--learn-only", action="store_true", help="Run auto-learn only")
    args = parser.parse_args()

    ensure_sources()

    if args.learn_only:
        logger.info("Starting auto-learn scheduler only")
        run_scheduler()
    elif args.bot_only:
        logger.info("Starting bot only")
        run_bot()
    else:
        logger.info("Starting bot with background auto-learn")
        t = threading.Thread(target=run_scheduler, daemon=True)
        t.start()
        run_bot()


if __name__ == "__main__":
    main()
