from datetime import UTC, datetime

from course2career.model_catalog import ModelCatalogSnapshot
from scripts.check_deepseek_models import build_model_report


def test_model_report_separates_approved_available_and_unknown_models() -> None:
    snapshot = ModelCatalogSnapshot(
        available_models=(
            "deepseek-v4-flash",
            "deepseek-v4-pro",
            "deepseek-v5-preview",
        ),
        fetched_at=datetime(2026, 8, 6, tzinfo=UTC),
    )

    report = build_model_report(snapshot)

    assert report["approved_available"] == [
        "deepseek-v4-flash",
        "deepseek-v4-pro",
    ]
    assert report["unknown_models"] == ["deepseek-v5-preview"]
    assert report["fetched_at"] == "2026-08-06T00:00:00+00:00"
