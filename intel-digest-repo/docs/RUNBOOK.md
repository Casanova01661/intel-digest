# Runbook

Operational reference for running the pipeline unattended. For the project overview, see the [README](../README.md).

Paths below assume the project lives at `~/intel-digest`. Adjust to your setup.

## Setup from scratch

```bash
cd ~/intel-digest
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env && chmod 600 .env     # fill in the three values
nano client_profile.json                    # replace the synthetic profile
./deploy/run_digest.sh && cat cron.log      # confirm one clean run
```

Telegram: create a bot with @BotFather, message it once, then read your chat ID from `https://api.telegram.org/bot<TOKEN>/getUpdates`.

Listener service (answers `/latest`):

```bash
# edit User= and paths in deploy/telegram-bot-listener.service first
sudo cp deploy/telegram-bot-listener.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now telegram-bot-listener
```

## Scheduling

```
0 9 * * *  /home/YOUR_USER/intel-digest/deploy/run_digest.sh    # daily digest
0 9 1 * *  /home/YOUR_USER/intel-digest/deploy/run_archive.sh   # monthly archive (older than 30 days)
```

Cron uses the system's local time zone.

**Why 9 AM.** CISA's feed stamps most items `12:00:00 +0000` (a batch timestamp, inferred from a sample of items). A run at 8 AM US Eastern Daylight Time landed on that same instant, so some mornings the fetch ran before the feed updated. 9 AM gives about an hour of buffer in summer and about two hours after clocks go back. If CISA items still arrive a day late, move the run later.

**Environment.** Cron does not read `~/.bashrc`. `run_digest.sh` sources `.env` and calls the venv's Python directly. The listener reads the same `.env` through the systemd `EnvironmentFile`.

**WSL2.** systemd must be enabled (`[boot]` `systemd=true` in `/etc/wsl.conf`, then `wsl --shutdown` from Windows) before the listener service and cron can be managed properly.

## Behavior to expect

- Each digest contains only **new** items. An item appears once, in the run that first scores it. `/latest` returns the newest digest file, not a cumulative list.
- A run with nothing new still writes and sends a digest ("No client-relevant items this run"). Most days look like this.
- The SANS Stormcast podcast entry has no body text and is correctly scored not relevant.
- If Telegram fails or its variables are missing, the digest is still saved and the run does not crash.
- Telegram messages are split on item boundaries at ~3,800 characters (the API cap is 4,096).

## Daily validation (about two minutes)

1. Skim the digest. Anything that looks like a stretch, or anything missing?
2. From the project root: `sqlite3 intel_digest.db "SELECT COUNT(*), SUM(is_relevant) FROM items;"`
3. `tail -40 cron.log` and confirm no traceback between the start and finish markers.
4. For anything questionable: `sqlite3 intel_digest.db "SELECT title, digest_summary FROM items WHERE title LIKE '%keyword%';"`

## Useful commands

```bash
sudo journalctl -u telegram-bot-listener -f          # listener logs
sudo systemctl restart telegram-bot-listener         # after code changes

# Re-score everything after a prompt change (one API call per stored item)
sqlite3 intel_digest.db "UPDATE items SET is_relevant = NULL, digest_summary = NULL;"
python3 main.py
```

## Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| `ModuleNotFoundError` | venv not active | `source venv/bin/activate` |
| `no such table: items` | `sqlite3` run outside the project root created an empty decoy DB | `cd` to the project root; delete the 0-byte `.db` file in the wrong folder |
| Auth error under cron, fine by hand | `ANTHROPIC_API_KEY` missing from `.env` | Add it; cron doesn't read `.bashrc` |
| `System has not been booted with systemd` | WSL without systemd | Enable it (see WSL2 above) |
| "No client-relevant items" every day | Items were already scored in an earlier run, or the CISA batch hadn't published yet | Check `SELECT` counts; confirm run time vs. 12:00 UTC |
| Telegram silent | Wrong chat ID, or bot never messaged | Message the bot once, re-read `getUpdates` |

## Cost

Claude Haiku 4.5 at $1 / $5 per million input / output tokens: a few cents on a normal day, well under $1 for a full 40-50 item re-score. Output is capped at `max_tokens=1000`; going lower caused truncated JSON (see README).

## Security checklist

- `.env` is `chmod 600` and git-ignored. Check `git log -p -- .env` returns nothing before publishing.
- If a bot token is ever pasted anywhere, revoke and reissue it via @BotFather.
- Re-run `bandit -r .` and `pip-audit` periodically.
- Feed content is untrusted input to the model. Add delimiter hardening before adding more feeds.

## Built but not deployed

`attack_mapper.py`, `build_attack_library.py` and `push_to_misp.py` implement ATT&CK technique validation and unpublished MISP event creation. `summarize.py` already asks the model for technique IDs and stores them, but nothing validates or reports them until `attack_mapper.py` is wired into `main.py`. Generate the technique library with `python3 build_attack_library.py`.
