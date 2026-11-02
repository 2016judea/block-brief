# POS marketplaces: which ones take a new third-party app today

Read 2026-11-01 off each platform's own developer pages (links inline). The
question for Block Brief: can a stranger's app get listed without a sales call
or a paid tier, does the platform bill the merchant for it, and does the API
give one location's daily sales. Square paused new-app onboarding on
2026-10-01 (`~/.claude/skills/square-api/SKILL.md`), so this is the next-open
list. The rule it serves: we only integrate into existing platforms, never
outreach (`feedback_only_integrate_into_existing_platforms`, 11/01).

| Platform | Reaches | Open to new apps? | Prerequisites | Review | Billing | Rev share | Daily sales by location |
|---|---|---|---|---|---|---|---|
| **Clover App Market** (Fiserv) | cafés, restaurants, salons, retail | **Yes, self-serve.** Global Developer Dashboard signup, sandbox + production, no active-merchant minimum. | Production developer account verified (name, DOB, home address, EIN for a business, OFAC check); app needs privacy policy + TOS URLs, 3 benefits, screenshots, a functional-flow video, support email/site/phone. Bank account for payouts. | Functional, legal, listing review; "timelines vary", nudge devrel by email if long. | **Clover bills the merchant** on the 1st, monthly subscription tiers or metered; disburses to the developer's bank in the third week of the next month. | Developer keeps **70%** (30% transaction fee, developer terms §9.2). | Yes: `GET /v3/merchants/{mId}/payments?filter=createdTime>=…` (ms, cents, `result: SUCCESS`), 90-day window per call, 1,000 per page. One merchant id = one location. |
| **Shopify App Store** | retail (Shopify POS) | Yes, but **$19 one-time** registration per Partner account to list. | Public app + automated checks + demo screencast + test credentials; compliance webhooks; Shopify App Pricing mandatory (off-platform billing disallowed). | App Review team, email loop. | Charges land on the merchant's Shopify invoice. | **0% on the first $1M lifetime, 15% above**; 2.9% processing. | Yes: Orders API with `location_id`; retail only, cafés/restaurants rarely on it. |
| **Toast** (Partner Integrations) | restaurants | **Not self-serve.** Application → BD review ("high volume… delay") → discovery call → signed partner agreement → sandbox creds → 1-hour certification call → alpha/beta with 3–5 restaurants → GA. | Partner agreement with business terms; compliance/security/legal approval. | Months, human at every stage. | Some integrations "paid to the partner or to Toast"; merchant needs a Restaurant Management suite ($25/location/mo) to add integrations. | Set in the partner agreement (not published). | Yes once credentialed (orders API). |
| **Lightspeed** (Retail X / Restaurant K / eCom) | retail, restaurants | **Not self-serve.** Application form → technical partnerships team → partnership agreement → partner manager publishes. | Partner agreement; API licence forbids retaining data >60 days and "multi-store research". | Partner manager's final check. | eCom: "By Lightspeed eCom" or "By Partner", price "determined together with our partnerships team". Retail/Restaurant: not published. | Not published. | Yes (sales/register endpoints) once a partner. |
| **SpotOn** | restaurants | **No.** "Does SpotOn have an open API? No." Intake form, hand-picked Preferred Partners, certification call, 5–10 merchant pilot. | Integration agreement with SpotOn. | Human; "does not guarantee an integration, partnership, or timeline". | Merchant pays the partner directly; SpotOn charges no blanket fee. | n/a | `reporting:orders:read` scope exists, granted per agreement. |
| **Mindbody / Booker** | salons, spas, studios | API is self-serve but **there is no app store that bills the merchant**: the developer pays Mindbody $0.002 per call (free under 5,000/cycle) and bills the business itself; "Mindbody Integrations" is a directory you qualify for. | Developer account, go-live application with billing info on file. | Launch Checklist Review. | Developer bills; Mindbody bills the developer per call. | n/a | Sale endpoints per site, yes. |
| **Vagaro** | salons | **No.** APIs & webhooks are a per-business feature ($10/mo to the salon), enabled by Enterprise Sales after a request form, 5–7 business days. No third-party developer program or app listing. | n/a | n/a | n/a | n/a | Transactions webhook, per business. |

## Verdict

**Clover first.** It is the only one of the seven where a new developer can
sign up, build, submit and set a price without a human on the other side or
money up front, and where the platform bills the merchant and pays the
developer. Shopify is open too but costs $19 to register and reaches retail
only; it is the second integration if Clover approves. Toast, Lightspeed and
SpotOn are partner programmes with a sales call in the path; Mindbody and
Vagaro have no merchant-billed app store at all.

The Clover integration lives in `site/api/clover/` and `pipeline/brief.py`;
the tool skill is `~/.claude/skills/clover-api/SKILL.md`. Where the listing
stands is in the README.

## Sources

- Clover: docs.clover.com/dev/docs/approval, /developer-account-approval, /monetizing-your-apps, /billing-for-apps, /gdp-set-up-pricing-tiers, /get-all-payments, /applying-filters, /oauth-flows-in-clover, /app-approval-and-app-market-faqs; clover.com/developer-agreement §3.1, §8, §9.2.
- Shopify: shopify.dev/docs/apps/launch/distribution/revenue-share, /launch/billing, /launch/app-store-review/submit-app-for-review, /launch/shopify-app-store/app-store-requirements §1.2; community.shopify.dev thread 32021 (2026-03).
- Toast: pos.toasttab.com/partners/integration-partner-application; doc.toasttab.com/doc/devguide/integrationDevProcess.html; support.toasttab.com "Set Up Toast Partner Integrations" (2026-06-08).
- Lightspeed: developers.lightspeedhq.com/ecom/introduction/becoming-a-partner, /ecom/tutorials/publish-an-app, /terms (API licence 2025-05-20); lightspeedhq.com/partners/integrate.
- SpotOn: spoton.com/integrations (FAQ); developers.spoton.com/central-api/docs/spoton-oauth-integration-guide, /certification-process.
- Mindbody: support.mindbodyonline.com API FAQ; developers.mindbodyonline.com/Resources/DeveloperAgreement §10; Booker API FAQ.
- Vagaro: support.vagaro.com "Set Up Webhooks From Vagaro" (2026-07-01); vagaro.com/pro/updates/webhooks.
