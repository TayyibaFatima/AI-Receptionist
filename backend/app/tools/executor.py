"""Runs a tool requested by the AI. Validates input, enforces every rule, returns (result, ui_cards).

The model can only *ask*; everything is validated and executed here by normal backend code.
"""

import hashlib
import json
import logging
from dataclasses import dataclass, field
from datetime import date, time
from decimal import Decimal

from pydantic import ValidationError
from sqlalchemy.exc import SQLAlchemyError

from app.models import ConversationMessage, ConversationSession
from app.services import appointment_service as appts
from app.services import availability_service as avail
from app.services import catalog_service as catalog
from app.services import session_service
from app.services.confirmation import verify_confirmation
from app.services.errors import ServiceError
from app.tools import arguments as A

logger = logging.getLogger(__name__)


@dataclass
class ToolContext:
    db: object
    session: ConversationSession
    user_message: ConversationMessage
    appointments_changed: bool = False
    booked_this_turn: bool = False
    cards: list = field(default_factory=list)


# ---------- formatting helpers ----------
def fmt_date(d: date) -> str:
    return d.strftime("%A, %d %B %Y")


def fmt_time(t: time) -> str:
    return t.strftime("%I:%M %p").lstrip("0")


def _money(value, currency: str) -> str | None:
    if value is None:
        return None
    return f"{currency} {Decimal(value):,.0f}"


def _currency(db) -> str:
    info = catalog.get_clinic_info(db)
    return info.currency if info else ""


def _service_dict(s) -> dict:
    return {"id": s.id, "name": s.name, "category": s.category, "description": s.description,
            "price": float(s.price) if s.price is not None else None, "duration_minutes": s.duration_minutes}


def _doctor_dict(d) -> dict:
    return {"id": d.id, "name": d.full_name, "specialization": d.specialization,
            "profile": d.profile_description,
            "consultation_fee": float(d.consultation_fee) if d.consultation_fee is not None else None,
            "services": [s.name for s in d.services if s.is_active]}


REPEAT_WINDOW_TURNS = 5
ALREADY_SHOWN = "The patient can already see this list on screen. Do not repeat it in full; answer briefly."


def _emit_browse_card(ctx, card: dict) -> bool:
    """Add a services/doctors card unless the same one was shown in the last few turns."""
    sig = hashlib.md5(json.dumps(card["items"], sort_keys=True, default=str).encode()).hexdigest()
    turn = session_service.user_turn_count(ctx.db, ctx.session.id)
    shown = dict((ctx.session.state or {}).get("shown_cards", {}))
    last = shown.get(card["type"])
    if last and last["sig"] == sig and turn - last["turn"] < REPEAT_WINDOW_TURNS:
        return False
    shown[card["type"]] = {"sig": sig, "turn": turn}
    session_service.set_state_value(ctx.db, ctx.session, "shown_cards", shown)
    ctx.cards.append(card)
    return True


def _fee_text(plan, currency: str) -> str:
    return _money(plan.fee, currency) or "Not listed"


# ---------- individual tools ----------
def _get_clinic_information(args, ctx):
    info = catalog.get_clinic_info(ctx.db)
    if info is None:
        return {"ok": False, "error": "Clinic information is not available in the database."}
    return {"ok": True, "clinic": {
        "name": info.clinic_name, "address": info.address, "phone": info.phone, "email": info.email,
        "opening_hours": info.opening_hours, "general_information": info.general_info,
        "currency": info.currency}}


def _get_services(args: A.ServicesArgs, ctx):
    services = catalog.list_services(ctx.db, category=args.category)
    if not services:
        return {"ok": False, "error": "No services are listed in the database."}
    items = [_service_dict(s) for s in services]
    currency = _currency(ctx.db)
    shown = _emit_browse_card(ctx, {"type": "services", "currency": currency, "items": items})
    result = {"ok": True, "currency": currency, "services": items}
    if not shown:
        result["note"] = ALREADY_SHOWN
    return result


def _get_doctors(args: A.DoctorsArgs, ctx):
    service_id = None
    if args.service_id is not None or args.service_name:
        service_id = catalog.resolve_service(ctx.db, args.service_id, args.service_name).id
    doctors = catalog.list_doctors(ctx.db, service_id=service_id)
    if not doctors:
        return {"ok": False, "error": "No active doctors are listed for that request."}
    items = [_doctor_dict(d) for d in doctors]
    currency = _currency(ctx.db)
    shown = _emit_browse_card(ctx, {"type": "doctors", "currency": currency, "items": items})
    result = {"ok": True, "currency": currency, "doctors": items}
    if not shown:
        result["note"] = ALREADY_SHOWN
    return result


def _get_doctor_schedule(args: A.DoctorRefArgs, ctx):
    doctor = catalog.resolve_doctor(ctx.db, args.doctor_id, args.doctor_name)
    rows = catalog.get_doctor_schedule(ctx.db, doctor.id)
    if not rows:
        return {"ok": False, "error": f"No working hours are listed for {doctor.full_name}."}
    return {"ok": True, "doctor": doctor.full_name, "schedule": [
        {"day": catalog.DAY_NAMES[r.day_of_week], "from": fmt_time(r.start_time), "to": fmt_time(r.end_time),
         "slot_minutes": r.slot_minutes} for r in rows]}


