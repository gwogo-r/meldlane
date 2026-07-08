# Backlog — Meldlane

> Формат ID: MEL-NNN · Priority: P0 / P1 / P2 / P3 · Status: TODO / IN PROGRESS / DONE · Area: frontend / backend / infra / design / ai

| ID | Title | Priority | Status | Area | Notes |
|----|-------|----------|--------|------|-------|
| MEL-001 | Project initialization | P1 | DONE | infra | CLAUDE.md, comments-style.md, MEMORY.md, backlog.md; git init |
| MEL-000 | ARCHITECTURE.md + PLAN.md + каркас (config/models/storage/CLI) | P1 | DONE | backend | `members` работает, БД создаётся, стиль от CompanyScout |
| MEL-002 | Поднять Plane self-hosted на VPS (Docker Compose) | P1 | DUPLICATE | infra | Дубль MEL-005, туда перенесены детали и статус |
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
| MEL-017 | Capacity: разделить $ API и $ подписка (billing source) | P2 | DONE | backend | TokenUsage.billing (api/subscription); capacity выводит две колонки, чтобы не путать реальную оплату с cost-эквивалентом под подпиской |
| MEL-018 | AgentExecutor: рабочая копия репозитория для агента (не пустая папка) | P2 | DONE | backend | sync_workspace() копирует репозиторий (без .git/out/venv/db) в out/agent_workspace перед каждым запуском — агент видит реальный код, но не боевой репозиторий |
| MEL-019 | Codex: --json терялся на многострочных промптах (баг cmd.exe) | P2 | DONE | backend | cmd.exe рвёт командную строку на \n даже в кавычках — codex тихо переключался на human-readable вывод, токены парсились как 0. Фикс: схлопывать \n в аргументах перед cmd.exe /c |
| MEL-020 | Codex: sandbox=read-only по умолчанию, не может писать файлы | P2 | DONE | backend | Добавлен --sandbox workspace-write в run_codex — безопасно, т.к. всегда работает в изолированной копии (MEL-018) |
| MEL-008 | AI Capacity Dashboard: burndown людей + агентов, ROI | P2 | TODO | frontend | CLI-срез (`capacity`) готов; веб-дашборд — фаза 2 |
| MEL-009 | RAG: подключить AnythingLLM и llmwiki | P3 | TODO | ai | По коду и документации |
| MEL-010 | FeedbackOps: внешний фидбек → задачи в Meldlane | P3 | TODO | backend | Второй источник задач помимо митингов |
| MEL-011 | Landing page meldlane.io | P3 | TODO | frontend | — |
| MEL-021 | Автовыбор Claude vs Codex по типу задачи (не только назначение из митинга) | P3 | TODO | ai | Сейчас provider жёстко привязан к Member в team.yaml; можно роутить по типу задачи/стоимости/загрузке |
| MEL-022 | Web UI для Meldlane (не только CLI) | P2 | TODO | frontend | Сейчас весь продукт — CLI под одного пользователя; нужен доступ для команды |
| MEL-023 | Дедуп задач при повторном extract одного транскрипта | P3 | TODO | backend | meeting.id всегда новый uuid → clear_tasks чистит пустоту, задачи дублируются при повторном прогоне того же файла |
| MEL-024 | CLI-старт 10.7с → 2.2с: ленивые импорты whisper/executor | P2 | DONE | backend | Аудит 2026-07-02: main.py тянул torch на верхнем уровне даже для --help |
| MEL-025 | audio.py: два параллельных sd.rec() не работают — переписано на InputStream | P2 | DONE | backend | Аудит: convenience-функции sounddevice делят один глобальный поток, второй rec глушил первый. Микс mic+system теперь два InputStream в тредах. Mic-путь проверен записью; system-путь ждёт VB-Cable |
| MEL-026 | Таймаут CLI-агентов (15 мин) + не глотать CliAgentError | P2 | DONE | backend | Аудит: зависший claude/codex держал run-task вечно; ошибка исполнения молча превращалась в blocked без причины |
| MEL-027 | Whisper → faster-whisper (CTranslate2, без torch) | P2 | DONE | backend | В разы быстрее на CPU (3.3с вместо ~10+с на том же клипе), не тянет torch (~450МБ). torch/openai-whisper удалены из окружения. Проверено вживую на реальной речи |
| MEL-028 | System audio без VB-Cable через штатный «Стерео микшер» | P1 | DONE | backend | Обнаружено вживую: Stereo Mix ловит системный звук без установки чего-либо. Но требовал переписать audio.py — WDM-KS не поддерживает blocking read (нужен callback) и работает на нативной частоте устройства (48kHz), не 16kHz. Добавлен resample_poly (scipy) до 16kHz перед миксом с mic. Проверено: mic+system вместе, 16kHz WAV, Whisper распознал |
| MEL-029 | Graceful stop для записи (capture-stop) — не терять запись при ранней остановке | P1 | DONE | backend | Раньше WAV писался только по истечении фиксированного --seconds — ранняя остановка = потеря всего. Добавлен файл-флаг out/.capture_stop: capture без --seconds пишет открыто (до 4ч), capture-stop из другого терминала останавливает и сохраняет накопленное. Проверено вживую: старт → речь → capture-stop → WAV сохранён и распознан |
| MEL-030 | Кроссплатформенный захват системного звука (не только Stereo Mix) | P1 | DONE | backend | Windows: WASAPI loopback через pyaudiowpatch (meldlane_transcribe/wasapi.py) — записывает default output loopback, работает с любым устройством вывода без Stereo Mix/VB-Cable. Проверено вживую дважды: реальный сигнал захвачен и корректно разделён от mic-дорожки. capture.py: system_track_strategy() — каскад WASAPI → именованный автодетект (Stereo Mix/BlackHole) → mic-only. macOS BlackHole-подсказка в doctor есть, сам BlackHole не тестировался (нет Mac) |
| MEL-031 | Файловый вход: mp3/m4a/ogg/wav + видео (mp4/mkv/webm...) → транскрипт | P1 | TODO | backend | Путь нулевого сопротивления — без аудиодрайверов вообще: Zoom/Meet пишут звонки сами, человек кидает файл. faster-whisper декодирует аудиоформаты через PyAV без внешнего ffmpeg; видеоконтейнеры — опционально через ffmpeg. Форматы взять из MOM/MeetingScribe |

