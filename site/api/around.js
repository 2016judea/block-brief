// GET /api/around?address=… -> the free slice: what the city filed within 500 ft of any
// Minneapolis address, this half-year, read live. No register, no history, no comps:
// those are the paid Monday briefing. Same layers and same rules as pipeline/signals.py.
const MPLS = "https://services.arcgis.com/afSMGVsC7QlRK1kZ/arcgis/rest/services";
const HENN = "https://gis.hennepin.us/arcgis/rest/services/HennepinData/LAND_PROPERTY/MapServer/1/query";
const R = 500;
const FT_PER_DEG = 20902231 * Math.PI / 180;

const dist = (a, b, c, d) => Math.hypot((d - b) * Math.cos((a + c) / 2 * Math.PI / 180), c - a) * FT_PER_DEG;
const env = (lat, lon) => { const dl = R / FT_PER_DEG, dn = dl / Math.cos(lat * Math.PI / 180); return JSON.stringify({ xmin: lon - dn, ymin: lat - dl, xmax: lon + dn, ymax: lat + dl }); };
const day = (ms) => (ms ? new Date(ms).toISOString().slice(0, 10) : null);
const company = (n) => !!n && /\b(INC|LLC|CO|CORP|CONSTRUCTION|BUILDERS|HOMES|ENERGY|CABLE|COMMUNICATIONS|SEWER|WATER|UNDERGROUND|ELECTRIC|WIRELESS|MIDWEST)\b/i.test(n);

async function arc(url, where, lat, lon, outFields) {
  const q = new URLSearchParams({ where, geometry: env(lat, lon), geometryType: "esriGeometryEnvelope", inSR: "4326", spatialRel: "esriSpatialRelIntersects", outFields, returnGeometry: "false", f: "json", resultRecordCount: "2000" });
  const j = await (await fetch(`${url}?${q}`)).json();
  if (j.error) throw new Error(JSON.stringify(j.error));
  return (j.features || []).map((f) => f.attributes);
}

function cleanComment(s) {
  s = (s || "").trim();
  if (/^source information is not available/i.test(s)) return "";
  for (const m of ["certificate of occupancy", "const type", "CONST TYPE", "Building Code", "Construction Documents", "(JJL)", "-ACW", "(DMH", "special inspec"]) { const i = s.indexOf(m); if (i > 0) s = s.slice(0, i); }
  return s.replace(/\s+/g, " ").replace(/^[\s.-]+|[\s.-]+$/g, "");
}

