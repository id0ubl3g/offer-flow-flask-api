from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

TIME_PATTERN = r"^([01]\d|2[0-3]):[0-5]\d$"

def _validate_days(days: list[int] | None) -> list[int] | None:
    if days is None:
        return None

    if not days or any(day < 1 or day > 7 for day in days):
        raise ValueError("days_of_week must contain values from 1 (Monday) to 7 (Sunday)")

    return sorted(set(days))

def _validate_timezone(timezone: str | None) -> str | None:
    if timezone is None:
        return None

    try:
        ZoneInfo(timezone)

    except (ZoneInfoNotFoundError, ValueError):
        raise ValueError("Invalid timezone")

    return timezone

class ScheduleCreate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    send_time: str = Field(pattern=TIME_PATTERN)
    days_of_week: list[int] = Field(default_factory=lambda: [1, 2, 3, 4, 5, 6, 7])
    timezone: str = "America/Sao_Paulo"
    active: bool = Field(default=True, strict=True)

    _days = field_validator("days_of_week")(_validate_days)
    _timezone = field_validator("timezone")(_validate_timezone)

class ScheduleUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    send_time: str | None = Field(default=None, pattern=TIME_PATTERN)
    days_of_week: list[int] | None = None
    timezone: str | None = None
    active: bool | None = Field(default=None, strict=True)

    _days = field_validator("days_of_week")(_validate_days)
    _timezone = field_validator("timezone")(_validate_timezone)

    @model_validator(mode="after")
    def reject_nulls(self) -> "ScheduleUpdate":
        for field in self.model_fields_set:
            if getattr(self, field) is None:
                raise ValueError(f"{field} cannot be null")

        return self

class DispatchSettingsUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    min_delay_seconds: int | None = Field(default=None, ge=5, le=300, strict=True)
    max_delay_seconds: int | None = Field(default=None, ge=5, le=300, strict=True)
    daily_limit: int | None = Field(default=None, ge=1, le=1000, strict=True)

    @model_validator(mode="after")
    def reject_nulls(self) -> "DispatchSettingsUpdate":
        for field in self.model_fields_set:
            if getattr(self, field) is None:
                raise ValueError(f"{field} cannot be null")

        return self