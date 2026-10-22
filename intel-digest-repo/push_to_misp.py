"""
Pushes each relevant, summarized intel item into MISP as an event:
  - IOCs become MISP attributes (ip-dst, domain, url, hash types, vulnerability)
  - Validated ATT&CK techniques get attached as MISP Galaxy clusters
  - The Claude-written summary goes in as a comment attribute for context

Requires environment variables:
    MISP_URL       e.g. https://misp.homelab.local
    MISP_API_KEY   from your MISP user profile (Auth Keys)

By design this only CREATES events for review in MISP -- it does not
publish them. Publishing (making an event visible to sync partners/feeds)
is a deliberate action you take in the MISP UI, not something this
script does automatically. Same principle as the detection-rule
discussion: automation drafts, a human approves.

Usage:
    export MISP_URL=https://misp.homelab.local
    export MISP_API_KEY=your-api-key-here
    python push_to_misp.py
"""

import os
import sqlite3
import json

from pymisp import PyMISP, MISPEvent, MISPAttribute

MISP_URL = os.environ.get("MISP_URL")
MISP_API_KEY = os.environ.get("MISP_API_KEY")
MISP_VERIFY_SSL = os.environ.get("MISP_VERIFY_SSL", "true").lower() != "false"  # set false for self-signed homelab certs

HASH_TYPE_BY_LENGTH = {32: "md5", 40: "sha1", 64: "sha256"}


def get_misp_client() -> PyMISP:
    if not MISP_URL or not MISP_API_KEY:
        raise RuntimeError(
            "MISP_URL and MISP_API_KEY must be set as environment variables. "
            "MISP_VERIFY_SSL=false if your homelab MISP uses a self-signed cert."
        )
    return PyMISP(MISP_URL, MISP_API_KEY, ssl=MISP_VERIFY_SSL)


def hash_attribute_type(hash_value: str) -> str:
    return HASH_TYPE_BY_LENGTH.get(len(hash_value.strip()), "sha256")  # default fallback, rarely hit


def build_event_from_item(item: dict) -> MISPEvent:
    """Build (but don't yet push) a MISPEvent from one digest item's stored analysis."""
    analysis = json.loads(item["digest_summary"])

    event = MISPEvent()
    event.info = f"[Intel Digest] {item['title']}"
    event.distribution = 0  # "Your organisation only" -- safest default, change deliberately if you want to share
    event.threat_level_id = 2  # Medium -- a reasonable default; adjust per-event in the MISP UI as needed
    event.analysis = 1  # "Ongoing" -- this was auto-drafted, not yet fully analyst-reviewed

    # Context as a comment attribute, not just tucked in event.info
    event.add_attribute(
        "comment",
        (
            f"Source: {item['source']} | Original link: {item['link']}\n"
            f"Relevance: {analysis.get('relevance_reason', '')}\n"
            f"Summary: {analysis.get('summary', '')}\n"
            f"Why it matters: {analysis.get('why_it_matters', '')}\n"
            f"Suggested action: {analysis.get('suggested_action', '')}\n"
            f"[Auto-drafted by intel-digest pipeline -- review before acting]"
        ),
        comment="Claude-generated triage summary",
    )

    iocs = analysis.get("iocs", {})
    for ip in iocs.get("ips", []):
        event.add_attribute("ip-dst", ip, comment="from intel-digest pipeline")
    for domain in iocs.get("domains", []):
        event.add_attribute("domain", domain, comment="from intel-digest pipeline")
    for url in iocs.get("urls", []):
        event.add_attribute("url", url, comment="from intel-digest pipeline")
    for h in iocs.get("hashes", []):
        event.add_attribute(hash_attribute_type(h), h, comment="from intel-digest pipeline")
    for cve in iocs.get("cves", []):
        event.add_attribute("vulnerability", cve, comment="from intel-digest pipeline")

    for ref_url in analysis.get("reference_links", []):
        event.add_attribute("link", ref_url, comment="technical reference")

    # Tag with validated ATT&CK techniques via MISP's galaxy/taxonomy convention.
    # This assumes your MISP instance has the standard ATT&CK galaxy installed
    # (it does by default on most modern MISP installs).
    for t in analysis.get("validated_techniques", []):
        event.add_tag(f'misp-galaxy:mitre-attack-pattern="{t["name"]} - {t["id"]}"')

    return event


def push_pending_events(db_path: str = "intel_digest.db") -> list[str]:
    """
    Push every relevant item that hasn't been pushed to MISP yet.
    Tracks push status in a new column so re-running doesn't duplicate events.
    """
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row

    conn.execute(
        "ALTER TABLE items ADD COLUMN pushed_to_misp INTEGER DEFAULT 0"
    ) if not _has_column(conn, "items", "pushed_to_misp") else None
    conn.commit()

    pending = conn.execute(
        "SELECT * FROM items WHERE is_relevant = 1 AND pushed_to_misp = 0"
    ).fetchall()

    if not pending:
        print("No new relevant items to push to MISP.")
        conn.close()
        return []

    misp = get_misp_client()
    pushed_event_uuids = []

    for row in pending:
        item = dict(row)
        event = build_event_from_item(item)
        result = misp.add_event(event, pythonify=True)

        if isinstance(result, dict) and result.get("errors"):
            print(f"  [error] failed to push '{item['title']}': {result['errors']}")
            continue

        pushed_event_uuids.append(result.uuid)
        conn.execute(
            "UPDATE items SET pushed_to_misp = 1 WHERE link = ?", (item["link"],)
        )
        print(f"  Pushed '{item['title']}' -> MISP event {result.uuid} (unpublished, review in MISP UI)")

    conn.commit()
    conn.close()
    return pushed_event_uuids


def _has_column(conn: sqlite3.Connection, table: str, column: str) -> bool:
    cols = [row[1] for row in conn.execute(f"PRAGMA table_info({table})")]
    return column in cols


if __name__ == "__main__":
    uuids = push_pending_events()
    print(f"\nPushed {len(uuids)} new event(s) to MISP. All are unpublished -- review and publish manually.")
