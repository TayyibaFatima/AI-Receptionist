"""Helpers that create small, predictable test data."""

from datetime import date, time, timedelta
from types import SimpleNamespace

from app.models import ClinicInfo, Doctor, DoctorSchedule, Service
from app.services.availability_service import clinic_now


def future_day(days: int = 2) -> date:
    return clinic_now().date() + timedelta(days=days)


def create_clinic(db) -> SimpleNamespace:
    db.add(ClinicInfo(id=1, clinic_name="Luméra Aesthetics", address="Test address", phone="000",
                      opening_hours="9-5", general_info="Test", currency="PKR"))
    facial = Service(name="HydraFacial", category="aesthetic_treatment", description="d", price=12000,
                     duration_minutes=60, is_active=True)
    consult = Service(name="General Physician Consultation", category="general_consultation", description="d",
                      price=2500, duration_minutes=30, is_active=True)
    retired = Service(name="Old Treatment", category="aesthetic_treatment", price=1, duration_minutes=30,
                      is_active=False)
    doctor = Doctor(full_name="Dr. Test One", specialization="Aesthetic Physician", consultation_fee=5000,
                    is_active=True)
    gp = Doctor(full_name="Dr. Test GP", specialization="General Physician", consultation_fee=2500, is_active=True)
    inactive = Doctor(full_name="Dr. Inactive", specialization="Dermatologist", consultation_fee=4000,
                      is_active=False)
    doctor.services = [facial]
    gp.services = [consult]
    db.add_all([facial, consult, retired, doctor, gp, inactive])
    db.flush()
    for d in (doctor, gp, inactive):  # every day, 09:00-17:00, 30-minute slots
        for dow in range(7):
            db.add(DoctorSchedule(doctor_id=d.id, day_of_week=dow, start_time=time(9), end_time=time(17),
                                  slot_minutes=30, is_active=True))
    db.commit()
    return SimpleNamespace(doctor=doctor, gp=gp, inactive=inactive, facial=facial, consult=consult, retired=retired)
