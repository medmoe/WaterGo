# Batna Water Delivery — implementation notes

This document summarises what was built on top of `fastapi/full-stack-fastapi-template`
to execute the task list in `PROJECT_SPEC.md` §18. It is the map from the spec to the
code. For deferred work see [`follow-ups.md`](./follow-ups.md).

- **19 commits on `master`** (`git log --oneline`).
- Backend: **120 pytest tests, ~94% line coverage**, `ruff` / `mypy --strict` / `ty` /
  `alembic check` all clean.
- Frontend builds clean (`tsc` + `vite`); public-flow Playwright specs added.
- Whole stack verified end-to-end in Docker (order → delivery → cash report → worker
  notifications).

---

## 1. Stack

| Layer | Choice |
|---|---|
| API | FastAPI + SQLModel, routers under `app/api/routes/`, DI for DB session / current user |
| DB | PostgreSQL **`postgis/postgis:16-3.4`** (was plain `postgres:18`) |
| Migrations | Alembic — 5 grouped migrations; `geoalchemy2.alembic_helpers` + `public`-schema pin in `env.py` |
| Auth | Phone number + OTP (JWT issuance only changed; `get_current_user` untouched) |
| Background jobs | Celery + Redis (`worker` service, `celery -A app.worker.celery_app worker`) |
| Realtime | In-process WebSocket manager (no broker) |
| Frontend | React + Vite + TS + Tailwind, TanStack Router/Query, generated `@hey-api` client, Leaflet for maps |
| Deploy | Docker Compose (`compose.yml` + `compose.override.yml` dev + `compose.deploy.yml` prod) |

---

## 2. What changed in the repo

### Removed (template demo cruft)
`items` resource (model/router/CRUD/tests/frontend), `private` dev-users router,
`login` router (password login + recovery/reset), all email code (`app/utils.py`,
`email-templates/`, `emails` + `pwdlib` deps), frontend `signup` / `recover-password`
/ `reset-password` routes and `ChangePassword`, the item-era Alembic migrations, the
old `items`/email Playwright specs.

### Added — backend

```
app/
  worker.py                 Celery app
  tasks.py                  send_notification, request_review (+ enqueue_* helpers)
  core/redis_client.py      shared cached Redis client (OTP store)
  services/
    otp.py                  6-digit code: generate / store in Redis / verify
    notifications.py        send(phone, message) behind NotificationProvider protocol
    orders.py               create_order + transition_status (THE state machine)
    pricing.py              current price (history-preserving), add_pricing
    routes.py               dispatch route building + driver stop actions
    ws.py                   ConnectionManager (dispatch + per-driver channels)
    reviews.py              signed review token, create_review, list_reviews
    reports.py              cash reconciliation
    telegram.py             team Telegram notifications + /link account flow
  api/routes/
    auth.py    orders.py  dispatch.py  driver.py  vehicles.py
    pricing.py reviews.py  reports.py   ws.py  telegram.py
  alembic/versions/
    0001_users_and_postgis.py     users + CREATE EXTENSION postgis
    0002_locations_vehicles.py    locations (geom + GiST index), vehicles, maintenance_logs
    0003_orders_routes.py         orders, routes, route_stops
    0004_reviews_pricing.py       pricing_settings, reviews, notification_logs
    0005_user_telegram_chat_id.py users.telegram_chat_id
```

### Added — frontend

```
src/routes/
  index.tsx              /                    customer order form (public)
  track.$orderId.tsx     /track/:id           order tracking (public, phone-gated)
  review.$orderId.tsx    /review/:id?token=   public star rating (no login)
  dispatch.tsx           /dispatch            dispatcher dashboard (role-gated)
  driver.tsx             /driver              driver stop list (role-gated)
  _layout/reports.tsx    /reports             cash reconciliation (admin)
src/components/Map/maps.tsx     PinPicker + PointsMap (react-leaflet, OSM tiles)
src/hooks/useLiveChannel.ts     WS subscription with silent polling fallback
src/hooks/useAuth.ts            OTP request/verify mutations, role-aware redirect
```

---

