from datetime import date

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.services.tasks import MAX_EVERY, UNITS


def _check_unit(value: str | None) -> str | None:
    if value is not None and value not in UNITS:
        raise ValueError(f"recur_unit must be one of {', '.join(UNITS)}")
    return value


class TaskCreate(BaseModel):
    title: str
    # None = one-off. 'day' | 'week' | 'month', times recur_every.
    recur_unit: str | None = None
    recur_every: int = Field(default=1, ge=1, le=MAX_EVERY)

    _unit = field_validator("recur_unit")(_check_unit)


class TaskUpdate(BaseModel):
    title: str | None = None
    # Explicit null turns a recurring task back into a one-off; omitting the
    # field leaves the stored recurrence alone.
    recur_unit: str | None = None
    recur_every: int | None = Field(default=None, ge=1, le=MAX_EVERY)

    _unit = field_validator("recur_unit")(_check_unit)


class TaskComplete(BaseModel):
    # The client sends its own local date, so a chore ticked off late in the
    # evening recurs from the day the household thinks it is.
    completed_on: date | None = None


class TaskResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    recur_unit: str | None = None
    recur_every: int = 1
    # Recurring only, and never shown as a date: null means "due now".
    next_due: str | None = None
