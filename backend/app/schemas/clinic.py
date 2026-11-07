from datetime import time

from pydantic import BaseModel, ConfigDict


class ClinicOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    clinic_name: str
    address: str | None
    phone: str | None
    email: str | None
    opening_hours: str | None
    general_info: str | None
    currency: str


class ServiceOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    category: str
    description: str | None
    price: float | None
    duration_minutes: int | None


class DoctorOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    full_name: str
    specialization: str
    profile_description: str | None
    consultation_fee: float | None


class ScheduleOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    day_of_week: int
    start_time: time
    end_time: time
    slot_minutes: int


class SlotOut(BaseModel):
    time: str
    display: str


class AvailabilityOut(BaseModel):
    doctor_id: int
    date: str
    timezone: str
    slots: list[SlotOut]
