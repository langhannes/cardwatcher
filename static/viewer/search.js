/* Search grid controller — client-side port of app/watchersearch.py:build_search.
 *
 * Config-driven via window.CW_CFG (see cw-common.js CFG_DEFAULTS): the same file
 * powers both the standalone GitHub Pages viewer (defaults, no collection) and
 * CardWatcher (collection features on, app-relative URLs). Filters / sorts /
 * formats the gallery in the browser so the server no longer re-renders it on
 * every sort/period/type change.
 *
 * Collection features (heart badges, collection view, collection-price sort) are
 * active only when CW_CFG.collection is true; they read the existing
 * /api/collection endpoint. The collection total/history bar is left to the host
 * shell's own inline script.
 */
(function () {
  "use strict";
  const { escapeHtml, fetchJSON, imagePath, cfg } = window.CW;

  let MANIFEST = null;
  let PRICE_HISTORY = {};
  let COLLECTION_NAMES = new Set();     // canonical names in collection (badges/filter)
  let COLLECTION_BY_CARD = {};          // canonical -> {qty, total, unit}

  function params() {
    const p = new URLSearchParams(window.location.search);
    const sortBy = p.get("sortBy") || "name";
    const order = p.get("order") || (sortBy === "name" ? "asc" : "desc");
    return {
      q: p.get("q") || p.get("searchString") || "",
      sortBy,
      order,
      pricePeriod: p.get("pricePeriod") || "last",
      priceType: p.get("priceType") || "available",
      collectionView: p.get("collection") === "true" && cfg().collection,
    };
  }

  function fmtDate(ts) {
    const d = new Date(parseFloat(ts) * 1000);
    const pad = (x) => ("0" + x).slice(-2);
    return pad(d.getDate()) + "." + pad(d.getMonth() + 1) + "." + d.getFullYear();
  }

  const r2 = (v) => Math.round(v * 100) / 100;
  const r1 = (v) => Math.round(v * 10) / 10;

  function compact(v) {
    if (Math.abs(v) >= 100) return String(Math.round(v));
    const r = r2(v);
    return r === Math.trunc(r) ? String(Math.trunc(r)) : String(r);
  }

  function cardData(card, cfgv) {
    const canonical = card.canonical;
    const fileName = canonical + ".json";
    const ph = PRICE_HISTORY[canonical];
    const available = ph ? (ph.current_available || 0) : 0;

    let priceAvg = 0, priceChg = 0, percentChg = 0, priceMin = 0;
    let endedAvg = 0, endedChg = 0, endedPercentChg = 0;

    if (ph) priceMin = ph.current_min || 0;

    if (cfgv.pricePeriod === "last") {
      if (ph) {
        const last = ph.last_download || {};
        priceAvg = last.avg || 0;
        priceChg = last.avg_change || 0;
        if (priceAvg > 0) percentChg = (priceChg / priceAvg) * 100;
        endedAvg = last.ended_avg || 0;
        endedChg = last.ended_avg_change || 0;
        if (endedAvg > 0) endedPercentChg = (endedChg / endedAvg) * 100;
      }
    } else if (ph) {
      priceAvg = ph.current_avg || 0;
      const pd = ph[cfgv.pricePeriod] || {};
      if (pd && pd.change != null) priceChg = pd.change;
      if (priceAvg > 0) percentChg = (priceChg / priceAvg) * 100;
      endedAvg = ph.current_ended_avg || 0;
      if (pd && pd.ended_change != null) endedChg = pd.ended_change;
      if (endedAvg > 0) endedPercentChg = (endedChg / endedAvg) * 100;
    }

    let ins = 0, sld = 0;
    if (ph) {
      if (cfgv.pricePeriod === "last") {
        const ld = ph.last_download || {};
        ins = ld.inserted || 0; sld = ld.sold || 0;
      } else {
        const pd = ph[cfgv.pricePeriod] || {};
        ins = pd.listings_added || 0; sld = pd.listings_removed || 0;
      }
    }
    const base = available - ins + sld;
    const drainage = base > 0 ? r1(sld / base * 100) : null;
    const inflation = base > 0 ? r1(ins / base * 100) : null;
    const netSupply = base > 0 ? r1((ins - sld) / base * 100) : null;

    let marketFloor = 0, fromChange = null, floorChange = null;
    if (ph) {
      marketFloor = (ph.market || {}).floor || 0;
      const curMin = ph.current_min || 0;
      if (cfgv.pricePeriod === "last") {
        const ld = ph.last_download || {};
        fromChange = ld.min_change != null ? ld.min_change : null;
        floorChange = ld.floor_change != null ? ld.floor_change : null;
      } else {
        const pd = ph[cfgv.pricePeriod] || {};
        if (pd.historical_min) fromChange = r2(curMin - pd.historical_min);
        const hf = (pd.market || {}).floor;
        if (hf) floorChange = r2(marketFloor - hf);
      }
    }

    const coll = COLLECTION_BY_CARD[canonical] || { qty: 0, total: 0, unit: 0 };

    return {
      fileName, canonical, updated: card.updated,
      priceAvg, priceChg, percentChg, priceMin,
      endedAvg, endedChg, endedPercentChg,
      available, ins, sld,
      drainage, inflation, netSupply,
      marketFloor, fromChange, floorChange,
      inCollection: COLLECTION_NAMES.has(canonical),
      collTotal: coll.total, collQty: coll.qty, collUnit: coll.unit,
    };
  }

  function sortList(list, cfgv) {
    const desc = cfgv.order === "desc";
    const dir = desc ? -1 : 1;
    const by = (fn) => list.sort((a, b) => (fn(a) < fn(b) ? -1 : fn(a) > fn(b) ? 1 : 0) * dir);
    const num = (fn) => list.sort((a, b) => (fn(a) - fn(b)) * dir);
    switch (cfgv.sortBy) {
      case "price": return num((x) => cfgv.priceType === "sold" ? x.endedAvg : x.priceAvg);
      case "priceChange": return num((x) => cfgv.priceType === "sold" ? x.endedChg : x.priceChg);
      case "percentChange": return num((x) => cfgv.priceType === "sold" ? x.endedPercentChg : x.percentChg);
      case "lowestPrice": return num((x) => x.priceMin);
      case "drainage": return num((x) => x.drainage != null ? x.drainage : -1);
      case "inflation": return num((x) => x.inflation != null ? x.inflation : -1);
      case "netSupply": return num((x) => x.netSupply != null ? x.netSupply : 0);
      case "collectionPrice": return num((x) => x.collTotal);
      default: return by((x) => x.fileName);
    }
  }

  function availabilityBadges(d) {
    const parts = [];
    if (d.ins > 0) parts.push('<span style="color: rgb(34,139,34); font-weight: bold;">+' + d.ins + "</span>");
    if (d.sld > 0) parts.push('<span style="color: rgb(220, 20, 60); font-weight: bold;">-' + d.sld + "</span>");
    let nsBadge = "";
    if (d.netSupply != null) {
      const c = d.netSupply > 0 ? "rgb(34,139,34)" : (d.netSupply < 0 ? "rgb(220,53,69)" : "#888");
      const s = d.netSupply > 0 ? "+" : "";
      nsBadge = '<div style="text-align:right;color:' + c + ';font-weight:bold;font-size:0.9em;">' + s + d.netSupply + "%</div>";
    }
    if (d.available > 0 || parts.length || nsBadge) {
      const countPart = d.available > 0 ? '<span style="font-weight: bold;">' + d.available + "</span>" : "";
      const sep = countPart && parts.length ? " " : "";
      const changesRow = countPart + sep + parts.join(" ");
      const inner = (changesRow ? '<div style="display:flex;gap:6px;">' + changesRow + "</div>" : "") + nsBadge;
      return '<div style="position: absolute; top: 4px; right: 4px; background: var(--cw-pill-strong); padding: 2px 6px; border-radius: 4px; font-size: 0.8em;">' + inner + "</div>";
    }
    return "";
  }

  function pricePill(d, cfgv) {
    let avg = d.priceAvg, chg = d.priceChg;
    let str = "--€ (0€)";
    let style = "font-size: 0.85em; font-weight: bold; background: var(--cw-pill); padding: 2px 4px; border-radius: 4px; display: inline-block;";
    let arrow = "";
    if (avg > 0) {
      const sign = chg >= 0 ? "+" : "";
      const pct = (chg / avg) * 100;
      arrow = chg > 0 ? " ↑" : (chg < 0 ? " ↓" : " →");
      avg = avg < 1000 ? r2(avg) : Math.trunc(avg);
      if (cfgv.sortBy === "percentChange") str = "Avail: " + avg + "€ (" + sign + r1(pct) + "%)" + arrow;
      else { chg = (d.priceAvg < 1000 || chg < 1) ? r2(chg) : Math.trunc(chg); str = "Avail: " + avg + "€ (" + sign + chg + "€)" + arrow; }
      if (d.priceChg > 0) style = "font-size: 0.85em; color: rgb(34,139,34); font-weight: bold; background: var(--cw-pill); padding: 2px 4px; border-radius: 4px; display: inline-block;";
      else if (d.priceChg < 0) style = "font-size: 0.85em; color: rgb(220, 20, 60); font-weight: bold; background: var(--cw-pill); padding: 2px 4px; border-radius: 4px; display: inline-block;";
    }
    return '<div style="' + style + '">' + str + "</div>";
  }

  function endedPill(d, cfgv) {
    let avg = d.endedAvg, chg = d.endedChg;
    if (!(avg > 0)) {
      return '<div style="font-size: 0.85em; font-weight: bold; background: var(--cw-pill-gray); padding: 2px 4px; border-radius: 4px; display: inline-block;">Sold: --</div>';
    }
    const sign = chg >= 0 ? "+" : "";
    const pct = (chg / avg) * 100;
    const arrow = chg > 0 ? " ↑" : (chg < 0 ? " ↓" : " →");
    avg = avg < 1000 ? r2(avg) : Math.trunc(avg);
    let str;
    if (cfgv.sortBy === "percentChange") str = "Sold: " + avg + "€ (" + sign + r1(pct) + "%)" + arrow;
    else { chg = avg < 1000 ? r2(chg) : Math.trunc(chg); str = "Sold: " + avg + "€ (" + sign + chg + "€)" + arrow; }
    let style = "font-size: 0.85em; font-weight: bold; background: var(--cw-pill-gray); padding: 2px 4px; border-radius: 4px; display: inline-block;";
    if (d.endedChg > 0) style = "font-size: 0.85em; color: rgb(34,139,34); font-weight: bold; background: var(--cw-pill-gray); padding: 2px 4px; border-radius: 4px; display: inline-block;";
    else if (d.endedChg < 0) style = "font-size: 0.85em; color: rgb(220, 20, 60); font-weight: bold; background: var(--cw-pill-gray); padding: 2px 4px; border-radius: 4px; display: inline-block;";
    return '<div style="' + style + '">' + str + "</div>";
  }

  function priceRow(label, value, change) {
    if (value <= 0) return "";
    const base = "font-size: 0.78em; font-weight: bold; background: var(--cw-pill-blue); padding: 2px 4px; border-radius: 4px; display: inline-block; white-space: nowrap;";
    if (change == null) return '<div style="' + base + '">' + label + ": " + compact(value) + "€</div>";
    const sign = change >= 0 ? "+" : "";
    const arrow = change > 0 ? " ↑" : (change < 0 ? " ↓" : " →");
    const color = change > 0 ? "rgb(34,139,34)" : (change < 0 ? "rgb(220,20,60)" : "#555");
    const style = change === 0 ? base : "font-size: 0.78em; font-weight: bold; color: " + color + "; background: var(--cw-pill-blue); padding: 2px 4px; border-radius: 4px; display: inline-block; white-space: nowrap;";
    return '<div style="' + style + '">' + label + ": " + compact(value) + "€ (" + sign + compact(change) + "€)" + arrow + "</div>";
  }

  function cardShell(d, badges, bodyExtra, hrefExtra) {
    const articleName = d.canonical.split("_").pop().replace(/-/g, " ");
    const href = cfg().cardHref(d.fileName, false) + (hrefExtra || "");
    return (
      '<div class="d-flex mb-4 col-12 col-sm-6 col-md-4 col-lg-2">' +
        '<a name="' + d.fileName + '" href="' + href + '" class="card text-center w-100 galleryBox" style="position: relative;">' +
          badges +
          '<img src="' + imagePath(d.canonical) + '" alt="' + escapeHtml(articleName) + '" class="lazy card-img-top img-fluid">' +
          '<div class="card-body d-flex flex-column p-2" style="gap: 2px;">' +
            '<div class="card-title" style="font-size: 0.9em; font-weight: bold; margin-bottom: 2px;">' + escapeHtml(articleName) + "</div>" +
            '<div style="font-size: 0.75em; color: #666;">(' + fmtDate(d.updated) + ")</div>" +
            bodyExtra +
          "</div>" +
        "</a>" +
      "</div>"
    );
  }

  function cardHtml(d, cfgv) {
    // Collection view: show collection holdings instead of market pills.
    if (cfgv.collectionView) {
      let collHtml = "";
      if (d.collTotal > 0) {
        collHtml = '<div style="font-size: 0.85em; font-weight: bold; color: #28a745; background: rgba(40,167,69,0.15); padding: 4px 8px; border-radius: 4px; display: inline-block;">' +
          d.collQty + "x @ " + r2(d.collUnit) + "€ = " + r2(d.collTotal) + "€</div>";
      }
      return cardShell(d, availabilityBadges(d), collHtml, "&collection=true");
    }
    const metrics = (["drainage", "inflation", "netSupply"].indexOf(cfgv.sortBy) !== -1 && d.drainage != null)
      ? '<div style="font-size:0.78em;color:rgb(220,53,69);">Drainage: ' + d.drainage + "%</div>" +
        '<div style="font-size:0.78em;color:rgb(34,139,34);">Inflation: ' + d.inflation + "%</div>"
      : "";
    const lowest = priceRow("From", d.priceMin, d.fromChange) + priceRow("Floor", d.marketFloor, d.floorChange);
    let badges = availabilityBadges(d);
    if (d.inCollection) {
      badges = '<div style="position: absolute; top: 4px; left: 4px; background: rgba(40,167,69,0.9); color: white; padding: 2px 6px; border-radius: 4px; font-size: 0.8em;" title="In Collection">&#9829;</div>' + badges;
    }
    const body = pricePill(d, cfgv) + endedPill(d, cfgv) + lowest + metrics;
    return cardShell(d, badges, body, "");
  }

  function archiveHtml(cfgv) {
    let html = '<h1 class="page-header">Archive</h1>';
    const term = cfgv.q.toLowerCase();
    const archived = (MANIFEST.archived || []).slice().sort((a, b) => (a.canonical < b.canonical ? -1 : 1));
    archived.forEach((card) => {
      const fileName = card.canonical + ".json";
      if (term && fileName.toLowerCase().indexOf(term) === -1) return;
      const articleName = card.canonical.split("_").pop().replace(/-/g, " ");
      html +=
        '<div class="d-flex mb-4 col-12 col-sm-6 col-md-4 col-lg-2">' +
          '<a name="' + fileName + '" href="' + cfg().cardHref(fileName, true) + '" class="card text-center w-100 galleryBox">' +
            '<img src="' + imagePath(card.canonical) + '" alt="' + escapeHtml(articleName) + '" class="lazy card-img-top img-fluid">' +
            '<div class="card-body d-flex flex-column p-2" style="gap: 2px;">' +
              '<div class="card-title" style="font-size: 0.9em; font-weight: bold; margin-bottom: 2px;">' + escapeHtml(articleName) + "</div>" +
              (card.updated ? '<div style="font-size: 0.75em; color: #666;">(' + fmtDate(card.updated) + ")</div>" : "") +
            "</div>" +
          "</a>" +
        "</div>";
    });
    return html;
  }

  function render() {
    const cfgv = params();
    const terms = cfgv.q.toLowerCase().split(/\s+/).filter(Boolean);
    let list = (MANIFEST.cards || [])
      .filter((c) => terms.every((t) => (c.canonical + ".json").toLowerCase().indexOf(t) !== -1))
      .map((c) => cardData(c, cfgv));
    if (cfgv.collectionView) list = list.filter((d) => COLLECTION_NAMES.has(d.canonical));
    sortList(list, cfgv);
    let grid = list.map((d) => cardHtml(d, cfgv)).join("");
    if (!cfgv.collectionView) grid += archiveHtml(cfgv); // archive only in browse view
    document.getElementById("searchResults").innerHTML = grid;
    syncControls(cfgv);
    const rc = document.getElementById("resultCount");
    if (rc) rc.textContent = list.length + " cards";
  }

  function syncControls(cfgv) {
    const set = (id, val) => { const el = document.getElementById(id); if (el) el.value = val; };
    set("sortBy", cfgv.sortBy); set("order", cfgv.order);
    set("pricePeriod", cfgv.pricePeriod); set("priceType", cfgv.priceType);
    const sh = document.getElementById("searchStringHidden");
    if (sh) sh.value = cfgv.q;
    const si = document.getElementById("ProductSearchInput");
    if (si && !si.value) si.value = cfgv.q;
  }

  function updateUrl(cfgv) {
    // Preserve host-specific params (view / collection) and only rewrite the
    // grid controls; works for both the /search.html viewer and CardWatcher's /.
    const p = new URLSearchParams(window.location.search);
    if (cfgv.q) p.set("q", cfgv.q); else p.delete("q");
    p.delete("searchString");
    p.set("sortBy", cfgv.sortBy); p.set("order", cfgv.order);
    p.set("pricePeriod", cfgv.pricePeriod); p.set("priceType", cfgv.priceType);
    history.replaceState(null, "", window.location.pathname + "?" + p.toString());
  }

  function onControlChange() {
    const cur = params();
    const cfgv = {
      q: cur.q,
      sortBy: document.getElementById("sortBy").value,
      order: document.getElementById("order").value,
      pricePeriod: valOr("pricePeriod", cur.pricePeriod),
      priceType: valOr("priceType", cur.priceType),
      collectionView: cur.collectionView,
    };
    updateUrl(cfgv);
    render();
  }
  function valOr(id, fallback) { const el = document.getElementById(id); return el ? el.value : fallback; }

  async function main() {
    const c = cfg();
    try {
      const jobs = [fetchJSON(c.priceHistoryUrl).catch(() => ({})), fetchJSON(c.manifestUrl)];
      if (c.collection) jobs.push(fetchJSON(c.collectionApi).catch(() => null));
      const [ph, manifest, collection] = await Promise.all(jobs);
      PRICE_HISTORY = ph || {};
      MANIFEST = manifest;
      if (collection && collection.items) {
        for (const item of collection.items) {
          COLLECTION_NAMES.add(item.canonical_name);
          const agg = COLLECTION_BY_CARD[item.canonical_name] || { qty: 0, total: 0, unit: 0 };
          agg.qty += item.quantity || 0;
          agg.total += item.total_value || 0;
          agg.unit = agg.qty > 0 ? agg.total / agg.qty : 0;
          COLLECTION_BY_CARD[item.canonical_name] = agg;
        }
      }
    } catch (e) {
      document.getElementById("searchResults").innerHTML =
        '<div class="col-12 text-danger">Failed to load card data.</div>';
      console.error(e);
      return;
    }
    render();

    const sortBy = document.getElementById("sortBy");
    if (sortBy) {
      sortBy.addEventListener("change", function () {
        document.getElementById("order").value = this.value === "name" ? "asc" : "desc";
        onControlChange();
      });
    }
    ["order", "pricePeriod", "priceType"].forEach((id) => {
      const el = document.getElementById(id);
      if (el) el.addEventListener("change", onControlChange);
    });
  }

  document.addEventListener("DOMContentLoaded", main);
})();
