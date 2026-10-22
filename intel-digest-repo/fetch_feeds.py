"""
Pulls items from configured RSS feeds and stores new ones in a local
SQLite database, deduplicated by link so re-running doesn't re-process
the same advisory.
"""

import sqlite3
import feedparser
from datetime import datetime, timezone

from feeds import FEEDS

DB_PATH = "intel_digest.db"


def init_db(db_path: str = DB_PATH) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS items (
            link TEXT PRIMARY KEY,
            source TEXT,
            title TEXT,
            summary TEXT,
            published TEXT,
            fetched_at TEXT,
            is_relevant INTEGER DEFAULT NULL,
            digest_summary TEXT DEFAULT NULL,
            included_in_digest INTEGER DEFAULT 0
        )
        """
    )
    conn.commit()
    return conn


def fetch_new_items(conn: sqlite3.Connection) -> list[dict]:
    """Pull all configured feeds, insert new items, return the new ones."""
    new_items = []
    now = datetime.now(timezone.utc).isoformat()

    for feed in FEEDS:
        parsed = feedparser.parse(feed["url"])
        if parsed.bozo:
            print(f"  [warn] could not cleanly parse {feed['name']}: {parsed.bozo_exception}")

        for entry in parsed.entries:
            link = entry.get("link", "")
            if not link:
                continue

            existing = conn.execute(
                "SELECT 1 FROM items WHERE link = ?", (link,)
            ).fetchone()
            if existing:
                continue

            item = {
                "link": link,
                "source": feed["name"],
                "title": entry.get("title", "(no title)"),
                "summary": entry.get("summary", entry.get("description", "")),
                "published": entry.get("published", entry.get("updated", "")),
                "fetched_at": now,
            }
            conn.execute(
                """
                INSERT INTO items (link, source, title, summary, published, fetched_at)
                VALUES (:link, :source, :title, :summary, :published, :fetched_at)
                """,
                item,
            )
            new_items.append(item)

    conn.commit()
    return new_items


if __name__ == "__main__":
    conn = init_db()
    new = fetch_new_items(conn)
    print(f"Pulled {len(new)} new item(s) across {len(FEEDS)} feed(s).")
    for item in new:
        print(f"  [{item['source']}] {item['title']}")
    conn.close()
