from io import BytesIO

import pandas as pd
import pytest

from course2career.course_parser import (
    CourseFileValidationError,
    create_course_template,
    parse_course_dataframe,
    read_course_excel,
)

REQUIRED_COLUMNS = [
    "课程名称",
    "学分",
    "成绩",
    "课程类别",
    "自评掌握程度",
]


def test_parse_course_dataframe_with_valid_rows_returns_courses() -> None:
    # Arrange
    frame = pd.DataFrame(
        [
            [" 数据库原理 ", 3, 88, "专业必修", 4],
            ["Python 程序设计", 2.5, 92.5, "专业选修", 5],
        ],
        columns=REQUIRED_COLUMNS,
    )

    # Act
    result = parse_course_dataframe(frame)

    # Assert
    assert result.errors == []
    assert len(result.courses) == 2
    assert result.courses[0].name == "数据库原理"
    assert result.courses[0].credit == 3.0
    assert result.courses[1].grade == 92.5


def test_parse_course_dataframe_missing_column_raises_validation_error() -> None:
    # Arrange
    frame = pd.DataFrame(
        [["数据库原理", 3, 88, "专业必修"]],
        columns=REQUIRED_COLUMNS[:-1],
    )

    # Act and assert
    with pytest.raises(CourseFileValidationError, match="自评掌握程度"):
        parse_course_dataframe(frame)


def test_parse_course_dataframe_invalid_rows_returns_field_errors() -> None:
    # Arrange
    frame = pd.DataFrame(
        [
            ["数据库原理", 3, 88, "专业必修", 4],
            ["", 2, 76, "专业选修", 3],
            ["统计学", 0, 101, "专业必修", 6],
        ],
        columns=REQUIRED_COLUMNS,
    )

    # Act
    result = parse_course_dataframe(frame)

    # Assert
    assert len(result.courses) == 1
    assert {(error.row_number, error.field) for error in result.errors} == {
        (3, "课程名称"),
        (4, "学分"),
        (4, "成绩"),
        (4, "自评掌握程度"),
    }


def test_parse_course_dataframe_blank_row_is_ignored() -> None:
    # Arrange
    frame = pd.DataFrame(
        [
            ["数据库原理", 3, 88, "专业必修", 4],
            [None, None, None, None, None],
        ],
        columns=REQUIRED_COLUMNS,
    )

    # Act
    result = parse_course_dataframe(frame)

    # Assert
    assert len(result.courses) == 1
    assert result.errors == []


def test_parse_course_dataframe_duplicate_course_returns_row_error() -> None:
    # Arrange
    frame = pd.DataFrame(
        [
            ["Python 程序设计", 3, 90, "专业必修", 4],
            [" python 程序设计 ", 2, 80, "专业选修", 3],
        ],
        columns=REQUIRED_COLUMNS,
    )

    # Act
    result = parse_course_dataframe(frame)

    # Assert
    assert len(result.courses) == 1
    assert len(result.errors) == 1
    assert result.errors[0].row_number == 3
    assert result.errors[0].field == "课程名称"
    assert "重复" in result.errors[0].message


def test_read_course_excel_reads_first_sheet_from_file_like_object() -> None:
    # Arrange
    frame = pd.DataFrame(
        [["数据库原理", 3, 88, "专业必修", 4]],
        columns=REQUIRED_COLUMNS,
    )
    excel_file = BytesIO()
    frame.to_excel(excel_file, index=False, engine="openpyxl")
    excel_file.seek(0)

    # Act
    result = read_course_excel(excel_file)

    # Assert
    assert len(result.courses) == 1
    assert result.courses[0].name == "数据库原理"


def test_read_course_excel_invalid_content_raises_validation_error() -> None:
    # Arrange
    invalid_file = BytesIO(b"not an xlsx file")

    # Act and assert
    with pytest.raises(CourseFileValidationError, match="无法读取"):
        read_course_excel(invalid_file)


def test_create_course_template_returns_expected_workbook() -> None:
    workbook = pd.ExcelFile(BytesIO(create_course_template()), engine="openpyxl")
    frame = pd.read_excel(workbook, sheet_name="课程信息")

    assert list(frame.columns) == REQUIRED_COLUMNS
    assert "填写说明" in workbook.sheet_names
