"""Repository health and abandonment indicators.

Indicators are observable evidence, not a score. Inactivity alone never
proves abandonment: the category stays unresolved unless explicit
evidence supports it. This layer is derived at investigation time and
stays outside the evidence seal.
"""

from __future__ import annotations

import re
from datetime import datetime, timezone
from pathlib import Path

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
    # Project-scoped declarations can only come from the root README,
    # read sentence by sentence. A research paper, a quoted example, a
    # feature note or a negated sentence ("not to be abandoned") is not
    # a project abandonment declaration (KRAKADYL regression, Round 4).
    import re as _re

    declarations: list[dict] = []
    scoped_declarations: list[dict] = []
    root_readmes = [
        path for path in excavation.texts
        if "/" not in path and Path(path).name.lower().startswith("readme")
    ]
    _scope_words = (
        "feature", "component", "module", "branch", "plugin", "endpoint",
        "parser", "legacy", "subsystem", "library", "service", "endpoint",
        "característica", "componente", "módulo", "rama", "función",
        "subsistema", "librería", "servicio",
    )
    # Declaration-eligible lines exclude quoted material and fenced
    # code blocks: a README that shows an example announcement inside
    # ``` fences or a > quote has not declared anything (Round 6
    # red-team finding: fenced/quoted text produced EXPLICITLY_ABANDONED
    # and SUPERSEDED). The same filter feeds every category below.
    def eligible_lines(text: str) -> list[tuple[int, str]]:
        out: list[tuple[int, str]] = []
        in_fence = False
        for lineno, line in enumerate(text.splitlines(), start=1):
            stripped = line.strip()
            if stripped.startswith("```"):
                in_fence = not in_fence
                continue
            if in_fence or not stripped or stripped.startswith(">"):
                continue
            out.append((lineno, line))
        return out

    eligible_by_path = {
        path: eligible_lines(excavation.texts[path]) for path in root_readmes
    }
    for path in sorted(root_readmes):
        for lineno, line in eligible_by_path[path]:
            sentence = line.strip()
            lower = sentence.lower()
            phrase = next(
                (item for item in _EXPLICIT_ABANDONED if item in lower), None)
            if phrase is None:
                continue
            if _re.search(r"\b(not|never|no|nunca|jamás)\b[^.]{0,50}(abandon|manten)", lower):
                continue  # negated: "not to be abandoned" declares the opposite
            entry = {"file": path, "line": lineno, "quote": sentence[:160]}
            if any(word in lower for word in _scope_words):
                scoped_declarations.append({**entry, "scope": "feature/component"})
            else:
                declarations.append({**entry, "scope": "project"})
    root_text = "\n".join(
        line.lower()
        for path in root_readmes
        for _lineno, line in eligible_by_path[path]
    )
    # Strict code-convention markers only: the Spanish word "todo" in
    # prose or data must never count as an unfinished-work reference.
    todo_refs = sum(
        len(re.findall(r"\b(TODO|FIXME)\b|NotImplementedError", text))
        for text in excavation.texts.values()
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
    if declarations:
        category = "EXPLICITLY_ABANDONED"
        first = declarations[0]
        evidence.append(
            f"Project-scoped declaration at {first['file']}:{first['line']}: "
            f"\"{first['quote'][:100]}\"")
    elif any(phrase in root_text for phrase in _SUPERSEDED):
        category = "SUPERSEDED"
        evidence.append("Documentation states the project was superseded or replaced")
    elif any(phrase in root_text for phrase in _ARCHIVED):
        category = "ARCHIVED"
        evidence.append("Documentation states the repository is archived")
    elif any(phrase in root_text for phrase in _MAINTENANCE_ONLY):
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
        "declarations": declarations,
        "scoped_declarations": scoped_declarations,
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
