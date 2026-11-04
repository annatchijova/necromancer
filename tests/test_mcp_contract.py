"""MCP contract: real stdio client against the real server.

The server must expose typed read-only tools, return sealed evidence, and
never modify the target repository. No model is involved.
"""

import asyncio
import json
import os
import subprocess
import sys

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

EXPECTED_TOOLS = {
    "excavate_repository",
    "get_timeline",
    "list_claims",
    "get_contradictions",
    "get_hypothesis_context",
    "get_resurrection_plan",
}


def _params() -> StdioServerParameters:
    env = dict(os.environ)
    return StdioServerParameters(
        command=sys.executable,
        args=["-m", "necromancer.mcp_server"],
        env=env,
    )


def _payload(result) -> dict:
    if getattr(result, "structuredContent", None):
        return result.structuredContent
    text = result.content[0].text
    return json.loads(text)


async def _exercise(fixture_a: str) -> dict:
    async with stdio_client(_params()) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            tools = await session.list_tools()
            names = {tool.name for tool in tools.tools}
            report_result = await session.call_tool(
                "excavate_repository", {"path": fixture_a})
            claims_result = await session.call_tool(
                "list_claims", {"path": fixture_a, "state": "CONTRADICTED"})
            bad_result = await session.call_tool(
                "excavate_repository", {"path": "/nonexistent/definitely-not-a-repo"})
            return {
                "names": names,
                "report": _payload(report_result),
                "report_error": bool(report_result.is_error),
                "claims": _payload(claims_result),
                "bad_error": bool(bad_result.is_error),
            }


def test_mcp_contract_over_stdio(synthetic):
    fixture_a = str(synthetic["a"])
    before = subprocess.run(
        ["git", "-C", fixture_a, "status", "--porcelain"],
        capture_output=True, text=True, check=True).stdout
    outcome = asyncio.run(_exercise(fixture_a))
    after = subprocess.run(
        ["git", "-C", fixture_a, "status", "--porcelain"],
        capture_output=True, text=True, check=True).stdout

    assert outcome["names"] == EXPECTED_TOOLS
    assert outcome["report_error"] is False
    assert outcome["report"]["seal"]
    states = {claim["state"] for claim in outcome["report"]["claims"]}
    assert "CONTRADICTED" in states
    assert outcome["claims"]["claims"], "state filter must return contradicted claims"
    assert all(c["state"] == "CONTRADICTED" for c in outcome["claims"]["claims"])
    for claim in outcome["report"]["claims"]:
        assert claim["origin"] and claim["scope"] and claim["falsifier"]
    assert outcome["bad_error"] is True
    assert before == after == "", "MCP excavation must not modify the target"
