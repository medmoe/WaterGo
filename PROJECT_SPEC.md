# Batna water delivery platform — build specification

This document is the source of truth for turning the cloned `fastapi/full-stack-fastapi-template`
into our project. Follow it in order. Where the template already provides something usable,
adapt it rather than rewriting from scratch. Where a decision isn't specified here, flag it
instead of guessing — see "open questions" at the end.

## 1. Context

A water tanker delivery business operating in the **Wilaya of Batna, Algeria**. Customers submit
water orders on a website. A dispatcher calls each customer to confirm before sending a tanker.
Drivers collect cash on delivery. The business wants to batch nearby orders onto single truck
routes to cut fuel and tire wear versus one truck per order.

Three user-facing experiences, one backend:
- **Customer site** — place an order, track its status
- **Dispatcher dashboard** — see pending orders on a map, confirm them by phone, group them into
  routes, assign a truck/driver
- **Driver view** — see today's assigned stops in order, mark each delivered, mark cash collected

## 2. Confirmed tech stack

- Backend: FastAPI + SQLModel + Alembic (from the template)
- Frontend: React + Vite + TypeScript + Tailwind (from the template), generated API client
- Database: **PostgreSQL with the PostGIS extension** (template ships plain Postgres — swap the image)
- Background jobs / real-time: Celery + Redis (not in the template — add it)
- Auth: phone number + OTP (replace the template's email/password auth)
- Payment: cash only for v1 — no payment gateway integration
- Deployment target: Docker Compose on a VPS, later decision

## 3. What to strip from the template vs. keep

**Keep and adapt:**
- Docker Compose structure, `.env` pattern, Alembic setup
- FastAPI app structure (`app/api/routes/`, `app/models.py`, `app/crud.py`, dependency injection
  pattern for DB sessions and current-user)
- Frontend build tooling, generated TypeScript client, routing setup, base UI components
- Test scaffolding (`pytest`, frontend test setup) — keep the pattern, replace the test content

**Remove:**
- The `items` example resource (backend router, model, CRUD, frontend pages) — it was only a demo
- Email-based login, password recovery flow, and any email-sending code — we don't use email
- Any seed data referencing the `items` demo

**Add (not present in template):**
- PostGIS-enabled Postgres image
- Celery worker + Redis service in `docker-compose.yml`
- WebSocket routes
- SMS/WhatsApp sending integration (provider TBD — stub it behind an interface for now, see
  section 11)

## 4. Domain model overview

Core entities: `User` (with a role), `Location`, `Vehicle`, `MaintenanceLog`, `Order`, `Route`,
`RouteStop`, `Review`, `PricingSetting`, `NotificationLog`.

Roles: `customer`, `dispatcher`, `driver`, `admin`. Use a single `users` table with a `role`
column rather than separate tables per role — simpler joins, and a person could in theory hold
more than one role later.

## 5. Database schema

Write these as SQLModel classes. Use UUID primary keys (the template already does this).
All `created_at` / `updated_at` columns are implied on every table even where not listed.

### `users`
| column | type | notes |
|---|---|---|
| id | UUID PK | |
| phone_number | string, unique, indexed | E.164 format, e.g. `+2135XXXXXXXX` |
| full_name | string, nullable | |
| role | enum: customer, dispatcher, driver, admin | |
| is_active | bool, default true | |

No password field for customers/drivers — OTP only. Dispatcher/admin accounts may optionally keep
a password as a fallback login method; decide based on how many admin accounts there will be
(if just 1-2, OTP-only is fine and simpler).

### `locations`
| column | type | notes |
|---|---|---|
| id | UUID PK | |
| user_id | FK → users, nullable | nullable so a location can be attached to a guest order |
| geom | PostGIS `geography(Point, 4326)` | lat/lng as a geography point |
| landmark_text | string | free text, e.g. "près de la mosquée El Atik" |
| commune | string | within Wilaya of Batna |
| raw_lat / raw_lng | float, float | keep alongside `geom` for easy display without PostGIS functions |

### `vehicles`
| column | type | notes |
|---|---|---|
| id | UUID PK | |
| plate_number | string, unique | |
| capacity_liters | int | ranges 2000–4000 per the business's fleet |
| status | enum: available, on_route, maintenance | |
| current_odometer_km | int | updated manually or by driver |

### `maintenance_logs`
| column | type | notes |
|---|---|---|
| id | UUID PK | |
| vehicle_id | FK → vehicles | |
| type | enum: tire, oil, service, other | |
| odometer_km_at_event | int | |
| notes | string, nullable | |

This table is what eventually lets the owner see km-driven-per-tire-change trending upward —
not needed for MVP UI, but the table should exist from the start so data accumulates.

### `pricing_settings`
| column | type | notes |
|---|---|---|
| id | UUID PK | |
| price_per_liter_dzd | numeric | starts at 4 |
| effective_from | timestamp | |

Always read the *latest* row where `effective_from <= now()` to get the active price. Never
update a row in place — insert a new row when price changes, so historical orders can still be
traced to the price that applied when they were placed.

### `orders`
| column | type | notes |
|---|---|---|
| id | UUID PK | |
| customer_id | FK → users, nullable | nullable if guest checkout is allowed |
| customer_phone | string | always stored directly on the order, even if `customer_id` is set, so dispatcher can always call regardless of account state |
| location_id | FK → locations | |
| quantity_liters | int | customer-entered, free amount |
| price_per_liter_dzd | numeric | snapshot from `pricing_settings` at order time — never recompute later |
| total_price_dzd | numeric | `quantity_liters * price_per_liter_dzd`, stored, not computed on read |
| status | enum, see section 6 | |
| requested_window_start / requested_window_end | timestamp, nullable | optional customer preference |
| confirmed_by | FK → users, nullable | dispatcher who confirmed by phone |
| confirmed_at | timestamp, nullable | |
| cancelled_reason | string, nullable | |

### `routes`
| column | type | notes |
|---|---|---|
| id | UUID PK | |
| vehicle_id | FK → vehicles | |
| driver_id | FK → users | must have role=driver |
| planned_date | date | |
| status | enum: planned, in_progress, completed | |

### `route_stops`
| column | type | notes |
|---|---|---|
| id | UUID PK | |
| route_id | FK → routes | |
| order_id | FK → orders, unique | one order belongs to at most one route stop |
| sequence_number | int | order within the route |
| delivered_at | timestamp, nullable | |
| payment_collected | bool, default false | |
| payment_collected_at | timestamp, nullable | |

### `reviews`
| column | type | notes |
|---|---|---|
| id | UUID PK | |
| order_id | FK → orders, unique | |
| customer_id | FK → users, nullable | |
| rating | int, 1–5 | |
| comment | string, nullable | |

### `notification_logs`
| column | type | notes |
|---|---|---|
| id | UUID PK | |
| order_id | FK → orders, nullable | |
| channel | enum: sms, whatsapp | |
| purpose | enum: order_received, confirmation_call_reminder, review_request, other | |
| status | enum: sent, failed | |

## 6. Order status state machine

```
pending → confirmed → assigned → en_route → delivered
   ↓          ↓
cancelled  cancelled
```

- `pending`: customer just submitted the order. Not yet actionable by dispatch.
- `confirmed`: dispatcher called the customer, verified quantity/location/price, set
  `confirmed_by` and `confirmed_at`. Only `confirmed` orders are eligible to be added to a route.
- `assigned`: order has been added to a `route_stop` on a planned route.
- `en_route`: the route's status flips to `in_progress` and this propagates to its stops, OR
  set per-stop when the driver starts toward that specific stop — pick per-stop granularity if
  the dispatcher wants to see progress mid-route, otherwise route-level is simpler for MVP.
- `delivered`: driver marks the stop delivered. This also triggers the review-request
  notification (see section 11).
- `cancelled`: allowed from `pending` or `confirmed` only, not after a truck has been dispatched.

Enforce these transitions in a single service function (e.g. `orders_service.transition_status`)
rather than letting routers set `status` directly — this keeps the rules in one place.

## 7. Pricing rules

- Price is per-liter, currently 4 DZD, adjustable by admin via a settings endpoint.
- No minimum order enforced for MVP unless the client specifies one later.
- Cap `quantity_liters` per order at the largest tanker capacity (4000L) — a single order can't
  exceed what one truck can carry, since there's no multi-truck-per-order flow in MVP.

## 8. API endpoints

Group these as separate routers under `app/api/routes/`, following the template's existing
pattern (`app/api/routes/orders.py`, etc.)

### Auth
- `POST /auth/otp/request` — body: `{phone_number}`. Sends an OTP via SMS/WhatsApp.
- `POST /auth/otp/verify` — body: `{phone_number, code}`. Returns JWT on success.

### Orders
- `POST /orders` — customer creates an order (auth optional if guest checkout allowed)
- `GET /orders/{id}` — order detail
- `GET /orders?status=&mine=true` — list, filterable; customers see only their own, dispatchers see all
- `PATCH /orders/{id}/confirm` — dispatcher only, sets status → confirmed
- `PATCH /orders/{id}/cancel` — allowed states only, see section 6

### Dispatch
- `GET /dispatch/pending-map` — geo points of all `confirmed` orders not yet on a route, for the
  dispatcher map
- `POST /dispatch/routes` — create a route: `{vehicle_id, driver_id, planned_date, order_ids: []}`
- `PATCH /dispatch/routes/{id}` — reorder stops, change status

### Driver
- `GET /driver/routes/today` — the logged-in driver's route and ordered stops for today
- `PATCH /driver/stops/{id}/delivered` — mark delivered
- `PATCH /driver/stops/{id}/payment-collected` — mark cash collected

### Fleet
- `GET/POST/PATCH /vehicles`
- `POST /vehicles/{id}/maintenance-logs`

### Pricing
- `GET /pricing/current`
- `POST /pricing` — admin only, inserts a new pricing row

### Reviews
- `POST /reviews` — `{order_id, rating, comment}`, only for delivered orders
- `GET /reviews?order_id=` (admin/reporting)

### Realtime
- `WS /ws/dispatch` — pushes new pending orders and route status changes to the dispatcher board
- `WS /ws/driver/{driver_id}` — pushes new route assignments to a driver

## 9. Auth details

Replace the template's email+password flow entirely with OTP:

1. Customer/driver enters phone number → `POST /auth/otp/request` → backend generates a
   short-lived code (e.g. 6 digits, 5 min expiry), stores it (Redis is a good fit, keyed by
   phone number), sends via SMS/WhatsApp.
2. `POST /auth/otp/verify` checks the code, creates the user if it doesn't exist yet (role
   defaults to `customer` for self-serve signup; `dispatcher`/`driver`/`admin` accounts are
   created manually by an admin, not self-registered), issues a JWT exactly like the template
   already does after its own login endpoint.
