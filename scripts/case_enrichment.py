from __future__ import annotations

import csv
import json
import re
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
OUTPUT_JSON_DIR = ROOT / "output" / "json"
OUTPUT_TEXT_DIR = ROOT / "output" / "text"
PUBLIC_DIR = ROOT / "public"
MANUAL_REVIEW_CSV = OUTPUT_JSON_DIR.parent / "manual_review.csv"
MANUAL_REVIEW_JSON = OUTPUT_JSON_DIR.parent / "manual_review.json"
CONCLUSION_REPORT_JSON = OUTPUT_JSON_DIR.parent / "conclusion_report.json"


CONCLUSION_MANUAL = "待人工确认"
CONCLUSION_FULL = "全部无效"
CONCLUSION_PARTIAL = "部分无效"
CONCLUSION_MAINTAINED = "维持有效"


def text_path_for_record(record: dict[str, Any]) -> Path | None:
    text_path = str(record.get("text_path") or "")
    if not text_path:
        case_id = record.get("id", "")
        return OUTPUT_TEXT_DIR / f"{case_id}.txt" if case_id else None
    path = Path(text_path)
    if path.is_absolute():
        return path
    if text_path.startswith("../"):
        return (PUBLIC_DIR / path).resolve()
    return (ROOT / path).resolve()


def read_case_text(record: dict[str, Any]) -> str:
    path = text_path_for_record(record)
    if not path or not path.exists():
        return ""
    return path.read_text(encoding="utf-8", errors="ignore")


def enrich_record_from_body(record: dict[str, Any], text: str) -> dict[str, Any]:
    text = text or ""
    record.setdefault("secondary_title", record.get("title", ""))
    record.setdefault("file_name", Path(record.get("source_file", "")).name)
    add_manual_fields(record)
    enrich_ocr_fields(record, text)
    enrich_patent_title(record, text)
    enrich_drug_name(record, text)
    enrich_conclusion(record, text)
    return record


def add_manual_fields(record: dict[str, Any]) -> None:
    record.setdefault("manual_patent_title", "")
    record.setdefault("manual_drug_name", "")
    record.setdefault("manual_summary", "")
    record.setdefault("manual_conclusion", "")
    record.setdefault("manual_notes", "")


def enrich_ocr_fields(record: dict[str, Any], text: str) -> None:
    record.setdefault("ocr_text", "")
    record.setdefault("ocr_text_path", "")
    record.setdefault("ocr_status", "")
    if record.get("needs_ocr"):
        if text.strip():
            record["ocr_status"] = record.get("ocr_status") or "not_required_text_extracted"
            record.setdefault("extracted_text_status", "text_extracted")
            record["needs_manual_summary"] = False
        else:
            record["ocr_status"] = record.get("ocr_status") or "unavailable"
            record.setdefault("extracted_text_status", "ocr_unavailable")
            record["needs_manual_summary"] = True
    else:
        record["ocr_status"] = record.get("ocr_status") or "not_required"
        record.setdefault("extracted_text_status", "text_extracted" if text.strip() else "empty")
        record.setdefault("needs_manual_summary", False)


def enrich_patent_title(record: dict[str, Any], text: str) -> None:
    manual = record.get("manual_patent_title", "").strip()
    if manual:
        record["patent_title"] = manual
        record["title"] = manual
        return

    extracted = extract_patent_title(text)
    if not extracted:
        extracted = title_from_filename(record.get("file_name") or Path(record.get("source_file", "")).stem)
    if not extracted:
        extracted = "未识别专利名称"
    record["patent_title"] = extracted
    record["title"] = extracted


def extract_patent_title(text: str) -> str:
    sample = re.sub(r"\s+", " ", text[:50000])
    patterns = [
        r"(?:专利名称|发明名称|名称)[:：]\s*([^，。；;\n]{3,120})",
        r"涉案专利(?:名称)?(?:为|是|名称为)[:：]?\s*([^，。；;\n]{3,120})",
        r"名称为[“\"]([^”\"]{3,120})[”\"]",
    ]
    for pattern in patterns:
        match = re.search(pattern, sample)
        if match:
            title = cleanup_title(match.group(1))
            if valid_title(title):
                return title
    return ""


def title_from_filename(name: str) -> str:
    stem = Path(name).stem
    stem = re.sub(r"case_\d+_[a-z]+", "", stem, flags=re.I)
    stem = re.sub(r"\b(?:IPR|PGR|CBM)\d{4}-\d{5}\b", "", stem, flags=re.I)
    stem = re.sub(r"[\d._\-（）()]+", " ", stem)
    stem = re.sub(r"\s+", " ", stem).strip(" -_")
    return stem if valid_title(stem) else ""


