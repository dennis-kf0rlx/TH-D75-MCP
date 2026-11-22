/* d75mon widget front-end: SSE with polling fallback. */
(() => {
  "use strict";

  const $ = (id) => document.getElementById(id);

  // Fields rendered as cards, in display order. Keys match backend POLL_SET.
  const CARDS = [
    ["vfo_a_offset", "VFO A OFFSET"],
    ["vfo_b_offset", "VFO B OFFSET"],
    ["audio_gain", "AUDIO GAIN"],
    ["tnc", "TNC BAND"],
    ["gps", "GPS STATUS"],
    ["backlight", "BACKLIGHT"],
    ["voice", "VOICE GUIDE"],
    ["vox", "VOX"],
    ["data_speed", "DATA SPEED"],
    ["fr", "FR"],
    ["ft", "FT"],
    ["gateway", "GATEWAY"],
    ["sd", "SD"],
    ["bs", "BS"],
    ["lc", "LC"],
    ["ds", "DS"],
    ["io", "IO"],
    ["vd", "VD"],
    ["bt", "BT"],
    ["gps_dst", "GPS DEST"],
    ["ps", "PS"],
    ["ms", "MS"],
    ["as", "AS"],
    ["ty", "TY"],
    ["ae", "AE"],
  ];

  let lastState = null;
  let lastFullRender = 0;
  let es = null;

  function fmtAge(sec) {
    if (sec === null || sec === undefined) return "--";
    if (sec < 60) return sec.toFixed(1) + "s ago";
    return (sec / 60).toFixed(1) + "m ago";
  }

  function clockText(fields) {
    const c = fields && fields.clock;
    if (!c) return "--";
    if (c.iso) {
      // show radio clock as HH:MM:SS (radio-local), plus date
      const t = c.iso.split("T");
      return t[1] + "  " + t[0];
    }
    return c.value || "--";
  }

  function fmtCard(key, fields) {
    const v = fieldValue(fields, key);
    if (v === "--" || !key.endsWith("_offset")) return v;
    const n = Number(v);
    if (!Number.isFinite(n)) return v;
    return n >= 1e6 ? (n / 1e6).toFixed(3) + " MHz" : (n / 1000).toFixed(1) + " kHz";
  }

  function fieldValue(fields, key) {
    const f = fields && fields[key];
    if (!f) return "--";
    if (f.error) return "ERR";
    return (f.value && String(f.value).trim()) || "--";
  }

  function bandLabel(hz) {
    const mhz = hz / 1e6;
    if (mhz >= 87.5 && mhz <= 108.0) return "FM RADIO";
    if (mhz >= 144.0 && mhz <= 148.0) return "2 m band";
    if (mhz >= 430.0 && mhz <= 450.0) return "70 cm band";
    return "VFO";
  }

  function renderLive(fields) {
    for (const band of ["a", "b"]) {
      const key = "vfo_" + band + "_hz";
      const f = fields && fields[key];
      const hz = f ? Number(f.value) : NaN;
      const el = $("freq-" + band);
      const sub = $("chan-" + band);
      if (Number.isFinite(hz) && hz > 0) {
        el.textContent = (hz / 1e6).toFixed(4);
        sub.textContent = bandLabel(hz) + " · live VFO " + band.toUpperCase();
      } else {
        el.textContent = "---.----";
        sub.textContent = "waiting for DDR read";
      }
    }
  }

  function render(state) {
    lastState = state;
    const connected = !!state.connected;
    const fields = state.fields || {};

    const badge = $("link-badge");
    badge.textContent = connected ? "ONLINE" : "OFFLINE";
    badge.className = "badge " + (connected ? "ok" : "bad");

    $("transport").textContent =
      state.transport ? state.transport.toUpperCase() + " · " + state.port : "--";
    $("fw").textContent = "FW " + fieldValue(fields, "firmware");

    $("callsign").textContent = fieldValue(fields, "callsign");
    $("clock").textContent = clockText(fields);
    renderLive(fields);
    $("last-update").textContent =
      (state.age_seconds === null || state.age_seconds === undefined)
        ? "--" : fmtAge(state.age_seconds);

    const err = $("error");
    if (state.last_error && !connected) {
      err.textContent = "error: " + state.last_error;
      err.classList.remove("hidden");
    } else if (state.last_error && connected) {
      err.textContent = "last warning: " + state.last_error;
      err.classList.remove("hidden");
    } else {
      err.classList.add("hidden");
    }

    // Cards and the raw table are heavy; refresh at most every 1.5 s while
    // the live frequency/RSSI above update on every SSE event (fast lane).
    const nowMs = Date.now();
    if (nowMs - lastFullRender > 1500) {
      lastFullRender = nowMs;

      const grid = $("fields");
      grid.innerHTML = "";
      for (const [key, label] of CARDS) {
        const div = document.createElement("div");
        div.className = "card";
        const l = document.createElement("label");
        l.textContent = label;
        const v = document.createElement("div");
        v.className = "val";
        v.textContent = fmtCard(key, fields);
        div.appendChild(l);
        div.appendChild(v);
        const raw = document.createElement("div");
        raw.className = "raw2";
        const f = fields[key];
        raw.textContent = f && f.raw ? f.raw : "";
        div.appendChild(raw);
        grid.appendChild(div);
      }

      const body = $("raw-body");
      body.innerHTML = "";
      const keys = Object.keys(fields).sort();
      for (const k of keys) {
        const f = fields[k];
        const tr = document.createElement("tr");
        for (const text of [k, f.cmd, f.error ? "ERR: " + f.error : (f.raw || "")]) {
          const td = document.createElement("td");
          td.textContent = text;
          tr.appendChild(td);
        }
        body.appendChild(tr);
      }
    }

    $("status-line").textContent = connected
      ? "radio connected · live DDR fast lane + CAT snapshot"
      : "waiting for radio (USB /dev/ttyACM0 or Bluetooth /dev/rfcomm0)";
  }

  function connectSSE() {
    if (es) es.close();
    es = new EventSource("/events");
    es.addEventListener("state", (ev) => {
      try { render(JSON.parse(ev.data)); } catch (e) { /* ignore */ }
    });
    es.onerror = () => {
      // EventSource retries automatically; also poll once in case SSE is blocked.
      fetchState();
    };
  }

  async function fetchState() {
    try {
      const r = await fetch("/state", { cache: "no-store" });
      if (!r.ok) throw new Error("HTTP " + r.status);
      render(await r.json());
    } catch (e) {
      $("status-line").textContent = "backend unreachable: " + e.message;
    }
  }


  // ---- LCD screen capture (framebuffer via DDR read) ----
  const screenBtn = $("screen-toggle");
  const screenWrap = $("screen-wrap");
  const screenImg = $("screen-img");
  const screenStatus = $("screen-status");
  let screenTimer = null;
  let screenOn = false;

  async function refreshScreen() {
    try {
      const r = await fetch("/screen.png?t=" + Date.now(), { cache: "no-store" });
      if (!r.ok) throw new Error("HTTP " + r.status);
      const blob = await r.blob();
      const url = URL.createObjectURL(blob);
      const old = screenImg.dataset.url;
      screenImg.src = url;
      screenImg.dataset.url = url;
      if (old) URL.revokeObjectURL(old);
      screenStatus.textContent = "live " + new Date().toLocaleTimeString();
    } catch (e) {
      screenStatus.textContent = "capture failed: " + e.message;
    }
  }

  screenBtn.addEventListener("click", () => {
    screenOn = !screenOn;
    screenWrap.classList.toggle("hidden", !screenOn);
    screenBtn.textContent = screenOn ? "HIDE SCREEN" : "SHOW SCREEN";
    if (screenOn) {
      refreshScreen();
      screenTimer = setInterval(refreshScreen, 2500);
    } else if (screenTimer) {
      clearInterval(screenTimer);
      screenTimer = null;
      screenStatus.textContent = "off";
    }
  });

  fetchState();
  connectSSE();
  setInterval(() => {
    if (!lastState || (lastState.age_seconds ?? 99) > 6) fetchState();
  }, 4000);
})();
