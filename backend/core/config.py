from pydantic_settings import BaseSettings
from typing import List


class Settings(BaseSettings):
    # API Configuration
    api_title: str = "Med-Analyst NL2SQL Engine"
    api_version: str = "1.0.0"
    debug: bool = False
    port: int = 8000

    # Security
    jwt_secret_key: str
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 1440

    # Database
    supabase_url: str
    supabase_key: str
    supabase_service_key: str
    database_url: str

    # LLM Configuration
    openrouter_api_key: str
    openrouter_base_url: str = "https://openrouter.ai/api/v1"
    llm_model: str = "openai/gpt-4"
    llm_temperature: float = 0.3
    llm_max_tokens: int = 2000

    # Redis
    redis_url: str = "redis://localhost:6379"

    # Rate Limiting
    rate_limit_per_minute: int = 60
    max_query_complexity: int = 10
    query_timeout_seconds: int = 30

    # CORS
    allowed_origins: str = "http://localhost:3000"

    # Agent Configuration
    max_agent_retries: int = 3
    schema_cache_ttl: int = 3600

    @property
    def allowed_origins_list(self) -> List[str]:
        return [origin.strip() for origin in self.allowed_origins.split(",")]

    class Config:
        env_file = ".env"
        case_sensitive = False


# Global settings instance
settings = Settings()