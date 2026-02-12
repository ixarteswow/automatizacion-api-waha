from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any

import httpx

from src.utils.phone import to_chat_id

@dataclass(frozen=True)
class NotificationConfig:
    waha_base_url: str
    waha_api_key: str | None
    waha_session: str
    agent_name: str | None
    calendly_url: str | None
    red_info_url: str | None


def build_notification_text(label: str, config: NotificationConfig) -> tuple[str | None, str | None]:
    label_norm = label.strip().upper()
    agent = config.agent_name or "el agente"

    if label_norm == "GOLD":
        if not config.calendly_url:
            return None, "missing_calendly_url"
        return (
            f"🏆 ¡Excelente noticia! Tu perfil cumple todos los requisitos. "
            f"{agent} te invita a reservar una visita al inmueble directamente "
            f"en el siguiente enlace:\n\n"
            f"📅 {config.calendly_url}\n\n"
            f"¡Te esperamos!",
            None,
        )

    if label_norm == "SILVER":
        return (
            f"✅ Gracias por completar la encuesta. Tu perfil es interesante y "
            f"nos gustaría conocerte mejor. {agent} revisará tu solicitud "
            f"personalmente y te contactará en las próximas horas para los "
            f"siguientes pasos.\n\n"
            f"¡Estate atento/a!",
            None,
        )

    if label_norm == "RED":
        if not config.red_info_url:
            return None, "missing_red_info_url"
        return (
            f"Gracias por tu tiempo y tu interés. Tras valorar tu perfil, "
            f"en este momento no disponemos de una opción que encaje bien "
            f"con tus necesidades actuales.\n\n"
            f"Te dejamos este enlace con información y alternativas "
            f"que podrían interesarte:\n"
            f"🔗 {config.red_info_url}\n\n"
            f"Te deseamos mucha suerte.",
            None,
        )

    return None, "unknown_label"


def send_whatsapp_text(
    chat_id: str,
    text: str,
    *,
    config: NotificationConfig,
    timeout_seconds: float = 8.0,
) -> None:
    url = config.waha_base_url.rstrip("/") + "/api/sendText"
    headers: dict[str, str] = {}
    if config.waha_api_key:
        headers["X-API-KEY"] = config.waha_api_key

    normalized_chat_id = to_chat_id(chat_id) or chat_id

    payload = {
        "session": config.waha_session,
        "chatId": normalized_chat_id,
        "text": text,
    }

    with httpx.Client(timeout=timeout_seconds) as client:
        response = client.post(url, json=payload, headers=headers)
        response.raise_for_status()


def build_notification_metadata(
    *,
    sent: bool,
    label: str,
    error: str | None = None,
    skipped_reason: str | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "sent": sent,
        "label": label,
        "sent_at": int(time.time()) if sent else None,
    }
    if error:
        payload["error"] = error
    if skipped_reason:
        payload["skipped_reason"] = skipped_reason
    return payload
