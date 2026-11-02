#!/usr/bin/env python3
"""Write one Monday briefing for one shop: the register's week next to the city's records.

    python3 pipeline/brief.py --example            # the landing page's example (sample register, real records)
    python3 pipeline/brief.py --owner <owner_id>   # a real subscriber: Square or Clover payments + records, emailed
    python3 pipeline/brief.py --all                # every active owner (the Monday job)

The model (claude-sonnet-5-5) writes prose from a JSON of numbers it did not
produce. It is told every figure must come from that JSON, and the output is
checked: every dollar amount and percentage in the prose must appear in the
input, or the briefing is not sent.

Needs: ANTHROPIC_API_KEY, MAILGUN_API_KEY, MAILGUN_DOMAIN, CLOUDFLARE_API_TOKEN,
ACCESS_SECRET (token blobs), SQUARE_ENV and CLOVER_ENV (sandbox|production),
CLOVER_APP_ID / CLOVER_PROD_APP_ID (token refresh). The first three live in
~/Desktop/bricks/.env; the repo's .env adds the Square and Clover ones.
"""
import argparse
import base64
import datetime as dt
import hashlib
import json
import os
import random
import re
import statistics
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "pipeline"))
import signals as S  # noqa: E402

MODEL = "claude-sonnet-5-5"
SITE = os.environ.get("SITE_URL", "https://block-brief.vercel.app")
CF_ACCT = "6e9ce2a0c1d0c9b570955eaaae7db72d"
D1 = "41c7b8b6-c367-4cc2-b963-063beb1edcbd"


def load_env():
    for p in (Path.home() / "Desktop" / "bricks" / ".env", ROOT / ".env"):
        if p.exists():
            for line in p.read_text().splitlines():
                if "=" in line and not line.startswith("#"):
                    k, v = line.split("=", 1)
                    os.environ.setdefault(k.strip(), v.strip().strip('"'))


# ---- the register -----------------------------------------------------------

def week_bounds(today=None):
    today = today or dt.date.today()
    monday = today - dt.timedelta(days=today.weekday())
    return monday - dt.timedelta(days=7), monday  # [last Monday, this Monday)


def summarise(days, week_start, week_end):
    """days: {date: {gross_cents, n_payments, hours[24]}} covering >= 9 weeks. Pure arithmetic."""
    def wk(start):
        return [days.get((start + dt.timedelta(d)).isoformat()) for d in range(7)]
    this = wk(week_start)
    prior = wk(week_start - dt.timedelta(days=7))
    ly = wk(week_start - dt.timedelta(days=364))
    gross = lambda w: sum((d or {}).get("gross_cents", 0) for d in w)
    cnt = lambda w: sum((d or {}).get("n_payments", 0) for d in w)
    g, pg, lg = gross(this), gross(prior), gross(ly)
    out = dict(week_start=week_start.isoformat(), week_end=(week_end - dt.timedelta(days=1)).isoformat(),
               week_gross_usd=round(g / 100), week_payments=cnt(this),
               avg_ticket_usd=round(g / cnt(this) / 100, 2) if cnt(this) else None,
               prior_week_gross_usd=round(pg / 100), week_vs_prior_pct=round((g - pg) / pg * 100, 1) if pg else None,
               same_week_last_year_gross_usd=round(lg / 100) if lg else None,
               week_vs_last_year_pct=round((g - lg) / lg * 100, 1) if lg else None, days=[])
    # typical = median of the same weekday over the trailing 8 weeks
    worst = None
    for i, d in enumerate(this):
        date = week_start + dt.timedelta(i)
        hist = [days[(date - dt.timedelta(weeks=w)).isoformat()]["gross_cents"] for w in range(1, 9) if (date - dt.timedelta(weeks=w)).isoformat() in days]
        typical = statistics.median(hist) if hist else None
        gc = (d or {}).get("gross_cents", 0)
        vs = round((gc - typical) / typical * 100, 1) if typical else None
        row = dict(date=date.isoformat(), weekday=date.strftime("%A"), gross_usd=round(gc / 100), payments=(d or {}).get("n_payments", 0),
                   typical_usd=round(typical / 100) if typical else None, vs_typical_pct=vs)
        if d and d.get("hours"):
            h = d["hours"]
            peak = max(range(24), key=lambda x: h[x])
            row["peak_hour"] = f"{peak:02d}:00"
        out["days"].append(row)
        if vs is not None and typical and gc > 0 and (worst is None or vs < worst["vs_typical_pct"]):
            worst = row
    out["worst_day"] = worst
    return out


