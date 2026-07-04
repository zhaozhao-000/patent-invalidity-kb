from __future__ import annotations

import html
import json
from pathlib import Path
from typing import Any

from case_enrichment import enrich_record_from_body, read_case_text, write_manual_review_files
from classify_case import TAG_LABELS, classify_case_tags, classify_doc_type, extract_case_metadata, should_include_document
from dedupe import append_unique, content_hash, ensure_dedupe_fields, extract_identifiers, write_json
from manifest import load_manifest, register_content_hash, save_manifest, status_for_record, upsert_case, upsert_file


ROOT = Path(__file__).resolve().parents[1]
OUTPUT_JSON_DIR = ROOT / "output" / "json"
PUBLIC_DIR = ROOT / "public"
CASES_INDEX_PATH = PUBLIC_DIR / "cases_index.json"
CASES_JSON_PATH = PUBLIC_DIR / "data" / "cases.json"
DUPLICATES_REPORT_JSON_PATH = PUBLIC_DIR / "duplicates_report.json"
DUPLICATES_REPORT_HTML_PATH = PUBLIC_DIR / "duplicates_report.html"
EXCLUDED_REPORT_JSON_PATH = PUBLIC_DIR / "excluded_files_report.json"
EXCLUDED_REPORT_HTML_PATH = PUBLIC_DIR / "excluded_files_report.html"
RELATED_REPORT_JSON_PATH = PUBLIC_DIR / "related_cases_report.json"
LOCAL_ONLY_CASE_FIELDS = {
    "source_file",
    "text_path",
    "external_ocr_source",
    "file_hash",
    "content_hash",
    "dedupe_identifiers",
}


def load_case_jsons(json_dir: Path = OUTPUT_JSON_DIR) -> list[dict[str, Any]]:
    cases: list[dict[str, Any]] = []
    for path in sorted(json_dir.glob("case_*.json")):
        with path.open("r", encoding="utf-8") as f:
            raw_record = json.load(f)
        had_doc_type = "doc_type" in raw_record
        record = ensure_document_fields(ensure_dedupe_fields(raw_record))
        cases.append(enrich_record_from_text(record, refresh_doc_type=not had_doc_type))
        write_json(path, record)
    return cases


def ensure_document_fields(record: dict[str, Any]) -> dict[str, Any]:
    record.setdefault("doc_type", record.get("case_type", "invalidity_decision"))
    record.setdefault("include_in_kb", not record.get("is_duplicate", False))
    record.setdefault("exclude_reason", "duplicate" if record.get("is_duplicate") else "")
    for key in [
        "patent_number",
        "patent_title",
        "decision_number",
        "proceeding_number",
        "court_case_number",
        "court_name",
        "judgment_date",
        "litigation_stage",
        "case_number",
        "petitioner",
        "patentee_or_patent_owner",
    ]:
        record.setdefault(key, "")
    record.setdefault("related_patent_numbers", [record["patent_number"]] if record.get("patent_number") else [])
    record.setdefault(
        "related_decision_numbers",
        [value for value in [record.get("decision_number"), record.get("proceeding_number")] if value],
    )
    record.setdefault("related_case_ids", [])
    record.setdefault("suspected_related_cases", [])
    return record


