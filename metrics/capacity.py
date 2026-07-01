from models import CapacityRow, Member, Task, TokenUsage


def compute_capacity(members: list[Member], tasks: list[Task], usage: list[TokenUsage]) -> list[CapacityRow]:
    """Люди — сумма story points назначенных задач. Агенты — сумма токенов/$ их вызовов."""
    by_id = {m.id: m for m in members}
    rows = {m.id: CapacityRow(member_id=m.id, name=m.name, kind=m.kind.value) for m in members}

    for t in tasks:
        if t.assignee_id and t.assignee_id in rows:
            row = rows[t.assignee_id]
            row.task_count += 1
            if by_id[t.assignee_id].kind.value == "human" and t.story_points:
                row.story_points += t.story_points

    for u in usage:
        if u.member_id and u.member_id in rows:
            row = rows[u.member_id]
            row.tokens += u.prompt_tokens + u.completion_tokens
            if u.billing == "subscription":
                row.cost_usd_subscription += u.cost_usd
            else:
                row.cost_usd_api += u.cost_usd

    return sorted(rows.values(), key=lambda r: (r.kind, r.name))
