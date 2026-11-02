// GET /clover/callback?code=…&merchant_id=…&state=…  (redirect_uri under the registered Site URL).
// Exchanges the code at /oauth/v2/token for an expiring access/refresh pair, reads the merchant's
// name, address and owner email, geocodes it, finds the Hennepin parcel, seals the pair into the
// owner row, lands on /connected/. Refresh tokens are single-use: pipeline/brief.py rotates them
// and writes the new pair back before every Monday read.
const { clover, CLOVER, d1, sealToken, checkState, placeShop, SITE } = require("../_lib");

module.exports = async (req, res) => {
  try {
    const stateId = checkState(req.query.state);
    if (!stateId) return res.status(400).send("This connection link has expired. Open your checkout email and try again, or open Block Brief from your Clover dashboard.");
    if (req.query.error) return res.redirect(302, `${SITE}/connect/?denied=1&pos=clover`);
    const code = String(req.query.code || "");
    if (!code) return res.status(400).send("Clover sent no code.");
    const tok = await (await fetch(`${CLOVER().api}/oauth/v2/token`, {
      method: "POST",
      headers: { "content-type": "application/json", accept: "application/json" },
      body: JSON.stringify({ client_id: CLOVER().appId, client_secret: CLOVER().secret, code }),
    })).json();
    if (!tok.access_token) throw new Error(`token: ${JSON.stringify(tok).slice(0, 300)}`);
    const mid = String(req.query.merchant_id || "").replace(/[^A-Za-z0-9]/g, "");
    if (!mid) throw new Error("no merchant_id on the callback");

    const m = await clover(`/v3/merchants/${mid}?expand=address,owner`, tok.access_token);
    const a = m.address || {};
    const addr = [a.address1, a.city, a.state, a.zip].filter(Boolean).join(", ");
    const { geo, parcel, flags } = await placeShop(addr);

    // Two ways in: a paid Stripe owner (state = their owner id) or a Clover App Market install (state = cl_<mid>).
    const fromMarket = stateId === `cl_${mid}`;
    const ownerId = fromMarket ? `cl_${mid}` : stateId;
    const email = m.owner?.email || m.email || "";
    if (fromMarket) {
      await d1("insert into owners (owner_id, email, plan_status, pos_provider) values (?,?,'clover','clover') on conflict(owner_id) do update set email=case when excluded.email<>'' then excluded.email else owners.email end, plan_status='clover', updated_at=datetime('now')", [ownerId, email]);
    }
    const expiresAt = tok.access_token_expiration ? new Date(tok.access_token_expiration * 1000).toISOString() : null;
    await d1(
      "update owners set pos_provider='clover', merchant_id=?, location_id=?, shop_name=?, address=?, lat=?, lon=?, parcel_pin=?, token_blob=?, token_expires_at=?, updated_at=datetime('now') where owner_id=?",
      [mid, mid, m.name || null, addr || null, geo?.lat ?? null, geo?.lon ?? null, parcel?.PID || null,
        sealToken({ access_token: tok.access_token, refresh_token: tok.refresh_token, merchant_id: mid,
          access_token_expiration: tok.access_token_expiration, refresh_token_expiration: tok.refresh_token_expiration }),
        expiresAt, ownerId],
    );
    if (fromMarket && !email) flags.push("noemail");
    res.setHeader("Cache-Control", "no-store");
    res.redirect(302, `${SITE}/connected/?pos=clover&shop=${encodeURIComponent(m.name || "")}${flags.length ? "&flag=" + flags.join(",") : ""}`);
  } catch (e) {
    console.error("[clover/callback]", e.message);
    res.status(502).send("Clover connected but we could not save it. Reply to your receipt email and we will fix it by hand.");
  }
};
