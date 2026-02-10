from __future__ import annotations

import json
import re
import unicodedata
from typing import Any, Mapping

from .models import LeadProfile
from .scoring import HIGH_SECTORS, LOW_SECTORS, MEDIUM_SECTORS, PPP_BREEDS, compute_score

ANSWER_KEY_ALIASES = {
    "mascotas": ("mascotas", "p1"),
    "fumador": ("fumador", "p2"),
    "ocupantes": ("ocupantes", "p3"),
    "laboral": ("laboral", "p4"),
    "sector": ("sector", "p5"),
    "ingresos": ("ingresos", "p6"),
}


def build_lead_profile(
    answers: Mapping[str, Any] | str,
    *,
    alquiler_mensual: float,
    metros_cuadrados: float,
) -> LeadProfile:
    if alquiler_mensual <= 0 or metros_cuadrados <= 0:
        raise ValueError("Property values must be positive")

    data = _coerce_answers(answers)
    mascotas_raw = _get_answer(data, ANSWER_KEY_ALIASES["mascotas"])
    fumador_raw = _get_answer(data, ANSWER_KEY_ALIASES["fumador"])
    ocupantes_raw = _get_answer(data, ANSWER_KEY_ALIASES["ocupantes"])
    laboral_raw = _get_answer(data, ANSWER_KEY_ALIASES["laboral"])
    sector_raw = _get_answer(data, ANSWER_KEY_ALIASES["sector"])
    ingresos_raw = _get_answer(data, ANSWER_KEY_ALIASES["ingresos"])

    tiene_mascotas, mascota_tipo, mascota_tamano, tiene_ppp = _parse_mascotas(
        mascotas_raw
    )
    es_fumador = _parse_bool(fumador_raw, field_name="fumador")
    ocupantes = _parse_int(ocupantes_raw, field_name="ocupantes")
    contrato_tipo, antiguedad_meses = _parse_contrato(laboral_raw)
    sector = _parse_sector(sector_raw)
    ingresos = _parse_float(ingresos_raw, field_name="ingresos")

    return LeadProfile(
        ingresos_mensuales=ingresos,
        alquiler_mensual=alquiler_mensual,
        metros_cuadrados=metros_cuadrados,
        ocupantes=ocupantes,
        es_fumador=es_fumador,
        contrato_tipo=contrato_tipo,
        antiguedad_meses=antiguedad_meses,
        sector=sector,
        tiene_mascotas=tiene_mascotas,
        mascota_tipo=mascota_tipo,
        mascota_tamano=mascota_tamano,
        tiene_ppp=tiene_ppp,
    )


def score_from_answers(
    answers: Mapping[str, Any] | str,
    *,
    alquiler_mensual: float,
    metros_cuadrados: float,
):
    profile = build_lead_profile(
        answers, alquiler_mensual=alquiler_mensual, metros_cuadrados=metros_cuadrados
    )
    return compute_score(profile)


def _coerce_answers(raw: Mapping[str, Any] | str) -> dict[str, Any]:
    if isinstance(raw, Mapping):
        return dict(raw)
    if isinstance(raw, str):
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise ValueError("answers must be a mapping or JSON string") from exc
        if not isinstance(parsed, Mapping):
            raise ValueError("answers JSON must be an object")
        return dict(parsed)
    raise ValueError("answers must be a mapping or JSON string")


def _get_answer(data: Mapping[str, Any], keys: tuple[str, ...]) -> Any:
    for key in keys:
        if key in data:
            return data[key]
    raise ValueError(f"Missing required answer: {keys[0]}")


def _normalize(text: str) -> str:
    normalized = unicodedata.normalize("NFKD", text)
    normalized = normalized.encode("ascii", "ignore").decode("ascii")
    normalized = normalized.strip().lower()
    normalized = re.sub(r"\s+", " ", normalized)
    return normalized


def _parse_bool(value: Any, *, field_name: str) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        raise ValueError(f"Missing value for {field_name}")
    text = _normalize(str(value))
    if re.search(r"\b(no|nadie|ningun|ninguna|ninguno)\b", text):
        return False
    if re.search(r"\b(si|claro|afirmativo)\b", text):
        return True
    if text.isdigit():
        return bool(int(text))
    raise ValueError(f"Invalid boolean value for {field_name}: {value}")


