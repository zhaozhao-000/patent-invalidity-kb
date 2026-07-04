from __future__ import annotations

import re
from pathlib import Path
from typing import Any


PARTY_STOPWORDS = re.compile(
    r"trials@|united states patent|patent trial and appeal board|administrative patent judge|"
    r"judge|attorney|counsel|law firm|llp|p\.c\.|address|telephone|facsimile|email|@|"
    r"before the patent trial|trademark office",
    re.I,
)


def compact(text: str, limit: int | None = None) -> str:
    value = re.sub(r"\s+", " ", str(text or "")).strip(" \t\r\n,;:.")
    if limit and len(value) > limit:
        return value[:limit].rstrip(" ,;:.")
    return value


def normalize_us_patent_number(value: str) -> str:
    raw = str(value or "").upper().replace(",", "")
    pub = re.search(r"\bUS\s*(20\d{2})\s*/?\s*(\d{7})\s*([A-Z]\d)?\b", raw)
    if pub:
        return f"US{pub.group(1)}{pub.group(2)}{pub.group(3) or ''}"
    compacted = re.sub(r"[^A-Z0-9]", "", raw)
    pub2 = re.search(r"US(20\d{9})([A-Z]\d)?", compacted)
    if pub2:
        return f"US{pub2.group(1)}{pub2.group(2) or ''}"
    match = re.search(r"(?:US|USPATENTNO|USPATENT|PATENTNO|PATENT)?(\d{7,11})([A-Z]\d)?", compacted)
    if not match:
        return ""
    number = match.group(1)
    if number.startswith(("20", "19")) and len(number) >= 11:
        return ""
    return f"US{number}{match.group(2) or ''}"


def extract_us_patent_numbers(text: str, filename: str = "", existing: str = "") -> dict[str, Any]:
    sources = [
        ("challenged_patent", text[:12000]),
        ("pdf_text", text[:50000]),
        ("filename", filename),
        ("manual", existing),
    ]
    patterns = [
        r"(?:challenging|challenges|review of|claims?\s+\d+[^\n]{0,80}\s+of)\s+U\.?S\.?\s+Patent\s+(?:No\.?\s*)?([0-9,]{7,12}\s*(?:[A-Z]\d)?)",
        r"U\.?S\.?\s+Patent\s+(?:No\.?\s*)?([0-9,]{7,12}\s*(?:[A-Z]\d)?)",
        r"US\s*Patent\s+(?:No\.?\s*)?([0-9,]{7,12}\s*(?:[A-Z]\d)?)",
        r"Patent\s+No\.?\s*([0-9,]{7,12}\s*(?:[A-Z]\d)?)",
        r"\bPatent\s+([0-9,]{7,12}\s*(?:[A-Z]\d)?)",
        r"\bUS\s*([0-9,]{7,12})\s*([A-Z]\d)\b",
        r"\bUS([0-9]{7,11})([A-Z]\d)?\b",
        r"U\.?S\.?\s+Patent\s+Application\s+Publication\s+No\.?\s*([0-9]{4}/[0-9]{7})",
        r"\bUS(20[0-9]{9})([A-Z]\d)?\b",
    ]
    seen: list[str] = []
    evidence = ""
    source = "unknown"
    for source_name, haystack in sources:
        for pattern in patterns:
            for match in re.finditer(pattern, haystack or "", re.I):
                groups = [g for g in match.groups() if g]
                number = normalize_us_patent_number(" ".join(groups))
                if not number:
                    continue
                if re.search(r"IPR|PGR|CBM", match.group(0), re.I):
                    continue
                if number not in seen:
                    seen.append(number)
                    if not evidence:
                        evidence = compact(match.group(0), 220)
                        source = source_name
        if seen and source_name in {"challenged_patent", "filename", "manual"}:
            break
    return {
        "patent_number": seen[0] if seen else "",
        "patent_numbers": seen,
        "main_patent_number": seen[0] if seen else "",
        "patent_number_source": source,
        "patent_number_confidence": 0.9 if source == "challenged_patent" else (0.75 if seen else 0.0),
        "patent_number_evidence": evidence,
    }


def clean_party(value: str) -> str:
    value = compact(value, 160)
    embedded = re.search(r"\bPetitioner\s+([A-Z][A-Za-z0-9&.,'’\- ]{2,120})$", value)
    if embedded and re.search(r"for the reasons|we determine|set forth below", value, re.I):
        value = embedded.group(1)
    value = re.sub(r"^(?:and|v\.?|vs\.?)\s+", "", value, flags=re.I)
    value = re.sub(r"^Petitioner\s+", "", value, flags=re.I)
    value = re.sub(r"\s+(?:Petitioner|Patent Owner|Plaintiff|Defendant)s?\.?$", "", value, flags=re.I)
    value = compact(value, 120).strip(" ?�")
    if re.search(r"\b(to prevail|would prevail|challenging claims|petition establishes|we determine|set forth below|after institution|filed a|in turn|owned by)\b", value, re.I):
        return ""
    if not value or PARTY_STOPWORDS.search(value):
        return ""
    if len(value.split()) > 14:
        return ""
    return value


