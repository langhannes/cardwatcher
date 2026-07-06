/* Dashboard controller — client-side port of app/dashboard.py:build_dashboard.
 *
 * Ranks cards from the precomputed changes/price_history.json into three signal
 * panels (biggest movers, net supply loss, pressure/divergence), using the
 * blended market price and the same thresholds as the Flask dashboard.
 */
(function () {
  "use strict";
  const { escapeHtml, fetchJSON } = window.CW;

  // Tunable thresholds (identical to dashboard.py).
  const MIN_AVAILABLE = 10, MIN_BASE = 10, TOP_N = 8;
  const SUPPLY_DROP = 15, PRICE_FLAT = 5, PRICE_UP = 8, SUPPLY_GROW = 10;

  const r1 = (v) => Math.round(v * 10) / 10;

  function cardMeta(canonical) {
    return {
      file: canonical + ".json",
      name: canonical.split("_").pop().replace(/-/g, " "),
      image: window.CW.imagePath(canonical),
    };
  }

  function tint(color, alpha) {
    alpha = alpha || "0.12";
    color = color.trim();
    if (color.startsWith("rgb(") && color.endsWith(")")) {
      return "rgba(" + color.slice(4, -1) + "," + alpha + ")";
    }
    return "rgba(0,0,0,0.05)";
  }

  function fmtEur(v) {
    if (!v) return "--€";
    return (v >= 1000 ? String(Math.trunc(v)) : String(Math.round(v * 100) / 100)) + "€";
  }

  function rows(entries) {
    if (!entries.length) return '<div class="dash-empty">No cards meet the criteria yet.</div>';
    return entries.map((e) => {
      const meta = cardMeta(e.canonical);
      const color = e.color || "#444";
      return (
        '<a href="' + window.CW.cfg().cardHref(meta.file, false) + '" class="dash-card" style="--accent:' + color + ";--tint:" + tint(color) + ';">' +
          '<img src="' + meta.image + '" alt="" class="lazy dash-thumb">' +
          '<div class="dash-info">' +
            '<div class="dash-primary">' + e.primary + "</div>" +
            '<div class="dash-name">' + escapeHtml(meta.name) + "</div>" +
            '<div class="dash-secondary">' + e.secondary + "</div>" +
          "</div>" +
        "</a>"
      );
    }).join("");
  }

  function build(priceHistory, activePages) {
    const movers = [], supply = [], pressureRows = [];

    for (const canonical in priceHistory) {
      if (activePages.indexOf(canonical) === -1) continue;
      const entry = priceHistory[canonical];
      const market = entry.market || {};
      const blendNow = market.blend || 0;
      const available = entry.current_available || 0;
      const wk = entry["1w"] || {};
      const blend1w = (wk.market || {}).blend || 0;

      let pricePct = null;
      if (blendNow > 0 && blend1w > 0 && available >= MIN_AVAILABLE) {
        pricePct = (blendNow - blend1w) / blend1w * 100;
        movers.push({ pct: pricePct, canonical, now: blendNow, prev: blend1w });
      }

      const added = wk.listings_added || 0;
      const removed = wk.listings_removed || 0;
      const base = wk.historical_available || 0;
      let netPct = null;
      if (base >= MIN_BASE) {
        netPct = (added - removed) / base * 100;
        if (netPct < 0) supply.push({ netPct, canonical, added, removed, base, blendNow });
      }

      if (pricePct != null && netPct != null) {
        pressureRows.push({ canonical, price_pct: pricePct, net_pct: netPct, blend_now: blendNow });
      }
    }

    // Movers: top risers and fallers side by side.
    movers.sort((a, b) => b.pct - a.pct);
    const risers = movers.slice(0, TOP_N);
    let fallers = movers.length > TOP_N ? movers.slice(-TOP_N).sort((a, b) => a.pct - b.pct) : [];
    const riserNames = new Set(risers.map((m) => m.canonical));
    fallers = fallers.filter((f) => !riserNames.has(f.canonical)).slice(0, TOP_N);

    const moverRow = (m) => {
      const sign = m.pct >= 0 ? "+" : "";
      const color = m.pct > 0 ? "rgb(34,139,34)" : (m.pct < 0 ? "rgb(220,53,69)" : "#666");
      const arrow = m.pct > 0 ? " ↑" : (m.pct < 0 ? " ↓" : "");
      return { canonical: m.canonical, color, primary: sign + r1(m.pct) + "%" + arrow, secondary: fmtEur(m.prev) + " → " + fmtEur(m.now) };
    };

    const moversHtml =
      '<div class="dash-col"><h3 class="dash-subhead">▲ Gainers</h3>' + rows(risers.map(moverRow)) + "</div>" +
      '<div class="dash-col"><h3 class="dash-subhead">▼ Fallers</h3>' + rows(fallers.map(moverRow)) + "</div>";

    // Net supply loss.
    supply.sort((a, b) => a.netPct - b.netPct);
    const supplyRow = (s) => ({
      canonical: s.canonical, color: "rgb(220,53,69)",
      primary: r1(s.netPct) + "% supply",
      secondary: s.base + "→" + (s.base + s.added - s.removed) + " avail · " + fmtEur(s.blendNow),
    });
    const supplyHtml = rows(supply.slice(0, TOP_N).map(supplyRow));

    // Pressure / divergence buckets.
    const coiling = [], overbought = [], cooling = [];
    for (const r of pressureRows) {
      const pp = r.price_pct, np = r.net_pct;
      if (np <= -SUPPLY_DROP && Math.abs(pp) < PRICE_FLAT) coiling.push(r);
      else if (pp >= PRICE_UP && np >= SUPPLY_GROW) cooling.push(r);
      else if (pp >= PRICE_UP && np > -PRICE_FLAT) overbought.push(r);
    }
    coiling.sort((a, b) => a.net_pct - b.net_pct);
    overbought.sort((a, b) => b.price_pct - a.price_pct);
    cooling.sort((a, b) => b.price_pct - a.price_pct);

    const pressureRow = (r, color) => ({
      canonical: r.canonical, color,
      primary: "price " + (r.price_pct >= 0 ? "+" : "") + r1(r.price_pct) + "%",
      secondary: "supply " + r1(r.net_pct) + "% · " + fmtEur(r.blend_now),
    });

    const pressureHtml =
      '<div class="dash-col"><h3 class="dash-subhead" title="Supply drained but price has not moved — possible upward pressure">Coiling</h3>' +
        rows(coiling.slice(0, TOP_N).map((r) => pressureRow(r, "rgb(34,139,34)"))) + "</div>" +
      '<div class="dash-col"><h3 class="dash-subhead" title="Price rising without supply shrinking">Overbought</h3>' +
        rows(overbought.slice(0, TOP_N).map((r) => pressureRow(r, "rgb(255,140,0)"))) + "</div>" +
      '<div class="dash-col"><h3 class="dash-subhead" title="Price up but sellers are piling in">Cooling</h3>' +
        rows(cooling.slice(0, TOP_N).map((r) => pressureRow(r, "rgb(220,53,69)"))) + "</div>";

    return { moversHtml, supplyHtml, pressureHtml };
  }

  async function main() {
    let priceHistory, manifest;
    try {
      const c = CW.cfg();
      [priceHistory, manifest] = await Promise.all([
        fetchJSON(c.priceHistoryUrl),
        fetchJSON(c.manifestUrl),
      ]);
    } catch (e) {
      document.getElementById("moversPanel").innerHTML = '<div class="dash-empty">Failed to load data.</div>';
      console.error(e);
      return;
    }
    const activePages = (manifest.cards || []).map((c) => c.canonical);
    const out = build(priceHistory, activePages);
    document.getElementById("moversPanel").innerHTML = out.moversHtml;
    document.getElementById("supplyPanel").innerHTML = out.supplyHtml;
    document.getElementById("pressurePanel").innerHTML = out.pressureHtml;
  }

  document.addEventListener("DOMContentLoaded", main);
})();
