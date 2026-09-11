# Aprovisionamiento de Google Cloud (TASK-055, TASK-057)

Lo que estos scripts dejan listo: dos imágenes en Artifact Registry, una
identidad federada para GitHub Actions **sin ninguna clave JSON**, los secretos
en Secret Manager y una service account por carga de trabajo con el mínimo
privilegio (TASK-055); y, una vez que TASK-056 ha desplegado los servicios,
dominio, TLS, alertas y budget sobre ellos (TASK-057, `60`-`70`). Desplegar los
servicios en sí es `.github/workflows/deploy.yml`, TASK-056; ningún script de
este directorio lo hace.

Implementan la [ADR-001](../../docs/refactor/ADR-001-cloud-run-ingress.md) —
opción A, la API invocable tras el proxy Nginx del frontend— y **no la
re-deciden**.

## Por qué scripts idempotentes y no Terraform

Terraform sería mejor si su estado tuviera dónde vivir y su `plan` pudiera
compararse contra un proyecto real. Ninguna de las dos cosas es cierta todavía:
no hay bucket de estado porque no hay proyecto, y un módulo escrito a ciegas
aparenta una certeza que no tiene. Estos scripts son leíbles, re-ejecutables y
comprobables uno a uno, y `99-verify.sh` afirma el resultado contra el proyecto
en vez de contra un fichero de estado. Migrar a Terraform después es mecánico e
importará estos recursos; hacerlo antes habría sido escribir infraestructura que
nadie puede ejecutar.

## Orden

```bash
cd infra/gcp
cp config.env.example config.env   # y rellenar
./00-enable-apis.sh
./10-artifact-registry.sh
./20-service-accounts.sh
./30-workload-identity.sh
./40-secrets.sh
./50-cloud-tasks.sh
./99-verify.sh
# En este punto TASK-055 está listo. TASK-056 (deploy.yml) despliega los
# servicios. Solo entonces tienen sentido los dos siguientes:
./60-domain-mapping.sh    # requiere DOMAIN en config.env
./70-observability.sh     # requiere ALERT_EMAIL; BILLING_ACCOUNT_ID y BUDGET_AMOUNT son opcionales
```

Todos son idempotentes: re-ejecutarlos no duplica nada y es la forma de
reconciliar un proyecto que alguien tocó a mano.

## La base es Neon, y eso decide dos cosas

`DATABASE_URL` apunta a un Postgres serverless de Neon, no a Cloud SQL. De ahí
salen dos consecuencias que no son cosméticas:

1. **Ningún rol `cloudsql.client`.** Concederlo daría acceso a un servicio que
   este proyecto no usa, y le diría a quien audite esto mañana que sí lo usa.
2. **`ALEMBIC_DATABASE_URL` es obligatorio, no opcional.** El endpoint
   `-pooler` de Neon es PgBouncer en modo transacción, que no puede sostener los
   locks de sesión que toma Alembic. La app va por el pooler; el Job de
   migraciones va por el endpoint directo. Que `app/db.py` ya fije
   `statement_cache_size=0` es la otra mitad de la misma restricción.

## Qué secretos existen, y por qué esa lista

`_secrets.sh` es la única fuente: la crean `40-secrets.sh` y la comprueba
`99-verify.sh`. Antes había dos copias y divergieron — ambas nombraban
`APIFY_API_TOKEN`, que no lee ningún código, y a ninguna le constaba
`IMAGEKIT_PRIVATE_KEY`, que el servicio de media lee en cada subida. Un
despliegue cableado desde esa lista arranca limpio y falla en el primer avatar.

La lista sale de lo que el código **lee** (barrido de `os.getenv` / `env_str`
sobre `backend/app`), no de lo que el servicio vivo tiene puesto. Las dos cosas
no coinciden, y la que decide si una revisión funciona es el código.

## Los valores de los secretos no están aquí

`40-secrets.sh` crea los contenedores y concede acceso; **no** escribe valores.
Cada valor se añade a mano, una vez, desde un terminal:

```bash
gcloud secrets versions add SECRET_KEY --data-file=- --project "$PROJECT_ID"
# escribir el valor, Ctrl-D
```

`--data-file=-` mantiene el valor fuera de `argv` y del historial del shell. Un
valor que pasa por un script pasa también por los logs de ese script.

Rotar es añadir una versión nueva y desplegar: las referencias apuntan a
`versions/latest`, así que la revisión siguiente la toma. La versión anterior se
deshabilita **después** de comprobar que la nueva revisión arranca, nunca antes:
una rotación que rompe el arranque debe poder deshacerse.

## Qué puede hacer cada identidad

