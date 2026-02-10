import json
import sqlite3
import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from src.domain import fsm
from src.api import app
from src.config import load_scoring_settings
from src.services import lead_intake


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


def test_api_webhook_happy_path(tmp_path, monkeypatch):
    db_path = tmp_path / "app.db"
    _init_db(db_path)
    monkeypatch.setenv("DB_PATH", str(db_path))
    monkeypatch.setenv("PROPERTY_RENT_EUR", "700")
    monkeypatch.setenv("PROPERTY_SQM", "60")
    monkeypatch.setenv("DISABLE_OUTBOUND_MESSAGES", "1")

    telefono = "+34600000006"
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

    client = TestClient(app)
    response = client.post(
        "/waha/message",
        json={
            "id": "waha-msg-2",
            "from": telefono,
            "text": "1200",
        },
    )
    payload = response.json()

    assert response.status_code == 200
    assert payload["status"] == "ok"
    assert payload["state"] == fsm.FINAL_STATE

    conn = sqlite3.connect(str(db_path))
    try:
        row = conn.execute(
            "SELECT scoring, finalizado_en FROM sesiones_leads WHERE telefono = ?",
            (telefono,),
        ).fetchone()
        evento = conn.execute(
            "SELECT correlation_id FROM eventos_sistema WHERE telefono = ?",
            (telefono,),
        ).fetchone()
        procesado = conn.execute(
            "SELECT waha_message_id FROM mensajes_procesados WHERE telefono = ?",
            (telefono,),
        ).fetchone()
    finally:
        conn.close()

    assert row is not None
    assert row[0] == 0.0
    assert row[1] is not None
    assert evento is not None
    assert evento[0] == "waha-msg-2"
    assert procesado is not None
    assert procesado[0] == "waha-msg-2"


def test_api_webhook_duplicate_message(tmp_path, monkeypatch):
    db_path = tmp_path / "app.db"
    _init_db(db_path)
    monkeypatch.setenv("DB_PATH", str(db_path))
    monkeypatch.setenv("PROPERTY_RENT_EUR", "950")
    monkeypatch.setenv("PROPERTY_SQM", "75")
    monkeypatch.setenv("DISABLE_OUTBOUND_MESSAGES", "1")

    telefono = "+34600000007"
    conn = sqlite3.connect(str(db_path))
    try:
        _insert_session(conn, telefono, 1)
    finally:
        conn.close()

    client = TestClient(app)
    payload = {"id": "waha-msg-3", "from": telefono, "text": "No"}
    first = client.post("/waha/message", json=payload)
    second = client.post("/waha/message", json=payload)

    assert first.status_code == 200
    assert second.status_code == 200
    assert second.json()["status"] == "duplicate"


def test_api_webhook_ignores_non_text(tmp_path, monkeypatch):
    db_path = tmp_path / "app.db"
    _init_db(db_path)
    monkeypatch.setenv("DB_PATH", str(db_path))
    monkeypatch.setenv("PROPERTY_RENT_EUR", "950")
    monkeypatch.setenv("PROPERTY_SQM", "75")
    monkeypatch.setenv("DISABLE_OUTBOUND_MESSAGES", "1")

    client = TestClient(app)
    response = client.post("/waha/message", json={"id": "waha-msg-4", "from": "+34"})

    assert response.status_code == 200
    assert response.json()["status"] == "ignored"


def test_api_webhook_nested_payload(tmp_path, monkeypatch):
    db_path = tmp_path / "app.db"
    _init_db(db_path)
    monkeypatch.setenv("DB_PATH", str(db_path))
    monkeypatch.setenv("PROPERTY_RENT_EUR", "700")
    monkeypatch.setenv("PROPERTY_SQM", "60")
    monkeypatch.setenv("DISABLE_OUTBOUND_MESSAGES", "1")

    telefono = "+34600000008"
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

    client = TestClient(app)
    response = client.post(
        "/waha/message",
        json={
            "body": {
                "event": "message.any",
                "payload": {
                    "id": "waha-msg-5",
                    "from": telefono,
                    "body": "1200",
                    "fromMe": False,
                },
            }
        },
    )

    payload = response.json()
    assert response.status_code == 200
    assert payload["status"] == "ok"
    assert payload["state"] == fsm.FINAL_STATE


