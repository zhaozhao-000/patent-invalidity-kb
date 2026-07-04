from __future__ import annotations

import hashlib
import json
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from build_index import write_index
from classify_case import make_case_record
from dedupe import (
    append_unique,
    content_hash,
    ensure_dedupe_fields,
    extract_identifiers,
    record_duplicate_file,
    suspected_duplicate_ids,
    write_json,
)
from extract_text import extract_pdf_text
from manifest import (
    case_for_content_hash,
    case_for_file_hash,
    load_manifest,
    register_content_hash,
    save_manifest,
    status_for_record,
    upsert_case,
    upsert_file,
)


ROOT = Path(__file__).resolve().parents[1]
INPUT_DIRS = {
    "CN": ROOT / "input_pdfs" / "cn",
    "US": ROOT / "input_pdfs" / "us",
}
OUTPUT_TEXT_DIR = ROOT / "output" / "text"
OUTPUT_JSON_DIR = ROOT / "output" / "json"
PUBLIC_PDF_DIR = ROOT / "public" / "pdfs"


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def next_case_number() -> int:
    highest = 0
    for path in OUTPUT_JSON_DIR.glob("case_*.json"):
        try:
            highest = max(highest, int(path.stem.split("_")[1]))
        except (IndexError, ValueError):
            continue
    return highest + 1


def safe_public_pdf_name(region: str, case_id: str, source_name: str) -> str:
    suffix = Path(source_name).suffix.lower() or ".pdf"
    return f"{case_id}_{region.lower()}{suffix}"


def case_json_path(case_id: str) -> Path:
    return OUTPUT_JSON_DIR / f"{case_id}.json"


def find_existing_record(json_path: Path) -> dict[str, Any] | None:
    if not json_path.exists():
        return None
    with json_path.open("r", encoding="utf-8") as f:
        return json.load(f)


def load_case_records() -> dict[str, dict[str, Any]]:
    records: dict[str, dict[str, Any]] = {}
    for path in sorted(OUTPUT_JSON_DIR.glob("case_*.json")):
        with path.open("r", encoding="utf-8") as f:
            record = ensure_dedupe_fields(json.load(f))
        records[record["id"]] = record
    return records


def save_case_record(record: dict[str, Any]) -> None:
    write_json(case_json_path(record["id"]), record)


def text_file_for_record(record: dict[str, Any]) -> Path | None:
    text_path = str(record.get("text_path") or "")
    if not text_path:
        return None
    if text_path.startswith("../"):
        return (ROOT / "public" / text_path).resolve()
    return (ROOT / text_path).resolve()


def enrich_existing_cases(
    case_records: dict[str, dict[str, Any]],
    manifest: dict[str, Any],
) -> None:
    file_hash_by_case: dict[str, str] = {}
    for entry in manifest.get("files", {}).values():
        case_id = entry.get("case_id")
        if case_id and entry.get("file_hash"):
            file_hash_by_case.setdefault(case_id, entry["file_hash"])

    for record in case_records.values():
        before = json.dumps(record, sort_keys=True, ensure_ascii=False)
        ensure_dedupe_fields(record)
        case_id = record["id"]
        record["canonical_case_id"] = record.get("duplicate_of") or record.get("canonical_case_id") or case_id
        record["file_hash"] = record.get("file_hash") or file_hash_by_case.get(case_id, "")

        if not record.get("content_hash"):
            text_path = text_file_for_record(record)
            if text_path and text_path.exists():
                text = text_path.read_text(encoding="utf-8", errors="ignore")
                record["content_hash"] = content_hash(text)
                record["dedupe_identifiers"] = extract_identifiers(
                    text,
                    record.get("title", ""),
                    record.get("region", ""),
                )

        after = json.dumps(record, sort_keys=True, ensure_ascii=False)
        if before != after:
            save_case_record(record)


def sync_manifest_from_cases(
    manifest: dict[str, Any],
    case_records: dict[str, dict[str, Any]],
) -> None:
    for record in case_records.values():
        ensure_dedupe_fields(record)
        upsert_case(manifest, record)
        if record.get("content_hash") and not record.get("is_duplicate"):
            register_content_hash(manifest, record["content_hash"], record["id"])


def register_same_file_duplicate(
    *,
    pdf_path: Path,
    file_hash: str,
    master_id: str,
    case_records: dict[str, dict[str, Any]],
    manifest: dict[str, Any],
) -> dict[str, Any]:
    master = case_records.get(master_id) or find_existing_record(case_json_path(master_id))
    if master:
        record_duplicate_file(master, str(pdf_path), "same_file_hash")
        master["updated_at"] = now_iso()
        save_case_record(master)
        case_records[master_id] = master

    if master:
        upsert_case(manifest, master)
    entry = upsert_file(
        manifest,
        file_path=pdf_path,
        file_hash=file_hash,
        case_id=master_id,
        content_hash=(master or {}).get("content_hash", ""),
        status="duplicate",
        duplicate_of=master_id,
        duplicate_reason="same_file_hash",
    )
    return entry


