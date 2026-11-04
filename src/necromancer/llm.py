"""Provider-neutral LLM inference. Optional, pluggable, never required.

Providers receive only the sealed summary and may only produce
Provenance.HYPOTHESIS rows. Model output is untrusted data: it is parsed
against a strict shape and can never change a claim state or the seal.
No vendor is hardcoded as a requirement; offline mode needs nothing.
"""

from __future__ import annotations

import hashlib
import json
import os
import urllib.request
from fractions import Fraction
from typing import Callable

from .models import Hypothesis, Provenance, Report
from .seance import OfflineTemplateProvider

Transport = Callable[[str, dict, dict], dict]

_SYSTEM = (
    "You are an investigator proposing competing explanations. "
    "Respond with JSON only: {\"hypotheses\": [{\"group\": \"...\", "
    "\"statement\": \"...\", \"discriminators\": [\"...\"]}]}. "
    "Give at least two rival statements per group. Never state facts."
)


def sealed_summary(report: Report) -> dict:
    """The only input a model may receive: the already-sealed summary."""
    return {
        "repo_path": report.repo_path,
        "head": report.head,
        "snapshot": report.snapshot,
        "seal": report.seal,
        "claims": [
            {"id": c.claim_id, "text": c.text, "state": c.state.value, "why": c.rationale}
            for c in report.claims
            if c.state.value in ("CONTRADICTED", "UNVERIFIED", "NOT_DETERMINABLE")
        ],
        "abandoned_branches": [b.name for b in report.abandoned_branches],
    }


def _parse_hypotheses(content: str) -> list[Hypothesis]:
    try:
        data = json.loads(content)
        items = data["hypotheses"]
    except (ValueError, KeyError, TypeError) as error:
        raise RuntimeError("model returned malformed hypothesis JSON") from error
    valid: list[tuple[str, str, tuple[str, ...]]] = []
    for item in items if isinstance(items, list) else []:
        if not isinstance(item, dict):
            continue
        statement = item.get("statement")
        discriminators = item.get("discriminators")
        if not isinstance(statement, str) or not statement.strip():
            continue
        if not isinstance(discriminators, list):
            discriminators = []
        valid.append((
            str(item.get("group", "model")),
            statement.strip(),
            tuple(str(d) for d in discriminators if isinstance(d, str)),
        ))
    if not valid:
        raise RuntimeError("model returned no usable hypotheses")
    counts: dict[str, int] = {}
    for group, _statement, _disc in valid:
        counts[group] = counts.get(group, 0) + 1
    return [
        Hypothesis(
            hypothesis_id=hashlib.sha256(f"{group}|{statement}".encode()).hexdigest()[:16],
            group_id=group,
            question=f"Model-proposed explanations for {group}",
            statement=statement,
            discriminators=discriminators,
            confidence=Fraction(1, counts[group]),
            provenance=Provenance.HYPOTHESIS,
        )
        for group, statement, discriminators in valid
    ]


def _urllib_transport(url: str, payload: dict, headers: dict) -> dict:
    request = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json", **headers},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=30) as response:  # noqa: S310 - configured endpoint only
        return json.loads(response.read().decode("utf-8"))


class _ChatProvider:
    name = "chat"

    def __init__(self, transport: Transport | None = None) -> None:
        self.transport = transport or _urllib_transport

    def _call(self, report: Report) -> str:
        raise NotImplementedError

    def generate(self, report: Report) -> list[Hypothesis]:
        return _parse_hypotheses(self._call(report))


class OpenAICompatibleProvider(_ChatProvider):
    """Any OpenAI-compatible chat endpoint (hosted or local server)."""

    name = "openai-compatible"

    def __init__(self, base_url: str = "", model: str = "", api_key: str = "",
                 transport: Transport | None = None) -> None:
        super().__init__(transport)
        self.base_url = (base_url or os.environ.get("NECROMANCER_LLM_BASE_URL", "")).rstrip("/")
        self.model = model or os.environ.get("NECROMANCER_LLM_MODEL", "")
        self.api_key = api_key or os.environ.get("NECROMANCER_LLM_API_KEY", "")

    def _call(self, report: Report) -> str:
        if not self.base_url or not self.model:
            raise RuntimeError("NECROMANCER_LLM_BASE_URL / NECROMANCER_LLM_MODEL not configured")
        headers = {"Authorization": f"Bearer {self.api_key}"} if self.api_key else {}
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": _SYSTEM},
                {"role": "user", "content": json.dumps(sealed_summary(report), sort_keys=True)},
            ],
            "temperature": 0,
        }
        data = self.transport(f"{self.base_url}/chat/completions", payload, headers)
        try:
            return str(data["choices"][0]["message"]["content"])
        except (KeyError, IndexError, TypeError) as error:
            raise RuntimeError("unexpected OpenAI-compatible response shape") from error


class OllamaProvider(_ChatProvider):
    """Local Ollama server. No credentials, nothing leaves the machine."""

    name = "ollama"

    def __init__(self, host: str = "", model: str = "",
                 transport: Transport | None = None) -> None:
        super().__init__(transport)
        self.host = (host or os.environ.get("NECROMANCER_OLLAMA_HOST", "http://localhost:11434")).rstrip("/")
        self.model = model or os.environ.get("NECROMANCER_LLM_MODEL", "")

    def _call(self, report: Report) -> str:
        if not self.model:
            raise RuntimeError("NECROMANCER_LLM_MODEL not configured for Ollama")
        payload = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": _SYSTEM},
                {"role": "user", "content": json.dumps(sealed_summary(report), sort_keys=True)},
            ],
            "stream": False,
        }
        data = self.transport(f"{self.host}/api/chat", payload, {})
        try:
            return str(data["message"]["content"])
        except (KeyError, TypeError) as error:
            raise RuntimeError("unexpected Ollama response shape") from error


def get_provider(name: str | None = None, transport: Transport | None = None):
    """Resolve a provider by name. Default and fallback: offline."""
    chosen = (name or os.environ.get("NECROMANCER_LLM_PROVIDER", "offline")).strip().lower()
    if chosen == "offline":
        return OfflineTemplateProvider()
    if chosen == "openai-compatible":
        return OpenAICompatibleProvider(transport=transport)
    if chosen == "ollama":
        return OllamaProvider(transport=transport)
    raise ValueError(f"unknown LLM provider: {chosen!r} (offline, openai-compatible, ollama)")
