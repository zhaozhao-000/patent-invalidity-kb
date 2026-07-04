from __future__ import annotations

import argparse
import hashlib
import http.client
import json
import os
import re
import time
import urllib.error
import urllib.parse
import urllib.request
import zipfile
from pathlib import Path
from typing import Any

from build_jurisdiction_data import INPUT_DIR, PARSED_DIR, ROOT, jurisdiction_from_path

try:
    import requests
except ImportError:  # pragma: no cover - optional dependency for closer MinerU docs parity.
    requests = None


MANIFEST_PATH = ROOT / "public" / "data" / "all_cases_manifest.json"
DONE_STATES = {"done"}
WAIT_STATES = {"waiting-file", "uploading", "pending", "running", "converting"}
FAILED_STATES = {"failed"}


def request_json(method: str, url: str, api_key: str, payload: dict[str, Any] | None = None, timeout: int = 60) -> dict[str, Any]:
    data = None
    headers = {"Authorization": f"Bearer {api_key}", "Accept": "*/*"}
    if payload is not None:
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = resp.read().decode("utf-8", errors="ignore")
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="ignore")
        raise RuntimeError(f"HTTP {exc.code}: {detail[:500]}") from exc
    result = json.loads(body) if body.strip() else {}
    if result.get("code") not in (None, 0):
        raise RuntimeError(f"MinerU API error {result.get('code')}: {result.get('msg')}")
    return result


def put_file(url: str, pdf_path: Path, timeout: int = 300) -> None:
    # MinerU signed upload URLs reject some automatic Content-Type headers.
    # Prefer requests because it matches MinerU's official sample:
    # requests.put(file_url, data=f). If unavailable, use http.client and only
    # send Content-Length.
    if requests is not None:
        with pdf_path.open("rb") as f:
            resp = requests.put(url, data=f, timeout=timeout)
        if resp.status_code not in (200, 201):
            raise RuntimeError(f"Upload failed: HTTP {resp.status_code} {resp.text[:300]}")
        return

    parsed = urllib.parse.urlsplit(url)
    if parsed.scheme != "https":
        raise RuntimeError(f"Unsupported upload URL scheme: {parsed.scheme}")
    upload_path = urllib.parse.urlunsplit(("", "", parsed.path or "/", parsed.query, ""))
    conn = http.client.HTTPSConnection(parsed.netloc, timeout=timeout)
    try:
        with pdf_path.open("rb") as f:
            conn.request(
                "PUT",
                upload_path,
                body=f,
                headers={"Content-Length": str(pdf_path.stat().st_size)},
            )
            resp = conn.getresponse()
            detail = resp.read(300).decode("utf-8", errors="ignore")
            if resp.status not in (200, 201):
                raise RuntimeError(f"Upload failed: HTTP {resp.status} {detail}")
    finally:
        conn.close()


def download_bytes(url: str, timeout: int = 300) -> bytes:
    with urllib.request.urlopen(url, timeout=timeout) as resp:
        return resp.read()


def safe_data_id(pdf: Path) -> str:
    rel = pdf.relative_to(ROOT).as_posix()
    digest = hashlib.sha1(rel.encode("utf-8")).hexdigest()[:12]
    stem = re.sub(r"[^A-Za-z0-9_.-]+", "_", pdf.stem)[:80].strip("._-") or "document"
    return f"{stem}_{digest}"


def parsed_paths(pdf: Path, jurisdiction: str) -> tuple[Path, Path, Path]:
    data_id = safe_data_id(pdf)
    md_path = PARSED_DIR / jurisdiction / "markdown" / f"{data_id}.md"
    json_path = PARSED_DIR / jurisdiction / "json" / f"{data_id}.json"
    zip_path = PARSED_DIR / jurisdiction / "zip" / f"{data_id}.zip"
    return md_path, json_path, zip_path


def load_manifest() -> dict[str, Any]:
    if MANIFEST_PATH.exists():
        return json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    return {"schema_version": 1, "totals": {}, "files": []}


