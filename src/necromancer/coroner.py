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
    (r"\b(validated|validates|validar|validad\w*)\b", "VALIDATED"),
    (r"\b(sanitized|sanitizes|sanead\w*)\b", "SANITIZED"),
    (r"\b(deprecated|deprecad\w*|removed|eliminad\w*)\b", "DEPRECATED"),
]
_FIX_WORDS = ("fix", "correg", "resolv", "resuel", "patch", "solucion")
# Incomplete markers are code conventions, matched case-sensitively as
# whole tokens. Substring matching on lowered text is forbidden: it fires
# on the Spanish word "todo", on identifiers containing "xxx", and on
# prose that merely discusses incompleteness (calibration, Round 3).
_INCOMPLETE_RE = re.compile(r"\b(TODO|FIXME|XXX)\b|NotImplementedError")
_NEGATIONS = ("not implemented", "not yet", "no implementad", "sin implementar", "pendiente", "not completed")
# A claim sentence that itself negates the feature ("is not implemented
# yet") asserts absence. Evidence of absence agrees with it; it can never
# be contradicted by the stub it describes (Round 5, case N3).
_NEGATED_CLAIM = ("not implemented", "not yet implemented", "not completed",
                  "no implementad", "sin implementar", "not yet")
# Platform scope tokens. A claim scoped to one platform cannot be
# confirmed-contradicted by a marker in a file scoped to another
# (Round 5, case A4); that is a scope mismatch, hence POTENTIAL.
_PLATFORMS = {"linux", "windows", "win", "win32", "macos", "darwin", "osx",
              "android", "ios"}
# Polarity antonyms for document conflicts: "complete" in one document
# and "incomplete" in another is opposition even when only the subject
# token is shared (Round 5, case A3).
_ANTONYMS = {"complete": "incomplete", "completed": "incomplete",
             "implemented": "unimplemented", "working": "broken",
             "fixed": "broken", "completo": "incompleto",
             "implementado": "sin implementar"}
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


_PLANNED_MARKERS = (
    "will be", "will implement", "planned", "plan:", "propose", "proposal",
    "should be", "would be", "hypothet", "to be implemented", "next sprint",
    "planificado", "propuesta", "se propone", "debería", "habría que", "por implementar",
)
_HISTORICAL_MARKERS = (
    "previously", "formerly", "at the time", "back then", "historical",
    "anteriormente", "en su momento", "antes se", "was removed in", "was fixed in",
)


