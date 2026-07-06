/* Shared data + helpers for the static CardWatcher viewer.
 *
 * Transcribed 1:1 from the Flask app's app/language_libraries.py so the card
 * rows render with identical flag sprites and labels. Kept as a plain global
 * (no modules) to match the app's inline-script style and avoid a build step.
 */
(function (global) {
  "use strict";

  const CONDITION_LONG = {
    MT: "Mint", NM: "Near Mint", EX: "Excellent", GD: "Good",
    LP: "Light Played", PL: "Played", PO: "Poor",
  };

  const FLAGS = {
    "Item location: Austria": "-16px -70px",
    "Item location: Belgium": "-32px -70px",
    "Item location: Bulgaria": "-48px -70px",
    "Item location: Croatia": "-272px -70px",
    "Item location: Cyprus": "-96px -70px",
    "Item location: Czech Republic": "-112px -70px",
    "Item location: Estonia": "-160px -70px",
    "Item location: Denmark": "-144px -70px",
    "Item location: Finland": "-208px -70px",
    "Item location: France": "-224px -70px",
    "Item location: Greece": "-256px -70px",
    "Item location: Germany": "-128px -70px",
    "Item location: Hungary": "-288px -70px",
    "Item location: Iceland": "-336px -70px",
    "Item location: Ireland": "-304px -70px",
    "Item location: Italy": "-352px -70px",
    "Item location: Japan": "-368px -70px",
    "Item location: Latvia": "-432px -70px",
    "Item location: Liechtenstein": "-384px -70px",
    "Item location: Lithuania": "-400px -70px",
    "Item location: Luxembourg": "-416px -70px",
    "Item location: Malta": " -448px -70px",
    "Item location: Netherlands": "-464px -70px",
    "Item location: Norway": "-480px -70px",
    "Item location: Poland": "-496px -70px",
    "Item location: Portugal": "-512px -70px",
    "Item location: Romania": "-528px -70px",
    "Item location: Singapore": "-576px -70px",
    "Item location: Slovakia": "-608px -70px",
    "Item location: Slovenia": "-592px -70px",
    "Item location: Spain": "-176px -70px",
    "Item location: Sweden": "-560px -70px",
    "Item location: Switzerland": "-80px -70px",
    "Item location: United Kingdom": " -240px -70px",
  };

  const LANGUAGE_FLAGS = {
    German: "-80px -0px",
    English: " -16px -0px",
    "S-Chinese": " -176px -0px",
    Japanese: "-208px -0px",
    Korean: "-304px -0px",
    "T-Chinese": "-336px -0px",
    French: "-48px -0px",
    Spanish: "-112px -0px",
    Portuguese: "-240px -0px",
    Italian: "-144px -0px",
    Russian: "-272px -0px",
    Dutch: "-368px -0px",
    Polish: "-400px -0px",
    Czech: "-432px -0px",
    Hungarian: "-464px -0px",
  };

  // Both German and English keys map to the canonical English value. Data in
  // this repo is already English, but the app normalizes both, so we mirror it.
  const LANGUAGE_TO_ENGLISH = {
    Deutsch: "German", German: "German",
    Englisch: "English", English: "English",
    Japanisch: "Japanese", Japanese: "Japanese",
    "S-Chinesisch": "S-Chinese", "S-Chinese": "S-Chinese",
    "T-Chinesisch": "T-Chinese", "T-Chinese": "T-Chinese",
    Koreanisch: "Korean", Korean: "Korean",
    Spanisch: "Spanish", Spanish: "Spanish",
    Italienisch: "Italian", Italian: "Italian",
    Portugiesisch: "Portuguese", Portuguese: "Portuguese",
    "Französisch": "French", French: "French",
    Russisch: "Russian", Russian: "Russian",
    "Niederländisch": "Dutch", Dutch: "Dutch",
    Polnisch: "Polish", Polish: "Polish",
    Tschechisch: "Czech", Czech: "Czech",
    Ungarisch: "Hungarian", Hungarian: "Hungarian",
  };

  const LOCATION_TO_ENGLISH = {
    "Artikelstandort: Italien": "Item location: Italy", "Item location: Italy": "Item location: Italy",
    "Artikelstandort: Malta": "Item location: Malta", "Item location: Malta": "Item location: Malta",
    "Artikelstandort: Deutschland": "Item location: Germany", "Item location: Germany": "Item location: Germany",
    "Artikelstandort: Österreich": "Item location: Austria", "Item location: Austria": "Item location: Austria",
    "Artikelstandort: Schweiz": "Item location: Switzerland", "Item location: Switzerland": "Item location: Switzerland",
    "Artikelstandort: Vereinigtes Königreich": "Item location: United Kingdom", "Item location: United Kingdom": "Item location: United Kingdom",
    "Artikelstandort: Niederlande": "Item location: Netherlands", "Item location: Netherlands": "Item location: Netherlands",
    "Artikelstandort: Frankreich": "Item location: France", "Item location: France": "Item location: France",
    "Artikelstandort: Belgien": "Item location: Belgium", "Item location: Belgium": "Item location: Belgium",
    "Artikelstandort: Bulgarien": "Item location: Bulgaria", "Item location: Bulgaria": "Item location: Bulgaria",
    "Artikelstandort: Schweden": "Item location: Sweden", "Item location: Sweden": "Item location: Sweden",
    "Artikelstandort: Polen": "Item location: Poland", "Item location: Poland": "Item location: Poland",
    "Artikelstandort: Dänemark": "Item location: Denmark", "Item location: Denmark": "Item location: Denmark",
    "Artikelstandort: Spanien": "Item location: Spain", "Item location: Spain": "Item location: Spain",
    "Artikelstandort: Portugal": "Item location: Portugal", "Item location: Portugal": "Item location: Portugal",
    "Artikelstandort: Irland": "Item location: Ireland", "Item location: Ireland": "Item location: Ireland",
    "Artikelstandort: Luxemburg": "Item location: Luxembourg", "Item location: Luxembourg": "Item location: Luxembourg",
    "Artikelstandort: Slowenien": "Item location: Slovenia", "Item location: Slovenia": "Item location: Slovenia",
    "Artikelstandort: Griechenland": "Item location: Greece", "Item location: Greece": "Item location: Greece",
    "Artikelstandort: Tschechische Republik": "Item location: Czech Republic", "Item location: Czech Republic": "Item location: Czech Republic",
    "Artikelstandort: Kroatien": "Item location: Croatia", "Item location: Croatia": "Item location: Croatia",
    "Artikelstandort: Rumänien": "Item location: Romania", "Item location: Romania": "Item location: Romania",
    "Artikelstandort: Zypern": "Item location: Cyprus", "Item location: Cyprus": "Item location: Cyprus",
    "Artikelstandort: Slowakei": "Item location: Slovakia", "Item location: Slovakia": "Item location: Slovakia",
    "Artikelstandort: Litauen": "Item location: Lithuania", "Item location: Lithuania": "Item location: Lithuania",
    "Artikelstandort: Norwegen": "Item location: Norway", "Item location: Norway": "Item location: Norway",
    "Artikelstandort: Finnland": "Item location: Finland", "Item location: Finland": "Item location: Finland",
    "Artikelstandort: Lettland": "Item location: Latvia", "Item location: Latvia": "Item location: Latvia",
    "Artikelstandort: Estland": "Item location: Estonia", "Item location: Estonia": "Item location: Estonia",
    "Artikelstandort: Ungarn": "Item location: Hungary", "Item location: Hungary": "Item location: Hungary",
    "Artikelstandort: Island": "Item location: Iceland", "Item location: Iceland": "Item location: Iceland",
    "Artikelstandort: Tschechien": "Item location: Czech Republic",
  };

  // --- Helpers -------------------------------------------------------------

  function escapeHtml(s) {
    return String(s == null ? "" : s)
      .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;").replace(/'/g, "&#39;");
  }

  // Runtime config, overridable per host page via window.CW_CFG. Defaults match
  // the standalone GitHub Pages viewer; CardWatcher overrides the URLs/links so
  // the same JS drives both. See CW.cfg() for the resolved values.
  const CFG_DEFAULTS = {
    imageBase: "images/",                       // CardWatcher: "data/images/"
    priceHistoryUrl: "changes/price_history.json", // CardWatcher: "data/price_history.json"
    manifestUrl: "manifest.json",               // CardWatcher: "api/manifest"
    collection: false,                          // CardWatcher: true
    collectionApi: "api/collection",
    // Link to a card page. archived only matters to the static viewer, which
    // serves active vs archived cards from different dirs.
    cardHref: function (fileName, archived) {
      return "card.html?name=" + encodeURIComponent(fileName) + (archived ? "&archived=1" : "");
    },
  };
  function cfg() {
    return Object.assign({}, CFG_DEFAULTS, global.CW_CFG || {});
  }

  // Card product image, derived from the canonical name (the page JSON's own
  // `image` field points at the app's legacy data/images path).
  function imagePath(canonical) {
    return cfg().imageBase + canonical + ".jpg";
  }

  // Fetch JSON from a site-root-relative path; throws on HTTP error.
  async function fetchJSON(path) {
    const res = await fetch(path, { cache: "no-cache" });
    if (!res.ok) throw new Error("HTTP " + res.status + " for " + path);
    return res.json();
  }

  // Unix seconds -> "dd.mm.yyyy" (mirrors datetime.fromtimestamp(...).strftime).
  function fmtDateFromTs(ts) {
    const n = parseFloat(ts);
    if (!n || !isFinite(n)) return "";
    const d = new Date(n * 1000);
    const p = (x) => ("0" + x).slice(-2);
    return p(d.getDate()) + "." + p(d.getMonth() + 1) + "." + d.getFullYear();
  }

  global.CW = {
    CONDITION_LONG, FLAGS, LANGUAGE_FLAGS, LANGUAGE_TO_ENGLISH, LOCATION_TO_ENGLISH,
    escapeHtml, imagePath, fetchJSON, fmtDateFromTs, cfg,
  };
})(window);
