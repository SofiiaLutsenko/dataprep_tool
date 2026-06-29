from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    app_version: str = "0.1.0"
    cors_origins: list[str] = ["http://localhost:3000"]
    api_key: str  # no default — must be set in .env
    database_url: str  # New: will automatically read DATABASE_URL from .env

    model_config = {"env_file": ".env"}

settings = Settings()