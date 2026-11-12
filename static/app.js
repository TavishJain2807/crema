/* Crema — single-page coffee journal */

(function () {
  "use strict";

  var appEl = document.getElementById("app");
  var modalRoot = document.getElementById("modal-root");
  var toastRoot = document.getElementById("toast-root");

  var state = {
    user: null,
    beans: [],
    shots: [],
    stats: null,
    authMode: "signin",
    route: { name: "dashboard", id: null },
    historyQuery: "",
    historyMethod: "",
    historyFavorite: false,
    offline: false,
    pending: [],
    flushing: false
  };

  var deferredInstall = null;
  var draftFlush = null;

  function runningStandalone() {
    return window.matchMedia("(display-mode: standalone)").matches || window.navigator.standalone === true;
  }

  var METHODS = ["espresso", "latte", "cappuccino", "flat white", "filter", "cold brew", "other"];
  var MILK_METHODS = ["latte", "cappuccino", "flat white"];
  var TAGS = ["Chocolate", "Caramel", "Nutty", "Citrus", "Berry", "Stone fruit", "Floral",
    "Honey", "Molasses", "Spice", "Smoky", "Creamy", "Tea-like", "Winey"];
  var TASTE = [
    ["acidity", "Acidity"],
    ["body", "Body"],
    ["sweetness", "Sweetness"],
    ["bitterness", "Bitterness"],
    ["aftertaste", "Aftertaste"]
  ];
  var MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];

  var ICON = {
    grid: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"><rect x="3.5" y="3.5" width="7" height="7" rx="1.6"/><rect x="13.5" y="3.5" width="7" height="7" rx="1.6"/><rect x="3.5" y="13.5" width="7" height="7" rx="1.6"/><rect x="13.5" y="13.5" width="7" height="7" rx="1.6"/></svg>',
    cup: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"><path d="M4 9.5h13v4.5a5 5 0 0 1-5 5H9a5 5 0 0 1-5-5V9.5Z"/><path d="M17 10.5h1.3a2.4 2.4 0 0 1 0 4.8H17"/><path d="M7.5 3.5v2.2M11.5 3.5v2.2M15.5 3.5v2.2"/></svg>',
    cafe: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"><path d="M4 20V10.5M20 20V10.5"/><path d="M3 10.5 4.5 4h15L21 10.5Z"/><path d="M9 20v-5h6v5"/></svg>',
    more: '<svg viewBox="0 0 24 24" fill="currentColor" stroke="none"><circle cx="5" cy="12" r="1.8"/><circle cx="12" cy="12" r="1.8"/><circle cx="19" cy="12" r="1.8"/></svg>',
    clock: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="8.6"/><path d="M12 7.4V12l3.1 2"/></svg>',
    bean: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"><ellipse cx="12" cy="12" rx="6.4" ry="8.6" transform="rotate(38 12 12)"/><path d="M9.2 6.6c2.6 3 2.6 7.8 0 10.8"/></svg>',
    calc: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"><rect x="4.5" y="3.5" width="15" height="17" rx="2.4"/><path d="M8 7.8h8"/><path d="M8 12h.01M12 12h.01M16 12h.01M8 16h.01M12 16h.01M16 16h.01"/></svg>',
    gear: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="3.1"/><path d="M12 2.6v2.8M12 18.6v2.8M2.6 12h2.8M18.6 12h2.8M5.4 5.4l2 2M16.6 16.6l2 2M18.6 5.4l-2 2M7.4 16.6l-2 2"/></svg>',
    plus: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"><path d="M12 5v14M5 12h14"/></svg>',
    search: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round"><circle cx="11" cy="11" r="6.6"/><path d="m16.2 16.2 4 4"/></svg>',
    chevron: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="m6 9.5 6 6 6-6"/></svg>',
    edit: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"><path d="M4 20h4l10.5-10.5a2.1 2.1 0 0 0-3-3L5 17v3Z"/><path d="m14.5 7.5 2 2"/></svg>',
    trash: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"><path d="M4.5 7h15M9.5 7V4.8h5V7M6.5 7l.8 12.2h9.4L17.5 7"/><path d="M10.2 10.5v5.4M13.8 10.5v5.4"/></svg>',
    archive: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"><rect x="3.5" y="4.5" width="17" height="4.5" rx="1.2"/><path d="M5.2 9v9.3a1.2 1.2 0 0 0 1.2 1.2h11.2a1.2 1.2 0 0 0 1.2-1.2V9"/><path d="M10 12.8h4"/></svg>',
    download: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"><path d="M12 4v11"/><path d="m7.5 10.8 4.5 4.5 4.5-4.5"/><path d="M5 19.5h14"/></svg>',
    logout: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"><path d="M14.5 4.5H6.8A1.8 1.8 0 0 0 5 6.3v11.4a1.8 1.8 0 0 0 1.8 1.8h7.7"/><path d="M10 12h9.5M16 8.5l3.5 3.5L16 15.5"/></svg>',
    x: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"><path d="M6 6l12 12M18 6 6 18"/></svg>',
    star: '<svg viewBox="0 0 24 24" fill="currentColor" stroke="currentColor" stroke-width="1" stroke-linejoin="round"><path d="m12 3.6 2.5 5.2 5.7.8-4.1 4 1 5.7-5.1-2.7-5.1 2.7 1-5.7-4.1-4 5.7-.8L12 3.6Z"/></svg>',
    starOutline: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.4" stroke-linejoin="round"><path d="m12 3.6 2.5 5.2 5.7.8-4.1 4 1 5.7-5.1-2.7-5.1 2.7 1-5.7-4.1-4 5.7-.8L12 3.6Z"/></svg>',
    check: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="m5 12.5 4.5 4.5L19 6.5"/></svg>',
    camera: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"><path d="M4 8.6h3.2l1.4-2.1h6.8l1.4 2.1H20v10.2H4z"/><circle cx="12" cy="13.4" r="3.2"/></svg>',
    timer: '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="13.6" r="7.6"/><path d="M12 10.2v3.6l2.6 1.7"/><path d="M9.2 2.6h5.6"/><path d="M18.6 5.2l1.5 1.5"/></svg>',
    play: '<svg viewBox="0 0 24 24" fill="currentColor" stroke="none"><path d="M8.4 5.3a1 1 0 0 1 1.5-.9l9 6.7a1 1 0 0 1 0 1.8l-9 6.7a1 1 0 0 1-1.5-.9z"/></svg>',
    stop: '<svg viewBox="0 0 24 24" fill="currentColor" stroke="none"><rect x="6.4" y="6.4" width="11.2" height="11.2" rx="2.2"/></svg>'
  };

  // ------------------------------------------------------------ utilities

  function esc(value) {
    return String(value == null ? "" : value).replace(/[&<>"']/g, function (ch) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[ch];
    });
  }

  function $(sel, root) { return (root || document).querySelector(sel); }
  function $$(sel, root) { return Array.prototype.slice.call((root || document).querySelectorAll(sel)); }

  function num(value, digits) {
    if (value === null || value === undefined || value === "") return "—";
    var n = Number(value);
    if (!isFinite(n)) return "—";
    var d = digits === undefined ? 1 : digits;
    var out = n.toFixed(d);
    if (d > 0) out = out.replace(/\.0+$/, "");
    return out;
  }

  function grams(value) { return value === null || value === undefined || value === "" ? "—" : num(value, 1) + "g"; }

  function shotTime(value) {
    if (value === null || value === undefined || value === "") return "—";
    var s = Number(value);
    if (s < 60) return num(s, s % 1 ? 1 : 0) + "s";
    var m = Math.floor(s / 60);
    var rest = Math.round(s % 60);
    return m + ":" + (rest < 10 ? "0" : "") + rest;
  }

  function ratio(shot) {
    if (!shot || !shot.dose_g || !shot.yield_g) return null;
    var r = shot.yield_g / shot.dose_g;
    return r >= 10 ? "1:" + Math.round(r) : "1:" + r.toFixed(1);
  }

  // Turns the three numbers people actually know (dose, yield, time) into
  // plain advice they can act on before the next shot. A style (ristretto,
  // single, double, lungo) moves the windows that advice is measured against.
  var ESPRESSO_METHODS = ["espresso", "latte", "cappuccino", "flat white"];

  var ESPRESSO_STYLES = [
    { id: "ristretto", label: "Ristretto", dose: 18, yield: 24, time: 22,
      ratio: [1.15, 1.6], window: [18, 28], flow: 1.1 },
    { id: "single", label: "Single", dose: 9, yield: 18, time: 25,
      ratio: [1.8, 2.2], window: [22, 32], flow: 0.72 },
    { id: "double", label: "Double", dose: 18, yield: 36, time: 28,
      ratio: [1.8, 2.2], window: [25, 32], flow: 1.3 },
    { id: "lungo", label: "Lungo", dose: 18, yield: 50, time: 38,
      ratio: [2.5, 3.5], window: [32, 45], flow: 1.3 }
  ];

  function styleById(id) {
    for (var i = 0; i < ESPRESSO_STYLES.length; i++) {
      if (ESPRESSO_STYLES[i].id === id) return ESPRESSO_STYLES[i];
    }
    return null;
  }

  function styleRecipe(style) {
    if (!style) return "Choose a style to set the target and starting recipe.";
    var r = style.yield / style.dose;
    return style.label + " · " + style.dose + "g in · " + style.yield + "g out · 1:" +
      (r >= 10 ? Math.round(r) : r.toFixed(1)) + " · about " + style.time + "s";
  }

  function dialInNotes(doseValue, yieldValue, timeValue, method, styleId) {
    var dose = parseFloat(doseValue);
    var yieldG = parseFloat(yieldValue);
    var time = parseFloat(timeValue);
    var notes = [];
    var isEspresso = ESPRESSO_METHODS.indexOf(method || "espresso") !== -1;
    var ratioValue = dose > 0 && yieldG > 0 ? yieldG / dose : null;
    var style = styleById(styleId);

    function ratioLabel(value) {
      return "1:" + (value >= 10 ? Math.round(value) : value.toFixed(1));
    }

    if (!isEspresso) {
      if (ratioValue !== null) {
        var filterRatio = ratioLabel(ratioValue);
        if (ratioValue < 12) notes.push({ kind: "warn", text: "That is " + filterRatio + " — strong for filter. Most pour-over lands around 1:15 to 1:17." });
        else if (ratioValue > 18) notes.push({ kind: "warn", text: filterRatio + " is thin for filter. Try 1:15 to 1:17 and taste again." });
        else notes.push({ kind: "ok", text: filterRatio + " sits in the usual filter range." });
      }
      return notes;
    }

    // With no style chosen, fall back to the classic 1:2 double.
    var lowRatio = style ? style.ratio[0] : 1.7;
    var highRatio = style ? style.ratio[1] : 2.4;
    var lowTime = style ? style.window[0] : 25;
    var highTime = style ? style.window[1] : 32;
    var article = style ? "a " + style.label.toLowerCase() : "an espresso";
    var aim = "1:" + lowRatio + "–" + highRatio;
    var doseNote = style
      ? " — " + style.dose + "g in to " + Math.round(style.dose * lowRatio) + "–" + Math.round(style.dose * highRatio) + "g out"
      : "";

    if (ratioValue !== null) {
      var shotRatio = ratioLabel(ratioValue);
      if (ratioValue < lowRatio) {
        notes.push({ kind: "warn", text: shotRatio + " is short for " + article + " (" + aim + doseNote + "). Let it run longer; short shots taste sharp and thin." });
      } else if (ratioValue > highRatio) {
        notes.push({ kind: "warn", text: shotRatio + " is long for " + article + " (" + aim + doseNote + "). Stop a little earlier; long shots turn watery and bitter." });
      } else {
        notes.push({ kind: "ok", text: shotRatio + " is where " + article + " should land (" + aim + ")." });
      }
    }

    if (time > 0) {
      if (time < lowTime) {
        notes.push({ kind: "warn", text: time.toFixed(1) + "s is quick for " + article + " (" + lowTime + "–" + highTime + "s). Grind finer in small steps and keep the dose steady." });
      } else if (time > highTime) {
        notes.push({ kind: "warn", text: time.toFixed(1) + "s runs long for " + article + " (" + lowTime + "–" + highTime + "s). Coarsen the grind a notch; if it still stalls, check for channeling." });
      } else {
        notes.push({ kind: "ok", text: time.toFixed(1) + "s sits in the " + lowTime + "–" + highTime + "s window for " + article + "." });
      }
    }

    if (ratioValue !== null && time > 0) {
      if (time < lowTime && ratioValue < lowRatio) notes.push({ kind: "tip", text: "Fast and short together point at the grind: go finer before changing anything else." });
      if (time > highTime && ratioValue > highRatio) notes.push({ kind: "tip", text: "Slow and long: coarsen the grind, then stop the shot at " + aim + "." });
      if (time < lowTime && ratioValue > highRatio) notes.push({ kind: "tip", text: "Fast but long means the grind is too coarse — tightening it fixes both numbers at once." });
      if (time > highTime && ratioValue < lowRatio) notes.push({ kind: "tip", text: "Slow but short usually means channeling or a choked puck. Work on puck prep before the grind." });
      var flow = yieldG / time;
      var expected = style ? style.flow : 1.3;
      if (flow < expected * 0.7) notes.push({ kind: "tip", text: "Flow is about " + flow.toFixed(1) + " g/s, well under the " + expected.toFixed(1) + " g/s " + article + " usually shows — expect a heavier body." });
      else if (flow > expected * 1.35) notes.push({ kind: "tip", text: "Flow is about " + flow.toFixed(1) + " g/s, quicker than the " + expected.toFixed(1) + " g/s " + article + " usually shows — the puck is offering little resistance." });
    }

    return notes.slice(0, 6);
  }

  function stars(value, outline) {
    if (!value) return "";
    var out = "";
    for (var i = 1; i <= 5; i++) out += i <= value ? "★" : (outline ? "☆" : "");
    return out;
  }

  function relDay(isoDate) {
    var d = new Date(isoDate);
    var now = new Date();
    var midnight = new Date(now.getFullYear(), now.getMonth(), now.getDate());
    var target = new Date(d.getFullYear(), d.getMonth(), d.getDate());
    var diff = Math.round((midnight - target) / 86400000);
    if (diff === 0) return "Today";
    if (diff === 1) return "Yesterday";
    if (diff < 7 && diff > 0) return diff + " days ago";
    return MONTHS[d.getMonth()] + " " + d.getDate() + (d.getFullYear() !== now.getFullYear() ? ", " + d.getFullYear() : "");
  }

  function fmtDateTime(isoDate) {
    var d = new Date(isoDate);
    var time = d.toLocaleTimeString(undefined, { hour: "numeric", minute: "2-digit" });
    return relDay(isoDate) + " · " + time;
  }

  function toLocalInput(value) {
    var d = value ? new Date(value) : new Date();
    if (isNaN(d.getTime())) d = new Date();
    function p(n) { return String(n).padStart(2, "0"); }
    return d.getFullYear() + "-" + p(d.getMonth() + 1) + "-" + p(d.getDate()) + "T" + p(d.getHours()) + ":" + p(d.getMinutes());
  }

  function fromLocalInput(value) {
    if (!value) return new Date().toISOString();
    var d = new Date(value);
    return isNaN(d.getTime()) ? new Date().toISOString() : d.toISOString();
  }

  function initials(name) {
    return String(name || "?").trim().split(/\s+/).slice(0, 2).map(function (p) { return p.charAt(0).toUpperCase(); }).join("");
  }

  function avatarHtml(user, extra) {
    var cls = "avatar" + (extra ? " " + extra : "");
    var avatar = user && user.avatar;
    if (avatar && avatar.url) {
      return '<span class="' + cls + ' has-photo"><img src="' + esc(avatar.url) + '" alt=""></span>';
    }
    return '<span class="' + cls + '">' + esc(initials(user ? user.name : "")) + "</span>";
  }

  function titleCase(value) {
    var text = String(value || "");
    return text.charAt(0).toUpperCase() + text.slice(1);
  }

  function icon(name) { return ICON[name] || ""; }

  function compressPhoto(file) {
    return new Promise(function (resolve, reject) {
      if (!file || !/^image\//.test(file.type || "")) {
        reject(new Error("Choose a photo from your library or camera"));
        return;
      }
      var reader = new FileReader();
      reader.onerror = function () { reject(new Error("That photo could not be read")); };
      reader.onload = function () {
        var img = new Image();
        img.onerror = function () { reject(new Error("That photo could not be read")); };
        img.onload = function () {
          function render(maxSide, quality) {
            var scale = Math.min(1, maxSide / Math.max(img.width, img.height));
            var width = Math.max(1, Math.round(img.width * scale));
            var height = Math.max(1, Math.round(img.height * scale));
            var canvas = document.createElement("canvas");
            canvas.width = width;
            canvas.height = height;
            var ctx = canvas.getContext("2d");
            ctx.fillStyle = "#f5eee3";
            ctx.fillRect(0, 0, width, height);
            ctx.drawImage(img, 0, 0, width, height);
            return { data: canvas.toDataURL("image/jpeg", quality), width: width, height: height };
          }
          try {
            var full = render(1600, 0.82);
            var thumb = render(480, 0.7);
            resolve({ full: full.data, thumb: thumb.data, width: full.width, height: full.height });
          } catch (e) {
            reject(new Error("That photo could not be prepared"));
          }
        };
        img.src = reader.result;
      };
      reader.readAsDataURL(file);
    });
  }

  function openPhoto(url, caption) {
    openModal({
      title: caption || "Shot photo",
      body: '<div class="photo-view"><img src="' + esc(url) + '" alt="' + esc(caption || "Shot photo") + '"></div>',
      footer: '<button class="btn btn-quiet" id="photo-close">Close</button>',
      onMount: function () {
        $("#photo-close").addEventListener("click", closeModal);
      }
    });
  }

  function toast(message, kind) {
    var el = document.createElement("div");
    el.className = "toast" + (kind === "error" ? " error" : "");
    el.textContent = message;
    toastRoot.appendChild(el);
    setTimeout(function () {
      el.classList.add("out");
      setTimeout(function () { el.remove(); }, 220);
    }, 3200);
  }

  async function api(path, options) {
    options = options || {};
    var init = {
      method: options.method || "GET",
      credentials: "same-origin",
      headers: {}
    };
    if (options.body !== undefined) {
      init.headers["Content-Type"] = "application/json";
      init.body = JSON.stringify(options.body);
    }
    var res;
    try {
      res = await fetch(path, init);
    } catch (networkError) {
      var offline = new Error("Can’t reach Crema. Check your connection and try again.");
      offline.offline = true;
      throw offline;
    }
    if (state.offline) {
      // Any successful response proves the connection is back. Clear the
      // banner immediately instead of waiting for the (unreliable) online event.
      state.offline = false;
      setOfflineNotice(false);
    }
    var data = null;
    try { data = await res.json(); } catch (e) { data = null; }
    if (!res.ok) {
      var err = new Error((data && data.error) || "Something went wrong. Please try again.");
      err.status = res.status;
      throw err;
    }
    return data;
  }

  function haptic() {
    try { if (navigator.vibrate) navigator.vibrate(8); } catch (e) { /* not supported */ }
  }

  function snapshotKey(userId) {
    return "crema.snapshot." + userId;
  }

  function saveSnapshot() {
    if (!state.user) return;
    try {
      localStorage.setItem(snapshotKey(state.user.id), JSON.stringify({
        user: state.user,
        beans: state.beans,
        shots: state.shots,
        stats: state.stats,
        saved_at: Date.now()
      }));
      localStorage.setItem("crema.last_user", String(state.user.id));
    } catch (e) { /* storage may be full or disabled */ }
  }

  function readSnapshot() {
    try {
      var last = localStorage.getItem("crema.last_user");
      if (!last) return null;
      var raw = localStorage.getItem(snapshotKey(last));
      if (!raw) return null;
      var snapshot = JSON.parse(raw);
      if (!snapshot || !snapshot.user || !Array.isArray(snapshot.shots)) return null;
      if (Date.now() - (snapshot.saved_at || 0) > 30 * 86400000) return null;
      return snapshot;
    } catch (e) {
      return null;
    }
  }

  function forgetSnapshot() {
    try {
      if (state.user) localStorage.removeItem(snapshotKey(state.user.id));
      localStorage.removeItem("crema.last_user");
    } catch (e) { /* ignore */ }
  }

  function draftKey() {
    return "crema.draft." + (state.user ? state.user.id : "anon");
  }

  function readDraft() {
    try {
      var draft = JSON.parse(localStorage.getItem(draftKey()) || "null");
      if (!draft || !draft.values || Date.now() - (draft.saved_at || 0) > 30 * 86400000) return null;
      return draft.values;
    } catch (e) {
      return null;
    }
  }

  function saveDraft(values) {
    try {
      localStorage.setItem(draftKey(), JSON.stringify({ saved_at: Date.now(), values: values }));
    } catch (e) { /* ignore */ }
  }

  function clearDraft() {
    try { localStorage.removeItem(draftKey()); } catch (e) { /* ignore */ }
  }

  // ------------------------------------------------------------ offline queue
  //
  // Logging a shot in a kitchen with patchy wifi should not lose the shot.
  // A failed POST is parked in IndexedDB and replayed when Crema is reachable
  // again. Each entry carries a client id so a retry cannot log it twice.

  var QUEUE_DB = "crema-queue";
  var QUEUE_STORE = "shots";

  function queueOpen() {
    return new Promise(function (resolve, reject) {
      if (!window.indexedDB) {
        reject(new Error("This browser can’t store offline entries"));
        return;
      }
      var request = indexedDB.open(QUEUE_DB, 1);
      request.onupgradeneeded = function () {
        var db = request.result;
        if (!db.objectStoreNames.contains(QUEUE_STORE)) {
          db.createObjectStore(QUEUE_STORE, { keyPath: "key", autoIncrement: true });
        }
      };
      request.onsuccess = function () { resolve(request.result); };
      request.onerror = function () { reject(request.error || new Error("Offline storage failed")); };
    });
  }

  function queueWrite(mode, run) {
    return queueOpen().then(function (db) {
      return new Promise(function (resolve, reject) {
        var tx = db.transaction(QUEUE_STORE, mode);
        var request = run(tx.objectStore(QUEUE_STORE));
        tx.oncomplete = function () { resolve(request ? request.result : undefined); };
        tx.onerror = function () { reject(tx.error || new Error("Offline storage failed")); };
        tx.onabort = function () { reject(tx.error || new Error("Offline storage failed")); };
      }).finally(function () { db.close(); });
    });
  }

  function queueAdd(entry) {
    return queueWrite("readwrite", function (store) { return store.add(entry); });
  }

  function queueAll() {
    return queueWrite("readonly", function (store) { return store.getAll(); })
      .then(function (rows) { return rows || []; });
  }

  function queueDelete(key) {
    return queueWrite("readwrite", function (store) { return store.delete(key); });
  }

  function newClientId() {
    if (window.crypto && crypto.randomUUID) return crypto.randomUUID();
    return Date.now().toString(36) + "-" + Math.random().toString(36).slice(2, 10);
  }

  async function enqueueShot(payload, photo) {
    await queueAdd({
      client_id: payload.client_id,
      user_id: state.user ? state.user.id : null,
      created_at: new Date().toISOString(),
      shot: payload,
      photo: photo && photo.full
        ? { full: photo.full, thumb: photo.thumb, width: photo.width, height: photo.height }
        : null
    });
    await refreshPending();
  }

  function myQueue(entries) {
    var me = state.user ? state.user.id : null;
    return (entries || []).filter(function (entry) {
      return me !== null && entry.user_id === me;
    });
  }

  async function refreshPending() {
    try {
      state.pending = myQueue(await queueAll());
    } catch (e) {
      state.pending = [];
    }
    paintQueueBanner();
  }

  function paintQueueBanner() {
    var banner = $("#queue-banner");
    if (!banner) return;
    var count = state.pending.length;
    banner.hidden = count === 0;
    var copy = $("#queue-copy");
    if (copy) {
      copy.innerHTML = count === 1
        ? '<strong>1 shot waiting</strong> — saved on this device, uploads when Crema is reachable.'
        : '<strong>' + count + ' shots waiting</strong> — saved on this device, uploads when Crema is reachable.';
    }
  }

  async function flushQueue(silent) {
    if (state.flushing || !state.user) return 0;
    var entries = [];
    try {
      entries = myQueue(await queueAll());
    } catch (e) {
      return 0;
    }
    if (!entries.length) {
      await refreshPending();
      return 0;
    }

    state.flushing = true;
    var uploaded = 0;
    try {
      for (var i = 0; i < entries.length; i++) {
        var entry = entries[i];
        try {
          var result = await api("/api/shots", { method: "POST", body: entry.shot });
          if (entry.photo) {
            try {
              await api("/api/shots/" + result.shot.id + "/photo", { method: "POST", body: entry.photo });
            } catch (photoErr) { /* the shot matters more than its picture */ }
          }
          await queueDelete(entry.key);
          uploaded++;
        } catch (err) {
          if (err.offline) break;
          if (err.status >= 400 && err.status < 500) {
            // The server will never accept this one; drop it rather than retrying forever.
            await queueDelete(entry.key);
            toast("One offline entry could not be saved", "error");
            continue;
          }
          break;
        }
      }
    } finally {
      state.flushing = false;
    }

    await refreshPending();
    if (uploaded) {
      if (!silent) toast(uploaded === 1 ? "Offline shot uploaded" : uploaded + " offline shots uploaded");
      try {
        await loadAll();
        if (state.route && state.route.name !== "log") route();
      } catch (e) { /* the next refresh will catch up */ }
    }
    return uploaded;
  }

  var reconnectTimer = null;

  function scheduleReconnect() {
    if (reconnectTimer || !state.offline) return;
    reconnectTimer = setTimeout(function () {
      reconnectTimer = null;
      probeConnection(true);
    }, 12000);
  }

  function setOfflineNotice(show) {
    var banner = $("#offline-banner");
    if (banner) banner.hidden = !show;
    if (show) {
      scheduleReconnect();
    } else if (reconnectTimer) {
      clearTimeout(reconnectTimer);
      reconnectTimer = null;
    }
  }

  async function probeConnection(auto) {
    if (!state.offline) return true;
    var reachable = false;
    try {
      var res = await fetch("/api/health", { credentials: "same-origin", cache: "no-store" });
      reachable = res.ok;
    } catch (e) {
      reachable = false;
    }
    if (!reachable) {
      if (!auto) toast("Still offline — check your connection and try again", "error");
      scheduleReconnect();
      return false;
    }
    state.offline = false;
    setOfflineNotice(false);
    if (!state.user) {
      boot();
      return true;
    }
    toast("Back online");
    try {
      await loadAll();
      var inForm = document.querySelector(".modal-backdrop") || (state.route && state.route.name === "log");
      if (!inForm) route();
      await flushQueue(false);
    } catch (e) {
      // Still show the snapshot; the banner is gone because we are reachable.
    }
    return true;
  }

  function installBannerHtml() {
    if (runningStandalone()) return "";
    try { if (localStorage.getItem("crema.install-dismissed") === "1") return ""; } catch (e) { return ""; }
    var isIOS = /iphone|ipad|ipod/i.test(navigator.userAgent);
    var canPrompt = Boolean(deferredInstall);
    if (!canPrompt && !isIOS) return "";

    return '<div class="install-banner" id="install-banner">' +
      '<span class="ib-icon">' + icon("cup") + '</span>' +
      '<div class="ib-copy"><strong>Keep Crema on your home screen</strong>' +
        '<span>' + (canPrompt ? "Opens full screen, one tap away." : "In Safari, tap Share then “Add to Home Screen”.") + '</span></div>' +
      '<div class="ib-actions">' +
        (canPrompt ? '<button class="btn btn-primary btn-sm" id="banner-install">Install</button>' : "") +
        '<button class="btn btn-quiet btn-sm" id="banner-dismiss">Not now</button>' +
      '</div>' +
    '</div>';
  }

  async function promptInstall() {
    if (!deferredInstall) {
      toast("Use your browser menu to install Crema");
      return;
    }
    deferredInstall.prompt();
    try { await deferredInstall.userChoice; } catch (e) { /* dismissed */ }
    deferredInstall = null;
    var banner = $("#install-banner");
    if (banner) banner.remove();
    if (state.route.name === "settings") viewSettings();
  }

  function busy(button, isBusy, label) {
    if (!button) return;
    if (isBusy) {
      button.dataset.label = button.innerHTML;
      button.disabled = true;
      button.innerHTML = label || "Saving…";
    } else {
      button.disabled = false;
      if (button.dataset.label) button.innerHTML = button.dataset.label;
    }
  }

  // ------------------------------------------------------------ data

  async function loadAll() {
    var results = await Promise.all([
      api("/api/me"),
      api("/api/beans"),
      api("/api/shots?limit=400"),
      api("/api/stats")
    ]);
    state.user = results[0].user;
    state.beans = results[1].beans;
    state.shots = results[2].shots;
    state.stats = results[3];
    saveSnapshot();
  }

  async function refreshShots() {
    var data = await api("/api/shots?limit=400");
    state.shots = data.shots;
    saveSnapshot();
  }

  async function refreshBeans() {
    var data = await api("/api/beans");
    state.beans = data.beans;
    saveSnapshot();
  }

  async function refreshStats() {
    state.stats = await api("/api/stats");
    saveSnapshot();
  }

  async function refreshAll() {
    await Promise.all([refreshShots(), refreshBeans(), refreshStats()]);
  }

  // ------------------------------------------------------------ auth

  function renderAuth(mode, error, notice) {
    var activeMode = mode || state.authMode || "signin";
    state.authMode = activeMode;
    var isRegister = activeMode === "register";

    appEl.innerHTML =
      '<div class="auth-shell">' +
        '<aside class="auth-story">' +
          '<a class="brand" href="#/dashboard">' +
            '<span class="brand-mark"></span><span class="brand-word">Crema</span>' +
          '</a>' +
          '<div class="story-copy">' +
            '<h1>Every shot,<br><em>remembered.</em></h1>' +
            '<p>A quiet place for the coffees worth repeating — recipes, beans, and the small details that made the cup taste the way it did.</p>' +
            '<ul class="story-list">' +
              '<li><span class="dot"></span>Log espresso, milk drinks, and filter brews</li>' +
              '<li><span class="dot"></span>Keep notes on every bag of beans</li>' +
              '<li><span class="dot"></span>Your journal, synced across your devices</li>' +
            '</ul>' +
          '</div>' +
          '<div class="story-foot">Self-hosted on your own hardware.</div>' +
          '<div class="rings" aria-hidden="true"><span></span><span></span><span></span><span></span><span></span></div>' +
        '</aside>' +
        '<section class="auth-panel">' +
          '<div class="auth-box">' +
            '<a class="brand auth-mobile-brand" href="#/dashboard"><span class="brand-mark"></span><span class="brand-word">Crema</span></a>' +
            '<h2>' + (isRegister ? "Create your journal" : "Welcome back") + '</h2>' +
            '<p class="sub">' + (isRegister ? "A few details and your first shot is a moment away." : "Sign in to pick up where you left off.") + '</p>' +
            '<div class="auth-tabs">' +
              '<button class="auth-tab' + (!isRegister ? " active" : "") + '" data-mode="signin">Sign in</button>' +
              '<button class="auth-tab' + (isRegister ? " active" : "") + '" data-mode="register">Create account</button>' +
            '</div>' +
            '<div class="auth-error' + (error ? " show" : "") + '" id="auth-error">' + esc(error || "") + '</div>' +
            '<div class="auth-notice' + (notice ? " show" : "") + '" id="auth-notice" role="status">' + esc(notice || "") + '</div>' +
            '<form class="auth-form" id="auth-form" novalidate>' +
              (isRegister ? '<div class="field"><label for="name">Your name</label><input id="name" name="name" type="text" autocomplete="name" placeholder="Tavish Jain" required></div>' : "") +
              '<div class="field"><label for="email">Email</label><input id="email" name="email" type="email" autocomplete="email" placeholder="you@example.com" required></div>' +
              '<div class="field"><label for="password">Password</label><input id="password" name="password" type="password" autocomplete="' + (isRegister ? "new-password" : "current-password") + '" placeholder="' + (isRegister ? "At least 8 characters" : "Your password") + '" required></div>' +
              (isRegister ? '<div class="field"><label for="confirm">Confirm password</label><input id="confirm" name="confirm" type="password" autocomplete="new-password" placeholder="Repeat your password" required></div>' : "") +
              '<button class="btn btn-primary btn-lg btn-block" type="submit">' + (isRegister ? "Create account" : "Sign in") + '</button>' +
            '</form>' +
            '<div class="auth-alt">' +
              (isRegister
                ? 'Already have an account? <a href="#" data-mode="signin">Sign in</a>'
                : 'New here? <a href="#" data-mode="register">Create an account</a>') +
            '</div>' +
            '<p class="auth-sample"><a href="/crema-sample-journal.pdf" target="_blank" rel="noopener">See a sample journal (PDF)</a></p>' +
            '<p class="auth-fine">Your notes are stored on this coffee journal’s own drive and are never shared with anyone else.</p>' +
          '</div>' +
        '</section>' +
      '</div>';

    $$("[data-mode]").forEach(function (el) {
      el.addEventListener("click", function (event) {
        event.preventDefault();
        if (state.authMode !== el.dataset.mode) renderAuth(el.dataset.mode);
      });
    });

    var form = $("#auth-form");
    form.addEventListener("submit", async function (event) {
      event.preventDefault();
      var errorBox = $("#auth-error");
      errorBox.classList.remove("show");

      var data = {
        name: (form.name && form.name.value || "").trim(),
        email: form.email.value.trim(),
        password: form.password.value
      };

      if (!data.email || !data.password) {
        errorBox.textContent = "Please fill in your email and password.";
        errorBox.classList.add("show");
        return;
      }
      if (isRegister) {
        if (!data.name) {
          errorBox.textContent = "Please tell us your name.";
          errorBox.classList.add("show");
          return;
        }
        if (data.password.length < 8) {
          errorBox.textContent = "Password must be at least 8 characters.";
          errorBox.classList.add("show");
          return;
        }
        if (data.password !== form.confirm.value) {
          errorBox.textContent = "Those passwords don’t match yet.";
          errorBox.classList.add("show");
          return;
        }
      }

      var button = form.querySelector("button[type=submit]");
      busy(button, true, isRegister ? "Creating…" : "Signing in…");
      try {
        var payload = await api(isRegister ? "/api/auth/register" : "/api/auth/login", {
          method: "POST",
          body: data
        });
        if (payload.pending) {
          busy(button, false);
          renderAuth("signin", "", payload.message || "Your request has been sent. You’ll be able to sign in once it’s approved.");
          return;
        }
        state.user = payload.user;
        await loadAll();
        if (!location.hash || location.hash === "#/") location.hash = "#/dashboard";
        renderShell();
        route();
        toast(isRegister ? "Welcome to Crema" : "Welcome back");
      } catch (err) {
        busy(button, false);
        errorBox.textContent = err.message;
        errorBox.classList.add("show");
      }
    });
  }

  async function signOut() {
    try { await api("/api/auth/logout", { method: "POST" }); } catch (e) { /* ignore */ }
    forgetSnapshot();
    clearDraft();
    state.user = null;
    state.beans = [];
    state.shots = [];
    state.stats = null;
    history.replaceState(null, "", location.pathname);
    renderAuth("signin");
  }

  // ------------------------------------------------------------ shell

  var NAV = [
    { id: "dashboard", label: "Dashboard", icon: "grid" },
    { id: "log", label: "Log a shot", icon: "cup" },
    { id: "cafe", label: "Café", icon: "cafe" },
    { id: "history", label: "History", icon: "clock" },
    { id: "beans", label: "Beans", icon: "bean", secondary: true },
    { id: "calculator", label: "Calculator", icon: "calc", secondary: true },
    { id: "settings", label: "Settings", icon: "gear", secondary: true }
  ];

  var TITLES = {
    dashboard: ["Journal", "Your coffee, lately"],
    log: ["New entry", "Log a shot"],
    cafe: ["Out and about", "At a café"],
    history: ["Journal", "Brewing history"],
    beans: ["Cellar", "Beans"],
    calculator: ["Tools", "Recipe calculator"],
    settings: ["Crema", "Settings"]
  };

  function renderShell() {
    var user = state.user;
    appEl.innerHTML =
      '<a class="skip" href="#view" id="skip-link">Skip to journal</a>' +
      '<div class="app-shell">' +
        '<aside class="sidebar">' +
          '<a class="brand" href="#/dashboard"><span class="brand-mark"></span><span class="brand-word">Crema</span></a>' +
          '<nav class="nav" aria-label="Main">' +
            '<div class="nav-label">Journal</div>' +
            NAV.map(function (item) {
              return '<a class="nav-item' + (item.secondary ? " nav-secondary" : "") + '" data-nav="' + item.id + '" href="#/' + item.id + '">' + icon(item.icon) + '<span>' + item.label + '</span></a>';
            }).join("") +
            '<button class="nav-item nav-more" id="nav-more" type="button" aria-expanded="false" aria-controls="more-sheet" aria-haspopup="true">' +
              icon("more") + '<span>More</span>' +
            '</button>' +
          '</nav>' +
          '<div class="sidebar-foot">' +
            '<div class="user-chip">' +
              avatarHtml(user) +
              '<span class="who"><strong>' + esc(user.name) + '</strong><span>' + esc(user.email) + '</span></span>' +
            '</div>' +
            '<div class="sidebar-note">A quiet record of good coffee.</div>' +
          '</div>' +
        '</aside>' +
        '<main class="main">' +
          '<div class="main-inner">' +
            '<header class="topbar">' +
              '<div><p class="eyebrow" id="page-eyebrow"></p><h1 class="page-title serif" id="page-title"></h1></div>' +
              '<div class="topbar-actions" id="topbar-actions"></div>' +
            '</header>' +
            '<div class="offline-banner" id="offline-banner" hidden><span class="dot"></span>' +
              '<span class="ob-copy"><strong>Offline</strong> — showing your last synced journal. New shots are kept on this device and upload when you reconnect.</span>' +
              '<button class="btn btn-quiet btn-sm" id="offline-retry" type="button">Try again</button></div>' +
            '<div class="offline-banner queue-banner" id="queue-banner" hidden><span class="dot"></span>' +
              '<span class="ob-copy" id="queue-copy"></span>' +
              '<button class="btn btn-quiet btn-sm" id="queue-upload" type="button">Upload now</button></div>' +
            '<div class="view" id="view" tabindex="-1"></div>' +
          '</div>' +
        '</main>' +
      '</div>' +
      '<div class="more-backdrop" id="more-backdrop" hidden></div>' +
      '<div class="more-sheet" id="more-sheet" hidden role="dialog" aria-label="More sections">' +
        '<div class="more-sheet-head"><span>More</span>' +
          '<button class="more-close" id="more-close" type="button" aria-label="Close menu">' + icon("x") + '</button>' +
        '</div>' +
        '<div class="more-sheet-links">' +
          NAV.filter(function (item) { return item.secondary; }).map(function (item) {
            return '<a class="more-link" data-nav="' + item.id + '" href="#/' + item.id + '">' +
              icon(item.icon) + '<span>' + item.label + '</span></a>';
          }).join("") +
        '</div>' +
      '</div>';

    $$("[data-nav]").forEach(function (link) {
      link.addEventListener("click", function () { closeModal(); });
    });

    var moreButton = $("#nav-more");
    if (moreButton) {
      moreButton.addEventListener("click", function (event) {
        event.stopPropagation();
        setMoreMenu($("#more-sheet").hidden);
      });
    }
    var moreBackdrop = $("#more-backdrop");
    if (moreBackdrop) moreBackdrop.addEventListener("click", function () { setMoreMenu(false); });
    var moreClose = $("#more-close");
    if (moreClose) moreClose.addEventListener("click", function () { setMoreMenu(false); });
    $$(".more-link").forEach(function (link) {
      link.addEventListener("click", function () { setMoreMenu(false); });
    });
    var moreSheet = $("#more-sheet");
    if (moreSheet) moreSheet.addEventListener("keydown", function (event) {
      if (event.key === "Escape") setMoreMenu(false);
    });

    var skip = $("#skip-link");
    if (skip) {
      skip.addEventListener("click", function (event) {
        event.preventDefault();
        var view = $("#view");
        if (view) view.focus();
      });
    }

    var retry = $("#offline-retry");
    if (retry) {
      retry.addEventListener("click", async function () {
        busy(retry, true, "Checking…");
        await probeConnection(false);
        busy(retry, false);
      });
    }

    var upload = $("#queue-upload");
    if (upload) {
      upload.addEventListener("click", async function () {
        busy(upload, true, "Uploading…");
        var sent = await flushQueue(false);
        busy(upload, false);
        if (!sent && state.pending.length) toast("Still can’t reach Crema", "error");
      });
    }

    setOfflineNotice(state.offline);
    paintQueueBanner();
  }

  function setActiveNav(name) {
    $$("[data-nav]").forEach(function (link) {
      var active = link.dataset.nav === name;
      link.classList.toggle("active", active);
      if (active) link.setAttribute("aria-current", "page");
      else link.removeAttribute("aria-current");
    });
    var more = $("#nav-more");
    var secondary = NAV.some(function (item) { return item.secondary && item.id === name; });
    if (more) {
      more.classList.toggle("active", secondary);
      if (secondary) more.setAttribute("aria-current", "page");
      else more.removeAttribute("aria-current");
    }
  }

  function setMoreMenu(open) {
    var button = $("#nav-more");
    var sheet = $("#more-sheet");
    var backdrop = $("#more-backdrop");
    if (!button || !sheet || !backdrop) return;
    button.setAttribute("aria-expanded", open ? "true" : "false");
    sheet.hidden = !open;
    backdrop.hidden = !open;
    document.body.classList.toggle("more-open", open);
    if (open) {
      var first = $(".more-link", sheet);
      if (first) first.focus();
    } else if (sheet.contains(document.activeElement)) {
      button.focus();
    }
  }

  // ------------------------------------------------------------ routing

  function parseHash() {
    var raw = (location.hash || "").replace(/^#\/?/, "");
    var parts = raw.split("/");
    return { name: parts[0] || "dashboard", id: parts[1] || null };
  }

  function route() {
    if (!state.user) {
      renderAuth(state.authMode);
      return;
    }
    if (typeof draftFlush === "function") {
      try { draftFlush(); } catch (e) { /* ignore */ }
      draftFlush = null;
    }
    if (!$("#view")) renderShell();
    setMoreMenu(false);

    var parsed = parseHash();
    if (!TITLES[parsed.name]) parsed.name = "dashboard";
    state.route = parsed;

    var meta = TITLES[parsed.name];
    $("#page-eyebrow").textContent = meta[0];
    $("#page-title").textContent = meta[1];
    setActiveNav(parsed.name);

    var actions = $("#topbar-actions");
    actions.innerHTML = parsed.name === "log" || parsed.name === "cafe"
      ? '<button class="btn btn-quiet" id="topbar-cancel">Cancel</button>'
      : '<a class="btn btn-primary topbar-cta" href="#/log">' + icon("plus") + 'Log a shot</a>';
    var cancel = $("#topbar-cancel");
    if (cancel) cancel.addEventListener("click", function () {
      if (state.route.name === "log") {
        clearDraft();
        draftFlush = null;
      }
      location.hash = "#/history";
    });

    $("#view").innerHTML = '<div class="loading"><div><div class="spinner"></div>Loading your journal…</div></div>';

    Promise.resolve()
      .then(function () {
        if (parsed.name === "dashboard") return viewDashboard();
        if (parsed.name === "log") return viewLog(parsed.id);
        if (parsed.name === "cafe") return viewCafe(parsed.id);
        if (parsed.name === "history") return viewHistory(parsed.id);
        if (parsed.name === "beans") return viewBeans();
        if (parsed.name === "calculator") return viewCalculator();
        return viewSettings();
      })
      .catch(function (err) {
        if (err && err.status === 401) {
          state.user = null;
          renderAuth("signin", "Your session has ended. Please sign in again.");
        } else {
          $("#view").innerHTML = '<div class="card empty"><div class="mark">' + icon("cup") + '</div><h3>Something went wrong</h3><p>' + esc(err.message || "Please try again.") + '</p><button class="btn btn-ghost" id="retry">Retry</button></div>';
          var retry = $("#retry");
          if (retry) retry.addEventListener("click", route);
        }
      });
  }

  // ------------------------------------------------------------ dashboard

  function greeting() {
    var hour = new Date().getHours();
    if (hour < 12) return "Good morning";
    if (hour < 18) return "Good afternoon";
    return "Good evening";
  }

  function viewDashboard() {
    var stats = state.stats || {};
    var total = stats.total_shots || 0;
    var last = state.shots[0];
    var first = (state.user.name || "").split(" ")[0];
    var avg = stats.avg_rating;

    var heroCopy;
    if (last && last.is_cafe) {
      heroCopy = "Last out: " + esc(titleCase(last.method)) +
        (last.drink_name ? " — " + esc(last.drink_name) : "") +
        (last.cafe_name ? " at " + esc(last.cafe_name) : "") + ". " +
        (last.rating ? "You rated it " + last.rating + " of 5." : "How was it?");
    } else if (last) {
      heroCopy = esc(titleCase(last.method)) + (last.bean_name ? " with " + esc(last.bean_name) : "") +
        " — " + grams(last.dose_g) + " in, " + grams(last.yield_g) + " out" +
        (last.time_s ? " in " + shotTime(last.time_s) : "") + ". " +
        (last.rating ? "You rated it " + last.rating + " of 5." : "How did it taste?");
    } else {
      heroCopy = "Log your first shot and Crema will start keeping track of the recipes, beans, and cups worth coming back to.";
    }

    var tiles = [
      { label: "Shots logged", value: total, meta: (stats.week_shots || 0) + " in the last seven days" + (stats.cafe_shots ? " · " + stats.cafe_shots + " café " + (stats.cafe_shots === 1 ? "visit" : "visits") : "") },
      { label: "Average score", value: avg ? Number(avg).toFixed(1) : "—", suffix: avg ? "/ 5" : "", meta: avg ? "across your rated shots" : "rate a shot to see this" },
      { label: "Beans in the cellar", value: stats.bean_count || 0, meta: (stats.favorite_bean ? "Most brewed: " + stats.favorite_bean.name : "Add a bag to get started") },
      { label: "Typical espresso", value: stats.avg_dose ? num(stats.avg_dose, 1) + "g" : "—", meta: stats.avg_yield ? "→ " + num(stats.avg_yield, 1) + "g" + (stats.avg_time ? " · " + shotTime(stats.avg_time) : "") : "dose and yield will appear here" }
    ];

    var max = 1;
    (stats.series || []).forEach(function (point) { if (point.count > max) max = point.count; });
    var todayKey = new Date().toISOString().slice(0, 10);

    var chart = (stats.series || []).map(function (point) {
      var isToday = point.date === todayKey;
      var height = point.count === 0 ? 3 : Math.max(6, Math.round((point.count / max) * 100));
      var date = new Date(point.date + "T12:00:00");
      return '<div class="chart-col' + (isToday ? " is-today" : "") + '" title="' + point.count + ' shot' + (point.count === 1 ? "" : "s") + '">' +
        '<div class="chart-bar" style="height:' + height + '%"></div>' +
        '<div class="chart-day">' + date.getDate() + '</div>' +
      '</div>';
    }).join("");

    var tagCloud = (stats.top_tags || []).length
      ? stats.top_tags.map(function (t) { return '<span class="pill">' + esc(t.tag) + '<b>' + t.count + '</b></span>'; }).join("")
      : '<p class="small muted">Flavour tags will collect here as you log shots.</p>';

    var recent = state.shots.slice(0, 5);

    // The bag that will go stale first, among those with something left in it.
    var bag = state.beans.filter(function (b) {
      return !b.archived && b.bag_size_g && (b.shots_left === null || b.shots_left === undefined || b.shots_left > 0);
    }).sort(function (a, b) {
      var ageA = daysSince(a.roast_date);
      var ageB = daysSince(b.roast_date);
      if (ageA === null && ageB === null) return (a.shots_left || 0) - (b.shots_left || 0);
      if (ageA === null) return 1;
      if (ageB === null) return -1;
      return ageB - ageA;
    })[0];

    var bagCard = "";
    if (bag) {
      var bagAge = daysSince(bag.roast_date);
      var bagBits = [];
      if (bag.roaster) bagBits.push(bag.roaster);
      if (bagAge !== null) bagBits.push(bagAge === 0 ? "roasted today" : bagAge + " days off roast");
      bagBits.push(num(bag.remaining_g, 0) + "g left" + (bag.shots_left ? " · about " + bag.shots_left + " shots" : ""));
      bagCard = '<a class="card card-pad bag-first" href="#/beans">' +
        '<div>' +
          '<p class="eyebrow">Drink this one first</p>' +
          '<h3>' + esc(bag.name) + '</h3>' +
          '<p class="small muted">' + esc(bagBits.join(" · ")) + '</p>' +
        '</div>' +
        '<span class="pill olive">' + (bagAge !== null && bagAge > 21 ? "Past its peak" : "Open bag") + '</span>' +
      '</a>';
    }

    $("#view").innerHTML =
      '<section class="hero">' +
        '<div class="hero-rings" aria-hidden="true"><span></span><span></span><span></span><span></span></div>' +
        '<div>' +
          '<p class="eyebrow">' + new Date().toLocaleDateString(undefined, { weekday: "long", day: "numeric", month: "long" }) + '</p>' +
          '<h2>' + greeting() + ', ' + esc(first) + '.</h2>' +
          '<p>' + heroCopy + '</p>' +
        '</div>' +
        '<a class="btn btn-primary btn-lg" href="#/log">' + icon("plus") + 'Log a shot</a>' +
      '</section>' +

      installBannerHtml() +

      '<div class="stat-grid" style="margin-bottom:20px">' +
        tiles.map(function (tile) {
          return '<div class="stat"><div class="label">' + tile.label + '</div>' +
            '<div class="value">' + esc(tile.value) + (tile.suffix ? ' <small>' + tile.suffix + '</small>' : "") + '</div>' +
            '<div class="meta">' + esc(tile.meta) + '</div></div>';
        }).join("") +
      '</div>' +

      bagCard +

      '<div class="split" style="margin-bottom:20px">' +
        '<section class="card card-pad">' +
          '<div class="card-head"><div><h3>Last two weeks</h3><p>A quiet measure of your habit.</p></div>' +
            '<span class="pill line">' + (stats.week_shots || 0) + ' this week</span></div>' +
          '<div class="chart">' + chart + '</div>' +
        '</section>' +
        '<section class="card card-pad">' +
          '<div class="card-head"><div><h3>At a glance</h3><p>The notes that keep returning.</p></div></div>' +
          '<div class="tag-cloud">' + tagCloud + '</div>' +
          '<div class="divider"></div>' +
          '<div class="avg-recipe">' +
            '<div><div class="k">Dose</div><div class="v">' + (stats.avg_dose ? num(stats.avg_dose, 1) + "g" : "—") + '</div></div>' +
            '<div><div class="k">Yield</div><div class="v">' + (stats.avg_yield ? num(stats.avg_yield, 1) + "g" : "—") + '</div></div>' +
            '<div><div class="k">Time</div><div class="v">' + (stats.avg_time ? shotTime(stats.avg_time) : "—") + '</div></div>' +
          '</div>' +
        '</section>' +
      '</div>' +

      '<section class="card card-pad">' +
        '<div class="card-head"><div><h3>Recent shots</h3><p>Where you left off.</p></div>' +
          '<a class="btn btn-quiet btn-sm" href="#/history">View all</a></div>' +
        (recent.length ? '<div class="recent-list">' + recent.map(recentRow).join("") + '</div>' :
          '<div class="empty" style="padding:30px 10px"><div class="mark">' + icon("cup") + '</div><h3>Nothing logged yet</h3><p>Your first entry is the beginning of a useful record.</p><a class="btn btn-primary" href="#/log">Log your first shot</a></div>') +
      '</section>';

    $$(".recent-row").forEach(function (row) {
      row.addEventListener("click", function () { location.hash = "#/history/" + row.dataset.id; });
    });

    $$(".recent-row [data-photo]").forEach(function (button) {
      button.addEventListener("click", function (event) {
        event.stopPropagation();
        openPhoto(button.dataset.photo, "Shot photo");
      });
    });

    var bannerInstall = $("#banner-install");
    if (bannerInstall) bannerInstall.addEventListener("click", promptInstall);
    var bannerDismiss = $("#banner-dismiss");
    if (bannerDismiss) {
      bannerDismiss.addEventListener("click", function () {
        try { localStorage.setItem("crema.install-dismissed", "1"); } catch (e) { /* ignore */ }
        var banner = $("#install-banner");
        if (banner) banner.remove();
      });
    }
  }

  function recentRow(shot) {
    var meta = [titleCase(shot.method)];
    if (shot.is_cafe && shot.drink_name) meta.push(shot.drink_name);
    if (shot.dose_g || shot.yield_g) meta.push(grams(shot.dose_g) + " → " + grams(shot.yield_g));
    if (shot.time_s) meta.push(shotTime(shot.time_s));
    var name = shot.is_cafe
      ? (shot.cafe_name || "Out for coffee")
      : (shot.bean_name || "No bean recorded");
    return '<div class="recent-row" data-id="' + shot.id + '">' +
      '<div class="when">' + esc(relDay(shot.brewed_at)) + '</div>' +
      (shot.photo ? '<button type="button" class="recent-thumb" data-photo="' + esc(shot.photo.url) + '" aria-label="View photo"><img src="' + esc(shot.photo.thumb_url) + '" alt="" loading="lazy"></button>' : "") +
      '<div class="what"><strong>' + esc(name) + '</strong><span>' + esc(meta.join(" · ")) + '</span></div>' +
      '<div class="rating">' + stars(shot.rating) + '</div>' +
    '</div>';
  }

  // ------------------------------------------------------------ log / edit

  function beanOptions(selected) {
    if (!state.beans.length) return '<option value="">No beans yet — add one</option>';
    return '<option value="">No bean</option>' + state.beans.filter(function (b) { return !b.archived || String(b.id) === String(selected); }).map(function (b) {
      return '<option value="' + b.id + '"' + (String(b.id) === String(selected) ? " selected" : "") + '>' +
        esc(b.name) + (b.roaster ? " · " + esc(b.roaster) : "") + '</option>';
    }).join("");
  }

  // Shared by the shot form and the café form. Both pages use the same photo
  // field ids, so the uploader only has to live in one place.
  function mountPhotoField(photoState) {
    var preview = $("#photo-preview");
    var add = $("#photo-add");
    var img = $("#photo-img");
    var input = $("#photo-input");
    var remove = $("#photo-remove");
    if (!preview || !add || !img || !input || !remove) return;

    function paintPhoto() {
      var src = photoState.full || (photoState.existing && !photoState.removed ? photoState.existing.thumb_url : "");
      if (src) {
        img.src = src;
        preview.hidden = false;
        add.hidden = true;
      } else {
        img.removeAttribute("src");
        preview.hidden = true;
        add.hidden = false;
      }
    }
    paintPhoto();

    input.addEventListener("change", async function (event) {
      var file = event.target.files && event.target.files[0];
      if (!file) return;
      add.classList.add("working");
      try {
        var prepared = await compressPhoto(file);
        photoState.full = prepared.full;
        photoState.thumb = prepared.thumb;
        photoState.width = prepared.width;
        photoState.height = prepared.height;
        photoState.removed = false;
        paintPhoto();
        haptic();
      } catch (err) {
        toast(err.message, "error");
        event.target.value = "";
      } finally {
        add.classList.remove("working");
      }
    });

    remove.addEventListener("click", function () {
      photoState.full = null;
      photoState.thumb = null;
      photoState.width = null;
      photoState.height = null;
      photoState.removed = Boolean(photoState.existing);
      input.value = "";
      paintPhoto();
    });

    img.addEventListener("click", function () {
      if (photoState.full) openPhoto(photoState.full, "Photo for this entry");
      else if (photoState.existing && !photoState.removed) openPhoto(photoState.existing.url, "Photo for this entry");
    });
  }

  function mountRating(initial) {
    var rating = initial || 0;
    var label = $("#rating-label");
    function paintStars() {
      $$("#rating-input button").forEach(function (btn) {
        btn.classList.toggle("on", Number(btn.dataset.star) <= rating);
      });
      if (label) label.textContent = rating ? rating + " of 5" : "Not rated yet";
    }
    $$("#rating-input button").forEach(function (btn) {
      btn.addEventListener("click", function () {
        var value = Number(btn.dataset.star);
        rating = rating === value ? 0 : value;
        paintStars();
      });
    });
    paintStars();
    return { value: function () { return rating; } };
  }

  async function viewLog(id) {
    var shot = null;
    if (id) {
      shot = state.shots.filter(function (s) { return String(s.id) === String(id); })[0];
      if (!shot) {
        shot = (await api("/api/shots/" + id)).shot;
      }
    }
    // Café visits have their own page, with none of the espresso fields.
    if (shot && shot.is_cafe) {
      location.replace("#/cafe/" + shot.id);
      return;
    }

    var prefs = state.user.preferences || {};
    var draft = !shot ? readDraft() : null;
    var source = draft || shot;
    var isMilk = source ? MILK_METHODS.indexOf(source.method) !== -1 : false;
    var chosenTags = source && source.flavor_tags ? source.flavor_tags.slice() : [];
    var tagList = TAGS.slice();
    chosenTags.forEach(function (tag) { if (tagList.indexOf(tag) === -1) tagList.push(tag); });

    // A saved style supplies the timer target and, for a fresh shot, the
    // starting dose and yield. Explicit defaults still win.
    var chosenStyle = styleById(prefs.espresso_style);

    var values = {
      dose: source ? source.dose_g : (prefs.dose_g !== null && prefs.dose_g !== undefined && prefs.dose_g !== "" ? prefs.dose_g : (chosenStyle ? chosenStyle.dose : null)),
      yield: source ? source.yield_g : (prefs.yield_g !== null && prefs.yield_g !== undefined && prefs.yield_g !== "" ? prefs.yield_g : (chosenStyle ? chosenStyle.yield : null)),
      time: source ? source.time_s : null,
      grind: source ? source.grind : "",
      temp: source ? source.temp_c : prefs.temp_c,
      pressure: source ? source.pressure_bar : null,
      preinfusion: source ? source.preinfusion_s : null,
      tds: source ? source.tds : null,
      ey: source ? source.ey : null,
      milk_type: source ? source.milk_type : (prefs.milk_type || ""),
      milk_volume: source ? source.milk_volume_ml : null,
      machine: source ? source.machine : (prefs.machine || ""),
      grinder: source ? source.grinder : (prefs.grinder || ""),
      basket: source ? source.basket : (prefs.basket || ""),
      tasting: source ? source.tasting_notes : "",
      notes: source ? source.notes : "",
      bean_id: source ? source.bean_id : "",
      brewed_at: source ? source.brewed_at : new Date().toISOString()
    };

    var photoState = {
      existing: shot && shot.photo ? shot.photo : null,
      full: null,
      thumb: null,
      width: null,
      height: null,
      removed: false
    };

    $("#view").innerHTML =
      (!shot ? '<a class="cafe-invite" href="#/cafe">' +
        '<span class="cafe-invite-icon">' + icon("cafe") + '</span>' +
        '<span class="cafe-invite-copy"><strong>Out for coffee?</strong><span>Log a café visit — just the place, the drink, and how it tasted.</span></span>' +
        '<span class="cafe-invite-go">' + icon("chevron") + '</span>' +
      '</a>' : "") +
      '<form id="shot-form" novalidate>' +
        '<div class="log-grid">' +
          '<div class="section-stack">' +
            '<section class="form-card card timer-card" id="timer-card">' +
              '<div class="timer-head">' +
                '<div><h3>Brew timer</h3><p class="sub">Start it as the pump kicks in.</p></div>' +
                '<label class="timer-target" for="timer-target">Target <input type="text" inputmode="decimal" id="timer-target" value="' + (chosenStyle ? chosenStyle.time : 27) + '" aria-label="Target shot time in seconds"> s</label>' +
              '</div>' +
              '<div class="seg timer-styles" id="style-seg" role="group" aria-label="Espresso style">' +
                ESPRESSO_STYLES.map(function (style) {
                  var active = chosenStyle && chosenStyle.id === style.id;
                  return '<button type="button" class="' + (active ? "active" : "") + '" data-style="' + esc(style.id) + '">' + esc(style.label) + '</button>';
                }).join("") +
              '</div>' +
              '<p class="timer-preset" id="timer-preset">' + esc(styleRecipe(chosenStyle)) + '</p>' +
              '<div class="timer-display" id="timer-display">0:00.0</div>' +
              '<div class="timer-controls">' +
                '<button type="button" class="btn btn-primary timer-btn" id="timer-toggle">' + icon("play") + '<span>Start</span></button>' +
                '<button type="button" class="btn btn-quiet" id="timer-reset">Reset</button>' +
              '</div>' +
              '<div class="dialin" id="dialin" hidden>' +
                '<div class="dialin-head"><strong>Dial-in notes</strong>' +
                  '<button type="button" class="btn btn-quiet btn-sm" id="dialin-copy">Add to notes</button>' +
                '</div>' +
                '<ul id="dialin-list"></ul>' +
              '</div>' +
            '</section>' +

            '<section class="form-card card">' +
              '<h3>Photo</h3><p class="sub">A picture of the shot, the bag, or the moment.</p>' +
              '<div class="photo-field">' +
                '<div class="photo-preview" id="photo-preview" hidden>' +
                  '<img id="photo-img" alt="Photo for this shot">' +
                  '<button type="button" class="photo-remove" id="photo-remove" aria-label="Remove photo">' + icon("x") + '</button>' +
                '</div>' +
                '<label class="photo-add" id="photo-add" for="photo-input">' +
                  '<span class="photo-add-icon">' + icon("camera") + '</span>' +
                  '<strong>Add a photo</strong>' +
                  '<span>Take one now, or choose from your library.</span>' +
                '</label>' +
                '<input type="file" id="photo-input" accept="image/*" hidden>' +
              '</div>' +
            '</section>' +

            '<section class="form-card card">' +
              '<h3>The coffee</h3><p class="sub">What went into the cup.</p>' +
              '<div class="field" style="margin-bottom:14px">' +
                '<span class="field-label">Brew method</span>' +
                '<div class="seg" id="method-seg">' +
                  METHODS.map(function (m) {
                    var active = (source && source.method ? source.method : "espresso") === m;
                    return '<button type="button" class="' + (active ? "active" : "") + '" data-method="' + esc(m) + '">' + esc(titleCase(m)) + '</button>';
                  }).join("") +
                '</div>' +
              '</div>' +
              '<div class="form-grid">' +
                '<div class="field span-2">' +
                  '<label for="bean_id">Bean</label>' +
                  '<div style="display:flex;gap:8px">' +
                    '<select id="bean_id" name="bean_id" style="flex:1">' + beanOptions(values.bean_id) + '</select>' +
                    '<button type="button" class="btn btn-ghost" id="quick-bean">' + icon("plus") + 'New</button>' +
                  '</div>' +
                '</div>' +
                '<div class="field"><label for="brewed_at">When</label><input type="datetime-local" id="brewed_at" name="brewed_at" value="' + toLocalInput(values.brewed_at) + '"></div>' +
                '<div class="field" style="justify-content:flex-end"><label class="sr-only">Favourite</label>' +
                  '<div class="toggle-row" style="border:0;padding:0">' +
                    '<div><div class="t">A favourite</div><div class="d">Keep it close</div></div>' +
                    '<span class="switch"><input type="checkbox" name="favorite"' + (source && source.favorite ? " checked" : "") + '><span class="track"></span></span>' +
                  '</div>' +
                '</div>' +
              '</div>' +
            '</section>' +

            '<section class="form-card card">' +
              '<h3>Recipe</h3><p class="sub">The numbers you would want to repeat.</p>' +
              '<div class="form-grid">' +
                field("dose_g", "Dose", values.dose, "g", "0.1") +
                field("yield_g", "Yield", values.yield, "g", "0.1") +
                field("time_s", "Shot time", values.time, "s", "0.1") +
                field("grind", "Grind setting", values.grind, "", null) +
                field("temp_c", "Temperature", values.temp, "°C", "0.1") +
                field("pressure_bar", "Pressure", values.pressure, "bar", "0.1") +
                field("preinfusion_s", "Pre-infusion", values.preinfusion, "s", "0.1") +
                field("tds", "TDS", values.tds, "%", "0.01") +
                field("ey", "Extraction yield", values.ey, "%", "0.1") +
              '</div>' +
              '<div class="ratio-readout">' +
                '<div><div class="num" id="ratio-out">—</div><div class="lbl">brew ratio</div></div>' +
                '<div class="spacer"></div>' +
                '<div class="flow"><strong id="flow-out">—</strong><span>grams per second</span></div>' +
              '</div>' +
            '</section>' +

            '<section class="form-card card" id="milk-card"' + (isMilk ? "" : ' hidden') + '>' +
              '<h3>Milk</h3><p class="sub">For the drinks that need it.</p>' +
              '<div class="form-grid">' +
                '<div class="field"><label for="milk_type">Milk</label>' +
                  '<select id="milk_type" name="milk_type">' +
                    ["", "Whole milk", "Semi-skimmed", "Oat", "Almond", "Soy", "Coconut", "Lactose-free", "Other"].map(function (m) {
                      return '<option value="' + esc(m) + '"' + (values.milk_type === m ? " selected" : "") + '>' + (m ? esc(m) : "Not specified") + '</option>';
                    }).join("") +
                  '</select></div>' +
                field("milk_volume_ml", "Milk volume", values.milk_volume, "ml", "1") +
              '</div>' +
            '</section>' +

            '<section class="form-card card">' +
              '<h3>Tasting notes</h3><p class="sub">The part a recipe can’t tell you.</p>' +
              '<div class="field" style="margin-bottom:16px">' +
                '<span class="field-label">Flavour</span>' +
                '<div class="tag-picker" id="tag-picker">' +
                  tagList.map(function (tag) {
                    return '<button type="button" class="' + (chosenTags.indexOf(tag) !== -1 ? "on" : "") + '" data-tag="' + esc(tag) + '">' + esc(tag) + '</button>';
                  }).join("") +
                '</div>' +
              '</div>' +
              '<div class="field" style="margin-bottom:14px"><label for="tasting_notes">What did it taste like?</label>' +
                '<textarea id="tasting_notes" name="tasting_notes" placeholder="Bright citrus up front, a little caramel as it cooled…">' + esc(values.tasting) + '</textarea></div>' +
              '<div class="field"><label for="notes">Anything else</label>' +
                '<textarea id="notes" name="notes" placeholder="What you would change next time, or what worked.">' + esc(values.notes) + '</textarea></div>' +
            '</section>' +
          '</div>' +

          '<div class="section-stack">' +
            '<section class="form-card card">' +
              '<h3>Rating</h3><p class="sub">A quick honest score.</p>' +
              '<div class="rating-input" id="rating-input">' +
                [1, 2, 3, 4, 5].map(function (n) {
                  return '<button type="button" data-star="' + n + '" aria-label="' + n + ' star' + (n > 1 ? "s" : "") + '" class="' + (shot && shot.rating >= n ? "on" : "") + '">★</button>';
                }).join("") +
              '</div>' +
              '<p class="small muted" id="rating-label" style="margin-top:8px">' + (shot && shot.rating ? shot.rating + " of 5" : "Not rated yet") + '</p>' +
            '</section>' +

            '<section class="form-card card">' +
              '<h3>Balance</h3><p class="sub">Leave a slider at zero to skip it.</p>' +
              '<div class="section-stack" style="gap:10px">' +
                TASTE.map(function (pair) {
                  var value = source && source[pair[0]] ? source[pair[0]] : 0;
                  return '<div class="slider-row">' +
                    '<span class="name">' + pair[1] + '</span>' +
                    '<input type="range" min="0" max="5" step="1" value="' + value + '" data-taste="' + pair[0] + '" aria-label="' + pair[1] + '">' +
                    '<span class="val" data-taste-out="' + pair[0] + '">' + (value || "—") + '</span>' +
                  '</div>';
                }).join("") +
              '</div>' +
            '</section>' +

            '<section class="form-card card" id="gear-card">' +
              '<h3>Gear</h3><p class="sub">Filled in from your defaults.</p>' +
              '<div class="form-grid">' +
                field("machine", "Machine", values.machine, "", null) +
                field("grinder", "Grinder", values.grinder, "", null) +
                field("basket", "Basket", values.basket, "", null) +
              '</div>' +
            '</section>' +
          '</div>' +
        '</div>' +

        '<div class="form-actions">' +
          '<span class="hint">' + (shot ? "Editing your entry from " + esc(fmtDateTime(shot.brewed_at)) : "You can come back and edit any detail later.") + '</span>' +
          '<button class="btn btn-primary btn-lg" type="submit" id="save-shot">' + (shot ? "Save changes" : "Save shot") + '</button>' +
        '</div>' +
      '</form>';

    // segmented method
    var method = source && source.method ? source.method : "espresso";
    $$("#method-seg button").forEach(function (btn) {
      btn.addEventListener("click", function () {
        method = btn.dataset.method;
        $$("#method-seg button").forEach(function (b) { b.classList.toggle("active", b === btn); });
        var milkCard = $("#milk-card");
        if (milkCard) milkCard.hidden = MILK_METHODS.indexOf(method) === -1;
        paintDialIn();
      });
    });

    // espresso style — sets the timer target and the starting recipe
    var activeStyle = chosenStyle ? chosenStyle.id : "";

    $$("#style-seg button").forEach(function (btn) {
      btn.addEventListener("click", function () {
        var style = styleById(btn.dataset.style);
        activeStyle = style ? style.id : "";
        $$("#style-seg button").forEach(function (b) { b.classList.toggle("active", b === btn); });
        if (style) {
          $("#timer-target").value = style.time;
          $("#dose_g").value = style.dose;
          $("#yield_g").value = style.yield;
        }
        $("#timer-preset").textContent = styleRecipe(style);
        updateReadout();
        paintTimer();
      });
    });

    // live ratio / flow
    function updateReadout() {
      var dose = parseFloat($("#dose_g").value);
      var yieldG = parseFloat($("#yield_g").value);
      var time = parseFloat($("#time_s").value);
      var ratioEl = $("#ratio-out");
      var flowEl = $("#flow-out");
      ratioEl.textContent = dose > 0 && yieldG > 0 ? (yieldG / dose >= 10 ? "1:" + Math.round(yieldG / dose) : "1:" + (yieldG / dose).toFixed(1)) : "—";
      flowEl.textContent = yieldG > 0 && time > 0 ? (yieldG / time).toFixed(1) : "—";
      paintDialIn();
    }
    ["dose_g", "yield_g", "time_s"].forEach(function (id) {
      var input = $("#" + id);
      if (input) input.addEventListener("input", updateReadout);
    });

    function paintDialIn() {
      var panel = $("#dialin");
      var list = $("#dialin-list");
      if (!panel || !list) return;
      var notes = dialInNotes($("#dose_g").value, $("#yield_g").value, $("#time_s").value, method, activeStyle);
      panel.hidden = !notes.length;
      list.innerHTML = notes.map(function (note) {
        return '<li class="' + esc(note.kind || "tip") + '">' + esc(note.text) + '</li>';
      }).join("");
    }

    // brew timer — counts up, writes the elapsed time into the shot time field
    var timerDisplay = $("#timer-display");
    var timerToggle = $("#timer-toggle");
    var timerTarget = $("#timer-target");
    var timerState = { running: false, startedAt: 0, elapsed: 0, frame: 0 };

    function formatElapsed(ms) {
      var total = ms / 1000;
      var minutes = Math.floor(total / 60);
      var seconds = total - minutes * 60;
      return minutes + ":" + (seconds < 10 ? "0" : "") + seconds.toFixed(1);
    }

    function paintTimer() {
      var ms = timerState.running ? timerState.elapsed + (performance.now() - timerState.startedAt) : timerState.elapsed;
      timerDisplay.textContent = formatElapsed(ms);
      var target = parseFloat(timerTarget.value);
      timerDisplay.classList.toggle("over", target > 0 && ms / 1000 > target);
      return ms;
    }

    function timerTick() {
      if (!timerState.running) return;
      paintTimer();
      timerState.frame = requestAnimationFrame(timerTick);
    }

    function setTimerIdle() {
      timerToggle.classList.remove("running");
      timerToggle.innerHTML = icon("play") + "<span>Start</span>";
    }

    timerToggle.addEventListener("click", function () {
      if (timerState.running) {
        timerState.elapsed += performance.now() - timerState.startedAt;
        timerState.running = false;
        cancelAnimationFrame(timerState.frame);
        setTimerIdle();
        paintTimer();
        var seconds = timerState.elapsed / 1000;
        if (seconds >= 0.5) {
          $("#time_s").value = seconds.toFixed(1);
          $("#time_s").dispatchEvent(new Event("input", { bubbles: true }));
          haptic();
        }
      } else {
        timerState.startedAt = performance.now();
        timerState.running = true;
        timerToggle.classList.add("running");
        timerToggle.innerHTML = icon("stop") + "<span>Stop</span>";
        timerTick();
      }
    });

    $("#timer-reset").addEventListener("click", function () {
      timerState.running = false;
      cancelAnimationFrame(timerState.frame);
      timerState.elapsed = 0;
      setTimerIdle();
      paintTimer();
    });

    $("#dialin-copy").addEventListener("click", function () {
      var notesEl = $("#notes");
      var lines = $$("#dialin-list li").map(function (li) { return "• " + li.textContent; }).join("\n");
      if (!lines) return;
      notesEl.value = (notesEl.value ? notesEl.value.replace(/\s*$/, "") + "\n" : "") + lines;
      notesEl.dispatchEvent(new Event("input", { bubbles: true }));
      toast("Notes added");
    });

    paintTimer();
    updateReadout();

    // tags
    $$("#tag-picker button").forEach(function (btn) {
      btn.addEventListener("click", function () { btn.classList.toggle("on"); });
    });

    // rating
    var ratingState = mountRating(source && source.rating ? Number(source.rating) : 0);

    // taste sliders
    $$("[data-taste]").forEach(function (slider) {
      slider.addEventListener("input", function () {
        var out = $('[data-taste-out="' + slider.dataset.taste + '"]');
        if (out) out.textContent = Number(slider.value) || "—";
      });
    });

    // quick bean
    $("#quick-bean").addEventListener("click", function () {
      openBeanModal(null, async function (bean) {
        await refreshBeans();
        var select = $("#bean_id");
        select.innerHTML = beanOptions(bean.id);
      });
    });

    // photo
    mountPhotoField(photoState);

    // save
    var form = $("#shot-form");

    function draftSnapshot() {
      var draftValues = {
        method: method,
        bean_id: form.bean_id ? form.bean_id.value : "",
        dose_g: form.dose_g ? form.dose_g.value || null : null,
        yield_g: form.yield_g ? form.yield_g.value || null : null,
        time_s: form.time_s ? form.time_s.value || null : null,
        grind: form.grind ? form.grind.value : "",
        temp_c: form.temp_c ? form.temp_c.value || null : null,
        pressure_bar: form.pressure_bar ? form.pressure_bar.value || null : null,
        preinfusion_s: form.preinfusion_s ? form.preinfusion_s.value || null : null,
        tds: form.tds ? form.tds.value || null : null,
        ey: form.ey ? form.ey.value || null : null,
        milk_type: form.milk_type ? form.milk_type.value : "",
        milk_volume_ml: form.milk_volume_ml ? form.milk_volume_ml.value || null : null,
        rating: ratingState.value() || null,
        flavor_tags: $$("#tag-picker button.on").map(function (b) { return b.dataset.tag; }),
        tasting_notes: form.tasting_notes.value,
        notes: form.notes.value,
        machine: form.machine.value,
        grinder: form.grinder.value,
        basket: form.basket.value,
        favorite: form.favorite.checked,
        brewed_at: fromLocalInput(form.brewed_at.value)
      };
      TASTE.forEach(function (pair) {
        var slider = $('[data-taste="' + pair[0] + '"]');
        draftValues[pair[0]] = slider && slider.value !== "0" ? slider.value : null;
      });
      return draftValues;
    }

    if (!shot) {
      var draftTimer = null;
      var persistDraft = function () { saveDraft(draftSnapshot()); };
      draftFlush = persistDraft;
      form.addEventListener("input", function () {
        clearTimeout(draftTimer);
        draftTimer = setTimeout(persistDraft, 500);
      });
      form.addEventListener("change", function () {
        clearTimeout(draftTimer);
        draftTimer = setTimeout(persistDraft, 250);
      });
    }

    form.addEventListener("submit", async function (event) {
      event.preventDefault();
      var payload = {
        method: method,
        bean_id: form.bean_id.value || null,
        dose_g: form.dose_g.value || null,
        yield_g: form.yield_g.value || null,
        time_s: form.time_s.value || null,
        grind: form.grind.value,
        temp_c: form.temp_c.value || null,
        pressure_bar: form.pressure_bar.value || null,
        preinfusion_s: form.preinfusion_s.value || null,
        tds: form.tds.value || null,
        ey: form.ey.value || null,
        milk_type: form.milk_type ? form.milk_type.value : "",
        milk_volume_ml: form.milk_volume_ml ? form.milk_volume_ml.value || null : null,
        rating: ratingState.value() || null,
        flavor_tags: $$("#tag-picker button.on").map(function (b) { return b.dataset.tag; }),
        tasting_notes: form.tasting_notes.value,
        notes: form.notes.value,
        machine: form.machine.value,
        grinder: form.grinder.value,
        basket: form.basket.value,
        favorite: form.favorite.checked,
        brewed_at: fromLocalInput(form.brewed_at.value)
      };
      TASTE.forEach(function (pair) {
        var slider = $('[data-taste="' + pair[0] + '"]');
        payload[pair[0]] = slider && slider.value !== "0" ? slider.value : null;
      });

      if (!shot) payload.client_id = newClientId();

      var button = $("#save-shot");
      busy(button, true, shot ? "Saving…" : "Adding…");
      var photoError = null;
      try {
        var result = await api(shot ? "/api/shots/" + shot.id : "/api/shots", {
          method: shot ? "PATCH" : "POST",
          body: payload
        });

        try {
          if (photoState.full) {
            busy(button, true, "Adding photo…");
            await api("/api/shots/" + result.shot.id + "/photo", {
              method: "POST",
              body: {
                full: photoState.full,
                thumb: photoState.thumb,
                width: photoState.width,
                height: photoState.height
              }
            });
          } else if (photoState.removed && photoState.existing) {
            await api("/api/shots/" + result.shot.id + "/photo", { method: "DELETE" });
          }
        } catch (photoErr) {
          photoError = photoErr;
        }

        clearDraft();
        draftFlush = null;
        await refreshAll();
        if (photoError) {
          toast("Entry saved, but the photo didn’t upload", "error");
        } else {
          toast(shot ? "Entry updated" : "Shot logged");
        }
        location.hash = "#/history/" + result.shot.id;
      } catch (err) {
        if (err.offline && !shot) {
          try {
            await enqueueShot(payload, photoState);
            clearDraft();
            draftFlush = null;
            toast("Saved on this device — it uploads when Crema is back");
            location.hash = "#/history";
            return;
          } catch (queueErr) {
            busy(button, false);
            toast("Couldn’t save that offline — " + queueErr.message, "error");
            return;
          }
        }
        busy(button, false);
        toast(err.message, "error");
      }
    });
  }

  // ------------------------------------------------------------ café log

  async function viewCafe(id) {
    var shot = null;
    if (id) {
      shot = state.shots.filter(function (s) { return String(s.id) === String(id); })[0];
      if (!shot) {
        shot = (await api("/api/shots/" + id)).shot;
      }
      if (shot && !shot.is_cafe) {
        location.replace("#/log/" + shot.id);
        return;
      }
    }

    var source = shot;
    var method = source && source.method ? source.method : "flat white";
    var chosenTags = source && source.flavor_tags ? source.flavor_tags.slice() : [];
    var tagList = TAGS.slice();
    chosenTags.forEach(function (tag) { if (tagList.indexOf(tag) === -1) tagList.push(tag); });

    var values = {
      cafe_name: source ? source.cafe_name || "" : "",
      drink_name: source ? source.drink_name || "" : "",
      tasting: source ? source.tasting_notes : "",
      notes: source ? source.notes : "",
      brewed_at: source ? source.brewed_at : new Date().toISOString()
    };

    var photoState = {
      existing: shot && shot.photo ? shot.photo : null,
      full: null,
      thumb: null,
      width: null,
      height: null,
      removed: false
    };

    $("#view").innerHTML =
      '<form id="cafe-form" class="cafe-page" novalidate>' +
        '<div class="log-grid">' +
          '<div class="section-stack">' +
            '<section class="form-card card">' +
              '<div class="cafe-visit-head">' +
                '<span class="cafe-stamp">' + icon("cafe") + '</span>' +
                '<div><h3>The visit</h3><p class="sub">Where you went, and what you ordered.</p></div>' +
              '</div>' +
              '<div class="form-grid">' +
                '<div class="field span-2">' +
                  '<label for="cafe_name">Where did you go?</label>' +
                  '<input id="cafe_name" name="cafe_name" placeholder="e.g. Prufrock, London" value="' + esc(values.cafe_name) + '">' +
                '</div>' +
                '<div class="field span-2">' +
                  '<label for="drink_name">What did you order?</label>' +
                  '<input id="drink_name" name="drink_name" placeholder="e.g. Oat flat white, extra hot" value="' + esc(values.drink_name) + '">' +
                '</div>' +
                '<div class="field span-2">' +
                  '<span class="field-label">Drink style</span>' +
                  '<div class="seg" id="cafe-method-seg">' +
                    METHODS.map(function (m) {
                      var active = method === m;
                      return '<button type="button" class="' + (active ? "active" : "") + '" data-method="' + esc(m) + '">' + esc(titleCase(m)) + '</button>';
                    }).join("") +
                  '</div>' +
                '</div>' +
                '<div class="field"><label for="brewed_at">When</label><input type="datetime-local" id="brewed_at" name="brewed_at" value="' + toLocalInput(values.brewed_at) + '"></div>' +
                '<div class="field" style="justify-content:flex-end"><label class="sr-only">Would go back</label>' +
                  '<div class="toggle-row" style="border:0;padding:0">' +
                    '<div><div class="t">Would go back</div><div class="d">A place worth returning to</div></div>' +
                    '<span class="switch"><input type="checkbox" name="favorite"' + (source && source.favorite ? " checked" : "") + '><span class="track"></span></span>' +
                  '</div>' +
                '</div>' +
              '</div>' +
            '</section>' +

            '<section class="form-card card">' +
              '<h3>Photo</h3><p class="sub">The café, the cup, or the moment.</p>' +
              '<div class="photo-field">' +
                '<div class="photo-preview" id="photo-preview" hidden>' +
                  '<img id="photo-img" alt="Photo from this café visit">' +
                  '<button type="button" class="photo-remove" id="photo-remove" aria-label="Remove photo">' + icon("x") + '</button>' +
                '</div>' +
                '<label class="photo-add" id="photo-add" for="photo-input">' +
                  '<span class="photo-add-icon">' + icon("camera") + '</span>' +
                  '<strong>Add a photo</strong>' +
                  '<span>Take one now, or choose from your library.</span>' +
                '</label>' +
                '<input type="file" id="photo-input" accept="image/*" hidden>' +
              '</div>' +
            '</section>' +

            '<section class="form-card card">' +
              '<h3>Tasting notes</h3><p class="sub">The part a menu can’t tell you.</p>' +
              '<div class="field" style="margin-bottom:16px">' +
                '<span class="field-label">Flavour</span>' +
                '<div class="tag-picker" id="tag-picker">' +
                  tagList.map(function (tag) {
                    return '<button type="button" class="' + (chosenTags.indexOf(tag) !== -1 ? "on" : "") + '" data-tag="' + esc(tag) + '">' + esc(tag) + '</button>';
                  }).join("") +
                '</div>' +
              '</div>' +
              '<div class="field" style="margin-bottom:14px"><label for="tasting_notes">How did it taste?</label>' +
                '<textarea id="tasting_notes" name="tasting_notes" placeholder="Silky milk, cocoa and a long finish…">' + esc(values.tasting) + '</textarea></div>' +
              '<div class="field"><label for="notes">Anything else</label>' +
                '<textarea id="notes" name="notes" placeholder="What to order next time, who you were with, the seat by the window…">' + esc(values.notes) + '</textarea></div>' +
            '</section>' +
          '</div>' +

          '<div class="section-stack">' +
            '<section class="form-card card">' +
              '<h3>Rating</h3><p class="sub">A quick honest score.</p>' +
              '<div class="rating-input" id="rating-input">' +
                [1, 2, 3, 4, 5].map(function (n) {
                  return '<button type="button" data-star="' + n + '" aria-label="' + n + ' star' + (n > 1 ? "s" : "") + '" class="' + (shot && shot.rating >= n ? "on" : "") + '">★</button>';
                }).join("") +
              '</div>' +
              '<p class="small muted" id="rating-label" style="margin-top:8px">' + (shot && shot.rating ? shot.rating + " of 5" : "Not rated yet") + '</p>' +
            '</section>' +

            '<section class="form-card card cafe-note">' +
              '<span class="cafe-note-icon">' + icon("bean") + '</span>' +
              '<h3>Kept out of the numbers</h3>' +
              '<p class="sub">A café visit stays in your journal, but it never moves your dial-in, brew ratios, or home statistics.</p>' +
            '</section>' +
          '</div>' +
        '</div>' +

        '<div class="form-actions">' +
          '<span class="hint">' + (shot ? "Editing your visit from " + esc(fmtDateTime(shot.brewed_at)) : "Jot it down while it’s fresh.") + '</span>' +
          '<button class="btn btn-primary btn-lg" type="submit" id="save-cafe">' + (shot ? "Save changes" : "Save café visit") + '</button>' +
        '</div>' +
      '</form>';

    $$("#cafe-method-seg button").forEach(function (btn) {
      btn.addEventListener("click", function () {
        method = btn.dataset.method;
        $$("#cafe-method-seg button").forEach(function (b) { b.classList.toggle("active", b === btn); });
      });
    });

    $$("#tag-picker button").forEach(function (btn) {
      btn.addEventListener("click", function () { btn.classList.toggle("on"); });
    });

    var ratingState = mountRating(shot && shot.rating ? Number(shot.rating) : 0);
    mountPhotoField(photoState);

    var form = $("#cafe-form");
    form.addEventListener("submit", async function (event) {
      event.preventDefault();
      var payload = {
        method: method,
        rating: ratingState.value() || null,
        flavor_tags: $$("#tag-picker button.on").map(function (b) { return b.dataset.tag; }),
        tasting_notes: form.tasting_notes.value,
        notes: form.notes.value,
        favorite: form.favorite.checked,
        is_cafe: true,
        cafe_name: form.cafe_name.value.trim(),
        drink_name: form.drink_name.value.trim(),
        brewed_at: fromLocalInput(form.brewed_at.value)
      };
      if (!shot) payload.client_id = newClientId();

      var button = $("#save-cafe");
      busy(button, true, shot ? "Saving…" : "Adding…");
      var photoError = null;
      try {
        var result = await api(shot ? "/api/shots/" + shot.id : "/api/shots", {
          method: shot ? "PATCH" : "POST",
          body: payload
        });

        try {
          if (photoState.full) {
            busy(button, true, "Adding photo…");
            await api("/api/shots/" + result.shot.id + "/photo", {
              method: "POST",
              body: {
                full: photoState.full,
                thumb: photoState.thumb,
                width: photoState.width,
                height: photoState.height
              }
            });
          } else if (photoState.removed && photoState.existing) {
            await api("/api/shots/" + result.shot.id + "/photo", { method: "DELETE" });
          }
        } catch (photoErr) {
          photoError = photoErr;
        }

        await refreshAll();
        if (photoError) {
          toast("Visit saved, but the photo didn’t upload", "error");
        } else {
          toast(shot ? "Café visit updated" : "Café visit logged");
        }
        location.hash = "#/history/" + result.shot.id;
      } catch (err) {
        if (err.offline && !shot) {
          try {
            await enqueueShot(payload, photoState);
            toast("Saved on this device — it uploads when Crema is back");
            location.hash = "#/history";
            return;
          } catch (queueErr) {
            busy(button, false);
            toast("Couldn’t save that offline — " + queueErr.message, "error");
            return;
          }
        }
        busy(button, false);
        toast(err.message, "error");
      }
    });
  }

  function field(name, label, value, unit, step, fieldName) {
    var attr = fieldName || name;
    var input = '<input type="text" inputmode="' + (unit ? "decimal" : "text") + '" id="' + name + '" name="' + attr + '"' +
      (value !== null && value !== undefined && value !== "" ? ' value="' + esc(value) + '"' : "") +
      (unit ? ' placeholder="' + unit + '"' : "") + '>';
    return '<div class="field"><label for="' + name + '">' + esc(label) + (unit ? " <span style=\"text-transform:none;letter-spacing:0;font-weight:400\">(" + unit + ")</span>" : "") + '</label>' + input + '</div>';
  }

  // ------------------------------------------------------------ history

  function filteredShots() {
    var q = state.historyQuery.trim().toLowerCase();
    return state.shots.filter(function (shot) {
      if (state.historyFavorite && !shot.favorite) return false;
      if (state.historyMethod && shot.method !== state.historyMethod) return false;
      if (!q) return true;
      var haystack = [
        shot.bean_name, shot.bean_roaster, shot.method, shot.grind, shot.machine, shot.grinder,
        shot.tasting_notes, shot.notes, shot.cafe_name, shot.drink_name, (shot.flavor_tags || []).join(" ")
      ].join(" ").toLowerCase();
      return haystack.indexOf(q) !== -1;
    });
  }

  function viewHistory(openId) {
    var list = filteredShots();

    $("#view").innerHTML =
      '<div class="toolbar">' +
        '<div class="search">' + icon("search") + '<input type="search" id="history-search" placeholder="Search notes or beans…" value="' + esc(state.historyQuery) + '" aria-label="Search history"></div>' +
        '<select id="history-method" aria-label="Filter by method">' +
          '<option value="">All methods</option>' +
          METHODS.map(function (m) { return '<option value="' + esc(m) + '"' + (state.historyMethod === m ? " selected" : "") + '>' + esc(titleCase(m)) + '</option>'; }).join("") +
        '</select>' +
        '<button class="btn btn-ghost" id="history-fav" style="' + (state.historyFavorite ? "border-color:var(--clay);color:var(--clay)" : "") + '">' + icon("star") + 'Favourites</button>' +
        '<a class="btn btn-ghost" href="#/cafe">' + icon("cafe") + 'Log a café visit</a>' +
        '<span class="count">' + list.length + ' ' + (list.length === 1 ? "entry" : "entries") + '</span>' +
      '</div>' +
      '<div id="history-list">' + historyList(list) + '</div>';

    var search = $("#history-search");
    var timer = null;
    search.addEventListener("input", function () {
      clearTimeout(timer);
      timer = setTimeout(function () {
        state.historyQuery = search.value;
        var pos = search.selectionStart;
        $("#history-list").innerHTML = historyList(filteredShots());
        var again = $("#history-search");
        again.focus();
        try { again.setSelectionRange(pos, pos); } catch (e) { /* ignore */ }
        bindShotCards();
        $(".count").textContent = filteredShots().length + " " + (filteredShots().length === 1 ? "entry" : "entries");
      }, 140);
    });

    $("#history-method").addEventListener("change", function (event) {
      state.historyMethod = event.target.value;
      viewHistory();
    });

    $("#history-fav").addEventListener("click", function () {
      state.historyFavorite = !state.historyFavorite;
      viewHistory();
    });

    bindShotCards();

    if (openId) {
      var card = $('.shot-card[data-id="' + openId + '"]');
      if (card) {
        card.classList.add("open");
        setTimeout(function () { card.scrollIntoView({ behavior: "smooth", block: "center" }); }, 100);
      }
    }
  }

  function historyList(list) {
    if (!list.length) {
      return '<div class="card empty"><div class="mark">' + icon("clock") + '</div><h3>' +
        (state.shots.length ? "Nothing matches that" : "Your journal is waiting") + '</h3><p>' +
        (state.shots.length ? "Try a different search, or clear the filters." : "Once you log a shot, it will live here — with all the details you might want later.") +
        '</p>' + (state.shots.length ? "" : '<a class="btn btn-primary" href="#/log">Log your first shot</a>') + '</div>';
    }
    return '<div class="shot-list">' + list.map(shotCard).join("") + '</div>';
  }

  function shotCard(shot) {
    var date = new Date(shot.brewed_at);
    var meta = [];
    if (shot.dose_g || shot.yield_g) meta.push(grams(shot.dose_g) + " → " + grams(shot.yield_g));
    if (shot.time_s) meta.push(shotTime(shot.time_s));
    if (shot.grind) meta.push("grind " + shot.grind);
    if (shot.rating) meta.push(shot.rating + "/5");

    var details = [];
    function add(label, value) { if (value !== null && value !== undefined && value !== "" && value !== "—") details.push('<div><div class="k">' + esc(label) + '</div><div class="v">' + esc(value) + '</div></div>'); }
    if (shot.is_cafe) {
      add("Where", shot.cafe_name);
      add("Ordered", shot.drink_name);
      add("Style", titleCase(shot.method));
    }
    add("Dose", shot.dose_g ? grams(shot.dose_g) : "");
    add("Yield", shot.yield_g ? grams(shot.yield_g) : "");
    add("Ratio", ratio(shot) || "");
    add("Time", shot.time_s ? shotTime(shot.time_s) : "");
    add("Grind", shot.grind);
    add("Temp", shot.temp_c ? num(shot.temp_c, 1) + " °C" : "");
    add("Pressure", shot.pressure_bar ? num(shot.pressure_bar, 1) + " bar" : "");
    add("Pre-infusion", shot.preinfusion_s ? shotTime(shot.preinfusion_s) : "");
    add("TDS", shot.tds ? num(shot.tds, 2) + "%" : "");
    add("Extraction", shot.ey ? num(shot.ey, 1) + "%" : "");
    add("Milk", shot.milk_type ? shot.milk_type + (shot.milk_volume_ml ? " · " + num(shot.milk_volume_ml, 0) + "ml" : "") : "");
    add("Machine", shot.machine);
    add("Grinder", shot.grinder);
    add("Basket", shot.basket);

    var meterFields = TASTE.filter(function (pair) { return shot[pair[0]]; });
    var meters = meterFields.length ? '<div class="meters">' + meterFields.map(function (pair) {
      var value = shot[pair[0]];
      return '<div class="meter-row"><span>' + pair[1] + '</span><div class="meter-track"><div class="meter-fill" style="width:' + (value / 5 * 100) + '%"></div></div><span>' + value + '</span></div>';
    }).join("") + '</div>' : "";

    return '<article class="shot-card" data-id="' + shot.id + '">' +
      '<div class="shot-head">' +
        '<div class="shot-date"><div class="d">' + date.getDate() + '</div><div class="m">' + MONTHS[date.getMonth()] + '</div></div>' +
        '<div class="shot-main">' +
          '<div class="top"><h4>' + esc(shot.is_cafe ? (shot.cafe_name || "Out for coffee") : (shot.bean_name || "No bean recorded")) + '</h4>' +
            '<span class="pill">' + esc(titleCase(shot.method)) + '</span>' +
            (shot.is_cafe && shot.drink_name ? '<span class="pill line">' + icon("cup") + esc(shot.drink_name) + '</span>' : "") +
            (shot.favorite ? '<span class="pill clay">' + (shot.is_cafe ? "Would go back" : "Favourite") + '</span>' : "") +
          '</div>' +
          '<div class="meta">' + esc(meta.join(" · ")) + '</div>' +
          '<div class="meta" style="margin-top:3px">' + esc(fmtDateTime(shot.brewed_at)) + '</div>' +
          (shot.flavor_tags && shot.flavor_tags.length ? '<div class="meta" style="margin-top:6px"><span>' + shot.flavor_tags.slice(0, 4).map(esc).join(" · ") + '</span></div>' : "") +
        '</div>' +
        '<div class="shot-side">' +
          (shot.photo ? '<button type="button" class="shot-thumb" data-photo="' + esc(shot.photo.url) + '" aria-label="View photo"><img src="' + esc(shot.photo.thumb_url) + '" alt="" loading="lazy"></button>' : "") +
          '<div class="stars">' + stars(shot.rating) + '</div><span class="chev">' + icon("chevron") + '</span></div>' +
      '</div>' +
      '<div class="shot-body">' +
        (shot.photo ? '<button type="button" class="shot-photo" data-photo="' + esc(shot.photo.url) + '" aria-label="View photo"><img src="' + esc(shot.photo.thumb_url) + '" alt="Photo of this shot" loading="lazy"></button>' : "") +
        (details.length ? '<div class="detail-grid">' + details.join("") + '</div>' : "") +
        (meters || shot.flavor_tags.length ? '<div class="split" style="gap:18px;margin-bottom:14px">' +
          '<div>' + (meters ? '<div class="eyebrow" style="margin-bottom:8px">Balance</div>' + meters : "") + '</div>' +
          '<div>' + (shot.flavor_tags.length ? '<div class="eyebrow" style="margin-bottom:8px">Flavour</div><div class="tag-cloud">' + shot.flavor_tags.map(function (t) { return '<span class="pill clay">' + esc(t) + '</span>'; }).join("") + '</div>' : "") + '</div>' +
        '</div>' : "") +
        (shot.tasting_notes ? '<div class="notes-block"><div class="k">Tasting notes</div>' + esc(shot.tasting_notes) + '</div>' : "") +
        (shot.notes ? '<div class="notes-block"><div class="k">Notes</div>' + esc(shot.notes) + '</div>' : "") +
        '<div class="shot-actions">' +
          '<a class="btn btn-ghost btn-sm" href="' + (shot.is_cafe ? "#/cafe/" : "#/log/") + shot.id + '">' + icon("edit") + 'Edit</a>' +
          '<button class="btn btn-ghost btn-sm" data-fav="' + shot.id + '">' + icon("star") + (shot.favorite ? (shot.is_cafe ? "Not again" : "Unfavourite") : (shot.is_cafe ? "Would go back" : "Favourite")) + '</button>' +
          '<button class="btn btn-danger btn-sm" data-del="' + shot.id + '">' + icon("trash") + 'Delete</button>' +
        '</div>' +
      '</div>' +
    '</article>';
  }

  function bindShotCards() {
    $$(".shot-card").forEach(function (card) {
      var head = $(".shot-head", card);
      head.addEventListener("click", function (event) {
        if (event.target.closest("[data-fav]") || event.target.closest("[data-del]") || event.target.closest("[data-photo]")) return;
        card.classList.toggle("open");
      });
    });

    $$("[data-photo]").forEach(function (button) {
      button.addEventListener("click", function (event) {
        event.stopPropagation();
        openPhoto(button.dataset.photo, "Shot photo");
      });
    });

    $$("[data-fav]").forEach(function (button) {
      button.addEventListener("click", async function () {
        var shot = state.shots.filter(function (s) { return String(s.id) === button.dataset.fav; })[0];
        if (!shot) return;
        try {
          await api("/api/shots/" + shot.id, { method: "PATCH", body: { favorite: !shot.favorite } });
          await refreshShots();
          await refreshStats();
          toast(shot.favorite ? "Removed from favourites" : "Added to favourites");
          var open = $(".shot-card.open");
          viewHistory(open ? open.dataset.id : null);
        } catch (err) { toast(err.message, "error"); }
      });
    });

    $$("[data-del]").forEach(function (button) {
      button.addEventListener("click", async function () {
        var shot = state.shots.filter(function (s) { return String(s.id) === button.dataset.del; })[0];
        if (!shot) return;
        var ok = await confirmDialog("Delete this entry?", "This removes the shot and its tasting notes. It can’t be undone.");
        if (!ok) return;
        try {
          await api("/api/shots/" + shot.id, { method: "DELETE" });
          await refreshAll();
          toast("Entry deleted");
          viewHistory();
        } catch (err) { toast(err.message, "error"); }
      });
    });
  }

  // ------------------------------------------------------------ beans

  function viewBeans() {
    var active = state.beans.filter(function (b) { return !b.archived; });
    var archived = state.beans.filter(function (b) { return b.archived; });

    $("#view").innerHTML =
      '<div class="toolbar" style="justify-content:space-between">' +
        '<p class="small muted" style="margin:0">' + active.length + ' open ' + (active.length === 1 ? "bag" : "bags") + (archived.length ? " · " + archived.length + " archived" : "") + '</p>' +
        '<button class="btn btn-primary" id="add-bean">' + icon("plus") + 'Add beans</button>' +
      '</div>' +
      (active.length + archived.length ? '<div class="bean-grid">' + active.concat(archived).map(beanCard).join("") + '</div>' :
        '<div class="card empty"><div class="mark">' + icon("bean") + '</div><h3>The cellar is empty</h3><p>Add the bag you are brewing now. Every shot can then point back to it.</p><button class="btn btn-primary" id="add-bean-empty">Add your first bag</button></div>');

    function attachAdd() {
      ["add-bean", "add-bean-empty"].forEach(function (id) {
        var button = $("#" + id);
        if (button) button.addEventListener("click", function () {
          openBeanModal(null, async function () { await refreshBeans(); viewBeans(); });
        });
      });
    }
    attachAdd();

    $$("[data-edit-bean]").forEach(function (button) {
      button.addEventListener("click", function () {
        var bean = state.beans.filter(function (b) { return String(b.id) === button.dataset.editBean; })[0];
        if (!bean) return;
        openBeanModal(bean, async function () { await refreshBeans(); viewBeans(); });
      });
    });

    $$("[data-archive-bean]").forEach(function (button) {
      button.addEventListener("click", async function () {
        var bean = state.beans.filter(function (b) { return String(b.id) === button.dataset.archiveBean; })[0];
        if (!bean) return;
        try {
          await api("/api/beans/" + bean.id, { method: "PATCH", body: { archived: !bean.archived } });
          await refreshBeans();
          viewBeans();
          toast(bean.archived ? "Bag restored" : "Bag archived");
        } catch (err) { toast(err.message, "error"); }
      });
    });

    $$("[data-delete-bean]").forEach(function (button) {
      button.addEventListener("click", async function () {
        var bean = state.beans.filter(function (b) { return String(b.id) === button.dataset.deleteBean; })[0];
        if (!bean) return;
        var ok = await confirmDialog("Delete this bag?", "Shots logged with " + bean.name + " will stay in your journal, but they will no longer be linked to this bag.");
        if (!ok) return;
        try {
          await api("/api/beans/" + bean.id, { method: "DELETE" });
          await refreshAll();
          viewBeans();
          toast("Bag deleted");
        } catch (err) { toast(err.message, "error"); }
      });
    });
  }

  function daysSince(dateText) {
    if (!dateText) return null;
    var d = new Date(dateText + "T12:00:00");
    if (isNaN(d.getTime())) return null;
    return Math.max(0, Math.round((Date.now() - d.getTime()) / 86400000));
  }

  function beanCard(bean) {
    var age = daysSince(bean.roast_date);
    var usage = "";
    if (bean.bag_size_g) {
      var shotsLeft = bean.shots_left;
      usage = '<div class="bag-usage">' +
        '<span><strong>' + num(bean.remaining_g, 0) + 'g</strong> of ' + num(bean.bag_size_g, 0) + 'g left</span>' +
        (shotsLeft === null || shotsLeft === undefined ? "" :
          '<span class="sep">·</span><span>' + (shotsLeft === 0 ? "down to the last shots" : "about " + shotsLeft + " shot" + (shotsLeft === 1 ? "" : "s")) + '</span>') +
      '</div>';
    }
    return '<article class="bean-card' + (bean.archived ? " is-archived" : "") + '">' +
      '<div class="top"><div><h3>' + esc(bean.name) + '</h3>' + (bean.roaster ? '<div class="roaster">' + esc(bean.roaster) + '</div>' : "") + '</div>' +
        (bean.archived ? '<span class="pill line">Archived</span>' : "") +
      '</div>' +
      '<div class="chips">' +
        (bean.origin ? '<span class="pill">' + esc(bean.origin) + '</span>' : "") +
        (bean.process ? '<span class="pill">' + esc(bean.process) + '</span>' : "") +
        (bean.roast_level ? '<span class="pill olive">' + esc(titleCase(bean.roast_level)) + '</span>' : "") +
        (age !== null ? '<span class="pill line">' + (age === 0 ? "Roasted today" : age + " days off roast") + '</span>' : "") +
        (age !== null && age >= 7 && age <= 21 ? '<span class="pill olive">In its prime</span>' : "") +
      '</div>' +
      (bean.notes ? '<p class="notes">' + esc(bean.notes) + '</p>' : "") +
      usage +
      '<div class="foot">' +
        '<span class="shots">' + bean.shot_count + ' shot' + (bean.shot_count === 1 ? "" : "s") + ' logged</span>' +
        '<span class="acts">' +
          '<button class="icon-btn" data-edit-bean="' + bean.id + '" title="Edit">' + icon("edit") + '</button>' +
          '<button class="icon-btn" data-archive-bean="' + bean.id + '" title="' + (bean.archived ? "Restore" : "Archive") + '">' + icon("archive") + '</button>' +
          '<button class="icon-btn" data-delete-bean="' + bean.id + '" title="Delete">' + icon("trash") + '</button>' +
        '</span>' +
      '</div>' +
    '</article>';
  }

  // ------------------------------------------------------------ calculator

  function viewCalculator() {
    $("#view").innerHTML =
      '<div class="calc-grid" style="margin-bottom:20px">' +
        '<section class="card card-pad">' +
          '<div class="card-head"><div><h3>Ratio calculator</h3><p>Change any field to solve the others.</p></div></div>' +
          '<div class="form-grid">' +
            '<div class="field"><label for="calc-dose">Dose (g)</label><input type="text" inputmode="decimal" id="calc-dose" value="18"></div>' +
            '<div class="field"><label for="calc-ratio">Ratio (1 : x)</label><input type="text" inputmode="decimal" id="calc-ratio" value="2"></div>' +
            '<div class="field"><label for="calc-yield">Yield (g)</label><input type="text" inputmode="decimal" id="calc-yield" value="36"></div>' +
            '<div class="field"><label for="calc-time">Shot time (s)</label><input type="text" inputmode="decimal" id="calc-time" value="28"></div>' +
          '</div>' +
          '<div class="big-result" style="margin-top:18px">' +
            '<div class="k">Target yield</div>' +
            '<div class="v" id="calc-out">36.0<small> g</small></div>' +
            '<div class="n" id="calc-sub">1 : 2.0 · 18.0g in</div>' +
          '</div>' +
        '</section>' +
        '<section class="card card-pad">' +
          '<div class="card-head"><div><h3>At the machine</h3><p>Little checks that save a shot.</p></div></div>' +
          '<div class="section-stack" style="gap:16px">' +
            '<div><div class="eyebrow" style="margin-bottom:6px">Flow rate</div><div class="ratio-readout" style="margin-top:0"><div><div class="num" id="calc-flow">1.3</div><div class="lbl">grams per second</div></div><div class="spacer"></div><div class="flow"><strong id="calc-pace">In range</strong><span>espresso is usually 0.8–2.0 g/s</span></div></div></div>' +
            '<div class="notes-block"><div class="k">Dialling in</div>Sour and thin usually means grind finer or extract more. Bitter and drying usually means grind coarser or extract less. Change one variable at a time.</div>' +
            '<div class="notes-block"><div class="k">A useful starting point</div>18g in, 36g out, 25–30 seconds. Adjust grind first; keep dose steady while you do.</div>' +
          '</div>' +
        '</section>' +
      '</div>' +
      '<section class="card card-pad">' +
        '<div class="card-head"><div><h3>Starting points</h3><p>Common ratios, before you make it yours.</p></div></div>' +
        '<table class="plain"><thead><tr><th>Style</th><th>Ratio</th><th>Notes</th></tr></thead><tbody>' +
          '<tr><td>Ristretto</td><td>1 : 1 – 1 : 1.5</td><td>Short, syrupy, intense</td></tr>' +
          '<tr><td>Espresso</td><td>1 : 2</td><td>The familiar starting point</td></tr>' +
          '<tr><td>Lungo</td><td>1 : 3 – 1 : 4</td><td>Longer, lighter, more tea-like</td></tr>' +
          '<tr><td>Filter</td><td>1 : 15 – 1 : 17</td><td>Adjust for the brewer and the bean</td></tr>' +
          '<tr><td>Cold brew</td><td>1 : 8 – 1 : 12</td><td>Concentrate; dilute to taste</td></tr>' +
        '</tbody></table>' +
      '</section>';

    var dose = $("#calc-dose");
    var ratioInput = $("#calc-ratio");
    var yieldInput = $("#calc-yield");
    var timeInput = $("#calc-time");
    var lock = false;

    function read(el) { var n = parseFloat(el.value); return isFinite(n) && n > 0 ? n : null; }

    function paint() {
      var d = read(dose);
      var r = read(ratioInput);
      var y = read(yieldInput);
      var t = read(timeInput);
      $("#calc-out").innerHTML = (y ? y.toFixed(1) : "—") + '<small> g</small>';
      $("#calc-sub").textContent = (d && y ? "1 : " + (y / d).toFixed(1) + " · " + d.toFixed(1) + "g in" : "Enter a dose and yield");
      var flow = y && t ? y / t : null;
      $("#calc-flow").textContent = flow ? flow.toFixed(1) : "—";
      var pace = $("#calc-pace");
      if (!flow) { pace.textContent = "—"; }
      else if (flow < 0.8) { pace.textContent = "Slow"; }
      else if (flow > 2) { pace.textContent = "Fast"; }
      else { pace.textContent = "In range"; }
    }

    function solveFromDoseRatio() {
      if (lock) return;
      var d = read(dose);
      var r = read(ratioInput);
      if (!d || !r) return;
      lock = true;
      yieldInput.value = (d * r).toFixed(1);
      lock = false;
      paint();
    }

    function solveFromYield() {
      if (lock) return;
      var d = read(dose);
      var y = read(yieldInput);
      if (!d || !y) return;
      lock = true;
      ratioInput.value = (y / d).toFixed(1);
      lock = false;
      paint();
    }

    dose.addEventListener("input", solveFromDoseRatio);
    ratioInput.addEventListener("input", solveFromDoseRatio);
    yieldInput.addEventListener("input", solveFromYield);
    timeInput.addEventListener("input", paint);
    paint();
  }

  // ------------------------------------------------------------ settings

  function viewSettings() {
    var user = state.user;
    var prefs = user.preferences || {};
    var isIOS = /iphone|ipad|ipod/i.test(navigator.userAgent);
    var installCard = "";

    if (!runningStandalone()) {
      installCard =
        '<section class="card card-pad">' +
          '<div class="card-head"><div><h3>On your phone</h3><p>Keep Crema a tap away.</p></div></div>' +
          (deferredInstall
            ? '<p class="small muted" style="margin-bottom:14px">It opens full screen, like an app of its own.</p>' +
              '<button class="btn btn-primary" id="install-app">' + icon("download") + 'Install app</button>'
            : '<p class="small muted">' + (isIOS
                ? 'In Safari, tap the Share button and choose “Add to Home Screen”.'
                : 'Open your browser menu and choose “Install app” or “Add to Home Screen”.') + '</p>') +
        '</section>';
    }

    var adminCard = "";
    var backupCard = "";
    if (user.admin) {
      adminCard =
        '<section class="card card-pad" id="accounts-card">' +
          '<div class="card-head"><div><h3>New accounts</h3><p>Decide who gets a journal.</p></div></div>' +
          '<label class="switch-row">' +
            '<span class="switch-copy"><strong>Require my approval</strong><span>New sign-ups wait here until you let them in.</span></span>' +
            '<span class="switch"><input type="checkbox" id="approval-toggle" role="switch"' + (user.registration_approval ? " checked" : "") + '><span class="track"></span></span>' +
          '</label>' +
          '<div class="pending-list" id="pending-list"><p class="small muted">Loading requests…</p></div>' +
        '</section>';

      backupCard =
        '<section class="card card-pad" id="backup-card">' +
          '<div class="card-head"><div><h3>Backups</h3><p>Nightly archives on this machine.</p></div></div>' +
          '<p class="small muted" id="backup-status">Checking…</p>' +
          '<div class="export-row" style="margin-top:12px">' +
            '<button class="btn btn-ghost btn-sm" id="backup-now" type="button">Back up now</button>' +
            '<a class="btn btn-quiet btn-sm" href="/api/backup/latest" download>Download latest</a>' +
          '</div>' +
        '</section>';
    }

    $("#view").innerHTML =
      '<div class="settings-grid">' +
        '<div class="section-stack">' +
          '<section class="card card-pad">' +
            '<div class="profile-head">' +
              avatarHtml(user, "avatar-lg") +
              '<div><div class="n">' + esc(user.name) + '</div><div class="e">' + esc(user.email) + '</div></div>' +
            '</div>' +
            '<div class="avatar-actions">' +
              '<label class="btn btn-ghost btn-sm" for="avatar-input">' + icon("camera") + 'Change photo</label>' +
              '<input type="file" id="avatar-input" accept="image/*" hidden>' +
              (user.avatar ? '<button class="btn btn-quiet btn-sm" id="avatar-remove" type="button">Remove</button>' : '') +
            '</div>' +
            '<p class="small muted avatar-hint">A square photo works best. It stays on your own server.</p>' +
            '<form id="profile-form" class="form-grid">' +
              '<div class="field span-2"><label for="profile-name">Display name</label><input type="text" id="profile-name" name="name" autocomplete="name" value="' + esc(user.name) + '"></div>' +
              '<div class="field span-2"><label for="profile-email">Email</label><input type="email" id="profile-email" value="' + esc(user.email) + '" disabled></div>' +
              '<div class="span-2"><button class="btn btn-primary" type="submit">Save profile</button></div>' +
            '</form>' +
          '</section>' +

          '<section class="card card-pad">' +
            '<div class="card-head"><div><h3>Defaults</h3><p>Used to fill in a new entry.</p></div></div>' +
            '<form id="defaults-form" class="form-grid">' +
              field("pref-machine", "Machine", prefs.machine || "", "", null, "machine") +
              field("pref-grinder", "Grinder", prefs.grinder || "", "", null, "grinder") +
              field("pref-basket", "Basket", prefs.basket || "", "", null, "basket") +
              field("pref-dose", "Default dose", prefs.dose_g, "g", null, "dose_g") +
              field("pref-yield", "Default yield", prefs.yield_g, "g", null, "yield_g") +
              field("pref-temp", "Default temperature", prefs.temp_c, "°C", null, "temp_c") +
              '<div class="field span-2"><label for="pref-style">Espresso style</label>' +
                '<select id="pref-style">' +
                  '<option value=""' + (prefs.espresso_style ? "" : " selected") + '>No preset</option>' +
                  ESPRESSO_STYLES.map(function (style) {
                    return '<option value="' + esc(style.id) + '"' + (prefs.espresso_style === style.id ? " selected" : "") + '>' +
                      esc(style.label) + ' — ' + style.dose + 'g in, ' + style.yield + 'g out, ' + style.time + 's</option>';
                  }).join("") +
                '</select>' +
                '<p class="small muted" style="margin-top:6px">Sets the timer target and the starting dose and yield for a new shot.</p>' +
              '</div>' +
              '<div class="span-2"><button class="btn btn-primary" type="submit">Save defaults</button></div>' +
            '</form>' +
          '</section>' +
        '</div>' +

        '<div class="section-stack">' +
          adminCard +
          installCard +
          '<section class="card card-pad">' +
            '<div class="card-head"><div><h3>Your data</h3><p>Yours to take with you.</p></div></div>' +
            '<p class="small muted" style="margin-bottom:14px">A printed-style PDF of your whole journal, plus a spreadsheet and a complete JSON backup.</p>' +
            '<div class="export-row">' +
              '<a class="btn btn-primary" href="/api/export.pdf" download>' + icon("download") + 'PDF journal</a>' +
              '<a class="btn btn-ghost" href="/api/export.csv" download>' + icon("download") + 'CSV</a>' +
              '<a class="btn btn-ghost" href="/api/export.json" download>' + icon("download") + 'JSON</a>' +
            '</div>' +
          '</section>' +

          backupCard +

          '<section class="card card-pad">' +
            '<div class="card-head"><div><h3>Password</h3><p>Change the key to your journal.</p></div></div>' +
            '<form id="password-form" class="form-grid">' +
              '<div class="field span-2"><label for="new-password">New password</label><input type="password" id="new-password" name="password" autocomplete="new-password" placeholder="At least 8 characters"></div>' +
              '<div class="field span-2"><label for="confirm-password">Confirm new password</label><input type="password" id="confirm-password" name="confirm" autocomplete="new-password" placeholder="Repeat it"></div>' +
              '<div class="span-2"><button class="btn btn-ghost" type="submit">Update password</button></div>' +
            '</form>' +
          '</section>' +

          '<section class="card card-pad">' +
            '<div class="about-list">' +
              '<div><strong>Crema</strong> · a small coffee journal</div>' +
              '<div>Stored on this home server’s own drive, available to any device you sign in from.</div>' +
              '<div>Version 1.2.1 · a tidier mobile bar</div>' +
            '</div>' +
            '<div class="divider"></div>' +
            '<button class="btn btn-danger" id="sign-out">' + icon("logout") + 'Sign out</button>' +
          '</section>' +
        '</div>' +
      '</div>';

    $("#profile-form").addEventListener("submit", async function (event) {
      event.preventDefault();
      var button = this.querySelector("button[type=submit]");
      busy(button, true);
      try {
        var data = await api("/api/me", { method: "PATCH", body: { name: $("#profile-name").value } });
        state.user = data.user;
        renderShell();
        route();
        toast("Profile saved");
      } catch (err) { busy(button, false); toast(err.message, "error"); }
    });

    var avatarInput = $("#avatar-input");
    if (avatarInput) {
      avatarInput.addEventListener("change", async function (event) {
        var file = event.target.files && event.target.files[0];
        if (!file) return;
        try {
          var prepared = await compressPhoto(file);
          var data = await api("/api/me/avatar", { method: "POST", body: { photo: prepared.thumb } });
          state.user = data.user;
          haptic();
          toast("Profile photo updated");
          renderShell();
          route();
        } catch (err) {
          event.target.value = "";
          toast(err.message, "error");
        }
      });
    }

    var avatarRemove = $("#avatar-remove");
    if (avatarRemove) {
      avatarRemove.addEventListener("click", async function () {
        busy(avatarRemove, true);
        try {
          var data = await api("/api/me/avatar", { method: "DELETE" });
          state.user = data.user;
          toast("Profile photo removed");
          renderShell();
          route();
        } catch (err) {
          busy(avatarRemove, false);
          toast(err.message, "error");
        }
      });
    }

    $("#defaults-form").addEventListener("submit", async function (event) {
      event.preventDefault();
      var button = this.querySelector("button[type=submit]");
      busy(button, true);
      try {
        var data = await api("/api/me", {
          method: "PATCH",
          body: {
            preferences: {
              machine: $("#pref-machine").value,
              grinder: $("#pref-grinder").value,
              basket: $("#pref-basket").value,
              dose_g: $("#pref-dose").value || null,
              yield_g: $("#pref-yield").value || null,
              temp_c: $("#pref-temp").value || null,
              espresso_style: $("#pref-style").value
            }
          }
        });
        state.user = data.user;
        busy(button, false);
        toast("Defaults saved");
      } catch (err) { busy(button, false); toast(err.message, "error"); }
    });

    var prefStyle = $("#pref-style");
    if (prefStyle) {
      prefStyle.addEventListener("change", function () {
        var style = styleById(prefStyle.value);
        if (!style) return;
        if (!$("#pref-dose").value) $("#pref-dose").value = style.dose;
        if (!$("#pref-yield").value) $("#pref-yield").value = style.yield;
      });
    }

    $("#password-form").addEventListener("submit", async function (event) {
      event.preventDefault();
      var form = this;
      if (form.password.value.length < 8) { toast("Password must be at least 8 characters", "error"); return; }
      if (form.password.value !== form.confirm.value) { toast("Those passwords don’t match", "error"); return; }
      var button = form.querySelector("button[type=submit]");
      busy(button, true);
      try {
        await api("/api/me", { method: "PATCH", body: { password: form.password.value } });
        form.reset();
        busy(button, false);
        toast("Password updated");
      } catch (err) { busy(button, false); toast(err.message, "error"); }
    });

    $("#sign-out").addEventListener("click", async function () {
      var ok = await confirmDialog("Sign out?", "You can sign back in at any time. Your journal will be waiting.");
      if (ok) signOut();
    });

    if (user.admin) {
      var listEl = $("#pending-list");
      var approvalToggle = $("#approval-toggle");

      function showPending(rows) {
        if (!listEl) return;
        if (!rows.length) {
          listEl.innerHTML = '<p class="small muted pending-empty">No requests waiting.</p>';
          return;
        }
        listEl.innerHTML = rows.map(function (row) {
          return '<div class="pending-row">' +
            '<div class="pending-who"><strong>' + esc(row.name) + '</strong><span>' + esc(row.email) + '</span></div>' +
            '<div class="pending-actions">' +
              '<button class="btn btn-primary btn-sm" data-approve="' + row.id + '">Approve</button>' +
              '<button class="btn btn-quiet btn-sm" data-reject="' + row.id + '">Decline</button>' +
            '</div></div>';
        }).join("");
      }

      async function loadPending() {
        try {
          var data = await api("/api/admin/registration");
          if (approvalToggle) approvalToggle.checked = data.registration_approval;
          showPending(data.pending || []);
        } catch (err) {
          if (listEl) listEl.innerHTML = '<p class="small muted pending-empty">Could not load requests.</p>';
        }
      }

      if (approvalToggle) {
        approvalToggle.addEventListener("change", async function () {
          var next = approvalToggle.checked;
          approvalToggle.disabled = true;
          try {
            await api("/api/admin/registration", {
              method: "POST",
              body: { registration_approval: next }
            });
            toast(next ? "New accounts need your approval" : "Registration is open to anyone");
          } catch (err) {
            approvalToggle.checked = !next;
            toast(err.message, "error");
          }
          approvalToggle.disabled = false;
        });
      }

      if (listEl) {
        listEl.addEventListener("click", async function (event) {
          var button = event.target.closest("button[data-approve],button[data-reject]");
          if (!button) return;
          var approving = Boolean(button.dataset.approve);
          var id = button.dataset.approve || button.dataset.reject;
          busy(button, true, "…");
          try {
            await api("/api/admin/users/" + id + "/" + (approving ? "approve" : "reject"), { method: "POST" });
            toast(approving ? "Account approved" : "Request declined");
            await loadPending();
          } catch (err) {
            busy(button, false);
            toast(err.message, "error");
          }
        });
      }

      loadPending();
    }

    var backupStatus = $("#backup-status");
    if (backupStatus) {
      var paintBackup = function (data) {
        if (!data) {
          backupStatus.textContent = "Backups are unavailable right now.";
          return;
        }
        var pieces = [];
        pieces.push(data.last_backup_at
          ? "Last backup " + fmtDateTime(data.last_backup_at)
          : "No backup yet");
        if (data.files && data.files.length) {
          pieces.push(data.files.length + (data.files.length === 1 ? " archive" : " archives") + " kept");
        } else {
          pieces.push("none kept yet");
        }
        pieces.push("runs every " + (data.hours >= 24 ? Math.round(data.hours / 24) + " day" + (data.hours >= 48 ? "s" : "") : data.hours + " hours"));
        if (data.enabled === false) {
          pieces[pieces.length - 1] = "automatic backups are off";
        }
        backupStatus.textContent = pieces.join(" · ");
      };

      api("/api/backup").then(paintBackup).catch(function () { paintBackup(null); });

      var backupNow = $("#backup-now");
      if (backupNow) {
        backupNow.addEventListener("click", async function () {
          busy(backupNow, true, "Backing up…");
          try {
            await api("/api/backup", { method: "POST" });
            var fresh = await api("/api/backup");
            paintBackup(fresh);
            toast("Backup written");
          } catch (err) {
            toast(err.message, "error");
          }
          busy(backupNow, false);
        });
      }
    }

    var installButton = $("#install-app");
    if (installButton) installButton.addEventListener("click", promptInstall);
  }

  // ------------------------------------------------------------ modal

  function closeModal() {
    modalRoot.innerHTML = "";
  }

  function openModal(options) {
    modalRoot.innerHTML =
      '<div class="modal-backdrop" id="modal-backdrop">' +
        '<div class="modal" role="dialog" aria-modal="true" aria-label="' + esc(options.title) + '">' +
          '<div class="modal-head"><div><h3>' + esc(options.title) + '</h3>' + (options.subtitle ? '<p>' + esc(options.subtitle) + '</p>' : "") + '</div>' +
            '<button class="icon-btn" id="modal-close" aria-label="Close">' + icon("x") + '</button>' +
          '</div>' +
          '<div class="modal-body">' + options.body + '</div>' +
          (options.footer ? '<div class="modal-foot' + (options.footerBetween ? " between" : "") + '">' + options.footer + '</div>' : "") +
        '</div>' +
      '</div>';

    $("#modal-close").addEventListener("click", closeModal);
    $("#modal-backdrop").addEventListener("mousedown", function (event) {
      if (event.target.id === "modal-backdrop") closeModal();
    });
    if (options.onMount) options.onMount();
  }

  function confirmDialog(title, message) {
    return new Promise(function (resolve) {
      openModal({
        title: title,
        body: '<p class="muted" style="font-size:14px">' + esc(message) + '</p>',
        footer: '<button class="btn btn-ghost" id="confirm-no">Cancel</button><button class="btn btn-danger" id="confirm-yes">Delete</button>',
        onMount: function () {
          $("#confirm-no").addEventListener("click", function () { closeModal(); resolve(false); });
          $("#confirm-yes").addEventListener("click", function () { closeModal(); resolve(true); });
        }
      });
    });
  }

  function openBeanModal(bean, onSaved) {
    var isEdit = Boolean(bean);
    var values = bean || { name: "", roaster: "", origin: "", process: "", varietal: "", roast_level: "", roast_date: "", notes: "", bag_size_g: "" };

    openModal({
      title: isEdit ? "Edit bag" : "Add a bag of beans",
      subtitle: isEdit ? "Update the details of this coffee." : "A little context makes every shot easier to repeat.",
      body:
        '<form id="bean-form" class="form-grid">' +
          '<div class="field span-2"><label for="bean-name">Name</label><input id="bean-name" name="name" value="' + esc(values.name) + '" placeholder="e.g. Yirgacheffe Konga" required></div>' +
          '<div class="field"><label for="bean-roaster">Roaster</label><input id="bean-roaster" name="roaster" value="' + esc(values.roaster) + '" placeholder="e.g. Square Mile"></div>' +
          '<div class="field"><label for="bean-origin">Origin</label><input id="bean-origin" name="origin" value="' + esc(values.origin) + '" placeholder="e.g. Ethiopia"></div>' +
          '<div class="field"><label for="bean-process">Process</label><input id="bean-process" name="process" value="' + esc(values.process) + '" placeholder="e.g. Washed"></div>' +
          '<div class="field"><label for="bean-varietal">Varietal</label><input id="bean-varietal" name="varietal" value="' + esc(values.varietal) + '" placeholder="e.g. Heirloom"></div>' +
          '<div class="field"><label for="bean-roast">Roast level</label><select id="bean-roast" name="roast_level">' +
            ["", "light", "medium-light", "medium", "medium-dark", "dark"].map(function (level) {
              return '<option value="' + level + '"' + (values.roast_level === level ? " selected" : "") + '>' + (level ? esc(titleCase(level.replace("-", " "))) : "Not specified") + '</option>';
            }).join("") +
          '</select></div>' +
          '<div class="field"><label for="bean-date">Roast date</label><input type="date" id="bean-date" name="roast_date" value="' + esc(values.roast_date) + '"></div>' +
          '<div class="field"><label for="bean-size">Bag size <span style="text-transform:none;letter-spacing:0;font-weight:400">(g)</span></label><input type="text" inputmode="decimal" id="bean-size" name="bag_size_g" value="' + (values.bag_size_g || "") + '" placeholder="e.g. 250"></div>' +
          '<div class="field span-2"><label for="bean-notes">Notes</label><textarea id="bean-notes" name="notes" placeholder="Tasting notes from the bag, or your own.">' + esc(values.notes) + '</textarea></div>' +
        '</form>',
      footer: '<button class="btn btn-ghost" id="bean-cancel">Cancel</button><button class="btn btn-primary" id="bean-save">' + (isEdit ? "Save bag" : "Add bag") + '</button>',
      onMount: function () {
        $("#bean-cancel").addEventListener("click", closeModal);
        var save = $("#bean-save");
        save.addEventListener("click", async function () {
          var form = $("#bean-form");
          var payload = {
            name: form.name.value.trim(),
            roaster: form.roaster.value.trim(),
            origin: form.origin.value.trim(),
            process: form.process.value.trim(),
            varietal: form.varietal.value.trim(),
            roast_level: form.roast_level.value,
            roast_date: form.roast_date.value,
            notes: form.notes.value.trim(),
            bag_size_g: form.bag_size_g.value.trim() || null
          };
          if (!payload.name) { toast("Give the bag a name", "error"); return; }
          busy(save, true, isEdit ? "Saving…" : "Adding…");
          try {
            var result = await api(isEdit ? "/api/beans/" + bean.id : "/api/beans", {
              method: isEdit ? "PATCH" : "POST",
              body: payload
            });
            closeModal();
            toast(isEdit ? "Bag updated" : "Bag added");
            if (onSaved) await onSaved(result.bean);
          } catch (err) { busy(save, false); toast(err.message, "error"); }
        });
        $("#bean-form").addEventListener("submit", function (event) {
          event.preventDefault();
          save.click();
        });
      }
    });
  }

  // ------------------------------------------------------------ boot

  document.addEventListener("keydown", function (event) {
    if (event.key === "Escape") closeModal();
  });

  window.addEventListener("beforeinstallprompt", function (event) {
    event.preventDefault();
    deferredInstall = event;
    if (state.user && state.route.name === "settings") viewSettings();
  });

  if ("serviceWorker" in navigator && (location.protocol === "https:" || location.hostname === "localhost" || location.hostname === "127.0.0.1")) {
    window.addEventListener("load", function () {
      navigator.serviceWorker.register("/sw.js").catch(function () { /* offline support is optional */ });
    });
  }

  window.addEventListener("hashchange", function () {
    if (!state.user) return;
    route();
  });

  window.addEventListener("offline", function () {
    state.offline = true;
    setOfflineNotice(true);
  });

  window.addEventListener("online", function () {
    if (state.offline) probeConnection(true);
    else flushQueue(false);
  });

  document.addEventListener("visibilitychange", function () {
    if (document.visibilityState === "visible" && state.offline) probeConnection(true);
  });

  async function boot() {
    try {
      await loadAll();
      renderShell();
      if (!location.hash) history.replaceState(null, "", "#/dashboard");
      route();
      flushQueue(false);
    } catch (err) {
      if (err && err.status === 401) {
        renderAuth("signin");
      } else if (err && err.offline) {
        var snapshot = readSnapshot();
        if (snapshot) {
          state.user = snapshot.user;
          state.beans = snapshot.beans || [];
          state.shots = snapshot.shots || [];
          state.stats = snapshot.stats || null;
          state.offline = true;
          renderShell();
          if (!location.hash) history.replaceState(null, "", "#/dashboard");
          route();
          refreshPending();
          toast("Offline — showing your last synced journal");
        } else {
          renderAuth("signin", "You’re offline. Reconnect to sign in to Crema.");
        }
      } else {
        renderAuth("signin", "Couldn’t reach the journal. Please check the server and try again.");
      }
    }
  }

  boot();
})();
