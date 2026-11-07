import uuid

from tests.factories import future_day


def headers(sid):
    return {"X-Session-ID": sid}


def payload(clinic, **over):
    body = {"patient_name": "Sara Khan", "appointment_type": "aesthetic_treatment",
            "doctor_id": clinic.doctor.id, "service_id": clinic.facial.id,
            "appointment_date": future_day().isoformat(), "appointment_time": "10:00", "confirmed": True}
    body.update(over)
    return body


def test_full_crud_flow(client, clinic, sid):
    r = client.post("/appointments", json=payload(clinic), headers=headers(sid))
    assert r.status_code == 201, r.text
    appt_id = r.json()["id"]

    assert len(client.get("/appointments", headers=headers(sid)).json()) == 1
    assert client.get(f"/appointments/{appt_id}", headers=headers(sid)).json()["status"] == "booked"

    r = client.patch(f"/appointments/{appt_id}", headers=headers(sid),
                     json={"appointment_date": future_day(3).isoformat(), "appointment_time": "14:00", "confirmed": True})
    assert r.status_code == 200 and r.json()["appointment_time"] == "14:00"

    r = client.delete(f"/appointments/{appt_id}?confirmed=true", headers=headers(sid))
    assert r.status_code == 200 and r.json()["status"] == "cancelled"
    assert client.get("/appointments", headers=headers(sid)).json() == []


def test_confirmation_required_over_rest(client, clinic, sid):
    r = client.post("/appointments", json=payload(clinic, confirmed=False), headers=headers(sid))
    assert r.status_code == 400 and r.json()["code"] == "confirmation_required"


def test_duplicate_returns_409(client, clinic, sid):
    assert client.post("/appointments", json=payload(clinic), headers=headers(sid)).status_code == 201
    r = client.post("/appointments", json=payload(clinic), headers=headers(str(uuid.uuid4())))
    assert r.status_code == 409


def test_validation_errors(client, clinic, sid):
    assert client.post("/appointments", json=payload(clinic, doctor_id=9999), headers=headers(sid)).status_code == 404
    assert client.post("/appointments", json=payload(clinic, appointment_time="25:99"), headers=headers(sid)).status_code == 422
    assert client.post("/appointments", json=payload(clinic), headers={}).status_code == 400
    assert client.post("/appointments", json=payload(clinic), headers=headers("not-a-uuid")).status_code == 400


def test_other_session_cannot_see_or_change(client, clinic, sid):
    appt_id = client.post("/appointments", json=payload(clinic), headers=headers(sid)).json()["id"]
    other = headers(str(uuid.uuid4()))
    assert client.get("/appointments", headers=other).json() == []
    assert client.get(f"/appointments/{appt_id}", headers=other).status_code == 404
    assert client.delete(f"/appointments/{appt_id}?confirmed=true", headers=other).status_code == 404
    assert client.patch(f"/appointments/{appt_id}", headers=other, json={
        "appointment_date": future_day().isoformat(), "appointment_time": "15:00", "confirmed": True}).status_code == 404


def test_availability_endpoint(client, clinic, sid):
    day = future_day().isoformat()
    slots = client.get(f"/availability?doctor_id={clinic.doctor.id}&date={day}").json()["slots"]
    assert slots[0] == {"time": "09:00", "display": "9:00 AM"}
    client.post("/appointments", json=payload(clinic), headers=headers(sid))
    after = [s["time"] for s in client.get(f"/availability?doctor_id={clinic.doctor.id}&date={day}").json()["slots"]]
    assert "10:00" not in after
