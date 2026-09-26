"""C08-D2 synthetic user journey; no external provider or production database."""

from datetime import UTC, datetime
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

from course2career.access_services import AIUsageService, AnalysisRecordService
from course2career.adaptability import assess_job_adaptability
from course2career.api_key_service import APIKeyNotFoundError, APIKeyService
from course2career.auth_service import AuthService
from course2career.byok_mode import BYOKModeService
from course2career.demo_cases import demo_inputs, load_demo_cases
from course2career.jd_analyzer import analyze_job_description
from course2career.key_encryption import APIKeyCipher
from course2career.llm_provider import LLMUsage, ProviderName
from course2career.permissions import PermissionDeniedError
from course2career.product_repository import SQLiteProductRepository
from course2career.provider_profile import ProviderProfileService


class SyntheticProvider:
    provider_name = ProviderName.DEEPSEEK
    model_name = "deepseek-flash"
    last_usage = LLMUsage(input_tokens=31, output_tokens=12, model=model_name)

    def extract_job_skills(self, jd_text):
        return analyze_job_description(jd_text).model_copy(update={"source": "ai"})


def test_synthetic_byok_journey_persists_and_isolates_user_assets(tmp_path: Path):
    path = tmp_path / "d2-sandbox.db"
    repository = SQLiteProductRepository(path)
    auth = AuthService(repository)
    password = "synthetic-password-123"
    owner = auth.register("d2-owner", password)
    assert auth.authenticate("d2-owner", password).user_id == owner.user_id

    mode = BYOKModeService(repository)
    mode.set_enabled(owner, True)
    owner = auth.authenticate("d2-owner", password)
    cipher = APIKeyCipher(bytes(range(32)))
    keys = APIKeyService(repository, cipher)
    profiles = ProviderProfileService(repository)
    synthetic_key = "synthetic-key-never-sent"
    keys.save_key(owner, ProviderName.DEEPSEEK, synthetic_key)
    profiles.save(owner, ProviderName.DEEPSEEK, "global", "deepseek-flash")
    stored = repository.get_api_key(owner.user_id, "deepseek")
    assert stored is not None
    assert synthetic_key.encode() not in stored.encrypted_key

    case = load_demo_cases()[0]
    courses, candidate, requirements = demo_inputs(case)
    fake = SyntheticProvider()
    usage = AIUsageService(repository)
    usage_id = usage.start_call(
        owner, "user", fake.model_name, provider=fake.provider_name.value
    )
    job = analyze_job_description(case["jd"], fake)
    assert job.source == "ai" and job.skills
    usage.complete_call(usage_id, success=True, usage=fake.last_usage)
    report = assess_job_adaptability(courses, job, candidate, requirements)
    record_id = AnalysisRecordService(repository).save(owner, report)
    assert usage.get_quota_status(owner, "system").used == 0

    reconnected = SQLiteProductRepository(path)
    owner = AuthService(reconnected).authenticate("d2-owner", password)
    assert owner.byok_enabled
    assert APIKeyService(reconnected, cipher).get_key(owner, ProviderName.DEEPSEEK) == (
        synthetic_key
    )
    assert (
        ProviderProfileService(reconnected).get(owner, ProviderName.DEEPSEEK).model_id
        == "deepseek-flash"
    )
    history = AnalysisRecordService(reconnected)
    assert any(item.id == record_id for item in history.list_own(owner))
    assert history.get_own(owner, record_id) is not None
    assert (
        reconnected.count_ai_calls_today(
            user_id=owner.user_id,
            guest_session_id=None,
            key_mode="user",
            created_time=datetime.now(UTC),
        )
        == 1
    )

    mode = BYOKModeService(reconnected)
    mode.set_enabled(owner, False)
    with pytest.raises(PermissionDeniedError):
        AIUsageService(reconnected).start_call(
            owner, "user", fake.model_name, provider=fake.provider_name.value
        )
    mode.set_enabled(owner, True)
    owner = AuthService(reconnected).authenticate("d2-owner", password)
    assert APIKeyService(reconnected, cipher).get_key(owner, ProviderName.DEEPSEEK) == (
        synthetic_key
    )

    other = AuthService(reconnected).register("d2-other", "synthetic-pass-456")
    BYOKModeService(reconnected).set_enabled(other, True)
    other = AuthService(reconnected).authenticate("d2-other", "synthetic-pass-456")
    with pytest.raises(APIKeyNotFoundError):
        APIKeyService(reconnected, cipher).get_key(other, ProviderName.DEEPSEEK)
    assert ProviderProfileService(reconnected).get(other, ProviderName.DEEPSEEK) is None
    assert AnalysisRecordService(reconnected).get_own(other, record_id) is None


def test_provider_connection_status_is_not_shared_between_browser_accounts(
    tmp_path: Path,
):
    path = tmp_path / "shared-browser.db"
    repository = SQLiteProductRepository(path)
    auth = AuthService(repository)
    previous = auth.register("previous", "synthetic-pass-123")
    current = auth.register("current", "synthetic-pass-456")
    BYOKModeService(repository).set_enabled(current, True)
    current = auth.authenticate("current", "synthetic-pass-456")
    APIKeyService(repository, APIKeyCipher(bytes(range(32)))).save_key(
        current, ProviderName.DEEPSEEK, "synthetic-current-key"
    )
    ProviderProfileService(repository).save(
        current, ProviderName.DEEPSEEK, "global", "deepseek-flash"
    )
    app = AppTest.from_string(
        f'''
import streamlit as st
from course2career.api_key_service import APIKeyService
from course2career.auth_service import AuthService
from course2career.byok_mode import BYOKModeService
from course2career.key_encryption import APIKeyCipher
from course2career.product_repository import SQLiteProductRepository
from course2career.provider_profile import ProviderProfileService
from course2career.ui.developer_page import render_developer_page

repo = SQLiteProductRepository(r"{path.as_posix()}")
principal = AuthService(repo).authenticate("current", "synthetic-pass-456")
st.session_state["provider_connection_deepseek"] = (
    "{previous.user_id}", "global", "deepseek-flash", "API 可连接"
)
keys = APIKeyService(repo, APIKeyCipher(bytes(range(32))))
render_developer_page(
    principal, keys, None, ProviderProfileService(repo),
    byok_mode_service=BYOKModeService(repo)
)
'''
    ).run()
    assert not app.exception
    assert not any("API 可连接" in item.value for item in app.caption)
