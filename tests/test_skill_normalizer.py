from course2career.skill_normalizer import (
    find_skills_in_text,
    load_skill_aliases,
    normalize_skill_name,
)


def test_normalize_skill_name_handles_aliases_and_spacing() -> None:
    aliases = {"Power BI": ["powerbi", "Power BI"], "SQL": ["sql"]}

    assert normalize_skill_name("  power-bi ", aliases) == "Power BI"
    assert normalize_skill_name("Sql", aliases) == "SQL"


def test_normalize_skill_name_preserves_unknown_skill() -> None:
    assert normalize_skill_name("  用户研究  ", {}) == "用户研究"


def test_find_skills_in_text_returns_unique_canonical_names() -> None:
    aliases = {
        "Python": ["python"],
        "SQL": ["sql", "MySQL"],
        "数据可视化": ["数据可视化", "可视化"],
    }

    result = find_skills_in_text(
        "熟练使用 Python 和 MySQL，能用 SQL 完成数据查询与数据可视化。", aliases
    )

    assert result == ["Python", "SQL", "数据可视化"]


def test_bundled_alias_dictionary_contains_common_skills() -> None:
    aliases = load_skill_aliases()

    assert {"Python", "SQL", "Excel", "需求分析"}.issubset(aliases)


def test_short_english_alias_does_not_match_inside_another_word() -> None:
    aliases = {"机器学习": ["ML"]}

    assert find_skills_in_text("负责 HTML 页面开发", aliases) == []
