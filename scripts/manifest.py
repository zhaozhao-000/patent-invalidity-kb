from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
OUTPUT_DIR = ROOT / "output"
MANIFEST_PATH = OUTPUT_DIR / "manifest.json"
LEGACY_PROCESSED_PATH = OUTPUT_DIR / "processed_files.json"


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def empty_manifest() -> dict[str, Any]:
    return {
        "schema_version": 1,
        "files": {},
        "content_hashes": {},
        "cases": {},
        "updated_at": now_iso(),
    }


def load_manifest() -> dict[str, Any]:
    if MANIFEST_PATH.exists():
        with MANIFEST_PATH.open("r", encoding="utf-8") as f:
            data = json.load(f)
    else:
        data = migrate_legacy_processed()

    data.setdefault("schema_version", 1)
    data.setdefault("files", {})
    data.setdefault("content_hashes", {})
    data.setdefault("cases", {})
    return data


def save_manifest(manifest: dict[str, Any]) -> None:
    manifest["updated_at"] = now_iso()
    MANIFEST_PATH.parent.mkdir(parents=True, exist_ok=True)
    MANIFEST_PATH.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def migrate_legacy_processed() -> dict[str, Any]:
    manifest = empty_manifest()
    if not LEGACY_PROCESSED_PATH.exists():
        return manifest

    with LEGACY_PROCESSED_PATH.open("r", encoding="utf-8") as f:
        legacy = json.load(f)

    for entry in legacy.get("files", {}).values():
        file_hash = entry.get("file_hash")
        if not file_hash:
            continue
        manifest["files"][file_hash] = {
            "file_path": entry.get("file_path", ""),
            "file_name": entry.get("file_name", ""),
            "file_hash": file_hash,
            "content_hash": entry.get("content_hash", ""),
            "case_id": entry.get("case_id", ""),
            "status": "duplicate" if entry.get("duplicate_of") else "canonical",
            "duplicate_of": entry.get("duplicate_of", ""),
            "duplicate_reason": entry.get("duplicate_reason", ""),
            "processed_at": entry.get("processed_at", ""),
            "file_paths": unique_nonempty([entry.get("file_path", "")]),
        }
    return manifest


def unique_nonempty(values: list[str]) -> list[str]:
    result: list[str] = []
    for value in values:
        if value and value not in result:
            result.append(value)
    return result


def status_for_record(record: dict[str, Any]) -> str:
    if record.get("is_duplicate"):
        return "duplicate"
    if not record.get("include_in_kb", True):
        return "excluded"
    if record.get("suspected_duplicates"):
        return "suspected_duplicate"
    if record.get("needs_ocr"):
        return "needs_ocr"
    return "canonical"


def upsert_case(manifest: dict[str, Any], record: dict[str, Any]) -> None:
    case_id = record.get("id", "")
    if not case_id:
        return
    case_entry = manifest["cases"].setdefault(
        case_id,
        {
            "canonical_file": record.get("source_file", ""),
            "duplicate_files": [],
            "suspected_duplicates": [],
        },
    )
    if not case_entry.get("canonical_file"):
        case_entry["canonical_file"] = record.get("source_file", "")
    case_entry["duplicate_files"] = unique_nonempty(
        list(case_entry.get("duplicate_files", [])) + list(record.get("duplicate_files", []))
    )
    case_entry["suspected_duplicates"] = unique_nonempty(
        list(case_entry.get("suspected_duplicates", [])) + list(record.get("suspected_duplicates", []))
    )


def upsert_file(
    manifest: dict[str, Any],
    *,
    file_path: Path,
    file_hash: str,
    case_id: str,
    content_hash: str = "",
    status: str = "canonical",
    duplicate_of: str = "",
    duplicate_reason: str = "",
) -> dict[str, Any]:
    entry = manifest["files"].setdefault(
        file_hash,
        {
            "file_path": str(file_path),
            "file_name": file_path.name,
            "file_hash": file_hash,
            "content_hash": content_hash,
            "case_id": case_id,
            "status": status,
            "duplicate_of": duplicate_of,
            "duplicate_reason": duplicate_reason,
            "processed_at": now_iso(),
            "file_paths": [],
        },
    )
    entry["file_name"] = entry.get("file_name") or file_path.name
    entry["file_path"] = entry.get("file_path") or str(file_path)
    entry["file_hash"] = file_hash
    entry["content_hash"] = content_hash or entry.get("content_hash", "")
    entry["case_id"] = case_id or entry.get("case_id", "")
    entry["status"] = status
    entry["duplicate_of"] = duplicate_of
    entry["duplicate_reason"] = duplicate_reason
    entry["processed_at"] = now_iso()
    entry["file_paths"] = unique_nonempty(list(entry.get("file_paths", [])) + [str(file_path)])
    return entry


def register_content_hash(manifest: dict[str, Any], content_hash: str, case_id: str) -> None:
    if content_hash and case_id:
        manifest["content_hashes"].setdefault(content_hash, case_id)


def case_for_file_hash(manifest: dict[str, Any], file_hash: str) -> str:
    entry = manifest.get("files", {}).get(file_hash, {})
    return entry.get("duplicate_of") or entry.get("case_id", "")


def case_for_content_hash(manifest: dict[str, Any], content_hash: str) -> str:
    if not content_hash:
        return ""
    return manifest.get("content_hashes", {}).get(content_hash, "")
