from concurrent.futures import ThreadPoolExecutor
from datetime import time, timedelta
import uuid

import pytest

from app.database import SessionLocal
from app.services import appointment_service as svc
from app.services import availability_service as avail
from app.services import session_service
from app.services.errors import (
    ConfirmationRequiredError, InvalidInputError, NotFoundError, SlotUnavailableError,
)
from tests.factories import future_day


def book(db, clinic, session_id, *, at=time(10, 0), day=None, confirmed=True, name="Sara Khan", **over):
    session_service.get_or_create_session(db, session_id)
    params = dict(session_id=session_id, patient_name=name, contact=None, appointment_type="aesthetic_treatment",
                  doctor_id=clinic.doctor.id, service_id=clinic.facial.id, day=day or future_day(), slot_time=at,
                  reason=None, confirmed=confirmed)
    params.update(over)
    return svc.create_appointment(db, **params)


def test_availability_lists_real_slots(db, clinic):
    slots = avail.get_available_slots(db, clinic.doctor.id, future_day())
    assert time(9, 0) in slots and time(16, 30) in slots and time(17, 0) not in slots


def test_long_treatment_must_fit_before_closing(db, clinic):
    slots = avail.get_available_slots(db, clinic.doctor.id, future_day(), duration_minutes=60)
    assert time(16, 0) in slots and time(16, 30) not in slots


def test_successful_booking_hides_slot(db, clinic):
    sid = uuid.uuid4()
    appt = book(db, clinic, sid)
    assert appt.id and appt.status == "booked" and appt.duration_minutes == 60
    slots = avail.get_available_slots(db, clinic.doctor.id, future_day())
    assert time(10, 0) not in slots and time(10, 30) not in slots  # 60-minute treatment blocks two slots
    assert time(11, 0) in slots


def test_duplicate_booking_prevented(db, clinic):
    book(db, clinic, uuid.uuid4())
    with pytest.raises(SlotUnavailableError):
        book(db, clinic, uuid.uuid4())


def test_overlapping_booking_prevented(db, clinic):
    book(db, clinic, uuid.uuid4(), at=time(10, 0))
    with pytest.raises(SlotUnavailableError):
        book(db, clinic, uuid.uuid4(), at=time(10, 30))


def test_booking_without_confirmation_rejected(db, clinic):
    with pytest.raises(ConfirmationRequiredError):
        book(db, clinic, uuid.uuid4(), confirmed=False)


def test_invalid_doctor_and_service(db, clinic):
    with pytest.raises(NotFoundError):
        book(db, clinic, uuid.uuid4(), doctor_id=9999)
    with pytest.raises(InvalidInputError):
        book(db, clinic, uuid.uuid4(), doctor_id=clinic.inactive.id)
    with pytest.raises(NotFoundError):
        book(db, clinic, uuid.uuid4(), service_id=9999)
    with pytest.raises(InvalidInputError):
        book(db, clinic, uuid.uuid4(), service_id=clinic.retired.id)


def test_doctor_must_offer_the_service(db, clinic):
    with pytest.raises(InvalidInputError):
        book(db, clinic, uuid.uuid4(), doctor_id=clinic.gp.id)


def test_past_and_outside_hours_rejected(db, clinic):
    with pytest.raises(InvalidInputError):
        book(db, clinic, uuid.uuid4(), day=future_day(-1))
    with pytest.raises(InvalidInputError):
        book(db, clinic, uuid.uuid4(), at=time(20, 0))


def test_general_consultation_needs_no_treatment_but_needs_reason(db, clinic):
    sid = uuid.uuid4()
    with pytest.raises(InvalidInputError):
        book(db, clinic, sid, appointment_type="general_consultation", doctor_id=clinic.gp.id,
             service_id=None, reason="")
    appt = book(db, clinic, sid, appointment_type="general_consultation", doctor_id=clinic.gp.id,
                service_id=None, reason="Persistent cough")
    assert appt.service_id is None and appt.appointment_type == "general_consultation"


def test_reschedule(db, clinic):
    sid = uuid.uuid4()
    appt = book(db, clinic, sid)
    moved = svc.reschedule_appointment(db, appointment_id=appt.id, session_id=sid,
                                       new_day=future_day(3), new_time=time(14, 0), confirmed=True)
    assert moved.appointment_date == future_day(3) and moved.appointment_time == time(14, 0)
    assert time(10, 0) in avail.get_available_slots(db, clinic.doctor.id, future_day())  # old slot freed


def test_reschedule_into_taken_slot_and_without_confirmation(db, clinic):
    sid = uuid.uuid4()
    first = book(db, clinic, sid, at=time(10, 0))
    book(db, clinic, uuid.uuid4(), at=time(12, 0))
    with pytest.raises(SlotUnavailableError):
        svc.reschedule_appointment(db, appointment_id=first.id, session_id=sid, new_day=future_day(),
                                   new_time=time(12, 0), confirmed=True)
    with pytest.raises(ConfirmationRequiredError):
        svc.reschedule_appointment(db, appointment_id=first.id, session_id=sid, new_day=future_day(),
                                   new_time=time(13, 0), confirmed=False)


def test_cancel_frees_slot(db, clinic):
    sid = uuid.uuid4()
    appt = book(db, clinic, sid)
    cancelled = svc.cancel_appointment(db, appointment_id=appt.id, session_id=sid, confirmed=True)
    assert cancelled.status == "cancelled"
    assert time(10, 0) in avail.get_available_slots(db, clinic.doctor.id, future_day())
    book(db, clinic, uuid.uuid4())  # slot can be booked again


def test_session_isolation(db, clinic):
    owner, stranger = uuid.uuid4(), uuid.uuid4()
    appt = book(db, clinic, owner)
    session_service.get_or_create_session(db, stranger)
    with pytest.raises(NotFoundError):
        svc.get_appointment(db, appt.id, stranger)
    with pytest.raises(NotFoundError):
        svc.cancel_appointment(db, appointment_id=appt.id, session_id=stranger, confirmed=True)
    with pytest.raises(NotFoundError):
        svc.reschedule_appointment(db, appointment_id=appt.id, session_id=stranger, new_day=future_day(),
                                   new_time=time(15, 0), confirmed=True)
    assert svc.list_appointments(db, stranger) == []
    assert len(svc.list_appointments(db, owner)) == 1


def test_concurrent_bookings_only_one_wins(clinic):
    """Two visitors click at the same moment: PostgreSQL locking lets exactly one through."""
    day = future_day()

    def attempt(_):
        db = SessionLocal()
        try:
            sid = uuid.uuid4()
            session_service.get_or_create_session(db, sid)
            svc.create_appointment(db, session_id=sid, patient_name="Racer One", contact=None,
                                   appointment_type="aesthetic_treatment", doctor_id=clinic.doctor.id,
                                   service_id=clinic.facial.id, day=day, slot_time=time(15, 0),
                                   reason=None, confirmed=True)
            return "ok"
        except SlotUnavailableError:
            return "taken"
        finally:
            db.close()

    with ThreadPoolExecutor(max_workers=6) as pool:
        results = list(pool.map(attempt, range(6)))
    assert results.count("ok") == 1 and results.count("taken") == 5