def square_days(token, location_id, start, end, env="production"):
    """GET /v2/payments, COMPLETED only, bucketed by local day. amount_money.amount is cents."""
    host = "https://connect.squareupsandbox.com" if env == "sandbox" else "https://connect.squareup.com"
    days, cursor = {}, None
    while True:
        q = dict(location_id=location_id, begin_time=start.isoformat() + "T00:00:00Z", end_time=end.isoformat() + "T00:00:00Z", limit=100, sort_order="ASC")
        if cursor:
            q["cursor"] = cursor
        req = urllib.request.Request(f"{host}/v2/payments?" + urllib.parse.urlencode(q),
                                     headers={"Authorization": f"Bearer {token}", "Square-Version": "2026-09-16"})
        with urllib.request.urlopen(req, timeout=60) as r:
            j = json.load(r)
        for p in j.get("payments", []):
            if p.get("status") != "COMPLETED":
                continue
            d = p["created_at"][:10]
            row = days.setdefault(d, dict(gross_cents=0, n_payments=0, hours=[0] * 24))
            row["gross_cents"] += p["amount_money"]["amount"]
            row["n_payments"] += 1
            row["hours"][int(p["created_at"][11:13])] += p["amount_money"]["amount"]
        cursor = j.get("cursor")
        if not cursor:
            return days


# ---- Clover (Fiserv) ------------------------------------------------------------
# ~/.claude/skills/clover-api/SKILL.md. Payments carry amount (cents), result (SUCCESS), createdTime
# (ms). Time filters are capped at 90 days per call (our window is 63), pages are limit/offset, max 1000.
SHOP_TZ = ZoneInfo("America/Chicago")  # Minneapolis only in v1; Clover keeps the timezone in merchant properties


def clover_host(env):
    return "https://apisandbox.dev.clover.com" if env == "sandbox" else "https://api.clover.com"


def clover_app_id(env):
    return os.environ["CLOVER_APP_ID" if env == "sandbox" else "CLOVER_PROD_APP_ID"]


def clover_refresh(tok, env):
    """Rotate the expiring pair when the access token has under a day left. Refresh tokens are single-use,
    so the caller must persist what comes back before anything else runs. Returns (tok, rotated)."""
    if tok.get("access_token_expiration", 0) - time.time() > 24 * 3600:
        return tok, False
    req = urllib.request.Request(f"{clover_host(env)}/oauth/v2/refresh",
                                 data=json.dumps({"client_id": clover_app_id(env), "refresh_token": tok["refresh_token"]}).encode(),
                                 headers={"content-type": "application/json", "accept": "application/json"})
    with urllib.request.urlopen(req, timeout=60) as r:
        j = json.load(r)
    new = dict(tok, access_token=j["access_token"], refresh_token=j["refresh_token"],
               access_token_expiration=j["access_token_expiration"], refresh_token_expiration=j["refresh_token_expiration"],
               previous_refresh_token=tok["refresh_token"])  # the recovery token, if the new pair is ever lost
    return new, True


def clover_days(token, merchant_id, start, end, env="production"):
    """GET /v3/merchants/{mId}/payments, result SUCCESS only, bucketed by local (Central) day."""
    t0 = int(dt.datetime.combine(start, dt.time(), SHOP_TZ).timestamp() * 1000)
    t1 = int(dt.datetime.combine(end, dt.time(), SHOP_TZ).timestamp() * 1000)
    days, offset = {}, 0
    while True:
        q = f"filter=createdTime>={t0}&filter=createdTime<{t1}&limit=1000&offset={offset}"
        req = urllib.request.Request(f"{clover_host(env)}/v3/merchants/{merchant_id}/payments?{q}",
                                     headers={"Authorization": f"Bearer {token}", "accept": "application/json"})
        with urllib.request.urlopen(req, timeout=60) as r:
            j = json.load(r)
        els = j.get("elements", [])
        for p in els:
            if p.get("result") != "SUCCESS":
                continue
            when = dt.datetime.fromtimestamp(p["createdTime"] / 1000, SHOP_TZ)
            row = days.setdefault(when.date().isoformat(), dict(gross_cents=0, n_payments=0, hours=[0] * 24))
            row["gross_cents"] += p.get("amount", 0)
            row["n_payments"] += 1
            row["hours"][when.hour] += p.get("amount", 0)
        if len(els) < 1000:
            return days
        offset += 1000


