from dataclasses import FrozenInstanceError, replace
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest

from course2career.api_key_service import APIKeyService
from course2career.auth_service import AuthService
from course2career.byok_mode import BYOKModeService
from course2career.config import Settings
from course2career.key_encryption import APIKeyCipher
from course2career.llm_client import OpenAIJDClient
from course2career.llm_provider import ProviderName
from course2career.llm_providers import (
    DeepSeekProvider,
    OpenAICompatibleChatProvider,
    ProviderError,
)
from course2career.native_providers import AnthropicMessagesProvider, GeminiProvider
from course2career.permissions import PermissionDeniedError, Principal
from course2career.product_repository import SQLiteProductRepository
from course2career.provider_access import (
    AccessMode,
    CredentialKind,
    CredentialResolutionError,
    CredentialResolver,
    ResolvedCredential,
)
from course2career.provider_connection import (
    test_provider_connection as check_connection,
)
from course2career.provider_error_classification import classify_provider_error
from course2career.provider_factory import LLMProviderFactory
from course2career.provider_registry import ProviderProtocol, get_provider_preset
from course2career.provider_runtime import ModelMatch, returned_model_id
from course2career.provider_validation import load_fixtures, validate_provider
from course2career.provider_verification import (
    CERTIFIED_RECORD_PATH,
    ProviderErrorCode,
    Verification,
    get_record,
    load_records,
    save_record,
)
from tests.faux_provider import AUTO_MODEL, FauxWire, faux_error


def client_for(provider, wire):
    preset = get_provider_preset(provider)
    model = preset.default_model or "synthetic-model"
    if provider == ProviderName.OPENAI:
        return OpenAIJDClient(
            Settings(openai_api_key="synthetic-only", openai_model=model),
            sdk_client=wire,
        )
    if provider == ProviderName.DEEPSEEK:
        return DeepSeekProvider(api_key="synthetic-only", model=model, sdk_client=wire)
    if preset.primary_protocol == ProviderProtocol.OPENAI_CHAT:
        return OpenAICompatibleChatProvider(
            preset=preset, api_key="synthetic-only", model=model, sdk_client=wire
        )
    adapter = (
        AnthropicMessagesProvider
        if provider == ProviderName.ANTHROPIC
        else GeminiProvider
    )
    return adapter(
        preset=preset,
        api_key="synthetic-only",
        model=model,
        transport=wire.native_reply,
    )


@pytest.mark.parametrize("provider", list(ProviderName))
@pytest.mark.parametrize(
    "returned,expected",
    [
        (AUTO_MODEL, ModelMatch.MATCH),
        (None, ModelMatch.UNKNOWN),
        ("unfamiliar-model", ModelMatch.MISMATCH),
    ],
)
def test_all_provider_identity_paths_and_normalized_result(
    provider, returned, expected
):
    wire = FauxWire(returned=returned)
    client = client_for(provider, wire)
    result = client.extract_job_skills("要求 Python 和 SQL。")
    trace = client.last_trace
    raw = client.model_name if returned is AUTO_MODEL else returned
    assert trace.saved_model == trace.resolved_model == client.model_name
    assert trace.attempts[0].requested_model == client.model_name
    assert trace.returned_model == raw
    assert trace.model_match == expected
    assert client.last_result.analysis == result
    assert client.last_result.provider == provider
    assert client.last_result.endpoint == get_provider_preset(provider).base_url
    assert client.last_result.verification.model_match == expected
    assert len(wire.requests) == client.attempt_budget.max_attempts == 1
    with pytest.raises(FrozenInstanceError):
        trace.saved_model = "changed"


@pytest.mark.parametrize(
    "provider",
    [
        ProviderName.OPENAI,
        ProviderName.DEEPSEEK,
        ProviderName.BAILIAN,
        ProviderName.ANTHROPIC,
        ProviderName.GEMINI,
    ],
)
def test_identity_does_not_depend_on_usage_and_resets_after_failure(provider):
    wire = FauxWire(usage=False)
    client = client_for(provider, wire)
    client.extract_job_skills("Python")
    assert client.last_usage is None
    assert client.last_trace.model_match == ModelMatch.MATCH
    wire.errors.append(TimeoutError("synthetic-private-secret"))
    with pytest.raises(RuntimeError):
        client.extract_job_skills("SQL")
    assert client.last_result is None
    assert client.last_trace.returned_model is None
    assert client.last_trace.model_match == ModelMatch.UNKNOWN
    assert client.last_trace.attempts[0].error_code == "TIMEOUT"


