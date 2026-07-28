from __future__ import annotations

import json
from datetime import date, timedelta
from pathlib import Path

import httpx
import pytest

from agent_memory_vault.classifier import DeepSeekClassifier
from agent_memory_vault.config import Settings
from agent_memory_vault.installer import disable_native_memories, install_hooks


def test_classifier_validates_json(
    settings: Settings,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("DEEPSEEK_API_KEY", "test-key")
    output = {
        "memories": [
            {
                "type": "preference",
                "scope": "global",
                "content": "Prefer local tools.",
                "eligibility": "explicit-user-statement",
                "evidence_excerpt": "Prefer local tools.",
                "supersedes_id": None,
                "review_after": (date.today() + timedelta(days=365)).isoformat(),
            }
        ]
    }

    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        assert body["thinking"] == {"type": "disabled"}
        assert body["response_format"] == {"type": "json_object"}
        return httpx.Response(
            200,
            json={
                "choices": [{"message": {"content": json.dumps(output)}}],
                "usage": {"prompt_tokens": 100, "completion_tokens": 20},
            },
        )

    client = httpx.Client(
        transport=httpx.MockTransport(handler),
        base_url="https://api.deepseek.com",
    )
    result = DeepSeekClassifier(settings, client).classify("Prefer local tools.", None)
    assert result.output.memories[0].content == "Prefer local tools."
    assert result.input_tokens == 100


def test_disable_native_memories_preserves_other_config(tmp_path: Path) -> None:
    path = tmp_path / "config.toml"
    path.write_text(
        'model = "gpt-test"\n\n[features]\nmemories = true\nmulti_agent = true\n',
        encoding="utf-8",
    )
    disable_native_memories(path)
    text = path.read_text(encoding="utf-8")
    assert 'model = "gpt-test"' in text
    assert "multi_agent = true" in text
    assert "memories = false" in text
    assert "[memories]" in text
    assert "generate_memories = false" in text
    assert "use_memories = false" in text


def test_install_hooks_preserves_unrelated_hooks(tmp_path: Path) -> None:
    path = tmp_path / "hooks.json"
    path.write_text(
        json.dumps({"hooks": {"Stop": [{"hooks": [{"type": "command", "command": "echo stop"}]}]}}),
        encoding="utf-8",
    )
    install_hooks(path, Path("/opt/memory/bin"))
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["hooks"]["Stop"]
    assert payload["hooks"]["SessionStart"][0]["hooks"][0]["additionalContextLimit"] == 5000
    assert payload["hooks"]["SessionEnd"][0]["hooks"][0]["timeout"] == 3
