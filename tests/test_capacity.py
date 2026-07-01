from metrics.capacity import compute_capacity
from models import Member, MemberKind, Task, TokenUsage


def test_compute_capacity_sums_human_story_points_and_tasks():
    members = [
        Member(id="h1", name="Alice", kind=MemberKind.human),
        Member(id="a1", name="Codex", kind=MemberKind.agent),
    ]
    tasks = [
        Task(id="t1", title="Build API", assignee_id="h1", story_points=3),
        Task(id="t2", title="Fix bug", assignee_id="h1", story_points=2.5),
        Task(id="t3", title="Generate tests", assignee_id="a1", story_points=8),
    ]

    rows = {row.member_id: row for row in compute_capacity(members, tasks, [])}

    assert rows["h1"].task_count == 2
    assert rows["h1"].story_points == 5.5
    assert rows["a1"].task_count == 1
    assert rows["a1"].story_points == 0.0


def test_compute_capacity_sums_tokens_and_splits_cost_by_billing():
    members = [
        Member(id="h1", name="Alice", kind=MemberKind.human),
        Member(id="a1", name="Codex", kind=MemberKind.agent),
    ]
    usage = [
        TokenUsage(
            stage="extractor",
            model="gpt-test",
            prompt_tokens=100,
            completion_tokens=25,
            cost_usd=0.12,
            billing="api",
            member_id="a1",
        ),
        TokenUsage(
            stage="agent_exec",
            model="gpt-test",
            prompt_tokens=50,
            completion_tokens=10,
            cost_usd=0.08,
            billing="subscription",
            member_id="a1",
        ),
    ]

    rows = {row.member_id: row for row in compute_capacity(members, [], usage)}

    assert rows["a1"].tokens == 185
    assert rows["a1"].cost_usd_api == 0.12
    assert rows["a1"].cost_usd_subscription == 0.08
    assert rows["h1"].tokens == 0


def test_compute_capacity_ignores_unknown_or_unassigned_tasks_and_usage():
    members = [Member(id="h1", name="Alice", kind=MemberKind.human)]
    tasks = [
        Task(id="t1", title="Unassigned", assignee_id=None, story_points=3),
        Task(id="t2", title="Unknown member", assignee_id="missing", story_points=5),
    ]
    usage = [
        TokenUsage(stage="extractor", model="gpt-test", member_id=None, prompt_tokens=10),
        TokenUsage(stage="agent_exec", model="gpt-test", member_id="missing", prompt_tokens=20),
    ]

    rows = compute_capacity(members, tasks, usage)

    assert len(rows) == 1
    assert rows[0].member_id == "h1"
    assert rows[0].task_count == 0
    assert rows[0].story_points == 0.0
    assert rows[0].tokens == 0


def test_compute_capacity_returns_rows_sorted_by_kind_then_name():
    members = [
        Member(id="h2", name="Zoe", kind=MemberKind.human),
        Member(id="a2", name="Beta", kind=MemberKind.agent),
        Member(id="h1", name="Alice", kind=MemberKind.human),
        Member(id="a1", name="Alpha", kind=MemberKind.agent),
    ]

    rows = compute_capacity(members, [], [])

    assert [(row.kind, row.name) for row in rows] == [
        ("agent", "Alpha"),
        ("agent", "Beta"),
        ("human", "Alice"),
        ("human", "Zoe"),
    ]
