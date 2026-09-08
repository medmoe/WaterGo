# User manuals — Batna water delivery platform

One section per role. Each is written to be handed to that person directly (or read aloud
to them) — plain steps, no technical jargon. Screens referenced below match the current
build; exact wording/layout may be refined before launch.

---

## For customers — ordering water

### What you need
- A phone number (any Algerian mobile number). You don't need to create an account first.

### How to place an order
1. Open the website.
2. On the map, tap the exact spot where the tanker should deliver. If your street doesn't
   have a clear address, that's fine — the pin is what matters.
3. Add a short note to help the driver find you (e.g. "next to the green gate," "3rd floor,
   blue building").
4. Enter how many liters you want.
5. Enter your phone number.
6. Check the price shown — it updates automatically based on the current rate per liter.
7. Submit the order.

### What happens after you submit
1. Someone from the company will **call you** on the number you gave, to confirm the
   quantity, location, and price before a truck is sent. Nothing is dispatched until this
   call happens.
2. Once confirmed, your order is scheduled onto a truck's route for delivery.
3. You can track the order status at any time using the tracking link you were given after
   submitting (you'll need the phone number you ordered with to view it).
4. Payment is **cash, paid to the driver when the water is delivered**. No online payment
   is needed or accepted at this time.
5. After delivery, you may receive a message asking you to rate the delivery — this is
   optional and takes a few seconds, but it helps the company improve the service.

### If something's wrong
- Wrong quantity or address after submitting, but before the confirmation call: mention it
  when the dispatcher calls to confirm.
- Need to cancel: this is only possible before a truck has been sent — contact the company
  directly.

---

## For dispatchers — managing incoming orders and routes

### What you need
- A phone number registered by the admin with the dispatcher role.
- Access to `/dispatch` on the platform.

### Logging in
1. Go to `/login`.
2. Enter your phone number, then the code sent to you by SMS.
3. You'll land on the dispatcher dashboard.

### Linking Telegram (one-time, during onboarding)
You'll get free push notifications for new orders on Telegram, on top of the dashboard.
1. Install Telegram and open the Batna Water bot (the admin gives you its link).
2. Tap **Start**.
3. Send `/link CODE`, using the 6-character code the admin gave you when they created your
   account. The bot replies "✅ Compte lié".
   - The code is valid for one hour. If it expired, ask the admin to issue a new one.
4. From then on the bot messages you whenever a new order comes in, plus alerts if the SMS
   sender goes down. If you never link, nothing breaks — you just rely on the dashboard.

### Daily workflow

**Step 1 — Confirm new orders**
- The "Pending orders" tab lists every order that hasn't been confirmed yet.
- For each one: **call the customer** on the phone number listed. Verify the quantity, the
  location (use the map pin and landmark note), and the price.
- If everything checks out, mark the order **Confirmed** in the app. This is what makes it
  eligible to go onto a route — nothing gets dispatched before this step.
- If the customer wants to cancel or something doesn't check out, mark it accordingly
  instead.

**Step 2 — Build routes**
- Switch to the map view — every confirmed order that isn't on a route yet shows as a pin.
- Group nearby orders together where it makes sense (this is currently done by eye — the
  app doesn't suggest groupings automatically yet).
- Pick the orders for a route, choose which truck and which driver will run it, set the
  date, and create the route.
- A good route keeps stops close together — this is what actually saves fuel and truck wear,
  which is the whole point of planning routes instead of sending one truck per order.

**Step 3 — Start and track routes**
- When a driver is ready to head out, mark the route **In progress**.
- You can see route status update in real time as the driver marks stops delivered.
- Mark the route **Completed** once every stop is done.

**Step 4 — Fleet**
- The "Fleet" tab lists all trucks. Add a new truck with its plate number and tank capacity
  when needed.
- Trucks show as available, on route, or in maintenance — this updates automatically when
  you start/complete a route, but you can also set a truck to maintenance manually if it's
  out of service.

### Things to keep in mind
- Never skip the confirmation call — it's the main quality check in the whole process.
- Keep an eye on tank capacity (2,000–4,000 L depending on the truck) — don't assign more
  total liters to a route than the truck can carry in one trip.

---

## For drivers — delivering and collecting payment

### What you need
- A phone number registered by the admin with the driver role.
- Access to `/driver` on the platform, from a phone or tablet in the truck.

### Logging in
1. Go to `/login`.
2. Enter your phone number, then the code sent to you by SMS.
3. You'll land on your stop list for the day.

### Linking Telegram (one-time, during onboarding)
So the dispatcher can push a new route straight to your phone.
1. Install Telegram, open the Batna Water bot (link from the admin), tap **Start**.
2. Send `/link CODE` with the 6-character code the admin gave you (valid one hour; ask for
   a fresh one if it expired). The bot replies "✅ Compte lié".
3. You'll then get a Telegram message whenever a route is assigned to you. Optional — the
   `/driver` stop list is still the source of truth.

### Running your route
1. Your stops are listed in the order the dispatcher planned them. Follow them in order
   unless told otherwise.
2. For each stop, you'll see: the customer's location on the map, their landmark note, the
   quantity to deliver, and the amount of cash to collect.
3. When you arrive and deliver the water: tap **Mark delivered**.
4. When you've collected the cash: tap **Mark cash collected**. Do this for every delivery —
   it's how the office reconciles cash at the end of the day, and it protects you if there's
   ever a question about a payment.
5. Move to the next stop.

### At the end of the day
- Once every stop is marked delivered, let the dispatcher know the route is complete.
- Hand in the cash collected — it should match the total shown for your route (the office
  can check this against the app's report).

### If something goes wrong at a stop
- Customer not available / refuses delivery / wrong amount agreed: don't mark it delivered
  — contact the dispatcher before doing anything else.

---

## For admins — managing users, pricing, and reports

### What you need
- Admin role, set up by whoever configures the platform initially (the first admin account
  is created automatically from a phone number set during setup).

### Managing people
- Go to `/admin` to see all registered users.
- To add a dispatcher or driver: create a new user with their phone number and the correct
  role. They'll then be able to log in with OTP like anyone else — no password to hand out.
- When you create a dispatcher or driver, the app shows a **6-character Telegram linking
  code**. Give it to that person (valid for one hour). They send it to the bot as
  `/link CODE` to start getting Telegram notifications. Need a fresh code? Reissue it from
  the platform (there's a "reissue link code" action per user).
- Customers don't need to be created manually — an account is created automatically the
  first time someone orders or logs in with a new phone number.

### Managing price
- The price per liter is currently 4 DZD, but can be changed at any time.
- Go to the pricing settings and enter a new rate. This only affects **new** orders placed
  after the change — orders already placed keep the price that was active when the customer
  submitted them, so no one is charged a different price after the fact.

### Reports
- Go to `/reports` to see the cash reconciliation report for any given day: how much cash
  each driver should have collected vs. what's been marked as collected in the app. Use this
  to reconcile with the physical cash handed in.

### Fleet and maintenance
- Vehicles and their maintenance history live in the Fleet section. Logging tire changes,
  oil changes, etc. against each truck's odometer reading over time is what will eventually
  show whether route planning is actually extending tire/vehicle lifespan — it's worth
  keeping this up to date even before that reporting view exists.

---

## Common questions across roles

**What if I don't get an SMS code to log in?**
The messaging provider integration is still being finalized. During this period, codes may
need to be provided to you directly by whoever is running the platform rather than arriving
automatically by text. This is temporary.

**Is there an app to download?**
No — everything runs in a web browser, on a phone or computer. No installation needed.

**What if a customer wants to pay online?**
Not available yet — cash on delivery only, for now.