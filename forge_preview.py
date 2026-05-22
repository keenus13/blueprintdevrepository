"""
forge_preview.py -- Queue Preview Tool
Part of: KD Empire / Forge AI Content System

Prints a summary of every package in the queue so you can
decide what to approve, reject, or publish.

Usage:
    python3 forge_preview.py              # Preview queue (default)
    python3 forge_preview.py --approved   # Preview approved folder instead
"""

import json
import sys
import argparse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from forge_core import AUTONOMOUS_QUEUE_DIR, AUTONOMOUS_APPROVED_DIR


def preview_folder(folder: Path):
    files = sorted(folder.glob("*.json"))

    if not files:
        print(f"No packages found in {folder}")
        return

    print(f"\n{'='*62}")
    print(f"  {len(files)} PACKAGE(S) IN: {folder.name.upper()}")
    print(f"{'='*62}")

    for i, filepath in enumerate(files, 1):
        try:
            with open(filepath) as f:
                d = json.load(f)

            titles = d.get("title_options", {})
            tiktok_title = titles.get("tiktok", "(no title)")
            hook = d.get("three_second_hook") or d.get("hook", "(no hook)")
            runtime = d.get("runtime_estimate", "?")
            words = d.get("word_count", "?")
            guardrail = d.get("guardrail_category", "?")
            topic = d.get("_meta", {}).get("topic_requested", "?")

            print(f"\n[{i}] {filepath.name}")
            print(f"    Topic:    {topic}")
            print(f"    Title:    {tiktok_title}")
            print(f"    Hook:     {hook}")
            print(f"    Runtime:  ~{runtime}  |  Words: {words}  |  {guardrail}")

        except Exception as e:
            print(f"\n[{i}] {filepath.name}")
            print(f"    ERROR reading file: {e}")

    print(f"\n{'='*62}")
    print("To approve: mv queue/FILENAME.json approved/")
    print("To reject:  mv queue/FILENAME.json rejected/")
    print(f"{'='*62}\n")


def main():
    parser = argparse.ArgumentParser(description="Forge Queue Preview Tool")
    parser.add_argument(
        "--approved",
        action="store_true",
        help="Preview the approved folder instead of the queue"
    )
    args = parser.parse_args()

    folder = AUTONOMOUS_APPROVED_DIR if args.approved else AUTONOMOUS_QUEUE_DIR
    preview_folder(folder)


if __name__ == "__main__":
    main()