def test_api_webhook_ignores_from_me(tmp_path, monkeypatch):
    db_path = tmp_path / "app.db"
    _init_db(db_path)
    monkeypatch.setenv("DB_PATH", str(db_path))
    monkeypatch.setenv("PROPERTY_RENT_EUR", "700")
    monkeypatch.setenv("PROPERTY_SQM", "60")
    monkeypatch.setenv("DISABLE_OUTBOUND_MESSAGES", "1")

    client = TestClient(app)
    response = client.post(
        "/waha/message",
        json={
            "event": "message.any",
            "payload": {
                "id": "waha-msg-6",
                "from": "+34600000009",
                "body": "Hola",
                "fromMe": True,
            },
        },
    )

    assert response.status_code == 200
    assert response.json()["status"] == "ignored"


def test_api_webhook_real_payload_shape(tmp_path, monkeypatch):
    db_path = tmp_path / "app.db"
    _init_db(db_path)
    monkeypatch.setenv("DB_PATH", str(db_path))
    monkeypatch.setenv("PROPERTY_RENT_EUR", "700")
    monkeypatch.setenv("PROPERTY_SQM", "60")
    monkeypatch.setenv("DISABLE_OUTBOUND_MESSAGES", "1")

    telefono = "208494976315552@lid"
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

    client = TestClient(app)
    response = client.post(
        "/waha/message",
        json={
            "id": "evt_test",
            "timestamp": 1770474196113,
            "event": "message.any",
            "session": "default",
            "metadata": {},
            "me": {"id": "34619427410@c.us", "pushName": "Amos"},
            "payload": {
                "id": "false_208494976315552@lid_ACD9",
                "timestamp": 1770474195,
                "from": telefono,
                "fromMe": False,
                "source": "app",
                "body": "Hola 123",
                "hasMedia": False,
                "media": None,
                "_data": {
                    "key": {
                        "remoteJid": telefono,
                        "fromMe": False,
                        "id": "ACD9",
                        "addressingMode": "lid",
                    },
                    "message": {"conversation": "Hola 123"},
                },
            },
            "engine": "NOWEB",
        },
    )

    payload = response.json()
    assert response.status_code == 200
    assert payload["status"] == "ok"
    assert payload["state"] == fsm.FINAL_STATE


def test_api_webhook_prefers_remote_jid_alt(tmp_path, monkeypatch):
    db_path = tmp_path / "app.db"
    _init_db(db_path)
    monkeypatch.setenv("DB_PATH", str(db_path))
    monkeypatch.setenv("PROPERTY_RENT_EUR", "700")
    monkeypatch.setenv("PROPERTY_SQM", "60")
    monkeypatch.setenv("DISABLE_OUTBOUND_MESSAGES", "1")

    telefono = "34685587879@c.us"
    conn = sqlite3.connect(str(db_path))
    try:
        _insert_session(conn, telefono, 1)
    finally:
        conn.close()

    client = TestClient(app)
    response = client.post(
        "/waha/message",
        json={
            "event": "message",
            "payload": {
                "id": "waha-msg-alt-1",
                "from": "208494976315552@lid",
                "body": "No",
                "fromMe": False,
                "_data": {
                    "key": {
                        "remoteJid": "208494976315552@lid",
                        "remoteJidAlt": "34685587879@s.whatsapp.net",
                        "fromMe": False,
                        "id": "ACAEE6",
                        "addressingMode": "lid",
                    }
                },
            },
        },
    )

    payload = response.json()
    assert response.status_code == 200
    assert payload["status"] == "ok"
    assert payload["state"] == 2


def test_api_webhook_timestamp_normalization_ms(tmp_path, monkeypatch):
    db_path = tmp_path / "app.db"
    _init_db(db_path)
    monkeypatch.setenv("DB_PATH", str(db_path))
    monkeypatch.setenv("PROPERTY_RENT_EUR", "700")
    monkeypatch.setenv("PROPERTY_SQM", "60")
    monkeypatch.setenv("DISABLE_OUTBOUND_MESSAGES", "1")

    telefono = "+34600000012"
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

    client = TestClient(app)
    response = client.post(
        "/waha/message",
        json={
            "id": "waha-msg-ts-ms",
            "from": telefono,
            "text": "1200",
            "timestamp": 1707500000000,
        },
    )

    assert response.status_code == 200

    conn = sqlite3.connect(str(db_path))
    try:
        row = conn.execute(
            "SELECT ultimo_mensaje_ts FROM sesiones_leads WHERE telefono = ?",
            (telefono,),
        ).fetchone()
    finally:
        conn.close()

    assert row is not None
    assert 1_600_000_000 < row[0] < 2_000_000_000