def enrich_record_from_text(record: dict[str, Any], refresh_doc_type: bool = False) -> dict[str, Any]:
    text = read_case_text(record)
    if text:
        record = enrich_record_from_body(record, text)
        refresh_auto_classification(record, text)
    if record.get("content_hash") and record.get("dedupe_identifiers") and not refresh_doc_type:
        return record
    text_path = resolve_text_path(record.get("text_path", ""))
    if not text_path or not text_path.exists():
        record = enrich_record_from_body(record, "")
        return record
    if not text:
        text = text_path.read_text(encoding="utf-8", errors="ignore")
    if not record.get("content_hash"):
        record["content_hash"] = content_hash(text)
    if not record.get("dedupe_identifiers"):
        record["dedupe_identifiers"] = extract_identifiers(
            text,
            record.get("title", ""),
            record.get("region", ""),
        )
    refresh_auto_classification(record, text)
    if refresh_doc_type:
        metadata = {
            "title": record.get("title", ""),
            "region": record.get("region", ""),
            "needs_ocr": record.get("needs_ocr", False),
        }
        doc_type = classify_doc_type(text, metadata)
        include_in_kb, exclude_reason = should_include_document(text, {**metadata, "doc_type": doc_type})
        record["doc_type"] = doc_type
        record["include_in_kb"] = include_in_kb
        record["exclude_reason"] = exclude_reason
        record["case_type"] = doc_type
        record.update(extract_case_metadata(text, record.get("title", ""), record.get("region", ""), doc_type))
        if record.get("is_duplicate"):
            record["include_in_kb"] = False
            record["exclude_reason"] = record.get("duplicate_reason") or "duplicate"
    record = enrich_record_from_body(record, text)
    return record


def refresh_auto_classification(record: dict[str, Any], text: str) -> None:
    if record.get("review_status") == "manually_reviewed":
        record.pop("technology_area", None)
        return
    tags = classify_case_tags(text, record.get("title", ""), record.get("region", ""))
    record["patent_type"] = tags["patent_type"]
    record["patent_type_basis"] = tags["patent_type_basis"]
    record.pop("technology_area", None)
    record["legal_issues"] = tags["legal_issues"]
    record["legal_issue_basis"] = tags["legal_issue_basis"]
    record["evidence_types"] = tags["evidence_types"]


def resolve_text_path(text_path: str) -> Path | None:
    if not text_path:
        return None
    path = Path(text_path)
    if path.is_absolute():
        return path
    if text_path.startswith("../"):
        return (PUBLIC_DIR / path).resolve()
    return (ROOT / path).resolve()


def reconcile_auto_duplicates(cases: list[dict[str, Any]]) -> None:
    reconcile_by_hash(cases, "file_hash", "same_file_hash")
    reconcile_by_hash(cases, "content_hash", "same_content_hash")


def reconcile_by_hash(cases: list[dict[str, Any]], field: str, reason: str) -> None:
    groups: dict[str, list[dict[str, Any]]] = {}
    for item in cases:
        value = item.get(field)
        if value:
            groups.setdefault(value, []).append(item)

    for group in groups.values():
        if len(group) < 2:
            continue
        group.sort(key=lambda item: item.get("id", ""))
        master = next((item for item in group if not item.get("is_duplicate")), group[0])
        master["is_duplicate"] = False
        master["duplicate_of"] = ""
        master["canonical_case_id"] = master.get("id", "")
        master.setdefault("duplicate_files", [])

        for item in group:
            if item.get("id") == master.get("id"):
                continue
            if item.get("duplicate_reason") == "manual_confirmed":
                continue
            item["is_duplicate"] = True
            item["duplicate_of"] = master.get("id", "")
            item["canonical_case_id"] = master.get("id", "")
            item["duplicate_reason"] = reason
            item["include_in_kb"] = False
            item["exclude_reason"] = reason
            append_unique(master["duplicate_files"], item.get("source_file", "") or item.get("pdf_path", ""))


def build_related_links(cases: list[dict[str, Any]]) -> dict[str, Any]:
    included = [item for item in cases if item.get("include_in_kb") and not item.get("is_duplicate")]
    by_id = {item["id"]: item for item in included}
    auto_links: list[dict[str, str]] = []
    suspected_links: list[dict[str, str]] = []

    for item in included:
        item["related_case_ids"] = []
        item["suspected_related_cases"] = []

    for index, left in enumerate(included):
        for right in included[index + 1 :]:
            reason = relation_reason(left, right)
            if reason:
                append_unique(left["related_case_ids"], right["id"])
                append_unique(right["related_case_ids"], left["id"])
                auto_links.append({"case_id": left["id"], "related_case_id": right["id"], "reason": reason})
                continue
            suspected_reason = suspected_relation_reason(left, right)
            if suspected_reason:
                append_unique(left["suspected_related_cases"], right["id"])
                append_unique(right["suspected_related_cases"], left["id"])
                suspected_links.append(
                    {"case_id": left["id"], "suspected_case_id": right["id"], "reason": suspected_reason}
                )

    for item in by_id.values():
        write_json(OUTPUT_JSON_DIR / f"{item['id']}.json", item)

    return {
        "schema_version": 1,
        "auto_related": auto_links,
        "suspected_related": suspected_links,
        "totals": {"auto_related": len(auto_links), "suspected_related": len(suspected_links)},
    }


