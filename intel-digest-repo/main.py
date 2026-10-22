"""
Phase 1: base digest pipeline (feeds -> relevance/IOC/reference-link
extraction via Claude -> markdown digest). No ATT&CK or MISP integration
yet -- those are added back in once this phase is validated.

Usage:
    export ANTHROPIC_API_KEY=sk-ant-...
    python main.py
"""

import json
import os
import sqlite3
from datetime import datetime, timezone

from fetch_feeds import init_db, fetch_new_items
from summarize import process_pending_items


def generate_digest_markdown(relevant_items: list[dict]) -> str:
    if not relevant_items:
        return "# Threat Intel Digest\n\nNo client-relevant items this run.\n"

    date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    lines = [f"# Threat Intel Digest — {date_str}", ""]
    lines.append(f"{len(relevant_items)} item(s) flagged as relevant to the client profile.\n")

    for item in relevant_items:
        a = item["analysis"]
        lines.append(f"## {item['title']}")
        lines.append(f"**Source:** {item['source']} | **Link:** {item['link']}")
        lines.append("")
        lines.append(f"**Why it's relevant:** {a['relevance_reason']}")
        lines.append("")
        lines.append(f"**Summary:** {a['summary']}")
        lines.append("")
        lines.append(f"**Why it matters here:** {a['why_it_matters']}")
        lines.append("")
        lines.append(f"**Suggested action:** {a['suggested_action']}")

        iocs = a.get("iocs", {})
        ioc_lines = []
        for label, key in [("IPs", "ips"), ("Domains", "domains"), ("URLs", "urls"), ("Hashes", "hashes"), ("CVEs", "cves")]:
            values = iocs.get(key) or []
            if values:
                ioc_lines.append(f"- **{label}:** {', '.join(values)}")

        if ioc_lines:
            lines.append("")
            lines.append("**IOCs:**")
            lines.extend(ioc_lines)
        else:
            lines.append("")
            lines.append("**IOCs:** none extracted from this item")

        reference_links = a.get("reference_links") or []
        if reference_links:
            lines.append("")
            lines.append("**Technical reports / additional references:**")
            for ref_url in reference_links:
                lines.append(f"- {ref_url}")

        lines.append("\n---\n")

    return "\n".join(lines)


def main():
    print("1. Fetching new feed items...")
    conn = init_db()
    new_items = fetch_new_items(conn)
    conn.close()
    print(f"   Pulled {len(new_items)} new item(s).")

    print("2. Analyzing relevance and summarizing with Claude...")
    relevant_items = process_pending_items()
    print(f"   {len(relevant_items)} item(s) relevant to client profile.")

    print("3. Writing digest...")
    digest_md = generate_digest_markdown(relevant_items)
    os.makedirs("digests", exist_ok=True)
    out_path = os.path.join("digests", f"digest_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}.md")
    with open(out_path, "w") as f:
        f.write(digest_md)
    print(f"   Digest written to {out_path}")

    print("4. Sending digest to Telegram...")
    try:
        from telegram_notify import send_digest
        send_digest(out_path)
    except RuntimeError as e:
        print(f"   [skipped] {e}")
    except Exception as e:
        print(f"   [error] Telegram send failed: {e}. Digest file is still saved locally.")


if __name__ == "__main__":
    main()
