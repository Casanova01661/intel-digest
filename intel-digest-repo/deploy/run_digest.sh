#!/bin/bash
#
# Wrapper for running the intel digest pipeline from cron.
#
# Cron runs with a minimal environment (no .bashrc, no venv activation,
# often a different working directory) so this script explicitly sets
# up everything main.py needs before running it.

# Exit immediately if any command fails, so partial/broken runs don't
# silently continue
set -e

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
LOG_FILE="$PROJECT_DIR/cron.log"

cd "$PROJECT_DIR"

# Load environment variables (ANTHROPIC_API_KEY, TELEGRAM_*) from the same .env file systemd uses.
# .env is in KEY=VALUE format (no 'export'), so we use set -a to mark
# everything sourced as exported automatically.
set -a
source "$PROJECT_DIR/.env"
set +a

echo "===== Run started: $(date -u '+%Y-%m-%d %H:%M:%S UTC') =====" >> "$LOG_FILE"

# Use the venv's python directly rather than relying on 'activate',
# which doesn't behave the same way in a non-interactive cron shell
"$PROJECT_DIR/venv/bin/python3" "$PROJECT_DIR/main.py" >> "$LOG_FILE" 2>&1

echo "===== Run finished: $(date -u '+%Y-%m-%d %H:%M:%S UTC') =====" >> "$LOG_FILE"
echo "" >> "$LOG_FILE"
