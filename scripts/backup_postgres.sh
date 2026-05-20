#!/usr/bin/env sh
set -eu

COMPOSE_FILE="${COMPOSE_FILE:-docker-compose.prod.yml}"
BACKUP_DIR="${BACKUP_DIR:-/opt/feed-aggregator/backups}"
POSTGRES_USER="${POSTGRES_USER:-feedagg}"
POSTGRES_DB="${POSTGRES_DB:-feed_aggregator}"
KEEP_DAYS="${KEEP_DAYS:-14}"

mkdir -p "$BACKUP_DIR"

stamp="$(date +%Y-%m-%d_%H-%M-%S)"
target="$BACKUP_DIR/feed_aggregator_$stamp.sql.gz"

docker compose -f "$COMPOSE_FILE" exec -T db \
  pg_dump -U "$POSTGRES_USER" "$POSTGRES_DB" | gzip > "$target"

find "$BACKUP_DIR" -type f -name 'feed_aggregator_*.sql.gz' -mtime +"$KEEP_DAYS" -delete

echo "$target"
