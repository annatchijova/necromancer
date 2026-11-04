"""HTTP API. Read-only excavation of local repositories."""

from __future__ import annotations

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from .cli import investigate
from .excavator import ExcavationError
from .export import report_to_dict

app = FastAPI(title="NECROMANCER", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)


class ExcavateRequest(BaseModel):
    path: str


@app.get("/health")
def health() -> dict:
    return {"status": "PASS", "service": "necromancer"}


@app.post("/excavate")
def excavate_endpoint(request: ExcavateRequest) -> dict:
    try:
        report = investigate(request.path)
    except ExcavationError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    return report_to_dict(report)
