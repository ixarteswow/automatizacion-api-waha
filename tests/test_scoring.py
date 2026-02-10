from src.domain.models import LeadProfile
from src.domain.scoring import compute_score


def test_compute_score_happy_path():
    profile = LeadProfile(
        ingresos_mensuales=3200.0,
        alquiler_mensual=950.0,
        metros_cuadrados=80.0,
        ocupantes=2,
        es_fumador=False,
        contrato_tipo="indefinido",
        antiguedad_meses=24,
        sector="sanidad",
        tiene_mascotas=False,
    )

    result = compute_score(profile)
    assert result.total > 0
    assert result.label in {"GOLD", "SILVER"}
    assert result.killers == []


def test_killer_ratio_esfuerzo():
    profile = LeadProfile(
        ingresos_mensuales=1200.0,
        alquiler_mensual=700.0,
        metros_cuadrados=60.0,
        ocupantes=2,
        es_fumador=False,
        contrato_tipo="indefinido",
        antiguedad_meses=12,
        sector="it",
        tiene_mascotas=False,
    )

    result = compute_score(profile)
    assert result.total == 0
    assert "ratio_esfuerzo" in result.killers
