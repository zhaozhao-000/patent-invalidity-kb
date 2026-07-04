from __future__ import annotations

import argparse
import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

from import_external_ocr import EXTERNAL_OCR_DIR


ROOT = Path(__file__).resolve().parents[1]
OUTPUT_JSON_DIR = ROOT / "output" / "json"
PUBLIC_DIR = ROOT / "public"


def load_records() -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for path in sorted(OUTPUT_JSON_DIR.glob("case_*.json")):
        with path.open("r", encoding="utf-8") as f:
            records.append(json.load(f))
    return records


def pdf_path_for_record(record: dict[str, Any]) -> Path | None:
    pdf_path = record.get("pdf_path", "")
    if not pdf_path:
        return None
    path = Path(pdf_path)
    if path.is_absolute():
        return path
    return PUBLIC_DIR / path


def request_json(method: str, url: str, api_key: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
    data = None
    headers = {"Authorization": f"Bearer {api_key}", "Accept": "application/json"}
    if payload is not None:
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            body = resp.read().decode("utf-8", errors="ignore")
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="ignore")
        raise RuntimeError(f"HTTP {exc.code} {url}: {detail[:500]}") from exc
    return json.loads(body) if body.strip() else {}


def upload_multipart(url: str, api_key: str, pdf_path: Path, extra_fields: dict[str, str]) -> dict[str, Any]:
    boundary = "----mineru-boundary-7MA4YWxkTrZu0gW"
    chunks: list[bytes] = []
    for key, value in extra_fields.items():
        chunks.extend(
            [
                f"--{boundary}\r\n".encode(),
                f'Content-Disposition: form-data; name="{key}"\r\n\r\n'.encode(),
                str(value).encode("utf-8"),
                b"\r\n",
            ]
        )
    chunks.extend(
        [
            f"--{boundary}\r\n".encode(),
            f'Content-Disposition: form-data; name="file"; filename="{pdf_path.name}"\r\n'.encode(),
            b"Content-Type: application/pdf\r\n\r\n",
            pdf_path.read_bytes(),
            b"\r\n",
            f"--{boundary}--\r\n".encode(),
        ]
    )
    data = b"".join(chunks)
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Accept": "application/json",
        "Content-Type": f"multipart/form-data; boundary={boundary}",
    }
    req = urllib.request.Request(url, data=data, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=300) as resp:
            body = resp.read().decode("utf-8", errors="ignore")
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="ignore")
        raise RuntimeError(f"HTTP {exc.code} {url}: {detail[:500]}") from exc
    return json.loads(body) if body.strip() else {}


def first_value(data: dict[str, Any], keys: list[str]) -> Any:
    current: Any = data
    for key in keys:
        if isinstance(current, dict) and key in current:
            current = current[key]
        else:
            return None
    return current


def extract_task_id(response: dict[str, Any]) -> str:
    for path in (["task_id"], ["id"], ["data", "task_id"], ["data", "id"]):
        value = first_value(response, path)
        if value:
            return str(value)
    raise RuntimeError(f"Cannot find task id in response: {response}")


def extract_status(response: dict[str, Any]) -> str:
    for path in (["status"], ["state"], ["data", "status"], ["data", "state"]):
        value = first_value(response, path)
        if value:
            return str(value).lower()
    return ""


def extract_markdown(response: dict[str, Any]) -> str:
    for path in (
        ["markdown"],
        ["md"],
        ["text"],
        ["data", "markdown"],
        ["data", "md"],
        ["data", "text"],
        ["result", "markdown"],
        ["result", "md"],
    ):
        value = first_value(response, path)
        if isinstance(value, str) and value.strip():
            return value
    return ""


def extract_download_url(response: dict[str, Any]) -> str:
    for path in (
        ["markdown_url"],
        ["md_url"],
        ["download_url"],
        ["data", "markdown_url"],
        ["data", "md_url"],
        ["data", "download_url"],
        ["result", "markdown_url"],
        ["result", "md_url"],
    ):
        value = first_value(response, path)
        if isinstance(value, str) and value.startswith(("http://", "https://")):
            return value
    return ""


def download_text(url: str) -> str:
    with urllib.request.urlopen(url, timeout=120) as resp:
        return resp.read().decode("utf-8", errors="ignore")


def poll_result(base_url: str, task_path: str, api_key: str, task_id: str, interval: int, timeout: int) -> dict[str, Any]:
    deadline = time.time() + timeout
    quoted_id = urllib.parse.quote(task_id, safe="")
    while time.time() < deadline:
        result = request_json("GET", f"{base_url.rstrip('/')}{task_path.rstrip('/')}/{quoted_id}", api_key)
        status = extract_status(result)
        if status in {"done", "success", "succeeded", "completed", "finish", "finished"}:
            return result
        if status in {"fail", "failed", "error"}:
            raise RuntimeError(f"MinerU task failed: {result}")
        print(f"  waiting task={task_id} status={status or 'unknown'}")
        time.sleep(interval)
    raise TimeoutError(f"MinerU task timeout: {task_id}")


def write_markdown(record: dict[str, Any], text: str) -> Path:
    EXTERNAL_OCR_DIR.mkdir(parents=True, exist_ok=True)
    path = EXTERNAL_OCR_DIR / f"{record['id']}.md"
    path.write_text(text, encoding="utf-8")
    return path


def main() -> int:
    parser = argparse.ArgumentParser(description="Submit OCR-needed PDFs to a MinerU-compatible cloud API.")
    parser.add_argument("--limit", type=int, default=1, help="Process at most N PDFs. Default is 1 for safe testing.")
    parser.add_argument("--poll-interval", type=int, default=10)
    parser.add_argument("--timeout", type=int, default=1800)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    api_key = os.environ.get("MINERU_API_KEY", "").strip()
    base_url = os.environ.get("MINERU_API_BASE", "").strip().rstrip("/")
    submit_path = os.environ.get("MINERU_SUBMIT_PATH", "/api/v4/extract/task").strip()
    task_path = os.environ.get("MINERU_TASK_PATH", "/api/v4/extract/task").strip()
    if not api_key or not base_url:
        raise SystemExit("Please set MINERU_API_KEY and MINERU_API_BASE first.")

    candidates = [record for record in load_records() if record.get("needs_ocr") or record.get("extracted_text_status") == "ocr_unavailable"]
    print(f"OCR candidates: {len(candidates)}")
    processed = 0
    for record in candidates:
        if processed >= args.limit:
            break
        pdf_path = pdf_path_for_record(record)
        if not pdf_path or not pdf_path.exists():
            print(f"missing PDF: {record.get('id')}")
            continue
        print(f"submit {record['id']} {pdf_path.name}")
        if args.dry_run:
            processed += 1
            continue
        submit_url = f"{base_url}{submit_path}"
        response = upload_multipart(
            submit_url,
            api_key,
            pdf_path,
            {"output_format": "markdown", "ocr": "true"},
        )
        task_id = extract_task_id(response)
        result = poll_result(base_url, task_path, api_key, task_id, args.poll_interval, args.timeout)
        markdown = extract_markdown(result)
        if not markdown:
            download_url = extract_download_url(result)
            if download_url:
                markdown = download_text(download_url)
        if not markdown:
            raise RuntimeError(f"Cannot find markdown result for {record['id']}: {result}")
        out = write_markdown(record, markdown)
        print(f"wrote {out}")
        processed += 1
    print(f"Processed: {processed}")
    print("Next: python scripts\\import_external_ocr.py")
    print("Next: python scripts\\build_index.py")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
