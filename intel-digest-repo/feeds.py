"""
Feed sources for the intel digest pipeline.
Start small and add more once the pipeline is proven out.
"""

FEEDS = [
    {
        "name": "CISA Alerts",
        "url": "https://www.cisa.gov/cybersecurity-advisories/all.xml",
    },
    {
        "name": "SANS ISC Diary",
        "url": "https://isc.sans.edu/rssfeed_full.xml",
    },
    # Add more later, e.g.:
    # {"name": "Auto-ISAC", "url": "..."},
    # {"name": "E-ISAC", "url": "..."},
]
