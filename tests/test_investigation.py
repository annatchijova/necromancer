import subprocess

from necromancer.cli import investigate
from necromancer.models import ClaimState


def test_fixture_a_incomplete_fix_is_contradicted(synthetic):
    report = investigate(str(synthetic["a"]))
    fixed = [c for c in report.claims if c.verb == "FIXED"]
    assert fixed, "fixture A must yield a FIXED claim"
    assert any(c.state == ClaimState.CONTRADICTED for c in fixed)
    assert any(item.kind == "INCOMPLETE_PATCH" for item in report.contradictions)


def test_fixture_b_abandoned_branch_is_surfaced(synthetic):
    report = investigate(str(synthetic["b"]))
    names = [branch.name for branch in report.abandoned_branches]
    assert "fix/parser-last-line" in names
    assert any(
        action.priority == 0 and "fix/parser-last-line" in action.title
        for action in report.actions
    )
    assert any(
        hyp.group_id == "branch:fix/parser-last-line" for hyp in report.hypotheses
    )
    # Hypotheses must never leak into the sealed facts.
    assert all(hyp.provenance.value == "HYPOTHESIS" for hyp in report.hypotheses)


def test_fixture_c_false_completion_is_contradicted(synthetic):
    report = investigate(str(synthetic["c"]))
    pdf_claims = [
        c for c in report.claims
        if "pdf" in c.text.lower() and c.verb in ("IMPLEMENTED", "COMPLETED")
    ]
    assert pdf_claims, "fixture C must yield a PDF completion claim"
    assert any(c.state == ClaimState.CONTRADICTED for c in pdf_claims)


def test_investigation_is_deterministic_and_read_only(synthetic):
    repo = str(synthetic["a"])
    before = subprocess.run(
        ["git", "-C", repo, "status", "--porcelain"],
        capture_output=True, text=True, check=True,
    ).stdout
    first = investigate(repo)
    second = investigate(repo)
    after = subprocess.run(
        ["git", "-C", repo, "status", "--porcelain"],
        capture_output=True, text=True, check=True,
    ).stdout
    assert first.seal == second.seal
    assert before == after == ""


def test_claims_carry_provenance_attributes(synthetic):
    report = investigate(str(synthetic["c"]))
    for claim in report.claims:
        assert claim.origin, "origin must travel with the claim"
        assert claim.scope, "scope must travel with the claim"
        assert claim.falsifier, "falsifier must travel with the claim"
