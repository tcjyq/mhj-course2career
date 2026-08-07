from datetime import UTC, datetime

from pydantic import BaseModel, ConfigDict

from course2career.llm_provider import LLMUsage
from course2career.models import AdaptabilityReport, AnalysisReport
from course2career.permissions import (
    Permission,
    Principal,
    authorize,
    daily_ai_limit,
)
from course2career.product_repository import (
    AdminOverview,
    AdminUserSummary,
    AnalysisSummary,
    QuotaConflictError,
    SQLiteProductRepository,
    StoredAnalysis,
)


class QuotaExceededError(PermissionError):
    """当前用户的AI日额度已经耗尽。"""


class AIQuotaStatus(BaseModel):
    model_config = ConfigDict(frozen=True)

    used: int
    limit: int | None
    remaining: int | None


class SystemStatus(BaseModel):
    model_config = ConfigDict(frozen=True)

    database_status: str
    user_count: int
    ai_call_count: int
    analysis_count: int


class AIUsageService:
    """在任何真实模型调用前执行权限和日额度检查。"""

    def __init__(self, repository: SQLiteProductRepository) -> None:
        self.repository = repository

    def start_call(
        self,
        principal: Principal,
        key_mode: str,
        model: str,
        guest_session_id: str | None = None,
        provider: str = "openai",
    ) -> str:
        permission = (
            Permission.USE_OWN_API_KEY
            if key_mode == "user"
            else Permission.USE_SYSTEM_AI
        )
        authorize(principal, permission)
        limit = daily_ai_limit(principal, key_mode)
        if principal.user_id is None and not guest_session_id:
            raise ValueError("游客调用必须提供匿名会话标识。")
        try:
            return self.repository.reserve_ai_call(
                user_id=principal.user_id,
                guest_session_id=guest_session_id,
                key_mode=key_mode,
                model=model,
                provider=provider,
                daily_limit=limit,
                created_time=datetime.now(UTC),
            )
        except QuotaConflictError as exc:
            raise QuotaExceededError(
                "今日 AI 体验次数已用完，请明日再试或使用本地规则模式。"
            ) from exc

    def complete_call(
        self,
        usage_id: str,
        *,
        success: bool,
        usage: LLMUsage | None = None,
        input_cost_per_million: float = 0.0,
        output_cost_per_million: float = 0.0,
    ) -> None:
        input_tokens = usage.input_tokens if usage is not None else 0
        output_tokens = usage.output_tokens if usage is not None else 0
        estimated_cost = (
            input_tokens * max(input_cost_per_million, 0.0)
            + output_tokens * max(output_cost_per_million, 0.0)
        ) / 1_000_000
        completion = {
            "status": "success" if success else "failed",
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "cost": estimated_cost,
        }
        try:
            self.repository.complete_ai_call(
                usage_id,
                **completion,
                model=usage.model if usage is not None else None,
            )
        except TypeError as exc:
            # Streamlit Cloud 热更新时，cache_resource 可能短暂保留旧仓储实例。
            # 旧接口不接受 model，但仍能安全回写状态、Token 与费用。
            if "unexpected keyword argument 'model'" not in str(exc):
                raise
            self.repository.complete_ai_call(usage_id, **completion)

    def get_quota_status(
        self,
        principal: Principal,
        key_mode: str,
        guest_session_id: str | None = None,
    ) -> AIQuotaStatus:
        limit = daily_ai_limit(principal, key_mode)
        if principal.user_id is None and not guest_session_id:
            raise ValueError("游客额度查询必须提供匿名会话标识。")
        used = self.repository.count_ai_calls_today(
            user_id=principal.user_id,
            guest_session_id=guest_session_id,
            key_mode=key_mode,
            created_time=datetime.now(UTC),
        )
        return AIQuotaStatus(
            used=used,
            limit=limit,
            remaining=None if limit is None else max(limit - used, 0),
        )


class AnalysisRecordService:
    """保存和查询当前用户自己的分析历史。"""

    def __init__(self, repository: SQLiteProductRepository) -> None:
        self.repository = repository

    def save(
        self, principal: Principal, report: AnalysisReport | AdaptabilityReport
    ) -> str:
        authorize(principal, Permission.SAVE_ANALYSIS)
        if principal.user_id is None:
            raise PermissionError("登录后才能保存分析记录。")
        return self.repository.add_analysis(principal.user_id, report)

    def list_own(self, principal: Principal) -> list[AnalysisSummary]:
        authorize(principal, Permission.VIEW_OWN_ANALYSES)
        if principal.user_id is None:
            return []
        return self.repository.list_analyses(principal.user_id)

    def get_own(self, principal: Principal, record_id: str) -> StoredAnalysis | None:
        """仅恢复当前登录用户自己的历史报告。"""
        authorize(principal, Permission.VIEW_OWN_ANALYSES)
        if principal.user_id is None:
            return None
        return self.repository.get_analysis(principal.user_id, record_id)


class SystemStatusService:
    """仅向管理员返回不包含用户敏感内容的聚合状态。"""

    def __init__(self, repository: SQLiteProductRepository) -> None:
        self.repository = repository

    def get_status(self, principal: Principal) -> SystemStatus:
        authorize(principal, Permission.VIEW_SYSTEM_STATUS)
        user_count, ai_call_count, analysis_count = self.repository.system_counts()
        return SystemStatus(
            database_status="正常",
            user_count=user_count,
            ai_call_count=ai_call_count,
            analysis_count=analysis_count,
        )


class AdminDashboardService:
    """向管理员提供聚合概况和脱敏用户列表。"""

    def __init__(self, repository: SQLiteProductRepository) -> None:
        self.repository = repository

    def get_overview(self, principal: Principal) -> AdminOverview:
        authorize(principal, Permission.VIEW_SYSTEM_STATUS)
        return self.repository.admin_overview(datetime.now(UTC))

    def list_users(self, principal: Principal) -> list[AdminUserSummary]:
        authorize(principal, Permission.MANAGE_MEMBERSHIPS)
        return self.repository.list_users_for_admin()
