from __future__ import annotations

import csv
import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
INPUT_DIR = ROOT / "input_pdfs"
OUTPUT_JSON_DIR = ROOT / "output" / "json"
OUTPUT_TEXT_DIR = ROOT / "output" / "text"
PUBLIC_DIR = ROOT / "public"
PUBLIC_DATA_DIR = PUBLIC_DIR / "data"
PARSED_DIR = ROOT / "parsed"
REPORTS_DIR = ROOT / "reports"

CN_LEGAL_LABELS = {
    "inventive_step": "创造性",
    "novelty": "新颖性",
    "enablement": "充分公开 / 可实施性",
    "written_description": "说明书支持",
    "claim_construction": "权利要求解释",
    "priority": "优先权",
    "amendment": "修改超范围",
    "experimental_data": "实验数据",
    "post_filing_data": "申请日后数据",
    "common_general_knowledge": "公知常识",
    "motivation_to_combine": "结合动机",
    "reasonable_expectation_of_success": "合理成功预期",
    "unexpected_effect": "预料不到的技术效果",
    "dosage_regimen": "给药方案",
    "medical_use": "医药用途",
    "polymorph": "晶型",
    "selection_invention": "选择发明",
    "pending_review": "待确认",
}

US_LEGAL_LABELS = {
    "patent_eligibility_101": "35 U.S.C. § 101 / Patent Eligibility（专利适格性）",
    "anticipation_102": "35 U.S.C. § 102 / Anticipation（新颖性/预见）",
    "obviousness_103": "35 U.S.C. § 103 / Obviousness（显而易见性）",
    "written_description_112a": "35 U.S.C. § 112(a) / Written Description（书面描述支持）",
    "enablement_112a": "35 U.S.C. § 112(a) / Enablement（可实施性）",
    "indefiniteness_112b": "35 U.S.C. § 112(b) / Indefiniteness（不明确）",
    "claim_construction": "Claim Construction（权利要求解释）",
    "inherency": "Inherency（固有性）",
    "motivation_to_combine": "Motivation to Combine（结合动机）",
    "reasonable_expectation_of_success": "Reasonable Expectation of Success（合理成功预期）",
    "secondary_considerations": "Secondary Considerations / Objective Indicia（客观证据）",
    "priority_written_description_support": "Priority / Written Description Support（优先权/书面描述支持）",
    "obviousness_type_double_patenting": "Obviousness-Type Double Patenting（显而易见型重复授权）",
    "printed_publication_prior_art": "Printed Publication / Prior Art Qualification（现有技术资格）",
    "real_party_procedural": "Real Party in Interest / Procedural Issue（程序问题）",
    "institution_discretionary_denial": "Institution / Discretionary Denial（立案/酌定拒绝）",
    "other": "Other（其他）",
    "pending_review": "Pending Review（待确认）",
}

