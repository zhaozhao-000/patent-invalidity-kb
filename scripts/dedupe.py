from __future__ import annotations

import hashlib
import re
from pathlib import Path
from typing import Any


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def normalize_text_for_hash(text: str) -> str:
    text = text.lower()
    text = re.sub(r"---\s*page\s*\d+\s*---", " ", text, flags=re.I)
    text = re.sub(r"第\s*\d+\s*页\s*(共\s*\d+\s*页)?", " ", text)
    text = re.sub(r"\bpage\s+\d+\s+(of\s+\d+)?\b", " ", text, flags=re.I)
    text = re.sub(r"^\s*\d+\s*$", " ", text, flags=re.M)
    text = re.sub(r"下载时间[:：].*$", " ", text, flags=re.M)
    text = re.sub(r"打印时间[:：].*$", " ", text, flags=re.M)
    text = re.sub(r"downloaded\s+(from|on).*$", " ", text, flags=re.I | re.M)
    text = re.sub(r"watermark.*$", " ", text, flags=re.I | re.M)
    text = re.sub(r"\b\d{4}[-/]\d{1,2}[-/]\d{1,2}\s+\d{1,2}:\d{2}(:\d{2})?\b", " ", text)
    text = re.sub(r"[^\u4e00-\u9fff\w\s.,;:!?()（）\[\]【】\-/#号第]", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def content_hash(text: str) -> str:
    normalized = normalize_text_for_hash(text)
    if not normalized:
        return ""
    return sha256_text(normalized)


def load_json(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    import json

    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def write_json(path: Path, data: dict[str, Any]) -> None:
    import json

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def ensure_dedupe_fields(record: dict[str, Any]) -> dict[str, Any]:
    case_id = record.get("id", "")
    record.setdefault("file_hash", "")
    record.setdefault("content_hash", "")
    record.setdefault("canonical_case_id", case_id)
    record.setdefault("is_duplicate", False)
    record.setdefault("duplicate_of", "")
    record.setdefault("duplicate_reason", "")
    record.setdefault("duplicate_files", [])
    record.setdefault("suspected_duplicates", [])
    record.setdefault("dedupe_identifiers", {})
    return record


def append_unique(values: list[str], new_value: str) -> list[str]:
    if new_value and new_value not in values:
        values.append(new_value)
    return values


def extract_identifiers(text: str, title: str, region: str) -> dict[str, list[str]]:
    sample = f"{title}\n{text[:30000]}"
    compact = re.sub(r"\s+", " ", sample)
    identifiers: dict[str, list[str]] = {
        "case_numbers": [],
        "patent_numbers": [],
        "parties": [],
        "titles": [],
    }

    if region == "CN":
        cn_decisions = re.findall(r"(?:第)?\d{4,7}\s*号|国知药裁\s*\d+\s*号|\(\d{4}\)\s*国知药裁\s*\d+\s*号", compact)
        cn_patents = re.findall(r"(?:cn\s*)?\d{8,12}\.?\d?[a-z]?", compact, flags=re.I)
        identifiers["case_numbers"] = clean_identifier_list(cn_decisions)
        identifiers["patent_numbers"] = clean_identifier_list(cn_patents)
        identifiers["parties"] = clean_identifier_list(
            re.findall(r"(?:请求人|专利权人)[:：]\s*([^，。；;\n]{2,40})", compact)
        )
        identifiers["titles"] = clean_identifier_list(
            re.findall(r"(?:发明名称|名称)[:：]\s*([^，。；;\n]{4,80})", compact)
        )
    else:
        us_cases = re.findall(r"\b(?:ipr|pgr|cbm)\d{4}-\d{5}\b", compact, flags=re.I)
        us_patents = re.findall(r"\b(?:u\.s\.\s*)?patent\s*(?:no\.)?\s*(\d{1,2},?\d{3},?\d{3})\b", compact, flags=re.I)
        identifiers["case_numbers"] = clean_identifier_list(us_cases)
        identifiers["patent_numbers"] = clean_identifier_list(us_patents)
        identifiers["parties"] = clean_identifier_list(
            re.findall(r"(?:petitioner|patent owner)[:\s]+([A-Z][A-Za-z0-9&.,\- ]{2,60})", sample)
        )
        identifiers["titles"] = clean_identifier_list([title])

    if not identifiers["titles"] and title:
        identifiers["titles"] = clean_identifier_list([title])
    return identifiers


def clean_identifier_list(values: list[str]) -> list[str]:
    cleaned: list[str] = []
    for value in values:
        normalized = re.sub(r"\s+", " ", str(value)).strip().lower()
        normalized = normalized.strip(" .,:;，。；：")
        if len(normalized) >= 3 and normalized not in cleaned:
            cleaned.append(normalized)
    return cleaned[:8]


def suspected_duplicate_ids(
    candidate: dict[str, Any],
    canonical_records: list[dict[str, Any]],
) -> list[str]:
    candidate_ids = candidate.get("dedupe_identifiers") or {}
    suspected: list[str] = []
    for record in canonical_records:
        if record.get("id") == candidate.get("id") or record.get("is_duplicate"):
            continue
        record_ids = record.get("dedupe_identifiers") or {}
        case_overlap = overlap(candidate_ids.get("case_numbers", []), record_ids.get("case_numbers", []))
        patent_overlap = overlap(candidate_ids.get("patent_numbers", []), record_ids.get("patent_numbers", []))
        if case_overlap or patent_overlap:
            suspected.append(record["id"])
            continue
        total_overlap = 0
        for key in ("parties", "titles"):
            total_overlap += len(overlap(candidate_ids.get(key, []), record_ids.get(key, [])))
        if total_overlap >= 2:
            suspected.append(record["id"])
    return suspected[:10]


def overlap(left: list[str], right: list[str]) -> set[str]:
    return set(left or []) & set(right or [])


def record_duplicate_file(master: dict[str, Any], duplicate_path: str, reason: str) -> None:
    ensure_dedupe_fields(master)
    master["canonical_case_id"] = master.get("canonical_case_id") or master.get("id", "")
    master["is_duplicate"] = False
    append_unique(master["duplicate_files"], duplicate_path)
    master.setdefault("duplicate_reason", "")
    if reason and reason not in master.get("duplicate_reason", ""):
        master["duplicate_reason"] = reason if not master["duplicate_reason"] else f"{master['duplicate_reason']},{reason}"
