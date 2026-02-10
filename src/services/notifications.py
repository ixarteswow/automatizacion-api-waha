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

    if label_norm == "GOLD":
        if not config.calendly_url:
            return None, "missing_calendly_url"
        return (
            f"¡Enhorabuena! Tu perfil encaja muy bien. "
            f"Puedes reservar tu visita aquí: {config.calendly_url}",
            None,
        )

    if label_norm == "SILVER":
        agent = config.agent_name or "el agente"
        return (
            f"Gracias. {agent} revisará tu solicitud y se pondrá en contacto lo antes posible.",
            None,
        )

    if label_norm == "RED":
        if not config.red_info_url:
            return None, "missing_red_info_url"
        return (
            "Gracias por tu interés. En este momento no contamos con una opción que encaje "
            "bien con tus necesidades, pero para ayudarte te dejo este enlace con información "
            f"y alternativas disponibles: {config.red_info_url}",
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