def _parse_int(value: Any, *, field_name: str) -> int:
    number = _parse_float(value, field_name=field_name)
    return int(round(number))


def _parse_float(value: Any, *, field_name: str) -> float:
    if isinstance(value, (int, float)):
        return float(value)
    if value is None:
        raise ValueError(f"Missing value for {field_name}")
    text = _normalize(str(value))
    cleaned = re.sub(r"[^0-9,\.]", "", text)
    if not cleaned:
        raise ValueError(f"Invalid numeric value for {field_name}: {value}")
    if "," in cleaned and "." in cleaned:
        if cleaned.rfind(",") > cleaned.rfind("."):
            cleaned = cleaned.replace(".", "").replace(",", ".")
        else:
            cleaned = cleaned.replace(",", "")
    elif "," in cleaned:
        cleaned = cleaned.replace(",", ".")
    elif "." in cleaned:
        parts = cleaned.split(".")
        if len(parts[-1]) == 3 and all(part.isdigit() for part in parts):
            cleaned = "".join(parts)
    try:
        return float(cleaned)
    except ValueError as exc:
        raise ValueError(f"Invalid numeric value for {field_name}: {value}") from exc


def _parse_contrato(value: Any) -> tuple[str, int]:
    if value is None:
        return "desconocido", 0
    text = _normalize(str(value))
    contrato = "desconocido"
    for token in ("funcionario", "indefinido", "autonomo", "temporal", "desempleado"):
        if token in text:
            contrato = token
            break
    if contrato == "desconocido" and "paro" in text:
        contrato = "desempleado"
    meses = _extract_meses(text)
    return contrato, meses


def _extract_meses(text: str) -> int:
    numbers = [int(x) for x in re.findall(r"\d+", text)]
    if not numbers:
        return 0
    value = numbers[0]
    if "ano" in text or "year" in text:
        return value * 12
    if "mes" in text:
        return value
    return value


def _parse_sector(value: Any) -> str:
    if value is None:
        return "desconocido"
    text = _normalize(str(value))
    for sector in HIGH_SECTORS | MEDIUM_SECTORS | LOW_SECTORS:
        if sector in text:
            return sector
    if not text:
        return "desconocido"
    return text.split()[0]


def _parse_mascotas(value: Any) -> tuple[bool, str | None, str | None, bool]:
    if isinstance(value, Mapping):
        tiene_mascotas = bool(value.get("tiene_mascotas", True))
        mascota_tipo = value.get("tipo") or value.get("mascota_tipo")
        mascota_tamano = value.get("tamano") or value.get("mascota_tamano")
        raza = value.get("raza") or value.get("breed")
        tiene_ppp = bool(value.get("tiene_ppp", False))
        if raza and not tiene_ppp:
            if _contains_ppp(_normalize(str(raza))):
                tiene_ppp = True
        return tiene_mascotas, _normalize_str(mascota_tipo), _normalize_str(
            mascota_tamano
        ), tiene_ppp

    if isinstance(value, bool):
        if not value:
            return False, None, None, False
        text = ""
    else:
        if value is None:
            return False, None, None, False
        text = _normalize(str(value))

    if _looks_like_no_pets(text):
        return False, None, None, False

    tipo = None
    if "gato" in text:
        tipo = "gato"
    if "perro" in text:
        tipo = "perro"

    tamano = None
    for token, label in (
        ("muy grande", "muy grande"),
        ("grande", "grande"),
        ("mediano", "mediano"),
        ("pequeno", "pequeno"),
        ("peque", "pequeno"),
    ):
        if token in text:
            tamano = label
            break

    tiene_ppp = _contains_ppp(text)
    return True, tipo, tamano, tiene_ppp


def _looks_like_no_pets(text: str) -> bool:
    if not text:
        return False
    if "no" in text and "mascot" in text:
        return True
    if re.search(r"\b(no|ningun|ninguna|sin)\b", text):
        return True
    return False


def _contains_ppp(text: str) -> bool:
    if "ppp" in text:
        return True
    for breed in PPP_BREEDS:
        if breed in text:
            return True
    return False


def _normalize_str(value: Any) -> str | None:
    if value is None:
        return None
    text = _normalize(str(value))
    return text or None
