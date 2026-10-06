"""Presentation must retain the rule engine's real synthetic results."""

import json
from html.parser import HTMLParser
from pathlib import Path
from runpy import run_path


def test_public_demo_matches_current_offline_rules() -> None:
    build = run_path("scripts/build_showcase_demo.py")["build_demo_data"]
    published = json.loads(
        Path("showcase/public/demo.json").read_text(encoding="utf-8")
    )
    assert published == build()
    assert published["synthetic"] is True
    assert {case["id"] for case in published["cases"]} == {
        "data-analysis",
        "ai-solutions",
        "digital-support",
    }


def test_default_no_js_report_preserves_score_and_independent_gate() -> None:
    class Values(HTMLParser):
        def __init__(self) -> None:
            super().__init__()
            self.active = None
            self.values = {}

        def handle_starttag(self, tag, attrs) -> None:
            for name, _value in attrs:
                if name in {
                    "data-score",
                    "data-completeness",
                    "data-confidence",
                    "data-eligibility",
                }:
                    self.active = name

        def handle_data(self, data) -> None:
            if self.active:
                self.values[self.active] = data
                self.active = None

    values = Values()
    values.feed(Path("showcase/public/index.html").read_text(encoding="utf-8"))
    published = json.loads(
        Path("showcase/public/demo.json").read_text(encoding="utf-8")
    )
    case = next(item for item in published["cases"] if item["id"] == "data-analysis")
    assert float(values.values["data-score"]) == case["score"]
    assert float(values.values["data-completeness"]) == case["completeness"]
    assert values.values["data-confidence"] == case["confidence"]
    assert values.values["data-eligibility"] == case["eligibility"]
    assert case["dimensions"]["technical"] > 80
    assert case["eligibility"] == "存在硬性门槛"
