"""One chat turn: save message -> emergency check -> AI -> save reply."""

import re
import uuid

from sqlalchemy.orm import Session

from app.agents.receptionist import AgentResult, run_receptionist
from app.services import session_service

EMERGENCY = re.compile(
    r"(chest pain|can'?t breathe|cannot breathe|difficulty breathing|trouble breathing|severe bleeding|"
    r"heavy bleeding|unconscious|passed out|stroke|heart attack|anaphyla|throat (is )?(closing|swelling)|"
    r"overdose|suicid|kill myself|want to die|seizure)", re.IGNORECASE)

EMERGENCY_REPLY = (
    "This sounds like it could be a medical emergency. Please contact your local emergency services or go to "
    "the nearest emergency department right now. I'm not able to provide emergency medical care through chat. "
    "If you or someone with you is in danger, please reach out to emergency services or someone nearby immediately.")


def handle_chat(db: Session, session_id: uuid.UUID, text: str) -> AgentResult:
    session = session_service.get_or_create_session(db, session_id)
    user_message = session_service.add_message(db, session.id, "user", text)  # committed before the AI runs

    if EMERGENCY.search(text):
        result = AgentResult(EMERGENCY_REPLY)
    else:
        history = session_service.get_history(db, session.id, limit=20)
        result = run_receptionist(db, session, user_message, history)

    session_service.add_message(db, session.id, "assistant", result.reply)
    return result