## Спринт 1 (Фаза 2) — вынос meldlane-transcribe на GitHub

> Цель: отдельный репозиторий, который запускается у кого угодно (Windows/macOS) и превращает файл или живой звук в структурированный JSON-транскрипт с таймлайном и спикерами. См. PLAN.md, Фаза 2.

| ID | Title | Priority | Status | Area | Notes |
|----|-------|----------|--------|------|-------|
| MEL-032 | Каркас meldlane-transcribe: pip-пакет + CLI + JSON-схема Transcript | P1 | DONE | infra | C:\Projects\meldlane-transcribe, первый коммит. pip install -e работает, `mtranscribe` глобально: file/record/stop/doctor. Тесты 3 passed. Схема Transcript по контракту |
| MEL-030 | Кроссплатформенный захват системного звука | P1 | DONE | backend | pyaudiowpatch (Windows, extra в pyproject через sys_platform=='win32'). system_track_strategy() каскад: WASAPI → именованный автодетект → mic-only. Проверено вживую дважды, реальный сигнал |
| MEL-031 | Файловый вход: mp3/wav/m4a/ogg/aac + видео (mp4/mkv/webm/mov/avi) | P1 | DONE | backend | `mtranscribe file` — проверено на реальном 4-мин m4a из MOM: 89 сегментов, корректный русский, таймлайн. Видеоконтейнеры через PyAV объявлены, вживую не проверены |
| MEL-033 | Спикеры: канальная диаризация mic/system из коробки, pyannote — extra | P1 | DONE | ai | Проверено вживую дважды через полный CLI (`mtranscribe record`): mic.wav и system.wav реально разделены и корректно помечены (me/others) — когда сигнал есть в одной дорожке, другая остаётся чистой. merge_tracks сортирует по таймлайну (unit-тест). Whisper иногда хаотично галлюцинирует на нессмысленном звуке (короткий сигнал/TTS не успел) — известное ограничение модели на неречевом контенте, не баг пайплайна. pyannote extra — не начат, P3 на будущее |
| MEL-034 | Структурированное хранение сессий + очистка временных файлов | P2 | DONE | backend | outputs/YYYY-MM-DD_HH-MM/transcript.json (+ WAV по флагу --keep-audio, иначе удаляются) |
| MEL-035 | Команда doctor: диагностика аудиоустройств и стратегии захвата | P2 | DONE | backend | Проверено вживую: нашёл mic по умолчанию и Stereo Mix автодетектом, печатает per-OS подсказки, если loopback нет |
| MEL-036 | Публикация на GitHub: README (Win/mac), pyproject, лицензия, uvx-запуск | P1 | TODO | infra | Критерий готовности спринта: человек со стороны ставит и получает транскрипт из mp3 без нашей помощи |
| MEL-037 | Meldlane-оркестратор переходит на meldlane-transcribe как зависимость | P2 | DONE | backend | capture/ удалён, requirements.txt → git+https на GitHub-репо. main.py: capture/capture-stop/transcribe используют meldlane_transcribe.capture/.transcriber, конвертация Segment→TranscriptSegment. Настройки WHISPER_*/*_DEVICE → MTRANSCRIBE_* в .env. Проверено вживую: capture (WASAPI) → transcribe → корректные speaker-метки me/others, дошло до LLM-стадии (упало на отсутствующем API-ключе, не связано с рефакторингом) |

### Соглашения спринта 1 (для любой сессии/модели, продолжающей работу)

- **Репозиторий:** `C:\Projects\meldlane-transcribe` (новый, git init, authorship Roman Fakhrutdinov / warmevents.ai.tools@gmail.com). GitHub remote добавим, когда Роман создаст репо.
- **Пакет:** PyPI-имя `meldlane-transcribe`, python-модуль `meldlane_transcribe`, CLI-команда `mtranscribe`. Python 3.11+.
- **Зависимости ядра (не раздувать):** faster-whisper, sounddevice, scipy, numpy, typer, pydantic. Extras: `[diarize]` → pyannote; `[loopback-win]` → pyaudiowpatch (если понадобится отдельно).
- **JSON-схема Transcript (контракт, не ломать):**
```json
{
  "meeting_id": "a1b2c3",
  "lang": "ru",
  "duration_sec": 3612.4,
  "source": {"type": "live | file", "path": "audio.m4a"},
  "created_at": "2026-07-02T18:00:00Z",
  "segments": [
    {"start": 0.0, "end": 4.2, "speaker": "me", "text": "..."}
  ]
}
```
- **Значения `speaker`:** канальная диаризация (live-запись) → `me` (mic) / `others` (system audio); pyannote (файлы, extra) → `spk_0`, `spk_1`, ...; неизвестно → `null`.
- **Из текущего Meldlane переносится с сохранением выстраданных фиксов** (`capture/audio.py`, `capture/transcriber.py`): callback-API вместо blocking read (WDM-KS падает с PaErrorCode -9999), запись на нативной частоте устройства + resample_poly до 16kHz, разрешение device=None через sd.default.device (query_devices(None) возвращает весь список), graceful stop через файл-флаг, faster-whisper (не openai-whisper — не тянуть torch).
- **Live-запись для канальной диаризации пишет дорожки раздельно** (не миксует, как сейчас в Meldlane) — микс только как опция для совместимости.
