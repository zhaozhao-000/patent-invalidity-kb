from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any

from case_enrichment import MANUAL_REVIEW_CSV, enrich_record_from_body, read_case_text, write_manual_review_files
from dedupe import write_json


ROOT = Path(__file__).resolve().parents[1]
PUBLIC_DIR = ROOT / "public"
PUBLIC_PDF_DIR = PUBLIC_DIR / "pdfs"
OCR_TEXT_DIR = PUBLIC_DIR / "data" / "ocr_texts"
OUTPUT_JSON_DIR = ROOT / "output" / "json"
OUTPUT_TEXT_DIR = ROOT / "output" / "text"
MIN_TEXT_CHARS = 500
_PADDLE_OCR: Any | None = None
_PADDLE_PROFILE = "fast"


def load_records() -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for path in sorted(OUTPUT_JSON_DIR.glob("case_*.json")):
        with path.open("r", encoding="utf-8") as f:
            records.append(json.load(f))
    return records


def save_record(record: dict[str, Any]) -> None:
    write_json(OUTPUT_JSON_DIR / f"{record['id']}.json", record)


def pdf_path_for_record(record: dict[str, Any]) -> Path | None:
    pdf_path = record.get("pdf_path", "")
    if not pdf_path:
        return None
    path = Path(pdf_path)
    if path.is_absolute():
        return path
    return PUBLIC_DIR / path


def needs_ocr(record: dict[str, Any]) -> bool:
    if record.get("ocr_status") == "succeeded" and record.get("ocr_text_path"):
        return False
    text = read_case_text(record)
    return bool(record.get("needs_ocr")) or len(text.strip()) < MIN_TEXT_CHARS


def force_or_needs_ocr(record: dict[str, Any], force: bool) -> bool:
    return force or needs_ocr(record)


def paddle_available() -> tuple[bool, str]:
    try:
        import paddleocr  # noqa: F401
    except Exception as exc:
        return False, str(exc)
    return True, ""


def pymupdf_available() -> tuple[bool, str]:
    try:
        import fitz  # noqa: F401
    except Exception as exc:
        return False, str(exc)
    return True, ""


def ocrmypdf_available() -> bool:
    return bool(shutil.which("ocrmypdf") and shutil.which("tesseract"))


def render_pdf_pages(pdf_path: Path, image_dir: Path, max_pages: int = 0, scale: float = 1.3) -> list[Path]:
    import fitz

    image_paths: list[Path] = []
    with fitz.open(pdf_path) as doc:
        limit = len(doc) if max_pages <= 0 else min(len(doc), max_pages)
        for index in range(limit):
            page = doc[index]
            pix = page.get_pixmap(matrix=fitz.Matrix(scale, scale), alpha=False)
            image_path = image_dir / f"page_{index + 1:04d}.png"
            pix.save(image_path)
            image_paths.append(image_path)
    return image_paths


def run_paddle_ocr(pdf_path: Path, max_pages: int = 0, render_scale: float = 1.3, profile: str = "fast") -> tuple[str, str]:
    configure_paddle_runtime()
    try:
        ocr = get_paddle_ocr(profile)
        parts: list[str] = []
        with tempfile.TemporaryDirectory() as tmp:
            image_paths = render_pdf_pages(pdf_path, Path(tmp), max_pages=max_pages, scale=render_scale)
            for page_index, image_path in enumerate(image_paths, start=1):
                print(f"    page {page_index}/{len(image_paths)}", flush=True)
                result = run_paddle_on_image(ocr, image_path)
                page_text = paddle_result_to_text(result)
                if page_text:
                    parts.append(f"\n\n--- OCR {image_path.stem} ---\n{page_text}")
        text = "\n".join(parts).strip()
        return text, "succeeded" if text else "failed"
    except Exception as exc:
        return "", f"failed: {exc}"


def configure_paddle_runtime() -> None:
    # Some PaddlePaddle 3.x CPU builds fail in the oneDNN/PIR path on Windows.
    # OCR is slower with these paths disabled, but it avoids batch-wide failures.
    os.environ.setdefault("FLAGS_use_mkldnn", "0")
    os.environ.setdefault("FLAGS_enable_pir_api", "0")
    os.environ.setdefault("FLAGS_enable_onednn", "0")
    os.environ.setdefault("ONEDNN_VERBOSE", "0")


