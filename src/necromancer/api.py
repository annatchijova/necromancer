"""HTTP API for the investigation workbench. Local-first, read-only."""

from __future__ import annotations

import importlib.util
from pathlib import Path
from tempfile import gettempdir

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from . import workspace as workspace_mod
from .acquire import AcquisitionError
from .cli import investigate, investigate_source
from .excavator import ExcavationError, _git, resolve_repo
from .export import report_to_dict

app = FastAPI(title="NECROMANCER", version="0.3.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173", "http://127.0.0.1:5173",
        "http://localhost:5174", "http://127.0.0.1:5174",
    ],
    allow_methods=["GET", "POST", "DELETE"],
    allow_headers=["*"],
)

_FIXTURE_KEYS = ("a", "b", "c")
_FIXTURE_LABELS = {
    "a": "Fixture A: documented security fix with an incomplete patch",
    "b": "Fixture B: missing solution on an unmerged branch",
    "c": "Fixture C: documentation claiming a completed feature that is a stub",
}


class InvestigateRequest(BaseModel):
    source: str = ""
    path: str = ""  # legacy alias for source (local path only)
    snapshot: str = "head"
    provider: str = "offline"
    save: bool = True

    def resolved_source(self) -> str:
        return self.source or self.path


class CompareRequest(BaseModel):
    older_id: str
    newer_id: str


def _db():
    return workspace_mod.connect()


def _save(report_dict: dict) -> str:
    conn = _db()
    try:
        return workspace_mod.save(conn, report_dict)
    finally:
        conn.close()


def _fixture_path(key: str) -> Path:
    if key not in _FIXTURE_KEYS:
        raise HTTPException(status_code=404, detail="unknown fixture")
    base = Path(gettempdir()) / "necromancer-fixtures-demo"
    target = base / {
        "a": "fixture-a-incomplete-fix",
        "b": "fixture-b-abandoned-branch",
        "c": "fixture-c-false-completion",
    }[key]
    if not (target / ".git").exists():
        spec = importlib.util.spec_from_file_location(
            "build_synthetic",
            Path(__file__).resolve().parents[2] / "fixtures" / "build_synthetic.py",
        )
        module = importlib.util.module_from_spec(spec)
        assert spec and spec.loader
        spec.loader.exec_module(module)
        module.build_all(base)
    return target


@app.get("/health")
def health() -> dict:
    return {"status": "PASS", "service": "necromancer"}


@app.post("/investigations")
def create_investigation(request: InvestigateRequest) -> dict:
    try:
        report = investigate_source(
            request.resolved_source(), snapshot=request.snapshot,
            provider_name=request.provider)
    except (ExcavationError, AcquisitionError, ValueError) as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    body = report_to_dict(report)
    if request.save:
        body["investigation_id"] = _save(body)
    return body


@app.post("/excavate")
def excavate_compat(request: InvestigateRequest) -> dict:
    return create_investigation(request)


@app.get("/fixtures")
def fixtures() -> dict:
    return {
        "fixtures": [
            {"key": key, "label": _FIXTURE_LABELS[key], "synthetic": True}
            for key in _FIXTURE_KEYS
        ],
        "note": "Synthetic evidence, explicitly labeled. Not a real repository.",
    }


@app.post("/fixtures/{key}")
def investigate_fixture(key: str) -> dict:
    target = _fixture_path(key)
    try:
        report = investigate(str(target), source_kind="synthetic", source_ref=key)
    except ExcavationError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    body = report_to_dict(report)
    body["investigation_id"] = _save(body)
    return body


@app.get("/investigations")
def list_saved() -> dict:
    conn = _db()
    try:
        return {"investigations": workspace_mod.list_investigations(conn)}
    finally:
        conn.close()


@app.get("/investigations/{inv_id}")
def get_saved(inv_id: str) -> dict:
    conn = _db()
    try:
        body = workspace_mod.get(conn, inv_id)
        if body is None:
            raise HTTPException(status_code=404, detail="investigation not found")
        status = "UNKNOWN"
        try:
            repo = resolve_repo(body["repo_path"])
            current_head = _git(repo, ["rev-parse", "HEAD"]).strip()
            status = workspace_mod.staleness(conn, inv_id, current_head)
        except Exception:
            status = "UNKNOWN"
        return {**body, "workspace_status": status}
    finally:
        conn.close()


@app.delete("/investigations/{inv_id}")
def delete_saved(inv_id: str) -> dict:
    conn = _db()
    try:
        if not workspace_mod.delete(conn, inv_id):
            raise HTTPException(status_code=404, detail="investigation not found")
        return {"deleted": inv_id}
    finally:
        conn.close()


@app.get("/investigations/{inv_id}/manifest")
def get_manifest(inv_id: str) -> dict:
    conn = _db()
    try:
        body = workspace_mod.get(conn, inv_id)
        if body is None:
            raise HTTPException(status_code=404, detail="investigation not found")
        return workspace_mod.manifest(body)
    finally:
        conn.close()


@app.post("/compare")
def compare_saved(request: CompareRequest) -> dict:
    conn = _db()
    try:
        older = workspace_mod.get(conn, request.older_id)
        newer = workspace_mod.get(conn, request.newer_id)
        if older is None or newer is None:
            raise HTTPException(status_code=404, detail="investigation not found")
        return workspace_mod.compare(older, newer)
    finally:
        conn.close()
