from __future__ import annotations

import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from dedupe import content_hash, ensure_dedupe_fields, extract_identifiers, normalize_text_for_hash


MIN_SUBSTANTIVE_CHARS = 800


TAG_LABELS = {
    "patent_type": {
        "compound": "化合物",
        "polymorph": "晶型",
        "formulation": "制剂",
        "medical_use": "医药用途",
        "antibody": "抗体",
        "nucleic_acid": "核酸",
        "cell_therapy": "细胞治疗",
        "method": "方法",
        "composition": "组合物",
        "process": "制备方法",
        "dosage_regimen": "给药方案",
        "other": "其他",
    },
    "legal_issues": {
        "inventive_step": "创造性",
        "novelty": "新颖性",
        "enablement": "充分公开 / 可实施性",
        "written_description": "说明书支持 / 书面描述",
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
    },
    "evidence_types": {
        "prior_art_patent": "在先专利",
        "prior_art_literature": "文献",
        "expert_declaration": "专家声明",
        "experimental_data": "实验数据",
        "textbook": "教科书",
        "common_general_knowledge": "公知常识证据",
        "prosecution_history": "审查历史",
        "comparative_example": "对比例",
    },
    "doc_type": {
        "invalidity_decision": "无效决定",
        "court_judgment": "法院判决",
        "appeal_decision": "上诉/再审决定",
        "litigation_related": "诉讼相关材料",
        "link_or_notice": "链接/通知页",
        "other": "其他",
    },
    "litigation_stage": {
        "invalidity_proceeding": "无效程序",
        "first_instance": "一审",
        "second_instance": "二审",
        "retrial": "再审",
        "ptab": "PTAB",
        "federal_circuit": "Federal Circuit",
        "district_court": "District Court",
        "supreme_court": "Supreme Court",
        "other": "其他",
    },
}


RULES = {
    "patent_type": {
        "compound": ["化合物", "compound", "genus", "markush"],
        "polymorph": ["晶型", "多晶型", "polymorph", "crystal form", "crystalline"],
        "formulation": ["制剂", "formulation", "tablet", "capsule", "composition"],
        "medical_use": ["用途", "适应症", "medical use", "method of treatment", "treating"],
        "antibody": ["抗体", "antibody", "monoclonal", "免疫球蛋白"],
        "nucleic_acid": ["核酸", "rna", "dna", "sirna", "oligonucleotide"],
        "cell_therapy": ["细胞治疗", "car-t", "cell therapy"],
        "method": ["方法", "method"],
        "composition": ["组合物", "composition"],
        "process": ["制备", "process", "preparation", "manufacturing"],
        "dosage_regimen": ["给药", "剂量", "dosage", "dose", "regimen"],
    },
    "legal_issues": {
        "inventive_step": ["创造性", "显而易见", "inventive step", "obviousness", "obvious"],
        "novelty": ["新颖性", "novelty", "anticipated", "anticipation"],
        "enablement": ["充分公开", "可实施", "enablement", "enabled"],
        "written_description": ["说明书支持", "书面描述", "written description", "support"],
        "claim_construction": ["权利要求解释", "claim construction", "claim interpretation"],
        "priority": ["优先权", "priority"],
        "amendment": ["修改超范围", "new matter", "amendment"],
        "experimental_data": ["实验数据", "experimental data", "test data"],
        "post_filing_data": ["申请日后", "post-filing", "post filing"],
        "common_general_knowledge": ["公知常识", "common general knowledge"],
        "motivation_to_combine": ["结合动机", "motivation to combine"],
        "reasonable_expectation_of_success": ["合理成功预期", "reasonable expectation"],
        "unexpected_effect": ["预料不到", "unexpected effect", "unexpected results"],
        "dosage_regimen": ["给药方案", "dosage regimen"],
        "medical_use": ["医药用途", "medical use", "method of treatment"],
        "polymorph": ["晶型", "polymorph"],
        "selection_invention": ["选择发明", "selection invention"],
    },
    "evidence_types": {
        "prior_art_patent": ["在先专利", "prior art patent", "patent publication"],
        "prior_art_literature": ["文献", "article", "journal", "publication"],
        "expert_declaration": ["专家声明", "expert declaration", "expert testimony"],
        "experimental_data": ["实验数据", "experimental data", "test data"],
        "textbook": ["教科书", "textbook"],
        "common_general_knowledge": ["公知常识", "common general knowledge"],
        "prosecution_history": ["审查历史", "prosecution history", "file history"],
        "comparative_example": ["对比例", "comparative example"],
    },
}


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def detect_language(region: str, text: str) -> str:
    if region == "CN":
        return "zh"
    if region == "US":
        return "en"
    chinese_chars = len(re.findall(r"[\u4e00-\u9fff]", text[:5000]))
    return "zh" if chinese_chars > 50 else "en"


