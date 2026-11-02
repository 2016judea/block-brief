// Shared by the functions. Files starting with "_" are not routes on Vercel.
// Pattern: ~/Desktop/msp-house-index/site/api/_lib.js (Stripe over fetch, no SDK).
const crypto = require("crypto");

const SITE = process.env.SITE_URL || "https://block-brief.vercel.app";
const PRODUCT = "block-brief";
const PRICE_USD = 29;
const CF_ACCT = "6e9ce2a0c1d0c9b570955eaaae7db72d";
const D1 = "41c7b8b6-c367-4cc2-b963-063beb1edcbd";

function need(k) {
  const v = process.env[k];
  if (!v) throw new Error(`${k} is not set`);
  return v;
}

async function stripe(path, { method = "GET", form } = {}) {
  const r = await fetch(`https://api.stripe.com/v1/${path}`, {
    method,
    headers: { Authorization: `Bearer ${need("STRIPE_SECRET_KEY")}`, ...(form ? { "Content-Type": "application/x-www-form-urlencoded" } : {}) },
    body: form ? new URLSearchParams(form).toString() : undefined,
  });
  const j = await r.json();
  if (!r.ok) throw new Error(`stripe ${path}: ${j.error?.message || r.status}`);
  return j;
}

// Cloudflare D1: one HTTP call per statement. Rows come back as objects.
async function d1(sql, params = []) {
  const r = await fetch(`https://api.cloudflare.com/client/v4/accounts/${CF_ACCT}/d1/database/${D1}/query`, {
    method: "POST",
    headers: { Authorization: `Bearer ${need("CLOUDFLARE_API_TOKEN")}`, "content-type": "application/json" },
    body: JSON.stringify({ sql, params }),
  });
  const j = await r.json();
  if (!j.success) throw new Error(`d1: ${JSON.stringify(j.errors).slice(0, 300)}`);
  return j.result[0].results;
}

// Square access tokens are stored AES-256-GCM under sha256(ACCESS_SECRET): base64(iv|tag|ct).
// pipeline/brief.py open_token() is the other half. The secret is never in source control.
function sealToken(obj) {
  const key = crypto.createHash("sha256").update(need("ACCESS_SECRET")).digest();
  const iv = crypto.randomBytes(12);
  const c = crypto.createCipheriv("aes-256-gcm", key, iv);
  const ct = Buffer.concat([c.update(JSON.stringify(obj), "utf8"), c.final()]);
  return Buffer.concat([iv, c.getAuthTag(), ct]).toString("base64");
}

// A signed, time-limited state for the OAuth round trip: ownerId.exp.hmac
function signState(ownerId) {
  const exp = Math.floor(Date.now() / 1000) + 1800;
  const mac = crypto.createHmac("sha256", need("ACCESS_SECRET")).update(`${ownerId}.${exp}`).digest("hex").slice(0, 24);
  return `${ownerId}.${exp}.${mac}`;
}
function checkState(state) {
  const [ownerId, exp, mac] = String(state || "").split(".");
  if (!ownerId || !exp || !mac || Number(exp) < Date.now() / 1000) return null;
  const want = crypto.createHmac("sha256", need("ACCESS_SECRET")).update(`${ownerId}.${exp}`).digest("hex").slice(0, 24);
  return mac.length === want.length && crypto.timingSafeEqual(Buffer.from(mac), Buffer.from(want)) ? ownerId : null;
}

// SQUARE_ENV picks the host AND the credential pair: sandbox-sq0idb-… only works against the
// sandbox host, sq0idp-… only against production. Flipping one without the other 401s.
const PROD = () => process.env.SQUARE_ENV === "production";
const SQUARE = () => (PROD()
  ? { connect: "https://connect.squareup.com", authorize: "https://connect.squareup.com/oauth2/authorize",
      appId: need("SQUARE_PROD_APPLICATION_ID"), secret: need("SQUARE_PROD_APPLICATION_SECRET") }
  : { connect: "https://connect.squareupsandbox.com", authorize: "https://connect.squareupsandbox.com/oauth2/authorize",
      appId: need("SQUARE_APPLICATION_ID"), secret: need("SQUARE_APPLICATION_SECRET") });

async function square(path, token, { method = "GET", body } = {}) {
  const r = await fetch(`${SQUARE().connect}${path}`, {
    method,
    headers: { Authorization: `Bearer ${token}`, "Square-Version": "2026-09-16", "content-type": "application/json" },
    body: body ? JSON.stringify(body) : undefined,
  });
  const j = await r.json();
  if (!r.ok) throw new Error(`square ${path}: ${JSON.stringify(j.errors || j).slice(0, 300)}`);
  return j;
}

