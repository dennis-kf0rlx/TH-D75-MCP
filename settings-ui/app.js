// TH-D75 Settings — front-end preview.
// Backend contract (future):
//   GET  /api/catalog  -> {settings:[{id,label,category,description,type,value,options,min,max,step,unit,menu,offset,keywords}]}
//   GET  /api/read     -> {values:{id:value}, model:"TH-D75", firmware:"1.03"}
//   POST /api/apply    -> {changes:[{id,value}], backup:true, verify:true} -> {ok,written,verified}
// Until then, this page uses window.D75_CATALOG and keeps edits in memory only.

const CATEGORY_META = {
  all:        {name:"All settings", color:"#93a2b7", desc:"Every setting in the catalogue"},
  display:    {name:"Display",      color:"#7db5ff", desc:"Screen, backlight, and appearance"},
  audio:      {name:"Audio",        color:"#f3bd64", desc:"Volume, beeps, and receive equalizer"},
  radio:      {name:"Radio",        color:"#63e0b2", desc:"RF, channels, and transmit behavior"},
  gps:        {name:"GPS",          color:"#c8a2ff", desc:"GPS receiver and NMEA output"},
  aprs:       {name:"APRS",         color:"#ff9f7d", desc:"Beaconing, filters, and packet paths"},
  dv:         {name:"DV / D-STAR",  color:"#7de0e6", desc:"D-STAR voice and DV gateway"},
  bluetooth:  {name:"Bluetooth",    color:"#a5b8ff", desc:"Pairing and device identity"},
  interfaces: {name:"Interfaces",   color:"#9acd7a", desc:"USB/Bluetooth data routing"},
  other:      {name:"Other",        color:"#8b949e", desc:"Miscellaneous settings"}
};

const state = {
  settings: window.D75_CATALOG || [],
  original: new Map(),
  edits: new Map(),
  category: "all",
  search: "",
  changedOnly: false,
  advanced: false
};

const els = {
  list: document.getElementById("settings-list"),
  empty: document.getElementById("empty"),
  nav: document.getElementById("category-nav"),
  search: document.getElementById("search"),
  changedOnly: document.getElementById("changed-only"),
  resultCount: document.getElementById("result-count"),
  summary: document.getElementById("change-summary"),
  apply: document.getElementById("apply"),
  revert: document.getElementById("revert"),
  advanced: document.getElementById("advanced-toggle"),
  read: document.getElementById("read-radio"),
  toast: document.getElementById("toast"),
  connectionChip: document.getElementById("connection-chip"),
  connectionText: document.getElementById("connection-text"),
  radioMeta: document.getElementById("radio-meta"),
  exitSettings: document.getElementById("exit-settings"),
  vfoA: document.getElementById("vfo-a"),
  vfoB: document.getElementById("vfo-b"),
  vfoStatus: document.getElementById("vfo-status"),
  screenToggle: document.getElementById("screen-toggle"),
  screenModal: document.getElementById("screen-modal"),
  screenClose: document.getElementById("screen-close"),
  screenModalImg: document.getElementById("screen-modal-img"),
  screenCaption: document.getElementById("screen-caption")
};
let sessionActive = false;
let radioTransport = null;
let screenVisible = false;
let screenBusy = false;
let screenTimer = null;
let screenObjectUrl = null;

for (const setting of state.settings) {
  state.original.set(setting.id, cloneValue(setting.value));
}

function cloneValue(value) {
  if (Array.isArray(value)) return value.slice();
  return value;
}

function sameValue(a, b) {
  return JSON.stringify(a) === JSON.stringify(b);
}

function effectiveValue(setting) {
  return state.edits.has(setting.id) ? state.edits.get(setting.id) : setting.value;
}

function isChanged(setting) {
  return state.edits.has(setting.id) && !sameValue(state.edits.get(setting.id), state.original.get(setting.id));
}

function setValue(setting, value) {
  if (sameValue(value, state.original.get(setting.id))) {
    state.edits.delete(setting.id);
  } else {
    state.edits.set(setting.id, value);
  }
  updateChangeUI();
  const row = els.list.querySelector(`[data-id="${cssEscape(setting.id)}"]`);
  if (row) {
    const changed = isChanged(setting);
    row.classList.toggle("changed", changed);
    row.querySelector(".changed-dot")?.toggleAttribute("hidden", !changed);
  }
}

