from __future__ import annotations

from datetime import datetime, timezone

from src.db import db_session


def get_leads(db_path: str, estado: str | None = None) -> list[dict]:
    query = (
        "SELECT id, telefono, nombre, estado_actual, scoring, creado_en "
        "FROM sesiones_leads"
    )
    params: list[object] = []
    if estado:
        try:
            estado_value = int(estado)
        except ValueError:
            return []
        query += " WHERE estado_actual = ?"
        params.append(estado_value)
    query += " ORDER BY id DESC"

    with db_session(db_path) as conn:
        rows = conn.execute(query, tuple(params)).fetchall()

    leads: list[dict] = []
    for row in rows:
        leads.append(
            {
                "lead_id": row["id"],
                "telefono": row["telefono"],
                "nombre": row["nombre"],
                "estado": row["estado_actual"],
                "scoring": row["scoring"],
                "label": _scoring_label(row["scoring"]),
                "fecha": _format_ts(row["creado_en"]),
            }
        )
    return leads


def get_estados(db_path: str) -> list[str]:
    with db_session(db_path) as conn:
        rows = conn.execute(
            "SELECT DISTINCT estado_actual FROM sesiones_leads WHERE estado_actual IS NOT NULL "
            "ORDER BY estado_actual ASC"
        ).fetchall()
    return [str(row[0]) for row in rows]


def _scoring_label(score: float | None) -> str | None:
    if score is None:
        return None
    if score > 85.0:
        return "GOLD"
    if score >= 60.0:
        return "SILVER"
    return "RED"


def _format_ts(ts) -> str:
    if ts is None:
        return "-"
    if isinstance(ts, (int, float)):
        return datetime.fromtimestamp(float(ts), tz=timezone.utc).strftime("%Y-%m-%d %H:%M")
    return str(ts)