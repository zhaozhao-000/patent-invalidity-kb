from __future__ import annotations


def url_for(patent_number: str) -> str:
    return f"https://patents.google.com/patent/{patent_number}/en" if patent_number else ""
