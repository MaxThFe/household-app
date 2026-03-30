from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="HT_", env_file=".env")

    database_path: str = "data/hometogether.db"
    ics_url: str = ""
    ics_sync_interval_minutes: int = 30
    user1_name: str = "User1"
    user2_name: str = "User2"
    roborock_username: str = ""
    roborock_password: str = ""
    vacuum_early_shift_time: str = "09:30"
    vacuum_late_shift_time: str = "15:30"
    vacuum_night_shift_time: str = "08:45"
    vacuum_day_off_time: str = "21:30"


settings = Settings()
