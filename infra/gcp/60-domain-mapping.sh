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

if gcloud beta run domain-mappings describe "$DOMAIN" \
      --project "$PROJECT_ID" --region "$REGION" >/dev/null 2>&1; then
  echo "El mapeo de $DOMAIN ya existe"
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
