# Meldlane

[Русская версия](README.ru.md)

![Python](https://img.shields.io/badge/python-3.12%2B-blue) ![Status](https://img.shields.io/badge/status-MVP-yellow)

A project tracker for teams where people and AI coding agents work side by side — not a Jira/Linear clone with an "AI feature" bolted on, but one where **capacity itself is people (story points) + agents (tokens and real dollars)** on the same chart.

Tasks come out of meetings automatically: record → transcribe → an LLM extracts action items → each task is assigned to a human **or** an agent. Agent-assigned tasks aren't just planned — `Claude Dev` and `Codex Dev` run as real subprocesses (Claude Code CLI / Codex CLI) with actual filesystem access, billed against your subscription rather than a per-token API key. A human confirms before anything irreversible happens.

Built on top of [Plane](https://plane.so) — the tracker core isn't reinvented, just synced to idempotently.

## Why

- **Agents are equal participants in the data model**, not a bolted-on integration. The same `Member` type represents Roman and Claude Dev; the same `Task` gets assigned to either.
- **Capacity that actually reflects cost.** Humans show story points; agents show tokens, plus cost split by `api` (real per-token billing) vs `subscription` (cost-equivalent under a Claude Pro/Max or ChatGPT Plus plan — not a separate charge).
- **Real execution, not planning theater.** Agent-assigned tasks that reach a CLI-capable provider actually run in an isolated workspace copy and produce real file changes — verified live, not simulated.
- **Honest about the gaps.** Plane expects `assignee` to be a real workspace user account — agent-as-native-assignee isn't solved, so agent name/cost/story-points go into the issue description as text. Single-user right now; the Telegram confirm-gate exists in code but hasn't been exercised live yet.

## How it works

```
meeting → mic+system audio → transcript → LLM extracts tasks → assign (human | agent)
                                                                        │
                                          agent picks it up ────────────┘
                                                │
                                      plan → confirm (human-in-the-loop) → real execution
                                                │
                                            testing → done
```

Every LLM call and every agent run logs its tokens/cost against the task, so `capacity` shows a true picture: who (or what) is actually consuming time and money.

## What's in this repo

- **CLI** (`main.py`) — the whole pipeline: extract tasks from a transcript, run an agent on a task, sync to Plane, search the knowledge base.
- **Web UI** (`api/` + `frontend/`) — read-only FastAPI backend and a React frontend for browsing tasks and capacity outside the terminal.
- **Knowledge base** (`kb/`) — full-text search (SQLite FTS5) over the project's own docs and code, so an agent working on a task can look things up instead of guessing.

## Built as a modular toolchain

Audio capture/transcription, LLM calls, and Plane sync are each their own published, independently useful package — this repo is the orchestrator that wires them together:

- [meldlane-transcribe](https://github.com/gwogo-r/meldlane-transcribe) — mic + system audio (WASAPI loopback on Windows, no VB-Cable) or a file, in, structured transcript with speaker labels, out.
- [llm-gateway](https://github.com/gwogo-r/llm-gateway) — one call for OpenRouter/OpenAI chat completions *and* for running Claude Code / Codex as real subprocess agents, with a single `TokenUsage` model that tracks which kind of billing applies.
- [meldlane-tasks](https://github.com/gwogo-r/meldlane-tasks) — idempotent `Task` → Plane issue sync (push the same task twice, get one issue, not two).

## Status

This is a working MVP, not a polished product yet:

- Meeting → task extraction, agent execution, Plane sync, and capacity accounting are all verified against live runs (real audio, real LLM calls, real Plane instance, real CLI-agent file writes).
- The Web UI is new: both API endpoints return correct data, the frontend builds and its dev server serves the app — not yet checked in an actual browser.
- The Telegram confirm-gate is written but untested live; real agent execution is currently only exercised with confirmation skipped, in disposable working copies.
- There's no real sandbox around agent execution — a CLI agent's working directory is a convention, not a filesystem jail. Treated procedurally for now, not solved.

## Install & run

```bash
pip install -r requirements.txt
cp .env.example .env   # fill in your LLM/Plane/Telegram keys as needed

python main.py members              # your team: humans + agents
python main.py extract samples/standup.txt
python main.py tasks
python main.py capacity
python main.py sync-plane           # needs PLANE_* in .env

python -m uvicorn api.app:app --reload   # web API, port 8000
cd frontend && npm install && npm run dev  # web UI, port 5173
```

Python 3.12+.

## License

All rights reserved — see [LICENSE](LICENSE). Source is public for demonstration; no reuse license is granted.
