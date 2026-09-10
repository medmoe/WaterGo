# Production deployment — one VPS, Docker Compose

Target: **sarbili.store** on a single Hetzner Cloud CX22 (2 vCPU / 4 GB / 40 GB),
running the whole stack (Traefik, backend+frontend, Postgres/PostGIS, Redis, Celery
worker+beat) as Docker containers. ~€5–7/month all in. Runs fine **without SMS** — see
the last section.

The template root `deployment.md` / `deployment-docker-compose.md` are generic FastAPI
docs; **this file is the one for this project.**

---

## What runs in production

`docker compose -f compose.yml -f compose.deploy.yml` starts exactly:

| service | what |
|---|---|
| `proxy` | Traefik — ports 80/443, HTTP→HTTPS redirect, Let's Encrypt (TLS-ALPN) |
| `backend` | FastAPI + the built React SPA (baked into the image), served at `https://sarbili.store` and `https://www.sarbili.store` |
| `worker` | Celery worker **with beat** (`-B`) — notifications + the SMS-gateway health check |
| `db` | `postgis/postgis:16-3.4`, data in the `app-db-data` volume, **not** published to the host |
| `redis` | OTP codes, Telegram link codes, Celery broker — **not** published |

`adminer` is moved to the `tools` profile (not started). `flower` / `playwright` are
dev-only and never start here.

---

## Prerequisites (you, before anything)

1. **Hetzner CX22**, Ubuntu 24.04 LTS. Note its public IPv4 (and IPv6).
2. **Harden the box**:
   ```bash
   adduser deploy && usermod -aG sudo deploy
   rsync --archive --chown=deploy:deploy ~/.ssh /home/deploy   # copy your key
   # /etc/ssh/sshd_config:  PermitRootLogin no   PasswordAuthentication no
   systemctl restart ssh
   ufw allow OpenSSH && ufw allow 80 && ufw allow 443 && ufw enable
   ```
   Nothing else is opened — Postgres/Redis stay on the Docker network.
3. **Docker**: `curl -fsSL https://get.docker.com | sh` then `usermod -aG docker deploy`.
4. **DNS** at your registrar — do this now so the record has propagated before step "Bring
   it up" (Let's Encrypt needs `sarbili.store` to resolve to the box):
   - `A  sarbili.store  → <VPS IPv4>`
   - `A  www.sarbili.store  → <VPS IPv4>`  (or a CNAME to `sarbili.store`)
   - optional `AAAA` records for IPv6
   Verify: `dig +short sarbili.store` returns the VPS IP from your laptop.

---

## Deploy

As `deploy` on the box:

```bash
git clone <repo-url> watergo && cd watergo
cp .env.example .env
```

Edit `.env` — **generate fresh secrets, never reuse dev values**:

```dotenv
# DELETE this line for production (makes the app reject "changethis" secrets)
# FASTAPI_ENV=development

PROJECT_NAME="Batna Water Delivery"
SECRET_KEY=<openssl rand -hex 32>
POSTGRES_PASSWORD=<openssl rand -hex 32>
FIRST_SUPERUSER_PHONE=<the real admin's E.164 phone>

DOMAIN=sarbili.store
FRONTEND_HOST=https://sarbili.store
ACME_EMAIL=<an address you monitor>

# leave blank for now — the platform runs without SMS
SMS_GATEWAY_BASE_URL=
SMS_GATEWAY_API_KEY=
SMS_GATEWAY_DEVICE_ID=

# fill in only if the Telegram bot (interim-messaging.md Part B) is set up
TELEGRAM_BOT_TOKEN=
TELEGRAM_WEBHOOK_SECRET=
```

> `.env` is git-ignored, so `git pull` on the server never touches it. Secrets you'd
> rather keep in a separate file can go in `.env.local` instead (loaded on top of
> `.env` by the backend/worker; `git`-ignored). Anything referenced as `${VAR}` in the
> compose files themselves (`DOMAIN`, `ACME_EMAIL`, `POSTGRES_PASSWORD`, `SECRET_KEY`,
> `FIRST_SUPERUSER_PHONE`, `PROJECT_NAME`) must be in `.env` or the shell env.

Bring it up and initialise the DB:

```bash
docker compose -f compose.yml -f compose.deploy.yml up -d --build
docker compose -f compose.yml -f compose.deploy.yml exec backend bash scripts/prestart.sh
#   ^ alembic upgrade head  +  seeds the admin from FIRST_SUPERUSER_PHONE
```

Verify (from your laptop):

```bash
curl -sI https://sarbili.store | head -1                       # 200, valid cert
curl -s  https://sarbili.store/api/v1/utils/health-check/      # true
```

If the cert doesn't issue on the first try, it's almost always DNS not yet pointing at
the box, or ports 80/443 not open — fix, then `docker compose ... restart proxy`.

---

## Backups

Cron on the **host** (not in a container):

```bash
sudo mkdir -p /backups && sudo chown deploy /backups
crontab -e
# 0 3 * * *  cd /home/deploy/watergo && docker compose -f compose.yml -f compose.deploy.yml exec -T db pg_dump -U postgres app | gzip > /backups/app-$(date +\%F).sql.gz && find /backups -name 'app-*.sql.gz' -mtime +14 -delete
```

Copy them off the box periodically (`scp deploy@sarbili.store:/backups/*.gz .`). Hetzner's
snapshot/backup add-on (~20% of the VPS price) is the next step up, not needed on day one.

Restore: `gunzip -c app-YYYY-MM-DD.sql.gz | docker compose ... exec -T db psql -U postgres app`.

---

## Monitoring

- **UptimeRobot** (free): HTTP monitor on `https://sarbili.store/api/v1/utils/health-check/`,
  5-min interval, email alert.
- The Celery beat job `sms_gateway_healthcheck` already pings any linked dispatchers on
  Telegram if the SMS gateway goes down (once the gateway + bot are configured).
- Hetzner Cloud Console has CPU/RAM/disk graphs for free.

---

## Redeploying

```bash
cd ~/watergo && git pull
docker compose -f compose.yml -f compose.deploy.yml up -d --build
docker compose -f compose.yml -f compose.deploy.yml exec backend bash scripts/prestart.sh   # if there are new migrations
```

`.env` and the data volumes are untouched. A GitHub Actions deploy is a later nicety, not
a launch requirement.

### Handy

```bash
# adminer, only when you need it (over an SSH tunnel: ssh -L 8080:localhost:8080 ...)
docker compose -f compose.yml -f compose.deploy.yml --profile tools up -d adminer
# logs
docker compose -f compose.yml -f compose.deploy.yml logs -f backend worker
# a shell
docker compose -f compose.yml -f compose.deploy.yml exec backend bash
```

---

## Deploying without SMS

Fully supported and expected for launch. With `SMS_GATEWAY_*` blank the provider is the
logging stub:

- Guest checkout, order tracking, dispatcher phone-call confirmation, delivery, and cash
  collection all work — none of it touches outbound messaging.
- The **only** accounts that log in are the dispatcher and driver. Their OTP codes are in
  the worker log — whoever has server access reads one out over the phone during
  onboarding: `docker compose ... logs worker | grep stub-sms`. Two people, occasionally.
- Review-request and status texts just don't go out yet. Known, temporary gap.

Turning SMS on later = fill `SMS_GATEWAY_*` in `.env` and
`docker compose ... up -d backend worker`. Nothing else changes. See
[`interim-messaging.md`](./interim-messaging.md).

---

## Team handover

Record where the team can reach it (a shared vault / password manager, not one laptop):
the VPS IP, the SSH key + `deploy` user, and that the live config is `~/watergo/.env` on
the box.
