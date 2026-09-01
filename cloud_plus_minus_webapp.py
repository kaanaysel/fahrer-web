#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations

import csv
import io
import json
import os
import re
import sqlite3
from datetime import datetime, timezone
from functools import wraps
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
from difflib import SequenceMatcher

try:
    from zoneinfo import ZoneInfo
except Exception:
    ZoneInfo = None

from flask import Flask, abort, flash, get_flashed_messages, jsonify, redirect, render_template_string, request, send_file, session, url_for, make_response
from werkzeug.security import check_password_hash, generate_password_hash
from werkzeug.utils import secure_filename

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle, Image

try:
    from pypdf import PdfReader
except Exception:
    PdfReader = None

APP_NAME = "Plus/Minus Cloud"
DATA_ROOT = Path(os.environ.get("PORTAL_DATA_DIR", "/opt/render/project/src/data")).resolve()
FILES_DIR = DATA_ROOT / "pdfs"
ATTACHMENTS_DIR = DATA_ROOT / "attachments"
EXPORT_DIR = DATA_ROOT / "exports"
BACKUP_DIR = DATA_ROOT / "backups"
DB_FILE = DATA_ROOT / "portal.sqlite3"
SECRET_KEY = os.environ.get("PORTAL_SECRET_KEY", "dev-secret-change-me")
ADMIN_API_TOKEN = os.environ.get("ADMIN_API_TOKEN", "0341")
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "0341")
MAX_CONTENT_LENGTH = 50 * 1024 * 1024

app = Flask(__name__)
app.secret_key = SECRET_KEY
app.config["MAX_CONTENT_LENGTH"] = MAX_CONTENT_LENGTH

MONATE = {
    1: "Januar", 2: "Februar", 3: "März", 4: "April", 5: "Mai", 6: "Juni",
    7: "Juli", 8: "August", 9: "September", 10: "Oktober", 11: "November", 12: "Dezember",
}

BASE_CSS = r"""
:root{--bg:#eef1f6;--card:#fff;--text:#101827;--muted:#667085;--line:#d9dee8;--blue:#123e7c;--blue2:#0f62fe;--green:#067647;--red:#b42318;--amber:#b54708;--soft:#f8fafc;--shadow:0 12px 35px rgba(16,24,40,.08)}
*{box-sizing:border-box} body{margin:0;font-family:Inter,Segoe UI,Arial,sans-serif;background:radial-gradient(circle at top left,#dce9ff 0,#eef1f6 35%,#f7f8fb 100%);color:var(--text)}
a{color:inherit}.shell{display:grid;grid-template-columns:270px 1fr;min-height:100vh}.side{background:#0f2446;color:#fff;padding:22px;position:sticky;top:0;height:100vh}.brand{font-size:1.35rem;font-weight:900;letter-spacing:-.02em;margin-bottom:22px}.nav a{display:block;text-decoration:none;padding:12px 14px;border-radius:14px;margin:6px 0;color:#d9e7ff}.nav a:hover,.nav a.active{background:rgba(255,255,255,.13);color:#fff}.main{padding:24px;max-width:1600px;width:100%;margin:0 auto}.top{display:flex;justify-content:space-between;gap:14px;align-items:flex-start;margin-bottom:20px}.title{font-size:2rem;font-weight:900;color:#0f2446;letter-spacing:-.03em}.subtitle{color:var(--muted);margin-top:4px}.card{background:rgba(255,255,255,.88);backdrop-filter:blur(12px);border:1px solid var(--line);border-radius:22px;padding:18px;box-shadow:var(--shadow);margin-bottom:18px}.grid{display:grid;gap:16px}.grid-2{grid-template-columns:repeat(2,minmax(0,1fr))}.grid-3{grid-template-columns:repeat(3,minmax(0,1fr))}.grid-4{grid-template-columns:repeat(4,minmax(0,1fr))}.kpi{padding:18px;border-radius:20px;background:linear-gradient(180deg,#fff,#f8fbff);border:1px solid var(--line)}.kpi b{display:block;font-size:1.65rem;margin-top:6px}.muted{color:var(--muted)}.badge{display:inline-flex;align-items:center;gap:6px;padding:6px 10px;border-radius:999px;background:#eff6ff;color:#1d4ed8;font-weight:800}.pos{color:var(--green);font-weight:800}.neg{color:var(--red);font-weight:800}.zero{color:var(--muted);font-weight:800}
label{display:block;font-weight:800;margin-bottom:6px}input,select,textarea,button,.btn{width:100%;padding:11px 12px;border:1px solid #c7ceda;border-radius:12px;font-size:15px;background:#fff}textarea{min-height:42px;resize:vertical}button,.btn{cursor:pointer;text-decoration:none;text-align:center;display:inline-block;background:#f8fafc;font-weight:800}.btn.primary,button.primary{background:linear-gradient(135deg,var(--blue),var(--blue2));border-color:var(--blue);color:#fff}.btn.danger,button.danger{background:#fff1f0;border-color:#fda29b;color:#b42318}.btn.small{width:auto;padding:8px 11px;border-radius:10px;font-size:13px}.actions{display:flex;gap:10px;flex-wrap:wrap;align-items:center}.actions .btn,.actions button{width:auto}.table-wrap{overflow:auto;border:1px solid var(--line);border-radius:18px;background:#fff}table{border-collapse:separate;border-spacing:0;width:100%;min-width:1180px}th,td{padding:12px;border-bottom:1px solid #edf0f5;text-align:left;vertical-align:middle}th{position:sticky;top:0;background:#f3f6fb;color:#344054;font-size:13px;z-index:1}tr:hover td{background:#fbfdff}.flash{padding:12px 14px;border-radius:14px;margin-bottom:14px;font-weight:700}.flash.ok{background:#ecfdf3;color:#067647;border:1px solid #abefc6}.flash.err{background:#fff1f0;color:#b42318;border:1px solid #fecdca}.login-wrap{max-width:520px;margin:8vh auto;padding:24px}.driver-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(210px,1fr));gap:14px}.month-card{padding:16px;border:1px solid var(--line);border-radius:18px;background:#fff;text-decoration:none}.month-card strong{display:block;color:#123e7c;font-size:1.1rem;margin-bottom:6px}.right{text-align:right}.nowrap{white-space:nowrap}.item-row{display:flex;gap:8px;align-items:center;margin-bottom:6px;padding:6px 8px;border:1px solid #edf0f5;border-radius:12px;background:#fbfdff}.item-row form{margin-left:auto}.mini-form{display:grid;grid-template-columns:110px 90px minmax(160px,1fr) auto;gap:8px;align-items:center}.sum-box{font-size:13px;margin-top:8px;color:var(--muted)}.admin-info{min-width:240px}.admin-info textarea{min-height:86px;font-size:14px;background:#fffef7;border-color:#f6d98b}.download-note{font-size:12px;color:var(--muted);margin-top:4px}.driver-row.row-base td{background:#ffffff}.driver-row.row-alt td{background:#f3f6fb}.driver-row:hover td{background:#eaf1fb!important}.adjustment-list{margin-top:12px;padding-top:10px;border-top:1px dashed #cfd6e3}.delete-month-btn{font-size:11px!important;padding:5px 8px!important;border-radius:9px!important;opacity:.82}.delete-month-btn:hover{opacity:1}.admin-info textarea.carried{background:#f5f8ff;border-color:#b8c8f0}.months-table{table-layout:fixed;min-width:0}.months-table th,.months-table td{padding:8px 7px}.col-admin{width:155px}.col-driver{width:190px}.col-hours{width:82px}.col-payroll{width:82px}.col-v{width:125px}.col-adjust{width:350px}.col-small{width:62px}.col-action{width:100px}.months-table input[name=worked_hours],.months-table input[name=payroll_hours],.months-table input[name=v_note]{padding:12px 9px;font-size:16px}.months-table input[name=worked_hours]{max-width:70px}.months-table input[name=payroll_hours]{max-width:74px}.months-table input[name=v_note]{max-width:115px}.v-preview{font-size:12px;color:#98a2b3;margin-top:4px;line-height:1.2;white-space:nowrap}.v-toggle{display:inline-flex!important;align-items:center;gap:4px;margin-top:4px;color:#667085;font-size:11px;font-weight:800;line-height:1;white-space:nowrap;max-width:70px;overflow:hidden;margin-bottom:0}.v-toggle input{width:auto!important;min-width:13px!important;height:13px!important;padding:0!important;margin:0!important}.v-disabled{background:#f2f4f7!important;border-color:#d0d5dd!important;color:#667085!important;opacity:.72}.v-disabled-note{font-size:10px;color:#98a2b3;margin-top:3px;font-weight:800;line-height:1.05;max-width:70px}.mini-form{display:flex;flex-wrap:wrap;gap:7px;align-items:center}.mini-form select{width:78px}.mini-form input[name=item_hours]{width:58px}.mini-form input[name=item_note]{width:105px}.mini-form button{width:auto}.dropzone{position:relative;border:2px dashed #b8c4d6;background:#f8fafc;border-radius:14px;padding:14px 12px;text-align:center;font-size:13px;line-height:1.25;color:#475467;cursor:pointer;min-height:48px;display:flex;align-items:center;justify-content:center;width:115px}.dropzone.dragover{border-color:#067647;background:#ecfdf3;color:#067647}.dropzone input[type=file]{position:absolute;inset:0;opacity:0;cursor:pointer}.file-pill{display:inline-flex;align-items:center;gap:6px;padding:5px 8px;border-radius:999px;background:#eef4ff;color:#123e7c;font-size:12px;margin-top:6px}.file-pill form{display:inline;margin:0}.file-remove{width:auto!important;padding:3px 7px!important;border-radius:999px!important;font-size:11px!important}.compact-save{display:flex;flex-direction:column;gap:7px;align-items:flex-start}.mobile-row-title{display:none;font-weight:900;color:#0f2446;margin-bottom:8px}.payroll-table{table-layout:fixed;min-width:0}.payroll-table th,.payroll-table td{padding:9px 8px}.col-pay-info{width:150px}.col-pay-num{width:84px}.col-days{width:105px}.days-vacation input{border-color:#75c087;background:#f0fdf4;color:#067647}.days-sick .sick-calendar-open{border-color:#fda29b;background:#fff1f0;color:#b42318;text-align:left}.payroll-table textarea{min-height:74px;font-size:14px}.driver-name{font-weight:900}.employment-vollzeit{color:#7c3aed}.employment-teilzeit{color:#d4a000}.employment-aushilfe{color:#38bdf8}.vacation-input-wrap{position:relative}.vacation-input-wrap input{padding-right:48px}.vacation-input-wrap .suffix{position:absolute;right:11px;top:50%;transform:translateY(-50%);pointer-events:none;color:#667085;opacity:.55;font-weight:800;font-size:12px}.sick-days-overview{margin-top:6px;font-size:12px;font-weight:800;color:#b42318;line-height:1.3}.sick-calendar-modal{position:fixed;inset:0;background:rgba(15,36,70,.45);display:none;align-items:center;justify-content:center;padding:18px;z-index:1000}.sick-calendar-modal.open{display:flex}.sick-calendar-panel{width:min(520px,100%);background:#fff;border-radius:22px;border:1px solid var(--line);box-shadow:0 24px 70px rgba(16,24,40,.25);padding:18px}.sick-calendar-head{display:flex;justify-content:space-between;gap:12px;align-items:center;margin-bottom:12px}.sick-calendar-week,.sick-calendar-grid{display:grid;grid-template-columns:repeat(7,1fr);gap:6px}.sick-calendar-week div{text-align:center;color:#667085;font-size:12px;font-weight:900;padding:5px}.sick-day{min-height:46px;padding:8px 4px;border-radius:12px;text-align:center;font-weight:900;touch-action:none;user-select:none}.sick-day.selected{background:#fee4e2;border-color:#f04438;color:#b42318}.sick-day.blank{visibility:hidden}.sick-calendar-hint{font-size:12px;color:#667085;margin:10px 0}.global-v-toggle{display:inline-flex!important;align-items:center;gap:5px;font-size:11px;font-weight:900;color:#667085;margin-top:5px;white-space:nowrap}.global-v-toggle input{width:auto!important;margin:0!important;padding:0!important}.group-member-preview{margin-top:8px;padding:8px;border-radius:12px;background:#f8fafc;border:1px dashed #cfd6e3;font-size:12px;color:#344054;min-width:0;max-width:100%;overflow:auto}.group-member-preview table{min-width:0!important;width:100%;font-size:12px}.group-member-preview th,.group-member-preview td{padding:4px 5px;white-space:nowrap}.group-worked-note{font-size:12px;color:#667085;margin-top:4px}.group-mini-form{display:flex;flex-wrap:wrap;gap:7px;align-items:center}.group-mini-form select{width:78px}.group-mini-form input[name=item_hours]{width:58px}.group-mini-form input[name=item_note]{width:105px}.group-mini-form button{width:auto}.driver-balance-mini{display:block;margin-top:4px;font-size:11px;font-weight:900;opacity:.68;line-height:1.1;letter-spacing:.01em}.month-locked-note{margin-top:10px;padding:10px 12px;border-radius:12px;background:#fff7ed;border:1px solid #fed7aa;color:#b54708;font-weight:800;font-size:13px}

@media(min-width:901px){.table-wrap.mobile-cards{max-height:calc(100vh - 230px);overflow:auto;position:relative}.months-table th,.payroll-table th{position:sticky;top:0;z-index:20;background:#f3f6fb}}
@media(max-width:900px){.shell{display:block}.side{position:relative;height:auto}.main{padding:14px}.grid-2,.grid-3,.grid-4{grid-template-columns:1fr}.top{display:block}.title{font-size:1.55rem}.mini-form{grid-template-columns:1fr}.table-wrap.mobile-cards{overflow:visible;border:0;background:transparent}.months-table{min-width:0;display:block}.months-table thead{display:none}.months-table tbody,.months-table tr,.months-table td{display:block;width:100%}.months-table tr{margin-bottom:14px;border:1px solid var(--line);border-radius:18px;background:#fff;box-shadow:var(--shadow);overflow:hidden}.months-table td{border-bottom:1px solid #edf0f5;padding:10px 12px}.months-table td::before{content:attr(data-label);display:block;font-size:12px;font-weight:900;color:#667085;margin-bottom:5px}.months-table .mobile-row-title{display:block}.months-table input[name=worked_hours],.months-table input[name=payroll_hours],.months-table input[name=v_note]{max-width:100%;width:100%}.admin-info{min-width:0}.col-adjust{width:auto}.compact-save{flex-direction:row;flex-wrap:wrap}.item-row{align-items:flex-start}.side .muted{display:none}}
"""

# ---------------- basic helpers ----------------
def ensure_paths() -> None:
    DATA_ROOT.mkdir(parents=True, exist_ok=True)
    FILES_DIR.mkdir(parents=True, exist_ok=True)
    ATTACHMENTS_DIR.mkdir(parents=True, exist_ok=True)
    EXPORT_DIR.mkdir(parents=True, exist_ok=True)
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def current_edit_year_month() -> Tuple[int, int]:
    """Latest month that may be edited in admin monthly tabs.

    A month opens automatically when the server date reaches the first day
    of that month. This prevents accidental entries in future months.
    """
    timezone_name = os.environ.get("PORTAL_TIMEZONE", "Europe/Berlin")
    try:
        today = datetime.now(ZoneInfo(timezone_name)) if ZoneInfo else datetime.now()
    except Exception:
        today = datetime.now()
    return int(today.year), int(today.month)


def month_is_editable(year: int, month: int) -> bool:
    current_year, current_month = current_edit_year_month()
    return (int(year), int(month)) <= (current_year, current_month)


def month_locked_message(year: int, month: int) -> str:
    month_name = MONATE.get(int(month), str(month))
    return f"{month_name} {year} ist noch nicht zur Bearbeitung freigeschaltet. Eingaben sind erst ab dem 1. {month_name} {year} möglich."


