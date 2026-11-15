/* South Sudan Trend Explorer — static Leaflet app.
 * Data bundle is produced by scripts/build_web_data.py:
 *   data/variables.json, data/series/<id>.json, data/counties.geojson, data/layers.json
 * Index = value / baseline, where baseline is the county's mean in the baseline year
 * (2018, or the first year a source has data). Variables where a ratio is not meaningful
 * (index_ok=false, e.g. temperatures in °C, SPEI) show the difference from baseline instead.
 */
(() => {
  "use strict";

  // ---------- palette (reference data-viz palette) ----------
  const BLUE = ["#cde2fb", "#9ec5f4", "#6da7ec", "#3987e5", "#256abf", "#184f95", "#0d366b"];
  const DIV_GOOD = ["#9ec5f4", "#5598e7", "#256abf", "#0d366b"]; // increasing intensity
  const DIV_BAD = ["#f4c3bd", "#eb8a85", "#e34948", "#a32b2a"];
  const DIV_UP_NEUTRAL = ["#c4c0f2", "#9085e9", "#6250d6", "#3d2f9a"];
  const DIV_DOWN_NEUTRAL = ["#f7c8a5", "#f09a69", "#eb6834", "#b4461b"];
  const MID = () => (matchMedia("(prefers-color-scheme: dark)").matches ? "#383835" : "#f0efec");
  const CATEGORICAL = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300", "#6250d6", "#e34948"];

  const MONTH_NAMES = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
  const state = {
    months: [], vars: [], varById: {}, series: {}, checked: new Set(), colorBy: null,
    mode: "trend", agg: "month", t: 0, selected: null,
    rasters: [], rasterOn: new Set(), rasterLayers: {}, points: [], pointLayers: {},
    timer: null, charts: [],
  };

  // ---------- helpers ----------
  const $ = (s) => document.querySelector(s);
  const fetchJSON = (u) => fetch(u).then((r) => { if (!r.ok) throw new Error(u + " " + r.status); return r.json(); });
  const fmt = (v, d = 3) => (v == null || !isFinite(v) ? "–" : Math.abs(v) >= 1000 ? Math.round(v).toLocaleString() : (+v.toPrecision(d)).toString());
  const monthLabel = (i) => { const [y, m] = state.months[i].split("-"); return `${MONTH_NAMES[+m - 1]} ${y}`; };
  const isIndexMode = () => state.mode !== "raw";

  // Season windows used in South Sudan's agricultural calendar.
  function seasonOf(i) {
    const [y, m] = state.months[i].split("-").map(Number);
    if (m === 12) return { key: `${y + 1}-dry`, label: `Dry season ${y}/${String(y + 1).slice(2)}` };
    if (m <= 3) return { key: `${y}-dry`, label: `Dry season ${y - 1}/${String(y).slice(2)}` };
    if (m <= 6) return { key: `${y}-early`, label: `Early rains (Apr–Jun) ${y}` };
    if (m <= 9) return { key: `${y}-main`, label: `Main rains (Jul–Sep) ${y}` };
    return { key: `${y}-late`, label: `Late season (Oct–Nov) ${y}` };
  }
  function windowKey(i) {
    if (state.agg === "month") return state.months[i];
    if (state.agg === "year") return state.months[i].slice(0, 4);
    return seasonOf(i).key;
  }
  function windowLabel(i) {
    if (state.agg === "month") return monthLabel(i);
    if (state.agg === "year") return state.months[i].slice(0, 4);
    return seasonOf(i).label;
  }
  function windowIdx(i) {
    const k = windowKey(i);
    const out = [];
    for (let j = 0; j < state.months.length; j++) if (windowKey(j) === k) out.push(j);
    return out;
  }
  const mean = (arr) => { let s = 0, n = 0; for (const v of arr) if (v != null && isFinite(v)) { s += v; n++; } return n ? s / n : null; };
  const yearOf = (i) => +state.months[i].slice(0, 4);

  // Same window shifted into the baseline year (for "same month/season in 2018").
  function baselineWindowIdx(i, baseYear) {
    const idx = windowIdx(i);
    const shift = (baseYear - yearOf(i)) * 12;
    if (state.agg === "year") return state.months.map((_, j) => j).filter((j) => yearOf(j) === baseYear);
    return idx.map((j) => j + shift).filter((j) => j >= 0 && j < state.months.length);
  }

  /** Value shown for variable v, county c, time index i (in current mode/agg). */
  const TREND_YEARS = 7;  // 2018 -> 2025
  function trendValue(v, c) {
    const tr = trendOf(v.id, c); if (!tr) return null;
    return trendIsPct(v) ? tr[T_PCT] : tr[T_SEN];
  }
  const trendIsPct = (v) => v.index_ok !== false && !v.sparse_count;
  function valueAt(v, c, i, mode = state.mode) {
    if (mode === "trend") return trendValue(v, c);
    const s = state.series[v.id]; if (!s || !s[c]) return null;
    const arr = s[c];
    const raw = mean(windowIdx(i).map((j) => arr[j]));
    if (raw == null) return null;
    if (mode === "raw" || v.temporal === "static") return raw;
    const by = v.baseline_year || 2018;
    let base;
    if (mode === "index_month" && v.baseline_mode !== "annual") base = mean(baselineWindowIdx(i, by).map((j) => arr[j]));
    else base = mean(state.months.map((_, j) => j).filter((j) => yearOf(j) === by).map((j) => arr[j]));
    if (base == null) return null;
    if (v.index_ok === false) return raw - base;
    if (Math.abs(base) < 1e-9) return null;
    return raw / base;
  }
  const usesDiff = (v) => v.index_ok === false;

  // ---------- colour scales ----------
  function scaleFor(v) {
    if (state.mode === "trend" && v.temporal !== "static") {
      const up = v.higher_is === "better" ? DIV_GOOD : v.higher_is === "worse" ? DIV_BAD : DIV_UP_NEUTRAL;
      const down = v.higher_is === "better" ? DIV_BAD : v.higher_is === "worse" ? DIV_GOOD : DIV_DOWN_NEUTRAL;
      if (v._trendSpan == null) {
        const vals = Object.keys((state.trends || {})[v.id] || {}).map((c) => Math.abs(trendValue(v, c))).filter((x) => isFinite(x)).sort((a, b) => a - b);
        v._trendSpan = vals.length ? Math.max(trendIsPct(v) ? 1 : 1e-6, vals[Math.floor(vals.length * 0.9)]) : 1;
      }
      const span = v._trendSpan;
      return { kind: "trend", span, up, down, color: (x) => divColor(x == null ? null : x / span, up, down) };
    }
    if (!isIndexMode() || v.temporal === "static") {
      const lo = v.p02 ?? v.min, hi = v.p98 ?? v.max;
      return { kind: "seq", lo, hi, color: (x) => {
        if (x == null) return null;
        const t = hi > lo ? Math.min(1, Math.max(0, (x - lo) / (hi - lo))) : 0.5;
        return BLUE[Math.min(BLUE.length - 1, Math.floor(t * BLUE.length))];
      } };
    }
    const up = v.higher_is === "better" ? DIV_GOOD : v.higher_is === "worse" ? DIV_BAD : DIV_UP_NEUTRAL;
    const down = v.higher_is === "better" ? DIV_BAD : v.higher_is === "worse" ? DIV_GOOD : DIV_DOWN_NEUTRAL;
    if (usesDiff(v)) {
      const span = Math.max(1e-6, v._diffSpan || ((v.p98 - v.p02) / 4) || 1);
      return { kind: "diff", span, up, down, color: (x) => divColor(x == null ? null : x / span, up, down) };
    }
    // Ratio: log2 scale, ±1 = halving/doubling saturates.
    return { kind: "ratio", up, down, color: (x) => divColor(x == null || x <= 0 ? null : Math.log2(x), up, down) };
  }
  function divColor(z, up, down) {
    if (z == null || !isFinite(z)) return null;
    const a = Math.min(1, Math.abs(z));
    if (a < 0.05) return MID();
    const ramp = z > 0 ? up : down;
    return ramp[Math.min(ramp.length - 1, Math.floor(a * ramp.length))];
  }

  // Robust span for difference-mode variables (95th pct of |diff| across counties & time).
  function computeDiffSpan(v) {
    const vals = [];
    const step = Math.max(1, Math.floor(state.months.length / 24));
    for (const c of Object.keys(state.series[v.id] || {})) {
      for (let i = 0; i < state.months.length; i += step) { const x = valueAt(v, c, i); if (x != null) vals.push(Math.abs(x)); }
    }
    vals.sort((a, b) => a - b);
    v._diffSpan = vals.length ? vals[Math.floor(vals.length * 0.95)] || 1 : 1;
  }

  // ---------- map ----------
  const map = L.map("map", { zoomControl: true, preferCanvas: false, minZoom: 5, maxZoom: 13 });
  const base = {
    "Light gray": L.tileLayer("https://server.arcgisonline.com/ArcGIS/rest/services/Canvas/World_Light_Gray_Base/MapServer/tile/{z}/{y}/{x}", { attribution: "Esri, HERE, Garmin, © OpenStreetMap contributors", maxZoom: 16 }),
    "Dark gray": L.tileLayer("https://server.arcgisonline.com/ArcGIS/rest/services/Canvas/World_Dark_Gray_Base/MapServer/tile/{z}/{y}/{x}", { attribution: "Esri, HERE, Garmin, © OpenStreetMap contributors", maxZoom: 16 }),
    "Satellite": L.tileLayer("https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}", { attribution: "Esri, Maxar, Earthstar Geographics" }),
    "OpenStreetMap": L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", { attribution: "© OpenStreetMap contributors", maxZoom: 19 }),
  };
  (matchMedia("(prefers-color-scheme: dark)").matches ? base["Dark gray"] : base["Light gray"]).addTo(map);
  L.control.layers(base, null, { position: "topright" }).addTo(map);
  map.createPane("rasters").style.zIndex = 350;
  map.createPane("counties").style.zIndex = 400;
  map.createPane("flows").style.zIndex = 450;
  map.createPane("points").style.zIndex = 600;
  let countyLayer;

  // ---------- trends (Mann-Kendall / Sen's slope, computed by scripts/trend_stats.py) ----------
  const T_P = 0, T_Q = 1, T_SEN = 2, T_PCT = 3, T_TAU = 4, T_N = 5, T_SIG = 6, T_TEST = 7, T_TXT = 8;
  const trendOf = (vid, cid) => (state.trends && state.trends[vid] && state.trends[vid][cid]) || null;
  function trendHtml(v, cid, compact) {
    const tr = trendOf(v.id, cid);
    if (!tr) return v.temporal === "static" ? `<div class="trend muted">Static layer: no trend test.</div>` : `<div class="trend muted">No trend test (too few observations).</div>`;
    const sigTxt = tr[T_SIG] ? `<span class="sig-badge">◆ Significant trend</span>` : `<span class="nosig-badge">No significant trend</span>`;
    const slope = tr[T_SEN] == null ? "n/a" : `${tr[T_SEN] >= 0 ? "+" : ""}${fmt(tr[T_SEN])} ${v.units || ""}/yr`;
    const pct = tr[T_PCT] == null ? "" : ` (${tr[T_PCT] >= 0 ? "+" : ""}${fmt(tr[T_PCT], 2)}%/yr)`;
    const stats = `Sen's slope ${slope}${pct} · ${tr[T_TEST] === "S" ? "seasonal " : ""}Mann-Kendall p = ${fmt(tr[T_P], 2)}, FDR q = ${fmt(tr[T_Q], 2)}, n = ${tr[T_N]}`;
    return `<div class="trend">${sigTxt}<div class="trend-txt">${tr[T_TXT]}</div>${compact ? "" : `<div class="trend-stats">${stats}</div>`}</div>`;
  }

  function styleCounty(f) {
    const v = state.varById[state.colorBy];
    const selected = state.selected === f.properties.district_id;
    const baseStyle = { color: selected ? "#0b0b0b" : "#898781", weight: selected ? 2.5 : 0.7, pane: "counties", dashArray: null };
    if (!v) return { ...baseStyle, fillOpacity: 0 };
    const x = valueAt(v, f.properties.district_id, state.t);
    const col = scaleFor(v).color(x);
    const rasterVisible = state.rasterOn.size > 0;
    const tr = trendOf(v.id, f.properties.district_id);
    if (tr && tr[T_SIG] && !selected) { baseStyle.color = "#ffffff"; baseStyle.weight = 2.6; }
    if (col == null) return { ...baseStyle, fillColor: "#898781", fillOpacity: rasterVisible ? 0 : 0.08, dashArray: "2 3" };
    return { ...baseStyle, fillColor: col, fillOpacity: rasterVisible ? 0.35 : 0.78 };
  }

  // ---------- hover card: profile + trend + sparklines ----------
  const SPARKS = [
    { label: "Forced migration (people displaced/returning, IOM ET)", ids: ["et_ind_total"], color: "#e34948" },
    { label: "US humanitarian funding — national (OCHA FTS, USD/month)", ids: ["fts_us_gov_funding_month_usd", "us_aid_disbursed_month_usd"], color: "#2a78d6" },
    { label: "Flood / surface-water extent (% of county)", ids: ["flood_s1_pct", "flood_gfm_pct", "flood_pct", "surface_water_pct"], prefix: "flood_", color: "#1baf7a" },
    { label: "Drought index (ensemble mean; band = spread across sources)", ids: ["drought_ensemble_mean", "spei3"], band: "drought_ensemble_spread", color: "#eb6834" },
  ];
  function sparkVar(sp) {
    let id = sp.ids.find((x) => state.varById[x]);
    if (!id && sp.prefix) id = (state.vars.find((v) => v.id.startsWith(sp.prefix) && v.id.endsWith("_pct")) || {}).id;
    return id ? state.varById[id] : null;
  }
  function sparkline(sp, cid) {
    const v = sparkVar(sp); if (!v || !state.series[v.id] || !state.series[v.id][cid]) return "";
    const arr = state.series[v.id][cid], W = 230, H = 22, n = arr.length;
    const band = sp.band && state.series[sp.band] && state.series[sp.band][cid];
    const lo = (i) => (band && arr[i] != null && band[i] != null ? arr[i] - band[i] / 2 : arr[i]);
    const hi = (i) => (band && arr[i] != null && band[i] != null ? arr[i] + band[i] / 2 : arr[i]);
    const vals = arr.map((x, i) => [lo(i), hi(i)]).flat().filter((x) => x != null && isFinite(x));
    if (!vals.length) return "";
    let mn = Math.min(...vals), mx = Math.max(...vals); if (mx === mn) { mx += 1; mn -= 1; }
    const X = (i) => (i / (n - 1)) * W, Y = (y) => H - 2 - ((y - mn) / (mx - mn)) * (H - 4);
    let d = "", pen = false;
    arr.forEach((y, i) => { if (y == null || !isFinite(y)) { pen = false; return; } d += `${pen ? "L" : "M"}${X(i).toFixed(1)},${Y(y).toFixed(1)}`; pen = true; });
    let bandPath = "";
    if (band) {
      const top = [], bot = [];
      arr.forEach((y, i) => { if (y != null && band[i] != null) { top.push(`${X(i).toFixed(1)},${Y(hi(i)).toFixed(1)}`); bot.unshift(`${X(i).toFixed(1)},${Y(lo(i)).toFixed(1)}`); } });
      if (top.length) bandPath = `<path d="M${top.join("L")}L${bot.join("L")}Z" fill="${sp.color}" opacity="0.18"/>`;
    }
    const zero = mn < 0 && mx > 0 ? `<line x1="0" x2="${W}" y1="${Y(0)}" y2="${Y(0)}" stroke="var(--line)" stroke-dasharray="2 2"/>` : "";
    const cx = X(state.t), cur = arr[state.t];
    return `<div class="spark"><div class="spark-l">${sp.label}${v.id !== sp.ids[0] ? ` <span class="muted">(${v.label})</span>` : ""}: <b>${cur == null ? "–" : fmt(cur)}</b></div>
      <svg width="${W}" height="${H}" viewBox="0 0 ${W} ${H}" aria-hidden="true">${zero}${bandPath}<path d="${d}" fill="none" stroke="${sp.color}" stroke-width="1.6"/>
      <line x1="${cx}" x2="${cx}" y1="0" y2="${H}" stroke="#eb6834" stroke-width="1.5"/></svg></div>`;
  }
  function profileHtml(cid) {
    const pr = state.profiles && state.profiles[cid]; if (!pr) return "";
    const lz = pr.livelihood_zone && pr.livelihood_zone.name ? `<div class="pf-lz">${pr.livelihood_zone.name}</div>` : "";
    const part = (t) => (t ? `<div class="pf">${t}</div>` : "");
    return `<div class="profile">${lz}${part(pr.livelihoods)}${part(pr.history)}${part(pr.conflict_impact)}</div>`;
  }

  function tooltipHtml(p) {
    const v = state.varById[state.colorBy];
    let line = "";
    if (v) {
      const x = valueAt(v, p.district_id, state.t);
      line = `<div class="tt-var">${v.label}: <b>${describeValue(v, x)}</b></div>${trendHtml(v, p.district_id, true)}`;
    }
    const sparks = SPARKS.map((sp) => sparkline(sp, p.district_id)).join("");
    return `<div class="tt"><div class="tt-h"><b>${p.name}</b> · ${p.admin1} <span class="muted">· ${windowLabel(state.t)}</span></div>${profileHtml(p.district_id)}${line}${sparks ? `<div class="sparks">${sparks}</div>` : ""}</div>`;
  }
  function describeValue(v, x, mode = state.mode) {
    if (x == null) return mode === "trend" ? "no trend test" : "no data";
    if (mode === "trend" && v.temporal !== "static") {
      if (trendIsPct(v)) { const f = Math.max(0, 1 + (x * TREND_YEARS) / 100); return `${x >= 0 ? "+" : ""}${fmt(x, 2)}% of ${v.baseline_year} level per year (≈${fmt(f, 2)}× from 2018 to 2025)`; }
      return `${x >= 0 ? "+" : ""}${fmt(x)} ${v.units || ""} per year (Sen's slope)`;
    }
    if (mode === "raw" || v.temporal === "static") return `${fmt(x)} ${v.units || ""}`;
    if (usesDiff(v)) return `${x >= 0 ? "+" : ""}${fmt(x)} ${v.units || ""} vs ${v.baseline_year}`;
    return `${fmt(x)}× ${v.baseline_year} level`;
  }

  function refreshCounties() {
    if (!countyLayer) return;
    countyLayer.setStyle(styleCounty);
    countyLayer.eachLayer((l) => {
      if (l.isTooltipOpen && l.isTooltipOpen()) l.setTooltipContent(tooltipHtml(l.feature.properties));
      const tr = trendOf(state.colorBy, l.feature.properties.district_id);
      if ((tr && tr[T_SIG]) || state.selected === l.feature.properties.district_id) l.bringToFront();  // keep outlines visible
    });
  }

  // ---------- legend ----------
  function renderLegend() {
    const el = $("#legend");
    const v = state.varById[state.colorBy];
    if (!v) { el.hidden = true; return; }
    const sc = scaleFor(v);
    let html = `<div class="title">${v.label}</div>`;
    if (sc.kind === "seq") {
      html += `<div class="bar" style="background:linear-gradient(90deg,${BLUE.join(",")})"></div>
        <div class="ticks"><span>${fmt(sc.lo)}</span><span>${v.units || ""}</span><span>${fmt(sc.hi)}</span></div>`;
    } else {
      const left = [...sc.down].reverse(), right = sc.up;
      const g = [...left, MID(), ...right].join(",");
      const tpct = sc.kind === "trend" && trendIsPct(v);
      const xf = (pct) => fmt(Math.max(0, 1 + (pct * TREND_YEARS) / 100), 2);
      const lo = sc.kind === "ratio" ? "≤0.5×" : sc.kind === "trend" ? (tpct ? `−${fmt(sc.span, 2)}%/yr (≈${xf(-sc.span)}×)` : `−${fmt(sc.span)} ${v.units || ""}/yr`) : `−${fmt(sc.span)}`;
      const hi = sc.kind === "ratio" ? "≥2×" : sc.kind === "trend" ? (tpct ? `+${fmt(sc.span, 2)}%/yr (≈${xf(sc.span)}×)` : `+${fmt(sc.span)} ${v.units || ""}/yr`) : `+${fmt(sc.span)}`;
      const mid = sc.kind === "ratio" ? `1.0 = ${v.baseline_year}` : sc.kind === "trend" ? "no change" : `0 = ${v.baseline_year}`;
      html += `<div class="bar" style="background:linear-gradient(90deg,${g})"></div>
        <div class="ticks"><span>${lo}</span><span>${mid}</span><span>${hi}</span></div>`;
      const dir = v.higher_is === "neutral" ? "Purple = higher, orange = lower than baseline"
        : `Blue = better, red = worse than baseline (higher is ${v.higher_is})`;
      html += `<div class="note">${dir}${sc.kind === "diff" ? ` · change in ${v.units || "units"} (ratio not meaningful)` : ""}</div>`;
      if (sc.kind === "trend") html += `<div class="note"><b>Trend 2018–2025 (Sen's slope)</b>: the median yearly change in each county's series${tpct ? `, as a % of its ${v.baseline_year} level; × = implied change from 2018 to 2025 (e.g. +10%/yr ≈ 1.7×)` : ` in ${v.units || "units"} per year (a % of baseline is not meaningful for this variable)`}. Monthly series use the seasonal Sen's slope. This map does not change with the time slider; arrows and points do.</div>`;
      else if (v.sparse_count) html += `<div class="note">Sparse count: shown as change from the ${v.baseline_year} monthly average (most ${v.baseline_year} months were zero, so a ratio is undefined).</div>`;
      else if (state.mode === "index_month") html += `<div class="note">Compared with the same ${state.agg === "month" ? "month" : state.agg === "season" ? "season" : "year"} in ${v.baseline_year}.</div>`;
    }
    if (v.baseline_year && v.baseline_year !== 2018 && isIndexMode()) html += `<div class="note">⚠ Source starts in ${v.baseline_year}; baseline = ${v.baseline_year}.</div>`;
    if (v.temporal && v.temporal !== "monthly") html += `<div class="note">Time step of source: ${v.temporal}${v.carry_forward_months ? ` (latest value carried forward up to ${v.carry_forward_months} months)` : ""}.</div>`;
    if (state.trends && state.trends[v.id]) {
      const nSig = Object.values(state.trends[v.id]).filter((t) => t[T_SIG]).length;
      html += `<div class="note"><span class="sig-swatch"></span> White outline = significant 2018–2025 trend (Mann-Kendall p &lt; 0.05): ${nSig} of 79 counties. Hover for Sen's slope.</div>`;
    }
    html += `<div class="note"><span class="nodata"></span> no data · Source: ${v.source || "–"}${v.native_resolution ? ` · ${v.native_resolution}` : ""}</div>`;
    const rs = [...state.rasterOn].map((k) => state.rasters.find((r) => r.key === k)).filter(Boolean);
    for (const r of rs) {
      const cm = r.colors || r.legend_colors || null;
      html += `<div class="title" style="margin-top:8px">Raster: ${r.label}</div>`;
      if (cm) html += `<div class="bar" style="background:linear-gradient(90deg,${cm.join(",")})"></div>`;
      html += `<div class="ticks"><span>${fmt(r.vmin)}</span><span>${r.units || ""} · ${r.colormap || ""}</span><span>${fmt(r.vmax)}</span></div>`;
    }
    // keep title + colour bar visible; fold the explanatory notes
    const cut = html.indexOf('<div class="note">');
    if (cut > 0) html = html.slice(0, cut) + `<details${state.legendOpen ? " open" : ""}><summary>How to read this</summary>${html.slice(cut)}</details>`;
    el.innerHTML = html;
    const det = el.querySelector("details"); if (det) det.ontoggle = () => (state.legendOpen = det.open);
    el.hidden = false;
  }

  // ---------- sidebar ----------
  function renderVarList() {
    const q = $("#filter").value.trim().toLowerCase();
    const el = $("#var-list");
    el.innerHTML = "";
    let lastCat = null, lastGroup = null;
    for (const v of state.vars) {
      const hay = `${v.label} ${v.id} ${v.group} ${v.source}`.toLowerCase();
      if (q && !hay.includes(q)) continue;
      if (v.category !== lastCat) {
        el.insertAdjacentHTML("beforeend", `<div class="cat-title">${v.category === "human" ? "Human & infrastructure" : v.category === "environment" ? "Environment & climate" : v.category}</div>`);
        lastCat = v.category; lastGroup = null;
      }
      if (v.group !== lastGroup) { el.insertAdjacentHTML("beforeend", `<div class="group-title">${v.group}</div>`); lastGroup = v.group; }
      const row = document.createElement("div");
      row.className = "var-row";
      const id = `cb-${v.id}`;
      const cov = `${v.first_period.slice(0, 4)}–${v.last_period.slice(0, 4)}${v.temporal && v.temporal !== "monthly" ? ", " + v.temporal : ""}`;
      row.innerHTML = `<button class="colorby ${state.colorBy === v.id ? "on" : ""}" title="Colour the map by this variable" aria-label="Colour map by ${v.label}"></button>
        <input type="checkbox" id="${id}" ${state.checked.has(v.id) ? "checked" : ""}>
        <label for="${id}" title="${(v.notes || v.source || "").replace(/"/g, "&quot;")}">${v.label} <span class="meta">${v.units ? "· " + v.units + " " : ""}(${cov})</span></label>`;
      row.querySelector("button").onclick = () => setColorBy(v.id);
      row.querySelector("input").onchange = (e) => {
        if (e.target.checked) { state.checked.add(v.id); if (!state.colorBy) setColorBy(v.id); else ensureSeries(v.id).then(renderDetail); }
        else { state.checked.delete(v.id); if (state.colorBy === v.id) setColorBy([...state.checked][0] || null); renderDetail(); }
      };
      el.appendChild(row);
    }
  }

  async function ensureSeries(id) {
    if (!state.series[id]) {
      if (state.bundle) { const all = await state.bundle; Object.assign(state.series, all); }
      else state.series[id] = await fetchJSON(`data/series/${id}.json`);
      const v = state.varById[id];
      if (usesDiff(v)) computeDiffSpan(v);
    }
    return state.series[id];
  }

  async function setColorBy(id) {
    state.colorBy = id;
    if (id) { state.checked.add(id); await ensureSeries(id); }
    renderVarList(); refreshCounties(); renderLegend(); renderDetail();
  }

  function renderRasterList() {
    const el = $("#raster-list");
    if (!state.rasters.length) { el.innerHTML = `<p class="empty">No raster overlays built yet.</p>`; return; }
    el.innerHTML = "";
    for (const r of state.rasters) {
      const row = document.createElement("div");
      row.className = "var-row";
      row.innerHTML = `<input type="checkbox" id="r-${r.key}"><label for="r-${r.key}">${r.label} <span class="meta">· ${r.native_resolution || ""} (${(r.dates || []).length} steps)</span></label>`;
      row.querySelector("input").onchange = (e) => {
        if (e.target.checked) state.rasterOn.add(r.key); else { state.rasterOn.delete(r.key); if (state.rasterLayers[r.key]) { map.removeLayer(state.rasterLayers[r.key]); delete state.rasterLayers[r.key]; } }
        updateRasters(); refreshCounties(); renderLegend();
      };
      el.appendChild(row);
    }
  }

  function rasterDateFor(r, i) {
    const dates = r.dates || [];
    if (!dates.length) return null;
    const ym = state.months[i];
    if (dates.includes(ym)) return ym;
    // Annual/sparse rasters: prefer one from the same year, else the latest earlier one, else the first.
    const sameYear = dates.find((d) => d.slice(0, 4) === ym.slice(0, 4));
    if (sameYear) return sameYear;
    let best = null;
    for (const d of dates) if (d.slice(0, 7) <= ym) best = d;
    return best || dates[0];
  }
  function updateRasters() {
    const op = +$("#raster-opacity").value;
    for (const key of state.rasterOn) {
      const r = state.rasters.find((x) => x.key === key);
      const d = rasterDateFor(r, state.t);
      if (!d) continue;
      let url = `rasters/${key}/${d}.png`;
      if (r.packed) {
        const y = d.slice(0, 4);
        r._maps = r._maps || {}; r._pending = r._pending || {};
        if (!r._maps[y]) {
          if (!r._pending[y]) r._pending[y] = fetchJSON(`rasters/${key}/${y}.json`).then((m) => { r._maps[y] = m; updateRasters(); });
          continue;
        }
        url = r._maps[y][d];
        if (!url) continue;
      }
      const b = r.bounds;
      if (state.rasterLayers[key]) { state.rasterLayers[key].setUrl(url); state.rasterLayers[key].setOpacity(op); }
      else state.rasterLayers[key] = L.imageOverlay(url, b, { pane: "rasters", opacity: op, interactive: false }).addTo(map);
    }
  }

  function renderPointList() {
    const el = $("#point-list");
    if (!state.points.length) { el.innerHTML = `<p class="empty">No point layers built yet.</p>`; return; }
    el.innerHTML = "";
    state.points.forEach((p, k) => {
      p._color = CATEGORICAL[k % CATEGORICAL.length];
      const row = document.createElement("div");
      row.className = "var-row";
      row.innerHTML = `<input type="checkbox" id="p-${p.key}"><span class="swatch" style="background:${p._color}"></span><label for="p-${p.key}">${p.label}${p.notes ? ` <span class="meta">· ${p.notes.slice(0, 60)}</span>` : ""}</label>`;
      row.querySelector("input").onchange = async (e) => {
        if (e.target.checked) { await loadPoints(p); } else if (state.pointLayers[p.key]) { map.removeLayer(state.pointLayers[p.key].layer); delete state.pointLayers[p.key]; }
      };
      el.appendChild(row);
    });
  }

  async function loadPoints(p) {
    const gj = await fetchJSON(p.file);
    const timed = gj.features.some((f) => f.properties && (f.properties.date || f.properties.year || f.properties.valid_from || f.properties.valid_to));
    const entry = { p, gj, timed, layer: null };
    state.pointLayers[p.key] = entry;
    drawPoints(entry);
  }
  function featureInWindow(f) {
    const pr = f.properties || {};
    const idx = windowIdx(state.t);
    const lo = state.months[idx[0]], hi = state.months[idx[idx.length - 1]];
    if (pr.date) { const ym = String(pr.date).slice(0, 7); return ym >= lo && ym <= hi; }
    if ("valid_from" in pr || "valid_to" in pr) {  // feature exists from valid_from to valid_to (YYYY-MM; null = open-ended)
      const from = pr.valid_from ? String(pr.valid_from).slice(0, 7) : "0000-00", to = pr.valid_to ? String(pr.valid_to).slice(0, 7) : "9999-99";
      return from <= hi && to >= lo;
    }
    if (pr.year) { const y = String(pr.year); return y >= lo.slice(0, 4) && y <= hi.slice(0, 4) || (y <= hi.slice(0, 4) && !pr.end_year) || (pr.end_year && y <= hi.slice(0, 4) && String(pr.end_year) >= lo.slice(0, 4)); }
    return true;
  }
  function drawPoints(entry) {
    if (entry.layer) map.removeLayer(entry.layer);
    const { p, gj, timed } = entry;
    const isEvent = timed && gj.features.some((f) => f.properties && f.properties.date);
    entry.layer = L.geoJSON(gj, {
      pane: "points",
      filter: (f) => !timed || featureInWindow(f),
      style: (f) => (f.geometry && /Point/.test(f.geometry.type) ? {} : { color: p._color, weight: 2, fillOpacity: 0.15 }),
      pointToLayer: (f, ll) => {
        const pr = f.properties || {};
        const sizeVal = +(pr.deaths_best ?? pr.deaths ?? pr.fatalities ?? 0);
        const r = isEvent ? Math.min(14, 4 + Math.sqrt(sizeVal)) : 5;
        return L.circleMarker(ll, { radius: r, color: getComputedStyle(document.documentElement).getPropertyValue("--surface").trim() || "#fff", weight: 1.5, fillColor: p._color, fillOpacity: 0.9 });
      },
      onEachFeature: (f, l) => {
        const pr = f.properties || {};
        const rows = Object.entries(pr).filter(([, val]) => val !== null && val !== "" && typeof val !== "object").slice(0, 12)
          .map(([k, val]) => `<tr><td style="color:var(--muted);padding-right:6px">${k}</td><td>${String(val).slice(0, 120)}</td></tr>`).join("");
        l.bindPopup(`<b>${p.label}</b><table>${rows}</table>`);
      },
    }).addTo(map);
  }
  function refreshPoints() { for (const e of Object.values(state.pointLayers)) if (e.timed) drawPoints(e); }

  // ---------- detail panel ----------
  async function renderDetail() {
    const el = $("#detail");
    if (!state.selected) { el.hidden = true; return; }
    const f = countyLayer.getLayers().find((l) => l.feature.properties.district_id === state.selected).feature.properties;
    $("#detail-title").textContent = `${f.name} County`;
    $("#detail-sub").textContent = `${f.admin1} · ${f.district_id} · ${windowLabel(state.t)}`;
    state.charts.forEach((c) => c.destroy()); state.charts = [];
    const box = $("#detail-charts"); box.innerHTML = "";
    const ids = [...state.checked];
    if (!ids.length) { box.innerHTML = `<p class="empty">Tick variables in the sidebar to compare their trends here.</p>`; el.hidden = false; return; }
    await Promise.all(ids.map(ensureSeries));
    const ink2 = getComputedStyle(document.documentElement).getPropertyValue("--ink-2").trim();
    const line = getComputedStyle(document.documentElement).getPropertyValue("--line").trim();
    for (const id of ids) {
      const v = state.varById[id];
      // One point per window (month / season / year).
      const keys = [], labels = [], vals = [], firstIdx = [];
      const cm = state.mode === "trend" ? "index_month" : state.mode;  // charts always show the time series
      state.months.forEach((_, i) => { const k = windowKey(i); if (!keys.includes(k)) { keys.push(k); firstIdx.push(i); labels.push(windowLabel(i)); vals.push(valueAt(v, state.selected, i, cm)); } });
      const cur = keys.indexOf(windowKey(state.t));
      const block = document.createElement("div");
      block.className = "chart-block";
      block.innerHTML = `<h3>${v.label}${v.units && state.mode === "raw" ? ` (${v.units})` : ""}</h3>
        <div class="now">${windowLabel(state.t)}: <b>${describeValue(v, vals[cur], cm)}</b></div>${trendHtml(v, state.selected, false)}<canvas></canvas>`;
      box.appendChild(block);
      const ref = cm === "raw" || v.temporal === "static" ? null : usesDiff(v) ? 0 : 1;
      const ratio = ref === 1;
      // Ratios: log axis clamped to 1/8x..8x so tiny dry-season baselines don't flatten the chart.
      const plotVals = ratio ? vals.map((x) => (x == null ? null : Math.min(8, Math.max(0.125, x)))) : vals;
      const color = v.id === state.colorBy ? "#2a78d6" : "#52514e";
      const chart = new Chart(block.querySelector("canvas"), {
        type: "line",
        data: { labels, datasets: [{ data: plotVals, borderColor: color, borderWidth: 2, pointRadius: 0, pointHitRadius: 8, spanGaps: false, tension: 0.15 }] },
        options: {
          animation: false, responsive: true, maintainAspectRatio: false,
          interaction: { mode: "index", intersect: false },
          plugins: { legend: { display: false }, tooltip: { callbacks: { label: (c) => describeValue(v, vals[c.dataIndex], cm) } } },
          scales: {
            x: { ticks: { color: ink2, maxTicksLimit: 8, autoSkip: true, font: { size: 10 } }, grid: { display: false } },
            y: ratio
              ? { type: "logarithmic", min: 0.125, max: 8, afterBuildTicks: (ax) => { ax.ticks = [0.125, 0.25, 0.5, 1, 2, 4, 8].map((value) => ({ value })); },
                  ticks: { color: ink2, font: { size: 10 }, callback: (x) => `${x}×` }, grid: { color: line } }
              : { ticks: { color: ink2, maxTicksLimit: 4, font: { size: 10 } }, grid: { color: line } },
          },
          onClick: (_, els) => { if (els.length) setTime(firstIdx[els[0].index]); },
        },
        plugins: [{
          id: "marks",
          afterDraw(c) {
            const { ctx, chartArea: a, scales } = c;
            ctx.save();
            if (ref != null) { const y = scales.y.getPixelForValue(ref); if (y >= a.top && y <= a.bottom) { ctx.strokeStyle = ink2; ctx.setLineDash([3, 3]); ctx.lineWidth = 1; ctx.beginPath(); ctx.moveTo(a.left, y); ctx.lineTo(a.right, y); ctx.stroke(); } }
            const x = scales.x.getPixelForValue(cur); ctx.setLineDash([]); ctx.strokeStyle = "#eb6834"; ctx.lineWidth = 2;
            ctx.beginPath(); ctx.moveTo(x, a.top); ctx.lineTo(x, a.bottom); ctx.stroke();
            ctx.restore();
          },
        }],
      });
      state.charts.push(chart);
    }
    el.hidden = false;
  }


  // ---------- migration flows (origin -> destination arrows) ----------
  const REASON_STYLE = {
    conflict: ["#e34948", "Conflict"], disaster: ["#2a78d6", "Flood / disaster"], food: ["#eda100", "Food / hardship"],
    sudan_conflict: ["#6250d6", "Sudan war (cross-border)"], return_relocation: ["#1baf7a", "Return / relocation"],
    other: ["#898781", "Other / unspecified"], unknown: ["#898781", "Unspecified"],
  };
  const SOURCE_SHORT = { et: "Event Tracking", fmr: "Flow Monitoring", dtm_mt_idp_od: "IDP stock by origin (Mobility Tracking)",
    dtm_mt_returnee_od: "Returnee stock by origin (Mobility Tracking)", dtm_renk_intentions: "Renk onward intentions (survey)" };
  // line style per source: dash pattern, opacity, max arrows drawn
  const SOURCE_STYLE = { et: [null, 0.85, 160], fmr: ["6 5", 0.85, 120], dtm_mt_idp_od: ["1 5", 0.6, 90],
    dtm_mt_returnee_od: ["1 5", 0.6, 90], dtm_renk_intentions: ["10 4 2 4", 0.8, 40] };
  const srcStyle = (k) => SOURCE_STYLE[k] || ["2 3", 0.7, 60];
  state.flowOn = true; state.flowSources = null; state.flowReasons = null; state.flowLayer = null;
  const flowRenderer = L.svg({ pane: "flows", padding: 0.5 });
  let flowDefsReady = false;
  function ensureArrowDefs() {
    if (flowDefsReady || !flowRenderer._container) return;
    const ns = "http://www.w3.org/2000/svg";
    const defs = document.createElementNS(ns, "defs");
    state.flows.reasons.forEach((r, i) => {
      const m = document.createElementNS(ns, "marker");
      m.setAttribute("id", `ah-${i}`); m.setAttribute("viewBox", "0 0 10 10"); m.setAttribute("refX", "7"); m.setAttribute("refY", "5");
      m.setAttribute("markerWidth", "3.2"); m.setAttribute("markerHeight", "3.2"); m.setAttribute("orient", "auto-start-reverse");
      m.setAttribute("markerUnits", "strokeWidth");
      const path = document.createElementNS(ns, "path");
      path.setAttribute("d", "M0,0 L10,5 L0,10 z"); path.setAttribute("fill", (REASON_STYLE[r] || REASON_STYLE.other)[0]);
      m.appendChild(path); defs.appendChild(m);
    });
    flowRenderer._container.insertBefore(defs, flowRenderer._container.firstChild);
    flowDefsReady = true;
  }
  function bezier(a, b, bendFrac) {
    // quadratic curve in lon/lat space, bent to the right of travel so A->B and B->A don't overlap
    const [y1, x1] = a, [y2, x2] = b, dx = x2 - x1, dy = y2 - y1, len = Math.hypot(dx, dy) || 1;
    const bend = Math.min(1.2, len * bendFrac);
    const qx = (x1 + x2) / 2 + (bend * dy) / len, qy = (y1 + y2) / 2 - (bend * dx) / len;
    const pts = [];
    for (let k = 0; k <= 20; k++) { const t = k / 20, u = 1 - t; pts.push([u * u * y1 + 2 * u * t * qy + t * t * y2, u * u * x1 + 2 * u * t * qx + t * t * x2]); }
    return pts;
  }
  function flowWindowMonths() { return windowIdx(state.t).map((j) => state.months[j]); }
  const FLOW_PRIORITY = ["et", "fmr", "dtm_mt_idp_od"];
  const FLOW_EXPLAIN = {
    et: "IOM Event Tracking: people newly displaced or returning in this month, from the county they left to the county where IOM recorded them. Cross-border arrivals start at the border crossing.",
    fmr: "IOM Flow Monitoring: people travelling because of conflict, disaster or hunger, counted at monitoring points (mostly Renk from 2023). Shows routes seen at those points, not all movement.",
    dtm_mt_idp_od: "IOM Mobility Tracking: everyone displaced at the latest survey round, drawn from the county they came from to where they live now. A stock (cumulative), not this month's movement.",
    dtm_mt_returnee_od: "IOM Mobility Tracking: returnees at the latest survey round, from where they were displaced to where they returned. A stock, not this month's movement.",
    dtm_renk_intentions: "IOM Renk transit-centre survey (Jul 2024 only): where people arriving at Renk said they intended to go. A sample of intentions.",
  };
  state.flowMode = "best";
  function sourceForMonth(m) {
    const F = state.flows;
    if (state.flowMode !== "best") { const si = F.sources.findIndex((x) => x.key === state.flowMode); return si >= 0 && F.sources[si].months.includes(m) ? si : -1; }
    for (const k of FLOW_PRIORITY) { const si = F.sources.findIndex((x) => x.key === k); if (si >= 0 && F.sources[si].months.includes(m)) return si; }
    return -1;
  }
  function flowStatus(used) {
    const F = state.flows; if (!F) return "";
    if (!used.size) {
      const m = flowWindowMonths()[0];
      const why = state.flowMode === "fmr" && m >= "2023-11" && m <= "2024-12" ? " IOM published no county-level Flow Monitoring data for Nov 2023–Dec 2024."
        : m < "2018-12" ? " No county-level flow data exists before Dec 2018." : "";
      return `<span class="none">No arrows for ${windowLabel(state.t)} from this source.${why}</span>`;
    }
    return [...used].map((si) => {
      const src = F.sources[si];
      let when = "";
      if (src.kind === "stock") { const obs = (src.observed || []).filter((o) => o <= flowWindowMonths().slice(-1)[0]).pop(); when = ` — survey round ${obs}`; }
      return `<span class="ok">Showing: ${SOURCE_SHORT[src.key] || src.key}${when}.</span> ${FLOW_EXPLAIN[src.key] || src.label}`;
    }).join("<br>");
  }
  function drawFlows() {
    if (state.flowLayer) { map.removeLayer(state.flowLayer); state.flowLayer = null; }
    const F = state.flows;
    if (!F) return;
    const ms = flowWindowMonths();
    const agg = new Map(), used = new Set();
    if (state.flowOn) for (const m of ms) {
      const pick = sourceForMonth(m); if (pick < 0) continue;
      used.add(pick);
      for (const [si, a, b, r, n] of F.months[m] || []) {
        if (si !== pick) continue;
        if (state.flowReasons && !state.flowReasons.has(F.reasons[r])) continue;
        const k = `${si}|${a}|${b}|${r}`; agg.set(k, (agg.get(k) || 0) + n);
      }
    }
    const st = $("#flow-status"); if (st) st.innerHTML = state.flowOn ? flowStatus(used) : "";
    if (!state.flowOn) return;
    const list = [...agg.entries()].map(([k, n]) => { const [si, a, b, r] = k.split("|").map(Number); return { si, a, b, r, n }; })
      .sort((x, y) => y.n - x.n).slice(0, 200);
    state.flowLayer = L.layerGroup().addTo(map);
    ensureArrowDefs();
    const crossingsUsed = new Map();
    for (const f of list) {
      const src = F.sources[f.si], A = F.nodes[f.a], B = F.nodes[f.b], reason = F.reasons[f.r];
      const [color, rlabel] = REASON_STYLE[reason] || REASON_STYLE.other;
      const w = Math.max(1.3, Math.min(14, 11 * Math.sqrt(f.n / (src.max || 1))));
      if (!String(A[3]).startsWith("SS")) crossingsUsed.set(f.a, (crossingsUsed.get(f.a) || 0) + f.n);
      const line = L.polyline(bezier(A, B, 0.12 + 0.03 * f.r), {
        renderer: flowRenderer, pane: "flows", color, weight: w, opacity: 0.85, lineCap: "round",
      }).bindTooltip(`<b>${A[2]} → ${B[2]}</b><br>${rlabel} · <b>${f.n.toLocaleString()}</b> people<br><span style="color:var(--muted)">${SOURCE_SHORT[src.key] || src.key} · ${windowLabel(state.t)}${src.kind === "stock" ? " · stock at the latest survey round, not monthly movement" : ""}</span>`, { sticky: true });
      line.addTo(state.flowLayer);
      if (line._path) line._path.setAttribute("marker-end", `url(#ah-${f.r})`);
    }
    for (const [ni, n] of crossingsUsed) {
      const N = F.nodes[ni];
      L.circleMarker([N[0], N[1]], { pane: "flows", radius: 6, color: "#0b0b0b", weight: 2, fillColor: "#ffffff", fillOpacity: 1 })
        .bindTooltip(`${N[2]}<br><b>${n.toLocaleString()}</b> people arriving`, { permanent: false, direction: "top" }).addTo(state.flowLayer);
    }
  }
  function renderFlowControls() {
    const F = state.flows, el = $("#flow-controls"); if (!F || !el) return;
    const used = new Set(); Object.values(F.months).forEach((rows) => rows.forEach((r) => used.add(F.reasons[r[3]])));
    state.flowReasons = new Set(used);
    let h = `<div class="var-row"><input type="checkbox" id="flow-on" checked><label for="flow-on"><b>Show migration arrows</b> <span class="meta">(arrow width ∝ √people; colour = reason)</span></label></div>`;
    h += `<div class="group-title">Data shown</div>`;
    const opt = (val, lab, meta) => `<div class="var-row"><input type="radio" name="flow-src" value="${val}" id="fs-${val}" ${state.flowMode === val ? "checked" : ""}><label for="fs-${val}">${lab} <span class="meta">${meta}</span></label></div>`;
    h += opt("best", "Best available each month", "· Event Tracking, else Flow Monitoring, else latest Mobility Tracking survey");
    F.sources.forEach((x) => { h += opt(x.key, SOURCE_SHORT[x.key] || x.key, `· ${x.kind === "stock" ? `${(x.observed || []).length} survey rounds (stock)` : `${x.months.length} months`}`); });
    h += `<div class="group-title">Reason</div>`;
    F.reasons.filter((r) => used.has(r)).forEach((r) => { const [c, lab] = REASON_STYLE[r] || REASON_STYLE.other;
      h += `<div class="var-row"><input type="checkbox" class="flow-reason" value="${r}" id="fr-${r}" checked><span class="swatch" style="background:${c}"></span><label for="fr-${r}">${lab}</label></div>`; });
    h += `<p class="hint">○ White circles on the border = crossing points where people arrived from neighbouring countries.</p><p class="hint" id="flow-status"></p>`;
    el.innerHTML = h;
    $("#flow-on").onchange = (e) => { state.flowOn = e.target.checked; drawFlows(); };
    el.querySelectorAll('input[name="flow-src"]').forEach((rb) => (rb.onchange = () => { state.flowMode = rb.value; drawFlows(); }));
    el.querySelectorAll(".flow-reason").forEach((cb) => (cb.onchange = () => { cb.checked ? state.flowReasons.add(cb.value) : state.flowReasons.delete(cb.value); drawFlows(); }));
  }


  // ---------- national timeline (bottom strip) ----------
  const NATIONAL = [
    { label: "US government humanitarian funding (OCHA FTS)", ids: ["fts_us_gov_funding_month_usd"], how: "national", units: "USD / month", color: "#2a78d6" },
    { label: "USAID disbursements (ForeignAssistance.gov)", ids: ["usaid_disbursed_month_usd"], how: "national", units: "USD / month", color: "#2a78d6" },
    { label: "All humanitarian funding (OCHA FTS)", ids: ["fts_hum_funding_month_usd"], how: "national", units: "USD / month", color: "#2a78d6" },
    { label: "Humanitarian Response Plan coverage (OCHA FTS)", ids: ["hrp_coverage_year"], how: "national", scale: 100, units: "% funded", color: "#2a78d6" },
    { label: "UNMISS uniformed personnel (UN DPO)", ids: ["unmiss_uniformed_personnel"], how: "national", units: "personnel", color: "#6250d6" },
    { label: "People newly displaced or returning (IOM ET, all counties)", ids: ["et_ind_total"], how: "sum", units: "people / month", color: "#e34948" },
    { label: "Conflict fatalities (ACLED political violence)", ids: ["acled_pv_fatalities"], how: "sum", units: "deaths / month", color: "#e34948" },
    { label: "Within-county / intercommunal violence events", ids: ["intracounty_conflict_events", "ucdp_non_state_events"], how: "sum", units: "events / month", color: "#e34948" },
    { label: "Sexual violence events (ACLED, gender-based violence)", ids: ["acled_st_sexual_violence_events"], how: "state_sum", units: "events / month", color: "#e87ba4" },
    { label: "Sexual-violence incidents (Insecurity Insight, national)", ids: ["ii_sexual_violence_incidents"], how: "national", units: "incidents / month", color: "#e87ba4" },
    { label: "Attacks on aid workers (Insecurity Insight, national)", ids: ["ii_aid_worker_incidents"], how: "national", units: "incidents / month", color: "#e34948" },
    { label: "Flood / surface-water extent (all counties)", ids: ["flood_s1_km2", "flood_gfm_km2", "flood_km2", "surface_water_km2"], prefix: "flood_", suffix: "_km2", how: "sum", units: "km²", color: "#1baf7a" },
    { label: "Drought index (national mean; ensemble if available)", ids: ["drought_ensemble_mean", "spei3"], how: "mean", units: "index", color: "#eb6834" },
    { label: "Rainfall (national mean, IMERG)", ids: ["precip_mm"], how: "mean", units: "mm / month", color: "#2a78d6" },
    { label: "Vegetation greenness NDVI (national mean)", ids: ["modis_ndvi"], how: "mean", units: "NDVI", color: "#008300" },
  ];
  state.natCharts = [];
  function natVar(spec) {
    let id = spec.ids.find((x) => state.varById[x]);
    if (!id && spec.prefix) id = (state.vars.find((v) => v.id.startsWith(spec.prefix) && v.id.endsWith(spec.suffix || "")) || {}).id;
    return id ? state.varById[id] : null;
  }
  function nationalSeries(spec, v) {
    const s = state.series[v.id]; if (!s) return null;
    const ids = Object.keys(s), n = state.months.length, out = new Array(n).fill(null);
    let rows = ids;
    if (spec.how === "national") rows = [ids.find((c) => s[c].some((x) => x != null))].filter(Boolean);
    if (spec.how === "state_sum") {  // state totals are repeated on each county: take one county per state
      const seen = new Set(); rows = [];
      countyLayer.eachLayer((l) => { const p = l.feature.properties; if (!seen.has(p.admin1) && s[p.district_id]) { seen.add(p.admin1); rows.push(p.district_id); } });
    }
    for (let i = 0; i < n; i++) {
      let tot = 0, k = 0;
      for (const c of rows) { const x = s[c][i]; if (x != null && isFinite(x)) { tot += x; k++; } }
      if (k) out[i] = (spec.how === "mean" ? tot / k : tot) * (spec.scale || 1);
    }
    return out;
  }
  async function renderNational() {
    const box = $("#nat-charts"); if (!box) return;
    state.natCharts.forEach((c) => c.destroy()); state.natCharts = []; box.innerHTML = "";
    const ink2 = getComputedStyle(document.documentElement).getPropertyValue("--ink-2").trim();
    const line = getComputedStyle(document.documentElement).getPropertyValue("--line").trim();
    for (const spec of NATIONAL) {
      const v = natVar(spec); if (!v) continue;
      try { await ensureSeries(v.id); } catch (e) { continue; }
      const data = nationalSeries(spec, v); if (!data || !data.some((x) => x != null)) continue;
      const tile = document.createElement("div"); tile.className = "nat-tile";
      tile.innerHTML = `<div class="nt-l" title="${v.label}">${spec.label}</div><div class="nt-v"></div><canvas></canvas>`;
      box.appendChild(tile);
      const chart = new Chart(tile.querySelector("canvas"), {
        type: "line",
        data: { labels: state.months, datasets: [{ data, borderColor: spec.color, borderWidth: 1.6, pointRadius: 0, pointHitRadius: 6, spanGaps: false, tension: 0.1 }] },
        options: {
          animation: false, responsive: false, maintainAspectRatio: false,
          plugins: { legend: { display: false }, tooltip: { callbacks: { title: (c) => monthLabel(c[0].dataIndex), label: (c) => `${fmt(c.raw)} ${spec.units}` } } },
          scales: { x: { display: true, ticks: { color: ink2, font: { size: 9 }, maxTicksLimit: 4, callback: (val, i) => state.months[i].slice(0, 4) }, grid: { display: false } },
                    y: { ticks: { color: ink2, font: { size: 9 }, maxTicksLimit: 3, callback: (x) => fmt(x, 2) }, grid: { color: line } } },
          onClick: (evt, els, ch) => { const i = Math.round(ch.scales.x.getValueForPixel(evt.x)); if (i >= 0 && i < state.months.length) setTime(i); },
        },
        plugins: [{ id: "cursor", afterDraw(c) { const { ctx, chartArea: a, scales } = c; const x = scales.x.getPixelForValue(state.t);
          ctx.save(); ctx.strokeStyle = "#eb6834"; ctx.lineWidth = 1.5; ctx.beginPath(); ctx.moveTo(x, a.top); ctx.lineTo(x, a.bottom); ctx.stroke(); ctx.restore(); } }],
      });
      chart._spec = spec; chart._tile = tile;
      state.natCharts.push(chart);
    }
    updateNational();
  }
  function updateNational() {
    for (const c of state.natCharts) {
      const x = c.data.datasets[0].data[state.t];
      c._tile.querySelector(".nt-v").textContent = `${monthLabel(state.t)}: ${x == null ? "–" : fmt(x)} ${c._spec.units}`;
      c.draw();
    }
  }

  // ---------- time ----------
  function setTime(i) {
    state.t = i;
    $("#time").value = i;
    $("#time-label").textContent = windowLabel(i);
    refreshCounties(); updateRasters(); refreshPoints(); drawFlows(); updateNational();
    if (state.selected) renderDetail();
  }
  function togglePlay() {
    if (state.timer) { clearInterval(state.timer); state.timer = null; $("#play").textContent = "▶"; return; }
    $("#play").textContent = "❚❚";
    state.timer = setInterval(() => {
      const idx = windowIdx(state.t);
      let next = idx[idx.length - 1] + 1;
      if (next >= state.months.length) next = 0;
      setTime(next);
    }, 900);
  }

  // ---------- boot ----------
  async function boot() {
    const [vj, counties, layers] = await Promise.all([
      fetchJSON("data/variables.json"), fetchJSON("data/counties.geojson"), fetchJSON("data/layers.json").catch(() => ({ points: [], rasters: [] })),
    ]);
    state.months = vj.months;
    if (vj.bundle) state.bundle = fetchJSON(vj.bundle);
    state.vars = vj.variables;
    state.vars.forEach((v) => (state.varById[v.id] = v));
    state.rasters = layers.rasters || [];
    state.points = layers.points || [];
    fetchJSON("data/trends.json").then((t) => { state.trends = t; state.vars.forEach((v) => (v._trendSpan = null)); refreshCounties(); renderLegend(); }).catch(() => {});
    fetchJSON("data/profiles.json").then((pj) => { state.profiles = pj; }).catch(() => {});
    SPARKS.forEach((sp) => { const v = sparkVar(sp); if (v) ensureSeries(v.id).catch(() => {}); if (sp.band && state.varById[sp.band]) ensureSeries(sp.band).catch(() => {}); });
    fetchJSON("data/flows.json").then((f) => { state.flows = f; renderFlowControls(); drawFlows(); }).catch((e) => console.warn("no flows", e));
    $("#time").max = state.months.length - 1;

    countyLayer = L.geoJSON(counties, {
      style: styleCounty,
      onEachFeature: (f, l) => {
        l.bindTooltip(() => tooltipHtml(f.properties), { sticky: true, className: "county-tt" });
        l.on("click", () => { state.selected = f.properties.district_id; refreshCounties(); renderDetail(); });
        l.on("mouseover", () => l.setStyle({ weight: 2.5, color: "#0b0b0b" }));
        l.on("mouseout", () => countyLayer.resetStyle(l));
      },
    }).addTo(map);
    map.fitBounds(countyLayer.getBounds(), { padding: [10, 10] });

    $("#mode").onchange = (e) => { state.mode = e.target.value; document.body.dataset.mode = state.mode; state.vars.forEach((v) => { if (usesDiff(v) && state.series[v.id]) computeDiffSpan(v); }); refreshCounties(); renderLegend(); renderDetail(); };
    $("#agg").onchange = (e) => { state.agg = e.target.value; state.vars.forEach((v) => { if (usesDiff(v) && state.series[v.id]) computeDiffSpan(v); }); setTime(state.t); renderLegend(); };
    $("#time").oninput = (e) => setTime(+e.target.value);
    $("#play").onclick = togglePlay;
    $("#filter").oninput = renderVarList;
    $("#raster-opacity").oninput = updateRasters;
    $("#detail-close").onclick = () => { state.selected = null; refreshCounties(); renderDetail(); };

    renderRasterList(); renderPointList();
    const first = state.vars.find((v) => v.id === "precip_mm") || state.vars[0];
    if (first) await setColorBy(first.id); else renderVarList();
    renderNational().then(() => map.invalidateSize()).catch((e) => console.warn("national", e));
    setTime(state.months.indexOf("2019-08") >= 0 ? state.months.indexOf("2019-08") : 0);
  }
  boot().catch((e) => { console.error(e); $("#var-list").innerHTML = `<p class="empty">Could not load data: ${e.message}</p>`; });
})();
