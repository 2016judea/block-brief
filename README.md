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

1. The owner pays ($29/month, Stripe embedded checkout, `site/api/checkout.js`), then connects their register read-only: Square (`site/api/square/connect.js` → Square OAuth → `site/api/square/callback.js`) or Clover (`site/api/clover/connect.js` → Clover OAuth v2 → `/clover/callback`). Either callback reads the location's name and address, geocodes it, finds the Hennepin parcel, and seals the tokens (AES-256-GCM) into a Cloudflare D1 row (`owners.pos_provider` says which register). A merchant who installs Block Brief from the **Clover App Market** skips Stripe: Clover bills them, and `/clover?merchant_id=…` (the app's Site URL, `site/api/clover/launch.js`) creates their row on the way through OAuth.
2. Every Monday 06:10 (`launchd/dev.brickandmortar.block-brief.plist`) `pipeline/brief.py --all` runs on the Mac that holds the bricks substrate. Per owner: Square `GET /v2/payments` or Clover `GET /v3/merchants/{mId}/payments` (refresh tokens rotated first; they are single-use) for the trailing nine weeks → day buckets; `pipeline/signals.py` → every record within 500 ft (city permits, right-of-way permits, liquor licences, the parcel's county value and its history, commercial sales within 1,500 ft); `claude-sonnet-5-5` writes the prose from that JSON only; a check refuses to send if the prose carries a figure the JSON does not; Mailgun sends it.
3. The landing page opens on a real block, read live: Mosaic Coffee Co., 3040 Hennepin Ave. The records are the city's and the county's own rows; the register is a labelled sample, because no one has connected that shop's Square. `pipeline/brief.py --example` rebuilds it.
4. Free slice (`site/api/around.js`): any Minneapolis address → what is filed within 500 ft right now, no login. The paid briefing adds the register, the value history and the sales.

## The data model

`DATA_MODEL.md`, written from the need before any data was looked at, then
checked field by field. The things that cannot be filled are listed there with
what they cost (day-ranged street closures, a parcel's own appeal date,
competitors in unlicensed trades, Saint Paul).

## Clover

`MARKETPLACES.md` is the 11/01 read of seven POS marketplaces; Clover is the only
one open to a new developer without a sales call or a fee, and **Clover bills the
merchant** (monthly tiers, 70% to the developer, no active-merchant minimum). Tool
skill: `~/.claude/skills/clover-api/SKILL.md`.

Developer account (2026-11-01, as Aidan): login `aidan@brickandmortar.dev`,
password + TOTP secret in `.env` (`CLOVER_LOGIN_PASSWORD`, `CLOVER_TOTP_SECRET`),
Developer Account Name **Brick & Mortar**, regions Latin America (the accidental
default) and North America (the one in use), developer id `R7XD0E0S48V0P`.

Sandbox app **Block Brief** `42R6YZF78NXY4` (NA sandbox, type Private + Web,
permissions Merchant/Orders/Payments read, Site URL
`https://block-brief.vercel.app/clover`, Alternate Launch Path `/clover`, OAuth
response Code). Secret in `.env` and Vercel (`CLOVER_APP_ID`, `CLOVER_APP_SECRET`,
`CLOVER_ENV=sandbox`). Driven end to end on 11/01 with the sandbox test merchant
`4ZNNY5AK5SNT1`: install from the sandbox App Market → Open the app → `/clover`
→ authorize → `/clover/callback` → `/connected/?pos=clover`, D1 row
`cl_4ZNNY5AK5SNT1` with a sealed pair, Monday dry-run through `clover_days()`.

Production app **Block Brief** `T2GTSDQ5FCTQ4` (NA production, type **App Market
app** + Web, same permissions and REST configuration as the sandbox app; secret in
`.env` and Vercel as `CLOVER_PROD_APP_*`, `CLOVER_ENV=production`, so the live
Connect Clover button already points at `www.clover.com`). Production developer id
`YRGPCMT5T4Z5Y`.

Where the listing stands (2026-11-01, evening):

- Developer Settings: Account Details saved as a **Business** (Brick and Mortar
  AI LLC, EIN, 1651 Eleanor Ave), Contact Info saved (emergency
  aidanjude2016@gmail.com). **Identity Verification is not saved: the form
  requires Aidan's date of birth, which is nowhere on this machine.** Until he
  types it and clicks "Verify Your Account", Clover will not review the app.
- Market Listing: tagline, description, legal (EULA `/terms/`, privacy
  `brickandmortar.dev/privacy/`), support (612-836-7262, Mon–Fri 9–5 Central,
  aidan@brickandmortar.dev, block-brief.vercel.app) and categorization (Reporting
  & Analytics; restaurants, bars, bakeries, salons, barbers, book stores, florists,
  grocery, pet, toy, other retail) are saved. **Not saved: the three merchant
  benefits, the icon, the cover and the screenshots.** The dashboard's image
  uploader opens a crop pop-up whose Submit ignored every automated click, and
  the benefits dialog could not be told apart from the others by automation;
  `listing/` holds the icon (`icon-512.png`), cover (`cover-1080x216.png`) and four
  screenshots ready to drag in by hand, and `icon-512.png` is currently attached
  as a *screenshot* by mistake (remove it under Manage Screenshots). Benefits to
  paste: see `listing/BENEFITS.md`.
- Walkthrough video for the functional review:
  https://block-brief.vercel.app/listing/walkthrough.mp4 (27 s, the public pages;
  the listing's own video field only takes YouTube/Vimeo URLs).
- Pricing & Distribution: a $29 tier needs a **bank account on the developer
  account first** (Developer Settings), which is his to enter.

Then "Submit App" on the production app.

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
`SQUARE_APPLICATION_SECRET`, `SQUARE_LOGIN_EMAIL`, `SQUARE_LOGIN_PASSWORD`,
`CLOVER_ENV`, `CLOVER_APP_ID`, `CLOVER_APP_SECRET`, `CLOVER_LOGIN_EMAIL`,
`CLOVER_LOGIN_PASSWORD`, `CLOVER_TOTP_SECRET`. Vercel carries the app ones plus
Stripe, Cloudflare and Mailgun (`scripts/vercel_env.py KEY…` pushes from `.env`).

## Price

$29 a month, one price, no trial, no tiers. Hypothesis (2026-11-01): a café
owner who learns one Monday that the 33% Tuesday dip was the gas company's
permit, or that a 228-unit building was just permitted across the road, has had
a conversation with their landlord or their staff that is worth more than a
month. Revised on evidence, not vibes.

## Licence

MIT. Records are public: City of Minneapolis open data, Hennepin County GIS.
