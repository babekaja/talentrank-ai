FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /code
RUN apt-get update && apt-get install -y --no-install-recommends \
    tesseract-ocr tesseract-ocr-fra tesseract-ocr-eng fonts-dejavu-core && \
    rm -rf /var/lib/apt/lists/*
COPY requirements.txt .
RUN --mount=type=cache,target=/root/.cache/pip pip install --timeout 120 --retries 10 -r requirements.txt
COPY alembic.ini .
COPY alembic ./alembic
COPY app ./app
COPY scripts ./scripts
RUN useradd -r -m -u 10001 talent
RUN chmod -R a+rX /code
USER talent
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
