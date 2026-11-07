"""The AI receptionist: a Groq tool-calling loop. The model asks for tools; the backend executes them."""

import json
import logging
import re
from dataclasses import dataclass, field

import groq
from groq import Groq
from sqlalchemy.orm import Session

from app.agents.prompts import build_system_prompt
from app.config import get_settings
from app.models import ConversationMessage, ConversationSession
from app.services import availability_service as avail
from app.services import session_service
from app.tools.definitions import TOOLS
from app.tools.executor import ToolContext, execute_tool

logger = logging.getLogger(__name__)
MAX_TOOL_ROUNDS = 6

FALLBACK = ("I'm sorry, I'm having trouble right now. Please try again in a moment, "
            "or contact the clinic staff directly.")
NOT_CONFIGURED = ("The receptionist's AI service is not configured yet (missing GROQ_API_KEY or GROQ_MODEL). "
                  "Please contact the clinic staff.")
_FALSE_BOOKING = re.compile(
    r"(appointment (is|has been|was) (now )?(booked|confirmed|scheduled)|i('ve| have) (booked|confirmed|scheduled)|"
    r"you('re| are) (all set|booked))", re.IGNORECASE)
NOT_BOOKED = ("I haven't completed a booking yet. Let me confirm the details with you first — "
              "would you like me to prepare the appointment summary?")


@dataclass
class AgentResult:
    reply: str
    cards: list = field(default_factory=list)
    appointments_changed: bool = False


def get_groq_client():
    """Separate function so tests can replace it with a fake."""
    settings = get_settings()
    if not settings.groq_api_key or not settings.groq_model:
        return None
    return Groq(api_key=settings.groq_api_key, timeout=30.0, max_retries=2)


def _assistant_tool_message(message) -> dict:
    return {
        "role": "assistant",
        "content": message.content or "",
        "tool_calls": [
            {"id": tc.id, "type": "function",
             "function": {"name": tc.function.name, "arguments": tc.function.arguments or "{}"}}
            for tc in message.tool_calls
        ],
    }


def run_receptionist(db: Session, session: ConversationSession, user_message: ConversationMessage,
                     history: list[ConversationMessage]) -> AgentResult:
    settings = get_settings()
    client = get_groq_client()
    if client is None:
        return AgentResult(NOT_CONFIGURED)

    messages = [{"role": "system", "content": build_system_prompt(settings.clinic_name, avail.clinic_now())}]
    messages += [{"role": m.role, "content": m.content} for m in history]

    ctx = ToolContext(db=db, session=session, user_message=user_message)
    bad_request_retries = 0
    reply = ""

    for _ in range(MAX_TOOL_ROUNDS):
        try:
            response = client.chat.completions.create(
                model=settings.groq_model, messages=messages, tools=TOOLS, tool_choice="auto",
                temperature=0.3, max_tokens=700)
        except groq.RateLimitError:
            logger.warning("Groq rate limit")
            return AgentResult("I'm receiving a lot of requests right now. Please try again in a minute.")
        except groq.BadRequestError:
            # Typically a malformed tool call produced by the model; retry once.
            logger.exception("Groq bad request")
            bad_request_retries += 1
            if bad_request_retries > 1:
                return AgentResult(FALLBACK, ctx.cards, ctx.appointments_changed)
            continue
        except (groq.APIConnectionError, groq.APITimeoutError, groq.APIStatusError):
            logger.exception("Groq API error")
            return AgentResult(FALLBACK, ctx.cards, ctx.appointments_changed)
        except Exception:  # noqa: BLE001
            logger.exception("Unexpected Groq error")
            return AgentResult(FALLBACK, ctx.cards, ctx.appointments_changed)

        if not response.choices:
            return AgentResult(FALLBACK, ctx.cards, ctx.appointments_changed)
        message = response.choices[0].message

        if getattr(message, "tool_calls", None):
            messages.append(_assistant_tool_message(message))
            for call in message.tool_calls:
                result = execute_tool(call.function.name, call.function.arguments, ctx)
                messages.append({"role": "tool", "tool_call_id": call.id,
                                 "content": json.dumps(result, default=str)})
            continue

        reply = (message.content or "").strip()
        break

    if not reply:
        return AgentResult(FALLBACK, ctx.cards, ctx.appointments_changed)

    # Safety net: never let the AI claim a booking that the database did not make.
    if _FALSE_BOOKING.search(reply) and not ctx.booked_this_turn:
        reply = NOT_BOOKED
    return AgentResult(reply, ctx.cards, ctx.appointments_changed)
