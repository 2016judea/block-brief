#!/usr/bin/env python3
"""Gather every public record filed within reach of one shop's door.

One function per Signal kind in DATA_MODEL.md. Every number in the output is a
field read off a register; nothing here is typed. The live layers are queried
on every run (the city updates them daily); the two substrate reads (comparable
sales, value history) come from the bricks repo on this Mac.

    python3 pipeline/signals.py --lat 44.94686 --lon -93.29867 --pin 0402824210187

Sources (DATA_MODEL.md, "Reality check"):
  CCS_Permits (Minneapolis)                        -> big_build, demolition
  PWROW_Admin_Utility_Sidewalk_Permits (Minneapolis) -> street_work
  On_Sale_Liquor / Off_Sale_Liquor (Minneapolis)   -> new_competitor, licence_change
  Hennepin LAND_PROPERTY/MapServer/1 (live)        -> value_change (current year), parcel
  bricks data/tax_appeals/mpls_commercial_value_changes.parquet -> value_change (history)
  bricks data/hennepin_gis.duckdb                  -> comp_sale, pin lookup
"""
import argparse
import datetime as dt
import json
import math
import re
import sys
import urllib.parse
import urllib.request
from pathlib import Path

MPLS = "https://services.arcgis.com/afSMGVsC7QlRK1kZ/arcgis/rest/services"
HENN = "https://gis.hennepin.us/arcgis/rest/services/HennepinData/LAND_PROPERTY/MapServer/1/query"
BRICKS = Path.home() / "Desktop" / "bricks"
RADIUS_FT = 500
COMP_RADIUS_FT = 1500
FT_PER_DEG = 20902231 * math.pi / 180  # Earth radius in feet times radians per degree


def dist_ft(lat1, lon1, lat2, lon2):
    p = math.pi / 180
    return math.hypot((lon2 - lon1) * math.cos((lat1 + lat2) / 2 * p), (lat2 - lat1)) * FT_PER_DEG


def envelope(lat, lon, ft):
    dlat = ft / FT_PER_DEG
    dlon = dlat / math.cos(lat * math.pi / 180)
    return json.dumps({"xmin": lon - dlon, "ymin": lat - dlat, "xmax": lon + dlon, "ymax": lat + dlat})


def arcgis(url, where, lat, lon, ft, out_fields="*"):
    rows, offset = [], 0
    while True:
        q = urllib.parse.urlencode({
            "where": where, "geometry": envelope(lat, lon, ft), "geometryType": "esriGeometryEnvelope",
            "inSR": 4326, "spatialRel": "esriSpatialRelIntersects", "outFields": out_fields,
            "returnGeometry": "false", "f": "json", "resultOffset": offset, "resultRecordCount": 2000,
        })
        with urllib.request.urlopen(url + "?" + q, timeout=60) as r:
            j = json.load(r)
        if "error" in j:
            raise RuntimeError(f"{url}: {j['error']}")
        rows += [f["attributes"] for f in j.get("features", [])]
        if not j.get("exceededTransferLimit"):
            return rows
        offset += 2000


def day(ms):
    return dt.datetime.utcfromtimestamp(ms / 1000).date().isoformat() if ms else None


def clean_comment(s):
    """Permit comments carry reviewer boilerplate; cut at the first marker (mpls-permits skill)."""
    s = (s or "").strip()
    if s.lower().startswith("source information is not available"):
        return ""
    for marker in ("certificate of occupancy", "const type", "CONST TYPE", "Building Code", "Construction Documents", "(JJL)", "-ACW", "(DMH", "special inspec"):
        i = s.find(marker)
        if i > 0:
            s = s[:i]
    return re.sub(r"\s+", " ", s).strip(" .-")


def is_company(name):
    return bool(name) and bool(re.search(r"\b(INC|LLC|CO|CORP|CONSTRUCTION|BUILDERS|HOMES|ENERGY|CABLE|COMMUNICATIONS|SEWER|WATER|UNDERGROUND|ELECTRIC|WIRELESS|MIDWEST)\b", name.upper()))


def units_in(comment):
    m = re.search(r"(\d{1,4})[\s-]*unit", comment or "", re.I)
    return int(m.group(1)) if m else None


# ---- signals -------------------------------------------------------------

