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
  // direction-word palettes: [up ramp, down ramp]
  const DIR_PALETTES = {
    wetter_drier: [["#c7eae5", "#5ab4ac", "#01665e", "#003c30"], ["#f6e8c3", "#d8b365", "#8c510a", "#543005"]],
    warmer_cooler: [["#fbc4a6", "#f0805a", "#d03b3b", "#8a1f1f"], ["#cde2fb", "#86b6ef", "#2a78d6", "#104281"]],
    greener_browner: [["#c7e9c0", "#74c476", "#238b45", "#00441b"], ["#f6e8c3", "#d8b365", "#8c510a", "#543005"]],
  };
  const DIR_WORDS = { wetter_drier: ["wetter", "drier"], warmer_cooler: ["warmer", "cooler"], greener_browner: ["greener", "browner"] };
  const CATEGORICAL = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300", "#6250d6", "#e34948"];

  const MONTH_NAMES = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
  const state = {
    months: [], vars: [], varById: {}, series: {}, checked: new Set(), colorBy: null,
    mode: "trend", agg: "month", t: 0, selected: null,
    rasters: [], rasterOn: new Set(), rasterLayers: {}, points: [], pointLayers: {},
    timer: null, charts: [], natExtra: new Set(), selectedList: [], compareMode: false,
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
    const Y = trendYear();
    if (Y < 2025 && tr[T_TODATE]) { const x = tr[T_TODATE][Y - 2020]; return x == null ? null : x; }
    return trendIsPct(v) ? tr[T_PCT] : tr[T_SEN];
  }
  // a "% of 2018 level" only makes sense for positive quantities with a meaningful zero
  const trendIsPct = (v) => v.index_ok !== false && !v.sparse_count && !v.national_only &&
    !/%|standard|flag|index|\bsd\b|°|deg|class|share|fraction|anomal/i.test(`${v.units || ""} ${v.id}`);
  function valueAt(v, c, i, mode = state.mode) {
    if (mode === "trend") return trendValue(v, c);
    const s = state.series[v.id]; if (!s || !s[c]) return null;
    const arr = s[c];
    const wvals = windowIdx(i).map((j) => arr[j]);
    const raw = mean(wvals);
    if (raw == null) return null;
    // counts (people, events, deaths…) are totals over a season/year in raw mode
    if (mode === "raw" && v.aggregate === "sum" && state.agg !== "month") return wvals.reduce((a, x) => a + (x != null && isFinite(x) ? x : 0), 0);
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
      const pal = DIR_PALETTES[v.direction];
      const up = pal ? pal[0] : v.higher_is === "better" ? DIV_GOOD : v.higher_is === "worse" ? DIV_BAD : DIV_UP_NEUTRAL;
      const down = pal ? pal[1] : v.higher_is === "better" ? DIV_BAD : v.higher_is === "worse" ? DIV_GOOD : DIV_DOWN_NEUTRAL;
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
  L.control.layers(base, null, { position: "topleft" }).addTo(map);
  map.createPane("rasters").style.zIndex = 350;
  map.createPane("counties").style.zIndex = 400;
  map.createPane("flows").style.zIndex = 450;
  map.createPane("points").style.zIndex = 600;
  let countyLayer;

  // ---------- trends (Mann-Kendall / Sen's slope, computed by scripts/trend_stats.py) ----------
  const T_P = 0, T_Q = 1, T_SEN = 2, T_PCT = 3, T_TAU = 4, T_N = 5, T_SIG = 6, T_TEST = 7, T_TXT = 8, T_LISA = 9, T_PNAIVE = 10, T_TODATE = 11, T_BASIS = 12;
  const BASIS_TXT = { wet_season: "Jun–Sep wet-season total", flood_season: "Aug–Nov flood-season average", annual_total: "annual totals", seasonal: "same-month comparisons" };
  // trend map follows the slider: Sen's slope from 2018 to the slider's year (needs ≥3 years, so 2020 at the earliest)
  const trendYear = () => Math.min(2025, Math.max(2020, +state.months[state.t].slice(0, 4)));
  const trendOf = (vid, cid) => (state.trends && state.trends[vid] && state.trends[vid][cid]) || null;
  function trendHtml(v, cid, compact) {
    const tr = trendOf(v.id, cid);
    if (!tr) return v.temporal === "static" ? `<div class="trend muted">Static layer: no trend test.</div>` : `<div class="trend muted">No trend test (too few observations).</div>`;
    const sigTxt = tr[T_SIG] ? `<span class="sig-badge">◆ Significant trend</span>` : `<span class="nosig-badge">No significant trend</span>`;
    const slope = tr[T_SEN] == null ? "n/a" : `${tr[T_SEN] >= 0 ? "+" : ""}${fmt(tr[T_SEN])} ${v.units || ""}/yr`;
    const pct = tr[T_PCT] == null || !trendIsPct(v) ? "" : ` (${tr[T_PCT] >= 0 ? "+" : ""}${fmt(tr[T_PCT], 2)}%/yr)`;
    const stats = `${tr[T_TEST] === "S" ? "Seasonal Mann-Kendall test, corrected for month-to-month persistence (Hirsch–Slack)" : "Mann-Kendall test, corrected for persistence where possible (Hamed–Rao)"}: p = ${fmt(tr[T_P], 2)}${tr[T_PNAIVE] != null ? ` (uncorrected ${fmt(tr[T_PNAIVE], 2)})` : ""}, FDR q = ${fmt(tr[T_Q], 2)}, n = ${tr[T_N]}${tr[T_LISA] && tr[T_LISA] !== "ns" ? ` · ${{ HH: "part of a cluster of counties with similarly high trends", LL: "part of a cluster of counties with similarly low trends", HL: "higher trend than its neighbours", LH: "lower trend than its neighbours" }[tr[T_LISA]]} (Local Moran's I)` : ""}`;
    return `<div class="trend">${sigTxt}<div class="trend-txt">${tr[T_TXT]}</div>${compact ? "" : `<div class="trend-stats">${stats}</div>`}</div>`;
  }

  function styleCounty(f) {
    const v = state.varById[state.colorBy];
    const si = state.selectedList.indexOf(f.properties.district_id), selected = si >= 0;
    const baseStyle = { color: selected ? (state.selectedList.length > 1 ? COUNTY_COLORS[si] : "#0b0b0b") : "#898781", weight: selected ? 3 : 0.7, pane: "counties", dashArray: null };
    if (!v) return { ...baseStyle, fillOpacity: 0 };
    const x = valueAt(v, f.properties.district_id, state.t);
    const col = scaleFor(v).color(x);
    const rasterVisible = state.rasterOn.size > 0;
    const tr = trendOf(v.id, f.properties.district_id);
    if (tr && tr[T_SIG] && !selected && (state.mode !== "trend" || trendYear() === 2025)) { baseStyle.color = "#ffffff"; baseStyle.weight = 2.6; }
    if (col == null) return { ...baseStyle, fillColor: "#898781", fillOpacity: rasterVisible ? 0 : 0.08, dashArray: "2 3" };
    return { ...baseStyle, fillColor: col, fillOpacity: rasterVisible ? 0.35 : 0.78 };
  }

  // ---------- hover card: profile + trend + sparklines ----------
  const SPARKS = [
    { label: "Forced migration (people displaced/returning, IOM ET)", ids: ["et_ind_total"], color: "#e34948" },
    { label: "US humanitarian funding — national (OCHA FTS, USD/month)", ids: ["fts_us_gov_funding_month_usd", "us_aid_disbursed_month_usd"], color: "#2a78d6" },
    { label: "Surface water / flood extent, all seasons (MODIS, % of county)", ids: ["surface_water_pct"], color: "#1baf7a" },
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
    return `<div class="profile">${lz}${part(pr.livelihoods)}${part(pr.conflict_impact)}</div>`;
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
      const Y = trendYear(), dw = DIR_WORDS[v.direction], word = dw ? ` — ${x > 0 ? dw[0] : x < 0 ? dw[1] : "no change"}` : "";
      const basis = v.trend_basis && ["wet_season", "flood_season", "annual_total"].includes(v.trend_basis) ? ` (${BASIS_TXT[v.trend_basis]})` : "";
      if (trendIsPct(v)) { const f = Math.max(0, 1 + (x * (Y - 2018)) / 100); return `${x >= 0 ? "+" : ""}${fmt(x, 2)}% of ${v.baseline_year} level per year${basis}, 2018→${Y} (≈${fmt(f, 2)}×)${word}`; }
      return `${x >= 0 ? "+" : ""}${fmt(x)} ${(v.units || "").replace(/\s*\/\s*month/, basis ? "" : "/month")} per year${basis}, 2018→${Y}${word}`;
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
    let html = `<div class="title">${v.label}${state.mode === "trend" && v.temporal !== "static" ? ` — trend 2018→${trendYear()}` : ""}</div>`;
    if (v.national_only) html += `<div class="caution">National-only series: the same value for every county.</div>`;
    if (plainOf(v)) html += `<div class="var-plain">${plainOf(v)}</div>`;
    if (v.caution) html += `<div class="caution">⚠ ${v.caution}</div>`;
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
      const dw = DIR_WORDS[v.direction];
      const dir = dw ? `${sc.kind === "trend" ? "Trend towards" : "Colour shows"}: ${dw[0]} (right) vs ${dw[1]} (left)${sc.kind === "trend" ? "" : " than the baseline"} — not “better” or “worse”`
        : v.higher_is === "neutral" ? "Purple = higher, orange = lower than baseline"
        : `Blue = better, red = worse than baseline (higher is ${v.higher_is})`;
      html += `<div class="note">${dir}${sc.kind === "diff" ? ` · change in ${v.units || "units"} (ratio not meaningful)` : ""}</div>`;
      if (sc.kind === "trend") html += `<div class="note"><b>Trend 2018→${trendYear()} (Sen's slope)</b>${v.trend_basis && BASIS_TXT[v.trend_basis] ? `, based on ${BASIS_TXT[v.trend_basis]}` : ""}. Move the time slider to see how the trend developed (first available: 2018→2020). ${trendYear() < 2025 ? "White significance outlines appear for the full 2018→2025 period. " : ""}The median yearly change in each county's series${tpct ? `, as a % of its ${v.baseline_year} level; × = implied change from 2018 to 2025 (e.g. +10%/yr ≈ 1.7×)` : ` in ${v.units || "units"} per year (a % of baseline is not meaningful for this variable)`}. Monthly series use the seasonal Sen's slope. This map does not change with the time slider; arrows and points do.</div>`;
      else if (v.sparse_count) html += `<div class="note">Sparse count: shown as change from the ${v.baseline_year} monthly average (most ${v.baseline_year} months were zero, so a ratio is undefined).</div>`;
      else if (state.mode === "index_month") html += `<div class="note">Compared with the same ${state.agg === "month" ? "month" : state.agg === "season" ? "season" : "year"} in ${v.baseline_year}.</div>`;
    }
    if (v.baseline_year && v.baseline_year !== 2018 && isIndexMode()) html += `<div class="note">⚠ Source starts in ${v.baseline_year}; baseline = ${v.baseline_year}.</div>`;
    if (v.temporal && v.temporal !== "monthly") html += `<div class="note">Time step of source: ${v.temporal}${v.carry_forward_months ? ` (latest value carried forward up to ${v.carry_forward_months} months)` : ""}.</div>`;
    if (state.trends && state.trends[v.id]) {
      const nSig = Object.values(state.trends[v.id]).filter((t) => t[T_SIG]).length;
      const reg = v.regional || {}, rtxt = (k, lab) => reg[k] ? `${lab}: median ${trendIsPct(v) && reg[k].median_pct != null ? `${reg[k].median_pct >= 0 ? "+" : ""}${fmt(reg[k].median_pct, 2)}%/yr` : `${fmt(reg[k].median_slope)} ${v.units || ""}/yr`}, regional Kendall p = ${fmt(reg[k].p, 2)}${reg[k].p < 0.05 ? " <b>(significant)</b>" : ""}` : "";
      if (reg.national || reg.sudd) html += `<div class="note"><b>Regional trend</b> (pools counties; bootstrap over years keeps spatial & seasonal correlation) — ${[rtxt("national", "all counties"), rtxt("sudd", "Sudd")].filter(Boolean).join(" · ")}</div>`;
      if (v.trend_moran_I != null) html += `<div class="note"><b>Spatial clustering of trends</b>: Moran's I = ${fmt(v.trend_moran_I, 2)} (p = ${fmt(v.trend_moran_p, 2)})${v.trend_moran_p < 0.05 ? " — neighbouring counties trend alike, so read trends regionally" : ""}.</div>`;
      html += `<div class="note"><span class="sig-swatch"></span> White outline = significant 2018–2025 trend (Mann-Kendall corrected for month-to-month persistence, then false-discovery-rate q &lt; 0.05 across counties): ${nSig} of 79 counties. Hover for Sen's slope.</div>`;
    }
    html += `<div class="note"><span class="nodata"></span> no data · Source: ${v.source || "–"}${v.native_resolution ? ` · ${v.native_resolution}` : ""}</div>`;
    const rs = [...state.rasterOn].map((k) => (state.mode === "trend" && state.rasters.find((r) => r.key === `${k}_trend`)) || state.rasters.find((r) => r.key === k)).filter(Boolean);
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
    let lastCat = null, lastGroup = null, shown = 0;
    const matcher = searchMatcher(q);
    const topicIds = state.topic && state.topicPicks ? null : null;
    for (const v of state.vars) {
      if (q && !matcher(v)) continue;
      if (state.topic && v.topic !== state.topic && !(state.topicPicks[state.topic] || []).includes(v.id)) continue;
      shown++;
      if (v.category !== lastCat) {
        el.insertAdjacentHTML("beforeend", `<div class="cat-title">${v.category === "human" ? "Human & infrastructure" : v.category === "environment" ? "Environment & climate" : v.category}</div>`);
        lastCat = v.category; lastGroup = null;
      }
      if (v.group !== lastGroup) { el.insertAdjacentHTML("beforeend", `<div class="group-title">${v.group}</div>`); lastGroup = v.group; }
      const row = document.createElement("div");
      row.className = "var-row";
      const id = `cb-${v.id}`;
      const cov = `${v.first_period.slice(0, 4)}–${v.last_period.slice(0, 4)}${v.temporal && v.temporal !== "monthly" ? ", " + v.temporal : ""}`;
      if (v.national_only) {
        row.innerHTML = `<span class="colorby nat" title="National-only series: shown in the National timeline, not on the county map">N</span>
          <input type="checkbox" id="${id}" ${state.natExtra.has(v.id) ? "checked" : ""}>
          <label for="${id}">${v.label} <span class="meta">· national only — adds a chart to the National timeline</span></label>`;
        row.querySelector("input").onchange = (e) => { e.target.checked ? state.natExtra.add(v.id) : state.natExtra.delete(v.id); renderNational(); writeHash(); };
        el.appendChild(row); continue;
      }
      row.innerHTML = `<button class="colorby ${state.colorBy === v.id ? "on" : ""}" title="Colour the map by this variable" aria-label="Colour map by ${v.label}"></button>
        <input type="checkbox" id="${id}" ${state.checked.has(v.id) ? "checked" : ""}>
        <label for="${id}">${v.label} <span class="meta">${v.units ? "· " + v.units + " " : ""}(${cov})</span></label>
        ${state.colorBy === v.id || state.checked.has(v.id) ? `<div class="var-plain">${plainOf(v)}</div>` : ""}`;
      row.querySelector("button").onclick = () => setColorBy(v.id);
      row.querySelector("input").onchange = (e) => {
        if (e.target.checked) { state.checked.add(v.id); if (!state.colorBy) setColorBy(v.id); else ensureSeries(v.id).then(renderDetail); }
        else { state.checked.delete(v.id); if (state.colorBy === v.id) setColorBy([...state.checked][0] || null); renderDetail(); }
      };
      el.appendChild(row);
    }
    if (q && !shown) el.innerHTML = `<p class="empty">No variables match “${q.replace(/</g, "&lt;")}”. Try: flood, rain, drought, heat, fighting, displaced, food prices, aid, pollution.</p>`;
  }

  // ---------- guided topic picks ----------
  function renderTopics() {
    const el = $("#topic-picks"); if (!el || !state.topicPicks) return;
    const topics = Object.keys(state.topicPicks);
    el.innerHTML = `<div class="topic-head">Start with a question:</div><div class="topic-chips">${topics.map((t) => `<button class="chip ${state.topic === t ? "on" : ""}" data-t="${t}">${t}</button>`).join("")}${state.topic ? `<button class="chip clear" data-t="">Show all</button>` : ""}</div>`;
    el.querySelectorAll("button").forEach((b) => (b.onclick = async () => {
      const t = b.dataset.t; state.topic = t || null;
      if (t) {
        const picks = (state.topicPicks[t] || []).filter((id) => state.varById[id] && !state.varById[id].national_only);
        picks.slice(0, 3).forEach((id) => state.checked.add(id));
        if (picks[0]) await setColorBy(picks[0]);
      }
      renderTopics(); renderVarList();
    }));
  }

  // ---------- search: plain words, plurals and synonyms; matches labels, topics, definitions (not source names) ----------
  const SYN = {
    flood: ["flood", "inundat", "surface water", "water extent", "sudd", "sentinel-1"], water: ["water", "flood", "inundat", "wetland", "sudd", "groundwater", "storage"],
    rain: ["rain", "precip", "chirps", "imerg", "wet"], drought: ["drought", "spei", "pdsi", "dry", "deficit"], dry: ["dry", "drought", "deficit"],
    heat: ["temperature", "\\btmax", "\\blst", "hottest", "heat", "warm"], hot: ["temperature", "hottest", "heat"], temperature: ["temperature", "\\btmax", "\\btmin", "lst"],
    displaced: ["displac", "\\bidp", "et_ind", "migration", "flow monitoring", "returnee", "refugee", "arriv"], displacement: ["displac", "\\bidp", "migration", "returnee"],
    migration: ["migration", "displac", "flow monitoring", "arriv", "returnee"], refugee: ["refugee", "unhcr", "arriv"], idp: ["\\bidp", "displac"],
    fighting: ["conflict", "acled", "ucdp", "violence", "clash", "battle", "attack", "fatalit"], conflict: ["conflict", "acled", "ucdp", "violence", "clash", "fatalit"],
    violence: ["violence", "acled", "ucdp", "attack", "sexual"], war: ["conflict", "acled", "ucdp", "sudan"],
    pollution: ["pollution", "aerosol", "\\bno2", "\\bco\\b", "s5p", "air quality", "dust", "smoke", "oil", "contamin"], air: ["aerosol", "no2", "air", "dust", "smoke"],
    fire: ["fire", "burn", "viirs"], vegetation: ["ndvi", "evi", "vegetation", "green"], crops: ["crop", "ndvi", "land cover"],
    food: ["food", "ipc", "price", "hunger", "malnutrition", "nutrition"], hunger: ["ipc", "food", "malnutrition", "hunger"], price: ["price", "wfp", "exchange"],
    aid: ["aid", "funding", "usaid", "fts", "humanitarian", "hrp", "partner"], funding: ["funding", "usaid", "fts", "aid"], money: ["funding", "usaid", "fts", "price"],
    women: ["women", "girls", "gender", "sexual", "gbv", "wps"], gbv: ["gbv", "sexual", "gender", "protection"], gender: ["gender", "women", "gbv", "wps"],
    health: ["health", "hospital", "vaccin", "mortality", "cholera"], school: ["school", "educat", "enrol"], peacekeeping: ["unmiss", "peacekeep"], un: ["unmiss", "un "],
    cattle: ["cattle", "livestock", "goat", "sheep", "graz"], population: ["population", "worldpop", "people"], oil: ["oil", "pipeline", "well"],
  };
  const stem = (w) => w.replace(/(ings|ing|ies|es|s|ed)$/i, "");
  function searchMatcher(q) {
    const words = q.split(/\s+/).filter(Boolean);
    const pats = words.map((w) => {
      const key = Object.keys(SYN).find((k) => stem(k) === stem(w) || k === w);
      const alts = [w.replace(/[.*+?^${}()|[\]\\]/g, "\\$&"), stem(w).replace(/[.*+?^${}()|[\]\\]/g, "\\$&")].filter((x) => x.length > 1).map((x) => `\\b${x}`);
      if (key) alts.push(...SYN[key]);
      return new RegExp(alts.join("|"), "i");
    });
    return (v) => {
      const hay = `${v.label} ${v.id.replace(/_/g, " ")} ${v.group || ""} ${v.topic || ""} ${v.plain || ""} ${(v.synonyms || []).join(" ")}`;
      return pats.every((re) => re.test(hay));
    };
  }
  const plainOf = (v) => (v.plain || v.notes || "").split(/(?<=\.)\s/)[0].slice(0, 220);

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
    renderVarList(); refreshCounties(); renderLegend(); renderDetail(); writeHash();
  }

  function renderRasterList() {
    const el = $("#raster-list");
    if (!state.rasters.length) { el.innerHTML = `<p class="empty">No raster overlays built yet.</p>`; return; }
    el.innerHTML = "";
    for (const r of state.rasters.filter((x) => !x.trend_of && !/_trend$/.test(x.key))) {
      const hasTrend = state.rasters.some((x) => x.key === `${r.key}_trend`);
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
      let r = state.rasters.find((x) => x.key === key);
      // in trend mode, show the "trend 2018→slider year" companion layer when it exists
      const tr = state.mode === "trend" && state.rasters.find((x) => x.key === `${key}_trend`);
      let d;
      if (tr) { r = tr; d = String(trendYear()); if (!(tr.dates || []).includes(d)) d = (tr.dates || []).filter((x) => x <= d).pop() || (tr.dates || [])[0]; }
      else d = rasterDateFor(r, state.t);
      const shownKey = r.key;
      if (!d) continue;
      let url = `rasters/${shownKey}/${d}.png`;
      if (r.packed) {
        const y = d.slice(0, 4);
        r._maps = r._maps || {}; r._pending = r._pending || {};
        if (!r._maps[y]) {
          if (!r._pending[y]) r._pending[y] = fetchJSON(`rasters/${shownKey}/${y}.json`).then((m) => { r._maps[y] = m; updateRasters(); });
          continue;
        }
        url = r._maps[y][d];
        if (!url) continue;
      }
      const b = r.bounds;
      if (state.rasterLayers[key]) { state.rasterLayers[key].setUrl(url); state.rasterLayers[key].setBounds(L.latLngBounds(b)); state.rasterLayers[key].setOpacity(op); }
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
      row.innerHTML = `<input type="checkbox" id="p-${p.key}"><span class="swatch" style="background:${p._color}"></span><label for="p-${p.key}">${p.label}${typeof p.plain === "string" && p.plain ? ` <span class="meta">· ${p.plain.slice(0, 90)}</span>` : ""}</label>`;
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
        return L.circleMarker(ll, { pane: "points", radius: r, color: getComputedStyle(document.documentElement).getPropertyValue("--surface").trim() || "#fff", weight: 1.5, fillColor: p._color, fillOpacity: 0.9 });
      },
      onEachFeature: (f, l) => {
        const pr = f.properties || {};
        const rows = Object.entries(pr).filter(([, val]) => val !== null && val !== "" && typeof val !== "object").slice(0, 12)
          .map(([k, val]) => `<tr><td style="color:var(--muted);padding-right:6px">${k}</td><td>${String(val).slice(0, 120)}</td></tr>`).join("");
        const head = pr.name || pr.facility_name || pr.site_name || pr.title || "";
        const status = pr.status ? `<div><b>Status:</b> ${pr.status}</div>` : "";
        const when = pr.date ? `<div><b>Date:</b> ${String(pr.date).slice(0, 10)}</div>` : (pr.valid_from || pr.valid_to) ? `<div><b>Period:</b> ${pr.valid_from ? String(pr.valid_from).slice(0, 7) : "before 2018"} → ${pr.valid_to ? String(pr.valid_to).slice(0, 7) : "2025+"}</div>` : "";
        const ev = pr.evidence || pr.date_basis ? `<div class="hint">Evidence: ${String(pr.evidence || pr.date_basis).slice(0, 220)}</div>` : "";
        l.bindPopup(`<b>${p.label}</b>${head ? `<div>${head}</div>` : ""}${status}${when}${ev}<details><summary>All fields</summary><table>${rows}</table></details>`);
      },
    }).addTo(map);
  }
  function refreshPoints() { for (const e of Object.values(state.pointLayers)) if (e.timed) drawPoints(e); }

  // ---------- detail panel (docked beside the map; compare up to 3 counties) ----------
  const COUNTY_COLORS = ["#2a78d6", "#eb6834", "#1baf7a"];
  const countyProps = (cid) => { const l = countyLayer.getLayers().find((x) => x.feature.properties.district_id === cid); return l ? l.feature.properties : { name: cid, admin1: "" }; };
  const chartKind = (v) => (/flag/i.test(v.units || "") ? "flag" : /standard|spei|pdsi|drought_ensemble/i.test(`${v.units || ""} ${v.id}`) ? "std" : "raw");
  function openDetail(open) {
    const wrap = $("#mapwrap");
    wrap.classList.toggle("with-detail", open);
    $("#detail").hidden = !open;
    setTimeout(() => map.invalidateSize(), 50);
  }
  function rawWindowSeries(v, cid) {
    const keys = [], labels = [], vals = [], firstIdx = [];
    state.months.forEach((_, i) => { const k = windowKey(i); if (!keys.includes(k)) { keys.push(k); firstIdx.push(i); labels.push(windowLabel(i)); vals.push(valueAt(v, cid, i, "raw")); } });
    return { keys, labels, vals, firstIdx };
  }
  function nowText(v, cid) {
    const raw = valueAt(v, cid, state.t, "raw");
    if (raw == null) return "no data";
    const k = chartKind(v);
    if (k === "flag") return `${fmt(raw)} ${state.agg === "month" ? (raw >= 1 ? "(extreme month)" : "(normal month)") : "months flagged"}`;
    if (k === "std") return `${fmt(raw, 2)} (${raw <= -1.5 ? "very dry" : raw <= -1 ? "dry" : raw >= 1.5 ? "very wet" : raw >= 1 ? "wet" : "near normal"}; below −1 = dry, above +1 = wet)`;
    const idx = valueAt(v, cid, state.t, "index_month");
    const rel = idx == null ? "" : usesDiff(v) ? ` (${idx >= 0 ? "+" : ""}${fmt(idx)} vs ${v.baseline_year})` : ` (${fmt(idx, 2)}× ${state.agg === "month" ? "same month of" : ""} ${v.baseline_year})`;
    return `${fmt(raw)} ${v.units || ""}${rel}`;
  }
  async function renderDetail() {
    const el = $("#detail");
    const sel = state.selectedList;
    if (!sel.length) { openDetail(false); return; }
    openDetail(true);
    const P = sel.map(countyProps);
    $("#detail-title").textContent = sel.length === 1 ? `${P[0].name} County` : `Comparing ${P.map((p) => p.name).join(", ")}`;
    $("#detail-sub").innerHTML = `${sel.length === 1 ? `${P[0].admin1} · ${sel[0]} · ` : ""}${windowLabel(state.t)}`;
    const pbox = document.getElementById("detail-profile") || (() => { const d = document.createElement("div"); d.id = "detail-profile"; $("#detail-sub").after(d); return d; })();
    const pr = state.profiles && state.profiles[sel[0]];
    pbox.innerHTML = `<div class="detail-actions">
        <button id="btn-compare" class="${state.compareMode ? "on" : ""}">${state.compareMode ? "Click a county on the map to add it…" : "＋ Compare another county"}</button>
        <button id="btn-csv">⬇ Download CSV</button><button id="btn-copycsv">Copy data</button><button id="btn-link">🔗 Copy link to this view</button></div>
      ${sel.length > 1 ? `<div class="legend-chips">${P.map((p, i) => `<span><i style="background:${COUNTY_COLORS[i]}"></i>${p.name} <button data-rm="${sel[i]}" title="Remove">×</button></span>`).join("")}</div>` : ""}
      ${sel.length === 1 && pr ? `<details class="profile full" open><summary>${pr.livelihood_zone && pr.livelihood_zone.name ? pr.livelihood_zone.name : "County profile"}</summary>
        ${["livelihoods", "history", "conflict_impact"].map((k) => (pr[k] ? `<p><b>${{ livelihoods: "Livelihoods", history: "History", conflict_impact: "Conflict impact" }[k]}:</b> ${pr[k]}</p>` : "")).join("")}
        ${pr.sources && pr.sources.length ? `<p class="hint">Sources: ${pr.sources.slice(0, 4).map((u, i) => `<a href="${u}" target="_blank" rel="noopener">[${i + 1}]</a>`).join(" ")}</p>` : ""}</details>` : ""}`;
    $("#btn-compare").onclick = () => { state.compareMode = !state.compareMode; renderDetail(); };
    $("#btn-csv").onclick = () => downloadCSV();
    $("#btn-copycsv").onclick = () => copyText(buildCSV(), "Data copied to the clipboard (CSV).");
    $("#btn-link").onclick = () => { writeHash(); copyText(location.href, "Link copied. It reopens this view (variables, counties, month, mode)."); };
    pbox.querySelectorAll("[data-rm]").forEach((b) => (b.onclick = () => { state.selectedList = state.selectedList.filter((c) => c !== b.dataset.rm); state.selected = state.selectedList[0] || null; refreshCounties(); renderDetail(); writeHash(); }));

    state.charts.forEach((c) => c.destroy()); state.charts = [];
    const box = $("#detail-charts"); box.innerHTML = "";
    const ids = [...state.checked].filter((id) => state.varById[id] && !state.varById[id].national_only);
    if (!ids.length) { box.innerHTML = `<p class="empty">Tick variables in the sidebar to see their history here.</p>`; return; }
    await Promise.all(ids.map(ensureSeries));
    const ink2 = getComputedStyle(document.documentElement).getPropertyValue("--ink-2").trim();
    const line = getComputedStyle(document.documentElement).getPropertyValue("--line").trim();

    // Combined comparison chart: every ticked variable on ONE axis, as standard deviations from its own 2018–2025 mean
    if (ids.length > 1 && sel.length === 1) {
      const blk = document.createElement("div"); blk.className = "chart-block";
      blk.innerHTML = `<h3>All ticked variables together</h3><div class="hint">Each line is scaled to its own average (0) and typical variation (±1), using 12-month averages, so different units can share one axis. Up = higher than usual.</div><canvas class="tall"></canvas>`;
      box.appendChild(blk);
      const { labels } = rawWindowSeries(state.varById[ids[0]], sel[0]);
      const datasets = ids.map((id, k) => {
        const v = state.varById[id], arr = (state.series[id] || {})[sel[0]] || [];
        const roll = arr.map((_, i) => { const w = arr.slice(Math.max(0, i - 11), i + 1).filter((x) => x != null && isFinite(x)); return w.length >= 6 ? w.reduce((a, b) => a + b, 0) / w.length : null; });
        const ok = roll.filter((x) => x != null), mu = ok.reduce((a, b) => a + b, 0) / (ok.length || 1);
        const sd = Math.sqrt(ok.reduce((a, b) => a + (b - mu) ** 2, 0) / (ok.length || 1)) || 1;
        const z = roll.map((x) => (x == null ? null : (x - mu) / sd));
        const per = state.months.map((_, i) => i).filter((i) => windowKey(i) !== (i ? windowKey(i - 1) : null));
        return { label: v.label, data: per.map((i) => z[i]), borderColor: CATEGORICAL[k % CATEGORICAL.length], borderWidth: 2, pointRadius: 0, tension: 0.2, spanGaps: false };
      });
      const ch = new Chart(blk.querySelector("canvas"), { type: "line", data: { labels, datasets },
        options: { animation: false, responsive: true, maintainAspectRatio: false, interaction: { mode: "index", intersect: false },
          plugins: { legend: { display: true, position: "bottom", labels: { boxWidth: 10, font: { size: 10 } } }, tooltip: { callbacks: { label: (c) => `${c.dataset.label}: ${c.raw == null ? "–" : (c.raw >= 0 ? "+" : "") + c.raw.toFixed(1)} SD` } } },
          scales: { x: { ticks: { color: ink2, maxTicksLimit: 8, font: { size: 10 } }, grid: { display: false } }, y: { title: { display: true, text: "SD from own average", color: ink2, font: { size: 10 } }, ticks: { color: ink2, font: { size: 10 } }, grid: { color: line } } } } });
      state.charts.push(ch);
    }

    for (const id of ids) {
      const v = state.varById[id], kind = chartKind(v);
      const S = sel.map((cid) => rawWindowSeries(v, cid));
      const { labels, keys, firstIdx } = S[0];
      const cur = keys.indexOf(windowKey(state.t));
      // 2018 reference: the same calendar month/season of the baseline year, repeated (dashed grey)
      const baseVals = keys.map((k, j) => { const i = firstIdx[j]; const idx = baselineWindowIdx(i, v.baseline_year || 2018); const vals = idx.map((q) => ((state.series[id] || {})[sel[0]] || [])[q]); return state.agg === "year" ? null : mean(vals); });
      const block = document.createElement("div"); block.className = "chart-block";
      const caution = v.caution ? `<div class="caution">⚠ ${v.caution}</div>` : "";
      block.innerHTML = `<h3>${v.label} <span class="muted">(${v.units || ""})</span></h3>
        <div class="var-plain">${plainOf(v)}${v.how_to_read ? ` <i>${v.how_to_read}</i>` : ""}</div>${caution}
        ${sel.map((cid, i) => `<div class="now">${sel.length > 1 ? `<i class="dot" style="background:${COUNTY_COLORS[i]}"></i>${countyProps(cid).name} — ` : ""}${windowLabel(state.t)}: <b>${nowText(v, cid)}</b></div>`).join("")}
        ${sel.map((cid, i) => (sel.length > 1 ? `<div class="cmp-name"><i class="dot" style="background:${COUNTY_COLORS[i]}"></i>${countyProps(cid).name}</div>` : "") + trendHtml(v, cid, false)).join("")}<canvas></canvas>`;
      box.appendChild(block);
      const datasets = S.map((ser, i) => ({ label: countyProps(sel[i]).name, data: ser.vals, borderColor: sel.length > 1 ? COUNTY_COLORS[i] : "#2a78d6", borderWidth: 2, pointRadius: 0, pointHitRadius: 8, tension: 0.15, spanGaps: false }));
      if (kind === "raw" && sel.length === 1 && v.temporal === "monthly" && baseVals.some((x) => x != null))
        datasets.push({ label: `${v.baseline_year} same ${state.agg === "month" ? "month" : "season"}`, data: baseVals, borderColor: "#898781", borderDash: [4, 3], borderWidth: 1.2, pointRadius: 0, tension: 0.15 });
      const refs = kind === "std" ? [-1, 0, 1] : [];
      const chart = new Chart(block.querySelector("canvas"), {
        type: kind === "flag" && state.agg !== "month" ? "bar" : "line",
        data: { labels, datasets },
        options: {
          animation: false, responsive: true, maintainAspectRatio: false, interaction: { mode: "index", intersect: false },
          plugins: { legend: { display: datasets.length > 1, position: "bottom", labels: { boxWidth: 10, font: { size: 10 } } },
            tooltip: { callbacks: { label: (c) => `${c.dataset.label}: ${c.raw == null ? "–" : fmt(c.raw)} ${v.units || ""}` } } },
          scales: { x: { ticks: { color: ink2, maxTicksLimit: 8, autoSkip: true, font: { size: 10 } }, grid: { display: false } },
                    y: { ticks: { color: ink2, maxTicksLimit: 5, font: { size: 10 } }, grid: { color: line } } },
          onClick: (_, els) => { if (els.length) setTime(firstIdx[els[0].index]); },
        },
        plugins: [{ id: "marks", afterDraw(c) {
          const { ctx, chartArea: a, scales } = c; ctx.save();
          for (const r of refs) { const y = scales.y.getPixelForValue(r); if (y >= a.top && y <= a.bottom) { ctx.strokeStyle = r === 0 ? ink2 : r < 0 ? "#b4461b" : "#256abf"; ctx.setLineDash([3, 3]); ctx.lineWidth = 1; ctx.beginPath(); ctx.moveTo(a.left, y); ctx.lineTo(a.right, y); ctx.stroke();
            ctx.fillStyle = ctx.strokeStyle; ctx.font = "10px sans-serif"; if (r) ctx.fillText(r < 0 ? "dry" : "wet", a.right - 22, y - 2); } }
          const x = scales.x.getPixelForValue(cur); ctx.setLineDash([]); ctx.strokeStyle = "#eb6834"; ctx.lineWidth = 2;
          ctx.beginPath(); ctx.moveTo(x, a.top); ctx.lineTo(x, a.bottom); ctx.stroke(); ctx.restore(); } }],
      });
      state.charts.push(chart);
    }
  }

  // ---------- export & shareable state ----------
  function buildCSV() {
    const ids = [...state.checked, ...(state.colorBy ? [state.colorBy] : [])].filter((x, i, a) => a.indexOf(x) === i && state.varById[x]);
    const cids = state.selectedList.length ? state.selectedList : Object.keys((state.series[ids[0]] || {}));
    const rows = [["county_id", "county", "state", "variable", "label", "units", "month", "value"]];
    for (const id of ids) { const v = state.varById[id], s = state.series[id] || {};
      for (const c of cids) { const p = countyProps(c), arr = s[c] || []; state.months.forEach((m, i) => { if (arr[i] != null) rows.push([c, p.name, p.admin1, id, v.label, v.units || "", m, arr[i]]); }); } }
    return rows.map((r) => r.map((x) => (/[",\n]/.test(String(x)) ? `"${String(x).replace(/"/g, '""')}"` : x)).join(",")).join("\n");
  }
  function downloadCSV() {
    const csv = buildCSV();
    try {
      const a = document.createElement("a"); a.href = URL.createObjectURL(new Blob([csv], { type: "text/csv" }));
      a.download = `south_sudan_${state.selectedList.join("_") || "all_counties"}_${new Date().toISOString().slice(0, 10)}.csv`;
      document.body.appendChild(a); a.click(); a.remove();
    } catch (e) { copyText(csv, "Download blocked here — the CSV was copied to your clipboard instead."); }
  }
  function copyText(txt, msg) {
    const done = () => toast(msg), fail = () => { const ta = document.createElement("textarea"); ta.value = txt; document.body.appendChild(ta); ta.select(); try { document.execCommand("copy"); done(); } catch (e) { toast("Copy not allowed here; select and copy from the box."); return; } ta.remove(); };
    if (navigator.clipboard && navigator.clipboard.writeText) navigator.clipboard.writeText(txt).then(done, fail); else fail();
  }
  function toast(msg) { let t = $("#toast"); if (!t) { t = document.createElement("div"); t.id = "toast"; document.body.appendChild(t); } t.textContent = msg; t.className = "show"; setTimeout(() => (t.className = ""), 2600); }
  function writeHash() {
    if (!state.months.length) return;
    const h = new URLSearchParams({ m: state.mode, a: state.agg, t: state.months[state.t], v: state.colorBy || "", c: [...state.checked].join(","),
      s: state.selectedList.join(","), f: state.flowMode || "best", r: [...state.rasterOn].join(","), p: Object.keys(state.pointLayers).join(","), n: [...state.natExtra].join(",") });
    try { history.replaceState(null, "", `#${h.toString()}`); } catch (e) { /* sandboxed */ }
  }
  function readHash() {
    try { const h = new URLSearchParams(location.hash.slice(1)); return h.has("m") ? h : null; } catch (e) { return null; }
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
      const lead = state.flowMode === "best"
        ? (src.kind === "stock" ? `Best available for ${windowLabel(state.t)}: no monthly movement data this month, so showing the latest survey of where displaced people came from (${SOURCE_SHORT[src.key] || src.key}${when}).`
                                : `Best available for ${windowLabel(state.t)}: ${SOURCE_SHORT[src.key] || src.key} (monthly movements).`)
        : `Showing: ${SOURCE_SHORT[src.key] || src.key}${when}.`;
      return `<span class="ok">${lead}</span> ${FLOW_EXPLAIN[src.key] || src.label}`;
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
      // survey stocks are not additive over months: in season/year views use only the last month of the window
      if (F.sources[pick].kind === "stock" && m !== ms.filter((x) => sourceForMonth(x) === pick).slice(-1)[0]) continue;
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
    el.querySelectorAll('input[name="flow-src"]').forEach((rb) => (rb.onchange = () => { state.flowMode = rb.value; drawFlows(); writeHash(); }));
    el.querySelectorAll(".flow-reason").forEach((cb) => (cb.onchange = () => { cb.checked ? state.flowReasons.add(cb.value) : state.flowReasons.delete(cb.value); drawFlows(); }));
  }


  // ---------- national timeline (bottom strip) ----------
  // Counties overlapping the Sudd wetland (used for regional GRACE series; GRACE resolution is ~300 km)
  const SUDD = ["Panyijiar", "Mayendit", "Leer", "Guit", "Fangak", "Ayod", "Canal/Pigi", "Duk", "Twic East", "Bor South",
    "Yirol East", "Awerial", "Rubkona", "Koch", "Nyirol", "Uror"];
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
    { label: "Surface water / flood extent, all seasons (MODIS)", ids: ["surface_water_km2"], how: "sum", units: "km²", color: "#1baf7a" },
    { label: "Flooded area, Sentinel-1 radar (reliable Jul–Nov; sees flooded vegetation)", ids: ["flood_s1_flood_km2"], how: "sum", units: "km²", color: "#1baf7a" },
    { label: "People in flooded areas (Sentinel-1 × WorldPop)", ids: ["flood_population_exposed"], how: "sum", units: "people", color: "#1baf7a" },
    { label: "Sudd inundation incl. flooded vegetation (MODIS water index, gap-filled)", ids: ["sudd_inundation_km2"], how: "subset", counties: SUDD, sum: true, units: "km²", color: "#01665e" },
    { label: "Water storage anomaly, Sudd counties (GRACE/GRACE-FO; vs 2002–2020)", ids: ["grace_tws_cm"], how: "subset", counties: SUDD, units: "cm water", color: "#01665e" },
    { label: "Groundwater storage anomaly, Sudd counties (G3P from GRACE; to Sep 2023)", ids: ["g3p_gwsa_cm"], how: "subset", counties: SUDD, units: "cm water", color: "#01665e" },
    { label: "Drought index (national mean; ensemble if available)", ids: ["drought_ensemble_mean", "spei3"], how: "mean", units: "index", color: "#eb6834" },
    { label: "Rainfall (national mean, CHIRPS v3 — primary)", ids: ["chirps_precip_mm", "precip_mm"], how: "mean", units: "mm / month", color: "#2a78d6" },
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
    if (spec.how === "subset") {
      rows = []; countyLayer.eachLayer((l) => { const p = l.feature.properties; if (spec.counties.includes(p.name) && s[p.district_id]) rows.push(p.district_id); });
    }
    if (spec.how === "state_sum") {  // state totals are repeated on each county: take one county per state
      const seen = new Set(); rows = [];
      countyLayer.eachLayer((l) => { const p = l.feature.properties; if (!seen.has(p.admin1) && s[p.district_id]) { seen.add(p.admin1); rows.push(p.district_id); } });
    }
    for (let i = 0; i < n; i++) {
      let tot = 0, k = 0;
      for (const c of rows) { const x = s[c][i]; if (x != null && isFinite(x)) { tot += x; k++; } }
      if (k) out[i] = (spec.how === "mean" || (spec.how === "subset" && !spec.sum) ? tot / k : tot) * (spec.scale || 1);
    }
    return out;
  }
  async function renderNational() {
    const box = $("#nat-charts"); if (!box) return;
    state.natCharts.forEach((c) => c.destroy()); state.natCharts = []; box.innerHTML = "";
    const ink2 = getComputedStyle(document.documentElement).getPropertyValue("--ink-2").trim();
    const line = getComputedStyle(document.documentElement).getPropertyValue("--line").trim();
    const specs = [...NATIONAL, ...[...state.natExtra].map((id) => ({ label: state.varById[id].label, ids: [id], how: "national", units: state.varById[id].units || "", color: "#6250d6" }))];
    for (const spec of specs) {
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
                    y: { ...(() => { const ok = data.filter((x) => x != null && isFinite(x)); const lo = Math.min(...ok), hi = Math.max(...ok);
                          // tiny negative corrections (e.g. -29k against 100M) should not stretch the axis
                          return { min: lo < 0 && Math.abs(lo) > 0.03 * Math.abs(hi) ? lo : Math.max(0, lo < 0 ? 0 : lo * 0.9), max: hi === lo ? hi + 1 : hi }; })(),
                         ticks: { color: ink2, font: { size: 9 }, maxTicksLimit: 3, callback: (x) => fmt(x, 2) }, grid: { color: line } } },
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
    $("#time-label").textContent = state.mode === "trend" ? `${windowLabel(i)} · trend 2018→${trendYear()}` : windowLabel(i);
    if (state.mode === "trend") { state.vars.forEach((v) => (v._trendSpan = null)); renderLegend(); }
    refreshCounties(); updateRasters(); refreshPoints(); drawFlows(); updateNational();
    if (state.selectedList.length) renderDetail();
    clearTimeout(state._hashT); state._hashT = setTimeout(writeHash, 400);
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
    fetchJSON("data/topic_picks.json").then((tp) => { state.topicPicks = tp; renderTopics(); }).catch(() => {});
    SPARKS.forEach((sp) => { const v = sparkVar(sp); if (v) ensureSeries(v.id).catch(() => {}); if (sp.band && state.varById[sp.band]) ensureSeries(sp.band).catch(() => {}); });
    fetchJSON("data/flows.json").then((f) => { state.flows = f; renderFlowControls(); drawFlows(); }).catch((e) => console.warn("no flows", e));
    $("#time").max = state.months.length - 1;

    countyLayer = L.geoJSON(counties, {
      style: styleCounty,
      onEachFeature: (f, l) => {
        l.bindTooltip(() => tooltipHtml(f.properties), { sticky: true, direction: "right", offset: [16, 0], className: "county-tt" });
        l.on("click", () => {
          const cid = f.properties.district_id;
          if (state.compareMode && state.selectedList.length && !state.selectedList.includes(cid)) { state.selectedList = [...state.selectedList, cid].slice(-3); state.compareMode = false; }
          else state.selectedList = [cid];
          state.selected = state.selectedList[0]; refreshCounties(); renderDetail(); writeHash();
        });
        l.on("mouseover", () => l.setStyle({ weight: 2.5, color: "#0b0b0b" }));
        l.on("mouseout", () => countyLayer.resetStyle(l));
      },
    }).addTo(map);
    map.fitBounds(countyLayer.getBounds(), { padding: [10, 10] });

    $("#mode").onchange = (e) => { state.mode = e.target.value; document.body.dataset.mode = state.mode; state.vars.forEach((v) => { if (usesDiff(v) && state.series[v.id]) computeDiffSpan(v); }); setTime(state.t); renderLegend(); writeHash(); };
    $("#agg").onchange = (e) => { state.agg = e.target.value; state.vars.forEach((v) => { if (usesDiff(v) && state.series[v.id]) computeDiffSpan(v); }); setTime(state.t); renderLegend(); };
    $("#time").oninput = (e) => setTime(+e.target.value);
    $("#play").onclick = togglePlay;
    $("#filter").oninput = renderVarList;
    $("#raster-opacity").oninput = updateRasters;
    $("#detail-close").onclick = () => { state.selected = null; state.selectedList = []; state.compareMode = false; refreshCounties(); renderDetail(); writeHash(); };

    renderRasterList(); renderPointList();
    // restore a shared view from the URL (#m=…&v=…&c=…&s=…&t=…), else defaults
    const H = readHash();
    let tStart = state.months.indexOf("2019-08") >= 0 ? state.months.indexOf("2019-08") : 0;
    if (H) {
      const list = (k) => (H.get(k) || "").split(",").filter(Boolean);
      if (H.get("m")) { state.mode = H.get("m"); $("#mode").value = state.mode; }
      if (H.get("a")) { state.agg = H.get("a"); $("#agg").value = state.agg; }
      list("c").filter((x) => state.varById[x]).forEach((x) => state.checked.add(x));
      list("n").filter((x) => state.varById[x]).forEach((x) => state.natExtra.add(x));
      state.selectedList = list("s").filter((x) => countyLayer.getLayers().some((l) => l.feature.properties.district_id === x)).slice(0, 3);
      state.selected = state.selectedList[0] || null;
      if (H.get("f")) state.flowMode = H.get("f");
      const ti = state.months.indexOf(H.get("t")); if (ti >= 0) tStart = ti;
      list("r").forEach((k) => { const cb = document.getElementById(`r-${k}`); if (cb) { cb.checked = true; state.rasterOn.add(k); } });
      for (const k of list("p")) { const p = state.points.find((x) => x.key === k); const cb = document.getElementById(`p-${k}`); if (p && cb) { cb.checked = true; loadPoints(p); } }
    }
    const first = (H && state.varById[H.get("v")]) || state.vars.find((v) => v.id === "chirps_precip_mm") || state.vars.find((v) => v.id === "precip_mm") || state.vars.find((v) => !v.national_only);
    if (first) await setColorBy(first.id); else renderVarList();
    renderNational().then(() => map.invalidateSize()).catch((e) => console.warn("national", e));
    setTime(tStart);
  }
  boot().catch((e) => { console.error(e); $("#var-list").innerHTML = `<p class="empty">Could not load data: ${e.message}</p>`; });
})();
