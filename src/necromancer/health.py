"""Repository health and abandonment indicators.

Indicators are observable evidence, not a score. Inactivity alone never
proves abandonment: the category stays unresolved unless explicit
evidence supports it. This layer is derived at investigation time and
stays outside the evidence seal.
"""

from __future__ import annotations

import re
from datetime import datetime, timezone

from .excavator import Excavation
from .models import Report

_EXPLICIT_ABANDONED = (
    "no longer maintained", "not maintained", "abandoned", "unmaintained",
    "ya no se mantiene", "abandonado", "sin mantenimiento",
)
_MAINTENANCE_ONLY = ("maintenance only", "security fixes only", "solo mantenimiento")
_SUPERSEDED = ("superseded by", "replaced by", "deprecated in favor", "reemplazado por")
_ARCHIVED = ("archived", "archivado", "read-only archive")


def _parse_ts(value: str) -> datetime | None:
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (ValueError, AttributeError):
        return None


def analyze_health(excavation: Excavation, report: Report,
                   as_of: datetime | None = None) -> dict:
    now = as_of or datetime.now(timezone.utc)
    dates = sorted(
        parsed for parsed in (_parse_ts(c.date_iso) for c in excavation.commits)
        if parsed is not None
    )
    texts = {path: text.lower() for path, text in excavation.texts.items()}
    doc_text = "\n".join(
        text for path, text in texts.items()
        if path.lower().startswith(("readme", "docs/"))
    )
    todo_refs = sum(
        len(re.findall(r"\b(todo|fixme)\b", text)) for text in texts.values()
    )
    test_files = [a.path for a in excavation.artifacts if a.kind == "TEST"]
    code_files = [a.path for a in excavation.artifacts if a.kind == "CODE"]
    ci_files = [
        a.path for a in excavation.artifacts
        if a.path.startswith(".github/workflows/") or a.path in (
            ".gitlab-ci.yml", "Jenkinsfile", ".circleci/config.yml")
    ]
    last = dates[-1] if dates else None
    days_since = (now - last).days if last else None

    category = "STATUS_UNKNOWN"
    evidence: list[str] = []
    if any(phrase in doc_text for phrase in _EXPLICIT_ABANDONED):
        category = "EXPLICITLY_ABANDONED"
        evidence.append("Documentation explicitly states the project is unmaintained or abandoned")
    elif any(phrase in doc_text for phrase in _SUPERSEDED):
        category = "SUPERSEDED"
        evidence.append("Documentation states the project was superseded or replaced")
    elif any(phrase in doc_text for phrase in _ARCHIVED):
        category = "ARCHIVED"
        evidence.append("Documentation states the repository is archived")
    elif any(phrase in doc_text for phrase in _MAINTENANCE_ONLY):
        category = "MAINTENANCE_ONLY"
        evidence.append("Documentation states maintenance-only mode")
    elif days_since is not None and days_since >= 730:
        category = "DORMANT"
        evidence.append(
            f"Last commit is {days_since} days before the investigation date; "
            "this indicates dormancy, not proven abandonment")
    elif days_since is not None:
        category = "ACTIVE"
        evidence.append(f"Last commit {days_since} days before the investigation date")

    return {
        "category": category,
        "category_evidence": evidence,
        "as_of": now.isoformat(),
        "commit_count": len(excavation.commits),
        "first_commit": dates[0].isoformat() if dates else "",
        "last_commit": last.isoformat() if last else "",
        "days_since_last_commit": days_since,
        "active_span_days": (dates[-1] - dates[0]).days if len(dates) >= 2 else 0,
        "authors": len({c.author for c in excavation.commits}),
        "unmerged_branches": [b.name for b in report.abandoned_branches],
        "todo_fixme_references": todo_refs,
        "test_files": len(test_files),
        "code_files": len(code_files),
        "ci_config_present": bool(ci_files),
        "ci_files": ci_files,
        "tags": [name for name, _tip in excavation.tags],
        "note": "Indicators only. Missing metadata never proves inactivity or abandonment.",
    }
