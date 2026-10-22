"""
Validates LLM-suggested ATT&CK technique IDs against the real MITRE
catalog (built by build_attack_library.py), and maintains a running
"library" table tracking which techniques keep showing up in intel
relevant to the client profile.

Any technique ID the model proposes that ISN'T in the real MITRE
catalog is dropped, not guessed at or auto-corrected -- garbage in
should not become garbage-that-looks-official out.
"""

import json
import sqlite3

TECHNIQUES_PATH = "attack_techniques.json"


def load_technique_catalog(path: str = TECHNIQUES_PATH) -> dict:
    with open(path) as f:
        return json.load(f)


def init_library_table(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS technique_library (
            technique_id TEXT PRIMARY KEY,
            name TEXT,
            tactics TEXT,
            url TEXT,
            times_seen INTEGER DEFAULT 0,
            first_seen TEXT,
            last_seen TEXT
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS technique_observations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            technique_id TEXT,
            item_link TEXT,
            item_title TEXT,
            observed_at TEXT,
            FOREIGN KEY (technique_id) REFERENCES technique_library(technique_id),
            FOREIGN KEY (item_link) REFERENCES items(link)
        )
        """
    )
    conn.commit()


def validate_technique_ids(proposed_ids: list[str], catalog: dict) -> list[str]:
    """Drop any ID the model proposed that isn't a real, current ATT&CK technique."""
    valid = []
    for tid in proposed_ids:
        tid_clean = tid.strip().upper()
        if tid_clean in catalog:
            valid.append(tid_clean)
        else:
            print(f"  [warn] model proposed unknown/invalid technique ID '{tid}', dropping it")
    return valid


def record_observations(
    conn: sqlite3.Connection,
    technique_ids: list[str],
    catalog: dict,
    item: dict,
    observed_at: str,
) -> None:
    """Update the running library + observation log for each validated technique."""
    for tid in technique_ids:
        info = catalog[tid]

        existing = conn.execute(
            "SELECT times_seen, first_seen FROM technique_library WHERE technique_id = ?",
            (tid,),
        ).fetchone()

        if existing is None:
            conn.execute(
                """
                INSERT INTO technique_library
                    (technique_id, name, tactics, url, times_seen, first_seen, last_seen)
                VALUES (?, ?, ?, ?, 1, ?, ?)
                """,
                (tid, info["name"], ",".join(info["tactics"]), info["url"], observed_at, observed_at),
            )
        else:
            conn.execute(
                """
                UPDATE technique_library
                SET times_seen = times_seen + 1, last_seen = ?
                WHERE technique_id = ?
                """,
                (observed_at, tid),
            )

        conn.execute(
            """
            INSERT INTO technique_observations (technique_id, item_link, item_title, observed_at)
            VALUES (?, ?, ?, ?)
            """,
            (tid, item["link"], item["title"], observed_at),
        )


def get_library_summary(db_path: str = "intel_digest.db") -> list[dict]:
    """Return the current technique library, most-observed first."""
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        "SELECT * FROM technique_library ORDER BY times_seen DESC, last_seen DESC"
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


if __name__ == "__main__":
    catalog = load_technique_catalog()
    print(f"Loaded {len(catalog)} valid ATT&CK techniques.")

    conn = sqlite3.connect("intel_digest.db")
    init_library_table(conn)
    conn.close()
    print("Library tables ready.")
