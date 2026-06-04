from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    GROQ_API_KEY: str = ""
    GEMINI_API_KEY: str = ""

    REDIS_URL: str = "redis://localhost:6379"
    DATABASE_URL: str = (
        "postgresql+asyncpg://user:password@localhost/xenonpie"
    )

    TELEGRAM_BOT_TOKEN: str = ""

    WHATSAPP_FROM: str = ""
    TWILIO_SID: str = ""
    TWILIO_AUTH: str = ""

    RESEND_API_KEY: str = ""

    X_BEARER_TOKEN: str = ""

    class Config:
        env_file = ".env"


settings = Settings()