from __future__ import annotations

import argparse
import html
import json
import os
import re
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

from us_case_parser import normalize_us_patent_number


ROOT = Path(__file__).resolve().parents[1]
CACHE_PATH = ROOT / "data" / "external" / "us_patents_cache.json"
NEEDED_PATH = ROOT / "reports" / "us_patent_lookup_needed.csv"


def load_cache() -> dict[str, Any]:
    if not CACHE_PATH.exists():
        return {}
    try:
        return json.loads(CACHE_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return {}


def save_cache(cache: dict[str, Any]) -> None:
    CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
    CACHE_PATH.write_text(json.dumps(cache, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def google_patents_url(patent_number: str) -> str:
    return f"https://patents.google.com/patent/{patent_number}/en" if patent_number else ""


def empty_result(patent_number: str, status: str = "failed", source: str = "lookup_failed") -> dict[str, Any]:
    return {
        "patent_number": patent_number,
        "patent_title": "",
        "abstract": "",
        "independent_claims": [],
        "assignee": "",
        "inventors": [],
        "cpc": [],
        "publication_date": "",
        "grant_date": "",
        "source": source,
        "lookup_status": status,
        "status": status,
        "google_patents_url": google_patents_url(patent_number),
        "confidence": 0.0,
    }


def patent_digits(patent_number: str) -> str:
    normalized = normalize_us_patent_number(patent_number)
    match = re.match(r"US(\d+)", normalized)
    return match.group(1) if match else ""


def fetch_json(url: str, timeout: int = 12) -> dict[str, Any]:
    req = urllib.request.Request(url, headers={"User-Agent": "patent-invalidity-kb/1.0"})
    with urllib.request.urlopen(req, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8", errors="ignore"))


def lookup_patentsview(patent_number: str) -> dict[str, Any]:
    digits = patent_digits(patent_number)
    if not digits:
        return empty_result(patent_number)
    query = {
        "q": {"patent_number": digits},
        "f": [
            "patent_number",
            "patent_title",
            "patent_abstract",
            "patent_date",
            "assignee_organization",
            "inventor_first_name",
            "inventor_last_name",
            "cpc_subgroup_id",
        ],
        "o": {"per_page": 1},
    }
    url = "https://api.patentsview.org/patents/query?" + urllib.parse.urlencode({"q": json.dumps(query["q"]), "f": json.dumps(query["f"]), "o": json.dumps(query["o"])})
    data = fetch_json(url)
    patents = data.get("patents") or []
    if not patents:
        return empty_result(patent_number, "failed", "patentsview")
    patent = patents[0]
    assignees = [a.get("assignee_organization") for a in patent.get("assignees", []) if a.get("assignee_organization")]
    inventors = [
        " ".join([i.get("inventor_first_name", ""), i.get("inventor_last_name", "")]).strip()
        for i in patent.get("inventors", [])
    ]
    cpcs = [c.get("cpc_subgroup_id") for c in patent.get("cpcs", []) if c.get("cpc_subgroup_id")]
    return {
        "patent_number": normalize_us_patent_number(patent_number),
        "patent_title": patent.get("patent_title") or "",
        "abstract": patent.get("patent_abstract") or "",
        "independent_claims": [],
        "assignee": assignees[0] if assignees else "",
        "inventors": [v for v in inventors if v],
        "cpc": cpcs,
        "publication_date": "",
        "grant_date": patent.get("patent_date") or "",
        "source": "patentsview",
        "lookup_status": "partial",
        "status": "partial",
        "google_patents_url": google_patents_url(normalize_us_patent_number(patent_number)),
        "confidence": 0.85,
    }


def lookup_google_patents(patent_number: str) -> dict[str, Any]:
    normalized = normalize_us_patent_number(patent_number)
    url = google_patents_url(normalized)
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=4) as response:
        page = response.read().decode("utf-8", errors="ignore")
    title = ""
    title_match = re.search(r"<title>\s*(.*?)\s+-\s+Google Patents\s*</title>", page, re.I | re.S)
    if title_match:
        raw_title = re.sub(r"^US[0-9A-Z]+(?:\s*-\s*)?", "", html.unescape(title_match.group(1)))
        title = re.sub(r"\s+", " ", raw_title).strip(" -")
    abstract = ""
    abstract_match = re.search(r"<meta\s+name=[\"']DC\.description[\"']\s+content=[\"'](.*?)[\"']", page, re.I | re.S)
    if abstract_match:
        abstract = re.sub(r"\s+", " ", html.unescape(abstract_match.group(1))).strip()
    return {
        "patent_number": normalized,
        "patent_title": title,
        "abstract": abstract,
        "independent_claims": [],
        "assignee": "",
        "inventors": [],
        "cpc": [],
        "publication_date": "",
        "grant_date": "",
        "source": "google_patents",
        "lookup_status": "partial" if title or abstract else "failed",
        "status": "partial" if title or abstract else "failed",
        "google_patents_url": url,
        "confidence": 0.72 if title else 0.35,
    }


def lookup_us_patent(patent_number: str, cache: dict[str, Any] | None = None, allow_network: bool = True) -> dict[str, Any]:
    normalized = normalize_us_patent_number(patent_number)
    if not normalized:
        return empty_result("", "failed", "invalid_patent_number")
    cache = cache if cache is not None else load_cache()
    cached = cache.get(normalized)
    if isinstance(cached, dict) and (cached.get("patent_title") or cached.get("abstract")):
        result = {**empty_result(normalized, "success", cached.get("source", "local_cache")), **cached}
        result["patent_number"] = normalized
        result["google_patents_url"] = result.get("google_patents_url") or google_patents_url(normalized)
        result["lookup_status"] = result.get("lookup_status") or result.get("status") or "success"
        result["status"] = result["lookup_status"]
        return result
    if not allow_network:
        return empty_result(normalized, "failed", "local_cache_miss")
    result = empty_result(normalized, "failed", "official_lookup_not_configured")
    if os.environ.get("USE_PATENTSVIEW_LEGACY") == "1":
        try:
            result = lookup_patentsview(normalized)
        except Exception as exc:  # network/API failures should not break the database build
            result = empty_result(normalized, "failed", f"patentsview_error: {exc.__class__.__name__}")
    if result.get("lookup_status") == "failed":
        try:
            google_result = lookup_google_patents(normalized)
            if google_result.get("lookup_status") != "failed":
                result = google_result
        except Exception as exc:
            result["source"] = f"{result.get('source', 'lookup_failed')}+google_error:{exc.__class__.__name__}"
    cache[normalized] = result
    save_cache(cache)
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description="Lookup US patent bibliography and cache the result.")
    parser.add_argument("patent_number")
    parser.add_argument("--no-network", action="store_true")
    args = parser.parse_args()
    cache = load_cache()
    result = lookup_us_patent(args.patent_number, cache, allow_network=not args.no_network)
    save_cache(cache)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