| Service account | Rol | Por qué exactamente eso |
| --- | --- | --- |
| `sc-api` | `cloudtasks.enqueuer` y `secretAccessor` **por secreto** | Encola el análisis de CV y lee los valores que necesita. No tiene `secretAccessor` a nivel de proyecto: un secreto nuevo no queda legible por el hecho de existir. **No** tiene `cloudsql.client`: la base es Neon, alcanzada por internet con una cadena de conexión, no Cloud SQL por el conector. |
| `sc-front` | ninguno | Sirve un bundle compilado y proxea. No lee ningún secreto, no llama a ninguna API de Google. La lista vacía es el diseño. |
| `sc-migrate` | ninguno de proyecto; `secretAccessor` sobre `DATABASE_URL` y `ALEMBIC_DATABASE_URL` | Llega a Neon con su URL y no necesita nada de ninguna API de Google. No publica imágenes ni despliega. |
| `sc-tasks` | ninguno de proyecto | Es la identidad que Cloud Tasks firma en el token OIDC. La API verifica este email exacto (`app/core/internalAuth.py`). Su poder es ser suplantada por la cola, no tener permisos. |
| `sc-deployer` | `artifactregistry.writer`, `run.developer`, `iam.serviceAccountUser` | Publica imágenes y despliega revisiones. **No** tiene `secretAccessor`: CI cablea referencias y nunca lee un valor, así que sus logs no pueden filtrar uno. |

## WIF, y qué sustituye exactamente

Una clave JSON de service account en los secretos de GitHub no caduca, no se
puede acotar por repositorio, funciona desde cualquier sitio y queda expuesta
entera a cada workflow que pueda leer secretos. La identidad federada se emite
por ejecución, caduca en minutos y solo para este repositorio.

Ese «solo para este repositorio» es la `--attribute-condition` de
`30-workload-identity.sh`, y **es la frontera de seguridad, no un filtro de
comodidad**: el emisor del token es `token.actions.githubusercontent.com`, así
que un token del repositorio de cualquier otra persona viene firmado igual de
válidamente que el nuestro. Sin la condición, cualquier repositorio de GitHub
podría cambiar su token por credenciales de este proyecto.

La segunda acotación está en el binding de impersonación, que solo alcanza al
repositorio indicado. La condición de atributo restringe además por rama
(`assertion.ref == 'refs/heads/main'`) desde la corrección de TASK-055 en
TASK-056: antes solo comprobaba el repositorio, y el comentario que prometía la
rama no tenía código detrás. `deploy.yml` (TASK-056) también comprueba la rama
en su propio `if`, pero esa comprobación vive en un fichero que cualquiera con
permiso de push puede editar — la que no se puede sortear así es la condición
de WIF, evaluada por Google antes de emitir el token.

### Lo que TASK-056 debe usar

Variables de Actions (son identificadores, no secretos; `30-workload-identity.sh`
los imprime):

- `GCP_WORKLOAD_IDENTITY_PROVIDER`
- `GCP_DEPLOYER_SERVICE_ACCOUNT`

```yaml
permissions:
  contents: read
  id-token: write        # sin esto no hay token OIDC que intercambiar

steps:
  - uses: google-github-actions/auth@v2
    with:
      workload_identity_provider: ${{ vars.GCP_WORKLOAD_IDENTITY_PROVIDER }}
      service_account: ${{ vars.GCP_DEPLOYER_SERVICE_ACCOUNT }}
```

Y los secretos se cablean **por referencia**, nunca por valor:

```bash
gcloud run deploy studentscompass-api \
  --set-secrets "DATABASE_URL=DATABASE_URL:latest,SECRET_KEY=SECRET_KEY:latest,..." \
  --service-account "sc-api@${PROJECT_ID}.iam.gserviceaccount.com"
```

`--set-env-vars` con un valor literal dejaría el secreto en texto plano dentro de
la definición del servicio, legible para siempre por cualquiera con `run.viewer`.

## La imagen del frontend no lleva secretos

Es una propiedad del `Dockerfile`, no una promesa: la etapa de runtime parte de
`nginx-unprivileged` y copia exactamente dos cosas, `nginx.conf` y `dist/`. No
hay `ARG` de build ni `ENV` con credenciales, y `API_ORIGIN` se sustituye en el
arranque del contenedor, no en el bundle (§11 del plan 08).

`backend/tests/test_deployment_configuration.py` lo comprueba en la lane rápida,
junto con la ausencia de claves JSON en el árbol y de valores literales en el
compose. Esas tres cosas se pueden verificar sin Google Cloud; lo demás lo
comprueba `99-verify.sh` contra el proyecto.

## Estado de la verificación

Ejecutados el **2026-09-10** contra `gen-lang-client-0908704200` (nombre: `teko`,
región `us-central1`), con `mmedinac26@gmail.com`:

| Script | Estado |
| --- | --- |
| `00-enable-apis.sh` | ✅ ejecutado |
| `10-artifact-registry.sh` | ✅ ejecutado |
| `20-service-accounts.sh` | ✅ ejecutado — cinco identidades creadas |
| `30-workload-identity.sh` | ✅ ejecutado — pool y provider acotados al repo |
| `40-secrets.sh` | ⛔ **pendiente** |
| `50-cloud-tasks.sh` | ✅ ejecutado — cola creada |
| `99-verify.sh` | ⚠️ todo en verde salvo los secretos |

`99-verify.sh` pasa Artifact Registry, la ausencia de claves JSON en las cinco
cuentas, el pool y la condición de repositorio de WIF, la cola y el binding de
impersonación de Cloud Tasks. Falla, y debe fallar, en los ocho secretos: no
existen todavía.

