"""Read-only access to clinic info, services, doctors and schedules."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import ClinicInfo, Doctor, DoctorSchedule, Service, doctor_services
from app.services.errors import InvalidInputError, NotFoundError

DAY_NAMES = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]


def _escape_like(value: str) -> str:
    return value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


def get_clinic_info(db: Session) -> ClinicInfo | None:
    return db.scalars(select(ClinicInfo).order_by(ClinicInfo.id).limit(1)).first()


def list_services(db: Session, category: str | None = None, active_only: bool = True) -> list[Service]:
    stmt = select(Service).order_by(Service.category, Service.name)
    if active_only:
        stmt = stmt.where(Service.is_active.is_(True))
    if category:
        stmt = stmt.where(Service.category == category)
    return list(db.scalars(stmt))


def list_doctors(db: Session, service_id: int | None = None, active_only: bool = True) -> list[Doctor]:
    stmt = select(Doctor).order_by(Doctor.full_name)
    if active_only:
        stmt = stmt.where(Doctor.is_active.is_(True))
    if service_id is not None:
        stmt = stmt.join(doctor_services, doctor_services.c.doctor_id == Doctor.id).where(
            doctor_services.c.service_id == service_id
        )
    return list(db.scalars(stmt))


def get_doctor(db: Session, doctor_id: int, require_active: bool = False) -> Doctor:
    doctor = db.get(Doctor, doctor_id)
    if doctor is None:
        raise NotFoundError(f"No doctor with id {doctor_id} exists.")
    if require_active and not doctor.is_active:
        raise InvalidInputError(f"{doctor.full_name} is not currently available for appointments.")
    return doctor


def get_service(db: Session, service_id: int, require_active: bool = False) -> Service:
    service = db.get(Service, service_id)
    if service is None:
        raise NotFoundError(f"No service with id {service_id} exists.")
    if require_active and not service.is_active:
        raise InvalidInputError(f"{service.name} is not currently offered.")
    return service


def resolve_doctor(db: Session, doctor_id: int | None = None, doctor_name: str | None = None) -> Doctor:
    """Find a doctor by id or (partial) name. Always returns an ACTIVE doctor."""
    if doctor_id is not None:
        return get_doctor(db, doctor_id, require_active=True)
    if doctor_name and doctor_name.strip():
        pattern = f"%{_escape_like(doctor_name.strip())}%"
        matches = list(db.scalars(
            select(Doctor).where(Doctor.full_name.ilike(pattern, escape="\\"), Doctor.is_active.is_(True))
        ))
        if not matches:
            raise NotFoundError(f"No active doctor matches '{doctor_name}'.")
        if len(matches) > 1:
            names = ", ".join(d.full_name for d in matches)
            raise InvalidInputError(f"Several doctors match '{doctor_name}': {names}. Please be more specific.")
        return matches[0]
    raise InvalidInputError("Please provide a doctor_id or doctor_name.")


def resolve_service(db: Session, service_id: int | None = None, service_name: str | None = None) -> Service:
    if service_id is not None:
        return get_service(db, service_id, require_active=True)
    if service_name and service_name.strip():
        pattern = f"%{_escape_like(service_name.strip())}%"
        matches = list(db.scalars(
            select(Service).where(Service.name.ilike(pattern, escape="\\"), Service.is_active.is_(True))
        ))
        exact = [s for s in matches if s.name.lower() == service_name.strip().lower()]
        if exact:
            return exact[0]
        if not matches:
            raise NotFoundError(f"No active service matches '{service_name}'.")
        if len(matches) > 1:
            names = ", ".join(s.name for s in matches)
            raise InvalidInputError(f"Several services match '{service_name}': {names}. Please be more specific.")
        return matches[0]
    raise InvalidInputError("Please provide a service_id or service_name.")


def get_doctor_schedule(db: Session, doctor_id: int) -> list[DoctorSchedule]:
    get_doctor(db, doctor_id)
    return list(db.scalars(
        select(DoctorSchedule)
        .where(DoctorSchedule.doctor_id == doctor_id, DoctorSchedule.is_active.is_(True))
        .order_by(DoctorSchedule.day_of_week, DoctorSchedule.start_time)
    ))
