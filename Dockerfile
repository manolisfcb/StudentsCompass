FROM python:3.12-slim

WORKDIR /app

COPY pyproject.toml uv.lock ./

RUN pip install --no-cache-dir uv \
    && uv pip install --system -r pyproject.toml

COPY . .

ENV PORT=8080

CMD ["sh", "-c", "uvicorn app.app:app --host 0.0.0.0 --port ${PORT}"]