3. Keep the template's JWT dependency (`get_current_user`) as-is — only the issuance path changes.

## 10. Real-time updates

Add a lightweight WebSocket connection manager (a simple in-memory dict of active connections is
fine at this scale — no need for a pub/sub broker yet). On any event that should push to the
dispatcher board (new order confirmed, route status change) or to a driver (new stop assigned),
broadcast to the relevant open connections. If a driver isn't connected, they'll see the update on
next page load/poll — a fallback poll is worth keeping even with WebSockets in place.

## 11. Background jobs (Celery + Redis)

Add a `worker` service to `docker-compose.yml` alongside the existing `backend` service, both
pointing at the same codebase, `celery -A app.worker worker` as the run command.

Jobs to implement:
- `send_notification(order_id, purpose)` — sends SMS/WhatsApp. **Stub the actual provider call
  behind a small interface** (e.g. `app/services/notifications.py` with a `send(phone, message)`
  function) so swapping in a real SMS gateway later doesn't touch calling code.
- `request_review(order_id)` — triggered when a stop is marked `delivered`; sends a short message
  with a link to the review form.
- `suggest_route_clusters()` — optional for MVP, can be manually triggered by the dispatcher
  hitting an endpoint rather than running on a schedule at first. See section 12.

## 12. Route clustering logic (for the dispatcher's "suggest a route" button)

