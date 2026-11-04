"""Claim archaeology: extract claims and confront them with evidence.

Deterministic rules only. CONTRADICTED requires positive contradicting
evidence; missing evidence yields UNVERIFIED or NOT_DETERMINABLE, never a
refutation (invariant I2).
"""

from __future__ import annotations

import hashlib
import re
from pathlib import Path

from .excavator import Excavation
from .models import (
    Claim, ClaimState, Contradiction, EvidenceLink, Relation,
)

_VERB_PATTERNS: list[tuple[str, str]] = [
    (r"\b(fixed|fixes|fix|patched|corregid\w*|reparad\w*|solucionad\w*)\b", "FIXED"),
    (r"\b(resolved|resuelt\w*)\b", "RESOLVED"),
    (r"\b(implemented|implementad\w*|added|agregad\w*|añadid\w*)\b", "IMPLEMENTED"),
    (r"\b(completed|completad\w*|finished|terminad\w*)\b", "COMPLETED"),
    (r"\b(verified|verificad\w*|tested|probad\w*|covered)\b", "VERIFIED"),
    (r"\b(deprecated|deprecad\w*|removed|eliminad\w*)\b", "DEPRECATED"),
]
_FIX_WORDS = ("fix", "correg", "resolv", "resuel", "patch", "solucion")
_INCOMPLETE = ("todo", "fixme", "notimplementederror", "xxx", "incomplete")
_NEGATIONS = ("not implemented", "not yet", "no implementad", "sin implementar", "pendiente", "not completed")
_STOPWORDS = {
    "the", "and", "for", "with", "was", "were", "has", "have", "been", "this", "that",
    "una", "uno", "los", "las", "del", "que", "por", "para", "con", "fue", "han", "esta",
    "este", "issue", "bug", "feature", "vulnerability", "vulnerabilidad", "security", "seguridad",
}


def _claim_id(source_ref: str, text: str) -> str:
    return hashlib.sha256(f"{source_ref}|{text}".encode("utf-8")).hexdigest()[:16]


def _sentences(text: str) -> list[str]:
    parts = re.split(r"(?<=[.!?])\s+|\n+", text)
    return [part.strip() for part in parts if 8 <= len(part.strip()) <= 320]


def _verb_of(sentence: str) -> str | None:
    lower = sentence.lower()
    for pattern, verb in _VERB_PATTERNS:
        if re.search(pattern, lower):
            return verb
    return None


def _tokens(text: str) -> list[str]:
    quoted = re.findall(r"[`'\"]([\w\- ]{2,40})[`'\"]", text)
    tokens: list[str] = []
    for item in quoted:
        tokens.extend(item.lower().split())
    words = re.findall(r"[a-záéíóúñü0-9][a-záéíóúñü0-9\-]{2,}", text.lower())
    tokens.extend(word for word in words if word not in _STOPWORDS)
    seen: list[str] = []
    for token in tokens:
        if token not in seen:
            seen.append(token)
    return seen[:8]


def extract_claims(excavation: Excavation) -> list[Claim]:
    claims: list[Claim] = []
    seen: set[str] = set()
    doc_paths = {a.path for a in excavation.artifacts if a.kind == "DOC"}
    for path in sorted(doc_paths):
        for lineno, line_text in enumerate(
            excavation.texts.get(path, "").splitlines(), start=1
        ):
            for sentence in _sentences(line_text):
                verb = _verb_of(sentence)
                if verb is None:
                    continue
                claim_id = _claim_id(path, sentence)
                if claim_id in seen:
                    continue
                seen.add(claim_id)
                claims.append(Claim(
                    claim_id, sentence, "DOC", path, verb,
                    origin=f"{path}:{lineno}", line=lineno,
                ))
    for commit in excavation.commits:
        for sentence in _sentences(f"{commit.subject}. {commit.body}"):
            verb = _verb_of(sentence)
            if verb is None:
                continue
            claim_id = _claim_id(commit.commit_hash, sentence)
            if claim_id in seen:
                continue
            seen.add(claim_id)
            claims.append(Claim(claim_id, sentence, "COMMIT", commit.commit_hash[:12], verb,
                                origin=f"commit:{commit.commit_hash}"))
    claims.sort(key=lambda claim: claim.claim_id)
    return claims


