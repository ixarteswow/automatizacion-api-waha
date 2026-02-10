from __future__ import annotations

import re

_DIGITS_RE = re.compile(r"\D+")


def to_chat_id(value: str | None) -> str | None:
    if not value:
        return value
    raw = value.strip()
    if not raw:
        return value
    if "@" in raw:
        if raw.endswith("@s.whatsapp.net"):
            return raw.replace("@s.whatsapp.net", "@c.us")
        return raw
    digits = _DIGITS_RE.sub("", raw)
    if not digits:
        return raw
    if digits.startswith("00") and len(digits) > 4:
        digits = digits[2:]
    return f"{digits}@c.us"
