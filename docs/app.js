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
    mode: "index_month", agg: "month", t: 0, selected: null,
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
  function valueAt(v, c, i) {
    const s = state.series[v.id]; if (!s || !s[c]) return null;
    const arr = s[c];
    const raw = mean(windowIdx(i).map((j) => arr[j]));
    if (raw == null) return null;
    if (state.mode === "raw" || v.temporal === "static") return raw;
    const by = v.baseline_year || 2018;
    let base;
    if (state.mode === "index_month" && v.baseline_mode !== "annual") base = mean(baselineWindowIdx(i, by).map((j) => arr[j]));
    else base = mean(state.months.map((_, j) => j).filter((j) => yearOf(j) === by).map((j) => arr[j]));
    if (base == null) return null;
    if (v.index_ok === false) return raw - base;
    if (Math.abs(base) < 1e-9) return null;
    return raw / base;
  }
  const usesDiff = (v) => v.index_ok === false;

  // ---------- colour scales ----------
  function scaleFor(v) {
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

  function tooltipHtml(p) {
    const v = state.varById[state.colorBy];
    let line = "";
    if (v) {
      const x = valueAt(v, p.district_id, state.t);
      line = `<br>${v.label}: <b>${describeValue(v, x)}</b>${trendHtml(v, p.district_id, true)}`;
    }
    return `<b>${p.name}</b> · ${p.admin1}${line}`;
  }
  function describeValue(v, x) {
    if (x == null) return "no data";
    if (state.mode === "raw" || v.temporal === "static") return `${fmt(x)} ${v.units || ""}`;
    if (usesDiff(v)) return `${x >= 0 ? "+" : ""}${fmt(x)} ${v.units || ""} vs ${v.baseline_year}`;
    return `${fmt(x)}× ${v.baseline_year} level`;
  }

  function refreshCounties() {
    if (!countyLayer) return;
    countyLayer.setStyle(styleCounty);
    countyLayer.eachLayer((l) => {
      l.setTooltipContent(tooltipHtml(l.feature.properties));
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
      const lo = sc.kind === "ratio" ? "≤0.5×" : `−${fmt(sc.span)}`;
      const hi = sc.kind === "ratio" ? "≥2×" : `+${fmt(sc.span)}`;
      const mid = sc.kind === "ratio" ? `1.0 = ${v.baseline_year}` : `0 = ${v.baseline_year}`;
      html += `<div class="bar" style="background:linear-gradient(90deg,${g})"></div>
        <div class="ticks"><span>${lo}</span><span>${mid}</span><span>${hi}</span></div>`;
      const dir = v.higher_is === "neutral" ? "Purple = higher, orange = lower than baseline"
        : `Blue = better, red = worse than baseline (higher is ${v.higher_is})`;
      html += `<div class="note">${dir}${sc.kind === "diff" ? ` · change in ${v.units || "units"} (ratio not meaningful)` : ""}</div>`;
      if (v.sparse_count) html += `<div class="note">Sparse count: shown as change from the ${v.baseline_year} monthly average (most ${v.baseline_year} months were zero, so a ratio is undefined).</div>`;
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
    el.innerHTML = html;
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
    const timed = gj.features.some((f) => f.properties && (f.properties.date || f.properties.year));
    const entry = { p, gj, timed, layer: null };
    state.pointLayers[p.key] = entry;
    drawPoints(entry);
  }
  function featureInWindow(f) {
    const pr = f.properties || {};
    const idx = windowIdx(state.t);
    const lo = state.months[idx[0]], hi = state.months[idx[idx.length - 1]];
    if (pr.date) { const ym = String(pr.date).slice(0, 7); return ym >= lo && ym <= hi; }
    if (pr.year) { const y = String(pr.year); return y >= lo.slice(0, 4) && y <= hi.slice(0, 4) || (y <= hi.slice(0, 4) && !pr.end_year) || (pr.end_year && y <= hi.slice(0, 4) && String(pr.end_year) >= lo.slice(0, 4)); }
    return true;
  }
  function drawPoints(entry) {
    if (entry.layer) map.removeLayer(entry.layer);
    const { p, gj, timed } = entry;
    const isEvent = timed && gj.features.some((f) => f.properties && f.properties.date);
    entry.layer = L.geoJSON(gj, {
      pane: "points",
      filter: (f) => !isEvent || featureInWindow(f),
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
      state.months.forEach((_, i) => { const k = windowKey(i); if (!keys.includes(k)) { keys.push(k); firstIdx.push(i); labels.push(windowLabel(i)); vals.push(valueAt(v, state.selected, i)); } });
      const cur = keys.indexOf(windowKey(state.t));
      const block = document.createElement("div");
      block.className = "chart-block";
      block.innerHTML = `<h3>${v.label}${v.units && state.mode === "raw" ? ` (${v.units})` : ""}</h3>
        <div class="now">${windowLabel(state.t)}: <b>${describeValue(v, vals[cur])}</b></div>${trendHtml(v, state.selected, false)}<canvas></canvas>`;
      box.appendChild(block);
      const ref = state.mode === "raw" || v.temporal === "static" ? null : usesDiff(v) ? 0 : 1;
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
          plugins: { legend: { display: false }, tooltip: { callbacks: { label: (c) => describeValue(v, vals[c.dataIndex]) } } },
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
  const SOURCE_SHORT = { et: "Event Tracking", fmr: "Flow Monitoring" };
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
  function flowStatus() {
    const F = state.flows; if (!F) return "";
    const ms = flowWindowMonths();
    return F.sources.filter((src) => !state.flowSources || state.flowSources.has(src.key)).map((src) => {
      const have = ms.filter((m) => src.months.includes(m)).length;
      const name = SOURCE_SHORT[src.key] || src.key;
      if (have === ms.length) return `<span class="ok">✓ ${name}</span>`;
      if (have > 0) return `<span class="part">◐ ${name}: ${have}/${ms.length} months</span>`;
      const note = src.key === "fmr" ? (ms[0] >= "2023-11" && ms[0] <= "2024-12" ? " (IOM published no county data Nov 2023–Dec 2024)" : ms[0] < "2020-01" ? " (series starts Jan 2020)" : "") :
                   src.key === "et" && ms[0] < "2020-01" ? " (series starts 2020)" : "";
      return `<span class="none">✕ ${name}: no county flow data${note}</span>`;
    }).join(" · ");
  }
  function drawFlows() {
    if (state.flowLayer) { map.removeLayer(state.flowLayer); state.flowLayer = null; }
    const F = state.flows;
    const st = $("#flow-status"); if (st) st.innerHTML = F ? flowStatus() : "";
    if (!F || !state.flowOn) return;
    const ms = flowWindowMonths();
    const agg = new Map();
    for (const m of ms) for (const [si, a, b, r, n] of F.months[m] || []) {
      const src = F.sources[si];
      if (state.flowSources && !state.flowSources.has(src.key)) continue;
      if (state.flowReasons && !state.flowReasons.has(F.reasons[r])) continue;
      const k = `${si}|${a}|${b}|${r}`; agg.set(k, (agg.get(k) || 0) + n);
    }
    const list = [...agg.entries()].map(([k, n]) => { const [si, a, b, r] = k.split("|").map(Number); return { si, a, b, r, n }; })
      .sort((x, y) => y.n - x.n).slice(0, 250);
    state.flowLayer = L.layerGroup().addTo(map);
    ensureArrowDefs();
    for (const f of list) {
      const src = F.sources[f.si], A = F.nodes[f.a], B = F.nodes[f.b], reason = F.reasons[f.r];
      const [color, rlabel] = REASON_STYLE[reason] || REASON_STYLE.other;
      const w = Math.max(1.3, Math.min(14, 11 * Math.sqrt(f.n / (src.max || 1))));
      const line = L.polyline(bezier(A, B, 0.12 + 0.03 * f.r), {
        renderer: flowRenderer, pane: "flows", color, weight: w, opacity: 0.82, lineCap: "round",
        dashArray: src.key === "fmr" ? "6 5" : null,
      }).bindTooltip(`<b>${A[2]} → ${B[2]}</b><br>${rlabel} · <b>${f.n.toLocaleString()}</b> people<br><span style="color:var(--muted)">${src.label} · ${windowLabel(state.t)}</span>`, { sticky: true });
      line.addTo(state.flowLayer);
      if (line._path) line._path.setAttribute("marker-end", `url(#ah-${f.r})`);
    }
  }
  function renderFlowControls() {
    const F = state.flows, el = $("#flow-controls"); if (!F || !el) return;
    state.flowSources = new Set(F.sources.map((x) => x.key));
    const used = new Set(); Object.values(F.months).forEach((rows) => rows.forEach((r) => used.add(F.reasons[r[3]])));
    state.flowReasons = new Set(used);
    let h = `<div class="var-row"><input type="checkbox" id="flow-on" checked><label for="flow-on"><b>Show migration arrows</b> <span class="meta">(width ∝ √people)</span></label></div>`;
    h += `<div class="group-title">Source</div>`;
    F.sources.forEach((x) => { h += `<div class="var-row"><input type="checkbox" class="flow-src" value="${x.key}" id="fs-${x.key}" checked>
      <svg width="22" height="8" aria-hidden="true"><line x1="1" y1="4" x2="21" y2="4" stroke="var(--ink-2)" stroke-width="3" ${x.key === "fmr" ? 'stroke-dasharray="5 4"' : ""}/></svg>
      <label for="fs-${x.key}">${SOURCE_SHORT[x.key] || x.key} <span class="meta">· ${x.months.length} months · ${x.label}</span></label></div>`; });
    h += `<div class="group-title">Reason</div>`;
    F.reasons.filter((r) => used.has(r)).forEach((r) => { const [c, lab] = REASON_STYLE[r] || REASON_STYLE.other;
      h += `<div class="var-row"><input type="checkbox" class="flow-reason" value="${r}" id="fr-${r}" checked><span class="swatch" style="background:${c}"></span><label for="fr-${r}">${lab}</label></div>`; });
    h += `<p class="hint" id="flow-status"></p>`;
    el.innerHTML = h;
    $("#flow-on").onchange = (e) => { state.flowOn = e.target.checked; drawFlows(); };
    el.querySelectorAll(".flow-src").forEach((cb) => (cb.onchange = () => { cb.checked ? state.flowSources.add(cb.value) : state.flowSources.delete(cb.value); drawFlows(); }));
    el.querySelectorAll(".flow-reason").forEach((cb) => (cb.onchange = () => { cb.checked ? state.flowReasons.add(cb.value) : state.flowReasons.delete(cb.value); drawFlows(); }));
  }

  // ---------- time ----------
  function setTime(i) {
    state.t = i;
    $("#time").value = i;
    $("#time-label").textContent = windowLabel(i);
    refreshCounties(); updateRasters(); refreshPoints(); drawFlows();
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
    fetchJSON("data/trends.json").then((t) => { state.trends = t; refreshCounties(); renderLegend(); }).catch(() => {});
    fetchJSON("data/flows.json").then((f) => { state.flows = f; renderFlowControls(); drawFlows(); }).catch((e) => console.warn("no flows", e));
    $("#time").max = state.months.length - 1;

    countyLayer = L.geoJSON(counties, {
      style: styleCounty,
      onEachFeature: (f, l) => {
        l.bindTooltip(tooltipHtml(f.properties), { sticky: true });
        l.on("click", () => { state.selected = f.properties.district_id; refreshCounties(); renderDetail(); });
        l.on("mouseover", () => l.setStyle({ weight: 2.5, color: "#0b0b0b" }));
        l.on("mouseout", () => countyLayer.resetStyle(l));
      },
    }).addTo(map);
    map.fitBounds(countyLayer.getBounds(), { padding: [10, 10] });

    $("#mode").onchange = (e) => { state.mode = e.target.value; state.vars.forEach((v) => { if (usesDiff(v) && state.series[v.id]) computeDiffSpan(v); }); refreshCounties(); renderLegend(); renderDetail(); };
    $("#agg").onchange = (e) => { state.agg = e.target.value; state.vars.forEach((v) => { if (usesDiff(v) && state.series[v.id]) computeDiffSpan(v); }); setTime(state.t); renderLegend(); };
    $("#time").oninput = (e) => setTime(+e.target.value);
    $("#play").onclick = togglePlay;
    $("#filter").oninput = renderVarList;
    $("#raster-opacity").oninput = updateRasters;
    $("#detail-close").onclick = () => { state.selected = null; refreshCounties(); renderDetail(); };

    renderRasterList(); renderPointList();
    const first = state.vars.find((v) => v.id === "precip_mm") || state.vars[0];
    if (first) await setColorBy(first.id); else renderVarList();
    setTime(state.months.indexOf("2019-08") >= 0 ? state.months.indexOf("2019-08") : 0);
  }
  boot().catch((e) => { console.error(e); $("#var-list").innerHTML = `<p class="empty">Could not load data: ${e.message}</p>`; });
})();
