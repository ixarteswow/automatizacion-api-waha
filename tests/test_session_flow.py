import json
import sqlite3
import time
from pathlib import Path

from src.domain import fsm
from src.services.session_flow import advance_on_valid_answer, finalize_session


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


def _insert_session(conn: sqlite3.Connection, telefono: str, estado: int) -> None:
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
            estado,
            "{}",
            0,
            int(time.time()),
            "{}",
        ),
    )
    conn.commit()


def test_advance_to_final_triggers_scoring(tmp_path, monkeypatch):
    db_path = tmp_path / "app.db"
    _init_db(db_path)
    monkeypatch.setenv("PROPERTY_RENT_EUR", "700")
    monkeypatch.setenv("PROPERTY_SQM", "60")

    telefono = "+34600000003"
    conn = sqlite3.connect(str(db_path))
    try:
        _insert_session(conn, telefono, fsm.MAX_STATE)
        conn.execute(
            "UPDATE sesiones_leads SET respuestas_clean = ? WHERE telefono = ?",
            (
                json.dumps(
                    {
                        "p1": "No mascotas",
                        "p2": "no",
                        "p3": "2",
                        "p4": "Temporal 2 meses",
                        "p5": "it",
                        "p6": "1200",
                    },
                    ensure_ascii=True,
                ),
                telefono,
            ),
        )
        conn.commit()
    finally:
        conn.close()

    new_state = advance_on_valid_answer(
        str(db_path),
        telefono,
        answer_key="p6",
        answer_value="1200",
        correlation_id="corr-flow",
    )

    assert new_state == fsm.FINAL_STATE

    conn = sqlite3.connect(str(db_path))
    try:
        row = conn.execute(
            "SELECT scoring, finalizado_en FROM sesiones_leads WHERE telefono = ?",
            (telefono,),
        ).fetchone()
        evento = conn.execute(
            "SELECT tipo, correlation_id FROM eventos_sistema WHERE telefono = ?",
            (telefono,),
        ).fetchone()
    finally:
        conn.close()

    assert row is not None
    assert row[0] == 0.0
    assert row[1] is not None
    assert evento is not None
    assert evento[0] == "scoring_calculated"
    assert evento[1] == "corr-flow"


def test_finalize_session_propagates_correlation(tmp_path, monkeypatch):
    db_path = tmp_path / "app.db"
    _init_db(db_path)
    monkeypatch.setenv("PROPERTY_RENT_EUR", "950")
    monkeypatch.setenv("PROPERTY_SQM", "75")

    telefono = "+34600000004"
    conn = sqlite3.connect(str(db_path))
    try:
        _insert_session(conn, telefono, fsm.MAX_STATE)
        conn.execute(
            "UPDATE sesiones_leads SET respuestas_clean = ? WHERE telefono = ?",
            (
                json.dumps(
                    {
                        "p1": "No mascotas",
                        "p2": "no",
                        "p3": "2",
                        "p4": "Indefinido 24 meses",
                        "p5": "sanidad",
                        "p6": "3200",
                    },
                    ensure_ascii=True,
                ),
                telefono,
            ),
        )
        conn.commit()
    finally:
        conn.close()

    finalize_session(str(db_path), telefono, correlation_id="corr-finalize")

    conn = sqlite3.connect(str(db_path))
    try:
        row = conn.execute(
            "SELECT finalizado_en FROM sesiones_leads WHERE telefono = ?",
            (telefono,),
        ).fetchone()
        evento = conn.execute(
            "SELECT tipo, correlation_id FROM eventos_sistema WHERE telefono = ?",
            (telefono,),
        ).fetchone()
    finally:
        conn.close()

    assert row is not None
    assert row[0] is not None
    assert evento is not None
    assert evento[0] == "scoring_calculated"
    assert evento[1] == "corr-finalize"
