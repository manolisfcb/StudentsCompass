# El error model de `/api/v1` (TASK-040)

Toda respuesta de error de `/api/v1` tiene **una** forma. No hay una segunda.

```json
{
  "error": {
    "code": "not_found",
    "message": "The requested resource was not found.",
    "details": null,
    "request_id": "1bc58bf0025f4aefad658904ec6a8c8e"
  },
  "detail": "The requested resource was not found."
}
```

| Campo | Qué es | Qué no es |
| --- | --- | --- |
| `code` | Miembro de `ErrorCode`, estable. **Es el contrato**: el cliente ramifica por aquí. | No es traducible ni reformulable. |
| `message` | Frase para una persona. Se puede reescribir o traducir cuando sea. | No es un identificador; no ramifiques por su texto. |
| `details` | Específicos legibles por máquina — qué campo falló y por qué. `null` si no hay nada estructurado que decir. | No es un segundo mensaje ni la causa. |
| `request_id` | El id de **esta** petición, el mismo que va en la cabecera `X-Request-ID` y en la línea de log. | No es un id por error: antes lo era, y eso daba dos ids para un solo evento. |
| `detail` | **Adapter legacy.** Lo que las pantallas Jinja ya leen. Lo retira TASK-059. | No lo uses en código nuevo: no lleva código ni detalles. |

## Por qué se normaliza en el borde y no en cada `raise`

Había 119 `HTTPException(...)` crudos repartidos por 15 routers. Reescribirlos
uno a uno habría cambiado *qué* falla y *con qué status*, que es exactamente lo
que el Scope de TASK-040 pone fuera de alcance. Los handlers de
`app/core/error_handlers.py` normalizan a la salida: no cambia cuándo falla una
petición, solo los bytes con los que responde.

Un sitio que quiera precisión levanta `AppError`, que lleva su código del
catálogo y sus `details` hasta el cliente:

```python
raise AppError(
    ErrorCode.CONFLICT,
    "That slot is already taken.",
    status_code=409,
    details={"field": "slot_id"},
)
```

## El catálogo está cerrado

`ErrorCode` es un `StrEnum`. Un código que no sea miembro **no llega al
cliente**: se registra un WARNING y se responde con el código de la familia del
status. Antes de esto había cinco strings sueltos en tres módulos
(`csrf.py`, `idempotency.py`, `internalAuth.py`) que podían publicar un código
nuevo por una errata, de forma permanente y sin que nadie lo declarara.

`ERROR_CATALOG_VERSION` sube solo cuando se **retira** un código o cambia su
significado. Añadir un miembro es compatible: un cliente que no lo conoce cae a
la familia del status, y por eso cada código está fijado a un solo status.

## Nada de la infraestructura sale

El cuerpo público nunca contiene `str(exception)`. Un `detail` que huela a
máquina —una DSN, SQL, una ruta, un nombre de driver— se sustituye por la frase
de la familia; la causa real va al log, redactada, bajo el mismo `request_id`.
`is_safe_client_message` decide, y es la misma función que TASK-011 ya usaba.

## Dónde se lee el `request_id`

Del **scope**, no del `ContextVar`. Starlette invoca el handler de una excepción
no capturada desde `ServerErrorMiddleware`, que está **por fuera** de
`RequestContextMiddleware` — para cuando el handler corre, el `finally` de ese
middleware ya reseteó el contextvar y valdría `-`. El cuerpo del 500 citaría
entonces un id que no aparece en ninguna línea de log, que es justo la
correlación que esta tarea existe para dar. `scope["state"]` no se desenrolla.

## Fuera de `/api/v1` no cambia nada

`views_router` sirve Jinja e `internal_tasks_router` no es contrato público;
ninguno cuelga del prefijo. Un 404 de una página HTML que se volviera un
envelope JSON sería una regresión, así que los handlers delegan en los de
FastAPI para todo lo que esté fuera.