### El proyecto ya tenía un despliegue, hecho a mano

Esto no es un proyecto vacío. `studentscompass-api` lleva sirviendo desde el
commit `f9ca382` (2026-09-06) con `gcloud run deploy --source`, y su
configuración es lo contrario de lo que este directorio construye:

- los ocho valores están como **env vars literales**, no como referencias a
  Secret Manager, de modo que cualquiera con `run.viewer` los lee en claro y para
  siempre;
- corre como la **service account por defecto de Compute**, que trae
  `roles/editor` sobre todo el proyecto;
- no tiene `REDIS_URL` y sí `max-instances=20`, así que los rate limits por IP
  cuentan por proceso y no son los límites que dicen ser.

Los valores actuales **no deben copiarse** a Secret Manager: ya estuvieron
expuestos. La carga es también la rotación.

### Evidencia pendiente para que TASK-055 pase a COMPLETED

1. `40-secrets.sh` ejecutado y los ocho valores cargados, rotados, con
   `gcloud secrets versions add … --data-file=-`.
2. Un run del workflow que publique una imagen autenticándose por WIF, sin
   credencial estática almacenada. Necesita `deploy.yml`, que es TASK-056.
3. Los permisos efectivos de cada service account revisados contra la tabla de
   arriba (`gcloud projects get-iam-policy`).
4. Inspección de las dos imágenes construidas buscando secretos
   (`docker history` y `docker run --rm <img> env`).

Los puntos 2 a 4 dependen de que exista el pipeline; el 1 solo depende de tener
los valores rotados a mano.

## TASK-056 — `deploy.yml`

Vive en `.github/workflows/deploy.yml`, no en este directorio: es el pipeline,
no aprovisionamiento. Implementa la secuencia de plan 08 §10 — build, migrate
bloqueante, API sin tráfico, smoke contra la revisión etiquetada, promoción,
frontend, smoke público — y hace rollback automático a la revisión anterior si
algo falla después de promover.

Escrito pero **no ejecutado ni una vez**: nada de esto se ha corrido contra
`gen-lang-client-0908704200`. Cuando corra por primera vez, reemplazará el
despliegue hecho a mano (`gcloud run deploy --source`, sección de arriba) por
uno con secretos por referencia y la service account `sc-api` de mínimo
privilegio en vez de la de Compute por defecto — ese reemplazo es automático,
`gcloud run deploy` no conserva configuración que el comando nuevo no pida.

Depende de que `40-secrets.sh` tenga los ocho valores cargados: sin eso,
`--set-secrets` en el propio `deploy.yml` falla al desplegar porque el secreto
referenciado no tiene ninguna versión.

## TASK-057 — dominio, TLS, alertas y budget

`60-domain-mapping.sh` mapea `DOMAIN` a `$FRONT_SERVICE` y deja que Cloud Run
gestione el certificado; no hay paso manual de TLS más allá de crear los
registros DNS que el propio comando imprime.

`70-observability.sh` crea un canal de notificación por email, cuatro métricas
basadas en logs sobre campos que `backend/app/logging.py` ya escribe (429,
fallos de proveedor externo, jobs de CV fallidos tras gastar, techo de gasto de
IA alcanzado), seis políticas de alerta —esas cuatro más 5xx y p95 nativas de
Cloud Run— y un budget de facturación mensual. Cada política trae su propio
runbook en `documentation.content`, legible desde la propia alerta cuando
dispara.

Lo que **no** cubre, documentado en la salida del propio script: una métrica
real de pool de conexiones de DB. No existe hoy ni en logs ni en Cloud
Monitoring (SQLAlchemy no la expone; Neon no es Cloud SQL), así que su síntoma
—agotamiento— se alerta indirectamente vía la alerta de 5xx en vez de
inventarse una fuente de telemetría que TASK-028 no decidió emitir.

### Runbook de rollback por revisión

No hay comando especial: es el mismo que usa el job `rollback` de `deploy.yml`.

```bash
# Revisión que está sirviendo tráfico ahora mismo, por servicio:
gcloud run services describe studentscompass-api \
  --project "$PROJECT_ID" --region "$REGION" \
  --format='value(status.traffic.filter(percent:100).revisionName)'

# Volver a una revisión concreta (código anterior). Las migraciones nunca se
# revierten con esto: expand/contract (§12) es lo que hace que el código
# anterior siga funcionando contra el schema nuevo.
gcloud run services update-traffic studentscompass-api \
  --project "$PROJECT_ID" --region "$REGION" \
  --to-revisions REVISION_ANTERIOR=100

gcloud run services update-traffic studentscompass-front \
  --project "$PROJECT_ID" --region "$REGION" \
  --to-revisions REVISION_ANTERIOR=100
```

**No ensayado todavía.** El criterio de aceptación de TASK-057 pide un rollback
"ejecutado en staging, no solo documentado" — esto es la documentación; falta
desplegar de verdad, romper algo a propósito y medir cuánto tarda en volver a
servir, lo que a su vez espera a que TASK-056 haya corrido al menos una vez.