def normalize(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").strip().lower())


def slugify(text: str) -> str:
    repl = {"ä":"ae","ö":"oe","ü":"ue","ß":"ss","Ä":"ae","Ö":"oe","Ü":"ue"}
    for a,b in repl.items():
        text = text.replace(a,b)
    s = re.sub(r"[^a-zA-Z0-9._-]+", ".", (text or "").strip().lower())
    s = re.sub(r"\.+", ".", s).strip(".")
    return s or "fahrer"


def fmt_signed(v: float) -> str:
    return f"{float(v):+.2f}".replace(".", ",")


def fmt_hours(v: float) -> str:
    return f"{float(v):.2f}".replace(".", ",") + " Std."


def fmt_v_input(v_note: Any) -> str:
    """V is a pure note field and never participates in calculations."""
    return str(v_note or "").strip()


def fmt_decimal_input(value: float) -> str:
    amount = round(float(value or 0), 2)
    if abs(amount) < 0.0001:
        return ""
    text = f"{amount:.2f}".replace(".", ",")
    return text[:-3] if text.endswith(",00") else text


def parse_decimal(raw: str) -> float:
    text = (raw or "").strip()
    if not text:
        return 0.0
    return float(text.replace(".", "").replace(",", "."))


def normalize_day_ranges(raw: str) -> str:
    text = (raw or "").strip()
    if not text:
        return ""
    text = text.replace("–", "-").replace("—", "-").replace("/", ",").replace(";", ",")
    parts = [p.strip() for p in text.split(",") if p.strip()]
    clean = []
    for part in parts:
        m = re.fullmatch(r"(\d{1,2})(?:\s*-\s*(\d{1,2}))?", part)
        if not m:
            raise ValueError("Tage bitte so eingeben: 9-13, 16-20, 28")
        a = int(m.group(1)); b = int(m.group(2) or a)
        if a < 1 or a > 31 or b < 1 or b > 31 or b < a:
            raise ValueError("Tage müssen zwischen 1 und 31 liegen, z.B. 9-13, 16-20, 28")
        clean.append(str(a) if a == b else f"{a}-{b}")
    return ", ".join(clean)


EMPLOYMENT_TYPES = {"vollzeit", "teilzeit", "aushilfe"}

def normalize_employment_type(raw: str) -> str:
    value = (raw or "").strip().lower()
    return value if value in EMPLOYMENT_TYPES else ""

def employment_class(raw: Any) -> str:
    value = normalize_employment_type(str(raw or ""))
    return f"employment-{value}" if value else ""

def _expand_day_ranges(raw: str) -> List[int]:
    text = normalize_day_ranges(raw)
    if not text:
        return []
    days = set()
    for part in [p.strip() for p in text.split(",") if p.strip()]:
        if "-" in part:
            a, b = [int(x.strip()) for x in part.split("-", 1)]
            days.update(range(a, b + 1))
        else:
            days.add(int(part))
    return sorted(days)

def normalize_vacation_count(raw: str) -> str:
    text = (raw or "").strip()
    if not text:
        return ""
    if re.fullmatch(r"\d{1,2}", text):
        value = int(text)
        if 0 <= value <= 31:
            return str(value)
        raise ValueError("Urlaubstage müssen zwischen 0 und 31 liegen.")
    # Backward compatibility: old day ranges are converted to a day count on save.
    return str(len(_expand_day_ranges(text)))

def vacation_display(raw: Any) -> str:
    text = str(raw or "").strip()
    if not text:
        return ""
    try:
        return normalize_vacation_count(text)
    except Exception:
        return text

def row_get(row: Any, key: str, default: Any = "") -> Any:
    try:
        return row[key] if hasattr(row, "keys") and key in set(row.keys()) else default
    except Exception:
        return default


def safe_float(value: Any) -> float:
    try:
        return float(value or 0)
    except Exception:
        return 0.0


def group_display_name(group: Any, members: List[Any]) -> str:
    manual = str(row_get(group, "name", "") or "").strip()
    if manual:
        return manual
    names = [str(row_get(m, "name", "")).strip() for m in members if str(row_get(m, "name", "")).strip()]
    if not names:
        return "Fahrergruppe"
    if len(names) == 1:
        return names[0]
    return " und ".join(names)


def load_driver_groups(conn) -> List[Dict[str, Any]]:
    groups: List[Dict[str, Any]] = []
    for g in conn.execute("SELECT * FROM driver_groups WHERE is_active=1 ORDER BY id").fetchall():
        members = conn.execute("""
            SELECT d.*
            FROM driver_group_members gm
            JOIN drivers d ON d.id=gm.driver_id
            WHERE gm.group_id=? AND d.is_active=1 AND COALESCE(d.is_disposition,0)=0
            ORDER BY COALESCE(NULLIF(gm.position,0), d.display_order, d.id), d.name COLLATE NOCASE
        """, (g["id"],)).fetchall()
        if members:
            groups.append({"group": g, "members": members, "member_ids": [int(m["id"]) for m in members], "name": group_display_name(g, members)})
    return groups


def get_group_month_override(conn, group_id: int, year: int, month: int) -> Optional[Any]:
    try:
        return conn.execute("SELECT * FROM driver_group_month_data WHERE group_id=? AND year=? AND month=?", (group_id, year, month)).fetchone()
    except Exception:
        return None


def make_group_member_preview(conn, group_info: Dict[str, Any], year: int, month: int) -> List[Dict[str, Any]]:
    preview: List[Dict[str, Any]] = []
    for member in group_info["members"]:
        r = conn.execute("SELECT * FROM monthly_data WHERE driver_id=? AND year=? AND month=?", (int(member["id"]), year, month)).fetchone()
        preview.append({
            "name": member["name"],
            "worked_hours": safe_float(row_get(r, "worked_hours", 0)) if r else 0,
            "payroll_hours": safe_float(row_get(r, "payroll_hours", 0)) if r else 0,
            "v_hours": 0,
            "v_note": str(row_get(r, "v_note", "") or "") if r else "",
            "employment_type": str(row_get(member, "employment_type", "") or ""),
            "bonus_hours": safe_float(row_get(r, "bonus_hours", 0)) if r else 0,
            "deduction_hours": safe_float(row_get(r, "deduction_hours", 0)) if r else 0,
            "difference_hours": safe_float(row_get(r, "difference_hours", 0)) if r else 0,
        })
    return preview


def make_group_month_summary(conn, group_info: Dict[str, Any], year: int, month: int) -> Dict[str, Any]:
    rows = []
    for did in group_info["member_ids"]:
        r = conn.execute("SELECT * FROM monthly_data WHERE driver_id=? AND year=? AND month=?", (did, year, month)).fetchone()
        if r:
            rows.append(r)
    numeric = ["worked_hours", "payroll_hours", "bonus_hours", "deduction_hours", "adjustment_hours", "difference_hours", "previous_balance", "new_balance", "payroll_surcharge", "fuel_voucher"]
    summary: Dict[str, Any] = {"driver_id": f"group_{group_info['group']['id']}", "year": year, "month": month, "admin_info_carried": 0, "v_enabled": 0, "v_note": "", "v_hours": 0}
    for key in numeric:
        summary[key] = round(sum(safe_float(row_get(r, key, 0)) for r in rows), 2)
    override = get_group_month_override(conn, int(group_info["group"]["id"]), year, month)
    if override and row_get(override, "worked_hours", None) is not None:
        summary["worked_hours"] = round(safe_float(row_get(override, "worked_hours", 0)), 2)
    for key in ["admin_info", "bonus_comment", "deduction_comment", "comment", "payroll_office_info", "vacation_days", "sick_days"]:
        vals = []
        for r in rows:
            val = str(row_get(r, key, "") or "").strip()
            if val:
                vals.append(val)
        summary[key] = "\n".join(vals)
    v_notes = []
    for member in group_info["members"]:
        mr = conn.execute("SELECT v_note FROM monthly_data WHERE driver_id=? AND year=? AND month=?", (int(member["id"]), year, month)).fetchone()
        note = str(row_get(mr, "v_note", "") or "").strip() if mr else ""
        if note:
            v_notes.append(f"{member['name']}: {note}")
    summary["v_note"] = " | ".join(v_notes)
    if override:
        summary["v_enabled"] = 1 if row_v_enabled(override) else 0
        group_admin = str(row_get(override, "admin_info", "") or "").strip()
        if group_admin:
            summary["admin_info"] = group_admin
        group_items = get_group_adjustment_items(conn, int(row_get(override, "id", 0) or 0))
        if group_items:
            group_bonus = round(sum(abs(safe_float(i["hours"])) for i in group_items if i["kind"] == "bonus"), 2)
            group_deduction = round(-sum(abs(safe_float(i["hours"])) for i in group_items if i["kind"] == "deduction"), 2)
            summary["bonus_hours"] = round(safe_float(summary.get("bonus_hours")) + group_bonus, 2)
            summary["deduction_hours"] = round(safe_float(summary.get("deduction_hours")) + group_deduction, 2)
            group_bonus_comment = "\n".join(f'{fmt_hours(abs(safe_float(i["hours"])))} - {i["note"]}' for i in group_items if i["kind"] == "bonus")
            group_deduction_comment = "\n".join(f'{fmt_hours(-abs(safe_float(i["hours"])))} - {i["note"]}' for i in group_items if i["kind"] == "deduction")
            if group_bonus_comment:
                summary["bonus_comment"] = (summary.get("bonus_comment", "") + "\n" + group_bonus_comment).strip()
            if group_deduction_comment:
                summary["deduction_comment"] = (summary.get("deduction_comment", "") + "\n" + group_deduction_comment).strip()
            summary["adjustment_hours"] = round(safe_float(summary.get("bonus_hours")) + safe_float(summary.get("deduction_hours")), 2)
    summary["difference_hours"] = compute_difference(summary["worked_hours"], summary["payroll_hours"], 0, summary["bonus_hours"], summary["deduction_hours"], 0)
    return summary


def ensure_group_month_row(conn, group_id: int, year: int, month: int) -> int:
    row = conn.execute("SELECT id FROM driver_group_month_data WHERE group_id=? AND year=? AND month=?", (group_id, year, month)).fetchone()
    if row:
        return int(row["id"])
    cur = conn.execute("INSERT INTO driver_group_month_data(group_id, year, month, worked_hours, v_enabled, admin_info, updated_at) VALUES(?,?,?,?,?,?,?)", (group_id, year, month, 0, 0, "", now_iso()))
    return int(cur.lastrowid)


def get_group_adjustment_items(conn, group_month_data_id: int) -> List[Any]:
    if not group_month_data_id:
        return []
    try:
        return conn.execute("SELECT * FROM driver_group_adjustment_items WHERE group_month_data_id=? ORDER BY id", (group_month_data_id,)).fetchall()
    except Exception:
        return []


def get_group_for_driver(conn, driver_id: int) -> Optional[Dict[str, Any]]:
    row = conn.execute("SELECT group_id FROM driver_group_members WHERE driver_id=?", (driver_id,)).fetchone()
    if not row:
        return None
    gid = int(row["group_id"])
    for g in load_driver_groups(conn):
        if int(g["group"]["id"]) == gid:
            return g
    return None


def sync_group_admin_info(conn, group_id: int, year: int, month: int, admin_info: str) -> None:
    """Keep the internal admin note identical in both admin tabs for a driver group."""
    text = (admin_info or "").strip()
    group_month_id = ensure_group_month_row(conn, group_id, year, month)
    conn.execute(
        "UPDATE driver_group_month_data SET admin_info=?, updated_at=? WHERE id=?",
        (text, now_iso(), group_month_id),
    )
    members = conn.execute(
        """
        SELECT d.id
        FROM driver_group_members gm
        JOIN drivers d ON d.id=gm.driver_id
        WHERE gm.group_id=? AND d.is_active=1 AND COALESCE(d.is_disposition,0)=0
        ORDER BY COALESCE(NULLIF(gm.position,0), d.display_order, d.id), d.name COLLATE NOCASE
        """,
        (group_id,),
    ).fetchall()
    for member in members:
        monthly_id = get_or_create_month_row(conn, int(member["id"]), year, month)
        conn.execute(
            "UPDATE monthly_data SET admin_info=?, admin_info_carried=0, updated_at=? WHERE id=?",
            (text, now_iso(), monthly_id),
        )


def sync_member_admin_info_to_group(conn, driver_id: int, year: int, month: int, admin_info: str) -> None:
    """When a grouped driver is edited in payroll, mirror the note to the group and all members."""
    group_info = get_group_for_driver(conn, driver_id)
    if not group_info:
        return
    sync_group_admin_info(conn, int(group_info["group"]["id"]), year, month, admin_info)


def group_pdf_relative_path(group_id: int, group_name: str, year: int, month: int) -> Path:
    safe_name = secure_filename(f"{month:02d}_{MONATE.get(month, str(month))}_{year}_gruppe.pdf")
    return Path("pdfs") / (slugify(group_name) + f"-gruppe-{group_id}") / str(year) / safe_name


def create_group_pdf(conn, group_info: Dict[str, Any], year: int, month: int) -> Path:
    group_id = int(group_info["group"]["id"])
    group_name = group_info["name"]
    r = make_group_month_summary(conn, group_info, year, month)
    pdf_path = DATA_ROOT / group_pdf_relative_path(group_id, group_name, year, month)
    extra_story: List[Any] = []
    styles = getSampleStyleSheet()
    attachment_title = ParagraphStyle("AttachmentTitle", parent=styles["Heading2"], fontName="Helvetica-Bold", fontSize=12, leading=14, textColor=colors.HexColor("#123e7c"), spaceBefore=10, spaceAfter=6)
    attachment_text = ParagraphStyle("AttachmentText", parent=styles["BodyText"], fontName="Helvetica", fontSize=9, leading=11, textColor=colors.HexColor("#111827"))
    group_month_id = ensure_group_month_row(conn, group_id, year, month)
    attachments = conn.execute("""
        SELECT gf.*, gi.kind, gi.hours, gi.note
        FROM driver_group_adjustment_files gf
        JOIN driver_group_adjustment_items gi ON gi.id=gf.group_adjustment_item_id
        WHERE gi.group_month_data_id=? AND gi.kind='deduction'
        ORDER BY gi.id, gf.id
    """, (group_month_id,)).fetchall()
    if attachments:
        extra_story.extend([Spacer(1, 6*mm), Paragraph("Anhänge zu Abzügen", attachment_title)])
        for att in attachments:
            path = DATA_ROOT / att["relative_path"]
            extra_story.append(Paragraph(f"Abzug {fmt_hours(-abs(safe_float(att['hours'])))} – {att['note']}", attachment_text))
            if path.exists() and path.suffix.lower().lstrip(".") in IMAGE_ATTACHMENT_EXTENSIONS:
                try:
                    extra_story.append(Image(str(path), width=120*mm, height=80*mm, kind="proportional"))
                    extra_story.append(Spacer(1, 4*mm))
                except Exception:
                    extra_story.append(Paragraph(f"Datei: {att['original_filename'] or att['filename']}", attachment_text))
            else:
                extra_story.append(Paragraph(f"Datei: {att['original_filename'] or att['filename']}", attachment_text))
                extra_story.append(Spacer(1, 3*mm))
    create_pdf_report(pdf_path, f"Monatsübersicht {group_name} – {MONATE[month]} {year}", "+ - Stunden", ["Fahrer","Stunden","Abrechnung","V","Zuschüsse","Abzüge","Differenz","Aktueller\nStand","Neuer\nStand"], [[
        group_name, fmt_hours(r["worked_hours"]), fmt_hours(r["payroll_hours"]), fmt_v_display(r.get("v_note", ""), r.get("v_enabled", 0), True),
        (r.get("bonus_comment") or "-").strip() or "-", (r.get("deduction_comment") or "-").strip() or "-",
        fmt_signed(r["difference_hours"]), fmt_signed(r["previous_balance"]), fmt_signed(r["new_balance"])
    ]], extra_story=extra_story)
    return pdf_path

def signed_class(v: float) -> str:
    v = float(v or 0)
    return "pos" if v > 0 else "neg" if v < 0 else "zero"


def normalize_balance_sort(raw: str) -> str:
    raw = (raw or "").strip().lower()
    return raw if raw in {"asc", "desc"} else "order"


def normalize_driver_sort_mode(raw: str) -> str:
    raw = (raw or "").strip().lower()
    return raw if raw in {"custom", "name_az"} else "custom"


def balance_value(row: Any) -> float:
    return safe_float(row_get(row, "bal", row_get(row, "starting_balance", 0)) if row_get(row, "bal", None) is not None else row_get(row, "starting_balance", 0))


def load_current_balances(conn: sqlite3.Connection, sort_mode: str = "order") -> List[Any]:
    rows = list(conn.execute("""
        SELECT d.id,d.name,d.starting_balance,
               (SELECT new_balance FROM monthly_data m WHERE m.driver_id=d.id ORDER BY year DESC, month DESC, id DESC LIMIT 1) bal
        FROM drivers d
        WHERE d.is_active=1 AND COALESCE(d.is_disposition,0)=0
        ORDER BY COALESCE(NULLIF(d.display_order,0), d.id), d.name COLLATE NOCASE
    """).fetchall())
    sort_mode = normalize_balance_sort(sort_mode)
    if sort_mode == "asc":
        rows.sort(key=lambda r: (balance_value(r), normalize(str(row_get(r, "name", "")))))
    elif sort_mode == "desc":
        rows.sort(key=lambda r: (-balance_value(r), normalize(str(row_get(r, "name", "")))))
    return rows


DRIVER_SORT_MODE_KEY = "drivers_sort_mode"
DRIVER_CUSTOM_ORDER_KEY = "drivers_custom_order"


def get_app_setting(conn: sqlite3.Connection, key: str, default: str = "") -> str:
    try:
        row = conn.execute("SELECT setting_value FROM app_settings WHERE setting_key=?", (key,)).fetchone()
        return str(row["setting_value"] if row else default)
    except Exception:
        return default


def set_app_setting(conn: sqlite3.Connection, key: str, value: str) -> None:
    conn.execute(
        """
        INSERT INTO app_settings(setting_key, setting_value, updated_at) VALUES(?,?,?)
        ON CONFLICT(setting_key) DO UPDATE SET setting_value=excluded.setting_value, updated_at=excluded.updated_at
        """,
        (key, value, now_iso()),
    )


def get_driver_sort_mode(conn: sqlite3.Connection) -> str:
    return normalize_driver_sort_mode(get_app_setting(conn, DRIVER_SORT_MODE_KEY, "custom"))


def set_driver_sort_mode(conn: sqlite3.Connection, mode: str) -> None:
    set_app_setting(conn, DRIVER_SORT_MODE_KEY, normalize_driver_sort_mode(mode))


def current_driver_order_ids(conn: sqlite3.Connection) -> List[int]:
    return [
        int(r["id"])
        for r in conn.execute(
            "SELECT id FROM drivers WHERE COALESCE(is_disposition,0)=0 ORDER BY COALESCE(NULLIF(display_order,0), id), name COLLATE NOCASE"
        ).fetchall()
    ]


def alpha_driver_order_ids(conn: sqlite3.Connection) -> List[int]:
    rows = list(conn.execute("SELECT id, name, display_order FROM drivers WHERE COALESCE(is_disposition,0)=0").fetchall())
    rows.sort(key=lambda r: (normalize(str(row_get(r, "name", ""))), safe_float(row_get(r, "display_order", 0)), int(row_get(r, "id", 0))))
    return [int(r["id"]) for r in rows]


def apply_driver_order(conn: sqlite3.Connection, ordered_ids: List[int]) -> List[int]:
    valid_ids = current_driver_order_ids(conn)
    valid_set = set(valid_ids)
    final_order: List[int] = []
    for driver_id in ordered_ids:
        try:
            did = int(driver_id)
        except Exception:
            continue
        if did in valid_set and did not in final_order:
            final_order.append(did)
    for did in valid_ids:
        if did not in final_order:
            final_order.append(did)
    for pos, driver_id in enumerate(final_order, start=1):
        conn.execute("UPDATE drivers SET display_order=?, updated_at=? WHERE id=?", (pos, now_iso(), driver_id))
    return final_order


def save_custom_driver_order(conn: sqlite3.Connection, ordered_ids: Optional[List[int]] = None) -> None:
    order = ordered_ids if ordered_ids is not None else current_driver_order_ids(conn)
    set_app_setting(conn, DRIVER_CUSTOM_ORDER_KEY, json.dumps([int(x) for x in order]))


def sort_drivers_name_az(conn: sqlite3.Connection) -> None:
    if get_driver_sort_mode(conn) != "name_az":
        save_custom_driver_order(conn)
    apply_driver_order(conn, alpha_driver_order_ids(conn))
    set_driver_sort_mode(conn, "name_az")


def restore_custom_driver_order(conn: sqlite3.Connection) -> None:
    raw = get_app_setting(conn, DRIVER_CUSTOM_ORDER_KEY, "")
    try:
        saved_order = json.loads(raw) if raw else []
    except Exception:
        saved_order = []
    final_order = apply_driver_order(conn, [int(x) for x in saved_order if str(x).isdigit()]) if saved_order else current_driver_order_ids(conn)
    save_custom_driver_order(conn, final_order)
    set_driver_sort_mode(conn, "custom")


def parse_hours(raw: str) -> float:
    text = (raw or "").strip().lower().replace(" ", "")
    if not text:
        return 0.0
    if re.fullmatch(r"[+-]?\d+[:h]\d{1,2}", text):
        sign = -1 if text.startswith("-") else 1
        clean = text[1:] if text[:1] in "+-" else text
        h, m = re.split(r"[:h]", clean)
        if int(m) >= 60:
            raise ValueError("Minuten müssen kleiner als 60 sein.")
        return sign * (int(h) + int(m) / 60)
    direct = text.replace(",", ".")
    if re.fullmatch(r"[+-]?\d+(\.\d+)?", direct):
        return float(direct)
    nums = re.findall(r"[+-]?\d+(?:[\.,]\d+)?", text)
    if nums and ("+" in text or any(ch.isalpha() for ch in text)):
        return round(sum(float(n.replace(",", ".")) for n in nums), 2)
    raise ValueError("Ungültiges Stundenformat. Beispiele: 145,5 | 145:30 | 130+15 | -0,5")


def parse_german_money(raw: str) -> float:
    return float(str(raw).replace(".", "").replace(",", ".").strip())


def v_is_enabled(value: Any = 0) -> bool:
    try:
        return int(value if value is not None else 0) != 0
    except Exception:
        return False

def row_v_enabled(row: Any) -> bool:
    return v_is_enabled(row_get(row, "v_enabled", 0))

def form_v_enabled(name: str = "v_enabled", default: int = 0) -> int:
    values = request.form.getlist(name)
    if not values:
        return 1 if default else 0
    return 1 if "1" in values else 0

def fmt_v_display(v_note: Any, v_enabled: Any = 0, hours: bool = True) -> str:
    text = str(v_note or "").strip()
    if not text:
        return "-"
    return text if v_is_enabled(v_enabled) else f"{text} (inaktiv)"

def compute_difference(worked: float, payroll: float, v: Any = 0, bonus: float = 0, deduction: float = 0, v_enabled: Any = 0) -> float:
    # V is deliberately excluded from every calculation. It is a note only.
    return round(float(worked) - float(payroll) + float(bonus) + float(deduction), 2)


def make_unique_username(conn: sqlite3.Connection, username: str, exclude_id: Optional[int] = None) -> str:
    base = slugify(username)
    candidate = base
    n = 2
    while True:
        if exclude_id:
            row = conn.execute("SELECT id FROM drivers WHERE lower(username)=lower(?) AND id<>?", (candidate, exclude_id)).fetchone()
        else:
            row = conn.execute("SELECT id FROM drivers WHERE lower(username)=lower(?)", (candidate,)).fetchone()
        if not row:
            return candidate
        candidate = f"{base}.{n}"
        n += 1


def password_candidates_for_driver(row: Any) -> List[str]:
    """Known/likely legacy password candidates used only to recover display text from existing hashes.

    Existing hashes cannot be decoded. This safely tests likely old default values
    against the hash and stores the plain text only when it is an exact match.
    """
    name = str(row_get(row, "name", "") or "").strip()
    username = str(row_get(row, "username", "") or "").strip()
    ext = row_get(row, "external_driver_id", "")
    name_slug = slugify(name)
    compact_name = re.sub(r"\s+", "", name.lower())
    first_name = name.split()[0].lower() if name.split() else ""
    raw_candidates = [
        ADMIN_PASSWORD, ADMIN_API_TOKEN, "0341", "1234",
        username, username.lower(), username.replace(".", ""),
        name_slug, name_slug.replace(".", ""), compact_name, first_name,
        str(ext or ""),
    ]
    extra = os.environ.get("PASSWORD_BACKFILL_CANDIDATES", "")
    if extra:
        raw_candidates.extend([x.strip() for x in re.split(r"[,;\n]+", extra) if x.strip()])
    seen = set()
    candidates: List[str] = []
    for c in raw_candidates:
        c = str(c or "").strip()
        if c and c not in seen:
            seen.add(c)
            candidates.append(c)
    return candidates


def backfill_visible_passwords(conn: sqlite3.Connection) -> int:
    """Fill password_plain for old accounts when the old password can be verified.

    Important: Password hashes are one-way. This does not crack or change unknown
    passwords. It only records the plain text when a likely known password exactly
    matches the stored hash.
    """
    try:
        rows = conn.execute(
            "SELECT id, name, username, external_driver_id, password_hash FROM drivers WHERE COALESCE(password_plain,'')=''"
        ).fetchall()
    except Exception:
        return 0
    updated = 0
    for row in rows:
        stored_hash = str(row_get(row, "password_hash", "") or "")
        if not stored_hash:
            continue
        for candidate in password_candidates_for_driver(row):
            try:
                if check_password_hash(stored_hash, candidate):
                    conn.execute("UPDATE drivers SET password_plain=?, updated_at=? WHERE id=?", (candidate, now_iso(), int(row_get(row, "id", 0))))
                    updated += 1
                    break
            except Exception:
                continue
    return updated

# ---------------- database ----------------
class _PgResult:
    def __init__(self, cursor, lastrowid: Optional[int] = None):
        self.cursor = cursor
        self._lastrowid = lastrowid

    def fetchone(self):
        if self.cursor.description is None:
            return None
        return self.cursor.fetchone()

    def fetchall(self):
        if self.cursor.description is None:
            return []
        return self.cursor.fetchall()

    @property
    def lastrowid(self) -> Optional[int]:
        return self._lastrowid


class _PostgresCompatConnection:
    """Small compatibility layer so the existing SQLite-style app code can use PostgreSQL.

    The rest of the application intentionally stays unchanged: it can still call
    conn.execute(...), use ? placeholders, access rows by column name, and read
    lastrowid after INSERTs.
    """

    _RETURNING_TABLES = {
        "drivers", "monthly_data", "documents", "audit_log", "adjustment_items", "adjustment_files", "driver_groups", "driver_group_members", "driver_group_month_data", "driver_group_adjustment_items", "driver_group_adjustment_files", "month_releases"
    }

    def __init__(self, raw_conn):
        self.raw_conn = raw_conn

    def _translate_sql(self, query: str) -> str:
        q = query.strip()
        q = q.replace("?", "%s")
        # SQLite-specific case-insensitive ordering. PostgreSQL equivalent here is LOWER(...).
        q = q.replace("d.name COLLATE NOCASE", "LOWER(d.name)")
        q = q.replace("name COLLATE NOCASE", "LOWER(name)")
        q = q.replace("m.year,m.month,d.name COLLATE NOCASE", "m.year,m.month,LOWER(d.name)")
        return q

    def _with_returning_id(self, query: str) -> Tuple[str, bool]:
        low = query.lower().strip()
        if not low.startswith("insert into") or " returning " in low:
            return query, False
        m = re.match(r"insert\s+into\s+([a-zA-Z_][a-zA-Z0-9_]*)", low)
        if not m or m.group(1) not in self._RETURNING_TABLES:
            return query, False
        q = query.rstrip().rstrip(";") + " RETURNING id"
        return q, True

    def execute(self, query: str, params: Tuple[Any, ...] = ()):
        q = self._translate_sql(query)
        q, expects_id = self._with_returning_id(q)
        cur = self.raw_conn.cursor()
        cur.execute(q, params)
        lastrowid = None
        if expects_id and cur.description is not None:
            row = cur.fetchone()
            if row is not None:
                lastrowid = int(row["id"])
        return _PgResult(cur, lastrowid)

    def commit(self) -> None:
        self.raw_conn.commit()

    def close(self) -> None:
        self.raw_conn.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        if exc_type:
            self.raw_conn.rollback()
        else:
            self.raw_conn.commit()
        self.raw_conn.close()


def _init_postgres_schema(conn) -> None:
    # Tables are intentionally equivalent to the original SQLite schema.
    conn.execute("""
    CREATE TABLE IF NOT EXISTS drivers(
        id SERIAL PRIMARY KEY,
        external_driver_id INTEGER UNIQUE,
        name TEXT NOT NULL,
        employment_type TEXT NOT NULL DEFAULT '',
        username TEXT NOT NULL UNIQUE,
        password_hash TEXT NOT NULL,
        password_plain TEXT NOT NULL DEFAULT '',
        starting_balance DOUBLE PRECISION NOT NULL DEFAULT 0,
        display_order INTEGER NOT NULL DEFAULT 0,
        is_active INTEGER NOT NULL DEFAULT 1,
        is_disposition INTEGER NOT NULL DEFAULT 0,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL
    )
    """)
    conn.execute("""
    CREATE TABLE IF NOT EXISTS monthly_data(
        id SERIAL PRIMARY KEY,
        driver_id INTEGER NOT NULL REFERENCES drivers(id) ON DELETE CASCADE,
        year INTEGER NOT NULL,
        month INTEGER NOT NULL,
        worked_hours DOUBLE PRECISION NOT NULL DEFAULT 0,
        payroll_hours DOUBLE PRECISION NOT NULL DEFAULT 0,
        v_hours DOUBLE PRECISION NOT NULL DEFAULT 0,
        v_note TEXT NOT NULL DEFAULT '',
        v_enabled INTEGER NOT NULL DEFAULT 0,
        bonus_hours DOUBLE PRECISION NOT NULL DEFAULT 0,
        bonus_comment TEXT NOT NULL DEFAULT '',
        deduction_hours DOUBLE PRECISION NOT NULL DEFAULT 0,
        deduction_comment TEXT NOT NULL DEFAULT '',
        adjustment_hours DOUBLE PRECISION NOT NULL DEFAULT 0,
        comment TEXT NOT NULL DEFAULT '',
        admin_info TEXT NOT NULL DEFAULT '',
        admin_info_carried INTEGER NOT NULL DEFAULT 0,
        payroll_office_info TEXT NOT NULL DEFAULT '',
        payroll_surcharge DOUBLE PRECISION NOT NULL DEFAULT 0,
        fuel_voucher DOUBLE PRECISION NOT NULL DEFAULT 0,
        payroll_carry_initialized INTEGER NOT NULL DEFAULT 0,
        vacation_days TEXT NOT NULL DEFAULT '',
        sick_days TEXT NOT NULL DEFAULT '',
        difference_hours DOUBLE PRECISION NOT NULL DEFAULT 0,
        previous_balance DOUBLE PRECISION NOT NULL DEFAULT 0,
        new_balance DOUBLE PRECISION NOT NULL DEFAULT 0,
        updated_at TEXT NOT NULL,
        UNIQUE(driver_id, year, month)
    )
    """)
    conn.execute("""
    CREATE TABLE IF NOT EXISTS documents(
        id SERIAL PRIMARY KEY,
        driver_id INTEGER NOT NULL REFERENCES drivers(id) ON DELETE CASCADE,
        year INTEGER NOT NULL,
        month INTEGER NOT NULL,
        filename TEXT NOT NULL,
        original_filename TEXT NOT NULL,
        relative_path TEXT NOT NULL UNIQUE,
        uploaded_at TEXT NOT NULL,
        UNIQUE(driver_id, year, month)
    )
    """)
    conn.execute("""
    CREATE TABLE IF NOT EXISTS audit_log(
        id SERIAL PRIMARY KEY,
        actor TEXT NOT NULL,
        action TEXT NOT NULL,
        details TEXT NOT NULL DEFAULT '',
        created_at TEXT NOT NULL
    )
    """)
    conn.execute("""
    CREATE TABLE IF NOT EXISTS app_settings(
        setting_key TEXT PRIMARY KEY,
        setting_value TEXT NOT NULL DEFAULT '',
        updated_at TEXT NOT NULL
    )
    """)
    conn.execute("""
    CREATE TABLE IF NOT EXISTS adjustment_items(
        id SERIAL PRIMARY KEY,
        monthly_data_id INTEGER NOT NULL REFERENCES monthly_data(id) ON DELETE CASCADE,
        kind TEXT NOT NULL,
        hours DOUBLE PRECISION NOT NULL DEFAULT 0,
        note TEXT NOT NULL DEFAULT '',
        created_at TEXT NOT NULL
    )
    """)
    conn.execute("""
    CREATE TABLE IF NOT EXISTS adjustment_files(
        id SERIAL PRIMARY KEY,
        adjustment_item_id INTEGER NOT NULL REFERENCES adjustment_items(id) ON DELETE CASCADE,
        filename TEXT NOT NULL,
        original_filename TEXT NOT NULL DEFAULT '',
        relative_path TEXT NOT NULL UNIQUE,
        mime_type TEXT NOT NULL DEFAULT '',
        uploaded_at TEXT NOT NULL
    )
    """)
    conn.execute("""
    CREATE TABLE IF NOT EXISTS driver_groups(
        id SERIAL PRIMARY KEY,
        name TEXT NOT NULL DEFAULT '',
        is_active INTEGER NOT NULL DEFAULT 1,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL
    )
    """)
    conn.execute("""
    CREATE TABLE IF NOT EXISTS driver_group_members(
        id SERIAL PRIMARY KEY,
        group_id INTEGER NOT NULL REFERENCES driver_groups(id) ON DELETE CASCADE,
        driver_id INTEGER NOT NULL REFERENCES drivers(id) ON DELETE CASCADE,
        position INTEGER NOT NULL DEFAULT 0,
        UNIQUE(group_id, driver_id),
        UNIQUE(driver_id)
    )
    """)

    conn.execute("""
    CREATE TABLE IF NOT EXISTS driver_group_month_data(
        id SERIAL PRIMARY KEY,
        group_id INTEGER NOT NULL REFERENCES driver_groups(id) ON DELETE CASCADE,
        year INTEGER NOT NULL,
        month INTEGER NOT NULL,
        worked_hours DOUBLE PRECISION NOT NULL DEFAULT 0,
        v_enabled INTEGER NOT NULL DEFAULT 0,
        admin_info TEXT NOT NULL DEFAULT '',
        updated_at TEXT NOT NULL,
        UNIQUE(group_id, year, month)
    )
    """)
    conn.execute("""
    CREATE TABLE IF NOT EXISTS driver_group_adjustment_items(
        id SERIAL PRIMARY KEY,
        group_month_data_id INTEGER NOT NULL REFERENCES driver_group_month_data(id) ON DELETE CASCADE,
        kind TEXT NOT NULL,
        hours DOUBLE PRECISION NOT NULL DEFAULT 0,
        note TEXT NOT NULL DEFAULT '',
        created_at TEXT NOT NULL
    )
    """)
    conn.execute("""
    CREATE TABLE IF NOT EXISTS driver_group_adjustment_files(
        id SERIAL PRIMARY KEY,
        group_adjustment_item_id INTEGER NOT NULL REFERENCES driver_group_adjustment_items(id) ON DELETE CASCADE,
        filename TEXT NOT NULL,
        original_filename TEXT NOT NULL DEFAULT '',
        relative_path TEXT NOT NULL UNIQUE,
        mime_type TEXT NOT NULL DEFAULT '',
        uploaded_at TEXT NOT NULL
    )
    """)
    conn.execute("""
    CREATE TABLE IF NOT EXISTS month_releases(
        id SERIAL PRIMARY KEY,
        year INTEGER NOT NULL,
        month INTEGER NOT NULL,
        is_released INTEGER NOT NULL DEFAULT 0,
        updated_at TEXT NOT NULL,
        UNIQUE(year, month)
    )
    """)
    # Safe migrations for existing PostgreSQL databases.
    migrations = [
        "ALTER TABLE drivers ADD COLUMN IF NOT EXISTS starting_balance DOUBLE PRECISION NOT NULL DEFAULT 0",
        "ALTER TABLE drivers ADD COLUMN IF NOT EXISTS display_order INTEGER NOT NULL DEFAULT 0",
        "ALTER TABLE drivers ADD COLUMN IF NOT EXISTS is_disposition INTEGER NOT NULL DEFAULT 0",
        "ALTER TABLE drivers ADD COLUMN IF NOT EXISTS password_plain TEXT NOT NULL DEFAULT ''",
        "ALTER TABLE drivers ADD COLUMN IF NOT EXISTS employment_type TEXT NOT NULL DEFAULT ''",
        "ALTER TABLE monthly_data ADD COLUMN IF NOT EXISTS v_note TEXT NOT NULL DEFAULT ''",
        "ALTER TABLE monthly_data ADD COLUMN IF NOT EXISTS v_enabled INTEGER NOT NULL DEFAULT 0",
        "ALTER TABLE monthly_data ADD COLUMN IF NOT EXISTS payroll_carry_initialized INTEGER NOT NULL DEFAULT 0",
        "ALTER TABLE monthly_data ADD COLUMN IF NOT EXISTS bonus_hours DOUBLE PRECISION NOT NULL DEFAULT 0",
        "ALTER TABLE monthly_data ADD COLUMN IF NOT EXISTS bonus_comment TEXT NOT NULL DEFAULT ''",
        "ALTER TABLE monthly_data ADD COLUMN IF NOT EXISTS deduction_hours DOUBLE PRECISION NOT NULL DEFAULT 0",
        "ALTER TABLE monthly_data ADD COLUMN IF NOT EXISTS deduction_comment TEXT NOT NULL DEFAULT ''",
        "ALTER TABLE monthly_data ADD COLUMN IF NOT EXISTS admin_info TEXT NOT NULL DEFAULT ''",
        "ALTER TABLE monthly_data ADD COLUMN IF NOT EXISTS admin_info_carried INTEGER NOT NULL DEFAULT 0",
        "ALTER TABLE monthly_data ADD COLUMN IF NOT EXISTS adjustment_hours DOUBLE PRECISION NOT NULL DEFAULT 0",
        "ALTER TABLE monthly_data ADD COLUMN IF NOT EXISTS comment TEXT NOT NULL DEFAULT ''",
        "ALTER TABLE monthly_data ADD COLUMN IF NOT EXISTS payroll_office_info TEXT NOT NULL DEFAULT ''",
        "ALTER TABLE monthly_data ADD COLUMN IF NOT EXISTS payroll_surcharge DOUBLE PRECISION NOT NULL DEFAULT 0",
        "ALTER TABLE monthly_data ADD COLUMN IF NOT EXISTS fuel_voucher DOUBLE PRECISION NOT NULL DEFAULT 0",
        "ALTER TABLE monthly_data ADD COLUMN IF NOT EXISTS vacation_days TEXT NOT NULL DEFAULT ''",
        "ALTER TABLE monthly_data ADD COLUMN IF NOT EXISTS sick_days TEXT NOT NULL DEFAULT ''",
        "ALTER TABLE adjustment_files ADD COLUMN IF NOT EXISTS original_filename TEXT NOT NULL DEFAULT ''",
        "ALTER TABLE adjustment_files ADD COLUMN IF NOT EXISTS mime_type TEXT NOT NULL DEFAULT ''",
        "ALTER TABLE driver_group_month_data ADD COLUMN IF NOT EXISTS admin_info TEXT NOT NULL DEFAULT ''",
        "ALTER TABLE driver_group_month_data ADD COLUMN IF NOT EXISTS v_enabled INTEGER NOT NULL DEFAULT 0",
        "ALTER TABLE monthly_data ALTER COLUMN v_enabled SET DEFAULT 0",
        "ALTER TABLE driver_group_month_data ALTER COLUMN v_enabled SET DEFAULT 0",
    ]
    for sql in migrations:
        conn.execute(sql)
    conn.execute("UPDATE drivers SET display_order=id WHERE COALESCE(display_order,0)=0")
    # Do not run backfill_visible_passwords() here. This schema function is called
    # for every PostgreSQL connection/request, while every password guess uses the
    # deliberately expensive scrypt algorithm. Running the backfill here can
    # exceed Gunicorn's request timeout and break otherwise valid logins.

    migrated = conn.execute("SELECT COUNT(*) AS c FROM audit_log WHERE action=?", ("v_storage_direct_migration_2026_05_01",)).fetchone()
    if not migrated or int(migrated["c"] or 0) == 0:
        conn.execute("UPDATE monthly_data SET v_hours=COALESCE(v_hours,0)*14.0 WHERE ABS(COALESCE(v_hours,0))>0.0001")
        conn.execute(
            "INSERT INTO audit_log(actor, action, details, created_at) VALUES(?,?,?,?)",
            ("system", "v_storage_direct_migration_2026_05_01", "V-Werte von alter /14-Speicherung auf direkte Speicherung umgestellt.", now_iso()),
        )
    note_migrated = conn.execute("SELECT COUNT(*) AS c FROM audit_log WHERE action=?", ("v_note_only_migration_2026_09_01",)).fetchone()
    if not note_migrated or int(note_migrated["c"] or 0) == 0:
        conn.execute("UPDATE monthly_data SET v_note=CAST(v_hours AS TEXT) WHERE TRIM(COALESCE(v_note,''))='' AND ABS(COALESCE(v_hours,0))>0.0001")
        conn.execute("UPDATE monthly_data SET v_hours=0, v_enabled=0")
        conn.execute("UPDATE driver_group_month_data SET v_enabled=0")
        conn.execute(
            "INSERT INTO audit_log(actor, action, details, created_at) VALUES(?,?,?,?)",
            ("system", "v_note_only_migration_2026_09_01", "V in reines Notizfeld umgestellt und aus allen Berechnungen entfernt.", now_iso()),
        )
    conn.commit()


def db_conn():
    ensure_paths()
    database_url = os.environ.get("DATABASE_URL", "").strip()

    if database_url:
        import psycopg2
        from psycopg2.extras import RealDictCursor

        raw = psycopg2.connect(database_url, cursor_factory=RealDictCursor)
        raw.autocommit = False
        conn = _PostgresCompatConnection(raw)
        _init_postgres_schema(conn)
        return conn

    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    conn.executescript("""
    CREATE TABLE IF NOT EXISTS drivers(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        external_driver_id INTEGER UNIQUE,
        name TEXT NOT NULL,
        employment_type TEXT NOT NULL DEFAULT '',
        username TEXT NOT NULL UNIQUE,
        password_hash TEXT NOT NULL,
        password_plain TEXT NOT NULL DEFAULT '',
        starting_balance REAL NOT NULL DEFAULT 0,
        display_order INTEGER NOT NULL DEFAULT 0,
        is_active INTEGER NOT NULL DEFAULT 1,
        is_disposition INTEGER NOT NULL DEFAULT 0,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL
    );
    CREATE TABLE IF NOT EXISTS monthly_data(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        driver_id INTEGER NOT NULL,
        year INTEGER NOT NULL,
        month INTEGER NOT NULL,
        worked_hours REAL NOT NULL DEFAULT 0,
        payroll_hours REAL NOT NULL DEFAULT 0,
        v_hours REAL NOT NULL DEFAULT 0,
        v_note TEXT NOT NULL DEFAULT '',
        v_enabled INTEGER NOT NULL DEFAULT 0,
        bonus_hours REAL NOT NULL DEFAULT 0,
        bonus_comment TEXT NOT NULL DEFAULT '',
        deduction_hours REAL NOT NULL DEFAULT 0,
        deduction_comment TEXT NOT NULL DEFAULT '',
        adjustment_hours REAL NOT NULL DEFAULT 0,
        comment TEXT NOT NULL DEFAULT '',
        admin_info TEXT NOT NULL DEFAULT '',
        admin_info_carried INTEGER NOT NULL DEFAULT 0,
        payroll_office_info TEXT NOT NULL DEFAULT '',
        payroll_surcharge REAL NOT NULL DEFAULT 0,
        fuel_voucher REAL NOT NULL DEFAULT 0,
        payroll_carry_initialized INTEGER NOT NULL DEFAULT 0,
        vacation_days TEXT NOT NULL DEFAULT '',
        sick_days TEXT NOT NULL DEFAULT '',
        difference_hours REAL NOT NULL DEFAULT 0,
        previous_balance REAL NOT NULL DEFAULT 0,
        new_balance REAL NOT NULL DEFAULT 0,
        updated_at TEXT NOT NULL,
        FOREIGN KEY(driver_id) REFERENCES drivers(id) ON DELETE CASCADE,
        UNIQUE(driver_id, year, month)
    );
    CREATE TABLE IF NOT EXISTS documents(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        driver_id INTEGER NOT NULL,
        year INTEGER NOT NULL,
        month INTEGER NOT NULL,
        filename TEXT NOT NULL,
        original_filename TEXT NOT NULL,
        relative_path TEXT NOT NULL UNIQUE,
        uploaded_at TEXT NOT NULL,
        FOREIGN KEY(driver_id) REFERENCES drivers(id) ON DELETE CASCADE,
        UNIQUE(driver_id, year, month)
    );
    CREATE TABLE IF NOT EXISTS audit_log(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        actor TEXT NOT NULL,
        action TEXT NOT NULL,
        details TEXT NOT NULL DEFAULT '',
        created_at TEXT NOT NULL
    );
    CREATE TABLE IF NOT EXISTS app_settings(
        setting_key TEXT PRIMARY KEY,
        setting_value TEXT NOT NULL DEFAULT '',
        updated_at TEXT NOT NULL
    );
    CREATE TABLE IF NOT EXISTS adjustment_items(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        monthly_data_id INTEGER NOT NULL,
        kind TEXT NOT NULL,
        hours REAL NOT NULL DEFAULT 0,
        note TEXT NOT NULL DEFAULT '',
        created_at TEXT NOT NULL,
        FOREIGN KEY(monthly_data_id) REFERENCES monthly_data(id) ON DELETE CASCADE
    );
    CREATE TABLE IF NOT EXISTS adjustment_files(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        adjustment_item_id INTEGER NOT NULL,
        filename TEXT NOT NULL,
        original_filename TEXT NOT NULL DEFAULT '',
        relative_path TEXT NOT NULL UNIQUE,
        mime_type TEXT NOT NULL DEFAULT '',
        uploaded_at TEXT NOT NULL,
        FOREIGN KEY(adjustment_item_id) REFERENCES adjustment_items(id) ON DELETE CASCADE
    );
    CREATE TABLE IF NOT EXISTS driver_groups(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL DEFAULT '',
        is_active INTEGER NOT NULL DEFAULT 1,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL
    );
    CREATE TABLE IF NOT EXISTS driver_group_members(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        group_id INTEGER NOT NULL,
        driver_id INTEGER NOT NULL UNIQUE,
        position INTEGER NOT NULL DEFAULT 0,
        FOREIGN KEY(group_id) REFERENCES driver_groups(id) ON DELETE CASCADE,
        FOREIGN KEY(driver_id) REFERENCES drivers(id) ON DELETE CASCADE,
        UNIQUE(group_id, driver_id)
    );
    CREATE TABLE IF NOT EXISTS driver_group_month_data(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        group_id INTEGER NOT NULL,
        year INTEGER NOT NULL,
        month INTEGER NOT NULL,
        worked_hours REAL NOT NULL DEFAULT 0,
        v_enabled INTEGER NOT NULL DEFAULT 0,
        admin_info TEXT NOT NULL DEFAULT '',
        updated_at TEXT NOT NULL,
        FOREIGN KEY(group_id) REFERENCES driver_groups(id) ON DELETE CASCADE,
        UNIQUE(group_id, year, month)
    );
    CREATE TABLE IF NOT EXISTS driver_group_adjustment_items(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        group_month_data_id INTEGER NOT NULL,
        kind TEXT NOT NULL,
        hours REAL NOT NULL DEFAULT 0,
        note TEXT NOT NULL DEFAULT '',
        created_at TEXT NOT NULL,
        FOREIGN KEY(group_month_data_id) REFERENCES driver_group_month_data(id) ON DELETE CASCADE
    );
    CREATE TABLE IF NOT EXISTS driver_group_adjustment_files(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        group_adjustment_item_id INTEGER NOT NULL,
        filename TEXT NOT NULL,
        original_filename TEXT NOT NULL DEFAULT '',
        relative_path TEXT NOT NULL UNIQUE,
        mime_type TEXT NOT NULL DEFAULT '',
        uploaded_at TEXT NOT NULL,
        FOREIGN KEY(group_adjustment_item_id) REFERENCES driver_group_adjustment_items(id) ON DELETE CASCADE
    );
    CREATE TABLE IF NOT EXISTS month_releases(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        year INTEGER NOT NULL,
        month INTEGER NOT NULL,
        is_released INTEGER NOT NULL DEFAULT 0,
        updated_at TEXT NOT NULL,
        UNIQUE(year, month)
    );
    """)

    cols = {r[1] for r in conn.execute("PRAGMA table_info(drivers)").fetchall()}
    if "starting_balance" not in cols:
        conn.execute("ALTER TABLE drivers ADD COLUMN starting_balance REAL NOT NULL DEFAULT 0")
    if "display_order" not in cols:
        conn.execute("ALTER TABLE drivers ADD COLUMN display_order INTEGER NOT NULL DEFAULT 0")
    if "is_disposition" not in cols:
        conn.execute("ALTER TABLE drivers ADD COLUMN is_disposition INTEGER NOT NULL DEFAULT 0")
    if "password_plain" not in cols:
        conn.execute("ALTER TABLE drivers ADD COLUMN password_plain TEXT NOT NULL DEFAULT ''")
    if "employment_type" not in cols:
        conn.execute("ALTER TABLE drivers ADD COLUMN employment_type TEXT NOT NULL DEFAULT ''")
    conn.execute("UPDATE drivers SET display_order=id WHERE COALESCE(display_order,0)=0")

    try:
        gcols = {r[1] for r in conn.execute("PRAGMA table_info(driver_group_month_data)").fetchall()}
        if "admin_info" not in gcols:
            conn.execute("ALTER TABLE driver_group_month_data ADD COLUMN admin_info TEXT NOT NULL DEFAULT ''")
        if "v_enabled" not in gcols:
            conn.execute("ALTER TABLE driver_group_month_data ADD COLUMN v_enabled INTEGER NOT NULL DEFAULT 0")
    except Exception:
        pass

    cols = {r[1] for r in conn.execute("PRAGMA table_info(monthly_data)").fetchall()}
    for name, ddl in {
        "v_note":"ALTER TABLE monthly_data ADD COLUMN v_note TEXT NOT NULL DEFAULT ''",
        "v_enabled":"ALTER TABLE monthly_data ADD COLUMN v_enabled INTEGER NOT NULL DEFAULT 0",
        "payroll_carry_initialized":"ALTER TABLE monthly_data ADD COLUMN payroll_carry_initialized INTEGER NOT NULL DEFAULT 0",
        "bonus_hours":"ALTER TABLE monthly_data ADD COLUMN bonus_hours REAL NOT NULL DEFAULT 0",
        "bonus_comment":"ALTER TABLE monthly_data ADD COLUMN bonus_comment TEXT NOT NULL DEFAULT ''",
        "deduction_hours":"ALTER TABLE monthly_data ADD COLUMN deduction_hours REAL NOT NULL DEFAULT 0",
        "deduction_comment":"ALTER TABLE monthly_data ADD COLUMN deduction_comment TEXT NOT NULL DEFAULT ''",
        "admin_info":"ALTER TABLE monthly_data ADD COLUMN admin_info TEXT NOT NULL DEFAULT ''",
        "admin_info_carried":"ALTER TABLE monthly_data ADD COLUMN admin_info_carried INTEGER NOT NULL DEFAULT 0",
        "payroll_office_info":"ALTER TABLE monthly_data ADD COLUMN payroll_office_info TEXT NOT NULL DEFAULT ''",
        "payroll_surcharge":"ALTER TABLE monthly_data ADD COLUMN payroll_surcharge REAL NOT NULL DEFAULT 0",
        "fuel_voucher":"ALTER TABLE monthly_data ADD COLUMN fuel_voucher REAL NOT NULL DEFAULT 0",
        "vacation_days":"ALTER TABLE monthly_data ADD COLUMN vacation_days TEXT NOT NULL DEFAULT ''",
        "sick_days":"ALTER TABLE monthly_data ADD COLUMN sick_days TEXT NOT NULL DEFAULT ''",
    }.items():
        if name not in cols:
            conn.execute(ddl)


    migrated = conn.execute("SELECT COUNT(*) AS c FROM audit_log WHERE action=?", ("v_storage_direct_migration_2026_05_01",)).fetchone()
    if not migrated or int(migrated["c"] or 0) == 0:
        conn.execute("UPDATE monthly_data SET v_hours=COALESCE(v_hours,0)*14.0 WHERE ABS(COALESCE(v_hours,0))>0.0001")
        conn.execute(
            "INSERT INTO audit_log(actor, action, details, created_at) VALUES(?,?,?,?)",
            ("system", "v_storage_direct_migration_2026_05_01", "V-Werte von alter /14-Speicherung auf direkte Speicherung umgestellt.", now_iso()),
        )
    note_migrated = conn.execute("SELECT COUNT(*) AS c FROM audit_log WHERE action=?", ("v_note_only_migration_2026_09_01",)).fetchone()
    if not note_migrated or int(note_migrated["c"] or 0) == 0:
        conn.execute("UPDATE monthly_data SET v_note=CAST(v_hours AS TEXT) WHERE TRIM(COALESCE(v_note,''))='' AND ABS(COALESCE(v_hours,0))>0.0001")
        conn.execute("UPDATE monthly_data SET v_hours=0, v_enabled=0")
        conn.execute("UPDATE driver_group_month_data SET v_enabled=0")
        conn.execute(
            "INSERT INTO audit_log(actor, action, details, created_at) VALUES(?,?,?,?)",
            ("system", "v_note_only_migration_2026_09_01", "V in reines Notizfeld umgestellt und aus allen Berechnungen entfernt.", now_iso()),
        )
    conn.commit()
    return conn


def audit(conn: sqlite3.Connection, action: str, details: str = "", actor: str = "admin") -> None:
    conn.execute("INSERT INTO audit_log(actor, action, details, created_at) VALUES(?,?,?,?)", (actor, action, details, now_iso()))


def get_driver_by_db_id(conn: sqlite3.Connection, driver_id: int) -> Optional[sqlite3.Row]:
    return conn.execute("SELECT * FROM drivers WHERE id=?", (driver_id,)).fetchone()


def next_external_id(conn: sqlite3.Connection) -> int:
    row = conn.execute("SELECT MAX(external_driver_id) AS m FROM drivers WHERE COALESCE(is_disposition,0)=0").fetchone()
    return int(row["m"] or 0) + 1


def previous_month(year: int, month: int) -> Tuple[int, int]:
    if month <= 1:
        return year - 1, 12
    return year, month - 1


def maybe_carry_admin_info(conn: sqlite3.Connection, monthly_data_id: int, driver_id: int, year: int, month: int) -> None:
    """Copy admin-only info exactly one month forward.

    If January has manually saved info, February gets it automatically.
    The copied February value is marked as carried, so it will not automatically continue into March.
    If the admin edits/saves February, it becomes manual again and can carry into March.
    """
    current = conn.execute(
        "SELECT admin_info, COALESCE(admin_info_carried,0) AS admin_info_carried FROM monthly_data WHERE id=?",
        (monthly_data_id,),
    ).fetchone()
    if not current or (current["admin_info"] or "").strip():
        return

    py, pm = previous_month(year, month)
    prev = conn.execute(
        """
        SELECT admin_info, COALESCE(admin_info_carried,0) AS admin_info_carried
        FROM monthly_data
        WHERE driver_id=? AND year=? AND month=?
        """,
        (driver_id, py, pm),
    ).fetchone()

    if prev and (prev["admin_info"] or "").strip() and int(prev["admin_info_carried"] or 0) == 0:
        conn.execute(
            "UPDATE monthly_data SET admin_info=?, admin_info_carried=1, updated_at=? WHERE id=?",
            (prev["admin_info"], now_iso(), monthly_data_id),
        )


def maybe_carry_payroll_values(conn: sqlite3.Connection, monthly_data_id: int, driver_id: int, year: int, month: int) -> None:
    """When the real calendar advances, carry surcharge and fuel voucher one month forward once."""
    if (int(year), int(month)) != current_edit_year_month():
        return
    current = conn.execute(
        "SELECT payroll_surcharge, fuel_voucher, COALESCE(payroll_carry_initialized,0) AS payroll_carry_initialized FROM monthly_data WHERE id=?",
        (monthly_data_id,),
    ).fetchone()
    if not current or int(row_get(current, "payroll_carry_initialized", 0) or 0) == 1:
        return
    current_surcharge = safe_float(row_get(current, "payroll_surcharge", 0))
    current_voucher = safe_float(row_get(current, "fuel_voucher", 0))
    py, pm = previous_month(year, month)
    prev = conn.execute(
        "SELECT payroll_surcharge, fuel_voucher FROM monthly_data WHERE driver_id=? AND year=? AND month=?",
        (driver_id, py, pm),
    ).fetchone()
    previous_surcharge = safe_float(row_get(prev, "payroll_surcharge", 0)) if prev else 0.0
    previous_voucher = safe_float(row_get(prev, "fuel_voucher", 0)) if prev else 0.0
    # Preserve values already entered in the new month; only empty/zero fields are carried.
    surcharge = current_surcharge if abs(current_surcharge) > 0.0001 else previous_surcharge
    voucher = current_voucher if abs(current_voucher) > 0.0001 else previous_voucher
    conn.execute(
        "UPDATE monthly_data SET payroll_surcharge=?, fuel_voucher=?, payroll_carry_initialized=1, updated_at=? WHERE id=?",
        (surcharge, voucher, now_iso(), monthly_data_id),
    )

def get_or_create_month_row(conn: sqlite3.Connection, driver_id: int, year: int, month: int, carry_admin_info: bool = True) -> int:
    row = conn.execute(
        "SELECT id FROM monthly_data WHERE driver_id=? AND year=? AND month=?",
        (driver_id, year, month),
    ).fetchone()
    if row:
        monthly_id = int(row["id"])
    else:
        cur = conn.execute(
            "INSERT INTO monthly_data(driver_id, year, month, v_enabled, payroll_carry_initialized, updated_at) VALUES(?,?,?,?,?,?)",
            (driver_id, year, month, 0, 0, now_iso()),
        )
        monthly_id = int(cur.lastrowid)

    if carry_admin_info:
        maybe_carry_admin_info(conn, monthly_id, driver_id, year, month)
    maybe_carry_payroll_values(conn, monthly_id, driver_id, year, month)
    return monthly_id


def is_month_released(conn: sqlite3.Connection, year: int, month: int) -> bool:
    """Return True only when the selected month is visible in the driver portal."""
    row = conn.execute(
        "SELECT is_released FROM month_releases WHERE year=? AND month=?",
        (year, month),
    ).fetchone()
    return bool(row and int(row["is_released"] or 0) == 1)


def set_month_release(conn: sqlite3.Connection, year: int, month: int, is_released: bool) -> None:
    """Block or allow the selected month for all drivers in the driver portal."""
    released = 1 if is_released else 0
    existing = conn.execute(
        "SELECT id FROM month_releases WHERE year=? AND month=?",
        (year, month),
    ).fetchone()
    if existing:
        conn.execute(
            "UPDATE month_releases SET is_released=?, updated_at=? WHERE id=?",
            (released, now_iso(), existing["id"]),
        )
    else:
        conn.execute(
            "INSERT INTO month_releases(year, month, is_released, updated_at) VALUES(?,?,?,?)",
            (year, month, released, now_iso()),
        )

def recalc_month_adjustments(conn: sqlite3.Connection, monthly_data_id: int) -> None:
    items = conn.execute(
        "SELECT kind, hours, note FROM adjustment_items WHERE monthly_data_id=? ORDER BY id",
        (monthly_data_id,),
    ).fetchall()

    bonus = round(sum(abs(float(i["hours"] or 0)) for i in items if i["kind"] == "bonus"), 2)
    deduction = round(-sum(abs(float(i["hours"] or 0)) for i in items if i["kind"] == "deduction"), 2)

    bonus_comment = "\n".join(
        f'{fmt_hours(abs(float(i["hours"] or 0)))} - {i["note"]}'
        for i in items if i["kind"] == "bonus"
    )
    deduction_comment = "\n".join(
        f'{fmt_hours(-abs(float(i["hours"] or 0)))} - {i["note"]}'
        for i in items if i["kind"] == "deduction"
    )

    conn.execute(
        """
        UPDATE monthly_data
        SET bonus_hours=?, bonus_comment=?, deduction_hours=?, deduction_comment=?,
            adjustment_hours=?, comment=?, updated_at=?
        WHERE id=?
        """,
        (
            bonus,
            bonus_comment,
            deduction,
            deduction_comment,
            round(bonus + deduction, 2),
            (bonus_comment + "\n" + deduction_comment).strip(),
            now_iso(),
            monthly_data_id,
        ),
    )


def recalc_driver(conn: sqlite3.Connection, driver_id: int) -> None:
    driver = get_driver_by_db_id(conn, driver_id)
    if not driver:
        return
    balance = float(driver["starting_balance"] or 0)
    rows = conn.execute("SELECT * FROM monthly_data WHERE driver_id=? ORDER BY year, month, id", (driver_id,)).fetchall()
    for r in rows:
        diff = compute_difference(r["worked_hours"], r["payroll_hours"], 0, r["bonus_hours"], r["deduction_hours"], 0)
        new_balance = round(balance + diff, 2)
        conn.execute("UPDATE monthly_data SET difference_hours=?, previous_balance=?, new_balance=? WHERE id=?", (diff, round(balance,2), new_balance, r["id"]))
        balance = new_balance


def recalc_all(conn: sqlite3.Connection) -> None:
    for d in conn.execute("SELECT id FROM drivers WHERE COALESCE(is_disposition,0)=0 ORDER BY id").fetchall():
        recalc_driver(conn, int(d["id"]))

ALLOWED_ATTACHMENT_EXTENSIONS = {"png", "jpg", "jpeg", "webp", "gif", "pdf"}
IMAGE_ATTACHMENT_EXTENSIONS = {"png", "jpg", "jpeg"}


def allowed_attachment(filename: str) -> bool:
    return "." in (filename or "") and filename.rsplit(".", 1)[1].lower() in ALLOWED_ATTACHMENT_EXTENSIONS


def attachment_relative_path(driver_id: int, year: int, month: int, adjustment_id: int, filename: str) -> Path:
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    safe = secure_filename(filename) or "anhang"
    return Path("attachments") / str(driver_id) / str(year) / f"{month:02d}" / str(adjustment_id) / f"{stamp}_{safe}"


def delete_attachment_file(relative_path: str) -> None:
    try:
        path = DATA_ROOT / relative_path
        if path.exists() and path.is_file():
            path.unlink()
    except Exception:
        pass


def delete_relative_file(relative_path: str) -> None:
    try:
        path = DATA_ROOT / relative_path
        if path.exists() and path.is_file():
            path.unlink()
    except Exception:
        pass


def delete_driver_files(conn: sqlite3.Connection, driver_id: int) -> None:
    for r in conn.execute("SELECT relative_path FROM documents WHERE driver_id=?", (driver_id,)).fetchall():
        delete_relative_file(r["relative_path"])
    for r in conn.execute("""
        SELECT af.relative_path
        FROM adjustment_files af
        JOIN adjustment_items ai ON ai.id=af.adjustment_item_id
        JOIN monthly_data m ON m.id=ai.monthly_data_id
        WHERE m.driver_id=?
    """, (driver_id,)).fetchall():
        delete_relative_file(r["relative_path"])


def delete_month_files(conn: sqlite3.Connection, monthly_id: int) -> None:
    month_row = conn.execute("SELECT driver_id, year, month FROM monthly_data WHERE id=?", (monthly_id,)).fetchone()
    if not month_row:
        return
    did, year, month = int(month_row["driver_id"]), int(month_row["year"]), int(month_row["month"])
    for r in conn.execute("SELECT relative_path FROM documents WHERE driver_id=? AND year=? AND month=?", (did, year, month)).fetchall():
        delete_relative_file(r["relative_path"])
    for r in conn.execute("""
        SELECT af.relative_path
        FROM adjustment_files af
        JOIN adjustment_items ai ON ai.id=af.adjustment_item_id
        WHERE ai.monthly_data_id=?
    """, (monthly_id,)).fetchall():
        delete_relative_file(r["relative_path"])


def cleanup_empty_dirs(root: Path) -> None:
    try:
        if not root.exists():
            return
        for current, dirs, files in os.walk(root, topdown=False):
            path = Path(current)
            try:
                if path != root and not any(path.iterdir()):
                    path.rmdir()
            except Exception:
                pass
    except Exception:
        pass


def month_has_real_data(row: sqlite3.Row, adjustment_count: int = 0, document_count: int = 0, file_count: int = 0) -> bool:
    """Return True only when a monthly row contains real data.

    This helper is intentionally tolerant because some cleanup queries load only
    a reduced set of columns. Missing columns are treated as empty/zero instead
    of crashing the cleanup page.
    """
    keys = set(row.keys()) if hasattr(row, "keys") else set()

    def get_value(key: str, default: Any = 0) -> Any:
        if key not in keys:
            return default
        try:
            return row[key]
        except (IndexError, KeyError):
            return default

    numeric = ["worked_hours", "payroll_hours", "bonus_hours", "deduction_hours", "adjustment_hours", "difference_hours"]
    for key in numeric:
        try:
            if abs(float(get_value(key, 0) or 0)) > 0.0001:
                return True
        except (TypeError, ValueError):
            pass

    text = ["v_note", "bonus_comment", "deduction_comment", "comment", "admin_info"]
    for key in text:
        if str(get_value(key, "") or "").strip():
            return True

    return adjustment_count > 0 or document_count > 0 or file_count > 0

# ---------------- PDF ----------------
def _pdf_table(data: List[List[str]], widths: List[float]) -> Table:
    styles = getSampleStyleSheet()
    cell = ParagraphStyle("Cell", parent=styles["BodyText"], fontName="Helvetica", fontSize=7.7, leading=9, textColor=colors.HexColor("#111827"), wordWrap="CJK")
    header = ParagraphStyle("HeaderCell", parent=styles["BodyText"], fontName="Helvetica-Bold", fontSize=7.7, leading=9, alignment=1, textColor=colors.black, wordWrap="CJK")
    wrapped = [[Paragraph(str(c).replace("\n", "<br/>"), header if r == 0 else cell) for c in row] for r,row in enumerate(data)]
    table = Table(wrapped, colWidths=widths, repeatRows=1, splitByRow=1)
    table.setStyle(TableStyle([
        ("BACKGROUND",(0,0),(-1,0),colors.HexColor("#dfddd8")), ("FONTNAME",(0,0),(-1,0),"Helvetica-Bold"),
        ("ROWBACKGROUNDS",(0,1),(-1,-1),[colors.white, colors.HexColor("#f9fafb")]),
        ("BOX",(0,0),(-1,-1),0.8,colors.HexColor("#8f8b84")), ("INNERGRID",(0,0),(-1,-1),0.5,colors.HexColor("#b8b4ad")),
        ("VALIGN",(0,0),(-1,-1),"MIDDLE"), ("ALIGN",(1,0),(-1,-1),"CENTER"),
        ("LEFTPADDING",(0,0),(-1,-1),5), ("RIGHTPADDING",(0,0),(-1,-1),5), ("TOPPADDING",(0,0),(-1,-1),7), ("BOTTOMPADDING",(0,0),(-1,-1),7),
    ]))
    return table


def create_pdf_report(pdf_path: Path, title: str, subtitle: str, headers: List[str], rows: List[List[str]], wide: bool = True, extra_story: Optional[List[Any]] = None) -> None:
    pdf_path.parent.mkdir(parents=True, exist_ok=True)
    if pdf_path.exists():
        pdf_path.unlink()
    pagesize = landscape(A4) if wide else A4
    page_width = pagesize[0]
    margin = 8 * mm
    usable_width = page_width - margin * 2
    doc = SimpleDocTemplate(str(pdf_path), pagesize=pagesize, leftMargin=margin, rightMargin=margin, topMargin=10*mm, bottomMargin=10*mm, title=title, author=APP_NAME)
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle("TitleCustom", parent=styles["Title"], fontName="Helvetica-Bold", fontSize=17, leading=20, textColor=colors.HexColor("#123e7c"), spaceAfter=3)
    subtitle_style = ParagraphStyle("SubtitleCustom", parent=styles["BodyText"], fontName="Helvetica", fontSize=9.5, leading=12, textColor=colors.HexColor("#374151"), spaceAfter=6)
    if len(headers) == 9:
        col_widths = [0.13,0.12,0.11,0.07,0.14,0.14,0.09,0.09,0.11]
    elif len(headers) == 10:
        col_widths = [0.09,0.13,0.10,0.10,0.07,0.13,0.13,0.08,0.08,0.09]
    elif len(headers) == 11:
        col_widths = [0.08,0.10,0.12,0.09,0.09,0.06,0.12,0.12,0.07,0.07,0.08]
    else:
        col_widths = [1/max(len(headers),1)] * len(headers)
    story = [Paragraph(title,title_style), Paragraph(subtitle,subtitle_style), Spacer(1,4*mm), _pdf_table([headers]+rows, [w*usable_width for w in col_widths])]
    if extra_story:
        story.extend(extra_story)
    doc.build(story)


def format_value_comment(value: float, comment: str, hours: bool = False) -> str:
    first = fmt_hours(value) if hours else fmt_signed(value)
    comment = (comment or "").strip()
    return first if not comment else f"{first}\n{comment}"


def color_text(value: str, color_hex: str) -> str:
    text = str(value or "-").strip() or "-"
    return f'<font color="{color_hex}">{text}</font>'


def create_driver_pdf(conn: sqlite3.Connection, driver_id: int, year: int, month: int) -> Optional[int]:
    """Creates the current driver PDF. Admin-only internal fields are intentionally not included."""
    driver = get_driver_by_db_id(conn, driver_id)
    row = conn.execute("SELECT * FROM monthly_data WHERE driver_id=? AND year=? AND month=?", (driver_id, year, month)).fetchone()
    if not driver or not row:
        return None
    driver_slug = slugify(driver["name"]) + f"-{driver['id']}"
    safe_name = secure_filename(f"{month:02d}_{MONATE.get(month, str(month))}_{year}.pdf")
    relative_path = Path("pdfs") / driver_slug / str(year) / safe_name
    pdf_path = DATA_ROOT / relative_path
    styles = getSampleStyleSheet()
    attachment_title = ParagraphStyle("AttachmentTitle", parent=styles["Heading2"], fontName="Helvetica-Bold", fontSize=12, leading=14, textColor=colors.HexColor("#123e7c"), spaceBefore=10, spaceAfter=6)
    attachment_text = ParagraphStyle("AttachmentText", parent=styles["BodyText"], fontName="Helvetica", fontSize=9, leading=11, textColor=colors.HexColor("#111827"))
    attachments = conn.execute("""
        SELECT af.*, ai.kind, ai.hours, ai.note
        FROM adjustment_files af
        JOIN adjustment_items ai ON ai.id=af.adjustment_item_id
        JOIN monthly_data m ON m.id=ai.monthly_data_id
        WHERE m.driver_id=? AND m.year=? AND m.month=? AND ai.kind='deduction'
        ORDER BY ai.id, af.id
    """, (driver_id, year, month)).fetchall()
    extra_story: List[Any] = []
    if attachments:
        extra_story.extend([Spacer(1, 6*mm), Paragraph("Anhänge zu Abzügen", attachment_title)])
        for att in attachments:
            path = DATA_ROOT / att["relative_path"]
            label = f"Abzug {fmt_hours(-abs(float(att['hours'] or 0)))} – {att['note']}"
            extra_story.append(Paragraph(label, attachment_text))
            if path.exists() and path.suffix.lower().lstrip(".") in IMAGE_ATTACHMENT_EXTENSIONS:
                try:
                    extra_story.append(Image(str(path), width=120*mm, height=80*mm, kind="proportional"))
                    extra_story.append(Spacer(1, 4*mm))
                except Exception:
                    extra_story.append(Paragraph(f"Datei: {att['original_filename'] or att['filename']}", attachment_text))
            else:
                extra_story.append(Paragraph(f"Datei: {att['original_filename'] or att['filename']}", attachment_text))
                extra_story.append(Spacer(1, 3*mm))

    create_pdf_report(pdf_path, f"Monatsübersicht {driver['name']} – {MONATE[month]} {year}", "+ - Stunden", ["Fahrer","Stunden","Abrechnung","V","Zuschüsse","Abzüge","Differenz","Aktueller\nStand","Neuer\nStand"], [[
        driver["name"], fmt_hours(row["worked_hours"]), fmt_hours(row["payroll_hours"]), fmt_v_display(row_get(row, "v_note", ""), row_get(row, "v_enabled", 0), True),
        (row["bonus_comment"] or "-").strip() or "-", (row["deduction_comment"] or "-").strip() or "-",
        fmt_signed(row["difference_hours"]), fmt_signed(row["previous_balance"]), fmt_signed(row["new_balance"])
    ]], extra_story=extra_story)
    ts = now_iso()
    existing = conn.execute("SELECT id FROM documents WHERE driver_id=? AND year=? AND month=?", (driver_id, year, month)).fetchone()
    if existing:
        conn.execute("UPDATE documents SET filename=?, original_filename=?, relative_path=?, uploaded_at=? WHERE id=?", (safe_name, safe_name, str(relative_path), ts, existing["id"]))
        return int(existing["id"])
    cur = conn.execute("INSERT INTO documents(driver_id,year,month,filename,original_filename,relative_path,uploaded_at) VALUES(?,?,?,?,?,?,?)", (driver_id,year,month,safe_name,safe_name,str(relative_path),ts))
    return int(cur.lastrowid)


def ensure_active_driver_month_rows(conn: sqlite3.Connection, year: int, month: int) -> None:
    """Ensure every active driver has a row for the requested month before exports."""
    active_drivers = conn.execute(
        "SELECT id FROM drivers WHERE is_active=1 AND COALESCE(is_disposition,0)=0 ORDER BY COALESCE(NULLIF(display_order,0), id), name COLLATE NOCASE"
    ).fetchall()
    for d in active_drivers:
        get_or_create_month_row(conn, int(d["id"]), year, month, carry_admin_info=True)


def set_global_v_enabled(conn: sqlite3.Connection, year: int, month: int, enabled: bool) -> None:
    value = 1 if enabled else 0
    active_drivers = conn.execute("SELECT id FROM drivers WHERE is_active=1 AND COALESCE(is_disposition,0)=0").fetchall()
    for d in active_drivers:
        mid = get_or_create_month_row(conn, int(d["id"]), year, month, carry_admin_info=True)
        conn.execute("UPDATE monthly_data SET v_enabled=?, updated_at=? WHERE id=?", (value, now_iso(), mid))
    for g in load_driver_groups(conn):
        gm_id = ensure_group_month_row(conn, int(g["group"]["id"]), year, month)
        conn.execute("UPDATE driver_group_month_data SET v_enabled=?, updated_at=? WHERE id=?", (value, now_iso(), gm_id))

def month_all_drivers_v_enabled(conn: sqlite3.Connection, year: int, month: int) -> bool:
    rows = conn.execute(
        "SELECT COALESCE(m.v_enabled,0) AS v_enabled FROM drivers d LEFT JOIN monthly_data m ON m.driver_id=d.id AND m.year=? AND m.month=? WHERE d.is_active=1 AND COALESCE(d.is_disposition,0)=0",
        (year, month),
    ).fetchall()
    return bool(rows) and all(v_is_enabled(row_get(r, "v_enabled", 0)) for r in rows)

def export_month_pdf(conn: sqlite3.Connection, year: int, month: int) -> Path:
    groups = load_driver_groups(conn)
    grouped_driver_ids = {did for g in groups for did in g["member_ids"]}
    normal_rows = conn.execute("""
        SELECT m.*, d.name, d.id AS d_id
        FROM monthly_data m
        JOIN drivers d ON d.id=m.driver_id
        WHERE m.year=? AND m.month=? AND COALESCE(d.is_disposition,0)=0
        ORDER BY COALESCE(NULLIF(d.display_order,0), d.id), d.name COLLATE NOCASE
    """, (year, month)).fetchall()

    pdf_rows = []
    for r in normal_rows:
        if int(r["driver_id"]) in grouped_driver_ids:
            continue
        pdf_rows.append([
            f"{MONATE[month]} {year}", r["admin_info"] or "-", r["name"],
            fmt_hours(r["worked_hours"]), fmt_hours(r["payroll_hours"]), fmt_v_display(row_get(r, "v_note", ""), row_get(r, "v_enabled", 0), True),
            format_value_comment(r["bonus_hours"], r["bonus_comment"], True),
            format_value_comment(r["deduction_hours"], r["deduction_comment"], True),
            fmt_signed(r["difference_hours"]), fmt_signed(r["previous_balance"]), fmt_signed(r["new_balance"]),
        ])
    for g in groups:
        r = make_group_month_summary(conn, g, year, month)
        pdf_rows.append([
            f"{MONATE[month]} {year}", r.get("admin_info") or "-", g["name"],
            fmt_hours(r.get("worked_hours", 0)), fmt_hours(r.get("payroll_hours", 0)), fmt_v_display(r.get("v_note", ""), r.get("v_enabled", 0), True),
            format_value_comment(r.get("bonus_hours", 0), r.get("bonus_comment", ""), True),
            format_value_comment(r.get("deduction_hours", 0), r.get("deduction_comment", ""), True),
            fmt_signed(r.get("difference_hours", 0)), fmt_signed(r.get("previous_balance", 0)), fmt_signed(r.get("new_balance", 0)),
        ])
    if not pdf_rows:
        pdf_rows = [[f"{MONATE[month]} {year}", "-", "Keine Einträge", "-", "-", "-", "-", "-", "-", "-", "-"]]
    path = EXPORT_DIR / str(year) / f"{month:02d}_{MONATE[month]}_{year}.pdf"
    create_pdf_report(path, f"Monatsübersicht {MONATE[month]} {year}", "Admin-Übersicht inklusive interner Allgemeiner Infos", ["Monat","Allgemeine Infos","Fahrer","Stunden","Abrechnung","V","Zuschüsse","Abzüge","Differenz","Aktueller Stand","Neuer Stand"], pdf_rows)
    return path

def export_payroll_hours_pdf(conn: sqlite3.Connection, year: int, month: int) -> Path:
    rows = conn.execute("""
        SELECT
            d.name,
            COALESCE(m.payroll_office_info, '') AS payroll_office_info,
            COALESCE(m.payroll_hours, 0) AS payroll_hours,
            COALESCE(m.v_note, '') AS v_note,
            COALESCE(m.v_enabled, 0) AS v_enabled,
            COALESCE(m.payroll_surcharge, 0) AS payroll_surcharge,
            COALESCE(m.fuel_voucher, 0) AS fuel_voucher,
            COALESCE(m.vacation_days, '') AS vacation_days,
            COALESCE(m.sick_days, '') AS sick_days
        FROM drivers d
        LEFT JOIN monthly_data m
            ON m.driver_id=d.id AND m.year=? AND m.month=?
        WHERE d.is_active=1 AND COALESCE(d.is_disposition,0)=0
        ORDER BY COALESCE(NULLIF(d.display_order,0), d.id), d.name COLLATE NOCASE
    """, (year, month)).fetchall()
    pdf_rows = [[
        row_get(r, "payroll_office_info", "") or "-",
        r["name"],
        fmt_hours(r["payroll_hours"]),
        fmt_v_display(r["v_note"], row_get(r, "v_enabled", 0), False),
        fmt_decimal_input(row_get(r, "payroll_surcharge", 0)) or "-",
        fmt_decimal_input(row_get(r, "fuel_voucher", 0)) or "-",
        color_text((vacation_display(row_get(r, "vacation_days", "")) + " Tage") if vacation_display(row_get(r, "vacation_days", "")) else "-", "#067647"),
        color_text(row_get(r, "sick_days", "") or "-", "#b42318"),
    ] for r in rows]
    if not pdf_rows:
        pdf_rows = [["-", "Keine Einträge", "-", "-", "-", "-", "-", "-"]]
    path = EXPORT_DIR / str(year) / f"{month:02d}_{MONATE[month]}_{year}_lohnabrechnung.pdf"
    create_pdf_report(
        path,
        f"Stunden für Lohnabrechnung – {MONATE[month]} {year}",
        "",
        ["Allgemeine Infos für Lohnbüro", "Fahrer", "Abrechnung", "V", "Zuschlag", "Tankgutschein", "Urlaub", "Krank"],
        pdf_rows,
        wide=True,
    )
    return path

# ---------------- payroll PDF import ----------------
def extract_payroll_entries_from_pdf(pdf_path: Path) -> List[Dict[str, Any]]:
    if PdfReader is None:
        raise RuntimeError("Für den PDF-Import wird pypdf benötigt. Bitte in requirements.txt aufnehmen.")
    reader = PdfReader(str(pdf_path))
    entries: List[Dict[str, Any]] = []
    for page_no, page in enumerate(reader.pages, start=1):
        text = page.extract_text() or ""
        if "Verpflegungszuschuss" not in text:
            continue
        month_match = re.search(r"für\s+([A-Za-zÄÖÜäöüß]+)\s+(\d{4})", text)
        month_name = month_match.group(1) if month_match else ""
        year = int(month_match.group(2)) if month_match else None
        pers_match = re.search(r"Pers\.-Nr\.\s*0*(\d+)", text)
        personalnummer = pers_match.group(1) if pers_match else ""
        name_match = re.search(r"Hasan\s+Aysel\s+Taxiunternehmen.*?Kirn\s*([^\n]+?)\s*(?:\d{5}\s+[A-ZÄÖÜa-zäöüß-]+|B/N|\*Pers\.-Nr\.)", text, re.S)
        driver_name = re.sub(r"\s+", " ", name_match.group(1)).strip() if name_match else ""
        v_match = re.search(r"9650\s+Verpflegungszuschuss\s+([0-9\.]+,\d{2}-?)", text)
        v_amount = parse_german_money(v_match.group(1).replace("-", "")) if v_match else None
        if not driver_name or v_amount is None:
            continue
        month_num = next((i for i,n in MONATE.items() if normalize(n)==normalize(month_name)), None)
        entries.append({"page":page_no,"name":driver_name,"personalnummer":personalnummer,"month_name":month_name,"year":year,"month":month_num,"v_source_amount":round(v_amount,2),"v_note":fmt_decimal_input(v_amount)})
    return entries


def guess_driver_match(conn: sqlite3.Connection, source_name: str) -> Tuple[Optional[int], str]:
    drivers = conn.execute("SELECT id,name FROM drivers WHERE is_active=1 AND COALESCE(is_disposition,0)=0").fetchall()
    if not drivers:
        return None, "Kein Fahrer im System"
    source_norm = normalize(source_name)
    exact = [d for d in drivers if normalize(d["name"]) == source_norm]
    if len(exact) == 1:
        return int(exact[0]["id"]), "Exakter Treffer"
    best, ratio = None, 0.0
    for d in drivers:
        r = SequenceMatcher(None, source_norm, normalize(d["name"])).ratio()
        if r > ratio:
            best, ratio = d, r
    if best and ratio >= 0.84:
        return int(best["id"]), f"Ähnlicher Treffer ({int(ratio*100)}%)"
    return None, "Nicht gefunden"

# ---------------- auth ----------------
def admin_logged_in() -> bool:
    return bool(session.get("admin_ok"))


def admin_login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not admin_logged_in():
            return redirect(url_for("admin_login", next=request.path))
        return view(*args, **kwargs)
    return wrapped


def driver_login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not session.get("driver_db_id"):
            return redirect(url_for("driver_login"))
        return view(*args, **kwargs)
    return wrapped


def disposition_login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not session.get("dispo_db_id"):
            return redirect(url_for("driver_login"))
        return view(*args, **kwargs)
    return wrapped


def admin_api_required() -> None:
    token = request.headers.get("X-Admin-Token", "")
    if not ADMIN_API_TOKEN or token != ADMIN_API_TOKEN:
        abort(401)

# ---------------- templates ----------------
def base_page(title: str, body: str, active: str = "dashboard") -> str:
    nav = [
        ("dashboard","Dashboard",url_for("admin_dashboard")), ("drivers","Fahrer",url_for("admin_drivers")),
        ("payroll_hours","Stunden für Lohnabrechnung",url_for("admin_payroll_hours")),
        ("months","Plus/Minus Stunden",url_for("admin_months")),
        ("exports","Export/Backup",url_for("admin_exports")), ("cleanup","Aufräumen",url_for("admin_cleanup")), ("portal","Fahrerportal",url_for("driver_login")),
    ]
    flashes = "".join(f'<div class="flash {"ok" if c=="ok" else "err"}">{m}</div>' for c,m in get_flashed_messages(with_categories=True))
    return render_template_string("""
    <!doctype html><html lang="de"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{{ title }}</title><style>{{ css }}</style></head><body>
    <div class="shell"><aside class="side"><div class="brand">± Plus/Minus Cloud</div><div class="nav">{% for key,label,href in nav %}<a class="{{ 'active' if key==active else '' }}" href="{{ href }}">{{ label }}</a>{% endfor %}<a href="{{ url_for('admin_logout') }}">Logout Admin</a></div><p class="muted" style="color:#bdd2f4;margin-top:24px">Zentrale Cloud-Datenbank. Keine manuelle Synchronisation.</p></aside>
    <main class="main"><div class="top"><div><div class="title">{{ title }}</div><div class="subtitle">Änderungen werden direkt auf dem Server gespeichert und sind sofort auf allen PCs sichtbar.</div></div><span class="badge">Live Cloud</span></div>{{ flashes|safe }}{{ body|safe }}</main></div>
    <script>
    (function(){
      const key = 'plusminus_scroll_restore_v1';
      function saveScroll(){
        const wraps = Array.from(document.querySelectorAll('.table-wrap'));
        const wrapData = wraps.map((w, i) => ({i:i, left:w.scrollLeft || 0, top:w.scrollTop || 0}));
        try { localStorage.setItem(key, JSON.stringify({path: location.pathname + location.search, y: window.scrollY || 0, wraps: wrapData})); } catch(e) {}
      }
      document.addEventListener('submit', saveScroll, true);
      document.addEventListener('click', function(e){ if(e.target && (e.target.closest('button') || e.target.closest('.btn'))) saveScroll(); }, true);
      window.addEventListener('DOMContentLoaded', function(){
        let data = null;
        try { data = JSON.parse(localStorage.getItem(key) || 'null'); } catch(e) {}
        if(!data) return;
        if(data.path === location.pathname + location.search){
          const wraps = Array.from(document.querySelectorAll('.table-wrap'));
          (data.wraps || []).forEach(function(w){ if(wraps[w.i]){ wraps[w.i].scrollLeft = w.left || 0; wraps[w.i].scrollTop = w.top || 0; } });
          setTimeout(function(){ window.scrollTo(0, data.y || 0); }, 30);
          setTimeout(function(){ window.scrollTo(0, data.y || 0); }, 180);
        }
      });
    })();
    </script>
    </body></html>
    """, title=title, css=BASE_CSS, nav=nav, active=active, flashes=flashes, body=body)

# ---------------- admin routes ----------------
@app.get("/health")
def health():
    return {"ok": True, "app": APP_NAME, "db": str(DB_FILE)}


@app.get("/")
def index():
    return redirect(url_for("driver_login"))


@app.route("/admin/login", methods=["GET","POST"])
def admin_login():
    error = ""
    if request.method == "POST":
        password = request.form.get("password", "")
        ok = bool(ADMIN_PASSWORD and password == ADMIN_PASSWORD)
        if ok:
            session.clear()
            session["admin_ok"] = True
            return redirect(request.args.get("next") or url_for("admin_dashboard"))
        error = "Admin-Login fehlgeschlagen. Bitte Passwort prüfen."
    return render_template_string("""
    <!doctype html><html lang="de"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Admin Login</title><style>{{ css }}</style></head><body>
    <div class="login-wrap"><div class="card">
      <div class="title">Admin Login</div>
      <p class="muted">Plus/Minus-Stunden-Rechner als Cloud-Web-App</p>
      {% if error %}<div class="flash err">{{ error }}</div>{% endif %}
      <form method="post">
        <label>Admin-Passwort</label>
        <input name="password" type="password" autocomplete="current-password" required autofocus>
        <button class="primary" style="margin-top:14px">Einloggen</button>
      </form>
      <p style="margin-top:14px"><a class="btn" href="{{ url_for('driver_login') }}">Zurück zum Fahrer-Login</a></p>
    </div></div></body></html>
    """, css=BASE_CSS, error=error)


@app.get("/admin/logout")
def admin_logout():
    session.clear()
    return redirect(url_for("admin_login"))


@app.get("/admin")
@admin_login_required
def admin_dashboard():
    sort_mode = normalize_balance_sort(request.args.get("sort", "order"))
    with db_conn() as conn:
        recalc_all(conn); conn.commit()
        k = conn.execute("SELECT COUNT(*) drivers, COALESCE(SUM(is_active),0) active FROM drivers WHERE COALESCE(is_disposition,0)=0").fetchone()
        m = conn.execute("""
            SELECT COUNT(*) cnt
            FROM monthly_data m
            JOIN drivers d ON d.id=m.driver_id
            WHERE COALESCE(d.is_disposition,0)=0
        """).fetchone()["cnt"]
        docs = conn.execute("""
            SELECT COUNT(*) cnt
            FROM documents doc
            JOIN drivers d ON d.id=doc.driver_id
            WHERE COALESCE(d.is_disposition,0)=0
        """).fetchone()["cnt"]
        latest = conn.execute("""
            SELECT m.*, d.name
            FROM monthly_data m
            JOIN drivers d ON d.id=m.driver_id
            WHERE COALESCE(d.is_disposition,0)=0
            ORDER BY m.updated_at DESC
            LIMIT 8
        """).fetchall()
        balances = load_current_balances(conn, sort_mode)
    body = render_template_string("""
    <div class="grid grid-4"><div class="kpi">Fahrer<b>{{ k['active'] }}</b><span class="muted">aktiv</span></div><div class="kpi">Monatsdaten<b>{{ m }}</b><span class="muted">gespeichert</span></div><div class="kpi">PDFs<b>{{ docs }}</b><span class="muted">im Portal</span></div><div class="kpi">Sync<b>0</b><span class="muted">manuelle Schritte</span></div></div>
    <div class="grid grid-2"><div class="card"><div class="actions" style="justify-content:space-between;margin-bottom:10px"><h2 style="margin:0">Aktuelle Salden</h2><div class="actions"><span class="muted">Sortieren nach:</span><a class="btn small {{ 'primary' if sort_mode=='asc' else '' }}" href="{{ url_for('admin_dashboard', sort='asc') }}">Aufsteigend</a><a class="btn small {{ 'primary' if sort_mode=='desc' else '' }}" href="{{ url_for('admin_dashboard', sort='desc') }}">Absteigend</a><a class="btn small {{ 'primary' if sort_mode=='order' else '' }}" href="{{ url_for('admin_dashboard') }}">Fahrer-Reihenfolge</a></div></div><div class="table-wrap"><table style="min-width:420px"><tr><th>Fahrer</th><th class="right">Saldo</th></tr>{% for r in balances %}<tr><td>{{ r['name'] }}</td><td class="right {{ signed_class(r['bal'] if r['bal'] is not none else r['starting_balance']) }}">{{ fmt_signed(r['bal'] if r['bal'] is not none else r['starting_balance']) }}</td></tr>{% endfor %}</table></div></div>
    <div class="card"><h2>Letzte Änderungen</h2><div class="table-wrap"><table style="min-width:560px"><tr><th>Fahrer</th><th>Monat</th><th>Differenz</th><th>Neu</th></tr>{% for r in latest %}<tr><td>{{ r['name'] }}</td><td>{{ months[r['month']] }} {{ r['year'] }}</td><td class="{{ signed_class(r['difference_hours']) }}">{{ fmt_signed(r['difference_hours']) }}</td><td class="{{ signed_class(r['new_balance']) }}">{{ fmt_signed(r['new_balance']) }}</td></tr>{% endfor %}</table></div></div></div>
    """, k=k, m=m, docs=docs, latest=latest, balances=balances, months=MONATE, fmt_signed=fmt_signed, signed_class=signed_class, sort_mode=sort_mode)
    return base_page("Dashboard", body, "dashboard")

@app.route("/admin/drivers", methods=["GET","POST"])
@admin_login_required
def admin_drivers():
    with db_conn() as conn:
        if request.method == "POST":
            action = request.form.get("action")
            ts = now_iso()
            if action == "sort_name_az":
                sort_drivers_name_az(conn)
                audit(conn, "drivers_sort_name_az", "")
                conn.commit(); flash("Fahrer wurden alphabetisch nach Name A-Z sortiert. Diese Reihenfolge gilt auch für Stunden für Lohnabrechnung.", "ok")
                return redirect(url_for("admin_drivers"))
            elif action == "sort_custom":
                restore_custom_driver_order(conn)
                audit(conn, "drivers_sort_custom", "")
                conn.commit(); flash("Eigene Sortierung wurde wiederhergestellt.", "ok")
                return redirect(url_for("admin_drivers"))
            elif action == "create":
                name = request.form.get("name", "").strip(); username = request.form.get("username", "").strip() or slugify(name); password = request.form.get("password", "").strip(); is_disposition = 1 if request.form.get("is_disposition") == "on" else 0
                employment_type = "" if is_disposition else normalize_employment_type(request.form.get("employment_type", ""))
                start = 0.0 if is_disposition else parse_hours(request.form.get("starting_balance", "0"))
                if not name or not password:
                    flash("Name und Passwort sind Pflicht.", "err")
                else:
                    ext = None if is_disposition else next_external_id(conn); username = make_unique_username(conn, username)
                    display_order = 0 if is_disposition else int(ext or 0)
                    conn.execute("INSERT INTO drivers(external_driver_id,name,employment_type,username,password_hash,password_plain,starting_balance,display_order,is_active,is_disposition,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,1,?,?,?)", (ext,name,employment_type,username,generate_password_hash(password),password,start,display_order,is_disposition,ts,ts)); audit(conn,"disposition_create" if is_disposition else "driver_create",name); conn.commit(); flash("Disposition-Account angelegt." if is_disposition else "Fahrer angelegt.", "ok")
            elif action == "update":
                did = int(request.form["driver_id"]); name = request.form.get("name", "").strip(); username = request.form.get("username", "").strip(); start = parse_hours(request.form.get("starting_balance", "0")); active = 1 if request.form.get("is_active") == "on" else 0; employment_type = normalize_employment_type(request.form.get("employment_type", ""))
                username = make_unique_username(conn, username or name, exclude_id=did)
                conn.execute("UPDATE drivers SET name=?,employment_type=?,username=?,starting_balance=?,is_active=?,updated_at=? WHERE id=?", (name,employment_type,username,start,active,ts,did))
                pw = request.form.get("password", "").strip()
                if pw:
                    conn.execute("UPDATE drivers SET password_hash=?,password_plain=?,updated_at=? WHERE id=?", (generate_password_hash(pw),pw,ts,did))
                recalc_driver(conn,did); audit(conn,"driver_update",name); conn.commit(); flash("Fahrer gespeichert.", "ok")
            elif action == "delete":
                did = int(request.form["driver_id"]); conn.execute("DELETE FROM drivers WHERE id=?", (did,)); audit(conn,"driver_delete",str(did)); conn.commit(); flash("Fahrer gelöscht.", "ok")
            elif action == "create_group":
                member_ids = [int(x) for x in request.form.getlist("group_driver_ids") if str(x).isdigit()]
                member_ids = list(dict.fromkeys(member_ids))
                group_name = request.form.get("group_name", "").strip()
                if len(member_ids) < 2:
                    flash("Bitte mindestens zwei Fahrer für eine Gruppe auswählen.", "err")
                else:
                    already = conn.execute("SELECT driver_id FROM driver_group_members WHERE driver_id IN (" + ",".join(["?"]*len(member_ids)) + ")", tuple(member_ids)).fetchall()
                    if already:
                        flash("Mindestens ein ausgewählter Fahrer ist bereits in einer Gruppe. Bitte erst die alte Gruppe löschen.", "err")
                    else:
                        if not group_name:
                            selected = conn.execute("SELECT name FROM drivers WHERE id IN (" + ",".join(["?"]*len(member_ids)) + ") ORDER BY COALESCE(NULLIF(display_order,0), id), name COLLATE NOCASE", tuple(member_ids)).fetchall()
                            group_name = " und ".join([r["name"] for r in selected])
                        cur = conn.execute("INSERT INTO driver_groups(name,is_active,created_at,updated_at) VALUES(?,1,?,?)", (group_name, ts, ts))
                        gid = int(cur.lastrowid)
                        for pos, mid in enumerate(member_ids, start=1):
                            conn.execute("INSERT INTO driver_group_members(group_id,driver_id,position) VALUES(?,?,?)", (gid, mid, pos))
                        audit(conn, "driver_group_create", f"{group_name}: {member_ids}")
                        conn.commit(); flash("Fahrergruppe erstellt. In Plus/Minus Stunden werden diese Fahrer zusammen angezeigt.", "ok")
            elif action == "delete_group":
                gid = int(request.form["group_id"])
                conn.execute("DELETE FROM driver_groups WHERE id=?", (gid,))
                audit(conn, "driver_group_delete", str(gid))
                conn.commit(); flash("Fahrergruppe gelöscht. Die einzelnen Fahrerdaten bleiben erhalten.", "ok")
        drivers = conn.execute("SELECT d.*, COALESCE((SELECT new_balance FROM monthly_data m WHERE m.driver_id=d.id ORDER BY year DESC,month DESC,id DESC LIMIT 1), d.starting_balance) AS balance FROM drivers d WHERE COALESCE(d.is_disposition,0)=0 ORDER BY COALESCE(NULLIF(d.display_order,0), d.id), d.name COLLATE NOCASE").fetchall()
        disposition_accounts = conn.execute("SELECT * FROM drivers WHERE COALESCE(is_disposition,0)=1 ORDER BY name COLLATE NOCASE").fetchall()
        groups = load_driver_groups(conn)
        driver_sort_mode = get_driver_sort_mode(conn)
    body = render_template_string("""
    <div class="card"><h2>Neuen Fahrer anlegen</h2><form method="post" class="grid grid-4"><input type="hidden" name="action" value="create"><div><label>Name</label><input name="name" required></div><div><label>Vollzeit/Teilzeit/Aushilfe</label><select name="employment_type"><option value="">— auswählen —</option><option value="vollzeit">Vollzeit</option><option value="teilzeit">Teilzeit</option><option value="aushilfe">Aushilfe</option></select></div><div><label>Benutzername</label><input name="username" placeholder="automatisch"></div><div><label>Passwort</label><input name="password" required></div><div><label>Anfangssaldo</label><input name="starting_balance" value="0"><label style="margin-top:10px;width:auto;font-weight:800"><input style="width:auto" type="checkbox" name="is_disposition"> Disposition</label><div class="download-note">Wenn aktiviert, wird daraus kein Fahrer, sondern ein Dispo-Login nur für das Dashboard mit aktuellen Salden.</div></div><button class="primary">Anlegen</button></form></div>
    <div class="card"><h2>Fahrer nur für Plus/Minus Stunden zusammenführen</h2><p class="muted">Die ausgewählten Fahrer bleiben bei „Stunden für Lohnabrechnung“ einzeln sichtbar. Nur in „Plus/Minus Stunden“ erscheinen sie als gemeinsame Zeile mit zusammengerechneten Werten.</p><form method="post" class="grid grid-3"><input type="hidden" name="action" value="create_group"><div><label>Gruppenname</label><input name="group_name" placeholder="z.B. Alex und Jennifer"></div><div><label>Fahrer auswählen</label><select name="group_driver_ids" multiple size="6">{% for d in drivers %}<option value="{{ d['id'] }}">{{ d['name'] }}</option>{% endfor %}</select><div class="download-note">Mehrere auswählen mit Strg/Cmd oder Shift.</div></div><div style="align-self:end"><button class="primary">Gruppe erstellen</button></div></form>{% if groups %}<div class="adjustment-list"><h3>Aktive Gruppen</h3>{% for g in groups %}<div class="item-row"><b>{{ g.name }}</b><span class="muted">{{ g.members|map(attribute='name')|join(', ') }}</span><form method="post" onsubmit="return confirm('Gruppe wirklich löschen? Die Fahrer und Monatsdaten bleiben erhalten.')"><input type="hidden" name="action" value="delete_group"><input type="hidden" name="group_id" value="{{ g.group['id'] }}"><button class="small danger">Gruppe löschen</button></form></div>{% endfor %}</div>{% endif %}</div>
    {% if disposition_accounts %}<div class="card"><h2>Disposition-Accounts</h2><p class="muted">Diese Accounts sehen nur das Dashboard mit den aktuellen Salden und keine Fahrerportal- oder Admin-Tabs.</p><div class="table-wrap"><table style="min-width:900px"><thead><tr><th>Name</th><th>Benutzername</th><th>Aktiv</th><th>Aktuelles Passwort</th><th>Neues Passwort</th><th>Aktion</th></tr></thead><tbody>{% for d in disposition_accounts %}<tr><form method="post"><input type="hidden" name="action" value="update"><input type="hidden" name="driver_id" value="{{ d['id'] }}"><input type="hidden" name="starting_balance" value="0"><td><input name="name" value="{{ d['name'] }}"></td><td><input name="username" value="{{ d['username'] }}"></td><td><input style="width:auto" type="checkbox" name="is_active" {% if d['is_active'] %}checked{% endif %}></td><td><input readonly tabindex="-1" value="{{ d['password_plain'] or 'nicht auslesbar – neu setzen' }}" style="background:#f3f4f6;color:#667085;font-family:monospace"></td><td><input name="password" placeholder="leer lassen"></td><td class="actions"><button class="small primary">Speichern</button></form><form method="post" onsubmit="return confirm('Disposition-Account wirklich löschen?')"><input type="hidden" name="action" value="delete"><input type="hidden" name="driver_id" value="{{ d['id'] }}"><button class="small danger">Löschen</button></form></td></tr>{% endfor %}</tbody></table></div></div>{% endif %}
    <div class="card"><div class="actions" style="justify-content:space-between;margin-bottom:10px"><h2 style="margin:0">Fahrer verwalten</h2><div class="actions"><span class="muted">Sortieren nach:</span><form method="post"><input type="hidden" name="action" value="sort_custom"><button class="small driver-sort-button driver-sort-button-custom {{ 'primary' if driver_sort_mode=='custom' else '' }}" type="submit">Eigene Sortierung</button></form><form method="post"><input type="hidden" name="action" value="sort_name_az"><button class="small driver-sort-button driver-sort-button-az {{ 'primary' if driver_sort_mode=='name_az' else '' }}" type="submit">Name A-Z</button></form></div></div><p class="muted">Ziehe die Fahrer mit dem Griff links nach oben oder unten. Die Reihenfolge wird automatisch gespeichert. Bei alten Konten wird das aktuelle Passwort nach dem nächsten erfolgreichen Fahrer-Login angezeigt; alternativ kann es hier neu gesetzt werden.</p><div class="table-wrap"><table><thead><tr><th style="width:48px">Sort.</th><th>Name</th><th>Vollzeit/Teilzeit/Aushilfe</th><th>Benutzername</th><th>Anfang</th><th>Aktueller Saldo</th><th>Aktiv</th><th>Aktuelles Passwort</th><th>Neues Passwort</th><th>Aktion</th></tr></thead><tbody id="drivers-sortable">{% for d in drivers %}<tr draggable="true" data-driver-id="{{ d['id'] }}"><td class="drag-handle" title="Ziehen zum Sortieren" style="cursor:grab;font-size:20px;text-align:center;color:#667085">☰</td><form method="post"><input type="hidden" name="action" value="update"><input type="hidden" name="driver_id" value="{{ d['id'] }}"><td><input name="name" value="{{ d['name'] }}"></td><td><select name="employment_type"><option value="" {% if not d['employment_type'] %}selected{% endif %}>— auswählen —</option><option value="vollzeit" {% if d['employment_type']=='vollzeit' %}selected{% endif %}>Vollzeit</option><option value="teilzeit" {% if d['employment_type']=='teilzeit' %}selected{% endif %}>Teilzeit</option><option value="aushilfe" {% if d['employment_type']=='aushilfe' %}selected{% endif %}>Aushilfe</option></select></td><td><input name="username" value="{{ d['username'] }}"></td><td><input name="starting_balance" value="{{ fmt_signed(d['starting_balance']) }}"></td><td class="{{ signed_class(d['balance']) }} nowrap">{{ fmt_signed(d['balance']) }}</td><td><input style="width:auto" type="checkbox" name="is_active" {% if d['is_active'] %}checked{% endif %}></td><td><input readonly tabindex="-1" value="{{ d['password_plain'] or 'nicht auslesbar – neu setzen' }}" style="background:#f3f4f6;color:#667085;font-family:monospace"></td><td><input name="password" placeholder="leer lassen"></td><td class="actions"><button class="small primary">Speichern</button></form><form method="post" onsubmit="return confirm('Fahrer wirklich löschen?')"><input type="hidden" name="action" value="delete"><input type="hidden" name="driver_id" value="{{ d['id'] }}"><button class="small danger">Löschen</button></form></td></tr>{% endfor %}</tbody></table></div></div>
    <script>
    (function(){
      const tbody = document.getElementById('drivers-sortable');
      if(!tbody) return;
      let dragged = null;
      let saving = false;
      function rows(){ return Array.from(tbody.querySelectorAll('tr[data-driver-id]')); }
      function saveOrder(){
        if(saving) return;
        saving = true;
        fetch('{{ url_for("admin_drivers_reorder") }}', {
          method: 'POST',
          headers: {'Content-Type': 'application/json'},
          credentials: 'same-origin',
          body: JSON.stringify({driver_ids: rows().map(r => r.dataset.driverId)})
        }).then(r => r.json()).then(data => {
          saving = false;
          if(!data.ok) alert(data.error || 'Reihenfolge konnte nicht gespeichert werden.');
          else {
            document.querySelectorAll('.driver-sort-button').forEach(function(btn){ btn.classList.remove('primary'); });
            var customBtn = document.querySelector('.driver-sort-button-custom');
            if(customBtn) customBtn.classList.add('primary');
          }
        }).catch(() => { saving = false; alert('Reihenfolge konnte nicht gespeichert werden.'); });
      }
      tbody.addEventListener('dragstart', function(e){
        const tr = e.target.closest('tr[data-driver-id]');
        if(!tr) return;
        dragged = tr;
        tr.style.opacity = '0.45';
        e.dataTransfer.effectAllowed = 'move';
        e.dataTransfer.setData('text/plain', tr.dataset.driverId);
      });
      tbody.addEventListener('dragend', function(){
        if(dragged) dragged.style.opacity = '';
        dragged = null;
      });
      tbody.addEventListener('dragover', function(e){
        e.preventDefault();
        const over = e.target.closest('tr[data-driver-id]');
        if(!dragged || !over || dragged === over) return;
        const rect = over.getBoundingClientRect();
        const after = (e.clientY - rect.top) > rect.height / 2;
        tbody.insertBefore(dragged, after ? over.nextSibling : over);
      });
      tbody.addEventListener('drop', function(e){
        e.preventDefault();
        saveOrder();
      });
    })();
    </script>
    """, drivers=drivers, disposition_accounts=disposition_accounts, groups=groups, driver_sort_mode=driver_sort_mode, fmt_signed=fmt_signed, signed_class=signed_class)
    return base_page("Fahrer", body, "drivers")


@app.post("/admin/drivers/reorder")
@admin_login_required
def admin_drivers_reorder():
    data = request.get_json(silent=True) or {}
    ids = data.get("driver_ids", [])
    try:
        driver_ids = [int(x) for x in ids]
    except Exception:
        return jsonify({"ok": False, "error": "Ungültige Fahrer-Reihenfolge."}), 400

    if not driver_ids:
        return jsonify({"ok": False, "error": "Keine Fahrer übergeben."}), 400

    with db_conn() as conn:
        final_order = apply_driver_order(conn, driver_ids)
        save_custom_driver_order(conn, final_order)
        set_driver_sort_mode(conn, "custom")
        audit(conn, "drivers_reorder", ",".join(str(x) for x in final_order))
        conn.commit()
    return jsonify({"ok": True, "sort_mode": "custom"})


@app.route("/admin/months", methods=["GET","POST"])
@admin_login_required
def admin_months():
    year = int(request.values.get("year") or datetime.now().year)
    month = int(request.values.get("month") or datetime.now().month)
    editable = month_is_editable(year, month)
    locked_note = month_locked_message(year, month)
    with db_conn() as conn:
        if request.method == "POST":
            action = request.form.get("action")
            if not editable and action != "toggle_month_release":
                flash(locked_note, "err")
                return redirect(url_for("admin_months", year=year, month=month))
            if action == "set_global_v":
                enabled = request.form.get("global_v_enabled") == "1"
                set_global_v_enabled(conn, year, month, enabled)
                recalc_all(conn)
                audit(conn, "global_v_toggle", f"{year}-{month} {int(enabled)}")
                conn.commit()
                flash("V wurde bei allen Fahrern aktiviert." if enabled else "V wurde bei allen Fahrern deaktiviert.", "ok")
                return redirect(url_for("admin_months", year=year, month=month))
            if action == "toggle_month_release":
                release = request.form.get("release") == "1"
                set_month_release(conn, year, month, release)
                audit(conn, "month_release" if release else "month_lock", f"{year}-{month}")
                conn.commit()
                flash(
                    f"{MONATE[month]} {year} ist jetzt für Fahrer sichtbar." if release else f"{MONATE[month]} {year} ist jetzt für Fahrer gesperrt.",
                    "ok",
                )
                return redirect(url_for("admin_months", year=year, month=month))
            if action in {"save_all", "save", "delete", "add_adjustment", "delete_adjustment", "delete_adjustment_file"}:
                if action == "save_all":
                    saved_count = 0
                    # Speichert alle sichtbaren Einzel- und Gruppenzeilen auf einmal.
                    for key in request.form:
                        if not key.startswith("row_driver_id_"):
                            continue
                        suffix = key.replace("row_driver_id_", "", 1)
                        row_driver_raw = request.form.get(key, "")
                        if not row_driver_raw:
                            continue
                        if row_driver_raw.startswith("group_"):
                            gid = int(row_driver_raw.split("_", 1)[1])
                            gm_id = ensure_group_month_row(conn, gid, year, month)
                            worked = parse_hours(request.form.get(f"worked_hours_{suffix}", "0"))
                            admin_info = request.form.get(f"admin_info_{suffix}", "").strip()
                            v_enabled = form_v_enabled(f"v_enabled_{suffix}")
                            conn.execute("UPDATE driver_group_month_data SET worked_hours=?, v_enabled=?, admin_info=?, updated_at=? WHERE id=?", (worked, v_enabled, admin_info, now_iso(), gm_id))
                            sync_group_admin_info(conn, gid, year, month, admin_info)
                            saved_count += 1
                        else:
                            did2 = int(row_driver_raw)
                            mid = get_or_create_month_row(conn, did2, year, month)
                            worked = parse_hours(request.form.get(f"worked_hours_{suffix}", "0"))
                            payroll = parse_hours(request.form.get(f"payroll_hours_{suffix}", "0"))
                            v_note = request.form.get(f"v_note_{suffix}", "").strip()
                            v_enabled = form_v_enabled(f"v_enabled_{suffix}")
                            admin_info = request.form.get(f"admin_info_{suffix}", "").strip()
                            conn.execute("UPDATE monthly_data SET worked_hours=?, payroll_hours=?, v_hours=0, v_note=?, v_enabled=?, admin_info=?, admin_info_carried=0, updated_at=? WHERE id=?", (worked, payroll, v_note, v_enabled, admin_info, now_iso(), mid))
                            recalc_month_adjustments(conn, mid)
                            recalc_driver(conn, did2)
                            create_driver_pdf(conn, did2, year, month)
                            saved_count += 1
                    audit(conn, "month_save_all", f"{year}-{month} {saved_count}")
                    conn.commit()
                    flash(f"Alle Einträge gespeichert ({saved_count}).", "ok")
                    return redirect(url_for("admin_months", year=year, month=month))
                driver_id_raw = request.form.get("driver_id", "")
                if driver_id_raw.startswith("group_"):
                    group_id = int(driver_id_raw.split("_", 1)[1])
                    if action in {"save", "add_adjustment"}:
                        worked = parse_hours(request.form.get("worked_hours", "0"))
                        admin_info = request.form.get("admin_info", "").strip()
                        v_enabled = form_v_enabled("v_enabled")
                        group_month_id = ensure_group_month_row(conn, group_id, year, month)
                        conn.execute("UPDATE driver_group_month_data SET worked_hours=?, v_enabled=?, admin_info=?, updated_at=? WHERE id=?", (worked, v_enabled, admin_info, now_iso(), group_month_id))
                        sync_group_admin_info(conn, group_id, year, month, admin_info)
                        should_add_item = action == "add_adjustment" or bool((request.form.get("item_hours", "") or "").strip() or (request.form.get("item_note", "") or "").strip() or (request.files.get("item_file") and request.files.get("item_file").filename))
                        if should_add_item:
                            kind = request.form.get("kind", "")
                            if kind not in {"bonus", "deduction"}:
                                flash("Ungültige Art.", "err")
                            else:
                                hours = abs(parse_hours(request.form.get("item_hours", "0")))
                                note = request.form.get("item_note", "").strip()
                                if hours <= 0:
                                    flash("Bitte Stunden für Zuschuss/Abzug eingeben.", "err")
                                elif not note:
                                    flash("Bitte Kommentar/Grund eingeben.", "err")
                                else:
                                    cur = conn.execute("INSERT INTO driver_group_adjustment_items(group_month_data_id, kind, hours, note, created_at) VALUES(?,?,?,?,?)", (group_month_id, kind, hours, note, now_iso()))
                                    group_adjustment_id = int(cur.lastrowid)
                                    uploaded = request.files.get("item_file")
                                    if uploaded and uploaded.filename:
                                        if kind != "deduction":
                                            flash("Anhänge sind nur bei Abzügen möglich. Position wurde ohne Datei gespeichert.", "err")
                                        elif not allowed_attachment(uploaded.filename):
                                            flash("Datei nicht erlaubt. Bitte JPG, PNG, WEBP, GIF oder PDF hochladen. Position wurde ohne Datei gespeichert.", "err")
                                        else:
                                            rel = Path("attachments") / "groups" / str(group_id) / str(year) / f"{month:02d}" / str(group_adjustment_id) / (datetime.now().strftime("%Y%m%d_%H%M%S_%f") + "_" + (secure_filename(uploaded.filename) or "anhang"))
                                            abs_path = DATA_ROOT / rel
                                            abs_path.parent.mkdir(parents=True, exist_ok=True)
                                            uploaded.save(abs_path)
                                            conn.execute("INSERT INTO driver_group_adjustment_files(group_adjustment_item_id, filename, original_filename, relative_path, mime_type, uploaded_at) VALUES(?,?,?,?,?,?)", (group_adjustment_id, abs_path.name, uploaded.filename, str(rel), uploaded.mimetype or "", now_iso()))
                                            flash("Bild/Datei erfolgreich hochgeladen.", "ok")
                                    flash("Gruppenposition hinzugefügt und automatisch verrechnet.", "ok")
                        audit(conn, "group_month_save", f"{group_id} {year}-{month} {worked}")
                        conn.commit()
                        flash("Gruppe gespeichert.", "ok")
                    elif action == "delete_adjustment":
                        item_id = int(request.form["item_id"])
                        row = conn.execute("SELECT gi.*, gm.group_id FROM driver_group_adjustment_items gi JOIN driver_group_month_data gm ON gm.id=gi.group_month_data_id WHERE gi.id=? AND gm.group_id=? AND gm.year=? AND gm.month=?", (item_id, group_id, year, month)).fetchone()
                        if row:
                            for f in conn.execute("SELECT relative_path FROM driver_group_adjustment_files WHERE group_adjustment_item_id=?", (item_id,)).fetchall():
                                delete_relative_file(f["relative_path"])
                            conn.execute("DELETE FROM driver_group_adjustment_items WHERE id=?", (item_id,))
                            conn.commit()
                            flash("Gruppenposition gelöscht.", "ok")
                    elif action == "delete_adjustment_file":
                        file_id = int(request.form["file_id"])
                        frow = conn.execute("""
                            SELECT gf.*
                            FROM driver_group_adjustment_files gf
                            JOIN driver_group_adjustment_items gi ON gi.id=gf.group_adjustment_item_id
                            JOIN driver_group_month_data gm ON gm.id=gi.group_month_data_id
                            WHERE gf.id=? AND gm.group_id=? AND gm.year=? AND gm.month=?
                        """, (file_id, group_id, year, month)).fetchone()
                        if frow:
                            delete_relative_file(frow["relative_path"])
                            conn.execute("DELETE FROM driver_group_adjustment_files WHERE id=?", (file_id,))
                            conn.commit()
                            flash("Bild/Datei wurde entfernt.", "ok")
                    else:
                        flash("Diese Aktion ist bei Gruppen nicht möglich.", "err")
                    return redirect(url_for("admin_months", year=year, month=month))
                did = int(driver_id_raw)

                if action == "delete":
                    conn.execute("DELETE FROM monthly_data WHERE driver_id=? AND year=? AND month=?", (did, year, month))
                    recalc_driver(conn, did)
                    audit(conn, "month_delete", f"{did} {year}-{month}")
                    conn.commit()
                    flash("Monatsdatensatz gelöscht.", "ok")

                elif action in {"save", "add_adjustment"}:
                    # Immer zuerst die Monatsdaten speichern, egal ob man auf
                    # "Speichern" oder "Hinzufügen" klickt. So gehen Stunden,
                    # Abrechnung, V und Admin-Infos nicht verloren.
                    worked = parse_hours(request.form.get("worked_hours", "0"))
                    payroll = parse_hours(request.form.get("payroll_hours", "0"))
                    # V is a pure text note. It is never used in calculations.
                    v_note = request.form.get("v_note", "").strip()
                    v_enabled = form_v_enabled("v_enabled")
                    admin_info = request.form.get("admin_info", "").strip()
                    monthly_id = get_or_create_month_row(conn, did, year, month)
                    conn.execute("UPDATE monthly_data SET worked_hours=?, payroll_hours=?, v_hours=0, v_note=?, v_enabled=?, admin_info=?, admin_info_carried=0, updated_at=? WHERE id=?", (worked, payroll, v_note, v_enabled, admin_info, now_iso(), monthly_id))

                    should_add_item = action == "add_adjustment" or bool((request.form.get("item_hours", "") or "").strip() or (request.form.get("item_note", "") or "").strip() or (request.files.get("item_file") and request.files.get("item_file").filename))

                    if should_add_item:
                        kind = request.form.get("kind", "")
                        if kind not in {"bonus", "deduction"}:
                            flash("Ungültige Art.", "err")
                        else:
                            hours = abs(parse_hours(request.form.get("item_hours", "0")))
                            note = request.form.get("item_note", "").strip()
                            if hours <= 0:
                                flash("Bitte Stunden für Zuschuss/Abzug eingeben.", "err")
                            elif not note:
                                flash("Bitte Kommentar/Grund eingeben.", "err")
                            else:
                                cur = conn.execute("INSERT INTO adjustment_items(monthly_data_id, kind, hours, note, created_at) VALUES(?,?,?,?,?)", (monthly_id, kind, hours, note, now_iso()))
                                adjustment_id = int(cur.lastrowid)
                                uploaded = request.files.get("item_file")
                                if uploaded and uploaded.filename:
                                    if kind != "deduction":
                                        flash("Anhänge sind nur bei Abzügen möglich. Position wurde ohne Datei gespeichert.", "err")
                                    elif not allowed_attachment(uploaded.filename):
                                        flash("Datei nicht erlaubt. Bitte JPG, PNG, WEBP, GIF oder PDF hochladen. Position wurde ohne Datei gespeichert.", "err")
                                    else:
                                        rel = attachment_relative_path(did, year, month, adjustment_id, uploaded.filename)
                                        abs_path = DATA_ROOT / rel
                                        abs_path.parent.mkdir(parents=True, exist_ok=True)
                                        uploaded.save(abs_path)
                                        conn.execute("INSERT INTO adjustment_files(adjustment_item_id, filename, original_filename, relative_path, mime_type, uploaded_at) VALUES(?,?,?,?,?,?)", (adjustment_id, abs_path.name, uploaded.filename, str(rel), uploaded.mimetype or "", now_iso()))
                                        flash("Bild/Datei erfolgreich hochgeladen.", "ok")
                                audit(conn, "adjustment_add", f"{did} {year}-{month} {kind} {hours} {note}")
                                flash("Position hinzugefügt und automatisch verrechnet.", "ok")

                    recalc_month_adjustments(conn, monthly_id)
                    recalc_driver(conn, did)
                    create_driver_pdf(conn, did, year, month)
                    audit(conn, "month_save", f"{did} {year}-{month}")
                    conn.commit()
                    flash("Plus/Minus Stunden gespeichert und Fahrer-PDF automatisch aktualisiert.", "ok")

                elif action == "delete_adjustment":
                    item_id = int(request.form["item_id"])
                    item = conn.execute("""
                        SELECT ai.*, m.driver_id
                        FROM adjustment_items ai
                        JOIN monthly_data m ON m.id=ai.monthly_data_id
                        WHERE ai.id=? AND m.driver_id=? AND m.year=? AND m.month=?
                    """, (item_id, did, year, month)).fetchone()
                    if item:
                        monthly_id = int(item["monthly_data_id"])
                        for f in conn.execute("SELECT relative_path FROM adjustment_files WHERE adjustment_item_id=?", (item_id,)).fetchall():
                            delete_attachment_file(f["relative_path"])
                        conn.execute("DELETE FROM adjustment_items WHERE id=?", (item_id,))
                        recalc_month_adjustments(conn, monthly_id)
                        recalc_driver(conn, did)
                        create_driver_pdf(conn, did, year, month)
                        audit(conn, "adjustment_delete", str(item_id))
                        conn.commit()
                        flash("Position gelöscht und neu berechnet.", "ok")

                elif action == "delete_adjustment_file":
                    file_id = int(request.form["file_id"])
                    frow = conn.execute("""
                        SELECT af.*, ai.monthly_data_id
                        FROM adjustment_files af
                        JOIN adjustment_items ai ON ai.id=af.adjustment_item_id
                        JOIN monthly_data m ON m.id=ai.monthly_data_id
                        WHERE af.id=? AND m.driver_id=? AND m.year=? AND m.month=?
                    """, (file_id, did, year, month)).fetchone()
                    if frow:
                        delete_attachment_file(frow["relative_path"])
                        conn.execute("DELETE FROM adjustment_files WHERE id=?", (file_id,))
                        monthly_id = int(frow["monthly_data_id"])
                        recalc_month_adjustments(conn, monthly_id)
                        recalc_driver(conn, did)
                        create_driver_pdf(conn, did, year, month)
                        audit(conn, "adjustment_file_delete", str(file_id))
                        conn.commit()
                        flash("Bild/Datei wurde entfernt.", "ok")

        recalc_all(conn); conn.commit()
        drivers = conn.execute("SELECT * FROM drivers WHERE is_active=1 AND COALESCE(is_disposition,0)=0 ORDER BY COALESCE(NULLIF(display_order,0), id), name COLLATE NOCASE").fetchall()
        if editable:
            for d in drivers:
                get_or_create_month_row(conn, int(d["id"]), year, month, carry_admin_info=True)
            conn.commit()
        rows = {int(r["driver_id"]): r for r in conn.execute("SELECT * FROM monthly_data WHERE year=? AND month=?", (year,month)).fetchall()}
        adjustments: Dict[int, List[sqlite3.Row]] = {}
        for item in conn.execute("""
            SELECT ai.*, m.driver_id
            FROM adjustment_items ai
            JOIN monthly_data m ON m.id=ai.monthly_data_id
            WHERE m.year=? AND m.month=?
            ORDER BY ai.id
        """, (year, month)).fetchall():
            adjustments.setdefault(int(item["driver_id"]), []).append(item)
        adjustment_files: Dict[int, List[sqlite3.Row]] = {}
        for f in conn.execute("""
            SELECT af.*, ai.id AS adjustment_id
            FROM adjustment_files af
            JOIN adjustment_items ai ON ai.id=af.adjustment_item_id
            JOIN monthly_data m ON m.id=ai.monthly_data_id
            WHERE m.year=? AND m.month=?
            ORDER BY af.id
        """, (year, month)).fetchall():
            adjustment_files.setdefault(int(f["adjustment_id"]), []).append(f)

        group_infos = load_driver_groups(conn)
        grouped_driver_ids = {did for g in group_infos for did in g["member_ids"]}
        display_drivers: List[Dict[str, Any]] = []
        for d in drivers:
            if int(d["id"]) not in grouped_driver_ids:
                nd = dict(d); nd["is_group"] = 0; nd["form_id"] = str(d["id"]); nd["member_names"] = ""
                display_drivers.append(nd)
        group_adjustment_files: Dict[int, List[Any]] = {}
        for g in group_infos:
            gid = int(g["group"]["id"])
            key = f"group_{gid}"
            group_types = {normalize_employment_type(str(row_get(m, "employment_type", "") or "")) for m in g["members"]}
            group_types.discard("")
            group_type = next(iter(group_types)) if len(group_types) == 1 else ""
            display_drivers.append({"id": key, "form_id": key, "is_group": 1, "name": g["name"], "employment_type": group_type, "member_names": ", ".join(m["name"] for m in g["members"]), "member_preview": make_group_member_preview(conn, g, year, month)})
            rows[key] = make_group_month_summary(conn, g, year, month)
            group_items: List[Dict[str, Any]] = []
            group_month = get_group_month_override(conn, gid, year, month)
            if group_month:
                for it in get_group_adjustment_items(conn, int(group_month["id"])):
                    gi = dict(it)
                    gi["is_group_adj"] = 1
                    group_items.append(gi)
                    for gf in conn.execute("SELECT * FROM driver_group_adjustment_files WHERE group_adjustment_item_id=? ORDER BY id", (int(it["id"]),)).fetchall():
                        group_adjustment_files.setdefault(int(it["id"]), []).append(gf)
            for member in g["members"]:
                for it in adjustments.get(int(member["id"]), []):
                    gi = dict(it)
                    gi["note"] = f"{member['name']}: {it['note']}"
                    gi["is_group_adj"] = 0
                    group_items.append(gi)
            adjustments[key] = group_items
        drivers = display_drivers
        month_released = is_month_released(conn, year, month)
        global_v_all = month_all_drivers_v_enabled(conn, year, month)

    body = render_template_string("""
    <div class="card">
      <div class="actions" style="justify-content:space-between;align-items:flex-end">
        <form method="get" class="actions" id="month-filter-form">
          <div><label>Jahr</label><input name="year" value="{{ year }}" onchange="this.form.submit()"></div>
          <div><label>Monat</label><select name="month" onchange="this.form.submit()">{% for n,m in months.items() %}<option value="{{ n }}" {% if n==month %}selected{% endif %}>{{ m }}</option>{% endfor %}</select></div>
          <noscript><button class="primary">Anzeigen</button></noscript>
          <a class="btn" href="{{ url_for('download_month_export', year=year, month=month) }}">Monats-PDF herunterladen</a>
          <button class="primary" type="submit" form="all-months-form" {% if not editable %}disabled title="{{ locked_note }}"{% endif %}>Alle Einträge speichern</button>
          <div class="download-note">Der PDF-Button lädt die Datei direkt herunter.</div>
          {% if not editable %}<div class="month-locked-note">{{ locked_note }}</div>{% endif %}
        </form>
        <form method="post" class="actions" style="margin-left:auto;align-items:center">
          <input type="hidden" name="action" value="toggle_month_release">
          <input type="hidden" name="year" value="{{ year }}">
          <input type="hidden" name="month" value="{{ month }}">
          <input type="hidden" name="release" value="{{ 0 if month_released else 1 }}">
          <span class="badge">{{ 'Für Fahrer freigegeben' if month_released else 'Für Fahrer gesperrt' }}</span>
          <button class="small {{ 'danger' if month_released else 'primary' }}" onclick="return confirm('{{ 'Monat für Fahrer wieder sperren?' if month_released else 'Monat jetzt für Fahrer freigeben?' }}')">{{ 'Monat für Fahrer sperren' if month_released else 'Monat für Fahrer freigeben' }}</button>
        </form>
      </div>
    </div>
    <div class="card"><h2>{{ months[month] }} {{ year }}</h2><form method="post" id="all-months-form"><input type="hidden" name="action" value="save_all"></form><form method="post" id="global-v-form-months"><input type="hidden" name="action" value="set_global_v"><input type="hidden" name="year" value="{{ year }}"><input type="hidden" name="month" value="{{ month }}"><input type="hidden" id="global-v-value-months" name="global_v_enabled" value="{{ 1 if global_v_all else 0 }}"></form><div class="table-wrap mobile-cards"><table class="months-table">
      <thead><tr><th class="col-admin">Allgemeine Infos<br><span class="muted">nur Admin</span></th><th class="col-driver">Fahrer</th><th class="col-hours">geleistete Stunden</th><th class="col-payroll">Abrechnung</th><th class="col-v">V<br><label class="global-v-toggle" title="Aktiv-Markierung für alle Fahrer"><input type="checkbox" {% if global_v_all %}checked{% endif %} {% if not editable %}disabled{% endif %} onchange="document.getElementById('global-v-value-months').value=this.checked?'1':'0';document.getElementById('global-v-form-months').submit()"> alle aktiv</label></th><th class="col-adjust">Zuschüsse / Abzüge</th><th class="col-small">Diff</th><th class="col-small">Alt</th><th class="col-small">Neu</th><th class="col-action">Aktion</th></tr></thead><tbody>
      {% for d in drivers %}
      {% set r = rows.get(d['id']) %}
      {% set items = adjustments.get(d['id'], []) %}
      <tr class="driver-row {{ 'row-alt' if loop.index0 % 2 else 'row-base' }}">
        {% if d['is_group'] %}
        <td class="admin-info" data-label="Allgemeine Infos"><textarea form="save-{{ d['form_id'] }}" name="admin_info" placeholder="Interne Infos, nur für Admin sichtbar">{{ r['admin_info'] if r else '' }}</textarea><input type="hidden" form="all-months-form" name="row_driver_id_{{ d['form_id'] }}" value="{{ d['id'] }}"><input type="hidden" form="all-months-form" name="admin_info_{{ d['form_id'] }}" value="{{ r['admin_info'] if r else '' }}" class="all-copy-admin-{{ d['form_id'] }}"><div class="download-note">Gruppe: {{ d['member_names'] }}</div></td>
        <td class="nowrap" data-label="Fahrer"><div class="mobile-row-title {{ employment_class(row_get(d, 'employment_type', '')) }}">{{ d['name'] }}</div><b class="driver-name {{ employment_class(row_get(d, 'employment_type', '')) }}">{{ d['name'] }}</b><div class="download-note">zusammengeführt nur in Plus/Minus Stunden</div>{% if d.member_preview %}<div class="group-member-preview"><b>Einzelvorschau</b><table><tr><th>Fahrer</th><th>Std.</th><th>Abr.</th><th>V</th><th>Diff</th></tr>{% for p in d.member_preview %}<tr><td class="driver-name {{ employment_class(p.employment_type) }}">{{ p.name }}</td><td>{{ fmt_hours(p.worked_hours) }}</td><td>{{ fmt_hours(p.payroll_hours) }}</td><td>{{ p.v_note or '-' }}</td><td class="{{ signed_class(p.difference_hours) }}">{{ fmt_signed(p.difference_hours) }}</td></tr>{% endfor %}</table></div>{% endif %}</td>
        <td data-label="geleistete Stunden"><form method="post" enctype="multipart/form-data" id="save-{{ d['form_id'] }}"><input type="hidden" name="driver_id" value="{{ d['id'] }}"><input name="worked_hours" value="{{ r['worked_hours'] if r else '' }}"><div class="group-worked-note">Nur Gruppenwert für Plus/Minus Stunden.</div></form></td>
        <td data-label="Abrechnung"><input readonly value="{{ r['payroll_hours'] if r else '' }}"></td>
        {% set v_enabled = row_v_enabled(r) %}
        <td data-label="V"><input class="v-markable {{ 'v-disabled' if not v_enabled else '' }}" readonly value="{{ fmt_v_input(row_get(r, 'v_note', '')) if r else '' }}" placeholder="Notiz"><input type="hidden" form="save-{{ d['form_id'] }}" name="v_enabled" value="0"><label class="v-toggle" title="Nur Aktiv-Markierung; V wird nie berechnet"><input class="v-enabled-toggle" form="save-{{ d['form_id'] }}" type="checkbox" name="v_enabled" value="1" {% if v_enabled %}checked{% endif %}> aktiv</label><input type="hidden" form="all-months-form" name="v_enabled_{{ d['form_id'] }}" value="{{ 1 if v_enabled else 0 }}" class="all-copy-v-enabled-{{ d['form_id'] }}"><div class="v-disabled-note">nur Notiz · ohne Berechnung</div></td>
        <td data-label="Zuschüsse / Abzüge"><div class="group-mini-form"><select form="save-{{ d['form_id'] }}" name="kind"><option value="deduction">Abzug</option><option value="bonus">Zuschuss</option></select><input form="save-{{ d['form_id'] }}" name="item_hours" placeholder="Std."><input form="save-{{ d['form_id'] }}" name="item_note" placeholder="Grund, z.B. Auto dreckig"><label class="dropzone">Bild/Datei<input form="save-{{ d['form_id'] }}" type="file" name="item_file" accept="image/*,.pdf"></label><button form="save-{{ d['form_id'] }}" name="action" value="add_adjustment" class="small primary">Hinzufügen</button></div>
          {% if r %}<div class="sum-box">Summe Zuschüsse: <span class="pos">{{ fmt_hours(r['bonus_hours']) }}</span><br>Summe Abzüge: <span class="neg">{{ fmt_hours(r['deduction_hours']) }}</span></div>{% endif %}
          <div class="adjustment-list">{% if items %}{% for it in items %}<div class="item-row"><span class="{{ 'pos' if it['kind']=='bonus' else 'neg' }}">{{ '+' if it['kind']=='bonus' else '-' }}{{ fmt_hours(it['hours']) }}</span><span>{{ it['note'] }}</span>{% if it.get('is_group_adj') %}{% for f in group_adjustment_files.get(it['id'], []) %}<span class="file-pill">📎 {{ f['original_filename'] or f['filename'] }}<form method="post"><input type="hidden" name="action" value="delete_adjustment_file"><input type="hidden" name="driver_id" value="{{ d['id'] }}"><input type="hidden" name="file_id" value="{{ f['id'] }}"><button class="file-remove danger" onclick="return confirm('Bild/Datei entfernen?')">entfernen</button></form></span>{% endfor %}<form method="post"><input type="hidden" name="action" value="delete_adjustment"><input type="hidden" name="driver_id" value="{{ d['id'] }}"><input type="hidden" name="item_id" value="{{ it['id'] }}"><button class="small danger" onclick="return confirm('Position löschen?')">x</button></form>{% endif %}</div>{% endfor %}{% else %}<div class="muted">Keine Positionen</div>{% endif %}</div>
        </td>
        <td data-label="Diff" class="{{ signed_class(r['difference_hours']) if r else '' }} nowrap">{{ fmt_signed(r['difference_hours']) if r else '-' }}</td>
        <td data-label="Alt" class="nowrap">{{ fmt_signed(r['previous_balance']) if r else '-' }}</td>
        <td data-label="Neu" class="{{ signed_class(r['new_balance']) if r else '' }} nowrap">{{ fmt_signed(r['new_balance']) if r else '-' }}</td>
        <td data-label="Aktion" class="actions compact-save"><button form="save-{{ d['form_id'] }}" name="action" value="save" class="small primary">Speichern</button><span class="badge">Gruppe</span></td>
        {% else %}
        <td class="admin-info" data-label="Allgemeine Infos"><textarea class="{{ 'carried' if r and r['admin_info_carried'] else '' }}" form="save-{{ d['form_id'] }}" name="admin_info" placeholder="Interne Infos, nur für Admin sichtbar">{{ r['admin_info'] if r else '' }}</textarea><input type="hidden" form="all-months-form" name="row_driver_id_{{ d['form_id'] }}" value="{{ d['id'] }}"><input type="hidden" form="all-months-form" name="admin_info_{{ d['form_id'] }}" value="{{ r['admin_info'] if r else '' }}" class="all-copy-admin-{{ d['form_id'] }}">{% if r and r['admin_info_carried'] %}<div class="download-note">aus Vormonat übernommen</div>{% endif %}</td>
        <td class="nowrap" data-label="Fahrer"><div class="mobile-row-title {{ employment_class(row_get(d, 'employment_type', '')) }}">{{ d['name'] }}</div><b class="driver-name {{ employment_class(row_get(d, 'employment_type', '')) }}">{{ d['name'] }}</b></td>
        <td data-label="geleistete Stunden"><form method="post" enctype="multipart/form-data" id="save-{{ d['form_id'] }}"><input type="hidden" name="driver_id" value="{{ d['id'] }}"><input name="worked_hours" value="{{ r['worked_hours'] if r else '' }}"></form></td>
        <td data-label="Abrechnung"><input form="save-{{ d['form_id'] }}" name="payroll_hours" value="{{ r['payroll_hours'] if r else '' }}"><input type="hidden" form="all-months-form" name="payroll_hours_{{ d['form_id'] }}" value="{{ r['payroll_hours'] if r else '' }}" class="all-copy-payroll-{{ d['form_id'] }}"></td>
        {% set v_enabled = row_v_enabled(r) %}
        <td data-label="V"><input class="v-input v-markable {{ 'v-disabled' if not v_enabled else '' }}" form="save-{{ d['form_id'] }}" name="v_note" value="{{ fmt_v_input(row_get(r, 'v_note', '')) if r else '' }}" placeholder="Notiz"><input type="hidden" form="all-months-form" name="v_note_{{ d['form_id'] }}" value="{{ fmt_v_input(row_get(r, 'v_note', '')) if r else '' }}" class="all-copy-v-{{ d['form_id'] }}"><input type="hidden" form="save-{{ d['form_id'] }}" name="v_enabled" value="0"><label class="v-toggle" title="Nur Aktiv-Markierung; V wird nie berechnet"><input class="v-enabled-toggle" form="save-{{ d['form_id'] }}" type="checkbox" name="v_enabled" value="1" {% if v_enabled %}checked{% endif %}> aktiv</label><input type="hidden" form="all-months-form" name="v_enabled_{{ d['form_id'] }}" value="{{ 1 if v_enabled else 0 }}" class="all-copy-v-enabled-{{ d['form_id'] }}"><div class="v-disabled-note">nur Notiz · ohne Berechnung</div></td>
        <td data-label="Zuschüsse / Abzüge"><div class="mini-form"><select form="save-{{ d['form_id'] }}" name="kind"><option value="deduction">Abzug</option><option value="bonus">Zuschuss</option></select><input form="save-{{ d['form_id'] }}" name="item_hours" placeholder="Std."><input form="save-{{ d['form_id'] }}" name="item_note" placeholder="Grund, z.B. Auto dreckig"><label class="dropzone">Bild/Datei<input form="save-{{ d['form_id'] }}" type="file" name="item_file" accept="image/*,.pdf"></label><button form="save-{{ d['form_id'] }}" name="action" value="add_adjustment" class="small primary">Hinzufügen</button></div>
          {% if r %}<div class="sum-box">Summe Zuschüsse: <span class="pos">{{ fmt_hours(r['bonus_hours']) }}</span><br>Summe Abzüge: <span class="neg">{{ fmt_hours(r['deduction_hours']) }}</span></div>{% endif %}
          <div class="adjustment-list">{% if items %}{% for it in items %}<div class="item-row"><span class="{{ 'pos' if it['kind']=='bonus' else 'neg' }}">{{ '+' if it['kind']=='bonus' else '-' }}{{ fmt_hours(it['hours']) }}</span><span>{{ it['note'] }}</span>{% for f in adjustment_files.get(it['id'], []) %}<span class="file-pill">📎 {{ f['original_filename'] or f['filename'] }}<form method="post"><input type="hidden" name="action" value="delete_adjustment_file"><input type="hidden" name="driver_id" value="{{ d['id'] }}"><input type="hidden" name="file_id" value="{{ f['id'] }}"><button class="file-remove danger" onclick="return confirm('Bild/Datei entfernen?')">entfernen</button></form></span>{% endfor %}<form method="post"><input type="hidden" name="action" value="delete_adjustment"><input type="hidden" name="driver_id" value="{{ d['id'] }}"><input type="hidden" name="item_id" value="{{ it['id'] }}"><button class="small danger" onclick="return confirm('Position löschen?')">x</button></form></div>{% endfor %}{% else %}<div class="muted">Keine Positionen</div>{% endif %}</div>
        </td>
        <td data-label="Diff" class="{{ signed_class(r['difference_hours']) if r else '' }} nowrap">{{ fmt_signed(r['difference_hours']) if r else '-' }}</td>
        <td data-label="Alt" class="nowrap">{{ fmt_signed(r['previous_balance']) if r else '-' }}</td>
        <td data-label="Neu" class="{{ signed_class(r['new_balance']) if r else '' }} nowrap">{{ fmt_signed(r['new_balance']) if r else '-' }}</td>
        <td data-label="Aktion" class="actions compact-save"><button form="save-{{ d['form_id'] }}" name="action" value="save" class="small primary">Speichern</button>{% if r %}<form method="post" onsubmit="return confirm('Datensatz löschen?')"><input type="hidden" name="action" value="delete"><input type="hidden" name="driver_id" value="{{ d['id'] }}"><button class="small danger delete-month-btn">Monat löschen</button></form>{% endif %}</td>
        {% endif %}
      </tr>
      {% endfor %}
    </tbody></table></div></div>
    <script>
    {% if not editable %}
    document.querySelectorAll('.months-table input, .months-table textarea, .months-table select, .months-table button, button[form="all-months-form"]').forEach(function(el){
      if(el.type !== 'hidden'){ el.disabled = true; el.title = '{{ locked_note }}'; }
    });
    {% endif %}
    document.querySelectorAll('.dropzone input[type="file"]').forEach(function(input){
      var zone = input.closest('.dropzone');
      var defaultText = 'Bild/Datei hier ablegen';
      function setZoneText(text){
        Array.from(zone.childNodes).forEach(function(node){
          if(node.nodeType === Node.TEXT_NODE){ node.nodeValue = text; }
        });
      }
      setZoneText(defaultText);
      input.addEventListener('change', function(){
        setZoneText(input.files.length ? input.files[0].name : defaultText);
      });
      ['dragenter','dragover'].forEach(function(ev){
        zone.addEventListener(ev, function(e){
          e.preventDefault();
          e.stopPropagation();
          zone.classList.add('dragover');
          if(e.dataTransfer){ e.dataTransfer.dropEffect = 'copy'; }
        });
      });
      ['dragleave','dragend'].forEach(function(ev){
        zone.addEventListener(ev, function(e){
          e.preventDefault();
          e.stopPropagation();
          zone.classList.remove('dragover');
        });
      });
      zone.addEventListener('drop', function(e){
        e.preventDefault();
        e.stopPropagation();
        zone.classList.remove('dragover');
        if(e.dataTransfer && e.dataTransfer.files && e.dataTransfer.files.length){
          input.files = e.dataTransfer.files;
          setZoneText(e.dataTransfer.files[0].name);
        }
      });
    });
    function refreshVEnabledState(row){
      var cb = row.querySelector('.v-enabled-toggle');
      if(!cb){ return; }
      var input = row.querySelector('.v-markable');
      if(input){ input.classList.toggle('v-disabled', !cb.checked); }
    }
    document.querySelectorAll('.v-enabled-toggle').forEach(function(cb){
      var row = cb.closest('tr');
      cb.addEventListener('change', function(){ refreshVEnabledState(row); });
      refreshVEnabledState(row);
    });

    document.querySelectorAll('tr.driver-row').forEach(function(row){
      var fidInput = row.querySelector('form[id^="save-"] input[name="driver_id"]');
      if(!fidInput) return;
      var formId = fidInput.closest('form').id.replace('save-', '');
      function sync(){
        var admin = row.querySelector('textarea[name="admin_info"]');
        var worked = row.querySelector('input[name="worked_hours"]');
        var payroll = row.querySelector('input[name="payroll_hours"]');
        var v = row.querySelector('input[name="v_note"]');
        var vEnabled = row.querySelector('.v-enabled-toggle');
        var ha = document.querySelector('.all-copy-admin-' + CSS.escape(formId)); if(ha && admin) ha.value = admin.value;
        var hw = document.querySelector('.all-copy-worked-' + CSS.escape(formId)); if(hw && worked) hw.value = worked.value;
        var hp = document.querySelector('.all-copy-payroll-' + CSS.escape(formId)); if(hp && payroll) hp.value = payroll.value;
        var hv = document.querySelector('.all-copy-v-' + CSS.escape(formId)); if(hv && v) hv.value = v.value;
        var hve = document.querySelector('.all-copy-v-enabled-' + CSS.escape(formId)); if(hve && vEnabled) hve.value = vEnabled.checked ? '1' : '0';
      }
      row.addEventListener('input', sync);
      row.addEventListener('change', sync);
      sync();
    });
    </script>
    """, year=year, month=month, months=MONATE, month_released=month_released, editable=editable, locked_note=locked_note, drivers=drivers, rows=rows, adjustments=adjustments, adjustment_files=adjustment_files, group_adjustment_files=locals().get("group_adjustment_files", {}), fmt_signed=fmt_signed, fmt_hours=fmt_hours, fmt_v_input=fmt_v_input, fmt_decimal_input=fmt_decimal_input, signed_class=signed_class, row_v_enabled=row_v_enabled, row_get=row_get, employment_class=employment_class, global_v_all=global_v_all)
    return base_page("Plus/Minus Stunden", body, "months")


@app.route("/admin/import-pdf", methods=["GET","POST"])
@admin_login_required
def admin_import_pdf():
    flash("Der Lohn-PDF-Import wurde deaktiviert. Bitte V direkt in der Monatsübersicht eintragen.", "ok")
    return redirect(url_for("admin_months"))



@app.route("/admin/payroll-hours", methods=["GET","POST"])
@admin_login_required
def admin_payroll_hours():
    year = int(request.values.get("year") or datetime.now().year)
    month = int(request.values.get("month") or datetime.now().month)
    editable = month_is_editable(year, month)
    locked_note = month_locked_message(year, month)
    with db_conn() as conn:
        if request.method == "POST":
            action = request.form.get("action", "save")
            if not editable:
                flash(locked_note, "err")
                return redirect(url_for("admin_payroll_hours", year=year, month=month))
            if action == "set_global_v":
                enabled = request.form.get("global_v_enabled") == "1"
                set_global_v_enabled(conn, year, month, enabled)
                recalc_all(conn)
                audit(conn, "global_v_toggle", f"{year}-{month} {int(enabled)}")
                conn.commit()
                flash("V wurde bei allen Fahrern aktiviert." if enabled else "V wurde bei allen Fahrern deaktiviert.", "ok")
                return redirect(url_for("admin_payroll_hours", year=year, month=month))
            if action == "save_all":
                saved_count = 0
                for key in request.form:
                    if not key.startswith("row_driver_id_"):
                        continue
                    suffix = key.replace("row_driver_id_", "", 1)
                    did = int(request.form.get(key))
                    monthly_id = get_or_create_month_row(conn, did, year, month)
                    worked = parse_hours(request.form.get(f"worked_hours_{suffix}", "0"))
                    payroll = parse_hours(request.form.get(f"payroll_hours_{suffix}", "0"))
                    v_note = request.form.get(f"v_note_{suffix}", "").strip()
                    v_enabled = form_v_enabled(f"v_enabled_{suffix}")
                    admin_info = request.form.get(f"admin_info_{suffix}", "").strip()
                    payroll_office_info = request.form.get(f"payroll_office_info_{suffix}", "").strip()
                    payroll_surcharge = parse_decimal(request.form.get(f"payroll_surcharge_{suffix}", "0"))
                    fuel_voucher = parse_decimal(request.form.get(f"fuel_voucher_{suffix}", "0"))
                    vacation_days = normalize_vacation_count(request.form.get(f"vacation_days_{suffix}", ""))
                    sick_days = normalize_day_ranges(request.form.get(f"sick_days_{suffix}", ""))
                    conn.execute("""
                        UPDATE monthly_data
                        SET worked_hours=?, payroll_hours=?, v_hours=0, v_note=?, v_enabled=?, admin_info=?, admin_info_carried=0,
                            payroll_office_info=?, payroll_surcharge=?, fuel_voucher=?, payroll_carry_initialized=1,
                            vacation_days=?, sick_days=?, updated_at=?
                        WHERE id=?
                    """, (worked, payroll, v_note, v_enabled, admin_info, payroll_office_info, payroll_surcharge, fuel_voucher, vacation_days, sick_days, now_iso(), monthly_id))
                    sync_member_admin_info_to_group(conn, did, year, month, admin_info)
                    recalc_month_adjustments(conn, monthly_id)
                    recalc_driver(conn, did)
                    create_driver_pdf(conn, did, year, month)
                    saved_count += 1
                audit(conn, "payroll_hours_save_all", f"{year}-{month} {saved_count}")
                conn.commit()
                flash(f"Alle Einträge gespeichert ({saved_count}).", "ok")
                return redirect(url_for("admin_payroll_hours", year=year, month=month))
            if action == "save":
                did = int(request.form["driver_id"])
                monthly_id = get_or_create_month_row(conn, did, year, month)
                worked = parse_hours(request.form.get("worked_hours", "0"))
                payroll = parse_hours(request.form.get("payroll_hours", "0"))
                v_note = request.form.get("v_note", "").strip()
                v_enabled = form_v_enabled("v_enabled")
                admin_info = request.form.get("admin_info", "").strip()
                payroll_office_info = request.form.get("payroll_office_info", "").strip()
                payroll_surcharge = parse_decimal(request.form.get("payroll_surcharge", "0"))
                fuel_voucher = parse_decimal(request.form.get("fuel_voucher", "0"))
                vacation_days = normalize_vacation_count(request.form.get("vacation_days", ""))
                sick_days = normalize_day_ranges(request.form.get("sick_days", ""))
                conn.execute("""
                    UPDATE monthly_data
                    SET worked_hours=?, payroll_hours=?, v_hours=0, v_note=?, v_enabled=?, admin_info=?, admin_info_carried=0,
                        payroll_office_info=?, payroll_surcharge=?, fuel_voucher=?, payroll_carry_initialized=1,
                        vacation_days=?, sick_days=?, updated_at=?
                    WHERE id=?
                """, (worked, payroll, v_note, v_enabled, admin_info, payroll_office_info, payroll_surcharge, fuel_voucher, vacation_days, sick_days, now_iso(), monthly_id))
                sync_member_admin_info_to_group(conn, did, year, month, admin_info)
                recalc_month_adjustments(conn, monthly_id)
                recalc_driver(conn, did)
                create_driver_pdf(conn, did, year, month)
                audit(conn, "payroll_hours_save", f"{did} {year}-{month}")
                conn.commit()
                flash("Stunden für Lohnabrechnung gespeichert und in Plus/Minus Stunden übernommen.", "ok")

        recalc_all(conn); conn.commit()
        drivers = conn.execute("SELECT * FROM drivers WHERE is_active=1 AND COALESCE(is_disposition,0)=0 ORDER BY COALESCE(NULLIF(display_order,0), id), name COLLATE NOCASE").fetchall()
        if editable:
            for d in drivers:
                get_or_create_month_row(conn, int(d["id"]), year, month, carry_admin_info=True)
            conn.commit()
        rows = {int(r["driver_id"]): r for r in conn.execute("SELECT * FROM monthly_data WHERE year=? AND month=?", (year, month)).fetchall()}
        global_v_all = month_all_drivers_v_enabled(conn, year, month)

    body = render_template_string("""
    <div class="card">
      <form method="get" class="actions" id="payroll-filter-form">
        <div><label>Jahr</label><input name="year" value="{{ year }}" onchange="this.form.submit()"></div>
        <div><label>Monat</label><select name="month" onchange="this.form.submit()">{% for n,m in months.items() %}<option value="{{ n }}" {% if n==month %}selected{% endif %}>{{ m }}</option>{% endfor %}</select></div>
        <noscript><button class="primary">Anzeigen</button></noscript>
        <a class="btn" href="{{ url_for('download_payroll_hours_export', year=year, month=month) }}">Lohnbüro-PDF herunterladen</a>
        <button class="primary" type="submit" form="all-payroll-form" {% if not editable %}disabled title="{{ locked_note }}"{% endif %}>Alle Einträge speichern</button>
        <div class="download-note">Interne Admin-Infos werden in dieser PDF nicht angezeigt. „Allgemeine Infos für Lohnbüro“ werden ganz links angezeigt.</div>
        {% if not editable %}<div class="month-locked-note">{{ locked_note }}</div>{% endif %}
      </form>
    </div>
    <div class="card"><h2>Stunden für Lohnabrechnung – {{ months[month] }} {{ year }}</h2>
      <p class="muted">Bei Urlaub trägst du nur die Anzahl der Tage ein. Kranktage wählst du bequem im Kalender aus.</p>
      <form method="post" id="global-v-form-payroll"><input type="hidden" name="action" value="set_global_v"><input type="hidden" name="year" value="{{ year }}"><input type="hidden" name="month" value="{{ month }}"><input type="hidden" id="global-v-value-payroll" name="global_v_enabled" value="{{ 1 if global_v_all else 0 }}"></form>
      <form method="post" id="all-payroll-form"><input type="hidden" name="action" value="save_all"><input type="hidden" name="year" value="{{ year }}"><input type="hidden" name="month" value="{{ month }}"></form>
      <div class="table-wrap mobile-cards"><table class="months-table payroll-table">
      <thead><tr><th class="col-admin">Allgemeine Infos<br><span class="muted">nur Admin</span></th><th class="col-pay-info">Allgemeine Infos für Lohnbüro</th><th class="col-driver">Fahrer</th><th class="col-hours">geleistete Stunden</th><th class="col-payroll">Abrechnung</th><th class="col-v">V<br><label class="global-v-toggle" title="Aktiv-Markierung für alle Fahrer"><input type="checkbox" {% if global_v_all %}checked{% endif %} {% if not editable %}disabled{% endif %} onchange="document.getElementById('global-v-value-payroll').value=this.checked?'1':'0';document.getElementById('global-v-form-payroll').submit()"> alle aktiv</label></th><th class="col-pay-num">Zuschlag</th><th class="col-pay-num">Tankgutschein</th><th class="col-days">Urlaub</th><th class="col-days">Krank</th><th class="col-action">Aktion</th></tr></thead><tbody>
      {% for d in drivers %}
      {% set r = rows.get(d['id']) %}
      <tr class="driver-row {{ 'row-alt' if loop.index0 % 2 else 'row-base' }}">
        <td class="admin-info" data-label="Allgemeine Infos"><textarea form="payroll-{{ d['id'] }}" name="admin_info" placeholder="Interne Infos, nur für Admin sichtbar">{{ r['admin_info'] if r else '' }}</textarea></td>
        <td data-label="Allgemeine Infos für Lohnbüro"><textarea form="payroll-{{ d['id'] }}" name="payroll_office_info" placeholder="Text für Lohnbüro-PDF">{{ row_get(r, 'payroll_office_info', '') if r else '' }}</textarea></td>
        <td class="nowrap" data-label="Fahrer"><b class="driver-name {{ employment_class(row_get(d, 'employment_type', '')) }}">{{ d['name'] }}</b>{% if r %}<span class="driver-balance-mini {{ signed_class(row_get(r, 'new_balance', 0)) }}">Stand: {{ fmt_signed(row_get(r, 'new_balance', 0)) }}</span>{% endif %}</td>
        <td data-label="geleistete Stunden"><form method="post" id="payroll-{{ d['id'] }}"><input type="hidden" name="action" value="save"><input type="hidden" name="driver_id" value="{{ d['id'] }}"><input type="hidden" name="year" value="{{ year }}"><input type="hidden" name="month" value="{{ month }}"><input name="worked_hours" value="{{ r['worked_hours'] if r else '' }}"></form></td>
        <td data-label="Abrechnung"><input form="payroll-{{ d['id'] }}" name="payroll_hours" value="{{ r['payroll_hours'] if r else '' }}"></td>
        {% set v_enabled = row_v_enabled(r) %}
        <td data-label="V"><input class="v-input v-markable {{ 'v-disabled' if not v_enabled else '' }}" form="payroll-{{ d['id'] }}" name="v_note" value="{{ fmt_v_input(row_get(r, 'v_note', '')) if r else '' }}" placeholder="Notiz"><input type="hidden" form="payroll-{{ d['id'] }}" name="v_enabled" value="0"><label class="v-toggle" title="Nur Aktiv-Markierung; V wird nie berechnet"><input class="v-enabled-toggle" form="payroll-{{ d['id'] }}" type="checkbox" name="v_enabled" value="1" {% if v_enabled %}checked{% endif %}> aktiv</label><div class="v-disabled-note">nur Notiz · ohne Berechnung</div></td>
        <td data-label="Zuschlag"><input form="payroll-{{ d['id'] }}" name="payroll_surcharge" value="{{ fmt_decimal_input(row_get(r, 'payroll_surcharge', 0)) if r else '' }}"></td>
        <td data-label="Tankgutschein"><input form="payroll-{{ d['id'] }}" name="fuel_voucher" value="{{ fmt_decimal_input(row_get(r, 'fuel_voucher', 0)) if r else '' }}"></td>
        <td data-label="Urlaub" class="days-vacation"><div class="vacation-input-wrap"><input form="payroll-{{ d['id'] }}" name="vacation_days" inputmode="numeric" pattern="[0-9]*" value="{{ vacation_display(row_get(r, 'vacation_days', '')) if r else '' }}"><span class="suffix">Tage</span></div></td>
        <td data-label="Krank" class="days-sick"><input type="hidden" class="sick-days-input" form="payroll-{{ d['id'] }}" name="sick_days" value="{{ row_get(r, 'sick_days', '') if r else '' }}"><button type="button" class="sick-calendar-open" data-form="payroll-{{ d['id'] }}" data-driver-name="{{ d['name'] }}">Kalender öffnen</button><div class="sick-days-overview">{{ row_get(r, 'sick_days', '') if r and row_get(r, 'sick_days', '') else 'Keine Kranktage' }}</div></td>
        <td data-label="Aktion" class="actions compact-save"><button form="payroll-{{ d['id'] }}" class="small primary">Speichern</button></td>
      </tr>
      {% endfor %}
      </tbody></table></div></div>
    <div id="sick-calendar-modal" class="sick-calendar-modal" aria-hidden="true"><div class="sick-calendar-panel"><div class="sick-calendar-head"><div><h3 style="margin:0">Kranktage auswählen</h3><div class="muted" id="sick-calendar-title"></div></div><button type="button" class="small" id="sick-calendar-close" style="width:auto">Schließen</button></div><div class="sick-calendar-week"><div>Mo</div><div>Di</div><div>Mi</div><div>Do</div><div>Fr</div><div>Sa</div><div>So</div></div><div id="sick-calendar-grid" class="sick-calendar-grid"></div><div class="sick-calendar-hint">Einzelne Tage anklicken oder mit gedrückter Maustaste / Finger über mehrere Tage ziehen. Erneutes Markieren entfernt Tage.</div><div class="actions" style="justify-content:flex-end"><button type="button" class="small" id="sick-calendar-cancel">Abbrechen</button><button type="button" class="small primary" id="sick-calendar-save">Speichern</button></div></div></div>
    <script>
    {% if not editable %}
    document.querySelectorAll('.payroll-table input, .payroll-table textarea, .payroll-table select, .payroll-table button, button[form="all-payroll-form"]').forEach(function(el){
      if(el.type !== 'hidden'){ el.disabled = true; el.title = '{{ locked_note }}'; }
    });
    {% endif %}
    function refreshVEnabledState(row){var cb=row.querySelector('.v-enabled-toggle'); if(!cb){return;} var input=row.querySelector('.v-markable'); if(input){input.classList.toggle('v-disabled', !cb.checked);}}
    document.querySelectorAll('.v-enabled-toggle').forEach(function(cb){var row=cb.closest('tr'); cb.addEventListener('change', function(){refreshVEnabledState(row);}); refreshVEnabledState(row);});

    (function(){
      var modal=document.getElementById('sick-calendar-modal'), grid=document.getElementById('sick-calendar-grid'), title=document.getElementById('sick-calendar-title');
      if(!modal||!grid) return;
      var activeInput=null, activeForm=null, selected=new Set(), dragging=false, dragState=true;
      var year={{ year }}, month={{ month }};
      function parseRanges(raw){ var out=new Set(); (raw||'').split(',').map(function(x){return x.trim();}).filter(Boolean).forEach(function(part){ var bits=part.split('-').map(function(x){return parseInt(x.trim(),10);}); if(bits.length===2&&Number.isFinite(bits[0])&&Number.isFinite(bits[1])){ for(var d=bits[0];d<=bits[1];d++) out.add(d); } else if(Number.isFinite(bits[0])) out.add(bits[0]); }); return out; }
      function formatRanges(set){ var a=Array.from(set).sort(function(x,y){return x-y;}); if(!a.length) return ''; var parts=[], start=a[0], prev=a[0]; for(var i=1;i<=a.length;i++){ var cur=a[i]; if(cur===prev+1){ prev=cur; continue; } parts.push(start===prev?String(start):(start+'-'+prev)); start=cur; prev=cur; } return parts.join(', '); }
      function paint(btn, day, state){ if(state) selected.add(day); else selected.delete(day); btn.classList.toggle('selected', state); }
      function build(){ grid.innerHTML=''; var first=new Date(year,month-1,1), days=new Date(year,month,0).getDate(), blanks=(first.getDay()+6)%7; for(var b=0;b<blanks;b++){ var blank=document.createElement('button'); blank.type='button'; blank.className='sick-day blank'; blank.tabIndex=-1; grid.appendChild(blank); } for(let day=1;day<=days;day++){ let btn=document.createElement('button'); btn.type='button'; btn.className='sick-day'+(selected.has(day)?' selected':''); btn.textContent=day; btn.addEventListener('pointerdown',function(e){ dragging=true; dragState=!selected.has(day); paint(btn,day,dragState); e.preventDefault(); }); btn.addEventListener('pointerenter',function(e){ if(dragging){ paint(btn,day,dragState); e.preventDefault(); } }); btn.addEventListener('click',function(e){ e.preventDefault(); }); grid.appendChild(btn); } }
      function close(){ modal.classList.remove('open'); modal.setAttribute('aria-hidden','true'); dragging=false; }
      document.addEventListener('pointerup',function(){ dragging=false; });
      document.querySelectorAll('.sick-calendar-open').forEach(function(open){ open.addEventListener('click',function(){ activeForm=document.getElementById(open.dataset.form); activeInput=document.querySelector('input.sick-days-input[form="'+open.dataset.form+'"]'); selected=parseRanges(activeInput?activeInput.value:''); title.textContent=(open.dataset.driverName||'')+' · {{ months[month] }} {{ year }}'; build(); modal.classList.add('open'); modal.setAttribute('aria-hidden','false'); }); });
      document.getElementById('sick-calendar-close').addEventListener('click',close); document.getElementById('sick-calendar-cancel').addEventListener('click',close);
      modal.addEventListener('click',function(e){ if(e.target===modal) close(); });
      document.getElementById('sick-calendar-save').addEventListener('click',function(){ if(!activeInput||!activeForm) return close(); activeInput.value=formatRanges(selected); close(); activeForm.requestSubmit(); });
    })();

    var allPayrollForm = document.getElementById('all-payroll-form');
    if(allPayrollForm){
      allPayrollForm.addEventListener('submit', function(){
        allPayrollForm.querySelectorAll('input[data-dynamic="1"]').forEach(function(x){x.remove();});
        document.querySelectorAll('form[id^="payroll-"]').forEach(function(f){
          var id = f.id.replace('payroll-', '');
          var row = f.closest('tr');
          if(!row) return;
          function add(name, value){ var inp=document.createElement('input'); inp.type='hidden'; inp.name=name; inp.value=value || ''; inp.dataset.dynamic='1'; allPayrollForm.appendChild(inp); }
          add('row_driver_id_' + id, id);
          ['admin_info','payroll_office_info','worked_hours','payroll_hours','v_note','payroll_surcharge','fuel_voucher','vacation_days','sick_days'].forEach(function(name){
            var el = row.querySelector('[name="' + name + '"]');
            add(name + '_' + id, el ? el.value : '');
          });
          var vEnabled = row.querySelector('.v-enabled-toggle');
          add('v_enabled_' + id, vEnabled && vEnabled.checked ? '1' : '0');
        });
      });
    }
    </script>
    """, year=year, month=month, months=MONATE, editable=editable, locked_note=locked_note, drivers=drivers, rows=rows, fmt_hours=fmt_hours, fmt_signed=fmt_signed, fmt_v_input=fmt_v_input, fmt_decimal_input=fmt_decimal_input, signed_class=signed_class, row_get=row_get, row_v_enabled=row_v_enabled, employment_class=employment_class, vacation_display=vacation_display, global_v_all=global_v_all)
    return base_page("Stunden für Lohnabrechnung", body, "payroll_hours")


@app.get("/admin/payroll-hours/export/<int:year>/<int:month>.pdf")
@admin_login_required
def download_payroll_hours_export(year:int, month:int):
    with db_conn() as conn:
        if month_is_editable(year, month):
            ensure_active_driver_month_rows(conn, year, month)
        recalc_all(conn)
        path = export_payroll_hours_pdf(conn, year, month)
        conn.commit()
    response = send_file(path, mimetype="application/pdf", as_attachment=True, download_name=path.name, max_age=0)
    response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"
    return response

@app.get("/admin/exports")
@admin_login_required
def admin_exports():
    with db_conn() as conn:
        month_rows = conn.execute("""
            SELECT year, month, total_rows, filled_rows
            FROM (
                SELECT m.year, m.month,
                       COUNT(*) AS total_rows,
                       SUM(CASE WHEN ABS(COALESCE(m.worked_hours,0))>0.0001
                                  OR ABS(COALESCE(m.payroll_hours,0))>0.0001
                                  OR TRIM(COALESCE(m.v_note,''))<>''
                                  OR ABS(COALESCE(m.bonus_hours,0))>0.0001
                                  OR ABS(COALESCE(m.deduction_hours,0))>0.0001
                                  OR ABS(COALESCE(m.adjustment_hours,0))>0.0001
                                  OR ABS(COALESCE(m.difference_hours,0))>0.0001
                                  OR TRIM(COALESCE(m.bonus_comment,''))<>''
                                  OR TRIM(COALESCE(m.deduction_comment,''))<>''
                                  OR TRIM(COALESCE(m.comment,''))<>''
                                  OR TRIM(COALESCE(m.admin_info,''))<>''
                                  OR EXISTS(SELECT 1 FROM adjustment_items ai WHERE ai.monthly_data_id=m.id)
                                  OR EXISTS(SELECT 1 FROM documents doc WHERE doc.driver_id=m.driver_id AND doc.year=m.year AND doc.month=m.month)
                                THEN 1 ELSE 0 END) AS filled_rows
                FROM monthly_data m
                GROUP BY m.year, m.month
            ) export_months
            WHERE filled_rows > 0
            ORDER BY year DESC, month DESC
        """).fetchall()
    body = render_template_string("""
    <div class="card"><h2>Export & Backup</h2><div class="actions"><a class="btn primary" href="{{ url_for('download_backup_json') }}">Backup JSON herunterladen</a><a class="btn" href="{{ url_for('download_backup_csv') }}">Monatsdaten CSV herunterladen</a><a class="btn danger" href="{{ url_for('admin_cleanup') }}">Aufräumen / Löschen</a></div><p class="download-note">Hier werden nur Monate angezeigt, die echte Daten enthalten. Leere automatisch erzeugte Monate erscheinen nicht mehr.</p></div>
    <div class="card"><h2>Monats-PDFs</h2>{% if month_rows %}<div class="driver-grid">{% for r in month_rows %}<a class="month-card" href="{{ url_for('download_month_export', year=r['year'], month=r['month']) }}"><strong>{{ months[r['month']] }} {{ r['year'] }}</strong>PDF herunterladen<br><span class="muted">{{ r['filled_rows'] }} Eintrag/Einträge</span></a>{% endfor %}</div>{% else %}<p class="muted">Noch keine echten Monatsdaten vorhanden.</p>{% endif %}</div>
    """, month_rows=month_rows, months=MONATE)
    return base_page("Export/Backup", body, "exports")


@app.route("/admin/cleanup", methods=["GET", "POST"])
@admin_login_required
def admin_cleanup():
    with db_conn() as conn:
        if request.method == "POST":
            action = request.form.get("action", "")
            confirm = request.form.get("confirm", "") == "JA"
            if not confirm:
                flash("Bitte zum Löschen das Kontrollkästchen bestätigen.", "err")
            elif action == "delete_selected_months":
                ids = [int(x) for x in request.form.getlist("monthly_ids") if x.isdigit()]
                if not ids:
                    flash("Keine Monate ausgewählt.", "err")
                else:
                    affected_drivers = set()
                    for mid in ids:
                        row = conn.execute("SELECT driver_id FROM monthly_data WHERE id=?", (mid,)).fetchone()
                        if row:
                            affected_drivers.add(int(row["driver_id"]))
                        delete_month_files(conn, mid)
                        conn.execute("DELETE FROM monthly_data WHERE id=?", (mid,))
                    for did in affected_drivers:
                        recalc_driver(conn, did)
                    cleanup_empty_dirs(FILES_DIR); cleanup_empty_dirs(ATTACHMENTS_DIR)
                    audit(conn, "cleanup_delete_months", ",".join(map(str, ids)))
                    conn.commit()
                    flash(f"{len(ids)} Monatsdatensatz/Datensätze gelöscht.", "ok")
            elif action == "delete_empty_months":
                rows = conn.execute("""
                    SELECT m.*,
                           (SELECT COUNT(*) FROM adjustment_items ai WHERE ai.monthly_data_id=m.id) AS adjustment_count,
                           (SELECT COUNT(*) FROM documents doc WHERE doc.driver_id=m.driver_id AND doc.year=m.year AND doc.month=m.month) AS document_count,
                           (SELECT COUNT(*) FROM adjustment_files af JOIN adjustment_items ai ON ai.id=af.adjustment_item_id WHERE ai.monthly_data_id=m.id) AS file_count
                    FROM monthly_data m
                    ORDER BY m.year, m.month
                """).fetchall()
                delete_ids = [int(r["id"]) for r in rows if not month_has_real_data(r, int(r["adjustment_count"]), int(r["document_count"]), int(r["file_count"]))]
                for mid in delete_ids:
                    delete_month_files(conn, mid)
                    conn.execute("DELETE FROM monthly_data WHERE id=?", (mid,))
                recalc_all(conn)
                cleanup_empty_dirs(FILES_DIR); cleanup_empty_dirs(ATTACHMENTS_DIR)
                audit(conn, "cleanup_delete_empty_months", str(len(delete_ids)))
                conn.commit()
                flash(f"{len(delete_ids)} leere automatisch erzeugte Monate gelöscht.", "ok")
            elif action == "delete_selected_drivers":
                ids = [int(x) for x in request.form.getlist("driver_ids") if x.isdigit()]
                if not ids:
                    flash("Keine Fahrer ausgewählt.", "err")
                else:
                    for did in ids:
                        delete_driver_files(conn, did)
                        conn.execute("DELETE FROM drivers WHERE id=?", (did,))
                    cleanup_empty_dirs(FILES_DIR); cleanup_empty_dirs(ATTACHMENTS_DIR)
                    audit(conn, "cleanup_delete_drivers", ",".join(map(str, ids)))
                    conn.commit()
                    flash(f"{len(ids)} Fahrer inkl. Monatsdaten, PDFs und Anhänge gelöscht.", "ok")
            elif action == "delete_selected_years":
                years = [int(x) for x in request.form.getlist("years") if x.isdigit()]
                if not years:
                    flash("Keine Jahre ausgewählt.", "err")
                else:
                    mids = []
                    for y in years:
                        mids.extend([int(r["id"]) for r in conn.execute("SELECT id FROM monthly_data WHERE year=?", (y,)).fetchall()])
                    affected_drivers = set()
                    for mid in mids:
                        row = conn.execute("SELECT driver_id FROM monthly_data WHERE id=?", (mid,)).fetchone()
                        if row:
                            affected_drivers.add(int(row["driver_id"]))
                        delete_month_files(conn, mid)
                        conn.execute("DELETE FROM monthly_data WHERE id=?", (mid,))
                    for did in affected_drivers:
                        recalc_driver(conn, did)
                    cleanup_empty_dirs(FILES_DIR); cleanup_empty_dirs(ATTACHMENTS_DIR)
                    audit(conn, "cleanup_delete_years", ",".join(map(str, years)))
                    conn.commit()
                    flash(f"Jahr(e) gelöscht: {', '.join(map(str, years))}.", "ok")
            elif action == "delete_generated_exports":
                removed = 0
                if EXPORT_DIR.exists():
                    for f in EXPORT_DIR.rglob("*"):
                        if f.is_file():
                            try:
                                f.unlink(); removed += 1
                            except Exception:
                                pass
                cleanup_empty_dirs(EXPORT_DIR)
                audit(conn, "cleanup_delete_exports", str(removed))
                conn.commit()
                flash(f"{removed} Export-Datei(en) von der Disk gelöscht. Sie werden bei Bedarf neu erzeugt.", "ok")
            elif action == "vacuum_db":
                conn.commit()
                conn.execute("VACUUM")
                flash("SQLite-Datenbank wurde komprimiert.", "ok")
            else:
                flash("Unbekannte Aktion.", "err")

        recalc_all(conn); conn.commit()
        drivers = conn.execute("""
            SELECT d.id, d.name, d.username, d.is_active,
                   COUNT(m.id) AS month_count,
                   COALESCE((SELECT new_balance FROM monthly_data mm WHERE mm.driver_id=d.id ORDER BY year DESC, month DESC, id DESC LIMIT 1), d.starting_balance) AS balance
            FROM drivers d
            LEFT JOIN monthly_data m ON m.driver_id=d.id
            WHERE COALESCE(d.is_disposition,0)=0
            GROUP BY d.id
            ORDER BY d.name COLLATE NOCASE
        """).fetchall()
        months = conn.execute("""
            SELECT m.id, m.year, m.month, d.name AS driver_name,
                   m.worked_hours, m.payroll_hours, m.v_note, m.bonus_hours, m.deduction_hours, m.difference_hours, m.admin_info,
                   (SELECT COUNT(*) FROM adjustment_items ai WHERE ai.monthly_data_id=m.id) AS adjustment_count,
                   (SELECT COUNT(*) FROM documents doc WHERE doc.driver_id=m.driver_id AND doc.year=m.year AND doc.month=m.month) AS document_count,
                   (SELECT COUNT(*) FROM adjustment_files af JOIN adjustment_items ai ON ai.id=af.adjustment_item_id WHERE ai.monthly_data_id=m.id) AS file_count
            FROM monthly_data m
            JOIN drivers d ON d.id=m.driver_id
            WHERE COALESCE(d.is_disposition,0)=0
            ORDER BY m.year DESC, m.month DESC, d.name COLLATE NOCASE
        """).fetchall()
        month_view = []
        for r in months:
            is_real = month_has_real_data(r, int(r["adjustment_count"]), int(r["document_count"]), int(r["file_count"]))
            month_view.append({"row": r, "is_real": is_real})
        years = conn.execute("SELECT DISTINCT year FROM monthly_data ORDER BY year DESC").fetchall()
        empty_count = sum(1 for m in month_view if not m["is_real"])
        real_count = sum(1 for m in month_view if m["is_real"])
        docs_count = conn.execute("SELECT COUNT(*) AS c FROM documents").fetchone()["c"]
        files_count = conn.execute("SELECT COUNT(*) AS c FROM adjustment_files").fetchone()["c"]

    body = render_template_string("""
    <div class="card">
      <h2>Aufräumen & Löschen</h2>
      <p class="muted">Vor großen Löschaktionen zuerst ein Backup herunterladen. Gelöschte Fahrer/Monate werden direkt aus der SQLite-Datenbank und die dazugehörigen PDF-/Anhang-Dateien von der Disk entfernt.</p>
      <div class="actions"><a class="btn primary" href="{{ url_for('download_backup_json') }}">Backup JSON herunterladen</a><a class="btn" href="{{ url_for('download_backup_csv') }}">CSV herunterladen</a><a class="btn" href="{{ url_for('admin_exports') }}">Zurück zu Export</a></div>
    </div>
    <div class="grid grid-4"><div class="kpi">Echte Monate<b>{{ real_count }}</b></div><div class="kpi">Leere Monate<b>{{ empty_count }}</b></div><div class="kpi">PDFs<b>{{ docs_count }}</b></div><div class="kpi">Anhänge<b>{{ files_count }}</b></div></div>

    <div class="card"><h2>Schnell aufräumen</h2><div class="grid grid-3">
      <form method="post" onsubmit="return confirm('Alle leeren Monate wirklich löschen?')"><input type="hidden" name="action" value="delete_empty_months"><label><input style="width:auto" type="checkbox" name="confirm" value="JA" required> bestätigen</label><button class="danger">Leere Monate löschen</button><p class="download-note">Löscht automatisch erzeugte Monate ohne Stunden, Kommentare, Positionen, PDFs oder Anhänge.</p></form>
      <form method="post" onsubmit="return confirm('Generierte Export-PDFs wirklich von der Disk löschen?')"><input type="hidden" name="action" value="delete_generated_exports"><label><input style="width:auto" type="checkbox" name="confirm" value="JA" required> bestätigen</label><button class="danger">Export-Dateien löschen</button><p class="download-note">Monats-Export-PDFs werden bei erneutem Klick automatisch neu erstellt.</p></form>
      <form method="post"><input type="hidden" name="action" value="vacuum_db"><input type="hidden" name="confirm" value="JA"><button>SQLite komprimieren</button><p class="download-note">Gibt nach Löschungen Speicher in der SQLite-Datei frei.</p></form>
    </div></div>

    <div class="card"><h2>Monate verwalten</h2><form method="post" onsubmit="return confirm('Ausgewählte Monatsdatensätze wirklich löschen?')"><input type="hidden" name="action" value="delete_selected_months">
      <div class="actions" style="margin-bottom:10px"><button type="button" onclick="document.querySelectorAll('.month-check').forEach(x=>x.checked=true)">Alle auswählen</button><button type="button" onclick="document.querySelectorAll('.month-check').forEach(x=>x.checked=false)">Auswahl entfernen</button><label style="width:auto;margin:0"><input style="width:auto" type="checkbox" name="confirm" value="JA" required> Löschen bestätigen</label><button class="danger">Ausgewählte Monate löschen</button></div>
      <div class="table-wrap"><table style="min-width:980px"><tr><th></th><th>Status</th><th>Monat</th><th>Fahrer</th><th>Stunden</th><th>Abrechnung</th><th>V</th><th>Positionen</th><th>PDF</th><th>Anhänge</th></tr>{% for m in month_view %}{% set r=m.row %}<tr><td><input class="month-check" style="width:auto" type="checkbox" name="monthly_ids" value="{{ r['id'] }}"></td><td>{% if m.is_real %}<span class="badge">Daten</span>{% else %}<span class="muted">leer</span>{% endif %}</td><td>{{ months_name[r['month']] }} {{ r['year'] }}</td><td>{{ r['driver_name'] }}</td><td>{{ fmt_hours(r['worked_hours']) }}</td><td>{{ fmt_hours(r['payroll_hours']) }}</td><td>{{ r['v_note'] or '-' }}</td><td>{{ r['adjustment_count'] }}</td><td>{{ r['document_count'] }}</td><td>{{ r['file_count'] }}</td></tr>{% endfor %}</table></div>
    </form></div>

    <div class="card"><h2>Fahrer verwalten/löschen</h2><form method="post" onsubmit="return confirm('Ausgewählte Fahrer wirklich komplett löschen? Alle Monatsdaten, PDFs und Anhänge werden gelöscht.')"><input type="hidden" name="action" value="delete_selected_drivers">
      <div class="actions" style="margin-bottom:10px"><button type="button" onclick="document.querySelectorAll('.driver-check').forEach(x=>x.checked=true)">Alle auswählen</button><button type="button" onclick="document.querySelectorAll('.driver-check').forEach(x=>x.checked=false)">Auswahl entfernen</button><label style="width:auto;margin:0"><input style="width:auto" type="checkbox" name="confirm" value="JA" required> Löschen bestätigen</label><button class="danger">Ausgewählte Fahrer löschen</button></div>
      <div class="table-wrap"><table style="min-width:760px"><tr><th></th><th>Fahrer</th><th>Benutzername</th><th>Aktiv</th><th>Monate</th><th>Saldo</th></tr>{% for d in drivers %}<tr><td><input class="driver-check" style="width:auto" type="checkbox" name="driver_ids" value="{{ d['id'] }}"></td><td>{{ d['name'] }}</td><td>{{ d['username'] }}</td><td>{{ 'ja' if d['is_active'] else 'nein' }}</td><td>{{ d['month_count'] }}</td><td class="{{ signed_class(d['balance']) }}">{{ fmt_signed(d['balance']) }}</td></tr>{% endfor %}</table></div>
    </form></div>

    <div class="card"><h2>Ganze Jahre löschen</h2><form method="post" onsubmit="return confirm('Ausgewählte Jahre wirklich komplett löschen?')"><input type="hidden" name="action" value="delete_selected_years"><div class="actions">{% for y in years %}<label style="width:auto"><input style="width:auto" type="checkbox" name="years" value="{{ y['year'] }}"> {{ y['year'] }}</label>{% endfor %}<label style="width:auto"><input style="width:auto" type="checkbox" name="confirm" value="JA" required> Löschen bestätigen</label><button class="danger">Ausgewählte Jahre löschen</button></div></form></div>
    """, drivers=drivers, month_view=month_view, years=years, real_count=real_count, empty_count=empty_count, docs_count=docs_count, files_count=files_count, months_name=MONATE, fmt_hours=fmt_hours, fmt_signed=fmt_signed, signed_class=signed_class)
    return base_page("Aufräumen", body, "cleanup")

# ---------------- driver portal ----------------
@app.route("/login", methods=["GET","POST"])
def driver_login():
    error = ""
    if request.method == "POST":
        username = request.form.get("username", "").strip(); password = request.form.get("password", "")
        with db_conn() as conn:
            row = conn.execute("SELECT * FROM drivers WHERE lower(username)=lower(?) AND is_active=1", (username,)).fetchone()
            password_ok = bool(row and check_password_hash(row["password_hash"], password))
            if not password_ok:
                error = "Login fehlgeschlagen."
            else:
                # Reuse the password that was already verified for this login.
                # This avoids an expensive bulk scrypt backfill on every request.
                if not str(row_get(row, "password_plain", "") or ""):
                    conn.execute(
                        "UPDATE drivers SET password_plain=?, updated_at=? WHERE id=?",
                        (password, now_iso(), int(row["id"])),
                    )
                    conn.commit()
                session.clear()
                if int(row_get(row, "is_disposition", 0) or 0) == 1:
                    session["dispo_db_id"] = int(row["id"]); session["dispo_name"] = row["name"]
                    return redirect(url_for("disposition_dashboard"))
                session["driver_db_id"] = int(row["id"]); session["driver_name"] = row["name"]
                return redirect(url_for("driver_years"))
    return render_template_string("""<!doctype html><html lang="de"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Login</title><style>{{ css }}</style></head><body><div class="login-wrap"><div class="card"><div class="title">Fahrer-/Disposition-Login</div><p class="muted">Fahrer sehen ihre eigenen freigegebenen Monatsdaten. Disposition sieht nur das Dashboard mit aktuellen Salden.</p>{% if error %}<div class="flash err">{{ error }}</div>{% endif %}<form method="post"><label>Benutzername</label><input name="username" required><label style="margin-top:12px">Passwort</label><input name="password" type="password" required><button class="primary" style="margin-top:14px">Einloggen</button></form><p><a href="{{ url_for('admin_login') }}">Admin Login</a></p></div></div></body></html>""", css=BASE_CSS, error=error)

@app.get("/logout")
def driver_logout():
    session.clear()
    return redirect(url_for("driver_login"))



@app.get("/disposition")
@disposition_login_required
def disposition_dashboard():
    sort_mode = normalize_balance_sort(request.args.get("sort", "order"))
    with db_conn() as conn:
        recalc_all(conn); conn.commit()
        balances = load_current_balances(conn, sort_mode)
    return render_template_string("""<!doctype html><html lang="de"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Disposition Dashboard</title><style>{{ css }}</style></head><body><main class="main"><div class="top"><div><div class="title">Dashboard</div><div class="subtitle">Angemeldet als <span class="badge">{{ session['dispo_name'] }}</span></div></div><a class="btn small" href="{{ url_for('driver_logout') }}">Logout</a></div><div class="card"><div class="actions" style="justify-content:space-between;margin-bottom:10px"><h2 style="margin:0">Aktuelle Salden</h2><div class="actions"><span class="muted">Sortieren nach:</span><a class="btn small {{ 'primary' if sort_mode=='asc' else '' }}" href="{{ url_for('disposition_dashboard', sort='asc') }}">Aufsteigend</a><a class="btn small {{ 'primary' if sort_mode=='desc' else '' }}" href="{{ url_for('disposition_dashboard', sort='desc') }}">Absteigend</a><a class="btn small {{ 'primary' if sort_mode=='order' else '' }}" href="{{ url_for('disposition_dashboard') }}">Fahrer-Reihenfolge</a></div></div><div class="table-wrap"><table style="min-width:420px"><tr><th>Fahrer</th><th class="right">Saldo</th></tr>{% for r in balances %}<tr><td>{{ r['name'] }}</td><td class="right {{ signed_class(r['bal'] if r['bal'] is not none else r['starting_balance']) }}">{{ fmt_signed(r['bal'] if r['bal'] is not none else r['starting_balance']) }}</td></tr>{% endfor %}</table></div></div></main></body></html>""", css=BASE_CSS, balances=balances, fmt_signed=fmt_signed, signed_class=signed_class, sort_mode=sort_mode)


@app.get("/jahre")
@driver_login_required
def driver_years():
    did = int(session["driver_db_id"])
    with db_conn() as conn:
        driver = get_driver_by_db_id(conn,did)
        if not driver or int(row_get(driver, "is_disposition", 0) or 0) == 1:
            session.clear(); return redirect(url_for("driver_login"))
        group = get_group_for_driver(conn, did)
        if group:
            placeholders = ",".join(["?"] * len(group["member_ids"]))
            years = conn.execute(f"""
                SELECT m.year, COUNT(DISTINCT m.month) cnt
                FROM monthly_data m
                JOIN month_releases mr ON mr.year=m.year AND mr.month=m.month AND mr.is_released=1
                WHERE m.driver_id IN ({placeholders})
                GROUP BY m.year
                ORDER BY m.year DESC
            """, tuple(group["member_ids"])).fetchall()
            latest_year_month = conn.execute(f"""
                SELECT m.year, m.month
                FROM monthly_data m
                JOIN month_releases mr ON mr.year=m.year AND mr.month=m.month AND mr.is_released=1
                WHERE m.driver_id IN ({placeholders})
                ORDER BY m.year DESC, m.month DESC
                LIMIT 1
            """, tuple(group["member_ids"])).fetchone()
            bal = make_group_month_summary(conn, group, int(latest_year_month["year"]), int(latest_year_month["month"]))["new_balance"] if latest_year_month else driver["starting_balance"]
        else:
            years = conn.execute("""
                SELECT m.year, COUNT(*) cnt
                FROM monthly_data m
                JOIN month_releases mr ON mr.year=m.year AND mr.month=m.month AND mr.is_released=1
                WHERE m.driver_id=?
                GROUP BY m.year
                ORDER BY m.year DESC
            """, (did,)).fetchall()
            latest = conn.execute("""
                SELECT m.new_balance
                FROM monthly_data m
                JOIN month_releases mr ON mr.year=m.year AND mr.month=m.month AND mr.is_released=1
                WHERE m.driver_id=?
                ORDER BY m.year DESC, m.month DESC, m.id DESC
                LIMIT 1
            """, (did,)).fetchone()
            bal = latest["new_balance"] if latest else driver["starting_balance"]
    return render_template_string("""<!doctype html><html lang="de"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Fahrerportal</title><style>{{ css }}</style></head><body><main class="main"><div class="top"><div><div class="title">Fahrerportal</div><div class="subtitle">Angemeldet als <span class="badge">{{ session['driver_name'] }}</span></div></div><a class="btn small" href="{{ url_for('driver_logout') }}">Logout</a></div><div class="card"><h2>Aktueller Stand: <span class="{{ signed_class(bal) }}">{{ fmt_signed(bal) }}</span></h2>{% if years %}<div class="driver-grid">{% for y in years %}<a class="month-card" href="{{ url_for('driver_months_for_year', year=y['year']) }}"><strong>{{ y['year'] }}</strong>{{ y['cnt'] }} Monat(e)</a>{% endfor %}</div>{% else %}<p class="muted">Es ist noch kein Monat für dich freigegeben.</p>{% endif %}</div></main></body></html>""", css=BASE_CSS, years=years, bal=bal, fmt_signed=fmt_signed, signed_class=signed_class)


@app.get("/jahr/<int:year>")
@driver_login_required
def driver_months_for_year(year:int):
    did = int(session["driver_db_id"])
    with db_conn() as conn:
        group = get_group_for_driver(conn, did)
        if group:
            placeholders = ",".join(["?"] * len(group["member_ids"]))
            month_nums = [int(r["month"]) for r in conn.execute(f"""
                SELECT DISTINCT m.month
                FROM monthly_data m
                JOIN month_releases mr ON mr.year=m.year AND mr.month=m.month AND mr.is_released=1
                WHERE m.driver_id IN ({placeholders}) AND m.year=?
                ORDER BY m.month
            """, tuple(group["member_ids"])+(year,)).fetchall()]
            rows = [make_group_month_summary(conn, group, year, m) for m in month_nums]
        else:
            rows = conn.execute("""
                SELECT m.*, doc.id AS doc_id
                FROM monthly_data m
                JOIN month_releases mr ON mr.year=m.year AND mr.month=m.month AND mr.is_released=1
                LEFT JOIN documents doc ON doc.driver_id=m.driver_id AND doc.year=m.year AND doc.month=m.month
                WHERE m.driver_id=? AND m.year=?
                ORDER BY m.month
            """, (did,year)).fetchall()
    return render_template_string("""<!doctype html><html lang="de"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{{ year }}</title><style>{{ css }}</style></head><body><main class="main"><div class="top"><div><div class="title">{{ year }}</div><div class="subtitle">{{ session['driver_name'] }}</div></div><div class="actions"><a class="btn small" href="{{ url_for('driver_years') }}">Zurück</a><a class="btn small" href="{{ url_for('driver_logout') }}">Logout</a></div></div><div class="card">{% if rows %}<div class="driver-grid">{% for r in rows %}<a class="month-card" href="{{ url_for('driver_month_detail', year=year, month=r['month']) }}"><strong>{{ months[r['month']] }}</strong><div>Differenz: <span class="{{ signed_class(r['difference_hours']) }}">{{ fmt_signed(r['difference_hours']) }}</span></div><div>Neuer Stand: <span class="{{ signed_class(r['new_balance']) }}">{{ fmt_signed(r['new_balance']) }}</span></div></a>{% endfor %}</div>{% else %}<p class="muted">Für dieses Jahr ist noch kein Monat freigegeben.</p>{% endif %}</div></main></body></html>""", css=BASE_CSS, rows=rows, year=year, months=MONATE, fmt_signed=fmt_signed, signed_class=signed_class)


@app.get("/jahr/<int:year>/<int:month>")
@driver_login_required
def driver_month_detail(year:int, month:int):
    did = int(session["driver_db_id"])
    with db_conn() as conn:
        if not is_month_released(conn, year, month):
            abort(404)
        group = get_group_for_driver(conn, did)
        if group:
            r = make_group_month_summary(conn, group, year, month)
            items = []
            group_month = get_group_month_override(conn, int(group["group"]["id"]), year, month)
            if group_month:
                items.extend([dict(i) for i in get_group_adjustment_items(conn, int(group_month["id"]))])
            for member in group["members"]:
                for it in conn.execute("""
                    SELECT ai.* FROM adjustment_items ai
                    JOIN monthly_data m ON m.id=ai.monthly_data_id
                    WHERE m.driver_id=? AND m.year=? AND m.month=?
                    ORDER BY ai.id
                """, (int(member["id"]), year, month)).fetchall():
                    x = dict(it); x["note"] = f"{member['name']}: {it['note']}"; items.append(x)
            doc = {"is_group": True}
            group_name = group["name"]
            group_mode = True
        else:
            r = conn.execute("SELECT * FROM monthly_data WHERE driver_id=? AND year=? AND month=?", (did,year,month)).fetchone()
            if not r:
                abort(404)
            recalc_month_adjustments(conn, int(r["id"]))
            recalc_driver(conn, did)
            create_driver_pdf(conn, did, year, month)
            conn.commit()
            r = conn.execute("SELECT * FROM monthly_data WHERE driver_id=? AND year=? AND month=?", (did,year,month)).fetchone()
            doc = conn.execute("SELECT * FROM documents WHERE driver_id=? AND year=? AND month=?", (did,year,month)).fetchone()
            items = conn.execute("""
                SELECT ai.* FROM adjustment_items ai
                JOIN monthly_data m ON m.id=ai.monthly_data_id
                WHERE m.driver_id=? AND m.year=? AND m.month=?
                ORDER BY ai.id
            """, (did, year, month)).fetchall()
            group_name = ""
            group_mode = False
    return render_template_string("""<!doctype html><html lang="de"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Monatsdetails</title><style>{{ css }}</style></head><body><main class="main"><div class="top"><div><div class="title">{{ months[month] }} {{ year }}</div><div class="subtitle">{{ group_name if group_mode else session['driver_name'] }}</div></div><div class="actions"><a class="btn small" href="{{ url_for('driver_months_for_year', year=year) }}">Zurück</a><a class="btn small" href="{{ url_for('driver_logout') }}">Logout</a></div></div><div class="card"><div class="grid grid-3"><div class="kpi">Stunden<b>{{ fmt_hours(r['worked_hours']) }}</b></div><div class="kpi">Abrechnung<b>{{ fmt_hours(r['payroll_hours']) }}</b></div><div class="kpi">V<b class="{{ '' if row_v_enabled(r) else 'zero' }}">{{ fmt_v_display(row_get(r, 'v_note', ''), row_get(r, 'v_enabled', 0), True) }}</b></div><div class="kpi">Zuschüsse<b>{{ fmt_hours(r['bonus_hours']) }}</b><span class="muted">{{ r['bonus_comment'] or '-' }}</span></div><div class="kpi">Abzüge<b>{{ fmt_hours(r['deduction_hours']) }}</b><span class="muted">{{ r['deduction_comment'] or '-' }}</span></div><div class="kpi">Differenz<b class="{{ signed_class(r['difference_hours']) }}">{{ fmt_signed(r['difference_hours']) }}</b></div><div class="kpi">Alter Stand<b>{{ fmt_signed(r['previous_balance']) }}</b></div><div class="kpi">Neuer Stand<b class="{{ signed_class(r['new_balance']) }}">{{ fmt_signed(r['new_balance']) }}</b></div></div><h3>Einzelne Zuschüsse / Abzüge</h3>{% if items %}{% for it in items %}<div class="item-row"><span class="{{ 'pos' if it['kind']=='bonus' else 'neg' }}">{{ '+' if it['kind']=='bonus' else '-' }}{{ fmt_hours(it['hours']) }}</span><span>{{ it['note'] }}</span></div>{% endfor %}{% else %}<p class="muted">Keine Positionen vorhanden.</p>{% endif %}{% if group_mode %}<p><a class="btn primary" style="width:auto;margin-top:14px" href="{{ url_for('download_group_pdf', year=year, month=month) }}">PDF herunterladen</a></p>{% elif doc %}<p><a class="btn primary" style="width:auto;margin-top:14px" href="{{ url_for('download_pdf', document_id=doc['id']) }}">PDF herunterladen</a></p>{% endif %}</div></main></body></html>""", css=BASE_CSS, r=r, doc=doc, items=items, year=year, month=month, months=MONATE, fmt_hours=fmt_hours, fmt_signed=fmt_signed, signed_class=signed_class, group_mode=group_mode, group_name=group_name, row_v_enabled=row_v_enabled, row_get=row_get, fmt_v_display=fmt_v_display)


@app.get("/pdf/gruppe/<int:year>/<int:month>")
@driver_login_required
def download_group_pdf(year:int, month:int):
    did = int(session["driver_db_id"])
    with db_conn() as conn:
        if not is_month_released(conn, year, month):
            abort(404)
        group = get_group_for_driver(conn, did)
        if not group:
            abort(404)
        path = create_group_pdf(conn, group, year, month)
        conn.commit()
        if not path.exists():
            abort(404)
    response = send_file(path, mimetype="application/pdf", as_attachment=True, download_name=path.name, max_age=0)
    response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"
    return response

@app.get("/pdf/<int:document_id>")
@driver_login_required
def download_pdf(document_id:int):
    """Always regenerates the PDF before download so the driver receives the newest version."""
    did = int(session["driver_db_id"])
    with db_conn() as conn:
        doc = conn.execute("SELECT * FROM documents WHERE id=? AND driver_id=?", (document_id,did)).fetchone()
        if not doc:
            abort(404)
        if not is_month_released(conn, int(doc["year"]), int(doc["month"])):
            abort(404)
        create_driver_pdf(conn, did, int(doc["year"]), int(doc["month"]))
        conn.commit()
        doc = conn.execute("SELECT * FROM documents WHERE driver_id=? AND year=? AND month=?", (did, int(doc["year"]), int(doc["month"]))).fetchone()
        if not doc:
            abort(404)
        path = DATA_ROOT / doc["relative_path"]
        if not path.exists():
            abort(404)
    response = send_file(path, mimetype="application/pdf", as_attachment=True, download_name=doc["original_filename"], max_age=0)
    response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"
    return response

# ---------------- downloads / APIs ----------------
@app.get("/admin/export/<int:year>/<int:month>.pdf")
@admin_login_required
def download_month_export(year:int, month:int):
    with db_conn() as conn:
        if month_is_editable(year, month):
            ensure_active_driver_month_rows(conn, year, month)
        recalc_all(conn); path = export_month_pdf(conn, year, month); conn.commit()
    response = send_file(path, mimetype="application/pdf", as_attachment=True, download_name=path.name, max_age=0)
    response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"
    return response


@app.get("/admin/backup.json")
@admin_login_required
def download_backup_json():
    with db_conn() as conn:
        data = {
            "drivers":[dict(r) for r in conn.execute("SELECT id,external_driver_id,name,employment_type,username,starting_balance,is_active,is_disposition,created_at,updated_at FROM drivers").fetchall()],
            "monthly_data":[dict(r) for r in conn.execute("SELECT * FROM monthly_data").fetchall()],
            "adjustment_items":[dict(r) for r in conn.execute("SELECT * FROM adjustment_items").fetchall()],
            "adjustment_files":[dict(r) for r in conn.execute("SELECT * FROM adjustment_files").fetchall()],
            "documents":[dict(r) for r in conn.execute("SELECT * FROM documents").fetchall()],
            "month_releases":[dict(r) for r in conn.execute("SELECT * FROM month_releases").fetchall()],
            "created_at":now_iso()
        }
    buf = io.BytesIO(json.dumps(data, ensure_ascii=False, indent=2).encode("utf-8"))
    return send_file(buf, mimetype="application/json", as_attachment=True, download_name=f"plus_minus_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json")


@app.get("/admin/month-data.csv")
@admin_login_required
def download_backup_csv():
    with db_conn() as conn:
        rows = conn.execute("SELECT d.name,m.* FROM monthly_data m JOIN drivers d ON d.id=m.driver_id WHERE COALESCE(d.is_disposition,0)=0 ORDER BY m.year,m.month,d.name COLLATE NOCASE").fetchall()
    out = io.StringIO(); w = csv.writer(out, delimiter=";")
    w.writerow(["Fahrer","Jahr","Monat","Allgemeine Infos nur Admin","Stunden","Abrechnung","V Notiz","Zuschuss Summe","Zuschuss Details","Abzug Summe","Abzug Details","Differenz","Alter Stand","Neuer Stand"])
    for r in rows:
        w.writerow([r["name"],r["year"],r["month"],r["admin_info"],r["worked_hours"],r["payroll_hours"],row_get(r,"v_note",""),r["bonus_hours"],r["bonus_comment"],r["deduction_hours"],r["deduction_comment"],r["difference_hours"],r["previous_balance"],r["new_balance"]])
    buf = io.BytesIO(out.getvalue().encode("utf-8-sig"))
    return send_file(buf, mimetype="text/csv", as_attachment=True, download_name="plus_minus_monatsdaten.csv")

# Keep old admin API compatible with your EXE/sync while moving to website-first
@app.post("/api/admin/upsert-driver")
def api_upsert_driver():
    admin_api_required(); p = request.get_json(force=True)
    ext_id = int(p["external_driver_id"]); name = str(p["name"]).strip(); username = str(p.get("username") or slugify(name)); password = p.get("password")
    if not password:
        abort(400, "password fehlt")
    start = float(p.get("starting_balance", 0) or 0); ts = now_iso()
    with db_conn() as conn:
        existing = conn.execute("SELECT * FROM drivers WHERE external_driver_id=?", (ext_id,)).fetchone()
        if existing:
            final = make_unique_username(conn, username, int(existing["id"])); conn.execute("UPDATE drivers SET name=?, username=?, password_hash=?, password_plain=?, starting_balance=?, is_active=1, is_disposition=0, updated_at=? WHERE id=?", (name,final,generate_password_hash(password),password,start,ts,existing["id"])); did=int(existing["id"])
        else:
            final = make_unique_username(conn, username); cur=conn.execute("INSERT INTO drivers(external_driver_id,name,username,password_hash,password_plain,starting_balance,is_active,created_at,updated_at) VALUES(?,?,?,?,?,?,1,?,?)", (ext_id,name,final,generate_password_hash(password),password,start,ts,ts)); did=int(cur.lastrowid)
        recalc_driver(conn,did); conn.commit()
    return jsonify({"ok":True,"driver_db_id":did,"username":final})


@app.get("/api/admin/drivers")
def api_drivers():
    admin_api_required()
    with db_conn() as conn:
        rows = conn.execute("SELECT id, external_driver_id, name, employment_type, username, starting_balance, is_active, is_disposition FROM drivers WHERE COALESCE(is_disposition,0)=0 ORDER BY COALESCE(NULLIF(display_order,0), id), name COLLATE NOCASE").fetchall()
        return jsonify({"drivers":[dict(r) for r in rows]})


@app.get("/api/admin/month-data")
def api_month_data():
    admin_api_required()
    with db_conn() as conn:
        rows = conn.execute("SELECT d.external_driver_id,d.name,m.year,m.month,m.worked_hours AS stunden,m.payroll_hours AS abrechnung,m.v_note AS v,m.bonus_hours AS zuschuesse,m.bonus_comment AS zuschuss_kommentar,m.deduction_hours AS abzuege,m.deduction_comment AS abzug_kommentar,m.difference_hours AS differenz,m.previous_balance AS aktueller_stand,m.new_balance AS neuer_stand FROM monthly_data m JOIN drivers d ON d.id=m.driver_id WHERE COALESCE(d.is_disposition,0)=0 ORDER BY d.external_driver_id,m.year,m.month").fetchall()
        return jsonify({"rows":[dict(r) for r in rows]})


@app.post("/api/admin/upsert-month-data")
def api_upsert_month_data():
    admin_api_required(); p = request.get_json(force=True)
    ext = int(p["external_driver_id"]); year=int(p["year"]); month=int(p["month"])
    with db_conn() as conn:
        d = conn.execute("SELECT * FROM drivers WHERE external_driver_id=? AND is_active=1 AND COALESCE(is_disposition,0)=0", (ext,)).fetchone()
        if not d:
            abort(400, "Fahrer nicht vorhanden")
        worked=float(p.get("worked_hours",p.get("stunden",0)) or 0); payroll=float(p.get("payroll_hours",p.get("abrechnung",0)) or 0); v_note=str(p.get("v_note",p.get("v",p.get("v_hours",''))) or '').strip(); bonus=float(p.get("bonus_hours",p.get("zuschuesse",0)) or 0); deduction=float(p.get("deduction_hours",p.get("abzuege",0)) or 0)
        diff=compute_difference(worked,payroll,0,bonus,deduction,0); ts=now_iso(); did=int(d["id"])
        existing=conn.execute("SELECT id FROM monthly_data WHERE driver_id=? AND year=? AND month=?", (did,year,month)).fetchone()
        vals=(worked,payroll,v_note,bonus,str(p.get("bonus_comment",p.get("zuschuss_kommentar",'')) or ''),deduction,str(p.get("deduction_comment",p.get("abzug_kommentar",'')) or ''),bonus+deduction,str(p.get("comment",'' ) or ''),diff,ts,did,year,month)
        if existing:
            conn.execute("UPDATE monthly_data SET worked_hours=?,payroll_hours=?,v_hours=0,v_note=?,v_enabled=0,bonus_hours=?,bonus_comment=?,deduction_hours=?,deduction_comment=?,adjustment_hours=?,comment=?,difference_hours=?,updated_at=? WHERE driver_id=? AND year=? AND month=?", vals)
        else:
            conn.execute("INSERT INTO monthly_data(worked_hours,payroll_hours,v_hours,v_note,v_enabled,bonus_hours,bonus_comment,deduction_hours,deduction_comment,adjustment_hours,comment,difference_hours,updated_at,driver_id,year,month) VALUES(?,?,0,?,0,?,?,?,?,?,?,?,?,?,?,?)", vals)
        recalc_driver(conn,did); create_driver_pdf(conn,did,year,month); conn.commit()
    return jsonify({"ok":True})


@app.post("/api/admin/upload-pdf")
def api_upload_pdf():
    admin_api_required(); ext=int(request.form["external_driver_id"]); year=int(request.form["year"]); month=int(request.form["month"]); upload=request.files.get("file")
    if not upload or not upload.filename.lower().endswith(".pdf"):
        abort(400,"PDF-Datei fehlt")
    with db_conn() as conn:
        d=conn.execute("SELECT * FROM drivers WHERE external_driver_id=? AND is_active=1 AND COALESCE(is_disposition,0)=0", (ext,)).fetchone()
        if not d:
            abort(400,"Fahrer nicht vorhanden")
        driver_slug=slugify(d["name"])+f"-{d['id']}"; target_dir=FILES_DIR/driver_slug/str(year); target_dir.mkdir(parents=True,exist_ok=True)
        safe_name=secure_filename(f"{month:02d}_{MONATE.get(month,str(month))}_{year}.pdf"); rel=Path("pdfs")/driver_slug/str(year)/safe_name; abs_path=DATA_ROOT/rel; upload.save(abs_path); ts=now_iso()
        existing=conn.execute("SELECT id FROM documents WHERE driver_id=? AND year=? AND month=?", (d["id"],year,month)).fetchone()
        if existing:
            conn.execute("UPDATE documents SET filename=?, original_filename=?, relative_path=?, uploaded_at=? WHERE id=?", (safe_name,upload.filename,str(rel),ts,existing["id"]))
        else:
            conn.execute("INSERT INTO documents(driver_id,year,month,filename,original_filename,relative_path,uploaded_at) VALUES(?,?,?,?,?,?,?)", (d["id"],year,month,safe_name,upload.filename,str(rel),ts))
        conn.commit()
    return jsonify({"ok":True,"stored_as":str(rel)})

if __name__ == "__main__":
    ensure_paths()
    with db_conn() as conn:
        recalc_all(conn); conn.commit()
    port = int(os.environ.get("PORT", "5050"))
    app.run(host="0.0.0.0", port=port, debug=False)












