# Meldlane — Архитектура

## 1. Зачем

Трекер задач, где **люди и AI-агенты — равноправные участники команды**. Существующие трекеры (Jira, Linear, Plane) сделаны для людей: когда в команде появляются агенты, они невидимы — нет метрик, нет capacity, нет истории. Meldlane закрывает три вещи, которых нет ни в одном трекере:

1. **Задачи рождаются сами** — из митингов (транскрибация → LLM → структурированные задачи) и из внешнего фидбека (FeedbackOps), а не заводятся руками.
2. **Агент — полноправный assignee** — задача назначается на человека *или* агента; агент выполняет, запрашивает подтверждение, проходит тест, закрывает.
3. **Единый capacity** — на одном графике story points людей и токены/стоимость агентов. Впервые видно, сколько «весит» агент в команде и какой у него ROI.

Ключевой принцип: **Meldlane не переписывает трекер**. Ядро задач/досок/статусов — это Plane (open-source). Meldlane — слой вокруг Plane: питает его задачами, расширяет модель данных (агент как участник), логирует метрики и ведёт human-in-the-loop исполнение.

Второй принцип: **human-in-the-loop**. Агент не деплоит и не делает необратимого без явного подтверждения человека. Инструмент усиливает команду, а не действует за её спиной.

Аудитория — продуктовые команды 5–50 человек, которые уже используют AI-агентов в разработке и хотят это измерять и управлять.

## 2. Конвейер

Основной срез — **митинг → задачи в трекере**:

```
AudioCapture ─▶ Transcriber ─▶ TaskExtractor ─▶ TaskStore ─▶ TrackerSync ─▶ Plane
(mic+system)    (Whisper)      (LLM)            (SQLite)     (Plane API)    (issues)
     │              │                                                          │
     └──────────────┴──────────── Storage (SQLite: members, meetings, ────────┘
                                   transcripts, tasks, token_usage)
```

Второй срез — **исполнение задачи агентом** (human-in-the-loop):

```
Task(assignee=agent) ─▶ AgentExecutor ─▶ ConfirmGate ─▶ execute ─▶ test ─▶ done
                            │            (Telegram)                          │
                            └──────────── MetricsLogger (токены/$ на задачу) ┘
```

Каждая стрелка — отдельный тестируемый этап. Между этапами передаются **только Pydantic-модели** (раздел 5), не сырой текст. Метрики токенов/стоимости логируются на **каждом** LLM-вызове и привязываются к задаче и участнику — это и есть спинной хребет capacity-планирования.

## 3. Стадии

### 3.1 AudioCapture (захват звука)
Windows: `sounddevice` + VB-Cable. Пишет одновременно микрофон (свой голос) и системный звук (собеседники в звонке) в WAV. Оффлайн, без облака — звук митингов не покидает машину.

### 3.2 Transcriber
Whisper (локально): WAV → `Transcript` (сегменты с таймкодами, язык). Модель настраивается (`tiny…large`) — компромисс скорость/качество. Транскрипт кэшируется, повторный прогон экстрактора не гоняет Whisper заново.

### 3.3 TaskExtractor (LLM, per-meeting)
Из `Transcript` извлекает список `Task`: заголовок (императив), описание, `assignee_hint` (на кого прозвучало назначение), грубая оценка в story points, `evidence_quote` (цитата из транскрипта — обоснование). Строгий JSON-выход, `temperature=0`, не выдумывать задач, которых не было. Каждый вызов логирует `TokenUsage`.

### 3.4 TaskSource (источники задач) — плагины
Единый интерфейс `TaskSource.collect() -> list[Task]`. Источник = отдельный класс в реестре, добавить источник = добавить класс, не трогая конвейер. MVP: `MeetingSource` (транскрипт митинга). Фаза 2: `FeedbackSource` (FeedbackOps — внешний фидбек: тикеты поддержки, отзывы, формы → задачи).

### 3.5 Assignment (назначение)
`assignee_hint` резолвится в конкретного `Member` (человек или агент) по составу команды (`team.yaml`). Модель не различает «человек/агент» на уровне назначения — оба являются `Member`. Это и есть то, чего нет в других трекерах.

