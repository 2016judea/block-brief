# Data model: the ideal weekly briefing for one shop owner

Written 2026-11-01 from the need alone, before looking at what data we hold
(`~/.claude/BUSINESS.md` rule 5). The need, in Aidan's words the same day: *one
tool one owner uses every week.* The owner connects their register. Every Monday
one briefing joins their own numbers to what the city filed around their door:
the street dug up outside, the apartment block going up across the road, the bar
that just got its licence two doors down, the county's new opinion of what their
building is worth, and what the storefronts near them sold for. Buying Window
turned inside out, for the owner.

The reality check against this model is at the bottom, added after probing.

## Entities

```
Owner ──1:N── Shop ──N:1── Parcel ──1:N── Assessment (by year)
                │              │
                │              ├──1:N── RecordedSale
                │              └──N:N── Neighbour (parcels within R ft)
                │
                ├──1:N── DailySales   (from the POS, one row per day)
                ├──1:N── Signal       (one public record, with a distance)
                └──1:N── Briefing     (one per Monday; joins the two)
```

## Owner — *who gets the email?*

| field | question it answers |
|---|---|
| owner_id | which account |
| email | where the Monday briefing goes |
| pos_provider, pos_merchant_id | which register is connected (Square first) |
| pos_access_token (encrypted), pos_refresh_token (encrypted), token_expires_at | can we still read their register this Monday |
| plan_status, subscribed_at | are they paying, since when |
| timezone | which day is "Monday" and "yesterday" for this shop |

## Shop — *where is the door?*

| field | question |
|---|---|
| shop_id, owner_id | whose |
| pos_location_id | which register location (one briefing per location) |
| name | what the owner calls it |
| address, city, zip, lat, lon | where the door is |
| parcel_pin | the county parcel the door sits on: the join key to everything the city files |
| trade | café / salon / bar / retail, from the POS category: changes which signals matter |
| open_days, open_hours | which days count as trading days, so a closed Sunday is not a dip |

## DailySales — *what did the register do?*

| field | question |
|---|---|
| shop_id, day | which shop, which day |
| gross_cents | what came in |
| n_payments | how many transactions (a dip in count is traffic; a dip in ticket is price) |
| avg_ticket_cents | gross / count |
| refunds_cents | what went back out |
| hour_histogram (24 ints) | when the day happened: a lunch that vanished vs. a slow morning |

Derived per week, never stored by hand: `week_gross`, `week_vs_prior_pct`,
`week_vs_same_week_last_year_pct`, `worst_day`, `worst_day_vs_typical_pct`
(typical = median of the same weekday over the trailing 8 weeks).

## Parcel / Assessment / RecordedSale — *what does the county say about the building?*

| field | question |
|---|---|
| pin, address | which parcel |
| owner_name, taxpayer_name | who the landlord is (the owner may or may not be them) |
| property_type, year_built, lot_sqft | what kind of building |
| assessment.year, total_value, land_value, building_value | the county's opinion of what it is worth, per year |
| assessment.prior_total_value, change_pct | did it jump, and by how much |
| assessment.taxes_payable | what the tax bill is: the number a triple-net tenant actually pays |
| assessment.notice_date, appeal_deadline | when the new value lands and when the window to contest it closes |
| recorded_sale.date, price, deed_type, arms_length | what it last sold for, and whether that price means anything |

## Signal — *one record the city filed near the door*

