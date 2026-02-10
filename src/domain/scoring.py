from __future__ import annotations

from .models import LeadProfile, ScoreBreakdown, ScoreResult

WEIGHTS = {
    "ratio_esfuerzo": 0.30,
    "estabilidad": 0.25,
    "mascotas": 0.15,
    "densidad": 0.15,
    "sector": 0.10,
    "fumador": 0.05,
}

PPP_BREEDS = {
    "pitbull",
    "pit bull",
    "american staffordshire",
    "staffordshire bull",
    "rottweiler",
    "dogo argentino",
    "fila brasileiro",
    "tosa inu",
    "akita inu",
}

HIGH_SECTORS = {
    "sanidad",
    "salud",
    "it",
    "tecnologia",
    "informatica",
    "ingenieria",
    "finanzas",
    "publico",
    "administracion",
}

MEDIUM_SECTORS = {
    "educacion",
    "logistica",
    "comercio",
    "retail",
    "industria",
}

LOW_SECTORS = {
    "hosteleria",
    "construccion",
    "turismo",
    "eventos",
}


def _normalize(text: str) -> str:
    return text.strip().lower()


def _clamp(value: float, low: float = 0.0, high: float = 100.0) -> float:
    return max(low, min(high, value))


def score_ratio_esfuerzo(alquiler_mensual: float, ingresos_mensuales: float) -> float:
    if ingresos_mensuales <= 0 or alquiler_mensual <= 0:
        return 0.0
    ratio = alquiler_mensual / ingresos_mensuales
    if ratio <= 0.30:
        return 100.0
    if ratio >= 0.45:
        return 0.0
    score = 100.0 * (0.45 - ratio) / 0.15
    return _clamp(round(score, 2))


def score_estabilidad(contrato_tipo: str, antiguedad_meses: int) -> float:
    contrato = _normalize(contrato_tipo)
    meses = max(0, antiguedad_meses)
    if contrato == "funcionario":
        return 100.0
    if contrato == "indefinido":
        if meses >= 24:
            return 100.0
        if meses >= 12:
            return 85.0
        if meses >= 6:
            return 70.0
        return 60.0
    if contrato == "autonomo":
        if meses >= 24:
            return 80.0
        if meses >= 12:
            return 65.0
        return 55.0
    if contrato == "temporal":
        if meses >= 6:
            return 30.0
        return 10.0
    if contrato == "desempleado":
        return 0.0
    return 50.0


def score_mascotas(
    tiene_mascotas: bool,
    mascota_tipo: str | None,
    mascota_tamano: str | None,
    tiene_ppp: bool,
) -> float:
    if not tiene_mascotas:
        return 100.0
    if tiene_ppp:
        return 0.0
    tipo = _normalize(mascota_tipo or "")
    tamano = _normalize(mascota_tamano or "")
    if tipo == "gato":
        return 60.0
    if tipo == "perro" and tamano in {"grande", "muy grande"}:
        return 20.0
    if tipo == "perro":
        return 40.0
    return 50.0


def score_densidad(metros_cuadrados: float, ocupantes: int) -> float:
    if metros_cuadrados <= 0 or ocupantes <= 0:
        return 0.0
    densidad = metros_cuadrados / ocupantes
    if densidad >= 40.0:
        return 100.0
    if densidad <= 20.0:
        return 50.0
    score = 50.0 + (densidad - 20.0) * 2.5
    return _clamp(round(score, 2))


def score_sector(sector: str) -> float:
    sector_norm = _normalize(sector)
    if sector_norm in HIGH_SECTORS:
        return 100.0
    if sector_norm in MEDIUM_SECTORS:
        return 70.0
    if sector_norm in LOW_SECTORS:
        return 40.0
    return 60.0


def score_fumador(es_fumador: bool) -> float:
    return 0.0 if es_fumador else 100.0


def evaluate_killers(profile: LeadProfile) -> list[str]:
    killers: list[str] = []

    if profile.ingresos_mensuales <= 0 or profile.alquiler_mensual <= 0:
        killers.append("ratio_esfuerzo_invalido")
    else:
        ratio = profile.alquiler_mensual / profile.ingresos_mensuales
        if ratio > 0.45:
            killers.append("ratio_esfuerzo")

    if profile.metros_cuadrados <= 0 or profile.ocupantes <= 0:
        killers.append("densidad_invalida")
    else:
        densidad = profile.metros_cuadrados / profile.ocupantes
        if densidad < 15.0:
            killers.append("densidad")

    if profile.tiene_ppp:
        killers.append("ppp")

    contrato = _normalize(profile.contrato_tipo)
    if contrato == "desempleado":
        killers.append("inestabilidad_laboral")
    if contrato == "temporal" and profile.antiguedad_meses < 6:
        killers.append("inestabilidad_laboral")

    return killers


def compute_score(profile: LeadProfile) -> ScoreResult:
    breakdown = ScoreBreakdown(
        ratio_esfuerzo=score_ratio_esfuerzo(
            profile.alquiler_mensual, profile.ingresos_mensuales
        ),
        estabilidad=score_estabilidad(profile.contrato_tipo, profile.antiguedad_meses),
        mascotas=score_mascotas(
            profile.tiene_mascotas,
            profile.mascota_tipo,
            profile.mascota_tamano,
            profile.tiene_ppp,
        ),
        densidad=score_densidad(profile.metros_cuadrados, profile.ocupantes),
        sector=score_sector(profile.sector),
        fumador=score_fumador(profile.es_fumador),
    )

    killers = evaluate_killers(profile)
    if killers:
        return ScoreResult(total=0.0, label="RED", killers=killers, breakdown=breakdown)

    weighted_total = (
        breakdown.ratio_esfuerzo * WEIGHTS["ratio_esfuerzo"]
        + breakdown.estabilidad * WEIGHTS["estabilidad"]
        + breakdown.mascotas * WEIGHTS["mascotas"]
        + breakdown.densidad * WEIGHTS["densidad"]
        + breakdown.sector * WEIGHTS["sector"]
        + breakdown.fumador * WEIGHTS["fumador"]
    )
    total = round(weighted_total, 2)

    if total > 85.0:
        label = "GOLD"
    elif total >= 60.0:
        label = "SILVER"
    else:
        label = "RED"

    return ScoreResult(total=total, label=label, killers=killers, breakdown=breakdown)
