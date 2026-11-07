"""Tool (function) schemas sent to Groq. The model may ask for these; the backend decides what happens."""

_DOCTOR = {
    "doctor_id": {"type": "integer", "description": "Doctor ID from get_doctors."},
    "doctor_name": {"type": "string", "description": "Doctor name (use if the ID is not known)."},
}
_SERVICE = {
    "service_id": {"type": "integer", "description": "Service ID from get_services."},
    "service_name": {"type": "string", "description": "Service name (use if the ID is not known)."},
}


def _tool(name: str, description: str, properties: dict, required: list[str] | None = None) -> dict:
    return {
        "type": "function",
        "function": {
            "name": name,
            "description": description,
            "parameters": {"type": "object", "properties": properties, "required": required or []},
        },
    }


TOOLS = [
    _tool("get_clinic_information",
          "Get the clinic's name, address, phone, email, opening hours and general information.", {}),
    _tool("get_services",
          "List the clinic's active services with description, price and duration. Optionally filter by category.",
          {"category": {"type": "string", "enum": ["aesthetic_treatment", "general_consultation"]}}),
    _tool("get_doctors",
          "List active doctors with specialization, profile and consultation fee. "
          "Pass a service to list only doctors who perform it.", {**_SERVICE}),
    _tool("get_doctor_schedule", "Get a doctor's weekly working hours.", {**_DOCTOR}),
    _tool("check_availability",
          "Get the real free appointment slots for a doctor on a date (YYYY-MM-DD). Never guess availability.",
          {**_DOCTOR, **_SERVICE, "date": {"type": "string", "description": "Date, YYYY-MM-DD."}},
          ["date"]),
    _tool("create_appointment",
          "Book an appointment. FIRST call with confirmed=false: this validates everything and returns a "
          "summary to show the patient. ONLY after the patient replies with a clear yes, call again with the "
          "same details and confirmed=true. The backend rejects confirmed=true without a prior summary "
          "and a patient 'yes'.",
          {
              "appointment_type": {"type": "string", "enum": ["aesthetic_treatment", "general_consultation"]},
              "patient_name": {"type": "string"},
              **_DOCTOR, **_SERVICE,
              "date": {"type": "string", "description": "YYYY-MM-DD"},
              "time": {"type": "string", "description": "24-hour HH:MM"},
              "reason": {"type": "string", "description": "Reason for visit (required for general consultations)."},
              "contact": {"type": "string", "description": "Optional phone or email."},
              "confirmed": {"type": "boolean", "description": "true only after the patient explicitly said yes."},
          },
          ["appointment_type", "patient_name", "date", "time"]),
    _tool("get_patient_appointments",
          "List this visitor's own appointments in the current chat session.",
          {"include_cancelled": {"type": "boolean"}}),
    _tool("reschedule_appointment",
          "Move one of this visitor's appointments. Same two-step rule: confirmed=false first, "
          "confirmed=true only after the patient says yes.",
          {"appointment_id": {"type": "integer"}, "new_date": {"type": "string", "description": "YYYY-MM-DD"},
           "new_time": {"type": "string", "description": "24-hour HH:MM"}, "confirmed": {"type": "boolean"}},
          ["appointment_id", "new_date", "new_time"]),
    _tool("cancel_appointment",
          "Cancel one of this visitor's appointments. Same two-step rule: confirmed=false first, "
          "confirmed=true only after the patient says yes.",
          {"appointment_id": {"type": "integer"}, "confirmed": {"type": "boolean"}},
          ["appointment_id"]),
]
