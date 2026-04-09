from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    # Environment: "development" or "production". Controls cookie security flags.
    environment: str = "development"

    # Database
    database_url: str = "postgresql://costadvisor:costadvisor@localhost:5432/costadvisor"

    # Google OAuth
    google_client_id: str = ""
    google_client_secret: str = ""

    # JWT
    jwt_secret: str = "change-me"
    jwt_algorithm: str = "HS256"
    jwt_expiry_hours: int = 72

    # URLs
    app_url: str = "http://localhost:5173"
    api_url: str = "http://localhost:8000"

    # Redis
    redis_url: str = "redis://localhost:6379/0"

    # EIA (Energy Information Administration) API key for oil/gas scraping
    eia_api_key: str = ""

    # FRED (Federal Reserve Economic Data) API key — free at https://fred.stlouisfed.org/docs/api/api_key.html
    fred_api_key: str = ""

    # External data API base URLs (no auth needed)
    ecb_api_base: str = "https://data-api.ecb.europa.eu/service"
    eurostat_api_base: str = "https://ec.europa.eu/eurostat/api/dissemination/sdmx/2.1"
    worldbank_api_base: str = "https://api.worldbank.org/v2"

    # Ollama (local LLM)
    ollama_url: str = "http://localhost:11434"
    ollama_model: str = "llama3.1:8b"
    ollama_timeout: int = 60
    # When false, ollama_generate() returns None on cache miss instead of calling Ollama.
    # Used in production with a pre-warmed Redis cache so no live LLM is needed.
    llm_enabled: bool = True

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


@lru_cache()
def get_settings() -> Settings:
    return Settings()