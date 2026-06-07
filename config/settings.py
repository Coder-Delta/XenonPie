from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env")

    GROQ_API_KEY: str = ""
    GEMINI_API_KEY: str = ""
    COHERE_API_KEY: str = ""
    REDIS_URL: str = "redis://127.0.0.1:6379"
    DATABASE_URL: str = "postgresql+asyncpg://xenonpie:xenonpie123@localhost/xenonpie"
    TELEGRAM_BOT_TOKEN: str = ""
    WHATSAPP_FROM: str = ""
    TWILIO_SID: str = ""
    TWILIO_AUTH: str = ""
    RESEND_API_KEY: str = ""
    X_BEARER_TOKEN: str = ""
    HEALTH_HOST: str = "0.0.0.0"
    HEALTH_PORT: int = 8000
    REDIS_MAX_CONNECTIONS: int = 20
    HTTP_MAX_CONNECTIONS: int = 100
    HTTP_MAX_KEEPALIVE_CONNECTIONS: int = 20
    TELEGRAM_RATE_LIMIT_PER_SECOND: int = 1


settings = Settings()