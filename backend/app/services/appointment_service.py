"""Booking, rescheduling and cancelling. All business rules live here."""

import uuid
from dataclasses import dataclass
from datetime import date, time
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import Appointment, ConversationSession, Doctor, Patient, Service, doctor_services
from app.services import availability_service as avail
from app.services import catalog_service as catalog
from app.services.errors import (
    ConfirmationRequiredError, InvalidInputError, NotFoundError, ServiceError, SlotUnavailableError,
)

APPOINTMENT_TYPES = ("aesthetic_treatment", "general_consultation")
TYPE_LABELS = {"aesthetic_treatment": "Aesthetic Treatment", "general_consultation": "General Consultation"}
SLOT_TAKEN = "That time is no longer available. Please choose another slot."


@dataclass
class BookingPlan:
    patient_name: str
    contact: str | None
    appointment_type: str
    doctor: Doctor
    service: Service | None
    day: date
    slot_time: time
    duration_minutes: int
    reason: str | None

    @property
    def fee(self) -> Decimal | None:
        if self.appointment_type == "aesthetic_treatment" and self.service is not None:
            return self.service.price
        if self.doctor.consultation_fee is not None:
            return self.doctor.consultation_fee
        return self.service.price if self.service is not None else None


def _clean_name(name: str | None) -> str:
    cleaned = " ".join((name or "").split())
    if len(cleaned) < 2 or len(cleaned) > 100:
        raise InvalidInputError("Please provide the patient's full name (2-100 characters).")
    return cleaned


def lock_doctor(db: Session, doctor_id: int) -> None:
    """Row lock: concurrent bookings for the same doctor wait for each other (no double booking)."""
    row = db.execute(select(Doctor.id).where(Doctor.id == doctor_id).with_for_update()).first()
    if row is None:
        raise NotFoundError(f"No doctor with id {doctor_id} exists.")


def plan_booking(
    db: Session, *, patient_name: str, contact: str | None, appointment_type: str, doctor_id: int,
    service_id: int | None, day: date, slot_time: time, reason: str | None,
) -> BookingPlan:
    """Validate everything about a booking request (except confirmation and slot conflicts)."""
    name = _clean_name(patient_name)
    if appointment_type not in APPOINTMENT_TYPES:
        raise InvalidInputError("appointment_type must be 'aesthetic_treatment' or 'general_consultation'.")
    doctor = catalog.get_doctor(db, doctor_id, require_active=True)
    service = catalog.get_service(db, service_id, require_active=True) if service_id is not None else None

    reason_clean = " ".join((reason or "").split())[:500] or None
    if appointment_type == "aesthetic_treatment":
        if service is None:
            raise InvalidInputError("An aesthetic treatment must be selected.")
        if service.category != "aesthetic_treatment":
            raise InvalidInputError(f"{service.name} is not an aesthetic treatment.")
    else:
        if service is not None and service.category != "general_consultation":
            raise InvalidInputError(f"{service.name} is not a general consultation.")
        if not reason_clean or len(reason_clean) < 3:
            raise InvalidInputError("Please give a short reason for the visit.")

    if service is not None:
        offered_by = set(db.scalars(
            select(doctor_services.c.doctor_id).where(doctor_services.c.service_id == service.id)
        ))
        if offered_by and doctor.id not in offered_by:
            raise InvalidInputError(f"{doctor.full_name} does not offer {service.name}.")

    if avail.local_datetime(day, slot_time) <= avail.clinic_now():
        raise InvalidInputError("That date and time is in the past.")

    block = avail.schedule_for_time(db, doctor.id, day, slot_time)
    if block is None:
        raise InvalidInputError(f"{doctor.full_name} does not work at that day/time.")
    duration = service.duration_minutes if service and service.duration_minutes else block.slot_minutes

    return BookingPlan(name, (contact or "").strip()[:100] or None, appointment_type, doctor, service,
                       day, slot_time, duration, reason_clean)


def ensure_slot_free(db: Session, plan: BookingPlan, exclude_appointment_id: int | None = None) -> None:
    if not avail.is_slot_available(db, plan.doctor.id, plan.day, plan.slot_time,
                                   plan.duration_minutes, exclude_appointment_id):
        raise SlotUnavailableError(SLOT_TAKEN)


def _get_or_create_patient(db: Session, session_id: uuid.UUID | None, name: str, contact: str | None) -> Patient:
    session = db.get(ConversationSession, session_id) if session_id else None
    if session is not None and session.patient_id:
        existing = db.get(Patient, session.patient_id)
        if existing and existing.full_name.lower() == name.lower():
            if contact:
                existing.contact = contact
            return existing
    patient = Patient(full_name=name, contact=contact)
    db.add(patient)
    db.flush()
    if session is not None:
        session.patient_id = patient.id
    return patient


