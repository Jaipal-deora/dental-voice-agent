from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env",extra="ignore")
    database_url: str = "sqlite+aiosqlite:///./clinic.db"
    llm_api_key:str = ""
    llm_model: str = "gemini-3.8-flash"
    llm_timeout_s:float = 8.0
    llm_max_attempts:int = 3 


settings = Settings()
