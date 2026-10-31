FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 HF_HOME=/models/cache
WORKDIR /code
COPY requirements-ml.txt requirements.txt ./
RUN pip install --no-cache-dir -r requirements-ml.txt
COPY app ./app
RUN useradd -r -m -u 10001 talent && mkdir -p /models/cache && chown -R talent:talent /models
USER talent
EXPOSE 8090
CMD ["uvicorn", "app.ml.sidecar:app", "--host", "0.0.0.0", "--port", "8090"]