def _corpora(excavation: Excavation) -> tuple[str, str, dict[str, str]]:
    code_texts = {
        a.path: excavation.texts.get(a.path, "")
        for a in excavation.artifacts if a.kind in ("CODE", "TEST")
    }
    code = "\n".join(
        text.lower() for path, text in code_texts.items()
        if next((a.kind for a in excavation.artifacts if a.path == path), "") == "CODE"
    )
    tests = "\n".join(
        excavation.texts.get(a.path, "").lower()
        for a in excavation.artifacts if a.kind == "TEST"
    )
    return code, tests, code_texts


def _fix_commits(excavation: Excavation):
    from .excavator import CODE_SUFFIXES

    return [
        commit for commit in excavation.commits
        if any(word in f"{commit.subject} {commit.body}".lower() for word in _FIX_WORDS)
        and any(
            Path(path).suffix.lower() in CODE_SUFFIXES
            for _status, path in commit.files
        )
    ]


def _word_set(text: str) -> set[str]:
    return {
        word for word in re.findall(r"[a-záéíóúñü0-9][a-záéíóúñü0-9\-]{2,}", text.lower())
        if word not in _STOPWORDS
    }


_GENERIC_VERB_WORDS = {
    "fix", "fixed", "fixes", "patched", "resolved", "implemented", "completed",
    "verified", "tested", "corregido", "corregida", "resuelto", "resuelta",
    "implementado", "implementada", "completado", "verificado", "probado",
}


def _bind_fix_commit(claim: Claim, candidates):
    """Bind a FIXED claim to one specific commit, or to none.

    Invariant: a claim may only inherit a commit verdict when the two share
    evidence — the claim originates in that commit, or they share content
    tokens in the message or in the changed file paths. Picking the newest
    fix in the repository (batch laundering) is forbidden.
    """
    claim_tokens = set(_tokens(claim.text)) - _GENERIC_VERB_WORDS
    scored: list[tuple[int, object]] = []
    for commit in candidates:
        score = 0
        if claim.source_kind == "COMMIT" and (
            claim.origin == f"commit:{commit.commit_hash}"
            or claim.source_ref == commit.commit_hash[:12]
        ):
            score += 5
        message_tokens = _word_set(f"{commit.subject} {commit.body}") - _GENERIC_VERB_WORDS
        score += 2 * len(claim_tokens & message_tokens)
        file_tokens: set[str] = set()
        for _status, path in commit.files:
            file_tokens |= _word_set(path.replace("/", " ").replace("_", " ").replace(".", " "))
        score += 3 * len(claim_tokens & file_tokens)
        if claim.source_kind == "DOC" and any(
            path == claim.source_ref for _status, path in commit.files
        ):
            score += 3
        if score >= 2:
            scored.append((score, commit))
    if not scored:
        return None
    best = max(score for score, _commit in scored)
    tied = [commit for score, commit in scored if score == best]
    tied.sort(key=lambda commit: commit.commit_hash)
    tied.sort(key=lambda commit: commit.date_iso, reverse=True)
    return tied[0], best


