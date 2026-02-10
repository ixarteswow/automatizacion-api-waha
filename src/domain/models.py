from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class LeadProfile:
    ingresos_mensuales: float
    alquiler_mensual: float
    metros_cuadrados: float
    ocupantes: int
    es_fumador: bool
    contrato_tipo: str
    antiguedad_meses: int
    sector: str
    tiene_mascotas: bool
    mascota_tipo: str | None = None
    mascota_tamano: str | None = None
    tiene_ppp: bool = False


@dataclass(frozen=True)
class ScoreBreakdown:
    ratio_esfuerzo: float
    estabilidad: float
    mascotas: float
    densidad: float
    sector: float
    fumador: float


@dataclass(frozen=True)
class ScoreResult:
    total: float
    label: str
    killers: list[str]
    breakdown: ScoreBreakdown
