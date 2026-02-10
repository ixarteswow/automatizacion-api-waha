from __future__ import annotations

import base64
import json
from dataclasses import dataclass
from typing import Any

from src.db import db_session

_TABLE_CONFIG: dict[str, dict[str, str]] = {
    "sesiones_leads": {"time_column": "ultimo_mensaje_ts", "pk_column": "id"},
    "mensajes_procesados": {"time_column": "procesado_en", "pk_column": "waha_message_id"},
    "inbox_messages": {"time_column": "received_at", "pk_column": "id"},
    "cola_exportacion": {"time_column": "creado_en", "pk_column": "id"},
    "eventos_sistema": {"time_column": "timestamp", "pk_column": "id"},
}


@dataclass(frozen=True)
class ExportResult:
    table: str
    rows: list[dict[str, Any]]
    next_cursor: str | None


def list_export_tables() -> list[str]:
    return sorted(_TABLE_CONFIG.keys())


def export_table_rows(
    db_path: str,
    table: str,
    *,
    updated_since: int | None = None,
    limit: int = 200,
    cursor: str | None = None,
) -> ExportResult:
    config = _TABLE_CONFIG.get(table)
    if config is None:
        raise ValueError("unknown_table")

    time_column = config["time_column"]
    pk_column = config["pk_column"]
    limit = _normalize_limit(limit)

    where_clauses: list[str] = []
    params: list[Any] = []

    if updated_since is not None:
        where_clauses.append(f"{time_column} >= ?")
        params.append(int(updated_since))

    if cursor:
        cursor_ts, cursor_pk = _decode_cursor(cursor)
        where_clauses.append(
            f"({time_column} > ? OR ({time_column} = ? AND {pk_column} > ?))"
        )
        params.extend([cursor_ts, cursor_ts, cursor_pk])

    where_sql = f"WHERE {' AND '.join(where_clauses)}" if where_clauses else ""
    query = (
        f"SELECT * FROM {table} {where_sql} "
        f"ORDER BY {time_column} ASC, {pk_column} ASC LIMIT ?"
    )
    params.append(limit)

    with db_session(db_path) as conn:
        rows = conn.execute(query, tuple(params)).fetchall()

    payload = [_row_to_dict(row) for row in rows]
    next_cursor = None
    if rows and len(rows) == limit:
        last = rows[-1]
        last_ts = last[time_column] if last[time_column] is not None else 0
        last_pk = last[pk_column]
        next_cursor = _encode_cursor(int(last_ts), str(last_pk))

    return ExportResult(table=table, rows=payload, next_cursor=next_cursor)


def _normalize_limit(limit: int) -> int:
    if limit < 1:
        return 1
    if limit > 1000:
        return 1000
    return limit


def _row_to_dict(row) -> dict[str, Any]:
    return {key: row[key] for key in row.keys()}


def _encode_cursor(ts: int, pk: str) -> str:
    payload = json.dumps({"ts": int(ts), "pk": pk}, separators=(",", ":"), ensure_ascii=True)
    encoded = base64.urlsafe_b64encode(payload.encode("utf-8")).decode("ascii")
    return encoded.rstrip("=")


def _decode_cursor(cursor: str) -> tuple[int, str]:
    if not cursor:
        raise ValueError("empty_cursor")
    padding = "=" * (-len(cursor) % 4)
    raw = base64.urlsafe_b64decode((cursor + padding).encode("ascii")).decode("utf-8")
    parsed = json.loads(raw)
    if not isinstance(parsed, dict) or "ts" not in parsed or "pk" not in parsed:
        raise ValueError("invalid_cursor")
    try:
        ts = int(parsed["ts"])
    except (TypeError, ValueError) as exc:
        raise ValueError("invalid_cursor_ts") from exc
    pk = str(parsed["pk"])
    return ts, pk
