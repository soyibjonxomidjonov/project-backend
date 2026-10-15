from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    APP_ENV: str = "development"
    APP_NAME: str = "Universal AI Backend"
    BASE_DOMAIN: str = "localhost"
    API_URL: str = "http://localhost:8000"
    ALLOWED_FRONTEND_SUFFIX: str = ".localhost"
    EXTRA_CORS_ORIGINS: str = "http://localhost:5173,http://localhost:3000"

    DATABASE_URL: str = "postgresql+asyncpg://app:app@db:5432/app"

    # Email (SMTP)
    EMAIL_HOST: str = "smtp.gmail.com"
    EMAIL_PORT: int = 587
    EMAIL_HOST_USER: str = ""
    EMAIL_HOST_PASSWORD: str = ""

    # Google OAuth (ixtiyoriy)
    GOOGLE_CLIENT_ID: str = ""
    GOOGLE_CLIENT_SECRET: str = ""
    GOOGLE_REDIRECT_URI: str = ""

    # JWT
    SECRET_KEY: str = "change-me"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 240
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    SESSION_SECRET: str = "change-me"
    ADMIN_EMAILS: str = ""
    DEMO_LOGIN_ENABLED: bool = True

    # LLM (Groq — OpenAI-compatible)
    LLM_BASE_URL: str = "https://api.groq.com/openai/v1"
    LLM_API_KEY: str = ""
    LLM_API_KEYS: str = ""
    LLM_MODEL: str = "openai/gpt-oss-120b"
    LLM_FALLBACK_MODEL: str = "qwen/qwen3.8-27b"

    # Gemini (rasm tahlili + embedding)
    GEMINI_API_KEY: str = ""
    GEMINI_API_KEYS: str = ""

    # Embedding (Gemini gemini-embedding-001 = 3072 dim)
    EMBEDDING_DIM: int = 3072

    # Fayllar
    UPLOAD_DIR: str = "/data/uploads"
    MAX_UPLOAD_MB: int = 20

    GIT_SHA: str = "dev"

    model_config = {"env_file": ("../.env", ".env"), "extra": "ignore"}

    def get_llm_keys(self) -> list[str]:
        if self.LLM_API_KEYS:
            return [k.strip() for k in self.LLM_API_KEYS.split(",") if k.strip()]
        if self.LLM_API_KEY:
            return [self.LLM_API_KEY]
        return []


settings = Settings()
