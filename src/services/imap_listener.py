from __future__ import annotations

import argparse
import email
import imaplib
import json
import os
import re
import time
from dataclasses import dataclass
from email.header import decode_header
from typing import Any, Iterable

import httpx

from src.logging_utils import log_json

_NAME_RE = re.compile(r"(?im)^\s*nombre\s*[:\-]\s*(.+)$")
_PHONE_RE = re.compile(r"(?im)^\s*tel[eé]fono\s*[:\-]\s*([+0-9][0-9 .\-]{6,})$")
_PHONE_FALLBACK_RE = re.compile(r"(?<!\d)(\d{9})(?!\d)")
_HTML_TAG_RE = re.compile(r"<[^>]+>")


@dataclass(frozen=True)
class ImapSettings:
    host: str
    port: int
    user: str
    password: str
    folder: str
    subject_keyword: str
    label_success: str | None
    label_error: str | None
    leads_api_url: str
    poll_seconds: float


def load_imap_settings() -> ImapSettings:
    host = os.getenv("IMAP_HOST", "imap.gmail.com").strip()
    port = int(os.getenv("IMAP_PORT", "993"))
    user = _require_env("IMAP_USER")
    password = _require_env("IMAP_PASSWORD")
    folder = os.getenv("IMAP_FOLDER", "INBOX").strip() or "INBOX"
    subject_keyword = os.getenv("IMAP_SUBJECT_KEYWORD", "Idealista").strip() or "Idealista"
    label_success = _normalize_optional_env("IMAP_LABEL")
    label_error = _normalize_optional_env("IMAP_LABEL_ERROR")
    leads_api_url = os.getenv("LEADS_API_URL", "http://api:8000/leads").strip()
    poll_seconds = float(os.getenv("IMAP_POLL_SECONDS", "30"))
    return ImapSettings(
        host=host,
        port=port,
        user=user,
        password=password,
        folder=folder,
        subject_keyword=subject_keyword,
        label_success=label_success,
        label_error=label_error,
        leads_api_url=leads_api_url,
        poll_seconds=poll_seconds,
    )


def run_once(settings: ImapSettings) -> int:
    processed = 0
    with imaplib.IMAP4_SSL(settings.host, settings.port) as imap:
        imap.login(settings.user, settings.password)
        status, _ = imap.select(settings.folder)
        if status != "OK":
            log_json("error", "imap_select_failed", folder=settings.folder)
            return processed

        status, data = _search_unseen(imap, settings.subject_keyword)
        if status != "OK":
            log_json("error", "imap_search_failed")
            return processed

        msg_ids = data[0].split() if data and data[0] else []
        log_json("info", "imap_poll_started", unseen=len(msg_ids))
        for msg_id in msg_ids:
            if _process_message(imap, msg_id, settings):
                processed += 1

        skipped = max(0, len(msg_ids) - processed)
        log_json("info", "imap_poll_complete", processed=processed, skipped=skipped)

    return processed


def _search_unseen(imap, subject_keyword: str) -> tuple[str, list[Any]]:
    keyword = subject_keyword.strip() if subject_keyword else ""
    if keyword:
        try:
            criteria = f'(UNSEEN SUBJECT "{_escape_imap_search(keyword)}")'
            status, data = imap.search(None, criteria)
            if status == "OK":
                return status, data
        except Exception as exc:
            log_json("warning", "imap_search_subject_failed", error=str(exc))
    return imap.search(None, "UNSEEN")


def run_forever(settings: ImapSettings) -> None:
    while True:
        run_once(settings)
        time.sleep(settings.poll_seconds)


def _process_message(imap, msg_id: bytes, settings: ImapSettings) -> bool:
    status, data = imap.fetch(msg_id, "(RFC822)")
    if status != "OK" or not data:
        log_json("error", "imap_fetch_failed", msg_id=_decode_bytes(msg_id))
        return False

    raw_bytes = _first_message_bytes(data)
    if raw_bytes is None:
        log_json("error", "imap_empty_message", msg_id=_decode_bytes(msg_id))
        return False

    message = email.message_from_bytes(raw_bytes)
    subject = _decode_subject(message.get("Subject"))
    log_json(
        "info",
        "imap_processing_email",
        msg_id=_decode_bytes(msg_id),
        subject=subject,
    )
    if not subject_matches(subject, settings.subject_keyword):
        return False

    body_text = _extract_body_text(message)
    nombre, telefono = extract_lead_fields(body_text)
    message_id = _safe_header(message.get("Message-ID")) or _decode_bytes(msg_id)

    if not nombre or not telefono:
        _mark_seen(imap, msg_id)
        _apply_label(imap, msg_id, settings.label_error, settings.host)
        log_json(
            "warning",
            "lead_parse_failed",
            msg_id=_decode_bytes(msg_id),
            subject=subject,
        )
        return True

    payload = {
        "nombre": nombre,
        "telefono": telefono,
        "origen": "Idealista",
        "message_id": message_id,
        "metadata": {
            "email_subject": subject,
            "email_from": _safe_header(message.get("From")),
            "email_date": _safe_header(message.get("Date")),
            "imap_msg_id": _decode_bytes(msg_id),
        },
    }

    try:
        response = httpx.post(settings.leads_api_url, json=payload, timeout=10)
    except Exception as exc:
        log_json("error", "lead_api_error", error=str(exc))
        return False

    if response.status_code == 200:
        _mark_seen(imap, msg_id)
        _apply_label(imap, msg_id, settings.label_success, settings.host)
        log_json("info", "lead_sent", telefono=telefono, status=response.status_code)
        return True

    if response.status_code in {400, 422}:
        _mark_seen(imap, msg_id)
        _apply_label(imap, msg_id, settings.label_error, settings.host)
        log_json(
            "warning",
            "lead_rejected",
            status=response.status_code,
            detail=_safe_json(response.text),
        )
        return True

    log_json(
        "error",
        "lead_api_unexpected",
        status=response.status_code,
        body=_safe_json(response.text),
    )
    return False


