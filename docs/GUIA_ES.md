# Guía en español

GenAI Release Lab permite comprobar si una versión puede liberarse con evidencia disponible. Los datos pertenecen a la organización ficticia Aster Systems y fueron creados para este portafolio.

Arranque: `docker compose up --build -d`. Abra http://localhost:3103. Usuarios DEMO: `operator`, `reviewer`, `viewer`; contraseña `demo-release`. El indicador DEMO permanece visible. No hay llamadas a modelos en este modo.

Como operador, seleccione el dataset de60 casos y la configuración Deterministic gate. Ejecute Reference fixture: el worker calcula60 aprobados de60. Ejecute Regression fixture:30 casos fallan por citas inventadas o argumentos alterados. Estos números describen fixtures, no calidad de un modelo real. Abra un fallo, revise expectativa/salida y compare ambas ejecuciones. La comparación señala diferencias y casos faltantes.

Seleccione Grounding required para ver una evaluación obligatoria pendiente: sin ejecución LIVE del juez, la liberación queda inconclusa. No se inventa puntuación. Con reviewer puede registrar una revisión humana y aprobar únicamente una ejecución con todos los criterios obligatorios resueltos. Las correcciones humanas conservan el resultado automatizado original.

Puede importar datasets y salidas JSON/JSONL, exportar JSON/JUnit/HTML y utilizar la CLI. Código0: aprobado;2: rechazado;3: inconcluso;4: entrada inválida. Consulte [operación](OPERATIONS.md) para activar LIVE con SDK OpenAI/Gemini o endpoints autorizados. Las integraciones LIVE están implementadas y probadas con transportes simulados; las llamadas a modelos quedan pendientes de credenciales; los endpoints externos necesitan además una salida de red directa permitida y un destino autorizado. Azure contiene configuración, sin despliegue realizado.

## Auditoría y reproducción

Consulte [audit.md](audit.md) para la instalación limpia aislada, los defectos reproducidos y corregidos, pruebas y limitaciones. El fallo HTTP 503 de la entrega original fue un bloqueo histórico; el registro actual distingue la nueva reconstrucción del uso de imágenes anteriores.

`./scripts/demo-local.sh` requiere Python/Node/Docker/uv y las cachés de `uv sync --frozen` y `npm ci`; no es una instalación inicial sin dependencias. La prueba destructiva de base de datos solo acepta `TEST_DATABASE_URL` con nombre terminado en `_test`, nunca la base de la aplicación. Las comparaciones excluyen casos cuyo contrato cambió y muestran resultados pendientes sin inventar una variación de calidad. El acceso LIVE permite nombres de usuario propios; si la configuración no se obtiene, el modo queda desconocido y no se presupone DEMO.