### 3.6 TrackerSync (Plane)
`tracker/plane.py` — клиент Plane API: задачи Meldlane → issues в Plane, статусы синкаются в обе стороны. Модель ассайни в Plane расширяется так, чтобы агент был участником наравне с человеком (fork/расширение, не костыль поверх кастомных полей).

### 3.7 AgentExecutor (LLM, дорого, per-task)
Берёт задачу с ассайни-агентом, выполняет (кодинг/ресёрч через инструменты), логирует токены/стоимость. Перед необратимым действием (деплой, запись, отправка) проходит через `ConfirmGate`. После выполнения — стадия `testing`, затем `done`.

**Текущий MVP-статус:** `agents/executor.py` делает только один шаг — просит LLM словами описать план (1-3 шага), без реального доступа к файлам/терминалу/интернету. Это не исполнение, а заглушка под него.

**Открытый вопрос (не решён, вернуться отдельно):** как делать реальное исполнение. Три варианта на столе:
1. **Оркестратор над CLI-агентами** — запускать Claude Code/Codex как подпроцесс с заданием, ловить результат/стоимость. Не изобретаем tool-use сами, Meldlane координирует уже существующих исполнителей.
2. **Свой tool-calling цикл на OpenAI SDK** — набор функций (read/write/shell/http) + цикл вызовов через OpenRouter. Больше контроля, больше работы и ответственности за песочницу/безопасность.
3. **Готовый агентский SDK** (напр. Claude Agent SDK) — качественный tool-use из коробки, но привязка к конкретному провайдеру.

### 3.8 ConfirmGate (human-in-the-loop)
`agents/confirm.py` — Telegram-бот: агент шлёт «вот что я собираюсь сделать — подтвердить?», ждёт человека. Никаких автономных необратимых действий.

### 3.9 MetricsLogger + Capacity
`metrics/logger.py` считает стоимость каждого LLM-вызова по цене модели участника и пишет `TokenUsage` с привязкой к задаче/участнику. `metrics/capacity.py` агрегирует: люди — в story points, агенты — в токенах/$. `report/dashboard.py` рисует burndown людей+агентов и ROI на одном экране — фирменная фича Meldlane.

## 4. Структура проекта

```
Meldlane/
  main.py                 # CLI-оркестратор (typer): meldlane <cmd>
  config.py               # Pydantic Settings из .env
  team.yaml               # состав команды: люди + агенты (данные, не код)
  models/
    member.py             # Member, MemberKind (human|agent)
    meeting.py            # Meeting, Transcript, TranscriptSegment
    task.py               # Task, TaskStatus, TaskSource
    metrics.py            # TokenUsage, CapacityRow
  capture/
    audio.py              # AudioCapture (mic + system, VB-Cable)      [Шаг 3]
    transcriber.py        # Whisper: WAV -> Transcript                 [Шаг 3]
  pipeline/
    extractor.py          # TaskExtractor: Transcript -> Task[] (LLM)
    sources/
      base.py             # TaskSource интерфейс + реестр              [Шаг 4+]
      meeting.py          # митинг -> задачи
      feedback.py         # FeedbackOps: внешний фидбек -> задачи      [фаза 2]
  agents/
    executor.py           # AgentExecutor                             [Шаг 7]
    confirm.py            # ConfirmGate (Telegram)                     [Шаг 6]
  tracker/
    plane.py              # Plane API client, агент-как-assignee       [Шаг 4]
  metrics/
    logger.py             # логирование токенов/стоимости на LLM-вызов
    capacity.py           # capacity: люди SP + агенты токены/$        [Шаг 5]
  storage/
    db.py                 # aiosqlite: members, meetings, transcripts, tasks, token_usage
  report/
    dashboard.py          # AI Capacity Dashboard (burndown + ROI)     [Шаг 5+]
  samples/                # готовые транскрипты для проверки без аудио
  out/                    # артефакты (gitignore)
  ARCHITECTURE.md / PLAN.md / CLAUDE.md / comments-style.md
```

Пометки `[Шаг N]` — этапы из [PLAN.md](PLAN.md); в первом коммите реализованы модели, storage, extractor, metrics/logger и CLI.

## 5. Модели данных (ядро контрактов между этапами)