@pytest.mark.parametrize(
    "provider",
    [
        ProviderName.OPENAI,
        ProviderName.DEEPSEEK,
        ProviderName.SILICONFLOW,
        ProviderName.ANTHROPIC,
        ProviderName.GEMINI,
    ],
)
def test_parse_failure_retains_response_identity_without_success(provider):
    client = client_for(provider, FauxWire(invalid=True))
    with pytest.raises(RuntimeError):
        client.extract_job_skills("Python")
    assert client.last_trace.returned_model == client.model_name
    assert client.last_trace.attempts[0].response_received
    assert not client.last_trace.attempts[0].success
    assert client.last_result is None


def test_fallback_preserves_saved_resolved_and_each_attempt():
    wire = FauxWire(errors=[faux_error(404)])
    client = DeepSeekProvider(
        api_key="synthetic-only",
        model="deepseek-v4-pro",
        saved_model="deepseek-flash",
        fallback_models=("deepseek-v4-flash",),
        sdk_client=wire,
    )
    client.extract_job_skills("Python")
    trace = client.last_trace
    assert trace.saved_model == "deepseek-flash"
    assert trace.resolved_model == "deepseek-v4-pro"
    assert wire.requests == ["deepseek-v4-pro", "deepseek-v4-flash"]
    assert trace.attempts[0].error_code == "MODEL_NOT_FOUND"
    assert trace.attempts[1].fallback_reason == "MODEL_NOT_FOUND"
    assert trace.returned_model == "deepseek-v4-flash"
    assert trace.model_match == ModelMatch.MATCH
    assert not trace.proves_exact_model("deepseek-v4-pro")
    assert not trace.proves_exact_model("deepseek-v4-flash")


@pytest.mark.parametrize(
    "error",
    [
        faux_error(401),
        faux_error(429),
        faux_error(429, "insufficient_quota"),
        TimeoutError("synthetic-private-secret"),
    ],
)
def test_no_implicit_retry_or_fallback_for_non_404(error):
    wire = FauxWire(errors=[error])
    client = DeepSeekProvider(
        api_key="synthetic-only",
        model="deepseek-flash",
        fallback_models=("deepseek-v4-pro",),
        sdk_client=wire,
    )
    with pytest.raises(ProviderError):
        client.extract_job_skills("Python")
    assert wire.requests == ["deepseek-flash"]
    assert len(client.last_trace.attempts) == 1
    assert "synthetic-private-secret" not in str(client.last_trace)


@pytest.mark.parametrize("provider", list(ProviderName))
def test_exact_fixture_certification_uses_each_raw_trace(provider, tmp_path):
    client = client_for(provider, FauxWire())
    preset = get_provider_preset(provider)
    record = validate_provider(
        provider,
        client.model_name,
        preset.selected_endpoint_id,
        client,
        load_fixtures(),
    )
    assert record.identity_evidence_version == 1
    assert record.model_match == ModelMatch.MATCH
    assert record.result == (
        Verification.SCHEMA_COMPATIBLE
        if provider == ProviderName.OPENROUTER
        else Verification.VERIFIED
    )
    path = tmp_path / "records.json"
    save_record(record, path)
    assert (
        get_record(provider, preset.selected_endpoint_id, client.model_name, path)
        == record
    )
    if record.result == Verification.VERIFIED:
        with pytest.raises(ValueError, match="trace"):
            replace(record, model_traces=())


@pytest.fixture
def accounts(tmp_path):
    repo = SQLiteProductRepository(tmp_path / "credentials.db")
    auth = AuthService(repo)
    mode = BYOKModeService(repo)
    keys = APIKeyService(repo, APIKeyCipher(bytes(range(32))))
    users = []
    for username in ("access_a", "access_b"):
        principal = auth.register(username, "synthetic-password-123")
        mode.set_enabled(principal, True)
        principal = auth.refresh_principal(principal)
        for provider in ProviderName:
            keys.save_key(principal, provider, f"synthetic-{username}")
        users.append(principal)
    return repo, auth, mode, keys, users


