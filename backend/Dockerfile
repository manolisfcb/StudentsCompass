FROM python:3.12-slim

WORKDIR /app

# TRUSTED_PROXY_IPS declares which immediate peers may speak for the client
# through X-Forwarded-For; the app resolves every per-IP limit through it (see
# docs/ingress_and_client_ip.md). "private" trusts loopback/RFC1918 peers, which
# is what a managed load balancer looks like from inside the container, while a
# direct hit from the internet arrives from a public peer and cannot forge its
# own IP. Narrow it to the balancer's CIDR once the real ingress is known.
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PORT=8080 \
    TRUSTED_PROXY_IPS=private

COPY requirements.txt ./
RUN pip install --upgrade pip \
    && pip install -r requirements.txt

COPY app ./app
COPY alembic ./alembic
COPY alembic.ini ./

RUN addgroup --system app \
    && adduser --system --ingroup app --home /app app

USER app

EXPOSE 8080

# No --proxy-headers: uvicorn would rewrite the socket peer from X-Forwarded-For
# before the app sees it, which would leave two places deciding who is trusted.
# TRUSTED_PROXY_IPS is the single source of truth.
CMD ["sh", "-c", "exec uvicorn app.app:app --host 0.0.0.0 --port \"${PORT}\""]