def first(patterns: list[str], text: str, flags: int = re.I | re.S) -> str:
    for pattern in patterns:
        match = re.search(pattern, text, flags)
        if match:
            value = clean_party(match.group(1))
            if value:
                return value
    return ""


def section_between(text: str, headings: list[str], stop_headings: list[str]) -> str:
    heading_pattern = "|".join(re.escape(h) for h in headings)
    stop_pattern = "|".join(re.escape(h) for h in stop_headings)
    match = re.search(rf"(?:^|\n)#+\s*(?:{heading_pattern})\b(.*?)(?=\n#+\s*(?:{stop_pattern})\b|\Z)", text, re.I | re.S)
    return compact(match.group(1), 2500) if match else ""


def parse_ptab_decision(text: str, filename: str = "", existing_patent_number: str = "") -> dict[str, Any]:
    front = text[:14000]
    trial = re.search(r"\b(IPR|PGR|CBM)\d{4}-\d{5}\b", f"{filename}\n{front}", re.I)
    paper = re.search(r"\bPaper\s+(\d+)\b", front, re.I)
    patent_numbers = extract_us_patent_numbers(text, filename, existing_patent_number)
    caption_match = re.search(
        r"BOARD\s+(.{2,220}?)(?:,)?\s*Petitioners?,?\.?\s*(?:v\.?\s*)?#?\s*(.{2,180}?),?\s*Patent Owner",
        front,
        re.I | re.S,
    )
    petitioner_only_caption = re.search(r"BOARD\s+(.{2,220}?),\s*Petitioners?,", front, re.I | re.S)
    petitioner = first(
        [
            r"Petitioner,\s*([A-Z][A-Za-z0-9&.,'’\- ]{2,120}),\s*filed",
            r"([A-Z][A-Za-z0-9&.,'’\- ]{2,120})\s+\([\"“]?Petitioner[\"”]?\)",
            r"([A-Z][A-Z0-9&.,'’\- ]{2,120}),\s*Petitioner",
            r"Petitioner[:\s]+([A-Z][A-Za-z0-9&.,'’\- ]{2,120})",
        ],
        front,
    )
    patent_owner = first(
        [
            r"Patent Owner,\s*([A-Z][A-Za-z0-9&.,'’\- ]{2,120}),\s*(?:did|filed|timely)",
            r"Patent Owner\s+([A-Z][A-Za-z0-9&.,'’\- ]{2,120})[’']?s",
            r"([A-Z][A-Za-z0-9&.,'’\- ]{2,120})\s+\([\"“]?Patent Owner[\"”]?\)",
            r"v\.\s*([A-Z][A-Z0-9&.,'’\- ]{2,120}),\s*Patent Owner",
            r"([A-Z][A-Z0-9&.,'’\- ]{2,120}),\s*Patent Owner",
            r"Patent Owner[:\s]+([A-Z][A-Za-z0-9&.,'’\- ]{2,120})",
            r"Patent Owner,\s*([A-Z][A-Za-z0-9&.,'’\- ]{2,120}),",
        ],
        front,
    )
    if caption_match:
        caption_petitioner = clean_party(caption_match.group(1))
        caption_owner = clean_party(caption_match.group(2))
        petitioner = caption_petitioner or petitioner
        patent_owner = caption_owner or patent_owner
    elif petitioner_only_caption:
        petitioner = clean_party(petitioner_only_caption.group(1)) or petitioner
    decision_type = "Other"
    if re.search(r"Final Written Decision|35\s+U\.S\.C\.\s+§?\s*318", front, re.I):
        decision_type = "Final Written Decision"
    elif re.search(r"Decision\s+(?:Granting|Denying)?\s*Institution|Institution of Inter Partes Review|35\s+U\.S\.C\.\s+§?\s*314", front, re.I):
        decision_type = "Institution Decision"
    elif re.search(r"rehearing", front, re.I):
        decision_type = "Rehearing Decision"
    elif re.search(r"termination|terminated", front, re.I):
        decision_type = "Termination"
    challenged_claims = compact(
        (re.search(r"(?:review of|challenging|challenges)\s+(claims?[^.]{1,160})\s+of\s+U\.?S\.?\s+Patent", front, re.I | re.S) or [None, ""])[1],
        220,
    )
    asserted = []
    for law in ["§ 101", "§ 102", "§ 103", "§ 112", "35 U.S.C. § 101", "35 U.S.C. § 102", "35 U.S.C. § 103", "35 U.S.C. § 112"]:
        if law.lower() in text[:60000].lower() and law not in asserted:
            asserted.append(law)
    outcome = "unknown"
    low = text[-12000:].lower()
    if "unpatentable" in low and "not unpatentable" not in low:
        outcome = "claims unpatentable"
    if "not unpatentable" in low:
        outcome = "claims not unpatentable"
    if "institution denied" in low or "deny institution" in low:
        outcome = "institution denied"
    if "institution granted" in low or "institute inter partes review" in low:
        outcome = "institution granted"
    stops = ["BACKGROUND", "THE CHALLENGED PATENT", "RELATED MATTERS", "REAL PARTIES", "ASSERTED GROUNDS", "ANALYSIS", "CONCLUSION", "ORDER"]
    key_sections = {
        "introduction": section_between(text, ["I. INTRODUCTION", "INTRODUCTION"], stops),
        "background": section_between(text, ["BACKGROUND"], stops),
        "challenged_patent": section_between(text, ["THE CHALLENGED PATENT", "The '", "The Challenged Patent"], stops),
        "asserted_grounds": section_between(text, ["ASSERTED GROUNDS", "Instituted Challenges to Patentability", "Grounds"], stops),
        "analysis": section_between(text, ["ANALYSIS"], ["CONCLUSION", "ORDER"]),
        "conclusion": section_between(text, ["CONCLUSION"], ["ORDER"]),
        "order": section_between(text, ["ORDER"], []),
    }
    return {
        "proceeding_type": trial.group(1).upper() if trial else "PTAB",
        "proceeding_number": trial.group(0).upper() if trial else "",
        "paper_number": paper.group(1) if paper else "",
        "decision_type": decision_type,
        "petitioner": petitioner,
        "patent_owner": patent_owner,
        "real_parties_in_interest": [],
        "patent_numbers": patent_numbers["patent_numbers"],
        "challenged_claims": challenged_claims,
        "asserted_grounds": asserted,
        "outcome": outcome,
        "key_sections": key_sections,
        "evidence": {
            "proceeding": trial.group(0) if trial else "",
            "patent_number": patent_numbers["patent_number_evidence"],
            "petitioner": petitioner,
            "patent_owner": patent_owner,
        },
        **patent_numbers,
    }


