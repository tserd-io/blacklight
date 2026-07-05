FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    LLM_PROVIDER=mock \
    LLM_MODEL=mock-ticket-classifier \
    TRACE_DB_PATH=/app/data/traces.sqlite3

WORKDIR /app

RUN addgroup --system app && adduser --system --ingroup app app

COPY pyproject.toml README.md LICENSE ./
COPY src ./src

RUN python -m pip install --no-cache-dir --upgrade pip \
    && python -m pip install --no-cache-dir ".[api]"

RUN mkdir -p /app/data && chown -R app:app /app

USER app

EXPOSE 8000

CMD ["uvicorn", "blacklight.api:app", "--host", "0.0.0.0", "--port", "8000"]
