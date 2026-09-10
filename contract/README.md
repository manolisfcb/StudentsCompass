# El contrato de la API

`openapi.json` es el documento OpenAPI que sirve la API de este commit. El plan
08 §5.1 lo declara fuente de verdad del contrato, y TASK-043 lo convirtió en algo
verificable en vez de en una frase.

No se edita a mano. Se regenera:

```bash
cd backend && python scripts/export_openapi.py -o ../contract/openapi.json
cd ../frontend && npm run api:types
```

Los dos pasos van juntos: de este fichero salen los tipos TypeScript del
frontend (`frontend/src/api/generated/`), y regenerar uno sin el otro los
desincroniza.

## Por qué está versionado

Podría ser solo un artefacto de CI, y de hecho `backend-fast` también lo publica
así. Está en el repositorio por tres razones:

1. **El diff del contrato se revisa.** Un PR que cambia una respuesta enseña
   exactamente qué cambió, al lado del código que lo cambió.
2. **Da una referencia estable.** El check de compatibilidad compara este fichero
   con el de la rama base. Sin él habría que instalar y arrancar la aplicación de
   la base para saber qué prometía.
3. **El frontend no depende del backend para compilar.** La lane de frontend
   genera sus tipos de aquí, sin Python ni base de datos, que es lo que TASK-039
   separó.

## Qué lo comprueba

| Pregunta | Dónde se responde |
| --- | --- |
| ¿Este fichero es el de este commit? | `backend/tests/test_openapi_contract.py`, en la lane rápida |
| ¿Los tipos del frontend salen de él? | `npm run api:check`, en la lane de frontend |
| ¿Lo que cambió rompe a un cliente? | job `contrato` de CI, con `backend/scripts/check_openapi_compat.py` |

El tercero es el que bloquea un cambio incompatible. Sus reglas —y la vía de
retiro de §5.3, marcar `deprecated` antes de quitar— están documentadas en la
cabecera del propio script.