PATENT_TYPE_LABELS = {
    "compound": "化合物专利",
    "polymorph": "晶型/盐/溶剂合物",
    "formulation": "制剂/组合物",
    "composition": "制剂/组合物",
    "medical_use": "用途/适应症",
    "method": "制备方法/中间体",
    "process": "制备方法/中间体",
    "dosage_regimen": "给药方案/剂量",
    "antibody": "生物制品/抗体",
    "nucleic_acid": "生物制品/抗体",
    "cell_therapy": "生物制品/抗体",
    "other": "其他",
    "pending_review": "待确认",
}


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def rel(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def read_text_for_case(record: dict[str, Any]) -> str:
    candidates: list[Path] = []
    text_path = str(record.get("text_path") or "")
    if text_path:
        path = Path(text_path)
        candidates.append(path if path.is_absolute() else (PUBLIC_DIR / path if text_path.startswith("../") else ROOT / path))
    candidates.append(OUTPUT_TEXT_DIR / f"{record.get('id')}.txt")
    candidates.append(PUBLIC_DATA_DIR / "ocr_texts" / f"{record.get('id')}.txt")
    for path in candidates:
        try:
            resolved = path.resolve()
            if resolved.exists():
                return resolved.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
    return ""


def normalized_source_key(value: str) -> str:
    return Path(str(value or "")).name.lower()


def jurisdiction_from_path(path: Path) -> str:
    parts = {part.lower() for part in path.parts}
    name = path.name.lower()
    if "cn" in parts or "中国" in str(path):
        return "cn"
    if "us" in parts or "美国" in str(path) or re.search(r"\b(ipr|pgr|cbm)\d", name):
        return "us"
    return "unknown"


def jurisdiction_from_text(path: Path, text: str) -> str:
    haystack = f"{path.name}\n{text[:12000]}".lower()
    cn_hits = [
        "国家知识产权局",
        "专利复审委员会",
        "无效宣告请求审查决定",
        "第22条",
        "第26条",
        "第33条",
        "中华人民共和国",
    ]
    us_hits = [
        "united states patent and trademark office",
        "patent trial and appeal board",
        "ptab",
        "ipr",
        "pgr",
        "cbm",
        "inter partes review",
        "post grant review",
        "35 u.s.c.",
        "u.s. patent no.",
    ]
    cn_score = sum(1 for item in cn_hits if item.lower() in haystack)
    us_score = sum(1 for item in us_hits if item in haystack)
    if cn_score > us_score and cn_score:
        return "cn"
    if us_score > cn_score and us_score:
        return "us"
    return jurisdiction_from_path(path)


def language_for(jurisdiction: str, text: str) -> str:
    if jurisdiction == "cn":
        return "zh"
    if jurisdiction == "us":
        return "en"
    return "zh" if len(re.findall(r"[\u4e00-\u9fff]", text[:5000])) > 50 else "unknown"


def public_pdf_path(record: dict[str, Any], jurisdiction: str) -> str:
    existing = str(record.get("pdf_path") or "")
    return existing


def write_parsed_markdown(record: dict[str, Any], jurisdiction: str, text: str) -> str:
    if not text.strip() or jurisdiction not in {"cn", "us"}:
        return ""
    path = PARSED_DIR / jurisdiction / "markdown" / f"{record['id'].replace('case_', jurisdiction + '_')}.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        path.write_text(text, encoding="utf-8")
    return rel(path)


def patent_type_label(record: dict[str, Any]) -> tuple[str, float]:
    values = record.get("patent_type") or []
    value = values[0] if isinstance(values, list) and values else str(values or "")
    if not value:
        return "待确认", 0.2
    return PATENT_TYPE_LABELS.get(value, "待确认"), 0.75 if value not in {"other", "pending_review"} else 0.35


def cn_status(record: dict[str, Any]) -> str:
    conclusion = str(record.get("conclusion") or "")
    outcome = str(record.get("outcome") or "")
    if "全部无效" in conclusion or outcome == "invalidated":
        return "全部无效"
    if "部分无效" in conclusion or outcome == "partially_invalidated":
        return "部分无效"
    if "维持有效" in conclusion or outcome == "maintained":
        return "有效"
    return "待确认"


def us_outcome(record: dict[str, Any]) -> str:
    outcome = str(record.get("outcome") or "").lower()
    if outcome == "invalidated":
        return "claims unpatentable"
    if outcome == "maintained":
        return "claims not unpatentable"
    if outcome == "partially_invalidated":
        return "mixed"
    if outcome in {"dismissed", "settled"}:
        return outcome
    return "unknown"


def us_proceeding_type(record: dict[str, Any], text: str) -> str:
    haystack = f"{record.get('title','')}\n{record.get('proceeding_number','')}\n{text[:8000]}".lower()
    if "ipr" in haystack or "inter partes review" in haystack:
        return "IPR"
    if "pgr" in haystack or "post grant review" in haystack:
        return "PGR"
    if "cbm" in haystack or "covered business method" in haystack:
        return "CBM"
    if "federal circuit" in haystack:
        return "Federal Circuit"
    if "district court" in haystack:
        return "District Court"
    if "united states patent and trademark office" in haystack or "uspto" in haystack:
        return "USPTO"
    return "Unknown"


def us_legal_points(record: dict[str, Any], text: str) -> tuple[list[str], float]:
    focus = f"{record.get('title','')}\n{text[:40000]}".lower()
    rules = [
        ("patent_eligibility_101", [r"35\s+u\.s\.c\.\s*§?\s*101", "patent eligibility"]),
        ("anticipation_102", [r"35\s+u\.s\.c\.\s*§?\s*102", "anticipation", "anticipated"]),
        ("obviousness_103", [r"35\s+u\.s\.c\.\s*§?\s*103", "obviousness", "obvious"]),
        ("written_description_112a", ["written description", r"112\(a\).*written"]),
        ("enablement_112a", ["enablement", "not enabled", "fails to enable"]),
        ("indefiniteness_112b", ["indefiniteness", "112(b)", "indefinite"]),
        ("claim_construction", ["claim construction", "ordinary meaning", "plain meaning"]),
        ("inherency", ["inherency", "inherent"]),
        ("motivation_to_combine", ["motivation to combine"]),
        ("reasonable_expectation_of_success", ["reasonable expectation of success", "reasonable expectation"]),
        ("secondary_considerations", ["secondary considerations", "objective indicia", "unexpected results"]),
        ("priority_written_description_support", ["priority", "priority date", "written description support"]),
        ("obviousness_type_double_patenting", ["obviousness-type double patenting", "double patenting"]),
        ("printed_publication_prior_art", ["printed publication", "prior art qualification"]),
        ("real_party_procedural", ["real party in interest", "procedural"]),
        ("institution_discretionary_denial", ["institution denied", "discretionary denial", "325(d)", "314(a)"]),
    ]
    found: list[str] = []
    for tag, patterns in rules:
        for pattern in patterns:
            if re.search(pattern, focus, re.I):
                found.append(tag)
                break
    if not found:
        return ["pending_review"], 0.2
    return found[:4], 0.7


def clean_title(record: dict[str, Any], jurisdiction: str) -> tuple[str, float]:
    manual = str(record.get("manual_patent_title") or "").strip()
    if manual:
        return manual, 1.0
    patent_title = str(record.get("patent_title") or "").strip()
    if patent_title and "未识别" not in patent_title:
        return patent_title, 0.85
    title = str(record.get("title") or "").strip()
    if title and "未识别" not in title and "δʶ" not in title:
        return title, 0.6
    return ("未识别专利名称" if jurisdiction == "cn" else "Unidentified patent/proceeding title"), 0.1


def drug_name(record: dict[str, Any]) -> tuple[str, str]:
    manual = str(record.get("manual_drug_name") or "").strip()
    if manual:
        return manual, "high"
    value = str(record.get("drug_name") or "").strip()
    if value and "待人工" not in value:
        return value, str(record.get("drug_name_confidence") or "medium")
    return "待人工确认", "manual_required"


def base_summary(record: dict[str, Any], text: str) -> str:
    manual = str(record.get("manual_summary") or "").strip()
    if manual:
        return manual
    summary = str(record.get("summary") or "").strip()
    if summary:
        return summary
    return re.sub(r"\s+", " ", text).strip()[:420]


def build_cn_case(record: dict[str, Any], text: str, pdf_path: str, parsed_md: str) -> dict[str, Any]:
    title, title_conf = clean_title(record, "cn")
    ptype, ptype_conf = patent_type_label(record)
    points = record.get("legal_issues") or ["pending_review"]
    if not points:
        points = ["pending_review"]
    drug, drug_conf = drug_name(record)
    return {
        "case_id": record["id"].replace("case_", "cn_"),
        "source_case_id": record["id"],
        "jurisdiction": "cn",
        "language": "zh",
        "title": title,
        "decision_number": record.get("decision_number", ""),
        "patent_number": record.get("patent_number", ""),
        "patent_title": title if title != "未识别专利名称" else "",
        "pdf": pdf_path,
        "parsed_markdown": parsed_md,
        "patent_type": ptype,
        "legal_points": points,
        "drug_name": drug,
        "drug_name_confidence": drug_conf,
        "summary": base_summary(record, text),
        "status": cn_status(record),
        "confidence": {
            "title": title_conf,
            "patent_type": ptype_conf,
            "legal_points": 0.65 if points != ["pending_review"] else 0.2,
            "drug_name": {"high": 0.9, "medium": 0.6, "low": 0.35}.get(drug_conf, 0.2),
        },
        "review_required": bool(record.get("needs_manual_summary") or record.get("exclude_reason") or points == ["pending_review"]),
        "original_exclude_reason": record.get("exclude_reason", ""),
        "parse_status": parse_status(record, text),
    }


def build_us_case(record: dict[str, Any], text: str, pdf_path: str, parsed_md: str) -> dict[str, Any]:
    title, title_conf = clean_title(record, "us")
    ptype, ptype_conf = patent_type_label(record)
    points, points_conf = us_legal_points(record, text)
    drug, drug_conf = drug_name(record)
    return {
        "case_id": record["id"].replace("case_", "us_"),
        "source_case_id": record["id"],
        "jurisdiction": "us",
        "language": "en",
        "title": title,
        "proceeding_type": us_proceeding_type(record, text),
        "proceeding_number": record.get("proceeding_number", ""),
        "patent_number": record.get("patent_number", ""),
        "patent_title": record.get("patent_title", "") or title,
        "petitioner": record.get("petitioner", ""),
        "patent_owner": record.get("patentee_or_patent_owner", ""),
        "pdf": pdf_path,
        "parsed_markdown": parsed_md,
        "patent_type": ptype,
        "us_legal_points": points,
        "drug_name": drug,
        "drug_name_confidence": drug_conf,
        "orange_book_match": {
            "matched": False,
            "application_number": "",
            "product_name": "",
            "active_ingredient": "",
            "applicant": "",
            "patent_numbers": [],
            "match_method": "none",
            "confidence": 0,
        },
        "summary": base_summary(record, text),
        "outcome": us_outcome(record),
        "confidence": {
            "title": title_conf,
            "patent_type": ptype_conf,
            "us_legal_points": points_conf,
            "drug_name": {"high": 0.9, "medium": 0.6, "low": 0.35}.get(drug_conf, 0.2),
            "orange_book_match": 0,
        },
        "review_required": bool(record.get("needs_manual_summary") or record.get("exclude_reason") or points == ["pending_review"]),
        "original_exclude_reason": record.get("exclude_reason", ""),
        "parse_status": parse_status(record, text),
    }


def parse_status(record: dict[str, Any], text: str) -> str:
    if record.get("ocr_status") == "missing_pdf":
        return "failed"
    if record.get("is_duplicate"):
        return "duplicate"
    if text.strip():
        return "success"
    return "failed"


def database_status(record: dict[str, Any], text: str, jurisdiction: str) -> str:
    if record.get("is_duplicate"):
        return "excluded"
    if jurisdiction not in {"cn", "us"}:
        return "pending_review"
    if text.strip():
        return "included"
    return "pending_review"


def load_records() -> list[dict[str, Any]]:
    return [load_json(path) for path in sorted(OUTPUT_JSON_DIR.glob("case_*.json"))]


def input_pdfs() -> list[Path]:
    return sorted(INPUT_DIR.rglob("*.pdf"))


def record_maps(records: list[dict[str, Any]]) -> tuple[dict[str, dict[str, Any]], dict[str, dict[str, Any]]]:
    by_source_name: dict[str, dict[str, Any]] = {}
    by_pdf_name: dict[str, dict[str, Any]] = {}
    for record in records:
        source = normalized_source_key(str(record.get("source_file") or ""))
        if source:
            by_source_name.setdefault(source, record)
        pdf = normalized_source_key(str(record.get("pdf_path") or ""))
        if pdf:
            by_pdf_name.setdefault(pdf, record)
    return by_source_name, by_pdf_name


def build() -> dict[str, Any]:
    records = load_records()
    by_source_name, _ = record_maps(records)
    cn_cases: list[dict[str, Any]] = []
    us_cases: list[dict[str, Any]] = []
    manifest_files: list[dict[str, Any]] = []
    now = now_iso()

    seen_case_ids: set[str] = set()
    for pdf in input_pdfs():
        record = by_source_name.get(pdf.name.lower())
        text = read_text_for_case(record) if record else ""
        jurisdiction = jurisdiction_from_text(pdf, text)
        lang = language_for(jurisdiction, text)
        case_id = record.get("id", "") if record else ""
        pdf_rel = ""
        parsed_md = ""
        if record:
            pdf_rel = public_pdf_path(record, jurisdiction)
            parsed_md = write_parsed_markdown(record, jurisdiction, text)
            seen_case_ids.add(record["id"])
            if jurisdiction == "cn":
                cn_cases.append(build_cn_case(record, text, pdf_rel, parsed_md))
            elif jurisdiction == "us":
                us_cases.append(build_us_case(record, text, pdf_rel, parsed_md))

        manifest_files.append(
            {
                "file_name": pdf.name,
                "source_path": rel(pdf),
                "public_pdf_path": pdf_rel,
                "jurisdiction": jurisdiction,
                "language": lang,
                "parse_status": parse_status(record, text) if record else "failed",
                "mineru_status": record.get("mineru_status", "not_called") if record else "not_called",
                "database_status": database_status(record, text, jurisdiction) if record else "pending_review",
                "error_message": "" if record else "No generated case JSON matched this input PDF.",
                "case_id": case_id,
                "parsed_markdown_path": parsed_md,
                "parsed_json_path": rel(OUTPUT_JSON_DIR / f"{case_id}.json") if case_id else "",
                "file_hash": file_sha256(pdf),
                "original_exclude_reason": record.get("exclude_reason", "") if record else "not_processed",
                "processed_at": now,
            }
        )

    orphan_records: list[dict[str, Any]] = []
    # Keep generated cases whose original source file is unavailable out of the file manifest.
    # The manifest is a PDF processing checklist, so it must match input_pdfs one-for-one.
    for record in records:
        if record["id"] in seen_case_ids:
            continue
        text = read_text_for_case(record)
        jurisdiction = str(record.get("region") or "").lower() or "unknown"
        pdf_rel = public_pdf_path(record, jurisdiction) if jurisdiction in {"cn", "us"} else str(record.get("pdf_path") or "")
        parsed_md = write_parsed_markdown(record, jurisdiction, text)
        orphan_records.append(
            {
                "file_name": Path(str(record.get("source_file") or record.get("pdf_path") or record["id"])).name,
                "source_path": str(record.get("source_file") or ""),
                "public_pdf_path": pdf_rel,
                "jurisdiction": jurisdiction,
                "language": language_for(jurisdiction, text),
                "parse_status": parse_status(record, text),
                "mineru_status": record.get("mineru_status", "not_called"),
                "database_status": database_status(record, text, jurisdiction),
                "error_message": "Generated case JSON exists, but original input PDF was not found by source filename.",
                "case_id": record["id"],
                "parsed_markdown_path": parsed_md,
                "parsed_json_path": rel(OUTPUT_JSON_DIR / f"{record['id']}.json"),
                "file_hash": record.get("file_hash", ""),
                "original_exclude_reason": record.get("exclude_reason", ""),
                "processed_at": now,
            }
        )

    cn_cases.sort(key=lambda item: item["case_id"])
    us_cases.sort(key=lambda item: item["case_id"])
    totals = {
        "input_pdf_total": len(input_pdfs()),
        "manifest_file_total": len(manifest_files),
        "parse_success_total": sum(1 for item in manifest_files if item["parse_status"] == "success"),
        "parse_failed_total": sum(1 for item in manifest_files if item["parse_status"] == "failed"),
        "included_total": sum(1 for item in manifest_files if item["database_status"] == "included"),
        "cn_total": sum(1 for item in manifest_files if item["jurisdiction"] == "cn"),
        "us_total": sum(1 for item in manifest_files if item["jurisdiction"] == "us"),
        "unknown_total": sum(1 for item in manifest_files if item["jurisdiction"] == "unknown"),
        "duplicate_total": sum(1 for item in manifest_files if item["parse_status"] == "duplicate"),
        "mineru_success_total": sum(1 for item in manifest_files if item["mineru_status"] == "success"),
        "mineru_failed_total": sum(1 for item in manifest_files if item["mineru_status"] == "failed"),
        "mineru_not_called_total": sum(1 for item in manifest_files if item["mineru_status"] == "not_called"),
        "generated_at": now,
    }

    write_json(PUBLIC_DATA_DIR / "cn_cases.json", {"schema_version": 1, "jurisdiction": "cn", "tag_labels": {"patent_type": PATENT_TYPE_LABELS, "legal_points": CN_LEGAL_LABELS}, "total": len(cn_cases), "cases": cn_cases})
    write_json(PUBLIC_DATA_DIR / "us_cases.json", {"schema_version": 1, "jurisdiction": "us", "tag_labels": {"patent_type": PATENT_TYPE_LABELS, "us_legal_points": US_LEGAL_LABELS}, "total": len(us_cases), "cases": us_cases})
    write_json(PUBLIC_DATA_DIR / "all_cases_manifest.json", {"schema_version": 1, "totals": totals, "files": manifest_files, "orphan_generated_records": orphan_records})
    write_manual_review(manifest_files, cn_cases, us_cases)
    write_report(totals, manifest_files, cn_cases, us_cases, orphan_records)
    return totals


def write_manual_review(manifest_files: list[dict[str, Any]], cn_cases: list[dict[str, Any]], us_cases: list[dict[str, Any]]) -> None:
    case_by_id = {item["source_case_id"]: item for item in [*cn_cases, *us_cases]}
    rows = []
    for item in manifest_files:
        case = case_by_id.get(item.get("case_id", ""), {})
        if item["database_status"] == "included" and not case.get("review_required"):
            continue
        rows.append(
            {
                "file_name": item["file_name"],
                "case_id": item.get("case_id", ""),
                "jurisdiction": item["jurisdiction"],
                "parse_status": item["parse_status"],
                "mineru_status": item["mineru_status"],
                "database_status": item["database_status"],
                "current_title": case.get("title", ""),
                "current_patent_number": case.get("patent_number", ""),
                "current_outcome": case.get("status") or case.get("outcome", ""),
                "reason": item.get("error_message") or item.get("original_exclude_reason") or "review_required",
                "pdf_path": item.get("public_pdf_path", ""),
            }
        )
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    csv_path = ROOT / "output" / "manual_review_jurisdiction.csv"
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    with csv_path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()) if rows else ["file_name"])
        writer.writeheader()
        writer.writerows(rows)
    write_json(ROOT / "output" / "manual_review_jurisdiction.json", rows)