def evaluate_claims(excavation: Excavation, claims: list[Claim]):
    code, tests, code_texts = _corpora(excavation)
    test_paths = [a.path for a in excavation.artifacts if a.kind == "TEST"]
    kind_by_path = {a.path: a.kind for a in excavation.artifacts}
    fix_commits = _fix_commits(excavation)
    reverts = [c for c in excavation.commits if c.subject.lower().startswith("revert")]
    links: list[EvidenceLink] = []
    contradictions: list[Contradiction] = []

    def contradict(claim: Claim, ref: str, kind: str, detail: str) -> None:
        claim.state = ClaimState.CONTRADICTED
        claim.rationale = detail
        claim.falsifier = "Reopened if the contradicting evidence is shown stale, unrelated, or superseded at HEAD."
        links.append(EvidenceLink(claim.claim_id, ref, Relation.CONTRADICTS, detail))
        cid = hashlib.sha256(f"{claim.claim_id}|{ref}|{kind}".encode()).hexdigest()[:16]
        contradictions.append(Contradiction(cid, claim.claim_id, ref, kind, detail))

    for claim in claims:
        tokens = _tokens(claim.text)
        token_in_code = [t for t in tokens if t in code]
        token_in_tests = [t for t in tokens if t in tests or any(t in p.lower() for p in test_paths)]

        if claim.verb in ("FIXED", "RESOLVED"):
            bound = _bind_fix_commit(claim, fix_commits)
            if bound is None:
                claim.state = ClaimState.UNVERIFIED
                claim.rationale = (
                    f"No fix commit bound to this claim was found ({len(fix_commits)} fix "
                    "commit(s) exist but share no evidence with it). Absence of evidence "
                    "is not treated as disproof."
                )
                claim.falsifier = "Resolved by locating a fix commit that shares evidence with this claim."
                continue
            commit, bind_score = bound
            changed = [path for _s, path in commit.files]
            links.append(EvidenceLink(claim.claim_id, commit.commit_hash[:12], Relation.SUPPORTS,
                                      f"Bound fix commit {commit.commit_hash[:8]} (binding score {bind_score}) changed {', '.join(changed[:4])}"))
            has_test = any(
                next((a.kind for a in excavation.artifacts if a.path == p), "") == "TEST"
                for p in changed
            ) or bool(token_in_tests)
            incomplete_in = [
                p for p in changed
                if any(marker in code_texts.get(p, "").lower() for marker in _INCOMPLETE)
            ]
            reverted = next(
                (r for r in reverts if {p for _s, p in r.files} & set(changed)), None
            )
            if reverted is not None:
                contradict(claim, reverted.commit_hash[:12], "REVERTED_FIX",
                           f"Fix in {commit.commit_hash[:8]} was later reverted by {reverted.commit_hash[:8]}")
            elif incomplete_in:
                contradict(claim, incomplete_in[0], "INCOMPLETE_PATCH",
                           f"Fix documented, but {incomplete_in[0]} still contains an incomplete marker")
            elif has_test:
                claim.state = ClaimState.SUPPORTED
                claim.rationale = "Fix commit changes code and a test artifact mentions it, but target tests are never executed and token presence is a weak oracle. Verification is supported, not demonstrated."
                claim.falsifier = "Upgraded only by a trusted execution showing the test fails before and passes after the fix."
            else:
                claim.state = ClaimState.SUPPORTED
                claim.rationale = "Fix documented and code changed, but no regression test was found. Verification not demonstrated."
                claim.falsifier = "Upgraded only by a regression test that fails on the pre-fix code; downgraded if the patch proves incomplete."
            continue

        if claim.verb in ("IMPLEMENTED", "COMPLETED"):
            if not tokens:
                claim.state = ClaimState.NOT_DETERMINABLE
                claim.rationale = "Claim names no searchable feature token."
                claim.falsifier = "Requires a searchable feature name in the claim."
                continue
            stub_paths = [
                p for p, text in code_texts.items()
                if any(marker in text.lower() for marker in _INCOMPLETE)
                and any(t in text.lower() or t in p.lower() for t in tokens)
            ]
            negated = stub_paths[0] if stub_paths else None
            non_stub_code = "\n".join(
                text.lower() for path, text in code_texts.items() if path not in stub_paths
            )
            real_tokens = [t for t in tokens if t in non_stub_code]
            if not real_tokens and negated is not None:
                contradict(claim, negated, "STUB_ONLY",
                           f"Feature claimed, but only a stub with an incomplete marker was found in {negated}")
            elif not real_tokens:
                claim.state = ClaimState.UNVERIFIED
                claim.rationale = "No code reference to the claimed feature was found. This does not prove it never existed."
                claim.falsifier = "Resolved by locating the feature on any branch, tag, or earlier revision."
            elif token_in_tests:
                claim.state = ClaimState.SUPPORTED
                claim.rationale = "Feature present in code and mentioned by a test artifact, but tests were not executed. Supported, not verified."
                claim.falsifier = "Upgraded only by a trusted test execution; reopened if the feature code is removed or the test is shown unrelated."
                test_file = next(
                    (p for p in sorted(code_texts)
                     if kind_by_path.get(p) == "TEST"
                     and any(t in code_texts[p].lower() for t in tokens)),
                    test_paths[0] if test_paths else claim.source_ref,
                )
                links.append(EvidenceLink(claim.claim_id, test_file, Relation.SUPPORTS,
                                          "Feature token found in this test artifact"))
            else:
                claim.state = ClaimState.SUPPORTED
                claim.rationale = "Feature present in code; no covering test artifact was found."
                claim.falsifier = "Upgraded by a covering test artifact; downgraded if the code proves to be a stub."
                code_file = next(
                    (p for p in sorted(code_texts)
                     if kind_by_path.get(p) == "CODE"
                     and any(t in code_texts[p].lower() for t in real_tokens)),
                    claim.source_ref,
                )
                links.append(EvidenceLink(claim.claim_id, code_file, Relation.SUPPORTS,
                                          "Feature token found in this code file"))
            continue

        if claim.verb == "VERIFIED":
            if token_in_tests:
                claim.state = ClaimState.SUPPORTED
                claim.rationale = "A test artifact exists, but target tests are never executed, so verification is supported, not demonstrated."
                claim.falsifier = "Upgraded only by a trusted execution of the target tests."
            else:
                claim.state = ClaimState.UNVERIFIED
                claim.rationale = "Verification claimed, but no test artifact was found. Absence is not treated as disproof."
                claim.falsifier = "Resolved by locating the test artifact or a trusted test report."
            continue

        if claim.verb == "DEPRECATED":
            if token_in_code:
                code_file = next(
                    (p for p in sorted(code_texts)
                     if kind_by_path.get(p) == "CODE"
                     and any(t in code_texts[p].lower() for t in tokens)),
                    claim.source_ref,
                )
                contradict(claim, code_file, "STILL_PRESENT",
                           "Deprecation claimed, but the token is still present in current code")
            else:
                claim.state = ClaimState.SUPPORTED
                claim.rationale = "Token absent from current code, consistent with the deprecation claim."
                claim.falsifier = "Reopened if the token reappears in current code."
            continue

        claim.state = ClaimState.NOT_DETERMINABLE
        claim.rationale = "No deterministic rule applies to this claim."
        claim.falsifier = "Requires a deterministic rule or human review with recorded evidence."

    _doc_conflicts(excavation, claims, contradict)
    contradictions.sort(key=lambda item: item.contradiction_id)
    links.sort(key=lambda item: (item.claim_id, item.evidence_ref))
    return claims, links, contradictions


def _doc_conflicts(excavation: Excavation, claims: list[Claim], contradict) -> None:
    doc_texts = {
        a.path: excavation.texts.get(a.path, "").lower()
        for a in excavation.artifacts if a.kind == "DOC"
    }
    for claim in claims:
        if claim.verb not in ("IMPLEMENTED", "COMPLETED") or claim.source_kind != "DOC":
            continue
        tokens = _tokens(claim.text)
        for path, text in doc_texts.items():
            if path == claim.source_ref:
                continue
            if any(neg in text for neg in _NEGATIONS) and any(t in text for t in tokens):
                if claim.state != ClaimState.CONTRADICTED:
                    contradict(claim, path, "DOC_CONFLICT",
                               f"{claim.source_ref} claims completion, but {path} states the opposite")
                break


def analyze(excavation: Excavation):
    claims = extract_claims(excavation)
    return evaluate_claims(excavation, claims)