Not required for the very first working version — the dispatcher can build routes manually by
picking orders on the map. Build this as a second pass:

1. Query all `confirmed` orders without a route, as geography points.
2. Use PostGIS `ST_ClusterDBSCAN` with a distance threshold (start around 1.5km, make it
   configurable) to group nearby pending orders.
3. Within a cluster, order stops with a nearest-neighbor walk starting from the depot/yard
   location.
4. Return the suggested grouping and order to the dispatcher as a draft — they can edit before
   confirming route creation. Never auto-create a route without dispatcher review.

## 13. Cash payment handling

No payment gateway. The only two fields that matter are `route_stops.payment_collected` and
`payment_collected_at`. Build a simple end-of-day report endpoint
(`GET /admin/reports/cash-reconciliation?date=`) that sums `total_price_dzd` for delivered stops
per driver, so the owner can check declared cash against expected cash.

## 14. Reviews

- Triggered automatically after a stop is marked delivered (see section 11).
- Public review link needs no login — a signed token tied to the order id is enough
  (e.g. `/review/{order_id}?token=...`), since requiring OTP login just to leave a rating will
  kill response rate.
- No public display of reviews for MVP — they're for the owner's internal reporting only.

## 15. Infrastructure changes to `docker-compose.yml`

- Replace `postgres:*` image with `postgis/postgis:16-3.4` (or current stable equivalent)
- Add `redis` service
- Add `worker` service (Celery, same image/build as backend)
- Optionally add `flower` for Celery monitoring during development (drop before production if
  not needed)
