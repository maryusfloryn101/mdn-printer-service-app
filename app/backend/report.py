# -*- coding: utf-8 -*-
"""Raportul PDF de service pentru client (A4), cu sigla MDN Digital."""
from __future__ import annotations

import json
import os
from typing import Optional

from fpdf import FPDF

from . import config

NAVY = (15, 23, 32)
TEXT = (22, 32, 42)
MUTED = (85, 96, 108)
GREEN = (4, 120, 87)
AMBER = (154, 77, 0)
LINE = (213, 220, 227)

# Textele raportului în cele 12 limbi ale aplicației.
with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "report_i18n.json"), encoding="utf-8") as _fh:
    T = json.load(_fh)


def _pct(v) -> str:
    if v is None:
        return "–"
    try:
        return f"{float(v):.1f} %".replace(".", ",")
    except (TypeError, ValueError):
        return str(v)


def build(job: dict, out_dir: str, assets_dir: str, fonts_dir: str, lang: str = "ro") -> str:
    t = T.get(lang, T["ro"])
    pdf = FPDF(format="A4", unit="mm")
    pdf.set_margins(20, 18, 20)
    pdf.set_auto_page_break(True, 18)
    for w, style in ((400, ""), (700, "B"), (800, "I")):  # I = extra-bold, folosit la titluri
        pdf.add_font("Manrope", style, os.path.join(fonts_dir, f"Manrope-{w}.ttf"))
    pdf.add_page()

    # Antet
    logo = os.path.join(assets_dir, "logo-light.png")
    if os.path.exists(logo):
        pdf.image(logo, x=20, y=16, w=30)
    pdf.set_xy(110, 17)
    pdf.set_font("Manrope", "I", 17)
    pdf.set_text_color(*TEXT)
    pdf.cell(80, 8, t["title"], align="R")
    pdf.set_xy(110, 26)
    pdf.set_font("Manrope", "", 9.5)
    pdf.set_text_color(*MUTED)
    date = (job.get("created") or "")[:10]
    if len(date) == 10:
        date = f"{date[8:10]}.{date[5:7]}.{date[0:4]}"
    pdf.cell(80, 5, f"{t['no']} {job.get('id', '')}, {date}", align="R")
    pdf.set_draw_color(*NAVY)
    pdf.set_line_width(0.6)
    pdf.line(20, 36, 190, 36)

    # Client + imprimantă
    y = 44
    pdf.set_xy(20, y)
    _label(pdf, t["client"])
    pdf.set_xy(110, y)
    _label(pdf, t["printer"])
    pdf.set_font("Manrope", "B", 12)
    pdf.set_text_color(*TEXT)
    pdf.set_xy(20, y + 6)
    pdf.multi_cell(85, 6, job.get("client") or "–")
    pdf.set_xy(110, y + 6)
    pdf.cell(80, 6, f"{job.get('brand') or ''} {job.get('model') or ''}".strip())
    pdf.set_font("Manrope", "", 9.5)
    pdf.set_xy(20, y + 13)
    pdf.multi_cell(85, 5, job.get("client_contact") or "")
    pdf.set_xy(110, y + 13)
    serial = job.get("serial") or "–"
    fw = job.get("firmware")
    pdf.multi_cell(80, 5, f"{t['serial']} {serial}" + (f", {t['fw']} {fw}" if fw else "")
                   + (f"\n{t['conn']}: {job['connection']}" if job.get("connection") else ""))

    # Contoare
    y = 76
    wb, wa = job.get("waste_before") or {}, job.get("waste_after") or {}
    if isinstance(wb, dict) and wb:
        pdf.set_xy(20, y)
        _h2(pdf, t["waste"])
        y += 9
        pdf.set_font("Manrope", "", 9)
        pdf.set_text_color(*MUTED)
        pdf.set_xy(20, y)
        pdf.cell(90, 6, t["pad"])
        pdf.cell(40, 6, t["before"], align="R")
        pdf.cell(40, 6, t["after"], align="R")
        y += 7
        pdf.set_draw_color(*LINE)
        pdf.set_line_width(0.3)
        pdf.line(20, y, 190, y)
        names = {"main_waste": t["main"], "borderless_waste": t["borderless"],
                 "first_waste": "1", "second_waste": "2", "third_waste": "3"}
        for key, label in names.items():
            if key not in wb and key not in wa:
                continue
            pdf.set_xy(20, y + 1.5)
            pdf.set_font("Manrope", "", 10.5)
            pdf.set_text_color(*TEXT)
            pdf.cell(90, 7, label)
            pdf.set_font("Manrope", "B", 10.5)
            pdf.cell(40, 7, _pct(wb.get(key)), align="R")
            pdf.set_text_color(*GREEN if wa else TEXT)
            pdf.cell(40, 7, _pct(wa.get(key)) if wa else "–", align="R")
            y += 9
            pdf.line(20, y, 190, y)
        y += 8

    # Stare
    stats = job.get("stats") or {}
    has_stats = isinstance(stats, dict) and any(k in stats for k in (
        "Total print page counter", "Total scan counter", "First TI received time"))
    if has_stats:
        pdf.set_xy(20, y)
        _h2(pdf, t["state"])
        y += 10
        items = []
        if stats.get("Total print page counter") is not None:
            items.append((t["pages"], f"{stats['Total print page counter']:,}".replace(",", " ")))
        if stats.get("Total scan counter") is not None:
            items.append((t["scans"], f"{stats['Total scan counter']:,}".replace(",", " ")))
        if stats.get("First TI received time"):
            items.append((t["first"], str(stats["First TI received time"])))
        for i, (lab, val) in enumerate(items[:4]):
            x = 20 + i * 43
            pdf.set_xy(x, y)
            _label(pdf, lab)
            pdf.set_xy(x, y + 5)
            pdf.set_font("Manrope", "B", 12)
            pdf.set_text_color(*TEXT)
            pdf.cell(42, 7, val)
        y += 18

    # Lucrări
    pdf.set_xy(20, y)
    _h2(pdf, t["work"])
    y += 9
    pdf.set_font("Manrope", "", 10.5)
    pdf.set_text_color(*TEXT)
    lines = list(t["kinds"].get(job.get("kind"), []))
    if job.get("kind") == "canon_assist":
        lines = canon_lines(t, (stats or {}).get("canon") if isinstance(stats, dict) else {})
    for i, line in enumerate(lines, 1):
        pdf.set_xy(20, y)
        pdf.multi_cell(170, 6, f"{i}. {line}")
        y = pdf.get_y() + 1
    if job.get("notes"):
        y += 3
        pdf.set_xy(20, y)
        _label(pdf, t["notes"])
        pdf.set_xy(20, y + 5)
        pdf.set_font("Manrope", "", 10.5)
        pdf.set_text_color(*TEXT)
        pdf.multi_cell(170, 6, job["notes"])

    # Semnături + subsol
    pdf.set_draw_color(154, 166, 178)
    pdf.set_line_width(0.3)
    pdf.line(20, 255, 95, 255)
    pdf.line(115, 255, 190, 255)
    pdf.set_xy(20, 256)
    _label(pdf, t["sig_tech"])
    pdf.set_xy(115, 256)
    _label(pdf, t["sig_client"])
    pdf.set_draw_color(*LINE)
    pdf.line(20, 270, 190, 270)
    pdf.set_xy(20, 272)
    pdf.set_font("Manrope", "", 8)
    pdf.set_text_color(*MUTED)
    pdf.cell(120, 5, t["footer"])
    pdf.cell(50, 5, config.SUPPORT_EMAIL, align="R")

    os.makedirs(out_dir, exist_ok=True)
    safe_client = "".join(c for c in (job.get("client") or "client") if c.isalnum() or c in " -_")[:40].strip()
    path = os.path.join(out_dir, f"Raport_{job.get('id')}_{safe_client or 'client'}.pdf")
    pdf.output(path)
    return path


def canon_lines(t: dict, d: Optional[dict]) -> list:
    d = d or {}
    c = t["canon"]
    out = []
    if d.get("prep_ok"):
        out.append(c["prep"])
    if d.get("service") == "auto":
        out.append(c["svc_auto"].format(a=d.get("pid_from") or "?", b=d.get("pid_to") or "?"))
    elif d.get("service") == "manual":
        out.append(c["svc_manual"])
    else:
        out.append(c["svc_none"])
    if d.get("steps_total"):
        out.append(c["steps"].format(d=d.get("steps_done", 0), t=d["steps_total"]))
    if d.get("maintenance"):
        out.append(c["maint"])
    out.append(c["nowrite"])
    return out


def _label(pdf, text):
    pdf.set_font("Manrope", "", 8.5)
    pdf.set_text_color(*MUTED)
    pdf.cell(80, 5, text)


def _h2(pdf, text):
    pdf.set_font("Manrope", "I", 12.5)
    pdf.set_text_color(*TEXT)
    pdf.cell(170, 7, text)