## 3. Data model (`app/models.py`) — spec §5

Table models: **`users`, `locations`, `vehicles`, `maintenance_logs`, `pricing_settings`,
`orders`, `routes`, `route_stops`, `reviews`, `notification_logs`** — plural names per
the §5 headers (the template used singular). Every table has `id: UUID` PK and
`created_at` / `updated_at` (via `TimestampMixin`). Enums are `StrEnum` mapped to native
PostgreSQL enum types: `UserRole`, `VehicleStatus`, `MaintenanceType`, `OrderStatus`,
`RouteStatus`, `NotificationChannel` / `NotificationPurpose` / `NotificationStatus`.

Notes:

- **`locations.geom`** = `geography(Point, 4326)` (GeoAlchemy2) with a GiST index
  (`ix_locations_geom`). `raw_lat` / `raw_lng` are stored alongside for display without
  PostGIS functions. `geom` is populated on insert with
  `ST_SetSRID(ST_MakePoint(lng, lat), 4326)` and is **not** exposed by the API.
- **`users`**: `phone_number` (unique, indexed, E.164), `full_name`, `role`, `is_active`.
  No email, no password, no `is_superuser`.
- **`orders`**: `customer_id` nullable (guest checkout), `customer_phone` always stored,
  `price_per_liter_dzd` + `total_price_dzd` snapshotted at creation and never
  recomputed, `status` indexed.
- **`pricing_settings`**: append-only. Read the latest row with
  `effective_from <= now()`; falls back to **4 DZD/L** when empty.
- FK delete behaviour: `SET NULL` where the parent is optional (`orders.customer_id`,
  `locations.user_id`, `notification_logs.order_id`, …), `CASCADE` for owned children
  (`route_stops`, `reviews`, `maintenance_logs`).

`alembic check` is clean — model and migrations are in sync.

---

## 4. Order status state machine — spec §6

Enforced **only** in `app/services/orders.py::transition_status(session, order,
new_status, *, actor=None, reason=None)`. Routers never assign `Order.status`.

```
pending ──▶ confirmed ──▶ assigned ──▶ en_route ──▶ delivered
   │            │             │
   ▼            ▼             ▼
cancelled   cancelled     confirmed        (un-assign; see note)
```

- `pending → confirmed`: sets `confirmed_by = actor.id`, `confirmed_at = now()`.
- `* → cancelled`: sets `cancelled_reason`. Allowed **only from `pending` / `confirmed`**.
- `confirmed → assigned`: done by `routes.create_route` when the order joins a route stop.
- `assigned → en_route`: route-level — flipping the route to `in_progress` propagates
  `en_route` to every stop's order (§6 offered per-stop or route-level; route-level chosen).
- `en_route → delivered`: `driver/stops/{id}/delivered`; enqueues `request_review`.
- **`assigned → confirmed`** is an addition beyond the §6 diagram — the "remove an order
  from a route" step needed by `PATCH /dispatch/routes`.
- A no-op transition (`x → x`) is allowed; `delivered` and `cancelled` are terminal.

Route status has its own flow: `planned → in_progress → completed`. `in_progress` marks
the vehicle `on_route`; `completed` marks it `available`.

---

## 5. API surface (`/api/v1`)

| Group | Endpoints |
|---|---|
| **Auth** | `POST /auth/otp/request` · `POST /auth/otp/verify` |
| **Users** | `GET/POST /users/` (admin) · `GET/PATCH/DELETE /users/me` · `GET/PATCH/DELETE /users/{id}` |
| **Orders** | `POST /orders` (guest or auth) · `GET /orders?status=&mine=` · `GET /orders/{id}` (owner / dispatch / guest `?phone=`) · `PATCH /orders/{id}/confirm` (dispatcher) · `PATCH /orders/{id}/cancel` |
| **Dispatch** | `GET /dispatch/pending-map` · `GET /dispatch/routes?planned_date=` · `POST /dispatch/routes` · `PATCH /dispatch/routes/{id}` (reorder = permutation; status) |
| **Driver** | `GET /driver/routes/today` (204 if none) · `PATCH /driver/stops/{id}/delivered` · `PATCH /driver/stops/{id}/payment-collected` |
| **Fleet** | `GET/POST /vehicles` · `PATCH /vehicles/{id}` · `POST /vehicles/{id}/maintenance-logs` |
| **Pricing** | `GET /pricing/current` · `POST /pricing` (admin) |
| **Reviews** | `POST /reviews` (signed token OR owner/admin) · `GET /reviews?order_id=` (admin) |
| **Reports** | `GET /admin/reports/cash-reconciliation?date=` (admin) |
| **Realtime** | `WS /ws/dispatch` · `WS /ws/driver/{driver_id}` (auth via `?token=`) |

