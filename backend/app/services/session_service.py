"""Persistent conversation sessions and messages (PostgreSQL)."""

import uuid

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import ConversationMessage, ConversationSession


def get_or_create_session(db: Session, session_id: uuid.UUID) -> ConversationSession:
    session = db.get(ConversationSession, session_id)
    if session is not None:
        return session
    session = ConversationSession(id=session_id, state={})
    db.add(session)
    try:
        db.commit()
    except IntegrityError:  # two requests created it at the same moment
        db.rollback()
        session = db.get(ConversationSession, session_id)
        if session is None:
            raise
    return session


def add_message(db: Session, session_id: uuid.UUID, role: str, content: str) -> ConversationMessage:
    message = ConversationMessage(session_id=session_id, role=role, content=content)
    db.add(message)
    db.commit()
    db.refresh(message)
    return message


def get_history(db: Session, session_id: uuid.UUID, limit: int = 20) -> list[ConversationMessage]:
    """Most recent `limit` user/assistant messages, oldest first."""
    rows = db.scalars(
        select(ConversationMessage)
        .where(ConversationMessage.session_id == session_id, ConversationMessage.role.in_(("user", "assistant")))
        .order_by(ConversationMessage.id.desc())
        .limit(limit)
    ).all()
    return list(reversed(rows))


def set_pending(db: Session, session: ConversationSession, pending: dict | None) -> None:
    state = dict(session.state or {})
    if pending is None:
        state.pop("pending", None)
    else:
        state["pending"] = pending
    session.state = state  # new dict object -> SQLAlchemy sees the change
    db.commit()


def user_turn_count(db: Session, session_id: uuid.UUID) -> int:
    return db.scalar(select(func.count()).select_from(ConversationMessage).where(
        ConversationMessage.session_id == session_id, ConversationMessage.role == "user")) or 0


def set_state_value(db: Session, session: ConversationSession, key: str, value) -> None:
    state = dict(session.state or {})
    state[key] = value
    session.state = state
    db.commit()
