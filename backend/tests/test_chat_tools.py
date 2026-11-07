"""Chat + AI tool calling, using a scripted fake Groq client (no network, no API key needed)."""

import json
import uuid
from types import SimpleNamespace

import pytest

from app.agents import receptionist
from tests.factories import future_day


def tool_call(name, args, call_id="call_1"):
    return SimpleNamespace(id=call_id, function=SimpleNamespace(name=name, arguments=json.dumps(args)))


def reply_with_tools(*calls):
    msg = SimpleNamespace(content=None, tool_calls=list(calls))
    return SimpleNamespace(choices=[SimpleNamespace(message=msg)])


def reply_text(text):
    return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=text, tool_calls=None))])


class FakeGroq:
    """Plays back scripted model responses in order."""

    def __init__(self, script):
        self.script = list(script)
        self.seen_tool_results = []
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self._create))

    def _create(self, **kwargs):
        for m in kwargs["messages"]:
            if m["role"] == "tool":
                self.seen_tool_results.append(json.loads(m["content"]))
        return self.script.pop(0)


@pytest.fixture
def fake(monkeypatch):
    def install(script):
        client = FakeGroq(script)
        monkeypatch.setattr(receptionist, "get_groq_client", lambda: client)
        return client
    return install


def booking_args(clinic, confirmed):
    return {"appointment_type": "aesthetic_treatment", "patient_name": "Sara Khan", "doctor_id": clinic.doctor.id,
            "service_id": clinic.facial.id, "date": future_day().isoformat(), "time": "10:00",
            "confirmed": confirmed}


def chat(client, sid, message):
    r = client.post("/chat", json={"session_id": sid, "message": message})
    assert r.status_code == 200, r.text
    return r.json()


def test_services_tool_reads_database(client, clinic, sid, fake):
    fake([reply_with_tools(tool_call("get_services", {})), reply_text("Here are our services.")])
    data = chat(client, sid, "What treatments do you offer?")
    assert data["reply"] == "Here are our services."
    assert data["cards"][0]["type"] == "services"
    assert {i["name"] for i in data["cards"][0]["items"]} == {"HydraFacial", "General Physician Consultation"}


def test_full_booking_conversation(client, clinic, sid, fake):
    # Turn 1: AI proposes -> summary card, nothing booked yet
    fake([reply_with_tools(tool_call("create_appointment", booking_args(clinic, False))),
          reply_text("Would you like me to confirm this appointment?")])
    t1 = chat(client, sid, "Book a HydraFacial with Dr. Test One tomorrow at 10, I'm Sara Khan")
    assert t1["cards"][0]["type"] == "confirmation" and not t1["appointments_changed"]
    assert client.get("/appointments", headers={"X-Session-ID": sid}).json() == []

    # Turn 2: patient says yes -> booked
    fake([reply_with_tools(tool_call("create_appointment", booking_args(clinic, True))),
          reply_text("Your appointment is booked!")])
    t2 = chat(client, sid, "Yes, please confirm")
    assert t2["appointments_changed"] and t2["cards"][0]["type"] == "booked"
    booked = client.get("/appointments", headers={"X-Session-ID": sid}).json()
    assert len(booked) == 1 and booked[0]["appointment_time"] == "10:00"


def test_model_cannot_book_without_summary(client, clinic, sid, fake):
    """The AI tries confirmed=true immediately. The backend refuses, and the false claim is replaced."""
    fake([reply_with_tools(tool_call("create_appointment", booking_args(clinic, True))),
          reply_text("Great, your appointment has been booked!")])
    data = chat(client, sid, "Yes book it")
    assert "haven't completed a booking" in data["reply"]
    assert client.get("/appointments", headers={"X-Session-ID": sid}).json() == []


def test_model_cannot_confirm_in_same_turn_as_summary(client, clinic, sid, fake):
    fake([reply_with_tools(tool_call("create_appointment", booking_args(clinic, False), "a")),
          reply_with_tools(tool_call("create_appointment", booking_args(clinic, True), "b")),
          reply_text("Done, appointment is booked!")])
    chat(client, sid, "Book a HydraFacial at 10 tomorrow as Sara Khan with Dr. Test One")
    assert client.get("/appointments", headers={"X-Session-ID": sid}).json() == []


def test_vague_reply_is_not_confirmation(client, clinic, sid, fake):
    fake([reply_with_tools(tool_call("create_appointment", booking_args(clinic, False))), reply_text("Confirm?")])
    chat(client, sid, "Book it please, Sara Khan, HydraFacial, tomorrow 10")
    fake([reply_with_tools(tool_call("create_appointment", booking_args(clinic, True))), reply_text("Booked!")])
    chat(client, sid, "Actually, can we change the time?")
    assert client.get("/appointments", headers={"X-Session-ID": sid}).json() == []


