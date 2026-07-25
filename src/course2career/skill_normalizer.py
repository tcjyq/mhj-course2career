import json
import re
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parents[2] / "data"


def load_skill_aliases(path: Path | None = None) -> dict[str, list[str]]:
    """加载规范技能名称与别名表。"""

    alias_path = path or DATA_DIR / "skill_aliases.json"
    with alias_path.open(encoding="utf-8") as file:
        data = json.load(file)
    return {
        str(name): [str(alias) for alias in aliases] for name, aliases in data.items()
    }


def normalize_skill_name(name: str, aliases: dict[str, list[str]] | None = None) -> str:
    """将技能别名转换为词典中的规范名称。"""

    cleaned_name = name.strip()
    alias_map = aliases if aliases is not None else load_skill_aliases()
    lookup_key = _comparison_key(cleaned_name)
    for canonical_name, known_aliases in alias_map.items():
        candidates = [canonical_name, *known_aliases]
        if any(_comparison_key(candidate) == lookup_key for candidate in candidates):
            return canonical_name
    return cleaned_name


def find_skills_in_text(
    text: str, aliases: dict[str, list[str]] | None = None
) -> list[str]:
    """按词典顺序从文本中识别技能，并去除同一技能的重复别名。"""

    alias_map = aliases if aliases is not None else load_skill_aliases()
    normalized_text = text.casefold()
    found: list[str] = []
    for canonical_name, known_aliases in alias_map.items():
        candidates = sorted({canonical_name, *known_aliases}, key=len, reverse=True)
        if any(_contains_alias(normalized_text, candidate) for candidate in candidates):
            found.append(canonical_name)
    return found


def _comparison_key(value: str) -> str:
    return re.sub(r"[\s_-]+", "", value).casefold()


def _contains_alias(normalized_text: str, alias: str) -> bool:
    normalized_alias = alias.casefold()
    if normalized_alias.isascii():
        pattern = rf"(?<![a-z0-9]){re.escape(normalized_alias)}(?![a-z0-9])"
        return re.search(pattern, normalized_text) is not None
    return normalized_alias in normalized_text
