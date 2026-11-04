"""Provider-neutral inference: adapters, offline fallback, seal isolation."""

import json

import pytest

from necromancer import llm
from necromancer.cli import investigate
from necromancer.models import Provenance


def _content(hypotheses):
    return json.dumps({"hypotheses": hypotheses})


def test_openai_compatible_adapter_parses_and_labels(synthetic):
    captured = {}

    def fake_transport(url, payload, headers):
        captured["url"] = url
        captured["payload"] = payload
        return {"choices": [{"message": {"content": _content([
            {"group": "g1", "statement": "It was partial.", "discriminators": ["inspect diff"]},
            {"group": "g1", "statement": "It regressed.", "discriminators": ["list later commits"]},
        ])}}]}

    provider = llm.OpenAICompatibleProvider(
        base_url="http://localhost:9999/v1", model="any-model", transport=fake_transport)
    report = investigate(str(synthetic["a"]), provider_name="offline")
    hypotheses = provider.generate(report)
    assert captured["url"].endswith("/chat/completions")
    assert captured["payload"]["model"] == "any-model"
    # The model only ever receives the sealed summary, identified by seal.
    sent = json.loads(captured["payload"]["messages"][1]["content"])
    assert sent["seal"] == report.seal
    assert hypotheses and all(h.provenance == Provenance.HYPOTHESIS for h in hypotheses)


def test_ollama_adapter_uses_local_chat_shape(synthetic):
    captured = {}

    def fake_transport(url, payload, headers):
        captured["url"] = url
        captured["payload"] = payload
        return {"message": {"content": _content([
            {"group": "g", "statement": "A.", "discriminators": []},
            {"group": "g", "statement": "B.", "discriminators": []},
        ])}}

    provider = llm.OllamaProvider(host="http://localhost:11434", model="local-model",
                                  transport=fake_transport)
    report = investigate(str(synthetic["a"]))
    assert len(provider.generate(report)) == 2
    assert captured["url"].endswith("/api/chat")
    assert captured["payload"]["stream"] is False


def test_malformed_model_output_is_rejected(synthetic):
    provider = llm.OpenAICompatibleProvider(
        base_url="http://localhost:9999/v1", model="m",
        transport=lambda url, payload, headers: {"choices": [{"message": {"content": "not json"}}]},
    )
    report = investigate(str(synthetic["a"]))
    with pytest.raises(RuntimeError):
        provider.generate(report)


def test_provider_failure_falls_back_offline_without_touching_seal(synthetic):
    def broken_transport(url, payload, headers):
        raise ConnectionError("no server")

    offline = investigate(str(synthetic["a"]), provider_name="offline")
    degraded = investigate(
        str(synthetic["a"]), provider_name="openai-compatible", transport=broken_transport)
    assert degraded.seal == offline.seal
    assert degraded.hypotheses, "offline hypotheses must fill the gap"
    assert all(h.provenance == Provenance.HYPOTHESIS for h in degraded.hypotheses)
    assert any("offline hypotheses used" in w for w in degraded.warnings)


def test_unknown_provider_is_an_error_not_a_silent_default():
    with pytest.raises(ValueError):
        llm.get_provider("carrier-pigeon")
