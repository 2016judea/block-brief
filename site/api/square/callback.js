// GET /api/square/callback?code=…&state=… (Square's redirect URL for this app).
// Exchanges the code (ObtainToken), reads the merchant's main location for the shop's
// name and address, geocodes it, seals the tokens into the owner row, and lands on
// /connected/. The token is AES-GCM sealed; the key is an env var, never in source.
const { square, SQUARE, d1, sealToken, checkState, SITE } = require("../_lib");

async function geocode(addr) {
  // Census geocoder: free, no key. Returns null when the address does not match.
  const u = `https://geocoding.geo.census.gov/geocoder/locations/onelineaddress?benchmark=Public_AR_Current&format=json&address=${encodeURIComponent(addr)}`;
  const j = await (await fetch(u)).json();
  const m = j.result?.addressMatches?.[0];
  return m ? { lat: m.coordinates.y, lon: m.coordinates.x, matched: m.matchedAddress } : null;
}

async function pinFor(lat, lon, houseNo) {
  // Hennepin's live parcel layer. A geocoded point sits on the street centreline, inside no
  // parcel, so buffer 80 ft and prefer the parcel whose house number matches. Minneapolis only in v1.
  const q = new URLSearchParams({ geometry: `${lon},${lat}`, geometryType: "esriGeometryPoint", inSR: "4326", distance: "250", units: "esriSRUnit_Foot", spatialRel: "esriSpatialRelIntersects", outFields: "PID,HOUSE_NO,STREET_NM,MUNIC_NM,LAT,LON", returnGeometry: "false", f: "json" });
  const j = await (await fetch(`https://gis.hennepin.us/arcgis/rest/services/HennepinData/LAND_PROPERTY/MapServer/1/query?${q}`)).json();
  const fs = (j.features || []).map((f) => f.attributes);
  fs.sort((a, b) => Math.abs(a.HOUSE_NO - houseNo) - Math.abs(b.HOUSE_NO - houseNo));
  return fs.find((f) => f.HOUSE_NO === houseNo) || fs[0] || null;
}

module.exports = async (req, res) => {
  try {
    const ownerId = checkState(req.query.state);
    if (!ownerId) return res.status(400).send("This connection link has expired. Open your checkout email and try again.");
    if (req.query.error) return res.redirect(302, `${SITE}/connect/?denied=1`);
    const code = String(req.query.code || "");
    if (!code) return res.status(400).send("Square sent no code.");
    const tok = await (await fetch(`${SQUARE().connect}/oauth2/token`, {
      method: "POST",
      headers: { "content-type": "application/json", "Square-Version": "2026-09-16" },
      body: JSON.stringify({ client_id: SQUARE().appId, client_secret: SQUARE().secret, code, grant_type: "authorization_code" }),
    })).json();
    if (!tok.access_token) throw new Error(`obtain token: ${JSON.stringify(tok).slice(0, 300)}`);

    const locs = await square("/v2/locations", tok.access_token);
    const loc = (locs.locations || []).find((l) => l.status === "ACTIVE" && l.type !== "MOBILE") || locs.locations?.[0];
    const a = loc?.address || {};
    const addr = [a.address_line_1, a.locality, a.administrative_district_level_1, a.postal_code].filter(Boolean).join(", ");
    const geo = addr ? await geocode(addr) : null;
    const parcel = geo ? await pinFor(geo.lat, geo.lon, Number((geo.matched.match(/^\d+/) || [])[0])) : null;

    await d1(
      "update owners set merchant_id=?, location_id=?, shop_name=?, address=?, lat=?, lon=?, parcel_pin=?, token_blob=?, token_expires_at=?, updated_at=datetime('now') where owner_id=?",
      [tok.merchant_id, loc?.id || null, loc?.name || loc?.business_name || null, addr || null, geo?.lat ?? null, geo?.lon ?? null,
        parcel?.PID || null, sealToken({ access_token: tok.access_token, refresh_token: tok.refresh_token, merchant_id: tok.merchant_id }), tok.expires_at || null, ownerId],
    );
    const flags = [];
    if (!geo) flags.push("noaddr");
    else if (!parcel) flags.push("nohennepin");
    else if ((parcel.MUNIC_NM || "").trim().toUpperCase() !== "MINNEAPOLIS") flags.push("notmpls");
    res.setHeader("Cache-Control", "no-store");
    res.redirect(302, `${SITE}/connected/?shop=${encodeURIComponent(loc?.name || "")}${flags.length ? "&flag=" + flags.join(",") : ""}`);
  } catch (e) {
    console.error("[square/callback]", e.message);
    res.status(502).send("Square connected but we could not save it. Reply to your receipt email and we will fix it by hand.");
  }
};