def save_manifest(data: dict[str, Any]) -> None:
    MANIFEST_PATH.parent.mkdir(parents=True, exist_ok=True)
    MANIFEST_PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def update_manifest(
    manifest: dict[str, Any],
    pdf: Path,
    jurisdiction: str,
    md_path: Path,
    json_path: Path,
    mineru_status: str,
    error: str = "",
    batch_id: str = "",
) -> None:
    source = pdf.relative_to(ROOT).as_posix()
    for item in manifest.get("files", []):
        if item.get("source_path") == source:
            item["mineru_status"] = mineru_status
            item["error_message"] = error
            item["mineru_batch_id"] = batch_id
            item["parsed_markdown_path"] = md_path.relative_to(ROOT).as_posix() if md_path.exists() else ""
            item["parsed_json_path"] = json_path.relative_to(ROOT).as_posix() if json_path.exists() else ""
            item["jurisdiction"] = item.get("jurisdiction") or jurisdiction
            return
    manifest.setdefault("files", []).append(
        {
            "file_name": pdf.name,
            "source_path": source,
            "public_pdf_path": "",
            "jurisdiction": jurisdiction,
            "language": "zh" if jurisdiction == "cn" else "en" if jurisdiction == "us" else "unknown",
            "parse_status": "pending_review",
            "mineru_status": mineru_status,
            "database_status": "pending_review",
            "error_message": error,
            "case_id": "",
            "parsed_markdown_path": md_path.relative_to(ROOT).as_posix() if md_path.exists() else "",
            "parsed_json_path": json_path.relative_to(ROOT).as_posix() if json_path.exists() else "",
            "mineru_batch_id": batch_id,
        }
    )


def apply_upload_urls(base_url: str, api_key: str, pdfs: list[Path], model_version: str, language: str) -> tuple[str, list[str]]:
    payload = {
        "files": [
            {
                "name": pdf.name,
                "data_id": safe_data_id(pdf),
                "is_ocr": True,
            }
            for pdf in pdfs
        ],
        "model_version": model_version,
        "language": language,
        "enable_table": True,
        "enable_formula": True,
    }
    result = request_json("POST", f"{base_url}/api/v4/file-urls/batch", api_key, payload)
    data = result.get("data") or {}
    batch_id = data.get("batch_id")
    urls = data.get("file_urls") or []
    if not batch_id or len(urls) != len(pdfs):
        raise RuntimeError(f"Unexpected upload-url response: {result}")
    return str(batch_id), [str(url) for url in urls]


def poll_batch(base_url: str, api_key: str, batch_id: str, interval: int, timeout: int) -> list[dict[str, Any]]:
    deadline = time.time() + timeout
    quoted = urllib.parse.quote(batch_id, safe="")
    while time.time() < deadline:
        result = request_json("GET", f"{base_url}/api/v4/extract-results/batch/{quoted}", api_key)
        data = result.get("data") or {}
        rows = data.get("extract_result") or []
        states = [str(row.get("state", "")).lower() for row in rows]
        done = sum(1 for state in states if state in DONE_STATES)
        failed = sum(1 for state in states if state in FAILED_STATES)
        waiting = len(states) - done - failed
        print(f"batch {batch_id}: done={done} failed={failed} waiting={waiting}")
        if rows and all(state in DONE_STATES | FAILED_STATES for state in states):
            return rows
        if rows and not any(state in WAIT_STATES | DONE_STATES | FAILED_STATES for state in states):
            raise RuntimeError(f"Unexpected batch states: {states}")
        time.sleep(interval)
    raise TimeoutError(f"MinerU batch timeout: {batch_id}")


def extract_full_markdown(zip_bytes: bytes, zip_path: Path, md_path: Path) -> None:
    zip_path.parent.mkdir(parents=True, exist_ok=True)
    md_path.parent.mkdir(parents=True, exist_ok=True)
    zip_path.write_bytes(zip_bytes)
    with zipfile.ZipFile(zip_path) as archive:
        names = archive.namelist()
        md_names = [name for name in names if name.lower().endswith("full.md")]
        if not md_names:
            md_names = [name for name in names if name.lower().endswith(".md")]
        if not md_names:
            raise RuntimeError("MinerU result zip contains no markdown file.")
        text = archive.read(md_names[0]).decode("utf-8", errors="ignore")
    if not text.strip():
        raise RuntimeError("MinerU markdown is empty.")
    md_path.write_text(text, encoding="utf-8")


def candidate_pdfs(force: bool) -> list[Path]:
    candidates: list[Path] = []
    for pdf in sorted(INPUT_DIR.rglob("*.pdf")):
        jurisdiction = jurisdiction_from_path(pdf)
        if jurisdiction not in {"cn", "us"}:
            jurisdiction = "unknown"
        md_path, json_path, _ = parsed_paths(pdf, jurisdiction)
        # Only skip a file when a MinerU response JSON exists. Existing markdown alone
        # may have been generated from older local OCR/text extraction.
        if json_path.exists() and md_path.exists() and not force:
            continue
        candidates.append(pdf)
    return candidates


