// GET /api/clover/connect?session_id=cs_… -> 302 to Clover's OAuth page (v2 flow, response_type=code).
// Same contract as /api/square/connect: the Stripe session must be ours and paid; the owner row is
// created here so the callback has somewhere to put the token. The merchant logs in to Clover,
// approves the three read permissions the app requests, and lands on /clover/callback.
const { CLOVER, CLOVER_REDIRECT, signState, ownerFromCheckout } = require("../_lib");

module.exports = async (req, res) => {
  try {
    const o = await ownerFromCheckout(req.query.session_id);
    if (o.err) return res.status(o.err[0]).send(o.err[1]);
    const u = new URL(CLOVER().authorize);
    u.searchParams.set("client_id", CLOVER().appId);
    u.searchParams.set("response_type", "code");
    u.searchParams.set("redirect_uri", CLOVER_REDIRECT());
    u.searchParams.set("state", signState(o.ownerId));
    res.setHeader("Cache-Control", "no-store");
    res.redirect(302, u.toString());
  } catch (e) {
    console.error("[clover/connect]", e.message);
    res.status(502).send("Could not start the Clover connection. Please try again in a minute.");
  }
};