def process_pdf(
    *,
    pdf_path: Path,
    region: str,
    file_hash: str,
    next_number: int,
    case_records: dict[str, dict[str, Any]],
    manifest: dict[str, Any],
) -> tuple[dict[str, Any], int, dict[str, Any]]:
    case_id = f"case_{next_number:04d}"
    next_number += 1

    output_text_path = OUTPUT_TEXT_DIR / f"{case_id}.txt"
    output_json_path = OUTPUT_JSON_DIR / f"{case_id}.json"
    public_pdf_name = safe_public_pdf_name(region, case_id, pdf_path.name)
    public_pdf_path = PUBLIC_PDF_DIR / public_pdf_name

    PUBLIC_PDF_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUT_JSON_DIR.mkdir(parents=True, exist_ok=True)
    shutil.copy2(pdf_path, public_pdf_path)

    extraction = extract_pdf_text(pdf_path, output_text_path)
    existing_record = find_existing_record(output_json_path)
    record = make_case_record(
        case_id=case_id,
        pdf_path=pdf_path,
        public_pdf_path=(Path("pdfs") / public_pdf_name).as_posix(),
        output_text_path=output_text_path.relative_to(ROOT),
        region=region,
        text=extraction["text"],
        needs_ocr=extraction["needs_ocr"],
        file_hash=file_hash,
        existing_record=existing_record,
    )
    record["ocr_text"] = extraction.get("ocr_text", "")
    record["ocr_status"] = extraction.get("ocr_status", record.get("ocr_status", ""))

    duplicate_master_id = case_for_content_hash(manifest, record.get("content_hash", ""))
    if duplicate_master_id and duplicate_master_id != case_id:
        record["is_duplicate"] = True
        record["duplicate_of"] = duplicate_master_id
        record["canonical_case_id"] = duplicate_master_id
        record["duplicate_reason"] = "same_content_hash"
        record["include_in_kb"] = False
        record["exclude_reason"] = "same_content_hash"
        master = case_records.get(duplicate_master_id)
        if master:
            record_duplicate_file(master, str(pdf_path), "same_content_hash")
            master["updated_at"] = now_iso()
            save_case_record(master)
    else:
        canonical_records = [item for item in case_records.values() if not item.get("is_duplicate")]
        record["suspected_duplicates"] = suspected_duplicate_ids(record, canonical_records)
        record["canonical_case_id"] = case_id
        if record["content_hash"]:
            register_content_hash(manifest, record["content_hash"], case_id)

        for suspected_id in record["suspected_duplicates"]:
            suspected = case_records.get(suspected_id)
            if suspected:
                append_unique(suspected.setdefault("suspected_duplicates", []), case_id)
                save_case_record(suspected)

    save_case_record(record)
    case_records[case_id] = record
    upsert_case(manifest, record)
    entry = upsert_file(
        manifest,
        file_path=pdf_path,
        file_hash=file_hash,
        case_id=case_id,
        content_hash=record.get("content_hash", ""),
        status=status_for_record(record),
        duplicate_of=record.get("duplicate_of", ""),
        duplicate_reason=record.get("duplicate_reason", ""),
    )
    entry["output_json_path"] = str(output_json_path.relative_to(ROOT))
    entry["output_text_path"] = str(output_text_path.relative_to(ROOT))
    entry["public_pdf_path"] = str(public_pdf_path.relative_to(ROOT))
    return entry, next_number, record


def scan_pdfs() -> list[tuple[str, Path]]:
    pdfs: list[tuple[str, Path]] = []
    for region, input_dir in INPUT_DIRS.items():
        input_dir.mkdir(parents=True, exist_ok=True)
        for path in sorted(input_dir.rglob("*.pdf")):
            pdfs.append((region, path))
    return pdfs


def main() -> int:
    manifest = load_manifest()
    case_records = load_case_records()
    enrich_existing_cases(case_records, manifest)
    sync_manifest_from_cases(manifest, case_records)

    next_number = next_case_number()
    changed = 0
    skipped = 0
    same_file_duplicates = 0
    same_content_duplicates = 0

    for region, pdf_path in scan_pdfs():
        file_hash = sha256_file(pdf_path)
        existing = manifest.get("files", {}).get(file_hash)

        master_for_file_hash = case_for_file_hash(manifest, file_hash)
        if master_for_file_hash:
            known_paths = set(existing.get("file_paths", [])) if existing else set()
            if str(pdf_path) in known_paths:
                skipped += 1
                continue
            entry = register_same_file_duplicate(
                pdf_path=pdf_path,
                file_hash=file_hash,
                master_id=master_for_file_hash,
                case_records=case_records,
                manifest=manifest,
            )
            if entry.get("status") == "duplicate":
                same_file_duplicates += 1
            print(f"Duplicate file: {pdf_path.name} -> {entry['duplicate_of']}")
            continue

        entry, next_number, record = process_pdf(
            pdf_path=pdf_path,
            region=region,
            file_hash=file_hash,
            next_number=next_number,
            case_records=case_records,
            manifest=manifest,
        )
        changed += 1
        if record.get("is_duplicate"):
            same_content_duplicates += 1
            print(f"Duplicate content: {pdf_path.name} -> {record['duplicate_of']}")
        else:
            print(f"Processed {region}: {pdf_path.name} -> {record['id']}")

    save_manifest(manifest)
    index_path = write_index()
    print(f"Skipped unchanged PDFs: {skipped}")
    print(f"Processed new or changed PDFs: {changed}")
    print(f"Same-file duplicates recorded: {same_file_duplicates}")
    print(f"Same-content duplicates recorded: {same_content_duplicates}")
    print(f"Updated index: {index_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
