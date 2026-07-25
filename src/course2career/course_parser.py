from collections.abc import Iterable
from io import BytesIO
from pathlib import Path
from typing import BinaryIO
from zipfile import BadZipFile

import pandas as pd
from pydantic import ValidationError

from course2career.models import Course, CourseImportResult, CourseRowError

COURSE_COLUMN_MAP = {
    "课程名称": "name",
    "学分": "credit",
    "成绩": "grade",
    "课程类别": "category",
    "自评掌握程度": "self_assessment",
}

FIELD_LABELS = {field: label for label, field in COURSE_COLUMN_MAP.items()}


class CourseFileValidationError(ValueError):
    """课程文件无法读取或不符合模板结构。"""


def create_course_template() -> bytes:
    """生成可直接填写的课程信息 Excel 模板。"""

    course_sheet = pd.DataFrame(
        [["数据库原理", 3, 88, "专业必修", 4]],
        columns=list(COURSE_COLUMN_MAP),
    )
    instructions = pd.DataFrame(
        {
            "字段": list(COURSE_COLUMN_MAP),
            "填写要求": [
                "必填，课程名称不可重复",
                "必填，大于 0 且不超过 20",
                "必填，0 到 100",
                "必填，例如专业必修、专业选修、公共基础",
                "必填，1 到 5 的整数，5 表示掌握最好",
            ],
        }
    )
    output = BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        course_sheet.to_excel(writer, sheet_name="课程信息", index=False)
        instructions.to_excel(writer, sheet_name="填写说明", index=False)
    return output.getvalue()


def read_course_excel(source: str | Path | BinaryIO) -> CourseImportResult:
    """读取 Excel 首个工作表并校验课程数据。"""

    try:
        frame = pd.read_excel(source, sheet_name=0, engine="openpyxl")
    except (BadZipFile, OSError, TypeError, ValueError) as exc:
        raise CourseFileValidationError(
            "无法读取课程文件，请确认上传的是有效的 .xlsx 文件。"
        ) from exc

    return parse_course_dataframe(frame)


def parse_course_dataframe(frame: pd.DataFrame) -> CourseImportResult:
    """校验课程表结构，并分别返回合法课程和行级错误。"""

    normalized_frame = frame.copy()
    normalized_frame.columns = [str(column).strip() for column in frame.columns]
    _validate_columns(normalized_frame.columns)

    if normalized_frame.empty:
        raise CourseFileValidationError("课程文件中没有可导入的课程数据。")

    courses: list[Course] = []
    errors: list[CourseRowError] = []
    seen_course_names: set[str] = set()

    for position, (_, row) in enumerate(normalized_frame.iterrows(), start=2):
        required_values = [row[label] for label in COURSE_COLUMN_MAP]
        if all(_is_missing(value) for value in required_values):
            continue

        course_data = {
            field: _normalize_value(row[label])
            for label, field in COURSE_COLUMN_MAP.items()
        }

        try:
            course = Course.model_validate(course_data)
        except ValidationError as exc:
            errors.extend(_to_row_errors(position, exc))
            continue

        normalized_name = course.name.casefold()
        if normalized_name in seen_course_names:
            errors.append(
                CourseRowError(
                    row_number=position,
                    field="课程名称",
                    message=f"课程名称“{course.name}”重复。",
                )
            )
            continue

        seen_course_names.add(normalized_name)
        courses.append(course)

    return CourseImportResult(courses=courses, errors=errors)


def _validate_columns(columns: Iterable[str]) -> None:
    column_list = list(columns)
    duplicate_columns = sorted(
        {column for column in column_list if column_list.count(column) > 1}
    )
    if duplicate_columns:
        names = "、".join(duplicate_columns)
        raise CourseFileValidationError(f"课程文件包含重复列：{names}。")

    missing_columns = [label for label in COURSE_COLUMN_MAP if label not in column_list]
    if missing_columns:
        names = "、".join(missing_columns)
        raise CourseFileValidationError(f"课程文件缺少必填列：{names}。")


def _is_missing(value: object) -> bool:
    return value is None or bool(pd.isna(value))


def _normalize_value(value: object) -> object:
    if _is_missing(value):
        return None
    if isinstance(value, str):
        return value.strip()
    if hasattr(value, "item"):
        return value.item()
    return value


def _to_row_errors(row_number: int, exc: ValidationError) -> list[CourseRowError]:
    row_errors: list[CourseRowError] = []
    for error in exc.errors():
        field_name = str(error["loc"][0])
        label = FIELD_LABELS[field_name]
        row_errors.append(
            CourseRowError(
                row_number=row_number,
                field=label,
                message=_validation_message(field_name),
            )
        )
    return row_errors


def _validation_message(field_name: str) -> str:
    messages = {
        "name": "课程名称不能为空。",
        "credit": "学分必须是大于 0 且不超过 20 的数字。",
        "grade": "成绩必须是 0 到 100 之间的数字。",
        "category": "课程类别不能为空。",
        "self_assessment": "自评掌握程度必须是 1 到 5 之间的整数。",
    }
    return messages[field_name]
