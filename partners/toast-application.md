# Toast Integration Partner application — Block Brief

Prepared 2026-11-01. **Step 1 submitted by Aidan 2026-11-11** (API Terms of Use agreed as Brick and Mortar AI LLC, aidan@brickandmortar.dev). Step 2 email arrived 11/11. **Step 3 form filled headless 2026-11-17, not submitted**: Aidan answers the six blanks and submits (see "Step 3 — form as filled").

Toast's application is three steps, not one form
(pos.toasttab.com/partners/integration-partner-application):

1. **Agree to the Toast API Terms of Use** at
   pos.toasttab.com/api-documentation-license-agreement. Three fields and an
   "I Agree" button. This binds the LLC to Toast's API terms (binding
   individual arbitration, no class actions; notices to 333 Summer Street,
   Boston). Filled, not clicked. Screenshot: `partners/toast-step1-filled.png`.
2. Toast emails instructions and API documentation access to the address in step 1.
3. The application form itself is linked from that email. It is not public, so
   its exact fields are unknown. The answers below cover what Toast's dev guide
   says it vets on (doc.toasttab.com/doc/devguide/integrationDevProcess.html:
   fit, business opportunity, technical readiness, customer demand). Paste them
   into whatever fields the email's form asks for.

## Step 1 — filled in the browser

| Field | Value |
|---|---|
| Email Address | aidan@brickandmortar.dev |
| First and Last Name | Aidan Jude |
| Company Name | Brick and Mortar AI LLC |

The legal name is "Brick and Mortar AI LLC" ("and", not "&"), per the IRS EIN letter.

## Step 3 — answers

### Company

| Field | Value |
|---|---|
| Legal name | Brick and Mortar AI LLC |
| EIN | 42-4059505 |
| State / file number | Minnesota, SoS file 1658388200024 |
| Contact | Aidan Jude, aidan@brickandmortar.dev |
| Phone | 612-836-7262 |
| Company website | https://brickandmortar.dev |
| Product website | https://block-brief.vercel.app |
| Business mailing address | 1651 Eleanor Ave, Saint Paul, MN 55116 (registered office on the Articles and the IRS EIN letter) |
| Company size | 1 |

### Integration name

Block Brief

### Category

Analytics / reporting. Read-only.

### Describe your integration

Every Monday, one email for one restaurant owner. Last week's sales from their
register, next to what the city filed within 500 feet of their door.

The street work permitted outside. A liquor licence granted to the bar two
doors down. A 228-unit building permitted across the road. What
the county now says the landlord's building is worth, and how that moved
year over year. What the storefronts nearby sold for.

An owner sees a slow Tuesday and guesses. Weather, staff, a bad week. Most of
the time the answer was filed with the city a week earlier, and nobody joins
the two. Block Brief does. If the dip lines up with a gas-company permit on
the block, the briefing says so, and it shows the permit.

Every number in the email comes from the owner's own sales or from a public
record. The prose is written by a model from that data only, and a check
refuses to send if the text carries a figure the data doesn't.

### What Toast data do you need?

Orders and payments, read-only, for the restaurant's location. Daily totals:
gross sales, number of checks, average check, refunds, and an hourly
breakdown, for the trailing nine weeks. Plus the location's address, which
is the join to the city's records.

Nothing is written back to Toast. No menu, labor, guest or card data.

### How often do you call the API?

Once a week per location, Monday morning, plus a single backfill of nine
weeks when the restaurant first connects.

### Pricing

$29 a month per location. One price, no tiers, no trial. Open to billing
through Toast if the partner agreement calls for it.

### Current status

Live at https://block-brief.vercel.app, in Minneapolis. Any Minneapolis
address gets what's filed within 500 feet of it, free, no login. The paid
briefing runs on Square today: the owner connects read-only by OAuth, pays
through Stripe, and the briefing goes out every Monday at 6:10am. Clover is
being built now. Toast is next, because restaurants are who this is for.

### Markets

Minneapolis today. The city records come from the City of Minneapolis open
data portal and Hennepin County GIS. A new city is a new set of records, not
a rebuild.

### Mutual customers / customer demand

None on Toast yet. Block Brief has no Toast integration, so no Toast
restaurant can use it today.

## Step 3 — form as filled 2026-11-17

**Form:** https://pos.toasttab.com/partners/inquiry-request-form. The 11/11 email's
"Partner Inquiry Request Form" link (go.toasttab.com) redirects there and adds a
`mkt_tok` tracking parameter. The page embeds a monday.com form titled
"Integration Request Application"
(forms.monday.com/forms/embed/4b133cd258772ce91bbaa045efb04f25). The rest of the
form appears only after you pick the purpose, and every field after it is
required.

It was filled headless and **not submitted**. A guard in the page counted zero
submit attempts. Screenshot: `partners/toast-form-filled-2026-11-17.png` (the
textareas show only their first lines, but the counters confirm the full text).
16 of 22 fields are filled. The 6 left blank are required, so the form won't
submit until they're answered.