def extract_lead_fields(text: str) -> tuple[str | None, str | None]:
    if not text:
        return None, None
    name_match = _NAME_RE.search(text)
    phone_match = _PHONE_RE.search(text)
    nombre = name_match.group(1).strip() if name_match else None
    telefono = phone_match.group(1).strip() if phone_match else None

    if not telefono:
        fallback = _PHONE_FALLBACK_RE.search(text)
        if fallback:
            telefono = fallback.group(1).strip()

    return nombre, telefono


def _extract_body_text(message: email.message.Message) -> str:
    if message.is_multipart():
        parts = list(_iter_text_parts(message))
        if parts:
            return "\n".join(parts)
    payload = message.get_payload(decode=True)
    if payload:
        return payload.decode(message.get_content_charset() or "utf-8", errors="replace")
    return ""


def _iter_text_parts(message: email.message.Message) -> Iterable[str]:
    html_fallback: list[str] = []
    for part in message.walk():
        if part.is_multipart():
            continue
        content_type = part.get_content_type().lower()
        disposition = part.get("Content-Disposition", "").lower()
        if "attachment" in disposition:
            continue
        payload = part.get_payload(decode=True)
        if payload is None:
            continue
        text = payload.decode(part.get_content_charset() or "utf-8", errors="replace")
        if content_type == "text/plain":
            yield text
        elif content_type == "text/html":
            html_fallback.append(_strip_html(text))
    if not html_fallback:
        return
    for item in html_fallback:
        yield item


def _strip_html(value: str) -> str:
    return _HTML_TAG_RE.sub(" ", value)


def _decode_subject(raw: str | None) -> str:
    if not raw:
        return ""
    decoded_parts = []
    for part, encoding in decode_header(raw):
        if isinstance(part, bytes):
            decoded_parts.append(part.decode(encoding or "utf-8", errors="replace"))
        else:
            decoded_parts.append(part)
    return "".join(decoded_parts).strip()


def subject_matches(subject: str, keyword: str) -> bool:
    if not keyword:
        return True
    return keyword.lower() in subject.lower()


def _escape_imap_search(value: str) -> str:
    return value.replace("\\", "\\\\").replace("\"", "\\\"")


def _first_message_bytes(data: list[Any]) -> bytes | None:
    for item in data:
        if isinstance(item, tuple) and isinstance(item[1], bytes):
            return item[1]
    return None


def _mark_seen(imap, msg_id: bytes) -> None:
    imap.store(msg_id, "+FLAGS", "\\Seen")


def _apply_label(imap, msg_id: bytes, label: str | None, host: str) -> None:
    if not label:
        return
    if "gmail" not in host.lower() and "google" not in host.lower():
        log_json(
            "debug",
            "imap_label_skipped_non_gmail",
            host=host,
            label=label,
        )
        return
    try:
        imap.store(msg_id, "+X-GM-LABELS", _quote_label(label))
    except Exception as exc:
        log_json(
            "warning",
            "imap_label_failed",
            msg_id=_decode_bytes(msg_id),
            label=label,
            error=str(exc),
        )


def _quote_label(label: str) -> str:
    return f"\"{label}\""


def _decode_bytes(value: bytes) -> str:
    return value.decode("utf-8", errors="replace") if value else ""


def _safe_header(value: str | None) -> str | None:
    if not value:
        return None
    return str(value).strip() or None


def _safe_json(raw: str) -> Any:
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return raw


def _normalize_optional_env(key: str) -> str | None:
    value = os.getenv(key)
    if value is None:
        return None
    value = value.strip()
    return value or None


def _require_env(key: str) -> str:
    value = os.getenv(key)
    if value is None or not value.strip():
        raise ValueError(f"Missing required env var: {key}")
    return value.strip()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Escucha IMAP y crea leads a partir de correos no leidos."
    )
    parser.add_argument(
        "--once",
        action="store_true",
        help="Ejecuta una unica iteracion y termina.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    settings = load_imap_settings()
    if args.once:
        count = run_once(settings)
        log_json("info", "imap_run_once_complete", processed=count)
        return
    run_forever(settings)


if __name__ == "__main__":
    main()
