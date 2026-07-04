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
MANUAL_OVERRIDES_DIR = ROOT / "data" / "manual_overrides"
US_PATENT_CACHE_PATH = ROOT / "data" / "external" / "us_patents_cache.json"

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

OLD_OCR_PROMPTS = [
    "该 PDF 可能为扫描件",
    "当前未提取到可用文本",
    "请后续接入 OCR",
    "人工补充摘要",
    "未提取到可用文本",
    "扫描件",
]


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


def safe_data_id(pdf: Path) -> str:
    source = pdf.relative_to(ROOT).as_posix()
    digest = hashlib.sha1(source.encode("utf-8")).hexdigest()[:12]
    stem = re.sub(r"[^A-Za-z0-9_.-]+", "_", pdf.stem)[:80].strip("._-") or "document"
    return f"{stem}_{digest}"


def load_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def load_optional_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        return load_json(path)
    except (OSError, json.JSONDecodeError):
        return {}


def ensure_manual_override_files() -> tuple[dict[str, Any], dict[str, Any]]:
    MANUAL_OVERRIDES_DIR.mkdir(parents=True, exist_ok=True)
    cn_path = MANUAL_OVERRIDES_DIR / "cn_overrides.json"
    us_path = MANUAL_OVERRIDES_DIR / "us_overrides.json"
    for path in [cn_path, us_path]:
        if not path.exists():
            write_json(path, {})
    return load_optional_json(cn_path), load_optional_json(us_path)


def read_path_text(relative_path: str) -> str:
    if not relative_path:
        return ""
    path = Path(relative_path)
    resolved = path if path.is_absolute() else ROOT / path
    try:
        if resolved.exists():
            return resolved.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return ""
    return ""


def strip_markup(text: str) -> str:
    text = re.sub(r"!\[[^\]]*]\([^)]*\)", " ", text)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\$+\s*", " ", text)
    return text


def clean_summary_text(text: str) -> str:
    text = strip_markup(text)
    text = text.replace("\\n", "\n")
    lines = []
    for raw_line in text.splitlines():
        line = re.sub(r"\s+", " ", raw_line).strip()
        if not line:
            continue
        lower = line.lower()
        if any(prompt.lower() in lower for prompt in OLD_OCR_PROMPTS):
            continue
        if re.fullmatch(r"[-—–_ ]*\d+\s*[-—–_ ]*", line):
            continue
        if re.search(r"page\s+\d+\s+of\s+\d+|---\s*page\s+\d+\s*---|第\s*\d+\s*页", lower, re.I):
            continue
        if re.search(r"^\d{6}$|邮编|邮政编码|电话|传真|fax|tel\.?|e-?mail|@|https?://|www\.", line, re.I):
            continue
        if re.search(r"trials@uspto\.gov|571-272-7822|united states patent and trademark office|patent trial and appeal board", lower):
            continue
        if re.search(r"国家知识产权局$|专利局复审和无效审理部$|复审和无效审理部$", line):
            continue
        if "C:\\Users" in line or "input_pdfs" in line or "parsed\\" in line or "MinerU" in line:
            continue
        lines.append(line)
    text = " ".join(lines)
    text = re.sub(r"\s+", " ", text).strip(" ，,。.;；")
    return text[:1200]


def too_short_summary(text: str, language: str) -> bool:
    if language == "zh":
        return len(re.findall(r"[\u4e00-\u9fff]", text)) < 50
    return len(re.findall(r"[A-Za-z]+", text)) < 30


def first_match(patterns: list[str], text: str, flags: int = 0) -> str:
    for pattern in patterns:
        match = re.search(pattern, text, flags)
        if match:
            return clean_party_name(match.group(1))
    return ""


def clean_party_name(value: str) -> str:
    value = strip_markup(str(value or ""))
    value = re.sub(r"\s+", " ", value).strip(" ：:,，.;；")
    value = re.sub(r"\b(Inc|LLC|Ltd|Corp|Co)\s*\.", lambda m: m.group(1) + ".", value)
    value = re.sub(r"\s+(Petitioner|Patent Owner|Plaintiff|Defendant)$", "", value, flags=re.I)
    return value[:140]


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


def mineru_paths_for_pdf(pdf: Path, jurisdiction: str) -> tuple[Path, Path]:
    data_id = safe_data_id(pdf)
    return PARSED_DIR / jurisdiction / "markdown" / f"{data_id}.md", PARSED_DIR / jurisdiction / "json" / f"{data_id}.json"


def mineru_status_for_pdf(pdf: Path, jurisdiction: str) -> tuple[str, str, str]:
    md_path, json_path = mineru_paths_for_pdf(pdf, jurisdiction)
    if not json_path.exists():
        return "not_called", "", md_path.relative_to(ROOT).as_posix() if md_path.exists() else ""
    try:
        data = load_json(json_path)
    except (OSError, json.JSONDecodeError) as exc:
        return "failed", f"Cannot read MinerU JSON: {exc}", md_path.relative_to(ROOT).as_posix() if md_path.exists() else ""
    state = str((data.get("result") or {}).get("state") or "").lower()
    if state == "done" and md_path.exists():
        return "success", "", md_path.relative_to(ROOT).as_posix()
    if state == "failed":
        return "failed", str((data.get("result") or {}).get("err_msg") or "MinerU failed"), md_path.relative_to(ROOT).as_posix() if md_path.exists() else ""
    return "failed", f"MinerU state={state or 'unknown'}", md_path.relative_to(ROOT).as_posix() if md_path.exists() else ""


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