def test_changed_details_after_summary_are_rejected(client, clinic, sid, fake):
    fake([reply_with_tools(tool_call("create_appointment", booking_args(clinic, False))), reply_text("Confirm?")])
    chat(client, sid, "Book HydraFacial at 10, Sara Khan, with Dr. Test One")
    changed = booking_args(clinic, True) | {"time": "11:00"}
    fake([reply_with_tools(tool_call("create_appointment", changed)), reply_text("Booked!")])
    chat(client, sid, "yes")
    assert client.get("/appointments", headers={"X-Session-ID": sid}).json() == []


def test_chat_cancel_and_isolation(client, clinic, sid, fake):
    fake([reply_with_tools(tool_call("create_appointment", booking_args(clinic, False))), reply_text("Confirm?")])
    chat(client, sid, "Book HydraFacial at 10 as Sara Khan with Dr. Test One")
    fake([reply_with_tools(tool_call("create_appointment", booking_args(clinic, True))), reply_text("Booked!")])
    chat(client, sid, "yes please")
    appt_id = client.get("/appointments", headers={"X-Session-ID": sid}).json()[0]["id"]

    # A different visitor tries to cancel it through chat
    stranger = str(uuid.uuid4())
    fake([reply_with_tools(tool_call("cancel_appointment", {"appointment_id": appt_id})), reply_text("Not found")])
    other = chat(client, stranger, "cancel appointment")
    assert other["cards"] == []

    # The owner cancels: summary first, then yes
    fake([reply_with_tools(tool_call("cancel_appointment", {"appointment_id": appt_id})), reply_text("Sure?")])
    chat(client, sid, "I need to cancel my appointment")
    fake([reply_with_tools(tool_call("cancel_appointment", {"appointment_id": appt_id, "confirmed": True})),
          reply_text("Cancelled.")])
    chat(client, sid, "yes")
    assert client.get("/appointments", headers={"X-Session-ID": sid}).json() == []


def test_invalid_tool_arguments_handled(client, clinic, sid, fake):
    bad = {"appointment_type": "aesthetic_treatment", "patient_name": "Sara Khan", "date": "not-a-date", "time": "10:00"}
    f = fake([reply_with_tools(tool_call("create_appointment", bad)), reply_text("Sorry, which date?")])
    data = chat(client, sid, "book")
    assert data["reply"] == "Sorry, which date?"
    assert f.seen_tool_results[0]["ok"] is False and "Invalid arguments" in f.seen_tool_results[0]["error"]


def test_session_history_is_persistent_and_separate(client, clinic, sid, fake):
    fake([reply_text("Hello! Welcome to Luméra.")])
    chat(client, sid, "Hi")
    history = client.get("/chat/history", headers={"X-Session-ID": sid}).json()
    assert [m["role"] for m in history] == ["user", "assistant"]
    assert client.get("/chat/history", headers={"X-Session-ID": str(uuid.uuid4())}).json() == []


def test_emergency_message_bypasses_ai(client, clinic, sid, fake):
    fake([])  # AI must not be called
    data = chat(client, sid, "I have severe chest pain")
    assert "emergency" in data["reply"].lower()


def test_groq_failure_is_graceful(client, clinic, sid, monkeypatch):
    import groq

    class Boom:
        chat = SimpleNamespace(completions=SimpleNamespace(create=lambda **k: (_ for _ in ()).throw(
            groq.APIConnectionError(request=SimpleNamespace()))))
    monkeypatch.setattr(receptionist, "get_groq_client", lambda: Boom())
    data = chat(client, sid, "Hello")
    assert "trouble" in data["reply"]


def test_missing_api_key_message(client, clinic, sid, monkeypatch):
    monkeypatch.setattr(receptionist, "get_groq_client", lambda: None)
    assert "not configured" in chat(client, sid, "Hello")["reply"]


def test_rate_limit(client, clinic, sid, monkeypatch):
    from app.utils.rate_limit import chat_limiter
    monkeypatch.setattr(receptionist, "get_groq_client", lambda: None)
    monkeypatch.setattr(chat_limiter, "max_calls", 2)
    client.post("/chat", json={"session_id": sid, "message": "a"})
    client.post("/chat", json={"session_id": sid, "message": "b"})
    assert client.post("/chat", json={"session_id": sid, "message": "c"}).status_code == 429


def test_service_card_not_repeated_every_turn(client, clinic, sid, fake):
    fake([reply_with_tools(tool_call("get_services", {})), reply_text("Here is what we offer.")])
    first = chat(client, sid, "What do you offer?")
    assert [c["type"] for c in first["cards"]] == ["services"]
    f = fake([reply_with_tools(tool_call("get_services", {})), reply_text("Anything else?")])
    second = chat(client, sid, "ok thanks")
    assert second["cards"] == []                       # already on screen: no duplicate box
    assert "already see" in f.seen_tool_results[0]["note"]


def test_services_card_lists_treatments_and_consultations_separately(client, clinic, sid, fake):
    fake([reply_with_tools(tool_call("get_services", {})), reply_text("Here you go.")])
    items = chat(client, sid, "show services")["cards"][0]["items"]
    assert {i["category"] for i in items} == {"aesthetic_treatment", "general_consultation"}
