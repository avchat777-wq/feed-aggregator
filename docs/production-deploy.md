# Production deploy

Server: `157.22.205.205`
Project path: `/opt/feed-aggregator`
Domain: `feed.mielbarnaul.ru`

## DNS

Create an `A` record:

```text
feed.mielbarnaul.ru -> 157.22.205.205
```

Wait until it resolves from the server:

```bash
dig +short feed.mielbarnaul.ru
```

## Environment

Use `.env.example` as a template and keep real secrets only in `/opt/feed-aggregator/.env`.

Important production values:

```dotenv
FEED_BASE_URL=https://feed.mielbarnaul.ru/feed
SYNC_INTERVAL_HOURS=24
```

Keep PostgreSQL and the backend private. In production use `docker-compose.prod.yml`, where only nginx is published.

## Deploy

```bash
cd /opt/feed-aggregator
git pull
docker compose -f docker-compose.prod.yml up -d --build
docker compose -f docker-compose.prod.yml ps
docker compose -f docker-compose.prod.yml exec nginx nginx -t
curl -I http://localhost:8080/
curl -I http://localhost:8080/sources
curl -I http://localhost:8080/feed/feed.xml
```

Expected ports:

```text
app    8000/tcp
db     5432/tcp
nginx  0.0.0.0:8080->80/tcp
```

## HTTPS

Recommended VPS layout:

1. Keep the app nginx container on `127.0.0.1:8080` or `0.0.0.0:8080`.
2. Install host nginx and Certbot on Ubuntu.
3. Terminate HTTPS on the host and proxy to the container.

Host nginx site:

```nginx
server {
    listen 80;
    server_name feed.mielbarnaul.ru;

    location / {
        proxy_pass http://127.0.0.1:8080;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

Then issue the certificate:

```bash
certbot --nginx -d feed.mielbarnaul.ru
```

After HTTPS is active, check:

```bash
curl -I https://feed.mielbarnaul.ru/
curl -I https://feed.mielbarnaul.ru/sources
curl -I https://feed.mielbarnaul.ru/feed/feed.xml
```

## Daily PostgreSQL backup

Install the cron job:

```bash
cd /opt/feed-aggregator
chmod +x scripts/backup_postgres.sh
crontab -e
```

Add:

```cron
15 2 * * * cd /opt/feed-aggregator && /opt/feed-aggregator/scripts/backup_postgres.sh >> /opt/feed-aggregator/backups/backup.log 2>&1
```

Manual test:

```bash
cd /opt/feed-aggregator
./scripts/backup_postgres.sh
ls -lh backups
```

Restore example:

```bash
gunzip -c backups/feed_aggregator_YYYY-MM-DD_HH-MM-SS.sql.gz | docker compose -f docker-compose.prod.yml exec -T db psql -U feedagg -d feed_aggregator
```