def cleanup_title(title: str) -> str:
    title = re.sub(r"\s+", " ", title).strip(" ：:，,。.;；")
    bad_suffixes = ["请求人", "专利权人", "本专利", "一案", "专利号"]
    for suffix in bad_suffixes:
        idx = title.find(suffix)
        if idx > 4:
            title = title[:idx].strip(" ：:，,。.;；")
    return title[:120]


def valid_title(title: str) -> bool:
    if not title or len(title) < 3:
        return False
    if re.fullmatch(r"[A-Za-z0-9_.\- ]+", title) and len(title) < 12:
        return False
    return True


def enrich_drug_name(record: dict[str, Any], text: str) -> None:
    manual = record.get("manual_drug_name", "").strip()
    if manual:
        record["drug_name"] = manual
        record["drug_name_confidence"] = "high"
        return

    drug = extract_drug_name(text)
    if drug:
        record["drug_name"] = drug
        record["drug_name_confidence"] = "medium"
    else:
        record["drug_name"] = "待人工确认"
        record["drug_name_confidence"] = "manual_required"


def extract_drug_name(text: str) -> str:
    sample = re.sub(r"\s+", " ", text[:40000])
    patterns = [
        r"(?:药物名称|药品名称|通用名|商品名)[:：]\s*([A-Za-z0-9\u4e00-\u9fff\-（）()]{2,60})",
        r"(?:涉及|关于)([A-Za-z0-9\u4e00-\u9fff\-（）()]{2,40})(?:药物|制剂|片|胶囊|注射液)",
        r"\b([A-Z][a-z]+(?:mab|nib|tinib|ciclib|zomib|parib|vir|stat|pril|sartan|olimus))\b",
    ]
    for pattern in patterns:
        match = re.search(pattern, sample, re.I)
        if match:
            return match.group(1).strip(" ：:，,。.;；")
    return ""


def enrich_conclusion(record: dict[str, Any], text: str) -> None:
    manual = record.get("manual_conclusion", "").strip()
    if manual:
        record["conclusion"] = manual
        record["conclusion_basis"] = "manual_conclusion"
        record["outcome"] = conclusion_to_outcome(manual)
        return
    conclusion, basis = detect_conclusion(text)
    record["conclusion"] = conclusion
    record["conclusion_basis"] = basis
    record["outcome"] = conclusion_to_outcome(conclusion)
    if conclusion == CONCLUSION_MANUAL:
        record["review_status"] = "needs_manual_review"


def detect_conclusion(text: str) -> tuple[str, str]:
    if not text.strip():
        return CONCLUSION_MANUAL, "未提取到可判断结论的正文。"

    windows = conclusion_windows(text)
    for window in windows:
        conclusion = classify_conclusion_window(window)
        if conclusion != CONCLUSION_MANUAL:
            return conclusion, compact_basis(window)

    tail = text[-1800:]
    conclusion = classify_conclusion_window(tail)
    if conclusion != CONCLUSION_MANUAL:
        return conclusion, compact_basis(tail)
    return CONCLUSION_MANUAL, compact_basis(tail or text[:800])


def conclusion_windows(text: str) -> list[str]:
    markers = [
        "决定如下",
        "审查决定",
        "结论",
        "决定主文",
        "判决如下",
        "ORDER",
        "CONCLUSION",
        "FINAL WRITTEN DECISION",
    ]
    windows: list[str] = []
    lower = text.lower()
    for marker in markers:
        search_text = lower if marker.isascii() else text
        marker_key = marker.lower() if marker.isascii() else marker
        positions = [m.start() for m in re.finditer(re.escape(marker_key), search_text)]
        for pos in positions[-3:]:
            start = max(0, pos - 250)
            end = min(len(text), pos + 1200)
            windows.append(text[start:end])
    if not windows:
        windows.append(text[-1800:])
    return windows


