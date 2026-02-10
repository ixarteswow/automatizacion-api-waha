import json
import sqlite3
import sys
import time
from typing import Any, Mapping


def log_json(level: str, message: str, **fields: Any) -> None:
    payload = {
        "ts": int(time.time()),
        "level": level,
        "message": message,
        **fields,
    }
    sys.stdout.write(json.dumps(payload, ensure_ascii=True) + "\n")
    sys.stdout.flush()


def log_evento(
    conn: sqlite3.Connection,
    tipo: str,
    telefono: str | None = None,
    payload: Mapping[str, Any] | None = None,
    correlation_id: str | None = None,
) -> None:
    payload_json = json.dumps(payload or {}, ensure_ascii=True)
    conn.execute(
        "INSERT INTO eventos_sistema (tipo, telefono, payload, correlation_id) VALUES (?, ?, ?, ?)",
        (tipo, telefono, payload_json, correlation_id),
    )