Role dependencies live in `app/api/deps.py`: `CurrentUser`, `CurrentUserOptional`,
`AdminUser`, `DispatcherUser` (dispatcher+admin), `DriverUser` (driver+admin),
`require_roles(*roles)`.

---

## 6. Auth — OTP (spec §9)

1. `POST /auth/otp/request {phone_number}` → `otp.request_otp`: 6-digit code, stored in
   Redis at `otp:code:<phone>` with TTL `OTP_EXPIRY_SECONDS` (300), sent via
   `notifications.send`. Always returns a generic message (no account enumeration).
2. `POST /auth/otp/verify {phone_number, code}` → checks the code (single-use, max 5
   attempts per code), `get_or_create_user_by_phone` (new users → `customer`;
   pre-provisioned dispatcher/driver/admin keep their role), returns a `Token` via the
   template's `security.create_access_token`.
3. `get_current_user` (JWT decode) is unchanged; only issuance moved.

Dispatcher / driver / admin accounts are created by an admin through `POST /users/`.
The first admin is seeded by `init_db` from `FIRST_SUPERUSER_PHONE` — **run
`prestart.sh` before anyone logs in** (see §9).

Getting a code in dev: `docker compose logs worker | grep stub-sms`, or
`docker compose exec redis redis-cli get "otp:code:+2135XXXXXXXX"`.

---

## 7. Background jobs & notifications (spec §11, §14)

`app/tasks.py`, discovered by `app.worker` via `autodiscover_tasks(["app"])`:

- **`send_notification(order_id, purpose, *, channel="sms", message=None)`** — resolves
  the phone from the order, calls `notifications.send`, writes a `NotificationLog` row
  (`sent` / `failed`).
- **`request_review(order_id)`** — delivered orders only; sends the signed review link
  and logs a `review_request` notification.
- `enqueue_notification` / `enqueue_review_request` — fire-and-forget helpers, never
  raise; called from the service layer.

Also `notify_dispatchers_new_order`, `notify_driver_route_assigned` (Telegram), and
`sms_gateway_healthcheck` (Celery Beat, every 5 min — the `worker` runs with `-B`).

Wiring:

| Event | Task(s) |
|---|---|
| `create_order` | `send_notification(order_id, "order_received")` (customer SMS) + `notify_dispatchers_new_order` (team Telegram) |
| route created | `notify_driver_route_assigned` (team Telegram) + the `/ws/driver` push |
| stop `delivered` | `request_review(order_id)` |
| every 5 min | `sms_gateway_healthcheck` → Telegram alert to dispatchers if the SMS gateway is down |

**Provider seam** — `app/services/notifications.py` exposes `send(phone, message)` behind
a `NotificationProvider` protocol. `_build_provider()` picks, in order:
`AndroidGatewaySmsProvider` (SIM-based SMS gateway, when `SMS_GATEWAY_BASE_URL` +
`SMS_GATEWAY_API_KEY` are set) → the Infobip/WhatsApp provider (`SMS_PROVIDER_*`,
reserved, not built) → `LoggingProvider` stub. `provider_healthy()` feeds the health
check. No calling code changes between providers. See
[`interim-messaging.md`](./interim-messaging.md).

**Telegram (internal team)** — `app/services/telegram.py` + `POST /telegram/webhook`.
Accounts link via a one-time code (`/link <code>`, Redis, 1 h) shown when an admin creates
a dispatcher/driver; `users.telegram_chat_id` (migration `0005`) is set only by that flow.
Not customer-facing.

