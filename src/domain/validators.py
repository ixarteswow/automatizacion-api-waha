from __future__ import annotations

import re


_BOOL_YES = re.compile(
    r"^(s[ií]|yes|si|claro|por supuesto|afirmativo|1|true)$", re.IGNORECASE
)
_BOOL_NO = re.compile(
    r"^(no|nop|negativo|0|false)$", re.IGNORECASE
)
_NUMBER = re.compile(r"\d")


def validate_answer(text: str, validation_type: str) -> tuple[bool, str | None]:
    """Validate an answer against the expected type.

    Returns (is_valid, reprompt_message).
    If is_valid is True, reprompt_message is None.
    """
    cleaned = text.strip()
    if not cleaned:
        return False, "No he recibido una respuesta. ¿Podrías responder de nuevo?"

    if validation_type == "bool":
        if _BOOL_YES.match(cleaned) or _BOOL_NO.match(cleaned):
            return True, None
        return False, "Necesito una respuesta de tipo sí o no. ¿Podrías confirmar?"

    if validation_type == "number":
        if _NUMBER.search(cleaned):
            return True, None
        return False, "Necesito un valor numérico en tu respuesta. ¿Podrías indicarlo?"

    # validation_type == "text" → any non-empty text is valid
    return True, None
