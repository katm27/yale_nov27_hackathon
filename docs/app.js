/* Climate Trends in South Sudan — static Leaflet app.
 * Data: data/variables.json + data/series/<id>.json (or a packed bundle), data/trends.json (Mann-Kendall / Sen's slope from
 * scripts/trend_stats.py), data/layers.json (raster + point layers), data/curated.json (what this app shows),
 * data/basemap_context.json (neighbouring countries, towns), data/context_timeline.json (sourced "what was happening" text).
 */
(() => {
  "use strict";

  // ---------- shared colour scale: 7 bins, red → white → green; no data = black hatching ----------
  const PAL7 = ["#b2182b", "#ef8a62", "#fddbc7", "#ffffff", "#d9f0d3", "#7fbf7b", "#1b7837"];
  const NODATA = "url(#nodata-hatch)";
  const CATEGORICAL = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300", "#6250d6", "#e34948", "#4a4a4a", "#0aa5b8"];
  const MONTH_NAMES = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
  const ORANGE = "#fc3c23";   // accent: slider cursor
  const MAIN = "#0B3D91";
  const SUDD_NAMES = ["Panyijiar", "Mayendit", "Leer", "Guit", "Fangak", "Ayod", "Canal/Pigi", "Duk", "Twic East", "Bor South", "Yirol East", "Awerial", "Rubkona", "Koch", "Nyirol", "Uror"];
  const GROUNDWATER_IDS = ["gracedm_gws_pctl", "gldas_gws_anom_cm", "grace_tws_cm", "g3p_gwsa_cm"];

  const state = {
    months: [], vars: [], varById: {}, allVars: {}, series: {}, colorBy: null,
    mode: "trend", agg: "month", t: 0, selected: null, gridOn: true,
    rasters: [], rasterByKey: {}, rasterLayers: {}, points: [], pointLayers: {}, bgOn: new Set(["water"]), chartVars: [],
    timer: null, charts: [], natCharts: [], view: "landing",
  };

  // ---------- helpers ----------
  const $ = (s) => document.querySelector(s);
  const css = (name) => getComputedStyle(document.documentElement).getPropertyValue(name).trim();
  const fetchJSON = (u) => fetch(u).then((r) => { if (!r.ok) throw new Error(u + " " + r.status); return r.json(); });
  const esc = (s) => String(s == null ? "" : s).replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
  function fmt(v, d = 3) {
    if (v == null || !isFinite(v)) return "–";
    const a = Math.abs(v);
    if (a >= 1e9) return (v / 1e9).toFixed(a >= 1e10 ? 1 : 2).replace(/\.?0+$/, "") + " billion";
    if (a >= 1e6) return (v / 1e6).toFixed(a >= 1e7 ? 0 : 1).replace(/\.0$/, "") + " million";
    if (a >= 1000) return Math.round(v).toLocaleString("en-US");
    if (a === 0) return "0";
    return (+v.toPrecision(d)).toString();
  }
  const signed = (v, d) => (v > 0 ? "+" : v < 0 ? "−" : "") + fmt(Math.abs(v), d);
  const usd = (v) => (v == null ? "–" : "US$" + fmt(v, 3));
  const usdShort = (v) => { const a = Math.abs(v); return a >= 1e9 ? `$${+(v / 1e9).toFixed(2)}B` : a >= 1e6 ? `$${+(v / 1e6).toFixed(0)}M` : a >= 1e3 ? `$${+(v / 1e3).toFixed(0)}k` : `$${v}`; };
  const monthLabel = (i) => { const [y, m] = state.months[i].split("-"); return `${MONTH_NAMES[+m - 1]} ${y}`; };
  const mean = (arr) => { let s = 0, n = 0; for (const v of arr) if (v != null && isFinite(v)) { s += v; n++; } return n ? s / n : null; };
  const yearOf = (i) => +state.months[i].slice(0, 4);
  const quantile = (sorted, q) => { if (!sorted.length) return null; const p = (sorted.length - 1) * q, lo = Math.floor(p), hi = Math.ceil(p); return sorted[lo] + (sorted[hi] - sorted[lo]) * (p - lo); };

  // ---------- time windows ----------
  function seasonOf(i) {
    const [y, m] = state.months[i].split("-").map(Number);
    if (m === 12 || m <= 2) {
      const Y = m === 12 ? y + 1 : y;
      const hasDec = state.months.includes(`${Y - 1}-12`), hasFeb = state.months.includes(`${Y}-02`);
      const lab = hasDec && hasFeb ? `Dec ${Y - 1}–Feb ${Y}` : hasFeb ? `Jan–Feb ${Y}` : `Dec ${Y - 1}`;
      return { key: `${Y}-djf`, label: `${lab} (dry and cool)` };
    }
    if (m <= 5) return { key: `${y}-mam`, label: `Mar–May ${y} (early rains)` };
    if (m <= 8) return { key: `${y}-jja`, label: `Jun–Aug ${y} (rainy)` };
    return { key: `${y}-son`, label: `Sep–Nov ${y} (late rains)` };
  }
  const windowKey = (i) => (state.agg === "month" ? state.months[i] : state.agg === "year" ? state.months[i].slice(0, 4) : seasonOf(i).key);
  const windowLabel = (i) => (state.agg === "month" ? monthLabel(i) : state.agg === "year" ? state.months[i].slice(0, 4) : seasonOf(i).label);
  function windowIdx(i) { const k = windowKey(i), out = []; for (let j = 0; j < state.months.length; j++) if (windowKey(j) === k) out.push(j); return out; }
  function baselineWindowIdx(i, baseYear) {
    if (state.agg === "year") return state.months.map((_, j) => j).filter((j) => yearOf(j) === baseYear);
    const shift = (baseYear - yearOf(i)) * 12;
    return windowIdx(i).map((j) => j + shift).filter((j) => j >= 0 && j < state.months.length);
  }

  // ---------- units ----------
  const isPctUnits = (v) => /%/.test(v.units || "");
  const isShareUnits = (v) => !isPctUnits(v) && /^(share|fraction)/i.test(v.units || "");
  const isStatic = (v) => v.temporal === "static";
  const isCategorical = (v) => /class code/i.test(v.units || "");
  const unitsShort = (v) => (isPctUnits(v) || isShareUnits(v) ? "%" : (v.units || "").replace(/\s*\(.*\)$/, ""));
  const slopeUnits = (v) => (isPctUnits(v) || isShareUnits(v) ? "percentage points per year" : `${unitsShort(v)} per year`);

  // ---------- trends (scripts/trend_stats.py) ----------
  const T_P = 0, T_Q = 1, T_SEN = 2, T_PCT = 3, T_N = 5, T_SIG = 6, T_TODATE = 11;
  const trendYear = () => Math.min(2025, Math.max(2020, yearOf(state.t)));
  const trendOf = (vid, cid) => (state.trends && state.trends[vid] && state.trends[vid][cid]) || null;
  const usesTrend = (v) => state.mode === "trend" && !isStatic(v) && !isCategorical(v);
  function baselineAbs(v, cid, tr) {
    if (tr && tr[T_SEN] && tr[T_PCT]) return Math.abs((100 * tr[T_SEN]) / tr[T_PCT]);
    const arr = (state.series[v.id] || {})[cid]; if (!arr) return null;
    const by = v.baseline_year || 2018;
    const b = mean(arr.filter((_, j) => yearOf(j) === by)); return b == null ? null : Math.abs(b);
  }
  /** Sen's slope in native units per year (percentage points for % and shares), 2018 → slider year. */
  function trendNative(v, cid, Y = trendYear()) {
    const tr = trendOf(v.id, cid); if (!tr) return null;
    let x;
    if (Y < 2025 && tr[T_TODATE]) {
      x = tr[T_TODATE][Y - 2020]; if (x == null) return null;
      if (tr[T_PCT] != null) { const b = baselineAbs(v, cid, tr); if (b == null) return null; x = (x / 100) * b; }
    } else x = tr[T_SEN];
    if (x == null || !isFinite(x)) return null;
    return isShareUnits(v) ? x * 100 : x;
  }

  /** Value used to colour county c at time i. */
  function valueAt(v, c, i, mode = state.mode) {
    if (mode === "trend" && usesTrend(v)) return trendNative(v, c);
    const s = state.series[v.id]; if (!s || !s[c]) return null;
    const arr = s[c], wvals = windowIdx(i).map((j) => arr[j]);
    const raw = mean(wvals); if (raw == null) return null;
    if (v.aggregate === "sum" && state.agg !== "month") return wvals.reduce((a, x) => a + (x != null && isFinite(x) ? x : 0), 0);
    return isShareUnits(v) ? raw * 100 : raw;
  }
  const centered = (v) => state.mode === "trend" && usesTrend(v);
  const isRatio = () => false;

  // ---------- 7-bin percentile scale per variable & mode ----------
  function binsFor(v) {
    const key = `${state.mode}|${state.agg}|${centered(v) ? "c" : "r"}`;
    v._bins = v._bins || {};
    if (v._bins[key]) return v._bins[key];
    const vals = [];
    const cids = Object.keys(state.series[v.id] || (state.trends || {})[v.id] || {});
    if (state.mode === "trend" && usesTrend(v)) {
      for (const c of Object.keys((state.trends || {})[v.id] || {})) for (let Y = 2020; Y <= 2025; Y++) { const x = trendNative(v, c, Y); if (x != null) vals.push(x); }
    } else {
      const step = isStatic(v) ? state.months.length : Math.max(1, Math.floor(state.months.length / 48));
      for (const c of cids) for (let i = 0; i < state.months.length; i += step) { const x = valueAt(v, c, i); if (x != null && isFinite(x)) vals.push(isRatio(v) ? Math.log2(Math.max(1e-6, x)) : x); }
    }
    let edges;
    if (centered(v)) {
      const a = vals.map(Math.abs).sort((p, q) => p - q);
      const t1 = quantile(a, 1 / 7) || 0, t2 = Math.max(t1, quantile(a, 3 / 7) || 0), t3 = Math.max(t2, quantile(a, 5 / 7) || 0);
      edges = [-t3, -t2, -t1, t1, t2, t3];
    } else {
      const s = vals.slice().sort((p, q) => p - q);
      edges = [1, 2, 3, 4, 5, 6].map((k) => quantile(s, k / 7));
    }
    return (v._bins[key] = { edges, centered: centered(v), n: vals.length });
  }
  function binOf(v, x) {
    if (x == null || !isFinite(x)) return -1;
    const b = binsFor(v), e = b.edges;
    const z = isRatio(v) ? Math.log2(Math.max(1e-6, x)) : x;
    if (b.centered) {
      if (Math.abs(z) <= e[3]) return 3;
      if (z > 0) return z <= e[4] ? 4 : z <= e[5] ? 5 : 6;
      return z >= e[1] ? 2 : z >= e[0] ? 1 : 0;
    }
    let k = 0; while (k < 6 && z > e[k]) k++; return k;
  }
  const colorOf = (v, x) => { const k = binOf(v, x); return k < 0 ? null : PAL7[k]; };

  // ---------- map & basemap ----------
  // Map limited to South Sudan and its neighbours: fewer tiles to load, nothing to get lost in.
  const MAX_BOUNDS = L.latLngBounds([[-1.5, 17.5], [16.5, 42.5]]);
  const map = L.map("map", { zoomControl: true, minZoom: 5, maxZoom: 12, zoomSnap: 0.25, maxBounds: MAX_BOUNDS, maxBoundsViscosity: 1 });
  const baseLayers = {
    "Terrain": L.tileLayer("https://server.arcgisonline.com/ArcGIS/rest/services/World_Terrain_Base/MapServer/tile/{z}/{y}/{x}", { attribution: "Terrain: Esri, USGS, NOAA · borders: Natural Earth", maxZoom: 13 }),
    "Satellite": L.tileLayer("https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}", { attribution: "Esri, Maxar, Earthstar Geographics" }),
    "OpenStreetMap (detailed)": L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", { attribution: "© OpenStreetMap contributors", maxZoom: 19 }),
  };
  baseLayers.Terrain.options.bounds = MAX_BOUNDS;
  baseLayers.Terrain.addTo(map);
  map.createPane("mask").style.zIndex = 300;        // greys out terrain outside South Sudan
  map.createPane("bg").style.zIndex = 330;          // background layers (soil type, cattle)
  map.createPane("rasters").style.zIndex = 380;   // under the county outlines, so significance outlines stay visible
  map.createPane("hatch").style.zIndex = 410; map.getPane("hatch").style.pointerEvents = "none";
  map.createPane("counties").style.zIndex = 400;
  map.createPane("water").style.zIndex = 430; map.getPane("water").style.pointerEvents = "none";
  map.createPane("points").style.zIndex = 600;
  map.createPane("flows").style.zIndex = 620;
  map.createPane("labels").style.zIndex = 640; map.getPane("labels").style.pointerEvents = "none";
  let countyLayer;

  function drawBasemapContext(ctx) {
    // mask = world minus South Sudan, so terrain shading shows only inside South Sudan
    const outer = [[-90, -180], [-90, 180], [90, 180], [90, -180]];
    const holes = [];
    const g = ctx.ssd.geometry, polys = g.type === "Polygon" ? [g.coordinates] : g.coordinates;
    for (const p of polys) holes.push(p[0].map(([x, y]) => [y, x]));
    L.polygon([outer, ...holes], { pane: "mask", stroke: false, fillColor: "#cfd4dc", fillOpacity: 0.82, interactive: false }).addTo(map);
    // rivers and lakes (Natural Earth): drawn over the neighbour tint so the Nile system reads across borders
    if (ctx.lakes) L.geoJSON(ctx.lakes, { pane: "mask", interactive: false, style: { color: "#6f9bd1", weight: 0.8, fillColor: "#a9c8ec", fillOpacity: 1 } }).addTo(map);
    if (ctx.rivers) L.geoJSON(ctx.rivers, { pane: "mask", interactive: false, style: { color: "#6f9bd1", weight: 1.3, opacity: 0.95 } }).addTo(map);
    const WLAB = { "Lake Victoria": [-1.0, 33.0], "Lake Albert": [1.7, 30.95], "Lake Turkana": [3.6, 36.05], "Lake Tana": [12.0, 37.3], "White Nile": [13.2, 32.55], "Blue Nile": [12.2, 34.6] };
    for (const [n, ll] of Object.entries(WLAB)) L.marker(ll, { pane: "labels", interactive: false, icon: L.divIcon({ className: "water-label", html: n, iconSize: null }) }).addTo(map);
    L.geoJSON(ctx.neighbors, { pane: "mask", interactive: false, style: { color: "#7d7b74", weight: 1.2, fill: false } }).addTo(map);
    L.geoJSON(ctx.ssd, { pane: "labels", interactive: false, style: { color: MAIN, weight: 1.6, opacity: 0.85, dashArray: "6 4", fill: false } }).addTo(map);
    const NLAB = { "Sudan": [11.4, 27.6], "Ethiopia": [7.9, 36.4], "Kenya": [3.6, 36.6], "Uganda": [2.6, 32.4], "DR Congo": [3.4, 27.4], "Central African Rep.": [7.3, 22.6] };
    for (const [n, ll] of Object.entries(NLAB)) L.marker(ll, { pane: "labels", interactive: false, icon: L.divIcon({ className: "country-label", html: n.toUpperCase(), iconSize: null }) }).addTo(map);
    for (const [lat, lon, name, rank, capital] of ctx.towns) {
      L.marker([lat, lon], { pane: "labels", interactive: false, icon: L.divIcon({ className: `town-label r${rank}${capital ? " cap" : ""}`, html: `<i></i><span>${esc(name)}</span>`, iconSize: null }) }).addTo(map);
    }
  }
  const townsVisible = () => { const z = map.getZoom(); document.body.dataset.zoom = z >= 7 ? "hi" : "lo"; };
  map.on("zoomend", townsVisible);

  // ---------- county styling ----------
  function styleCounty(f) {
    const v = state.varById[state.colorBy];
    const cid = f.properties.district_id, selected = state.selected === cid;
    const st = { color: selected ? "#0b0b0b" : "#77756e", weight: selected ? 3 : 0.6, pane: "counties", dashArray: null, fillOpacity: 0 };
    if (!v) return st;
    const gridShown = !!activeRaster(v);
    const tr = trendOf(v.id, cid);
    if (!isStatic(v) && !isCategorical(v) && tr && tr[T_SIG] && !selected) { st.color = "#111111"; st.weight = 2.6; }
    if (gridShown) return st;                                     // the grid carries the colour; counties are outlines
    const x = valueAt(v, cid, state.t);
    const col = colorOf(v, x);
    const flows = state.flowOn ? 0.62 : 0.82;
    if (col == null) return { ...st, fillColor: NODATA, fillOpacity: 0.78 };
    return { ...st, fillColor: col, fillOpacity: flows };
  }
  function refreshCounties() {
    if (!countyLayer) return;
    countyLayer.setStyle(styleCounty);
    countyLayer.eachLayer((l) => {
      const tr = trendOf(state.colorBy, l.feature.properties.district_id);
      if ((tr && tr[T_SIG]) || state.selected === l.feature.properties.district_id) l.bringToFront();
    });
  }

  // ---------- value text ----------
  function describe(v, x, cid) {
    if (x == null) {
      if (state.mode === "trend" && usesTrend(v)) return trendOf(v.id, cid) ? "too little data for a trend" : "no data";
      return "no data";
    }
    if (state.mode === "trend" && usesTrend(v)) {
      const word = Math.abs(binOf(v, x)) === 3 && binOf(v, x) === 3 ? " (little or no change)" : "";
      return `${signed(x, 2)} ${slopeUnits(v)}${word}`;
    }
    if (isCategorical(v)) return soilName(x);
    return `${fmt(x)} ${unitsShort(v)}`;
  }
  const SOIL = { 0: "Acrisols (weathered, acidic)", 6: "Cambisols (young soils)", 10: "Ferralsols (deeply weathered)", 12: "Gleysols (waterlogged)", 18: "Luvisols (clay-enriched subsoil)", 29: "Vertisols (cracking clay, floods easily)" };
  const soilName = (x) => SOIL[Math.round(x)] || `soil class ${Math.round(x)}`;

  // ---------- hover tooltip: selected measure + stacked mini-charts on ONE shared year axis ----------
  const SPARKS = [
    { id: "et_ind_total", label: "People displaced or returning (IOM)", color: MAIN, units: "people" },
    { id: "fts_us_gov_funding_month_usd", label: "US humanitarian funding, national", color: MAIN, units: "US$", money: true },
    { id: "surface_water_pct", label: "Surface water (% of county)", color: MAIN, units: "%" },
    { id: "spei3", label: "Drought index (SPEI)", color: MAIN, units: "", zero: true },
  ];
  function sparkPanel(cid) {
    const v = state.varById[state.colorBy];
    const rows = [];
    if (v && !isStatic(v) && !isCategorical(v) && state.series[v.id] && state.series[v.id][cid]) rows.push({ id: v.id, label: v.label, color: "#1d1c1a", units: unitsShort(v), arr: state.series[v.id][cid].map((x) => (x != null && isShareUnits(v) ? x * 100 : x)), main: true });
    for (const sp of SPARKS) {
      if (v && sp.id === v.id) continue;
      const s = state.series[sp.id]; if (!s) continue;
      const arr = s[cid] || (sp.money ? s[Object.keys(s).find((k) => s[k].some((x) => x != null))] : null);
      if (arr && arr.some((x) => x != null)) rows.push({ ...sp, arr });
    }
    if (!rows.length) return "";
    const W = 300, L0 = 4, R0 = 4, RH = 40, top = 2, n = state.months.length;
    const H = top + rows.length * RH + 16;
    const X = (i) => L0 + (i / (n - 1)) * (W - L0 - R0);
    let svg = "";
    for (let i = 0; i < n; i += 12) svg += `<line x1="${X(i)}" x2="${X(i)}" y1="${top}" y2="${H - 14}" class="sp-grid"/><text x="${X(Math.min(n - 1, i + 6))}" y="${H - 3}" class="sp-year">${state.months[i].slice(0, 4)}</text>`;
    rows.forEach((r, k) => {
      const y0 = top + k * RH, lh = 13, ph = RH - lh - 6;
      const ok = r.arr.filter((x) => x != null && isFinite(x));
      let mn = Math.min(...ok), mx = Math.max(...ok); if (r.zero) { mn = Math.min(mn, 0); mx = Math.max(mx, 0); } if (mx === mn) { mx += 1; mn -= 1; }
      const Y = (y) => y0 + lh + ph - ((y - mn) / (mx - mn)) * ph;
      let d = "", pen = false;
      r.arr.forEach((y, i) => { if (y == null || !isFinite(y)) { pen = false; return; } d += `${pen ? "L" : "M"}${X(i).toFixed(1)},${Y(y).toFixed(1)}`; pen = true; });
      const cur = r.arr[state.t];
      const val = cur == null ? "no data" : r.money ? usd(cur) : `${fmt(cur, 3)}${r.units ? " " + r.units : ""}`;
      svg += `<text x="${L0}" y="${y0 + 10}" class="sp-lab${r.main ? " main" : ""}">${esc(r.label.length > 46 ? r.label.slice(0, 45) + "…" : r.label)}</text><text x="${W - R0}" y="${y0 + 10}" class="sp-val">${esc(val)}</text>`;
      if (r.zero && mn < 0 && mx > 0) svg += `<line x1="${L0}" x2="${W - R0}" y1="${Y(0)}" y2="${Y(0)}" class="sp-zero"/>`;
      svg += `<path d="${d}" fill="none" stroke="${r.color}" stroke-width="${r.main ? 1.9 : 1.5}"/>`;
      if (k < rows.length - 1) svg += `<line x1="${L0}" x2="${W - R0}" y1="${y0 + RH - 1}" y2="${y0 + RH - 1}" class="sp-sep"/>`;
    });
    svg += `<line x1="${X(state.t)}" x2="${X(state.t)}" y1="${top}" y2="${H - 14}" stroke="${ORANGE}" stroke-width="1.6"/>`;
    return `<svg class="sparks" width="${W}" height="${H}" viewBox="0 0 ${W} ${H}" role="img" aria-label="Monthly history 2018–2025">${svg}</svg>`;
  }
  function tooltipHtml(p) {
    const v = state.varById[state.colorBy];
    let line = "";
    if (v) {
      const x = valueAt(v, p.district_id, state.t);
      const lab = state.mode === "trend" && usesTrend(v) ? `Trend 2018→${trendYear()} (Sen's slope)` : windowLabel(state.t);
      line = `<div class="tt-var"><span class="muted">${esc(v.label)}</span><br>${lab}: <b>${describe(v, x, p.district_id)}</b></div>`;
    }
    return `<div class="tt"><div class="tt-h"><b>${esc(p.name)}</b> <span class="muted">· ${esc(p.admin1)}</span></div>${line}${sparkPanel(p.district_id)}</div>`;
  }

  const hoverEl = () => $("#hovercard") || (() => { const d = document.createElement("div"); d.id = "hovercard"; d.setAttribute("role", "tooltip"); document.body.appendChild(d); return d; })();
  function showHover(p, ev) {
    const el = hoverEl();
    if (state.hoverCid !== p.district_id || state._hoverT !== state.t || state._hoverV !== state.colorBy || state._hoverM !== state.mode) {
      el.innerHTML = tooltipHtml(p); state.hoverCid = p.district_id; state._hoverT = state.t; state._hoverV = state.colorBy; state._hoverM = state.mode;
    }
    el.style.display = "block";
    const w = el.offsetWidth, h = el.offsetHeight, pad = 16;
    let x = ev.clientX + pad, y = ev.clientY - h / 2;
    if (x + w > innerWidth - 8) x = ev.clientX - w - pad;
    y = Math.max(8, Math.min(innerHeight - h - 8, y));
    el.style.left = `${x}px`; el.style.top = `${y}px`;
  }
  function hideHover() { const el = $("#hovercard"); if (el) el.style.display = "none"; state.hoverCid = null; }

  // ---------- legend ----------
  function binLabels(v) {
    const b = binsFor(v), e = b.edges, f = (z) => (isRatio(v) ? `${fmt(2 ** z, 2)}×` : signedOr(z));
    const signedOr = (z) => (b.centered ? signed(z, 2) : fmt(z, 2));
    const rng = (a, c) => (a === c ? null : `${f(a)} to ${f(c)}`);
    if (b.centered) return [`below ${f(e[0])}`, rng(e[0], e[1]), rng(e[1], e[2]), e[3] === 0 ? "no change" : `${f(e[2])} to ${f(e[3])}`, rng(e[3], e[4]), rng(e[4], e[5]), `above ${f(e[5])}`];
    return [`${f(e[0])} or less`, ...[0, 1, 2, 3, 4].map((k) => rng(e[k], e[k + 1])), `above ${f(e[5])}`];
  }
  function rasterBinLabels(r) {
    let e = r.bins;
    if (!e || e.length !== 8) { const lo = +r.vmin, hi = +r.vmax; e = [0, 1, 2, 3, 4, 5, 6, 7].map((k) => lo + (k * (hi - lo)) / 7); }
    if (r.bin_labels) return [r.bin_labels[0], null, null, null, r.bin_labels[1], null, r.bin_labels[2]];
    return [0, 1, 2, 3, 4, 5, 6].map((k) => `${fmt(e[k], 2)} to ${fmt(e[k + 1], 2)}`);
  }
  const FLOW_W = (n) => Math.max(1.4, Math.min(9, 1.4 + 7.6 * Math.sqrt(n / 20000)));   // arrow width in px, fixed scale
  const caveatHtml = (v) => {
    const cov = isStatic(v) ? "single snapshot" : `${(v.temporal || "monthly").replace(/\s*\(.*\)/, "")}, ${monthLabelYM(v.first_period)} to ${monthLabelYM(v.last_period)}`;
    const note = (v.caution || "").replace(/\s*Use it for patterns, not totals\.?/g, "").trim();
    return `<details class="lg-more"><summary>Caveats and source</summary>${note ? `<p>${esc(note)}</p>` : ""}<p><b>Spatial resolution:</b> ${esc(v.native_resolution || "county")}</p><p><b>Temporal resolution:</b> ${esc(cov)}</p><p><b>Source:</b> ${esc(v.source || "–")}</p></details>`;
  };
  const monthLabelYM = (ym) => { if (!ym) return "–"; const [y, m] = String(ym).split("-"); return `${MONTH_NAMES[+m - 1] || ""} ${y}`.trim(); };
  function renderLegend() {
    const el = $("#legend");
    const v = state.varById[state.colorBy];
    let html = "";
    if (v) {
      const r = activeRaster(v), trendOn = state.mode === "trend" && usesTrend(v);
      const what = trendOn ? `Trend, 2018 to ${trendYear()}, in ${slopeUnits(v)}` : isCategorical(v) ? "Main soil type" : `${windowLabel(state.t)}, in ${unitsShort(v) || "index units"}`;
      html += `<div class="lg-title">${esc(v.label)}</div><div class="lg-sub">${esc(what)}</div>`;
      if (isCategorical(v)) {
        html += `<div class="lg-bins">${Object.keys(SOIL).map((k, i) => `<div><i style="background:${CATEGORICAL[i]}"></i>${SOIL[k]}</div>`).join("")}</div>`;
      } else {
        const labs = r ? rasterBinLabels(r) : binLabels(v);
        const rows = PAL7.map((c, k) => ({ c, lab: labs[k] })).reverse().filter((x) => x.lab);
        html += `<div class="lg-bins">${rows.map((x) => `<div><i style="background:${x.c}"></i>${esc(x.lab)}</div>`).join("")}<div><i class="nd"></i>No data</div></div>`;
        if (!isStatic(v) && state.trends && state.trends[v.id]) {
          const nSig = Object.values(state.trends[v.id]).filter((t) => t[T_SIG]).length;
          html += `<div class="lg-note"><span class="sig-swatch"></span> <b>Outlined counties (${nSig})</b> have a 2018–2025 trend that is found to be statistically significant.</div>`;
        }
        if (GROUNDWATER_IDS.includes(v.id)) html += `<div class="lg-note"><span class="hatch-swatch"></span> <b>Hatched counties</b> are in the Sudd wetland, where readings are less reliable because surface flood water can be mistaken for groundwater.</div>`;
      }
      html += caveatHtml(v);
    }
    if (state.flowOn) {
      const G = state.curated.flow_groups;
      const shown = state.flowGroup === "all" ? Object.keys(G) : [state.flowGroup];
      const widths = [1000, 5000, 20000].map((n) => `<div class="fw"><i style="height:${FLOW_W(n)}px"></i>${n.toLocaleString("en-US")} people</div>`).join("");
      html += `<div class="lg-flows"><div class="lg-title">Migration arrows (IOM)</div>${shown.map((k) => `<div><i class="arrow" style="background:${G[k].color}"></i>${esc(G[k].label)}</div>`).join("")}<div class="lg-fw">${widths}</div></div>`;
    }
    if (state.bgOn.has("water")) {
      const wl = state.rasters.filter((x) => x.base_layer).flatMap((x) => x.legend || []).filter((x, i, a) => a.findIndex((y) => y[1] === x[1]) === i);
      if (wl.length) html += `<div class="lg-flows"><div class="lg-title">Water (NASA MODIS, monthly)</div>${wl.map(([c, l]) => `<div><i style="background:${c}"></i>${esc(l)}</div>`).join("")}</div>`;
    }
    html += [...state.bgOn].filter((k) => k !== "water").map((k) => bgLegend(k)).join("");
    el.innerHTML = html ? `<button class="lg-min" aria-expanded="${!state.legendMin}" title="${state.legendMin ? "Show key" : "Hide key"}">${state.legendMin ? "Key ▸" : "–"}</button><div class="lg-body">${html}</div>` : "";
    el.classList.toggle("min", !!state.legendMin);
    const mb = el.querySelector(".lg-min"); if (mb) mb.onclick = () => { state.legendMin = !state.legendMin; renderLegend(); };
    el.hidden = !html;
    updateSuddHatch();
  }
  let suddHatch = null;
  function updateSuddHatch() {
    const on = !!state.colorBy && GROUNDWATER_IDS.includes(state.colorBy);
    if (on && !suddHatch && state.countiesGJ) {
      const feats = state.countiesGJ.features.filter((f) => SUDD_NAMES.includes(f.properties.name));
      suddHatch = L.geoJSON({ type: "FeatureCollection", features: feats }, { pane: "hatch", interactive: false, style: { color: "#111", weight: 1, fillColor: "url(#sudd-hatch)", fillOpacity: 1 } }).addTo(map);
    } else if (!on && suddHatch) { map.removeLayer(suddHatch); suddHatch = null; }
  }
  function bgLegend(k) {
    if (k === "soil_type") return `<div class="lg-flows"><div class="lg-title">Background: main soil type</div><div class="lg-bins">${Object.keys(SOIL).map((c, i) => `<div><i style="background:${CATEGORICAL[i]}"></i>${SOIL[c]}</div>`).join("")}</div></div>`;
    const b = state.curated.background.find((x) => x.key === k); const r = b && b.rasters && state.rasterByKey[b.rasters[0]];
    if (!r) return "";
    const labs = rasterBinLabels(r);
    return `<div class="lg-flows"><div class="lg-title">Background: ${esc(b.label)}</div><div class="lg-mini">${PAL7.map((c) => `<i style="background:${c}"></i>`).join("")}</div><div class="lg-ticks"><span>${esc(labs[0].split(" to ")[0])}</span><span>${esc(r.units || "")}</span><span>${esc(labs[6].split(" to ").pop())}</span></div></div>`;
  }

  // ---------- sidebar: measures ----------
  const plainOf = (v) => (v.plain || v.notes || "").split(/(?<=\.)\s/).slice(0, 2).join(" ");
  // ---------- stories: colour-coded groups of measures that tell one story (data/stories.json) ----------
  const storyVars = (st) => [...new Set((st.steps || []).map((x) => x.var).filter((id) => state.varById[id]))];
  function renderStories() {
    const el = $("#stories"); if (!el) return;
    const S = state.stories || [];
    if (!S.length) { el.innerHTML = ""; return; }
    const act = S.find((x) => x.key === state.story);
    el.innerHTML = `<div class="story-chips">${S.map((x) => `<button class="story-chip${x.key === state.story ? " on" : ""}" data-k="${esc(x.key)}" style="--c:${esc(x.color)}">${esc(x.title)}</button>`).join("")}${act ? `<button class="story-chip clear" data-k="">Show all measures</button>` : ""}</div>` +
      (act ? `<div class="story-box" style="--c:${esc(act.color)}"><p>${act.summary}</p><ol>${act.steps.map((st, k) => `<li><button class="linkbtn story-step" data-i="${k}">${esc(st.say)}</button></li>`).join("")}</ol></div>` : "");
    el.querySelectorAll(".story-chip").forEach((b) => (b.onclick = () => { state.story = b.dataset.k || null; renderStories(); renderVarList(); }));
    el.querySelectorAll(".story-step").forEach((b) => (b.onclick = () => applyView(act.steps[+b.dataset.i])));
  }
  // ---------- your own story: drag measures into the circle, write a note per step, click through ----------
  const MS_KEY = "ssd-my-story-v1";
  const loadMyStory = () => { try { return JSON.parse(localStorage.getItem(MS_KEY) || "[]"); } catch (e) { return []; } };
  const saveMyStory = () => { try { localStorage.setItem(MS_KEY, JSON.stringify(state.myStory)); } catch (e) { /* storage blocked */ } };
  function addStoryStep(id) {
    if (!state.varById[id]) return;
    state.myStory.push({ var: id, month: state.months[state.t], county: state.selected || null, mode: state.mode, agg: state.agg, text: "" });
    saveMyStory(); renderMyStory();
    const tas = document.querySelectorAll("#my-story textarea"); if (tas.length) tas[tas.length - 1].focus();
  }
  function renderMyStory() {
    const el = $("#my-story"); if (!el) return;
    const steps = state.myStory;
    const where = (st) => (st.county ? countyProps(st.county).name : "all counties");
    el.innerHTML = `<h3 class="ms-h">Create your own story</h3>
      <p class="hint">If you found those stories interesting, then please create your own! If you drag and drop variables you found interesting, along with the time period and districts in which the trends occurred, you can construct a sequence of events that you can revisit and click through.</p>
      <div class="ms-drop" tabindex="0" role="button" aria-label="Add the measure on the map as a story step"><span class="ms-plus">+</span><span>Drop a measure here<br><small>it keeps the slider's date and the county you clicked</small></span></div>
      ${steps.length ? `<ol class="ms-steps">${steps.map((st, k) => `<li class="${state.myStep === k ? "on" : ""}">
        <button class="ms-go" data-i="${k}"><b>${esc((state.varById[st.var] || {}).label || st.var)}</b> · ${esc(monthLabel(Math.max(0, state.months.indexOf(st.month))))} · ${esc(where(st))}</button>
        <textarea data-i="${k}" rows="2" placeholder="What happens at this step?">${esc(st.text)}</textarea>
        <div class="ms-act"><button class="linkbtn ms-upd" data-i="${k}">Use the current date and county</button><button class="linkbtn ms-del" data-i="${k}">Remove</button></div></li>`).join("")}</ol>
        <div class="ms-nav"><button class="pill ms-prev">‹ Previous</button><button class="pill ms-next">Next ›</button><button class="linkbtn ms-clear">Clear story</button></div>` : ""}`;
    const drop = el.querySelector(".ms-drop");
    drop.ondragover = (e) => { e.preventDefault(); e.dataTransfer.dropEffect = "copy"; drop.classList.add("over"); };
    drop.ondragleave = () => drop.classList.remove("over");
    drop.ondrop = (e) => { e.preventDefault(); drop.classList.remove("over"); document.body.classList.remove("dragging"); addStoryStep(e.dataTransfer.getData("text/plain")); };
    const addCurrent = () => (state.colorBy ? addStoryStep(state.colorBy) : toast("Tick a measure first, or drag one here."));
    drop.onclick = addCurrent; drop.onkeydown = (e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); addCurrent(); } };
    const go = (k) => { if (k < 0 || k >= steps.length) return; state.myStep = k; const st = steps[k]; applyView({ var: st.var, month: st.month, mode: st.mode, agg: st.agg, county: st.county || undefined }); renderMyStory(); };
    el.querySelectorAll(".ms-go").forEach((b) => (b.onclick = () => go(+b.dataset.i)));
    el.querySelectorAll("textarea").forEach((t) => (t.oninput = () => { steps[+t.dataset.i].text = t.value; saveMyStory(); }));
    el.querySelectorAll(".ms-upd").forEach((b) => (b.onclick = () => { const st = steps[+b.dataset.i]; st.month = state.months[state.t]; st.county = state.selected || null; st.mode = state.mode; st.agg = state.agg; saveMyStory(); renderMyStory(); }));
    el.querySelectorAll(".ms-del").forEach((b) => (b.onclick = () => { steps.splice(+b.dataset.i, 1); state.myStep = null; saveMyStory(); renderMyStory(); }));
    const pv = el.querySelector(".ms-prev"), nx = el.querySelector(".ms-next"), cl = el.querySelector(".ms-clear");
    if (pv) pv.onclick = () => go(state.myStep == null ? 0 : state.myStep - 1);
    if (nx) nx.onclick = () => go(state.myStep == null ? 0 : state.myStep + 1);
    if (cl) cl.onclick = () => { if (confirm("Remove every step of your story?")) { state.myStory = []; state.myStep = null; saveMyStory(); renderMyStory(); } };
  }
  /** Apply a saved view: {var, month, mode, county, flows, flowGroup, grid}. */
  async function applyView(w) {
    if (!w) return;
    if (w.mode && [...$("#mode").options].some((o) => o.value === w.mode)) { state.mode = w.mode; $("#mode").value = w.mode; renderModeHint(); }
    if (w.agg) { state.agg = w.agg; $("#agg").value = w.agg; }
    if (w.flows != null) { state.flowOn = !!w.flows; if (w.flowGroup) state.flowGroup = w.flowGroup; renderFlowControls(); }
    if (w.var !== undefined) await setColorBy(state.varById[w.var] ? w.var : null);
    if (w.county) { state.selected = w.county; state.compare = []; }
    const ti = w.month ? state.months.indexOf(w.month) : -1;
    setTime(ti >= 0 ? ti : state.t);
    if (w.county) { refreshCounties(); await renderDetail(); showTab("county"); }
    if (w.national) openNat(true);
    if (w.zoom && countyLayer) { const l = countyLayer.getLayers().find((x) => x.feature.properties.district_id === w.county); if (l) map.fitBounds(l.getBounds().pad(1.2)); }
  }
  function renderVarList() {
    const q = $("#filter").value.trim().toLowerCase();
    const el = $("#var-list"); el.innerHTML = "";
    const act = (state.stories || []).find((x) => x.key === state.story);
    const only = act ? new Set(storyVars(act)) : null;
    if (!q && !only) el.insertAdjacentHTML("beforeend", `<p class="hint vl-hint">Tick measures to chart them together when you click a county. The map shows the one marked <span class="onmap">On map</span>.</p>`);
    let lastCat = null, lastGroup = null;
    for (const v of state.vars) {
      if (only && !only.has(v.id)) continue;
      const hay = `${v.label} ${v.group} ${v.plain || ""} ${(v.synonyms || []).join(" ")}`.toLowerCase();
      if (q && !q.split(/\s+/).every((w) => hay.includes(w))) continue;
      if (v.category !== lastCat) { el.insertAdjacentHTML("beforeend", `<div class="cat-title">${v.category === "climate" ? "Climate and environment" : "People, conflict and aid"}</div>`); lastCat = v.category; lastGroup = null; }
      if (v.group !== lastGroup) { el.insertAdjacentHTML("beforeend", `<div class="group-title">${esc(v.group)}</div>`); lastGroup = v.group; }
      const onMap = state.colorBy === v.id, ticked = state.chartVars.includes(v.id);
      const cov = isStatic(v) ? "single snapshot" : `${v.first_period.slice(0, 4)}–${v.last_period.slice(0, 4)}${v.temporal && v.temporal !== "monthly" ? ", " + v.temporal.replace(/\s*\(.*\)/, "") : ""}`;
      const row = document.createElement("div"); row.className = `var-item${onMap ? " on" : ""}${ticked ? " ticked" : ""}${v.sub ? " sub" : ""}`;
      row.draggable = true; row.title = "Drag into “Your story” to add it as a step";
      row.innerHTML = `<div class="var-line"><label class="var-row"><input type="checkbox" ${ticked ? "checked" : ""}> <span>${esc(v.label)}<span class="meta"> · ${cov}</span></span></label>${onMap ? '<span class="onmap">On map</span>' : ticked ? '<button class="mapbtn">Show on map</button>' : ""}</div>
        ${onMap ? `<div class="var-plain">${esc(plainOf(v))}</div>` : ""}`;
      row.querySelector("input").onchange = (e) => toggleChartVar(v.id, e.target.checked);
      const mb = row.querySelector(".mapbtn"); if (mb) mb.onclick = () => setColorBy(v.id);
      row.ondragstart = (e) => { e.dataTransfer.setData("text/plain", v.id); e.dataTransfer.effectAllowed = "copy"; document.body.classList.add("dragging"); };
      row.ondragend = () => document.body.classList.remove("dragging");
      el.appendChild(row);
    }
    if (q && !el.children.length) el.innerHTML = `<p class="empty">Nothing matches "${esc(q)}". Try flood, rain, heat, fire, fighting, hunger or aid.</p>`;
  }
  /** Tick = add to the county chart and colour the map with it; untick = remove (the map falls back to the last ticked). */
  async function toggleChartVar(id, on) {
    state.chartVars = state.chartVars.filter((x) => x !== id);
    if (on) { state.chartVars.push(id); await setColorBy(id); return; }
    if (state.colorBy === id) await setColorBy(state.chartVars[state.chartVars.length - 1] || null);
    else { renderVarList(); if (state.selected) renderDetail(); writeHash(); }
  }

  async function ensureSeries(id) {
    if (!state.series[id]) {
      if (state.bundle) { const all = await state.bundle; Object.assign(state.series, all); }
      if (!state.series[id]) state.series[id] = await fetchJSON(`data/series/${id}.json`);
    }
    return state.series[id];
  }
  async function setColorBy(id) {
    state.colorBy = id;
    if (id && !state.chartVars.includes(id)) state.chartVars.push(id);
    if (id) await ensureSeries(id);
    renderVarList(); refreshCounties(); updateRasters(); renderLegend(); if (state.selected) renderDetail(); writeHash();
  }

  // ---------- rasters ----------
  function activeRaster(v) {
    if (!v || !state.gridOn) return null;
    const key = state.curated.rasters[v.id]; if (!key) return null;
    if (state.mode === "trend" && usesTrend(v)) return state.rasterByKey[`${key}_trend`] || null;
    return state.rasterByKey[key] || null;
  }
  function rasterDateFor(r, i) {
    const dates = r.dates || []; if (!dates.length) return null;
    if (/_trend$/.test(r.key)) { const d = String(trendYear()); return dates.includes(d) ? d : dates.filter((x) => x <= d).pop() || dates[0]; }
    const ym = state.months[i];
    if (dates.includes(ym)) return ym;
    const sameYear = dates.find((d) => d.slice(0, 4) === ym.slice(0, 4)); if (sameYear) return sameYear;
    let best = null; for (const d of dates) if (d.slice(0, 7) <= ym) best = d; return best || dates[0];
  }
  function wantedRasters() {
    const out = [];   // [slotKey, raster, pane, opacity]
    const v = state.varById[state.colorBy], r = activeRaster(v);
    if (r) out.push(["main", r, "rasters", 0.85]);
    for (const b of state.curated.background) if (state.bgOn.has(b.key) && b.rasters) for (const k of b.rasters) if (state.rasterByKey[k]) out.push([`bg-${k}`, state.rasterByKey[k], k.startsWith("water_base") ? "water" : "bg", k.startsWith("water_base") ? 0.9 : 0.75]);
    return out;
  }
  function updateRasters() {
    const want = wantedRasters(), keep = new Set(want.map((w) => w[0]));
    for (const k of Object.keys(state.rasterLayers)) if (!keep.has(k)) { map.removeLayer(state.rasterLayers[k]); delete state.rasterLayers[k]; }
    for (const [slot, r, pane, op] of want) {
      const d = rasterDateFor(r, state.t); if (!d) continue;
      let url = `rasters/${r.key}/${d}.png`;
      if (r.packed) {
        const y = d.slice(0, 4); r._maps = r._maps || {}; r._pending = r._pending || {};
        if (!r._maps[y]) { if (!r._pending[y]) r._pending[y] = fetchJSON(`rasters/${r.key}/${y}.json`).then((m) => { r._maps[y] = m; updateRasters(); }); continue; }
        url = r._maps[y][d]; if (!url) continue;
      }
      const cur = state.rasterLayers[slot];
      if (cur && cur._pane === pane) { cur.setUrl(url); cur.setBounds(L.latLngBounds(r.bounds)); }
      else { if (cur) map.removeLayer(cur); const lay = L.imageOverlay(url, r.bounds, { pane, opacity: op, interactive: false }).addTo(map); lay._pane = pane; state.rasterLayers[slot] = lay; }
    }
  }

  // ---------- background layers ----------
  let soilLayer = null;
  function renderBgList() {
    const el = $("#bg-list"); el.innerHTML = "";
    for (const b of state.curated.background) {
      const row = document.createElement("label"); row.className = "var-row";
      row.innerHTML = `<input type="checkbox" ${state.bgOn.has(b.key) ? "checked" : ""}> <span>${esc(b.label)}</span>`;
      row.querySelector("input").onchange = (e) => { e.target.checked ? state.bgOn.add(b.key) : state.bgOn.delete(b.key); applyBackground(); writeHash(); };
      el.appendChild(row);
    }
  }
  async function applyBackground() {
    if (state.bgOn.has("soil_type") && !soilLayer) {
      await ensureSeries("soil_wrb_dominant");
      const s = state.series.soil_wrb_dominant, keys = Object.keys(SOIL);
      soilLayer = L.geoJSON(state.countiesGJ, { pane: "bg", interactive: false, style: (f) => { const a = s[f.properties.district_id]; const x = a && a.find((y) => y != null);
        const k = x == null ? -1 : keys.indexOf(String(Math.round(x))); return { stroke: false, fillColor: k < 0 ? NODATA : CATEGORICAL[k], fillOpacity: 0.55 }; } }).addTo(map);
    } else if (!state.bgOn.has("soil_type") && soilLayer) { map.removeLayer(soilLayer); soilLayer = null; }
    updateRasters(); renderLegend();
  }

  // ---------- points ----------
  const ETHNIC_COLORS = {};
  function renderPointList() {
    const el = $("#point-list"); el.innerHTML = "";
    state.points.forEach((p, k) => {
      p._color = CATEGORICAL[k % CATEGORICAL.length];
      const row = document.createElement("div"); row.className = "pt-item";
      const isPoly = /^polygons_/.test(p.key);
      row.innerHTML = `<label class="var-row"><input type="checkbox" id="p-${p.key}" ${state.pointLayers[p.key] ? "checked" : ""}>${isPoly ? '<span class="swatch poly"></span>' : `<span class="swatch" style="background:${p._color}"></span>`}<span>${esc(p.label)}</span></label><div class="pt-legend" id="pl-${p.key}"></div>`;
      row.querySelector("input").onchange = async (e) => {
        if (e.target.checked) await loadPoints(p);
        else if (state.pointLayers[p.key]) { map.removeLayer(state.pointLayers[p.key].layer); delete state.pointLayers[p.key]; $(`#pl-${p.key}`).innerHTML = ""; }
        writeHash();
      };
      el.appendChild(row);
    });
  }
  async function loadPoints(p) {
    const gj = await fetchJSON(p.file);
    const timed = gj.features.some((f) => f.properties && (f.properties.date || f.properties.year || "valid_from" in f.properties || "valid_to" in f.properties));
    if (/^polygons_/.test(p.key)) {
      // draw the largest areas first so smaller group areas stay visible on top
      const area = (f) => { const b = L.geoJSON(f).getBounds(); return (b.getNorth() - b.getSouth()) * (b.getEast() - b.getWest()); };
      gj.features.sort((a, b) => area(b) - area(a));
      [...new Set(gj.features.map((f) => f.properties.group || f.properties.name))].sort().forEach((g, i) => (ETHNIC_COLORS[g] = CATEGORICAL[i % CATEGORICAL.length]));
      $(`#pl-${p.key}`).innerHTML = `<div class="eth-key">${Object.entries(ETHNIC_COLORS).map(([g, c]) => `<span><i style="background:${c}"></i>${esc(g)}</span>`).join("")}</div><p class="hint">Settlement areas from GeoEPR 2023 (ETH Zurich); areas overlap where groups live together. Click an area for its political-power status.</p>`;
    } else {
      $(`#pl-${p.key}`).innerHTML = p.plain && typeof p.plain === "string" ? `<p class="hint">${esc(p.plain.split(/(?<=\.)\s/)[0])}${p.key === "points_gbv_one_stop_centres" ? " Hollow markers mean no source has confirmed the centre since it was last mentioned." : p.key === "points_disasters" || p.key === "points_subsidence_insar" ? "" : " Hollow markers mean the center is closed, damaged or not working."}</p>` : "";
    }
    const entry = { p, gj, timed, layer: null };
    state.pointLayers[p.key] = entry;
    drawPoints(entry);
  }
  function featureInWindow(f) {
    const pr = f.properties || {}, idx = windowIdx(state.t);
    const lo = state.months[idx[0]], hi = state.months[idx[idx.length - 1]];
    if (pr.date) { const ym = String(pr.date).slice(0, 7); return ym >= lo && ym <= hi; }
    if ("valid_from" in pr || "valid_to" in pr) { const from = pr.valid_from ? String(pr.valid_from).slice(0, 7) : "0000-00", to = pr.valid_to ? String(pr.valid_to).slice(0, 7) : "9999-99"; return from <= hi && to >= lo; }
    if (pr.year) { const y = String(pr.year); return (y >= lo.slice(0, 4) && y <= hi.slice(0, 4)) || (y <= hi.slice(0, 4) && !pr.end_year) || (pr.end_year && y <= hi.slice(0, 4) && String(pr.end_year) >= lo.slice(0, 4)); }
    return true;
  }
  const HIDDEN_FIELDS = /^(school_id|facility_id|wpdx_id|ucdp_id|event_id|market_id|osm_id|county_id|county_pcode|coord_quality|date_basis|in_moh_2016|in_mfl_2023|status_stale|inside_ssd|where_prec|geo_precision|valid_from|valid_to|Dataset ids)$/;
  const FIELD_LABELS = { name: "Name", status: "Status", enrol_female: "Girls enrolled", troops_est: "Estimated troops", fpu_present: "Formed police unit present", units_tcc: "Units (troop-contributing countries)",
    prod_oil_mbbl_y: "Oil production (million barrels a year)", side_a: "Side A", side_b: "Side B", deaths: "Deaths", deaths_best: "Deaths (best estimate)", fatalities: "Deaths", county: "County", state: "State", admin1: "State", admin2: "County",
    evidence: "Evidence", source: "Source", source_url: "Source link", year: "Year", end_year: "Until", type: "Type", operator: "Operator", date: "Date" };
  function drawPoints(entry) {
    if (entry.layer) map.removeLayer(entry.layer);
    const { p, gj, timed } = entry, isPoly = /^polygons_/.test(p.key);
    const isEvent = timed && gj.features.some((f) => f.properties && f.properties.date);
    entry.layer = L.geoJSON(gj, {
      pane: "points",
      filter: (f) => !timed || featureInWindow(f),
      style: (f) => {
        if (f.geometry && /Point/.test(f.geometry.type)) return {};
        const c = isPoly ? ETHNIC_COLORS[f.properties.group || f.properties.name] || p._color : p._color;
        return { color: c, weight: 2, fillColor: c, fillOpacity: isPoly ? 0.22 : 0.15 };
      },
      pointToLayer: (f, ll) => {
        const pr = f.properties || {};
        const sizeVal = +(pr.deaths_best ?? pr.deaths ?? pr.fatalities ?? 0);
        const r = isEvent ? Math.min(12, 4 + Math.sqrt(sizeVal)) : 5;
        const closed = /non[- ]?functional|closed|halted|disrupted|unconfirmed|shut|not operating|destroyed|looted/i.test(String(pr.status || ""));
        if (closed) return L.circleMarker(ll, { pane: "points", radius: r, color: p._color, weight: 2, fillColor: "#ffffff", fillOpacity: 0.9 });
        return L.circleMarker(ll, { pane: "points", radius: r, color: "#ffffff", weight: 1.3, fillColor: p._color, fillOpacity: 0.92 });
      },
      onEachFeature: (f, l) => {
        const pr = f.properties || {};
        const nice = (k) => FIELD_LABELS[k] || (/[A-Z ]/.test(k) ? k : k.replace(/_/g, " ").replace(/^./, (c) => c.toUpperCase()));
        const rows = Object.entries(pr).filter(([k, val]) => val !== null && val !== "" && typeof val !== "object" && !HIDDEN_FIELDS.test(k) && !/^(ids?|gwid|gwgroupid|groupid|fid|objectid|_.*)$/i.test(k)).slice(0, 14)
          .map(([k, val]) => `<tr><td class="muted">${esc(nice(k))}</td><td>${/^https?:/.test(String(val)) ? `<a href="${esc(val)}" target="_blank" rel="noopener">link</a>` : esc(String(val).slice(0, 200))}</td></tr>`).join("");
        const head = pr.name || pr.facility_name || pr.site_name || pr.title || "";
        const status = pr.status ? `<div><b>Status:</b> ${esc(pr.status)}</div>` : "";
        const when = pr.date ? `<div><b>Date:</b> ${esc(String(pr.date).slice(0, 10))}</div>` : (pr.valid_from || pr.valid_to) ? `<div><b>Period:</b> ${pr.valid_from ? esc(String(pr.valid_from).slice(0, 7)) : "before 2018"} → ${pr.valid_to ? esc(String(pr.valid_to).slice(0, 7)) : "2025+"}</div>` : "";
        const ev = pr.evidence || pr.date_basis ? `<div class="hint">Evidence: ${esc(String(pr.evidence || pr.date_basis).slice(0, 220))}</div>` : "";
        const popOpts = { maxWidth: 300, autoPanPadding: [20, 20], className: "pt-pop" };
        if (isPoly) {
          const keep = ["Political power status", "What this means", "Share of national population", "Period"];
          const trs = keep.filter((k) => pr[k]).map((k) => `<tr><td class="muted">${esc(k)}</td><td>${esc(String(pr[k]))}</td></tr>`).join("");
          l.bindPopup(`<b>${esc(pr.Group || pr.name || "")}</b><table>${trs}</table>${pr.source_url ? `<div class="hint"><a href="${esc(pr.source_url)}" target="_blank" rel="noopener">Source: Ethnic Power Relations (ETH Zurich)</a></div>` : ""}`, popOpts);
          return;
        }
        l.bindPopup(`<b>${esc(p.label)}</b>${head ? `<div>${esc(head)}</div>` : ""}${status}${when}${ev}<details><summary>Details</summary><table>${rows}</table></details>`, popOpts);
      },
    }).addTo(map);
  }
  const refreshPoints = () => { for (const e of Object.values(state.pointLayers)) if (e.timed) drawPoints(e); };

  // ---------- migration flows (IOM Event Tracking only) ----------
  state.flowOn = false; state.flowGroup = "all"; state.flowLayer = null;
  const flowRenderer = L.svg({ pane: "flows", padding: 0.5 });
  let flowDefsReady = false;
  const reasonGroup = (r) => { const G = state.curated.flow_groups; return Object.keys(G).find((k) => G[k].reasons.includes(r)) || "other"; };
  function ensureArrowDefs() {
    if (flowDefsReady || !flowRenderer._container) return;
    const ns = "http://www.w3.org/2000/svg", defs = document.createElementNS(ns, "defs");
    for (const [k, g] of Object.entries(state.curated.flow_groups)) {
      const m = document.createElementNS(ns, "marker");
      m.setAttribute("id", `ah-${k}`); m.setAttribute("viewBox", "0 0 10 10"); m.setAttribute("refX", "6"); m.setAttribute("refY", "5");
      m.setAttribute("markerWidth", "3.4"); m.setAttribute("markerHeight", "3.4"); m.setAttribute("orient", "auto-start-reverse"); m.setAttribute("markerUnits", "strokeWidth");
      const path = document.createElementNS(ns, "path"); path.setAttribute("d", "M0,0 L10,5 L0,10 z"); path.setAttribute("fill", g.color);
      path.setAttribute("stroke", "#ffffff"); path.setAttribute("stroke-width", "1.2");
      m.appendChild(path); defs.appendChild(m);
    }
    flowRenderer._container.insertBefore(defs, flowRenderer._container.firstChild);
    flowDefsReady = true;
  }
  function bezier(a, b, bendFrac) {
    const [y1, x1] = a, [y2, x2] = b, dx = x2 - x1, dy = y2 - y1, len = Math.hypot(dx, dy) || 1, bend = Math.min(1.2, len * bendFrac);
    const qx = (x1 + x2) / 2 + (bend * dy) / len, qy = (y1 + y2) / 2 - (bend * dx) / len, pts = [];
    for (let k = 0; k <= 20; k++) { const t = k / 20, u = 1 - t; pts.push([u * u * y1 + 2 * u * t * qy + t * t * y2, u * u * x1 + 2 * u * t * qx + t * t * x2]); }
    return pts;
  }
  function drawFlows() {
    if (state.flowLayer) { map.removeLayer(state.flowLayer); state.flowLayer = null; }
    const F = state.flows; if (!F) return;
    const si = F.sources.findIndex((x) => x.key === "et");
    const ms = windowIdx(state.t).map((j) => state.months[j]);
    const agg = new Map();
    let any = false;
    if (state.flowOn && si >= 0) for (const m of ms) {
      if (F.sources[si].months.includes(m)) any = true;
      for (const [s, a, b, r, n] of F.months[m] || []) {
        if (s !== si) continue;
        const g = reasonGroup(F.reasons[r]);
        if (state.flowGroup !== "all" && g !== state.flowGroup) continue;
        const k = `${a}|${b}|${g}`; agg.set(k, (agg.get(k) || 0) + n);
      }
    }
    const st = $("#flow-status");
    if (st) st.innerHTML = !state.flowOn ? "" : !any ? `<span class="none">No IOM Event Tracking data for ${windowLabel(state.t)}. Records start in late 2019, and most months from 2020 on are covered.</span>` : `${[...agg.values()].reduce((a, b) => a + b, 0).toLocaleString("en-US")} people moving in ${windowLabel(state.t)}.`;
    if (!state.flowOn) return;
    const list = [...agg.entries()].map(([k, n]) => { const [a, b, g] = k.split("|"); return { a: +a, b: +b, g, n }; }).sort((x, y) => y.n - x.n).slice(0, 150);
    const max = Math.max(1, ...list.map((f) => f.n));
    state.flowLayer = L.layerGroup().addTo(map);
    ensureArrowDefs();
    const crossings = new Map();
    const G = state.curated.flow_groups, gi = Object.keys(G);
    for (const f of list.slice().reverse()) {   // biggest drawn last = on top
      const A = F.nodes[f.a], B = F.nodes[f.b], g = G[f.g];
      const w = FLOW_W(f.n);
      if (!String(A[3]).startsWith("SS")) crossings.set(f.a, (crossings.get(f.a) || 0) + f.n);
      const pts = bezier(A, B, 0.12 + 0.05 * gi.indexOf(f.g));
      L.polyline(pts, { renderer: flowRenderer, pane: "flows", color: "#ffffff", weight: w + 2.5, opacity: 0.9, lineCap: "round", interactive: false }).addTo(state.flowLayer);
      const line = L.polyline(pts, { renderer: flowRenderer, pane: "flows", color: g.color, weight: w, opacity: 0.95, lineCap: "round" })
        .bindTooltip(`<b>${esc(A[2])} → ${esc(B[2])}</b><br>${esc(g.label)}<br><b>${f.n.toLocaleString("en-US")}</b> people · ${windowLabel(state.t)}<br><span class="muted">IOM Event Tracking</span>`, { sticky: true });
      line.addTo(state.flowLayer);
      if (line._path) line._path.setAttribute("marker-end", `url(#ah-${f.g})`);
    }
    for (const [ni, n] of crossings) {
      const N = F.nodes[ni];
      L.circleMarker([N[0], N[1]], { pane: "flows", radius: 6, color: "#0b0b0b", weight: 2, fillColor: "#ffffff", fillOpacity: 1 })
        .bindTooltip(`${esc(N[2])} (border crossing)<br><b>${n.toLocaleString("en-US")}</b> people arriving`, { direction: "top" }).addTo(state.flowLayer);
    }
  }
  function renderFlowControls() {
    const el = $("#flow-controls"); if (!state.flows || !el) return;
    const G = state.curated.flow_groups;
    const opt = (val, lab, col) => `<label class="var-row"><input type="radio" name="flow-g" value="${val}" ${state.flowGroup === val ? "checked" : ""}>${col ? `<span class="swatch" style="background:${col}"></span>` : ""}<span>${esc(lab)}</span></label>`;
    el.innerHTML = `<label class="var-row"><input type="checkbox" id="flow-on" ${state.flowOn ? "checked" : ""}> <span><b>Show where people moved</b></span></label>
      <p class="hint">From IOM Event Tracking. Each arrow runs from the county people left to the county they reached, for people newly displaced or returning. Arrivals from abroad start at a border crossing (white circle).</p>
      <div class="flow-opts">${opt("all", "All reasons")}${opt("climate", G.climate.label, G.climate.color)}${opt("conflict", G.conflict.label, G.conflict.color)}</div>
      <p class="hint" id="flow-status"></p>`;
    $("#flow-on").onchange = (e) => { state.flowOn = e.target.checked; drawFlows(); refreshCounties(); renderLegend(); writeHash(); };
    el.querySelectorAll('input[name="flow-g"]').forEach((rb) => (rb.onchange = () => { state.flowGroup = rb.value; drawFlows(); renderLegend(); writeHash(); }));
  }

  // ---------- right-hand panel: what was happening (time-based context) ----------
  function periodFor(ym) {
    const P = (state.context && state.context.periods) || [];
    const hits = P.filter((p) => p.from <= ym && ym <= p.to);
    hits.sort((a, b) => (a.to > a.from ? 1 : 0) - (b.to > b.from ? 1 : 0) || (a.from < b.from ? 1 : -1));   // single-month first
    return hits;
  }
  /** National monthly line for a series: sum or mean over counties, or the single national series. */
  function nationalLine(id, how) {
    const s = state.series[id]; if (!s) return null;
    const cs = Object.keys(s);
    if (how === "national" || cs.length === 1) return natArr(id);
    return state.months.map((_, i) => { const xs = cs.map((c) => s[c][i]).filter((x) => x != null && isFinite(x)); if (!xs.length) return null; const t = xs.reduce((a, b) => a + b, 0); return how === "sum" ? t : t / xs.length; });
  }
  state.ctxCharts = [];
  async function renderContext() {
    const el = $("#context"); if (!el) return;
    const ym = state.months[state.t];
    const hits = periodFor(ym);
    const evs = (state.events || []).filter((e) => e.date.slice(0, 7) === ym);
    const key = hits.map((p) => p.from + p.to).join("|") + "#" + evs.length;
    if (key === state._ctxKey) { state.ctxCharts.forEach((c) => c.draw()); return; }
    state._ctxKey = key;
    state.ctxCharts.forEach((c) => c.destroy()); state.ctxCharts = [];
    if (!hits.length && !evs.length) { el.innerHTML = `<p class="hint">${state.context ? "No summary for this month." : "Loading…"}</p>`; return; }
    const range = (p) => (p.from === p.to ? monthLabel(state.months.indexOf(p.from)) : `${monthLabel(state.months.indexOf(p.from))} – ${monthLabel(state.months.indexOf(p.to))}`);
    const charts = [];
    for (const p of hits) for (const c of p.charts || []) if (!charts.some((x) => x.id === c.id)) charts.push({ ...c, from: p.from, to: p.to });
    let html = "";
    // order: what happened (text), then the national charts, then sources
    for (const p of hits) {
      html += `<article class="ctx"><div class="ctx-range">${esc(range(p))}</div><h3>${esc(p.title)}</h3><p>${esc(p.text)}</p>${p.links ? `<p class="ctx-links">${esc(String(p.links).replace(/^\s*In the charts:\s*/i, ""))}</p>` : ""}</article>`;
    }
    if (charts.length) html += `<h3 class="ctx-h">National Trends</h3>${charts.map((c, k) => `<div class="ctx-chart"><div class="cc-t">${esc(c.label)}${c.units ? ` <span class="muted">(${esc(c.units)})</span>` : ""}</div><div class="cc-box"><canvas id="ctxc-${k}"></canvas></div></div>`).join("")}`;
    const srcs = hits.flatMap((p) => p.sources || []);
    if (srcs.length) html += `<p class="ctx-src">Sources: ${srcs.map((s, i) => `<a href="${esc(s.url)}" target="_blank" rel="noopener">${esc(s.label || `[${i + 1}]`)}</a>`).join(" · ")}</p>`;
    if (evs.length) html += `<div class="ctx-evs"><h3>Also recorded this month</h3><ul>${evs.map((e) => `<li>${esc(e.title)}${e.source_url ? ` <a href="${esc(e.source_url)}" target="_blank" rel="noopener">source</a>` : ""}</li>`).join("")}</ul></div>`;
    el.innerHTML = html;
    if (!charts.length) return;
    await Promise.all(charts.map((c) => ensureSeries(c.id).catch(() => null)));
    if (state._ctxKey !== key) return;
    const ink2 = css("--ink-2"), line = css("--line");
    charts.forEach((c, k) => {
      const data = nationalLine(c.id, c.how); const cv = document.getElementById(`ctxc-${k}`);
      if (!data || !cv) { if (cv) cv.parentElement.parentElement.remove(); return; }
      const a = state.months.indexOf(c.from), b = state.months.indexOf(c.to);
      state.ctxCharts.push(new Chart(cv, { type: "line", data: { labels: state.months, datasets: [{ data, borderColor: MAIN, borderWidth: 1.6, pointRadius: 0, pointHitRadius: 6, tension: 0, spanGaps: false }] },
        options: { animation: false, responsive: true, maintainAspectRatio: false, interaction: { mode: "index", intersect: false },
          plugins: { legend: { display: false }, tooltip: { callbacks: { title: (q) => monthLabel(q[0].dataIndex), label: (q) => `${q.raw == null ? "–" : fmt(q.raw)} ${c.units || ""}` } } },
          scales: { x: { ticks: { color: ink2, font: { size: 10 }, autoSkip: false, maxRotation: 0, callback: (_, i) => (i % 24 === 6 ? state.months[i].slice(0, 4) : null) }, grid: { color: (q) => (q.index % 12 === 0 ? line : "transparent"), drawTicks: false } },
            y: { beginAtZero: c.how !== "mean", ticks: { color: ink2, font: { size: 10 }, maxTicksLimit: 4, callback: (x) => fmt(x, 2) }, grid: { color: line } } } },
        plugins: [{ id: "marks", beforeDraw(ch) { const { ctx, chartArea: ar, scales } = ch; if (a < 0 || b < 0) return; ctx.save(); ctx.fillStyle = "rgba(11,61,145,0.08)"; const x0 = scales.x.getPixelForValue(a), x1 = scales.x.getPixelForValue(b); ctx.fillRect(x0, ar.top, Math.max(2, x1 - x0), ar.bottom - ar.top); ctx.restore(); },
          afterDraw(ch) { const { ctx, chartArea: ar, scales } = ch; const x = scales.x.getPixelForValue(state.t); ctx.save(); ctx.strokeStyle = ORANGE; ctx.lineWidth = 2; ctx.beginPath(); ctx.moveTo(x, ar.top); ctx.lineTo(x, ar.bottom); ctx.stroke(); ctx.restore(); } }] }));
    });
  }
  function showTab(which) {
    const ctx = which === "context";
    $("#tab-context").setAttribute("aria-selected", ctx); $("#tab-county").setAttribute("aria-selected", !ctx);
    $("#context").hidden = !ctx; $("#detail").hidden = ctx;
  }

  // ---------- county detail (on click): profile + selected measure only ----------
  function rawWindowSeries(v, cid) {
    const keys = [], labels = [], vals = [], firstIdx = [];
    state.months.forEach((_, i) => { const k = windowKey(i); if (!keys.includes(k)) { keys.push(k); firstIdx.push(i); labels.push(windowLabel(i)); vals.push(valueAt(v, cid, i, "raw")); } });
    return { keys, labels, vals, firstIdx };
  }
  function trendSentence(v, cid) {
    if (isStatic(v) || isCategorical(v)) return "This is a single snapshot, so there is no trend over time.";
    const tr = trendOf(v.id, cid); if (!tr || tr[T_SEN] == null) return "Too little data to estimate a trend for this county.";
    const x = trendNative(v, cid, 2025), sig = tr[T_SIG];
    const strength = sig ? "This trend is found to be statistically significant, even allowing for the fact that all 79 counties were tested." : tr[T_P] != null && tr[T_P] < 0.05 ? "This trend is suggestive, but it is not significant once all 79 counties are tested together." : "This change is not statistically significant and could be chance.";
    return `Trend 2018–2025: <b>${signed(x, 2)} ${slopeUnits(v)}</b> (Sen's slope). ${strength}`;
  }
  const COMPARE_COLORS = [MAIN, "#fc3c23", "#1baf7a", "#a05eb5"];
  const countyProps = (cid) => { const l = countyLayer.getLayers().find((x) => x.feature.properties.district_id === cid); return l ? l.feature.properties : { name: cid, admin1: "" }; };
  async function renderDetail() {
    const cid = state.selected;
    $("#tab-county").disabled = !cid;
    if (!cid) { $("#tab-county").textContent = "Click on a county for more detailed info"; showTab("context"); return; }
    const P = countyProps(cid), v = state.varById[state.colorBy];
    $("#tab-county").textContent = `${P.name} County`;
    state.compare = (state.compare || []).filter((c) => c !== cid);
    $("#detail-title").textContent = `${P.name} County`;
    $("#detail-sub").textContent = `${P.admin1} State`;
    const pr = state.profiles && state.profiles[cid];
    let html = "";
    if (pr) {
      html += `<div class="profile">${pr.livelihood_zone && pr.livelihood_zone.name ? `<p class="pf-lz">${esc(pr.livelihood_zone.name)}</p>` : ""}
        ${["livelihoods", "history", "conflict_impact"].map((k) => (pr[k] ? `<p><b>${{ livelihoods: "Livelihoods", history: "History", conflict_impact: "Conflict impact" }[k]}.</b> ${esc(pr[k])}</p>` : "")).join("")}
        ${pr.sources && pr.sources.length ? `<p class="hint">Sources: ${pr.sources.slice(0, 4).map((u, i) => `<a href="${esc(u)}" target="_blank" rel="noopener">[${i + 1}]</a>`).join(" ")}</p>` : ""}</div>`;
    }
    const cmp = (state.compare || []).map((c) => `<span class="cmp-chip" style="--c:${COMPARE_COLORS[(state.compare || []).indexOf(c) + 1]}">${esc(countyProps(c).name)} <button data-c="${esc(c)}" aria-label="Remove">×</button></span>`).join("");
    const top = `<div class="cmp-row"><button id="btn-compare" class="pill${state.comparing ? " on" : ""}">${state.comparing ? "Click a county on the map…" : "+ Compare with another county"}</button>${cmp}</div>`;
    html = top + html + `<div id="detail-chart"></div><div class="detail-actions"><button id="btn-csv">Download this data (CSV)</button></div>`;
    $("#detail-body").innerHTML = html;
    $("#btn-csv").onclick = downloadCSV;
    $("#btn-compare").onclick = () => { state.comparing = !state.comparing; renderDetail(); };
    $("#detail-body").querySelectorAll(".cmp-chip button").forEach((b) => (b.onclick = () => { state.compare = state.compare.filter((c) => c !== b.dataset.c); renderDetail(); }));
    state.charts.forEach((c) => c.destroy()); state.charts = [];
    const box = $("#detail-chart");
    if (!v) { box.innerHTML = `<p class="empty">Choose a measure in the left panel to see this county's history.</p>`; return; }
    await ensureSeries(v.id);
    const ticked = state.chartVars.filter((id) => state.varById[id] && !isStatic(state.varById[id]) && !isCategorical(state.varById[id]));
    if (ticked.length >= 2) { await renderMultiChart(box, cid, ticked); return; }
    const now = valueAt(v, cid, state.t, "raw");
    box.innerHTML = `<div class="chart-block"><h3>${esc(v.label)}</h3><div class="var-plain">${esc(plainOf(v))}</div>
      <p class="now">${windowLabel(state.t)}: <b>${isCategorical(v) ? soilName(now) : now == null ? "no data" : `${fmt(now)} ${esc(unitsShort(v))}`}</b></p>
      <p class="trend-s">${trendSentence(v, cid)}</p>${isStatic(v) ? "" : '<div class="chart-box"><canvas></canvas></div>'}</div>`;
    if (isStatic(v)) return;
    const S = rawWindowSeries(v, cid), cur = S.keys.indexOf(windowKey(state.t));
    const baseVals = S.firstIdx.map((i) => (state.agg === "year" ? null : mean(baselineWindowIdx(i, v.baseline_year || 2018).map((q) => ((state.series[v.id] || {})[cid] || [])[q]))));
    const ds = [{ label: P.name, data: S.vals, borderColor: COMPARE_COLORS[0], borderWidth: 2, pointRadius: 0, pointHitRadius: 8, tension: 0.15, spanGaps: false }];
    (state.compare || []).forEach((c, k) => ds.push({ label: countyProps(c).name, data: rawWindowSeries(v, c).vals, borderColor: COMPARE_COLORS[k + 1], borderWidth: 1.8, pointRadius: 0, pointHitRadius: 8, tension: 0.15, spanGaps: false }));
    if (v.temporal === "monthly" && !(state.compare || []).length && baseVals.some((x) => x != null)) ds.push({ label: `Same ${state.agg === "month" ? "month" : "season"} in ${v.baseline_year || 2018}`, data: baseVals.map((x) => (x != null && isShareUnits(v) ? x * 100 : x)), borderColor: "#898781", borderDash: [4, 3], borderWidth: 1.2, pointRadius: 0 });
    const ink2 = css("--ink-2"), line = css("--line");
    state.charts.push(new Chart(box.querySelector("canvas"), {
      type: "line", data: { labels: S.labels, datasets: ds },
      options: { animation: false, responsive: true, maintainAspectRatio: false, interaction: { mode: "index", intersect: false },
        plugins: { legend: { display: ds.length > 1, position: "bottom", labels: { boxWidth: 10, font: { size: 11 } } }, tooltip: { callbacks: { label: (c) => `${c.dataset.label}: ${c.raw == null ? "–" : fmt(c.raw)} ${unitsShort(v)}` } } },
        scales: { x: { ticks: { color: ink2, font: { size: 11 }, autoSkip: false, maxRotation: 0, callback: (_, i) => { const k = S.firstIdx[i]; return k % 12 === 0 || (state.agg === "year") ? state.months[k].slice(0, 4) : null; } }, grid: { color: (c) => (S.firstIdx[c.index] % 12 === 0 ? line : "transparent") } },
          y: { ticks: { color: ink2, maxTicksLimit: 5, font: { size: 11 } }, grid: { color: line }, title: { display: true, text: unitsShort(v), color: ink2, font: { size: 11 } } } },
        onClick: (_, els) => { if (els.length) setTime(S.firstIdx[els[0].index]); } },
      plugins: [{ id: "cursor", afterDraw(c) { const { ctx, chartArea: a, scales } = c; const x = scales.x.getPixelForValue(cur); ctx.save(); ctx.strokeStyle = ORANGE; ctx.lineWidth = 2; ctx.beginPath(); ctx.moveTo(x, a.top); ctx.lineTo(x, a.bottom); ctx.stroke(); ctx.restore(); } }],
    }));
  }

  /** Several ticked measures on one chart: each as change from the same month (season, year) of 2018, in standard
   *  deviations of that county's own record, so measures in different units share one axis. */
  const MULTI_COLORS = ["#0B3D91", "#fc3c23", "#1baf7a", "#eda100", "#a05eb5", "#0aa5b8", "#e87ba4", "#4a4a4a"];
  async function renderMultiChart(box, cid, ids) {
    await Promise.all(ids.map((id) => ensureSeries(id)));
    const rows = [], ds = [];
    let S0 = null;
    ids.forEach((id, k) => {
      const v = state.varById[id], arr = (state.series[id] || {})[cid] || [];
      const S = rawWindowSeries(v, cid); S0 = S0 || S;
      const ok = arr.filter((x) => x != null && isFinite(x)), m = mean(ok);
      const sd = ok.length > 2 ? Math.sqrt(ok.reduce((a, x) => a + (x - m) ** 2, 0) / (ok.length - 1)) : null;
      const sc = isShareUnits(v) ? 100 : 1;
      const z = S.firstIdx.map((i, w) => { const base = mean(baselineWindowIdx(i, v.baseline_year || 2018).map((q) => arr[q])); const x = S.vals[w];
        return x == null || base == null || !sd ? null : (x - base * sc) / (sd * sc); });
      const col = MULTI_COLORS[k % MULTI_COLORS.length];
      ds.push({ label: v.label, data: z, raw: S.vals, units: unitsShort(v), borderColor: col, backgroundColor: col, borderWidth: id === state.colorBy ? 2.4 : 1.6, pointRadius: 0, pointHitRadius: 8, tension: 0.15, spanGaps: false });
      const tr = trendOf(id, cid);
      rows.push(`<li><i style="background:${col}"></i><b>${esc(v.label)}</b>${tr && tr[T_SEN] != null ? ` · ${signed(trendNative(v, cid, 2025), 2)} ${esc(slopeUnits(v))}${tr[T_SIG] ? ' <span class="sigtag">significant</span>' : ""}` : ""}</li>`);
    });
    box.innerHTML = `<div class="chart-block"><h3>Your ticked measures, change from 2018</h3><p class="hint">Each line is the change from the same ${state.agg === "month" ? "month" : state.agg === "season" ? "season" : "year"} of 2018, scaled to the measure's usual range so different units share one chart.</p>
      <ul class="mc-list">${rows.join("")}</ul><div class="chart-box tall"><canvas></canvas></div></div>`;
    const ink2 = css("--ink-2"), line = css("--line"), cur = S0.keys.indexOf(windowKey(state.t));
    state.charts.push(new Chart(box.querySelector("canvas"), {
      type: "line", data: { labels: S0.labels, datasets: ds },
      options: { animation: false, responsive: true, maintainAspectRatio: false, interaction: { mode: "index", intersect: false },
        plugins: { legend: { display: false }, tooltip: { callbacks: { label: (c) => { const d = c.dataset, r = d.raw[c.dataIndex]; return `${d.label}: ${r == null ? "–" : `${fmt(r)} ${d.units}`}${c.raw == null ? "" : ` (${c.raw >= 0 ? "+" : ""}${c.raw.toFixed(1)} vs 2018)`}`; } } } },
        scales: { x: { ticks: { color: ink2, font: { size: 11 }, autoSkip: false, maxRotation: 0, callback: (_, i) => { const k = S0.firstIdx[i]; return k % 12 === 0 || state.agg === "year" ? state.months[k].slice(0, 4) : null; } }, grid: { color: (c) => (S0.firstIdx[c.index] % 12 === 0 ? line : "transparent") } },
          y: { ticks: { color: ink2, maxTicksLimit: 6, font: { size: 11 } }, grid: { color: (c) => (c.tick.value === 0 ? "#888" : line) }, title: { display: true, text: "change from 2018 (standard deviations)", color: ink2, font: { size: 11 } } } },
        onClick: (_, els) => { if (els.length) setTime(S0.firstIdx[els[0].index]); } },
      plugins: [{ id: "cursor", afterDraw(c) { const { ctx, chartArea: a, scales } = c; const x = scales.x.getPixelForValue(cur); ctx.save(); ctx.strokeStyle = ORANGE; ctx.lineWidth = 2; ctx.beginPath(); ctx.moveTo(x, a.top); ctx.lineTo(x, a.bottom); ctx.stroke(); ctx.restore(); } }],
    }));
  }

  // ---------- export & shareable state ----------
  function buildCSV() {
    const v = state.varById[state.colorBy]; if (!v) return "";
    const cids = state.selected ? [state.selected] : Object.keys(state.series[v.id] || {});
    const rows = [["county_id", "county", "state", "variable", "label", "units", "month", "value"]];
    for (const c of cids) { const p = countyProps(c), arr = (state.series[v.id] || {})[c] || []; state.months.forEach((m, i) => { if (arr[i] != null) rows.push([c, p.name, p.admin1, v.id, v.label, v.units || "", m, arr[i]]); }); }
    return rows.map((r) => r.map((x) => (/[",\n]/.test(String(x)) ? `"${String(x).replace(/"/g, '""')}"` : x)).join(",")).join("\n");
  }
  function downloadCSV() {
    const csv = buildCSV();
    try { const a = document.createElement("a"); a.href = URL.createObjectURL(new Blob([csv], { type: "text/csv" })); a.download = `south_sudan_${state.colorBy}_${state.selected || "all_counties"}.csv`; document.body.appendChild(a); a.click(); a.remove(); }
    catch (e) { copyText(csv, "The download was blocked, so the CSV was copied to your clipboard instead."); }
  }
  function copyText(txt, msg) {
    const done = () => toast(msg), fail = () => { const ta = document.createElement("textarea"); ta.value = txt; document.body.appendChild(ta); ta.select(); try { document.execCommand("copy"); done(); } catch (e) { toast("Copying is not allowed here."); } ta.remove(); };
    if (navigator.clipboard && navigator.clipboard.writeText) navigator.clipboard.writeText(txt).then(done, fail); else fail();
  }
  function toast(msg) { let t = $("#toast"); if (!t) { t = document.createElement("div"); t.id = "toast"; document.body.appendChild(t); } t.textContent = msg; t.className = "show"; setTimeout(() => (t.className = ""), 2600); }
  function writeHash() {
    if (!state.months.length) return;
    const h = new URLSearchParams({ view: state.view, m: state.mode, a: state.agg, t: state.months[state.t], v: state.colorBy || "", cv: state.chartVars.join(","), s: state.selected || "",
      fo: state.flowOn ? "1" : "0", fg: state.flowGroup, g: state.gridOn ? "1" : "0", bg: [...state.bgOn].join(","), p: Object.keys(state.pointLayers).join(","), n: state.natOpen ? "1" : "0" });
    try { history.replaceState(null, "", `#${h.toString()}`); } catch (e) { /* sandboxed */ }
  }
  function readHash() { try { const h = new URLSearchParams(location.hash.slice(1)); return h.has("m") ? h : null; } catch (e) { return null; } }

  // ---------- national timeline ----------
  function natArr(id) {
    const s = state.series[id]; if (!s) return null;
    const c = Object.keys(s).find((k) => s[k].some((x) => x != null)); return c ? s[c] : null;
  }
  function yearly(arr, how) {   // per-month array holding the calendar-year total (how = "sum") or last value
    const out = new Array(state.months.length).fill(null), byY = {};
    arr.forEach((x, i) => { if (x != null && isFinite(x)) (byY[yearOf(i)] = byY[yearOf(i)] || []).push(x); });
    state.months.forEach((_, i) => { const v = byY[yearOf(i)]; if (v) out[i] = how === "sum" ? v.reduce((a, b) => a + b, 0) : v[v.length - 1]; });
    return out;
  }
  function nationalSpecs() {
    const A = natArr, mul = (arr, k) => arr && arr.map((x) => (x == null ? null : x * k));
    const specs = [];
    const cov = A("hrp_coverage_year"), fund = A("hrp_funding_year_usd"), req = A("hrp_requirement_year_usd");
    if (cov) specs.push({ title: "UN aid appeal: share of the money requested that was received", sub: "South Sudan Humanitarian Response Plan, by calendar year (OCHA Financial Tracking Service).", step: true,
      sets: [{ data: mul(cov, 100), color: MAIN, label: "% of requested amount received", fmt: (x) => `${fmt(x, 2)}%` }], yMin: 0, yMax: 100,
      extra: (i) => (fund && req && fund[i] != null ? `${usd(fund[i])} received of ${usd(req[i])} requested` : "") });
    const disb = A("usaid_disbursed_month_usd"), obl = A("usaid_obligated_month_usd");
    if (disb && obl) {
      const yd = yearly(disb, "sum"), yo = yearly(obl, "sum"), pct = yd.map((x, i) => (x != null && yo[i] ? (100 * x) / yo[i] : null));
      specs.push({ title: "USAID aid paid out, as a % of aid committed that year", sub: "Calendar-year totals from ForeignAssistance.gov. The share can pass 100% when money committed in earlier years is paid out.", step: true,
        sets: [{ data: pct, color: MAIN, label: "Paid out as % of committed", fmt: (x) => `${fmt(x, 3)}%` }], yMin: 0, refLine: 100,
        extra: (i) => (yd[i] != null ? `${yearOf(i)}: ${usd(yd[i])} paid out · ${usd(yo[i])} committed` : "") });
    }
    const usm = A("fts_us_gov_funding_month_usd");
    if (usm) specs.push({ title: "US government humanitarian funding, by month", sub: "Funding decisions recorded by OCHA's Financial Tracking Service, in US$.", bar: true,
      sets: [{ data: usm, color: MAIN, label: "US$ per month", fmt: usd }], yMin: 0 });
    const share = A("fts_us_share_year"), usy = A("fts_us_gov_funding_year_usd");
    if (share && usy) specs.push({ title: "US share of all humanitarian funding (solid) and US amount per year (dashed)", sub: "OCHA Financial Tracking Service, by calendar year.", step: true,
      sets: [{ data: mul(share, 100), color: MAIN, label: "US share of all humanitarian funding", fmt: (x) => `${fmt(x, 2)}%`, axis: "y" },
        { data: usy, color: "#7a7872", dash: [6, 4], label: "US funding that year", fmt: usd, axis: "y2" }], yMin: 0, y2: true });
    const add = (id, title, sub, color, f, opts = {}) => { let a = A(id); if (a && opts.prep) a = opts.prep(a); if (a) specs.push({ title, sub, sets: [{ data: opts.mul ? mul(a, opts.mul) : a, color, label: title, fmt: f, dash: opts.dash }], yMin: 0, ...opts }); };
    // Survey-edition series (WPS Index): keep one value per edition year, drawn as a dot at mid-year.
    const editions = (arr) => arr.map((x, i) => (x != null && state.months[i].endsWith("-07") ? x : null));
    const editionTitle = (i) => `${yearOf(i)} edition`;
    const yearTitle = (i) => String(yearOf(i));
    add("ii_sexual_violence_incidents", "Conflict-related sexual violence: reported incidents per year (national)", "Insecurity Insight, yearly totals. Coverage starts in 2020, so 2018–2019 are blank, not zero. Reporting is very incomplete, and a low count may hide many unreported incidents.", MAIN, (x) => `${fmt(x)} incidents`, { bar: true, prep: (a) => yearly(a, "sum"), titleFn: yearTitle });
    add("unmiss_budget_fy_usd", "UN peacekeeping mission (UNMISS) budget", "Approved budget for each UN fiscal year (July–June).", "#7a7872", usd, { step: true, yMin: null });
    add("fmr_internal_forced_total", "Forced travel: people counted moving because of conflict, disaster or hunger (national)", "IOM Flow Monitoring. Counts only people passing its monitoring points, so it misses other routes. No county data for Nov 2023–Dec 2024.", MAIN, (x) => `${fmt(x)} people`, { bar: true });
    const wpsSub = "Women, Peace and Security Index (Georgetown Institute). One dot per index edition (2019, 2021, 2023, 2025); the dashed line only joins them. Methods differ between editions, so compare with care.";
    const wpsOpts = { points: true, dash: [5, 4], prep: editions, titleFn: editionTitle };
    add("wps_ipv_pct", "Women who faced violence from a partner in the last year (national)", wpsSub, MAIN, (x) => `${fmt(x, 3)}%`, { ...wpsOpts, yMax: 60 });
    add("wps_community_safety_pct", "Women who feel safe walking alone at night in their community (national)", wpsSub, MAIN, (x) => `${fmt(x, 3)}%`, { ...wpsOpts, yMax: 100 });
    add("wps_education_years", "Women's average years of schooling (national)", wpsSub, MAIN, (x) => `${fmt(x, 3)} years`, wpsOpts);
    return specs;
  }
  async function renderNational() {
    const box = $("#nat-charts"); if (!box) return;
    await Promise.all(state.curated.national_ids.map((id) => ensureSeries(id).catch(() => null)));
    state.natCharts.forEach((c) => c.destroy()); state.natCharts = []; box.innerHTML = "";
    const ink2 = css("--ink-2"), line = css("--line");
    for (const spec of nationalSpecs()) {
      const tile = document.createElement("div"); tile.className = "nat-tile";
      tile.innerHTML = `<h3>${esc(spec.title)}</h3><p class="nt-sub">${esc(spec.sub)}</p><div class="nt-v"></div><div class="nt-canvas"><canvas></canvas></div>`;
      box.appendChild(tile);
      const datasets = spec.sets.map((s) => ({ label: s.label, data: s.data, borderColor: s.color, backgroundColor: spec.bar ? s.color + "cc" : s.color, borderWidth: spec.bar ? 0 : 2,
        borderDash: s.dash || [], stepped: spec.step ? "middle" : false, pointRadius: spec.points ? 4 : 0, pointHitRadius: 8, spanGaps: !!spec.points, tension: 0, yAxisID: s.axis || "y", type: spec.bar && !s.dash ? "bar" : "line", barPercentage: 1, categoryPercentage: 1 }));
      const chart = new Chart(tile.querySelector("canvas"), {
        type: "line", data: { labels: state.months, datasets },
        options: { animation: false, responsive: true, maintainAspectRatio: false, interaction: spec.points ? { mode: "nearest", axis: "x", intersect: false } : { mode: "index", intersect: false },
          plugins: { legend: { display: false }, tooltip: { callbacks: { title: (c) => (spec.titleFn ? spec.titleFn(c[0].dataIndex) : monthLabel(c[0].dataIndex)), label: (c) => `${c.dataset.label}: ${c.raw == null ? "–" : spec.sets[c.datasetIndex].fmt(c.raw)}`, afterBody: (c) => (spec.extra ? spec.extra(c[0].dataIndex) : "") } } },
          scales: {
            x: { ticks: { color: ink2, font: { size: 11 }, autoSkip: false, maxRotation: 0, callback: (_, i) => (i % 12 === 6 ? state.months[i].slice(0, 4) : null) }, grid: { color: (c) => (c.index % 12 === 0 ? line : "transparent"), drawTicks: false } },
            y: { min: spec.yMin == null ? undefined : spec.yMin, max: spec.yMax, ticks: { color: ink2, font: { size: 10 }, maxTicksLimit: 4, callback: (x) => (spec.sets[0].fmt === usd ? usdShort(x) : spec.sets[0].fmt(x).replace(" people", "").replace(" incidents", "").replace(" years", "")) }, grid: { color: line } },
            ...(spec.y2 ? { y2: { position: "right", min: 0, ticks: { color: "#7a7872", font: { size: 10 }, maxTicksLimit: 4, callback: (x) => usdShort(x) }, grid: { display: false } } } : {}),
          },
          onClick: (evt, els, ch) => { const i = Math.round(ch.scales.x.getValueForPixel(evt.x)); if (i >= 0 && i < state.months.length && state.view === "map") setTime(i); } },
        plugins: [{ id: "marks", afterDraw(c) {
          const { ctx, chartArea: a, scales } = c; ctx.save();
          if (spec.refLine != null) { const y = scales.y.getPixelForValue(spec.refLine); ctx.strokeStyle = "#898781"; ctx.setLineDash([3, 3]); ctx.beginPath(); ctx.moveTo(a.left, y); ctx.lineTo(a.right, y); ctx.stroke(); ctx.setLineDash([]); }
          if (state.view === "map") { const x = scales.x.getPixelForValue(state.t); ctx.strokeStyle = ORANGE; ctx.lineWidth = 2; ctx.beginPath(); ctx.moveTo(x, a.top); ctx.lineTo(x, a.bottom); ctx.stroke(); }
          ctx.restore(); } }],
      });
      chart._spec = spec; chart._tile = tile;
      state.natCharts.push(chart);
    }
    updateNational();
  }
  function updateNational() {
    for (const c of state.natCharts) {
      const sp = c._spec, i0 = state.view === "map" ? state.t : lastIdx(sp.sets[0].data);
      const i = sp.points && i0 != null ? lastIdx(sp.sets[0].data.slice(0, i0 + 1)) : i0;   // dot series: latest edition so far
      const val = (s) => (s.data[i] == null ? "no data" : s.fmt(s.data[i]));
      const parts = sp.sets.length === 1 ? [`<b>${val(sp.sets[0])}</b>`] : sp.sets.map((s) => `${s.label}: <b>${val(s)}</b>`);
      const ex = sp.extra ? sp.extra(i) : "";
      c._tile.querySelector(".nt-v").innerHTML = `${i == null ? "" : (sp.titleFn ? sp.titleFn(i) : monthLabel(i)) + ": "}${parts.join(" · ")}${ex ? `<br><span class="muted">${esc(ex)}</span>` : ""}`;
      c.draw();
    }
  }
  const lastIdx = (arr) => { for (let i = arr.length - 1; i >= 0; i--) if (arr[i] != null) return i; return null; };


  // ---------- "How to use" panel ----------
  const HOWTO_HTML = `<button class="howto-close" aria-label="Close">×</button>
  <h2>How to use</h2>
  <details class="ht" open><summary>What this map shows</summary>
  <p>This map lays South Sudan’s counties beneath two kinds of monthly data from 2018 to 2025.</p>
  <ul class="ht-two">
    <li><span class="ht-tag climate">Climate</span>The climate conditions that farming, herding, and flood risk depend on: rainfall, vegetation greenness, land surface temperature, soil moisture, and surface water.</li>
    <li><span class="ht-tag human">People</span>Displacement, armed conflict, humanitarian funding, and UN presence.</li>
  </ul>
  <p>Checkboxes turn each layer on or off, the time slider moves through the record one month at a time, and clicking a county opens its values for the selected month. Users can place a climate layer beneath a human one to understand ecological drivers of socioeconomic pressures.</p>
  </details>
  <details class="ht"><summary>Reading the colours and outlines</summary>
  <div class="ht-row"><span class="ht-ramp"><i style="background:#b2182b"></i><i style="background:#ef8a62"></i><i style="background:#fddbc7"></i><i style="background:#ffffff"></i><i style="background:#d9f0d3"></i><i style="background:#7fbf7b"></i><i style="background:#1b7837"></i></span>
  <p><b>Trend view</b> (the default) colours each county by its typical change per year since 2018, estimated with Sen’s slope. Each month is compared with the same month of 2018, so seasonality does not show up as a trend. Green means the measure went up, red means it went down, and white means little or no change.</p></div>
  <div class="ht-row"><span class="ht-ico">123</span><p><b>Values in original units</b> compare counties against each other for the selected month or season, with no reference to 2018. A county can look quite different in the two views. Its value may be low next to other counties (red here) and still have risen since 2018 (green in the trend view).</p></div>
  <div class="ht-row"><span class="ht-ico">7</span><p>Each of the seven colors covers an equal percentile of the values contained within the overall range of the variable. There may be a skew towards the top of the range, which will be reflected by many districts shaded in that color.</p></div>
  <div class="ht-row"><span class="sig-swatch"></span><p><b>Outlined counties</b> passed the Mann-Kendall significance test for 2018–2025. An outline means the change is very unlikely to be due to pure random chance, indicating that there is an exogenous factor causing the trend.</p></div>
  <div class="ht-row"><span class="lg-hatch"></span><p><b>Black hatching</b> marks counties with no data for that period.</p></div>
  </details>
  <details class="ht"><summary>Understanding the data: implications and utility</summary>
  <p>In few countries do households depend on the seasons as closely as in South Sudan, where most families live off rain-fed farming, cattle, or fishing. A single rainy season, running roughly from April to October, sets when families plant, when herders drive cattle toward the rivers, and when roads wash out for months at a time.</p>
  <p>When the rains arrive late or the floodwater fails to recede, families move; that movement can bring herding and farming communities into competition over scarce land and water. The floods that covered large parts of Jonglei, Unity, and Upper Nile between 2019 and 2022 are the clearest recent example, since many of the families who fled the water had already fled the fighting years before.</p>
  <h4>Climate measures</h4>
  <ul class="ht-list">
    <li><b>Rainfall</b> records how much rain fell in each county during the month, which means the most when set against what usually falls there.</li>
    <li><b>Vegetation greenness (NDVI)</b> follows rainfall with a lag of several weeks. A county that stays brown into the rainy season points to failing pasture and crops, while one that greens unusually early or late points to a shifted season.</li>
    <li><b>Land surface temperature</b> measures how hot the ground itself becomes (not the air temperature a weather station reports), so it serves as a marker of dry-season heat stress on crops, livestock, and people.</li>
    <li><b>Soil moisture</b> shows how much water the ground already holds. Saturated soil cannot absorb the next storm, which is why heavy rain on already-wet ground in the Sudd produces floods that last for months rather than days.</li>
    <li><b>Surface water</b> maps where standing water covers the land, capturing both the seasonal swell of the Sudd wetland and the floods that spread beyond it.</li>
    <li><b>Maximum temperatures</b> (day temperatures) are particularly important for assessing heat stress, wildfire risk, and drought conditions. Heat stress is particularly relevant in urban areas where the heat island effect can intensify impacts.</li>
    <li><b>Minimum temperatures</b> (night temperatures) are critical for human health (e.g., sleep quality), animal health, agricultural productivity (e.g., frost risk), and ecosystem stability.</li>
    <li><b>Precipitation patterns</b> are broadly organized by climatic zones and rain fronts, but at finer scales, they are influenced by topography, distance from the coast, prevailing winds, and local convection processes.</li>
  </ul>
  <h4>People measures</h4>
  <ul class="ht-list">
    <li><b>The displacement layer</b> counts internally displaced people and returnees in each county using figures from IOM’s Displacement Tracking Matrix. IOM collects these figures in survey rounds a few months apart, so the value for any given month reflects the most recent round rather than a fresh count.</li>
    <li><b>The conflict layer</b> records reported incidents of political and communal violence, including the cattle raids and revenge attacks that tend to rise in the dry season.</li>
    <li><b>The funding layer</b> reports what donors committed to the humanitarian response.</li>
    <li><b>The UN presence layer</b> marks where UNMISS and UN agencies operated, which shows where international actors could see and respond to a crisis.</li>
  </ul>
  </details>
  <details class="ht"><summary>Data caveats</summary>
  <ul class="ht-list">
    <li><b>Displacement</b> coverage is thin in the earliest months, since IOM’s tracking covered fewer than 50 counties in 2018 and reached nearly every county only in early 2019; a county shown with black hatching lacks data for that month, which is different from reporting zero displaced people.</li>
    <li><b>Conflict</b> data come largely from media and partner reports, so remote counties are likely undercounted, while counties near UN bases may appear more violent simply because more observers were there to document what happened.</li>
    <li><b>County-level averages</b> also flatten local variation; a single rainfall value can conceal a flooded river corridor beside dry uplands.</li>
    <li><b>Boundaries.</b> Finally, South Sudan redrew its states in 2015 and again in 2017 before returning to ten states in 2020. The map uses one fixed set of county boundaries throughout, so figures that sources reported under the interim state names have been matched to those counties.</li>
  </ul>
  </details>`;
  function openHowto(open) {
    const el = $("#howto"); el.hidden = !open; $("#howto-toggle").setAttribute("aria-expanded", open);
    if (open && !el.innerHTML) { el.innerHTML = HOWTO_HTML; el.querySelector(".howto-close").onclick = () => openHowto(false); }
  }
  function setSidebar(open) {
    $("#app").classList.toggle("side-hidden", !open); $("#side-show").hidden = open;
    setTimeout(() => map.invalidateSize(), 260);
  }
  function renderModeHint() {
    const el = $("#mode-hint"); if (!el) return;
    el.innerHTML = state.mode === "trend"
      ? `Each county is compared with its own 2018 levels, month by month.<span class="mh-key"><span><i style="background:#1b7837"></i>rose after 2018</span><span><i style="background:#b2182b"></i>fell</span><span><i style="background:#fff"></i>little change</span></span>`
      : `Colours compare counties with each other in the selected period, not with 2018.<span class="mh-key"><span><i style="background:#b2182b"></i>lower</span><span><i style="background:#1b7837"></i>higher</span></span>`;
  }
  // ---------- views ----------
  function openNat(open) {
    state.natOpen = open;
    const d = $("#nat-drawer"); d.hidden = !open; $("#nat-toggle").setAttribute("aria-expanded", open);
    $("#nat-toggle").textContent = open ? "Hide national trends" : "See national trends in aid and socioeconomic outcomes";
    if (open && $("#national").parentElement !== $("#nat-slot")) { $("#nat-slot").appendChild($("#national")); renderNational(); }
    setTimeout(() => map.invalidateSize(), 60);
    writeHash();
  }
  function setView(view) {
    state.view = view; document.body.dataset.view = view;
    $("#landing").hidden = view !== "landing"; $("#app").hidden = view !== "map";
    if (view === "landing") { if ($("#national").parentElement !== $("#national-home")) { $("#national-home").appendChild($("#national")); renderNational(); } else updateNational(); window.scrollTo(0, 0); }
    else { openNat(!!state.natOpen); setTimeout(() => { map.invalidateSize(); if (!state._fitted) { fitMap(); state._fitted = true; } }, 30); updateNational(); }
    writeHash();
  }
  function renderWalkthrough(w) {
    const el = $("#walkthrough"); if (!el || !w || !w.steps) return;
    el.innerHTML = `<h3>${esc(w.title)}</h3>${w.subtitle ? `<p class="wt-sub">${esc(w.subtitle)}</p>` : ""}<p class="wt-intro">${w.intro}</p><ol class="wt-steps">${w.steps.map((st, k) => `<li><h4>${esc(st.heading)}</h4><p>${st.text}</p>${st.view ? `<button class="wt-go" data-i="${k}">Show me on the map →</button>` : ""}</li>`).join("")}</ol>${w.caveat ? `<p class="caveat">${w.caveat}</p>` : ""}`;
    el.querySelectorAll(".wt-go").forEach((b) => (b.onclick = async () => { setView("map"); await applyView(w.steps[+b.dataset.i].view); }));
  }
  const fitMap = () => countyLayer && map.fitBounds(countyLayer.getBounds(), { padding: [8, 8] });

  // ---------- time ----------
  function setTime(i) {
    state.t = i;
    $("#time").value = i;
    $("#time-label").textContent = windowLabel(i);
    refreshCounties(); updateRasters(); refreshPoints(); drawFlows(); updateNational(); renderContext();
    renderLegend();
    if (state.selected) renderDetail();
    clearTimeout(state._hashT); state._hashT = setTimeout(writeHash, 400);
  }
  function togglePlay() {
    if (state.timer) { clearInterval(state.timer); state.timer = null; $("#play").textContent = "▶"; $("#play").setAttribute("aria-label", "Play"); return; }
    $("#play").textContent = "❚❚"; $("#play").setAttribute("aria-label", "Pause");
    state.timer = setInterval(() => { const idx = windowIdx(state.t); let next = idx[idx.length - 1] + 1; if (next >= state.months.length) next = 0; setTime(next); }, 1000);
  }

  // ---------- boot ----------
  async function boot() {
    const [vj, counties, layers, curated] = await Promise.all([
      fetchJSON("data/variables.json"), fetchJSON("data/counties.geojson"), fetchJSON("data/layers.json").catch(() => ({ points: [], rasters: [] })), fetchJSON("data/curated.json"),
    ]);
    state.curated = curated;
    state.months = vj.months;
    if (vj.bundle) state.bundle = fetchJSON(vj.bundle);
    vj.variables.forEach((v) => (state.allVars[v.id] = v));
    state.vars = curated.variables.filter((c) => state.allVars[c.id]).map((c) => ({ ...state.allVars[c.id], label: c.label, group: c.group, category: c.category }));
    state.vars.forEach((v) => (state.varById[v.id] = v));
    state.rasters = layers.rasters || [];
    state.rasters.forEach((r) => (state.rasterByKey[r.key] = r));
    state.points = curated.points.map((k) => (layers.points || []).find((p) => p.key === k)).filter(Boolean);
    state.countiesGJ = counties;

    fetchJSON("data/basemap_context.json").then(drawBasemapContext).catch((e) => console.warn("basemap context", e));
    fetchJSON("data/trends.json").then((t) => { state.trends = t; state.vars.forEach((v) => (v._bins = null)); refreshCounties(); renderLegend(); }).catch(() => {});
    fetchJSON("data/stories.json").then((st) => { state.stories = st.stories || st; renderStories(); renderVarList(); }).catch(() => {});
    fetchJSON("data/walkthrough.json").then(renderWalkthrough).catch(() => {});
    fetchJSON("data/landing_text.json").then((lt) => { if (lt.exec_last_para && $("#exec-last")) $("#exec-last").innerHTML = lt.exec_last_para; }).catch(() => {});
    fetchJSON("data/profiles.json").then((pj) => (state.profiles = pj)).catch(() => {});
    fetchJSON("data/context_timeline.json").then((c) => { state.context = c; renderContext(); }).catch(() => { state.context = { periods: [] }; renderContext(); });
    fetchJSON("data/context_events.json").then((ce) => { state.events = (ce.events || ce || []).filter((e) => e.date); renderContext(); }).catch(() => {});
    SPARKS.forEach((sp) => ensureSeries(sp.id).catch(() => {}));
    fetchJSON("data/flows.json").then((f) => { state.flows = f; renderFlowControls(); drawFlows(); }).catch((e) => console.warn("no flows", e));
    $("#time").max = state.months.length - 1;

    countyLayer = L.geoJSON(counties, {
      style: styleCounty,
      onEachFeature: (f, l) => {
        l.on("mousemove", (e) => showHover(f.properties, e.originalEvent));
        l.on("click", () => {
          const id = f.properties.district_id;
          if (state.comparing && state.selected && id !== state.selected) { state.compare = [...(state.compare || []).filter((c) => c !== id), id].slice(-3); state.comparing = false; renderDetail().then(() => showTab("county")); return; }
          state.comparing = false; state.selected = id; state.compare = []; refreshCounties(); renderDetail().then(() => showTab("county")); writeHash();
        });
        l.on("mouseover", () => l.setStyle({ weight: 2.5, color: "#0b0b0b" }));
        l.on("mouseout", () => { countyLayer.resetStyle(l); hideHover(); });
      },
    }).addTo(map);
    map.fitBounds(countyLayer.getBounds(), { padding: [8, 8] }); townsVisible();

    $("#howto-toggle").onclick = () => openHowto($("#howto").hidden);
    $("#side-hide").onclick = () => setSidebar(false);
    $("#side-show").onclick = () => setSidebar(true);
    renderModeHint();
    $("#mode").onchange = (e) => { state.mode = e.target.value; renderModeHint(); refreshCounties(); updateRasters(); renderLegend(); if (state.selected) renderDetail(); writeHash(); };
    $("#agg").onchange = (e) => { state.agg = e.target.value; setTime(state.t); renderLegend(); };
    $("#time").oninput = (e) => setTime(+e.target.value);
    $("#play").onclick = togglePlay;
    $("#filter").oninput = renderVarList;
    $("#detail-close").onclick = () => { state.selected = null; state.compare = []; state.comparing = false; refreshCounties(); renderDetail(); $("#tab-county").textContent = "Click on a county for more detailed info"; writeHash(); };
    $("#tab-context").onclick = () => showTab("context");
    $("#tab-county").onclick = () => state.selected && showTab("county");
    $("#nat-toggle").onclick = () => openNat(!state.natOpen);
    $("#nat-close").onclick = () => openNat(false);
    $("#back-home").onclick = () => setView("landing");
    document.querySelectorAll("[data-open-map]").forEach((b) => (b.onclick = () => setView("map")));

    renderPointList(); renderBgList(); state.myStory = loadMyStory(); renderMyStory();
    const H = readHash();
    let tStart = state.months.indexOf("2022-09"); if (tStart < 0) tStart = state.months.length - 1;
    let first = null;   // open with nothing ticked: background, water and places only
    if (H) {
      const list = (k) => (H.get(k) || "").split(",").filter(Boolean);
      if (H.get("m") && [...$("#mode").options].some((o) => o.value === H.get("m"))) { state.mode = H.get("m"); $("#mode").value = state.mode; renderModeHint(); }
      if (H.get("a")) { state.agg = H.get("a"); $("#agg").value = state.agg; }
      if (H.get("s")) state.selected = H.get("s");
      if (H.get("fo") === "1") state.flowOn = true;
      if (H.get("fg")) state.flowGroup = H.get("fg");
      if (H.has("bg")) { state.bgOn = new Set(list("bg")); renderBgList(); }
      state.natOpen = H.get("n") === "1";
      const ti = state.months.indexOf(H.get("t")); if (ti >= 0) tStart = ti;
      for (const k of list("p")) { const p = state.points.find((x) => x.key === k); if (p) { await loadPoints(p); const cb = document.getElementById(`p-${k}`); if (cb) cb.checked = true; } }
      if (H.has("v")) first = state.varById[H.get("v")] ? H.get("v") : null;
      state.chartVars = list("cv").filter((id) => state.varById[id]);
    }
    state.t = tStart;
    await setColorBy(first);
    await applyBackground();
    if (state.selected) renderDetail();
    setTime(tStart);
    await renderNational().catch((e) => console.warn("national", e));
    setView(H && H.get("view") === "map" ? "map" : "landing");
  }
  boot().catch((e) => { console.error(e); const el = $("#nat-charts"); if (el) el.innerHTML = `<p class="empty">Could not load data: ${esc(e.message)}</p>`; });
})();
