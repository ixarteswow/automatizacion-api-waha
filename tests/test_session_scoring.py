import json
import sqlite3
import time
from pathlib import Path

from src.services.session_scoring import score_session


def _init_db(db_path: Path) -> None:
    schema_sql = (Path(__file__).resolve().parents[1] / "db" / "schema.sql").read_text(
        encoding="utf-8"
    )
    conn = sqlite3.connect(str(db_path))
    try:
        conn.executescript(schema_sql)
        conn.commit()
    finally:
        conn.close()


def _insert_session(conn: sqlite3.Connection, telefono: str, respuestas: dict) -> None:
    conn.execute(
        """
        INSERT INTO sesiones_leads (
            telefono,
            estado_actual,
            respuestas_clean,
            intentos_fallidos,
            ultimo_mensaje_ts,
            metadata
        )
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        (
            telefono,
            6,
            json.dumps(respuestas, ensure_ascii=True),
            0,
            int(time.time()),
            "{}",
        ),
    )
    conn.commit()


def test_score_session_persists_metadata(tmp_path, monkeypatch):
    db_path = tmp_path / "app.db"
    _init_db(db_path)
    monkeypatch.setenv("PROPERTY_RENT_EUR", "950")
    monkeypatch.setenv("PROPERTY_SQM", "75")

    telefono = "+34600000001"
    respuestas = {
        "mascotas": "No",
        "fumador": "no",
        "ocupantes": "2",
        "laboral": "Indefinido 24 meses",
        "sector": "sanidad",
        "ingresos": "3200",
    }

    conn = sqlite3.connect(str(db_path))
    try:
        _insert_session(conn, telefono, respuestas)
    finally:
        conn.close()

    result = score_session(str(db_path), telefono, correlation_id="corr-1")

    conn = sqlite3.connect(str(db_path))
    try:
        row = conn.execute(
            "SELECT scoring, metadata, finalizado_en FROM sesiones_leads WHERE telefono = ?",
            (telefono,),
        ).fetchone()
        evento = conn.execute(
            "SELECT tipo, correlation_id, payload FROM eventos_sistema WHERE telefono = ?",
            (telefono,),
        ).fetchone()
    finally:
        conn.close()

    assert row is not None
    assert row[0] == result.total
    metadata = json.loads(row[1])
    assert "scoring" in metadata
    assert metadata["scoring"]["label"] == result.label
    assert row[2] is None
    assert evento is not None
    assert evento[0] == "scoring_calculated"
    assert evento[1] == "corr-1"
    payload = json.loads(evento[2])
    assert payload["label"] == result.label


def test_score_session_with_killers_and_finalize(tmp_path, monkeypatch):
    db_path = tmp_path / "app.db"
    _init_db(db_path)
    monkeypatch.setenv("PROPERTY_RENT_EUR", "700")
    monkeypatch.setenv("PROPERTY_SQM", "60")

    telefono = "+34600000002"
    respuestas = {
        "p1": "No mascotas",
        "p2": "no",
        "p3": "2",
        "p4": "Temporal 2 meses",
        "p5": "it",
        "p6": "1200",
    }

    conn = sqlite3.connect(str(db_path))
    try:
        _insert_session(conn, telefono, respuestas)
    finally:
        conn.close()

    result = score_session(
        str(db_path), telefono, finalize=True, correlation_id="corr-2"
    )

    assert result.total == 0.0
    assert "ratio_esfuerzo" in result.killers
    assert "inestabilidad_laboral" in result.killers

    conn = sqlite3.connect(str(db_path))
    try:
        row = conn.execute(
            "SELECT scoring, metadata, finalizado_en FROM sesiones_leads WHERE telefono = ?",
            (telefono,),
        ).fetchone()
        evento = conn.execute(
            "SELECT tipo, correlation_id, payload FROM eventos_sistema WHERE telefono = ?",
            (telefono,),
        ).fetchone()
    finally:
        conn.close()

    assert row is not None
    assert row[2] is not None
    assert evento is not None
    assert evento[0] == "scoring_calculated"
    assert evento[1] == "corr-2"
