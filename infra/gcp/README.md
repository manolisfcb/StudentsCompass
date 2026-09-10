# Aprovisionamiento de Google Cloud (TASK-055)

Lo que estos scripts dejan listo: dos imágenes en Artifact Registry, una
identidad federada para GitHub Actions **sin ninguna clave JSON**, los secretos
en Secret Manager y una service account por carga de trabajo con el mínimo
privilegio. Desplegar los servicios es TASK-056; aquí no se despliega nada.

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
./99-verify.sh
```

Todos son idempotentes: re-ejecutarlos no duplica nada y es la forma de
reconciliar un proyecto que alguien tocó a mano.

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
| `sc-api` | `cloudsql.client`, `cloudtasks.enqueuer`, y `secretAccessor` **por secreto** | Habla con la base, encola el análisis de CV y lee los seis valores que necesita. No tiene `secretAccessor` a nivel de proyecto: un secreto nuevo no queda legible por el hecho de existir. |
| `sc-front` | ninguno | Sirve un bundle compilado y proxea. No lee ningún secreto, no llama a ninguna API de Google. La lista vacía es el diseño. |
| `sc-migrate` | `cloudsql.client`, `secretAccessor` sobre `DATABASE_URL` | Solo necesita llegar a la base con su URL. No publica imágenes ni despliega. |
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
repositorio indicado. TASK-056 restringe además por rama en el propio workflow.

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

Los scripts **no se han ejecutado**: no hay acceso a la consola ni a un proyecto
de Google Cloud desde este entorno. Lo que está comprobado es lo comprobable sin
él (ver arriba). Lo que queda pendiente, y por eso TASK-055 no se declara
COMPLETED, es la ejecución de `00`–`40` contra el proyecto real y la salida de
`99-verify.sh` en verde.
