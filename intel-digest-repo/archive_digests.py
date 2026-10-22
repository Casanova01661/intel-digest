"""
Archives old digest files to keep the digests/ folder manageable.

Digests older than ARCHIVE_AFTER_DAYS get consolidated into a single
monthly archive file (digests/archive/YYYY-MM.md) and the individual
files are removed. Nothing is ever deleted outright -- content is
merged into the monthly archive, not discarded, so your history stays
intact just in a more compact form.

Recent digests (within the threshold) are left alone so /latest and
manual browsing still work exactly as before.

Usage:
    python archive_digests.py            # archive anything older than 30 days
    python archive_digests.py --days 14  # custom threshold
"""

import argparse
import glob
import os
import re
from datetime import datetime, timezone, timedelta
from collections import defaultdict

DIGESTS_DIR = "digests"
ARCHIVE_DIR = os.path.join(DIGESTS_DIR, "archive")

FILENAME_PATTERN = re.compile(r"digest_(\d{8})_(\d{6})\.md$")


def parse_digest_timestamp(path: str) -> datetime | None:
    """Extract the timestamp from a digest_YYYYMMDD_HHMMSS.md filename."""
    match = FILENAME_PATTERN.search(os.path.basename(path))
    if not match:
        return None
    date_str, time_str = match.groups()
    return datetime.strptime(date_str + time_str, "%Y%m%d%H%M%S").replace(tzinfo=timezone.utc)


def archive_old_digests(days_threshold: int = 30) -> dict:
    """
    Move digests older than days_threshold into monthly archive files.
    Returns a summary dict for reporting.
    """
    cutoff = datetime.now(timezone.utc) - timedelta(days=days_threshold)
    os.makedirs(ARCHIVE_DIR, exist_ok=True)

    candidates = glob.glob(os.path.join(DIGESTS_DIR, "digest_*.md"))
    by_month = defaultdict(list)

    for path in candidates:
        ts = parse_digest_timestamp(path)
        if ts is None:
            print(f"  [skip] couldn't parse timestamp from {path}, leaving it alone")
            continue
        if ts >= cutoff:
            continue  # too recent, leave it in the main digests/ folder
        month_key = ts.strftime("%Y-%m")
        by_month[month_key].append((path, ts))

    archived_count = 0
    for month_key, entries in by_month.items():
        entries.sort(key=lambda e: e[1])  # chronological order within the month
        archive_path = os.path.join(ARCHIVE_DIR, f"{month_key}.md")

        # Append if the monthly archive already exists (e.g. from a previous run)
        mode = "a" if os.path.exists(archive_path) else "w"
        with open(archive_path, mode) as archive_file:
            if mode == "w":
                archive_file.write(f"# Archived Digests — {month_key}\n\n")
            for path, ts in entries:
                with open(path) as f:
                    content = f.read()
                archive_file.write(f"\n\n<!-- Originally: {os.path.basename(path)} ({ts.isoformat()}) -->\n\n")
                archive_file.write(content)
                os.remove(path)
                archived_count += 1

        print(f"  Archived {len(entries)} digest(s) into {archive_path}")

    return {"archived_count": archived_count, "months_touched": len(by_month), "cutoff": cutoff.isoformat()}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Archive old digest files into monthly summaries.")
    parser.add_argument("--days", type=int, default=30, help="Archive digests older than this many days (default: 30)")
    args = parser.parse_args()

    result = archive_old_digests(args.days)
    print(f"\nDone. Archived {result['archived_count']} digest(s) across {result['months_touched']} month(s).")
