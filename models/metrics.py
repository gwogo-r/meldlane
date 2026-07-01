from datetime import datetime

from pydantic import BaseModel, Field


class TokenUsage(BaseModel):
    stage: str  # extractor | agent_exec | ...
    model: str
    prompt_tokens: int = 0
    completion_tokens: int = 0
    cost_usd: float = 0.0
    # api: реальная оплата за токен (OpenRouter/OpenAI platform API).
    # subscription: списано с подписки (Claude Pro/Max, ChatGPT); cost_usd тут —
    #   не отдельный счёт, а cost-эквивалент для сравнения (если провайдер его отдаёт).
    billing: str = "api"
    task_id: str | None = None
    member_id: str | None = None
    created_at: datetime = Field(default_factory=datetime.utcnow)


class CapacityRow(BaseModel):
    member_id: str
    name: str
    kind: str  # human | agent
    story_points: float = 0.0        # люди: сумма SP назначенных задач
    task_count: int = 0
    tokens: int = 0                  # агенты: суммарные токены (все источники)
    cost_usd_api: float = 0.0        # агенты: реальная $-оплата по API
    cost_usd_subscription: float = 0.0  # агенты: cost-эквивалент по подписке, не отдельный счёт
