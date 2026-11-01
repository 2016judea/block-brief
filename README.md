# Block Brief

**Live:** https://block-brief.vercel.app

Every Monday, one email for one shop owner: last week's register next to what
the city filed within 500 feet of their door. The street dug up outside, the
apartment block going in across the road, the bar two doors down that just got
its licence, what the county now says the building is worth, what the
storefronts nearby sold for. Minneapolis, Square, $29 a month.

Buying Window turned inside out, for the owner. The Twin Cities public-records
model is what makes the briefing smart; it is not the thing being sold.

## How it works

1. The owner pays ($29/month, Stripe embedded checkout, `site/api/checkout.js`), then connects their Square account read-only (`site/api/square/connect.js` → Square OAuth → `site/api/square/callback.js`). The callback reads their main location's address, geocodes it, finds the Hennepin parcel, and seals the tokens (AES-256-GCM) into a Cloudflare D1 row.
2. Every Monday 06:10 (`launchd/dev.brickandmortar.block-brief.plist`) `pipeline/brief.py --all` runs on the Mac that holds the bricks substrate. Per owner: Square `GET /v2/payments` for the trailing nine weeks → day buckets; `pipeline/signals.py` → every record within 500 ft (city permits, right-of-way permits, liquor licences, the parcel's county value and its history, commercial sales within 1,500 ft); `claude-sonnet-5-5` writes the prose from that JSON only; a check refuses to send if the prose carries a figure the JSON does not; Mailgun sends it.
3. The landing page opens on a real block, read live: Mosaic Coffee Co., 3040 Hennepin Ave. The records are the city's and the county's own rows; the register is a labelled sample, because no one has connected that shop's Square. `pipeline/brief.py --example` rebuilds it.
4. Free slice (`site/api/around.js`): any Minneapolis address → what is filed within 500 ft right now, no login. The paid briefing adds the register, the value history and the sales.

## The data model

`DATA_MODEL.md`, written from the need before any data was looked at, then
checked field by field. The things that cannot be filled are listed there with
what they cost (day-ranged street closures, a parcel's own appeal date,
competitors in unlicensed trades, Saint Paul).

## Square

The tool skill is `~/.claude/skills/square-api/SKILL.md`. The one fact the
"bought without a call" claim rests on: **Square bills app subscriptions through
the seller's own Square account** (App Subscriptions, via the Subscriptions
API; the seller pays inside Square, the money lands in the developer's Square
balance; 2.9% + 30c processing, 20% revenue share after the first year). But
App Subscriptions and a marketplace listing both require the app to be listed,
listing requires five active sellers first, and Square **paused onboarding new
marketplace apps** (developer forum, 2026-10-01). So v1 bills through Stripe
and connects Square by OAuth from this site. The marketplace is the
distribution target once both gates open.

Developer account and app exist (2026-11-01, created as Aidan): app **Block
Brief**, production id `sq0idp-KAzlxYSV3b_xKnvvYDvzEQ`, sandbox id
`sandbox-sq0idb-OCIymLblrCZLAcxsHYbbQg`; secrets in `.env` and Vercel. The site
runs in **production** (`SQUARE_ENV=production` on Vercel and in `.env`, since
2026-11-01 evening): the production redirect URL in the Developer Console →
Block Brief → OAuth → Production reads exactly
`https://block-brief.vercel.app/api/square/callback` (it had saved mangled
earlier that day; re-entered and read back off `/api/portal/oauth-clients`).
Flip `SQUARE_ENV=sandbox` to test against the sandbox seller again; sandbox's
redirect URL is also correct.

## Running it

    set -a; . ~/Desktop/bricks/.env; set +a        # keys
    python3 pipeline/brief.py --example             # rebuild the landing example (calls Claude)
    python3 pipeline/brief.py --all --no-send       # dry-run every owner
    python3 scripts/deploy.py                       # Vercel, REST, public/ + api/

`.env` (gitignored): `ACCESS_SECRET`, `SQUARE_ENV`, `SQUARE_APPLICATION_ID`,
`SQUARE_APPLICATION_SECRET`, `SQUARE_LOGIN_EMAIL`, `SQUARE_LOGIN_PASSWORD`.
Vercel carries the same plus Stripe, Cloudflare and Mailgun.

## Price

$29 a month, one price, no trial, no tiers. Hypothesis (2026-11-01): a café
owner who learns one Monday that the 33% Tuesday dip was the gas company's
permit, or that a 228-unit building was just permitted across the road, has had
a conversation with their landlord or their staff that is worth more than a
month. Revised on evidence, not vibes.

## Licence

MIT. Records are public: City of Minneapolis open data, Hennepin County GIS.
