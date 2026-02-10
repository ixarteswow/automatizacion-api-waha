from __future__ import annotations

import json
import re
import time
from dataclasses import dataclass
from typing import Any, Iterable

from src.config import load_settings
from src.db import db_session
from src.domain import fsm
from src.domain.questions import QUESTIONS_BY_ID
from src.logging_utils import log_evento
from src.services.notifications import NotificationConfig, send_whatsapp_text
from src.utils.phone import to_chat_id

_DIGITS_RE = re.compile(r"\D+")


@dataclass(frozen=True)
class LeadCreateResult:
    status: str
    telefono: str | None = None
    estado: int | None = None
    question_sent: bool = False
    reason: str | None = None


def create_lead_session(
    db_path: str,
    *,
    nombre: str,
    telefono: str,
    origen: str | None = None,
    metadata: dict[str, Any] | None = None,
    message_id: str | None = None,
) -> LeadCreateResult:
    nombre_clean = nombre.strip() if isinstance(nombre, str) else ""
    telefono_clean = telefono.strip() if isinstance(telefono, str) else ""
    if not nombre_clean or not telefono_clean:
        return LeadCreateResult(status="bad_request", reason="missing_nombre_or_telefono")

    telefono_raw, telefono_e164, telefono_chat_id, candidates = _normalize_phone_candidates(
        telefono_clean
    )
    telefono_store = telefono_chat_id or telefono_e164 or telefono_raw
    if not telefono_store:
        return LeadCreateResult(status="bad_request", reason="invalid_telefono")

    origen_clean = (origen or "Idealista").strip() or "Idealista"
    metadata_payload: dict[str, Any] = dict(metadata or {})
    lead_payload = {
        "nombre": nombre_clean,
        "telefono_raw": telefono_raw,
        "telefono_e164": telefono_e164,
        "telefono_chat_id": telefono_chat_id,
        "origen": origen_clean,
        "message_id": message_id,
    }
    metadata_payload["lead"] = lead_payload

    now = int(time.time())
    with db_session(db_path) as conn:
        row = _find_existing_session(conn, candidates)
        if row is not None:
            if row["nombre"] is None and nombre_clean:
                conn.execute(
                    "UPDATE sesiones_leads SET nombre = ? WHERE telefono = ?",
                    (nombre_clean, row["telefono"]),
                )
            log_evento(
                conn,
                "lead_exists",
                telefono=row["telefono"],
                payload={"candidates": candidates, "nombre": nombre_clean},
                correlation_id=message_id,
            )
            return LeadCreateResult(
                status="exists",
                telefono=row["telefono"],
                estado=int(row["estado_actual"]),
                reason="already_exists",
            )

        conn.execute(
            """
            INSERT INTO sesiones_leads (
                telefono,
                nombre,
                origen,
                estado_actual,
                respuestas_clean,
                intentos_fallidos,
                ultimo_mensaje_ts,
                metadata
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                telefono_store,
                nombre_clean,
                origen_clean.lower(),
                fsm.MIN_STATE,
                "{}",
                0,
                now,
                json.dumps(metadata_payload, ensure_ascii=True),
            ),
        )
        log_evento(
            conn,
            "lead_created",
            telefono=telefono_store,
            payload=lead_payload,
            correlation_id=message_id,
        )

    question = QUESTIONS_BY_ID.get(fsm.MIN_STATE)
    if question is None:
        return LeadCreateResult(
            status="created",
            telefono=telefono_store,
            estado=fsm.MIN_STATE,
            question_sent=False,
            reason="missing_question",
        )

    try:
        _send_first_question(telefono_store, question.text)
    except Exception as exc:  # pragma: no cover - network errors
        _log_question_event(
            db_path,
            telefono_store,
            "lead_question_failed",
            {"error": str(exc)},
            correlation_id=message_id,
        )
        return LeadCreateResult(
            status="created",
            telefono=telefono_store,
            estado=fsm.MIN_STATE,
            question_sent=False,
            reason=str(exc),
        )

    _log_question_event(
        db_path,
        telefono_store,
        "lead_question_sent",
        {"question_id": question.id},
        correlation_id=message_id,
    )
    return LeadCreateResult(
        status="created",
        telefono=telefono_store,
        estado=fsm.MIN_STATE,
        question_sent=True,
    )


def _normalize_phone_candidates(raw: str) -> tuple[str, str | None, str | None, list[str]]:
    raw_clean = raw.strip()
    if "@" in raw_clean:
        chat_id = to_chat_id(raw_clean)
        candidates = [raw_clean]
        if chat_id and chat_id not in candidates:
            candidates.insert(0, chat_id)
        return raw_clean, raw_clean, chat_id, candidates

    digits = _DIGITS_RE.sub("", raw_clean)
    candidates: list[str] = []

    telefono_e164 = _to_e164(raw_clean, digits)
    telefono_chat_id = to_chat_id(telefono_e164 or raw_clean)
    for value in (telefono_chat_id, telefono_e164, raw_clean, digits):
        if value and value not in candidates:
            candidates.append(value)

    return raw_clean, telefono_e164, telefono_chat_id, candidates


def _to_e164(raw_clean: str, digits: str) -> str | None:
    if not digits:
        return None
    if raw_clean.startswith("+"):
        return f"+{digits}"
    if digits.startswith("00") and len(digits) > 4:
        digits = digits[2:]
    if digits.startswith("34") and len(digits) >= 11:
        return f"+34{digits[2:]}"
    if len(digits) == 9:
        return f"+34{digits}"
    if 10 <= len(digits) <= 15:
        return f"+{digits}"
    return None


def _find_existing_session(conn, candidates: Iterable[str]):
    candidates_list = [c for c in candidates if c]
    if not candidates_list:
        return None
    placeholders = ",".join("?" for _ in candidates_list)
    query = f"""
        SELECT telefono, estado_actual, nombre
        FROM sesiones_leads
        WHERE telefono IN ({placeholders})
        LIMIT 1
    """
    return conn.execute(query, tuple(candidates_list)).fetchone()


def _send_first_question(telefono: str, text: str) -> None:
    settings = load_settings()
    config = NotificationConfig(
        waha_base_url=settings.waha_base_url,
        waha_api_key=settings.waha_api_key,
        waha_session=settings.waha_session,
        agent_name=settings.agent_name,
        calendly_url=settings.calendly_url,
        red_info_url=settings.red_info_url,
    )
    send_whatsapp_text(telefono, text, config=config)


def _log_question_event(
    db_path: str,
    telefono: str,
    event_type: str,
    payload: dict[str, Any],
    *,
    correlation_id: str | None = None,
) -> None:
    with db_session(db_path) as conn:
        log_evento(
            conn,
            event_type,
            telefono=telefono,
            payload=payload,
            correlation_id=correlation_id,
        )
