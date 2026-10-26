/* MDN Printer Service — logica interfeței.
   Vorbește cu Python prin window.pywebview.api; în browser (fără pywebview)
   pornește un mod demo cu date de exemplu, ca interfața să poată fi văzută. */
(function () {
  "use strict";

  const $ = (s, r) => (r || document).querySelector(s);
  const $$ = (s, r) => Array.from((r || document).querySelectorAll(s));
  const esc = (v) => String(v == null ? "" : v).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  const S = { lang: "ro", info: null, scan: null, sheet: null, flow: {}, tab: "overview", brand: "Toate", sel: null, models: [] };

  // ---------- traduceri ----------
  function t(key, vars) {
    const dict = window.I18N[S.lang] || window.I18N.ro;
    let s = dict[key] != null ? dict[key] : (window.I18N.ro[key] != null ? window.I18N.ro[key] : key);
    if (vars) Object.keys(vars).forEach((k) => { s = s.split("{" + k + "}").join(vars[k]); });
    return s;
  }
  function applyI18n() {
    document.documentElement.lang = S.lang;
    $$("[data-i18n]").forEach((el) => { el.textContent = t(el.dataset.i18n); });
    $$("[data-i18n-ph]").forEach((el) => { el.placeholder = t(el.dataset.i18nPh); });
    $$("#langChips .chip").forEach((b) => b.classList.toggle("on", b.dataset.lang === S.lang));
  }
  const LOC = { ro: "ro-RO", en: "en-GB", de: "de-DE", fr: "fr-FR", es: "es-ES", it: "it-IT", pt: "pt-PT", pl: "pl-PL", nl: "nl-NL", hu: "hu-HU", tr: "tr-TR", ru: "ru-RU" };
  const pct = (v) => (v == null || isNaN(v)) ? "—" : Number(v).toFixed(1).replace(".", S.lang === "en" ? "." : ",");
  const num = (v) => (v == null || isNaN(v)) ? "—" : Number(v).toLocaleString(LOC[S.lang] || "en-GB");
  // Un text de ghid în limba aplicației (ghidurile au toate cele 12 limbi; rezervă: engleză, română).
  const pick = (o) => o == null ? "" : (typeof o === "string" ? o : (o[S.lang] || o.en || o.ro || ""));

  // ---------- API ----------
  let api = null;
  function call(name, ...args) {
    return api[name](...args).then((r) => r || { ok: false, error: "empty" }).catch((e) => ({ ok: false, error: "exception", detail: String(e) }));
  }
  function errText(r) {
    const map = { license: "e_license", no_backup: "e_no_backup", unsupported: "e_unsupported", no_answer: "e_no_answer" };
    if (map[r.error]) return t(map[r.error]);
    return t("e_generic", { d: r.detail || r.error || "?" });
  }

  // ---------- UI helpers ----------
  let toastTimer = null;
  function toast(msg, bad) {
    const el = $("#toast");
    el.textContent = msg; el.classList.toggle("bad", !!bad); el.hidden = false;
    clearTimeout(toastTimer); toastTimer = setTimeout(() => { el.hidden = true; }, 4200);
  }
  function busy(btn, on) { if (btn) { btn.classList.toggle("busy", on); btn.disabled = on; } }
  function modal(opts) {
    return new Promise((resolve) => {
      $("#modalTitle").textContent = opts.title;
      $("#modalBody").innerHTML = opts.body || "";
      const actions = $("#modalActions"); actions.innerHTML = "";
      (opts.buttons || [{ label: t("ok"), value: true, primary: true }]).forEach((b) => {
        const el = document.createElement("button");
        el.type = "button"; el.className = "btn" + (b.primary ? " primary" : "");
        el.textContent = b.label;
        el.onclick = () => {
          const form = {};
          $$("#modalBody [name]").forEach((i) => { form[i.name] = i.value; });
          $("#modal").hidden = true; resolve(b.value ? (opts.form ? form : true) : null);
        };
        actions.appendChild(el);
      });
      $("#modal").hidden = false;
      const first = $("#modalBody input, #modalBody textarea") || actions.lastChild;
      setTimeout(() => first && first.focus(), 30);
    });
  }
  const clientFields = (pre) => `
    <div class="field"><label for="f-client">${esc(t("client"))}</label><input id="f-client" name="client" value="${esc((pre || {}).client || "")}"></div>
    <div class="field"><label for="f-contact">${esc(t("contact"))}</label><input id="f-contact" name="contact" value="${esc((pre || {}).client_contact || "")}"></div>
    <div class="field"><label for="f-notes">${esc(t("notes"))}</label><textarea id="f-notes" name="notes">${esc((pre || {}).notes || "")}</textarea></div>`;

  // ---------- navigare ----------
  function show(view) {
    $$(".view").forEach((v) => v.classList.toggle("on", v.id === "view-" + view));
    $$(".nav-item").forEach((b) => b.classList.toggle("on", b.dataset.view === view || (view === "sheet" && b.dataset.view === "printers")));
    if (view === "models") loadModels();
    if (view === "history") loadHistory();
    if (view === "settings") renderSettings();
    $(".views").scrollTop = 0;
  }
  document.addEventListener("click", (e) => {
    const v = e.target.closest("[data-view]");
    if (v) { show(v.dataset.view); return; }
    const f = e.target.closest("[data-folder]");
    if (f) call("open_folder", f.dataset.folder);
    const l = e.target.closest("[data-lang]");
    if (l) setLang(l.dataset.lang);
  });

  // ---------- licență ----------
  function renderLic() {
    const L = (S.info && S.info.license) || {};
    $("#licDot").className = "dot " + (L.active ? "ok" : "warn");
    $("#licTitle").textContent = L.active ? t("lic_active") : t("lic_inactive");
    $("#licSub").textContent = L.active ? t("lic_sub", { key: L.key_hint || "" }) : t("lic_inactive_sub");
  }
  function renderSettings() {
    const L = (S.info && S.info.license) || {};
    const box = $("#licBox");
    if (L.active) {
      box.innerHTML = `<p class="small">${esc(t("lic_ok_text"))}</p>
        <dl class="dl" style="grid-template-columns:repeat(2,minmax(0,1fr));margin-top:10px">
          <div><dt>${esc(t("lic_key"))}</dt><dd>${esc(L.key_hint || "")}</dd></div>
          <div><dt>${esc(t("lic_machine", { m: "" }).replace(":", ""))}</dt><dd>${esc(L.machine)}</dd></div></dl>
        <div class="actions-row"><button type="button" class="btn" id="btnLicCheck">${esc(t("lic_check"))}</button></div>`;
      $("#btnLicCheck").onclick = async (e) => { busy(e.target, true); const r = await call("license_state", true); busy(e.target, false); S.info.license = r; renderLic(); renderSettings(); };
    } else {
      box.innerHTML = `<p class="small">${esc(t("lic_text"))}</p>
        <div class="lic-form">
          <label for="licKey">${esc(t("lic_key"))}</label>
          <input id="licKey" autocomplete="off" spellcheck="false" placeholder="MDN-XXXX-XXXX-XXXX">
          <button type="button" class="btn primary" id="btnActivate" style="height:48px">${esc(t("activate"))}</button>
          <span class="err" id="licErr" role="alert"></span>
          <div class="note">${esc(t("lic_note", { p: S.info.price, e: S.info.email }))}</div>
          <span class="muted">${esc(t("lic_machine", { m: L.machine || "" }))}</span>
        </div>`;
      $("#btnActivate").onclick = async (e) => {
        const key = $("#licKey").value.trim();
        if (!key) return;
        busy(e.target, true);
        const r = await call("activate", key);
        busy(e.target, false);
        if (r.ok) { S.info.license = r; renderLic(); renderSettings(); toast(t("lic_active")); }
        else $("#licErr").textContent = t("le_" + r.error) !== "le_" + r.error ? t("le_" + r.error) : t("le_unknown");
      };
    }
    $("#langChips").innerHTML = Object.entries(window.LANG_NAMES).map(([k, n]) => `<button type="button" class="chip" data-lang="${k}" lang="${k}">${esc(n)}</button>`).join("");
    if (S.info.linux_usb !== null && S.info.linux_usb !== undefined) {
      $("#usbBox").hidden = false;
      $("#usbBox").innerHTML = `<h2 class="mt">${esc(t("usb_linux_title"))}</h2><p class="small">${esc(t("usb_linux_text"))}</p>
        <button type="button" class="btn" id="btnUsb">${esc(t("usb_linux_btn"))}</button>`;
      $("#btnUsb").onclick = async (e) => { busy(e.target, true); const r = await call("linux_usb", true); busy(e.target, false); toast(t(r.ready ? "usb_linux_ok" : "usb_linux_fail"), !r.ready); };
    }
    $("#aboutText").textContent = t("about", { v: S.info.version });
    $("#aboutDocs").innerHTML = [["manual", "doc_manual"], ["eula", "doc_eula"], ["privacy", "doc_privacy"], ["terms", "doc_terms"]]
      .map(([k, l]) => `<button type="button" class="btn" data-doc="${k}">${esc(t(l))}</button>`).join("");
    $$("[data-doc]").forEach((b) => b.onclick = () => call("open_doc", b.dataset.doc));
    applyI18n();
  }
  async function setLang(lang) {
    S.lang = lang; await call("set_lang", lang); applyI18n(); renderLic();
    if (U.info) { renderUpdBox(t("upd_avail", { v: U.info.version })); if (!$("#updBar").hidden) call("update_progress").then(renderUpdBar); } else renderUpdBox("");
    if (S.scan) renderScan(); if (S.sheet) renderSheet();
    if ($("#view-settings").classList.contains("on")) renderSettings();
    if ($("#view-models").classList.contains("on")) loadModels();
    if ($("#view-history").classList.contains("on")) loadHistory();
  }

  // ---------- detectare ----------
  async function scan() {
    const btn = $("#btnScan"); busy(btn, true);
    $("#scanLead").textContent = t("printers_lead");
    $("#printerRows").innerHTML = `<div class="scanning">${esc(t("scanning"))}</div>`;
    const r = await call("scan", true);
    busy(btn, false);
    if (!r.ok) { $("#printerRows").innerHTML = `<div class="empty">${esc(errText(r))}</div>`; return; }
    S.scan = r; renderScan();
  }
  function renderScan() {
    const r = S.scan;
    $("#scanLead").textContent = t("printers_lead_done");
    const rows = [];
    (r.printers || []).forEach((p, i) => {
      const can = p.support === "auto" ? t("can_auto") : p.support === "box" ? t("can_box") : t("can_temp");
      const st = p.identify_error ? `<span class="state na">${esc(t("st_no_answer"))}</span>` : `<span class="state ok">${esc(t("st_found"))}</span>`;
      const conn = p.connection === "USB" ? "USB" : `Wi-Fi, ${esc(p.ip || "")}`;
      rows.push(`<div class="trow"><div class="name"><b>Epson ${esc(p.model || p.raw_model || "?")}</b><small>${esc(p.raw_model || "")}</small></div>
        <span>${conn}</span>${st}<span>${esc(can)}</span>
        <button type="button" class="btn ${i === 0 ? "dark" : ""} go" data-open="${esc(p.handle)}">${esc(t("open_sheet"))}</button></div>`);
    });
    (r.others || []).forEach((p) => {
      rows.push(`<div class="trow"><div class="name"><b>${esc(p.brand)} ${esc(p.model)}</b><small>${esc(t("installed_windows"))}: ${esc(p.name)}</small></div>
        <span>${esc(p.connection || "—")}</span><span class="state na">${esc(t("st_unknown"))}</span><span>${esc(t("can_guide"))}</span>
        <button type="button" class="btn go" data-guide="${esc(p.brand)}|${esc(p.model)}">${esc(t("see_guide"))}</button></div>`);
    });
    $("#printerRows").innerHTML = rows.join("") || `<div class="empty">${esc(t("no_printers"))}</div>`;
    $$("[data-open]").forEach((b) => b.onclick = () => openPrinter(b.dataset.open, b));
    $$("[data-guide]").forEach((b) => b.onclick = () => { const [br, m] = b.dataset.guide.split("|"); S.brand = br; S.sel = br + "|" + m; show("models"); });
  }

  // ---------- fișa ----------
  async function openPrinter(handle, btn) {
    busy(btn, true);
    const r = await call("open_printer", handle);
    busy(btn, false);
    if (!r.ok) { toast(errText(r), true); return; }
    S.sheet = r; S.flow = { backup: null, done: null }; S.tab = "overview";
    renderSheet(); show("sheet");
  }
  function padInfo(d) {
    const w = d.waste || null;
    const main = w ? (w.main_waste != null ? w.main_waste : w.first_waste) : null;
    const border = w ? (w.borderless_waste != null ? w.borderless_waste : w.second_waste) : null;
    return { main, border };
  }
  function renderSheet() {
    const d = S.sheet; if (!d) return;
    const { main, border } = padInfo(d);
    const fam = d.db_model && d.model && d.db_model !== d.model ? d.db_model : null;
    $("#h-sheet").textContent = "Epson " + (d.model || d.raw_model || "");
    $("#sheetMeta").innerHTML = [
      fam ? esc(t("series", { f: fam })) : "",
      esc(t("connected_via", { c: d.connection === "USB" ? "USB" : "Wi-Fi" + (d.ip ? " (" + d.ip + ")" : "") })),
      d.serial ? esc(t("serial")) + " " + esc(d.serial) : ""
    ].filter(Boolean).map((x) => `<span>${x}</span>`).join("");

    // tampon
    const done = S.flow.done === "reset";
    const shown = done ? (S.flow.after ? padInfo({ waste: S.flow.after }).main : 0) : main;
    const shownB = done ? (S.flow.after ? padInfo({ waste: S.flow.after }).border : 0) : border;
    $("#padPct").textContent = pct(shown);
    $("#padBorder").textContent = shownB == null ? "—" : pct(shownB) + " %";
    const scale = Math.max(100, shown || 0) * 1.08;
    requestAnimationFrame(() => { $("#padFill").style.width = Math.min(100, ((shown || 0) / scale) * 100) + "%"; });
    $("#padLimit").style.left = (100 / scale) * 100 + "%";
    $("#padImg").setAttribute("aria-label", t("pad_main") + " " + pct(shown) + " %");
    const stw = $("#padState");
    let state = "na", word = t("pad_na"), msg = t("msg_na");
    if (shown != null) {
      if (done) { state = "ok"; word = t("pad_reset"); msg = t("msg_reset"); }
      else if (shown >= 100) { state = "warn"; word = t("pad_full"); msg = t("msg_full"); }
      else if (shown >= 85) { state = "warn"; word = t("pad_near"); msg = t("msg_near"); }
      else { state = "ok"; word = t("pad_ok"); msg = t("msg_ok"); }
    }
    if (d.support === "box") {
      const b = (d.box && d.box.state) || "unknown";
      state = b === "ok" ? "ok" : b === "unknown" ? "na" : "warn";
      word = t({ ok: "box_ok", near: "box_near", full: "box_full" }[b] || "pad_na");
      msg = t({ ok: "msg_box_ok", near: "msg_box_near", full: "msg_box_full" }[b] || "msg_box_ok");
      $("#padPct").textContent = "—"; $("#padBorder").textContent = "—";
    } else if (d.support !== "auto") msg = S.flow.done === "temp" ? t("msg_reset") : t("msg_temp");
    if (S.flow.backup && !done && d.support === "auto") msg = t("msg_backup");
    stw.className = "state-word " + state; stw.textContent = word;
    $("#sheetMsg").textContent = msg;
    renderSteps(d);

    // LED-uri
    const leds = done || S.flow.done === "temp" ? { power: "on", ink: "off", paper: "off", reason: "after" } : (d.leds || {});
    const setLed = (id, v, color) => { const el = $(id); el.className = "led" + (v === "on" ? " " + color : v === "blink" ? " " + color + " blink" : ""); };
    setLed("#ledPower", leds.power || "on", "green");
    setLed("#ledWifi", d.connection === "USB" ? "off" : "on", "green");
    setLed("#ledInk", leds.ink, "amber"); setLed("#ledPaper", leds.paper, "amber");
    $("#ledText").textContent = t({ waste_full: "led_waste_full", paper: "led_paper_t", ink: "led_ink_t", after: "led_after" }[leds.reason] || "led_ok");

    // cerneală
    const inks = (d.status && d.status.inks) || [];
    const colors = { Black: "#1F2328", Cyan: "#0EA5E9", Magenta: "#DB2777", Yellow: "#EAB308", "Photo Black": "#111", "Light Cyan": "#67E8F9", "Light Magenta": "#F9A8D4" };
    const names = { ro: { Black: "Negru", Cyan: "Cyan", Magenta: "Magenta", Yellow: "Galben" }, en: {} };
    $("#inkGrid").innerHTML = inks.length && inks.some((i) => i.level > 0 && i.level <= 100)
      ? inks.map((i) => `<div class="ink"><div class="tank"><i style="height:${Math.max(0, Math.min(100, i.level))}%;background:${colors[i.color] || "#64748B"}"></i></div>
          <span class="${i.level < 20 ? "warn-t" : ""}">${esc((names[S.lang] || {})[i.color] || i.color)} ${esc(i.level)}%</span></div>`).join("")
      : `<p class="ink-note">${esc(t("inks_none"))}</p>`;
    renderTab();
  }
  function renderSteps(d) {
    const f = S.flow, L = (S.info && S.info.license) || {};
    const li = [];
    li.push(`<li><div class="step done"><span class="n">1</span>${esc(t("step_read"))}</div></li>`);
    if (d.support === "auto") {
      li.push(f.backup ? `<li><div class="step done"><span class="n">2</span>${esc(t("step_backup_done"))}</div></li>`
        : `<li><button type="button" class="step act" id="stepBackup"><span class="n">2</span>${esc(t("step_backup"))}</button></li>`);
      if (f.done === "reset") li.push(`<li><div class="step done"><span class="n">3</span>${esc(t("step_reset_done"))}</div></li>`);
      else if (f.backup) li.push(`<li><button type="button" class="step act" id="stepReset"><span class="n">3</span>${esc(t("step_reset"))}</button></li>`);
      else li.push(`<li><div class="step lock"><span class="n">3</span>${esc(t("step_reset_lock"))}</div></li>`);
    } else if (d.support === "box") {
      li.push(`<li><div class="step done"><span class="n">2</span>${esc(t("step_box"))}</div></li>`);
    } else {
      li.push(f.done === "temp" ? `<li><div class="step done"><span class="n">2</span>${esc(t("step_temp_done"))}</div></li>`
        : `<li><button type="button" class="step act" id="stepTemp"><span class="n">2</span>${esc(t("step_temp"))}</button></li>`);
    }
    $("#steps").innerHTML = li.join("");
    const needLic = () => { if (!L.active) { toast(t("e_license"), true); show("settings"); return true; } return false; };
    const sb = $("#stepBackup"); if (sb) sb.onclick = async () => {
      if (needLic()) return;
      sb.classList.add("busy"); sb.disabled = true;
      const r = await call("backup", d.handle);
      if (!r.ok) { sb.classList.remove("busy"); sb.disabled = false; toast(errText(r), true); return; }
      S.flow.backup = r.path; toast(t("toast_backup")); renderSheet();
    };
    const sr = $("#stepReset"); if (sr) sr.onclick = async () => {
      if (needLic()) return;
      const form = await modal({ title: t("reset_title"), body: `<p>${esc(t("reset_text"))}</p>` + clientFields(), form: true,
        buttons: [{ label: t("cancel") }, { label: t("do_reset"), value: true, primary: true }] });
      if (!form) return;
      sr.classList.add("busy"); sr.disabled = true;
      const r = await call("reset", d.handle, form.client, form.contact, form.notes);
      if (!r.ok) { sr.classList.remove("busy"); sr.disabled = false; toast(r.error ? errText(r) : t("e_reset_refused"), true); return; }
      S.flow.done = "reset"; S.flow.after = r.waste_after; S.flow.job = r.job_id;
      toast(t("toast_reset")); renderSheet();
    };
    const st = $("#stepTemp"); if (st) st.onclick = () => tempUnlock(d, st);
  }
  async function tempUnlock(d, btn) {
    const L = (S.info && S.info.license) || {};
    if (!L.active) { toast(t("e_license"), true); show("settings"); return; }
    const form = await modal({ title: t("temp_title"), body: `<p>${esc(t("temp_text"))}</p>` + clientFields(), form: true,
      buttons: [{ label: t("cancel") }, { label: t("do_temp"), value: true, primary: true }] });
    if (!form) return;
    if (btn) { btn.classList.add("busy"); btn.disabled = true; }
    const r = await call("temporary_unlock", d.handle, form.client, form.contact, form.notes);
    if (btn) { btn.classList.remove("busy"); btn.disabled = false; }
    if (!r.ok) { toast(r.error ? errText(r) : t("e_temp_refused"), true); return; }
    S.flow.done = "temp"; S.flow.job = r.job_id; toast(t("toast_temp")); renderSheet();
  }

  const ST_RO = { 0: "Eroare", 1: "Printează pagina de test", 2: "Ocupată", 3: "Așteaptă", 4: "Gata de printare", 5: "Pauză", 7: "Curăță capul", 8: "Neinițializată", 10: "Se oprește", 15: "Test duze", 17: "Încarcă cerneala" };
  const ERR_RO = [["ink overflow", "Tampon de cerneală uzată plin"], ["paper jam", "Hârtie blocată"], ["paper out", "Lipsă hârtie"], ["ink out", "Cerneală terminată"], ["cover open", "Capac deschis"], ["maintenance request", "Cere întreținere"], ["fatal", "Eroare gravă"], ["double feed", "A tras două foi"]];
  function statusText(s) {
    if (!s) return null;
    if (S.lang === "ro" && s.code != null && ST_RO[s.code]) return ST_RO[s.code];
    return s.text;
  }
  function errorText(e) {
    if (!e || S.lang !== "ro") return e;
    const hit = ERR_RO.find(([k]) => String(e).toLowerCase().includes(k));
    return hit ? hit[1] + " (" + e + ")" : e;
  }
  function renderTab() {
    $$("#tabs [data-tab]").forEach((b) => b.setAttribute("aria-selected", String(b.dataset.tab === S.tab)));
    const d = S.sheet, st = d.stats || {}, body = $("#tabBody");
    const row = (k, v, cls) => `<div><dt>${esc(k)}</dt><dd class="${cls || ""}">${v == null || v === "" ? "—" : esc(v)}</dd></div>`;
    if (S.tab === "overview") {
      body.innerHTML = `<dl class="dl">
        ${row(t("f_model"), d.raw_model)}${row(t("f_firmware"), d.firmware)}
        ${row(d.ip ? t("f_ip") : t("f_mac"), d.ip || d.mac)}${row(t("f_first"), st["First TI received time"])}
        ${row(t("f_pages"), st["Total print page counter"] != null ? num(st["Total print page counter"]) : null)}
        ${row(t("f_scans"), st["Total scan counter"] != null ? num(st["Total scan counter"]) : null)}
        ${row(t("f_status"), statusText(d.status))}
        ${row(t("f_support"), (d.support === "auto" ? t("can_auto") : d.support === "box" ? t("can_box") : t("can_temp")) + (d.support === "auto" ? (d.tested ? ", " + t("f_tested") : ", " + t("f_untested")) : ""), d.support === "auto" || d.support === "box" ? "good" : "warn-t")}
      </dl>`;
    } else if (S.tab === "counters") {
      const keys = Object.keys(st);
      body.innerHTML = keys.length ? `<dl class="dl">${keys.map((k) => row(k, typeof st[k] === "number" ? num(st[k]) : st[k])).join("")}</dl>` : `<p class="small">—</p>`;
    } else if (S.tab === "errors") {
      const s = d.status || {}, parts = [];
      if (s.error) parts.push(`<p class="small"><b class="warn-t">${esc(errorText(s.error))}</b></p>`);
      if ((s.warnings || []).length) parts.push(`<p class="small"><b>${esc(t("warnings"))}:</b> ${esc(s.warnings.join(", "))}</p>`);
      if ((d.fatal_errors || []).length) parts.push(`<p class="small"><b>${esc(t("fatal_codes"))}:</b> ${esc(d.fatal_errors.join(" "))}</p>`);
      body.innerHTML = parts.join("") || `<p class="small">${esc(t("no_errors"))}</p>`;
    } else if (S.tab === "memory") {
      body.innerHTML = `<p class="small">${S.flow.backup ? esc(t("backup_saved")) + " " + esc(S.flow.backup) : esc(t("backup_none"))}</p>
        <div class="actions-row">
          ${d.support === "auto" ? `<button type="button" class="btn" id="btnRestore">${esc(t("restore"))}</button>` : ""}
          ${d.support === "box" ? "" : `<button type="button" class="btn" id="btnTemp">${esc(t("temp_unlock"))}</button>`}
          <button type="button" class="btn" data-folder="backup">${esc(t("open_backups"))}</button>
        </div>`;
      const br = $("#btnRestore"); if (br) br.onclick = async () => {
        busy(br, true); const r = await call("restore", d.handle); busy(br, false);
        if (r.ok) { S.flow.after = r.waste_after; toast(t("toast_saved")); reread(); } else if (r.error !== "cancelled") toast(errText(r), true);
      };
      if ($("#btnTemp")) $("#btnTemp").onclick = (e) => tempUnlock(d, e.target);
    } else if (S.tab === "jobs") {
      body.innerHTML = `<p class="small">…</p>`;
      call("history_list", d.serial || "").then((r) => {
        const items = (r.items || []).filter((j) => !d.serial || j.serial === d.serial);
        body.innerHTML = items.length ? `<ul class="list">${items.map((j) => `<li>${esc(fmtDate(j.created))}: ${esc(t("k_" + j.kind))}${j.client ? ", " + esc(j.client) : ""}</li>`).join("")}</ul>` : `<p class="small">${esc(t("no_jobs"))}</p>`;
      });
    }
  }
  $("#tabs").addEventListener("click", (e) => { const b = e.target.closest("[data-tab]"); if (b) { S.tab = b.dataset.tab; renderTab(); } });
  async function reread() {
    const btn = $("#btnReread"); busy(btn, true);
    const r = await call("open_printer", S.sheet.handle); busy(btn, false);
    if (!r.ok) { toast(errText(r), true); return; }
    const keep = S.flow; S.sheet = r; S.flow = keep.done ? { backup: keep.backup } : keep; renderSheet();
  }
  $("#btnReread").onclick = reread;
  $("#btnCheckReport").onclick = async (e) => {
    let job = S.flow.job;
    if (!job) {
      const form = await modal({ title: t("check_title"), body: `<p>${esc(t("check_text"))}</p>` + clientFields(), form: true,
        buttons: [{ label: t("cancel") }, { label: t("report_pdf"), value: true, primary: true }] });
      if (!form) return;
      const r = await call("save_check", S.sheet.handle, form.client, form.contact, form.notes);
      if (!r.ok) { toast(errText(r), true); return; }
      job = r.job_id;
    }
    busy(e.target, true); const r = await call("report", job, true); busy(e.target, false);
    r.ok ? toast(t("toast_report")) : toast(errText(r), true);
  };

  // ---------- baza de modele ----------
  let searchTimer = null;
  $("#modelSearch").addEventListener("input", () => { clearTimeout(searchTimer); searchTimer = setTimeout(loadModels, 180); });
  async function loadModels() {
    const brands = ["Toate", "Epson", "Canon", "Brother"];
    $("#brandChips").innerHTML = brands.map((b) => `<button type="button" class="chip ${b === S.brand ? "on" : ""}" data-brand="${b}" aria-pressed="${b === S.brand}">${esc(b === "Toate" ? t("all") : b)}</button>`).join("");
    $$("#brandChips [data-brand]").forEach((b) => b.onclick = () => { S.brand = b.dataset.brand; loadModels(); });
    const r = await call("models_search", $("#modelSearch").value, S.brand);
    S.models = r.items || [];
    const c = (S.info && S.info.models) || {};
    $("#modelsLead").textContent = t("models_lead", { e: c.Epson || 0, c: c.Canon || 0, b: c.Brother || 0, n: r.total || 0 });
    const key = (m) => m.brand + "|" + m.model;
    if (!S.sel || !S.models.some((m) => key(m) === S.sel)) S.sel = S.models[0] ? key(S.models[0]) : null;
    $("#modelList").innerHTML = S.models.map((m) => `<button type="button" class="model-item ${key(m) === S.sel ? "on" : ""}" data-sel="${esc(key(m))}">
      <span><b>${esc(m.brand)} ${esc(m.model)}</b><span class="muted">${esc((m.aliases || []).slice(0, 5).join(", "))}</span></span>
      <span class="badge ${esc(m.mode)}">${esc(t("mode_" + m.mode))}</span></button>`).join("") || `<div class="empty">—</div>`;
    $$("#modelList [data-sel]").forEach((b) => b.onclick = () => { S.sel = b.dataset.sel; $$("#modelList .model-item").forEach((x) => x.classList.toggle("on", x === b)); renderModel(); });
    renderModel();
  }
  function renderModel() {
    const box = $("#modelDetail");
    const m = S.models.find((x) => x.brand + "|" + x.model === S.sel);
    if (!m) { box.innerHTML = `<p class="small">${esc(t("pick_model"))}</p>`; return; }
    if (m.mode !== "guide") {
      box.innerHTML = `<div class="row-between"><h2>${esc(m.brand)} ${esc(m.model)}</h2><span class="badge ${esc(m.mode)}">${esc(t("mode_" + m.mode))}</span></div>
        <p class="small">${esc(t(m.mode === "auto" ? "m_auto_text" : "m_temp_text"))}</p>
        ${(m.aliases || []).length ? `<p class="small">${esc(t("m_also", { a: m.aliases.join(", ") }))}</p>` : ""}
        <p class="small ${m.tested ? "good" : ""}">${esc(m.tested ? t("m_tested", { d: m.tested }) : t("m_untested"))}</p>`;
      return;
    }
    const g = m.guide || {}, free = (g.steps && pick(g.steps)) || null;
    const warnTxt = pick(g.warning);
    const early = g.confidence === "unverified" && (g.steps_n || 0) > 0;
    box.innerHTML = `<div class="row-between"><div><h2>${esc(m.brand)} ${esc(m.model)}</h2>
        ${g.errors ? `<span class="muted">${esc(t("errors_codes"))}: ${esc(pick(g.errors))}</span>` : ""}</div><span class="badge guide">${esc(t("mode_guide"))}</span></div>
      <p class="small">${esc(pick(g.intro) || t("guide_intro"))}</p>
      ${early && warnTxt ? `<p class="warnbox"><b>${esc(t("warning"))}:</b> ${esc(warnTxt)}</p>` : ""}
      <div id="guideSteps">${g.steps_n ? `<p class="small muted">${esc(t("g_steps_n", { n: g.steps_n }))}</p>` : ""}</div>
      ${g.tool ? `<p class="small"><b>${esc(t("tool_needed"))}:</b> ${esc(pick(g.tool))}</p>` : ""}
      ${!early && warnTxt ? `<p class="small warn-t"><b>${esc(t("warning"))}:</b> ${esc(warnTxt)}</p>` : ""}
      ${g.confidence && g.confidence !== "high" ? `<p class="small muted">${esc(t("conf_" + g.confidence))}</p>` : ""}
      ${(m.aliases || []).length ? `<p class="small">${esc(t("m_also", { a: m.aliases.join(", ") }))}</p>` : ""}
      <div class="row-between" style="margin-top:auto;padding-top:14px;border-top:1px solid #E2E7EC">
        <span class="src">${esc(t("source"))}: ${(g.sources || []).map((x) => esc(x)).join("; ") || "—"}</span>
        <span class="head-actions"><button type="button" class="btn" id="btnPrintGuide">${esc(t("print_guide"))}</button>
        ${m.brand === "Canon" ? `<button type="button" class="btn primary" id="btnCanon">${esc(t("ca_start"))}</button>` : ""}
        <button type="button" class="btn ${m.brand === "Canon" ? "" : "primary"}" id="btnGuideDone">${esc(t("guide_done"))}</button></span></div>`;
    const showSteps = (steps) => { $("#guideSteps").innerHTML = `<ol class="guide-steps">${steps.map((x) => `<li><span>${esc(x)}</span></li>`).join("")}</ol>`; };
    m._steps = null;
    if (free) { m._steps = free; showSteps(free); }
    else if (g.steps_n) {
      const lic = (S.info && S.info.license) || {};
      if (!lic.active) {
        $("#guideSteps").innerHTML = `<div class="lockbox"><p>${esc(t("g_locked"))}</p><button type="button" class="btn primary" data-view="settings">${esc(t("g_locked_btn"))}</button></div>`;
      } else {
        $("#guideSteps").innerHTML = `<p class="small muted">${esc(t("g_loading"))}</p>`;
        const sel = S.sel;
        call("guide_steps", m.brand, m.model).then((r) => {
          if (S.sel !== sel) return;
          if (r.ok) { m._steps = r.steps || []; showSteps(m._steps); }
          else $("#guideSteps").innerHTML = `<p class="warnbox">${esc(t(r.error === "license" ? "g_locked" : "g_offline"))}</p>`;
        });
      }
    }
    $("#btnPrintGuide").onclick = () => window.print();
    if ($("#btnCanon")) $("#btnCanon").onclick = () => {
      const lic = (S.info && S.info.license) || {};
      if (!lic.active) { toast(t("e_license"), true); show("settings"); return; }
      canonStart(m);
    };
    $("#btnGuideDone").onclick = async () => {
      const form = await modal({ title: t("edit_title"), body: clientFields(), form: true, buttons: [{ label: t("cancel") }, { label: t("save"), value: true, primary: true }] });
      if (!form) return;
      const r = await call("save_guide_job", m.brand, m.model, form.client, form.contact, form.notes);
      r.ok ? toast(t("toast_saved")) : toast(errText(r), true);
    };
  }

  // ---------- asistentul Canon ----------
  // Nu trimite comenzi imprimantei: urmărește doar lista dispozitivelor USB din Windows.
  // Prefixul pașilor de intrare în modul service, în fiecare limbă.
  const SVC = /^(Modul service|Service mode|Servicemodus|Mode service|Modo de servicio|Modalità di servizio|Modo de serviço|Tryb serwisowy|Szervizmód|Servis modu|Сервисный режим)\s*:\s*/i;
  let caTimer = null;
  function canonStop() { clearInterval(caTimer); caTimer = null; }
  async function canonStart(m) {
    const g = m.guide || {}, all = m._steps || [];
    S.ca = {
      m, g, stage: 0, cur: 0,
      svc: all.filter((s) => SVC.test(s)).map((s) => s.replace(SVC, "")),
      rest: all.filter((s) => !SVC.test(s)),
      prep: {}, done: {}, base: null, usb: { state: "none", devices: [] }, service: null,
      printers: [], printer: "", maint: false,
    };
    $("#h-canon").textContent = t("ca_title", { m: m.model });
    show("canon");
    const r = await call("canon_usb");
    S.ca.usb = { state: (r.devices || []).length ? "new" : "none", devices: r.devices || [] };
    const p = await call("canon_printers");
    S.ca.printers = p.printers || [];
    S.ca.printer = (S.ca.printers[0] || {}).name || "";
    canonRender();
    caTimer = setInterval(canonPoll, 1500);
  }
  async function canonPoll() {
    const A = S.ca; if (!A || !$("#view-canon").classList.contains("on")) { canonStop(); return; }
    const r = A.base ? await call("canon_compare", A.base) : await call("canon_usb");
    if (!r.ok) return;
    A.usb = A.base ? r : { state: (r.devices || []).length ? "new" : "none", devices: r.devices || [] };
    if (A.base && r.state === "changed" && !A.service) {
      A.service = { mode: "auto", from: (r.from || []).join(","), to: (r.to || []).join(",") };
      toast(t("ca_svc_detected_toast"));
      canonRender();
    }
    canonUsb();
  }
  function canonUsb() {
    const A = S.ca, u = A.usb || {}, devs = u.devices || [];
    const label = { none: "ca_usb_none", same: "ca_usb_same", changed: "ca_usb_changed", new: "ca_usb_found" }[u.state] || "ca_usb_none";
    const cls = u.state === "changed" ? "ok" : (u.state === "none" ? "warn" : "info");
    $("#caUsb").innerHTML = `<div class="ca-state ${cls}"><span class="ca-dot"></span>${esc(t(label))}</div>
      ${devs.map((d) => `<div class="ca-dev"><b>Canon</b> <code>04A9:${esc(d.pid)}</code>${d.name ? `<br><span>${esc(d.name)}</span>` : ""}</div>`).join("")}
      ${A.base ? `<p class="small">${esc(t("ca_usb_base", { p: A.base.map((d) => "04A9:" + d.pid).join(", ") || "—" }))}</p>` : ""}
      <p class="small">${esc(t("ca_usb_note"))}</p>`;
  }
  function canonRender() {
    const A = S.ca, names = ["ca_s1", "ca_s2", "ca_s3", "ca_s4"];
    $("#caStepper").innerHTML = names.map((n, i) => `<li class="${i < A.stage ? "done" : ""} ${i === A.stage ? "on" : ""}"><span>${i + 1}</span>${esc(t(n))}</li>`).join("");
    const box = $("#caMain"), warn = pick(A.g.warning);
    const nav = (back, next, nextOk, nextLabel) => `<div class="ca-nav">
      ${back ? `<button type="button" class="btn" id="caPrev">${esc(t("ca_prev"))}</button>` : "<span></span>"}
      ${next ? `<button type="button" class="btn primary" id="caNext" ${nextOk ? "" : "disabled"}>${esc(nextLabel || t("ca_next"))}</button>` : ""}</div>`;
    if (A.stage === 0) {
      const items = ["ca_p_pad", "ca_p_usb", "ca_p_tool", "ca_p_paper"];
      box.innerHTML = `<h2>${esc(t("ca_s1"))}</h2><p class="small">${esc(t("ca_p_lead"))}</p>
        <div class="ca-checks">${items.map((k) => `<label class="ca-check"><input type="checkbox" data-prep="${k}" ${A.prep[k] ? "checked" : ""}><span>${esc(t(k))}</span></label>`).join("")}</div>
        ${warn ? `<p class="warnbox"><b>${esc(t("warning"))}:</b> ${esc(warn)}</p>` : ""}
        ${A.g.tool ? `<p class="small"><b>${esc(t("tool_needed"))}:</b> ${esc(pick(A.g.tool))}</p>` : ""}
        ${nav(false, true, A.prep.ca_p_pad && A.prep.ca_p_usb, t("ca_to_svc"))}`;
      $$("[data-prep]").forEach((c) => c.onchange = () => { A.prep[c.dataset.prep] = c.checked; canonRender(); });
    } else if (A.stage === 1) {
      const n = A.svc.length, s = A.svc[A.cur] || "";
      const secs = (s.match(/(\d+)\s*(secunde|seconds|s\b)/i) || [])[1];
      box.innerHTML = `<h2>${esc(t("ca_s2"))}</h2>
        ${A.service ? `<div class="okbox"><b>${esc(t(A.service.mode === "auto" ? "ca_svc_auto" : "ca_svc_manual"))}</b>${A.service.mode === "auto" ? `<br>${esc(t("ca_svc_auto_d", { a: "04A9:" + A.service.from, b: "04A9:" + A.service.to }))}` : ""}</div>` : ""}
        ${n ? `<div class="ca-cur" id="caCur">
            <div class="ca-count">${esc(t("ca_step_of", { i: A.cur + 1, n }))}</div>
            <p class="ca-text">${esc(s)}</p>
            ${secs ? `<button type="button" class="btn ca-timer" id="caTimer" data-s="${secs}">${esc(t("ca_timer", { s: secs }))}</button>` : ""}
            <div class="ca-dots">${A.svc.map((_, i) => `<i class="${i < A.cur ? "done" : ""} ${i === A.cur ? "on" : ""}"></i>`).join("")}</div>
            <div class="ca-nav"><button type="button" class="btn" id="caStepBack" ${A.cur ? "" : "disabled"}>${esc(t("ca_step_back"))}</button>
            <button type="button" class="btn primary" id="caStepOk">${esc(t(A.cur < n - 1 ? "ca_step_ok" : "ca_step_last"))}</button></div></div>`
          : `<p class="warnbox">${esc(t("ca_no_steps"))}</p>`}
        <p class="small">${esc(t("ca_svc_hint"))}</p>
        <label class="ca-check"><input type="checkbox" id="caManual" ${A.service ? "checked" : ""} ${A.service && A.service.mode === "auto" ? "disabled" : ""}><span>${esc(t("ca_svc_confirm"))}</span></label>
        ${nav(true, true, true, n && A.rest.length ? t("ca_to_reset") : t("ca_to_end"))}`;
      if ($("#caStepOk")) $("#caStepOk").onclick = () => { A.done["s" + A.cur] = true; if (A.cur < n - 1) { A.cur++; canonRender(); } else { toast(t("ca_svc_wait")); } };
      if ($("#caStepBack")) $("#caStepBack").onclick = () => { A.cur = Math.max(0, A.cur - 1); canonRender(); };
      if ($("#caTimer")) $("#caTimer").onclick = (e) => {
        let left = Number(e.target.dataset.s); const b = e.target; b.disabled = true;
        const iv = setInterval(() => { left--; b.textContent = left > 0 ? t("ca_timer_run", { s: left }) : t("ca_timer_done"); if (left <= 0) clearInterval(iv); }, 1000);
      };
      $("#caManual").onchange = (e) => { A.service = e.target.checked ? (A.service || { mode: "manual" }) : null; canonRender(); };
    } else if (A.stage === 2) {
      const done = A.rest.filter((_, i) => A.done["r" + i]).length;
      box.innerHTML = `<h2>${esc(t("ca_s3"))}</h2><p class="small">${esc(t("ca_r_lead"))}</p>
        ${A.g.tool ? `<p class="small"><b>${esc(t("tool_needed"))}:</b> ${esc(pick(A.g.tool))}</p>` : ""}
        <div class="ca-checks">${A.rest.map((s, i) => `<label class="ca-check ${A.done["r" + i] ? "on" : ""}"><input type="checkbox" data-r="${i}" ${A.done["r" + i] ? "checked" : ""}><span><b>${i + 1}.</b> ${esc(s)}</span></label>`).join("")}</div>
        <p class="small">${esc(t("ca_r_count", { d: done, n: A.rest.length }))}</p>
        ${nav(true, true, true, t("ca_to_end"))}`;
      $$("[data-r]").forEach((c) => c.onchange = () => { A.done["r" + c.dataset.r] = c.checked; canonRender(); });
    } else {
      box.innerHTML = `<h2>${esc(t("ca_s4"))}</h2><p class="small">${esc(t("ca_f_lead"))}</p>
        <h3>${esc(t("ca_maint_title"))}</h3><p class="small">${esc(t("ca_maint_text"))}</p>
        ${A.printers.length ? `<div class="ca-row"><select id="caPrinter">${A.printers.map((p) => `<option ${p.name === A.printer ? "selected" : ""}>${esc(p.name)}</option>`).join("")}</select>
          <button type="button" class="btn" id="caMaint">${esc(t("ca_maint_btn"))}</button></div>` : `<p class="small muted">${esc(t("ca_maint_none"))}</p>`}
        <h3>${esc(t("ca_save_title"))}</h3>
        <div class="ca-form">${clientFields()}</div>
        <div class="ca-nav"><button type="button" class="btn" id="caPrev">${esc(t("ca_prev"))}</button>
        <button type="button" class="btn primary" id="caSave">${esc(t("ca_save_btn"))}</button></div>`;
      if ($("#caPrinter")) $("#caPrinter").onchange = (e) => { A.printer = e.target.value; };
      if ($("#caMaint")) $("#caMaint").onclick = async () => { const r = await call("canon_maintenance", A.printer); if (r.opened) { A.maint = true; toast(t("ca_maint_opened")); } else toast(t("ca_maint_fail"), true); };
      $("#caSave").onclick = async (e) => {
        busy(e.target, true);
        const f = {}; $$("#caMain [name]").forEach((i) => { f[i.name] = i.value; });
        const det = {
          prep_ok: !!(A.prep.ca_p_pad && A.prep.ca_p_usb),
          service: A.service ? A.service.mode : "none", pid_from: A.service && A.service.from, pid_to: A.service && A.service.to,
          steps_total: A.svc.length + A.rest.length,
          steps_done: A.svc.filter((_, i) => A.done["s" + i]).length + A.rest.filter((_, i) => A.done["r" + i]).length,
          maintenance: A.maint,
        };
        const r = await call("save_canon_job", A.m.model, f.client, f.contact, f.notes, det);
        if (r.ok) { const p = await call("report", r.job_id, true); toast(p.ok ? t("toast_report") : t("toast_saved")); canonStop(); show("history"); }
        else { busy(e.target, false); toast(errText(r), true); }
      };
    }
    if ($("#caPrev")) $("#caPrev").onclick = () => { A.stage--; canonRender(); };
    if ($("#caNext")) $("#caNext").onclick = () => {
      if (A.stage === 0) A.base = (A.usb.devices || []).map((d) => ({ pid: d.pid, serial: d.serial }));
      A.stage = (A.stage === 1 && !(A.svc.length && A.rest.length)) ? 3 : A.stage + 1;
      canonRender();
    };
    canonUsb();
  }
  $("#caBack").onclick = () => { canonStop(); show("models"); };

  // ---------- istoric ----------
  const fmtDate = (s) => s ? s.slice(8, 10) + "." + s.slice(5, 7) + "." + s.slice(0, 4) : "";
  let histTimer = null;
  $("#histSearch").addEventListener("input", () => { clearTimeout(histTimer); histTimer = setTimeout(loadHistory, 200); });
  async function loadHistory() {
    const r = await call("history_list", $("#histSearch").value);
    const items = r.items || [];
    const pad = (j) => {
      const b = j.waste_before && (j.waste_before.main_waste ?? j.waste_before.first_waste);
      const a = j.waste_after && (j.waste_after.main_waste ?? j.waste_after.first_waste);
      if (b == null) return `<span class="muted">—</span>`;
      return `<b class="${b >= 85 ? "warn-t" : ""}">${pct(b)}%</b>` + (a != null ? ` → <b class="good">${pct(a)}%</b>` : "");
    };
    $("#histRows").innerHTML = items.length ? items.map((j) => `<tr>
      <td>${esc(fmtDate(j.created))}</td><td><b>${esc(j.client || "—")}</b>${j.client_contact ? `<br><span class="muted">${esc(j.client_contact)}</span>` : ""}</td>
      <td>${esc((j.brand || "") + " " + (j.model || ""))}</td><td class="muted">${esc(j.serial || "—")}</td>
      <td>${pad(j)}</td><td>${esc(t("k_" + j.kind))}</td>
      <td class="r"><button type="button" class="linkbtn" data-rep="${j.id}">${esc(t("report"))}</button>${j.backup_path ? ` | <button type="button" class="linkbtn" data-bk="${esc(j.backup_path)}">${esc(t("backup"))}</button>` : ""} | <button type="button" class="linkbtn" data-ed="${j.id}">${esc(t("edit"))}</button></td></tr>`).join("")
      : `<tr><td colspan="7" class="empty">${esc(t("no_history"))}</td></tr>`;
    $$("[data-rep]").forEach((b) => b.onclick = async () => { const r = await call("report", Number(b.dataset.rep), true); r.ok ? toast(t("toast_report")) : toast(errText(r), true); });
    $$("[data-bk]").forEach((b) => b.onclick = () => call("open_path", b.dataset.bk));
    $$("[data-ed]").forEach((b) => b.onclick = async () => {
      const j = items.find((x) => x.id === Number(b.dataset.ed));
      const form = await modal({ title: t("edit_title"), body: clientFields(j), form: true, buttons: [{ label: t("cancel") }, { label: t("save"), value: true, primary: true }] });
      if (!form) return;
      await call("history_update", j.id, form.client, form.contact, form.notes); loadHistory();
    });
  }

  // ---------- actualizări ----------
  const U = { info: null, timer: null };
  const pickL = (o) => (o && (o[S.lang] || o.en || o.ro)) || "";
  function updHint() { const p = (S.info && S.info.platform) || ""; return t(p === "win32" ? "upd_hint_win" : p === "darwin" ? "upd_hint_mac" : "upd_hint_linux"); }
  function renderUpdBox(msg) {
    const box = $("#updBox"); if (!box) return;
    box.innerHTML = `<h3 class="mt">${esc(t("upd_title"))}</h3><p class="small" id="updMsg">${esc(msg || "")}</p>
      <div class="actions-row"><button type="button" class="btn" id="btnUpdCheck">${esc(t("upd_check"))}</button></div>`;
    $("#btnUpdCheck").onclick = (e) => checkUpdate(true, e.target);
  }
  function renderUpdBar(state) {
    const bar = $("#updBar"), i = U.info; if (!i) { bar.hidden = true; return; }
    bar.hidden = false;
    const notes = pickL(i.notes);
    if (!state || state.state === "idle") {
      bar.innerHTML = `<div class="upd-txt"><b>${esc(t("upd_avail", { v: i.version }))}</b>${notes ? `<span>${esc(notes)}</span>` : ""}</div>
        <div class="upd-act"><button type="button" class="btn primary" id="updDl">${esc(t("upd_dl"))}</button><button type="button" class="btn" id="updLater">${esc(t("upd_later"))}</button></div>`;
      $("#updDl").onclick = async () => { const r = await call("update_download"); if (r.ok === false) { toast(t("upd_err"), true); return; } pollUpd(); };
      $("#updLater").onclick = async () => { await call("update_dismiss", i.version); bar.hidden = true; };
    } else if (state.state === "running") {
      const p = state.total ? Math.floor(100 * state.done / state.total) : 0;
      bar.innerHTML = `<div class="upd-txt"><b>${esc(t("upd_downloading", { p }))}</b><div class="upd-prog"><i style="width:${p}%"></i></div></div>`;
    } else if (state.state === "done") {
      bar.innerHTML = `<div class="upd-txt"><b>${esc(t("upd_done"))}</b><span>${esc(updHint())}</span></div>
        <div class="upd-act"><button type="button" class="btn primary" id="updOpen">${esc(t("upd_open"))}</button></div>`;
      $("#updOpen").onclick = () => call("update_open");
    } else {
      bar.innerHTML = `<div class="upd-txt"><b>${esc(t("upd_err"))}</b></div>
        <div class="upd-act"><button type="button" class="btn" id="updRetry">${esc(t("upd_dl"))}</button><button type="button" class="btn" id="updSite">${esc(t("upd_site"))}</button></div>`;
      $("#updRetry").onclick = async () => { await call("update_download"); pollUpd(); };
      $("#updSite").onclick = () => call("open_doc", "download");
    }
  }
  function pollUpd() {
    clearInterval(U.timer);
    U.timer = setInterval(async () => {
      const s = await call("update_progress");
      renderUpdBar(s);
      if (s.state !== "running") clearInterval(U.timer);
    }, 500);
  }
  async function checkUpdate(manual, btn) {
    if (btn) busy(btn, true);
    const r = await call("update_check");
    if (btn) busy(btn, false);
    if (r.ok === false) { renderUpdBox(t("upd_offline")); return; }
    if (r.available) {
      U.info = r;
      renderUpdBox(t("upd_avail", { v: r.version }));
      if (manual || r.dismissed !== r.version) renderUpdBar();
    } else renderUpdBox(t("upd_latest", { v: r.current }));
  }

  // ---------- pornire ----------
  async function boot() {
    const info = await call("info");
    S.info = info; S.lang = info.lang || "ro";
    $("#footVer").textContent = "MDN Printer Service " + info.version;
    $("#footEmail").textContent = info.email;
    applyI18n(); renderLic(); show("printers");
    renderUpdBox("");
    scan();
    setTimeout(() => checkUpdate(false), 4000);
  }
  $("#btnScan").onclick = scan;

  function start() {
    if (window.pywebview && window.pywebview.api) { api = window.pywebview.api; boot(); }
    else if (window.MDN_DEMO) { api = window.MDN_DEMO; boot(); }
  }
  window.addEventListener("pywebviewready", start);
  setTimeout(() => {
    if (api) return;
    if (window.pywebview && window.pywebview.api) return start();
    const s = document.createElement("script"); s.src = "demo.js"; s.onload = start; document.head.appendChild(s);
  }, 1200);
})();
