// GET /clover?merchant_id=…&employee_id=…  (the app's registered Site URL / Alternate Launch Path).
// Where a merchant lands when they install Block Brief from the Clover App Market or open it from
// their Merchant Dashboard. Clover bills them for the subscription, so there is no Stripe step: the
// owner row is keyed on the Clover merchant id and marked plan_status='clover'. From here the app
// must start the v2 OAuth flow itself; the merchant is already signed in, so Clover returns a code
// straight to /clover/callback.
const { CLOVER, CLOVER_REDIRECT, signState } = require("../_lib");

module.exports = async (req, res) => {
  try {
    const mid = String(req.query.merchant_id || "").replace(/[^A-Za-z0-9]/g, "");
    if (!mid) return res.redirect(302, "/");
    const u = new URL(CLOVER().authorize);
    u.searchParams.set("client_id", CLOVER().appId);
    u.searchParams.set("response_type", "code");
    u.searchParams.set("redirect_uri", CLOVER_REDIRECT());
    u.searchParams.set("state", signState(`cl_${mid}`));
    res.setHeader("Cache-Control", "no-store");
    res.redirect(302, u.toString());
  } catch (e) {
    console.error("[clover/launch]", e.message);
    res.status(502).send("Could not start Block Brief from Clover. Please try again in a minute.");
  }
};
