"""Build public presentation data from synthetic fixtures; no Provider or network."""

import json
from pathlib import Path

from course2career.adaptability import DIMENSION_WEIGHTS, assess_job_adaptability
from course2career.demo_cases import demo_inputs, load_demo_cases
from course2career.evidence_display import eligibility_label, skill_sources
from course2career.jd_analyzer import analyze_job_description

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "showcase/public/demo.json"


def build_demo_data() -> dict:
    cases = []
    for case in load_demo_cases():
        courses, profile, requirements = demo_inputs(case)
        job = analyze_job_description(case["jd"])
        report = assess_job_adaptability(courses, job, profile, requirements)
        cases.append(
            {
                "id": case["id"],
                "title": case["title"],
                "task": case["task"],
                "jd": case["jd"],
                "courses": [course.name for course in courses],
                "score": report.overall_score,
                "dimensions": report.dimension_scores.model_dump(),
                "eligibility": eligibility_label(report.eligibility),
                "checks": [
                    check.model_dump(mode="json") for check in report.eligibility.checks
                ],
                "completeness": report.data_completeness,
                "confidence": report.confidence,
                "matches": [
                    {
                        "skill": match.skill_name,
                        "support": match.support_score,
                        "status": match.status.value,
                        "sources": skill_sources(match),
                    }
                    for match in report.matches
                ],
                "contributions": [item.model_dump() for item in report.contributions],
                "learning": [item.model_dump() for item in report.learning_modules],
                "boundary": case["boundary"],
                "input": case,
            }
        )
    return {
        "scoring_version": "2.1",
        "synthetic": True,
        "weights": DIMENSION_WEIGHTS,
        "cases": cases,
    }


if __name__ == "__main__":
    OUTPUT.write_text(
        json.dumps(build_demo_data(), ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print("Synthetic showcase data generated without AI or network.")
