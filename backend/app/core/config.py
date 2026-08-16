from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="HT_", env_file=".env")

    database_path: str = "data/ourhome.db"
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
    vacuum_goto_target_x: int = 25500
    vacuum_goto_target_y: int = 25500
    day_off_codes: str = ".,V8,rv"
    # BTHome v2 temperature/humidity sensors, by MAC — set in .env. A room with
    # no MAC configured is simply not shown.
    sensor_living_room_mac: str = ""
    sensor_bedroom_mac: str = ""
    sensor_kitchen_mac: str = ""
    sensor_stale_after_minutes: int = 30
    # Sensor history, kept in its own SQLite file.
    timeseries_path: str = "data/sensors.db"


settings = Settings()
