"""Local US patent lookup cache helper.

This script intentionally does not call an external API by default. It normalizes
US patent numbers and reads/writes data/external/us_patents_cache.json so manual
or future API adapters can provide reliable patent titles without changing the
main database builder.
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
CACHE_PATH = ROOT / "data" / "external" / "us_patents_cache.json"


def normalize_us_patent_number(value: str) -> str:
    text = str(value or "").upper()
    match = re.search(r"(?:US|U\.S\.\s*PATENT\s*NO\.?|PATENT\s*)?\s*(\d{6,11})(?:\s*([A-Z]\d))?", text.replace(",", ""))
    if not match:
        return ""
    suffix = match.group(2) or ""
    return f"US{match.group(1)}{suffix}"


def load_cache() -> dict[str, Any]:
    if not CACHE_PATH.exists():
        return {}
    return json.loads(CACHE_PATH.read_text(encoding="utf-8"))


def save_cache(cache: dict[str, Any]) -> None:
    CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
    CACHE_PATH.write_text(json.dumps(cache, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Read or update local US patent title cache.")
    parser.add_argument("patent_number", help="Example: US 10,123,456 B2")
    parser.add_argument("--title", default="", help="Patent title to store in the local cache.")
    parser.add_argument("--assignee", default="", help="Assignee to store in the local cache.")
    parser.add_argument("--abstract", default="", help="Patent abstract to store in the local cache.")
    args = parser.parse_args()

    normalized = normalize_us_patent_number(args.patent_number)
    if not normalized:
        raise SystemExit("Could not normalize patent number.")

    cache = load_cache()
    if args.title or args.assignee or args.abstract:
        current = cache.get(normalized, {})
        current.update(
            {
                "patent_title": args.title or current.get("patent_title", ""),
                "assignee": args.assignee or current.get("assignee", ""),
                "abstract": args.abstract or current.get("abstract", ""),
                "source": "manual_cache",
                "confidence": 0.95,
                "google_patents_url": f"https://patents.google.com/patent/{normalized}/en",
            }
        )
        cache[normalized] = current
        save_cache(cache)
    print(json.dumps(cache.get(normalized, {"patent_number": normalized, "status": "not_in_cache"}), ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
