import sqlite3
import time
from pathlib import Path

from fastapi.testclient import TestClient

from src.api import app


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


def _insert_session(conn: sqlite3.Connection, telefono: str, estado: int, scoring: float | None) -> None:
    conn.execute(
        """
        INSERT INTO sesiones_leads (
            telefono,
            estado_actual,
            respuestas_clean,
            intentos_fallidos,
            ultimo_mensaje_ts,
            scoring,
            metadata
        )
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            telefono,
            estado,
            "{}",
            0,
            int(time.time()),
            scoring,
            "{}",
        ),
    )
    conn.commit()


def test_csv_endpoint_returns_csv(tmp_path, monkeypatch):
    db_path = tmp_path / "app.db"
    _init_db(db_path)
    monkeypatch.setenv("DB_PATH", str(db_path))

    conn = sqlite3.connect(str(db_path))
    try:
        _insert_session(conn, "+34600000020", 2, 90.0)
    finally:
        conn.close()

    client = TestClient(app)
    response = client.get("/export/leads.csv")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/csv")
    assert "Content-Disposition" in response.headers

    first_line = response.text.splitlines()[0]
    assert "ID" in first_line
    assert "Telefono" in first_line


def test_csv_endpoint_empty_db(tmp_path, monkeypatch):
    db_path = tmp_path / "app.db"
    _init_db(db_path)
    monkeypatch.setenv("DB_PATH", str(db_path))

    client = TestClient(app)
    response = client.get("/export/leads.csv")

    assert response.status_code == 200
    lines = [line for line in response.text.splitlines() if line]
    assert len(lines) >= 1


def test_dashboard_returns_html(tmp_path, monkeypatch):
    db_path = tmp_path / "app.db"
    _init_db(db_path)
    monkeypatch.setenv("DB_PATH", str(db_path))

    client = TestClient(app)
    response = client.get("/")

    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    assert "Panel de Leads" in response.text


def test_dashboard_filter_nonexistent_estado(tmp_path, monkeypatch):
    db_path = tmp_path / "app.db"
    _init_db(db_path)
    monkeypatch.setenv("DB_PATH", str(db_path))

    client = TestClient(app)
    response = client.get("/?estado=inexistente")

    assert response.status_code == 200
    assert "No hay leads registrados" in response.text


def test_dashboard_contains_export_link(tmp_path, monkeypatch):
    db_path = tmp_path / "app.db"
    _init_db(db_path)
    monkeypatch.setenv("DB_PATH", str(db_path))

    client = TestClient(app)
    response = client.get("/")

    assert response.status_code == 200
    assert "/export/leads.csv" in response.text
