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
    agent_language: str = "Urdu"  # Urdu | English
    agent_timeout_s: float = 20.0
    max_tool_calls: int = 8
    max_conversation_tokens: int = 30_000
    phoenix_endpoint: str = ""
    phoenix_api_key: str = ""
    uplift_api_key: str = ""
    uplift_voice: str = "v_meklc281"
    uplift_stt_url: str = "https://api.upliftai.org/v1/transcribe/speech-to-text"
    uplift_stt_model: str = "scribe"  # scribe-mini
    uplift_stt_timeout_s: float = 4.0
    endpointing_delay_s: float = 0.5
    stt_provider: str = "groq"  # groq | uplift
    livekit_url: str = ""
    livekit_api_key: str = ""
    livekit_api_secret: str = ""


settings = Settings()
