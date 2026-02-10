from __future__ import annotations

from pathlib import Path

from src.config import load_base_settings
from src.db import get_connection
from src.logging_utils import log_json


def main() -> None:
    settings = load_base_settings()
    db_path = Path(settings.db_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)

    schema_path = Path(__file__).resolve().parents[1] / "db" / "schema.sql"
    if not schema_path.exists():
        raise FileNotFoundError(f"Schema not found: {schema_path}")

    schema_sql = schema_path.read_text(encoding="utf-8")

    conn = get_connection(str(db_path))
    try:
        conn.executescript(schema_sql)
        conn.commit()
    finally:
        conn.close()

    log_json("info", "db_initialized", db_path=str(db_path))


if __name__ == "__main__":
    main()
