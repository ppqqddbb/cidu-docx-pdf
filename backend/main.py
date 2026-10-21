from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any
from uuid import uuid4

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from backend.comparison import compare_documents, compare_markdown_documents
from backend.mineru_runner import MinerUParseError, parse_document_outputs
from backend.preview_locator import attach_preview_locations
from backend.preview_renderer import PreviewRenderError, render_document_preview

app = FastAPI(title="Structured Document Compare API")

ROOT = Path(__file__).resolve().parents[1]
FRONTEND_DIST = ROOT / "frontend" / "dist"
UPLOAD_ROOT = ROOT / "uploads"
UPLOAD_ROOT.mkdir(parents=True, exist_ok=True)

app.add_middleware(
    CORSMiddleware,
    # The UI can be opened through any address assigned to this computer
    # (localhost, a LAN address, a VPN address, and so on).
    allow_origin_regex=r"https?://.*",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/api/compare-json")
async def compare_json(old_file: UploadFile = File(...), new_file: UploadFile = File(...)) -> dict[str, Any]:
    old_payload = await _read_json_upload(old_file)
    new_payload = await _read_json_upload(new_file)
    result = compare_documents(old_payload, new_payload)
    return {
        "old_document": old_payload,
        "new_document": new_payload,
        "result": result,
    }


@app.post("/api/compare-documents")
async def compare_uploaded_documents(
    old_file: UploadFile = File(...),
    new_file: UploadFile = File(...),
    tier: str = Form("standard"),
    ocr_mode: str = Form("auto"),
) -> dict[str, Any]:
    _validate_document_upload(old_file)
    _validate_document_upload(new_file)
    comparison_id = uuid4().hex
    work_dir = UPLOAD_ROOT / comparison_id
    old_dir = work_dir / "old"
    new_dir = work_dir / "new"
    old_dir.mkdir(parents=True, exist_ok=True)
    new_dir.mkdir(parents=True, exist_ok=True)
    old_path = old_dir / _safe_filename(old_file.filename or "old")
    new_path = new_dir / _safe_filename(new_file.filename or "new")
    await _save_upload(old_file, old_path)
    await _save_upload(new_file, new_path)
    try:
        old_output = parse_document_outputs(old_path, tier=tier, ocr_mode=ocr_mode)
        new_output = parse_document_outputs(new_path, tier=tier, ocr_mode=ocr_mode)
        old_payload = old_output["structured_content"]
        new_payload = new_output["structured_content"]
        old_preview = render_document_preview(old_path, old_dir / "pages")
        new_preview = render_document_preview(new_path, new_dir / "pages")
    except MinerUParseError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except PreviewRenderError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    (old_dir / "structured_content.json").write_text(json.dumps(old_payload, ensure_ascii=False, indent=2), encoding="utf-8")
    (new_dir / "structured_content.json").write_text(json.dumps(new_payload, ensure_ascii=False, indent=2), encoding="utf-8")
    (old_dir / "document.md").write_text(old_output["markdown"], encoding="utf-8")
    (new_dir / "document.md").write_text(new_output["markdown"], encoding="utf-8")
    result = compare_markdown_documents(
        old_output["markdown"],
        new_output["markdown"],
        old_auxiliary_structured=old_payload,
        new_auxiliary_structured=new_payload,
    )
    result["input_format"] = "mineru_markdown"
    attach_preview_locations(result, old_preview["pdf_path"], new_preview["pdf_path"])
    return {
        "comparison_id": comparison_id,
        "old_document": old_payload,
        "new_document": new_payload,
        "previews": {
            "old": _preview_payload(comparison_id, "old", old_preview["pages"]),
            "new": _preview_payload(comparison_id, "new", new_preview["pages"]),
        },
        "result": result,
    }


async def _read_json_upload(upload: UploadFile) -> dict[str, Any]:
    try:
        raw = await upload.read()
        payload = json.loads(raw.decode("utf-8-sig"))
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"{upload.filename} is not valid JSON") from exc
    if not isinstance(payload, dict):
        raise HTTPException(status_code=400, detail=f"{upload.filename} must contain a JSON object")
    return payload


async def _save_upload(upload: UploadFile, path: Path) -> None:
    with path.open("wb") as file_obj:
        shutil.copyfileobj(upload.file, file_obj)


def _validate_document_upload(upload: UploadFile) -> None:
    suffix = Path(upload.filename or "").suffix.lower()
    if suffix not in {".pdf", ".docx"}:
        raise HTTPException(status_code=400, detail=f"{upload.filename} must be a PDF or DOCX file")


def _safe_filename(filename: str) -> str:
    name = Path(filename).name
    return name or "upload"


def _preview_payload(comparison_id: str, side: str, pages: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "pages": [
            {
                **page,
                "image_url": f"/uploads/{comparison_id}/{side}/pages/{page['image']}",
            }
            for page in pages
        ]
    }


app.mount("/uploads", StaticFiles(directory=UPLOAD_ROOT), name="uploads")

if FRONTEND_DIST.exists():
    app.mount("/", StaticFiles(directory=FRONTEND_DIST, html=True), name="frontend")
