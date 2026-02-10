from email.message import EmailMessage

from src.services.imap_listener import extract_lead_fields, subject_matches, _extract_body_text


def _build_email(
    *,
    subject: str = "Nuevo lead Idealista",
    body_text: str | None = None,
    body_html: str | None = None,
    attachment: bytes | None = None,
) -> EmailMessage:
    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = "test@example.com"
    msg["To"] = "dest@example.com"

    if body_text and body_html:
        msg.set_content(body_text)
        msg.add_alternative(body_html, subtype="html")
    elif body_html:
        msg.add_alternative(body_html, subtype="html")
    else:
        msg.set_content(body_text or "")

    if attachment:
        msg.add_attachment(
            attachment,
            maintype="application",
            subtype="pdf",
            filename="file.pdf",
        )
    return msg


def test_extract_lead_fields_basic():
    text = "Hola,\nNombre: Nombre-OK-Verde\nTeléfono: 685587879"
    nombre, telefono = extract_lead_fields(text)
    assert nombre == "Nombre-OK-Verde"
    assert telefono == "685587879"


def test_extract_lead_fields_fallback_phone():
    text = "Hola,\nNombre: Ana\nTe dejo el movil 612345678 cuando puedas."
    nombre, telefono = extract_lead_fields(text)
    assert nombre == "Ana"
    assert telefono == "612345678"


def test_extract_body_text_html_only():
    msg = _build_email(
        body_html="<p>Nombre: Ana</p><p>Teléfono: 612345678</p>",
        body_text=None,
    )
    body = _extract_body_text(msg)
    nombre, telefono = extract_lead_fields(body)
    assert nombre == "Ana"
    assert telefono == "612345678"


def test_extract_body_text_multipart_with_attachment():
    msg = _build_email(
        body_text="Nombre: Ana\nTeléfono: 612345678",
        attachment=b"%PDF-1.4 fake",
    )
    body = _extract_body_text(msg)
    nombre, telefono = extract_lead_fields(body)
    assert nombre == "Ana"
    assert telefono == "612345678"


def test_subject_matches_keyword():
    assert subject_matches("Nuevo lead de Idealista", "Idealista") is True
    assert subject_matches("Factura mensual", "Idealista") is False
