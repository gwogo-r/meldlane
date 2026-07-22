import tempfile
from pathlib import Path

from dotenv import load_dotenv
from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).parent

# pydantic-settings(env_file=".env") ниже читает .env только в свой Settings —
# не в os.environ. meldlane_transcribe (MTRANSCRIBE_*) читает переменные напрямую
# через os.getenv(), поэтому без этого MTRANSCRIBE_LANGUAGE/*_DEVICE молча
# игнорировались (обнаружено вживую 2026-07-22: MTRANSCRIBE_LANGUAGE=ru стоял
# в .env, но Whisper всё равно работал в автоопределении языка).
load_dotenv(BASE_DIR / ".env")


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    llm_provider: str = "openrouter"
    llm_base_url: str = "https://openrouter.ai/api/v1"
    openrouter_api_key: str = ""
    openai_api_key: str = ""

    # extractor — per-meeting, качество важнее цены → smart
    llm_model_cheap: str = "openai/gpt-4o-mini"
    llm_model_smart: str = "openai/gpt-4o"
    # цены $/1M токенов (для расчёта стоимости прогона; переопределяются в .env)
    price_cheap_in: float = 0.15  # OpenAI GPT-4o mini input
    price_cheap_out: float = 0.60  # OpenAI GPT-4o mini output
    price_smart_in: float = 2.50  # OpenAI GPT-4o input
    price_smart_out: float = 10.00  # OpenAI GPT-4o output

    # транскрибация и захват звука — делегированы пакету meldlane-transcribe
    # (MTRANSCRIBE_MODEL, MTRANSCRIBE_LANGUAGE, MTRANSCRIBE_MIC_DEVICE,
    # MTRANSCRIBE_SYSTEM_DEVICE в .env), здесь не дублируются

    # human-in-the-loop
    telegram_bot_token: str = ""
    telegram_chat_id: str = ""

    # Plane
    plane_base_url: str = ""
    plane_api_token: str = ""
    plane_workspace: str = ""
    plane_project_id: str = ""

    db_path: Path = BASE_DIR / "storage" / "meldlane.db"
    out_dir: Path = BASE_DIR / "out"
    team_path: Path = BASE_DIR / "team.yaml"
    samples_dir: Path = BASE_DIR / "samples"
    # Рабочая директория для реального исполнения CLI-агентов (claude-code/codex).
    # НАМЕРЕННО вне дерева этого репозитория (не BASE_DIR/out/...): git ищет .git
    # вверх по родительским папкам, если его нет в cwd — вложенная копия внутри
    # репозитория не была настоящей изоляцией, git-команды агента находили боевой
    # .git и коммитили туда (инцидент 2026-07-09, см. backlog MEL-042). Системный
    # temp-каталог гарантированно не имеет .git ни в себе, ни выше по дереву.
    agent_workspace_dir: Path = Path(tempfile.gettempdir()) / "meldlane_agent_workspace"

    @property
    def llm_api_key(self) -> str:
        if self.llm_provider == "openai":
            return self.openai_api_key
        return self.openrouter_api_key


settings = Settings()
