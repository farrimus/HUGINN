#!/usr/bin/env python3
"""
Backfill SystemKnowledgeStore from existing log_intel data.

Reads all data/{env}/log_intel/{wallet}.json files and imports
systems/ores/hostiles into the system knowledge graph.

Idempotent — safe to run multiple times.
"""
import os
import sys
import json
import logging

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
log = logging.getLogger(__name__)

# Allow running from project root
_project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _project_root)

from dotenv import load_dotenv
load_dotenv(os.path.join(_project_root, ".env"))


def main():
    from src.config import get_data_path
    from src import system_knowledge

    log_intel_dir = os.path.dirname(get_data_path("log_intel/_known_types.json", env_specific=True))
    if not os.path.isdir(log_intel_dir):
        log.info("No log_intel directory found at %s — nothing to backfill.", log_intel_dir)
        return

    wallets_processed = 0
    files_skipped = 0

    for filename in sorted(os.listdir(log_intel_dir)):
        if filename.startswith("_") or not filename.endswith(".json"):
            files_skipped += 1
            continue

        wallet = filename[:-5]  # strip .json
        path = os.path.join(log_intel_dir, filename)

        try:
            with open(path) as f:
                data = json.load(f)
        except Exception as e:
            log.warning("Skipping %s — failed to load: %s", filename, e)
            files_skipped += 1
            continue

        systems = data.get("systems", {})
        if not systems:
            wallets_processed += 1
            continue

        system_knowledge.record_from_upload(systems, reported_by=wallet)
        log.info("Imported %d systems from %s", len(systems), filename)
        wallets_processed += 1

    stats = system_knowledge.get_stats()
    log.info(
        "Backfill complete: %d wallets processed, %d files skipped. "
        "Result: %d systems, %d sightings.",
        wallets_processed,
        files_skipped,
        stats["systems_mapped"],
        stats["total_sightings"],
    )


if __name__ == "__main__":
    main()
