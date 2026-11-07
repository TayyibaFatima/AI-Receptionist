import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas.chat import ChatRequest, ChatResponse, HistoryMessage
from app.services import chat_service, session_service
from app.utils.deps import get_session_id
from app.utils.rate_limit import chat_rate_limit

router = APIRouter(prefix="/chat", tags=["chat"])


@router.post("", response_model=ChatResponse, dependencies=[Depends(chat_rate_limit)])
def chat(body: ChatRequest, db: Session = Depends(get_db)):
    session_id = body.session_id or uuid.uuid4()
    result = chat_service.handle_chat(db, session_id, body.message.strip())
    return ChatResponse(session_id=session_id, reply=result.reply, cards=result.cards,
                        appointments_changed=result.appointments_changed)


@router.get("/history", response_model=list[HistoryMessage])
def history(session_id: uuid.UUID = Depends(get_session_id), db: Session = Depends(get_db)):
    session_service.get_or_create_session(db, session_id)
    return session_service.get_history(db, session_id, limit=100)