def _check_availability(args: A.AvailabilityArgs, ctx):
    doctor = catalog.resolve_doctor(ctx.db, args.doctor_id, args.doctor_name)
    service = None
    if args.service_id is not None or args.service_name:
        service = catalog.resolve_service(ctx.db, args.service_id, args.service_name)
    duration = service.duration_minutes if service else None
    slots = avail.get_available_slots(ctx.db, doctor.id, args.day, duration)
    result = {"ok": True, "doctor": doctor.full_name, "doctor_id": doctor.id, "date": args.day.isoformat(),
              "weekday": args.day.strftime("%A"),
              "slots": [{"time": t.strftime("%H:%M"), "display": fmt_time(t)} for t in slots]}
    if slots:
        ctx.cards.append({"type": "slots", "doctor_id": doctor.id, "doctor_name": doctor.full_name,
                          "date": args.day.isoformat(), "date_display": fmt_date(args.day),
                          "slots": result["slots"]})
    else:
        nxt = avail.find_next_available_dates(ctx.db, doctor.id, args.day, duration)
        result["message"] = "No free slots on that date."
        result["next_available_dates"] = [d.isoformat() for d in nxt]
    return result


def _summary_rows(plan, currency):
    treatment_label = "Treatment" if plan.appointment_type == "aesthetic_treatment" else "Consultation"
    rows = [
        {"label": "Patient", "value": plan.patient_name},
        {"label": "Appointment type", "value": appts.TYPE_LABELS[plan.appointment_type]},
        {"label": treatment_label, "value": plan.service.name if plan.service else plan.doctor.specialization},
        {"label": "Doctor", "value": plan.doctor.full_name},
        {"label": "Date", "value": fmt_date(plan.day)},
        {"label": "Time", "value": fmt_time(plan.slot_time)},
        {"label": "Fee", "value": _fee_text(plan, currency)},
    ]
    if plan.reason:
        rows.append({"label": "Reason", "value": plan.reason})
    return rows


def _propose(ctx, action, params, rows, title):
    session_service.set_pending(ctx.db, ctx.session, {
        "action": action, "params": params, "after_message_id": ctx.user_message.id})
    ctx.cards.append({"type": "confirmation", "action": action, "title": title, "rows": rows})
    return {"ok": True, "status": "awaiting_confirmation", "summary": {r["label"]: r["value"] for r in rows},
            "instruction": "Show this summary to the patient and ask: 'Would you like me to confirm this "
                           "appointment?' Do NOT say it is booked/changed/cancelled yet."}


def _create_appointment(args: A.CreateAppointmentArgs, ctx):
    doctor = catalog.resolve_doctor(ctx.db, args.doctor_id, args.doctor_name)
    service_id = None
    if args.service_id is not None or args.service_name:
        service_id = catalog.resolve_service(ctx.db, args.service_id, args.service_name).id
    plan = appts.plan_booking(
        ctx.db, patient_name=args.patient_name, contact=args.contact, appointment_type=args.appointment_type,
        doctor_id=doctor.id, service_id=service_id, day=args.day, slot_time=args.slot_time, reason=args.reason)
    appts.ensure_slot_free(ctx.db, plan)
    params = {"appointment_type": plan.appointment_type, "patient_name": plan.patient_name.lower(),
              "doctor_id": plan.doctor.id, "service_id": plan.service.id if plan.service else None,
              "date": plan.day.isoformat(), "time": plan.slot_time.strftime("%H:%M")}
    currency = _currency(ctx.db)

    if not args.confirmed:
        return _propose(ctx, "create", params, _summary_rows(plan, currency), "Please review your appointment")

    verify_confirmation(ctx.session.state, "create", params, ctx.user_message.id, ctx.user_message.content)
    appt = appts.create_appointment(
        ctx.db, session_id=ctx.session.id, patient_name=plan.patient_name, contact=plan.contact,
        appointment_type=plan.appointment_type, doctor_id=plan.doctor.id, service_id=params["service_id"],
        day=plan.day, slot_time=plan.slot_time, reason=plan.reason, confirmed=True)
    session_service.set_pending(ctx.db, ctx.session, None)
    ctx.appointments_changed = ctx.booked_this_turn = True
    data = appts.appointment_to_dict(appt)
    ctx.cards.append({"type": "booked", "title": "Appointment confirmed", "rows": _summary_rows(plan, currency),
                      "appointment_id": appt.id})
    return {"ok": True, "status": "booked", "appointment_id": appt.id,
            "appointment": _jsonable(data)}


def _get_patient_appointments(args: A.AppointmentsArgs, ctx):
    rows = appts.list_appointments(ctx.db, ctx.session.id, include_cancelled=args.include_cancelled)
    if not rows:
        return {"ok": True, "appointments": [], "message": "There are no appointments in this session."}
    items = [_jsonable(appts.appointment_to_dict(a)) for a in rows]
    for item, a in zip(items, rows):
        item["date_display"] = fmt_date(a.appointment_date)
        item["time_display"] = fmt_time(a.appointment_time)
    ctx.cards.append({"type": "appointments", "items": items})
    return {"ok": True, "appointments": items}


