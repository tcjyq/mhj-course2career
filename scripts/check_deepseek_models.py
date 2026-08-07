"""检查 DeepSeek 官方模型目录，供定时工作流发现待验证模型。"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from course2career.model_catalog import (
    APPROVED_DEEPSEEK_MODELS,
    DeepSeekModelCatalog,
    ModelCatalogSnapshot,
)


def build_model_report(snapshot: ModelCatalogSnapshot) -> dict[str, Any]:
    available = set(snapshot.available_models)
    return {
        "available_models": sorted(available),
        "approved_available": sorted(available & APPROVED_DEEPSEEK_MODELS),
        "unknown_models": sorted(available - APPROVED_DEEPSEEK_MODELS),
        "fetched_at": snapshot.fetched_at.isoformat(),
    }


def main() -> None:
    api_key = os.getenv("DEEPSEEK_API_KEY", "")
    snapshot = DeepSeekModelCatalog().get_models(api_key, force_refresh=True)
    report = build_model_report(snapshot)
    serialized = json.dumps(report, ensure_ascii=False)
    print(serialized)

    output_path = os.getenv("GITHUB_OUTPUT")
    if output_path:
        with Path(output_path).open("a", encoding="utf-8") as output:
            output.write(
                f"unknown_count={len(report['unknown_models'])}\n"
                f"report_json={serialized}\n"
            )


if __name__ == "__main__":
    main()