def sample_days(seed, start, end):
    """A sample register for the landing page: a café's shape, labelled as a sample on the page.
    Deterministic from the seed so the example does not change between builds."""
    rng = random.Random(seed)
    days = {}
    d = start
    while d < end:
        wd = d.weekday()
        base = [1180, 1120, 1150, 1210, 1390, 1710, 1480][wd]  # Mon..Sun, dollars
        g = base * rng.uniform(0.9, 1.1)
        if d == end - dt.timedelta(days=6):   # last Monday: the dip the records can explain
            g *= 0.68
        n = max(1, int(g / rng.uniform(7.5, 9.5)))
        hours = [0] * 24
        for _ in range(n):
            hours[int(rng.triangular(6, 18, 9))] += int(g * 100 / n)
        days[d.isoformat()] = dict(gross_cents=int(g * 100), n_payments=n, hours=hours)
        d += dt.timedelta(days=1)
    return days


# ---- the prose ----------------------------------------------------------------

SYSTEM = """You write a Monday briefing for the owner of one small shop. You are given two things as JSON: what their register did last week, and what the city filed within 500 feet of their door. Your job is to put the two side by side in plain words.

Rules, each one matters:
- Every number you write (a dollar amount, a percentage, a unit count, a distance, a date, a price) must appear in the JSON. Never compute a new one, never round differently, never estimate. If a number is not there, do not write it.
- Plain language a fifth-grader reads without stopping. Short sentences. No jargon: say "the county's value for your building", not "assessed value"; "dug up the street", not "right-of-way excavation".
- Lead with the one thing that matters most this week. If a day was well below typical and a street or sidewalk permit on the block overlaps it, say the permit may explain it. Say "may": a permit date is when the city wrote it down, not the day the street was closed.
- One short paragraph per signal that matters, nearest first. Skip signals that do not change anything for this shop this week. Say what it means for them in one clause ("more people walking past from next year", "a bar two doors down now sells wine too", "your landlord's tax bill went up, and a triple-net lease passes that on").
- The county's value: give the number, the change, the tax bill, and the rule: notices come in March, and a Tax Court petition has to be filed by April 30 of the year the tax is paid.
- Comparable sales: give address, price, month, nearest first. Note when a deed is not a plain warranty deed or covers more than one parcel, in plain words.
- No greeting, no sign-off, no headings, no bullet points, no bold. 180 to 320 words. Address the owner as "you". Name the shop once.
- Do not praise, do not sell, do not add a disclaimer."""


def claude_prose(payload):
    import anthropic
    client = anthropic.Anthropic()
    msg = client.messages.create(
        model=MODEL, max_tokens=4000,
        output_config={"effort": "medium"},
        system=SYSTEM,
        messages=[{"role": "user", "content": "Write this Monday's briefing from this JSON only.\n\n" + json.dumps(payload, default=str)}],
    )
    if msg.stop_reason == "refusal":
        raise RuntimeError(f"model refused: {msg.stop_details}")
    return "".join(b.text for b in msg.content if b.type == "text").strip()


def numbers_in(text):
    return set(re.findall(r"\$?\d[\d,]*(?:\.\d+)?%?", text))


def check_prose(prose, payload):
    """Every figure in the prose must be a figure in the payload (as written, or as a plain integer)."""
    blob = json.dumps(payload, default=str)
    # JSON numbers carry no commas; a greedy [\d,]* would swallow the separator after a value ("743,").
    norm = lambda s: (s[:-2] if s.endswith(".0") else s)
    allowed = {norm(a) for a in re.findall(r"\d+(?:\.\d+)?", blob)}
    # the JSON carries 3200000; the prose may write $3,200,000. "3.2 million" is NOT allowed (rule: no re-rounding)
    bad = []
    for tok in re.findall(r"\$?\d[\d,]*\d(?:\.\d+)?%?|\$?\d%?", prose):
        plain = norm(tok.strip("$%").replace(",", ""))
        if plain in allowed:
            continue
        # dates written as "October 14" carry a bare day number; allow 1-31 and years
        if plain.isdigit() and (1 <= int(plain) <= 31 or 2018 <= int(plain) <= 2030):
            continue
        bad.append(tok)
    return bad


# ---- assembly -------------------------------------------------------------------

