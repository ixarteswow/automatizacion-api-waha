# RUNBOOK

## Registro de sesion
- Fecha: 2026-02-11
- Hecho: Se completo la mejora de dashboard con cabecera superior (agente + fecha/hora), modal por lead al hacer click en fila y rediseño visual premium.
- Decision: Se definio el nombre oficial del diseño como `Aurum Ledger` para referencia interna y continuidad de iteraciones.
- Error: Los cambios visuales no aparecian en el navegador tras editar plantillas/estilos. -> Solucion: reconstruir imagen y recrear contenedor `api` con `docker compose up -d --build api`, luego hard refresh.
- Hecho: Cambios subidos a GitHub en `main` con commit `21b3835`.
- Pendiente inmediato: Validar UX con datos reales y ajustar jerarquia/contraste segun feedback de uso.

## Proxima sesion (objetivos) - actualizado 2026-02-11
1. Probar `Aurum Ledger` con dataset real y revisar legibilidad en mobile.
2. Ajustar contenido del modal (campos y orden) segun prioridad operativa.
3. Definir si se mantiene ruta de Apps Script o se concentra reporting en dashboard/export CSV.

## Plan de trabajo - proxima sesion (2026-02-11)
1. Formalizar flujo E2E documentado: IMAP (`UNSEEN` + keyword `Idealista`) -> `POST /leads` -> WAHA preguntas 1..6 -> scoring -> dashboard.
2. Agregar mensaje de introduccion antes de la pregunta 1 al crear lead por correo.
3. Implementar validacion por tipo de pregunta antes de avanzar estado (`bool`, `number`, `text`) con repregunta en caso invalido.
4. Verificar y ajustar mensaje final por categoria:
   - `GOLD`: cierre premium con propuesta de agendamiento.
   - `SILVER`: cierre intermedio con llamada a accion clara.
   - `RED` u otra categoria: cierre informativo alternativo sin CTA agresivo.
5. Ejecutar prueba real controlada con al menos 2 correos `Idealista` y evidencias:
   - logs de `imap_listener` y webhook,
   - eventos en `eventos_sistema`,
   - estado final en `sesiones_leads`,
   - verificacion visual en dashboard.
6. Registrar resultados, incidencias y decisiones finales en `RUNBOOK.md` y `.notas/*`.
7. Definir esquema de trabajo con `/agent` para paralelizar sin conflictos:
   - coordinador con criterio de terminado,
   - ownership explicito por archivo para cada agente,
   - integracion final y validacion unica.
