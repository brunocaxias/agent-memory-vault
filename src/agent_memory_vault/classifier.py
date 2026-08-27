from __future__ import annotations

import json
import os
from dataclasses import dataclass

import httpx

from .config import Settings
from .models import ClassifierOutput


class ClassifierError(RuntimeError):
    pass


class ClassifierNotConfigured(ClassifierError):
    pass


@dataclass(frozen=True)
class Classification:
    output: ClassifierOutput
    input_tokens: int
    output_tokens: int


SYSTEM_PROMPT = """\
You extract durable Codex work memories from a redacted transcript excerpt.
Return JSON with exactly two top-level keys: "memories" and "handoff".

Eligible memories:
- an explicit statement made by the user;
- a project outcome or runbook step that the transcript shows was actually verified.

Reject:
- assistant guesses, proposed plans presented as completed, uncertain inferences;
- secrets, credentials, personal health, personal finances, contacts, diary material;
- transient conversational details and facts with no future value.

Each item must contain:
type: preference | decision | project-state | runbook | fact | lesson
scope: global | project:<slug>
content: one short durable statement
eligibility: explicit-user-statement | verified-project-outcome
evidence_excerpt: a short verbatim redacted excerpt supporting the memory
supersedes_id: null unless the transcript explicitly identifies an older memory
review_after: YYYY-MM-DD
entities: up to 12 concise named people, projects, tools, systems, or organizations
concepts: up to 12 concise durable topics grounded in the content and evidence
effective_from: optional YYYY-MM-DD when the evidence says when this became true
effective_to: optional YYYY-MM-DD when the evidence says when this ceased to be true
relations: up to 12 grounded objects with type, target, and target_kind
  (memory | entity | concept). Use short snake_case types such as requires,
  affects, blocks, supports, or relates_to. Never invent a relation target.

For a project session, handoff may contain a concise, evidence-grounded working
handoff with summary, completed, changed_files, verification, blockers,
next_steps, and open_questions. Use null when there is no useful project handoff.
This is temporary continuity context, not a durable memory: capture only work
actually visible in the redacted transcript and never include secrets or guesses.

Use project-state review after 30 days, decisions/runbooks after 180 days, and
global preferences/stable facts after 365 days. Empty memories are valid.
Use empty entity/concept/relation arrays when no grounded label is useful. Do not add IDs,
status, timestamps, priority, or claims absent from evidence.
"""


class DeepSeekClassifier:
    def __init__(self, settings: Settings, client: httpx.Client | None = None):
        self.settings = settings
        self.client = client

    def classify(self, excerpt: str, project_slug: str | None) -> Classification:
        api_key = os.environ.get(self.settings.classifier_api_key_env)
        if not api_key:
            raise ClassifierNotConfigured(
                f"{self.settings.classifier_api_key_env} is not configured"
            )
        context = (
            f"Current project slug: {project_slug or 'none'}.\n"
            "Output a JSON object only.\n\n"
            f"{excerpt}"
        )
        payload = {
            "model": self.settings.classifier_model,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": context},
            ],
            "thinking": {"type": "disabled"},
            "response_format": {"type": "json_object"},
            "max_tokens": self.settings.classifier_max_tokens,
            "stream": False,
        }
        owned_client = self.client is None
        client = self.client or httpx.Client(
            base_url=self.settings.classifier_base_url,
            timeout=httpx.Timeout(60.0, connect=15.0),
        )
        try:
            response = client.post(
                "/chat/completions",
                headers={"Authorization": f"Bearer {api_key}"},
                json=payload,
            )
            response.raise_for_status()
            body = response.json()
        except (httpx.HTTPError, json.JSONDecodeError, ValueError) as exc:
            raise ClassifierError(f"classifier request failed: {exc}") from exc
        finally:
            if owned_client:
                client.close()

        try:
            raw_content = body["choices"][0]["message"]["content"]
            output = ClassifierOutput.model_validate_json(raw_content)
            usage = body.get("usage", {})
            input_tokens = int(usage.get("prompt_tokens", 0))
            output_tokens = int(usage.get("completion_tokens", 0))
        except (KeyError, IndexError, TypeError, ValueError) as exc:
            raise ClassifierError("classifier returned invalid or empty JSON") from exc
        return Classification(output, input_tokens, output_tokens)
