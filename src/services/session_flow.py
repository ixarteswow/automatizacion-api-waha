from __future__ import annotations

import json
import time
from typing import Any, Mapping

from src.db import db_session
from src.domain import fsm
from src.services.session_scoring import score_session


def advance_on_valid_answer(
    db_path: str,
    telefono: str,
    *,
    answer_key: str,
    answer_value: Any,
    message_ts: int | None = None,
    correlation_id: str | None = None,
) -> int:
    timestamp = message_ts or int(time.time())
    with db_session(db_path) as conn:
        row = conn.execute(
            """
            SELECT estado_actual, respuestas_clean
            FROM sesiones_leads
            WHERE telefono = ?
            """,
            (telefono,),
        ).fetchone()
        if row is None:
            raise ValueError(f"Session not found for telefono={telefono}")

        estado_actual = int(row["estado_actual"])
        if not fsm.is_active_state(estado_actual):
            return estado_actual

        respuestas = _load_json(row["respuestas_clean"])
        respuestas[answer_key] = answer_value

        nuevo_estado = fsm.next_state(estado_actual)
        conn.execute(
            """
            UPDATE sesiones_leads
            SET estado_actual = ?,
                respuestas_clean = ?,
                intentos_fallidos = 0,
                ultimo_mensaje_ts = ?
            WHERE telefono = ?
            """,
            (
                nuevo_estado,
                json.dumps(respuestas, ensure_ascii=True),
                timestamp,
                telefono,
            ),
        )

    if nuevo_estado == fsm.FINAL_STATE:
        score_session(db_path, telefono, finalize=True, correlation_id=correlation_id)

    return nuevo_estado


def finalize_session(
    db_path: str,
    telefono: str,
    *,
    correlation_id: str | None = None,
) -> None:
    with db_session(db_path) as conn:
        row = conn.execute(
            "SELECT estado_actual FROM sesiones_leads WHERE telefono = ?",
            (telefono,),
        ).fetchone()
        if row is None:
            raise ValueError(f"Session not found for telefono={telefono}")
        estado_actual = int(row["estado_actual"])
        if estado_actual != fsm.FINAL_STATE:
            conn.execute(
                "UPDATE sesiones_leads SET estado_actual = ? WHERE telefono = ?",
                (fsm.FINAL_STATE, telefono),
            )

    score_session(db_path, telefono, finalize=True, correlation_id=correlation_id)


def _load_json(raw: Any) -> dict[str, Any]:
    if not raw:
        return {}
    if isinstance(raw, Mapping):
        return dict(raw)
    if isinstance(raw, str):
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError:
            return {}
        if isinstance(parsed, Mapping):
            return dict(parsed)
    return {}
