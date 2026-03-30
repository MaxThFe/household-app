from pydantic import BaseModel, ConfigDict, field_validator


class CalendarEventCreate(BaseModel):
    date: str
    title: str
    start_time: str | None = None
    end_time: str | None = None
    all_day: int = 0
    color: str = "#534AB7"
    notes: str = ""
    source: str = "manual"

    @field_validator("source")
    @classmethod
    def must_be_manual(cls, v: str) -> str:
        if v != "manual":
            raise ValueError("source must be 'manual' for created events")
        return v


class CalendarEventUpdate(BaseModel):
    title: str | None = None
    date: str | None = None
    start_time: str | None = None
    end_time: str | None = None
    all_day: int | None = None
    color: str | None = None
    notes: str | None = None


class CalendarEventResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    date: str
    title: str
    start_time: str | None = None
    end_time: str | None = None
    all_day: int
    source: str
    source_uid: str | None = None
    color: str
    notes: str
