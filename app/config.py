from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    app_version: str = "0.1.0"
    cors_origins: list[str] = ["http://localhost:3000"]
    
    database_url: str
    secret_key: str  # no default — JWT signing key, must be set in .env
    
    # Stripe (must be set in .env)
    stripe_secret_key: str
    stripe_webhook_secret: str

    model_config = {"env_file": ".env"}

settings = Settings()