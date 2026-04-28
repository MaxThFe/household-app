from pydantic import BaseModel


class VacuumScheduleEntry(BaseModel):
    date: str
    shift_type: str | None
    clean_time: str | None
    is_default: bool


class VacuumOverrideCreate(BaseModel):
    clean_time: str
