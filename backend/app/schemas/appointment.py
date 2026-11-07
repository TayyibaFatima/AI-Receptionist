from datetime import date, datetime, time
from typing import Literal

from pydantic import BaseModel, Field, field_validator

from app.tools.arguments import parse_time


class AppointmentCreate(BaseModel):
    patient_name: str = Field(min_length=2, max_length=100)
    contact: str | None = Field(default=None, max_length=100)
    appointment_type: Literal["aesthetic_treatment", "general_consultation"]
    doctor_id: int
    service_id: int | None = None
    appointment_date: date
    appointment_time: time
    reason: str | None = Field(default=None, max_length=500)
    confirmed: bool = Field(default=False, description="Must be true: the patient explicitly confirmed.")

    _t = field_validator("appointment_time", mode="before")(parse_time)


class AppointmentUpdate(BaseModel):
    appointment_date: date
    appointment_time: time
    confirmed: bool = False

    _t = field_validator("appointment_time", mode="before")(parse_time)


class AppointmentOut(BaseModel):
    id: int
    patient_name: str
    appointment_type: str
    appointment_type_label: str
    service_id: int | None
    service_name: str | None
    doctor_id: int
    doctor_name: str
    appointment_date: date
    appointment_time: str
    duration_minutes: int
    status: str
    reason: str | None
    fee: float | None
    created_at: datetime