**Reviews** — `app/services/reviews.py`: `make_review_token` (JWT, `sub=order_id`,
`purpose=review`, 14-day TTL), `create_review` (delivered orders only; authorised by a
valid token **or** the logged-in owner / an admin; one review per order),
`list_reviews` (admin). Public link: `/review/{order_id}?token=…`. No public display of
reviews.

---

## 8. Realtime (spec §10)

`app/services/ws.py::ConnectionManager` — a single module-global `manager`, an
in-memory `set` for dispatch connections and a `dict[driver_id → set]` for drivers, no
pub/sub broker. Producers are synchronous service code running in a threadpool worker,
so `notify_dispatch` / `notify_driver` are **sync** and hop back onto the event loop
via `loop.call_soon_threadsafe`. The loop handle is bound in the FastAPI lifespan
(`app/main.py`). Dead sockets are pruned on send; if a client isn't connected the event
is dropped (clients also poll — `useLiveChannel` falls back silently).

| Emitted from | Channel | Payload `type` |
|---|---|---|
| `orders.transition_status` → `confirmed` | dispatch | `order_confirmed` |
| `routes.create_route` | driver | `route_assigned` |
| `routes.update_route` status change | dispatch | `route_status` |

Endpoints: `WS /ws/dispatch` (dispatcher/admin), `WS /ws/driver/{driver_id}` (that
driver or admin). Auth via `?token=<jwt>` query param (browsers can't set WS headers).

---

## 9. Frontend route groups (spec §16)

Routing was restructured: the template's authed dashboard at `/` is gone. `_layout`
still exists but only gates `/admin`, `/settings`, `/reports`.

| Route | Access | What |
|---|---|---|
| `/` | public | Order form: Leaflet pin-picker (OSM tiles, emoji `divIcon`), landmark, commune, litres (capped 4000), phone; live price from `/pricing/current`; submit → redirect to tracking |
| `/track/:orderId?phone=` | public | Status timeline, phone-gated (matches `order.customer_phone`), polls every 15 s |
| `/review/:orderId?token=` | public | 1–5 star rating + comment |
| `/login` | public | Two-step phone → code; role-aware redirect (dispatch / driver / customer) |
| `/dispatch` | dispatcher / admin | Tabs: confirm pending orders · pending-orders map + route builder (pick stops, truck, driver, date) · routes list with start/complete · fleet + add vehicle. Subscribes to `/ws/dispatch` |
| `/driver` | driver / admin | Today's route; per-stop *mark delivered* / *cash encaissé*. Subscribes to `/ws/driver/{id}` |
| `/admin` | admin | User management (roles) — adapted template table |
| `/reports` | admin | Cash reconciliation table + date picker |

UI copy is French (the Batna audience); strings are inline and i18n-ready but not
translated — confirm the shipping language before wiring translations (§19).

Deps added: `leaflet`, `react-leaflet@5` (React 19), `@types/leaflet`. Everything else
reuses the template `Card` / `Tabs` / `Input` / `Button` / `Checkbox` / `AuthLayout`
and the generated client.

---

## 10. Cash reconciliation (spec §13)

`app/services/reports.py::cash_reconciliation(session, on_date)` joins delivered
`route_stops` → `orders` → driver for routes with `planned_date == on_date` and
aggregates per driver in Python (one operational day is small volume):
`delivered_stops`, `expected_cash_dzd` (Σ `total_price_dzd`), `collected_stops`,
`collected_cash_dzd` (where `payment_collected`), plus day totals.
`GET /admin/reports/cash-reconciliation?date=YYYY-MM-DD` (defaults to today, admin only).

---

## 11. Task-by-task changelog

| Task | Commit subject |
|---|---|
| 1 | Task 1: remove items demo and email/password auth flow |
| 2 | Task 2: PostGIS image, redis and worker services |
| 3 | Task 3: SQLModel models for the full section 5 schema |
| 4 | Task 4: phone-number + OTP auth (section 9) |
| 5 | Task 5: order endpoints + status state machine (sections 6, 8) |
| 6 | Task 6: dispatch + driver + fleet endpoints (section 8) |
| 7 | Task 7: WebSocket connection manager + dispatch/driver channels (section 10) |
| 8 | Task 8: Celery tasks + notification stub, wired to order/delivery events |
| 9 | Task 9: three frontend route groups (section 16) |
| 10 | Task 10: cash-reconciliation report (section 13) |
| 11 | Task 11: leave route clustering for a follow-up pass |
| 12 | Task 12: test suite for the water-delivery platform |

Each commit message carries the per-task assumptions/deviations.

---

## 12. Open questions (spec §20) — decisions taken

| Q | Decision |
|---|---|
| 20.1 Password fallback for dispatcher/admin | **OTP-only for everyone.** No password anywhere; first admin seeded by phone. |
| 20.2 Guest checkout | **Allowed.** `POST /orders` works anonymously with `customer_phone`; guests track by `?phone=`. |
| 20.3 SMS/WhatsApp provider | Interim: SIM-based Android SMS gateway for customers + Telegram for the team (see interim-messaging.md). Infobip/WhatsApp is the planned upgrade. |
| 20.4 Depot / yard location | Not needed yet (only the deferred clustering uses it). See `follow-ups.md`. |

## 13. Deviations from the spec

- Plural table names (`users`, …) matching the §5 headers, not the template's singular.
- `assigned → confirmed` transition added (route un-assign) — everything else matches §6.
- `Order.status` has a DB index (additive; heavy dispatch filtering).
- Worker command uses `app.worker.celery_app` (spec wrote `app.worker`) so `-A` resolves
  the app object explicitly.
- Route status flow + app-managed `Vehicle.status` (`on_route` on start, `available` on
  completion) — spec defines the enums, not the transitions.
- Route "reorder" is permutation-only (no add/remove stops in MVP).
- `GET /dispatch/routes` added — the dashboard needs a route list.
- Native PostgreSQL enum types for enum columns.
- Frontend `/` is the public customer site; the authed dashboard was removed.
- Playwright config drops the mandatory email-login setup; only public-flow E2E is
  included (authenticated E2E needs an OTP test hook — see `follow-ups.md`).

---

## 14. Running locally

**Prereqs:** Docker + Docker Compose. (Host-side backend dev also needs `uv`, which
fetches Python 3.14 itself.)

### Environment (`/.env`, already populated with dev defaults)

New variables this pass:

```
POSTGIS_ENABLED=true
REDIS_URL=redis://localhost:6379/0        # compose hardcodes redis://redis:6379/0 in-container
OTP_EXPIRY_SECONDS=300
SMS_PROVIDER_API_KEY=
SMS_PROVIDER_BASE_URL=
ROUTE_CLUSTER_DISTANCE_METERS=1500
FIRST_SUPERUSER_PHONE=+213555000000       # replaces FIRST_SUPERUSER (email)
```

Before any non-dev deployment change `SECRET_KEY`, `POSTGRES_PASSWORD` and
`FIRST_SUPERUSER_PHONE`.

### Start

```bash
docker compose up -d --build
# proxy, db (PostGIS), redis, backend, worker, adminer  (+ flower in dev)

docker compose exec backend bash scripts/prestart.sh
# = alembic upgrade head  +  python app/initial_data.py (seeds the admin)
# (WORKDIR in the container is /app/backend, so the path is scripts/…, not backend/scripts/…)
```

> **`failed to resolve host 'db'`** from `prestart.sh` means the Compose stack is in
> an inconsistent state — usually the `db` container is running but detached from the
> project network (a leftover from an interrupted `down`/`up` cycle). Fix:
> `docker compose down --remove-orphans && docker compose up -d`, then re-run
> `prestart.sh`. Add `-v` to `down` only if you also want to discard the database
> volume (dev only).

**Run `prestart.sh` before anyone logs in** — `init_db` only creates the admin if the
phone is absent; if someone OTP-authenticates with `FIRST_SUPERUSER_PHONE` first they'd
be created as a plain customer.

- App / API: `http://localhost` (Traefik) — OpenAPI at `/api/v1/openapi.json`, docs `/docs`
- Adminer: `http://adminer.localhost` · Flower (dev): `http://localhost:5555`

### Seed data

Only the bootstrap admin. Then, as admin (OTP login):

```
POST /api/v1/users/     {phone_number, role: "dispatcher" | "driver"}
POST /api/v1/vehicles   {plate_number, capacity_liters}
POST /api/v1/pricing    {price_per_liter_dzd}   # optional; default is 4 DZD/L
```

### Migrations

```bash
docker compose exec backend alembic upgrade head
docker compose exec backend alembic downgrade -1
docker compose exec backend alembic check                      # drift check (clean)
docker compose exec backend alembic revision --autogenerate -m "msg"
```

### Regenerate the TS client after backend changes

```bash
bash scripts/generate-client.sh        # needs `bun` on PATH
```

---

## 15. Testing

```bash
# backend — needs the db service up
docker compose exec backend bash scripts/tests-start.sh    # pytest + coverage

# frontend public-flow E2E — needs the app running
cd frontend && bunx playwright test
```

Backend tests (`backend/tests/`, template fixture pattern — `conftest.py` +
`tests/utils/*`): `test_auth`, `test_users`, `test_orders` + `services/test_orders_service`
(state machine), `test_pricing`, `test_dispatch`, `test_driver`, `test_vehicles`,
`test_ws` + `services/test_ws`, `test_reviews`, `test_tasks`, `test_reports`.
`conftest` swaps the OTP store for `fakeredis` and runs Celery eager.

Frontend (`frontend/tests/`): `home-order.spec.ts`, `login-otp.spec.ts` +
`utils/random.ts` (Playwright browsers not installed in the build env; these run via the
compose `playwright` service or `bunx playwright test`).

---

## 16. Internationalisation (FR / EN / AR)

> §19 lists multi-language UI as out of scope for the initial pass ("confirm which
> language with the client first"). Added afterwards **at the client's direction**:
> French kept, English and Arabic added, user-selectable.

- `i18next` + `react-i18next` + `i18next-browser-languagedetector`. Config in
  `src/i18n/index.ts`; resources in `src/i18n/locales/{fr,en,ar}.json` (169 keys each,
  key sets kept parallel — there's a check in the build guard). `fallbackLng: "fr"`.
- Language is detected from `localStorage["watergo-lang"]` then the browser, and
  persisted on change. `applyDirection()` sets `<html lang>` and `<html dir>`
  (`rtl` for `ar`, `ltr` otherwise) on load and on every `languageChanged`.
- `LanguageSwitcher` component — in `AuthLayout` (login / review), `PublicTopBar`
  (customer `/` and `/track`), and the app sidebar footer.
- Numbers/prices go through `src/lib/format.ts::fmtNumber` → `Intl.NumberFormat`
  with `ar-DZ` / `fr-DZ` / `en` so Arabic keeps Latin digits for money.
- Coverage: every custom route (`/`, `/track`, `/review`, `/login`, `/dispatch`,
  `/driver`, `/reports`), the sidebar, settings, admin user-management dialogs,
  not-found / error pages, and the appearance menu. Order/route **statuses** and
  **roles** are translated via `t(\`status.${x}\`)` / `t(\`roles.${x}\`)` /
  `t(\`routeStatus.${x}\`)`.
- Playwright: `login-otp.spec.ts` adds a switcher + RTL assertion; specs pin
  `watergo-lang=en` for stable text assertions.

Adding a language: drop a `locales/<lng>.json` with the same keys, add the code to
`SUPPORTED_LANGUAGES` (and `RTL_LANGUAGES` if it's RTL) in `src/i18n/index.ts`.

## 17. Deferred

See [`follow-ups.md`](./follow-ups.md): the dispatcher "suggest a route" button
(§12 `ST_ClusterDBSCAN` clustering + nearest-neighbour ordering, draft-only), the depot
location (§20.4), and authenticated dispatch/driver E2E (needs a dev-only OTP-code
endpoint).
