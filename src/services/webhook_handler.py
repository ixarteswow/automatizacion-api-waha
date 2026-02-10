from __future__ import annotations

import time
from dataclasses import dataclass

import os

from src.config import load_base_settings
from src.db import db_session
from src.domain import fsm
from src.domain.questions import QUESTIONS_BY_ID
from src.logging_utils import log_evento
from src.services.notifications import NotificationConfig, send_whatsapp_text
from src.services.session_flow import advance_on_valid_answer
from src.utils.phone import to_chat_id
from src.utils.time import normalize_ts


@dataclass(frozen=True)
class WebhookResult:
    status: str
    state: int | None = None
    reason: str | None = None


def handle_inbound_message(
    db_path: str,
    *,
    message_id: str,
    telefono: str,
    text: str,
    received_ts: int | None = None,
) -> WebhookResult:
    if received_ts:
        timestamp = int(normalize_ts(received_ts))
    else:
        timestamp = int(time.time())
    telefono_raw = telefono
    telefono_normalized = to_chat_id(telefono) or telefono
    telefono = telefono_normalized

    with db_session(db_path) as conn:
        session = _find_session(conn, telefono_normalized, telefono_raw)

        if session is None:
            return WebhookResult(status="unknown")

        telefono = session["telefono"]
        try:
            conn.execute(
                "INSERT INTO mensajes_procesados (waha_message_id, telefono) VALUES (?, ?)",
                (message_id, telefono),
            )
        except Exception:
            duplicate = conn.execute(
                "SELECT 1 FROM mensajes_procesados WHERE waha_message_id = ?",
                (message_id,),
            ).fetchone()
            if duplicate:
                return WebhookResult(status="duplicate")
            raise

        estado_actual = int(session["estado_actual"])

    if fsm.is_terminal_state(estado_actual):
        return WebhookResult(status="terminal", state=estado_actual)

    if not fsm.is_active_state(estado_actual):
        return WebhookResult(status="inactive", state=estado_actual)

    question = QUESTIONS_BY_ID.get(estado_actual)
    if question is None:
        return WebhookResult(status="error", state=estado_actual, reason="missing_question")

    new_state = advance_on_valid_answer(
        db_path,
        telefono,
        answer_key=question.key,
        answer_value=text,
        message_ts=timestamp,
        correlation_id=message_id,
    )

    _maybe_send_next_question(
        db_path,
        telefono,
        new_state=new_state,
        correlation_id=message_id,
    )

    return WebhookResult(status="ok", state=new_state)


def _maybe_send_next_question(
    db_path: str,
    telefono: str,
    *,
    new_state: int,
    correlation_id: str | None,
) -> None:
    if os.getenv("DISABLE_OUTBOUND_MESSAGES") == "1":
        return
    if not fsm.is_active_state(new_state):
        return
    question = QUESTIONS_BY_ID.get(new_state)
    if question is None:
        _log_event(
            db_path,
            "lead_question_missing",
            telefono,
            {"question_id": new_state},
            correlation_id=correlation_id,
        )
        return

    settings = load_base_settings()
    config = NotificationConfig(
        waha_base_url=settings.waha_base_url,
        waha_api_key=settings.waha_api_key,
        waha_session=settings.waha_session,
        agent_name=settings.agent_name,
        calendly_url=settings.calendly_url,
        red_info_url=settings.red_info_url,
    )
    try:
        send_whatsapp_text(telefono, question.text, config=config)
    except Exception as exc:  # pragma: no cover - network error
        _log_event(
            db_path,
            "lead_question_failed",
            telefono,
            {"question_id": question.id, "error": str(exc)},
            correlation_id=correlation_id,
        )
        return

    _log_event(
        db_path,
        "lead_question_sent",
        telefono,
        {"question_id": question.id},
        correlation_id=correlation_id,
    )


def _log_event(
    db_path: str,
    event_type: str,
    telefono: str,
    payload: dict,
    *,
    correlation_id: str | None,
) -> None:
    with db_session(db_path) as conn:
        log_evento(
            conn,
            event_type,
            telefono=telefono,
            payload=payload,
            correlation_id=correlation_id,
        )


def _find_session(conn, *candidates: str) -> Any:
    values = [value for value in candidates if value]
    if not values:
        return None
    placeholders = ",".join("?" for _ in values)
    query = f"""
        SELECT telefono, estado_actual
        FROM sesiones_leads
        WHERE telefono IN ({placeholders})
        LIMIT 1
    """
    return conn.execute(query, tuple(values)).fetchone()