def match_tags(bucket: str, haystack: str) -> list[str]:
    found: list[str] = []
    haystack_lower = haystack.lower()
    for tag, needles in RULES[bucket].items():
        if any(needle.lower() in haystack_lower for needle in needles):
            found.append(tag)
    return found or (["other"] if bucket == "patent_type" else [])


def classify_case_tags(text: str, title: str, region: str) -> dict[str, Any]:
    """Conservative, review-friendly tags used for the front-end index."""
    patent_type, patent_basis = infer_primary_patent_type(text, title)
    legal_issues, legal_basis = infer_legal_issues(text, title, region)
    evidence_types = infer_evidence_types(text, title)
    return {
        "patent_type": [patent_type],
        "patent_type_basis": patent_basis,
        "legal_issues": legal_issues,
        "legal_issue_basis": legal_basis,
        "evidence_types": evidence_types,
    }


def infer_primary_patent_type(text: str, title: str) -> tuple[str, str]:
    front = focused_front_matter(text, title)
    lower = front.lower()
    scores: dict[str, int] = {tag: 0 for tag in RULES["patent_type"]}

    weighted_patterns = [
        ("antibody", 120, ["抗体", "antibody", "monoclonal", "免疫球蛋白"]),
        ("cell_therapy", 115, ["细胞治疗", "car-t", "cart", "cell therapy", "t cell"]),
        ("nucleic_acid", 110, ["核酸", "rna", "dna", "sirna", "oligonucleotide", "寡核苷酸"]),
        ("polymorph", 105, ["晶型", "多晶型", "polymorph", "crystal form", "crystalline form"]),
        ("dosage_regimen", 95, ["给药方案", "给药间隔", "剂量方案", "dosage regimen", "dose regimen"]),
        ("formulation", 90, ["制剂", "片剂", "胶囊", "注射液", "formulation", "tablet", "capsule"]),
        ("medical_use", 85, ["医药用途", "用途", "适应症", "治疗", "medical use", "method of treatment", "treating"]),
        ("process", 80, ["制备方法", "制备工艺", "manufacturing process", "preparation process"]),
        ("composition", 70, ["组合物", "composition"]),
        ("compound", 65, ["化合物", "衍生物", "compound", "markush", "genus"]),
        ("method", 50, ["检测方法", "分析方法", "method for detecting", "assay method"]),
    ]
    for tag, weight, needles in weighted_patterns:
        for needle in needles:
            if needle.lower() in lower:
                scores[tag] += weight

    patent_title = extract_first(
        [
            r"(?:专利名称|发明名称|名称)[:：]\s*([^，。；;\n]{2,120})",
            r"涉案专利(?:名称)?(?:为|名称为)[:：]?\s*([^，。；;\n]{2,120})",
        ],
        front,
    )
    if patent_title:
        title_lower = patent_title.lower()
        for tag, weight, needles in weighted_patterns:
            if any(needle.lower() in title_lower for needle in needles):
                scores[tag] += weight * 2

    best_tag, best_score = max(scores.items(), key=lambda item: item[1])
    if best_score <= 0:
        return "other", "未在专利名称、发明名称或首页信息中识别出稳定的专利类型。"
    basis = patent_title or first_matching_sentence(front, RULES["patent_type"].get(best_tag, []))
    return best_tag, basis[:240]


def infer_evidence_types(text: str, title: str) -> list[str]:
    evidence_window = extract_relevant_windows(
        f"{title}\n{text}",
        ["证据", "附件", "exhibit", "declaration", "prior art", "reference"],
        window=1200,
        limit=8,
    )
    return match_tags("evidence_types", evidence_window)