def extract_cn_decision_points(text: str) -> str:
    table_match = re.search(r"<table>.*?决定要点[:：]?\s*</td>.*?</table>", text, re.S)
    if table_match:
        cleaned = clean_summary_text(table_match.group(0))
        cleaned = re.sub(r"^决定要点[:：]?\s*", "", cleaned)
        if cleaned:
            return cleaned
    heading_match = re.search(
        r"(?:^|\n)#{0,3}\s*(?:决定要点|案件要点|审查决定要点|本决定要点|要点)[:：]?\s*(.*?)(?=\n#{1,3}\s|\n一、|\n##\s|$)",
        text,
        re.S,
    )
    if heading_match:
        return clean_summary_text(heading_match.group(1))
    inline_match = re.search(r"决定要点[:：]\s*(.*?)(?=\n\s*##|\n\s*一、|\n\s*案由|$)", text, re.S)
    if inline_match:
        return clean_summary_text(inline_match.group(1))
    return ""


def extract_cn_parties(text: str, record: dict[str, Any]) -> tuple[str, str]:
    owner = first_match([r"专利权人[:：]\s*([^\n。；;]{2,120})", r"<td>专利权人</td><td>(.*?)</td>"], text, re.S)
    petitioner = first_match([r"无效宣告请求人[:：]\s*([^\n。；;]{2,120})", r"<td>无效宣告请求人</td><td>(.*?)</td>"], text, re.S)
    owner = owner or clean_party_name(str(record.get("patentee_or_patent_owner") or ""))
    petitioner = petitioner or clean_party_name(str(record.get("petitioner") or ""))
    return owner, petitioner


def extract_cn_patent_title(text: str, fallback: str) -> str:
    title = first_match(
        [
            r"发明创造名称[:：]\s*([^\n]{2,160})",
            r"发明名称[:：]\s*([^\n]{2,160})",
            r"<td>发明创造名称</td><td>(.*?)</td>",
        ],
        text,
        re.S,
    )
    return title or fallback


def cn_summary(record: dict[str, Any], text: str, title: str, points: list[str], status: str, owner: str, petitioner: str) -> tuple[str, str, bool]:
    manual = str(record.get("manual_summary") or "").strip()
    if manual:
        summary = clean_summary_text(manual)
        return summary, "manual", too_short_summary(summary, "zh")
    decision_points = extract_cn_decision_points(text)
    if decision_points and not too_short_summary(decision_points, "zh"):
        return decision_points, "decision_points", False
    issue_labels = "、".join(CN_LEGAL_LABELS.get(point, point) for point in points if point != "pending_review")
    pieces = [
        f"涉案专利为“{title}”。" if title else "",
        f"专利权人为{owner}。" if owner else "",
        f"无效请求人为{petitioner}。" if petitioner else "",
        f"主要争议点包括{issue_labels}。" if issue_labels else "",
        f"最终结果为{status}。" if status else "",
    ]
    snippet = clean_summary_text(text[:5000])
    if snippet:
        pieces.append(f"文书核心内容摘录：{snippet[:320]}。")
    summary = clean_summary_text("".join(pieces))
    return summary, "generated_from_full_text", too_short_summary(summary, "zh")


def extract_us_parties(text: str, record: dict[str, Any]) -> tuple[str, str, str, str]:
    petitioner = first_match(
        [
            r"([A-Z][A-Z0-9&.,'\- ]{2,120}),\s*Petitioner",
            r"Petitioner[:\s]+([A-Z][A-Za-z0-9&.,'\- ]{2,120})",
        ],
        text,
        re.I,
    )
    patent_owner = first_match(
        [
            r"v\.\s*([A-Z][A-Z0-9&.,'\- ]{2,120}),\s*Patent Owner",
            r"([A-Z][A-Z0-9&.,'\- ]{2,120}),\s*Patent Owner",
            r"Patent Owner[:\s]+([A-Z][A-Za-z0-9&.,'\- ]{2,120})",
        ],
        text,
        re.I,
    )
    plaintiff = first_match([r"([A-Z][A-Z0-9&.,'\- ]{2,120}),\s*Plaintiff"], text, re.I)
    defendant = first_match([r"([A-Z][A-Z0-9&.,'\- ]{2,120}),\s*Defendant"], text, re.I)
    petitioner = petitioner or clean_party_name(str(record.get("petitioner") or ""))
    patent_owner = patent_owner or clean_party_name(str(record.get("patentee_or_patent_owner") or ""))
    return petitioner, patent_owner, plaintiff, defendant


def normalize_us_patent_number(value: str) -> str:
    raw = str(value or "")
    match = re.search(r"(?:U\.?S\.?\s*)?(?:Patent\s*(?:No\.)?\s*)?([0-9,]{7,12})(?:\s*([A-Z][0-9]))?", raw, re.I)
    if not match:
        return ""
    return f"US{match.group(1).replace(',', '')}{match.group(2) or ''}"


def load_us_patent_cache() -> dict[str, Any]:
    cache = load_optional_json(US_PATENT_CACHE_PATH)
    return cache if isinstance(cache, dict) else {}


