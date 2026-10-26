# app/core/config.py
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    database_url: str
    jwt_secret: str                 # séance 5
    jwt_expire_minutes: int = 60
    sql_echo: bool = False


settings = Settings()