- Add `POSTGIS` extension creation to the first Alembic migration:
  `CREATE EXTENSION IF NOT EXISTS postgis;`

## 16. Frontend structure

Three route groups within the same React app (simplest to ship and maintain as one deployable
unit for now; can split later if needed):

- `/` — customer-facing: order form (map pin picker, landmark text, liters input, phone entry),
  order tracking page
- `/dispatch/*` — dispatcher dashboard: map of pending orders, route builder, fleet list —
  gate behind login + role check
- `/driver/*` — driver's stop list for the day, mark-delivered and mark-paid actions — gate
  behind login + role check

Reuse the template's existing auth context/hooks, generated API client, and component library;
just point them at the new endpoints instead of the `items`/user-management demo pages.

## 17. New environment variables to add

```
POSTGIS_ENABLED=true
REDIS_URL=redis://redis:6379/0
SMS_PROVIDER_API_KEY=
SMS_PROVIDER_BASE_URL=
OTP_EXPIRY_SECONDS=300
ROUTE_CLUSTER_DISTANCE_METERS=1500
```

## 18. Task list for the agent, in order

1. Remove the `items` demo (backend router/model/CRUD, frontend pages) and the email/password
   auth flow (backend routes, email-sending code, frontend login-by-email forms).
2. Swap the Postgres image for PostGIS in `docker-compose.yml` and add the `redis` and `worker`
   services.
3. Write the SQLModel models from section 5. One Alembic migration per logical group is fine
   (e.g. users+auth, then locations+vehicles, then orders+routes, then reviews+pricing) rather
   than one giant migration.
4. Implement OTP auth (section 9), replacing the template's login endpoints.
5. Implement the order endpoints and status state machine (sections 6, 8) as a service layer
   function, not inline in routers.
6. Implement dispatch + driver endpoints (section 8).
7. Add the WebSocket connection manager and the two channels (section 10).
8. Add the Celery worker, the notification-sending stub, and wire it to fire on order-created and
   stop-delivered events (section 11, 14).
9. Build the three frontend route groups (section 16), reusing existing template components
   where they fit.
10. Add the cash-reconciliation report endpoint (section 13).
11. Leave route clustering (section 12) for a follow-up pass — manual route building first.
12. Write/replace tests for whatever replaces the `items` demo, following the template's existing
    test patterns.

## 19. Explicitly out of scope for this pass

- Online payment integration
- Native mobile app
- Public-facing reviews display
- Multi-wilaya / zone expansion logic
- Automated (scheduled) route clustering — manual/on-demand only for now
- Multi-language UI (build with i18n-friendly string handling in mind, but only ship one
  language now — confirm which with the client before wiring up translations)

## 20. Open questions to resolve before or during build

- Should dispatcher/admin accounts have a password fallback in addition to OTP, or OTP-only?
- Is guest checkout (no account) allowed, or must every customer create an account via OTP first?
- Which SMS/WhatsApp provider will actually be used in Algeria? (Affects the interface in
  section 11 but not the surrounding code, so it can be decided after scaffolding starts.)
- Is there a company "yard"/depot location to use as the route start point for the
  nearest-neighbor ordering in section 12?