module.exports = async (req, res) => {
  const address = String(req.query.address || "").trim().slice(0, 160);
  if (!address) return res.status(400).json({ error: "address required" });
  try {
    const g = await (await fetch(`https://geocoding.geo.census.gov/geocoder/locations/onelineaddress?benchmark=Public_AR_Current&format=json&address=${encodeURIComponent(address.includes(",") ? address : address + ", Minneapolis, MN")}`)).json();
    const m = g.result?.addressMatches?.[0];
    if (!m) return res.status(404).json({ error: "We could not place that address. Try the number and street, e.g. 3040 Hennepin Ave." });
    const lat = m.coordinates.y, lon = m.coordinates.x;
    const since = new Date(Date.now() - 26 * 7 * 86400e3).toISOString().slice(0, 10);
    const [pq, permits, row, onsale, offsale] = await Promise.all([
      (async () => { const q = new URLSearchParams({ geometry: `${lon},${lat}`, geometryType: "esriGeometryPoint", inSR: "4326", spatialRel: "esriSpatialRelIntersects", outFields: "PID,HOUSE_NO,STREET_NM,MUNIC_NM,MKT_VAL_TOT,TAX_TOT,OWNER_NM,PR_TYP_NM1,SALE_DATE,SALE_PRICE", returnGeometry: "false", f: "json" }); return (await (await fetch(`${HENN}?${q}`)).json()).features?.[0]?.attributes || null; })(),
      arc(`${MPLS}/CCS_Permits/FeatureServer/0/query`, `issueDate >= date '${since}'`, lat, lon, "Display,Latitude,Longitude,permitType,occupancyType,workType,comments,issueDate,applicantName,totalFees,status"),
      arc(`${MPLS}/PWROW_Admin_Utility_Sidewalk_Permits_AGO_en_us_readonly/FeatureServer/0/query`, `Processed_Date >= date '${since}'`, lat, lon, "Display,Processed_Date,Expiration_Date,Permit_Type,Permit_Detail,Comments,Applicant_Name,Latitude,Longitude,Status__Permit_"),
      arc(`${MPLS}/On_Sale_Liquor/FeatureServer/0/query`, "1=1", lat, lon, "licenseName,licenseType,licenseStatus,issueDate,address,lat,long,endorsements"),
      arc(`${MPLS}/Off_Sale_Liquor/FeatureServer/0/query`, "1=1", lat, lon, "licenseName,licenseType,licenseStatus,issueDate,address,lat,long,endorsements"),
    ]);
    const out = [];
    const seen = new Set();
    for (const r of permits) {
      const d = dist(lat, lon, r.Latitude, r.Longitude); if (d > R) continue;
      const what = cleanComment(r.comments); const k = r.Display + what.slice(0, 80); if (seen.has(k)) continue; seen.add(k);
      const base = { filed_date: day(r.issueDate), address: r.Display, distance_ft: Math.round(d), what, who: company(r.applicantName) ? r.applicantName : null, status: r.status };
      if (r.permitType === "Wrecking") out.push({ kind: "demolition", ...base });
      else if (r.workType === "New" && ["MFD", "Comm", "Mixed", "TH", "3to4"].includes(r.occupancyType)) out.push({ kind: "big_build", ...base, size: (what.match(/(\d{1,4})[\s-]*unit/i) || [])[1] || null });
      else if (r.permitType === "Commercial" && ["Comm", "Mixed"].includes(r.occupancyType) && (r.totalFees || 0) >= 500) out.push({ kind: "tenant_work", ...base });
    }
    const words = { SidwlkConB: "sidewalk closed for work", Utility: "utility line work", Water: "water tap", Sewer: "sewer work", Excavation: "street dug up" };
    for (const r of row) {
      const d = dist(lat, lon, r.Latitude, r.Longitude); if (d > R) continue;
      let what = words[r.Permit_Type] || r.Permit_Type; if (r.Permit_Detail && !["N", "Y"].includes(r.Permit_Detail)) what += `: ${r.Permit_Detail}`; if (r.Comments) what += ". " + r.Comments.replace(/\s+/g, " ").trim().slice(0, 140);
      out.push({ kind: "street_work", filed_date: day(r.Processed_Date), end_date: day(r.Expiration_Date), address: r.Display, distance_ft: Math.round(d), what, who: company(r.Applicant_Name) ? r.Applicant_Name : null, status: r.Status__Permit_ });
    }
    for (const [rows, sale] of [[onsale, "on-sale"], [offsale, "off-sale"]]) for (const r of rows) {
      const d = dist(lat, lon, r.lat, r.long); if (d > R) continue;
      const issued = day(r.issueDate);
      let kind; if (["Inactive", "Expired", "Revoked"].includes(r.licenseStatus)) kind = "licence_change"; else if (issued && issued >= since) kind = "new_competitor"; else continue;
      out.push({ kind, filed_date: issued, address: r.address, distance_ft: Math.round(d), what: `${r.licenseName}: ${sale} ${r.licenseType.replace("BL", "").toLowerCase()} licence, ${r.licenseStatus.toLowerCase()}`, who: r.licenseName, status: r.licenseStatus });
    }
    if (pq) out.unshift({ kind: "value_change", distance_ft: 0, address: `${pq.HOUSE_NO} ${String(pq.STREET_NM).trim()}`, what: `county value: $${Number(pq.MKT_VAL_TOT).toLocaleString("en-US")}; taxes $${Number(pq.TAX_TOT).toLocaleString("en-US")}`, total_value: pq.MKT_VAL_TOT, taxes_payable: pq.TAX_TOT, landlord: String(pq.OWNER_NM).trim(), property_type: pq.PR_TYP_NM1, last_sale: pq.SALE_PRICE ? { date: pq.SALE_DATE, price: pq.SALE_PRICE } : null });
    out.sort((a, b) => (a.kind === "value_change" ? -1 : b.kind === "value_change" ? 1 : a.distance_ft - b.distance_ft));
    res.setHeader("Cache-Control", "public, max-age=3600");
    res.status(200).json({ address: m.matchedAddress, lat, lon, minneapolis: (pq?.MUNIC_NM || "").trim().toUpperCase() === "MINNEAPOLIS", radius_ft: R, since, signals: out });
  } catch (e) {
    console.error("[around]", e.message);
    res.status(502).json({ error: "The city's map servers did not answer. Try again in a minute." });
  }
};