def build(shop, days, sig, label_sample=False):
    ws, we = week_bounds()
    summary = summarise(days, ws, we)
    # keep the prose honest about which street-work rows overlap the worst day
    worst = summary.get("worst_day")
    for s in sig["signals"]:
        if s["kind"] == "street_work" and worst and s.get("filed_date") and s.get("end_date"):
            s["overlaps_worst_day"] = s["filed_date"] <= worst["date"] <= s["end_date"]
    payload = dict(shop=dict(name=shop["name"], address=shop["address"], pos=shop.get("pos", "Square")), register=summary,
                   records=dict(radius_ft=sig["radius_ft"], since=sig["since"], signals=sig["signals"], value_history=sig["value_history"]))
    prose = claude_prose(payload)
    bad = check_prose(prose, payload)
    return dict(week_start=ws.isoformat(), shop=payload["shop"], register=summary, records=payload["records"], prose=prose,
                prose_check=dict(ok=not bad, unsourced=bad), sample_register=label_sample, generated_at=dt.datetime.now().isoformat(timespec="seconds"))


def html_email(b):
    paras = "".join(f"<p style='margin:0 0 14px'>{p}</p>" for p in b["prose"].split("\n") if p.strip())
    rows = ""
    for d in b["register"]["days"]:
        vs = d["vs_typical_pct"]
        colour = "#b42318" if (vs or 0) < -15 else "#555"
        note = "" if vs is None else f"{vs:+.0f}% vs usual"
        rows += (f"<tr><td style='padding:4px 10px 4px 0;color:#555'>{d['weekday'][:3]} {d['date'][5:]}</td>"
                 f"<td style='padding:4px 10px;text-align:right'>${d['gross_usd']:,}</td>"
                 f"<td style='padding:4px 0 4px 10px;text-align:right;color:{colour}'>{note}</td></tr>")
    recs = "".join(f"<li style='margin:0 0 8px'><span style='color:#555'>{s['distance_ft']} ft</span> · {s['what']}" + (f" <span style='color:#777'>({s['filed_date']})</span>" if s.get('filed_date') else "") + "</li>" for s in b["records"]["signals"])
    return f"""<div style="font:16px/1.5 -apple-system,Segoe UI,Helvetica,Arial,sans-serif;color:#1a1a1a;max-width:560px">
<p style="margin:0 0 4px;color:#555;font-size:13px">Block Brief · week of {b['week_start']} · {b['shop']['name']}, {b['shop']['address']}</p>
{paras}
<p style="margin:18px 0 6px;font-weight:600">Your register, day by day</p>
<table style="border-collapse:collapse;font-size:14px">{rows}</table>
<p style="margin:18px 0 6px;font-weight:600">What the city filed within {b['records']['radius_ft']} ft</p>
<ul style="padding-left:18px;font-size:14px;margin:0">{recs}</ul>
<p style="margin:22px 0 0;color:#777;font-size:12px">Every number above is read off your {b['shop'].get('pos', 'Square')} account or a public record. <a href="{SITE}" style="color:#777">Block Brief</a> · reply to this email with any question.</p>
</div>"""


def mailgun(to, subject, html, text):
    key, dom = os.environ["MAILGUN_API_KEY"], os.environ["MAILGUN_DOMAIN"]
    frm = os.environ.get("MAILGUN_FROM", "aidan@brickandmortar.dev")
    data = urllib.parse.urlencode(dict(**{"from": f"Block Brief <{frm}>", "to": to, "subject": subject, "text": text, "html": html, "h:Reply-To": frm})).encode()
    req = urllib.request.Request(f"https://api.mailgun.net/v3/{dom}/messages", data=data,
                                 headers={"Authorization": "Basic " + base64.b64encode(f"api:{key}".encode()).decode()})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.load(r).get("id")


def d1(sql, params=()):
    req = urllib.request.Request(f"https://api.cloudflare.com/client/v4/accounts/{CF_ACCT}/d1/database/{D1}/query",
                                 data=json.dumps({"sql": sql, "params": list(params)}).encode(),
                                 headers={"Authorization": f"Bearer {os.environ['CLOUDFLARE_API_TOKEN']}", "content-type": "application/json"})
    with urllib.request.urlopen(req, timeout=60) as r:
        j = json.load(r)
    if not j.get("success"):
        raise RuntimeError(j.get("errors"))
    return j["result"][0]["results"]