def patent_lookup_us(patent_number: str, text: str, cache: dict[str, Any]) -> dict[str, Any]:
    normalized = normalize_us_patent_number(patent_number)
    cached = cache.get(normalized) if normalized else None
    if isinstance(cached, dict):
        return {**cached, "patent_number": normalized, "status": "success", "source": cached.get("source", "local_cache"), "confidence": cached.get("confidence", 0.9)}
    title = ""
    abstract = ""
    abstract_match = re.search(r"The\s+'?\d+\s+patent\s+\"([^\"]{20,260})\"", text, re.I)
    if abstract_match:
        abstract = clean_summary_text(abstract_match.group(1))
    if not abstract:
        abstract = first_match([r"(?:Abstract\.?|ABSTRACT)\s*(.{30,360})"], text, re.I | re.S)
    title_match = re.search(r"(?:Title|Patent Title)[:\s]+([A-Z][^\n]{12,180})", text)
    if title_match:
        title = clean_summary_text(title_match.group(1))
    return {
        "patent_number": normalized,
        "patent_title": title,
        "assignee": "",
        "inventors": [],
        "abstract": abstract,
        "publication_date": "",
        "grant_date": "",
        "source": "pdf",
        "status": "partial" if title else ("abstract_only" if abstract else "failed"),
        "confidence": 0.75 if title else 0.0,
    }


def us_title(record: dict[str, Any], text: str, lookup: dict[str, Any]) -> tuple[str, float, bool]:
    patent_title = clean_summary_text(str(lookup.get("patent_title") or ""))
    bad_title = re.search(
        r"paper\s+no\.|final written decision|decision on institution|united states patent|"
        r"patent trial and appeal board|before the|filed:|^IPR\d|^PGR\d|^CBM\d|\.pdf",
        patent_title,
        re.I,
    )
    if patent_title and not bad_title:
        return patent_title, float(lookup.get("confidence") or 0.55), False
    embedded = first_match([r"The\s+'?\d+\s+patent\s+\"([^\"]{20,180})\""], text, re.I)
    if embedded:
        embedded_title = clean_summary_text(embedded)
        if not re.search(r"^(provides|relates|teaches|discloses|describes)\b", embedded_title, re.I):
            return embedded_title, 0.45, True
    caption = first_match([r"(.+?\s+v\.\s+.+?)(?:\n|IPR|PGR|CBM)"], text[:3000], re.I | re.S)
    if caption:
        clean_caption = clean_summary_text(caption)
        if not re.search(r"paper\s+no\.|united states patent|patent trial and appeal board|before the|filed:", clean_caption, re.I):
            return clean_caption[:180].rstrip(" .;"), 0.35, True
    title = str(record.get("title") or "").strip()
    bad = re.search(
        r"paper\s+no\.|final written decision|decision on institution|draft|fd\s+final|"
        r"fd\s+ready|dismissal on remand|ipr\d|pgr\d|cbm\d|\.pdf|filed:|"
        r"^(provides|relates|teaches|discloses|describes)\b",
        title,
        re.I,
    )
    return (title if title and not bad else "Patent title pending review"), 0.15, True


def classify_us_patent_type(text: str, lookup: dict[str, Any]) -> tuple[str, list[str], float, str]:
    haystack = " ".join(
        [
            str(lookup.get("patent_title") or ""),
            str(lookup.get("abstract") or ""),
            clean_summary_text(text[:18000]),
        ]
    ).lower()
    rules = [
        ("晶型/盐/溶剂合物", ["crystalline form", "polymorph", "crystal form", "hydrate", "solvate", "salt form", " form a", " form b"], 0.8),
        ("生物制品/抗体", ["antibody", "antibodies", "monoclonal", "antigen-binding", "protein", "polypeptide", "nucleic acid", "oligonucleotide", "rna", "sirna", "car-t", "vaccine"], 0.78),
        ("制剂/组合物", ["formulation", "composition", "pharmaceutical composition", "dosage form", "tablet", "capsule", "sustained release", "extended release"], 0.75),
        ("用途/适应症", ["method of treating", "method for treating", "treatment of", "therapy", "administering to treat", "therapeutic"], 0.72),
        ("制备方法/中间体", ["process for preparing", "method for making", "method of making", "intermediate", "synthesis", "preparation", "manufacturing"], 0.7),
        ("化合物专利", ["compound", "compounds", "derivative", "analog", "analogue", "inhibitor compound", "formula i", "markush"], 0.68),
    ]
    found: list[tuple[str, float, str]] = []
    for label, needles, score in rules:
        if any(needle in haystack for needle in needles):
            found.append((label, score, next(needle for needle in needles if needle in haystack)))
    if not found:
        return "待确认", [], 0.2, "未在专利标题、摘要或权利要求描述中识别出稳定的医药专利类型。"
    found.sort(key=lambda item: item[1], reverse=True)
    primary = found[0][0]
    secondary = [item[0] for item in found[1:3] if item[0] != primary]
    return primary, secondary, found[0][1], f"命中关键词：{found[0][2]}"


