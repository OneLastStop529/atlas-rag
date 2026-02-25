FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml README.md ./
RUN pip install --upgrade pip \
    && pip install \
        "fastapi>=0.128.0" \
        "httpx>=0.28.1" \
        "pgvector>=0.4.2" \
        "fpdf>=1.7.2" \
        "reportlab>=4.2.0" \
        "pypdf>=4.3.1" \
        "psycopg2-binary>=2.9.11" \
        "pydantic>=2.12.5" \
        "pydantic-settings>=2.12.0" \
        "python-multipart>=0.0.21" \
        "sentence-transformers>=5.2.0" \
        "sqlalchemy>=2.0.45" \
        "torch>=2.10.0" \
        "uvicorn>=0.40.0" \
        "langchain>=1.2.9" \
        "langchain-text-splitters>=1.1.0"

COPY app ./app

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
