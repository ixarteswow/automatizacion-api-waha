from __future__ import annotations

from datetime import datetime, timezone
import json
from typing import Any, Mapping

from src.db import db_session
from src.domain.lead_profile_builder import ANSWER_KEY_ALIASES
from src.domain.questions import QUESTIONS

_QUESTION_LABELS = {q.key: q.text for q in QUESTIONS}
_CANONICAL_ORDER = [q.key for q in QUESTIONS]


def get_leads(db_path: str, estado: str | None = None) -> list[dict]:
    query = (
        "SELECT id, telefono, nombre, origen, estado_actual, scoring, creado_en, "
        "ultimo_mensaje_ts, respuestas_clean, metadata "
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
        answers = _build_answer_list(row["respuestas_clean"])
        metadata = _load_json(row["metadata"])
        leads.append(
            {
                "lead_id": row["id"],
                "telefono": row["telefono"],
                "nombre": row["nombre"],
                "origen": row["origen"],
                "estado": row["estado_actual"],
                "scoring": row["scoring"],
                "label": _scoring_label(row["scoring"]),
                "fecha": _format_ts(row["ultimo_mensaje_ts"] or row["creado_en"]),
                "creado": _format_ts(row["creado_en"]),
                "ultimo_mensaje": _format_ts(row["ultimo_mensaje_ts"]),
                "ultimo_mensaje_ts": row["ultimo_mensaje_ts"],
                "respuestas": answers,
                "metadata": metadata,
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


def get_lead_stats(db_path: str) -> dict[str, int]:
    with db_session(db_path) as conn:
        rows = conn.execute("SELECT scoring FROM sesiones_leads").fetchall()
    gold = silver = red = none = 0
    for row in rows:
        score = row["scoring"]
        if score is None:
            none += 1
            continue
        label = _scoring_label(score)
        if label == "GOLD":
            gold += 1
        elif label == "SILVER":
            silver += 1
        else:
            red += 1
    total = gold + silver + red + none
    return {
        "total": total,
        "gold": gold,
        "silver": silver,
        "red": red,
        "none": none,
    }


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


def _build_answer_list(raw: Any) -> list[dict[str, str]]:
    data = _load_json(raw)
    if not data:
        return []
    answers: list[dict[str, str]] = []
    seen: set[str] = set()

    for canonical in _CANONICAL_ORDER:
        aliases = ANSWER_KEY_ALIASES.get(canonical, (canonical,))
        value = _first_present(data, aliases)
        if value is None:
            continue
        answers.append(
            {
                "label": _QUESTION_LABELS.get(canonical, canonical),
                "value": _stringify(value),
            }
        )
        seen.update(aliases)

    for key, value in data.items():
        if key in seen:
            continue
        label = _QUESTION_LABELS.get(key, key)
        answers.append({"label": label, "value": _stringify(value)})

    return answers


def _first_present(data: Mapping[str, Any], keys: tuple[str, ...]) -> Any:
    for key in keys:
        if key in data:
            return data[key]
    return None


def _stringify(value: Any) -> str:
    if value is None:
        return "-"
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=True)
    return str(value)
