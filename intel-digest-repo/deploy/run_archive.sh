#!/bin/bash
#
# Wrapper for running the digest archival/cleanup script from cron.
# Unlike run_digest.sh, this doesn't need API keys (archive_digests.py
# only touches local files), so no .env sourcing required -- just the
# correct directory and the venv's Python.

set -e

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
LOG_FILE="$PROJECT_DIR/archive.log"

cd "$PROJECT_DIR"

echo "===== Archive run started: $(date -u '+%Y-%m-%d %H:%M:%S UTC') =====" >> "$LOG_FILE"

"$PROJECT_DIR/venv/bin/python3" "$PROJECT_DIR/archive_digests.py" >> "$LOG_FILE" 2>&1

echo "===== Archive run finished: $(date -u '+%Y-%m-%d %H:%M:%S UTC') =====" >> "$LOG_FILE"
echo "" >> "$LOG_FILE"
