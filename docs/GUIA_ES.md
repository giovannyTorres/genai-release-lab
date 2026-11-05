# Guía en español

GenAI Release Lab permite comprobar si una versión puede liberarse con evidencia disponible. Los datos pertenecen a la organización ficticia Aster Systems y fueron creados para este portafolio.

Arranque: `docker compose up --build -d`. Abra http://localhost:3103. Usuarios DEMO: `operator`, `reviewer`, `viewer`; contraseña `demo-release`. El indicador DEMO permanece visible. No hay llamadas a modelos en este modo.

Como operador, seleccione el dataset de60 casos y la configuración Deterministic gate. Ejecute Reference fixture: el worker calcula60 aprobados de60. Ejecute Regression fixture:30 casos fallan por citas inventadas o argumentos alterados. Estos números describen fixtures, no calidad de un modelo real. Abra un fallo, revise expectativa/salida y compare ambas ejecuciones. La comparación señala diferencias y casos faltantes.

Seleccione Grounding required para ver una evaluación obligatoria pendiente: sin ejecución LIVE del juez, la liberación queda inconclusa. No se inventa puntuación. Con reviewer puede registrar una revisión humana y aprobar únicamente una ejecución con todos los criterios obligatorios resueltos. Las correcciones humanas conservan el resultado automatizado original.

Puede importar datasets y salidas JSON/JSONL, exportar JSON/JUnit/HTML y utilizar la CLI. Código0: aprobado;2: rechazado;3: inconcluso;4: entrada inválida. Consulte [operación](OPERATIONS.md) para activar LIVE con SDK OpenAI/Gemini o endpoints autorizados. Las integraciones LIVE están implementadas y probadas con transportes simulados; las llamadas reales quedan pendientes de credenciales. Azure contiene configuración, sin despliegue realizado.

## Arranque verificado en este entorno

El proxy del entorno dejó de responder y devolvió HTTP503 al reconstruir las imágenes finales (PyPI y Docker Hub). Por ello no se afirma que el despliegue completo en contenedores haya sido verificado. La alternativa comprobada es `./scripts/demo-local.sh`: usa PostgreSQL real en Docker, API y worker locales, y Next en modo producción. Requiere las dependencias congeladas en caché, ya presentes en este workspace. Consulta VERIFICATION.md para distinguir esa validación de Docker Compose completo y de las pruebas LIVE pendientes.
