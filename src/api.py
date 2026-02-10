from __future__ import annotations

import json
import os
from typing import Any

from fastapi import Depends, FastAPI, Header, HTTPException, Query
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, Field

from src.config import load_base_settings
from src.services.export_service import export_table_rows, list_export_tables
from src.services.lead_intake import create_lead_session
from src.services.webhook_handler import handle_inbound_message

app = FastAPI()
templates = Jinja2Templates(directory="src/templates")
app.mount("/static", StaticFiles(directory="src/static"), name="static")


class LeadCreateRequest(BaseModel):
    nombre: str = Field(min_length=1)
    telefono: str = Field(min_length=6)
    origen: str = Field(default="Idealista")
    message_id: str | None = None
    metadata: dict[str, Any] | None = None


@app.post("/waha/message")
def waha_message(payload: dict[str, Any]):
    if os.getenv("LOG_WEBHOOK_PAYLOAD") == "1":
        try:
            print(json.dumps(payload, ensure_ascii=False))
        except (TypeError, ValueError):
            print(str(payload))
    message_id, telefono, text, received_ts = _extract_message(payload)
    if not text:
        return {"status": "ignored", "reason": "non_text_message"}
    if not message_id or not telefono:
        return {"status": "bad_request", "reason": "missing_message_id_or_telefono"}

    settings = load_base_settings()
    result = handle_inbound_message(
        settings.db_path,
        message_id=message_id,
        telefono=telefono,
        text=text,
        received_ts=received_ts,
    )

    return {"status": result.status, "state": result.state, "reason": result.reason}


@app.post("/leads")
def create_lead(payload: LeadCreateRequest):
    settings = load_base_settings()
    result = create_lead_session(
        settings.db_path,
        nombre=payload.nombre,
        telefono=payload.telefono,
        origen=payload.origen,
        metadata=payload.metadata,
        message_id=payload.message_id,
    )
    if result.status == "bad_request":
        raise HTTPException(status_code=400, detail=result.reason or "invalid_payload")
    return {
        "status": result.status,
        "telefono": result.telefono,
        "estado": result.estado,
        "question_sent": result.question_sent,
        "reason": result.reason,
    }


def _require_export_api_key(
    x_api_key: str | None = Header(default=None, alias="X-API-KEY"),
) -> None:
    settings = load_base_settings()
    expected = settings.export_api_key
    if not expected:
        raise HTTPException(status_code=500, detail="export_api_key_not_configured")
    if x_api_key != expected:
        raise HTTPException(status_code=401, detail="invalid_api_key")


@app.get("/export/{table}")
def export_table(
    table: str,
    updated_since: int | None = Query(default=None, ge=0),
    limit: int = Query(default=200, ge=1, le=1000),
    cursor: str | None = None,
    _auth: None = Depends(_require_export_api_key),
):
    settings = load_base_settings()
    try:
        result = export_table_rows(
            settings.db_path,
            table,
            updated_since=updated_since,
            limit=limit,
            cursor=cursor,
        )
    except ValueError as exc:
        if str(exc) == "unknown_table":
            raise HTTPException(status_code=404, detail="unknown_table") from exc
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return {
        "table": result.table,
        "count": len(result.rows),
        "rows": result.rows,
        "next_cursor": result.next_cursor,
        "has_more": result.next_cursor is not None,
        "available_tables": list_export_tables(),
    }