| field | question |
|---|---|
| signal_id, shop_id | for whom |
| kind | one of: `street_work`, `big_build`, `new_competitor`, `licence_change`, `value_change`, `comp_sale`, `demolition` |
| source, source_id, source_url | which register, which row, where to read it |
| filed_date | when the city wrote it down |
| start_date, end_date | when it affects the street (street work) or when it opens (a build) |
| address, lat, lon, distance_ft | where, and how far from the door |
| what | the record's own words, cut to one line |
| who | the applicant, when it is a company (never a homeowner's name) |
| size | units, dollars, feet: the one number that says how big |
| effect | the direction we expect on the register: `fewer_walk_ins`, `more_walk_ins_later`, `shared_customers`, `higher_rent_risk`, `lease_leverage`, `none_yet` |
| first_seen_briefing_id | so a signal is told once, then only when it changes |

What each kind answers for the owner:

- `street_work` — *why was Tuesday down 30%?* A utility cut, a sidewalk closure, a resurfacing on the block. Needs a date range that overlaps the dip.
- `big_build` — *will there be more people walking past next year?* A new apartment or commercial permit within R ft with a unit count or a fee that implies size.
- `new_competitor` — *who just opened near me selling what I sell?* A new food, liquor or trade licence within R ft, same trade as the shop.
- `licence_change` — *did a neighbour close?* A licence lapsed or went inactive within R ft (an empty storefront next door changes foot traffic too).
- `value_change` — *is my rent about to go up?* The shop's own parcel's assessed value moved; the appeal window is open or coming.
- `comp_sale` — *what is my landlord's building worth, in the market's words?* Storefronts within R ft that sold, with price and date, for the lease renewal conversation.
- `demolition` — *is the building across the street coming down?* A wrecking permit within R ft.

## Briefing — *the one thing they read on Monday*

| field | question |
|---|---|
| briefing_id, shop_id, week_start | which Monday |
| sales_summary (struct) | the week's derived numbers, above |
| signals (list of signal_id) | what was new or changed this week, nearest first |
| prose | the briefing as sent: plain language, the register's numbers next to the city's records, no number the records did not carry |
| sent_at, opened_at | did it go, did they read it |

The model writes `prose` from `sales_summary` + `signals`. It never supplies a
number. Every figure in the prose must be traceable to a field above.

## Joins

- Shop → Parcel: geocode the POS location's address, then point-in-polygon on the county parcel layer; fall back to nearest parcel centroid within 50 ft.
- Shop → Signal: every record with a point inside R = 500 ft of the parcel centroid (street work and comps use a wider R; set per kind).
- DailySales → Signal: a `street_work` signal whose `[start_date, end_date]` overlaps a `worst_day` is the explanation the briefing leads with.
- Assessment → Signal `value_change`: the shop's own pin, current year vs prior.

---

## Reality check (2026-11-01, Minneapolis only)

Checked field by field against the bricks substrate and the live city/county services.

**Fills:**

- Owner / Shop / DailySales: Square OAuth (`MERCHANT_PROFILE_READ`, `PAYMENTS_READ`, `ORDERS_READ`) + `GET /v2/locations`, `GET /v2/payments?location_id&begin_time&end_time` (amount in cents, `status=COMPLETED`, `created_at`). Hour histogram from `created_at`. `trade` from the location's `mcc` / business type. Open days are inferred from zero-sales weekdays, not asked.
- Parcel, Assessment (current), RecordedSale: Hennepin `LAND_PROPERTY/MapServer/1` live (`MKT_VAL_TOT`, `TAX_TOT`, `SALE_DATE`, `SALE_PRICE`, `SALE_CODE_NAME`, `OWNER_NM`, `BUILD_YR`, `PARCEL_AREA`), plus `bricks/data/hennepin_gis.duckdb` for the point-in-polygon join. **Trap found here:** the substrate's `market_value` column is `TOTAL_MV1`, the first property-class slice, not `MKT_VAL_TOT`; on a mixed apartment/commercial parcel (3040 Hennepin) it reads $1.12M where the county's total is $3.2M. Read `MKT_VAL_TOT` live.
- Assessment (prior years): `bricks/data/tax_appeals/mpls_commercial_value_changes.parquet`, Minneapolis commercial/apartment/industrial parcel-years 2018–2025 (`v`, `pv`, `chg`). Residential-class parcels and St Paul have no history here.
- `big_build`, `demolition`: Minneapolis `CCS_Permits` live (`mpls-permits` skill). Unit counts live in `comments` free text; `totalFees` is the size proxy. `value` is empty on every row.
- `street_work`: Minneapolis `PWROW_Admin_Utility_Sidewalk_Permits` live (23,718 rows; `Permit_Type` Utility/SidwlkConB…, `Processed_Date`, `Expiration_Date`, `Applicant_Name`, point). `Excavation_Permits` (262 rows, stale to 2020). `Current_Projects_and_Events_v2` road closures (26 points, 72 lines citywide; none in Uptown today). The 2026 construction map carries street reconstruction/resurfacing lines with start/end **year** only.
- `new_competitor`, `licence_change`: Minneapolis `On_Sale_Liquor` / `Off_Sale_Liquor` live (`issueDate`, `licenseStatus`, `apn`, point). Food: `Food_Inspections` is one row per inspection violation, deduped to a facility; it carries no licence issue date, so a new café is detected by first appearance, not by a filed date.
- `comp_sale`: `hennepin_gis.duckdb` parcels with `PR_TYP_NM1` commercial and `sale_date`, with the four Hennepin sale traps (`[[reference_hennepin_value_and_sale_emit]]`).

**Cannot fill, and what that costs:**

- `street_work.start_date / end_date` as a day range: utility permits carry a processed date and an expiry months out, not the days the street was actually cut. The briefing can say *"a gas-line permit was issued for your block on 28 Oct"*, not *"the street was closed Tuesday"*. The overlap with a sales dip is therefore suggestive, never asserted.
- `Assessment.notice_date / appeal_deadline`: derived from the Minnesota calendar (notices in March; Tax Court petition by 30 April of the payable year), not from a record. Stated as the rule, not as this parcel's own date.
- `new_competitor` for unlicensed trades (a salon, a print shop, a gym): the city licenses food, liquor and a few health trades only. For a salon owner the competitor signal is empty.
- `DailySales.open_hours`: not in Square's payments; inferred.
- Saint Paul: permits stopped publishing 2025-06-30; value history absent. **Minneapolis only in v1**, and the page says so.

**Call:** the model holds. Nothing above reduces the briefing to a lookup. The
v1 slice is Minneapolis, Square, one weekly email, no dashboard.
