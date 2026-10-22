"""
Downloads MITRE's Enterprise ATT&CK STIX bundle and distills it into a
small local lookup table (technique_id -> name/tactic/description).

Run this occasionally (e.g. monthly) to refresh the technique list --
MITRE adds/deprecates techniques periodically. It's a separate step
from the main pipeline so you're not re-downloading a 48MB file on
every digest run.

Usage:
    python build_attack_library.py
"""

import json
import urllib.request

STIX_URL = "https://raw.githubusercontent.com/mitre/cti/master/enterprise-attack/enterprise-attack.json"
OUTPUT_PATH = "attack_techniques.json"


def fetch_stix_bundle(url: str = STIX_URL) -> dict:
    print(f"Downloading ATT&CK STIX bundle from {url} ...")
    with urllib.request.urlopen(url) as response:
        return json.loads(response.read())


def extract_techniques(stix_bundle: dict) -> dict:
    """Distill the full STIX bundle down to id -> {name, tactic, description, url}."""
    techniques = {}

    for obj in stix_bundle["objects"]:
        if obj.get("type") != "attack-pattern":
            continue
        if obj.get("revoked") or obj.get("x_mitre_deprecated"):
            continue

        # Find the ATT&CK technique ID (e.g. T1566 or T1566.001) from external_references
        technique_id = None
        url = ""
        for ref in obj.get("external_references", []):
            if ref.get("source_name") == "mitre-attack":
                technique_id = ref.get("external_id")
                url = ref.get("url", "")
                break

        if not technique_id:
            continue

        tactics = [
            phase["phase_name"]
            for phase in obj.get("kill_chain_phases", [])
            if phase.get("kill_chain_name") == "mitre-attack"
        ]

        techniques[technique_id] = {
            "name": obj.get("name", ""),
            "tactics": tactics,
            "description": (obj.get("description", "") or "")[:300],  # trim, full descriptions are long
            "url": url,
        }

    return techniques


def main():
    bundle = fetch_stix_bundle()
    techniques = extract_techniques(bundle)

    with open(OUTPUT_PATH, "w") as f:
        json.dump(techniques, f, indent=2)

    print(f"Wrote {len(techniques)} techniques to {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
