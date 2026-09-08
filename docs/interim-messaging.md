# Interim messaging — SIM SMS gateway (customers) + Telegram (team)

The "get real delivery live cheaply, upgrade to Infobip + WhatsApp later" setup. Both
pieces sit behind the `notifications.py` provider seam, so the eventual paid integration
touches almost nothing else.

- **Part A** — a physical Android phone + local SIM sends customer SMS (OTP, order
  received, review request) through an on-device gateway API.
- **Part B** — a free Telegram bot pushes internal-team notifications (new order → all
  linked dispatchers; route assigned → that driver; SMS gateway down → dispatchers).

---

## Part A — Android SMS gateway

### Code (done)
`app/services/notifications.py::AndroidGatewaySmsProvider`. Selected automatically when
`SMS_GATEWAY_BASE_URL` **and** `SMS_GATEWAY_API_KEY` are set (precedence: gateway >
`SMS_PROVIDER_*` (reserved for Infobip) > `LoggingProvider` stub). `send()` returns
`False` on any transport/HTTP error — it never raises, so a request that triggers an SMS
still completes.

The exact endpoint / auth / body depends on the gateway app you install. The provider
currently assumes `POST {base}/message`, `Authorization: Bearer <key>`, body
`{"message", "phoneNumbers": [phone], "deviceId"?}`, `2xx` = accepted, and `GET
{base}/health` for the check. **Adjust `_post()` / `healthy()` to match the app's API
reference.**

### Health check (done)
`app.tasks.sms_gateway_healthcheck` runs every 5 min via Celery Beat (the `worker`
service runs with `-B`). If `notifications.provider_healthy()` is `False` it messages all
linked dispatchers on Telegram. With only the stub active it's a no-op.

### Still to do (physical / operational)
1. Spare Android phone (8+), local SIM (Djezzy/Mobilis/Ooredoo), generous SMS bundle.
   Permanent power + office Wi-Fi. **Disable battery optimization for the gateway app** —
   the #1 cause of "it silently stopped".
2. Install an OSS gateway app (e.g. capcom6 `android-sms-gateway`), grant SMS permission,
   set an API key. Choose **relay/cloud mode** (backend on the VPS, phone in the office →
   the phone only needs outbound internet).
3. Put the real values in `.env.local` (git-ignored; loaded by settings and by the
   backend/worker containers via `env_file`):
   ```
   SMS_GATEWAY_BASE_URL=...
   SMS_GATEWAY_API_KEY=...
   SMS_GATEWAY_DEVICE_ID=        # only if you run >1 phone
   ```
4. Test: send yourself an OTP; then take the phone offline and confirm the failure is
   logged (and the triggering request still returns), not a crash.

### Limits — know them
One phone + a consumer SIM ≈ a handful of SMS/min, and it's a single point of failure
(power / Wi-Fi / SIM balance). Fine for a pilot; add phones or move to Infobip to scale.
Keep the stub reachable as a manual fallback (the code is still logged and can be read to
a customer by phone).

---

## Part B — Telegram bot

### Code (done)
- `app/services/telegram.py` — `send_message`, `send_to_role(session, role, text)` (linked
  + active users only), Redis-backed one-time link codes (`tg:link:<code>`, 1 h,
  single-use), `handle_update()` for `/start` and `/link <code>`.
- `users.telegram_chat_id` column (migration `0005`), set only by the link flow.
- `POST /telegram/webhook` — inbound updates; optional `X-Telegram-Bot-Api-Secret-Token`
  check against `TELEGRAM_WEBHOOK_SECRET`; always answers `200`.
- `POST /users/` returns a `telegram_link_code` for new dispatcher/driver accounts;
  `POST /users/{id}/telegram-link-code` re-issues one. The `/admin` "Add user" dialog
  shows the code (FR/EN/AR).

### Still to do (operational)
1. `@BotFather` → `/newbot` → token. Put it in `.env.local` as `TELEGRAM_BOT_TOKEN=`
   (**rotate the token that was pasted in plaintext during setup**).
2. Register the webhook with Telegram once:
   ```
   curl "https://api.telegram.org/bot<TOKEN>/setWebhook" \
     -d "url=https://<your-domain>/api/v1/telegram/webhook" \
     -d "secret_token=<TELEGRAM_WEBHOOK_SECRET>"
   ```
3. Onboard the dispatcher + driver: create their accounts, hand over the linking code,
   have them send `/link <code>` to the bot. See `USER_MANUALS.md`.

---

## Path to Infobip / WhatsApp

- **Customer SMS**: implement an Infobip-backed `NotificationProvider` and add its branch
  to `_build_provider()` — one place, nothing in orders/dispatch/driver changes.
- **WhatsApp**: additive; layer a template-based provider in independently.
- **Telegram for the team** stays — free, no volume ceiling, not competing with the
  customer channel.
