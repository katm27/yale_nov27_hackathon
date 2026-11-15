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
  const ORANGE = "#eb6834";

  const state = {
    months: [], vars: [], varById: {}, allVars: {}, series: {}, colorBy: null,
    mode: "trend", agg: "month", t: 0, selected: null, gridOn: true,
    rasters: [], rasterByKey: {}, rasterLayers: {}, points: [], pointLayers: {}, bgOn: new Set(["water"]),
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
    if (m === 12) return { key: `${y + 1}-dry`, label: `Dry season ${y}/${String(y + 1).slice(2)}` };
    if (m <= 3) return { key: `${y}-dry`, label: `Dry season ${y - 1}/${String(y).slice(2)}` };
    if (m <= 6) return { key: `${y}-early`, label: `Early rains (Apr–Jun) ${y}` };
    if (m <= 9) return { key: `${y}-main`, label: `Main rains (Jul–Sep) ${y}` };
    return { key: `${y}-late`, label: `Late season (Oct–Nov) ${y}` };
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
    if (mode !== "index_month" || isStatic(v) || isCategorical(v)) {
      if (v.aggregate === "sum" && state.agg !== "month") return wvals.reduce((a, x) => a + (x != null && isFinite(x) ? x : 0), 0);
      return isShareUnits(v) ? raw * 100 : raw;
    }
    const base = mean(baselineWindowIdx(i, v.baseline_year || 2018).map((j) => arr[j]));
    if (base == null) return null;
    if (v.index_ok === false) return isShareUnits(v) ? (raw - base) * 100 : raw - base;
    if (Math.abs(base) < 1e-9) return null;
    return raw / base;
  }
  const centered = (v) => (state.mode === "trend" && usesTrend(v)) || (state.mode === "index_month" && !isStatic(v) && !isCategorical(v));
  const isRatio = (v) => state.mode === "index_month" && v.index_ok !== false && !isStatic(v) && !isCategorical(v);

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
  const map = L.map("map", { zoomControl: true, minZoom: 5, maxZoom: 12, zoomSnap: 0.25 });
  const baseLayers = {
    "Terrain": L.tileLayer("https://server.arcgisonline.com/ArcGIS/rest/services/World_Terrain_Base/MapServer/tile/{z}/{y}/{x}", { attribution: "Terrain: Esri, USGS, NOAA · borders: Natural Earth", maxZoom: 13 }),
    "Satellite": L.tileLayer("https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}", { attribution: "Esri, Maxar, Earthstar Geographics" }),
    "OpenStreetMap (detailed)": L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", { attribution: "© OpenStreetMap contributors", maxZoom: 19 }),
  };
  baseLayers.Terrain.addTo(map);
  L.control.layers(baseLayers, null, { position: "topleft" }).addTo(map);
  map.createPane("mask").style.zIndex = 300;        // greys out terrain outside South Sudan
  map.createPane("bg").style.zIndex = 330;          // background layers (soil type, cattle)
  map.createPane("rasters").style.zIndex = 440;
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
    L.polygon([outer, ...holes], { pane: "mask", stroke: false, fillColor: css("--maskfill") || "#efeee9", fillOpacity: 0.88, interactive: false }).addTo(map);
    L.geoJSON(ctx.neighbors, { pane: "mask", interactive: false, style: { color: "#7d7b74", weight: 1.2, fill: false } }).addTo(map);
    L.geoJSON(ctx.ssd, { pane: "labels", interactive: false, style: { color: "#3b3a36", weight: 1.8, fill: false } }).addTo(map);
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
    if (usesTrend(v) && tr && tr[T_SIG] && !selected) { st.color = "#1d1c1a"; st.weight = 2.4; }
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
    if (state.mode === "index_month" && !isStatic(v)) {
      if (v.index_ok === false) return `${signed(x, 2)} ${isPctUnits(v) || isShareUnits(v) ? "percentage points" : unitsShort(v)} vs same ${state.agg === "month" ? "month" : state.agg === "season" ? "season" : "year"} of ${v.baseline_year || 2018}`;
      return `${fmt(x, 2)}× the level in the same ${state.agg === "month" ? "month" : state.agg === "season" ? "season" : "year"} of ${v.baseline_year || 2018}`;
    }
    return `${fmt(x)} ${unitsShort(v)}`;
  }
  const SOIL = { 0: "Acrisols (weathered, acidic)", 6: "Cambisols (young soils)", 10: "Ferralsols (deeply weathered)", 12: "Gleysols (waterlogged)", 18: "Luvisols (clay-enriched subsoil)", 29: "Vertisols (cracking clay, floods easily)" };
  const soilName = (x) => SOIL[Math.round(x)] || `soil class ${Math.round(x)}`;

  // ---------- hover tooltip: selected measure + stacked mini-charts on ONE shared year axis ----------
  const SPARKS = [
    { id: "et_ind_total", label: "People displaced or returning (IOM)", color: "#d7301f", units: "people" },
    { id: "fts_us_gov_funding_month_usd", label: "US humanitarian funding, national", color: "#2a78d6", units: "US$", money: true },
    { id: "surface_water_pct", label: "Surface water (% of county)", color: "#0a8f86", units: "%" },
    { id: "spei3", label: "Drought index (SPEI; below 0 = drier)", color: "#b4461b", units: "", zero: true },
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
      const lab = state.mode === "trend" && usesTrend(v) ? `Trend 2018→${trendYear()} (Sen’s slope)` : windowLabel(state.t);
      line = `<div class="tt-var"><span class="muted">${esc(v.label)}</span><br>${lab}: <b>${describe(v, x, p.district_id)}</b></div>`;
    }
    return `<div class="tt"><div class="tt-h"><b>${esc(p.name)}</b> <span class="muted">· ${esc(p.admin1)}</span></div>${line}${sparkPanel(p.district_id)}<div class="tt-foot">Orange line = ${monthLabel(state.t)} · click for the county profile</div></div>`;
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
    const signedOr = (z) => (b.centered ? signed(z, 2) : fmt(z, 3));
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
  function renderLegend() {
    const el = $("#legend");
    const v = state.varById[state.colorBy];
    let html = "";
    if (v) {
      const r = activeRaster(v), trendOn = state.mode === "trend" && usesTrend(v);
      const what = trendOn ? `Trend, 2018→${trendYear()}: ${slopeUnits(v)}` : isCategorical(v) ? "Main soil type" : state.mode === "index_month" && !isStatic(v) ? (v.index_ok === false ? `Difference from the same ${state.agg === "month" ? "month" : "period"} of ${v.baseline_year || 2018}` : `Ratio to the same ${state.agg === "month" ? "month" : "period"} of ${v.baseline_year || 2018}`) : `${windowLabel(state.t)}: ${unitsShort(v)}`;
      html += `<div class="lg-title">${esc(v.label)}</div><div class="lg-sub">${esc(what)}${r ? " · satellite grid" : ""}</div>`;
      if (isCategorical(v)) {
        html += `<div class="lg-bins">${Object.keys(SOIL).map((k, i) => `<div><i style="background:${CATEGORICAL[i]}"></i>${SOIL[k]}</div>`).join("")}</div>`;
      } else {
        const labs = r ? rasterBinLabels(r) : binLabels(v);
        const rows = PAL7.map((c, k) => ({ c, lab: labs[k] })).reverse().filter((x) => x.lab);
        html += `<div class="lg-bins">${rows.map((x) => `<div><i style="background:${x.c}"></i>${esc(x.lab)}</div>`).join("")}<div><i class="nd"></i>No data</div></div>`;
        const mid = trendOn || (state.mode === "index_month" && !isStatic(v)) ? "White = little or no change. " : "";
        html += `<div class="lg-note">${trendOn ? "Green = increase, red = decrease. " : "Green = higher, red = lower. "}${mid}Colours show direction, not good or bad.</div>`;
        html += `<div class="lg-note">${r ? "Grid colours use 7 equal steps of the grid’s range. Hover a county for its own value." : `Each colour holds about one-seventh of the county values for this measure${trendOn || state.mode === "index_month" ? ", split evenly between rises and falls" : ""}.`}</div>`;
        if (trendOn && state.trends && state.trends[v.id]) {
          const nSig = Object.values(state.trends[v.id]).filter((t) => t[T_SIG]).length;
          html += `<div class="lg-note"><span class="sig-swatch"></span> Thick dark outline: the 2018–2025 trend is statistically significant (${nSig} ${nSig === 1 ? "county" : "counties"}).</div>`;
        }
      }
      if (v.caution) html += `<details class="lg-more"><summary>Caveats and source</summary><p>${esc(v.caution)}</p><p>Source: ${esc(v.source || "–")}${v.native_resolution ? ` · ${esc(v.native_resolution)}` : ""}</p></details>`;
      else html += `<details class="lg-more"><summary>Source</summary><p>${esc(v.source || "–")}${v.native_resolution ? ` · ${esc(v.native_resolution)}` : ""}</p></details>`;
    }
    if (state.flowOn) {
      const G = state.curated.flow_groups;
      const shown = state.flowGroup === "all" ? Object.keys(G) : [state.flowGroup];
      html += `<div class="lg-flows"><div class="lg-title">Migration arrows (IOM)</div>${shown.map((k) => `<div><i class="arrow" style="background:${G[k].color}"></i>${esc(G[k].label)}</div>`).join("")}<div class="lg-note">From the county people left to where they arrived. Thicker = more people.</div></div>`;
    }
    const bgHtml = [...state.bgOn].filter((k) => k !== "water").map((k) => bgLegend(k)).join("");
    html += bgHtml;
    el.innerHTML = html ? `<button class="lg-min" aria-expanded="${!state.legendMin}" title="${state.legendMin ? "Show key" : "Hide key"}">${state.legendMin ? "Key ▸" : "–"}</button><div class="lg-body">${html}</div>` : "";
    el.classList.toggle("min", !!state.legendMin);
    const mb = el.querySelector(".lg-min"); if (mb) mb.onclick = () => { state.legendMin = !state.legendMin; renderLegend(); };
    el.hidden = !html;
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
  function renderVarList() {
    const q = $("#filter").value.trim().toLowerCase();
    const el = $("#var-list"); el.innerHTML = "";
    const none = document.createElement("label"); none.className = "var-row";
    none.innerHTML = `<input type="radio" name="var" ${state.colorBy ? "" : "checked"}> <span>No measure (background and points only)</span>`;
    none.querySelector("input").onchange = () => setColorBy(null);
    if (!q) el.appendChild(none);
    let lastCat = null, lastGroup = null;
    for (const v of state.vars) {
      const hay = `${v.label} ${v.group} ${v.plain || ""} ${(v.synonyms || []).join(" ")}`.toLowerCase();
      if (q && !q.split(/\s+/).every((w) => hay.includes(w))) continue;
      if (v.category !== lastCat) { el.insertAdjacentHTML("beforeend", `<div class="cat-title">${v.category === "climate" ? "Climate and environment" : "People, conflict and aid"}</div>`); lastCat = v.category; lastGroup = null; }
      if (v.group !== lastGroup) { el.insertAdjacentHTML("beforeend", `<div class="group-title">${esc(v.group)}</div>`); lastGroup = v.group; }
      const on = state.colorBy === v.id;
      const cov = isStatic(v) ? "single snapshot" : `${v.first_period.slice(0, 4)}–${v.last_period.slice(0, 4)}${v.temporal && v.temporal !== "monthly" ? ", " + v.temporal.replace(/\s*\(.*\)/, "") : ""}`;
      const row = document.createElement("div"); row.className = `var-item${on ? " on" : ""}`;
      row.innerHTML = `<label class="var-row"><input type="radio" name="var" ${on ? "checked" : ""}> <span>${esc(v.label)} ${state.curated.rasters[v.id] ? '<span class="grid-ico" title="Satellite grid available">▦</span>' : ""}<span class="meta"> · ${cov}</span></span></label>
        ${on ? `<div class="var-plain">${esc(plainOf(v))}${v.how_to_read ? ` <i>${esc(v.how_to_read)}</i>` : ""}</div>` : ""}`;
      row.querySelector("input").onchange = () => setColorBy(v.id);
      el.appendChild(row);
    }
    if (q && !el.children.length) el.innerHTML = `<p class="empty">Nothing matches “${esc(q)}”. Try: flood, rain, heat, fire, fighting, hunger, aid.</p>`;
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
    if (id) await ensureSeries(id);
    renderVarList(); refreshCounties(); updateRasters(); renderLegend(); if (state.selected) renderDetail(); writeHash();
  }

  // ---------- rasters ----------
  function activeRaster(v) {
    if (!v || !state.gridOn) return null;
    const key = state.curated.rasters[v.id]; if (!key) return null;
    if (state.mode === "trend" && usesTrend(v)) return state.rasterByKey[`${key}_trend`] || null;
    if (state.mode === "index_month") return null;   // grids hold values, not change vs 2018
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
    const wl = state.rasters.filter((x) => x.base_layer).flatMap((x) => x.legend || []).filter((x, i, a) => a.findIndex((y) => y[1] === x[1]) === i);
    if (wl.length) el.insertAdjacentHTML("beforeend", `<div class="hint wl-key">${wl.map(([c, l]) => `<span class="wl"><i style="background:${c}"></i>${esc(l)}</span>`).join("")}</div>`);
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
      $(`#pl-${p.key}`).innerHTML = `<div class="eth-key">${Object.entries(ETHNIC_COLORS).map(([g, c]) => `<span><i style="background:${c}"></i>${esc(g)}</span>`).join("")}</div><p class="hint">Settlement areas from GeoEPR 2021 (ETH Zurich); areas overlap where groups live together. Click an area for its political-power status. Covers the ten groups coded by the Ethnic Power Relations dataset only.</p>`;
    } else {
      $(`#pl-${p.key}`).innerHTML = p.plain && typeof p.plain === "string" ? `<p class="hint">${esc(p.plain.split(/(?<=\.)\s/)[0])} Hollow markers = closed, damaged or not working.</p>` : "";
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
        const rows = Object.entries(pr).filter(([, val]) => val !== null && val !== "" && typeof val !== "object").slice(0, 12)
          .map(([k, val]) => `<tr><td class="muted">${esc(k)}</td><td>${esc(String(val).slice(0, 120))}</td></tr>`).join("");
        const head = pr.name || pr.facility_name || pr.site_name || pr.title || "";
        const status = pr.status ? `<div><b>Status:</b> ${esc(pr.status)}</div>` : "";
        const when = pr.date ? `<div><b>Date:</b> ${esc(String(pr.date).slice(0, 10))}</div>` : (pr.valid_from || pr.valid_to) ? `<div><b>Period:</b> ${pr.valid_from ? esc(String(pr.valid_from).slice(0, 7)) : "before 2018"} → ${pr.valid_to ? esc(String(pr.valid_to).slice(0, 7)) : "2025+"}</div>` : "";
        const ev = pr.evidence || pr.date_basis ? `<div class="hint">Evidence: ${esc(String(pr.evidence || pr.date_basis).slice(0, 220))}</div>` : "";
        l.bindPopup(`<b>${esc(p.label)}</b>${head ? `<div>${esc(head)}</div>` : ""}${status}${when}${ev}<details><summary>All fields</summary><table>${rows}</table></details>`);
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
    if (st) st.innerHTML = !state.flowOn ? "" : !any ? `<span class="none">No IOM Event Tracking data for ${windowLabel(state.t)}. Records start in late 2019; most months from 2020 on are covered.</span>` : `${[...agg.values()].reduce((a, b) => a + b, 0).toLocaleString("en-US")} people moving in ${windowLabel(state.t)} (top ${Math.min(agg.size, 150)} routes shown).`;
    if (!state.flowOn) return;
    const list = [...agg.entries()].map(([k, n]) => { const [a, b, g] = k.split("|"); return { a: +a, b: +b, g, n }; }).sort((x, y) => y.n - x.n).slice(0, 150);
    const max = Math.max(1, ...list.map((f) => f.n));
    state.flowLayer = L.layerGroup().addTo(map);
    ensureArrowDefs();
    const crossings = new Map();
    const G = state.curated.flow_groups, gi = Object.keys(G);
    for (const f of list.slice().reverse()) {   // biggest drawn last = on top
      const A = F.nodes[f.a], B = F.nodes[f.b], g = G[f.g];
      const w = Math.max(2.2, Math.min(15, 14 * Math.sqrt(f.n / max)));
      if (!String(A[3]).startsWith("SS")) crossings.set(f.a, (crossings.get(f.a) || 0) + f.n);
      const pts = bezier(A, B, 0.12 + 0.05 * gi.indexOf(f.g));
      L.polyline(pts, { renderer: flowRenderer, pane: "flows", color: "#ffffff", weight: w + 3.5, opacity: 0.9, lineCap: "round", interactive: false }).addTo(state.flowLayer);
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
      <p class="hint">IOM Event Tracking: people newly displaced or returning, drawn from the county they left to the county where they arrived. Cross-border arrivals start at the border crossing (white circle).</p>
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
  function renderContext() {
    const el = $("#context"); if (!el) return;
    const ym = state.months[state.t];
    const hits = periodFor(ym);
    const evs = (state.events || []).filter((e) => e.date.slice(0, 7) === ym);
    if (!hits.length && !evs.length) { el.innerHTML = `<p class="hint">${state.context ? "No summary for this month." : "Loading…"}</p>`; return; }
    const range = (p) => (p.from === p.to ? monthLabel(state.months.indexOf(p.from)) : `${monthLabel(state.months.indexOf(p.from))} – ${monthLabel(state.months.indexOf(p.to))}`);
    let html = `<div class="ctx-when">${monthLabel(state.t)}</div>`;
    for (const p of hits) {
      html += `<article class="ctx"><div class="ctx-range">${esc(range(p))}</div><h3>${esc(p.title)}</h3><p>${esc(p.text)}</p>${p.links ? `<p class="ctx-links"><b>In the charts:</b> ${esc(p.links)}</p>` : ""}
        ${p.sources && p.sources.length ? `<p class="ctx-src">Sources: ${p.sources.map((s, i) => `<a href="${esc(s.url)}" target="_blank" rel="noopener">${esc(s.label || `[${i + 1}]`)}</a>`).join(" · ")}</p>` : ""}</article>`;
    }
    if (evs.length) html += `<div class="ctx-evs"><h3>Also recorded this month</h3><ul>${evs.map((e) => `<li>${esc(e.title)}${e.source_url ? ` <a href="${esc(e.source_url)}" target="_blank" rel="noopener">source</a>` : ""}</li>`).join("")}</ul></div>`;
    el.innerHTML = html;
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
    if (isStatic(v) || isCategorical(v)) return "A single snapshot, so there is no trend over time.";
    const tr = trendOf(v.id, cid); if (!tr || tr[T_SEN] == null) return "Too little data to estimate a trend for this county.";
    const x = trendNative(v, cid, 2025), sig = tr[T_SIG];
    const strength = sig ? "This trend is statistically significant (unlikely to be chance, after allowing for testing all 79 counties)." : tr[T_P] != null && tr[T_P] < 0.05 ? "This trend is suggestive but not significant once all 79 counties are tested together." : "This change is not statistically significant: it could be chance.";
    return `Trend 2018–2025: <b>${signed(x, 2)} ${slopeUnits(v)}</b> (Sen’s slope). ${strength}`;
  }
  const countyProps = (cid) => { const l = countyLayer.getLayers().find((x) => x.feature.properties.district_id === cid); return l ? l.feature.properties : { name: cid, admin1: "" }; };
  async function renderDetail() {
    const cid = state.selected;
    $("#tab-county").disabled = !cid;
    if (!cid) { showTab("context"); return; }
    const P = countyProps(cid), v = state.varById[state.colorBy];
    $("#tab-county").textContent = `${P.name} County`;
    $("#detail-title").textContent = `${P.name} County`;
    $("#detail-sub").textContent = `${P.admin1} State`;
    const pr = state.profiles && state.profiles[cid];
    let html = "";
    if (pr) {
      html += `<div class="profile">${pr.livelihood_zone && pr.livelihood_zone.name ? `<p class="pf-lz">${esc(pr.livelihood_zone.name)}</p>` : ""}
        ${["livelihoods", "history", "conflict_impact"].map((k) => (pr[k] ? `<p><b>${{ livelihoods: "Livelihoods", history: "History", conflict_impact: "Conflict impact" }[k]}.</b> ${esc(pr[k])}</p>` : "")).join("")}
        ${pr.sources && pr.sources.length ? `<p class="hint">Sources: ${pr.sources.slice(0, 4).map((u, i) => `<a href="${esc(u)}" target="_blank" rel="noopener">[${i + 1}]</a>`).join(" ")}</p>` : ""}</div>`;
    }
    html += `<div id="detail-chart"></div><div class="detail-actions"><button id="btn-csv">Download this data (CSV)</button><button id="btn-link">Copy link to this view</button></div>`;
    $("#detail-body").innerHTML = html;
    $("#btn-csv").onclick = downloadCSV;
    $("#btn-link").onclick = () => { writeHash(); copyText(location.href, "Link copied."); };
    state.charts.forEach((c) => c.destroy()); state.charts = [];
    const box = $("#detail-chart");
    if (!v) { box.innerHTML = `<p class="empty">Choose a measure in the left panel to see this county’s history.</p>`; return; }
    await ensureSeries(v.id);
    const now = valueAt(v, cid, state.t, "raw");
    box.innerHTML = `<div class="chart-block"><h3>${esc(v.label)}</h3><div class="var-plain">${esc(plainOf(v))}</div>
      <p class="now">${windowLabel(state.t)}: <b>${isCategorical(v) ? soilName(now) : now == null ? "no data" : `${fmt(now)} ${esc(unitsShort(v))}`}</b></p>
      <p class="trend-s">${trendSentence(v, cid)}</p>${v.caution ? `<p class="caution">${esc(v.caution)}</p>` : ""}${isStatic(v) ? "" : "<canvas></canvas>"}</div>`;
    if (isStatic(v)) return;
    const S = rawWindowSeries(v, cid), cur = S.keys.indexOf(windowKey(state.t));
    const baseVals = S.firstIdx.map((i) => (state.agg === "year" ? null : mean(baselineWindowIdx(i, v.baseline_year || 2018).map((q) => ((state.series[v.id] || {})[cid] || [])[q]))));
    const ds = [{ label: P.name, data: S.vals, borderColor: "#2a78d6", borderWidth: 2, pointRadius: 0, pointHitRadius: 8, tension: 0.15, spanGaps: false }];
    if (v.temporal === "monthly" && baseVals.some((x) => x != null)) ds.push({ label: `Same ${state.agg === "month" ? "month" : "season"} in ${v.baseline_year || 2018}`, data: baseVals.map((x) => (x != null && isShareUnits(v) ? x * 100 : x)), borderColor: "#898781", borderDash: [4, 3], borderWidth: 1.2, pointRadius: 0 });
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
    catch (e) { copyText(csv, "Download blocked here; the CSV was copied to your clipboard instead."); }
  }
  function copyText(txt, msg) {
    const done = () => toast(msg), fail = () => { const ta = document.createElement("textarea"); ta.value = txt; document.body.appendChild(ta); ta.select(); try { document.execCommand("copy"); done(); } catch (e) { toast("Copying is not allowed here."); } ta.remove(); };
    if (navigator.clipboard && navigator.clipboard.writeText) navigator.clipboard.writeText(txt).then(done, fail); else fail();
  }
  function toast(msg) { let t = $("#toast"); if (!t) { t = document.createElement("div"); t.id = "toast"; document.body.appendChild(t); } t.textContent = msg; t.className = "show"; setTimeout(() => (t.className = ""), 2600); }
  function writeHash() {
    if (!state.months.length) return;
    const h = new URLSearchParams({ view: state.view, m: state.mode, a: state.agg, t: state.months[state.t], v: state.colorBy || "", s: state.selected || "",
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
      sets: [{ data: mul(cov, 100), color: "#2a78d6", label: "% of requested amount received", fmt: (x) => `${fmt(x, 2)}%` }], yMin: 0, yMax: 100,
      extra: (i) => (fund && req && fund[i] != null ? `${usd(fund[i])} received of ${usd(req[i])} requested` : "") });
    const disb = A("usaid_disbursed_month_usd"), obl = A("usaid_obligated_month_usd");
    if (disb && obl) {
      const yd = yearly(disb, "sum"), yo = yearly(obl, "sum"), pct = yd.map((x, i) => (x != null && yo[i] ? (100 * x) / yo[i] : null));
      specs.push({ title: "USAID aid paid out, as a % of aid committed that year", sub: "Calendar-year totals (ForeignAssistance.gov). Can pass 100% when money committed in earlier years is paid out.", step: true,
        sets: [{ data: pct, color: "#2a78d6", label: "Paid out as % of committed", fmt: (x) => `${fmt(x, 3)}%` }], yMin: 0, refLine: 100,
        extra: (i) => (yd[i] != null ? `${yearOf(i)}: ${usd(yd[i])} paid out · ${usd(yo[i])} committed` : "") });
    }
    const usm = A("fts_us_gov_funding_month_usd");
    if (usm) specs.push({ title: "US government humanitarian funding, by month", sub: "Funding decisions recorded by OCHA’s Financial Tracking Service (US$).", bar: true,
      sets: [{ data: usm, color: "#2a78d6", label: "US$ per month", fmt: usd }], yMin: 0 });
    const share = A("fts_us_share_year"), usy = A("fts_us_gov_funding_year_usd");
    if (share && usy) specs.push({ title: "US share of all humanitarian funding (solid) and US amount per year (dashed)", sub: "OCHA Financial Tracking Service, by calendar year.", step: true,
      sets: [{ data: mul(share, 100), color: "#2a78d6", label: "US share of all humanitarian funding", fmt: (x) => `${fmt(x, 2)}%`, axis: "y" },
        { data: usy, color: "#6250d6", dash: [6, 4], label: "US funding that year", fmt: usd, axis: "y2" }], yMin: 0, y2: true });
    const add = (id, title, sub, color, f, opts = {}) => { const a = A(id); if (a) specs.push({ title, sub, sets: [{ data: opts.mul ? mul(a, opts.mul) : a, color, label: title, fmt: f }], yMin: 0, ...opts }); };
    add("ii_sexual_violence_incidents", "Conflict-related sexual violence: reported incidents (national)", "Insecurity Insight, monthly. Reporting is very incomplete, so low numbers do not mean few incidents.", "#c2185b", (x) => `${fmt(x)} incidents`, { bar: true });
    add("unmiss_budget_fy_usd", "UN peacekeeping mission (UNMISS) budget", "Approved budget for each UN fiscal year (July–June).", "#6250d6", usd, { step: true, yMin: null });
    add("fmr_internal_forced_total", "Forced travel: people counted moving because of conflict, disaster or hunger (national)", "IOM Flow Monitoring at its monitoring points. Covers routes past those points, not all movement; no county data for Nov 2023–Dec 2024.", "#d7301f", (x) => `${fmt(x)} people`, { bar: true });
    add("wps_ipv_pct", "Women who faced violence from a partner in the last year (national)", "Women, Peace and Security Index (Georgetown Institute), survey years only.", "#c2185b", (x) => `${fmt(x, 3)}%`, { step: true, yMax: 60 });
    add("wps_community_safety_pct", "Women who feel safe walking alone at night in their community (national)", "Women, Peace and Security Index (Georgetown Institute), survey years only.", "#1baf7a", (x) => `${fmt(x, 3)}%`, { step: true, yMax: 100 });
    add("wps_education_years", "Women’s average years of schooling (national)", "Women, Peace and Security Index (Georgetown Institute), survey years only.", "#008300", (x) => `${fmt(x, 3)} years`, { step: true });
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
        options: { animation: false, responsive: true, maintainAspectRatio: false, interaction: { mode: "index", intersect: false },
          plugins: { legend: { display: false }, tooltip: { callbacks: { title: (c) => monthLabel(c[0].dataIndex), label: (c) => `${c.dataset.label}: ${c.raw == null ? "–" : spec.sets[c.datasetIndex].fmt(c.raw)}`, afterBody: (c) => (spec.extra ? spec.extra(c[0].dataIndex) : "") } } },
          scales: {
            x: { ticks: { color: ink2, font: { size: 11 }, autoSkip: false, maxRotation: 0, callback: (_, i) => (i % 12 === 6 ? state.months[i].slice(0, 4) : null) }, grid: { color: (c) => (c.index % 12 === 0 ? line : "transparent"), drawTicks: false } },
            y: { min: spec.yMin == null ? undefined : spec.yMin, max: spec.yMax, ticks: { color: ink2, font: { size: 10 }, maxTicksLimit: 4, callback: (x) => (spec.sets[0].fmt === usd ? usdShort(x) : spec.sets[0].fmt(x).replace(" people", "").replace(" incidents", "").replace(" years", "")) }, grid: { color: line } },
            ...(spec.y2 ? { y2: { position: "right", min: 0, ticks: { color: "#6250d6", font: { size: 10 }, maxTicksLimit: 4, callback: (x) => usdShort(x) }, grid: { display: false } } } : {}),
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
      const sp = c._spec, i = state.view === "map" ? state.t : lastIdx(sp.sets[0].data);
      const val = (s) => (s.data[i] == null ? "no data" : s.fmt(s.data[i]));
      const parts = sp.sets.length === 1 ? [`<b>${val(sp.sets[0])}</b>`] : sp.sets.map((s) => `${s.label}: <b>${val(s)}</b>`);
      const ex = sp.extra ? sp.extra(i) : "";
      c._tile.querySelector(".nt-v").innerHTML = `${i == null ? "" : monthLabel(i) + ": "}${parts.join(" · ")}${ex ? `<br><span class="muted">${esc(ex)}</span>` : ""}`;
      c.draw();
    }
  }
  const lastIdx = (arr) => { for (let i = arr.length - 1; i >= 0; i--) if (arr[i] != null) return i; return null; };

  // ---------- views ----------
  function openNat(open) {
    state.natOpen = open;
    const d = $("#nat-drawer"); d.hidden = !open; $("#nat-toggle").setAttribute("aria-expanded", open);
    $("#nat-toggle").textContent = open ? "Hide national timeline" : "National timeline";
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
  const fitMap = () => countyLayer && map.fitBounds(countyLayer.getBounds(), { padding: [8, 8] });

  // ---------- time ----------
  function setTime(i) {
    state.t = i;
    $("#time").value = i;
    $("#time-label").textContent = windowLabel(i);
    refreshCounties(); updateRasters(); refreshPoints(); drawFlows(); updateNational(); renderContext();
    if (state.mode === "trend") renderLegend();
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
        l.on("click", () => { state.selected = f.properties.district_id; refreshCounties(); renderDetail().then(() => showTab("county")); writeHash(); });
        l.on("mouseover", () => l.setStyle({ weight: 2.5, color: "#0b0b0b" }));
        l.on("mouseout", () => { countyLayer.resetStyle(l); hideHover(); });
      },
    }).addTo(map);
    map.fitBounds(countyLayer.getBounds(), { padding: [8, 8] }); townsVisible();

    $("#mode").onchange = (e) => { state.mode = e.target.value; refreshCounties(); updateRasters(); renderLegend(); if (state.selected) renderDetail(); writeHash(); };
    $("#agg").onchange = (e) => { state.agg = e.target.value; setTime(state.t); renderLegend(); };
    $("#time").oninput = (e) => setTime(+e.target.value);
    $("#play").onclick = togglePlay;
    $("#filter").oninput = renderVarList;
    $("#grid-on").onchange = (e) => { state.gridOn = e.target.checked; refreshCounties(); updateRasters(); renderLegend(); writeHash(); };
    $("#detail-close").onclick = () => { state.selected = null; refreshCounties(); renderDetail(); writeHash(); };
    $("#tab-context").onclick = () => showTab("context");
    $("#tab-county").onclick = () => state.selected && showTab("county");
    $("#nat-toggle").onclick = () => openNat(!state.natOpen);
    $("#nat-close").onclick = () => openNat(false);
    $("#back-home").onclick = () => setView("landing");
    document.querySelectorAll("[data-open-map]").forEach((b) => (b.onclick = () => setView("map")));

    renderPointList(); renderBgList();
    const H = readHash();
    let tStart = state.months.indexOf("2022-09"); if (tStart < 0) tStart = state.months.length - 1;
    let first = "flood_s1_flood_pct";
    if (H) {
      const list = (k) => (H.get(k) || "").split(",").filter(Boolean);
      if (H.get("m") && [...$("#mode").options].some((o) => o.value === H.get("m"))) { state.mode = H.get("m"); $("#mode").value = state.mode; }
      if (H.get("a")) { state.agg = H.get("a"); $("#agg").value = state.agg; }
      if (H.get("s")) state.selected = H.get("s");
      if (H.get("fo") === "1") state.flowOn = true;
      if (H.get("fg")) state.flowGroup = H.get("fg");
      if (H.get("g") === "0") { state.gridOn = false; $("#grid-on").checked = false; }
      if (H.has("bg")) { state.bgOn = new Set(list("bg")); renderBgList(); }
      state.natOpen = H.get("n") === "1";
      const ti = state.months.indexOf(H.get("t")); if (ti >= 0) tStart = ti;
      for (const k of list("p")) { const p = state.points.find((x) => x.key === k); if (p) { await loadPoints(p); const cb = document.getElementById(`p-${k}`); if (cb) cb.checked = true; } }
      if (H.has("v")) first = state.varById[H.get("v")] ? H.get("v") : null;
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
