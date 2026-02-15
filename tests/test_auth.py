
import sqlite3
import pytest
from pathlib import Path
from fastapi.testclient import TestClient
from src.api import app

def _init_db(db_path: Path) -> None:
    # Go up one level from 'tests' to project root, then to db/schema.sql
    schema_path = Path(__file__).resolve().parents[1] / "db" / "schema.sql"
    schema_sql = schema_path.read_text(encoding="utf-8")
    
    conn = sqlite3.connect(str(db_path))
    try:
        conn.executescript(schema_sql)
        conn.commit()
    finally:
        conn.close()

def test_dashboard_requires_auth(tmp_path, monkeypatch):
    db_path = tmp_path / "app.db"
    _init_db(db_path)

    monkeypatch.setenv("DB_PATH", str(db_path))
    monkeypatch.setenv("DASHBOARD_USERNAME", "admin")
    monkeypatch.setenv("DASHBOARD_PASSWORD", "secret")

    client = TestClient(app)
    
    # 1. No credentials -> 401
    response = client.get("/")
    assert response.status_code == 401
    assert "WWW-Authenticate" in response.headers
    assert response.headers["WWW-Authenticate"] == "Basic"

    response = client.get("/api/dashboard-data")
    assert response.status_code == 401
    
    # 2. Wrong credentials -> 401
    response = client.get("/", auth=("admin", "wrong"))
    assert response.status_code == 401
    
    # 3. Correct credentials -> 200
    response = client.get("/", auth=("admin", "secret"))
    assert response.status_code == 200
    
    response = client.get("/api/dashboard-data", auth=("admin", "secret"))
    assert response.status_code == 200
    assert "imap_alive" in response.json()

def test_dashboard_open_if_no_creds_configured(tmp_path, monkeypatch):
    db_path = tmp_path / "app.db"
    _init_db(db_path)

    monkeypatch.setenv("DB_PATH", str(db_path))
    monkeypatch.delenv("DASHBOARD_USERNAME", raising=False)
    monkeypatch.delenv("DASHBOARD_PASSWORD", raising=False)

    client = TestClient(app)
    
    # Should allow access as "admin"
    response = client.get("/")
    assert response.status_code == 200
