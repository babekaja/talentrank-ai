#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
if [ -f .env ]; then
  if ! grep -q '^S3_SECRET_KEY=' .env; then
    echo 'S3_SECRET_KEY='"$(openssl rand -hex 32)" >> .env
    echo 'S3_ACCESS_KEY=talentrank' >> .env
    echo 'S3_ENDPOINT=minio:9000' >> .env
    echo 'S3_BUCKET=cv-private' >> .env
    echo 'S3_SECURE=false' >> .env
    echo 'REDIS_URL=redis://redis:6379/0' >> .env
    echo 'OCR_LANGUAGES=fra+eng' >> .env
    echo 'MALWARE_SCAN_ENABLED=false' >> .env
    echo 'Paramètres privés de la phase 3 ajoutés sans modifier les anciens secrets.'
  else
    echo '.env existe déjà ; aucun secret écrasé.'
  fi
  if ! grep -q '^ML_SERVICE_TOKEN=' .env; then
    echo 'ML_SERVICE_TOKEN='"$(openssl rand -hex 32)" >> .env
  fi
  chmod 600 .env
  exit 0
fi
command -v openssl >/dev/null || { echo 'openssl est requis' >&2; exit 1; }
DB_PASSWORD="$(openssl rand -hex 20)"
ROOT_PASSWORD="$(openssl rand -hex 24)"
JWT_SECRET="$(openssl rand -hex 48)"
S3_SECRET="$(openssl rand -hex 32)"
ML_TOKEN="$(openssl rand -hex 32)"
cat > .env <<ENDENV
ENVIRONMENT=development
MYSQL_DATABASE=talentrank
MYSQL_USER=talentrank
MYSQL_PASSWORD=${DB_PASSWORD}
MYSQL_ROOT_PASSWORD=${ROOT_PASSWORD}
DATABASE_URL=mysql+pymysql://talentrank:${DB_PASSWORD}@mysql:3306/talentrank?charset=utf8mb4
JWT_SECRET=${JWT_SECRET}
JWT_ISSUER=talentrank-ai
JWT_AUDIENCE=talentrank-web
CORS_ORIGINS=http://localhost:4200,http://localhost:8080
REFRESH_COOKIE_SECURE=false
REDIS_URL=redis://redis:6379/0
S3_ENDPOINT=minio:9000
S3_ACCESS_KEY=talentrank
S3_SECRET_KEY=${S3_SECRET}
S3_BUCKET=cv-private
S3_SECURE=false
OCR_LANGUAGES=fra+eng
MALWARE_SCAN_ENABLED=false
SEMANTIC_ENABLED=false
EMBEDDING_MODEL=sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2
ML_SERVICE_URL=http://ml-service:8090
ML_SERVICE_TOKEN=${ML_TOKEN}
QDRANT_URL=http://qdrant:6333
ENDENV
chmod 600 .env
printf '%s\n' 'Configuration locale créée dans .env (non versionnée).'
