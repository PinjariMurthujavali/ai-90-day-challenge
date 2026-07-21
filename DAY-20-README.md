# Day 20: Payment System & Theme Refresh

Kicks off **Week 3 (Payments & Scale)**. Adds a Plans & Pricing page and an
admin-approval flow for plan upgrades — deliberately *without* faking a real
charge, since no payment gateway is configured yet. Also gives the pricing
page (and a few shared elements) a visual refresh.

## What was added

| File | Change |
|---|---|
| `pricing.py` | **New.** Plan catalog (`PLANS`) + the upgrade-request flow: `create_upgrade_request()`, `get_pending_requests()`, `resolve_request()`, `get_user_pending_request()`. |
| `database.py` | New `upgrade_requests` table: `id, user_id, requested_plan, status, created_at, resolved_at`. |
| `chatbot.py` | New **💎 Pricing** nav item and page: 3 plan cards (Free / Pro / Enterprise), current-plan badge, pending-request notice, and a Day 20 milestone banner. Admin panel gets a **Pending Upgrade Requests** section to approve/reject. |
| `admin_service.py` | Already had `set_user_plan()` from Day 18 — reused here so approving a request and manually setting a plan share the same code path. |
| `styles.py` | Theme refresh: hover-lift + glow on bordered containers (used by the plan cards), `.plan-badge` variants per tier (free/pro/enterprise), and `.milestone-banner` styling. |

## How the flow works

1. User opens **💎 Pricing**, sees their current plan and the 3 tiers.
2. Clicking **Request {Plan}** calls `pricing.create_upgrade_request()` —
   blocked if they already have a pending request.
3. Request shows up under **Admin → Pending Upgrade Requests**.
4. Admin clicks **✅ Approve** → `admin_service.set_user_plan()` updates the
   user's plan, then `pricing.resolve_request()` marks it resolved.
   **❌ Reject** just resolves it without touching the plan.
5. User sees their new plan badge next time they load the Pricing page.

## Why no real Stripe charge yet

Faking a "payment successful" message with no Stripe keys configured would
be actively misleading. This request → admin-approve model gives the same
end-to-end UX (pick a plan, get upgraded) without pretending money moved.
When Stripe checkout is wired in on **Day 21**, only the *caller* of
`create_upgrade_request()` changes — a checkout-success webhook instead of a
button click — the request/approve data model underneath stays the same.

## Known limitations (honest list)

- No real payment processing — this is a manual-approval queue, not billing.
- No downgrade confirmation / proration logic — an admin just sets whatever
  plan they choose.
- One pending request per user at a time, by design (prevents queue spam).
- Plan badges are cosmetic — enforcement of plan-gated features (e.g. file
  size limits, priority response speed) still needs to check `users.plan`
  wherever those limits apply.

## Coming next (Day 21)

Real Stripe integration: Checkout Sessions, webhook-driven plan upgrades,
and retiring the manual-approval queue in favor of actual payments.
