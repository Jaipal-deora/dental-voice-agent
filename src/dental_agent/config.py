from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    database_url: str = "sqlite+aiosqlite:///./clinic.db"
    llm_api_key: str = ""
    groq_base_url: str = "https://api.groq.com/openai/v1"
    llm_model: str = "openai/gpt-oss-20b"
    llm_timeout_s: float = 8.0
    llm_max_attempts: int = 3
    agent_model: str = "openai/gpt-oss-120b"
    fallback_model: str = "openai/gpt-oss-20b"
    judge_model: str = "openai/gpt-oss-120b"
    reasoning_effort: str = "low"
    max_output_tokens: int = 1500
    agent_language: str = "English"
    agent_timeout_s: float = 20.0
    max_tool_calls: int = 8
    max_conversation_tokens: int = 30_000
    phoenix_endpoint: str = ""
    phoenix_api_key: str = ""


settings = Settings()