def _extract_message(
    payload: dict[str, Any]
) -> tuple[str | None, str | None, str | None, int | None]:
    data = _coerce_mapping(payload.get("data")) if isinstance(payload, dict) else {}
    body = _coerce_mapping(payload.get("body")) if isinstance(payload, dict) else {}
    payload_map = (
        _coerce_mapping(payload.get("payload")) if isinstance(payload, dict) else {}
    )
    body_payload = _coerce_mapping(body.get("payload"))
    body_data = _coerce_mapping(body.get("data"))
    data_payload = _coerce_mapping(data.get("payload"))
    nested_payloads = [
        _coerce_mapping(payload_map.get("_data")),
        _coerce_mapping(body_payload.get("_data")),
        _coerce_mapping(data_payload.get("_data")),
    ]

    candidates = list(
        (
            payload,
            data,
            body,
            payload_map,
            body_payload,
            body_data,
            data_payload,
        )
    )
    candidates.extend(nested_payloads)

    event = _first_str(*(_candidate_get(c, "event") for c in candidates))
    if event and not event.startswith("message"):
        return None, None, None, _first_int(
            payload.get("timestamp"), data.get("timestamp"), body.get("timestamp")
        )

    from_me = _first_bool(*(_candidate_get(c, "fromMe") for c in candidates))
    if from_me is True:
        return None, None, None, _first_int(
            payload.get("timestamp"), data.get("timestamp"), body.get("timestamp")
        )

    message_id = _first_str(
        *(_candidate_get(c, "id") for c in candidates),
        *(_candidate_get(c, "messageId") for c in candidates),
        *(_candidate_get(c, "message_id") for c in candidates),
        *(_candidate_get(c, "msgId") for c in candidates),
        _nested_id(*(_candidate_get(c, "key") for c in candidates)),
    )

    telefono = _first_str(
        _nested_remote_jid(*(_candidate_get(c, "key") for c in candidates)),
        *(_candidate_get(c, "chatId") for c in candidates),
        *(_candidate_get(c, "from") for c in candidates),
        *(_candidate_get(c, "phone") for c in candidates),
        *(_candidate_get(c, "telefono") for c in candidates),
    )

    conversation_text = _extract_conversation_text(candidates)
    text = _first_str(
        *(_candidate_get(c, "text") for c in candidates),
        *(_candidate_get(c, "body") for c in candidates),
        *(_candidate_get(c, "message") for c in candidates),
        *(_candidate_get(c, "content") for c in candidates),
        conversation_text,
    )

    received_ts = _first_int(
        payload.get("timestamp"),
        data.get("timestamp"),
        body.get("timestamp"),
    )
    return message_id, telefono, text, received_ts


def _coerce_mapping(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    return {}


def _first_str(*values: Any) -> str | None:
    for value in values:
        if value is None:
            continue
        if isinstance(value, str):
            text = value.strip()
            if text:
                return text
        if isinstance(value, (int, float)):
            text = str(value).strip()
            if text:
                return text
    return None


def _first_int(*values: Any) -> int | None:
    for value in values:
        if value is None:
            continue
        try:
            return int(value)
        except (TypeError, ValueError):
            continue
    return None


def _first_bool(*values: Any) -> bool | None:
    for value in values:
        if value is None:
            continue
        if isinstance(value, bool):
            return value
        if isinstance(value, (int, float)):
            return bool(value)
        if isinstance(value, str):
            lowered = value.strip().lower()
            if lowered in {"true", "1", "yes", "y"}:
                return True
            if lowered in {"false", "0", "no", "n"}:
                return False
    return None


def _candidate_get(candidate: Any, key: str) -> Any:
    if isinstance(candidate, dict):
        return candidate.get(key)
    return None


def _nested_id(*values: Any) -> str | None:
    for value in values:
        if isinstance(value, dict):
            nested = value.get("id") or value.get("messageId")
            if nested:
                return _first_str(nested)
    return None


def _nested_remote_jid(*values: Any) -> str | None:
    for value in values:
        if isinstance(value, dict):
            nested = value.get("remoteJidAlt") or value.get("remoteJid")
            if nested:
                return _first_str(nested)
    return None


def _extract_conversation_text(candidates: list[dict[str, Any] | Any]) -> str | None:
    for candidate in candidates:
        if not isinstance(candidate, dict):
            continue
        message = candidate.get("message")
        if isinstance(message, dict):
            conversation = message.get("conversation")
            if conversation:
                return _first_str(conversation)
            extended = message.get("extendedTextMessage")
            if isinstance(extended, dict):
                text = extended.get("text")
                if text:
                    return _first_str(text)
    return None
