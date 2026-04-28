from pydantic import BaseModel, ConfigDict


class HouseplantCreate(BaseModel):
    name: str
    watering_frequency_days: int
    image_data: str | None = None


class HouseplantUpdate(BaseModel):
    name: str | None = None
    watering_frequency_days: int | None = None
    image_data: str | None = None


class HouseplantResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    watering_frequency_days: int
    last_watered_at: str
    image_data: str | None = None
    created_at: str
    days_until_due: int
