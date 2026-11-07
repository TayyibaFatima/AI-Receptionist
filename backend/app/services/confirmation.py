"""Backend-enforced confirmation.

Flow: (1) the tool is called with confirmed=false -> we validate everything and store a PENDING
action in the session. (2) The patient replies. (3) The tool is called with confirmed=true -> we only
proceed if the pending action matches exactly, the patient has sent a NEW message since the summary,
and that message is a clear "yes". The AI model cannot bypass any of this.
"""

import re

from app.services.errors import ConfirmationRequiredError

_AFFIRM = re.compile(
    r"\b(yes|yeah|yep|yup|sure|ok|okay|confirm|confirmed|go ahead|please do|book it|proceed|correct|"
    r"that works|sounds good|do it|absolutely|definitely)\b",
    re.IGNORECASE,
)
_NEGATE = re.compile(
    r"\b(no|nope|nah|don'?t|do not|not|wait|stop|change|instead|actually|different|except|but)\b",
    re.IGNORECASE,
)


def is_affirmative(text: str) -> bool:
    return bool(_AFFIRM.search(text)) and not _NEGATE.search(text)


def verify_confirmation(session_state: dict | None, action: str, params: dict,
                        latest_user_message_id: int, latest_user_text: str) -> None:
    pending = (session_state or {}).get("pending")
    if not pending or pending.get("action") != action or pending.get("params") != params:
        raise ConfirmationRequiredError(
            "No matching summary has been shown to the patient. Call this tool with confirmed=false first, "
            "show the summary, and wait for the patient's explicit yes."
        )
    if latest_user_message_id <= pending.get("after_message_id", 0):
        raise ConfirmationRequiredError(
            "The patient has not replied since the summary was shown. Ask: "
            "'Would you like me to confirm this appointment?' and wait."
        )
    if not is_affirmative(latest_user_text):
        raise ConfirmationRequiredError(
            "The patient's latest message is not a clear confirmation. Do not proceed; ask again or "
            "update the details."
        )