def chunks(items: list[Path], size: int) -> list[list[Path]]:
    return [items[index : index + size] for index in range(0, len(items), size)]


def main() -> int:
    parser = argparse.ArgumentParser(description="Parse local PDFs with MinerU precise API using official signed upload URLs.")
    parser.add_argument("--limit", type=int, default=1, help="Maximum PDFs to parse. Default 1 for safe testing. Use 0 for all.")
    parser.add_argument("--batch-size", type=int, default=1, help="PDFs per MinerU batch. Max 50; keep 1 while testing.")
    parser.add_argument("--force", action="store_true", help="Re-parse even if MinerU JSON and markdown already exist.")
    parser.add_argument("--model-version", default="vlm", choices=["pipeline", "vlm"], help="MinerU precise model.")
    parser.add_argument("--language", default="ch", help="MinerU language value. Use ch for CN/mixed, en for English-only batches.")
    parser.add_argument("--poll-interval", type=int, default=10)
    parser.add_argument("--timeout", type=int, default=1800)
    args = parser.parse_args()

    api_key = os.environ.get("MINERU_API_KEY", "").strip()
    base_url = os.environ.get("MINERU_API_BASE", "https://mineru.net").strip().rstrip("/")
    if not api_key:
        print("MINERU_API_KEY is not set. No API calls were made.")
        return 2
    if args.batch_size < 1 or args.batch_size > 50:
        raise SystemExit("--batch-size must be between 1 and 50.")

    pdfs = candidate_pdfs(args.force)
    if args.limit:
        pdfs = pdfs[: args.limit]
    print(f"MinerU candidates: {len(pdfs)}")
    if not pdfs:
        return 0

    manifest = load_manifest()
    processed = 0
    for group in chunks(pdfs, args.batch_size):
        print("MinerU batch:")
        for pdf in group:
            print(f"  {pdf.relative_to(ROOT)}")
        batch_id = ""
        try:
            batch_id, upload_urls = apply_upload_urls(base_url, api_key, group, args.model_version, args.language)
            for pdf, upload_url in zip(group, upload_urls):
                print(f"upload {pdf.name}")
                put_file(upload_url, pdf)
            rows = poll_batch(base_url, api_key, batch_id, args.poll_interval, args.timeout)
            by_name = {str(row.get("file_name") or ""): row for row in rows}
            for pdf in group:
                jurisdiction = jurisdiction_from_path(pdf)
                if jurisdiction not in {"cn", "us"}:
                    jurisdiction = "unknown"
                md_path, json_path, zip_path = parsed_paths(pdf, jurisdiction)
                row = by_name.get(pdf.name) or next((item for item in rows if item.get("data_id") == safe_data_id(pdf)), {})
                json_path.parent.mkdir(parents=True, exist_ok=True)
                json_path.write_text(json.dumps({"batch_id": batch_id, "result": row}, ensure_ascii=False, indent=2), encoding="utf-8")
                state = str(row.get("state") or "").lower()
                if state != "done":
                    error = str(row.get("err_msg") or f"MinerU state={state}")
                    update_manifest(manifest, pdf, jurisdiction, md_path, json_path, "failed", error[:500], batch_id)
                    print(f"failed: {pdf.name}: {error}")
                    continue
                zip_url = str(row.get("full_zip_url") or "")
                if not zip_url:
                    raise RuntimeError(f"No full_zip_url for {pdf.name}: {row}")
                extract_full_markdown(download_bytes(zip_url), zip_path, md_path)
                update_manifest(manifest, pdf, jurisdiction, md_path, json_path, "success", "", batch_id)
                print(f"wrote {md_path.relative_to(ROOT)}")
                processed += 1
        except (urllib.error.URLError, RuntimeError, TimeoutError, OSError, zipfile.BadZipFile) as exc:
            for pdf in group:
                jurisdiction = jurisdiction_from_path(pdf)
                if jurisdiction not in {"cn", "us"}:
                    jurisdiction = "unknown"
                md_path, json_path, _ = parsed_paths(pdf, jurisdiction)
                update_manifest(manifest, pdf, jurisdiction, md_path, json_path, "failed", str(exc)[:500], batch_id)
            print(f"batch failed: {exc}")
        finally:
            save_manifest(manifest)
            time.sleep(1)

    print(f"MinerU processed successfully: {processed}")
    print("Next: python scripts\\build_jurisdiction_data.py")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