def us_summary(item: dict[str, Any], text: str, lookup: dict[str, Any], legal_points: list[str], drug_info: dict[str, Any]) -> tuple[str, str, bool]:
    legal = "、".join(US_LEGAL_LABELS.get(point, point) for point in legal_points if point != "pending_review")
    patent_title = item.get("patent_title") or lookup.get("patent_title") or item.get("title")
    parties = []
    if item.get("petitioner"):
        parties.append(f"Petitioner 为 {item['petitioner']}")
    if item.get("patent_owner"):
        parties.append(f"Patent Owner 为 {item['patent_owner']}")
    if item.get("plaintiff") or item.get("defendant"):
        parties.append(f"诉讼当事人为 {item.get('plaintiff', '')} v. {item.get('defendant', '')}".strip())
    intro = clean_summary_text(extract_relevant_us_text(text))
    pieces = [
        f"本案涉及美国专利 {item.get('patent_number') or '待确认'}，专利主题为“{patent_title}”。",
        f"程序类型为 {item.get('proceeding_type') or 'Unknown'}，程序号为 {item.get('proceeding_number') or item.get('case_number') or '待确认'}。",
        "；".join(parties) + "。" if parties else "",
        f"主要法律问题包括 {legal}。" if legal else "",
        f"PTAB/法院最终结果为 {item.get('outcome') or 'unknown'}。",
        f"药物/活性成分信息：{drug_info.get('drug_name') or drug_info.get('active_ingredient')}。" if drug_info.get("drug_name") or drug_info.get("active_ingredient") else "",
        f"关键内容：{intro[:420]}。" if intro else "",
    ]
    summary = clean_summary_text("".join(pieces))
    return summary, "generated_from_full_text", too_short_summary(summary, "zh")


def extract_relevant_us_text(text: str) -> str:
    anchors = [
        "I. INTRODUCTION",
        "Background",
        "The '",
        "Instituted Challenges",
        "Analysis",
        "Conclusion",
        "Order",
        "Final Written Decision",
        "Claim Construction",
        "Obviousness",
        "Anticipation",
        "Written Description",
        "Enablement",
    ]
    pieces: list[str] = []
    lower = text.lower()
    for anchor in anchors:
        pos = lower.find(anchor.lower())
        if pos >= 0:
            pieces.append(text[pos : pos + 1200])
        if len(pieces) >= 5:
            break
    return "\n".join(pieces) or text[:4000]


def drug_info(record: dict[str, Any], text: str) -> dict[str, Any]:
    drug, confidence_label = drug_name(record)
    if drug == "待人工确认":
        drug = ""
    active = first_match([r"active ingredient[:\s]+([A-Za-z0-9 ,;\-/]{2,80})", r"活性成分[:：]\s*([^\n。；;]{2,80})"], text, re.I)
    product = first_match([r"product name[:\s]+([A-Za-z0-9 ,;\-/]{2,80})", r"商品名[:：]\s*([^\n。；;]{2,80})"], text, re.I)
    confidence = {"high": 0.9, "medium": 0.6, "low": 0.35}.get(confidence_label, 0.2 if drug or active or product else 0)
    return {
        "drug_name": drug,
        "active_ingredient": active,
        "product_name": product,
        "applicant": "",
        "application_number": "",
        "source": "pdf" if drug or active or product else "unknown",
        "confidence": confidence,
        "review_required": confidence < 0.6,
    }