def infer_legal_issues(text: str, title: str, region: str) -> tuple[list[str], list[dict[str, str]]]:
    haystack = f"{title}\n{text}"
    focused = extract_legal_focus_text(haystack, region)
    lower = focused.lower()
    scores: dict[str, int] = {tag: 0 for tag in RULES["legal_issues"]}
    basis: dict[str, str] = {}

    legal_patterns: list[tuple[str, int, list[str]]] = [
        ("inventive_step", 100, ["创造性", "显而易见", "inventive step", "obviousness", "obvious"]),
        ("novelty", 95, ["新颖性", "不具备新颖性", "novelty", "anticipation", "anticipated"]),
        ("enablement", 90, ["专利法第26条第3款", "第二十六条第三款", "充分公开", "能够实现", "enablement", "enabled"]),
        ("written_description", 90, ["专利法第26条第4款", "第二十六条第四款", "说明书支持", "得不到说明书支持", "written description"]),
        ("claim_construction", 80, ["权利要求解释", "保护范围", "权利要求的解释", "claim interpretation"]),
        ("priority", 75, ["优先权不成立", "不享有优先权", "优先权是否成立", "priority challenge", "not entitled to priority"]),
        ("amendment", 75, ["修改超范围", "专利法第33条", "new matter", "amendment"]),
        ("experimental_data", 55, ["实验数据", "试验数据", "experimental data", "test data"]),
        ("post_filing_data", 55, ["申请日后", "补交实验数据", "post-filing", "post filing"]),
        ("common_general_knowledge", 55, ["公知常识", "common general knowledge"]),
        ("motivation_to_combine", 50, ["结合动机", "motivation to combine"]),
        ("reasonable_expectation_of_success", 50, ["合理成功预期", "reasonable expectation"]),
        ("unexpected_effect", 50, ["预料不到", "unexpected effect", "unexpected results"]),
        ("dosage_regimen", 35, ["给药方案", "dosage regimen"]),
        ("medical_use", 35, ["医药用途", "medical use", "method of treatment"]),
        ("polymorph", 30, ["晶型", "polymorph"]),
        ("selection_invention", 30, ["选择发明", "selection invention"]),
    ]
    for tag, weight, needles in legal_patterns:
        for needle in needles:
            if needle.lower() in lower:
                scores[tag] += weight
                basis.setdefault(tag, first_matching_sentence(focused, needles)[:260])

    apply_strict_legal_filters(scores, focused, region)
    selected = [tag for tag, score in sorted(scores.items(), key=lambda item: item[1], reverse=True) if score >= 75]
    secondary = [tag for tag, score in sorted(scores.items(), key=lambda item: item[1], reverse=True) if 45 <= score < 75]
    if selected:
        selected = selected[:3]
    elif secondary:
        selected = secondary[:2]
    else:
        selected = []
    return selected, [{"tag": tag, "basis": basis.get(tag, "")} for tag in selected]


def apply_strict_legal_filters(scores: dict[str, int], focused: str, region: str) -> None:
    lower = focused.lower()
    if region == "US":
        if not re.search(
            r"(we\s+(?:construe|interpret)|construction\s+(?:is|of)|ordinary\s+meaning|plain\s+meaning|means\s+that)",
            lower,
        ):
            scores["claim_construction"] = 0
        if not re.search(
            r"(not\s+entitled\s+to\s+priority|priority\s+(?:challenge|claim|date)\s+(?:fails|is disputed|is not)|earlier\s+priority)",
            lower,
        ):
            scores["priority"] = 0
        if "written description" in lower and not re.search(r"(lacks?|lack of|fails?|failure).*written description|written description.*(?:lacks?|fails?)", lower):
            scores["written_description"] = min(scores["written_description"], 40)
        if "enablement" in lower and not re.search(r"(not enabled|lack of enablement|fails? to enable|enablement requirement)", lower):
            scores["enablement"] = min(scores["enablement"], 40)
    else:
        if "优先权" in focused and not re.search(r"优先权.{0,30}(不成立|不能享有|是否成立|不予认可|不能成立)", focused):
            scores["priority"] = 0
        if "权利要求解释" not in focused and "保护范围" not in focused and "解释为" not in focused:
            scores["claim_construction"] = 0