def test_api_webhook_timestamp_normalization_seconds(tmp_path, monkeypatch):
    db_path = tmp_path / "app.db"
    _init_db(db_path)
    monkeypatch.setenv("DB_PATH", str(db_path))
    monkeypatch.setenv("PROPERTY_RENT_EUR", "700")
    monkeypatch.setenv("PROPERTY_SQM", "60")
    monkeypatch.setenv("DISABLE_OUTBOUND_MESSAGES", "1")

    telefono = "+34600000013"
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

    client = TestClient(app)
    response = client.post(
        "/waha/message",
        json={
            "id": "waha-msg-ts-s",
            "from": telefono,
            "text": "1200",
            "timestamp": 1707500000,
        },
    )

    assert response.status_code == 200

    conn = sqlite3.connect(str(db_path))
    try:
        row = conn.execute(
            "SELECT ultimo_mensaje_ts FROM sesiones_leads WHERE telefono = ?",
            (telefono,),
        ).fetchone()
    finally:
        conn.close()

    assert row is not None
    assert row[0] == 1707500000


def test_api_create_lead_happy_path(tmp_path, monkeypatch):
    db_path = tmp_path / "app.db"
    _init_db(db_path)
    monkeypatch.setenv("DB_PATH", str(db_path))
    monkeypatch.setenv("PROPERTY_RENT_EUR", "700")
    monkeypatch.setenv("PROPERTY_SQM", "60")

    monkeypatch.setattr(lead_intake, "_send_first_question", lambda *_args, **_kwargs: None)

    client = TestClient(app)
    response = client.post(
        "/leads",
        json={
            "nombre": "Nombre OK Verde",
            "telefono": "685587879",
            "origen": "Idealista",
        },
    )

    payload = response.json()
    assert response.status_code == 200
    assert payload["status"] == "created"
    assert payload["telefono"] == "34685587879@c.us"
    assert payload["estado"] == fsm.MIN_STATE
    assert payload["question_sent"] is True

    conn = sqlite3.connect(str(db_path))
    try:
        row = conn.execute(
            "SELECT telefono, nombre, origen, metadata FROM sesiones_leads WHERE telefono = ?",
            ("34685587879@c.us",),
        ).fetchone()
    finally:
        conn.close()

    assert row is not None
    assert row[0] == "34685587879@c.us"
    assert row[1] == "Nombre OK Verde"
    assert row[2] == "idealista"
    assert "lead" in json.loads(row[3])


def test_api_create_lead_duplicate(tmp_path, monkeypatch):
    db_path = tmp_path / "app.db"
    _init_db(db_path)
    monkeypatch.setenv("DB_PATH", str(db_path))
    monkeypatch.setenv("PROPERTY_RENT_EUR", "700")
    monkeypatch.setenv("PROPERTY_SQM", "60")

    monkeypatch.setattr(lead_intake, "_send_first_question", lambda *_args, **_kwargs: None)

    client = TestClient(app)
    payload = {"nombre": "Nombre OK Verde", "telefono": "685587879", "origen": "Idealista"}
    first = client.post("/leads", json=payload)
    second = client.post("/leads", json=payload)

    assert first.status_code == 200
    assert second.status_code == 200
    assert second.json()["status"] == "exists"


def test_api_create_lead_missing_phone(tmp_path, monkeypatch):
    db_path = tmp_path / "app.db"
    _init_db(db_path)
    monkeypatch.setenv("DB_PATH", str(db_path))

    client = TestClient(app)
    response = client.post("/leads", json={"nombre": "Solo nombre"})

    assert response.status_code == 422


