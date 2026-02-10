from __future__ import annotations

import csv
import io

from src.db import db_session

CSV_COLUMNS: list[tuple[str, str]] = [
    ("id", "ID"),
    ("telefono", "Telefono"),
    ("nombre", "Nombre"),
    ("estado_actual", "Estado"),
    ("scoring", "Scoring"),
    ("scoring_label", "Categoria"),
]


def generate_leads_csv(db_path: str) -> str:
    db_columns = [col[0] for col in CSV_COLUMNS if col[0] != "scoring_label"]
    display_columns = [col[1] for col in CSV_COLUMNS]

    query = (
        "SELECT id, telefono, nombre, estado_actual, scoring "
        "FROM sesiones_leads ORDER BY id DESC"
    )

    with db_session(db_path) as conn:
        rows = conn.execute(query).fetchall()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(display_columns)

    for row in rows:
        values = [row[column] for column in db_columns]
        label = _scoring_label(row["scoring"])
        values.append(label)
        writer.writerow(values)

    return output.getvalue()


def _scoring_label(score: float | None) -> str:
    if score is None:
        return "-"
    if score > 85.0:
        return "GOLD"
    if score >= 60.0:
        return "SILVER"
    return "RED"