def parse_court_decision(text: str, filename: str = "", existing_patent_number: str = "") -> dict[str, Any]:
    front = text[:12000]
    patent_numbers = extract_us_patent_numbers(text, filename, existing_patent_number)
    court = ""
    for pattern in [
        r"UNITED STATES DISTRICT COURT\s+([A-Z ,]+)",
        r"United States Court of Appeals\s+for the\s+([A-Za-z ]+)",
        r"Supreme Court of the United States",
        r"International Trade Commission",
    ]:
        match = re.search(pattern, front, re.I)
        if match:
            court = compact(match.group(0), 140)
            break
    proceeding_type = "Other"
    if "district court" in court.lower():
        proceeding_type = "District Court"
    elif "court of appeals" in court.lower() or "federal circuit" in front.lower():
        proceeding_type = "Federal Circuit"
    elif "supreme court" in court.lower():
        proceeding_type = "Supreme Court"
    elif "trade commission" in court.lower():
        proceeding_type = "ITC"
    case_number = compact((re.search(r"(?:Case|Civil Action|No\.)\s*(?:No\.)?\s*([0-9A-Za-z:.\-cvCV]+)", front) or [None, ""])[1], 80)
    plaintiff = first([r"([A-Z][A-Z0-9&.,'’\- ]{2,120}),\s*Plaintiff", r"([A-Z][A-Z0-9&.,'’\- ]{2,120})\s+v\."], front)
    defendant = first([r"([A-Z][A-Z0-9&.,'’\- ]{2,120}),\s*Defendant", r"v\.\s*([A-Z][A-Z0-9&.,'’\- ]{2,120})"], front)
    decision_type = "Other"
    if re.search(r"\bOPINION\b", front, re.I):
        decision_type = "Opinion"
    elif re.search(r"\bORDER\b", front, re.I):
        decision_type = "Order"
    elif re.search(r"\bJUDGMENT\b", front, re.I):
        decision_type = "Judgment"
    elif re.search(r"claim construction|Markman", front, re.I):
        decision_type = "Claim Construction"
    return {
        "proceeding_type": proceeding_type,
        "court": court,
        "case_number": case_number,
        "plaintiff": plaintiff,
        "defendant": defendant,
        "patent_numbers": patent_numbers["patent_numbers"],
        "decision_type": decision_type,
        "outcome": "unknown",
        "key_sections": {},
        **patent_numbers,
    }


def parse_us_case(text: str, filename: str = "", existing_patent_number: str = "") -> dict[str, Any]:
    haystack = f"{filename}\n{text[:12000]}"
    if re.search(r"\b(IPR|PGR|CBM)\d{4}-\d{5}\b|PATENT TRIAL AND APPEAL BOARD|inter partes review|post grant review", haystack, re.I):
        return parse_ptab_decision(text, filename, existing_patent_number)
    return parse_court_decision(text, filename, existing_patent_number)


if __name__ == "__main__":
    import json
    import sys

    path = Path(sys.argv[1])
    print(json.dumps(parse_us_case(path.read_text(encoding="utf-8", errors="ignore"), path.name), ensure_ascii=False, indent=2))
