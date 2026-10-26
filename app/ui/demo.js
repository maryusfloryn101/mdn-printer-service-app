/* Mod demo: se încarcă doar când interfața e deschisă într-un browser obișnuit,
   fără aplicația Python. Datele sunt de exemplu. */
(function () {
  const wait = (ms, v) => new Promise((r) => setTimeout(() => r(v), ms));
  let lic = { active: true, machine: "4F2A-91C0-7D3E-0B19", key_hint: "MDN-7K2F-…" };
  const sheet = {
    ok: true, handle: "usb:demo", model: "EcoTank", raw_model: "EPSON EcoTank Series", db_model: "EcoTank", manufacturer: "EPSON",
    connection: "USB", serial: "XXXX000000", firmware: "—", mac: null, support: "auto", tested: true,
    waste: { main_waste: 100.0, borderless_waste: 38.2 },
    status: { text: "Error", error: "Ink overflow error (Waste ink pad counter overflow)", warnings: [], inks: [] },
    stats: { "Total print page counter": 18406, "Total scan counter": 2117, "First TI received time": "—", "Total print pass counter": 912334 },
    fatal_errors: ["69"], leds: { power: "on", ink: "blink", paper: "blink", reason: "waste_full" }, errors: []
  };
  const jobs = [];
  const models = [
    { brand: "Epson", model: "L3150", aliases: ["L3151", "L3160", "L3166", "L3168"], mode: "auto", tested: "2026-10-24 (L3151)" },
    { brand: "Epson", model: "L4160", aliases: ["L4150", "L4152", "L4154"], mode: "auto", tested: null },
    { brand: "Epson", model: "ET-2810", aliases: ["ET-2811", "ET-2812"], mode: "auto", tested: null }, ...[{"brand": "Canon", "model": "G1420", "family": "G1420", "aliases": ["G2420", "G2460", "G3420", "G3460", "G3470", "G540", "G640", "G1020 series", "G2020 series", "G2060 series", "G3020 series", "G3060 series", "G3070 series", "G500 series", "G600 series"], "mode": "guide", "tested": null, "match": ["G1420", "G2420", "G2460", "G3420", "G3460", "G3470", "G540", "G640", "G1020", "G2020", "G2060", "G3020", "G3060", "G3070", "G500", "G600"], "guide": {"intro": {"ro": "La acest model nu există contor de resetat: cerneala uzată merge într-un cartuș de întreținere (MC-G02) pe care îl schimbați singur.", "en": "This model has no counter to reset: waste ink goes into a user-replaceable maintenance cartridge (MC-G02)."}, "errors": "1727 (cartuș de întreținere aproape plin, se poate continua cu OK), 1726 (cartuș de întreținere plin, printarea se oprește)", "steps": {"ro": ["Cumpărați un cartuș de întreținere nou Canon MC-G02.", "Scoateți cartușul nou și punga de plastic din cutie.", "Opriți imprimanta din butonul de pornire.", "Deșurubați șurubul cu fantă (se poate folosi o monedă) de pe capacul de întreținere.", "Scoateți capacul de întreținere: puneți degetul în orificiul capacului și trageți-l.", "Trageți cartușul de întreținere vechi spre dumneavoastră până se oprește.", "Ridicați puțin cartușul și scoateți-l de tot. Nu-l puneți pe masă, poate curge cerneală.", "Puneți imediat cartușul vechi în punga primită cu cel nou și legați-o strâns.", "Nu băgați mâna în imprimantă, vă puteți păta de cerneală.", "Introduceți drept cartușul nou până se oprește.", "Puneți la loc capacul: potriviți clapeta din spatele capacului cu orificiul din imprimantă și închideți-l.", "Puneți șurubul la loc și strângeți-l în sensul acelor de ceasornic.", "Porniți imprimanta. Eroarea dispare singură, nu e nevoie de resetare."], "en": ["Get a new Canon MC-G02 maintenance cartridge.", "Take the new cartridge and its plastic bag out of the box.", "Turn the printer off.", "Unlock the coin screw on the maintenance cover.", "Remove the maintenance cover (finger in the cover hole).", "Pull the maintenance cartridge out until it stops.", "Lift it slightly and pull it out; do not put it down on a desk.", "Put the used cartridge in the bag from the new one and tie it tightly.", "Do not put your hands inside the printer.", "Insert the new cartridge straight in until it stops.", "Refit the cover (tab on its back into the printer hole) and close it.", "Insert the coin screw and turn it clockwise.", "Turn the printer on. No counter reset is needed."]}, "tool": "Niciunul: piesă consumabilă înlocuibilă de utilizator (MC-G02)", "warning": {"ro": "Nu încercați resetare cu Service Tool la aceste modele; soluția oficială este înlocuirea cartușului MC-G02. Nu atingeți contactele și deschiderea cartușului. Aruncați cartușul vechi conform regulilor locale.", "en": "Do not attempt a Service Tool reset on these models; the official fix is replacing MC-G02. Do not touch the cartridge terminal/opening. Dispose of the used cartridge per local rules."}, "confidence": "high", "sources": ["https://ij.manual.canon/ij/webmanual/Manual/All/G3020%20series/EN/UG/ug-235.html", "https://ij.manual.canon/ij/webmanual/Manual/All/G600%20series/EN/UG/ug-235.html", "https://ij.manual.canon/ij/webmanual/Manual/All/G1020%20series/EN/UG/ug-235.html", "https://ij.manual.canon/ij/webmanual/ErrorCode/G500%20series/EN/ERR/1726.html", "https://ij.manual.canon/ij/webmanual/ErrorCode/G500%20series/EN/ERR/1727.html", "https://canon.ie/store/canon-mc-g02-maintenance-cartridge/4589C001"]}}, {"brand": "Canon", "model": "G2010", "family": "G2010", "aliases": ["G2410", "G2411", "G2415", "G2416", "G3010", "G3410", "G3411", "G3415", "G3416"], "mode": "guide", "tested": null, "match": ["G2010", "G2410", "G2411", "G2415", "G2416", "G3010", "G3410", "G3411", "G3415", "G3416"], "guide": {"intro": {"ro": "Resetarea se efectuează din modul de service al imprimantei. Aplicația prezintă pașii și nu scrie în imprimantă.", "en": "The reset is performed from the printer's service mode. The application presents the steps and does not write to the printer."}, "errors": "1700 (absorbant aproape plin, se poate continua), 5B00 (absorbant plin; pe afișaj poate apărea P07)", "tool": "Canon Service Tool, versiune neconfirmată pentru G2010/G3010 (pentru G1000–G3000 manualul cere V4718 sau mai nou; sursele menționează V5103/V5204 pentru modelele G mai noi). NU folosiți V3400 sau mai vechi.", "warning": {"ro": "Neconfirmat pentru exact aceste modele. Ordinea butoanelor e luată din procedura Canon standard și de la generația anterioară G2000/G3000. Un manual de service citat pe forum (G4000) spune să țineți întâi butonul de pornire, apoi să apăsați Stop de 5 ori (de 6 ori la modelele fără scanner); încercați această variantă doar dacă prima nu merge. O versiune prea veche de Service Tool poate bloca definitiv modul service. Înainte de resetare spălați sau înlocuiți buretele absorbant sau montați un recipient extern, altfel cerneala poate curge din imprimantă.", "en": "Unverified for these exact models; sequence taken from the standard Canon procedure and the G2000/G3000 predecessors. A forum-quoted service manual (G4000) says hold Power first, then press Stop 5 times (6 without scanner); use that only if the first variant fails. A too-old Service Tool can permanently lock service mode. Clean/replace the pads or fit an external waste tank before resetting, otherwise ink may leak."}, "confidence": "unverified", "sources": ["https://ij.manual.canon/ij/webmanual/ErrorCode/G2010%20series/EN/ERR/1700.html", "https://ij.manual.canon/ij/webmanual/ErrorCode/G2010%20series/EN/ERR/5B00.html", "https://www.printerknowledge.com/goto/post?id=92192", "https://printerknowledge.com/goto/post?id=116152", "https://www.printerknowledge.com/goto/post?id=110887", "https://www.printerknowledge.com/goto/post?id=140243", "https://www.druckerchannel.de/artikel_druckansicht.php?ID=2746"], "steps_n": 18}}]
  ];
  window.MDN_DEMO = {
    info: () => wait(50, { ok: true, version: "1.0.2", email: "service@mdndigital.ro", price: "10 €", lang: "ro", models: { Epson: 988, Canon: 8, Brother: 3 }, license: lic }),
    set_lang: () => wait(10, { ok: true }),
    service_info: () => wait(400, { ok: true, has_keys: true, can_write: true, network: true, counters: [{ key: "main_waste", level: 87.4 }, { key: "borderless_waste", level: 41.2 }], head_id: "1A2B3C4D", cartridges: ["T664 Black", "T664 Cyan", "T664 Magenta", "T664 Yellow"], ink_replacements: [{ color: "Black", counter: 1, value: 3 }, { color: "Cyan", counter: 1, value: 2 }], cartridge_info: [], poweroff: 30, poweroff_supported: true }),
    reset_counter: () => wait(800, { ok: true, waste_after: { main_waste: 0, borderless_waste: 41.2 } }),
    service_print: () => wait(500, { ok: true }),
    set_poweroff: () => wait(300, { ok: true }),
    dump_start: () => { window.__dT = Date.now(); return wait(50, { ok: true, started: true }); },
    job_progress: () => { const p = Math.min(1, (Date.now() - (window.__dT || 0)) / 2000); return wait(10, p < 1 ? { ok: true, state: "running", done: Math.floor(p * 256), total: 256 } : { ok: true, state: "done", cells: 256, path: "memorie_EcoTank.json" }); },
    snapshots_list: () => wait(50, { ok: true, items: [{ file: "b.json", date: "2026-10-26_12-10-00", model: "L3150", serial: "X1" }, { file: "a.json", date: "2026-10-26_11-50-00", model: "L3150", serial: "X1" }] }),
    snapshots_compare: () => wait(100, { ok: true, same_printer: true, diff: [{ addr: 48, a: "5E", b: "00" }, { addr: 49, a: "1A", b: "00" }] }),
    read_cells: (h, a) => wait(200, { ok: true, cells: Array.from({ length: 16 }, (_, i) => ({ addr: a + i, value: ((a + i) * 7 % 256).toString(16).toUpperCase().padStart(2, "0") })) }),
    write_cell: (h, a, v) => wait(300, { ok: true, before: "5E", after: v.toString(16).toUpperCase() }),
    find_key_start: () => wait(50, { ok: true, started: true }),
    update_check: () => wait(200, { ok: true, available: true, current: "1.0.2", version: "1.0.3", dismissed: "", notes: { ro: "Detectare mai rapidă a imprimantelor pe Wi-Fi și modele noi în bază.", en: "Faster Wi-Fi printer discovery and new models." } }),
    update_dismiss: () => wait(10, { ok: true }),
    update_download: () => { window.__updT = Date.now(); return wait(50, { ok: true, started: true }); },
    update_progress: () => { const p = Math.min(1, (Date.now() - (window.__updT || 0)) / 3000); return wait(10, p < 1 ? { ok: true, state: "running", done: p * 46e6, total: 46e6 } : { ok: true, state: "done", path: "MDN-Printer-Service-Setup.exe" }); },
    update_open: () => wait(10, { ok: true }),
    license_state: () => wait(300, Object.assign({ ok: true }, lic)),
    activate: () => wait(600, { ok: false, error: "offline" }),
    open_folder: () => wait(10, { ok: true }),
    open_path: () => wait(10, { ok: true }),
    scan: () => wait(1400, { ok: true, printers: [
      { handle: "usb:demo", connection: "USB", model: "EcoTank", raw_model: "EPSON EcoTank Series", support: "auto", tested: true },
      { handle: "net:192.168.1.42", connection: "Wi-Fi", ip: "192.168.1.42", model: "WorkForce", raw_model: "EPSON WorkForce Series", support: "auto" }
    ], others: [] }),
    open_printer: () => wait(900, JSON.parse(JSON.stringify(sheet))),
    backup: () => wait(1200, { ok: true, path: "C:\\Users\\Utilizator\\Documents\\MDN Printer Service\\Backup\\backup_EcoTank_XXXX000000.json", cells: 268 }),
    reset: (h, client) => { jobs.unshift({ id: jobs.length + 1, created: "2026-10-25 10:12:00", client, brand: "Epson", model: "EcoTank", serial: "XXXX000000", kind: "reset", waste_before: { main_waste: 100 }, waste_after: { main_waste: 0 } }); return wait(1500, { ok: true, waste_after: { main_waste: 0, borderless_waste: 0 }, job_id: jobs.length }); },
    temporary_unlock: () => wait(800, { ok: true, job_id: 9 }),
    restore: () => wait(300, { ok: false, error: "cancelled" }),
    save_check: () => wait(100, { ok: true, job_id: 9 }),
    report: () => wait(500, { ok: true, path: "Raport.pdf" }),
    models_search: (q, brand) => wait(60, { ok: true, items: models.filter((m) => (!brand || brand === "Toate" || m.brand === brand) && (m.model + m.aliases.join("")).toUpperCase().includes((q || "").toUpperCase())), total: 3 }),
    save_guide_job: () => wait(100, { ok: true, job_id: 10 }),
    guide_steps: () => wait(300, { ok: true, steps: ["Pas demonstrativ 1: în versiunea reală, pașii vin de pe serverul de licențe.", "Pas demonstrativ 2", "Pas demonstrativ 3"] }),
    linux_usb: () => wait(200, { ok: true, ready: true }),
    canon_usb: () => wait(150, { ok: true, devices: [{ pid: "1865", serial: "", name: "Canon G3010 series", status: "OK", cls: "Printer" }] }),
    canon_compare: (() => { let n = 0; return () => { n++; return wait(150, n < 4 ? { ok: true, state: "same", devices: [{ pid: "1865", name: "Canon G3010 series" }] } : { ok: true, state: "changed", from: ["1865"], to: ["12FE"], devices: [{ pid: "12FE", name: "" }] }); }; })(),
    canon_printers: () => wait(150, { ok: true, printers: [{ name: "Canon G3010 series", connection: "USB" }] }),
    canon_maintenance: () => wait(150, { ok: true, opened: true }),
    save_canon_job: () => wait(150, { ok: true, job_id: 11 }),
    history_list: () => wait(100, { ok: true, items: jobs }),
    history_update: () => wait(50, { ok: true })
  };
})();
