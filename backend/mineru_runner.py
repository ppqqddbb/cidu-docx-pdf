from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
MINERU_ROOT = ROOT / "MinerU"
MINERU_VENV_PYTHON = MINERU_ROOT / ".venv" / "Scripts" / "python.exe"


class MinerUParseError(RuntimeError):
    pass


def parse_to_structured_content(path: Path, *, tier: str = "standard", ocr_mode: str = "auto") -> dict[str, Any]:
    """Parse DOCX/PDF with MinerU and return structured_content JSON."""
    return parse_document_outputs(path, tier=tier, ocr_mode=ocr_mode)["structured_content"]


def parse_document_outputs(path: Path, *, tier: str = "standard", ocr_mode: str = "auto") -> dict[str, Any]:
    """Parse once and return both Markdown (Diff input) and structured JSON (debug)."""
    path = path.resolve()
    if not path.exists():
        raise MinerUParseError(f"input file does not exist: {path}")
    python = MINERU_VENV_PYTHON if MINERU_VENV_PYTHON.exists() else Path(sys.executable)
    with tempfile.TemporaryDirectory(prefix="mineru_structured_") as tmp:
        output_path = Path(tmp) / "structured_content.json"
        markdown_path = Path(tmp) / "document.md"
        script = (
            "import json, sys\n"
            "from pathlib import Path\n"
            f"sys.path.insert(0, {str(MINERU_ROOT)!r})\n"
            "from mineru.parser import parse\n"
            "input_path = Path(sys.argv[1])\n"
            "output_path = Path(sys.argv[2])\n"
            "markdown_path = Path(sys.argv[3])\n"
            "tier = sys.argv[4]\n"
            "ocr_mode = sys.argv[5]\n"
            "result = parse(input_path, tier=tier, ocr_mode=ocr_mode, page_range='')\n"
            "structured = result.structured_content()\n"
            "output_path.write_text(json.dumps(structured, ensure_ascii=False, indent=2), encoding='utf-8')\n"
            "markdown_path.write_text(result.markdown(add_markers=False), encoding='utf-8')\n"
        )
        env = os.environ.copy()
        env["PYTHONPATH"] = str(MINERU_ROOT) + os.pathsep + env.get("PYTHONPATH", "")
        completed = subprocess.run(
            [str(python), "-c", script, str(path), str(output_path), str(markdown_path), tier, ocr_mode],
            cwd=str(MINERU_ROOT),
            env=env,
            text=True,
            capture_output=True,
            timeout=900,
            check=False,
        )
        if completed.returncode != 0:
            detail = (completed.stderr or completed.stdout or "unknown MinerU parse failure").strip()
            raise MinerUParseError(detail[-4000:])
        try:
            payload = json.loads(output_path.read_text(encoding="utf-8"))
            markdown = markdown_path.read_text(encoding="utf-8")
        except Exception as exc:
            raise MinerUParseError("MinerU did not produce valid Markdown/structured_content output") from exc
    if not isinstance(payload, dict):
        raise MinerUParseError("MinerU structured_content must be a JSON object")
    return {"structured_content": payload, "markdown": markdown}
