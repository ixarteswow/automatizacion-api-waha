Si quieres retomar luego, el siguiente paso sería continuar con Semana 1 (DB + preguntas + scoring). Cuando vuelvas, solo dime “seguimos” y arrancamos desde ahí.
Token usage: total=404.801 input=372.185 (+ 867.968 cached) output=32.616 (reasoning 19.264)
To continue this session, run codex resume 019c2f10-1f33-7493-be9c-bc82fce3c042

# WAHA URL Webhook
http://api:8000/waha/message

# Crdenciales de Google
email: sinnombrename1@gmail.com
app: auto-python="szdz uuoo idfe xugc"

Fecha: 2026-02-08
- Nota: Se resolvio el problema de "no ver cambios" en Sheets al descubrir que se estaba viendo una tabla y no las hojas nuevas.
- Nota: Script final de plantilla DB completa listo (todas tablas + alias + derivadas + validaciones).
- Proximo: Implementar endpoints /export/{table} y script de pull para sincronizar con Google Sheets.

---

Invoke-WebRequest -Uri "http://localhost:8000/export/sesiones_leads" -Method Get -Headers @{ "X-API-KEY" = "password_1234" }
Invoke-WebRequest:                                                                                                      
{
  "detail": "Not Found"
}
Invoke-WebRequest -Uri "http://localhost:8000/export/sesiones_leads" -Method Get -SkipHttpErrorCheck | Select-Object StatusCode
Invoke-WebRequest: No se puede establecer una conexión ya que el equipo de destino denegó expresamente dicha conexión.
Invoke-WebRequest -Uri "http://localhost:8000/export/sesiones_leads" -Method Get -SkipHttpErrorCheck -Headers @{ "X-API-KEY" = "mal" } | Select-Object StatusCode
Invoke-WebRequest: No se puede establecer una conexión ya que el equipo de destino denegó expresamente dicha conexión.
Invoke-WebRequest -Uri "http://localhost:8000/export/sesiones_leads" -Method Get -Headers @{ "X-API-KEY" = "password_1234" }
Invoke-WebRequest: No se puede establecer una conexión ya que el equipo de destino denegó expresamente dicha conexión.

---

Fecha: 2026-02-09
- Nota: Endpoints `/export/{table}` listos con API key, cursor y filtro `updated_since`.
- Nota: Apps Script base en `scripts/apps_script_sync.gs`.
- Error resuelto: API caia por `NameError` de `_require_export_api_key` -> mover funcion antes del endpoint.
- Pendiente: Exponer API con URL publica (tunel o despliegue) para usar `API_URL` en Apps Script y ejecutar pull.

---

Fecha: 2026-02-10
- Nota: Repo en GitHub con tests versionados y `pytest.ini` (pythonpath=.) para evitar errores de import.
- Nota: Webhook ahora normaliza timestamps externos (ms->s) y busca sesion por telefono raw/normalizado.
- Nota: IMAP con busqueda server-side + fallback, labels condicionales Gmail y parsing HTML mejorado.
- Error resuelto: `pytest` fallaba por `ModuleNotFoundError: src` -> agregar `pytest.ini`.

---

Fecha: 2026-02-10
- Nota: Dashboard redisenado segun especificacion (KPIs, toolbar integrada, tabla con badges y barra de scoring).
- Nota: Busqueda en tiempo real + ordenacion por columnas + fechas relativas con tooltip.
- Error resuelto: Docker fallaba por `load_settings` en `scripts/setup_db.py` -> usar `load_base_settings`.
- Error resuelto: test de dashboard sin leads -> reintroducir estado vacio y proteger JS.

---

Fecha: 2026-02-10
- Nota: Pendiente reactivar modal por lead (click abre detalle).
- Nota: Pendiente cabecera superior con nombre de agente y fecha/hora.

---

Fecha: 2026-02-11
- Nota: Nombre oficial del diseño de dashboard definido como `Aurum Ledger`.
- Nota: Se implemento topbar con agente/fecha y modal de detalle por lead.
- Nota: Se aplico rediseño premium en CSS vanilla sin frameworks.
- Error resuelto: No se reflejaban cambios en UI por imagen vieja del contenedor `api` -> rebuild con `docker compose up -d --build api` + hard refresh.
- Nota: Cambios subidos a GitHub en `main` (commit `21b3835`).
