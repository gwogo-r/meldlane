# Backlog — Meldlane

> Формат ID: MEL-NNN · Priority: P0 / P1 / P2 / P3 · Status: TODO / IN PROGRESS / DONE · Area: frontend / backend / infra / design / ai

| ID | Title | Priority | Status | Area | Notes |
|----|-------|----------|--------|------|-------|
| MEL-001 | Project initialization | P1 | DONE | infra | CLAUDE.md, comments-style.md, MEMORY.md, backlog.md; git init |
| MEL-000 | ARCHITECTURE.md + PLAN.md + каркас (config/models/storage/CLI) | P1 | DONE | backend | `members` работает, БД создаётся, стиль от CompanyScout |
| MEL-002 | Поднять Plane self-hosted на VPS (Docker Compose) | P1 | TODO | infra | Ядро трекера, фундамент для всего остального |
| MEL-003 | AudioCapture: mic + system audio → Whisper транскрипт | P2 | DONE | backend | mic-запись + Whisper проверены. System audio через VB-Cable — код готов, кабель не установлен на машине |
| MEL-004 | TaskExtractor: LLM транскрипт → структурированные задачи → Plane API | P2 | IN PROGRESS | ai | Проверен end-to-end: 4 задачи из standup, SP + assignee, стоимость $0.0056. Осталось: синк в Plane (Шаг 4), точный резолв ассайни (cyrillic/latin) |
| MEL-005 | Plane self-hosted на VPS + агент как assignee | P1 | TODO | infra | Отложено 2026-07-01 — деплой на внешний VPS, не локально (тяжёлый 13-сервисный стек). До этого задачи в SQLite (уже работают: extract/tasks/run-task/capacity) |
| MEL-006 | Логирование токенов/стоимости по задачам | P2 | DONE | backend | metrics/logger.py + capacity.py готовы; capacity CLI проверен |
| MEL-012 | Резолв assignee: aliases для кириллицы/сокращений | P2 | DONE | backend | Member.aliases + team.yaml; «Роман»→roman теперь матчится |
| MEL-007 | Telegram бот: подтверждение действий агента | P2 | IN PROGRESS | backend | agents/confirm.py готов, импортируется; не проверен живьём — нужен TELEGRAM_BOT_TOKEN |
| MEL-013 | AgentExecutor: реальное исполнение через CLI (Claude Code / Codex) | P2 | DONE | ai | agents/cli_runner.py + провода в executor.py. Проверено вживую: файл реально создан агентом, capacity видит $. Провайдер выбирается через team.yaml |
| MEL-014 | Windows-фикс: запуск .cmd бинарников (codex) через subprocess | P3 | DONE | backend | asyncio create_subprocess_exec не умеет .cmd напрямую — WinError 193, чинится cmd.exe /c |
| MEL-015 | ConfirmGate перед реальным исполнением — прогнать живьём | P2 | TODO | backend | Нужен TELEGRAM_BOT_TOKEN; сейчас всё тестируется через --no-confirm |
| MEL-016 | TaskExtractor: формулировать задачи императивнее для CLI-агентов | P3 | TODO | ai | Замечено: агент не всегда понимает описание как команду "напиши файлы" |
| MEL-008 | AI Capacity Dashboard: burndown людей + агентов, ROI | P2 | TODO | frontend | CLI-срез (`capacity`) готов; веб-дашборд — фаза 2 |
| MEL-009 | RAG: подключить AnythingLLM и llmwiki | P3 | TODO | ai | По коду и документации |
| MEL-010 | FeedbackOps: внешний фидбек → задачи в Meldlane | P3 | TODO | backend | Второй источник задач помимо митингов |
| MEL-011 | Landing page meldlane.io | P3 | TODO | frontend | — |
