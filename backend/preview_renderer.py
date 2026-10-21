from __future__ import annotations

import shutil
import subprocess
from pathlib import Path
from typing import Any

import pypdfium2 as pdfium


class PreviewRenderError(RuntimeError):
    pass


def render_document_pages(source_path: Path, output_dir: Path, *, scale: float = 1.6) -> list[dict[str, Any]]:
    """Render PDF/DOCX pages to PNG images for original-document preview."""
    preview = render_document_preview(source_path, output_dir, scale=scale)
    return preview["pages"]


def render_document_preview(source_path: Path, output_dir: Path, *, scale: float = 1.6) -> dict[str, Any]:
    """Render PDF/DOCX pages and return page images plus the PDF used for locating text."""
    output_dir.mkdir(parents=True, exist_ok=True)
    suffix = source_path.suffix.lower()
    if suffix == ".pdf":
        pdf_path = source_path
    elif suffix == ".docx":
        pdf_path = _convert_docx_to_pdf(source_path, output_dir)
    else:
        raise PreviewRenderError(f"unsupported preview format: {suffix}")
    return {"pdf_path": pdf_path, "pages": _render_pdf(pdf_path, output_dir, scale=scale)}


def _render_pdf(pdf_path: Path, output_dir: Path, *, scale: float) -> list[dict[str, Any]]:
    document = pdfium.PdfDocument(str(pdf_path))
    pages: list[dict[str, Any]] = []
    try:
        for index in range(len(document)):
            page = document[index]
            bitmap = page.render(scale=scale)
            image = bitmap.to_pil()
            image_path = output_dir / f"page_{index + 1:03d}.png"
            image.save(image_path)
            pages.append(
                {
                    "page_index": index,
                    "image": image_path.name,
                    "width": image.width,
                    "height": image.height,
                }
            )
            bitmap.close()
            page.close()
    finally:
        document.close()
    return pages


def _convert_docx_to_pdf(source_path: Path, output_dir: Path) -> Path:
    converted = _convert_with_libreoffice(source_path, output_dir)
    if converted is not None:
        return converted
    converted = _convert_with_word_com(source_path, output_dir)
    if converted is not None:
        return converted
    raise PreviewRenderError(
        "DOCX preview requires LibreOffice/soffice in PATH or Microsoft Word COM automation on Windows."
    )


def _convert_with_libreoffice(source_path: Path, output_dir: Path) -> Path | None:
    executable = shutil.which("soffice") or shutil.which("libreoffice")
    if not executable:
        return None
    completed = subprocess.run(
        [
            executable,
            "--headless",
            "--convert-to",
            "pdf",
            "--outdir",
            str(output_dir),
            str(source_path),
        ],
        text=True,
        capture_output=True,
        timeout=180,
        check=False,
    )
    if completed.returncode != 0:
        raise PreviewRenderError((completed.stderr or completed.stdout or "LibreOffice conversion failed").strip())
    pdf_path = output_dir / f"{source_path.stem}.pdf"
    return pdf_path if pdf_path.exists() else None


def _convert_with_word_com(source_path: Path, output_dir: Path) -> Path | None:
    try:
        import win32com.client  # type: ignore[import-not-found]
    except Exception:
        return None
    pdf_path = output_dir / f"{source_path.stem}.pdf"
    word = win32com.client.DispatchEx("Word.Application")
    word.Visible = False
    document = None
    try:
        document = word.Documents.Open(str(source_path.resolve()))
        document.ExportAsFixedFormat(str(pdf_path.resolve()), 17)
    finally:
        if document is not None:
            document.Close(False)
        word.Quit()
    return pdf_path if pdf_path.exists() else None
