from __future__ import annotations

from dataclasses import dataclass
import os


def _get_env_str(key: str, default: str | None = None) -> str | None:
    value = os.getenv(key, default)
    if value is None:
        return None
    value = value.strip()
    return value if value else None


def _require_float(key: str) -> float:
    raw = _get_env_str(key)
    if raw is None:
        raise ValueError(f"Missing required env var: {key}")
    try:
        return float(raw)
    except ValueError as exc:
        raise ValueError(f"Invalid float for {key}: {raw}") from exc


@dataclass(frozen=True)
class Settings:
    db_path: str
    property_rent_eur: float
    property_sqm: float
    property_ref: str | None
    waha_base_url: str
    waha_api_key: str | None
    waha_session: str
    agent_name: str | None
    calendly_url: str | None
    red_info_url: str | None
    export_api_key: str | None


def load_settings() -> Settings:
    db_path = _get_env_str("DB_PATH", "data/app.db") or "data/app.db"
    property_rent_eur = _require_float("PROPERTY_RENT_EUR")
    property_sqm = _require_float("PROPERTY_SQM")
    property_ref = _get_env_str("PROPERTY_REF")
    waha_base_url = _get_env_str("WAHA_BASE_URL", "http://waha:3000") or "http://waha:3000"
    waha_api_key = _get_env_str("WAHA_API_KEY")
    waha_session = _get_env_str("WAHA_SESSION", "default") or "default"
    agent_name = _get_env_str("AGENT_NAME")
    calendly_url = _get_env_str("CALENDLY_URL")
    red_info_url = _get_env_str("RED_INFO_URL")
    export_api_key = _get_env_str("EXPORT_API_KEY")
    return Settings(
        db_path=db_path,
        property_rent_eur=property_rent_eur,
        property_sqm=property_sqm,
        property_ref=property_ref,
        waha_base_url=waha_base_url,
        waha_api_key=waha_api_key,
        waha_session=waha_session,
        agent_name=agent_name,
        calendly_url=calendly_url,
        red_info_url=red_info_url,
        export_api_key=export_api_key,
    )
