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

from build_jurisdiction_data import INPUT_DIR, PARSED_DIR, ROOT, jurisdiction_from_path


MANIFEST_PATH = ROOT / "public" / "data" / "all_cases_manifest.json"


def request_json(method: str, url: str, api_key: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
    data = None
    headers = {"Authorization": f"Bearer {api_key}", "Accept": "application/json"}
    if payload is not None:
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    with urllib.request.urlopen(req, timeout=60) as resp:
        body = resp.read().decode("utf-8", errors="ignore")
    return json.loads(body) if body.strip() else {}


def upload_multipart(url: str, api_key: str, pdf_path: Path) -> dict[str, Any]:
    boundary = "----mineru-boundary-kb"
    chunks = [
        f"--{boundary}\r\n".encode(),
        b'Content-Disposition: form-data; name="output_format"\r\n\r\nmarkdown,json\r\n',
        f"--{boundary}\r\n".encode(),
        b'Content-Disposition: form-data; name="ocr"\r\n\r\ntrue\r\n',
        f"--{boundary}\r\n".encode(),
        f'Content-Disposition: form-data; name="file"; filename="{pdf_path.name}"\r\n'.encode("utf-8"),
        b"Content-Type: application/pdf\r\n\r\n",
        pdf_path.read_bytes(),
        b"\r\n",
        f"--{boundary}--\r\n".encode(),
    ]
    req = urllib.request.Request(
        url,
        data=b"".join(chunks),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Accept": "application/json",
            "Content-Type": f"multipart/form-data; boundary={boundary}",
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=300) as resp:
        body = resp.read().decode("utf-8", errors="ignore")
    return json.loads(body) if body.strip() else {}


def first_value(data: dict[str, Any], paths: list[list[str]]) -> Any:
    for path in paths:
        current: Any = data
        for key in path:
            if isinstance(current, dict) and key in current:
                current = current[key]
            else:
                current = None
                break
        if current:
            return current
    return None


def task_id(response: dict[str, Any]) -> str:
    value = first_value(response, [["task_id"], ["id"], ["data", "task_id"], ["data", "id"]])
    if not value:
        raise RuntimeError(f"MinerU response has no task id: {response}")
    return str(value)


def status(response: dict[str, Any]) -> str:
    value = first_value(response, [["status"], ["state"], ["data", "status"], ["data", "state"]])
    return str(value or "").lower()


def markdown_from(response: dict[str, Any]) -> str:
    value = first_value(
        response,
        [["markdown"], ["md"], ["text"], ["data", "markdown"], ["data", "md"], ["data", "text"], ["result", "markdown"], ["result", "md"]],
    )
    return value if isinstance(value, str) else ""


def download_url_from(response: dict[str, Any]) -> str:
    value = first_value(
        response,
        [["markdown_url"], ["md_url"], ["download_url"], ["data", "markdown_url"], ["data", "md_url"], ["data", "download_url"], ["result", "markdown_url"]],
    )
    return value if isinstance(value, str) and value.startswith(("http://", "https://")) else ""


def download_text(url: str) -> str:
    with urllib.request.urlopen(url, timeout=120) as resp:
        return resp.read().decode("utf-8", errors="ignore")


def poll(base_url: str, task_path: str, api_key: str, task: str, interval: int, timeout: int) -> dict[str, Any]:
    deadline = time.time() + timeout
    quoted = urllib.parse.quote(task, safe="")
    while time.time() < deadline:
        result = request_json("GET", f"{base_url.rstrip('/')}{task_path.rstrip('/')}/{quoted}", api_key)
        current = status(result)
        if current in {"done", "success", "succeeded", "completed", "finish", "finished"}:
            return result
        if current in {"fail", "failed", "error"}:
            raise RuntimeError(f"MinerU task failed: {result}")
        print(f"waiting {task}: {current or 'unknown'}")
        time.sleep(interval)
    raise TimeoutError(f"MinerU task timeout: {task}")


def parsed_paths(pdf: Path, jurisdiction: str) -> tuple[Path, Path]:
    stem = pdf.stem
    return PARSED_DIR / jurisdiction / "markdown" / f"{stem}.md", PARSED_DIR / jurisdiction / "json" / f"{stem}.json"


def update_manifest(pdf: Path, jurisdiction: str, md_path: Path, json_path: Path, mineru_status: str, error: str = "") -> None:
    if not MANIFEST_PATH.exists():
        return
    data = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    source = pdf.relative_to(ROOT).as_posix()
    for item in data.get("files", []):
        if item.get("source_path") == source:
            item["mineru_status"] = mineru_status
            item["error_message"] = error
            if md_path.exists():
                item["parsed_markdown_path"] = md_path.relative_to(ROOT).as_posix()
            if json_path.exists():
                item["parsed_json_path"] = json_path.relative_to(ROOT).as_posix()
            break
    MANIFEST_PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Batch parse input PDFs with MinerU API and save markdown/json under parsed/.")
    parser.add_argument("--limit", type=int, default=0, help="Maximum PDFs to parse. 0 means all candidates.")
    parser.add_argument("--force", action="store_true", help="Re-parse even if parsed markdown already exists.")
    parser.add_argument("--poll-interval", type=int, default=10)
    parser.add_argument("--timeout", type=int, default=1800)
    args = parser.parse_args()

    api_key = os.environ.get("MINERU_API_KEY", "").strip()
    base_url = os.environ.get("MINERU_API_BASE", "").strip().rstrip("/")
    submit_path = os.environ.get("MINERU_SUBMIT_PATH", "/api/v4/extract/task").strip()
    task_path = os.environ.get("MINERU_TASK_PATH", "/api/v4/extract/task").strip()
    if not api_key or not base_url:
        print("MINERU_API_KEY or MINERU_API_BASE is not set. No API calls were made.")
        return 2

    pdfs = sorted(INPUT_DIR.rglob("*.pdf"))
    processed = 0
    for pdf in pdfs:
        jurisdiction = jurisdiction_from_path(pdf)
        if jurisdiction not in {"cn", "us"}:
            jurisdiction = "unknown"
        md_path, json_path = parsed_paths(pdf, jurisdiction)
        if md_path.exists() and not args.force:
            continue
        if args.limit and processed >= args.limit:
            break
        md_path.parent.mkdir(parents=True, exist_ok=True)
        json_path.parent.mkdir(parents=True, exist_ok=True)
        print(f"MinerU parse {pdf.relative_to(ROOT)}")
        try:
            submit = upload_multipart(f"{base_url}{submit_path}", api_key, pdf)
            task = task_id(submit)
            result = poll(base_url, task_path, api_key, task, args.poll_interval, args.timeout)
            markdown = markdown_from(result)
            if not markdown:
                url = download_url_from(result)
                markdown = download_text(url) if url else ""
            if not markdown.strip():
                raise RuntimeError("MinerU returned no markdown text.")
            md_path.write_text(markdown, encoding="utf-8")
            json_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
            update_manifest(pdf, jurisdiction, md_path, json_path, "success")
            processed += 1
            time.sleep(1)
        except (urllib.error.URLError, RuntimeError, TimeoutError, OSError) as exc:
            update_manifest(pdf, jurisdiction, md_path, json_path, "failed", str(exc)[:500])
            print(f"failed: {pdf.name}: {exc}")
            continue
    print(f"MinerU processed: {processed}")
    print("Next: python scripts\\build_jurisdiction_data.py")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
