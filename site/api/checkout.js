// POST /api/checkout -> { clientSecret } for Stripe embedded Checkout, mode=subscription, $29/month.
// One price, no trial, no tiers (feedback_no_pricing_gimmicks). After paying, Stripe returns the
// buyer to /connect/?session_id=…, where they connect their Square account.
const { SITE, PRODUCT, PRICE_USD, stripe } = require("./_lib");

module.exports = async (req, res) => {
  if (req.method !== "POST") return res.status(405).json({ error: "POST only" });
  try {
    const s = await stripe("checkout/sessions", {
      method: "POST",
      form: {
        ui_mode: "embedded_page",
        mode: "subscription",
        "line_items[0][quantity]": "1",
        "line_items[0][price_data][currency]": "usd",
        "line_items[0][price_data][unit_amount]": String(PRICE_USD * 100),
        "line_items[0][price_data][recurring][interval]": "month",
        "line_items[0][price_data][product_data][name]": "Block Brief",
        "line_items[0][price_data][product_data][description]": "One Monday briefing a week: your Square numbers next to what the city filed around your door. Minneapolis.",
        "payment_method_types[0]": "card",
        "payment_method_types[1]": "link",
        "metadata[product]": PRODUCT,
        "subscription_data[metadata][product]": PRODUCT,
        "subscription_data[description]": "Block Brief, weekly",
        return_url: `${SITE}/connect/?session_id={CHECKOUT_SESSION_ID}`,
      },
    });
    res.status(200).json({ clientSecret: s.client_secret });
  } catch (e) {
    console.error("[checkout]", e.message);
    res.status(502).json({ error: "Checkout could not start. Please try again in a minute." });
  }
};
