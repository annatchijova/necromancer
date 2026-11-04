"""Command line entry point and investigation assembly.

Order matters: excavate, derive claims, seal, and only then generate
hypotheses. The seal can therefore never contain model output.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from . import coroner, ledger as ledger_mod, planner, seance
from .canonicalize import seal
from .chronos import build_events
from .excavator import ExcavationError, excavate
from .export import to_json, to_markdown
from .models import Report


def investigate(repo_path: str, ledger_path: str | None = None) -> Report:
    excavation = excavate(repo_path)
    claims, links, contradictions = coroner.analyze(excavation)
    abandoned = [
        branch for branch in excavation.branches
        if not branch.merged_into_head and branch.name != excavation.current_branch
    ]
    report = Report(
        repo_path=excavation.repo_path,
        head=excavation.head,
        events=build_events(excavation),
        claims=claims,
        links=links,
        contradictions=contradictions,
        abandoned_branches=abandoned,
        warnings=list(excavation.warnings),
    )
    report.seal = seal(report.sealable_payload())
    provider = seance.OfflineTemplateProvider()
    report.hypotheses = provider.generate(report)
    report.actions = planner.build_plan(report)
    if ledger_path:
        conn = ledger_mod.connect(ledger_path)
        try:
            ledger_mod.append(
                conn, "INVESTIGATION",
                {"seal": report.seal, "head": report.head, "claims": len(report.claims)},
                [artifact.sha256 for artifact in excavation.artifacts],
            )
        finally:
            conn.close()
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="necromancer")
    sub = parser.add_subparsers(dest="command", required=True)
    exc = sub.add_parser("excavate", help="Excavate a local git repository (read-only)")
    exc.add_argument("repo")
    exc.add_argument("--out", default="necromancer-report.json")
    exc.add_argument("--markdown", default="")
    exc.add_argument("--ledger", default="")
    ver = sub.add_parser("verify-ledger", help="Verify an evidence ledger chain")
    ver.add_argument("db")
    args = parser.parse_args(argv)

    if args.command == "verify-ledger":
        conn = ledger_mod.connect(args.db)
        try:
            result = ledger_mod.verify_chain(ledger_mod.fetch_all(conn))
        finally:
            conn.close()
        print(f"linkage_ok={result['linkage_ok']} integrity_ok={result['integrity_ok']}")
        for issue in result["issues"]:
            print(f"FAIL: {issue}")
        return 0 if (result["linkage_ok"] and result["integrity_ok"]) else 1

    try:
        report = investigate(args.repo, ledger_path=args.ledger or None)
    except ExcavationError as error:
        print(f"FAIL: {error}", file=sys.stderr)
        return 2
    Path(args.out).write_text(to_json(report), encoding="utf-8")
    if args.markdown:
        Path(args.markdown).write_text(to_markdown(report), encoding="utf-8")
    counts: dict[str, int] = {}
    for claim in report.claims:
        counts[claim.state.value] = counts.get(claim.state.value, 0) + 1
    print(f"seal={report.seal}")
    print(f"events={len(report.events)} claims={len(report.claims)} "
          f"contradictions={len(report.contradictions)} hypotheses={len(report.hypotheses)}")
    print("claims_by_level=" + ", ".join(f"{key}:{counts[key]}" for key in sorted(counts)))
    print(f"wrote {args.out}" + (f" and {args.markdown}" if args.markdown else ""))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