def relation_reason(left: dict[str, Any], right: dict[str, Any]) -> str:
    left_patents = set(clean_values([left.get("patent_number", ""), *left.get("related_patent_numbers", [])]))
    right_patents = set(clean_values([right.get("patent_number", ""), *right.get("related_patent_numbers", [])]))
    left_decisions = set(clean_values([left.get("decision_number", ""), left.get("proceeding_number", ""), *left.get("related_decision_numbers", [])]))
    right_decisions = set(clean_values([right.get("decision_number", ""), right.get("proceeding_number", ""), *right.get("related_decision_numbers", [])]))
    if left_decisions & right_decisions:
        return "same_decision_or_proceeding_number"
    if left_patents & right_patents:
        left_party = clean_value(left.get("petitioner", "")) or clean_value(left.get("patentee_or_patent_owner", ""))
        right_party = clean_value(right.get("petitioner", "")) or clean_value(right.get("patentee_or_patent_owner", ""))
        if left_party and right_party and left_party == right_party:
            return "same_patent_and_party"
        if left.get("doc_type") != right.get("doc_type"):
            return "same_patent_cross_document_type"
        return "same_patent_number"
    return ""


def suspected_relation_reason(left: dict[str, Any], right: dict[str, Any]) -> str:
    if not left.get("title") or not right.get("title"):
        return ""
    left_title = clean_value(left["title"])
    right_title = clean_value(right["title"])
    if len(left_title) >= 10 and (left_title in right_title or right_title in left_title):
        return "similar_title_only"
    return ""


def clean_values(values: list[str]) -> list[str]:
    return [cleaned for value in values if (cleaned := clean_value(value))]


def clean_value(value: str) -> str:
    return "".join(str(value or "").lower().replace(",", "").split())


def sync_manifest(cases: list[dict[str, Any]], manifest: dict[str, Any]) -> None:
    for item in cases:
        upsert_case(manifest, item)
        if item.get("content_hash") and item.get("include_in_kb") and not item.get("is_duplicate"):
            register_content_hash(manifest, item["content_hash"], item["id"])
        if item.get("file_hash"):
            source = item.get("source_file") or item.get("pdf_path") or item["id"]
            entry = upsert_file(
                manifest,
                file_path=Path(source),
                file_hash=item["file_hash"],
                case_id=item["id"],
                content_hash=item.get("content_hash", ""),
                status=status_for_record(item),
                duplicate_of=item.get("duplicate_of", ""),
                duplicate_reason=item.get("duplicate_reason", ""),
            )
            entry["file_path"] = source
            entry["file_name"] = Path(source).name
            entry["doc_type"] = item.get("doc_type", "")
            entry["include_in_kb"] = item.get("include_in_kb", True)
            entry["exclude_reason"] = item.get("exclude_reason", "")


