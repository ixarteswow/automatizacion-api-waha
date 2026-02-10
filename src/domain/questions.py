from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Question:
    id: int
    key: str
    text: str
    context: str
    examples: list[str]
    validation_type: str


QUESTIONS: list[Question] = [
    Question(
        id=1,
        key="mascotas",
        text="Tienen mascotas? Que tipo y tamano? (Si es perro, indica raza)",
        context="Tipo de mascota, tamano y raza si aplica. Importa detectar perros PPP.",
        examples=[
            "No tenemos mascotas",
            "Si, un gato pequeno",
            "Tenemos un perro mediano, mestizo",
            "Perro pitbull",
        ],
        validation_type="text",
    ),
    Question(
        id=2,
        key="fumador",
        text="Hay alguna persona fumadora en el hogar?",
        context="Respuesta binaria si alguien fuma.",
        examples=["No, nadie fuma", "Si, fuma una persona"],
        validation_type="bool",
    ),
    Question(
        id=3,
        key="ocupantes",
        text="Cuantas personas viviran en el piso?",
        context="Numero total de ocupantes.",
        examples=["2 personas", "Somos 4"],
        validation_type="number",
    ),
    Question(
        id=4,
        key="laboral",
        text=(
            "Cual es la situacion laboral principal de los adultos y cuanto tiempo "
            "llevan en el trabajo actual?"
        ),
        context=(
            "Necesitamos tipo de contrato (funcionario, indefinido, temporal, autonomo, "
            "desempleado) y antiguedad en meses o anos."
        ),
        examples=[
            "Indefinido, llevo 3 anos",
            "Autonomo desde hace 2 anos",
            "Temporal, 4 meses",
            "Funcionario, 10 anos",
        ],
        validation_type="text",
    ),
    Question(
        id=5,
        key="sector",
        text="En que sector trabajan? (ej. sanidad, IT, hosteleria, construccion)",
        context="Sector profesional principal.",
        examples=["Sanidad", "IT", "Hosteleria"],
        validation_type="text",
    ),
    Question(
        id=6,
        key="ingresos",
        text="Cuales son los ingresos netos mensuales totales de todos los adultos?",
        context="Importe total mensual en euros.",
        examples=["Entre 2500 y 3000 EUR", "3200 euros"],
        validation_type="number",
    ),
]


QUESTIONS_BY_ID = {q.id: q for q in QUESTIONS}