@pytest.mark.parametrize("provider", list(ProviderName))
def test_ten_provider_factory_access_credential_adapter_path(
    accounts, provider, monkeypatch
):
    _, _, _, keys, users = accounts
    wire = FauxWire()
    import openai

    def sdk(**kwargs):
        assert kwargs["max_retries"] == 0
        assert kwargs["api_key"] == "synthetic-access_a"
        return wire

    monkeypatch.setattr(openai, "OpenAI", sdk)
    preset = get_provider_preset(provider)
    assert preset.access().credential_kind == CredentialKind.API_KEY
    factory = LLMProviderFactory(Settings(), keys)
    client = factory.create(
        users[0],
        provider=provider,
        key_mode="user",
        model=preset.default_model or "synthetic-model",
    )
    if provider in {ProviderName.GEMINI, ProviderName.ANTHROPIC}:
        client.transport = wire.native_reply
    client.extract_job_skills("Python")
    assert client.last_trace.model_match == ModelMatch.MATCH


def test_credentials_isolate_owner_rotate_disable_and_guest(accounts):
    _, _, mode, keys, users = accounts
    preset = get_provider_preset(ProviderName.OPENAI)
    resolver = CredentialResolver(Settings(openai_api_key="synthetic-system"), keys)
    assert (
        resolver.resolve(users[0], preset, "user").require_usable()
        == "synthetic-access_a"
    )
    assert (
        resolver.resolve(users[1], preset, "user").require_usable()
        == "synthetic-access_b"
    )
    keys.save_key(users[0], ProviderName.OPENAI, "synthetic-rotated")
    assert (
        resolver.resolve(users[0], preset, "user").require_usable()
        == "synthetic-rotated"
    )
    assert "synthetic-rotated" not in repr(resolver.resolve(users[0], preset, "user"))
    mode.set_enabled(users[0], False)
    with pytest.raises(PermissionDeniedError):
        resolver.resolve(users[0], preset, "user")
    with pytest.raises(PermissionDeniedError):
        resolver.resolve(Principal(), preset, "user")


@pytest.mark.parametrize("mode", [AccessMode.PLAN, AccessMode.OAUTH_SUBSCRIPTION])
def test_reserved_access_fails_before_secret_or_network(mode, accounts, monkeypatch):
    _, _, _, keys, users = accounts
    monkeypatch.setattr(keys, "get_key", lambda *_: pytest.fail("secret read"))
    factory = LLMProviderFactory(Settings(), keys)
    for provider in ProviderName:
        with pytest.raises(ProviderError, match="尚未开放"):
            factory.create(
                users[0],
                provider=provider,
                key_mode="user",
                model="synthetic-model",
                access_mode=mode,
            )


def test_expired_credential_is_fail_closed_and_not_oauth_subscription():
    credential = ResolvedCredential(
        ProviderName.OPENAI,
        AccessMode.API,
        CredentialKind.OAUTH,
        "user",
        "synthetic-expired",
        datetime.now(UTC) - timedelta(seconds=1),
    )
    with pytest.raises(CredentialResolutionError, match="过期"):
        credential.require_usable()
    assert credential.kind == CredentialKind.OAUTH
    assert credential.access_mode != AccessMode.OAUTH_SUBSCRIPTION


@pytest.mark.parametrize(
    "status,raw_code,expected",
    [
        (429, "insufficient_quota", ProviderErrorCode.QUOTA_EXHAUSTED),
        (429, "usage_limit_reached", ProviderErrorCode.USAGE_LIMIT),
        (403, "model_not_included", ProviderErrorCode.MODEL_NOT_INCLUDED),
        (400, None, ProviderErrorCode.PROVIDER_ERROR),
        (400, "unsupported_json_schema", ProviderErrorCode.SCHEMA_UNSUPPORTED),
        (503, None, ProviderErrorCode.PROVIDER_UNAVAILABLE),
    ],
)
def test_safe_explicit_error_classification(status, raw_code, expected):
    classified = classify_provider_error(
        faux_error(status, raw_code), schema_requested=True
    )
    assert classified.code == expected
    assert "synthetic-private-secret" not in str(classified)


