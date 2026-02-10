from src.domain.lead_profile_builder import build_lead_profile, score_from_answers


def test_build_profile_from_answers_text():
    answers = {
        "mascotas": "Si, un perro grande, pitbull",
        "fumador": "No, nadie fuma",
        "ocupantes": "3",
        "laboral": "Temporal, 4 meses",
        "sector": "Hosteleria",
        "ingresos": "2.500",
    }

    profile = build_lead_profile(
        answers, alquiler_mensual=950.0, metros_cuadrados=75.0
    )

    assert profile.tiene_mascotas is True
    assert profile.mascota_tipo == "perro"
    assert profile.mascota_tamano == "grande"
    assert profile.tiene_ppp is True
    assert profile.es_fumador is False
    assert profile.ocupantes == 3
    assert profile.contrato_tipo == "temporal"
    assert profile.antiguedad_meses == 4
    assert profile.sector == "hosteleria"
    assert profile.ingresos_mensuales == 2500.0


def test_score_from_answers_with_alias_keys():
    answers = {
        "p1": "No mascotas",
        "p2": "no",
        "p3": "2",
        "p4": "Temporal 2 meses",
        "p5": "it",
        "p6": "1200",
    }

    result = score_from_answers(
        answers, alquiler_mensual=700.0, metros_cuadrados=60.0
    )

    assert result.total == 0.0
    assert "ratio_esfuerzo" in result.killers
    assert "inestabilidad_laboral" in result.killers
