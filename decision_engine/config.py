from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Loads and validates environment variables."""

    DATABASE_URL: str
    REDIS_URL: str
    INTERNAL_API_KEY: str

    model_config = SettingsConfigDict(env_file=".env")


settings = Settings()