function cssEscape(value) {
  if (window.CSS && CSS.escape) return CSS.escape(value);
  return String(value).replace(/["\\]/g, "\\$&");
}

function changedSettings() {
  return state.settings.filter(isChanged);
}

function updateChangeUI() {
  const changed = changedSettings();
  const count = changed.length;
  els.summary.innerHTML = count
    ? `<strong>${count}</strong> unsaved change${count === 1 ? "" : "s"}`
    : "No unsaved changes";
  els.apply.disabled = count === 0;
  els.revert.disabled = count === 0;
  els.apply.textContent = count ? `Apply ${count} change${count === 1 ? "" : "s"}` : "Apply changes";
}

function categoryCounts() {
  const counts = new Map();
  for (const setting of state.settings) {
    counts.set(setting.category, (counts.get(setting.category) || 0) + 1);
  }
  return counts;
}

function renderCategories() {
  const counts = categoryCounts();
  els.nav.replaceChildren();
  const total = state.settings.length;
  const entries = [["all", total], ...Object.keys(CATEGORY_META).filter(k => k !== "all").map(k => [k, counts.get(k) || 0])];
  for (const [key, count] of entries) {
    if (key !== "all" && count === 0) continue;
    const meta = CATEGORY_META[key];
    const button = document.createElement("button");
    button.type = "button";
    button.className = "cat" + (key === "all" ? " cat-all" : "") + (state.category === key ? " active" : "");
    button.dataset.category = key;
    button.setAttribute("aria-pressed", state.category === key ? "true" : "false");
    button.style.setProperty("--cat-color", meta.color);
    const dot = document.createElement("span");
    dot.className = "cat-dot";
    const name = document.createElement("span");
    name.className = "cat-name";
    name.textContent = meta.name;
    const countEl = document.createElement("span");
    countEl.className = "cat-count";
    countEl.textContent = count;
    button.append(dot, name, countEl);
    button.addEventListener("click", () => {
      state.category = key;
      renderCategories();
      renderList();
    });
    els.nav.append(button);
  }
}

function matches(setting) {
  if (state.category !== "all" && setting.category !== state.category) return false;
  if (state.changedOnly && !isChanged(setting)) return false;
  const q = state.search.trim().toLowerCase();
  if (!q) return true;
  const haystack = [
    setting.label,
    setting.description,
    setting.id,
    setting.category,
    CATEGORY_META[setting.category]?.name,
    setting.keywords,
    `menu ${setting.menu}`,
    setting.offset
  ].filter(Boolean).join(" ").toLowerCase();
  return q.split(/\s+/).every(term => haystack.includes(term));
}

function renderList() {
  const visible = state.settings.filter(matches);
  els.resultCount.textContent = `${visible.length} setting${visible.length === 1 ? "" : "s"}`;
  els.empty.hidden = visible.length !== 0;
  els.list.hidden = visible.length === 0;
  els.list.replaceChildren();
  if (!visible.length) return;

  const groups = new Map();
  for (const setting of visible) {
    if (!groups.has(setting.category)) groups.set(setting.category, []);
    groups.get(setting.category).push(setting);
  }

  for (const [category, items] of groups) {
    const group = document.createElement("section");
    group.className = "group";
    group.dataset.category = category;
    const head = document.createElement("div");
    head.className = "group-head";
    const title = document.createElement("h2");
    title.textContent = CATEGORY_META[category]?.name || category;
    const desc = document.createElement("span");
    desc.className = "group-desc";
    desc.textContent = CATEGORY_META[category]?.desc || "";
    const line = document.createElement("span");
    line.className = "group-line";
    const count = document.createElement("span");
    count.className = "group-count";
    count.textContent = `${items.length}`;
    head.append(title, desc, line, count);

    const rows = document.createElement("div");
    rows.className = "rows";
    for (const setting of items) rows.append(buildRow(setting));
    group.append(head, rows);
    els.list.append(group);
  }
}

function buildRow(setting) {
  const row = document.createElement("div");
  row.className = "row" + (isChanged(setting) ? " changed" : "");
  row.dataset.id = setting.id;
  row.setAttribute("role", "listitem");

  const main = document.createElement("div");
  main.className = "row-main";
  const title = document.createElement("div");
  title.className = "row-title";
  const label = document.createElement("span");
  label.className = "row-label";
  label.textContent = setting.label;
  const dot = document.createElement("span");
  dot.className = "changed-dot";
  dot.hidden = !isChanged(setting);
  dot.title = "Unsaved change";
  title.append(label, dot);
  const desc = document.createElement("div");
  desc.className = "row-desc";
  desc.textContent = setting.description || "";
  desc.title = setting.description || "";
  main.append(title, desc);

  const control = document.createElement("div");
  control.className = "control";
  control.append(buildControl(setting));

  const meta = document.createElement("div");
  meta.className = "row-meta";
  if (setting.menu) {
    const badge = document.createElement("span");
    badge.className = "badge menu";
    badge.textContent = `Menu ${setting.menu}`;
    badge.title = "Radio menu number (optional)";
    meta.append(badge);
  }
  if (setting.offset) {
    const badge = document.createElement("span");
    badge.className = "badge offset";
    badge.textContent = setting.offset;
    badge.title = "MCP clone-image offset (advanced)";
    meta.append(badge);
  }

  row.append(main, control, meta);
  return row;
}

function buildControl(setting) {
  const value = effectiveValue(setting);
  if (setting.type === "toggle") {
    const wrap = document.createElement("div");
    wrap.className = "toggle-row";
    const toggle = document.createElement("button");
    toggle.type = "button";
    toggle.className = "toggle";
    toggle.setAttribute("role", "switch");
    toggle.setAttribute("aria-checked", value ? "true" : "false");
    toggle.setAttribute("aria-label", setting.label);
    const stateText = document.createElement("span");
    stateText.className = "toggle-state";
    stateText.textContent = value ? "On" : "Off";
    toggle.addEventListener("click", () => {
      const next = !(effectiveValue(setting) === true || effectiveValue(setting) === "true");
      toggle.setAttribute("aria-checked", next ? "true" : "false");
      stateText.textContent = next ? "On" : "Off";
      setValue(setting, next);
    });
    wrap.append(toggle, stateText);
    return wrap;
  }

  if (setting.type === "select") {
    const select = document.createElement("select");
    select.setAttribute("aria-label", setting.label);
    for (const [optionValue, optionLabel] of setting.options || []) {
      const option = document.createElement("option");
      option.value = optionValue;
      option.textContent = optionLabel;
      option.selected = String(optionValue) === String(value);
      select.append(option);
    }
    select.addEventListener("change", () => setValue(setting, select.value));
    return select;
  }

  if (setting.type === "number") {
    const wrap = document.createElement("div");
    wrap.className = "number-wrap";
    const input = document.createElement("input");
    input.type = "number";
    input.value = value;
    input.min = setting.min ?? "";
    input.max = setting.max ?? "";
    input.step = setting.step ?? 1;
    input.setAttribute("aria-label", setting.label);
    input.addEventListener("input", () => {
      if (input.value === "") return;
      let next = Number(input.value);
      if (Number.isNaN(next)) return;
      if (setting.min !== undefined) next = Math.max(setting.min, next);
      if (setting.max !== undefined) next = Math.min(setting.max, next);
      setValue(setting, next);
    });
    input.addEventListener("blur", () => {
      if (input.value === "") input.value = String(effectiveValue(setting));
    });
    wrap.append(input);
    if (setting.unit) {
      const unit = document.createElement("span");
      unit.className = "number-unit";
      unit.textContent = setting.unit;
      wrap.append(unit);
    }
    return wrap;
  }

  const input = document.createElement("input");
  input.type = "text";
  input.value = value ?? "";
  input.maxLength = setting.maxlength || 32;
  input.setAttribute("aria-label", setting.label);
  input.addEventListener("input", () => setValue(setting, input.value));
  return input;
}

let toastTimer = 0;
function toast(message) {
  els.toast.textContent = message;
  els.toast.hidden = false;
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => { els.toast.hidden = true; }, 4200);
}

els.search.addEventListener("input", () => {
  state.search = els.search.value;
  renderList();
});

els.changedOnly.addEventListener("change", () => {
  state.changedOnly = els.changedOnly.checked;
  renderList();
});

els.advanced.addEventListener("click", () => {
  state.advanced = !state.advanced;
  document.body.classList.toggle("advanced", state.advanced);
  els.advanced.setAttribute("aria-pressed", state.advanced ? "true" : "false");
  els.advanced.textContent = state.advanced ? "Advanced on" : "Advanced";
});

els.revert.addEventListener("click", () => {
  state.edits.clear();
  renderList();
  updateChangeUI();
  toast("All unsaved changes reverted.");
});

els.apply.addEventListener("click", () => {
  applyChanges();
});

els.read.addEventListener("click", () => {
  readFromRadio();
});

els.exitSettings.addEventListener("click", () => {
  stopSettings();
});

document.getElementById("clear-filters").addEventListener("click", () => {
  state.search = "";
  state.category = "all";
  state.changedOnly = false;
  els.search.value = "";
  els.changedOnly.checked = false;
  renderCategories();
  renderList();
});

document.addEventListener("keydown", (event) => {
  if (event.key === "/" && document.activeElement !== els.search && !isTyping(event.target)) {
    event.preventDefault();
    els.search.focus();
    els.search.select();
  }
  if (event.key === "Escape" && document.activeElement === els.search) {
    els.search.value = "";
    state.search = "";
    renderList();
    els.search.blur();
  }
});

function isTyping(target) {
  return target && (target.matches("input, select, textarea") || target.isContentEditable);
}

function setConnection(text, live) {
  els.connectionText.textContent = text;
  els.connectionChip.classList.toggle("live", Boolean(live));
}

function setRadioMeta(text) {
  els.radioMeta.textContent = text;
}

function setBusy(busy) {
  const el = els.list;
  el.setAttribute("aria-busy", busy ? "true" : "false");
  els.apply.disabled = busy || changedSettings().length === 0;
  els.revert.disabled = busy || changedSettings().length === 0;
  els.read.disabled = busy;
  els.advanced.disabled = busy;
}

function replaceSettings(list) {
  state.settings = list;
  state.original = new Map(list.map(s => [s.id, cloneValue(s.value)]));
  state.edits.clear();
}

function applyValues(values) {
  for (const setting of state.settings) {
    if (Object.prototype.hasOwnProperty.call(values, setting.id)) {
      setting.value = values[setting.id];
    }
  }
  state.original = new Map(state.settings.map(s => [s.id, cloneValue(s.value)]));
  state.edits.clear();
}

function updateSessionUI(active) {
  sessionActive = Boolean(active);
  els.exitSettings.hidden = !sessionActive;
  if (sessionActive) {
    setConnection("Settings mode · radio held", true);
  } else {
    setConnection(CACHE_HAS_VALUES ? "Cached values · click Read" : "Not read yet", false);
  }
}

let CACHE_HAS_VALUES = false;

async function loadFromApi() {
  try {
    const resp = await fetch("/api/catalog", {cache: "no-store"});
    if (!resp.ok) throw new Error(`catalog ${resp.status}`);
    const data = await resp.json();
    if (!Array.isArray(data.settings) || !data.settings.length) throw new Error("empty catalog");
    replaceSettings(data.settings);
    renderCategories();
    renderList();
    updateChangeUI();
    try {
      const vr = await fetch("/api/values", {cache: "no-store"});
      if (vr.ok) {
        const cached = await vr.json();
        const values = cached.values || {};
        if (Object.keys(values).length) {
          CACHE_HAS_VALUES = true;
          applyValues(values);
          if (cached.model) setRadioMeta(`${cached.model} · ${cached.firmware || "?"}`);
          renderList();
          updateChangeUI();
        }
      }
    } catch (error) { /* cache optional */ }
    updateSessionUI(false);
    await pollStatus();
  } catch (error) {
    setConnection("Preview data", false);
    setRadioMeta("TH-D75 · V1.03");
    if (!window.D75_CATALOG) toast("No catalogue available.");
  }
}

function formatHz(raw) {
  const n = Number(raw);
  if (!Number.isFinite(n) || n <= 0) return "—";
  return (n / 1000000).toFixed(6);
}

function setVfo(which, raw) {
  const el = which === "a" ? els.vfoA : els.vfoB;
  if (el) el.textContent = formatHz(raw);
}

function setVfoStatus(text, live) {
  if (!els.vfoStatus) return;
  els.vfoStatus.textContent = text;
  els.vfoStatus.classList.toggle("live", Boolean(live));
}

async function pollMonitor() {
  if (sessionActive) {
    setVfoStatus("monitor paused", false);
    return;
  }
  try {
    const resp = await fetch("/api/monitor/state", {cache: "no-store"});
    if (!resp.ok) throw new Error(`monitor ${resp.status}`);
    const data = await resp.json();
    if (data.transport === "bluetooth" || data.transport === "usb") {
      radioTransport = data.transport;
    }
    const fields = data.fields || {};
    setVfo("a", fields.vfo_a_hz?.value);
    setVfo("b", fields.vfo_b_hz?.value);
    const transport = data.transport === "bluetooth" ? "Bluetooth" : "USB";
    const port = data.port ? ` · ${data.port}` : "";
    setVfoStatus(data.connected ? `${transport}${port}` : "Monitor offline", Boolean(data.connected));
  } catch (error) {
    setVfo("a", null);
    setVfo("b", null);
    setVfoStatus("monitor unavailable", false);
  }
}

async function refreshScreen() {
  if (!screenVisible || screenBusy || !els.screenModalImg) return;
  screenBusy = true;
  if (!radioTransport) {
    try {
      const sr = await fetch("/api/status", {cache: "no-store"});
      if (sr.ok) {
        const sd = await sr.json();
        if (sd.transport === "bluetooth" || sd.transport === "usb") radioTransport = sd.transport;
      }
    } catch (error) { /* fall through */ }
  }
  const isBluetooth = radioTransport === "bluetooth";
  const transport = isBluetooth ? "Bluetooth" : "USB";
  const expected = isBluetooth
    ? "Bluetooth full-frame refresh is about 10–14 s"
    : "USB full-frame refresh is about 2 s";
  const started = performance.now();
  if (els.screenCaption) {
    els.screenCaption.textContent = isBluetooth
      ? "Bluetooth · capturing full 240×180 frame (about 6 s)…"
      : "USB · capturing full 240×180 frame…";
  }
  try {
    const resp = await fetch(`/api/monitor/screen.png?t=${Date.now()}`, {cache: "no-store"});
    if (!resp.ok) throw new Error(`screen ${resp.status}`);
    const blob = await resp.blob();
    if (screenObjectUrl) URL.revokeObjectURL(screenObjectUrl);
    screenObjectUrl = URL.createObjectURL(blob);
    els.screenModalImg.src = screenObjectUrl;
    const elapsed = ((performance.now() - started) / 1000).toFixed(1);
    if (els.screenCaption) {
      const elapsedLabel = Number(elapsed) < 0.1 ? "cached frame" : `captured in ${elapsed}s`;
      els.screenCaption.textContent = `${transport} · ${elapsedLabel} · ${expected}`;
    }
  } catch (error) {
    if (els.screenCaption) {
      els.screenCaption.textContent = `${transport} · capture failed — monitor stopped or link busy`;
    }
  } finally {
    screenBusy = false;
    if (screenVisible) screenTimer = setTimeout(refreshScreen, isBluetooth ? 5000 : 1000);
  }
}

function setScreenVisible(visible) {
  screenVisible = Boolean(visible);
  if (screenTimer) { clearTimeout(screenTimer); screenTimer = null; }
  if (els.screenModal) els.screenModal.hidden = !screenVisible;
  if (els.screenToggle) {
    els.screenToggle.setAttribute("aria-pressed", String(screenVisible));
    els.screenToggle.textContent = screenVisible ? "Hide" : "LCD";
  }
  if (screenVisible) refreshScreen();
}


function toggleScreen() {
  setScreenVisible(!screenVisible);
}

async function pollStatus() {
  try {
    const resp = await fetch("/api/status", {cache: "no-store"});
    if (!resp.ok) return;
    const status = await resp.json();
    if (status.transport === "bluetooth" || status.transport === "usb") {
      radioTransport = status.transport;
    }
    const transport = status.transport === "bluetooth" ? "Bluetooth" : "USB";
    const serialPath = status.serialPath ? ` · ${status.serialPath}` : "";
    setRadioMeta(`TH-D75 · V1.03 · ${transport}${serialPath}`);
    if (status.lastError) setConnection("Radio error · click Read", false);
    updateSessionUI(status.sessionActive);
    if (status.sessionActive) setConnection("Settings mode · radio held", true);
  } catch (error) { /* offline fallback */ }
}

async function readFromRadio(silent) {
  setConnection("Reading from radio…", false);
  setBusy(true);
  try {
    const resp = await fetch("/api/read", {cache: "no-store"});
    const data = await resp.json();
    if (!resp.ok) throw new Error(data.error || `read ${resp.status}`);
    const values = data.values || {};
    applyValues(values);
    CACHE_HAS_VALUES = Object.keys(values).length > 0;
    setRadioMeta(`${data.model || "TH-D75"} · ${data.firmware || "?"}`);
    renderCategories();
    renderList();
    updateChangeUI();
    updateSessionUI(true);
    if (!silent) toast(`Read ${Object.keys(values).length} values. Settings mode is active; no USB reset per save.`);
  } catch (error) {
    setConnection("Read failed", false);
    toast(`Read failed: ${error.message}`);
    await pollStatus();
  } finally {
    setBusy(false);
    updateChangeUI();
  }
}

async function stopSettings() {
  setBusy(true);
  setConnection("Leaving settings mode…", false);
  try {
    const resp = await fetch("/api/session/stop", {method: "POST", body: "{}"});
    const data = await resp.json();
    if (!resp.ok) throw new Error(data.error || `stop ${resp.status}`);
    sessionActive = false;
    els.exitSettings.hidden = true;
    setConnection(CACHE_HAS_VALUES ? "Cached values · click Read" : "Not read yet", false);
    toast("Settings mode closed; monitor restarted. One USB reset.");
  } catch (error) {
    toast(`Could not leave settings mode: ${error.message}`);
  } finally {
    setBusy(false);
    updateChangeUI();
  }
}

async function applyChanges() {
  const changes = changedSettings();
  if (!changes.length) return;
  const highRisk = changes.filter(s => s.risk === "high");
  if (highRisk.length && !window.confirm(
    `These high-risk settings will change: ${highRisk.map(s => s.label).join(", ")}. Continue?`
  )) return;
  const payload = {
    changes: changes.map(s => ({id: s.id, value: effectiveValue(s)})),
    confirmHighRisk: highRisk.length > 0,
  };
  setBusy(true);
  setConnection("Applying changes…", true);
  toast(`Applying ${changes.length} change${changes.length === 1 ? "" : "s"} — pausing monitor, reading clone, writing, verifying…`);
  try {
    const resp = await fetch("/api/apply", {
      method: "POST",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify(payload),
    });
    const data = await resp.json();
    if (!resp.ok) throw new Error(data.error || `apply ${resp.status}`);
    for (const change of changes) {
      change.value = effectiveValue(change);
      state.original.set(change.id, cloneValue(change.value));
    }
    state.edits.clear();
    CACHE_HAS_VALUES = true;
    renderList();
    updateChangeUI();
    updateSessionUI(Boolean(data.settingsMode));
    if (!data.settingsMode) setConnection("Cached values · click Read", false);
    const backup = data.backup ? " Backup saved." : "";
    const released = data.settingsMode ? "" : " Settings mode released.";
    toast(`Applied and verified ${data.verified || changes.length} change${changes.length === 1 ? "" : "s"}.${backup}${released}`);
    await pollStatus();
  } catch (error) {
    setConnection("Apply failed", false);
    toast(`Apply failed: ${error.message}`);
  } finally {
    setBusy(false);
    updateChangeUI();
  }
}

// Optional deep links for demos: ?q=backlight&category=display&advanced=1&changed=1
const params = new URLSearchParams(window.location.search);
if (params.get("q")) {
  state.search = params.get("q");
  els.search.value = state.search;
}
if (params.get("category") && (params.get("category") === "all" || CATEGORY_META[params.get("category")])) {
  state.category = params.get("category");
}
if (params.get("changed") === "1") {
  state.changedOnly = true;
  els.changedOnly.checked = true;
}
if (params.get("screen") === "1") {
  toggleScreen();
}
if (params.get("advanced") === "1") {
  state.advanced = true;
  document.body.classList.add("advanced");
  els.advanced.setAttribute("aria-pressed", "true");
  els.advanced.textContent = "Advanced on";
}

window.addEventListener("pagehide", () => {
  if (!sessionActive) return;
  try { navigator.sendBeacon("/api/session/stop", "{}"); } catch (error) { /* best effort */ }
});
setInterval(pollStatus, 15000);

els.screenToggle?.addEventListener("click", toggleScreen);
els.screenClose?.addEventListener("click", () => setScreenVisible(false));
els.screenModal?.addEventListener("click", (event) => {
  if (event.target === els.screenModal) setScreenVisible(false);
});
document.addEventListener("keydown", (event) => {
  if (event.key === "Escape" && screenVisible) setScreenVisible(false);
});
setInterval(pollMonitor, 1000);
renderCategories();
renderList();
updateChangeUI();
loadFromApi();
pollMonitor();
