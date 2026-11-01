// GET /api/square/connect?session_id=cs_… -> 302 to Square's OAuth page.
// The Stripe session must be ours and paid (or a comp). The owner row is created here,
// keyed on the Stripe customer, so the callback has somewhere to put the token.
const { stripe, d1, signState, SQUARE, PRODUCT, need } = require("../_lib");

const SCOPES = ["MERCHANT_PROFILE_READ", "PAYMENTS_READ", "ORDERS_READ"];

module.exports = async (req, res) => {
  try {
    const sid = String(req.query.session_id || "");
    if (!sid.startsWith("cs_")) return res.status(400).send("Start at the checkout.");
    const s = await stripe(`checkout/sessions/${sid}`);
    const paid = s.metadata?.product === PRODUCT && (s.status === "complete") && (s.payment_status === "paid" || s.payment_status === "no_payment_required");
    if (!paid) return res.status(402).send("That checkout has not completed. Go back and finish paying, then connect Square.");
    const ownerId = String(s.customer || s.id).replace(/[^A-Za-z0-9_]/g, "");
    const email = s.customer_details?.email || "";
    await d1(
      "insert into owners (owner_id, email, stripe_session, stripe_customer, stripe_subscription, plan_status) values (?,?,?,?,?,'active') " +
      "on conflict(owner_id) do update set email=excluded.email, stripe_session=excluded.stripe_session, stripe_subscription=excluded.stripe_subscription, plan_status='active', updated_at=datetime('now')",
      [ownerId, email, s.id, s.customer || null, s.subscription || null],
    );
    const u = new URL(SQUARE().authorize);
    u.searchParams.set("client_id", need("SQUARE_APPLICATION_ID"));
    u.searchParams.set("scope", SCOPES.join(" "));
    u.searchParams.set("session", "false");
    u.searchParams.set("state", signState(ownerId));
    res.setHeader("Cache-Control", "no-store");
    res.redirect(302, u.toString());
  } catch (e) {
    console.error("[square/connect]", e.message);
    res.status(502).send("Could not start the Square connection. Please try again in a minute.");
  }
};
