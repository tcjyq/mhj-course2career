"""Provider identity evidence must come from the response, never usage labels."""

import json
from types import SimpleNamespace

import pytest

from course2career.llm_provider import ProviderName
from course2career.llm_providers import DeepSeekProvider
from course2career.provider_validation import load_fixtures, validate_provider
from course2career.provider_verification import Verification


class ScriptedCompletions:
    def __init__(self, returned_model: str | None) -> None:
        self.returned_model = returned_model
        self.calls = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        jd = kwargs["messages"][-1]["content"]
        terms = [term for term in ("Python", "SQL", "需求分析", "Excel") if term in jd]
        content = json.dumps(
            {
                "skills": [
                    {
                        "name": term,
                        "normalized_name": term,
                        "category": "技术",
                        "evidence_text": term,
                    }
                    for term in terms
                ]
            },
            ensure_ascii=False,
        )
        return SimpleNamespace(
            model=self.returned_model,
            usage=SimpleNamespace(prompt_tokens=20, completion_tokens=10),
            choices=[SimpleNamespace(message=SimpleNamespace(content=content))],
        )


@pytest.mark.parametrize("returned", [None, "unknown-server-model"])
def test_usage_display_label_cannot_certify_model_identity(returned) -> None:
    completions = ScriptedCompletions(returned)
    client = DeepSeekProvider(
        api_key="synthetic-only",
        model="deepseek-flash",
        sdk_client=SimpleNamespace(chat=SimpleNamespace(completions=completions)),
    )
    record = validate_provider(
        ProviderName.DEEPSEEK,
        "deepseek-flash",
        "global",
        client,
        load_fixtures(),
    )
    assert record.fixture_passed == record.fixture_count
    assert record.result == Verification.SCHEMA_COMPATIBLE
    assert record.returned_model == returned
