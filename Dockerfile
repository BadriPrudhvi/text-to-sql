FROM python:3.12-slim AS base

WORKDIR /app

COPY pyproject.toml .
RUN pip install --no-cache-dir .

FROM base AS runtime

COPY src/ src/

EXPOSE 8000

CMD ["uvicorn", "text_to_sql.app:app", "--host", "0.0.0.0", "--port", "8000"]
