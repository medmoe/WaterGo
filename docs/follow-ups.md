# Deferred work

## Messaging — interim setup is live; Infobip + WhatsApp is the upgrade

**Now:** customer SMS goes through a SIM-based Android SMS gateway
(`AndroidGatewaySmsProvider`), and the internal team gets Telegram push
notifications. Details and remaining physical/operational steps:
[`interim-messaging.md`](./interim-messaging.md).

**Upgrade path (when order volume justifies the cost):**
- Customer SMS → implement an Infobip-backed `NotificationProvider` and add its
  branch to `notifications._build_provider()`. One place; orders/dispatch/driver
  code is untouched (they only call `notifications.send`).
- WhatsApp → additive; a template-based provider layered in independently.
- Telegram for the team stays (free, no volume ceiling, not a customer channel).

## Route clustering — the dispatcher's "suggest a route" button (spec section 12)

**Status: not built.** Task 18.11 says to ship manual route building first and
leave clustering for a follow-up pass. Automated / scheduled clustering is also
explicitly out of scope (section 19).

For the on-demand version, the plan from section 12 is:

1. Query all `confirmed` orders without a `route_stop`, as `geography` points
   (`app/services/routes.py::pending_map` already returns exactly this set).
2. `SELECT id, ST_ClusterDBSCAN(geom::geometry, eps := :eps, minpoints := 1)
   OVER () AS cluster ...` with `eps` derived from
   `settings.ROUTE_CLUSTER_DISTANCE_METERS` (default 1500 m; note DBSCAN eps is
   in the SRID's units, so cluster on `geography` cast to a metric projection
   or use `ST_ClusterDBSCAN` on `geography` with a metres threshold on PostGIS
   ≥ 3.4).
3. Within each cluster, order stops with a nearest-neighbour walk starting from
   the depot/yard.
4. Return the grouping + order as a **draft** to a new endpoint, e.g.
   `POST /dispatch/routes/suggest`. The dispatcher edits before confirming;
   never auto-create a route.

### Open question 20.4 — depot / yard location

The nearest-neighbour walk in step 3 needs a start point. There is no company
yard location in the spec or config yet. When clustering is built, add
`ROUTE_DEPOT_LAT` / `ROUTE_DEPOT_LNG` settings (or a singleton row) and confirm
the real coordinates with the client.