def permits(lat, lon, since):
    rows = arcgis(f"{MPLS}/CCS_Permits/FeatureServer/0/query", f"issueDate >= date '{since}'", lat, lon, RADIUS_FT,
                  "Display,APN,Latitude,Longitude,permitType,occupancyType,workType,comments,issueDate,completeDate,applicantName,totalFees,status,milestone")
    out, seen = [], set()
    for r in rows:
        d = dist_ft(lat, lon, r["Latitude"], r["Longitude"])
        if d > RADIUS_FT:
            continue
        what = clean_comment(r["comments"])
        key = (r["Display"], what[:80])
        if key in seen:
            continue
        seen.add(key)
        base = dict(source="Minneapolis CCS_Permits", source_id=None, filed_date=day(r["issueDate"]),
                    address=r["Display"], lat=r["Latitude"], lon=r["Longitude"], distance_ft=round(d), what=what,
                    who=r["applicantName"] if is_company(r["applicantName"]) else None,
                    status=r["status"], milestone=r["milestone"], fees_usd=round(r["totalFees"] or 0))
        if r["permitType"] == "Wrecking":
            out.append(dict(base, kind="demolition", effect="fewer_walk_ins", size=None))
        elif r["workType"] == "New" and r["occupancyType"] in ("MFD", "Comm", "Mixed", "TH", "3to4"):
            out.append(dict(base, kind="big_build", effect="more_walk_ins_later", size=units_in(r["comments"]), occupancy=r["occupancyType"]))
        elif r["permitType"] == "Commercial" and r["occupancyType"] in ("Comm", "Mixed") and (r["totalFees"] or 0) >= 500:
            out.append(dict(base, kind="tenant_work", effect="none_yet", size=None, occupancy=r["occupancyType"]))
    return out


def street_work(lat, lon, since):
    rows = arcgis(f"{MPLS}/PWROW_Admin_Utility_Sidewalk_Permits_AGO_en_us_readonly/FeatureServer/0/query",
                  f"Processed_Date >= date '{since}'", lat, lon, RADIUS_FT,
                  "Display,Permit_Number,Processed_Date,Expiration_Date,Permit_Type,Work_Type,Status__Permit_,Permit_Detail,Comments,Applicant_Name,Latitude,Longitude")
    out = []
    for r in rows:
        d = dist_ft(lat, lon, r["Latitude"], r["Longitude"])
        if d > RADIUS_FT:
            continue
        kind_words = {"SidwlkConB": "sidewalk closed for work", "Utility": "utility line work", "Water": "water tap", "Sewer": "sewer work", "Excavation": "street dug up"}
        what = kind_words.get(r["Permit_Type"], r["Permit_Type"])
        if r.get("Permit_Detail") and r["Permit_Detail"] not in ("N", "Y"):
            what += f": {r['Permit_Detail']}"
        if r.get("Comments"):
            what += ". " + re.sub(r"\s+", " ", r["Comments"]).strip()[:140]
        out.append(dict(kind="street_work", source="Minneapolis right-of-way permits", source_id=r["Permit_Number"],
                        filed_date=day(r["Processed_Date"]), end_date=day(r["Expiration_Date"]), address=r["Display"],
                        lat=r["Latitude"], lon=r["Longitude"], distance_ft=round(d), what=what,
                        who=r["Applicant_Name"] if is_company(r["Applicant_Name"]) else None, status=r["Status__Permit_"],
                        effect="fewer_walk_ins", size=None))
    return out


def liquor(lat, lon, since):
    out = []
    for layer, sale in (("On_Sale_Liquor", "on-sale"), ("Off_Sale_Liquor", "off-sale")):
        rows = arcgis(f"{MPLS}/{layer}/FeatureServer/0/query", "1=1", lat, lon, RADIUS_FT,
                      "licenseNumber,licenseType,licenseStatus,liquorType,issueDate,expirationDate,licenseName,address,endorsements,lat,long,lastUpdateDate,apn")
        for r in rows:
            d = dist_ft(lat, lon, r["lat"], r["long"])
            if d > RADIUS_FT:
                continue
            issued = day(r["issueDate"])
            status = r["licenseStatus"]
            if status in ("Inactive", "Expired", "Revoked"):
                kind, effect = "licence_change", "fewer_walk_ins"
            elif issued and issued >= since:
                kind, effect = "new_competitor", "shared_customers"
            else:
                continue
            out.append(dict(kind=kind, source=f"Minneapolis {layer.replace('_', ' ')}", source_id=r["licenseNumber"],
                            filed_date=issued, address=r["address"], lat=r["lat"], lon=r["long"], distance_ft=round(d),
                            what=f"{r['licenseName']}: {sale} {r['licenseType'].replace('BL', '').lower()} licence, {status.lower()}" + (f" ({(r['endorsements'] or '').strip().split(';')[0].strip()})" if r.get("endorsements") else ""),
                            who=r["licenseName"], status=status, effect=effect, size=None, expires=day(r["expirationDate"])))
    return out


