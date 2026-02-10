from __future__ import annotations

import json
from typing import Any, Mapping

from src.config import load_base_settings, load_scoring_settings
from src.db import db_session
from src.domain.lead_profile_builder import build_lead_profile
from src.domain.scoring import ScoreResult, compute_score
from src.logging_utils import log_evento
from src.services.notifications import (
    NotificationConfig,
    build_notification_metadata,
    build_notification_text,
    send_whatsapp_text,
)


def score_session(
    db_path: str,
    telefono: str,
    *,
    finalize: bool = False,
    correlation_id: str | None = None,
) -> ScoreResult:
    scoring_settings = load_scoring_settings()
    with db_session(db_path) as conn:
        row = conn.execute(
            """
            SELECT
                respuestas_clean,
                metadata,
                alquiler_mensual,
                metros_cuadrados,
                scoring
            FROM sesiones_leads
            WHERE telefono = ?
            """,
            (telefono,),
        ).fetchone()
        if row is None:
            raise ValueError(f"Session not found for telefono={telefono}")

        respuestas_clean = row["respuestas_clean"] or "{}"
        respuestas_payload = _load_json(respuestas_clean)
        metadata = _load_json(row["metadata"])

        alquiler_mensual = row["alquiler_mensual"] or scoring_settings.property_rent_eur
        metros_cuadrados = row["metros_cuadrados"] or scoring_settings.property_sqm

        profile = build_lead_profile(
            respuestas_clean,
            alquiler_mensual=alquiler_mensual,
            metros_cuadrados=metros_cuadrados,
        )
        result = compute_score(profile)

        metadata["scoring"] = {
            "label": result.label,
            "total": result.total,
            "killers": list(result.killers),
            "breakdown": {
                "ratio_esfuerzo": result.breakdown.ratio_esfuerzo,
                "estabilidad": result.breakdown.estabilidad,
                "mascotas": result.breakdown.mascotas,
                "densidad": result.breakdown.densidad,
                "sector": result.breakdown.sector,
                "fumador": result.breakdown.fumador,
            },
        }

        _persist_scoring(
            conn,
            telefono,
            result,
            metadata,
            alquiler_mensual,
            metros_cuadrados,
            finalize=finalize,
        )
        log_evento(
            conn,
            "scoring_calculated",
            telefono=telefono,
            payload={
                "input_keys": sorted(respuestas_payload.keys()),
                "label": result.label,
                "total": result.total,
                "killers": list(result.killers),
                "breakdown": {
                    "ratio_esfuerzo": result.breakdown.ratio_esfuerzo,
                    "estabilidad": result.breakdown.estabilidad,
                    "mascotas": result.breakdown.mascotas,
                    "densidad": result.breakdown.densidad,
                    "sector": result.breakdown.sector,
                    "fumador": result.breakdown.fumador,
                },
                "finalize": finalize,
            },
            correlation_id=correlation_id,
        )

    if finalize:
        _maybe_send_notification(db_path, telefono, result, correlation_id=correlation_id)

    return result


def _maybe_send_notification(
    db_path: str,
    telefono: str,
    result: ScoreResult,
    *,
    correlation_id: str | None = None,
) -> None:
    settings = load_base_settings()
    config = NotificationConfig(
        waha_base_url=settings.waha_base_url,
        waha_api_key=settings.waha_api_key,
        waha_session=settings.waha_session,
        agent_name=settings.agent_name,
        calendly_url=settings.calendly_url,
        red_info_url=settings.red_info_url,
    )

    with db_session(db_path) as conn:
        row = conn.execute(
            "SELECT metadata FROM sesiones_leads WHERE telefono = ?",
            (telefono,),
        ).fetchone()
        if row is None:
            return
        metadata = _load_json(row["metadata"])
        notif = metadata.get("notification")
        if isinstance(notif, dict) and notif.get("sent"):
            return

    text, skipped_reason = build_notification_text(result.label, config)
    if text is None:
        _update_notification(
            db_path,
            telefono,
            build_notification_metadata(
                sent=False, label=result.label, skipped_reason=skipped_reason
            ),
            event_type="notification_skipped",
            correlation_id=correlation_id,
        )
        return

    try:
        send_whatsapp_text(telefono, text, config=config)
    except Exception as exc:  # pragma: no cover - network error surface
        _update_notification(
            db_path,
            telefono,
            build_notification_metadata(
                sent=False, label=result.label, error=str(exc)
            ),
            event_type="notification_failed",
            correlation_id=correlation_id,
        )
        return

    _update_notification(
        db_path,
        telefono,
        build_notification_metadata(sent=True, label=result.label),
        event_type="notification_sent",
        correlation_id=correlation_id,
    )


def _update_notification(
    db_path: str,
    telefono: str,
    payload: dict[str, Any],
    *,
    event_type: str,
    correlation_id: str | None = None,
) -> None:
    with db_session(db_path) as conn:
        row = conn.execute(
            "SELECT metadata FROM sesiones_leads WHERE telefono = ?",
            (telefono,),
        ).fetchone()
        if row is None:
            return
        metadata = _load_json(row["metadata"])
        metadata["notification"] = payload
        conn.execute(
            "UPDATE sesiones_leads SET metadata = ? WHERE telefono = ?",
            (json.dumps(metadata, ensure_ascii=True), telefono),
        )
        log_evento(
            conn,
            event_type,
            telefono=telefono,
            payload=payload,
            correlation_id=correlation_id,
        )


def _persist_scoring(
    conn,
    telefono: str,
    result: ScoreResult,
    metadata: Mapping[str, Any],
    alquiler_mensual: float,
    metros_cuadrados: float,
    *,
    finalize: bool,
) -> None:
    if finalize:
        conn.execute(
            """
            UPDATE sesiones_leads
            SET scoring = ?,
                metadata = ?,
                alquiler_mensual = ?,
                metros_cuadrados = ?,
                finalizado_en = COALESCE(finalizado_en, strftime('%s','now'))
            WHERE telefono = ?
            """,
            (
                result.total,
                json.dumps(metadata, ensure_ascii=True),
                alquiler_mensual,
                metros_cuadrados,
                telefono,
            ),
        )
        return

    conn.execute(
        """
        UPDATE sesiones_leads
        SET scoring = ?,
            metadata = ?,
            alquiler_mensual = ?,
            metros_cuadrados = ?
        WHERE telefono = ?
        """,
        (
            result.total,
            json.dumps(metadata, ensure_ascii=True),
            alquiler_mensual,
            metros_cuadrados,
            telefono,
        ),
    )


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