def get_paddle_ocr(profile: str = "fast") -> Any:
    global _PADDLE_OCR, _PADDLE_PROFILE
    if _PADDLE_OCR is not None and _PADDLE_PROFILE == profile:
        return _PADDLE_OCR
    try:
        from paddleocr import PaddleOCR
    except Exception as exc:
        raise RuntimeError(f"unavailable: {exc}") from exc
    _PADDLE_PROFILE = profile
    _PADDLE_OCR = create_paddle_ocr(PaddleOCR, profile)
    return _PADDLE_OCR


def create_paddle_ocr(PaddleOCR: Any, profile: str) -> Any:
    model_kwargs = (
        {
            "text_detection_model_name": "PP-OCRv6_tiny_det",
            "text_recognition_model_name": "PP-OCRv6_tiny_rec",
            "use_doc_orientation_classify": False,
            "use_doc_unwarping": False,
            "use_textline_orientation": False,
            "text_recognition_batch_size": 8,
        }
        if profile == "fast"
        else {
            "lang": "ch",
            "use_doc_orientation_classify": False,
            "use_doc_unwarping": False,
            "use_textline_orientation": False,
        }
    )
    for kwargs in (
        {**model_kwargs, "enable_mkldnn": False},
        model_kwargs,
        {"lang": "ch", "enable_mkldnn": False},
        {"lang": "ch"},
        {},
    ):
        try:
            return PaddleOCR(**kwargs)
        except TypeError:
            continue
    return PaddleOCR()


def run_paddle_on_image(ocr: Any, image_path: Path) -> Any:
    if hasattr(ocr, "predict"):
        return ocr.predict(str(image_path))
    if hasattr(ocr, "ocr"):
        try:
            return ocr.ocr(str(image_path), cls=True)
        except TypeError as exc:
            if "cls" not in str(exc):
                raise
            return ocr.ocr(str(image_path))
    raise RuntimeError("Unsupported PaddleOCR object: missing ocr/predict method")


def paddle_result_to_text(result: Any) -> str:
    texts: list[str] = []

    def walk(value: Any) -> None:
        if isinstance(value, dict):
            for key in ("rec_text", "text"):
                if isinstance(value.get(key), str):
                    texts.append(value[key])
            for key in ("rec_texts", "texts"):
                if isinstance(value.get(key), list):
                    texts.extend(str(item) for item in value[key] if str(item).strip())
            for item in value.values():
                walk(item)
        elif isinstance(value, (list, tuple)):
            if len(value) >= 2 and isinstance(value[1], (list, tuple)) and value[1] and isinstance(value[1][0], str):
                texts.append(value[1][0])
            else:
                for item in value:
                    walk(item)

    walk(result)
    return "\n".join(dict.fromkeys(texts))


def run_ocrmypdf(pdf_path: Path) -> tuple[str, str]:
    if not ocrmypdf_available():
        return "", "unavailable"
    try:
        import fitz
    except Exception as exc:
        return "", f"failed: {exc}"

    with tempfile.TemporaryDirectory() as tmp:
        output_pdf = Path(tmp) / "searchable.pdf"
        result = subprocess.run(
            [
                "ocrmypdf",
                "--skip-text",
                "--language",
                "chi_sim+eng",
                str(pdf_path),
                str(output_pdf),
            ],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="ignore",
            check=False,
        )
        if result.returncode != 0 or not output_pdf.exists():
            return "", f"failed: {result.stderr.strip()[:300]}"
        parts: list[str] = []
        with fitz.open(output_pdf) as doc:
            for index, page in enumerate(doc, start=1):
                page_text = page.get_text("text") or ""
                if page_text.strip():
                    parts.append(f"\n\n--- OCR Page {index} ---\n{page_text}")
        text = "\n".join(parts).strip()
        return text, "succeeded" if text else "failed"


