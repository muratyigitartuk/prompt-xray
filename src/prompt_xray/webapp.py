from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from .analysis import analyze_target
from .reporting import build_comparison


class ScanRequest(BaseModel):
    target: str
    max_file_size_kb: int = Field(default=1024, ge=1)
    max_code_files_per_language: int = Field(default=400, ge=25)
    include_snippets: bool = True


class CompareRequest(BaseModel):
    left: str
    right: str
    max_file_size_kb: int = Field(default=1024, ge=1)
    max_code_files_per_language: int = Field(default=400, ge=25)
    include_snippets: bool = False


def _project_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _load_manifest(project_root: Path) -> dict:
    manifest_path = project_root / "ui" / "manifest.json"
    return json.loads(manifest_path.read_text(encoding="utf-8"))


def create_app(project_root: Optional[Path] = None) -> FastAPI:
    root = project_root or _project_root()

    app = FastAPI(title="Prompt-xray UI", version="0.1.0")

    @app.get("/api/manifest")
    def get_manifest() -> dict:
        return _load_manifest(root)

    @app.post("/api/scan")
    def api_scan(payload: ScanRequest) -> dict:
        report = analyze_target(
            target=payload.target,
            max_file_size_kb=payload.max_file_size_kb,
            include_snippets=payload.include_snippets,
            max_code_files_per_language=payload.max_code_files_per_language,
        )
        return report.model_dump(mode="json")

    @app.post("/api/compare")
    def api_compare(payload: CompareRequest) -> dict:
        left_report = analyze_target(
            target=payload.left,
            max_file_size_kb=payload.max_file_size_kb,
            include_snippets=payload.include_snippets,
            max_code_files_per_language=payload.max_code_files_per_language,
        )
        right_report = analyze_target(
            target=payload.right,
            max_file_size_kb=payload.max_file_size_kb,
            include_snippets=payload.include_snippets,
            max_code_files_per_language=payload.max_code_files_per_language,
        )
        return build_comparison(left_report, right_report)

    @app.get("/")
    def index() -> FileResponse:
        return FileResponse(root / "index.html")

    app.mount("/", StaticFiles(directory=root, html=True), name="static")
    return app