def focused_front_matter(text: str, title: str) -> str:
    normalized = re.sub(r"\s+", " ", f"{title}\n{text[:12000]}").strip()
    windows = extract_relevant_windows(
        normalized,
        ["专利名称", "发明名称", "名称", "涉案专利", "patent no", "u.s. patent", "challenged patent"],
        window=800,
        limit=6,
    )
    return windows or normalized[:8000]


def extract_legal_focus_text(text: str, region: str) -> str:
    if region == "CN":
        anchors = [
            "决定要点", "决定如下", "审查决定", "无效宣告请求的理由", "无效理由", "争议焦点",
            "关于", "合议组认为", "专利法第", "第二十二条", "第二十六条", "第三十三条",
            "创造性", "新颖性", "说明书是否", "权利要求是否",
        ]
    else:
        anchors = [
            "final written decision", "grounds", "analysis", "conclusion", "claim construction",
            "obviousness", "anticipation", "written description", "enablement", "priority",
        ]
    focused = extract_relevant_windows(text, anchors, window=1800, limit=18)
    return focused or re.sub(r"\s+", " ", text[:30000])


def extract_relevant_windows(text: str, anchors: list[str], window: int = 1200, limit: int = 10) -> str:
    normalized = re.sub(r"\s+", " ", text)
    lower = normalized.lower()
    pieces: list[str] = []
    seen: set[tuple[int, int]] = set()
    for anchor in anchors:
        start = 0
        anchor_lower = anchor.lower()
        while len(pieces) < limit:
            pos = lower.find(anchor_lower, start)
            if pos < 0:
                break
            left = max(0, pos - window // 2)
            right = min(len(normalized), pos + window)
            key = (left, right)
            if key not in seen:
                seen.add(key)
                pieces.append(normalized[left:right])
            start = pos + len(anchor)
    return "\n".join(pieces)


def first_matching_sentence(text: str, needles: list[str]) -> str:
    compact = re.sub(r"\s+", " ", text)
    sentences = re.split(r"(?<=[。！？.!?；;])\s+", compact)
    for sentence in sentences:
        sentence_lower = sentence.lower()
        if any(needle.lower() in sentence_lower for needle in needles):
            return sentence.strip()
    return ""


def contains_any(text: str, needles: list[str]) -> bool:
    text_lower = text.lower()
    return any(needle.lower() in text_lower for needle in needles)


def classify_doc_type(text: str, metadata: dict[str, Any]) -> str:
    title = metadata.get("title", "")
    region = metadata.get("region", "")
    haystack = f"{title}\n{text[:30000]}"
    normalized = normalize_text_for_hash(haystack)

    link_markers = ["http://", "https://", "下载", "附件", "链接", "目录", "跳转", "download", "attachment"]
    substantive_markers = [
        "本院认为", "决定如下", "判决如下", "final written decision", "analysis", "conclusion",
        "obviousness", "written description", "enablement", "claim construction",
    ]
    url_count = len(re.findall(r"https?://|www\.", haystack, flags=re.I))
    if len(normalized) < MIN_SUBSTANTIVE_CHARS and (
        url_count >= 2 or contains_any(haystack, link_markers)
    ) and not contains_any(haystack, substantive_markers):
        return "link_or_notice"

    cn_invalidity = [
        "无效宣告请求审查决定", "国家知识产权局", "专利复审委员会", "请求人", "专利权人",
        "决定号", "宣告专利权无效", "维持专利权有效", "在修改后的权利要求基础上维持有效",
    ]
    cn_court = [
        "行政判决书", "行政裁定书", "北京市知识产权法院", "最高人民法院",
        "中华人民共和国最高人民法院", "上诉人", "被上诉人", "原审第三人",
        "一审行政判决", "二审行政判决", "再审", "本院认为", "判决如下",
    ]
    us_ptab = [
        "final written decision", "inter partes review", "post-grant review",
        "covered business method", "patent trial and appeal board", "petitioner",
        "patent owner", "35 u.s.c.", "ipr", "pgr", "cbm",
    ]
    us_court = [
        "united states court of appeals for the federal circuit", "federal circuit",
        "district court", "appeal from the united states patent and trademark office",
        "patent trial and appeal board", "affirmed", "reversed", "vacated", "remanded",
    ]

    if region == "CN" and contains_any(haystack, cn_court):
        return "appeal_decision" if contains_any(haystack, ["上诉", "再审", "二审"]) else "court_judgment"
    if region == "CN" and contains_any(haystack, cn_invalidity):
        return "invalidity_decision"
    if region == "US" and contains_any(haystack, us_court):
        return "court_judgment"
    if region == "US" and contains_any(haystack, us_ptab):
        return "invalidity_decision"
    if contains_any(haystack, substantive_markers):
        return "litigation_related"
    if len(normalized) < MIN_SUBSTANTIVE_CHARS:
        return "other"
    return "other"


def has_substantive_analysis(text: str) -> bool:
    return contains_any(
        text,
        [
            "本院认为", "决定如下", "判决如下", "理由如下", "合议组认为",
            "final written decision", "analysis", "conclusion", "obviousness",
            "written description", "enablement", "claim construction",
        ],
    )


def should_include_document(text: str, metadata: dict[str, Any]) -> tuple[bool, str]:
    doc_type = metadata.get("doc_type", "other")
    needs_ocr = bool(metadata.get("needs_ocr", False))
    normalized_len = len(normalize_text_for_hash(text))

    if doc_type == "link_or_notice":
        return False, "link_only"
    if needs_ocr and normalized_len < MIN_SUBSTANTIVE_CHARS:
        return False, "needs_ocr_review"
    if doc_type in {"invalidity_decision", "court_judgment", "appeal_decision", "litigation_related"}:
        if normalized_len >= MIN_SUBSTANTIVE_CHARS or has_substantive_analysis(text):
            return True, ""
        return False, "too_short_or_no_substantive_content"
    if normalized_len < MIN_SUBSTANTIVE_CHARS and not has_substantive_analysis(text):
        return False, "too_short_or_no_substantive_content"
    return False, "needs_manual_review"


def extract_first(patterns: list[str], text: str, flags: int = 0) -> str:
    for pattern in patterns:
        match = re.search(pattern, text, flags)
        if match:
            return re.sub(r"\s+", " ", match.group(1)).strip(" ：:，,。.;；")
    return ""


def extract_case_metadata(text: str, title: str, region: str, doc_type: str) -> dict[str, str | list[str]]:
    sample = re.sub(r"\s+", " ", f"{title}\n{text[:50000]}")
    lower = sample.lower()
    patent_number = ""
    decision_number = ""
    proceeding_number = ""

    if region == "CN":
        patent_number = extract_first(
            [r"专利号[:：]?\s*([ZzLlCcNn0-9.\-]{6,30})", r"\b(CN\s*\d{6,15}[A-Z]?)\b"],
            sample,
            re.I,
        )
        decision_number = extract_first(
            [r"决定号[:：]?\s*([第0-9国知药裁（）()\-\s号]{3,40})", r"(\(\d{4}\)\s*国知药裁\s*\d+\s*号)"],
            sample,
        )
        court_case_number = extract_first([r"案号[:：]?\s*([（(]\d{4}[）)][^，。；;\s]{2,40})"], sample)
        court_name = extract_first(
            [r"((?:中华人民共和国)?最高人民法院|北京市知识产权法院|北京知识产权法院|[^，。；;\s]{2,20}人民法院)"],
            sample,
        )
        litigation_stage = infer_cn_stage(sample, doc_type)
        petitioner = extract_first([r"请求人[:：]\s*([^，。；;]{2,80})"], sample)
        owner = extract_first([r"专利权人[:：]\s*([^，。；;]{2,80})"], sample)
        patent_title = extract_first([r"(?:发明名称|名称)[:：]\s*([^，。；;]{2,120})"], sample)
    else:
        proceeding_number = extract_first([r"\b((?:IPR|PGR|CBM)\d{4}-\d{5})\b"], sample, re.I).upper()
        patent_number = extract_first(
            [r"patent\s*(?:no\.)?\s*([0-9,]{7,12})", r"U\.S\.\s*Patent\s*(?:No\.)?\s*([0-9,]{7,12})"],
            sample,
            re.I,
        )
        court_case_number = extract_first([r"\b(No\.\s*[0-9A-Za-z.\-]+)\b"], sample)
        court_name = extract_first(
            [
                r"(United States Court of Appeals for the Federal Circuit)",
                r"(Federal Circuit)",
                r"(United States District Court[^,\n]*)",
                r"(Supreme Court of the United States)",
            ],
            sample,
            re.I,
        )
        litigation_stage = infer_us_stage(lower, doc_type)
        petitioner = extract_first([r"Petitioner[:\s]+([A-Z][A-Za-z0-9&.,\- ]{2,80})"], sample)
        owner = extract_first([r"Patent Owner[:\s]+([A-Z][A-Za-z0-9&.,\- ]{2,80})"], sample)
        patent_title = ""

    judgment_date = extract_first(
        [
            r"(\d{4}\s*年\s*\d{1,2}\s*月\s*\d{1,2}\s*日)",
            r"(\b(?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2},\s+\d{4}\b)",
            r"(\b\d{4}-\d{1,2}-\d{1,2}\b)",
        ],
        sample,
        re.I,
    )
    case_number = court_case_number or proceeding_number or decision_number
    return {
        "patent_number": patent_number,
        "patent_title": patent_title,
        "decision_number": decision_number,
        "proceeding_number": proceeding_number,
        "court_case_number": court_case_number,
        "court_name": court_name,
        "judgment_date": judgment_date,
        "litigation_stage": litigation_stage,
        "case_number": case_number,
        "petitioner": petitioner,
        "patentee_or_patent_owner": owner,
        "related_patent_numbers": [patent_number] if patent_number else [],
        "related_decision_numbers": [value for value in [decision_number, proceeding_number] if value],
    }


def infer_cn_stage(text: str, doc_type: str) -> str:
    if "再审" in text:
        return "retrial"
    if "二审" in text or "上诉" in text:
        return "second_instance"
    if "一审" in text:
        return "first_instance"
    if doc_type == "invalidity_decision":
        return "invalidity_proceeding"
    return "other"


def infer_us_stage(text: str, doc_type: str) -> str:
    if "supreme court" in text:
        return "supreme_court"
    if "federal circuit" in text:
        return "federal_circuit"
    if "district court" in text:
        return "district_court"
    if doc_type == "invalidity_decision" or "patent trial and appeal board" in text:
        return "ptab"
    return "other"


def extract_keywords(text: str, title: str, limit: int = 16) -> list[str]:
    candidates = [
        "创造性", "新颖性", "充分公开", "优先权", "实验数据", "公知常识", "晶型",
        "抗体", "核酸", "细胞治疗", "化合物", "制剂", "用途", "行政判决", "上诉",
        "obviousness", "novelty", "enablement", "written description", "priority",
        "unexpected results", "polymorph", "antibody", "formulation", "compound",
        "Federal Circuit", "Final Written Decision",
    ]
    haystack = f"{title}\n{text}".lower()
    return [kw for kw in candidates if kw.lower() in haystack][:limit]


def summarize_text(text: str, needs_ocr: bool) -> str:
    if needs_ocr and not text.strip():
        return "该 PDF 可能为扫描件，当前未提取到可用文本。请后续接入 OCR 或人工补充摘要。"
    normalized = re.sub(r"\s+", " ", text).strip()
    if not normalized:
        return "暂无自动摘要。"
    return normalized[:420] + ("..." if len(normalized) > 420 else "")


def extract_key_holdings(text: str, legal_issues: list[str], needs_ocr: bool) -> list[str]:
    if needs_ocr and not text.strip():
        return ["需 OCR 后补充关键结论。"]

    sentences = re.split(r"(?<=[。！？.!?])\s+", re.sub(r"\s+", " ", text))
    needles = [
        "无效", "维持有效", "不具备创造性", "具备创造性", "显而易见", "本院认为",
        "判决如下", "not unpatentable", "unpatentable", "obvious", "anticipated",
        "enabled", "written description", "affirmed", "reversed", "vacated",
    ]
    holdings = [
        s.strip()
        for s in sentences
        if 20 <= len(s.strip()) <= 260 and any(n.lower() in s.lower() for n in needles)
    ]
    if holdings:
        return holdings[:3]
    if legal_issues:
        return [f"自动识别的争议点：{', '.join(legal_issues)}。请人工复核关键结论。"]
    return ["暂无自动提取的关键结论，请人工复核。"]


def extract_important_quotes(text: str) -> list[str]:
    sentences = re.split(r"(?<=[。！？.!?])\s+", re.sub(r"\s+", " ", text))
    markers = [
        "预料不到", "公知常识", "合理成功预期", "本院认为", "unexpected",
        "reasonable expectation", "motivation", "affirmed", "reversed",
    ]
    quotes = [
        s.strip()
        for s in sentences
        if 30 <= len(s.strip()) <= 280 and any(m.lower() in s.lower() for m in markers)
    ]
    return quotes[:3]


def infer_outcome(text: str) -> str:
    haystack = text.lower()
    if "全部无效" in text or "claims are unpatentable" in haystack:
        return "invalidated"
    if "部分无效" in text or "partially" in haystack:
        return "partially_invalidated"
    if "维持有效" in text or "not unpatentable" in haystack or "affirmed" in haystack:
        return "maintained"
    if "reversed" in haystack:
        return "reversed"
    if "vacated" in haystack:
        return "vacated"
    return "unknown"


def make_case_record(
    *,
    case_id: str,
    pdf_path: Path,
    public_pdf_path: str,
    output_text_path: Path,
    region: str,
    text: str,
    needs_ocr: bool,
    file_hash: str = "",
    existing_record: dict[str, Any] | None = None,
) -> dict[str, Any]:
    title = pdf_path.stem
    haystack = f"{pdf_path.name}\n{text[:20000]}"
    metadata = {"title": title, "region": region, "needs_ocr": needs_ocr}
    doc_type = classify_doc_type(text, metadata)
    include_in_kb, exclude_reason = should_include_document(text, {**metadata, "doc_type": doc_type})
    case_metadata = extract_case_metadata(text, title, region, doc_type)
    auto_tags = classify_case_tags(text, title, region)
    legal_issues = auto_tags["legal_issues"]
    patent_type = auto_tags["patent_type"]
    evidence_types = auto_tags["evidence_types"]
    created_at = (existing_record or {}).get("created_at") or now_iso()
    review_status = (existing_record or {}).get("review_status") or (
        "needs_manual_review" if exclude_reason in {"needs_manual_review", "needs_ocr_review"} else "auto_tagged"
    )

    record: dict[str, Any] = {
        "id": case_id,
        "title": title,
        "doc_type": doc_type,
        "include_in_kb": include_in_kb,
        "exclude_reason": exclude_reason,
        "region": region,
        "country_label": "中国" if region == "CN" else "美国",
        "source_file": str(pdf_path),
        "pdf_path": public_pdf_path,
        "text_path": (Path("..") / output_text_path).as_posix(),
        "language": detect_language(region, text),
        "case_type": doc_type,
        "patent_type": patent_type,
        "patent_type_basis": auto_tags["patent_type_basis"],
        "legal_issues": legal_issues,
        "legal_issue_basis": auto_tags["legal_issue_basis"],
        "keywords": extract_keywords(text, title),
        "summary": summarize_text(text, needs_ocr),
        "key_holdings": extract_key_holdings(text, legal_issues, needs_ocr),
        "evidence_types": evidence_types,
        "outcome": infer_outcome(text),
        "important_quotes": extract_important_quotes(text),
        "related_case_ids": (existing_record or {}).get("related_case_ids", []),
        "suspected_related_cases": (existing_record or {}).get("suspected_related_cases", []),
        "needs_ocr": needs_ocr,
        "review_status": review_status,
        "created_at": created_at,
        "updated_at": now_iso(),
    }
    record.update(case_metadata)
    ensure_dedupe_fields(record)
    record["file_hash"] = file_hash or (existing_record or {}).get("file_hash", "")
    record["content_hash"] = content_hash(text) or (existing_record or {}).get("content_hash", "")
    record["canonical_case_id"] = (existing_record or {}).get("canonical_case_id") or case_id
    record["is_duplicate"] = bool((existing_record or {}).get("is_duplicate", False))
    record["duplicate_of"] = (existing_record or {}).get("duplicate_of", "")
    record["duplicate_reason"] = (existing_record or {}).get("duplicate_reason", "")
    record["duplicate_files"] = (existing_record or {}).get("duplicate_files", [])
    record["suspected_duplicates"] = (existing_record or {}).get("suspected_duplicates", [])
    record["dedupe_identifiers"] = extract_identifiers(text, title, region)
    if record["is_duplicate"]:
        record["include_in_kb"] = False
        record["exclude_reason"] = record.get("duplicate_reason") or "duplicate"
    return record