// Clover (Fiserv): CLOVER_ENV picks host and credential pair the same way. Sandbox app ids only
// work against sandbox.dev.clover.com / apisandbox.dev.clover.com; production against www./api.clover.com.
// ~/.claude/skills/clover-api/SKILL.md has the flow. redirect_uri must sit under the registered Site URL
// (https://block-brief.vercel.app/clover), so vercel.json rewrites /clover/callback -> /api/clover/callback.
const CLOVER_PROD = () => process.env.CLOVER_ENV === "production";
const CLOVER = () => (CLOVER_PROD()
  ? { api: "https://api.clover.com", authorize: "https://www.clover.com/oauth/v2/authorize",
      appId: need("CLOVER_PROD_APP_ID"), secret: need("CLOVER_PROD_APP_SECRET") }
  : { api: "https://apisandbox.dev.clover.com", authorize: "https://sandbox.dev.clover.com/oauth/v2/authorize",
      appId: need("CLOVER_APP_ID"), secret: need("CLOVER_APP_SECRET") });
const CLOVER_REDIRECT = () => `${SITE}/clover/callback`;

async function clover(path, token, { method = "GET", body } = {}) {
  const r = await fetch(`${CLOVER().api}${path}`, {
    method,
    headers: { Authorization: `Bearer ${token}`, accept: "application/json", "content-type": "application/json" },
    body: body ? JSON.stringify(body) : undefined,
  });
  const j = await r.json().catch(() => ({}));
  if (!r.ok) throw new Error(`clover ${path}: ${r.status} ${JSON.stringify(j).slice(0, 300)}`);
  return j;
}

// Shared by both callbacks: a street address -> lat/lon (Census, free) -> the Hennepin parcel under the door.
async function geocode(addr) {
  const u = `https://geocoding.geo.census.gov/geocoder/locations/onelineaddress?benchmark=Public_AR_Current&format=json&address=${encodeURIComponent(addr)}`;
  const j = await (await fetch(u)).json();
  const m = j.result?.addressMatches?.[0];
  return m ? { lat: m.coordinates.y, lon: m.coordinates.x, matched: m.matchedAddress } : null;
}
async function pinFor(lat, lon, houseNo) {
  // A geocoded point sits on the street centreline, inside no parcel: buffer 250 ft, prefer the matching house number.
  const q = new URLSearchParams({ geometry: `${lon},${lat}`, geometryType: "esriGeometryPoint", inSR: "4326", distance: "250", units: "esriSRUnit_Foot", spatialRel: "esriSpatialRelIntersects", outFields: "PID,HOUSE_NO,STREET_NM,MUNIC_NM,LAT,LON", returnGeometry: "false", f: "json" });
  const j = await (await fetch(`https://gis.hennepin.us/arcgis/rest/services/HennepinData/LAND_PROPERTY/MapServer/1/query?${q}`)).json();
  const fs = (j.features || []).map((f) => f.attributes);
  fs.sort((a, b) => Math.abs(a.HOUSE_NO - houseNo) - Math.abs(b.HOUSE_NO - houseNo));
  return fs.find((f) => f.HOUSE_NO === houseNo) || fs[0] || null;
}
async function placeShop(addr) {
  const geo = addr ? await geocode(addr) : null;
  const parcel = geo ? await pinFor(geo.lat, geo.lon, Number((geo.matched.match(/^\d+/) || [])[0])) : null;
  const flags = [];
  if (!geo) flags.push("noaddr");
  else if (!parcel) flags.push("nohennepin");
  else if ((parcel.MUNIC_NM || "").trim().toUpperCase() !== "MINNEAPOLIS") flags.push("notmpls");
  return { geo, parcel, flags };
}

// The paid path: a finished Stripe checkout session -> an owners row keyed on the Stripe customer.
async function ownerFromCheckout(sid) {
  if (!String(sid || "").startsWith("cs_")) return { err: [400, "Start at the checkout."] };
  const s = await stripe(`checkout/sessions/${sid}`);
  const paid = s.metadata?.product === PRODUCT && (s.status === "complete") && (s.payment_status === "paid" || s.payment_status === "no_payment_required");
  if (!paid) return { err: [402, "That checkout has not completed. Go back and finish paying, then connect your register."] };
  const ownerId = String(s.customer || s.id).replace(/[^A-Za-z0-9_]/g, "");
  const email = s.customer_details?.email || "";
  await d1(
    "insert into owners (owner_id, email, stripe_session, stripe_customer, stripe_subscription, plan_status) values (?,?,?,?,?,'active') " +
    "on conflict(owner_id) do update set email=excluded.email, stripe_session=excluded.stripe_session, stripe_subscription=excluded.stripe_subscription, plan_status='active', updated_at=datetime('now')",
    [ownerId, email, s.id, s.customer || null, s.subscription || null],
  );
  return { ownerId, email };
}

module.exports = { SITE, PRODUCT, PRICE_USD, need, stripe, d1, sealToken, signState, checkState, SQUARE, square,
  CLOVER, CLOVER_REDIRECT, clover, geocode, pinFor, placeShop, ownerFromCheckout };