def apply_overrides(item: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
    if not override:
        return item
    for key, value in override.items():
        if value in ("", None, [], {}):
            continue
        if isinstance(value, dict) and isinstance(item.get(key), dict):
            merged = dict(item[key])
            merged.update({k: v for k, v in value.items() if v not in ("", None, [], {})})
            item[key] = merged
        else:
            item[key] = value
    item["manual_override_applied"] = True
    item["review_required"] = False
    return item


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


def build_cn_case(record: dict[str, Any], text: str, pdf_path: str, parsed_md: str, override: dict[str, Any] | None = None) -> dict[str, Any]:
    title, title_conf = clean_title(record, "cn")
    title = extract_cn_patent_title(text, title)
    ptype, ptype_conf = patent_type_label(record)
    points = record.get("legal_issues") or ["pending_review"]
    if not points:
        points = ["pending_review"]
    owner, petitioner = extract_cn_parties(text, record)
    status = cn_status(record)
    summary, summary_source, summary_review_required = cn_summary(record, text, title, points, status, owner, petitioner)
    dinfo = drug_info(record, text)
    item = {
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
        "secondary_patent_types": [],
        "legal_points": points,
        "drug_info": dinfo,
        "drug_name": dinfo["drug_name"] or "待人工确认",
        "drug_name_confidence": "manual_required" if dinfo["review_required"] else "medium",
        "patent_owner": owner,
        "invalidity_petitioner": petitioner,
        "parties": [
            {"role": "专利权人", "name": owner} if owner else {},
            {"role": "无效请求人", "name": petitioner} if petitioner else {},
        ],
        "summary": summary,
        "summary_source": summary_source,
        "summary_review_required": summary_review_required,
        "status": status,
        "outcome": status,
        "confidence": {
            "title": title_conf,
            "patent_type": ptype_conf,
            "legal_points": 0.65 if points != ["pending_review"] else 0.2,
            "drug_name": dinfo["confidence"],
            "summary": 0.85 if summary_source == "decision_points" else 0.55,
            "parties": 0.8 if owner and petitioner else 0.2,
        },
        "review_required": bool(
            record.get("needs_manual_summary")
            or record.get("exclude_reason")
            or points == ["pending_review"]
            or summary_review_required
            or not owner
            or not petitioner
            or dinfo["review_required"]
        ),
        "manual_override_applied": False,
        "original_exclude_reason": record.get("exclude_reason", ""),
        "parse_status": parse_status(record, text),
    }
    item["parties"] = [party for party in item["parties"] if party]
    return apply_overrides(item, override or {})


def build_us_case(
    record: dict[str, Any],
    text: str,
    pdf_path: str,
    parsed_md: str,
    patent_cache: dict[str, Any],
    override: dict[str, Any] | None = None,
) -> dict[str, Any]:
    points, points_conf = us_legal_points(record, text)
    lookup = patent_lookup_us(record.get("patent_number", ""), text, patent_cache)
    title, title_conf, title_review_required = us_title(record, text, lookup)
    ptype, secondary_types, ptype_conf, ptype_basis = classify_us_patent_type(text, lookup)
    petitioner, patent_owner, plaintiff, defendant = extract_us_parties(text, record)
    dinfo = drug_info(record, text)
    base_item = {
        "title": title,
        "patent_title": lookup.get("patent_title") or title,
        "proceeding_type": us_proceeding_type(record, text),
        "proceeding_number": record.get("proceeding_number", ""),
        "case_number": record.get("court_case_number", ""),
        "patent_number": normalize_us_patent_number(record.get("patent_number", "")) or record.get("patent_number", ""),
        "petitioner": petitioner,
        "patent_owner": patent_owner,
        "plaintiff": plaintiff,
        "defendant": defendant,
        "outcome": us_outcome(record),
    }
    summary, summary_source, summary_review_required = us_summary(base_item, text, lookup, points, dinfo)
    item = {
        "case_id": record["id"].replace("case_", "us_"),
        "source_case_id": record["id"],
        "jurisdiction": "us",
        "language": "en",
        **base_item,
        "court": record.get("court_name", ""),
        "pdf": pdf_path,
        "parsed_markdown": parsed_md,
        "patent_type": ptype,
        "secondary_patent_types": secondary_types,
        "patent_type_basis": ptype_basis,
        "us_legal_points": points,
        "drug_info": dinfo,
        "drug_name": dinfo["drug_name"] or "待人工确认",
        "drug_name_confidence": "manual_required" if dinfo["review_required"] else "medium",
        "parties": [
            {"role": "Petitioner", "name": petitioner} if petitioner else {},
            {"role": "Patent Owner", "name": patent_owner} if patent_owner else {},
            {"role": "Plaintiff", "name": plaintiff} if plaintiff else {},
            {"role": "Defendant", "name": defendant} if defendant else {},
        ],
        "summary": summary,
        "summary_source": summary_source,
        "summary_review_required": summary_review_required,
        "patent_lookup": lookup,
        "confidence": {
            "title": title_conf,
            "patent_type": ptype_conf,
            "us_legal_points": points_conf,
            "drug_name": dinfo["confidence"],
            "summary": 0.65 if not summary_review_required else 0.2,
            "parties": 0.8 if (petitioner and patent_owner) or (plaintiff and defendant) else 0.2,
        },
        "review_required": bool(
            record.get("needs_manual_summary")
            or record.get("exclude_reason")
            or points == ["pending_review"]
            or summary_review_required
            or title_review_required
            or ptype in {"其他", "待确认"}
            or not base_item["patent_number"]
            or lookup.get("status") == "failed"
            or not ((petitioner and patent_owner) or (plaintiff and defendant))
            or dinfo["review_required"]
        ),
        "manual_override_applied": False,
        "original_exclude_reason": record.get("exclude_reason", ""),
        "parse_status": parse_status(record, text),
    }
    item["parties"] = [party for party in item["parties"] if party]
    return apply_overrides(item, override or {})


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
    cn_overrides, us_overrides = ensure_manual_override_files()
    us_patent_cache = load_us_patent_cache()
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
        mineru_status, mineru_error, mineru_md_path = mineru_status_for_pdf(pdf, jurisdiction)
        mineru_text = read_path_text(mineru_md_path)
        if mineru_text.strip():
            text = mineru_text
        case_id = record.get("id", "") if record else ""
        pdf_rel = ""
        parsed_md = ""
        if record:
            pdf_rel = public_pdf_path(record, jurisdiction)
            parsed_md = write_parsed_markdown(record, jurisdiction, text)
            if mineru_md_path:
                parsed_md = mineru_md_path
            seen_case_ids.add(record["id"])
            if jurisdiction == "cn":
                cn_id = record["id"].replace("case_", "cn_")
                cn_cases.append(build_cn_case(record, text, pdf_rel, parsed_md, cn_overrides.get(cn_id, {})))
            elif jurisdiction == "us":
                us_id = record["id"].replace("case_", "us_")
                us_cases.append(build_us_case(record, text, pdf_rel, parsed_md, us_patent_cache, us_overrides.get(us_id, {})))

        manifest_files.append(
            {
                "file_name": pdf.name,
                "source_path": rel(pdf),
                "public_pdf_path": pdf_rel,
                "jurisdiction": jurisdiction,
                "language": lang,
                "parse_status": parse_status(record, text) if record else "failed",
                "mineru_status": mineru_status,
                "database_status": database_status(record, text, jurisdiction) if record else "pending_review",
                "error_message": mineru_error if mineru_error else ("" if record else "No generated case JSON matched this input PDF."),
                "case_id": case_id,
                "parsed_markdown_path": parsed_md,
                "parsed_json_path": rel(mineru_paths_for_pdf(pdf, jurisdiction)[1]) if mineru_status != "not_called" else (rel(OUTPUT_JSON_DIR / f"{case_id}.json") if case_id else ""),
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
    review_rows = write_review_queue(cn_cases, us_cases)
    write_data_quality_report(cn_cases, us_cases, review_rows)
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


def queue_row(
    item: dict[str, Any],
    field_name: str,
    current_value: Any,
    reason: str,
    confidence: float,
    suggested_value: Any = "",
) -> dict[str, Any]:
    jurisdiction = item.get("jurisdiction", "")
    edit_file = (
        "data/manual_overrides/cn_overrides.json"
        if jurisdiction == "cn"
        else "data/manual_overrides/us_overrides.json"
    )
    return {
        "case_id": item.get("case_id", ""),
        "jurisdiction": jurisdiction,
        "pdf": item.get("pdf", ""),
        "field_name": field_name,
        "current_value": json.dumps(current_value, ensure_ascii=False) if isinstance(current_value, (list, dict)) else str(current_value or ""),
        "suggested_value": json.dumps(suggested_value, ensure_ascii=False) if isinstance(suggested_value, (list, dict)) else str(suggested_value or ""),
        "reason": reason,
        "confidence": confidence,
        "edit_file": edit_file,
        "notes": "",
    }


def write_review_queue(cn_cases: list[dict[str, Any]], us_cases: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for item in [*cn_cases, *us_cases]:
        confidence = item.get("confidence", {})
        if item.get("summary_review_required") or too_short_summary(item.get("summary", ""), "zh"):
            rows.append(queue_row(item, "summary", item.get("summary", ""), "summary 过短或需要复核", confidence.get("summary", 0)))
        if any(prompt in str(item.get("summary", "")) for prompt in OLD_OCR_PROMPTS):
            rows.append(queue_row(item, "summary", item.get("summary", ""), "summary 含旧 OCR/扫描件提示", 0))
        if not item.get("title") or re.search(r"\.pdf$|final written decision|^IPR\d|^PGR\d|^CBM\d", str(item.get("title", "")), re.I):
            rows.append(queue_row(item, "title", item.get("title", ""), "title 缺失、使用文件名或程序名", confidence.get("title", 0)))
        if item.get("patent_type") in {"其他", "待确认", "other"}:
            rows.append(queue_row(item, "patent_type", item.get("patent_type", ""), "patent_type 为其他或待确认", confidence.get("patent_type", 0)))
        if item.get("jurisdiction") == "us":
            if not item.get("patent_number"):
                rows.append(queue_row(item, "patent_number", "", "美国案例 patent_number 缺失", 0))
            if (item.get("patent_lookup") or {}).get("status") == "failed":
                rows.append(queue_row(item, "patent_lookup", item.get("patent_lookup", {}), "美国专利信息未检索成功", (item.get("patent_lookup") or {}).get("confidence", 0)))
            if not item.get("us_legal_points") or item.get("us_legal_points") == ["pending_review"]:
                rows.append(queue_row(item, "us_legal_points", item.get("us_legal_points", []), "美国法律点为空或待确认", confidence.get("us_legal_points", 0)))
            if not ((item.get("petitioner") and item.get("patent_owner")) or (item.get("plaintiff") and item.get("defendant"))):
                rows.append(queue_row(item, "parties", item.get("parties", []), "美国当事人缺失", confidence.get("parties", 0)))
            if item.get("outcome") in {"", "unknown", None}:
                rows.append(queue_row(item, "outcome", item.get("outcome", ""), "outcome 为空或 unknown", 0))
        else:
            if not item.get("legal_points") or item.get("legal_points") == ["pending_review"]:
                rows.append(queue_row(item, "legal_points", item.get("legal_points", []), "中国法律点为空或待确认", confidence.get("legal_points", 0)))
            if not item.get("patent_owner") or not item.get("invalidity_petitioner"):
                rows.append(queue_row(item, "parties", item.get("parties", []), "中国专利权人或无效请求人缺失", confidence.get("parties", 0)))
            if item.get("status") in {"", "待确认", None}:
                rows.append(queue_row(item, "status", item.get("status", ""), "无效结果为空或待确认", 0))
        dinfo = item.get("drug_info") or {}
        if dinfo.get("review_required"):
            rows.append(queue_row(item, "drug_info", dinfo, "药物信息缺失或置信度低", dinfo.get("confidence", 0)))

    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    csv_path = REPORTS_DIR / "review_queue.csv"
    fieldnames = ["case_id", "jurisdiction", "pdf", "field_name", "current_value", "suggested_value", "reason", "confidence", "edit_file", "notes"]
    with csv_path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    md_lines = [
        "# 待复核清单",
        "",
        "人工修改请编辑 `data/manual_overrides/cn_overrides.json` 或 `data/manual_overrides/us_overrides.json`，然后重新运行 `python scripts\\build_jurisdiction_data.py`。",
        "",
        "| case_id | jurisdiction | field | reason | edit_file |",
        "|---|---|---|---|---|",
    ]
    for row in rows[:500]:
        md_lines.append(f"| {row['case_id']} | {row['jurisdiction']} | {row['field_name']} | {str(row['reason']).replace('|', '/')} | {row['edit_file']} |")
    if len(rows) > 500:
        md_lines.append(f"| ... | ... | ... | 另有 {len(rows) - 500} 条，详见 CSV | ... |")
    (REPORTS_DIR / "review_queue.md").write_text("\n".join(md_lines) + "\n", encoding="utf-8")
    return rows


def write_data_quality_report(cn_cases: list[dict[str, Any]], us_cases: list[dict[str, Any]], review_rows: list[dict[str, Any]]) -> None:
    all_cases = [*cn_cases, *us_cases]
    old_prompt_count = sum(1 for item in all_cases if any(prompt in str(item.get("summary", "")) for prompt in OLD_OCR_PROMPTS))
    cn_decision_points = sum(1 for item in cn_cases if item.get("summary_source") == "decision_points")
    cn_manual_summary = sum(1 for item in cn_cases if item.get("summary_review_required"))
    us_summaries = sum(1 for item in us_cases if item.get("summary_source") == "generated_from_full_text" and not item.get("summary_review_required"))
    us_title_lookup = sum(1 for item in us_cases if (item.get("patent_lookup") or {}).get("patent_title") and item.get("title") == (item.get("patent_lookup") or {}).get("patent_title"))
    us_lookup_success = sum(1 for item in us_cases if (item.get("patent_lookup") or {}).get("status") in {"success", "partial"})
    us_other = [item for item in us_cases if item.get("patent_type") in {"其他", "待确认"}]
    party_success = sum(1 for item in all_cases if item.get("parties"))
    drug_success = sum(1 for item in all_cases if (item.get("drug_info") or {}).get("drug_name") or (item.get("drug_info") or {}).get("active_ingredient"))
    lines = [
        "# 数据质量报告",
        "",
        f"- 总案例数：{len(all_cases)}",
        f"- 中国案例数：{len(cn_cases)}",
        f"- 美国案例数：{len(us_cases)}",
        f"- summary 含旧 OCR 提示数量：{old_prompt_count}",
        f"- 中国案例成功抽取“决定要点”数量：{cn_decision_points}",
        f"- 中国案例仍需人工摘要数量：{cn_manual_summary}",
        f"- 美国案例成功生成 key points 数量：{us_summaries}",
        f"- 美国案例 title 使用 patent_title 数量：{us_title_lookup}",
        f"- 美国案例 patent_lookup 成功或部分成功数量：{us_lookup_success}",
        f"- 美国案例 patent_type 仍为“其他/待确认”数量：{len(us_other)}",
        f"- 当事人字段提取成功数量：{party_success}",
        f"- 药物信息提取成功数量：{drug_success}",
        f"- 进入 review_queue 的字段数量：{len(review_rows)}",
        "",
        "## 仍为“其他/待确认”的美国案例原因",
        "",
    ]
    if us_other:
        for item in us_other[:50]:
            lines.append(f"- {item.get('case_id')}: {item.get('patent_type_basis', '信息不足或自动判断冲突')}")
        if len(us_other) > 50:
            lines.append(f"- 另有 {len(us_other) - 50} 条，详见 `reports/review_queue.csv`。")
    else:
        lines.append("- 暂无。")
    lines.extend(
        [
            "",
            "## manual_overrides 修改方式",
            "",
            "不要直接改 `public/data/cn_cases.json` 或 `public/data/us_cases.json`。请在 `data/manual_overrides/cn_overrides.json` 或 `data/manual_overrides/us_overrides.json` 中按 case_id 写入要覆盖的字段。重新运行 `python scripts\\build_jurisdiction_data.py` 后，manual_overrides 会优先于自动识别结果，后续重跑不会覆盖人工修改。",
        ]
    )
    (REPORTS_DIR / "data_quality_report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_review_queue(cn_cases: list[dict[str, Any]], us_cases: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for item in [*cn_cases, *us_cases]:
        confidence = item.get("confidence", {})
        if item.get("summary_review_required") or too_short_summary(item.get("summary", ""), "zh"):
            rows.append(queue_row(item, "summary", item.get("summary", ""), "summary 过短或需要复核", confidence.get("summary", 0)))
        if any(prompt in str(item.get("summary", "")) for prompt in OLD_OCR_PROMPTS):
            rows.append(queue_row(item, "summary", item.get("summary", ""), "summary 含旧 OCR/扫描件提示", 0))
        if not item.get("title") or re.search(r"\.pdf$|final written decision|^IPR\d|^PGR\d|^CBM\d", str(item.get("title", "")), re.I):
            rows.append(queue_row(item, "title", item.get("title", ""), "title 缺失、使用文件名或程序名", confidence.get("title", 0)))
        if item.get("patent_type") in {"其他", "待确认", "other"}:
            rows.append(queue_row(item, "patent_type", item.get("patent_type", ""), "patent_type 为其他或待确认", confidence.get("patent_type", 0)))

        if item.get("jurisdiction") == "us":
            if not item.get("patent_number"):
                rows.append(queue_row(item, "patent_number", "", "美国案例 patent_number 缺失", 0))
            if (item.get("patent_lookup") or {}).get("status") == "failed":
                rows.append(queue_row(item, "patent_lookup", item.get("patent_lookup", {}), "美国专利信息未检索成功", (item.get("patent_lookup") or {}).get("confidence", 0)))
            if not item.get("us_legal_points") or item.get("us_legal_points") == ["pending_review"]:
                rows.append(queue_row(item, "us_legal_points", item.get("us_legal_points", []), "美国法律点为空或待确认", confidence.get("us_legal_points", 0)))
            if not ((item.get("petitioner") and item.get("patent_owner")) or (item.get("plaintiff") and item.get("defendant"))):
                rows.append(queue_row(item, "parties", item.get("parties", []), "美国当事人缺失", confidence.get("parties", 0)))
            if item.get("outcome") in {"", "unknown", None}:
                rows.append(queue_row(item, "outcome", item.get("outcome", ""), "outcome 为空或 unknown", 0))
        else:
            if not item.get("legal_points") or item.get("legal_points") == ["pending_review"]:
                rows.append(queue_row(item, "legal_points", item.get("legal_points", []), "中国法律点为空或待确认", confidence.get("legal_points", 0)))
            if not item.get("patent_owner") or not item.get("invalidity_petitioner"):
                rows.append(queue_row(item, "parties", item.get("parties", []), "中国专利权人或无效请求人缺失", confidence.get("parties", 0)))
            if item.get("status") in {"", "待确认", None}:
                rows.append(queue_row(item, "status", item.get("status", ""), "无效结果为空或待确认", 0))

        dinfo = item.get("drug_info") or {}
        if dinfo.get("review_required"):
            rows.append(queue_row(item, "drug_info", dinfo, "药物信息缺失或置信度低", dinfo.get("confidence", 0)))

    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    csv_path = REPORTS_DIR / "review_queue.csv"
    fieldnames = ["case_id", "jurisdiction", "pdf", "field_name", "current_value", "suggested_value", "reason", "confidence", "edit_file", "notes"]
    with csv_path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    md_lines = [
        "# 待复核清单",
        "",
        "人工修改请编辑 `data/manual_overrides/cn_overrides.json` 或 `data/manual_overrides/us_overrides.json`，然后重新运行 `python scripts\\build_jurisdiction_data.py`。",
        "",
        "| case_id | jurisdiction | field | reason | edit_file |",
        "|---|---|---|---|---|",
    ]
    for row in rows[:500]:
        md_lines.append(f"| {row['case_id']} | {row['jurisdiction']} | {row['field_name']} | {str(row['reason']).replace('|', '/')} | {row['edit_file']} |")
    if len(rows) > 500:
        md_lines.append(f"| ... | ... | ... | 另有 {len(rows) - 500} 条，详见 CSV | ... |")
    (REPORTS_DIR / "review_queue.md").write_text("\n".join(md_lines) + "\n", encoding="utf-8")
    return rows


def write_data_quality_report(cn_cases: list[dict[str, Any]], us_cases: list[dict[str, Any]], review_rows: list[dict[str, Any]]) -> None:
    all_cases = [*cn_cases, *us_cases]
    old_prompt_count = sum(1 for item in all_cases if any(prompt in str(item.get("summary", "")) for prompt in OLD_OCR_PROMPTS))
    cn_decision_points = sum(1 for item in cn_cases if item.get("summary_source") == "decision_points")
    cn_manual_summary = sum(1 for item in cn_cases if item.get("summary_review_required"))
    us_summaries = sum(1 for item in us_cases if item.get("summary_source") == "generated_from_full_text" and not item.get("summary_review_required"))
    us_title_lookup = sum(1 for item in us_cases if (item.get("patent_lookup") or {}).get("patent_title") and item.get("title") == (item.get("patent_lookup") or {}).get("patent_title"))
    us_lookup_success = sum(1 for item in us_cases if (item.get("patent_lookup") or {}).get("status") in {"success", "partial"})
    us_other = [item for item in us_cases if item.get("patent_type") in {"其他", "待确认"}]
    party_success = sum(1 for item in all_cases if item.get("parties"))
    drug_success = sum(1 for item in all_cases if (item.get("drug_info") or {}).get("drug_name") or (item.get("drug_info") or {}).get("active_ingredient"))
    lines = [
        "# 数据质量报告",
        "",
        f"- 总案例数：{len(all_cases)}",
        f"- 中国案例数：{len(cn_cases)}",
        f"- 美国案例数：{len(us_cases)}",
        f"- summary 含旧 OCR 提示数量：{old_prompt_count}",
        f"- 中国案例成功抽取“决定要点”数量：{cn_decision_points}",
        f"- 中国案例仍需人工摘要数量：{cn_manual_summary}",
        f"- 美国案例成功生成 key points 数量：{us_summaries}",
        f"- 美国案例 title 使用 patent_title 数量：{us_title_lookup}",
        f"- 美国案例 patent_lookup 成功或部分成功数量：{us_lookup_success}",
        f"- 美国案例 patent_type 仍为“其他/待确认”数量：{len(us_other)}",
        f"- 当事人字段提取成功数量：{party_success}",
        f"- 药物信息提取成功数量：{drug_success}",
        f"- 进入 review_queue 的字段数量：{len(review_rows)}",
        "",
        "## 仍为“其他/待确认”的美国案例原因",
        "",
    ]
    if us_other:
        for item in us_other[:50]:
            lines.append(f"- {item.get('case_id')}: {item.get('patent_type_basis', '信息不足或自动判断冲突')}")
        if len(us_other) > 50:
            lines.append(f"- 另有 {len(us_other) - 50} 条，详见 `reports/review_queue.csv`。")
    else:
        lines.append("- 暂无。")
    lines.extend(
        [
            "",
            "## manual_overrides 修改方式",
            "",
            "不要直接改 `public/data/cn_cases.json` 或 `public/data/us_cases.json`。请在 `data/manual_overrides/cn_overrides.json` 或 `data/manual_overrides/us_overrides.json` 中按 case_id 写入要覆盖的字段。重新运行 `python scripts\\build_jurisdiction_data.py` 后，manual_overrides 会优先于自动识别结果，后续重跑不会覆盖人工修改。",
        ]
    )
    (REPORTS_DIR / "data_quality_report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    totals = build()
    print(json.dumps(totals, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
