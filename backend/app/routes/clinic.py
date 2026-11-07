from datetime import date as date_type
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import get_db
from app.schemas.clinic import AvailabilityOut, ClinicOut, DoctorOut, ScheduleOut, ServiceOut
from app.services import availability_service as avail
from app.services import catalog_service as catalog
from app.tools.executor import fmt_time

router = APIRouter(tags=["clinic"])


@router.get("/clinic", response_model=ClinicOut)
def get_clinic(db: Session = Depends(get_db)):
    info = catalog.get_clinic_info(db)
    if info is None:
        raise HTTPException(404, "Clinic information is not available.")
    return info


@router.get("/services", response_model=list[ServiceOut])
def get_services(category: Literal["aesthetic_treatment", "general_consultation"] | None = None,
                 db: Session = Depends(get_db)):
    return catalog.list_services(db, category=category)


@router.get("/doctors", response_model=list[DoctorOut])
def get_doctors(service_id: int | None = None, db: Session = Depends(get_db)):
    return catalog.list_doctors(db, service_id=service_id)


@router.get("/doctors/{doctor_id}/schedule", response_model=list[ScheduleOut])
def get_schedule(doctor_id: int, db: Session = Depends(get_db)):
    return catalog.get_doctor_schedule(db, doctor_id)


@router.get("/availability", response_model=AvailabilityOut)
def get_availability(doctor_id: int, day: date_type = Query(alias="date"), service_id: int | None = None,
                     db: Session = Depends(get_db)):
    catalog.get_doctor(db, doctor_id, require_active=True)
    duration = None
    if service_id is not None:
        duration = catalog.get_service(db, service_id, require_active=True).duration_minutes
    slots = avail.get_available_slots(db, doctor_id, day, duration)
    return AvailabilityOut(
        doctor_id=doctor_id, date=day.isoformat(), timezone=get_settings().clinic_timezone,
        slots=[{"time": t.strftime("%H:%M"), "display": fmt_time(t)} for t in slots])
