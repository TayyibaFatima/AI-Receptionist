from sqlalchemy import text

from app.services import catalog_service as catalog
from app.services.errors import InvalidInputError, NotFoundError
import pytest


def test_database_connection(db):
    assert db.execute(text("SELECT 1")).scalar() == 1


def test_health_endpoint(client):
    r = client.get("/health")
    assert r.status_code == 200 and r.json()["database"] == "connected"


def test_service_retrieval_only_active(db, clinic):
    names = [s.name for s in catalog.list_services(db)]
    assert "HydraFacial" in names and "Old Treatment" not in names


def test_service_category_filter(db, clinic):
    names = [s.name for s in catalog.list_services(db, category="general_consultation")]
    assert names == ["General Physician Consultation"]


def test_doctor_retrieval_only_active(db, clinic):
    names = [d.full_name for d in catalog.list_doctors(db)]
    assert "Dr. Inactive" not in names and "Dr. Test One" in names


def test_doctors_for_service(db, clinic):
    assert [d.full_name for d in catalog.list_doctors(db, service_id=clinic.facial.id)] == ["Dr. Test One"]


def test_schedule_retrieval(db, clinic):
    assert len(catalog.get_doctor_schedule(db, clinic.doctor.id)) == 7


def test_invalid_doctor_and_inactive_doctor(db, clinic):
    with pytest.raises(NotFoundError):
        catalog.get_doctor(db, 9999)
    with pytest.raises(InvalidInputError):
        catalog.resolve_doctor(db, doctor_id=clinic.inactive.id)


def test_rest_endpoints(client, clinic):
    assert client.get("/clinic").json()["clinic_name"] == "Luméra Aesthetics"
    assert len(client.get("/services").json()) == 2
    assert len(client.get("/doctors").json()) == 2
    assert client.get(f"/doctors/{clinic.doctor.id}/schedule").status_code == 200
    assert client.get("/doctors/9999/schedule").status_code == 404