def classify_conclusion_window(window: str) -> str:
    normalized = re.sub(r"\s+", "", window)
    lower = window.lower()

    partial_patterns = [
        r"宣告[^。；;]{0,80}权利要求[^。；;]{0,80}无效[^。；;]{0,120}维持",
        r"维持[^。；;]{0,120}权利要求[^。；;]{0,80}有效",
        r"在[^。；;]{0,120}基础上维持有效",
        r"部分无效",
        r"宣告部分权利要求无效",
    ]
    if any(re.search(pattern, normalized) for pattern in partial_patterns):
        return CONCLUSION_PARTIAL

    full_patterns = [
        "宣告专利权全部无效",
        "宣告本专利权全部无效",
        "宣告涉案专利全部无效",
        "宣告本专利全部无效",
        "全部无效",
    ]
    if any(pattern in normalized for pattern in full_patterns):
        return CONCLUSION_FULL

    invalid_claim = re.search(r"宣告[^。；;]{0,120}(权利要求|专利权)[^。；;]{0,120}无效", normalized)
    maintained = re.search(r"维持[^。；;]{0,120}有效|理由不成立", normalized)
    if invalid_claim and maintained:
        return CONCLUSION_PARTIAL
    if maintained and not invalid_claim:
        return CONCLUSION_MAINTAINED

    if "not unpatentable" in lower:
        return CONCLUSION_MAINTAINED
    if "all challenged claims" in lower and "unpatentable" in lower:
        return CONCLUSION_FULL
    if "some" in lower and "unpatentable" in lower:
        return CONCLUSION_PARTIAL
    return CONCLUSION_MANUAL


def compact_basis(text: str) -> str:
    basis = re.sub(r"\s+", " ", text).strip()
    return basis[:500] + ("..." if len(basis) > 500 else "")


def conclusion_to_outcome(conclusion: str) -> str:
    return {
        CONCLUSION_FULL: "invalidated",
        CONCLUSION_PARTIAL: "partially_invalidated",
        CONCLUSION_MAINTAINED: "maintained",
        CONCLUSION_MANUAL: "manual_review",
    }.get(conclusion, "manual_review")


def needs_manual_review(record: dict[str, Any]) -> bool:
    return (
        record.get("conclusion") == CONCLUSION_MANUAL
        or record.get("drug_name_confidence") == "manual_required"
        or record.get("needs_manual_summary")
        or record.get("ocr_status") in {"failed", "unavailable"}
        or record.get("patent_title") == "未识别专利名称"
        or record.get("review_status") == "needs_manual_review"
    )


def write_manual_review_files(cases: list[dict[str, Any]]) -> None:
    rows = []
    for record in cases:
        if not record.get("include_in_kb", True) and not record.get("needs_ocr"):
            continue
        if not needs_manual_review(record):
            continue
        rows.append(
            {
                "case_id": record.get("id", ""),
                "pdf_file_name": record.get("file_name") or Path(record.get("source_file", "")).name,
                "current_patent_title": record.get("patent_title", ""),
                "current_conclusion": record.get("conclusion", ""),
                "is_scanned": bool(record.get("needs_ocr")),
                "ocr_failed_or_unavailable": record.get("ocr_status") in {"failed", "unavailable"},
                "fields_to_fill": fields_to_fill(record),
                "pdf_path": record.get("pdf_path", ""),
                "source_file": record.get("source_file", ""),
            }
        )
    MANUAL_REVIEW_JSON.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")
    with MANUAL_REVIEW_CSV.open("w", encoding="utf-8-sig", newline="") as f:
        fieldnames = [
            "case_id",
            "pdf_file_name",
            "current_patent_title",
            "current_conclusion",
            "is_scanned",
            "ocr_failed_or_unavailable",
            "fields_to_fill",
            "pdf_path",
            "source_file",
        ]
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    write_conclusion_report(cases)


def write_conclusion_report(cases: list[dict[str, Any]]) -> None:
    buckets: dict[str, list[dict[str, str]]] = {
        CONCLUSION_MAINTAINED: [],
        CONCLUSION_PARTIAL: [],
        CONCLUSION_FULL: [],
        CONCLUSION_MANUAL: [],
    }
    for record in cases:
        if not record.get("include_in_kb", True) or record.get("is_duplicate"):
            continue
        conclusion = record.get("conclusion") or CONCLUSION_MANUAL
        buckets.setdefault(conclusion, []).append(
            {
                "case_id": record.get("id", ""),
                "patent_title": record.get("patent_title", ""),
                "file_name": record.get("file_name") or Path(record.get("source_file", "")).name,
                "pdf_path": record.get("pdf_path", ""),
                "conclusion_basis": record.get("conclusion_basis", ""),
            }
        )
    CONCLUSION_REPORT_JSON.write_text(json.dumps(buckets, ensure_ascii=False, indent=2), encoding="utf-8")


def fields_to_fill(record: dict[str, Any]) -> str:
    fields = []
    if record.get("patent_title") == "未识别专利名称":
        fields.append("manual_patent_title")
    if record.get("drug_name_confidence") == "manual_required":
        fields.append("manual_drug_name")
    if record.get("conclusion") == CONCLUSION_MANUAL:
        fields.append("manual_conclusion")
    if record.get("needs_manual_summary"):
        fields.append("manual_summary")
    fields.append("manual_notes")
    return ";".join(dict.fromkeys(fields))