def parcel_live(pin):
    q = urllib.parse.urlencode({"where": f"PID='{pin}'", "returnGeometry": "false", "f": "json",
                                "outFields": "PID,HOUSE_NO,STREET_NM,OWNER_NM,TAXPAYER_NM,BUILD_YR,SALE_DATE,SALE_PRICE,SALE_CODE_NAME,PARCEL_AREA,MKT_VAL_TOT,TAXABLE_VAL_TOT,TAX_TOT,PR_TYP_NM1,PR_TYP_NM2,TOTAL_MV1,TOTAL_MV2,PETITION_REVIEW_IND,MUNIC_NM"})
    with urllib.request.urlopen(HENN + "?" + q, timeout=60) as r:
        j = json.load(r)
    f = j["features"][0]["attributes"] if j.get("features") else None
    if not f:
        return None
    return {k: (v.strip() if isinstance(v, str) else v) for k, v in f.items()}


def value_history(pin):
    import duckdb
    pq = BRICKS / "data" / "tax_appeals" / "mpls_commercial_value_changes.parquet"
    if not pq.exists():
        return []
    rows = duckdb.sql(f"select yr, v, pv, chg from '{pq}' where pin='{pin}' order by yr").fetchall()
    return [dict(year=y, total_value=v, prior_total_value=pv, change_pct=round(c * 100, 1) if c is not None else None) for y, v, pv, c in rows]


def value_change(pin):
    live = parcel_live(pin)
    if not live:
        return None, []
    hist = value_history(pin)
    cur = live["MKT_VAL_TOT"]
    prior = None
    # the live layer carries the 2025 assessment (payable 2026) as of 2026-11-01: the panel's last year equals it
    for h in reversed(hist):
        if h["total_value"] == cur:
            prior = h["prior_total_value"]
            year = h["year"]
            break
    else:
        year = hist[-1]["year"] + 1 if hist else None
        prior = hist[-1]["total_value"] if hist else None
    sig = dict(kind="value_change", source="Hennepin County parcel record", source_id=pin, filed_date=None,
               address=f"{live['HOUSE_NO']} {live['STREET_NM']}", distance_ft=0, effect="higher_rent_risk",
               assessment_year=year, total_value=cur, prior_total_value=prior,
               change_pct=round((cur - prior) / prior * 100, 1) if prior else None,
               taxes_payable=live["TAX_TOT"], landlord=live["OWNER_NM"], taxpayer=live["TAXPAYER_NM"],
               property_type=", ".join(t for t in (live["PR_TYP_NM1"], live["PR_TYP_NM2"]) if t),
               year_built=live["BUILD_YR"], lot_sqft=round(live["PARCEL_AREA"]),
               last_sale=dict(date=live["SALE_DATE"], price=live["SALE_PRICE"], deed=live["SALE_CODE_NAME"]) if live.get("SALE_PRICE") else None,
               under_petition=(live.get("PETITION_REVIEW_IND") or "").strip() not in ("", "N"),
               what=f"county value {year}: ${cur:,.0f}" + (f", was ${prior:,.0f} ({(cur - prior) / prior * 100:+.1f}%)" if prior else ""),
               size=cur)
    return sig, hist


