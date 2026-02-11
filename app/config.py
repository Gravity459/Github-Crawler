from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import PostgresDsn, Field

class Settings(BaseSettings):
    github_token: str = Field(..., description="GitHub Personal Access Token")
    database_url: PostgresDsn = Field(..., description="Postgres Database URL")
    log_level: str = Field("INFO", description="Logging level")
    target_repo_count: int = Field(100000, description="Target number of repositories to crawl")

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

settings = Settings()