def write_ocr_text(record: dict[str, Any], text: str) -> str:
    OCR_TEXT_DIR.mkdir(parents=True, exist_ok=True)
    ocr_path = OCR_TEXT_DIR / f"{record['id']}.txt"
    ocr_path.write_text(text, encoding="utf-8")
    output_text_path = OUTPUT_TEXT_DIR / f"{record['id']}.txt"
    output_text_path.write_text(text, encoding="utf-8")
    return ocr_path.relative_to(PUBLIC_DIR).as_posix()


def process_record(record: dict[str, Any], engine: str, max_pages: int, force: bool, render_scale: float, profile: str) -> str:
    if not force and not needs_ocr(record):
        record.setdefault("extracted_text_status", "text_extracted")
        return "skipped"

    pdf_path = pdf_path_for_record(record)
    if not pdf_path or not pdf_path.exists():
        record["ocr_status"] = "missing_pdf"
        record["extracted_text_status"] = "missing_pdf"
        record["needs_manual_summary"] = True
        save_record(record)
        return "missing_pdf"

    text = ""
    status = "unavailable"
    if engine in {"auto", "paddle"}:
        text, status = run_paddle_ocr(pdf_path, max_pages=max_pages, render_scale=render_scale, profile=profile)
    if engine in {"auto", "ocrmypdf"} and not text:
        fallback_text, fallback_status = run_ocrmypdf(pdf_path)
        if fallback_text:
            text, status = fallback_text, fallback_status
        elif status.startswith("unavailable"):
            status = fallback_status

    if text:
        relative_ocr_path = write_ocr_text(record, text)
        record["ocr_text_path"] = relative_ocr_path
        record["ocr_text"] = text[:2000]
        record["ocr_status"] = "succeeded"
        record["extracted_text_status"] = "ocr"
        record["needs_ocr"] = False
        record["needs_manual_summary"] = False
        enrich_record_from_body(record, text)
        save_record(record)
        return "ocr_succeeded"

    record["ocr_status"] = status if status else "unavailable"
    record["extracted_text_status"] = "ocr_unavailable"
    record["needs_manual_summary"] = True
    save_record(record)
    return "ocr_failed"


def main() -> int:
    parser = argparse.ArgumentParser(description="Run local OCR for scanned PDFs in the case library.")
    parser.add_argument("--engine", choices=["auto", "paddle", "ocrmypdf"], default="auto")
    parser.add_argument("--max-pages", type=int, default=0, help="0 means all pages.")
    parser.add_argument("--limit", type=int, default=0, help="Only process the first N files that need OCR.")
    parser.add_argument("--render-scale", type=float, default=1.3, help="PDF render scale. Lower is faster; 1.3 is usually enough for testing.")
    parser.add_argument("--profile", choices=["fast", "accurate"], default="fast", help="fast uses tiny PaddleOCR models; accurate uses default Chinese models.")
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()

    paddle_ok, paddle_reason = paddle_available()
    pymupdf_ok, pymupdf_reason = pymupdf_available()
    print(f"PaddleOCR available: {paddle_ok}" + (f" ({paddle_reason})" if not paddle_ok else ""))
    print(f"PyMuPDF available: {pymupdf_ok}" + (f" ({pymupdf_reason})" if not pymupdf_ok else ""))
    print(f"OCRmyPDF/Tesseract available: {ocrmypdf_available()}")

    records = load_records()
    counts: dict[str, int] = {}
    total = len(records)
    processed_ocr = 0
    for index, record in enumerate(records, start=1):
        should_ocr = force_or_needs_ocr(record, args.force)
        if should_ocr and args.limit > 0 and processed_ocr >= args.limit:
            counts["deferred"] = counts.get("deferred", 0) + 1
            continue
        if should_ocr:
            processed_ocr += 1
            print(f"[{index}/{total}] OCR {record.get('id', '')} {Path(record.get('pdf_path', '')).name}", flush=True)
        result = process_record(record, args.engine, args.max_pages, args.force, args.render_scale, args.profile)
        counts[result] = counts.get(result, 0) + 1

    refreshed_records = load_records()
    write_manual_review_files(refreshed_records)

    print("OCR summary:")
    for key in sorted(counts):
        print(f"  {key}: {counts[key]}")
    print(f"Manual review CSV: {MANUAL_REVIEW_CSV}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
