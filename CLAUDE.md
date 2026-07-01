# Meldlane

Project management инструмент для AI-first команд, где люди и AI-агенты работают вместе в одном трекере. Задачи создаются автоматически из митингов (транскрибация → LLM → структурированные задачи), назначаются на человека **или** агента. Capacity planning считает story points людей и токены/стоимость агентов на одном графике. Единственный трекер, где capacity = люди + агенты.

Полное описание архитектуры — [ARCHITECTURE.md](ARCHITECTURE.md). План первого спринта — [PLAN.md](PLAN.md).

## Технологический стек

- **Backend:** Python 3.12+, FastAPI
- **Frontend:** TypeScript, React
- **Трекер-ядро:** Plane (open-source, fork или API поверх — не писать трекер с нуля)
- **Хранилища:** PostgreSQL, Redis
- **Транскрибация:** Whisper
- **LLM:** OpenAI SDK → OpenRouter
- **RAG:** AnythingLLM (по коду и документации)
- **Инфраструктура:** Docker Compose
- **Аудио (Windows):** sounddevice + VB-Cable (захват mic + system audio)

## Структура проекта

```
main.py / config.py / team.yaml     — CLI, настройки, состав команды (данные)
models/     — Member, Meeting, Transcript, Task, TokenUsage
pipeline/   — extractor.py (Transcript → Task[], LLM)
capture/    — audio.py + transcriber.py (Whisper)
tracker/    — plane.py (Plane API, агент-как-assignee) [Шаг 4, отложен — папки ещё нет]
tests/      — pytest (test_capacity.py написан Codex-агентом через саму систему)
agents/     — executor.py (маршрутизация по provider), confirm.py (Telegram),
              cli_runner.py (запуск claude/codex CLI подпроцессом, реальное исполнение)
metrics/    — logger.py (токены/$ для openrouter-агентов), capacity.py
storage/    — db.py (aiosqlite)
samples/    — готовые транскрипты для проверки без аудио
out/agent_workspace/ — изолированная рабочая директория для CLI-агентов (не репозиторий)
```

Между этапами передаём только Pydantic-модели. `Member` — единая модель для человека и агента (агент не костыль). Метрики токенов/стоимости логируются на каждом LLM-вызове с привязкой к задаче.

## Команды

- `python main.py members` — состав команды (люди + агенты)
- `python main.py extract samples/standup.txt` — транскрипт → задачи (нужен ключ LLM в `.env`)
- `python main.py capture --seconds N` / `transcribe <wav>` — живой звук → Whisper → задачи
- `python main.py tasks` — список задач с id/статусом/ассайни
- `python main.py run-task <id> [--no-confirm]` — AgentExecutor: план + (ConfirmGate) → testing
- `python main.py capacity` — загрузка: люди в SP, агенты в токенах/$

Python: `C:/Users/roman/AppData/Local/Programs/Python/Python311/python.exe`. Зависимости — `requirements.txt`.

## Правила и договорённости

- **Plane как движок** — форк или API поверх, не писать трекер с нуля.
- **Агент = полноправный участник команды** в модели данных, не костыль (агент может быть assignee наравне с человеком).
- **Все метрики токенов/стоимости логируются на уровне задачи.**
- **Self-hosted first**, SaaS потом.
- **Human-in-the-loop:** агент не деплоит без подтверждения.
- Комментарии в коде — только когда WHY неочевиден.

## Стиль комментариев

См. [comments-style.md](comments-style.md) — короткие, человеческие, без AI-шаблонов.

## Текущий статус

- **Сделано (Шаги 0-3, 5-7 из PLAN.md):** ARCHITECTURE.md + PLAN.md; каркас; TaskExtractor; AudioCapture+Whisper; Capacity CLI; ConfirmGate (Telegram, код готов); **AgentExecutor с реальным исполнением** через `agents/cli_runner.py` — запускает `claude`/`codex` CLI как подпроцесс, списывает с подписки (не по цене за токен). Проверено вживую: агент реально создавал файл на диске в изолированной `out/agent_workspace/`; `capacity` показывает настоящую стоимость.
- **Отложено:** Шаг 4 — Plane self-hosted. Решено разворачивать на внешнем VPS, не локально (тяжёлый 13-сервисный стек, конфликт портов). До этого задачи живут в SQLite.
- **Известный долг:**
  - VB-Cable не установлен на машине — system audio код готов (`SYSTEM_AUDIO_DEVICE` в `.env`), не проверен живьём.
  - ConfirmGate (Telegram) не проверен живьём — нужны `TELEGRAM_BOT_TOKEN`/`TELEGRAM_CHAT_ID`; реальное исполнение пока тестируется только через `--no-confirm`.
  - `team.yaml`: `Claude Dev`→provider `claude-code`, `Codex Dev`→provider `codex` (реальное исполнение); `GPT Researcher`→provider `openrouter` (planning-only).
  - TaskExtractor формулирует задачи не всегда достаточно императивно для CLI-агента (MEL-016) — иногда агент просто отвечает текстом вместо реального действия.

## Аудитория

Стартапы и продуктовые команды 5–50 человек, которые уже используют AI-агентов в разработке и хотят это измерять и управлять.