def build_duplicate_report(cases: list[dict[str, Any]], manifest: dict[str, Any]) -> dict[str, Any]:
    duplicate_cases = [
        {
            "case_id": item.get("id", ""),
            "title": item.get("title", ""),
            "duplicate_of": item.get("duplicate_of", ""),
            "duplicate_reason": item.get("duplicate_reason", ""),
            "source_file": public_file_label(item.get("source_file", "")),
            "pdf_path": item.get("pdf_path", ""),
        }
        for item in cases
        if item.get("is_duplicate")
    ]
    same_file_duplicates = [
        {
            "file_name": entry.get("file_name", ""),
            "file_path": public_file_label(entry.get("file_path", "")),
            "duplicate_of": entry.get("duplicate_of", ""),
            "duplicate_reason": entry.get("duplicate_reason", ""),
            "file_hash": entry.get("file_hash", ""),
            "file_paths": [public_file_label(value) for value in entry.get("file_paths", [])],
        }
        for entry in manifest.get("files", {}).values()
        if entry.get("duplicate_reason") == "same_file_hash" or len(entry.get("file_paths", [])) > 1
    ]
    return {
        "schema_version": 1,
        "same_file_duplicates": same_file_duplicates,
        "same_content_duplicates": duplicate_cases,
        "canonical_cases_with_duplicates": [
            {
                "case_id": item.get("id", ""),
                "title": item.get("title", ""),
                "duplicate_files_count": len(item.get("duplicate_files", [])),
                "duplicate_files": [public_file_label(value) for value in item.get("duplicate_files", [])],
            }
            for item in cases
            if not item.get("is_duplicate") and item.get("duplicate_files")
        ],
        "totals": {
            "same_file_duplicates": len(same_file_duplicates),
            "same_content_duplicates": len(duplicate_cases),
            "canonical_cases_with_duplicates": len([item for item in cases if not item.get("is_duplicate") and item.get("duplicate_files")]),
        },
    }


def build_excluded_report(cases: list[dict[str, Any]]) -> dict[str, Any]:
    records = []
    for item in cases:
        if item.get("include_in_kb") and not item.get("is_duplicate"):
            continue
        records.append(
            {
                "case_id": item.get("id", ""),
                "file_name": public_file_label(item.get("source_file", "") or item.get("pdf_path", "")),
                "file_path": item.get("pdf_path", ""),
                "doc_type": item.get("doc_type", ""),
                "exclude_reason": item.get("exclude_reason") or item.get("duplicate_reason") or "excluded",
                "text_length": text_length_for_case(item),
                "needs_ocr": item.get("needs_ocr", False),
                "suggestion": exclusion_suggestion(item),
            }
        )
    return {"schema_version": 1, "total": len(records), "excluded_files": records}


def public_file_label(value: str) -> str:
    value = str(value or "")
    if not value:
        return ""
    if value.startswith("pdfs/") or value.startswith("data/"):
        return value
    return Path(value).name


def sanitize_public_case(item: dict[str, Any]) -> dict[str, Any]:
    public_item = {key: value for key, value in item.items() if key not in LOCAL_ONLY_CASE_FIELDS}
    public_item["pdf_path"] = item.get("pdf_path", "")
    if "duplicate_files" in public_item:
        public_item["duplicate_files"] = [public_file_label(value) for value in public_item.get("duplicate_files", [])]
    return public_item


def text_length_for_case(item: dict[str, Any]) -> int:
    text_path = resolve_text_path(item.get("text_path", ""))
    if text_path and text_path.exists():
        return len(text_path.read_text(encoding="utf-8", errors="ignore"))
    return 0


def exclusion_suggestion(item: dict[str, Any]) -> str:
    reason = item.get("exclude_reason") or item.get("duplicate_reason")
    if reason in {"link_only", "too_short_or_no_substantive_content"}:
        return "可能是链接页、通知页或正文过短文件，不建议入库。"
    if reason == "needs_ocr_review":
        return "扫描件或图片型 PDF，需要 OCR 后再判断。"
    if "duplicate" in str(reason):
        return "疑似重复文件，已合并或指向主案例。"
    return "无法自动判断价值，建议人工检查。"


def write_report_html(path: Path, title: str, rows_data: list[dict[str, Any]], columns: list[str]) -> None:
    def rows() -> str:
        if not rows_data:
            return f'<tr><td colspan="{len(columns)}">暂无记录</td></tr>'
        return "\n".join(
            "<tr>" + "".join(f"<td>{html.escape(str(item.get(column, '')))}</td>" for column in columns) + "</tr>"
            for item in rows_data
        )

    header = "".join(f"<th>{html.escape(column)}</th>" for column in columns)
    page = f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{html.escape(title)}</title>
  <link rel="stylesheet" href="style.css">
