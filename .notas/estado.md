# Punto de registro - Estado del proyecto

Fecha: 2026-02-07

## Estado actual
- API FastAPI creada: src/api.py
- Scoring y flujo integrados: src/services/session_flow.py, src/services/session_scoring.py
- Handler webhook listo: src/services/webhook_handler.py
- Notificaciones automaticas segun GOLD/SILVER/RED implementadas
  - Env: WAHA_BASE_URL, WAHA_SESSION, AGENT_NAME, CALENDLY_URL, RED_INFO_URL
  - Eventos: notification_sent / notification_failed / notification_skipped
- Docker listo con WAHA (api + waha)
- Parser WAHA actualizado (message.any, fromMe, _data.message.conversation)
- LOG_WEBHOOK_PAYLOAD desactivado
- Lead demo y eventos limpiados

## Pendiente
1. Reemplazar enlaces/agent de demo por datos reales cuando toque.

## Siguiente paso al retomar
- Usar el flujo real con leads reales.

---
Fecha: 2026-02-08

## Estado actual
- Plantilla Google Sheets v1 lista via Apps Script.
- Script final para plantilla DB completa preparado (todas tablas + alias + derivadas).
- Skill registra-sesion-runbook creada.

## Pendiente
1. Implementar Hito 2 export endpoints y Apps Script pull.

## Siguiente paso al retomar
- Agregar endpoints /export/{table} y Apps Script de sync incremental.

---
Fecha: 2026-02-09

## Estado actual
- Endpoints export `/export/{table}` listos con `X-API-KEY`, `updated_since`, `limit` y cursor.
- Apps Script base preparado (`scripts/apps_script_sync.gs`).

## Bloqueos
- Apps Script no puede acceder a `localhost`; falta URL publica para `API_URL`.

## Siguiente paso al retomar
- Exponer la API con un tunel/despliegue y configurar Script Properties en Apps Script.

---
Fecha: 2026-02-10

## Estado actual
- Repo en GitHub con `src/`, tests y `pytest.ini`.
- Webhook: normaliza timestamps ms->s, busca sesion por telefono raw/normalizado y registra mensajes procesados.
- IMAP: busqueda server-side con fallback, labels condicionales Gmail, logs de polling y parsing HTML mejorado.
- Config separada base vs scoring (scoring falla si faltan envs).

## Bloqueos
- Apps Script requiere URL publica para `API_URL`.

## Siguiente paso al retomar
- Exponer API y validar `pullLeads`/`pullEvents` desde Apps Script.
- Probar WAHA/IMAP reales en E2E.

---
Fecha: 2026-02-10

## Estado actual
- Dashboard local redisenado (header/KPIs/toolbar/tabla) con busqueda y ordenacion en cliente.
- Export CSV activo en `/export/leads.csv`.
- Conteos por categoria enviados por `dashboard_service`.
- Docker API OK (setup_db corregido a `load_base_settings`).

## Bloqueos
- Ninguno para el dashboard local.

## Siguiente paso al retomar
- Validar UI con datos reales y ajustar columnas/labels.
- Decidir si Apps Script sigue siendo necesario para reporting externo.

---
Fecha: 2026-02-10

## Estado actual
- Pendiente reactivar modal por lead (click en fila/telefono).
- Pendiente añadir cabecera superior con nombre del agente y fecha/hora.

## Siguiente paso al retomar
- Reactivar modal y diseñar la cabecera superior con datos del agente.

---
Fecha: 2026-02-11

## Estado actual
- Modal por lead reactivado (click en fila abre detalle con metadata y respuestas).
- Cabecera superior agregada (agente + fecha/hora en vivo).
- Diseño del dashboard renovado y nombrado oficialmente: `Aurum Ledger`.
- Cambios desplegados en contenedor `api` y publicados en GitHub (`main`, commit `21b3835`).

## Bloqueos
- Ninguno tecnico inmediato.

## Siguiente paso al retomar
- Validar UX/UI de `Aurum Ledger` con datos reales y ajustar columnas, contraste y orden del modal.
- Continuar decision de estrategia de reporting externo (Apps Script vs dashboard + CSV).

## Plan proxima sesion
1. Documentar como flujo oficial: correo `Idealista` no leido -> extraccion nombre/telefono -> encuesta WhatsApp 6 preguntas -> scoring -> dashboard.
2. Agregar mensaje de introduccion previo a la pregunta 1.
3. Implementar validacion por tipo de respuesta antes de cambiar de estado.
4. Garantizar mensaje final diferenciado por categoria (`GOLD`, `SILVER`, `RED/otra`).
5. Ejecutar prueba real con evidencias en logs + DB + dashboard.
6. Definir coordinacion con `/agent` (roles, archivos por agente y regla de no pisarse cambios).