```
Member        id, name, kind(human|agent), role?
              human:  capacity_sp
              agent:  provider, model, price_in, price_out ($/1M токенов)
Meeting       id, title, started_at, source(audio|upload|live), participants[]
Transcript    meeting_id, lang, segments[{speaker?, text, start?, end?}]  (+ full_text)
Task          id, title, description, assignee_id?(Member.id), assignee_hint?,
              status, story_points?, source(meeting|feedback|manual), source_ref?,
              evidence_quote, created_at, plane_id?
TokenUsage    stage, model, prompt_tokens, completion_tokens, cost_usd,
              task_id?, member_id?, created_at
CapacityRow   member_id, name, kind, story_points, tokens, cost_usd, task_count
```

`Task.assignee_id` ссылается на `Member` независимо от того, человек это или агент, — единая модель назначения. `TokenUsage` привязан к задаче и участнику, поэтому стоимость всегда объяснима: видно, какая задача и какой агент сожгли токены.

## 6. Технологический стек

- Python 3.12+ (backend), TypeScript/React (frontend дашборда — фаза 2)
- FastAPI — API-слой (фаза 2, когда появится web-дашборд)
- **Plane** (open-source) — ядро трекера, fork/расширение, не пишем с нуля
- Pydantic + Pydantic Settings (`.env`)
- aiosqlite — локальное хранилище и кэш (до/рядом с Plane)
- Whisper — транскрибация; `sounddevice` + VB-Cable — захват аудио (Windows)
- OpenAI SDK → OpenRouter — LLM (extractor, agent executor)
- AnythingLLM — RAG по коду и документации (фаза 2)
- aiogram v3 — Telegram-бот подтверждений
- PostgreSQL + Redis — прод-хранилища Plane; Docker Compose — инфраструктура

## 7. Решения и их обоснование

- **Plane как движок, не свой трекер** — доски/статусы/права/API уже есть и вылизаны. Наша ценность — слой сверху (митинги→задачи, агент-assignee, capacity), а не переизобретение issue-tracker.
- **Агент — это `Member`, не кастомное поле** — назначение задачи одинаково для человека и агента. Иначе агенты навсегда останутся костылём сбоку, а весь смысл продукта — сделать их равноправными.
- **Метрики на каждом LLM-вызове, привязка к задаче** — capacity и ROI считаются только если каждый токен отнесён к задаче и участнику. Это спинной хребет, поэтому логирование встроено в вызов, а не прикручено потом.
- **Транскрипт до аудио** — экстрактор (ядро ценности) разрабатывается и проверяется на готовых текстовых транскриптах (`samples/`), не завися от капризного захвата звука на Windows. Аудио подключается вторым.
- **Источники задач — плагины через реестр** — митинги и FeedbackOps подключаются одинаково; добавить источник = один класс.
- **Human-in-the-loop** — агент не делает необратимого без подтверждения. И этично, и практично: доверие к автономным агентам пока не заслужено.
- **Локальный звук, локальный Whisper** — записи митингов не уходят в облако; для команд это вопрос доверия.
- **Состав команды — данные (`team.yaml`), не код** — цены агентов, ёмкости людей, роли меняются в YAML, не в коде.

## 8. MVP vs фаза 2

**MVP (цель — 1 митинг → задачи в трекере, локально, 1 спринт):**
- AudioCapture + Whisper (или готовый транскрипт).
- TaskExtractor + логирование токенов/стоимости.
- TrackerSync в Plane, агент как assignee.
- Capacity: люди SP + агенты токены/$ (CLI-срез).

**Фаза 2:**
- AgentExecutor — реальное исполнение задач агентом.
- FeedbackOps — внешний фидбек как источник задач.
- Web-дашборд (React) — burndown людей+агентов, ROI.
- RAG (AnythingLLM) по коду/докам для контекста агентов.
- SaaS-режим поверх self-hosted.

## 9. Порядок реализации

1. Каркас: модели + config + storage + CLI-скелет (`members`).
2. TaskExtractor (LLM per-meeting) + metrics/logger на готовом транскрипте.
3. AudioCapture + Whisper → тот же extractor на живом звуке.
4. Plane self-hosted (docker-compose) + TrackerSync + агент как assignee.
5. Capacity: агрегация токенов/$ по задачам, CLI-срез загрузки.
6. ConfirmGate (Telegram) — human-in-the-loop.
7. AgentExecutor — исполнение задач агентом.
8. FeedbackOps + web-дашборд + RAG (фаза 2).
```