def _modality(sentence: str, verb: str) -> str:
    lower = sentence.lower()
    if verb == "DEPRECATED":
        return "DEPRECATED"
    if any(marker in lower for marker in _PLANNED_MARKERS):
        return "PLANNED"
    if any(marker in lower for marker in _HISTORICAL_MARKERS) or re.search(
        r"\b(was|fue|era)\b[^.]{0,60}\bv?\d+\.\d+", lower
    ):
        return "HISTORICAL"
    return "CURRENT"


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
                    modality=_modality(sentence, verb),
                    subject_tokens=tuple(_tokens(sentence)),
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
                                origin=f"commit:{commit.commit_hash}",
                                modality=_modality(sentence, verb),
                                subject_tokens=tuple(_tokens(sentence))))
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

    def potential(claim: Claim, ref: str, kind: str, detail: str) -> None:
        """Record a possible conflict that changes no state (Round 4)."""
        cid = hashlib.sha256(f"{claim.claim_id}|{ref}|{kind}".encode()).hexdigest()[:16]
        contradictions.append(Contradiction(
            cid, claim.claim_id, ref, kind, detail, qualification="POTENTIAL"))

    def contradict(claim: Claim, ref: str, kind: str, detail: str) -> None:
        # A plan, proposal or historical statement cannot be contradicted
        # by the current tree; it can only raise a potential conflict.
        # Deprecation claims assert the present, so they stay eligible.
        if claim.modality not in ("CURRENT", "DEPRECATED"):
            potential(claim, ref, kind,
                      f"{detail} (potential only: claim modality is {claim.modality})")
            return
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
                if claim.modality == "HISTORICAL":
                    # A historical claim was true when written. If a file
                    # its subject names (by stem) now carries an incomplete
                    # marker, the tension is POTENTIAL, never CONFIRMED:
                    # history is not a current promise (Round 5, case A2).
                    stems = {t[:6] for t in _tokens(claim.text)
                             if len(t) >= 6} - {"fixed", "correg"}
                    for path in sorted(code_texts):
                        path_stems = {
                            w[:6] for w in _word_set(
                                path.replace("/", " ").replace("_", " "))
                            if len(w) >= 6
                        }
                        if stems & path_stems and _INCOMPLETE_RE.search(
                                code_texts[path]):
                            potential(claim, path, "STALE_HISTORY",
                                      f"Historical claim; {path} now carries an "
                                      "incomplete marker. The claim may have been "
                                      "true when written; review the timeline.")
                            break
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
                                      f"Bound fix commit {commit.commit_hash[:8]} (binding score {bind_score}; token-overlap strength, not a probability) changed {', '.join(changed[:4])}",
                                      binding_score=bind_score,
                                      match_basis="origin" if claim.origin == f"commit:{commit.commit_hash}" else "message/path tokens"))
            has_test = any(
                next((a.kind for a in excavation.artifacts if a.path == p), "") == "TEST"
                for p in changed
            ) or bool(token_in_tests)
            incomplete_in = [
                p for p in changed
                if _INCOMPLETE_RE.search(code_texts.get(p, ""))
            ]
            # A revert confirms only when it is tied to THIS fix: git
            # revert messages quote the original subject or cite its
            # hash. Mere file overlap is fan-out bait — one revert
            # restoring hundreds of bundle files "reverted" 683 claims
            # on VIGÍA (3 real revert commits). File-only overlap is
            # POTENTIAL (Round 5 stress finding).
            bound_subject_tokens = _word_set(commit.subject) - _GENERIC_VERB_WORDS
            reverted = None
            revert_file_only = None
            for candidate in reverts:
                if not ({p for _s, p in candidate.files} & set(changed)):
                    continue
                revert_text = f"{candidate.subject} {candidate.body}".lower()
                shared = bound_subject_tokens & _word_set(revert_text)
                if commit.commit_hash[:8] in revert_text or len(shared) >= 2:
                    reverted = candidate
                    break
                revert_file_only = revert_file_only or candidate
            if reverted is None and revert_file_only is not None:
                potential(claim, revert_file_only.commit_hash[:12], "REVERTED_FIX",
                          f"Revert {revert_file_only.commit_hash[:8]} touches the "
                          "same files but neither quotes this fix nor cites its "
                          "hash; subject relation unestablished. Review required.")
            # Scope qualification: a strict marker left inside a file the
            # bound fix itself changed shares the claim scope (the file).
            # Markers in files the fix never touched are not in
            # incomplete_in at all and can never contradict the claim.
            # Platform scope is part of that scope: a marker in a file
            # scoped to a different platform than the claim demotes to
            # POTENTIAL instead of confirming (Round 5, case A4).
            claim_platforms = {
                t for t in _word_set(claim.text) if t in _PLATFORMS
            }
            relevant_incomplete = []
            for path in incomplete_in:
                file_platforms = {
                    t for t in _word_set(path.replace("/", " ").replace("_", " "))
                    if t in _PLATFORMS
                }
                if claim_platforms and file_platforms \
                        and not (claim_platforms & file_platforms):
                    potential(claim, path, "INCOMPLETE_PATCH",
                              f"Marker in {path}, but the file is scoped to "
                              f"{sorted(file_platforms)} while the claim is scoped to "
                              f"{sorted(claim_platforms)}; scope mismatch requires review")
                else:
                    relevant_incomplete.append(path)

            if reverted is not None:
                contradict(claim, reverted.commit_hash[:12], "REVERTED_FIX",
                           f"Fix in {commit.commit_hash[:8]} was later reverted by {reverted.commit_hash[:8]}")
            elif relevant_incomplete:
                contradict(claim, relevant_incomplete[0], "INCOMPLETE_PATCH",
                           f"Fix documented, but {relevant_incomplete[0]} still contains a subject-related incomplete marker")
            elif has_test:
                claim.state = ClaimState.SUPPORTED
                claim.rationale = "Fix commit changes code and a test artifact mentions it, but target tests are never executed and token presence is a weak oracle. Verification is supported, not demonstrated."
                claim.falsifier = "Upgraded only by a trusted execution showing the test fails before and passes after the fix."
            else:
                claim.state = ClaimState.SUPPORTED
                claim.rationale = "Fix documented and code changed, but no regression test was found. Verification not demonstrated."
                claim.falsifier = "Upgraded only by a regression test that fails on the pre-fix code; downgraded if the patch proves incomplete."
            continue

        if claim.verb in ("IMPLEMENTED", "COMPLETED", "VALIDATED", "SANITIZED"):
            if not tokens:
                claim.state = ClaimState.NOT_DETERMINABLE
                claim.rationale = "Claim names no searchable feature token."
                claim.falsifier = "Requires a searchable feature name in the claim."
                continue
            if any(neg in claim.text.lower() for neg in _NEGATED_CLAIM):
                # The claim itself asserts absence. A stub agrees with it;
                # implemented code would be the surprise, and even that is
                # stale-documentation territory: POTENTIAL, never CONFIRMED.
                stub_agrees = [
                    p for p, text in code_texts.items()
                    if _INCOMPLETE_RE.search(text)
                    and any(t in text.lower() or t in p.lower() for t in tokens)
                ]
                if stub_agrees:
                    claim.state = ClaimState.SUPPORTED
                    claim.rationale = (
                        "Claim states the feature is not implemented, and the "
                        f"only matching code is a stub in {stub_agrees[0]}. "
                        "The evidence agrees with the claim.")
                    claim.falsifier = "Reopened if a real implementation of the feature is located."
                    links.append(EvidenceLink(
                        claim.claim_id, stub_agrees[0], Relation.SUPPORTS,
                        "Stub agrees with the negated claim"))
                elif tokens and any(t in code for t in tokens):
                    potential(claim, claim.source_ref, "NEGATED_CLAIM_STALE",
                              "Claim states absence, but matching code exists; "
                              "documentation may be stale. Review required.")
                    claim.state = ClaimState.UNVERIFIED
                    claim.rationale = "Negated claim with matching code present; scope unresolved."
                    claim.falsifier = "Resolved by checking whether the code implements the claimed feature."
                else:
                    claim.state = ClaimState.NOT_DETERMINABLE
                    claim.rationale = "Negated claim; no matching code or stub was found to agree or disagree."
                    claim.falsifier = "Resolved by locating the feature or its stub."
                continue
            stub_paths = [
                p for p, text in code_texts.items()
                if _INCOMPLETE_RE.search(text)
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
            # CONFIRMED requires the deprecated subject to be a code
            # identifier that is still DEFINED in current code. Narrative
            # prose containing "removed" (an airplane story, a design
            # note) shares generic tokens with code by accident and was
            # confirmed as STILL_PRESENT on real repositories (Round 5
            # adjudication). Mention without definition is POTENTIAL.
            identifiers = [
                t for t in tokens
                if "_" in t or (t.isalpha() and any(ch.isupper() for ch in t[1:]))
            ] + re.findall(r"`([A-Za-z_][\w\.]*)`", claim.text) \
                + re.findall(r"\b[A-Za-z][\w]*(?:_[\w]+)+\b", claim.text) \
                + re.findall(r"\b[A-Z][a-z]+(?:[A-Z][a-z]+)+\b", claim.text)
            defined_in = None
            defined_ident = ""
            for ident in identifiers:
                pattern = re.compile(
                    rf"(?:def|class)\s+{re.escape(ident)}\b|^\s*{re.escape(ident)}\s*=",
                    re.MULTILINE)
                defined_in = next(
                    (p for p in sorted(code_texts)
                     if kind_by_path.get(p) == "CODE"
                     and pattern.search(code_texts[p])),
                    None)
                if defined_in:
                    defined_ident = ident
                    break
            if defined_in:
                contradict(claim, defined_in, "STILL_PRESENT",
                           f"Deprecation claimed, but {defined_ident} is still defined in {defined_in}")
            elif token_in_code:
                code_file = next(
                    (p for p in sorted(code_texts)
                     if kind_by_path.get(p) == "CODE"
                     and any(t in code_texts[p].lower() for t in tokens)),
                    claim.source_ref,
                )
                potential(claim, code_file, "STILL_PRESENT",
                          "Deprecated subject is mentioned in current code but "
                          "not defined there; the claim may be narrative or "
                          "scoped elsewhere. Review required.")
                claim.state = ClaimState.UNVERIFIED
                claim.rationale = "Deprecation claimed; subject mentioned but not defined in code."
                claim.falsifier = "Resolved by locating a definition of the deprecated subject in current code."
            else:
                claim.state = ClaimState.SUPPORTED
                claim.rationale = "Token absent from current code, consistent with the deprecation claim."
                claim.falsifier = "Reopened if the token reappears in current code."
            continue

        claim.state = ClaimState.NOT_DETERMINABLE
        claim.rationale = "No deterministic rule applies to this claim."
        claim.falsifier = "Requires a deterministic rule or human review with recorded evidence."

    _doc_conflicts(excavation, claims, contradictions)
    contradictions.sort(key=lambda item: item.contradiction_id)
    links.sort(key=lambda item: (item.claim_id, item.evidence_ref))
    return claims, links, contradictions


def _doc_conflicts(excavation: Excavation, claims: list[Claim],
                   contradictions: list[Contradiction]) -> None:
    """Sentence-level document disagreement, always POTENTIAL (Round 4).

    A whole-document match is meaningless: one negated sentence about a
    different subject in a long research document cannot contradict an
    implementation claim. The negated sentence itself must share at
    least two subject tokens with the claim, and even then the result is
    a potential conflict for human review, never a state change, because
    documentation disagreement is not code disagreement.
    """
    import hashlib as _hashlib

    doc_lines: dict[str, list[str]] = {
        a.path: excavation.texts.get(a.path, "").splitlines()
        for a in excavation.artifacts if a.kind == "DOC"
    }
    for claim in claims:
        if claim.verb not in ("IMPLEMENTED", "COMPLETED") or claim.source_kind != "DOC":
            continue
        subject = set(claim.subject_tokens) - _GENERIC_VERB_WORDS
        if len(subject) < 1:
            continue
        for path, lines in doc_lines.items():
            if path == claim.source_ref:
                continue
            hit = None
            for lineno, line in enumerate(lines, start=1):
                lower = line.lower()
                shared = subject & _word_set(line)
                negated_hit = any(neg in lower for neg in _NEGATIONS) \
                    and len(shared) >= 2
                # Polarity opposition with a single shared subject token
                # ("complete" here, "incomplete" there) is also a
                # sentence-level conflict worth review (case A3).
                antonym_hit = len(shared) >= 1 and any(
                    _ANTONYMS[token] in lower
                    for token in subject if token in _ANTONYMS)
                if negated_hit or antonym_hit:
                    hit = (lineno, line.strip(), sorted(shared))
                    break
            if hit is None:
                continue
            lineno, quote, shared = hit
            cid = _hashlib.sha256(
                f"{claim.claim_id}|{path}:{lineno}|DOC_CONFLICT".encode()
            ).hexdigest()[:16]
            contradictions.append(Contradiction(
                cid, claim.claim_id, f"{path}:{lineno}", "DOC_CONFLICT",
                f"Potential conflict only: {path}:{lineno} negates a shared subject "
                f"({', '.join(shared)}): \"{quote[:120]}\". Documentation disagreement "
                "is not code disagreement and changes no claim state.",
                qualification="POTENTIAL",
            ))
            break


def analyze(excavation: Excavation):
    claims = extract_claims(excavation)
    return evaluate_claims(excavation, claims)
