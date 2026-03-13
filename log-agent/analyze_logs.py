"""
analyze_logs.py — EVE Frontier log catalog tool

Run this on your local machine against your Gamelogs directory.
It strips color/font tags, groups entries by type, and prints
a sample of distinct cleaned messages for each type.

Usage:
    python analyze_logs.py "C:\\path\\to\\Gamelogs"
    python analyze_logs.py "C:\\path\\to\\Gamelogs" --limit 20
"""

import re
import sys
import os
from collections import defaultdict

# Strip <color=...>, </color>, <font ...>, </font>, <b>, </b>, <br>, etc.
TAG_RE = re.compile(r'<[^>]+>')

# Main log line format
LINE_RE = re.compile(r'^\[\s*[\d.]+\s+[\d:]+\s*\]\s*\((\w+)\)\s*(.*)', re.DOTALL)


def strip_tags(text: str) -> str:
    return TAG_RE.sub('', text).strip()


def load_lines(log_dir: str):
    """Yield (type, cleaned_message) from all log files in log_dir."""
    if not os.path.isdir(log_dir):
        print(f"Directory not found: {log_dir}")
        sys.exit(1)

    files = [
        os.path.join(log_dir, f)
        for f in os.listdir(log_dir)
        if os.path.isfile(os.path.join(log_dir, f))
    ]
    if not files:
        print(f"No files found in {log_dir}")
        sys.exit(1)

    print(f"Reading {len(files)} file(s) from {log_dir}\n")

    for path in files:
        try:
            with open(path, "r", encoding="utf-8", errors="ignore") as f:
                for line in f:
                    line = line.strip()
                    m = LINE_RE.match(line)
                    if m:
                        msg_type = m.group(1)
                        msg_text = strip_tags(m.group(2))
                        yield msg_type, msg_text
        except Exception as e:
            print(f"  [warn] Could not read {path}: {e}")


def normalize(text: str) -> str:
    """Collapse numbers and proper nouns to surface structural patterns."""
    # Replace numbers (including decimals)
    t = re.sub(r'\b\d+(\.\d+)?\b', 'N', text)
    return t


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    log_dir = sys.argv[1]
    limit = 20
    for i, arg in enumerate(sys.argv):
        if arg == "--limit" and i + 1 < len(sys.argv):
            limit = int(sys.argv[i + 1])

    # Collect: per type -> {normalized_msg: first_real_example}
    by_type: dict[str, dict[str, str]] = defaultdict(dict)
    total = 0

    for msg_type, msg_text in load_lines(log_dir):
        total += 1
        norm = normalize(msg_text)
        bucket = by_type[msg_type]
        if norm not in bucket:
            bucket[norm] = msg_text  # store first real example

    print(f"Total log lines parsed: {total}")
    print(f"Entry types found: {sorted(by_type.keys())}\n")
    print("=" * 70)

    for msg_type in sorted(by_type.keys()):
        examples = list(by_type[msg_type].values())
        print(f"\n({msg_type})  —  {len(examples)} distinct pattern(s)")
        print("-" * 50)
        for ex in examples[:limit]:
            print(f"  {ex}")
        if len(examples) > limit:
            print(f"  ... and {len(examples) - limit} more (increase --limit to see all)")

    print("\n" + "=" * 70)
    print("Done.")


if __name__ == "__main__":
    main()
