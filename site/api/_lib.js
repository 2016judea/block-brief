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

module.exports = { SITE, PRODUCT, PRICE_USD, need, stripe, d1, sealToken, signState, checkState, SQUARE, square };
