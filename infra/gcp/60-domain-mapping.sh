#!/usr/bin/env bash
# TASK-057. Dominio y TLS sobre el frontend — el único servicio con dominio
# público (§3, ADR-001).
#
# Cloud Run gestiona el certificado TLS él mismo en cuanto el mapeo existe y el
# DNS apunta donde debe: no hay Certificate Manager, ni Load Balancer, ni nada
# que aprovisionar por separado. ADR-001 opción A ya decidió no pagar por un
# balanceador; un dominio mapeado directo al servicio es la otra mitad de esa
# decisión, no una alternativa a ella.
#
# Por qué el frontend y no la API: la API sigue alcanzable por su URL
# `run.app` (ADR-001, "qué se acepta explícitamente al decidir A"). El dominio
# público es first-party solo para lo que el navegador ve, que es el frontend;
# moverlo a la API sin más rompería exactamente el diseño de mismo origen que
# hace que las cookies sean first-party (plan 08 §1, §3).
set -euo pipefail
cd "$(dirname "$0")"
source ./config.env

if [ -z "${DOMAIN:-}" ]; then
  echo "DOMAIN no está definido en config.env — nada que mapear todavía." >&2
  echo "Añadir DOMAIN=\"app.tudominio.com\" a config.env y volver a correr esto." >&2
  exit 1
fi

# Comprobar el nombre y no el destino no es idempotencia: un mapeo creado a mano
# contra otro servicio hacía que este script dijera "ya existe" y saliera con
# éxito sin haber mapeado nada. Así es como `studentscompass.ca` estuvo
# apuntando a la API —sirviendo el monolito Jinja— mientras esta tarea figuraba
# como hecha. Ahora se lee el destino real.
# `describe` no expone spec.routeName en esta versión de gcloud (devuelve vacío
# sin error, que es la peor forma de no devolver algo); `list` sí lo trae.
CURRENT_ROUTE="$(gcloud beta run domain-mappings list \
  --project "$PROJECT_ID" --region "$REGION" \
  --format='value(spec.routeName)' \
  --filter="metadata.name=${DOMAIN}" 2>/dev/null | head -n1 || true)"

if [ -n "$CURRENT_ROUTE" ] && [ "$CURRENT_ROUTE" != "$FRONT_SERVICE" ]; then
  echo "ERROR: $DOMAIN está mapeado a '$CURRENT_ROUTE', no a '$FRONT_SERVICE'." >&2
  echo >&2
  echo "Este script NO lo repunta solo. Mover el dominio de un servicio a otro" >&2
  echo "cambia lo que ve todo usuario en la siguiente petición: si el destino" >&2
  echo "actual es la API, ese cambio ES el cutover de TASK-058, no un ajuste de" >&2
  echo "infraestructura, y se hace con su ventana y su plan de vuelta atrás." >&2
  echo >&2
  echo "Para hacerlo deliberadamente:" >&2
  echo "  gcloud beta run domain-mappings delete --domain=$DOMAIN --project $PROJECT_ID --region $REGION" >&2
  echo "  ./60-domain-mapping.sh" >&2
  exit 1
fi

if [ -n "$CURRENT_ROUTE" ]; then
  echo "El mapeo de $DOMAIN ya existe y apunta a $FRONT_SERVICE"
else
  gcloud beta run domain-mappings create \
    --service "$FRONT_SERVICE" \
    --domain "$DOMAIN" \
    --project "$PROJECT_ID" --region "$REGION"
fi

echo
echo "Registros DNS que el propio comando anterior imprime (o reimprime con"
echo "'gcloud beta run domain-mappings describe $DOMAIN --project $PROJECT_ID --region $REGION')"
echo "deben crearse en el proveedor de DNS del dominio antes de que el"
echo "certificado gestionado se emita. La emisión es automática y puede tardar"
echo "hasta 24h desde que el DNS resuelve; no hay paso manual adicional."
echo
echo "Verificación (repetible hasta que el certificado esté listo):"
echo "  gcloud beta run domain-mappings describe $DOMAIN --project $PROJECT_ID --region $REGION \\"
echo "    --format='value(status.conditions)'"
