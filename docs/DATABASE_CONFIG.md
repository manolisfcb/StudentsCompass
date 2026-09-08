# Configuración de base de datos y rotación de credenciales

Origen: TASK-002 / hallazgo F-01 del [tablero de refactor](refactor/TASKS.md).
Este documento no contiene ningún valor secreto y no debe contenerlo nunca.

Desde TASK-037 el árbol Python vive bajo `backend/`, y con él `alembic.ini`,
`alembic/` y `scripts/`. Los comandos de este documento se ejecutan desde ese
directorio (`cd backend`); las rutas citadas en el texto son relativas a él.

## Un solo destino

La aplicación y el migrador resuelven la base de datos desde la **misma**
variable, para que una migración no pueda aplicarse a un servidor distinto del
que usa la app:

| Componente | Variable | Notas |
| --- | --- | --- |
| Aplicación | `DATABASE_URL` | `app/db.py`; driver async (`postgresql+asyncpg`) |
| Alembic | `ALEMBIC_DATABASE_URL`, si no `DATABASE_URL` | `alembic/env.py`; traduce el driver async al síncrono equivalente |
| `scripts/migrate_sqlite_to_postgres.py` | `POSTGRES_URL` | Sin valor por defecto; el operador nombra el destino |

`alembic.ini` **no** declara `sqlalchemy.url`. La línea está comentada a
propósito: un valor ahí volvería a versionar una credencial y permitiría que el
migrador divergiera de la app. `alembic/env.py` la inyecta en tiempo de
ejecución.

`ALEMBIC_DATABASE_URL` existe solo para el caso en que el migrador necesite el
endpoint directo mientras la app pasa por un pooler (PgBouncer en modo
transacción). Si no se define, se usa `DATABASE_URL`.

Si ninguna está configurada, el proceso falla en el arranque con un mensaje
explícito. No hay fallback silencioso.

### Comprobar el destino antes de migrar

Cada ejecución online imprime el destino **redactado** (esquema, host y base; sin
usuario ni contraseña):

```
alembic: migrating postgresql+psycopg://HOST/DATABASE
```

Léelo antes de confirmar cualquier `upgrade`. En local, `.env` define
`DATABASE_URL`, de modo que un `alembic upgrade head` sin variables explícitas
apunta a lo que diga `.env` — que puede ser producción. Exporta
`ALEMBIC_DATABASE_URL` hacia una base desechable cuando estés probando:

```bash
ALEMBIC_DATABASE_URL='postgresql+psycopg://testuser:testpw@127.0.0.1:55432/studentscompass_test' \
  ../.venv/bin/alembic upgrade head
```

## Dos rutas de schema: baseline e histórico (F-08, F-20)

`alembic upgrade head` hace **dos cosas distintas** según con qué se encuentre,
y la diferencia importa antes de tocar cualquier despliegue.

### Base existente — cadena histórica, forward-only

Si la base tiene tablas, `env.py` ejecuta la cadena normal desde la revisión en
la que esté marcada. No cambia nada respecto a lo anterior.

### Base vacía — baseline verificado

La cadena histórica **no se puede reproducir desde cero**, y no es un detalle
recuperable editando revisiones:

- la raíz `025e4d7c446f` hace `ADD COLUMN` sobre `users` sin que ninguna
  revisión cree la tabla;
- `4897b7743b34` hace `DROP TABLE job_analysis` y ninguna revisión posterior la
  recrea, pero `1720e86014a0` y `e1f7c2b9a4d3` siguen alterándola;
- `73a6e7c411b9` hace `DROP TABLE applications` antes de que nada la cree.

Esas revisiones ya están aplicadas en producción, así que **no se editan**:
corregirlas reescribiría un historial por el que la base desplegada ya pasó.

En su lugar, una base vacía se construye desde `app/db_baseline.py`, que
contiene el DDL explícito del schema actual (generado desde `Base.metadata` y
versionado, no un `create_all` en tiempo de despliegue). El proceso es:

1. `database_is_empty()` — solo si no hay **ninguna** tabla; `alembic_version`
   sola ya cuenta como instalación existente.
2. `create_schema()` — DDL explícito.
3. `verify_against_metadata()` — se reintrospecta la base recién creada y se
   compara con la metadata mapeada.
4. Solo con **cero diferencias** se hace `stamp head`. Si hay alguna, se lanza
   `BaselineVerificationError` y la base queda **sin marcar**.

Las bases creadas así son forward-only: `alembic downgrade` ejecutaría
revisiones históricas por cuyo estado inicial nunca pasaron.

### Regenerar el baseline tras un cambio de schema

Contra una base desechable. `alembic stamp` **no** sirve aquí: una base vacía
entra por el baseline, así que `stamp` intentaría bootstrapear. Se siembra
`alembic_version` con SQL:

```sql
CREATE TABLE alembic_version (version_num varchar(32) NOT NULL,
    CONSTRAINT alembic_version_pkc PRIMARY KEY (version_num));
INSERT INTO alembic_version VALUES ('<head actual>');
```

```bash
ALEMBIC_DATABASE_URL='postgresql+psycopg://testuser:testpw@127.0.0.1:55432/studentscompass_test' \
  ../.venv/bin/alembic revision --autogenerate -m "snapshot"
```

y se traslada el cuerpo de `upgrade()` generado a `create_schema()`. El test
`tests/integration/test_migrations.py::test_bootstrapped_schema_matches_metadata`
falla si el baseline se queda atrás.

### El manifest de modelos

`Base.metadata` solo está completa si se han importado todos los módulos de
modelos. `env.py` y `tests/conftest.py` mantenían cada uno su propia lista, y
`roadmapModel` y `resumeCourseEvaluationModel` faltaban en la de Alembic: para
autogenerate esas tablas no existían. Ahora ambos importan
`app/models/registry.py`, y `tests/test_model_manifest.py` recorre
`app/models/` y falla si un modelo mapeado no está en el manifest.

Por el mismo motivo hay índices declarados ahora en los modelos que antes solo
existían en migraciones: `1720e86014a0` fue autogenerada con metadata incompleta
y **borró** un lote de índices funcionales precisamente porque no tenían
contrapartida en los modelos.

### Convergencia de `resource_lesson_progress` (F-20)

Dos ramas crearon la tabla con shapes distintos y solo una protegía su
`CREATE TABLE`, así que el shape de cada base depende del orden en que Alembic
recorrió las ramas. La revisión `a7f4c2b8d590` las reconcilia sin perder datos:
añade `resource_id` si falta y lo rellena por `lesson -> module -> resource`,
añade `created_at`/`updated_at` si faltan, y **relaja** a nullable
`resource_id`, `completed_at` y `last_opened_at` — el lado permisivo de cada
desacuerdo. El backfill solo toca filas con `NULL`, así que reejecutarlo es
seguro si la migración se interrumpe.

`resource_enrollments` se conserva y ahora está mapeada. No tiene consumidores,
pero retirarla exige inventario de datos desplegados y es una tarea destructiva
aparte; mapearla evita que autogenerate proponga borrarla.

## Estado del hallazgo F-01

La URL versionada en `alembic.ini` y en `scripts/migrate_sqlite_to_postgres.py`
contenía usuario y contraseña del proyecto Neon de producción, y coincidía con
la credencial que la aplicación usa en `.env`. Los literales ya están retirados
del árbol de trabajo, pero:

> **Siguen en el historial de Git** (`git log -S` los localiza en el commit que
> introdujo `alembic.ini`). Retirar el literal **no** revoca la credencial.
> Mientras no se rote, cualquiera con acceso al repositorio —incluido cualquier
> clon o fork existente— conserva acceso de escritura a la base de producción.

La rotación es una operación de infraestructura y no está hecha. Ver abajo.

## Runbook de rotación

Lo ejecuta la persona responsable de la infraestructura Neon. No requiere
reescribir el historial de Git y no debe hacerse automáticamente.

