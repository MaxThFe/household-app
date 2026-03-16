from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="HT_", env_file=".env")

    database_path: str = "data/hometogether.db"
    ics_url: str = ""
    ics_sync_interval_minutes: int = 30
    user1_name: str = "User1"
    user2_name: str = "User2"
    user1_pin: str = "1234"
    user2_pin: str = "5678"


settings = Settings()
