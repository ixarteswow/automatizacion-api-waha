import json
import sqlite3
import time
from pathlib import Path

from src.domain import fsm
from src.services.webhook_handler import handle_inbound_message


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


def test_handle_inbound_message_advances_and_logs(tmp_path, monkeypatch):
    db_path = tmp_path / "app.db"
    _init_db(db_path)
    monkeypatch.setenv("PROPERTY_RENT_EUR", "700")
    monkeypatch.setenv("PROPERTY_SQM", "60")
    monkeypatch.setenv("DISABLE_OUTBOUND_MESSAGES", "1")

    telefono = "+34600000005"
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

    result = handle_inbound_message(
        str(db_path),
        message_id="waha-msg-1",
        telefono=telefono,
        text="1200",
    )

    assert result.status == "ok"
    assert result.state == fsm.FINAL_STATE

    conn = sqlite3.connect(str(db_path))
    try:
        evento = conn.execute(
            "SELECT tipo, correlation_id FROM eventos_sistema WHERE telefono = ?",
            (telefono,),
        ).fetchone()
        procesado = conn.execute(
            "SELECT waha_message_id FROM mensajes_procesados WHERE telefono = ?",
            (telefono,),
        ).fetchone()
    finally:
        conn.close()

    assert evento is not None
    assert evento[0] == "scoring_calculated"
    assert evento[1] == "waha-msg-1"
    assert procesado is not None
    assert procesado[0] == "waha-msg-1"


def test_handle_inbound_message_idempotent_insert(tmp_path, monkeypatch):
    db_path = tmp_path / "app.db"
    _init_db(db_path)
    monkeypatch.setenv("PROPERTY_RENT_EUR", "700")
    monkeypatch.setenv("PROPERTY_SQM", "60")
    monkeypatch.setenv("DISABLE_OUTBOUND_MESSAGES", "1")

    telefono = "+34600000010"
    conn = sqlite3.connect(str(db_path))
    try:
        _insert_session(conn, telefono, 1)
    finally:
        conn.close()

    first = handle_inbound_message(
        str(db_path),
        message_id="dup-msg-1",
        telefono=telefono,
        text="Hola",
    )
    second = handle_inbound_message(
        str(db_path),
        message_id="dup-msg-1",
        telefono=telefono,
        text="Hola",
    )

    assert first.status == "ok"
    assert second.status == "duplicate"
