from __future__ import annotations

import re
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Any


MIN_TEXT_CHARS = 500


def clean_text(text: str) -> str:
    text = text.replace("\x00", " ")
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def extract_text_with_pymupdf(pdf_path: Path) -> str:
    try:
        import fitz  # PyMuPDF
    except ImportError as exc:
        raise RuntimeError(
            "PyMuPDF is not installed. Run: pip install -r requirements.txt"
        ) from exc

    parts: list[str] = []
    with fitz.open(pdf_path) as doc:
        for page_index, page in enumerate(doc, start=1):
            page_text = page.get_text("text") or ""
            if page_text.strip():
                parts.append(f"\n\n--- Page {page_index} ---\n{page_text}")
    return clean_text("\n".join(parts))


def run_ocr_placeholder(pdf_path: Path, max_pages: int = 12) -> tuple[str, str]:
    """Try local Tesseract OCR when it is available.

    This intentionally does not install system OCR tools. If Tesseract is missing,
    ingestion continues and the case is marked for manual review.
    """
    if not shutil.which("tesseract"):
        return "", "unavailable"

    try:
        import fitz  # PyMuPDF
    except ImportError:
        return "", "failed"

    parts: list[str] = []
    try:
        with tempfile.TemporaryDirectory() as tmp:
            tmpdir = Path(tmp)
            with fitz.open(pdf_path) as doc:
                for page_index in range(1, min(len(doc), max_pages) + 1):
                    page = doc[page_index - 1]
                    pix = page.get_pixmap(matrix=fitz.Matrix(2, 2), alpha=False)
                    image_path = tmpdir / f"page_{page_index}.png"
                    pix.save(image_path)
                    result = subprocess.run(
                        ["tesseract", str(image_path), "stdout", "-l", "chi_sim+eng"],
                        capture_output=True,
                        text=True,
                        encoding="utf-8",
                        errors="ignore",
                        check=False,
                    )
                    if result.returncode == 0 and result.stdout.strip():
                        parts.append(f"\n\n--- OCR Page {page_index} ---\n{result.stdout}")
        text = clean_text("\n".join(parts))
        return text, "succeeded" if text else "failed"
    except Exception:
        return "", "failed"


def extract_pdf_text(pdf_path: Path, output_text_path: Path) -> dict[str, Any]:
    text = extract_text_with_pymupdf(pdf_path)
    needs_ocr = len(text) < MIN_TEXT_CHARS
    ocr_text = ""
    ocr_status = "not_required"

    if needs_ocr:
        ocr_text, ocr_status = run_ocr_placeholder(pdf_path)
        if len(ocr_text.strip()) > len(text):
            text = clean_text(ocr_text)
            needs_ocr = len(text) < MIN_TEXT_CHARS
        elif ocr_status == "succeeded":
            ocr_status = "failed"

    output_text_path.parent.mkdir(parents=True, exist_ok=True)
    output_text_path.write_text(text, encoding="utf-8")

    return {
        "text": text,
        "ocr_text": ocr_text,
        "ocr_status": ocr_status,
        "text_length": len(text),
        "needs_ocr": needs_ocr,
        "text_path": str(output_text_path),
    }


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Extract text from a PDF.")
    parser.add_argument("pdf_path", type=Path)
    parser.add_argument("output_text_path", type=Path)
    args = parser.parse_args()

    result = extract_pdf_text(args.pdf_path, args.output_text_path)
    print(
        f"Extracted {result['text_length']} characters. "
        f"needs_ocr={result['needs_ocr']}"
    )
