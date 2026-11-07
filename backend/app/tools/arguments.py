"""Pydantic models that validate every tool call the AI makes. Bad input never reaches the database."""

from datetime import date, datetime, time
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

_TIME_FORMATS = ("%H:%M", "%H:%M:%S", "%I:%M %p", "%I:%M%p", "%I %p", "%I%p")


def parse_time(value):
    if isinstance(value, time):
        return value
    if isinstance(value, str):
        cleaned = value.strip().upper().replace(".", "")
        for fmt in _TIME_FORMATS:
            try:
                return datetime.strptime(cleaned, fmt).time()
            except ValueError:
                continue
    raise ValueError("time must look like 14:30 (24-hour HH:MM)")


class Args(BaseModel):
    model_config = ConfigDict(extra="ignore", str_strip_whitespace=True, populate_by_name=True)


class NoArgs(Args):
    pass


class ServicesArgs(Args):
    category: Literal["aesthetic_treatment", "general_consultation"] | None = None


class DoctorsArgs(Args):
    service_id: int | None = None
    service_name: str | None = None


class DoctorRefArgs(Args):
    doctor_id: int | None = None
    doctor_name: str | None = None


class AvailabilityArgs(Args):
    doctor_id: int | None = None
    doctor_name: str | None = None
    service_id: int | None = None
    service_name: str | None = None
    day: date = Field(alias="date")


class CreateAppointmentArgs(Args):
    appointment_type: Literal["aesthetic_treatment", "general_consultation"]
    patient_name: str = Field(min_length=2, max_length=100)
    doctor_id: int | None = None
    doctor_name: str | None = None
    service_id: int | None = None
    service_name: str | None = None
    day: date = Field(alias="date")
    slot_time: time = Field(alias="time")
    reason: str | None = Field(default=None, max_length=500)
    contact: str | None = Field(default=None, max_length=100)
    confirmed: bool = False

    _parse_time = field_validator("slot_time", mode="before")(parse_time)


class AppointmentsArgs(Args):
    include_cancelled: bool = False


class RescheduleArgs(Args):
    appointment_id: int
    new_day: date = Field(alias="new_date")
    new_time: time
    confirmed: bool = False

    _parse_time = field_validator("new_time", mode="before")(parse_time)


class CancelArgs(Args):
    appointment_id: int
    confirmed: bool = False
