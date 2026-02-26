from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # Database
    database_path: str = "data/news.db"

    # Server
    host: str = "0.0.0.0"
    port: int = 8000
    debug: bool = False

    # Gemini
    gemini_api_key: str = ""
    gemini_model: str = "gemini-3-flash-preview"

    # Reddit
    reddit_client_id: str = ""
    reddit_client_secret: str = ""
    reddit_user_agent: str = "sift/0.1"

    # YouTube
    youtube_api_key: str = ""

    # Scoring
    scoring_interval_minutes: int = 5
    scoring_max_concurrent: int = 10

    # Profile synthesis
    profile_synthesis_interval_hours: int = 6

    @property
    def database_dir(self) -> Path:
        return Path(self.database_path).parent


settings = Settings()