@pytest.mark.parametrize("value", [None, "", "\nmodel", "m" * 201, 12])
def test_invalid_returned_identity_never_truncates_into_a_match(value):
    assert returned_model_id(value) is None


def test_connection_unknown_model_and_missing_usage_are_independent(accounts):
    client = client_for(ProviderName.OPENAI, FauxWire(returned=None, usage=False))
    result = check_connection(
        SimpleNamespace(create=lambda *_args, **_kwargs: client),
        accounts[-1][0],
        ProviderName.OPENAI,
        client.model_name,
    )
    assert (
        result.auth_ok
        and result.request_ok
        and result.schema_ok
        and result.job_analysis_ok
    )
    assert not result.usage_ok
    assert result.model_match == ModelMatch.UNKNOWN
    assert result.returned_model is None


def test_fallback_external_call_count_and_failed_attempts_are_retained():
    wire = FauxWire(errors=[faux_error(404)])
    client = DeepSeekProvider(
        api_key="synthetic-only",
        model="deepseek-flash",
        fallback_models=("deepseek-v4-pro",),
        sdk_client=wire,
    )
    record = validate_provider(
        ProviderName.DEEPSEEK, "deepseek-flash", "global", client, load_fixtures()
    )
    assert record.result == Verification.SCHEMA_COMPATIBLE
    assert record.model_match == ModelMatch.MISMATCH
    assert record.external_calls == len(wire.requests) == 6
    assert len(record.model_traces) == 5
    assert sum(len(trace.attempts) for trace in record.model_traces) == 6


def test_failed_fixture_ends_with_failed_trace_not_previous_success():
    client = client_for(
        ProviderName.OPENAI,
        FauxWire(errors=[None, TimeoutError("synthetic-private-secret")]),
    )
    record = validate_provider(
        ProviderName.OPENAI, client.model_name, "global", client, load_fixtures()
    )
    assert record.external_calls == len(record.model_traces) == 2
    assert record.returned_model is None
    assert record.model_match == ModelMatch.UNKNOWN
    assert record.error_code == ProviderErrorCode.TIMEOUT
    assert record.model_traces[-1].attempts[0].error_code == "TIMEOUT"


def test_legacy_records_load_but_cannot_mint_new_legacy_certification(tmp_path):
    legacy = next(iter(load_records(CERTIFIED_RECORD_PATH).values()))
    assert legacy.legacy_model_identity_evidence
    assert legacy.model_match == ModelMatch.UNKNOWN
    with pytest.raises(ValueError, match="旧模型身份"):
        save_record(legacy, tmp_path / "new-records.json")
    with pytest.raises(ValueError, match="trace"):
        replace(legacy, identity_evidence_version=1, model_match=ModelMatch.MATCH)


def test_failed_fallback_never_exceeds_budget():
    wire = FauxWire(errors=[faux_error(404), faux_error(404), None])
    client = DeepSeekProvider(
        api_key="synthetic-only",
        model="deepseek-flash",
        fallback_models=("deepseek-v4-pro", "deepseek-v4-flash"),
        sdk_client=wire,
    )
    with pytest.raises(ProviderError):
        client.extract_job_skills("Python")
    assert len(wire.requests) == len(client.last_trace.attempts) == 2
    assert not client.attempt_budget.allows(2)
    assert client.last_result is None


def test_local_configuration_error_is_not_auth_or_request_success(accounts):
    def broken_factory(*_args, **_kwargs):
        raise ValueError("synthetic-private-secret local configuration")

    result = check_connection(
        SimpleNamespace(create=broken_factory),
        accounts[-1][0],
        ProviderName.OPENAI,
        "synthetic-model",
    )
    assert result.auth_ok is None
    assert not result.request_ok
    assert result.model_match == ModelMatch.UNKNOWN
    assert "synthetic-private-secret" not in str(result)