def write_report(
    totals: dict[str, Any],
    manifest_files: list[dict[str, Any]],
    cn_cases: list[dict[str, Any]],
    us_cases: list[dict[str, Any]],
    orphan_records: list[dict[str, Any]],
) -> None:
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    reasons: dict[str, int] = {}
    for item in manifest_files:
        if item["database_status"] == "included":
            continue
        reason = item.get("error_message") or item.get("original_exclude_reason") or item.get("parse_status") or "unknown"
        reasons[reason] = reasons.get(reason, 0) + 1
    lines = [
        "# 数据库构建报告",
        "",
        f"- input_pdfs 总 PDF 数：{totals['input_pdf_total']}",
        f"- manifest 记录数：{totals['manifest_file_total']}",
        f"- 成功解析数：{totals['parse_success_total']}",
        f"- 解析失败数：{totals['parse_failed_total']}",
        f"- 成功入库数：{totals['included_total']}",
        f"- 中国文件数：{totals['cn_total']}",
        f"- 美国文件数：{totals['us_total']}",
        f"- unknown 文件数：{totals['unknown_total']}",
        f"- 重复文件数：{totals['duplicate_total']}",
        f"- 中国案例库显示数：{len(cn_cases)}",
        f"- 美国案例库显示数：{len(us_cases)}",
        f"- MinerU 成功数：{totals['mineru_success_total']}",
        f"- MinerU 失败数：{totals['mineru_failed_total']}",
        f"- MinerU 未调用数：{totals['mineru_not_called_total']}",
        f"- 找不到原始 input PDF 的旧 JSON 记录：{len(orphan_records)}",
        "",
        "## 为什么旧网站只有 150 多个案例",
        "",
        "旧版 `public/data/cases.json` 只写入 `include_in_kb=true` 且非重复的主案例。当前 `output/json` 中共有 333 条生成记录，其中 177 条被旧规则排除，主要原因是 `needs_ocr_review` 或正文过短。新流程不再静默丢弃这些文件，而是在 `all_cases_manifest.json` 和本报告中逐项记录状态。",
        "",
        "## 未入库原因汇总",
        "",
    ]
    if reasons:
        lines.extend(f"- {reason}：{count}" for reason, count in sorted(reasons.items(), key=lambda item: (-item[1], item[0])))
    else:
        lines.append("- 暂无未入库文件。")
    lines.extend(
        [
            "",
            "## 下一步人工复核清单",
            "",
            "详见 `output/manual_review_jurisdiction.csv` 和 `output/manual_review_jurisdiction.json`。重点复核：标题置信度低、法律点为 pending_review、药物名称待人工确认、MinerU 未解析或解析失败的文件。",
        ]
    )
    (REPORTS_DIR / "database_build_report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    totals = build()
    print(json.dumps(totals, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
