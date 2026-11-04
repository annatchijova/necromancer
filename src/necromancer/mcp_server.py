"""First-class MCP server: deterministic evidence for external clients.

Built on the official Python MCP SDK. Every tool is read-only with
respect to the target repository, calls no language model, and uses no
sampling: external clients do their own reasoning over NECROMANCER's
sealed evidence. Hypotheses, when returned, stay labeled HYPOTHESIS.
"""

from __future__ import annotations

from mcp.server.mcpserver import MCPServer

from .acquire import AcquisitionError
from .cli import investigate, investigate_source
from .excavator import ExcavationError
from .export import report_to_dict

_INSTRUCTIONS = (
    "NECROMANCER is a read-only evidence engine for abandoned repositories. "
    "Tools return deterministic, provenance-linked evidence. Claim states "
    "are facts about the evidence; hypotheses are labeled proposals and "
    "never facts. Target repositories are never modified or executed."
)


def _validate(path: str, snapshot: str) -> None:
    if not isinstance(path, str) or not path.strip():
        raise ValueError("path must be a non-empty local repository path")
    if snapshot not in ("head", "worktree"):
        raise ValueError("snapshot must be 'head' or 'worktree'")


def _report(path: str, snapshot: str) -> dict:
    _validate(path, snapshot)
    try:
        return report_to_dict(investigate(path, snapshot=snapshot))
    except ExcavationError as error:
        raise ValueError(str(error)) from error


def build_server() -> MCPServer:
    server = MCPServer("necromancer", instructions=_INSTRUCTIONS)

    @server.tool()
    def excavate_repository(path: str, snapshot: str = "head") -> dict:
        """Excavate a local Git repository (read-only) and return the full sealed investigation report."""
        return _report(path, snapshot)

    @server.tool()
    def get_timeline(path: str, snapshot: str = "head") -> dict:
        """Return the provenance-linked event timeline and evidence seal for a repository."""
        report = _report(path, snapshot)
        return {"seal": report["seal"], "snapshot": report["snapshot"],
                "events": report["events"]}

    @server.tool()
    def list_claims(path: str, state: str = "", snapshot: str = "head") -> dict:
        """List extracted claims with origin, scope and falsifier. Optionally filter by state (VERIFIED, SUPPORTED, CONTRADICTED, UNVERIFIED, NOT_DETERMINABLE)."""
        report = _report(path, snapshot)
        claims = report["claims"]
        if state:
            claims = [claim for claim in claims if claim["state"] == state.upper()]
        return {"seal": report["seal"], "claims": claims}

    @server.tool()
    def get_contradictions(path: str, snapshot: str = "head") -> dict:
        """Return deterministic contradictions between claims and positive evidence."""
        report = _report(path, snapshot)
        return {"seal": report["seal"], "contradictions": report["contradictions"],
                "links": report["links"]}

    @server.tool()
    def get_hypothesis_context(path: str, snapshot: str = "head") -> dict:
        """Return sealed claim summaries plus labeled HYPOTHESIS proposals so an external client can reason itself. Hypotheses are not facts."""
        report = _report(path, snapshot)
        open_claims = [
            claim for claim in report["claims"]
            if claim["state"] in ("CONTRADICTED", "UNVERIFIED", "NOT_DETERMINABLE")
        ]
        return {
            "seal": report["seal"],
            "open_claims": open_claims,
            "abandoned_branches": report["abandoned_branches"],
            "hypotheses_not_facts": report["hypotheses_not_facts"],
        }

    @server.tool()
    def get_resurrection_plan(path: str, snapshot: str = "head") -> dict:
        """Return the prioritized, reversible-only recovery plan for a repository."""
        report = _report(path, snapshot)
        return {"seal": report["seal"], "resurrection_plan": report["resurrection_plan"]}

    @server.tool()
    def get_health_indicators(path: str, snapshot: str = "head") -> dict:
        """Return repository health and abandonment indicators with their evidence. Indicators, never a verdict."""
        report = _report(path, snapshot)
        return {"seal": report["seal"], "health": report["health"]}

    @server.tool()
    def get_evidence_graph(path: str, snapshot: str = "head") -> dict:
        """Return the typed evidence graph (claims, commits, files, hypotheses, actions). Speculative edges are labeled."""
        report = _report(path, snapshot)
        return {"seal": report["seal"], "graph": report["graph"]}

    @server.tool()
    def acquire_github_repository(url: str, snapshot: str = "head") -> dict:
        """Acquire a public https://github.com repository into an isolated bounded workspace and return its sealed report. Only github.com HTTPS URLs are accepted; acquisition failures are errors, not findings."""
        if snapshot not in ("head", "worktree"):
            raise ValueError("snapshot must be 'head' or 'worktree'")
        try:
            return report_to_dict(investigate_source(url, snapshot=snapshot))
        except (ExcavationError, AcquisitionError, ValueError) as error:
            raise ValueError(str(error)) from error

    return server


def main() -> None:
    build_server().run(transport="stdio")


if __name__ == "__main__":
    main()