| # | Field, as the form shows it | Value entered | From |
|---|---|---|---|
| 1 | Company Name | Brick and Mortar AI LLC | Company › Legal name |
| 2 | What is your purpose of filling out this form? | I wish to develop a technical integration between my product and Toast's APIs | (the other option sends you to refer.toasttab.com) |
| 3 | What is your TARGET location count of customer brands you work with? | **blank** (options: 1-15, 16-40, 41-500, 500+) | not in this file |
| 4 | Which of these categories best describes your product focus? | Commerce | Category: "Analytics / reporting" is not an option. Commerce is "improving the restaurant operations for owners and managers" |
| 5 | Contact Name | Aidan Jude | Company › Contact |
| 6 | Contact Email | aidan@brickandmortar.dev | Company › Contact |
| 7 | Contact Role | **blank** | not in this file |
| 8 | Company Website | https://brickandmortar.dev | Company › Company website |
| 9 | What countries do you currently operate within? | United States | Markets (Minneapolis) |
| 10 | Average Monthly Revenue per Customer | 29 | Pricing ($29 a month per location; this is the price, not a measured average) |
| 11 | Average customer size (units/locations) | **blank** (the form says: "If SMB focused, put "1".") | customer number, not in this file |
| 12 | How many customers do you provide services for? | **blank** | customer number, not in this file |
| 13 | How many of your customers are also Toast customers? | 0 | Mutual customers ("None on Toast yet") |
| 14 | Please list the names of any customers that are specifically requesting an integration with Toast | None on Toast yet. Block Brief has no Toast integration, so no Toast restaurant can use it today. | Mutual customers / customer demand, verbatim |
| 15 | How large is your sales team? | **blank** | not in this file (company size is 1) |
| 16 | Please provide a brief description of your product | Block A below (1,288 chars) | Describe your integration + Current status, verbatim |
| 17 | Does your product include payment processing? | No. | no prepared answer; the product reads sales and takes no card data |
| 18 | Please describe what you would like the integration to do | Block B below (442 chars) | What Toast data do you need? + How often do you call the API?, verbatim |
| 19 | What level of API access would you require? | Read-Only | Category ("Read-only") |
| 20 | What other POS companies do you integrate with? (multi-select) | Square, Clover | Current status (Square live, Clover being built) |
| 21 | Does your organization offer support, products/services or have any initiatives around the following: (language access, disability, marginalized communities) | **blank** (options: Not at this time, Yes) | not in this file |
| 22 | What other POS companies do you integrate with? (text) | Square, Clover (in progress) | Current status |

The form has no field for the EIN, SoS number, phone, mailing address, company size, product URL, integration name or the rest of Pricing.

Block A, product description:

```
Every Monday, one email for one restaurant owner. Last week's sales from their register, next to what the city filed within 500 feet of their door.

The street work permitted outside. A liquor licence granted to the bar two doors down. A 228-unit building permitted across the road. What the county now says the landlord's building is worth, and how that moved year over year. What the storefronts nearby sold for.

An owner sees a slow Tuesday and guesses. Weather, staff, a bad week. Most of the time the answer was filed with the city a week earlier, and nobody joins the two. Block Brief does. If the dip lines up with a gas-company permit on the block, the briefing says so, and it shows the permit.

Every number in the email comes from the owner's own sales or from a public record. The prose is written by a model from that data only, and a check refuses to send if the text carries a figure the data doesn't.

Live at https://block-brief.vercel.app, in Minneapolis. Any Minneapolis address gets what's filed within 500 feet of it, free, no login. The paid briefing runs on Square today: the owner connects read-only by OAuth, pays through Stripe, and the briefing goes out every Monday at 6:10am. Clover is being built now. Toast is next, because restaurants are who this is for.
```

Block B, what the integration does:

```
Orders and payments, read-only, for the restaurant's location. Daily totals: gross sales, number of checks, average check, refunds, and an hourly breakdown, for the trailing nine weeks. Plus the location's address, which is the join to the city's records.

Nothing is written back to Toast. No menu, labor, guest or card data.

Once a week per location, Monday morning, plus a single backfill of nine weeks when the restaurant first connects.
```

## Left blank

- On the real form (2026-11-17), six required fields: TARGET location count,
  Contact Role, Average customer size, How many customers, Sales team size, and
  the language/disability/communities initiatives question. See the table above.

## How Aidan submits

1. Open pos.toasttab.com/api-documentation-license-agreement, scroll to "API
   form submission", enter the three step-1 values above, click **I Agree**.
   That agrees to Toast's API terms on behalf of the LLC.
2. Wait for Toast's email at aidan@brickandmortar.dev. Open the application
   link in it.
3. Paste the step-3 answers above into its fields and submit.

## Held 2026-11-01: I Agree NOT clicked

Read the full licence (saved beside this file) before clicking. §4.8 obliges the LLC, from the
moment of I Agree, to carry at its own expense: general liability $1M/$2M (Toast as additional
insured), E&O $2M, and **cyber liability $5M per occurrence**, with certificates on request. That
is a recurring spend, so it's a money gate. Also binding: arbitration (§14), a 6-month non-solicit
of Toast merchants with 2x-revenue liquidated damages (§7.3), Toast Data may not feed
"aggregated datasets for sale" (§11), audit rights (§4.7). Waiting on Aidan.

**Decision 2026-11-01 (Aidan): hold Toast.** "if we can get some actual traffic and sales from a different platform and we know it works and will scale then we can go back to it." Reopen only once another platform (Clover first) shows real installs and paid subscriptions; then price the §4.8 insurance and agree.
