"""Deterministic wire fixtures, not a product Provider or live API client."""

from types import SimpleNamespace

from course2career.models import JobAnalysis, JobSkill

AUTO_MODEL = object()


class FauxWire:
    def __init__(self, *, returned=AUTO_MODEL, usage=True, errors=(), invalid=False):
        self.returned = returned
        self.usage = usage
        self.errors = list(errors)
        self.invalid = invalid
        self.requests = []
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self.chat_reply))
        self.responses = SimpleNamespace(
            with_raw_response=SimpleNamespace(parse=self.responses_reply)
        )

    def reply(self, requested, jd):
        self.requests.append(requested)
        error = self.errors.pop(0) if self.errors else None
        if error is not None:
            raise error
        model = requested if self.returned is AUTO_MODEL else self.returned
        terms = [term for term in ("Python", "SQL", "需求分析", "Excel") if term in jd]
        analysis = JobAnalysis(
            skills=[
                JobSkill(
                    name=term,
                    normalized_name=term,
                    category="技术",
                    evidence_text=term,
                )
                for term in terms
            ]
        )
        return model, analysis

    def chat_reply(self, **kwargs):
        model, analysis = self.reply(kwargs["model"], kwargs["messages"][-1]["content"])
        return SimpleNamespace(
            model=model,
            usage=(
                SimpleNamespace(prompt_tokens=20, completion_tokens=10)
                if self.usage
                else None
            ),
            choices=[
                SimpleNamespace(
                    message=SimpleNamespace(
                        content="invalid-json"
                        if self.invalid
                        else analysis.model_dump_json()
                    )
                )
            ],
        )

    def responses_reply(self, **kwargs):
        model, analysis = self.reply(kwargs["model"], kwargs["input"])
        response = SimpleNamespace(
            model=model,
            output_parsed=None if self.invalid else analysis,
            usage=SimpleNamespace(input_tokens=20, output_tokens=10)
            if self.usage
            else None,
        )
        return SimpleNamespace(
            http_response=SimpleNamespace(
                json=lambda: {
                    "model": model,
                    "usage": {"input_tokens": 20, "output_tokens": 10}
                    if self.usage
                    else None,
                }
            ),
            parse=lambda: response,
        )

    def native_reply(self, url, headers, body, timeout):
        gemini = "generationConfig" in body
        requested = url.split("/models/")[-1].split(":")[0] if gemini else body["model"]
        jd = (
            body["contents"][0]["parts"][0]["text"]
            if gemini
            else body["messages"][0]["content"]
        )
        model, analysis = self.reply(requested, jd)
        content = "invalid-json" if self.invalid else analysis.model_dump_json()
        if gemini:
            return {
                "modelVersion": model,
                "candidates": [{"content": {"parts": [{"text": content}]}}],
                **(
                    {
                        "usageMetadata": {
                            "promptTokenCount": 20,
                            "candidatesTokenCount": 10,
                        }
                    }
                    if self.usage
                    else {}
                ),
            }
        return {
            "model": model,
            "content": [{"type": "text", "text": content}],
            **(
                {"usage": {"input_tokens": 20, "output_tokens": 10}}
                if self.usage
                else {}
            ),
        }


def faux_error(status=None, code=None):
    error = RuntimeError("synthetic-private-secret and private response text")
    error.status_code = status
    error.code = code
    return error