def create_appointment(
    db: Session, *, session_id: uuid.UUID, patient_name: str, contact: str | None, appointment_type: str,
    doctor_id: int, service_id: int | None, day: date, slot_time: time, reason: str | None, confirmed: bool,
) -> Appointment:
    if not confirmed:
        raise ConfirmationRequiredError("The patient must explicitly confirm before an appointment is created.")
    try:
        lock_doctor(db, doctor_id)  # serialises bookings per doctor
        plan = plan_booking(db, patient_name=patient_name, contact=contact, appointment_type=appointment_type,
                            doctor_id=doctor_id, service_id=service_id, day=day, slot_time=slot_time, reason=reason)
        ensure_slot_free(db, plan)  # re-checked INSIDE the transaction
        patient = _get_or_create_patient(db, session_id, plan.patient_name, plan.contact)
        appt = Appointment(
            patient_id=patient.id, doctor_id=plan.doctor.id,
            service_id=plan.service.id if plan.service else None, session_id=session_id,
            appointment_type=plan.appointment_type, reason=plan.reason, appointment_date=plan.day,
            appointment_time=plan.slot_time, duration_minutes=plan.duration_minutes, status="booked",
        )
        db.add(appt)
        db.flush()
        db.commit()  # unique partial index is the last line of defence
    except IntegrityError:
        db.rollback()
        raise SlotUnavailableError(SLOT_TAKEN)
    except ServiceError:
        db.rollback()
        raise
    db.refresh(appt)
    return appt


def get_appointment(db: Session, appointment_id: int, session_id: uuid.UUID, for_update: bool = False) -> Appointment:
    """Ownership is enforced in the query. Someone else's appointment looks like 'not found'."""
    stmt = select(Appointment).where(Appointment.id == appointment_id, Appointment.session_id == session_id)
    if for_update:
        stmt = stmt.with_for_update()
    appt = db.scalars(stmt).first()
    if appt is None:
        raise NotFoundError("Appointment not found for this session.")
    return appt


def list_appointments(db: Session, session_id: uuid.UUID, include_cancelled: bool = False) -> list[Appointment]:
    stmt = select(Appointment).where(Appointment.session_id == session_id)
    if not include_cancelled:
        stmt = stmt.where(Appointment.status == "booked")
    stmt = stmt.order_by(Appointment.appointment_date, Appointment.appointment_time)
    return list(db.scalars(stmt))


def check_reschedule(db: Session, appt: Appointment, new_day: date, new_time: time) -> BookingPlan:
    if appt.status != "booked":
        raise InvalidInputError(f"This appointment is {appt.status} and cannot be rescheduled.")
    if avail.local_datetime(appt.appointment_date, appt.appointment_time) <= avail.clinic_now():
        raise InvalidInputError("Past appointments cannot be rescheduled.")
    if (new_day, new_time) == (appt.appointment_date, appt.appointment_time):
        raise InvalidInputError("The appointment is already at that date and time.")
    plan = plan_booking(
        db, patient_name=appt.patient.full_name, contact=None, appointment_type=appt.appointment_type,
        doctor_id=appt.doctor_id, service_id=appt.service_id, day=new_day, slot_time=new_time,
        reason=appt.reason or "Rescheduled appointment",
    )
    plan.duration_minutes = appt.duration_minutes
    ensure_slot_free(db, plan, exclude_appointment_id=appt.id)
    return plan


def reschedule_appointment(
    db: Session, *, appointment_id: int, session_id: uuid.UUID, new_day: date, new_time: time, confirmed: bool,
) -> Appointment:
    if not confirmed:
        raise ConfirmationRequiredError("The patient must explicitly confirm before rescheduling.")
    try:
        appt = get_appointment(db, appointment_id, session_id, for_update=True)
        lock_doctor(db, appt.doctor_id)
        check_reschedule(db, appt, new_day, new_time)
        appt.appointment_date, appt.appointment_time = new_day, new_time
        db.flush()
        db.commit()
    except IntegrityError:
        db.rollback()
        raise SlotUnavailableError(SLOT_TAKEN)
    except ServiceError:
        db.rollback()
        raise
    db.refresh(appt)
    return appt


def check_cancel(appt: Appointment) -> None:
    if appt.status != "booked":
        raise InvalidInputError(f"This appointment is already {appt.status}.")
    if avail.local_datetime(appt.appointment_date, appt.appointment_time) <= avail.clinic_now():
        raise InvalidInputError("Past appointments cannot be cancelled.")


def cancel_appointment(db: Session, *, appointment_id: int, session_id: uuid.UUID, confirmed: bool) -> Appointment:
    if not confirmed:
        raise ConfirmationRequiredError("The patient must explicitly confirm before cancelling.")
    try:
        appt = get_appointment(db, appointment_id, session_id, for_update=True)
        check_cancel(appt)
        appt.status = "cancelled"
        db.commit()
    except ServiceError:
        db.rollback()
        raise
    db.refresh(appt)
    return appt


def appointment_to_dict(appt: Appointment) -> dict:
    is_aesthetic = appt.appointment_type == "aesthetic_treatment"
    fee = appt.service.price if (is_aesthetic and appt.service) else appt.doctor.consultation_fee
    if fee is None and appt.service is not None:
        fee = appt.service.price
    return {
        "id": appt.id,
        "patient_name": appt.patient.full_name,
        "appointment_type": appt.appointment_type,
        "appointment_type_label": TYPE_LABELS[appt.appointment_type],
        "service_id": appt.service_id,
        "service_name": appt.service.name if appt.service else None,
        "doctor_id": appt.doctor_id,
        "doctor_name": appt.doctor.full_name,
        "appointment_date": appt.appointment_date,
        "appointment_time": appt.appointment_time.strftime("%H:%M"),
        "duration_minutes": appt.duration_minutes,
        "status": appt.status,
        "reason": appt.reason,
        "fee": float(fee) if fee is not None else None,
        "created_at": appt.created_at,
    }