</head>
<body>
  <header class="topbar">
    <div><h1>{html.escape(title)}</h1><p>由入库脚本自动生成，供管理员复核。</p></div>
    <div class="top-actions"><a class="button-link" href="index.html">返回知识库</a></div>
  </header>
  <main class="report-page">
    <section class="report-section">
      <table><thead><tr>{header}</tr></thead><tbody>{rows()}</tbody></table>
    </section>
  </main>
</body>
</html>
"""
    path.write_text(page, encoding="utf-8")


def build_index() -> dict[str, Any]:
    manifest = load_manifest()
    cases = load_case_jsons()
    for item in cases:
        item.pop("technology_area", None)
    reconcile_auto_duplicates(cases)
    related_report = build_related_links(cases)
    for item in cases:
        item.pop("technology_area", None)
        write_json(OUTPUT_JSON_DIR / f"{item['id']}.json", item)
    sync_manifest(cases, manifest)
    save_manifest(manifest)

    main_cases = [item for item in cases if item.get("include_in_kb") and not item.get("is_duplicate")]
    write_manual_review_files(main_cases)
    main_cases.sort(key=lambda item: item.get("updated_at", ""), reverse=True)
    duplicate_report = build_duplicate_report(cases, manifest)
    excluded_report = build_excluded_report(cases)
    tag_labels = {key: value for key, value in TAG_LABELS.items() if key != "technology_area"}
    public_cases = [sanitize_public_case(item) for item in main_cases]
    return {
        "schema_version": 3,
        "tag_labels": tag_labels,
        "total": len(main_cases),
        "excluded_total": excluded_report["total"],
        "duplicates_total": duplicate_report["totals"]["same_file_duplicates"] + duplicate_report["totals"]["same_content_duplicates"],
        "related_total": related_report["totals"]["auto_related"],
        "suspected_related_total": related_report["totals"]["suspected_related"],
        "cases": public_cases,
        "_duplicates_report": duplicate_report,
        "_excluded_report": excluded_report,
        "_related_report": related_report,
    }


def write_index() -> Path:
    PUBLIC_DIR.mkdir(parents=True, exist_ok=True)
    index = build_index()
    duplicate_report = index.pop("_duplicates_report")
    excluded_report = index.pop("_excluded_report")
    related_report = index.pop("_related_report")

    CASES_INDEX_PATH.write_text(json.dumps(index, ensure_ascii=False, indent=2), encoding="utf-8")
    CASES_JSON_PATH.parent.mkdir(parents=True, exist_ok=True)
    CASES_JSON_PATH.write_text(json.dumps(index, ensure_ascii=False, indent=2), encoding="utf-8")
    DUPLICATES_REPORT_JSON_PATH.write_text(json.dumps(duplicate_report, ensure_ascii=False, indent=2), encoding="utf-8")
    EXCLUDED_REPORT_JSON_PATH.write_text(json.dumps(excluded_report, ensure_ascii=False, indent=2), encoding="utf-8")
    RELATED_REPORT_JSON_PATH.write_text(json.dumps(related_report, ensure_ascii=False, indent=2), encoding="utf-8")

    write_report_html(
        DUPLICATES_REPORT_HTML_PATH,
        "重复文件报告",
        duplicate_report["same_file_duplicates"] + duplicate_report["same_content_duplicates"],
        ["file_name", "file_path", "case_id", "duplicate_of", "duplicate_reason", "source_file", "file_paths"],
    )
    write_report_html(
        EXCLUDED_REPORT_HTML_PATH,
        "排除文件报告",
        excluded_report["excluded_files"],
        ["case_id", "file_name", "file_path", "doc_type", "exclude_reason", "text_length", "needs_ocr", "suggestion"],
    )
    return CASES_INDEX_PATH


if __name__ == "__main__":
    path = write_index()
    print(f"Wrote {path}")
    print(f"Wrote {DUPLICATES_REPORT_JSON_PATH}")
    print(f"Wrote {EXCLUDED_REPORT_JSON_PATH}")
    print(f"Wrote {RELATED_REPORT_JSON_PATH}")
