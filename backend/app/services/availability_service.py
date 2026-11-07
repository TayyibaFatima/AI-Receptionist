"""Slot calculation. The backend (never the AI) decides which times are free."""

from datetime import date, datetime, time, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models import Appointment, Doctor, DoctorSchedule


def clinic_now() -> datetime:
    """Current time in the clinic's timezone (timezone-aware)."""
    return datetime.now(get_settings().timezone)


def local_datetime(day: date, at: time) -> datetime:
    return datetime.combine(day, at, tzinfo=get_settings().timezone)


def _minutes(t: time) -> int:
    return t.hour * 60 + t.minute


def _to_time(minutes: int) -> time:
    return time(minutes // 60, minutes % 60)


def schedule_for_time(db: Session, doctor_id: int, day: date, at: time) -> DoctorSchedule | None:
    """The working-hours block of that doctor that contains `at`, if any."""
    schedules = db.scalars(select(DoctorSchedule).where(
        DoctorSchedule.doctor_id == doctor_id,
        DoctorSchedule.day_of_week == day.weekday(),
        DoctorSchedule.is_active.is_(True),
        DoctorSchedule.start_time <= at,
        DoctorSchedule.end_time > at,
    )).all()
    return schedules[0] if schedules else None


def get_available_slots(
    db: Session,
    doctor_id: int,
    day: date,
    duration_minutes: int | None = None,
    exclude_appointment_id: int | None = None,
) -> list[time]:
    """Start times a doctor can accept on `day`.

    A slot is offered only if: the doctor is active, it is inside an active schedule block,
    the whole appointment fits before the block ends, it does not overlap a booked appointment,
    and it is in the future (clinic timezone).
    """
    doctor = db.get(Doctor, doctor_id)
    if doctor is None or not doctor.is_active:
        return []
    now = clinic_now()
    if day < now.date():
        return []

    schedules = db.scalars(select(DoctorSchedule).where(
        DoctorSchedule.doctor_id == doctor_id,
        DoctorSchedule.day_of_week == day.weekday(),
        DoctorSchedule.is_active.is_(True),
    ).order_by(DoctorSchedule.start_time)).all()
    if not schedules:
        return []

    stmt = select(Appointment.appointment_time, Appointment.duration_minutes).where(
        Appointment.doctor_id == doctor_id,
        Appointment.appointment_date == day,
        Appointment.status == "booked",
    )
    if exclude_appointment_id is not None:
        stmt = stmt.where(Appointment.id != exclude_appointment_id)
    busy = [(_minutes(t), _minutes(t) + d) for t, d in db.execute(stmt)]

    slots: set[time] = set()
    for sch in schedules:
        start, end, step = _minutes(sch.start_time), _minutes(sch.end_time), sch.slot_minutes
        length = duration_minutes or step
        cur = start
        while cur + length <= end:
            overlaps = any(cur < busy_end and cur + length > busy_start for busy_start, busy_end in busy)
            if not overlaps and local_datetime(day, _to_time(cur)) > now:
                slots.add(_to_time(cur))
            cur += step
    return sorted(slots)


def is_slot_available(
    db: Session, doctor_id: int, day: date, at: time,
    duration_minutes: int | None = None, exclude_appointment_id: int | None = None,
) -> bool:
    return at in get_available_slots(db, doctor_id, day, duration_minutes, exclude_appointment_id)


def find_next_available_dates(
    db: Session, doctor_id: int, from_day: date, duration_minutes: int | None = None,
    limit: int = 3, horizon_days: int = 30,
) -> list[date]:
    found: list[date] = []
    for offset in range(horizon_days):
        day = from_day + timedelta(days=offset)
        if get_available_slots(db, doctor_id, day, duration_minutes):
            found.append(day)
            if len(found) >= limit:
                break
    return found
