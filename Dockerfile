FROM node:20-alpine AS frontend-build

WORKDIR /frontend
COPY frontend/package*.json ./
RUN npm install
COPY frontend/ ./
RUN npm run build

FROM python:3.11-slim-bookworm

WORKDIR /app

RUN apt-get -o Acquire::Retries=5 update && \
    apt-get -o Acquire::Retries=5 install -y --no-install-recommends \
    gcc libpq-dev libxml2-dev libxslt1-dev && \
    rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY alembic.ini .
COPY alembic/ alembic/
COPY app/ app/
COPY --from=frontend-build /static/ static/

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
