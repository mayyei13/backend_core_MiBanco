from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    DATABASE_URL: str
    SECRET_KEY: str
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 480
    CORE_BACKEND_URL: str = "http://localhost:8001"
    # BD del nucleo bancario para el puente de promocion (sync_outbox -> core)
    CORE_DATABASE_URL: str
    PORT: int = 8003
    CORS_ORIGINS: str = (
        "http://localhost:5173,http://127.0.0.1:5173,"
        "http://localhost:8080,http://127.0.0.1:8080,"
        "http://localhost:8082,http://127.0.0.1:8082"
    )

    @property
    def cors_origins(self) -> list[str]:
        origins = [origin.strip() for origin in self.CORS_ORIGINS.split(",")]
        public_origins = [
            "https://fronted-core-mi-banco.vercel.app",
        ]
        allowed_origins = [origin for origin in origins if origin]
        return list(dict.fromkeys([*allowed_origins, *public_origins]))

    class Config:
        env_file = ".env"

settings = Settings()
