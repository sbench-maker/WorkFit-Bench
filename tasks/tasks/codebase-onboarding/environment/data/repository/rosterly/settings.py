from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_url: str
    audit_sink: str = "stdout"
    model_config = SettingsConfigDict(env_file=".env")


settings = Settings()
