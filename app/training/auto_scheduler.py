"""
Auto-learn scheduler: runs in background, periodically scrapes YouTube,
extracts rules, and restarts the bot when new rules are found.

Usage: python -m app.training.auto_scheduler [--once]
"""
import argparse
import asyncio
import json
import logging
import os
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger("auto_scheduler")

# YouTube channels/news sources that likely have Khmer captions
DEFAULT_SOURCES = [
    # Add Khmer YouTube channels here
    # Format: {"url": "...", "name": "..."}
]

CONFIG_PATH = os.path.join(os.path.dirname(__file__), "data", "sources.json")

def load_sources() -> list[dict]:
    if os.path.exists(CONFIG_PATH):
        with open(CONFIG_PATH) as f:
            return json.load(f)
    return DEFAULT_SOURCES

def save_sources(sources: list[dict]) -> None:
    os.makedirs(os.path.dirname(CONFIG_PATH), exist_ok=True)
    with open(CONFIG_PATH, "w") as f:
        json.dump(sources, f, indent=2)

async def run_cycle():
    from app.training.auto_learn import auto_learn_from_pairs, scrape_youtube_channel, auto_train_model
    
    logger.info("=== Auto-learn cycle starting ===")
    
    # Step 1: Scrape YouTube sources
    sources = load_sources()
    total_learned = 0
    for source in sources:
        try:
            learned = await scrape_youtube_channel(source["url"], max_videos=2)
            total_learned += learned
            logger.info("  %s: learned %d", source.get("name", source["url"]), learned)
        except Exception as e:
            logger.error("  %s: failed - %s", source.get("name", source["url"]), e)
    
    # Step 2: Auto-extract rules from all accumulated pairs
    repl_count, comp_count = await auto_learn_from_pairs()
    if repl_count or comp_count:
        logger.info("Extracted %d replacements, %d compounds", repl_count, comp_count)
    
    # Step 3: Auto-train model if enough data
    # await auto_train_model()
    
    logger.info("=== Auto-learn cycle complete ===")

async def scheduler(interval_hours: int = 6):
    """Run auto-learn cycles periodically."""
    while True:
        try:
            await run_cycle()
        except Exception as e:
            logger.error("Cycle failed: %s", e)
        logger.info("Next cycle in %d hours", interval_hours)
        await asyncio.sleep(interval_hours * 3600)

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--once", action="store_true", help="Run one cycle then exit")
    parser.add_argument("--interval", type=int, default=6, help="Hours between cycles")
    args = parser.parse_args()
    
    if args.once:
        asyncio.run(run_cycle())
    else:
        asyncio.run(scheduler(args.interval))

if __name__ == "__main__":
    main()
