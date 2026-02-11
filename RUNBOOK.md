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