def seal_token(obj):
    """The inverse of open_token, for the rotated Clover pair. Same layout as site/api/_lib.js sealToken."""
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    key = hashlib.sha256(os.environ["ACCESS_SECRET"].encode()).digest()
    iv = os.urandom(12)
    ct_tag = AESGCM(key).encrypt(iv, json.dumps(obj).encode(), None)  # ciphertext || 16-byte tag
    return base64.b64encode(iv + ct_tag[-16:] + ct_tag[:-16]).decode()


def open_token(blob):
    """AES-256-GCM under ACCESS_SECRET, written by site/api/square/callback.js or clover/callback.js: base64(iv|tag|ct)."""
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM
    key = hashlib.sha256(os.environ["ACCESS_SECRET"].encode()).digest()
    raw = base64.b64decode(blob)
    iv, tag, ct = raw[:12], raw[12:28], raw[28:]
    return json.loads(AESGCM(key).decrypt(iv, ct + tag, None))


def run_owner(o, send=True):
    tok = open_token(o["token_blob"])
    ws, we = week_bounds()
    provider = o.get("pos_provider") or "square"
    if provider == "clover":
        env = os.environ.get("CLOVER_ENV", "production")
        tok, rotated = clover_refresh(tok, env)
        if rotated:  # persist first: the old refresh token is dead the moment the new pair exists
            exp = dt.datetime.fromtimestamp(tok["access_token_expiration"], dt.timezone.utc).isoformat()
            d1("update owners set token_blob=?, token_expires_at=?, updated_at=datetime('now') where owner_id=?", (seal_token(tok), exp, o["owner_id"]))
        days = clover_days(tok["access_token"], o["merchant_id"], ws - dt.timedelta(weeks=9), we, env)
    else:
        days = square_days(tok["access_token"], o["location_id"], ws - dt.timedelta(weeks=9), we, os.environ.get("SQUARE_ENV", "production"))
    sig = S.gather(o["lat"], o["lon"], o["parcel_pin"])
    b = build(dict(name=o["shop_name"], address=o["address"], pos="Clover" if provider == "clover" else "Square"), days, sig)
    if not b["prose_check"]["ok"]:
        print(f"[{o['owner_id']}] NOT SENT: unsourced figures {b['prose_check']['unsourced']}", file=sys.stderr)
        return b
    if send:
        mid = mailgun(o["email"], f"Block Brief, week of {b['week_start']}: {o['shop_name']}", html_email(b), b["prose"])
        d1("insert into briefings (briefing_id, owner_id, week_start, signals_json, prose, sent_at, mailgun_id) values (?,?,?,?,?,datetime('now'),?)",
           (f"{o['owner_id']}:{b['week_start']}", o["owner_id"], b["week_start"], json.dumps(b["records"]["signals"], default=str), b["prose"], mid))
        print(f"[{o['owner_id']}] sent {mid}", file=sys.stderr)
    return b


if __name__ == "__main__":
    load_env()
    ap = argparse.ArgumentParser()
    ap.add_argument("--example", action="store_true")
    ap.add_argument("--owner")
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--no-send", action="store_true")
    ap.add_argument("--to", help="with --example: also email it here")
    a = ap.parse_args()
    if a.example:
        shop = json.loads((ROOT / "pipeline" / "example_shop.json").read_text())
        ws, we = week_bounds()
        days = sample_days(shop["name"], ws - dt.timedelta(weeks=9), we)
        sig = S.gather(shop["lat"], shop["lon"], shop["pin"])
        b = build(shop, days, sig, label_sample=True)
        out = ROOT / "site" / "public" / "example.json"
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(b, indent=1, default=str))
        print(b["prose"])
        print("\ncheck:", b["prose_check"], file=sys.stderr)
        if a.to and b["prose_check"]["ok"]:
            print("mailgun", mailgun(a.to, f"Block Brief, week of {b['week_start']}: {shop['name']} (example)", html_email(b), b["prose"]), file=sys.stderr)
    elif a.owner or a.all:
        where = "where owner_id = ?" if a.owner else "where plan_status in ('active','trial','clover') and token_blob is not null"
        for o in d1(f"select * from owners {where}", (a.owner,) if a.owner else ()):
            try:
                run_owner(o, send=not a.no_send)
            except Exception as e:  # one owner's failure never stops the Monday run
                print(f"[{o['owner_id']}] FAILED: {e}", file=sys.stderr)
