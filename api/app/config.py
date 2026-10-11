from pydantic_settings import BaseSettings, SettingsConfigDict

DISCLAIMER = "仅供研究参考，不构成投资建议"


class Settings(BaseSettings):
    database_url: str = "postgresql+psycopg://guanlan:guanlan@localhost:5432/guanlan"
    redis_url: str = "redis://localhost:6379/0"
    scan_interval_seconds: int = 4
    offhours_scan_interval_seconds: int = 60
    demo_auto_pulse: bool = False
    quote_source: str = "tencent"
    openai_api_key: str = ""
    openai_base_url: str = "https://api.openai.com/v1"
    openai_model: str = "gpt-4o-mini"

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = Settings()