def comp_sales(lat, lon, since_yyyymm):
    import duckdb
    db = BRICKS / "data" / "hennepin_gis.duckdb"
    if not db.exists():
        return []
    con = duckdb.connect(str(db), read_only=True)
    rows = con.sql(f"""
        select pin, addr_house, addr_street, PR_TYP_NM1, sale_price, sale_date, sale_code, market_value, county_sqft, build_yr, lat, lon
        from parcels
        where PR_TYP_NM1 in ('COMMERCIAL-PREFERRED','COMMERCIAL') and sale_date >= '{since_yyyymm}' and sale_price > 0
          and abs(lat - {lat}) < 0.01 and abs(lon - {lon}) < 0.014
    """).fetchall()
    out = []
    for pin, h, s, typ, price, sd, code, mv, sqft, yr, plat, plon in rows:
        d = dist_ft(lat, lon, plat, plon)
        if d > COMP_RADIUS_FT:
            continue
        arms = code in ("WARRANTY DEED",)
        multi = "MORE THAN ONE PARCEL" in (code or "")
        out.append(dict(kind="comp_sale", source="Hennepin County recorded sales", source_id=pin, filed_date=f"{sd[:4]}-{sd[4:6]}",
                        address=f"{h} {s}", lat=plat, lon=plon, distance_ft=round(d), effect="lease_leverage",
                        what=f"{h} {s.title()} sold for ${price:,.0f} ({sd[:4]}-{sd[4:6]})" + ("" if arms else f"; deed: {code.lower()}") + (", more than one parcel in the price" if multi else ""),
                        size=price, price=price, deed=code, arms_length=arms, multi_parcel=multi, lot_sqft=round(sqft or 0), year_built=yr))
    out.sort(key=lambda r: r["distance_ft"])
    return out


def pin_for(lat, lon):
    """Point-in-polygon on the substrate's parcel layer; nearest centroid within 50 ft as fallback."""
    import duckdb
    con = duckdb.connect(str(BRICKS / "data" / "hennepin_gis.duckdb"), read_only=True)
    con.sql("install spatial; load spatial")
    r = con.sql(f"select pin, addr_house, addr_street, addr_city from parcels where ST_Contains(geom, ST_Point({lon}, {lat})) limit 1").fetchall()
    if not r:
        r = con.sql(f"select pin, addr_house, addr_street, addr_city from parcels where abs(lat-{lat})<0.0005 and abs(lon+{-lon})<0.0007 order by (lat-{lat})*(lat-{lat})+(lon-{lon})*(lon-{lon}) limit 1").fetchall()
    return r[0] if r else None


def gather(lat, lon, pin, weeks_back=26):
    since = (dt.date.today() - dt.timedelta(weeks=weeks_back)).isoformat()
    comp_since = (dt.date.today() - dt.timedelta(days=730)).strftime("%Y%m")
    signals = []
    signals += permits(lat, lon, since)
    # One street-work line per (address, applicant): a new building files seven tap and sewer
    # permits in a week, and seven lines would bury the one sidewalk closure that matters.
    grouped = {}
    for s in street_work(lat, lon, since):
        g = grouped.setdefault((s["address"], s["who"]), dict(s, n_permits=0, kinds=[]))
        g["n_permits"] += 1
        g["kinds"].append(s["what"].split(".")[0].split(":")[0])
        g["filed_date"] = min(g["filed_date"], s["filed_date"]) if g["filed_date"] and s["filed_date"] else g["filed_date"] or s["filed_date"]
        g["end_date"] = max(g["end_date"] or "", s["end_date"] or "") or None
    for g in grouped.values():
        kinds = sorted(set(g.pop("kinds")))
        if g["n_permits"] > 1:
            g["what"] = f"{g['n_permits']} permits ({', '.join(kinds)})" + (f" for {g['who']}" if g["who"] else "") + f", {g['filed_date']} to {g['end_date']}"
        signals.append(g)
    signals += liquor(lat, lon, since)
    vc, hist = value_change(pin) if pin else (None, [])
    if vc:
        signals.append(vc)
    signals += comp_sales(lat, lon, comp_since)
    signals.sort(key=lambda s: (s["kind"] != "value_change", s["distance_ft"], s.get("filed_date") or ""))
    return dict(generated_at=dt.datetime.now().isoformat(timespec="seconds"), lat=lat, lon=lon, pin=pin,
                radius_ft=RADIUS_FT, comp_radius_ft=COMP_RADIUS_FT, since=since, signals=signals, value_history=hist)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--lat", type=float, required=True)
    ap.add_argument("--lon", type=float, required=True)
    ap.add_argument("--pin")
    ap.add_argument("--weeks", type=int, default=26)
    a = ap.parse_args()
    pin = a.pin
    if not pin:
        found = pin_for(a.lat, a.lon)
        pin = found[0] if found else None
        print("pin", found, file=sys.stderr)
    print(json.dumps(gather(a.lat, a.lon, pin, a.weeks), indent=1, default=str))
