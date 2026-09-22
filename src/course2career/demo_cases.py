"""公开合成案例：输入可下载，使用与用户分析相同的规则引擎。"""

import json
from io import BytesIO
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

import pandas as pd

from course2career.course_parser import COURSE_COLUMN_MAP
from course2career.models import CandidateProfile, Course, JobRequirements

CASES_PATH = Path(__file__).resolve().parents[2] / "data/demo_cases/cases.json"


def load_demo_cases() -> list[dict]:
    return json.loads(CASES_PATH.read_text(encoding="utf-8"))


def demo_inputs(case: dict) -> tuple[list[Course], CandidateProfile, JobRequirements]:
    return (
        [Course.model_validate(item) for item in case["courses"]],
        CandidateProfile.model_validate(case["profile"]),
        JobRequirements.model_validate(case["requirements"]),
    )


def demo_course_frame(case: dict) -> pd.DataFrame:
    courses, _, _ = demo_inputs(case)
    return pd.DataFrame(
        [
            {
                label: getattr(course, field)
                for label, field in COURSE_COLUMN_MAP.items()
            }
            for course in courses
        ]
    )


def export_demo_bundle(case: dict) -> bytes:
    excel = BytesIO()
    demo_course_frame(case).to_excel(excel, index=False, engine="openpyxl")
    bundle = BytesIO()
    with ZipFile(bundle, "w", compression=ZIP_DEFLATED) as archive:
        archive.writestr("courses.xlsx", excel.getvalue())
        archive.writestr("jd.txt", case["jd"])
        archive.writestr("case.json", json.dumps(case, ensure_ascii=False, indent=2))
        archive.writestr(
            "README.txt",
            (
                "合成演示，不代表真实岗位或候选人。\n"
                "个人分析页可直接运行预设合成演示；不使用AI、不要求登录。\n"
                "若手动重放：上传courses.xlsx，按case.json填写资料及门槛，"
                "粘贴jd.txt，选本地规则，核对技能后生成报告并下载。\n"
                "null表示未知，[]表示明确没有经历。结果只反映材料和规则。"
            ),
        )
    return bundle.getvalue()
