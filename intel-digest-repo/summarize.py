"""
Uses the Claude API to:
  1. Judge whether a threat intel item is relevant to the client profile
  2. If relevant, produce a short structured summary an analyst can scan

Requires ANTHROPIC_API_KEY to be set in the environment.
Uses Haiku by default since this is a cheap, high-volume summarization
task, not something that needs a frontier model.
"""

import json
import os
import sqlite3

import anthropic

MODEL = "claude-haiku-4-5-20251001"

PROMPT_TEMPLATE = """You are a threat intel triage assistant for a SOC team.

Below is a client environment profile and a single threat intel item
(an advisory, alert, or diary entry). Decide whether this item is
plausibly relevant to the client's environment, and if so, summarize it.

Be strict about what counts as relevant. Mark is_relevant true ONLY if
the item describes one of:
  - an active vulnerability, exploit, or CVE affecting a vendor/product/
    protocol in the client profile
  - an active threat, campaign, or attacker activity targeting the
    client's industry, vendors, or exposed services
  - a security incident or advisory directly tied to something in the
    client profile

Do NOT mark an item relevant just because it mentions a vendor/product
name from the profile in passing. Defensive how-to content, detection
scripting tutorials, admin tooling tips, and "how to audit your own
environment" writeups are NOT relevant on their own, even if they
reference a product in the profile (e.g. Entra ID, AWS) -- unless the
item itself is describing an active threat or vulnerability, not just
teaching a technique. When in doubt between "this is genuinely a threat"
and "this just name-drops something in our stack," lean toward NOT relevant.

EXCEPTION -- Operational Technology / Industrial Control Systems / critical
infrastructure equipment: for this category specifically, lean INCLUSIVE
rather than strict. If the item describes an active vulnerability, exploit,
or threat affecting OT/ICS equipment (PLCs, RTUs, SCADA components,
industrial networking/gateway appliances, industrial protocols, etc.) from
the SAME vendor family as something in the client profile, or from the same
critical-infrastructure sector (energy, EV charging, automotive, industrial
control), mark it relevant even if the exact model/product isn't explicitly
named in the profile. The consequence of missing a genuine OT/ICS threat is
high, so for this category only, prefer a false positive over a false
negative. Note in relevance_reason when you're using this exception (e.g.
"not explicitly in inventory, but same vendor family / OT category").

CLIENT PROFILE:
{profile}

INTEL ITEM:
Source: {source}
Title: {title}
Content: {content}

Also extract any Indicators of Compromise (IOCs) explicitly present in the
content: IP addresses, domains, URLs, file hashes (MD5/SHA1/SHA256), and
CVE IDs. Only include IOCs that are literally present in the text above —
never invent or infer one. If none are present, return empty lists.

Do NOT include well-known, non-malicious infrastructure addresses as
IOCs even if they appear in the text -- for example the AWS/Azure/GCP
cloud metadata service address (169.254.169.254), documentation example
addresses (e.g. RFC 5737 ranges like 203.0.113.0/24, 198.51.100.0/24),
or localhost/private ranges used as examples. These are technique
context, not indicators to hunt for. Only list addresses/values that are
actually attacker-controlled or malicious per the content.

Separately, extract any reference links explicitly present in the content
that point to additional technical resources — full technical reports,
vendor advisories, PDF writeups, MITRE ATT&CK Navigator layers, patch
notes, or similar. This is distinct from the item's own landing page link.
Only include URLs that are literally present in the text above.

If relevant, also identify which MITRE ATT&CK (Enterprise) techniques this
item describes or relates to, based on the adversary behavior mentioned
(not just the vendor/product affected). Give your best-guess technique IDs
in the form "T1566" or "T1566.001" — these will be validated against the
real ATT&CK catalog afterward, so it's fine to be uncertain; just don't
guess wildly. If no specific technique is identifiable, return an empty list.

Respond with ONLY a JSON object, no other text, no markdown fences:
{{
  "is_relevant": true or false,
  "relevance_reason": "one sentence explaining why, referencing specific vendors/products/industry from the profile if relevant",
  "summary": "2-3 sentence plain-language summary of what happened, only if relevant, otherwise empty string",
  "why_it_matters": "1-2 sentences on the potential impact to this specific environment, only if relevant, otherwise empty string",
  "suggested_action": "a short, concrete next step for the analyst, only if relevant, otherwise empty string",
  "iocs": {{
    "ips": [],
    "domains": [],
    "urls": [],
    "hashes": [],
    "cves": []
  }},
  "reference_links": [],
  "attack_technique_ids": []
}}
"""


def load_client_profile(path: str = "client_profile.json") -> dict:
    with open(path) as f:
        return json.load(f)


def analyze_item(client: anthropic.Anthropic, profile: dict, item: dict) -> dict:
    prompt = PROMPT_TEMPLATE.format(
        profile=json.dumps(profile, indent=2),
        source=item["source"],
        title=item["title"],
        content=item["summary"][:2000],  # keep token usage sane
    )

    response = client.messages.create(
        model=MODEL,
        max_tokens=1000,
        messages=[{"role": "user", "content": prompt}],
    )

    raw_text = response.content[0].text.strip()
    # Guard against the model wrapping in markdown fences despite instructions
    raw_text = raw_text.removeprefix("```json").removeprefix("```").removesuffix("```").strip()

    try:
        return json.loads(raw_text)
    except json.JSONDecodeError:
        print(f"  [WARNING] JSON parse failure for '{item['title']}' -- likely truncated output (raw length: {len(raw_text)} chars). Treating as NOT relevant, but this is NOT a real verdict -- re-run to get an actual answer for this item.")
        return {
            "is_relevant": False,
            "relevance_reason": "parse_error -- response was truncated or malformed, not a genuine relevance judgment",
            "summary": "",
            "why_it_matters": "",
            "suggested_action": "",
            "iocs": {"ips": [], "domains": [], "urls": [], "hashes": [], "cves": []},
            "reference_links": [],
            "attack_technique_ids": [],
        }


def process_pending_items(db_path: str = "intel_digest.db", profile_path: str = "client_profile.json") -> list[dict]:
    """Analyze every item that hasn't been scored yet. Returns the relevant ones."""
    client = anthropic.Anthropic()  # reads ANTHROPIC_API_KEY from environment
    profile = load_client_profile(profile_path)

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    pending = conn.execute(
        "SELECT * FROM items WHERE is_relevant IS NULL"
    ).fetchall()

    relevant_items = []
    for row in pending:
        item = dict(row)
        result = analyze_item(client, profile, item)

        conn.execute(
            """
            UPDATE items
            SET is_relevant = ?, digest_summary = ?
            WHERE link = ?
            """,
            (
                1 if result["is_relevant"] else 0,
                json.dumps(result),
                item["link"],
            ),
        )

        if result["is_relevant"]:
            item["analysis"] = result
            relevant_items.append(item)

    conn.commit()
    conn.close()
    return relevant_items


if __name__ == "__main__":
    relevant = process_pending_items()
    print(f"Found {len(relevant)} relevant item(s).")
    for item in relevant:
        print(f"  - {item['title']} ({item['source']})")
