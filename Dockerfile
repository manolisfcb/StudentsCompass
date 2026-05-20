FROM python:3.12-slim

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PORT=8080

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

CMD ["sh", "-c", "exec uvicorn app.app:app --host 0.0.0.0 --port ${PORT}"]
