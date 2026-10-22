# Sample digest

> **Illustrative example.** This is formatted exactly like real pipeline output, but the advisories, vendors, hashes, and links below are fabricated placeholders for demonstration. They do not describe real incidents. (Real output also excludes documentation-range IPs like `203.0.113.x` from IOCs, so none appear here.)

---

# Threat Intel Digest — 2026-01-15

2 item(s) flagged as relevant to the client profile.

## Ransomware affiliate abusing exposed RDP and VPN gateways (example)
**Source:** CISA Alerts | **Link:** https://www.example.com/advisories/example-ransomware-001

**Why it's relevant:** The advisory describes initial access through internet-exposed RDP and VPN gateways using stolen credentials. The client profile lists both RDP and a VPN gateway as exposed services.

**Summary:** An affiliate of a ransomware group gains access via valid credentials on remote access services, moves laterally with legitimate admin tools, then exfiltrates data before encrypting. The advisory lists behaviors and a small set of indicators.

**Why it matters here:** Exposed RDP and VPN are two of the client's listed entry points, and Windows Server 2022 hosts are the likely lateral movement targets.

**Suggested action:** Verify MFA is enforced on the VPN gateway, confirm RDP is not directly reachable from the internet, and search logs for the listed domain and hash.

**IOCs:**
- **Domains:** update-check.example
- **Hashes:** aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa

**Technical reports / additional references:**
- https://www.example.com/reports/example-ransomware-technical-analysis

---

## Remote code execution in an industrial protocol gateway (example)
**Source:** CISA Alerts | **Link:** https://www.example.com/advisories/example-ics-002

**Why it's relevant:** Critical-infrastructure/OT equipment. The product is not named in the profile, but it handles Modbus traffic, and the profile lists Modbus and SCADA components. OT/ICS items are treated inclusively by design.

**Summary:** An unauthenticated network attacker can execute code on a gateway that bridges serial and Modbus/TCP devices. A firmware update is available.

**Why it matters here:** Charging sites with Modbus-connected controllers could be affected if a similar gateway sits between the site network and field devices.

**Suggested action:** Confirm whether any site uses this gateway class, and check network segmentation between the gateway and the management network.

**IOCs:** none extracted from this item

---