def _reschedule(args: A.RescheduleArgs, ctx):
    appt = appts.get_appointment(ctx.db, args.appointment_id, ctx.session.id)
    plan = appts.check_reschedule(ctx.db, appt, args.new_day, args.new_time)
    params = {"appointment_id": appt.id, "date": args.new_day.isoformat(), "time": args.new_time.strftime("%H:%M")}
    if not args.confirmed:
        rows = [
            {"label": "Appointment", "value": f"#{appt.id} with {appt.doctor.full_name}"},
            {"label": "Current", "value": f"{fmt_date(appt.appointment_date)}, {fmt_time(appt.appointment_time)}"},
            {"label": "New", "value": f"{fmt_date(plan.day)}, {fmt_time(plan.slot_time)}"},
        ]
        return _propose(ctx, "reschedule", params, rows, "Please review the change")
    verify_confirmation(ctx.session.state, "reschedule", params, ctx.user_message.id, ctx.user_message.content)
    updated = appts.reschedule_appointment(ctx.db, appointment_id=appt.id, session_id=ctx.session.id,
                                           new_day=args.new_day, new_time=args.new_time, confirmed=True)
    session_service.set_pending(ctx.db, ctx.session, None)
    ctx.appointments_changed = True
    return {"ok": True, "status": "rescheduled", "appointment": _jsonable(appts.appointment_to_dict(updated))}


def _cancel(args: A.CancelArgs, ctx):
    appt = appts.get_appointment(ctx.db, args.appointment_id, ctx.session.id)
    appts.check_cancel(appt)
    params = {"appointment_id": appt.id}
    if not args.confirmed:
        rows = [
            {"label": "Appointment", "value": f"#{appt.id} with {appt.doctor.full_name}"},
            {"label": "When", "value": f"{fmt_date(appt.appointment_date)}, {fmt_time(appt.appointment_time)}"},
        ]
        return _propose(ctx, "cancel", params, rows, "Cancel this appointment?")
    verify_confirmation(ctx.session.state, "cancel", params, ctx.user_message.id, ctx.user_message.content)
    cancelled = appts.cancel_appointment(ctx.db, appointment_id=appt.id, session_id=ctx.session.id, confirmed=True)
    session_service.set_pending(ctx.db, ctx.session, None)
    ctx.appointments_changed = True
    return {"ok": True, "status": "cancelled", "appointment": _jsonable(appts.appointment_to_dict(cancelled))}


def _jsonable(data: dict) -> dict:
    return json.loads(json.dumps(data, default=str))


REGISTRY = {
    "get_clinic_information": (A.NoArgs, _get_clinic_information),
    "get_services": (A.ServicesArgs, _get_services),
    "get_doctors": (A.DoctorsArgs, _get_doctors),
    "get_doctor_schedule": (A.DoctorRefArgs, _get_doctor_schedule),
    "check_availability": (A.AvailabilityArgs, _check_availability),
    "create_appointment": (A.CreateAppointmentArgs, _create_appointment),
    "get_patient_appointments": (A.AppointmentsArgs, _get_patient_appointments),
    "reschedule_appointment": (A.RescheduleArgs, _reschedule),
    "cancel_appointment": (A.CancelArgs, _cancel),
}


def execute_tool(name: str, raw_arguments, ctx: ToolContext) -> dict:
    """Never raises: every failure becomes {"ok": False, "error": ...} that the AI can explain politely."""
    entry = REGISTRY.get(name)
    if entry is None:
        return {"ok": False, "error": f"Unknown tool '{name}'."}
    model, func = entry
    try:
        data = json.loads(raw_arguments) if isinstance(raw_arguments, str) and raw_arguments.strip() else (
            raw_arguments if isinstance(raw_arguments, dict) else {})
        if not isinstance(data, dict):
            raise ValueError("arguments must be a JSON object")
        # Models sometimes send null for unused optional fields.
        data = {k: v for k, v in data.items() if v is not None and v != ""}
        args = model.model_validate(data)
    except (ValidationError, ValueError) as exc:
        message = "; ".join(f"{'.'.join(map(str, e['loc']))}: {e['msg']}" for e in exc.errors()) \
            if isinstance(exc, ValidationError) else str(exc)
        return {"ok": False, "error": f"Invalid arguments: {message}"}
    try:
        return func(args, ctx)
    except ServiceError as exc:
        ctx.db.rollback()
        return {"ok": False, "error": exc.message, "code": exc.code}
    except SQLAlchemyError:
        logger.exception("Database error in tool %s", name)
        ctx.db.rollback()
        return {"ok": False, "error": "A database error occurred. Please try again or contact the clinic staff."}
    except Exception:  # noqa: BLE001 - last-resort safety net
        logger.exception("Unexpected error in tool %s", name)
        ctx.db.rollback()
        return {"ok": False, "error": "Something went wrong while processing that request."}
