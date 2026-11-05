# Guía en español

GenAI Release Lab permite decidir si una versión puede liberarse con la evidencia disponible. Aster Systems es una organización ficticia; Northstar Sandbox es el nombre de su espacio en la interfaz. Los casos y respuestas incluidos son sintéticos y originales.

## Instalar y arrancar

Necesita Git y Docker Desktop, o Docker Engine con Compose v2, en ejecución. Reserve el puerto 3103. Para este recorrido no necesita instalar Python/Node, crear un `.env` ni disponer de API keys.

```bash
git clone https://github.com/giovannyTorres/genai-release-lab.git
cd genai-release-lab
docker compose up --build -d --wait
```

Abra **http://localhost:3103**. Las migraciones y los datos iniciales se preparan automáticamente. El primer build descarga imágenes y dependencias fijadas. `docker compose ps` muestra la salud de los servicios.

Las cuentas `operator`, `reviewer` y `viewer` usan la contraseña **`demo-release`**. El operador crea datasets, políticas y ejecuciones; el supervisor (`reviewer`) registra revisiones y aprueba decisiones elegibles; el lector (`viewer`) consulta. Los permisos se verifican en backend. DEMO nunca llama a modelos.

## Recorrido de dos minutos

1. Entre como **operator** y pulse **New evaluation**. Seleccione **Aster assurance suite**, **Deterministic gate** y **Reference · expected behavior**. Al terminar debe mostrar **60/60**, **Approved**.
2. Repita con **Regression · deliberate failures**: **30/60**, **Rejected**. Abra un fallo y revise su expectativa, salida y comprobaciones.
3. En **Compare versions**, elija ambas ejecuciones y pulse **Compare runs**. Revise los casos pareados y las regresiones. Desde una ejecución puede exportar JSON, JUnit o HTML.
4. Ejecute la referencia con **Grounding required**. La evaluación obligatoria del juez queda pendiente y el resultado **Inconclusive**; no se inventa una puntuación ni se permite aprobarlo.
5. Cierre sesión con **Sign out** y entre como **reviewer**. Registre una revisión humana y apruebe la referencia terminada. Las correcciones conservan el resultado automatizado original.

Estas cifras describen fixtures, no calidad de un modelo real. Las comparaciones excluyen contratos de casos modificados y muestran evidencia faltante. Consulte el [guion de presentación](DEMO.md) y los [formatos de importación](../fixtures/README.md).

## Parar y conservar datos

```bash
docker compose down
docker compose up -d --wait
```

El primer comando detiene la aplicación sin borrar el volumen PostgreSQL; el segundo reanuda las imágenes existentes. **`docker compose down -v` borra los datos** y no es una parada normal. Si falla el arranque, use `docker compose logs --tail=80 migrate api worker web`. Las instrucciones de [operación](OPERATIONS.md) incluyen el ajuste de certificados para entornos administrados; no desactive TLS.

## Prueba rápida sin Docker

Con Python 3.12, uv 0.13.4 y GNU Make (Linux/macOS/WSL), desde la raíz:

```bash
uv sync --frozen
make quickcheck
```

El resultado esperado es **5 passed**. Reutiliza pruebas existentes de fixtures, persistencia, exportación, autorización, evaluaciones pendientes y códigos de salida reales de la CLI. El comando fuerza SQLite temporal: no necesita una base externa, servidor ni credenciales. Los códigos CLI son **0 aprobado**, **2 rechazado**, **3 inconcluso** y **4 entrada inválida**; la prueba reconoce los rechazos deliberados como resultados esperados.

Para la validación completa, el [README](../README.md#full-development-checks) documenta lint, tipos, backend, frontend, build, instalación de Chromium y Playwright. Las pruebas PostgreSQL solo aceptan una base desechable mediante `TEST_DATABASE_URL`, cuyo nombre termina en `_test`; nunca use la base de la aplicación. El [registro de auditoría](audit.md) contiene los comandos aislados y la evidencia de ejecución.

## LIVE y límites de la demostración

Puede instalar y revisar todo el proyecto sin claves. La [guía de operación](OPERATIONS.md#live-explicit-opt-in) explica la configuración backend y los smoke tests optativos cuando disponga de credenciales. OpenAI y Gemini están implementados con SDK oficiales y transportes simulados; las llamadas reales a modelos siguen pendientes. No hay cambio silencioso a DEMO ante errores.

Los endpoints externos requieren un destino autorizado y salida directa permitida. El acceso LIVE admite nombres de usuario propios; si la configuración no se obtiene, la interfaz muestra modo desconocido. Azure contiene configuración sin despliegue realizado. Revise el [modelo de confianza](SECURITY.md) y la [verificación](VERIFICATION.md) para distinguir implementación, contratos simulados y comprobaciones externas.

El arranque alternativo `./scripts/demo-local.sh` necesita herramientas host y cachés previamente pobladas; no es una instalación inicial sin dependencias. El bloqueo HTTP503 original fue resuelto durante la auditoría mediante nuevas reconstrucciones Docker y un volumen limpio.
