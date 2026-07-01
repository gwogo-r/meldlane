from models import TokenUsage


def cost_usd(prompt_tokens: int, completion_tokens: int, price_in, price_out) -> float:
    """Стоимость вызова по цене модели ($/1M токенов).

    Если цены None, использует 0.0 (например, для subscription-агентов без цены за токен).
    """
    pin = float(price_in or 0.0) / 1_000_000
    pout = float(price_out or 0.0) / 1_000_000
    return round(prompt_tokens * pin + completion_tokens * pout, 6)


def usage_from_response(
    response,
    *,
    stage: str,
    model: str,
    price_in=None,
    price_out=None,
    task_id: str | None = None,
    member_id: str | None = None,
) -> TokenUsage:
    """Собирает TokenUsage из ответа OpenAI SDK, считая стоимость."""
    u = getattr(response, "usage", None)
    pt = getattr(u, "prompt_tokens", 0) or 0
    ct = getattr(u, "completion_tokens", 0) or 0
    return TokenUsage(
        stage=stage,
        model=model,
        prompt_tokens=pt,
        completion_tokens=ct,
        cost_usd=cost_usd(pt, ct, price_in, price_out),
        task_id=task_id,
        member_id=member_id,
    )
