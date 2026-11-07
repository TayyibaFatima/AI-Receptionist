import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas.appointment import AppointmentCreate, AppointmentOut, AppointmentUpdate
from app.services import appointment_service as svc
from app.services import session_service
from app.utils.deps import get_session_id

router = APIRouter(prefix="/appointments", tags=["appointments"])


@router.post("", response_model=AppointmentOut, status_code=201)
def create_appointment(body: AppointmentCreate, session_id: uuid.UUID = Depends(get_session_id),
                       db: Session = Depends(get_db)):
    session = session_service.get_or_create_session(db, session_id)
    appt = svc.create_appointment(
        db, session_id=session.id, patient_name=body.patient_name, contact=body.contact,
        appointment_type=body.appointment_type, doctor_id=body.doctor_id, service_id=body.service_id,
        day=body.appointment_date, slot_time=body.appointment_time, reason=body.reason, confirmed=body.confirmed)
    return svc.appointment_to_dict(appt)


@router.get("", response_model=list[AppointmentOut])
def list_appointments(include_cancelled: bool = False, session_id: uuid.UUID = Depends(get_session_id),
                      db: Session = Depends(get_db)):
    session_service.get_or_create_session(db, session_id)
    return [svc.appointment_to_dict(a) for a in svc.list_appointments(db, session_id, include_cancelled)]


@router.get("/{appointment_id}", response_model=AppointmentOut)
def get_appointment(appointment_id: int, session_id: uuid.UUID = Depends(get_session_id),
                    db: Session = Depends(get_db)):
    return svc.appointment_to_dict(svc.get_appointment(db, appointment_id, session_id))


@router.patch("/{appointment_id}", response_model=AppointmentOut)
def reschedule_appointment(appointment_id: int, body: AppointmentUpdate,
                           session_id: uuid.UUID = Depends(get_session_id), db: Session = Depends(get_db)):
    appt = svc.reschedule_appointment(db, appointment_id=appointment_id, session_id=session_id,
                                      new_day=body.appointment_date, new_time=body.appointment_time,
                                      confirmed=body.confirmed)
    return svc.appointment_to_dict(appt)


@router.delete("/{appointment_id}", response_model=AppointmentOut)
def cancel_appointment(appointment_id: int, confirmed: bool = False,
                       session_id: uuid.UUID = Depends(get_session_id), db: Session = Depends(get_db)):
    """Cancels (soft delete: status becomes 'cancelled', the record is kept). Requires ?confirmed=true."""
    appt = svc.cancel_appointment(db, appointment_id=appointment_id, session_id=session_id, confirmed=confirmed)
    return svc.appointment_to_dict(appt)
