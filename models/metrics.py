from llm_gateway import TokenUsage
from pydantic import BaseModel


class CapacityRow(BaseModel):
    member_id: str
    name: str
    kind: str  # human | agent
    story_points: float = 0.0        # люди: сумма SP назначенных задач
    task_count: int = 0
    tokens: int = 0                  # агенты: суммарные токены (все источники)
    cost_usd_api: float = 0.0        # агенты: реальная $-оплата по API
    cost_usd_subscription: float = 0.0  # агенты: cost-эквивалент по подписке, не отдельный счёт
