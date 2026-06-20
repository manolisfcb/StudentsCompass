FROM python:3.12-slim

WORKDIR /app

# FORWARDED_ALLOW_IPS lets uvicorn trust the platform proxy/load balancer and
# resolve the real client IP from X-Forwarded-For. Narrow this to the proxy CIDR
# if the container is reachable directly (otherwise X-Forwarded-For is spoofable).
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PORT=8080 \
    FORWARDED_ALLOW_IPS=*

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

CMD ["sh", "-c", "exec uvicorn app.app:app --host 0.0.0.0 --port \"${PORT}\" --proxy-headers --forwarded-allow-ips \"${FORWARDED_ALLOW_IPS}\""]