def test_api_create_lead_e164_normalization(tmp_path, monkeypatch):
    db_path = tmp_path / "app.db"
    _init_db(db_path)
    monkeypatch.setenv("DB_PATH", str(db_path))

    monkeypatch.setattr(lead_intake, "_send_first_question", lambda *_args, **_kwargs: None)

    client = TestClient(app)
    response = client.post(
        "/leads",
        json={
            "nombre": "Nombre OK",
            "telefono": "+34612345678",
            "origen": "Idealista",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "created"
    assert payload["telefono"] == "34612345678@c.us"


def test_api_create_lead_short_phone_prefix(tmp_path, monkeypatch):
    db_path = tmp_path / "app.db"
    _init_db(db_path)
    monkeypatch.setenv("DB_PATH", str(db_path))

    monkeypatch.setattr(lead_intake, "_send_first_question", lambda *_args, **_kwargs: None)

    client = TestClient(app)
    response = client.post(
        "/leads",
        json={
            "nombre": "Nombre OK",
            "telefono": "612345678",
            "origen": "Idealista",
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "created"
    assert payload["telefono"] == "34612345678@c.us"


def test_export_requires_api_key(tmp_path, monkeypatch):
    db_path = tmp_path / "app.db"
    _init_db(db_path)
    monkeypatch.setenv("DB_PATH", str(db_path))
    monkeypatch.setenv("PROPERTY_RENT_EUR", "700")
    monkeypatch.setenv("PROPERTY_SQM", "60")
    monkeypatch.setenv("EXPORT_API_KEY", "secret")

    client = TestClient(app)
    response = client.get("/export/sesiones_leads")
    assert response.status_code == 401

    response = client.get("/export/sesiones_leads", headers={"X-API-KEY": "wrong"})
    assert response.status_code == 401

    response = client.get("/export/sesiones_leads", headers={"X-API-KEY": "secret"})
    assert response.status_code == 200
    assert response.json()["count"] == 0


def test_export_pagination_cursor(tmp_path, monkeypatch):
    db_path = tmp_path / "app.db"
    _init_db(db_path)
    monkeypatch.setenv("DB_PATH", str(db_path))
    monkeypatch.setenv("PROPERTY_RENT_EUR", "700")
    monkeypatch.setenv("PROPERTY_SQM", "60")
    monkeypatch.setenv("EXPORT_API_KEY", "secret")

    telefono_a = "+34600000010"
    telefono_b = "+34600000011"
    conn = sqlite3.connect(str(db_path))
    try:
        _insert_session(conn, telefono_a, 1)
        _insert_session(conn, telefono_b, 1)
        conn.execute(
            "UPDATE sesiones_leads SET ultimo_mensaje_ts = ? WHERE telefono = ?",
            (1700000000, telefono_a),
        )
        conn.execute(
            "UPDATE sesiones_leads SET ultimo_mensaje_ts = ? WHERE telefono = ?",
            (1700000001, telefono_b),
        )
        conn.commit()
    finally:
        conn.close()

    client = TestClient(app)
    response = client.get(
        "/export/sesiones_leads?limit=1", headers={"X-API-KEY": "secret"}
    )
    payload = response.json()
    assert response.status_code == 200
    assert payload["count"] == 1
    assert payload["next_cursor"]

    first_phone = payload["rows"][0]["telefono"]
    cursor = payload["next_cursor"]

    response = client.get(
        f"/export/sesiones_leads?limit=1&cursor={cursor}",
        headers={"X-API-KEY": "secret"},
    )
    payload = response.json()
    assert response.status_code == 200
    assert payload["count"] == 1
    assert payload["rows"][0]["telefono"] != first_phone

    response = client.get(
        "/export/sesiones_leads?updated_since=1700000001",
        headers={"X-API-KEY": "secret"},
    )
    payload = response.json()
    assert response.status_code == 200
    assert payload["count"] == 1
    assert payload["rows"][0]["telefono"] == telefono_b


def test_export_invalid_cursor(tmp_path, monkeypatch):
    db_path = tmp_path / "app.db"
    _init_db(db_path)
    monkeypatch.setenv("DB_PATH", str(db_path))
    monkeypatch.setenv("EXPORT_API_KEY", "secret")

    client = TestClient(app)
    response = client.get(
        "/export/sesiones_leads?cursor=e30", headers={"X-API-KEY": "secret"}
    )
    assert response.status_code == 400


def test_export_unknown_table(tmp_path, monkeypatch):
    db_path = tmp_path / "app.db"
    _init_db(db_path)
    monkeypatch.setenv("DB_PATH", str(db_path))
    monkeypatch.setenv("EXPORT_API_KEY", "secret")

    client = TestClient(app)
    response = client.get("/export/tabla_inventada", headers={"X-API-KEY": "secret"})
    assert response.status_code == 404


def test_export_without_scoring_env(tmp_path, monkeypatch):
    db_path = tmp_path / "app.db"
    _init_db(db_path)
    monkeypatch.setenv("DB_PATH", str(db_path))
    monkeypatch.setenv("EXPORT_API_KEY", "secret")
    monkeypatch.delenv("PROPERTY_RENT_EUR", raising=False)
    monkeypatch.delenv("PROPERTY_SQM", raising=False)

    client = TestClient(app)
    response = client.get("/export/sesiones_leads", headers={"X-API-KEY": "secret"})
    assert response.status_code == 200


def test_scoring_without_env_raises(monkeypatch):
    monkeypatch.delenv("PROPERTY_RENT_EUR", raising=False)
    monkeypatch.delenv("PROPERTY_SQM", raising=False)

    with pytest.raises(ValueError, match="PROPERTY_RENT_EUR"):
        load_scoring_settings()