1. **Inventariar consumidores** antes de tocar nada: variables `DATABASE_URL`
   del servicio desplegado, secretos de CI/CD, jobs programados, herramientas
   locales de cada persona del equipo y cualquier panel externo. Rotar sin este
   paso deja servicios caídos.
2. **Crear la nueva credencial** en Neon (rol nuevo o contraseña nueva del rol
   existente) sin borrar todavía la anterior, para tener solapamiento.
3. **Actualizar cada consumidor** con la nueva URL, empezando por el despliegue
   y CI. Los valores viven en el gestor de secretos del entorno, nunca en el
   repositorio.
4. **Verificar** que la aplicación arranca y que `alembic current` responde
   contra el destino esperado (el print redactado confirma host y base).
5. **Revocar la credencial anterior** en Neon. Este es el paso que cierra el
   hallazgo; los anteriores solo preparan.
6. **Registrar la evidencia** en las Completion Notes de TASK-002: fecha, quién
   la ejecutó y confirmación de que la credencial antigua ya no autentica.
   **Sin incluir ningún valor.**
7. **Revisar los logs de acceso** de Neon del periodo en que la credencial
   estuvo expuesta, por si hubo uso no reconocido.

Consideración aparte, fuera de esta tarea: el historial de Git seguirá
conteniendo el literal. Una vez rotada la credencial, el literal histórico deja
de ser utilizable y limpiar el historial pasa a ser opcional. Si aun así se
decide, es una operación coordinada (reescritura + reclonado por todo el equipo)
y merece su propia tarea.

## Regresión

`tests/test_migration_config.py` falla si vuelve a aparecer una URL con
credenciales embebidas en `alembic.ini`, `alembic/env.py` o
`scripts/migrate_sqlite_to_postgres.py`, si `alembic.ini` vuelve a fijar
`sqlalchemy.url`, o si la resolución deja de fallar cuando no hay configuración.

## Presupuestos de subida (F-05)

Ninguna cota se aplica una sola vez, porque un único punto no cubre el problema:

1. `app/middleware/body_size.py` acota el **cuerpo ASGI crudo** antes de que el
   parser multipart lo procese y lo vuelque a disco. Usa `Content-Length` como
   atajo cuando está, pero cuenta bytes según llegan — que es lo único que cubre
   una petición *chunked*, que no manda `Content-Length` en absoluto.
2. `app/core/uploads.py::read_upload_within_limit` lee la parte ya parseada de
   forma incremental y corta un chunk pasado el presupuesto.
3. `ensure_allowed_upload` rechaza un tipo declarado que la ruta no sirve y un
   payload cuyos bytes iniciales contradicen ese tipo.

| Variable | Default | Alcance |
| --- | --- | --- |
| `MAX_UPLOAD_BYTES` | 5 MB | CV (`/api/v1/profile/cv/*`) |
| `MAX_POST_UPLOAD_BYTES` | 10 MB | Media de posts (`/api/v1/upload_post`) |
| `MAX_REQUEST_BODY_BYTES` | 1 MB | Todo lo demás |
| `MAX_DOCX_EXPANDED_BYTES` | 20 MB | XML descomprimido de un DOCX |
| `MAX_DOCX_COMPRESSION_RATIO` | 200 | Ratio máximo declarado/comprimido |

Los presupuestos del middleware llevan `MULTIPART_OVERHEAD_BYTES` (16 KB) de
holgura sobre el presupuesto del archivo, para que sea la ruta —y no el
middleware— la que decida el límite exacto y devuelva el mensaje preciso.

Una cota sobre el archivo comprimido **no** acota un DOCX: unos pocos KB de ZIP
pueden declarar gigabytes de XML. Por eso se rechaza el tamaño declarado, se
rechaza un ratio de compresión implausible, y la lectura real sigue acotada —
la cabecera también la controla quien sube el archivo, y solo la tercera
comprobación no depende de ella. El fallo es controlado: el extractor devuelve
texto vacío, igual que con cualquier documento ilegible, y registra el motivo.
