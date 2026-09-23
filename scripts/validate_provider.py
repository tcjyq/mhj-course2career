"""显式执行真实 Provider 验证；结果仅写入 gitignored outputs。"""

import argparse
import os
from pathlib import Path

from course2career.llm_provider import ProviderName
from course2career.provider_registry import get_provider_preset, ui_provider_presets
from course2career.provider_validation import (
    build_validation_client,
    load_fixtures,
    openrouter_supports_schema,
    validate_provider,
)
from course2career.provider_verification import DEFAULT_RECORD_PATH, save_record

KEY_ENV = {
    ProviderName.OPENAI: "OPENAI_API_KEY",
    ProviderName.DEEPSEEK: "DEEPSEEK_API_KEY",
    ProviderName.BAILIAN: "BAILIAN_API_KEY",
    ProviderName.OPENROUTER: "OPENROUTER_API_KEY",
    ProviderName.SILICONFLOW: "SILICONFLOW_API_KEY",
    ProviderName.MOONSHOT: "MOONSHOT_API_KEY",
    ProviderName.ZHIPU: "ZHIPU_API_KEY",
    ProviderName.MINIMAX: "MINIMAX_API_KEY",
    ProviderName.GEMINI: "GEMINI_API_KEY",
    ProviderName.ANTHROPIC: "ANTHROPIC_API_KEY",
}
MODEL_CANDIDATES = {ProviderName.ANTHROPIC: "claude-haiku-4-5-20251001"}
SUMMARY_PATH = DEFAULT_RECORD_PATH.with_name("summary.md")


def main() -> int:
    parser = argparse.ArgumentParser(description="验证 Course2Career Provider 兼容性")
    selector = parser.add_mutually_exclusive_group(required=True)
    selector.add_argument("--provider", choices=[item.value for item in ProviderName])
    selector.add_argument("--all-available", action="store_true")
    parser.add_argument("--model", help="精确模型 ID；禁止 auto/random")
    parser.add_argument("--endpoint-id", help="官方预设端点 ID")
    args = parser.parse_args()
    if args.all_available and (args.model or args.endpoint_id):
        parser.error("--model 和 --endpoint-id 仅适用于 --provider")
    if args.model and args.model.casefold() in {"auto", "random"}:
        parser.error("必须提供精确模型 ID")

    print("Credential presence (values never printed):")
    for preset in ui_provider_presets():
        env_name = KEY_ENV[preset.provider_id]
        print(f"{env_name}: {'available' if os.getenv(env_name) else 'unavailable'}")

    providers = tuple(KEY_ENV) if args.all_available else (ProviderName(args.provider),)
    fixtures = load_fixtures()
    rows = []
    for provider in providers:
        preset = get_provider_preset(provider)
        env_name = KEY_ENV[provider]
        api_key = os.getenv(env_name)
        model = args.model or preset.default_model or MODEL_CANDIDATES.get(provider)
        endpoint_id = args.endpoint_id or preset.selected_endpoint_id
        if not api_key:
            rows.append(
                (provider.value, model or "(none)", "PENDING", 0, "credential absent")
            )
            continue
        if not model:
            rows.append(
                (provider.value, "(none)", "PENDING", 0, "exact model required")
            )
            continue
        schema_supported = False
        if provider == ProviderName.OPENROUTER:
            try:
                schema_supported = openrouter_supports_schema(model, api_key)
            except (OSError, ValueError):
                rows.append(
                    (provider.value, model, "PENDING", 1, "metadata unavailable")
                )
                continue
            if not schema_supported:
                rows.append(
                    (provider.value, model, "UNSUPPORTED", 1, "schema metadata")
                )
                continue
        try:
            client = build_validation_client(
                provider,
                model,
                endpoint_id,
                api_key,
                openrouter_schema_supported=schema_supported,
            )
        except (ValueError, RuntimeError):
            rows.append((provider.value, model, "PENDING", 0, "local setup failed"))
            continue
        record = validate_provider(provider, model, endpoint_id, client, fixtures)
        save_record(record)
        rows.append(
            (
                provider.value,
                model,
                record.result.value.upper(),
                record.external_calls
                + (1 if provider == ProviderName.OPENROUTER else 0),
                record.error_code.value if record.error_code else "(none)",
            )
        )
    print("Provider | Model | Status | Calls | Error")
    for row in rows:
        print(" | ".join(str(item) for item in row))
    _write_summary(rows, SUMMARY_PATH)
    print("Sanitized summary: outputs/c08-provider-validation/summary.md")
    return 0


def _write_summary(rows: list[tuple[str, str, str, int, str]], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# C08-B2 本机真实验证摘要",
        "",
        "此文件不含凭证、请求正文或原始响应。",
        "",
        "| Provider | Model | Status | External calls | Error class |",
        "|---|---|---|---:|---|",
    ]
    lines.extend(
        f"| {provider} | {model} | {status} | {calls} | {error} |"
        for provider, model, status, calls, error in rows
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(main())
