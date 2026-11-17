#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations

import csv
import io
import json
import os
import re
import sqlite3
import threading
from datetime import datetime, timezone
from functools import wraps
from contextvars import ContextVar
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

_SB_STEP_READ_TIMEOUT = ContextVar("sb_step_read_timeout", default=15)

APP_NAME = "Plus/Minus Cloud"
DATA_ROOT = Path(os.environ.get("PORTAL_DATA_DIR", "/opt/render/project/src/data")).resolve()
FILES_DIR = DATA_ROOT / "pdfs"
ATTACHMENTS_DIR = DATA_ROOT / "attachments"
EXPORT_DIR = DATA_ROOT / "exports"
BACKUP_DIR = DATA_ROOT / "backups"
DB_FILE = DATA_ROOT / "portal.sqlite3"
SECRET_KEY = os.environ.get("PORTAL_SECRET_KEY", "") or os.urandom(48).hex()
ADMIN_API_TOKEN = os.environ.get("ADMIN_API_TOKEN", "")
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "")
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
label{display:block;font-weight:800;margin-bottom:6px}input,select,textarea,button,.btn{width:100%;padding:11px 12px;border:1px solid #c7ceda;border-radius:12px;font-size:15px;background:#fff}textarea{min-height:42px;resize:vertical}button,.btn{cursor:pointer;text-decoration:none;text-align:center;display:inline-block;background:#f8fafc;font-weight:800}.btn.primary,button.primary{background:linear-gradient(135deg,var(--blue),var(--blue2));border-color:var(--blue);color:#fff}.btn.danger,button.danger{background:#fff1f0;border-color:#fda29b;color:#b42318}.btn.small{width:auto;padding:8px 11px;border-radius:10px;font-size:13px}.actions{display:flex;gap:10px;flex-wrap:wrap;align-items:center}.actions .btn,.actions button{width:auto}.table-wrap{overflow:auto;border:1px solid var(--line);border-radius:18px;background:#fff}table{border-collapse:separate;border-spacing:0;width:100%;min-width:1180px}th,td{padding:12px;border-bottom:1px solid #edf0f5;text-align:left;vertical-align:middle}th{position:sticky;top:0;background:#f3f6fb;color:#344054;font-size:13px;z-index:1}tr:hover td{background:#fbfdff}.flash{padding:12px 14px;border-radius:14px;margin-bottom:14px;font-weight:700}.flash.ok{background:#ecfdf3;color:#067647;border:1px solid #abefc6}.flash.err{background:#fff1f0;color:#b42318;border:1px solid #fecdca}.login-wrap{max-width:520px;margin:8vh auto;padding:24px}.driver-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(210px,1fr));gap:14px}.month-card{padding:16px;border:1px solid var(--line);border-radius:18px;background:#fff;text-decoration:none}.month-card strong{display:block;color:#123e7c;font-size:1.1rem;margin-bottom:6px}.right{text-align:right}.nowrap{white-space:nowrap}.item-row{display:flex;gap:8px;align-items:center;margin-bottom:6px;padding:6px 8px;border:1px solid #edf0f5;border-radius:12px;background:#fbfdff}.item-row form{margin-left:auto}.mini-form{display:grid;grid-template-columns:110px 90px minmax(160px,1fr) auto;gap:8px;align-items:center}.sum-box{font-size:13px;margin-top:8px;color:var(--muted)}.admin-info{min-width:240px}.admin-info textarea{min-height:86px;font-size:14px;background:#fffef7;border-color:#f6d98b}.download-note{font-size:12px;color:var(--muted);margin-top:4px}.driver-row.row-base td{background:#ffffff}.driver-row.row-alt td{background:#f3f6fb}.driver-row:hover td{background:#eaf1fb!important}.adjustment-list{margin-top:12px;padding-top:10px;border-top:1px dashed #cfd6e3}.delete-month-btn{font-size:11px!important;padding:5px 8px!important;border-radius:9px!important;opacity:.82}.delete-month-btn:hover{opacity:1}.admin-info textarea.carried{background:#f5f8ff;border-color:#b8c8f0}.months-table{table-layout:fixed;min-width:0}.months-table th,.months-table td{padding:8px 7px}.col-admin{width:155px}.col-driver{width:190px}.col-hours{width:82px}.col-payroll{width:82px}.col-v{width:125px}.col-adjust{width:350px}.col-small{width:62px}.col-balance{width:92px}.col-action{width:100px}.balance-input{min-width:72px;padding:8px 7px;font-size:13px;font-weight:800}.balance-mode{margin-top:3px;font-size:10px;color:#98a2b3;font-weight:800;line-height:1.05}.balance-mode.manual{color:#b54708}.months-table input[name=worked_hours],.months-table input[name=payroll_hours],.months-table input[name=v_note]{padding:12px 9px;font-size:16px}.months-table input[name=worked_hours]{max-width:70px}.months-table input[name=payroll_hours]{max-width:74px}.months-table input[name=v_note]{max-width:115px}.v-preview{font-size:12px;color:#98a2b3;margin-top:4px;line-height:1.2;white-space:nowrap}.v-toggle{display:inline-flex!important;align-items:center;gap:4px;margin-top:4px;color:#667085;font-size:11px;font-weight:800;line-height:1;white-space:nowrap;max-width:70px;overflow:hidden;margin-bottom:0}.v-toggle input{width:auto!important;min-width:13px!important;height:13px!important;padding:0!important;margin:0!important}.v-disabled{background:#f2f4f7!important;border-color:#d0d5dd!important;color:#667085!important;opacity:.72}.v-disabled-note{font-size:10px;color:#98a2b3;margin-top:3px;font-weight:800;line-height:1.05;max-width:70px}.mini-form{display:flex;flex-wrap:wrap;gap:7px;align-items:center}.mini-form select{width:78px}.mini-form input[name=item_hours]{width:58px}.mini-form input[name=item_note]{width:105px}.mini-form button{width:auto}.dropzone{position:relative;border:2px dashed #b8c4d6;background:#f8fafc;border-radius:14px;padding:14px 12px;text-align:center;font-size:13px;line-height:1.25;color:#475467;cursor:pointer;min-height:48px;display:flex;align-items:center;justify-content:center;width:115px}.dropzone.dragover{border-color:#067647;background:#ecfdf3;color:#067647}.dropzone input[type=file]{position:absolute;inset:0;opacity:0;cursor:pointer}.file-pill{display:inline-flex;align-items:center;gap:6px;padding:5px 8px;border-radius:999px;background:#eef4ff;color:#123e7c;font-size:12px;margin-top:6px}.file-pill form{display:inline;margin:0}.file-remove{width:auto!important;padding:3px 7px!important;border-radius:999px!important;font-size:11px!important}.compact-save{display:flex;flex-direction:column;gap:7px;align-items:flex-start}.mobile-row-title{display:none;font-weight:900;color:#0f2446;margin-bottom:8px}.payroll-table{table-layout:fixed;min-width:0}.payroll-table th,.payroll-table td{padding:9px 8px}.col-pay-info{width:150px}.col-pay-num{width:84px}.col-days{width:105px}.days-vacation input{border-color:#75c087;background:#f0fdf4;color:#067647}.days-sick .sick-calendar-open{border-color:#fda29b;background:#fff1f0;color:#b42318;text-align:left}.payroll-table textarea{min-height:74px;font-size:14px}.driver-name{font-weight:900}.employment-vollzeit{color:#7c3aed}.employment-teilzeit{color:#d4a000}.employment-aushilfe{color:#38bdf8}.vacation-input-wrap{position:relative}.vacation-input-wrap input{padding-right:48px}.vacation-input-wrap .suffix{position:absolute;right:11px;top:50%;transform:translateY(-50%);pointer-events:none;color:#667085;opacity:.55;font-weight:800;font-size:12px}.sick-days-overview{margin-top:6px;font-size:12px;font-weight:600;color:#b42318;line-height:1.3}.sick-days-total{font-weight:900;text-decoration:underline;text-decoration-thickness:1.5px;text-underline-offset:2px}.sick-calendar-modal{position:fixed;inset:0;background:rgba(15,36,70,.45);display:none;align-items:center;justify-content:center;padding:18px;z-index:1000}.sick-calendar-modal.open{display:flex}.sick-calendar-panel{width:min(520px,100%);background:#fff;border-radius:22px;border:1px solid var(--line);box-shadow:0 24px 70px rgba(16,24,40,.25);padding:18px}.sick-calendar-head{display:flex;justify-content:space-between;gap:12px;align-items:center;margin-bottom:12px}.sick-calendar-week,.sick-calendar-grid{display:grid;grid-template-columns:repeat(7,1fr);gap:6px}.sick-calendar-week div{text-align:center;color:#667085;font-size:12px;font-weight:900;padding:5px}.sick-day{min-height:46px;padding:8px 4px;border-radius:12px;text-align:center;font-weight:900;touch-action:none;user-select:none}.sick-day.selected{background:#fee4e2;border-color:#f04438;color:#b42318}.sick-day.blank{visibility:hidden}.sick-calendar-hint{font-size:12px;color:#667085;margin:10px 0}.global-v-toggle{display:inline-flex!important;align-items:center;gap:5px;font-size:11px;font-weight:900;color:#667085;margin-top:5px;white-space:nowrap}.global-v-toggle input{width:auto!important;margin:0!important;padding:0!important}.group-member-preview{margin-top:8px;padding:8px;border-radius:12px;background:#f8fafc;border:1px dashed #cfd6e3;font-size:12px;color:#344054;min-width:0;max-width:100%;overflow:auto}.group-member-preview table{min-width:0!important;width:100%;font-size:12px}.group-member-preview th,.group-member-preview td{padding:4px 5px;white-space:nowrap}.group-worked-note{font-size:12px;color:#667085;margin-top:4px}.group-mini-form{display:flex;flex-wrap:wrap;gap:7px;align-items:center}.group-mini-form select{width:78px}.group-mini-form input[name=item_hours]{width:58px}.group-mini-form input[name=item_note]{width:105px}.group-mini-form button{width:auto}.driver-balance-mini{display:block;margin-top:4px;font-size:11px;font-weight:900;opacity:.68;line-height:1.1;letter-spacing:.01em}.month-locked-note{margin-top:10px;padding:10px 12px;border-radius:12px;background:#fff7ed;border:1px solid #fed7aa;color:#b54708;font-weight:800;font-size:13px}

@media(min-width:901px){.table-wrap.mobile-cards{max-height:calc(100vh - 230px);overflow:auto;position:relative}.months-table th,.payroll-table th{position:sticky;top:0;z-index:20;background:#f3f6fb}}
@media(max-width:900px){.shell{display:block}.side{position:relative;height:auto}.main{padding:14px}.grid-2,.grid-3,.grid-4{grid-template-columns:1fr}.top{display:block}.title{font-size:1.55rem}.mini-form{grid-template-columns:1fr}.table-wrap.mobile-cards{overflow:visible;border:0;background:transparent}.months-table{min-width:0;display:block}.months-table thead{display:none}.months-table tbody,.months-table tr,.months-table td{display:block;width:100%}.months-table tr{margin-bottom:14px;border:1px solid var(--line);border-radius:18px;background:#fff;box-shadow:var(--shadow);overflow:hidden}.months-table td{border-bottom:1px solid #edf0f5;padding:10px 12px}.months-table td::before{content:attr(data-label);display:block;font-size:12px;font-weight:900;color:#667085;margin-bottom:5px}.months-table .mobile-row-title{display:block}.months-table input[name=worked_hours],.months-table input[name=payroll_hours],.months-table input[name=v_note]{max-width:100%;width:100%}.admin-info{min-width:0}.col-adjust{width:auto}.compact-save{flex-direction:row;flex-wrap:wrap}.item-row{align-items:flex-start}.side .muted{display:none}}

/* --- Zusammengefuehrte Stunden/Lohnabrechnung + Plus/Minus Ansicht --- */
@media(min-width:1181px){
.shell-payroll_hours{grid-template-columns:205px minmax(0,1fr)}
.shell-payroll_hours .side{padding:18px 12px}
.shell-payroll_hours .main{padding:12px 8px;max-width:none;min-width:0}
.page-payroll_hours .top{margin-bottom:12px}
.page-payroll_hours .combined-toolbar{padding:12px;margin-bottom:12px}
.page-payroll_hours .combined-card{padding:12px 6px}
.page-payroll_hours .combined-wrap{overflow-x:hidden!important;overflow-y:auto;max-height:calc(100vh - 238px);border-radius:14px}
.page-payroll_hours .merged-payroll-table{table-layout:fixed;min-width:0!important;width:100%;font-size:11px}
.page-payroll_hours .merged-payroll-table th,.page-payroll_hours .merged-payroll-table td{padding:6px 4px;min-width:0;overflow-wrap:anywhere}
.page-payroll_hours .merged-payroll-table th{font-size:10px;line-height:1.12}
.page-payroll_hours .merged-payroll-table .col-admin{width:8.5%}
.page-payroll_hours .merged-payroll-table .col-pay-info{width:8.5%}
.page-payroll_hours .merged-payroll-table .col-driver{width:8.5%}
.page-payroll_hours .merged-payroll-table .col-hours{width:4.5%}
.page-payroll_hours .merged-payroll-table .col-payroll{width:4.5%}
.page-payroll_hours .merged-payroll-table .col-v{width:6%}
.page-payroll_hours .merged-payroll-table .col-pay-num{width:4.3%}
.page-payroll_hours .merged-payroll-table .col-days{width:4.5%}
.page-payroll_hours .merged-payroll-table .col-sick{width:6.2%}
.page-payroll_hours .merged-payroll-table .col-adjust{width:18.5%}
.page-payroll_hours .merged-payroll-table .col-small{width:4%}
.page-payroll_hours .merged-payroll-table .col-balance{width:5.5%}
.page-payroll_hours .merged-payroll-table .col-action{width:6.2%}
.page-payroll_hours .merged-payroll-table input,.page-payroll_hours .merged-payroll-table select,.page-payroll_hours .merged-payroll-table textarea,.page-payroll_hours .merged-payroll-table button{min-width:0;width:100%;font-size:11px;padding:7px 5px;border-radius:9px}
.page-payroll_hours .merged-payroll-table textarea{min-height:60px;line-height:1.15}
.page-payroll_hours .merged-payroll-table .admin-info{min-width:0}
.page-payroll_hours .merged-payroll-table .admin-info textarea{min-height:60px;font-size:11px}
.page-payroll_hours .merged-payroll-table .nowrap{white-space:normal}
.page-payroll_hours .merged-payroll-table .driver-name{display:block;overflow-wrap:anywhere;line-height:1.15}
.page-payroll_hours .merged-payroll-table .driver-balance-mini{display:none}
.page-payroll_hours .merged-payroll-table .balance-input{min-width:0;width:100%;padding:7px 4px;font-size:11px}
.page-payroll_hours .merged-payroll-table .balance-mode{font-size:8px}
.page-payroll_hours .merged-payroll-table .v-toggle{font-size:9px;max-width:100%;white-space:normal;gap:2px}
.page-payroll_hours .merged-payroll-table .v-disabled-note{font-size:8px;max-width:100%}
.page-payroll_hours .merged-payroll-table .global-v-toggle{font-size:8px;white-space:normal}
.page-payroll_hours .merged-payroll-table .vacation-input-wrap .suffix{display:none}
.page-payroll_hours .merged-payroll-table .sick-calendar-open{font-size:9px;padding:7px 3px;white-space:normal}
.page-payroll_hours .merged-payroll-table .sick-days-overview{font-size:8px;overflow-wrap:anywhere}
.page-payroll_hours .merged-payroll-table .mini-form,.page-payroll_hours .merged-payroll-table .group-mini-form{display:grid;grid-template-columns:minmax(0,1fr) minmax(0,.72fr);gap:4px;align-items:center}
.page-payroll_hours .merged-payroll-table .mini-form select,.page-payroll_hours .merged-payroll-table .group-mini-form select,.page-payroll_hours .merged-payroll-table .mini-form input[name=item_hours],.page-payroll_hours .merged-payroll-table .group-mini-form input[name=item_hours]{width:100%!important}
.page-payroll_hours .merged-payroll-table .mini-form input[name=item_note],.page-payroll_hours .merged-payroll-table .group-mini-form input[name=item_note],.page-payroll_hours .merged-payroll-table .dropzone,.page-payroll_hours .merged-payroll-table .mini-form button,.page-payroll_hours .merged-payroll-table .group-mini-form button{grid-column:1/-1;width:100%!important}
.page-payroll_hours .merged-payroll-table .dropzone{min-height:34px;padding:6px 4px;font-size:9px;border-radius:9px}
.page-payroll_hours .merged-payroll-table .sum-box{font-size:9px;line-height:1.2;margin-top:5px}
.page-payroll_hours .merged-payroll-table .adjustment-list{margin-top:6px;padding-top:6px}
.page-payroll_hours .merged-payroll-table .item-row{display:flex;flex-wrap:wrap;gap:4px;min-width:0;padding:4px;font-size:9px;align-items:flex-start}
.page-payroll_hours .merged-payroll-table .item-row form{margin-left:0}
.page-payroll_hours .merged-payroll-table .item-row span,.page-payroll_hours .merged-payroll-table .file-pill{max-width:100%;white-space:normal;overflow-wrap:anywhere}
.page-payroll_hours .merged-payroll-table .file-pill{font-size:8px;padding:3px 4px}
.page-payroll_hours .merged-payroll-table .compact-save{display:flex;flex-direction:column;gap:5px;align-items:stretch}
.page-payroll_hours .merged-payroll-table .compact-save .btn,.page-payroll_hours .merged-payroll-table .compact-save button{width:100%!important;font-size:9px;padding:7px 3px}
.page-payroll_hours .merged-payroll-table .download-note{font-size:8px}
.page-payroll_hours .readonly-summary{font-size:9px;line-height:1.2;color:#667085;white-space:pre-line;overflow-wrap:anywhere}
}
@media(max-width:1180px){
.page-payroll_hours .combined-wrap{overflow:visible!important;max-height:none!important;border:0;background:transparent}
.page-payroll_hours .merged-payroll-table{display:block;min-width:0!important;width:100%}
.page-payroll_hours .merged-payroll-table thead{display:none}
.page-payroll_hours .merged-payroll-table tbody{display:block;width:100%}
.page-payroll_hours .merged-payroll-table tr{display:grid!important;grid-template-columns:repeat(2,minmax(0,1fr));width:100%;margin-bottom:14px;border:1px solid var(--line);border-radius:18px;background:#fff;box-shadow:var(--shadow);overflow:hidden}
.page-payroll_hours .merged-payroll-table td{display:block!important;width:100%!important;border-bottom:1px solid #edf0f5;padding:10px 12px;min-width:0}
.page-payroll_hours .merged-payroll-table td::before{content:attr(data-label);display:block;font-size:11px;font-weight:900;color:#667085;margin-bottom:5px}
.page-payroll_hours .merged-payroll-table td[data-label="Zuschüsse / Abzüge"],.page-payroll_hours .merged-payroll-table td[data-label="Aktion"]{grid-column:1/-1}
.page-payroll_hours .merged-payroll-table input,.page-payroll_hours .merged-payroll-table select,.page-payroll_hours .merged-payroll-table textarea,.page-payroll_hours .merged-payroll-table button,.page-payroll_hours .merged-payroll-table .balance-input{max-width:none!important;width:100%!important}
.page-payroll_hours .merged-payroll-table .mini-form,.page-payroll_hours .merged-payroll-table .group-mini-form{display:grid;grid-template-columns:120px 90px minmax(150px,1fr) 140px auto;gap:6px}
.page-payroll_hours .merged-payroll-table .dropzone{width:140px}
}
@media(max-width:650px){
.page-payroll_hours .merged-payroll-table tr{grid-template-columns:1fr}
.page-payroll_hours .merged-payroll-table td[data-label="Zuschüsse / Abzüge"],.page-payroll_hours .merged-payroll-table td[data-label="Aktion"]{grid-column:auto}
.page-payroll_hours .merged-payroll-table .mini-form,.page-payroll_hours .merged-payroll-table .group-mini-form{grid-template-columns:1fr}
.page-payroll_hours .merged-payroll-table .dropzone{width:100%}
}

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


def fmt_balance_input(value: Any) -> str:
    """Editable German decimal display for balance fields; zero must stay visible."""
    return f"{safe_float(value):.2f}".replace(".", ",")


def parse_optional_hours(raw: str) -> Optional[float]:
    """Blank means automatic balance calculation; otherwise parse a manual hour value."""
    text = (raw or "").strip()
    return None if not text else round(parse_hours(text), 2)


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

def sick_days_count(raw: str) -> int:
    """Return the number of unique selected sick days in the stored day ranges."""
    try:
        return len(_expand_day_ranges(raw))
    except Exception:
        return 0

def sick_days_display(raw: str) -> str:
    """Show stored sick-day ranges together with their total number of days."""
    value = str(raw or "").strip()
    if not value:
        return ""
    count = sick_days_count(value)
    return f"{value} = {count} Tage"

def sick_days_pdf_display(raw: str) -> str:
    """PDF display: emphasize the total sick-day count in bold and underline."""
    value = str(raw or "").strip()
    if not value:
        return ""
    count = sick_days_count(value)
    return f"{value} = <b><u>{count} Tage</u></b>"

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
            "UPDATE monthly_data SET admin_info=?, admin_info_carried=0, info_carry_initialized=1, updated_at=? WHERE id=?",
            (text, now_iso(), monthly_id),
        )
        propagate_admin_info_forward_only(conn, int(member["id"]), year, month, text)


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
        info_carry_initialized INTEGER NOT NULL DEFAULT 1,
        payroll_office_info TEXT NOT NULL DEFAULT '',
        payroll_office_info_carried INTEGER NOT NULL DEFAULT 0,
        payroll_surcharge DOUBLE PRECISION NOT NULL DEFAULT 0,
        fuel_voucher DOUBLE PRECISION NOT NULL DEFAULT 0,
        payroll_carry_initialized INTEGER NOT NULL DEFAULT 0,
        vacation_days TEXT NOT NULL DEFAULT '',
        sick_days TEXT NOT NULL DEFAULT '',
        difference_hours DOUBLE PRECISION NOT NULL DEFAULT 0,
        previous_balance DOUBLE PRECISION NOT NULL DEFAULT 0,
        new_balance DOUBLE PRECISION NOT NULL DEFAULT 0,
        previous_balance_override DOUBLE PRECISION DEFAULT NULL,
        new_balance_override DOUBLE PRECISION DEFAULT NULL,
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
        "ALTER TABLE monthly_data ADD COLUMN IF NOT EXISTS info_carry_initialized INTEGER NOT NULL DEFAULT 1",
        "ALTER TABLE monthly_data ADD COLUMN IF NOT EXISTS payroll_office_info_carried INTEGER NOT NULL DEFAULT 0",
        "ALTER TABLE monthly_data ADD COLUMN IF NOT EXISTS adjustment_hours DOUBLE PRECISION NOT NULL DEFAULT 0",
        "ALTER TABLE monthly_data ADD COLUMN IF NOT EXISTS comment TEXT NOT NULL DEFAULT ''",
        "ALTER TABLE monthly_data ADD COLUMN IF NOT EXISTS payroll_office_info TEXT NOT NULL DEFAULT ''",
        "ALTER TABLE monthly_data ADD COLUMN IF NOT EXISTS payroll_surcharge DOUBLE PRECISION NOT NULL DEFAULT 0",
        "ALTER TABLE monthly_data ADD COLUMN IF NOT EXISTS fuel_voucher DOUBLE PRECISION NOT NULL DEFAULT 0",
        "ALTER TABLE monthly_data ADD COLUMN IF NOT EXISTS vacation_days TEXT NOT NULL DEFAULT ''",
        "ALTER TABLE monthly_data ADD COLUMN IF NOT EXISTS sick_days TEXT NOT NULL DEFAULT ''",
        "ALTER TABLE monthly_data ADD COLUMN IF NOT EXISTS previous_balance_override DOUBLE PRECISION DEFAULT NULL",
        "ALTER TABLE monthly_data ADD COLUMN IF NOT EXISTS new_balance_override DOUBLE PRECISION DEFAULT NULL",
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


# Avoid executing the complete PostgreSQL CREATE/ALTER migration list on
# every transfer state change. Every process and every database URL still run
# the original schema/migration code once, under a lock; never mark success
# until the full schema transaction has committed.
_PG_SCHEMA_LOCK = threading.Lock()
_PG_SCHEMA_READY_FOR = set()


def db_conn():
    ensure_paths()
    database_url = os.environ.get("DATABASE_URL", "").strip()

    if database_url:
        import psycopg2
        from psycopg2.extras import RealDictCursor

        raw = psycopg2.connect(database_url, cursor_factory=RealDictCursor)
        raw.autocommit = False
        conn = _PostgresCompatConnection(raw)
        if database_url not in _PG_SCHEMA_READY_FOR:
            with _PG_SCHEMA_LOCK:
                if database_url not in _PG_SCHEMA_READY_FOR:
                    try:
                        _init_postgres_schema(conn)
                    except Exception:
                        raw.rollback()
                        raw.close()
                        raise
                    _PG_SCHEMA_READY_FOR.add(database_url)
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
        info_carry_initialized INTEGER NOT NULL DEFAULT 1,
        payroll_office_info TEXT NOT NULL DEFAULT '',
        payroll_office_info_carried INTEGER NOT NULL DEFAULT 0,
        payroll_surcharge REAL NOT NULL DEFAULT 0,
        fuel_voucher REAL NOT NULL DEFAULT 0,
        payroll_carry_initialized INTEGER NOT NULL DEFAULT 0,
        vacation_days TEXT NOT NULL DEFAULT '',
        sick_days TEXT NOT NULL DEFAULT '',
        difference_hours REAL NOT NULL DEFAULT 0,
        previous_balance REAL NOT NULL DEFAULT 0,
        new_balance REAL NOT NULL DEFAULT 0,
        previous_balance_override REAL DEFAULT NULL,
        new_balance_override REAL DEFAULT NULL,
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
        "info_carry_initialized":"ALTER TABLE monthly_data ADD COLUMN info_carry_initialized INTEGER NOT NULL DEFAULT 1",
        "payroll_office_info_carried":"ALTER TABLE monthly_data ADD COLUMN payroll_office_info_carried INTEGER NOT NULL DEFAULT 0",
        "payroll_office_info":"ALTER TABLE monthly_data ADD COLUMN payroll_office_info TEXT NOT NULL DEFAULT ''",
        "payroll_surcharge":"ALTER TABLE monthly_data ADD COLUMN payroll_surcharge REAL NOT NULL DEFAULT 0",
        "fuel_voucher":"ALTER TABLE monthly_data ADD COLUMN fuel_voucher REAL NOT NULL DEFAULT 0",
        "vacation_days":"ALTER TABLE monthly_data ADD COLUMN vacation_days TEXT NOT NULL DEFAULT ''",
        "sick_days":"ALTER TABLE monthly_data ADD COLUMN sick_days TEXT NOT NULL DEFAULT ''",
        "previous_balance_override":"ALTER TABLE monthly_data ADD COLUMN previous_balance_override REAL DEFAULT NULL",
        "new_balance_override":"ALTER TABLE monthly_data ADD COLUMN new_balance_override REAL DEFAULT NULL",
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


def maybe_carry_month_infos(conn: sqlite3.Connection, monthly_data_id: int, driver_id: int, year: int, month: int) -> None:
    """Initialize the two rolling info fields from the immediately previous month.

    A deliberately cleared field is still a valid monthly value. The
    ``info_carry_initialized`` flag distinguishes a new month from a month that
    has already been inherited or explicitly saved, so a deleted September note
    does not reappear from August on the next page load.
    """
    current = conn.execute(
        """
        SELECT COALESCE(info_carry_initialized,0) AS info_carry_initialized
        FROM monthly_data WHERE id=?
        """,
        (monthly_data_id,),
    ).fetchone()
    if not current or int(row_get(current, "info_carry_initialized", 0) or 0) == 1:
        return

    py, pm = previous_month(year, month)
    prev = conn.execute(
        """
        SELECT admin_info, payroll_office_info
        FROM monthly_data
        WHERE driver_id=? AND year=? AND month=?
        """,
        (driver_id, py, pm),
    ).fetchone()

    admin_info = str(row_get(prev, "admin_info", "") or "") if prev else ""
    payroll_office_info = str(row_get(prev, "payroll_office_info", "") or "") if prev else ""
    inherited = 1 if prev else 0
    conn.execute(
        """
        UPDATE monthly_data
        SET admin_info=?, admin_info_carried=?, payroll_office_info=?,
            payroll_office_info_carried=?, info_carry_initialized=1, updated_at=?
        WHERE id=?
        """,
        (admin_info, inherited, payroll_office_info, inherited, now_iso(), monthly_data_id),
    )


def rolling_info_save_state(
    conn: sqlite3.Connection, monthly_data_id: int, admin_info: str, payroll_office_info: str
) -> Dict[str, Any]:
    """Return carried/manual flags and whether either rolling field was changed."""
    old = conn.execute(
        """
        SELECT admin_info, COALESCE(admin_info_carried,0) AS admin_info_carried,
               payroll_office_info, COALESCE(payroll_office_info_carried,0) AS payroll_office_info_carried
        FROM monthly_data WHERE id=?
        """,
        (monthly_data_id,),
    ).fetchone()
    old_admin = str(row_get(old, "admin_info", "") or "") if old else ""
    old_payroll = str(row_get(old, "payroll_office_info", "") or "") if old else ""
    admin_text = (admin_info or "").strip()
    payroll_text = (payroll_office_info or "").strip()
    admin_changed = admin_text != old_admin
    payroll_changed = payroll_text != old_payroll
    return {
        "admin_changed": admin_changed,
        "payroll_changed": payroll_changed,
        "admin_carried": 0 if admin_changed else int(row_get(old, "admin_info_carried", 0) or 0),
        "payroll_carried": 0 if payroll_changed else int(row_get(old, "payroll_office_info_carried", 0) or 0),
    }


def propagate_rolling_info_forward(
    conn: sqlite3.Connection, driver_id: int, year: int, month: int,
    field: str, value: str,
) -> None:
    """Update only later months that are still inherited for this field.

    Propagation stops at the first later month that has its own manual value.
    Earlier months are never touched.
    """
    if field == "admin_info":
        carried_field = "admin_info_carried"
    elif field == "payroll_office_info":
        carried_field = "payroll_office_info_carried"
    else:
        raise ValueError("Unsupported rolling info field")

    rows = conn.execute(
        f"""
        SELECT id, COALESCE({carried_field},0) AS carried,
               COALESCE(info_carry_initialized,0) AS info_carry_initialized
        FROM monthly_data
        WHERE driver_id=? AND (year>? OR (year=? AND month>?))
        ORDER BY year, month, id
        """,
        (driver_id, year, year, month),
    ).fetchall()
    text = (value or "").strip()
    for future in rows:
        initialized = int(row_get(future, "info_carry_initialized", 0) or 0)
        carried = int(row_get(future, "carried", 0) or 0)
        if initialized == 1 and carried == 0:
            break
        conn.execute(
            f"""
            UPDATE monthly_data
            SET {field}=?, {carried_field}=1, info_carry_initialized=1, updated_at=?
            WHERE id=?
            """,
            (text, now_iso(), int(future["id"])),
        )


def propagate_admin_info_forward_only(
    conn: sqlite3.Connection, driver_id: int, year: int, month: int, admin_info: str
) -> None:
    """Forward only the internal admin note, used by grouped-driver synchronization."""
    propagate_rolling_info_forward(conn, driver_id, year, month, "admin_info", admin_info)


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
            "INSERT INTO monthly_data(driver_id, year, month, v_enabled, info_carry_initialized, payroll_carry_initialized, updated_at) VALUES(?,?,?,?,?,?,?)",
            (driver_id, year, month, 0, 0, 0, now_iso()),
        )
        monthly_id = int(cur.lastrowid)

    if carry_admin_info:
        maybe_carry_month_infos(conn, monthly_id, driver_id, year, month)
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


def update_balance_overrides_from_form(
    conn: sqlite3.Connection,
    monthly_data_id: int,
    previous_value_key: str = "previous_balance_manual",
    previous_touched_key: str = "previous_balance_touched",
    new_value_key: str = "new_balance_manual",
    new_touched_key: str = "new_balance_touched",
) -> bool:
    """Persist manual Alt/Neu only when the user actually edited the field.

    An edited-but-empty field clears the override and returns that balance to automatic mode.
    This prevents ordinary saves from accidentally freezing automatically calculated balances.
    """
    changed = False
    if request.form.get(previous_touched_key) == "1":
        value = parse_optional_hours(request.form.get(previous_value_key, ""))
        conn.execute(
            "UPDATE monthly_data SET previous_balance_override=?, updated_at=? WHERE id=?",
            (value, now_iso(), monthly_data_id),
        )
        changed = True
    if request.form.get(new_touched_key) == "1":
        value = parse_optional_hours(request.form.get(new_value_key, ""))
        conn.execute(
            "UPDATE monthly_data SET new_balance_override=?, updated_at=? WHERE id=?",
            (value, now_iso(), monthly_data_id),
        )
        changed = True
    return changed


def recalc_driver(conn: sqlite3.Connection, driver_id: int) -> None:
    driver = get_driver_by_db_id(conn, driver_id)
    if not driver:
        return
    balance = float(driver["starting_balance"] or 0)
    rows = conn.execute("SELECT * FROM monthly_data WHERE driver_id=? ORDER BY year, month, id", (driver_id,)).fetchall()
    for r in rows:
        diff = compute_difference(r["worked_hours"], r["payroll_hours"], 0, r["bonus_hours"], r["deduction_hours"], 0)

        # Alt normally comes from the previous month's effective Neu. A manual Alt override
        # deliberately starts this month from a corrected balance without rewriting the prior month.
        previous_override = row_get(r, "previous_balance_override", None)
        previous_balance = round(float(previous_override), 2) if previous_override is not None else round(balance, 2)

        calculated_new = round(previous_balance + diff, 2)
        new_override = row_get(r, "new_balance_override", None)
        new_balance = round(float(new_override), 2) if new_override is not None else calculated_new

        conn.execute(
            "UPDATE monthly_data SET difference_hours=?, previous_balance=?, new_balance=? WHERE id=?",
            (diff, previous_balance, new_balance, r["id"]),
        )
        # The effective Neu (manual or automatic) is always the basis for the following month.
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
    # Gesamtübersicht has many columns. Keep it readable on landscape A4 without clipping.
    compact = len(widths) >= 13
    font_size = 6.1 if compact else 7.7
    leading = 7.2 if compact else 9
    h_pad = 2.2 if compact else 5
    v_pad = 3.5 if compact else 7
    cell = ParagraphStyle("Cell", parent=styles["BodyText"], fontName="Helvetica", fontSize=font_size, leading=leading, textColor=colors.HexColor("#111827"), wordWrap="CJK")
    header = ParagraphStyle("HeaderCell", parent=styles["BodyText"], fontName="Helvetica-Bold", fontSize=font_size, leading=leading, alignment=1, textColor=colors.black, wordWrap="CJK")
    wrapped = [[Paragraph(str(c).replace("\n", "<br/>"), header if r == 0 else cell) for c in row] for r,row in enumerate(data)]
    table = Table(wrapped, colWidths=widths, repeatRows=1, splitByRow=1)
    table.setStyle(TableStyle([
        ("BACKGROUND",(0,0),(-1,0),colors.HexColor("#dfddd8")), ("FONTNAME",(0,0),(-1,0),"Helvetica-Bold"),
        ("ROWBACKGROUNDS",(0,1),(-1,-1),[colors.white, colors.HexColor("#f9fafb")]),
        ("BOX",(0,0),(-1,-1),0.8,colors.HexColor("#8f8b84")), ("INNERGRID",(0,0),(-1,-1),0.5,colors.HexColor("#b8b4ad")),
        ("VALIGN",(0,0),(-1,-1),"MIDDLE"), ("ALIGN",(1,0),(-1,-1),"CENTER"),
        ("LEFTPADDING",(0,0),(-1,-1),h_pad), ("RIGHTPADDING",(0,0),(-1,-1),h_pad), ("TOPPADDING",(0,0),(-1,-1),v_pad), ("BOTTOMPADDING",(0,0),(-1,-1),v_pad),
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
    elif len(headers) == 14:
        # Gesamtübersicht: all merged payroll + plus/minus data columns.
        col_widths = [0.12,0.12,0.08,0.055,0.055,0.05,0.05,0.05,0.05,0.065,0.14,0.055,0.055,0.055]
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
    """Export the complete merged admin view as a Gesamtübersicht PDF.

    It contains every meaningful data column from the combined
    "Stunden für Lohnabrechnung" view. The Action column is intentionally
    omitted because buttons/actions have no PDF representation.
    """
    groups = load_driver_groups(conn)
    normal_rows = conn.execute("""
        SELECT m.*, d.name, d.id AS d_id
        FROM monthly_data m
        JOIN drivers d ON d.id=m.driver_id
        WHERE m.year=? AND m.month=? AND d.is_active=1 AND COALESCE(d.is_disposition,0)=0
        ORDER BY COALESCE(NULLIF(d.display_order,0), d.id), d.name COLLATE NOCASE
    """, (year, month)).fetchall()

    def vacation_pdf(value: Any) -> str:
        raw = str(value or "").strip()
        if not raw:
            return "-"
        parts = [p.strip() for p in raw.splitlines() if p.strip()]
        shown = []
        for part in parts:
            try:
                v = vacation_display(part)
                shown.append((v + " Tage") if v else "-")
            except Exception:
                shown.append(part)
        return "\n".join(shown) or "-"

    def sick_pdf(value: Any) -> str:
        raw = str(value or "").strip()
        if not raw:
            return "-"
        parts = [p.strip() for p in raw.splitlines() if p.strip()]
        shown = []
        for part in parts:
            try:
                shown.append(sick_days_display(part) or part)
            except Exception:
                shown.append(part)
        return "\n".join(shown) or "-"

    def adjustments_pdf(row: Any) -> str:
        bonus = format_value_comment(safe_float(row_get(row, "bonus_hours", 0)), str(row_get(row, "bonus_comment", "") or ""), True)
        deduction = format_value_comment(safe_float(row_get(row, "deduction_hours", 0)), str(row_get(row, "deduction_comment", "") or ""), True)
        return f"Zuschüsse: {bonus}\nAbzüge: {deduction}"

    def overview_row(name: str, row: Any) -> List[str]:
        return [
            str(row_get(row, "admin_info", "") or "-").strip() or "-",
            str(row_get(row, "payroll_office_info", "") or "-").strip() or "-",
            name,
            fmt_hours(safe_float(row_get(row, "worked_hours", 0))),
            fmt_hours(safe_float(row_get(row, "payroll_hours", 0))),
            fmt_v_display(row_get(row, "v_note", ""), row_get(row, "v_enabled", 0), True),
            fmt_decimal_input(safe_float(row_get(row, "payroll_surcharge", 0))) or "-",
            fmt_decimal_input(safe_float(row_get(row, "fuel_voucher", 0))) or "-",
            vacation_pdf(row_get(row, "vacation_days", "")),
            sick_pdf(row_get(row, "sick_days", "")),
            adjustments_pdf(row),
            fmt_signed(safe_float(row_get(row, "previous_balance", 0))),
            fmt_signed(safe_float(row_get(row, "difference_hours", 0))),
            fmt_signed(safe_float(row_get(row, "new_balance", 0))),
        ]

    # Match the merged screen: every individual driver remains visible.
    pdf_rows = [overview_row(str(r["name"]), r) for r in normal_rows]

    # Driver groups are shown additionally as a Plus/Minus summary on the merged screen.
    for g in groups:
        summary = make_group_month_summary(conn, g, year, month)
        pdf_rows.append(overview_row(f"{g['name']} (Gruppe)", summary))

    if not pdf_rows:
        pdf_rows = [["-", "-", "Keine Einträge", "-", "-", "-", "-", "-", "-", "-", "-", "-", "-", "-"]]

    safe_name = secure_filename(f"{month:02d}_{MONATE[month]}_{year}_Gesamtuebersicht.pdf")
    path = EXPORT_DIR / str(year) / safe_name
    headers = [
        "Allgemeine Infos\nnur Admin",
        "Allgemeine Infos\nfür Lohnbüro",
        "Fahrer",
        "geleistete\nStunden",
        "Abrechnung",
        "V",
        "Zuschlag",
        "Tankgutschein",
        "Urlaub",
        "Krank",
        "Zuschüsse / Abzüge",
        "Alt",
        "Diff",
        "Neu",
    ]
    create_pdf_report(
        path,
        f"Gesamtübersicht - {MONATE[month]} {year}",
        "Vollständige Admin-Gesamtübersicht mit Lohnabrechnung und Plus/Minus",
        headers,
        pdf_rows,
        wide=True,
    )
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
        color_text(sick_days_pdf_display(row_get(r, "sick_days", "")) or "-", "#b42318"),
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
        ("payroll_hours","Stunden für Lohnabrechnung",url_for("admin_months")),
        ("shiftbase", "Shiftbase-Abgleich", url_for("admin_shiftbase_abgleich")),
        ("shiftbase_payroll", "Lohnzettel / Shiftbase-Dateien", url_for("admin_shiftbase_payroll")),
        ("exports","Export/Backup",url_for("admin_exports")), ("cleanup","Aufräumen",url_for("admin_cleanup")), ("portal","Fahrerportal",url_for("driver_login")),
    ]
    flashes = "".join(f'<div class="flash {"ok" if c=="ok" else "err"}">{m}</div>' for c,m in get_flashed_messages(with_categories=True))
    return render_template_string("""
    <!doctype html><html lang="de"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{{ title }}</title><style>{{ css }}</style></head><body>
    <div class="shell shell-{{ active }}"><aside class="side"><div class="brand">± Plus/Minus Cloud</div><div class="nav">{% for key,label,href in nav %}<a class="{{ 'active' if key==active else '' }}" href="{{ href }}">{{ label }}</a>{% endfor %}<a href="{{ url_for('admin_logout') }}">Logout Admin</a></div><p class="muted" style="color:#bdd2f4;margin-top:24px">Zentrale Cloud-Datenbank. Keine manuelle Synchronisation.</p></aside>
    <main class="main page-{{ active }}"><div class="top"><div><div class="title">{{ title }}</div><div class="subtitle">Änderungen werden direkt auf dem Server gespeichert und sind sofort auf allen PCs sichtbar.</div></div><span class="badge">Live Cloud</span></div>{{ flashes|safe }}{{ body|safe }}</main></div>
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
                        conn.commit(); flash("Fahrergruppe erstellt. In „Stunden für Lohnabrechnung“ erscheint zusätzlich eine gemeinsame Plus/Minus-Gruppenzeile.", "ok")
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
    <div class="card"><h2>Fahrer für Plus/Minus zusätzlich zusammenführen</h2><p class="muted">Die ausgewählten Fahrer bleiben in „Stunden für Lohnabrechnung“ einzeln sichtbar. Zusätzlich erscheint dort eine gemeinsame Gruppenzeile mit den zusammengerechneten Plus/Minus-Werten.</p><form method="post" class="grid grid-3"><input type="hidden" name="action" value="create_group"><div><label>Gruppenname</label><input name="group_name" placeholder="z.B. Alex und Jennifer"></div><div><label>Fahrer auswählen</label><select name="group_driver_ids" multiple size="6">{% for d in drivers %}<option value="{{ d['id'] }}">{{ d['name'] }}</option>{% endfor %}</select><div class="download-note">Mehrere auswählen mit Strg/Cmd oder Shift.</div></div><div style="align-self:end"><button class="primary">Gruppe erstellen</button></div></form>{% if groups %}<div class="adjustment-list"><h3>Aktive Gruppen</h3>{% for g in groups %}<div class="item-row"><b>{{ g.name }}</b><span class="muted">{{ g.members|map(attribute='name')|join(', ') }}</span><form method="post" onsubmit="return confirm('Gruppe wirklich löschen? Die Fahrer und Monatsdaten bleiben erhalten.')"><input type="hidden" name="action" value="delete_group"><input type="hidden" name="group_id" value="{{ g.group['id'] }}"><button class="small danger">Gruppe löschen</button></form></div>{% endfor %}</div>{% endif %}</div>
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
                            payroll_office_info = request.form.get(f"payroll_office_info_{suffix}", "").strip()
                            payroll_surcharge = parse_decimal(request.form.get(f"payroll_surcharge_{suffix}", "0"))
                            fuel_voucher = parse_decimal(request.form.get(f"fuel_voucher_{suffix}", "0"))
                            vacation_days = normalize_vacation_count(request.form.get(f"vacation_days_{suffix}", ""))
                            sick_days = normalize_day_ranges(request.form.get(f"sick_days_{suffix}", ""))
                            info_state = rolling_info_save_state(conn, mid, admin_info, payroll_office_info)
                            conn.execute("""
                                UPDATE monthly_data
                                SET worked_hours=?, payroll_hours=?, v_hours=0, v_note=?, v_enabled=?, admin_info=?, admin_info_carried=?,
                                    info_carry_initialized=1, payroll_office_info=?, payroll_office_info_carried=?,
                                    payroll_surcharge=?, fuel_voucher=?, payroll_carry_initialized=1,
                                    vacation_days=?, sick_days=?, updated_at=?
                                WHERE id=?
                            """, (worked, payroll, v_note, v_enabled, admin_info, info_state["admin_carried"], payroll_office_info, info_state["payroll_carried"], payroll_surcharge, fuel_voucher, vacation_days, sick_days, now_iso(), mid))
                            if info_state["admin_changed"]:
                                propagate_rolling_info_forward(conn, did2, year, month, "admin_info", admin_info)
                            if info_state["payroll_changed"]:
                                propagate_rolling_info_forward(conn, did2, year, month, "payroll_office_info", payroll_office_info)
                            sync_member_admin_info_to_group(conn, did2, year, month, admin_info)
                            update_balance_overrides_from_form(
                                conn, mid,
                                previous_value_key=f"previous_balance_manual_{suffix}",
                                previous_touched_key=f"previous_balance_touched_{suffix}",
                                new_value_key=f"new_balance_manual_{suffix}",
                                new_touched_key=f"new_balance_touched_{suffix}",
                            )
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
                    payroll_office_info = request.form.get("payroll_office_info", "").strip()
                    payroll_surcharge = parse_decimal(request.form.get("payroll_surcharge", "0"))
                    fuel_voucher = parse_decimal(request.form.get("fuel_voucher", "0"))
                    vacation_days = normalize_vacation_count(request.form.get("vacation_days", ""))
                    sick_days = normalize_day_ranges(request.form.get("sick_days", ""))
                    monthly_id = get_or_create_month_row(conn, did, year, month)
                    info_state = rolling_info_save_state(conn, monthly_id, admin_info, payroll_office_info)
                    conn.execute("""
                        UPDATE monthly_data
                        SET worked_hours=?, payroll_hours=?, v_hours=0, v_note=?, v_enabled=?, admin_info=?, admin_info_carried=?,
                            info_carry_initialized=1, payroll_office_info=?, payroll_office_info_carried=?,
                            payroll_surcharge=?, fuel_voucher=?, payroll_carry_initialized=1,
                            vacation_days=?, sick_days=?, updated_at=?
                        WHERE id=?
                    """, (worked, payroll, v_note, v_enabled, admin_info, info_state["admin_carried"], payroll_office_info, info_state["payroll_carried"], payroll_surcharge, fuel_voucher, vacation_days, sick_days, now_iso(), monthly_id))
                    if info_state["admin_changed"]:
                        propagate_rolling_info_forward(conn, did, year, month, "admin_info", admin_info)
                    if info_state["payroll_changed"]:
                        propagate_rolling_info_forward(conn, did, year, month, "payroll_office_info", payroll_office_info)
                    sync_member_admin_info_to_group(conn, did, year, month, admin_info)
                    update_balance_overrides_from_form(conn, monthly_id)

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
                    flash("Stunden und Plus/Minus-Werte gespeichert; Fahrer-PDF automatisch aktualisiert.", "ok")

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
        # In der zusammengefuehrten Ansicht bleiben ALLE einzelnen Fahrer sichtbar,
        # damit keine Lohnabrechnungsfelder durch eine Plus/Minus-Gruppe verloren gehen.
        # Gruppen werden zusaetzlich als reine Plus/Minus-Zusammenfassung angehaengt.
        display_drivers: List[Dict[str, Any]] = []
        for d in drivers:
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
        fuel_voucher_count = sum(
            1
            for d in display_drivers
            if not d.get("is_group")
            and abs(safe_float(row_get(rows.get(int(d["id"])), "fuel_voucher", 0))) > 0.0001
        )

    body = render_template_string("""
    <div class="card combined-toolbar">
      <div class="actions" style="justify-content:space-between;align-items:flex-end">
        <form method="get" class="actions" id="month-filter-form">
          <div><label>Jahr</label><input name="year" value="{{ year }}" onchange="this.form.submit()"></div>
          <div><label>Monat</label><select name="month" onchange="this.form.submit()">{% for n,m in months.items() %}<option value="{{ n }}" {% if n==month %}selected{% endif %}>{{ m }}</option>{% endfor %}</select></div>
          <noscript><button class="primary">Anzeigen</button></noscript>
          <a class="btn" href="{{ url_for('download_payroll_hours_export', year=year, month=month) }}">Lohnbüro-PDF herunterladen</a>
          <a class="btn" href="{{ url_for('download_month_export', year=year, month=month) }}">Gesamtübersicht-PDF herunterladen</a>
          <button class="primary" type="submit" form="all-months-form" {% if not editable %}disabled title="{{ locked_note }}"{% endif %}>Alle Einträge speichern</button>
          <div class="download-note">Alle bisherigen Felder aus „Stunden für Lohnabrechnung“ und „Plus/Minus Stunden“ sind hier in einer Ansicht zusammengeführt.</div>
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
    <div class="card combined-card"><h2>Stunden für Lohnabrechnung – {{ months[month] }} {{ year }}</h2>
      <p class="muted">Lohnabrechnung und Plus/Minus sind jetzt vollständig in einer Tabelle. Diff wird automatisch berechnet; Alt und Neu können bei Einzel-Fahrern weiterhin manuell korrigiert werden.</p>
      <form method="post" id="all-months-form"><input type="hidden" name="action" value="save_all"><input type="hidden" name="year" value="{{ year }}"><input type="hidden" name="month" value="{{ month }}"></form>
      <form method="post" id="global-v-form-months"><input type="hidden" name="action" value="set_global_v"><input type="hidden" name="year" value="{{ year }}"><input type="hidden" name="month" value="{{ month }}"><input type="hidden" id="global-v-value-months" name="global_v_enabled" value="{{ 1 if global_v_all else 0 }}"></form>
      <div class="table-wrap mobile-cards combined-wrap"><table class="months-table payroll-table merged-payroll-table">
      <thead><tr>
        <th class="col-admin">Allgemeine Infos<br><span class="muted">nur Admin</span></th>
        <th class="col-pay-info">Allgemeine Infos für Lohnbüro</th>
        <th class="col-driver">Fahrer</th>
        <th class="col-hours">geleistete Stunden</th>
        <th class="col-payroll">Abrechnung</th>
        <th class="col-v">V<br><label class="global-v-toggle" title="Aktiv-Markierung für alle Fahrer"><input type="checkbox" {% if global_v_all %}checked{% endif %} {% if not editable %}disabled{% endif %} onchange="document.getElementById('global-v-value-months').value=this.checked?'1':'0';document.getElementById('global-v-form-months').submit()"> alle aktiv</label></th>
        <th class="col-pay-num">Zuschlag</th>
        <th class="col-pay-num" id="fuel-voucher-count-head">Tankgutschein ={{ fuel_voucher_count }}</th>
        <th class="col-days">Urlaub</th>
        <th class="col-sick">Krank</th>
        <th class="col-adjust">Zuschüsse / Abzüge</th>
        <th class="col-balance">Alt</th>
        <th class="col-small">Diff</th>
        <th class="col-balance">Neu</th>
        <th class="col-action">Aktion</th>
      </tr></thead><tbody>
      {% for d in drivers %}
      {% set r = rows.get(d['id']) %}
      {% set items = adjustments.get(d['id'], []) %}
      <tr class="driver-row {{ 'row-alt' if loop.index0 % 2 else 'row-base' }}">
        {% if d['is_group'] %}
        <td class="admin-info" data-label="Allgemeine Infos"><textarea form="save-{{ d['form_id'] }}" name="admin_info" placeholder="Interne Infos, nur für Admin sichtbar">{{ r['admin_info'] if r else '' }}</textarea><input type="hidden" form="all-months-form" name="row_driver_id_{{ d['form_id'] }}" value="{{ d['id'] }}"><input type="hidden" form="all-months-form" name="admin_info_{{ d['form_id'] }}" value="{{ r['admin_info'] if r else '' }}" class="all-copy-admin-{{ d['form_id'] }}"><input type="hidden" form="all-months-form" name="worked_hours_{{ d['form_id'] }}" value="{{ r['worked_hours'] if r else '' }}" class="all-copy-worked-{{ d['form_id'] }}"><div class="download-note">Gruppe: {{ d['member_names'] }}</div></td>
        <td data-label="Allgemeine Infos für Lohnbüro"><textarea readonly title="Gruppenübersicht; die einzelnen Fahrerwerte bleiben oben separat editierbar">{{ row_get(r, 'payroll_office_info', '') if r else '' }}</textarea></td>
        <td data-label="Fahrer"><b class="driver-name {{ employment_class(row_get(d, 'employment_type', '')) }}">{{ d['name'] }}</b><div class="download-note">Zusätzliche Plus/Minus-Gruppenübersicht</div>{% if d.member_preview %}<div class="group-member-preview"><b>Einzelvorschau</b><table><tr><th>Fahrer</th><th>Std.</th><th>Abr.</th><th>V</th><th>Diff</th></tr>{% for p in d.member_preview %}<tr><td class="driver-name {{ employment_class(p.employment_type) }}">{{ p.name }}</td><td>{{ fmt_hours(p.worked_hours) }}</td><td>{{ fmt_hours(p.payroll_hours) }}</td><td>{{ p.v_note or '-' }}</td><td class="{{ signed_class(p.difference_hours) }}">{{ fmt_signed(p.difference_hours) }}</td></tr>{% endfor %}</table></div>{% endif %}</td>
        <td data-label="geleistete Stunden"><form method="post" enctype="multipart/form-data" id="save-{{ d['form_id'] }}"><input type="hidden" name="driver_id" value="{{ d['id'] }}"><input type="hidden" name="year" value="{{ year }}"><input type="hidden" name="month" value="{{ month }}"><input name="worked_hours" value="{{ r['worked_hours'] if r else '' }}"><div class="group-worked-note">Gruppenwert für Plus/Minus.</div></form></td>
        <td data-label="Abrechnung"><input readonly value="{{ r['payroll_hours'] if r else '' }}"></td>
        {% set v_enabled = row_v_enabled(r) %}
        <td data-label="V"><input class="v-markable {{ 'v-disabled' if not v_enabled else '' }}" readonly value="{{ fmt_v_input(row_get(r, 'v_note', '')) if r else '' }}" placeholder="Notiz"><input type="hidden" form="save-{{ d['form_id'] }}" name="v_enabled" value="0"><label class="v-toggle" title="Nur Aktiv-Markierung; V wird nie berechnet"><input class="v-enabled-toggle" form="save-{{ d['form_id'] }}" type="checkbox" name="v_enabled" value="1" {% if v_enabled %}checked{% endif %}> aktiv</label><input type="hidden" form="all-months-form" name="v_enabled_{{ d['form_id'] }}" value="{{ 1 if v_enabled else 0 }}" class="all-copy-v-enabled-{{ d['form_id'] }}"><div class="v-disabled-note">nur Notiz · ohne Berechnung</div></td>
        <td data-label="Zuschlag"><input readonly value="{{ fmt_decimal_input(row_get(r, 'payroll_surcharge', 0)) if r else '' }}"></td>
        <td data-label="Tankgutschein"><input readonly value="{{ fmt_decimal_input(row_get(r, 'fuel_voucher', 0)) if r else '' }}"></td>
        <td data-label="Urlaub"><div class="readonly-summary">{{ row_get(r, 'vacation_days', '') if r else '-' }}</div></td>
        <td data-label="Krank"><div class="readonly-summary">{{ row_get(r, 'sick_days', '') if r else '-' }}</div></td>
        <td data-label="Zuschüsse / Abzüge"><div class="group-mini-form"><select form="save-{{ d['form_id'] }}" name="kind"><option value="deduction">Abzug</option><option value="bonus">Zuschuss</option></select><input form="save-{{ d['form_id'] }}" name="item_hours" placeholder="Std."><input form="save-{{ d['form_id'] }}" name="item_note" placeholder="Grund, z.B. Auto dreckig"><label class="dropzone">Bild/Datei<input form="save-{{ d['form_id'] }}" type="file" name="item_file" accept="image/*,.pdf"></label><button form="save-{{ d['form_id'] }}" name="action" value="add_adjustment" class="small primary">Hinzufügen</button></div>
          {% if r %}<div class="sum-box">Summe Zuschüsse: <span class="pos">{{ fmt_hours(r['bonus_hours']) }}</span><br>Summe Abzüge: <span class="neg">{{ fmt_hours(r['deduction_hours']) }}</span></div>{% endif %}
          <div class="adjustment-list">{% if items %}{% for it in items %}<div class="item-row"><span class="{{ 'pos' if it['kind']=='bonus' else 'neg' }}">{{ '+' if it['kind']=='bonus' else '-' }}{{ fmt_hours(it['hours']) }}</span><span>{{ it['note'] }}</span>{% if it.get('is_group_adj') %}{% for f in group_adjustment_files.get(it['id'], []) %}<span class="file-pill">📎 {{ f['original_filename'] or f['filename'] }}<form method="post"><input type="hidden" name="action" value="delete_adjustment_file"><input type="hidden" name="driver_id" value="{{ d['id'] }}"><input type="hidden" name="file_id" value="{{ f['id'] }}"><button class="file-remove danger" onclick="return confirm('Bild/Datei entfernen?')">entfernen</button></form></span>{% endfor %}<form method="post"><input type="hidden" name="action" value="delete_adjustment"><input type="hidden" name="driver_id" value="{{ d['id'] }}"><input type="hidden" name="item_id" value="{{ it['id'] }}"><button class="small danger" onclick="return confirm('Position löschen?')">x</button></form>{% endif %}</div>{% endfor %}{% else %}<div class="muted">Keine Positionen</div>{% endif %}</div>
        </td>
        <td data-label="Alt" title="Gruppensumme aus den einzelnen Fahrerständen">{{ fmt_signed(r['previous_balance']) if r else '-' }}</td>
        <td data-label="Diff" class="{{ signed_class(r['difference_hours']) if r else '' }}">{{ fmt_signed(r['difference_hours']) if r else '-' }}</td>
        <td data-label="Neu" class="{{ signed_class(r['new_balance']) if r else '' }}" title="Gruppensumme aus den einzelnen Fahrerständen">{{ fmt_signed(r['new_balance']) if r else '-' }}</td>
        <td data-label="Aktion" class="actions compact-save"><button form="save-{{ d['form_id'] }}" name="action" value="save" class="small primary">Speichern</button><span class="badge">Gruppe</span></td>
        {% else %}
        <td class="admin-info" data-label="Allgemeine Infos"><textarea class="{{ 'carried' if r and r['admin_info_carried'] else '' }}" form="save-{{ d['form_id'] }}" name="admin_info" placeholder="Interne Infos, nur für Admin sichtbar">{{ r['admin_info'] if r else '' }}</textarea><input type="hidden" form="all-months-form" name="row_driver_id_{{ d['form_id'] }}" value="{{ d['id'] }}"><input type="hidden" form="all-months-form" name="admin_info_{{ d['form_id'] }}" value="{{ r['admin_info'] if r else '' }}" class="all-copy-admin-{{ d['form_id'] }}"><input type="hidden" form="all-months-form" name="worked_hours_{{ d['form_id'] }}" value="{{ r['worked_hours'] if r else '' }}" class="all-copy-worked-{{ d['form_id'] }}">{% if r and r['admin_info_carried'] and (r['admin_info'] or '').strip() %}<div class="download-note">aus Vormonat übernommen</div>{% endif %}</td>
        <td data-label="Allgemeine Infos für Lohnbüro"><textarea form="save-{{ d['form_id'] }}" name="payroll_office_info" placeholder="Text für Lohnbüro-PDF">{{ row_get(r, 'payroll_office_info', '') if r else '' }}</textarea><input type="hidden" form="all-months-form" name="payroll_office_info_{{ d['form_id'] }}" value="{{ row_get(r, 'payroll_office_info', '') if r else '' }}" class="all-copy-payroll-office-{{ d['form_id'] }}"></td>
        <td data-label="Fahrer"><b class="driver-name {{ employment_class(row_get(d, 'employment_type', '')) }}">{{ d['name'] }}</b></td>
        <td data-label="geleistete Stunden"><form method="post" enctype="multipart/form-data" id="save-{{ d['form_id'] }}"><input type="hidden" name="driver_id" value="{{ d['id'] }}"><input type="hidden" name="year" value="{{ year }}"><input type="hidden" name="month" value="{{ month }}"><input name="worked_hours" value="{{ r['worked_hours'] if r else '' }}"></form></td>
        <td data-label="Abrechnung"><input form="save-{{ d['form_id'] }}" name="payroll_hours" value="{{ r['payroll_hours'] if r else '' }}"><input type="hidden" form="all-months-form" name="payroll_hours_{{ d['form_id'] }}" value="{{ r['payroll_hours'] if r else '' }}" class="all-copy-payroll-{{ d['form_id'] }}"></td>
        {% set v_enabled = row_v_enabled(r) %}
        <td data-label="V"><input class="v-input v-markable {{ 'v-disabled' if not v_enabled else '' }}" form="save-{{ d['form_id'] }}" name="v_note" value="{{ fmt_v_input(row_get(r, 'v_note', '')) if r else '' }}" placeholder="Notiz"><input type="hidden" form="all-months-form" name="v_note_{{ d['form_id'] }}" value="{{ fmt_v_input(row_get(r, 'v_note', '')) if r else '' }}" class="all-copy-v-{{ d['form_id'] }}"><input type="hidden" form="save-{{ d['form_id'] }}" name="v_enabled" value="0"><label class="v-toggle" title="Nur Aktiv-Markierung; V wird nie berechnet"><input class="v-enabled-toggle" form="save-{{ d['form_id'] }}" type="checkbox" name="v_enabled" value="1" {% if v_enabled %}checked{% endif %}> aktiv</label><input type="hidden" form="all-months-form" name="v_enabled_{{ d['form_id'] }}" value="{{ 1 if v_enabled else 0 }}" class="all-copy-v-enabled-{{ d['form_id'] }}"><div class="v-disabled-note">nur Notiz · ohne Berechnung</div></td>
        <td data-label="Zuschlag"><input form="save-{{ d['form_id'] }}" name="payroll_surcharge" value="{{ fmt_decimal_input(row_get(r, 'payroll_surcharge', 0)) if r else '' }}"><input type="hidden" form="all-months-form" name="payroll_surcharge_{{ d['form_id'] }}" value="{{ fmt_decimal_input(row_get(r, 'payroll_surcharge', 0)) if r else '' }}" class="all-copy-surcharge-{{ d['form_id'] }}"></td>
        <td data-label="Tankgutschein"><input class="fuel-voucher-input" form="save-{{ d['form_id'] }}" name="fuel_voucher" value="{{ fmt_decimal_input(row_get(r, 'fuel_voucher', 0)) if r else '' }}"><input type="hidden" form="all-months-form" name="fuel_voucher_{{ d['form_id'] }}" value="{{ fmt_decimal_input(row_get(r, 'fuel_voucher', 0)) if r else '' }}" class="all-copy-fuel-{{ d['form_id'] }}"></td>
        <td data-label="Urlaub" class="days-vacation"><div class="vacation-input-wrap"><input form="save-{{ d['form_id'] }}" name="vacation_days" inputmode="numeric" pattern="[0-9]*" value="{{ vacation_display(row_get(r, 'vacation_days', '')) if r else '' }}"><span class="suffix">Tage</span></div><input type="hidden" form="all-months-form" name="vacation_days_{{ d['form_id'] }}" value="{{ vacation_display(row_get(r, 'vacation_days', '')) if r else '' }}" class="all-copy-vacation-{{ d['form_id'] }}"></td>
        <td data-label="Krank" class="days-sick"><input type="hidden" class="sick-days-input" form="save-{{ d['form_id'] }}" name="sick_days" value="{{ row_get(r, 'sick_days', '') if r else '' }}"><input type="hidden" form="all-months-form" name="sick_days_{{ d['form_id'] }}" value="{{ row_get(r, 'sick_days', '') if r else '' }}" class="all-copy-sick-{{ d['form_id'] }}"><button type="button" class="sick-calendar-open" data-form="save-{{ d['form_id'] }}" data-driver-name="{{ d['name'] }}">Kalender öffnen</button><div class="sick-days-overview">{% if r and row_get(r, 'sick_days', '') %}{{ row_get(r, 'sick_days', '') }} = <span class="sick-days-total">{{ sick_days_count(row_get(r, 'sick_days', '')) }} Tage</span>{% else %}Keine Kranktage{% endif %}</div></td>
        <td data-label="Zuschüsse / Abzüge"><div class="mini-form"><select form="save-{{ d['form_id'] }}" name="kind"><option value="deduction">Abzug</option><option value="bonus">Zuschuss</option></select><input form="save-{{ d['form_id'] }}" name="item_hours" placeholder="Std."><input form="save-{{ d['form_id'] }}" name="item_note" placeholder="Grund, z.B. Auto dreckig"><label class="dropzone">Bild/Datei<input form="save-{{ d['form_id'] }}" type="file" name="item_file" accept="image/*,.pdf"></label><button form="save-{{ d['form_id'] }}" name="action" value="add_adjustment" class="small primary">Hinzufügen</button></div>
          {% if r %}<div class="sum-box">Summe Zuschüsse: <span class="pos">{{ fmt_hours(r['bonus_hours']) }}</span><br>Summe Abzüge: <span class="neg">{{ fmt_hours(r['deduction_hours']) }}</span></div>{% endif %}
          <div class="adjustment-list">{% if items %}{% for it in items %}<div class="item-row"><span class="{{ 'pos' if it['kind']=='bonus' else 'neg' }}">{{ '+' if it['kind']=='bonus' else '-' }}{{ fmt_hours(it['hours']) }}</span><span>{{ it['note'] }}</span>{% for f in adjustment_files.get(it['id'], []) %}<span class="file-pill">📎 {{ f['original_filename'] or f['filename'] }}<form method="post"><input type="hidden" name="action" value="delete_adjustment_file"><input type="hidden" name="driver_id" value="{{ d['id'] }}"><input type="hidden" name="file_id" value="{{ f['id'] }}"><button class="file-remove danger" onclick="return confirm('Bild/Datei entfernen?')">entfernen</button></form></span>{% endfor %}<form method="post"><input type="hidden" name="action" value="delete_adjustment"><input type="hidden" name="driver_id" value="{{ d['id'] }}"><input type="hidden" name="item_id" value="{{ it['id'] }}"><button class="small danger" onclick="return confirm('Position löschen?')">x</button></form></div>{% endfor %}{% else %}<div class="muted">Keine Positionen</div>{% endif %}</div>
        </td>
        <td data-label="Alt"><input class="balance-input balance-previous" form="save-{{ d['form_id'] }}" name="previous_balance_manual" value="{{ fmt_balance_input(r['previous_balance']) if r else '' }}" title="Ändern = manueller Wert. Feld leeren und speichern = wieder automatisch."><input type="hidden" form="save-{{ d['form_id'] }}" name="previous_balance_touched" value="0" class="balance-previous-touched"><input type="hidden" form="all-months-form" name="previous_balance_manual_{{ d['form_id'] }}" value="{{ fmt_balance_input(r['previous_balance']) if r else '' }}" class="all-copy-previous-balance-{{ d['form_id'] }}"><input type="hidden" form="all-months-form" name="previous_balance_touched_{{ d['form_id'] }}" value="0" class="all-copy-previous-touched-{{ d['form_id'] }}"><div class="balance-mode {{ 'manual' if r and row_get(r, 'previous_balance_override', None) is not none else '' }}">{{ 'manuell' if r and row_get(r, 'previous_balance_override', None) is not none else 'auto' }}</div></td>
        <td data-label="Diff" class="{{ signed_class(r['difference_hours']) if r else '' }}">{{ fmt_signed(r['difference_hours']) if r else '-' }}</td>
        <td data-label="Neu"><input class="balance-input balance-new {{ signed_class(r['new_balance']) if r else '' }}" form="save-{{ d['form_id'] }}" name="new_balance_manual" value="{{ fmt_balance_input(r['new_balance']) if r else '' }}" title="Ändern = manueller Wert. Dieser Wert wird in den nächsten Monat übernommen. Feld leeren = wieder automatisch."><input type="hidden" form="save-{{ d['form_id'] }}" name="new_balance_touched" value="0" class="balance-new-touched"><input type="hidden" form="all-months-form" name="new_balance_manual_{{ d['form_id'] }}" value="{{ fmt_balance_input(r['new_balance']) if r else '' }}" class="all-copy-new-balance-{{ d['form_id'] }}"><input type="hidden" form="all-months-form" name="new_balance_touched_{{ d['form_id'] }}" value="0" class="all-copy-new-touched-{{ d['form_id'] }}"><div class="balance-mode {{ 'manual' if r and row_get(r, 'new_balance_override', None) is not none else '' }}">{{ 'manuell' if r and row_get(r, 'new_balance_override', None) is not none else 'auto' }}</div></td>
        <td data-label="Aktion" class="actions compact-save"><button form="save-{{ d['form_id'] }}" name="action" value="save" class="small primary">Speichern</button>{% if r %}<form method="post" onsubmit="return confirm('Datensatz löschen?')"><input type="hidden" name="action" value="delete"><input type="hidden" name="driver_id" value="{{ d['id'] }}"><button class="small danger delete-month-btn">Monat löschen</button></form>{% endif %}</td>
        {% endif %}
      </tr>
      {% endfor %}
      </tbody></table></div></div>
    <div id="sick-calendar-modal" class="sick-calendar-modal" aria-hidden="true"><div class="sick-calendar-panel"><div class="sick-calendar-head"><div><h3 style="margin:0">Kranktage auswählen</h3><div class="muted" id="sick-calendar-title"></div></div><button type="button" class="small" id="sick-calendar-close" style="width:auto">Schließen</button></div><div class="sick-calendar-week"><div>Mo</div><div>Di</div><div>Mi</div><div>Do</div><div>Fr</div><div>Sa</div><div>So</div></div><div id="sick-calendar-grid" class="sick-calendar-grid"></div><div class="sick-calendar-hint">Einzelne Tage anklicken oder mit gedrückter Maustaste / Finger über mehrere Tage ziehen. Erneutes Markieren entfernt Tage.</div><div class="actions" style="justify-content:flex-end"><button type="button" class="small" id="sick-calendar-cancel">Abbrechen</button><button type="button" class="small primary" id="sick-calendar-save">Speichern</button></div></div></div>
    <script>
    {% if not editable %}
    document.querySelectorAll('.merged-payroll-table input, .merged-payroll-table textarea, .merged-payroll-table select, .merged-payroll-table button, button[form="all-months-form"]').forEach(function(el){
      if(el.type !== 'hidden'){ el.disabled = true; el.title = '{{ locked_note }}'; }
    });
    {% endif %}

    document.querySelectorAll('.dropzone input[type="file"]').forEach(function(input){
      var zone = input.closest('.dropzone');
      var defaultText = 'Bild/Datei hier ablegen';
      function setZoneText(text){ Array.from(zone.childNodes).forEach(function(node){ if(node.nodeType === Node.TEXT_NODE){ node.nodeValue = text; } }); }
      setZoneText(defaultText);
      input.addEventListener('change', function(){ setZoneText(input.files.length ? input.files[0].name : defaultText); });
      ['dragenter','dragover'].forEach(function(ev){ zone.addEventListener(ev, function(e){ e.preventDefault(); e.stopPropagation(); zone.classList.add('dragover'); if(e.dataTransfer){ e.dataTransfer.dropEffect='copy'; } }); });
      ['dragleave','dragend'].forEach(function(ev){ zone.addEventListener(ev, function(e){ e.preventDefault(); e.stopPropagation(); zone.classList.remove('dragover'); }); });
      zone.addEventListener('drop', function(e){ e.preventDefault(); e.stopPropagation(); zone.classList.remove('dragover'); if(e.dataTransfer && e.dataTransfer.files && e.dataTransfer.files.length){ input.files=e.dataTransfer.files; setZoneText(e.dataTransfer.files[0].name); } });
    });

    function refreshFuelVoucherCount(){
      var head=document.getElementById('fuel-voucher-count-head');
      if(!head){return;}
      var count=0;
      document.querySelectorAll('.fuel-voucher-input').forEach(function(input){
        if((input.value || '').trim() !== ''){ count += 1; }
      });
      head.textContent='Tankgutschein =' + count;
    }
    document.querySelectorAll('.fuel-voucher-input').forEach(function(input){ input.addEventListener('input', refreshFuelVoucherCount); });
    refreshFuelVoucherCount();

    function refreshVEnabledState(row){ var cb=row.querySelector('.v-enabled-toggle'); if(!cb){return;} var input=row.querySelector('.v-markable'); if(input){input.classList.toggle('v-disabled', !cb.checked);} }
    document.querySelectorAll('.v-enabled-toggle').forEach(function(cb){ var row=cb.closest('tr'); cb.addEventListener('change',function(){refreshVEnabledState(row);}); refreshVEnabledState(row); });

    (function(){
      var modal=document.getElementById('sick-calendar-modal'), grid=document.getElementById('sick-calendar-grid'), title=document.getElementById('sick-calendar-title');
      if(!modal||!grid) return;
      var activeInput=null, activeForm=null, selected=new Set(), dragging=false, dragState=true;
      var year={{ year }}, month={{ month }};
      function parseRanges(raw){ var out=new Set(); (raw||'').split(',').map(function(x){return x.trim();}).filter(Boolean).forEach(function(part){ var bits=part.split('-').map(function(x){return parseInt(x.trim(),10);}); if(bits.length===2&&Number.isFinite(bits[0])&&Number.isFinite(bits[1])){ for(var d=bits[0];d<=bits[1];d++) out.add(d); } else if(Number.isFinite(bits[0])) out.add(bits[0]); }); return out; }
      function formatRanges(set){ var a=Array.from(set).sort(function(x,y){return x-y;}); if(!a.length) return ''; var parts=[], start=a[0], prev=a[0]; for(var i=1;i<=a.length;i++){ var cur=a[i]; if(cur===prev+1){ prev=cur; continue; } parts.push(start===prev?String(start):(start+'-'+prev)); start=cur; prev=cur; } return parts.join(', '); }
      function paint(btn,day,state){ if(state) selected.add(day); else selected.delete(day); btn.classList.toggle('selected',state); }
      function build(){ grid.innerHTML=''; var first=new Date(year,month-1,1), days=new Date(year,month,0).getDate(), blanks=(first.getDay()+6)%7; for(var b=0;b<blanks;b++){ var blank=document.createElement('button'); blank.type='button'; blank.className='sick-day blank'; blank.tabIndex=-1; grid.appendChild(blank); } for(let day=1;day<=days;day++){ let btn=document.createElement('button'); btn.type='button'; btn.className='sick-day'+(selected.has(day)?' selected':''); btn.textContent=day; btn.addEventListener('pointerdown',function(e){ dragging=true; dragState=!selected.has(day); paint(btn,day,dragState); e.preventDefault(); }); btn.addEventListener('pointerenter',function(e){ if(dragging){ paint(btn,day,dragState); e.preventDefault(); } }); btn.addEventListener('click',function(e){e.preventDefault();}); grid.appendChild(btn); } }
      function close(){ modal.classList.remove('open'); modal.setAttribute('aria-hidden','true'); dragging=false; }
      document.addEventListener('pointerup',function(){dragging=false;});
      document.querySelectorAll('.sick-calendar-open').forEach(function(open){ open.addEventListener('click',function(){ activeForm=document.getElementById(open.dataset.form); activeInput=document.querySelector('input.sick-days-input[form="'+open.dataset.form+'"]'); selected=parseRanges(activeInput?activeInput.value:''); title.textContent=(open.dataset.driverName||'')+' · {{ months[month] }} {{ year }}'; build(); modal.classList.add('open'); modal.setAttribute('aria-hidden','false'); }); });
      document.getElementById('sick-calendar-close').addEventListener('click',close); document.getElementById('sick-calendar-cancel').addEventListener('click',close); modal.addEventListener('click',function(e){if(e.target===modal)close();});
      document.getElementById('sick-calendar-save').addEventListener('click',function(){ if(!activeInput||!activeForm) return close(); activeInput.value=formatRanges(selected); var saveButton=activeForm.querySelector('button[name="action"][value="save"]') || document.querySelector('button[form="'+activeForm.id+'"][name="action"][value="save"]'); close(); if(saveButton){ activeForm.requestSubmit(saveButton); } });
    })();

    document.querySelectorAll('tr.driver-row').forEach(function(row){
      var fidInput=row.querySelector('form[id^="save-"] input[name="driver_id"]');
      if(!fidInput) return;
      var formId=fidInput.closest('form').id.replace('save-','');
      function copy(selector, targetClass){ var el=row.querySelector(selector); var hidden=document.querySelector('.'+targetClass+CSS.escape(formId)); if(hidden&&el){hidden.value=el.value;} }
      function sync(){
        copy('textarea[name="admin_info"]','all-copy-admin-');
        copy('textarea[name="payroll_office_info"]','all-copy-payroll-office-');
        copy('input[name="worked_hours"]','all-copy-worked-');
        copy('input[name="payroll_hours"]','all-copy-payroll-');
        copy('input[name="v_note"]','all-copy-v-');
        copy('input[name="payroll_surcharge"]','all-copy-surcharge-');
        copy('input[name="fuel_voucher"]','all-copy-fuel-');
        copy('input[name="vacation_days"]','all-copy-vacation-');
        copy('input[name="sick_days"]','all-copy-sick-');
        copy('input[name="previous_balance_manual"]','all-copy-previous-balance-');
        copy('input[name="new_balance_manual"]','all-copy-new-balance-');
        var vEnabled=row.querySelector('.v-enabled-toggle'); var hve=document.querySelector('.all-copy-v-enabled-'+CSS.escape(formId)); if(hve&&vEnabled){hve.value=vEnabled.checked?'1':'0';}
      }
      row.addEventListener('input',function(e){
        if(e.target&&e.target.classList.contains('balance-previous')){ var own=row.querySelector('.balance-previous-touched'); if(own)own.value='1'; var all=document.querySelector('.all-copy-previous-touched-'+CSS.escape(formId)); if(all)all.value='1'; }
        if(e.target&&e.target.classList.contains('balance-new')){ var ownNew=row.querySelector('.balance-new-touched'); if(ownNew)ownNew.value='1'; var allNew=document.querySelector('.all-copy-new-touched-'+CSS.escape(formId)); if(allNew)allNew.value='1'; }
        sync();
      });
      row.addEventListener('change',sync);
      sync();
    });
    </script>
    """, year=year, month=month, months=MONATE, month_released=month_released, editable=editable, locked_note=locked_note, drivers=drivers, rows=rows, adjustments=adjustments, adjustment_files=adjustment_files, group_adjustment_files=locals().get("group_adjustment_files", {}), fmt_signed=fmt_signed, fmt_hours=fmt_hours, fmt_v_input=fmt_v_input, fmt_decimal_input=fmt_decimal_input, fmt_balance_input=fmt_balance_input, signed_class=signed_class, row_v_enabled=row_v_enabled, row_get=row_get, employment_class=employment_class, vacation_display=vacation_display, sick_days_display=sick_days_display, sick_days_count=sick_days_count, global_v_all=global_v_all, fuel_voucher_count=fuel_voucher_count)
    return base_page("Stunden für Lohnabrechnung", body, "payroll_hours")


@app.route("/admin/import-pdf", methods=["GET","POST"])
@admin_login_required
def admin_import_pdf():
    flash("Der Lohn-PDF-Import wurde deaktiviert. Bitte V direkt in der Monatsübersicht eintragen.", "ok")
    return redirect(url_for("admin_months"))



@app.route("/admin/payroll-hours", methods=["GET","POST"])
@admin_login_required
def admin_payroll_hours():
    # Alte URL bleibt kompatibel, verwendet aber exakt dieselbe zusammengefuehrte Ansicht.
    return admin_months()

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
    <div class="card"><h2>Gesamtübersicht-PDFs</h2>{% if month_rows %}<div class="driver-grid">{% for r in month_rows %}<a class="month-card" href="{{ url_for('download_month_export', year=r['year'], month=r['month']) }}"><strong>{{ months[r['month']] }} {{ r['year'] }}</strong>Gesamtübersicht-PDF herunterladen<br><span class="muted">{{ r['filled_rows'] }} Eintrag/Einträge</span></a>{% endfor %}</div>{% else %}<p class="muted">Noch keine echten Monatsdaten vorhanden.</p>{% endif %}</div>
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


# =================== Shiftbase-Lohnabgleich: Lesen, Vorschau, geprüfte Einzelkorrekturen ===================
# API-Zugang wird ausschliesslich per Umgebungsvariablen konfiguriert.
# Schreibzugriff ausschließlich nach Admin-Belegbestätigung, Mitarbeiter-/Monatsprüfung und erneuter GET-Verifikation.
# Herstellerdokumentation: https://developer.shiftbase.com/

from collections import defaultdict
from datetime import date as shiftbase_date, timedelta as shiftbase_timedelta
from datetime import datetime as _sb_datetime, timedelta as _sb_timedelta, timezone as _sb_timezone
from decimal import Decimal, InvalidOperation
from html import escape as shiftbase_escape
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urlsplit, quote
import unicodedata
from urllib.request import Request, build_opener, HTTPRedirectHandler
import hmac
import secrets

# Reuse TLS connections during large transfers if urllib3 is present on Render.
# Safe fallback is the existing urllib transport; no extra package is required.
try:
    import urllib3 as _sb_urllib3
except ImportError:
    _sb_urllib3 = None

import threading as _sb_threading
_SB_HTTP_POOL = None
_SB_HTTP_POOL_LOCK = _sb_threading.Lock()
_SB_PREVIEW_NEIGHBORS = ContextVar('sb_preview_neighbors', default=None)


def _sb_http_request(method, url, headers, timeout, payload=None, max_bytes=5_000_000):
    """One HTTP operation, no redirects or automatic retries (especially PUT).

    A per-process urllib3 connection pool avoids a fresh TLS handshake for
    every timesheet. HTTPS certificate and hostname validation stay enabled.
    If urllib3 isn't installed, keep the previous urllib behavior.
    """
    global _SB_HTTP_POOL, _SB_HTTP_POOL_LOCK
    if _sb_urllib3 is not None and os.environ.get('SHIFTBASE_DISABLE_HTTP_POOL','').strip() != '1':
        if _SB_HTTP_POOL is None:
            # The pool is thread-safe; initialize once under a standard lock.
            with _SB_HTTP_POOL_LOCK:
                if _SB_HTTP_POOL is None:
                    _SB_HTTP_POOL = _sb_urllib3.PoolManager(
                        num_pools=4, maxsize=4, block=True,
                        cert_reqs='CERT_REQUIRED', retries=False)
        try:
            response = _SB_HTTP_POOL.request(
                method, url, body=payload, headers=headers,
                timeout=_sb_urllib3.Timeout(connect=min(3.0, float(timeout)), read=float(timeout)),
                retries=False, redirect=False, preload_content=False)
            try:
                status = int(response.status)
                raw = response.read(max_bytes + 1)
                if len(raw) > max_bytes:
                    response.close()  # don't leave a truncated connection in pool
                    raise ShiftbaseIntegrationError('Shiftbase-Antwort überschreitet die zulässige Größe.')
            finally:
                response.release_conn()
            if 300 <= status < 400:
                raise ShiftbaseIntegrationError('Unerwartete Weiterleitung der Shiftbase-API abgebrochen.')
            if status >= 400:
                # Preserve the existing sanitized error-handling paths.
                return _sb_raise_http_error(url, status, raw)
            return status, raw
        except _sb_urllib3.exceptions.HTTPError as exc:
            # Never retry a failed or ambiguous PUT automatically.
            raise URLError('Shiftbase-Verbindung fehlgeschlagen oder Zeitüberschreitung') from exc
    req = Request(url, data=payload, method=method, headers=headers)
    with build_opener(_ShiftbaseNoRedirect()).open(req, timeout=timeout) as response:
        raw=response.read(max_bytes + 1)
        if len(raw) > max_bytes:
            raise ShiftbaseIntegrationError('Shiftbase-Antwort überschreitet die zulässige Größe.')
        return response.status, raw


def _sb_raise_http_error(url, status, body):
    import io
    raise HTTPError(url, status, 'Shiftbase-API-Fehler', {}, io.BytesIO(body))


class ShiftbaseIntegrationError(Exception):
    pass

class _ShiftbaseNoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise ShiftbaseIntegrationError("Unerwartete Weiterleitung der Shiftbase-API abgebrochen.")


def _shiftbase_config():
    mock_dir = os.environ.get('SHIFTBASE_MOCK_DIR', '').strip()
    base = os.environ.get('SHIFTBASE_API_BASE_URL', '').strip().rstrip('/')
    token = os.environ.get('SHIFTBASE_API_TOKEN', '').strip()
    if mock_dir:
        return {'mock_dir': mock_dir, 'base': '', 'token': ''}
    if not token or token.startswith('DEMO_'):
        raise ShiftbaseIntegrationError('SHIFTBASE_API_TOKEN fehlt oder ist ein Demo-Schlüssel. Bitte nur bei Render als Environment Variable setzen.')
    if not base or urlsplit(base).scheme != 'https' or not urlsplit(base).hostname:
        raise ShiftbaseIntegrationError('SHIFTBASE_API_BASE_URL fehlt oder ist keine gültige HTTPS-Adresse. Den API-Basis-URL aus Shiftbase-Dokumentation übernehmen.')
    if urlsplit(base).username or urlsplit(base).password or urlsplit(base).query or urlsplit(base).fragment:
        raise ShiftbaseIntegrationError('SHIFTBASE_API_BASE_URL enthält unerlaubte Bestandteile.')
    return {'mock_dir': '', 'base': base, 'token': token}


def _shiftbase_read_json(kind, params=None):
    cfg = _shiftbase_config()
    if cfg['mock_dir']:
        allowed = {'users':'users.json', 'timesheets':'timesheets.json', 'absentees':'absentees.json'}
        if kind == 'timesheet_detail':
            ident = str((params or {}).get('_detail_id', ''))
            if not re.fullmatch(r'[0-9]{1,20}', ident):
                raise ShiftbaseIntegrationError('Ungueltige Timesheet-ID')
            f = Path(cfg['mock_dir']) / f'timesheet_{ident}.json'
            if not f.is_file():
                raise ShiftbaseIntegrationError(f'Testdatei timesheet_{ident}.json fehlt.')
            return json.loads(f.read_text(encoding='utf-8'))
        f = Path(cfg['mock_dir']) / allowed[kind]
        if not f.is_file():
            raise ShiftbaseIntegrationError(f'Testdatei {f.name} fehlt.')
        try:
            return json.loads(f.read_text(encoding='utf-8'))
        except (OSError, ValueError) as exc:
            raise ShiftbaseIntegrationError(f'Testdatei {f.name} kann nicht gelesen werden.') from exc
    defaults = {'users':'/users', 'timesheets':'/timesheets', 'absentees':'/absentees'}
    if kind == 'timesheet_detail':
        ident = str((params or {}).get('_detail_id', ''))
        if not re.fullmatch(r'[0-9]{1,20}', ident):
            raise ShiftbaseIntegrationError('Ungueltige Timesheet-ID')
        path = '/timesheets/' + quote(ident, safe='')
        params = None
    else:
        path = os.environ.get('SHIFTBASE_'+kind.upper()+'_PATH', defaults[kind]).strip()
    if not path.startswith('/') or path.startswith('//') or '?' in path or '#' in path:
        raise ShiftbaseIntegrationError(f'API-Pfad für {kind} ungültig.')
    url = cfg['base'] + path
    if params:
        url += '?' + urlencode(params)
    auth_header = os.environ.get('SHIFTBASE_AUTH_HEADER', 'Authorization').strip()
    if auth_header.lower() not in {'authorization','x-api-key','x-auth-token'}:
        raise ShiftbaseIntegrationError('Nicht unterstützter Authentifizierungsheader.')
    # Shiftbase expects "Authorization: API <token>". Build the space ourselves
    # because UI forms / environment stores may strip trailing spaces from prefixes.
    # Only this account's real Shiftbase App Token can authenticate.
    auth_prefix = os.environ.get('SHIFTBASE_AUTH_PREFIX', 'API').strip()
    raw_token = cfg['token'].strip()
    if auth_header.lower() == 'authorization':
        if auth_prefix.upper() == 'API':
            if raw_token.lower().startswith('api '):
                raw_token = raw_token[4:].strip()
            auth_value = 'API ' + raw_token
        elif auth_prefix.lower() == 'bearer':
            if raw_token.lower().startswith('bearer '):
                raw_token = raw_token[7:].strip()
            auth_value = 'Bearer ' + raw_token
        else:
            raise ShiftbaseIntegrationError('Ungültiges SHIFTBASE_AUTH_PREFIX. Für Shiftbase ist API vorgesehen.')
    else:
        # X-API-Key and X-Auth-Token headers take only the raw token.
        auth_value = raw_token
    headers={'Accept':'application/json', 'User-Agent':'PlusMinusCloud-ShiftbaseAbgleich/1.1', auth_header: auth_value}
    try:
        _, raw = _sb_http_request('GET', url, headers, _SB_STEP_READ_TIMEOUT.get(),
                                  max_bytes=5_000_000)
        return json.loads(raw.decode('utf-8'))
    except HTTPError as exc:
        # Antworttext nicht weitergeben, da personenbezogene Daten enthalten sein koennen.
        raise ShiftbaseIntegrationError(f'Shiftbase-API HTTP {exc.code} bei {kind}. API-Adresse, Token und Berechtigung prüfen.') from exc
    except (URLError, TimeoutError, OSError) as exc:
        raise ShiftbaseIntegrationError(f'Keine Verbindung zur Shiftbase-API ({kind}). Netzwerk/URL prüfen.') from exc
    except (UnicodeError, ValueError) as exc:
        raise ShiftbaseIntegrationError(f'Shiftbase antwortete bei {kind} nicht mit gültigem JSON.') from exc


def _shiftbase_items(response, kind):
    if isinstance(response, list):
        return response, None
    if not isinstance(response, dict):
        raise ShiftbaseIntegrationError(f'Unerwartetes JSON-Format für {kind}: JSON-Objekt/Liste erwartet.')
    for key in (kind, 'data', 'results', 'items', 'records'):
        v=response.get(key)
        if isinstance(v, list):
            return v, response.get('next_offset')
        if isinstance(v, dict):
            for inner in (kind, 'items', 'results', 'data'):
                if isinstance(v.get(inner), list):
                    return v[inner], response.get('next_offset')
    raise ShiftbaseIntegrationError(f'Kein bekannter Listenschlüssel für {kind}. API-Antwortstruktur prüfen.')


def _shiftbase_get_all(kind, params=None):
    result=[]
    off=0
    for _ in range(30):
        q=dict(params or {})
        q.update({'limit':200, 'offset':off})
        response=_shiftbase_read_json(kind, q)
        items,next_off=_shiftbase_items(response, kind)
        if not all(isinstance(x,dict) for x in items):
            raise ShiftbaseIntegrationError(f'Unerwartete Datensätze bei {kind}.')
        result.extend(items)
        if len(result)>5000:
            raise ShiftbaseIntegrationError('Mehr als 5000 Shiftbase-Einträge. Bitte Zeitraum verkleinern.')
        if os.environ.get('SHIFTBASE_MOCK_DIR','').strip() or not items:
            return result
        total=response.get('total') if isinstance(response,dict) else None
        if next_off is not None:
            new_off=int(next_off)
            if new_off<=off:
                raise ShiftbaseIntegrationError('Ungültige Seitenangabe in API-Antwort.')
            off=new_off
        elif isinstance(total,(int,float)) and len(result)<int(total):
            off += len(items)
        else:
            return result
    raise ShiftbaseIntegrationError('Zu viele API-Seiten. Bitte Support kontaktieren.')


def _sb_get(row, name):
    """Return a JSON member ignoring casing and underscores (Shiftbase nested API)."""
    if not isinstance(row, dict):
        return None
    if name in row:
        return row[name]
    norm = lambda x: re.sub(r"[^a-z0-9]", "", str(x).lower())
    want = norm(name)
    for key, value in row.items():
        if norm(key) == want:
            return value
    return None


def _sb_id(row, *names):
    if not isinstance(row, dict):
        return None
    for name in names:
        value = _sb_get(row, name)
        if isinstance(value, dict):
            value = _sb_get(value, 'id') or _sb_get(value, 'user_id')
        if value is not None and str(value).strip():
            return str(value).strip()
    return None


def _sb_value(row, *names):
    for name in names:
        v = _sb_get(row, name)
        if v is not None and v != '':
            return v
    return None


def _sb_day(value):
    if value is None or isinstance(value, (dict, list)):
        return None
    try:
        return shiftbase_date.fromisoformat(str(value)[:10]).isoformat()
    except ValueError:
        return None


def _sb_number(value):
    try:
        if isinstance(value,(dict,list,bool)):
            return None
        x = Decimal(str(value).replace(',', '.'))
        if not x.is_finite():
            return None
        return x
    except (InvalidOperation, TypeError):
        return None


def _sb_hhmm(value):
    if not isinstance(value, str) or not re.fullmatch(r'\d{1,4}:\d{2}', value.strip()):
        return None
    h, m = map(int, value.strip().split(':'))
    return Decimal(h)+Decimal(m)/60 if m < 60 else None


def _sb_timepoint(value, date_value):
    """Parse documented clock values and PHP-style DateTime JSON objects.

    Shiftbase may return Timesheet.datetime as e.g.
      {"date":"2026-10-01 06:00:00.000000", "timezone_type":3,
       "timezone":"Europe/Amsterdam"}.
    Never use a bare date as midnight or invent a missing hour.
    Returns (datetime, was_only_clock_time) or (None, False).
    """
    if value is None or isinstance(value, bool):
        return None, False
    if isinstance(value, dict):
        # PHP's serialized DateTime object, or an explicitly separated date/time.
        # The timezone is metadata for the wall time. Compare start/end in the
        # same timesheet's wall-time domain; don't infer a break from these fields.
        d=_sb_get(value,'date')
        t=_sb_get(value,'time')
        if isinstance(d,str) and re.fullmatch(r'\d{4}-\d{2}-\d{2}',d.strip()) and isinstance(t,str):
            return _sb_timepoint(d.strip()+' '+t.strip(),date_value)
        for field in ('date','datetime','timestamp','value'):
            child=_sb_get(value,field)
            if child is not None and child is not value:
                got, only_clock=_sb_timepoint(child,date_value)
                if got is not None:
                    return got,only_clock
        return None, False
    if isinstance(value,list):
        return None, False
    if isinstance(value,(int,float)):
        # Magnitude allows unambiguous Unix seconds or milliseconds only.
        if 1_260_000_000 <= float(value) <= 4_200_000_000:
            return _sb_datetime.fromtimestamp(float(value),_sb_timezone.utc),False
        if 1_260_000_000_000 <= float(value) <= 4_200_000_000_000:
            return _sb_datetime.fromtimestamp(float(value)/1000,_sb_timezone.utc),False
        return None,False
    text=str(value).strip()
    if not text:
        return None,False
    if re.fullmatch(r'\d{1,2}:\d{2}(?::\d{2})?',text):
        if not isinstance(date_value,str):
            return None,False
        try:
            base=_sb_datetime.strptime(date_value[:10],'%Y-%m-%d')
            clock=_sb_datetime.strptime(text,'%H:%M:%S' if text.count(':')==2 else '%H:%M')
            return base.replace(hour=clock.hour,minute=clock.minute,second=clock.second),True
        except ValueError:
            return None,False
    if not re.match(r'^\d{4}-\d{2}-\d{2}[ T]',text):
        return None,False
    try:
        return _sb_datetime.fromisoformat(text.replace('Z','+00:00')),False
    except ValueError:
        return None,False


def _sb_time_shape(value):
    """Only safe structural hints, not any employee's timestamps or values."""
    if value is None:
        return 'fehlend'
    if isinstance(value,dict):
        fields=','.join(sorted(str(k)[:32] for k in value)[:12])
        datechild=_sb_get(value,'date')
        shape=_sb_time_shape(datechild) if datechild is not None else '-'
        return 'Objekt-Felder('+fields+'), date-Muster='+shape
    if isinstance(value,str):
        val=value.strip()
        if re.fullmatch(r'\d{1,2}:\d{2}(?::\d{2})?',val): return 'Uhrzeit'
        if re.match(r'^\d{4}-\d{2}-\d{2}[ T]\d{1,2}:\d{2}',val): return 'Datum+Uhrzeit'
        if re.fullmatch(r'\d+(?:[,.]\d+)?',val): return 'Zahlen-Text'
        if not val: return 'leer'
        return 'anderer Text'
    return type(value).__name__


def _sb_break_as_minutes(value):
    """Shiftbase Timesheet.break is break minutes, including a possible HH:MM format.

    Do not guess the meaning of fractional numbers or nested structures.
    """
    if value is None or value == '':
        return Decimal(0)
    if isinstance(value,(dict,list,bool)):
        return None
    if isinstance(value,str) and ':' in value:
        parts = value.strip().split(':')
        if len(parts) not in (2,3) or not all(x.isdigit() for x in parts):
            return None
        h,m=int(parts[0]),int(parts[1]);sec=int(parts[2]) if len(parts)==3 else 0
        if m>=60 or sec>=60: return None
        minutes=Decimal(h)*60+Decimal(m)+Decimal(sec)/60
    else:
        minutes=_sb_number(value)
        if minutes is None or minutes != minutes.to_integral_value():
            return None
    if minutes < 0 or minutes > 600:
        return None
    return minutes


def _sb_hours_from_clock(row):
    """Calculate NET timesheet hours from start/end and recorded break.

    Only use timestamps belonging to the recorded timesheet (not hypothetical breaks).
    """
    day = _sb_value(row,'date','work_date')
    start_raw=_sb_value(row,'datetime','start_datetime','start_time','start','clocked_in')
    end_raw=_sb_value(row,'endtime','end_datetime','end_time','end','clocked_out')
    begin, begin_clock = _sb_timepoint(start_raw, day)
    finish, finish_clock = _sb_timepoint(end_raw, day)
    if begin is None or finish is None:
        return None
    # Reject mixed timezone-aware and naive timestamps.
    if (begin.tzinfo is None)!=(finish.tzinfo is None):
        return None
    if finish < begin:
        # An overnight shift may have only time-of-day for its end value.
        if begin_clock or finish_clock:
            finish += _sb_timedelta(days=1)
        else:
            return None
    duration_minutes = Decimal(str((finish-begin).total_seconds()))/Decimal(60)
    if not (Decimal(0) < duration_minutes <= Decimal(24*60)):
        return None
    pause = _sb_break_as_minutes(_sb_value(row,'break','break_minutes','unpaid_break_minutes'))
    if pause is None or pause > duration_minutes:
        return None
    return (duration_minutes-pause)/Decimal(60)


def _sb_hours(row):
    """Return the real NET hours supplied by a Shiftbase Timesheet.

    The observed Shiftbase API response contains the field ``total`` as
    a *decimal number of hours encoded as a string*: for example, an
    08:00–18:00 shift with 45 minutes recorded break has ``total`` =
    ``"9.250000"``.  Prefer that authoritative total over attempts to
    reconstruct hours from the optional (sometimes empty) ``datetime``.

    This function reads only; it never changes source timesheets or invents
    missing breaks. Do not confuse payroll_hours with work hours.
    """
    if not isinstance(row, dict):
        return None

    # 1) Shiftbase's own calculated net worked hours (confirmed in the
    #    real Timesheet payload). Accept both 9.250000 and 9:15 formats.
    for key in ('total', 'worked_hours', 'total_worked_hours', 'hours_worked',
                'duration_hours', 'net_hours', 'total_hours'):
        value = _sb_get(row, key)
        if value is None or value == '':
            continue
        amount = (_sb_hhmm(value) if isinstance(value, str) and ':' in value
                  else _sb_number(value))
        # A single timesheet cannot reasonably exceed 24 hours; do not
        # silently display negative or implausible source values.
        if amount is not None and Decimal(0) <= amount <= Decimal(24):
            return amount
        return None

    # 2) Explicit numeric lengths with a documented unit in the key.
    for key, denominator in (('worked_minutes', 60), ('total_worked_minutes', 60),
                             ('total_minutes', 60), ('duration_minutes', 60),
                             ('worked_seconds', 3600), ('duration_seconds', 3600)):
        value = _sb_get(row, key)
        if value is not None and value != '':
            amount = _sb_number(value)
            if amount is None:
                return None
            hours = amount / Decimal(denominator)
            return hours if Decimal(0) <= hours <= Decimal(24) else None

    # 3) Older hour formats with an explicit HH:MM value.
    for key in ('worked', 'hours', 'duration'):
        result = _sb_hhmm(_sb_get(row, key))
        if result is not None and Decimal(0) <= result <= Decimal(24):
            return result

    # 4) Last resort: read real start/end and recorded break only.
    return _sb_hours_from_clock(row)


def _sb_timesheet_parts(entry):
    """Shiftbase GET /timesheets can return joined records: {Timesheet:{...}, User:{...}}."""
    ts=_sb_get(entry,'Timesheet')
    if not isinstance(ts,dict):
        ts=entry
    usr=_sb_get(entry,'User')
    if not isinstance(usr,dict):
        usr={}
    uid=(_sb_id(usr,'id','user_id')
         or _sb_id(ts,'user_id','user','employee_id','employee')
         or _sb_id(entry,'user_id','user','employee_id','employee'))
    day=(_sb_day(_sb_value(ts,'date','work_date','start_date','start_time','start','clock_in'))
         or _sb_day(_sb_value(entry,'date','work_date','start_date','start_time','start','clock_in')))
    hours=_sb_hours(ts)
    if hours is None:
        hours=_sb_hours(entry)
    entry_id=_sb_id(ts,'id','timesheet_id') or _sb_id(entry,'id','timesheet_id')
    return uid,day,hours,entry_id


def _sb_absence_name(row):
    value=_sb_value(row,'absence_type','absentee_type','type','type_name','reason')
    if isinstance(value,dict):
        return str(_sb_value(value,'name','label','title') or 'Art unbekannt')
    return str(value or 'Art unbekannt')


def _sb_user_display(row):
    name=_sb_value(row,'name','full_name','display_name')
    if name: return str(name)
    return ' '.join(filter(None,[str(row.get('first_name') or ''),str(row.get('last_name') or '')])).strip() or 'Ohne Name'


def _sb_month_window(year, month):
    start=shiftbase_date(year,month,1)
    end=shiftbase_date(year+1,1,1)-shiftbase_timedelta(days=1) if month==12 else shiftbase_date(year,month+1,1)-shiftbase_timedelta(days=1)
    return start.isoformat(),end.isoformat()


def _sb_ensure_mapping_table(conn):
    conn.execute("""CREATE TABLE IF NOT EXISTS shiftbase_driver_map
        (driver_id INTEGER PRIMARY KEY, shiftbase_user_id TEXT NOT NULL UNIQUE, updated_at TEXT NOT NULL)""")


def _sb_mapping(conn):
    _sb_ensure_mapping_table(conn)
    return {int(r['driver_id']):str(r['shiftbase_user_id']) for r in conn.execute('SELECT driver_id,shiftbase_user_id FROM shiftbase_driver_map').fetchall()}


def _sb_local_month(conn,year,month):
    return [dict(r) for r in conn.execute("""
       SELECT d.id AS driver_id, d.external_driver_id,d.name,d.employment_type,
              m.payroll_hours,m.worked_hours,m.vacation_days,m.sick_days,
              m.previous_balance,m.new_balance
       FROM drivers d LEFT JOIN monthly_data m
       ON m.driver_id=d.id AND m.year=? AND m.month=?
       WHERE d.is_active=1 AND COALESCE(d.is_disposition,0)=0
       ORDER BY COALESCE(NULLIF(d.display_order,0),d.id),d.name COLLATE NOCASE""",(year,month)).fetchall()]


def _sb_fetch_snapshot(year,month):
    start,end=_sb_month_window(year,month)
    users=_shiftbase_get_all('users')
    # These parameter names are from the publicly described Shiftbase resource model;
    # adapt in env/API adapter if the account's official schema differs.
    times=_shiftbase_get_all('timesheets',{'min_date':start,'max_date':end})
    absences=_shiftbase_get_all('absentees',{'min_date':start,'max_date':end})
    return users,times,absences


def _sb_report(conn,year,month,users,times,absences):
    local=_sb_local_month(conn,year,month)
    mappings=_sb_mapping(conn)
    csv_snapshots=_sb_csv_snapshots(conn,year,month)
    known_users={}
    for row in users:
        uid=_sb_id(row,'id','user_id','employee_id') or _sb_id(_sb_get(row,'User'),'id','user_id')
        if uid: known_users[uid]=(_sb_get(row,'User') if isinstance(_sb_get(row,'User'),dict) else row)
    entries=defaultdict(list)
    ignored=[]
    missing_user_ids=0
    missing_dates=0
    missing_hour_units=0
    example_fields=[]
    nested_example_fields={}
    unknown_time_field_types={}
    for entry in times:
        if not example_fields and isinstance(entry,dict):
            # Only structural field names, never private employee/payroll values.
            example_fields=sorted(str(k)[:70] for k in entry.keys())[:45]
            nested_example_fields={
                str(k):sorted(str(child)[:70] for child in v.keys())[:35]
                for k,v in entry.items()
                if isinstance(v,dict) and str(k).lower() in {'user','employee','timesheet','shift','roster'}
            }
        ts = _sb_get(entry,'Timesheet')
        if not isinstance(ts,dict):ts=entry
        # A deliberately declined/removed entry is historical, not work time.
        if str(_sb_value(ts,'status') or '').strip().lower() in {'declined','rejected','abgelehnt'}:
            continue
        if str(_sb_get(ts,'deleted') or '').strip().lower() in {'1','true','yes'}:
            continue
        uid, day, hours, entry_id = _sb_timesheet_parts(entry)
        if not uid or not day:
            missing_user_ids += int(not bool(uid))
            missing_dates += int(not bool(day))
            if not example_fields:
                # Only JSON FIELD NAMES, never employee information, work times or token values.
                example_fields=sorted(str(k)[:70] for k in entry.keys())[:45]
                nested_example_fields={
                    str(k):sorted(str(child)[:70] for child in v.keys())[:20]
                    for k,v in entry.items()
                    if isinstance(v,dict) and str(k).lower() in {'user','employee','timesheet','shift','roster'}
                }
            ignored.append('Zeiteintrag ohne eindeutige Benutzer-ID/Datum')
            continue
        if hours is None:
            missing_hour_units += 1
            if not unknown_time_field_types:
                ts_debug=_sb_get(entry,'Timesheet')
                if not isinstance(ts_debug,dict): ts_debug=entry
                for k in ('datetime','endtime','break','date','clocked_in','clocked_out'):
                    v=_sb_get(ts_debug,k)
                    unknown_time_field_types[k] = _sb_time_shape(v)
        if (int(day[:4]),int(day[5:7]))!=(year,month):
            continue
        entries[uid].append({'date':day,'hours':hours,'entry_id':entry_id})
    absence_by_user=defaultdict(list)
    start,end=_sb_month_window(year,month)
    for a in absences:
        ab=_sb_get(a,'Absentee')
        if not isinstance(ab,dict): ab=a
        au=_sb_get(a,'User')
        uid=(_sb_id(au,'id','user_id') or _sb_id(ab,'user_id','user','employee_id','employee') or _sb_id(a,'user_id','user','employee_id','employee'))
        if not uid:
            continue
        astart=_sb_day(_sb_value(ab,'start_date','min_date','start','date'))
        aend=_sb_day(_sb_value(ab,'end_date','max_date','end')) or astart
        if astart and aend and astart<=end and aend>=start:
            absence_by_user[uid].append({'von':max(astart,start),'bis':min(aend,end),'art':_sb_absence_name(ab),'status':str(_sb_value(ab,'status') or 'unbekannt')})
    result=[]
    for r in local:
        uid=mappings.get(r['driver_id'])
        selected=entries.get(uid,[]) if uid else []
        complete=bool(uid and selected and all(x['hours'] is not None for x in selected))
        tot=sum((x['hours'] for x in selected),Decimal(0)) if complete else None
        csv_source=False
        saved=csv_snapshots.get(r['driver_id'])
        if tot is None and uid and saved and saved['shiftbase_user_id']==uid:
            # This is a dated, Shiftbase-exported snapshot, not live API data.
            # Do not confuse the two data sources or overwrite real timesheet rows.
            try:
                tot=Decimal(saved['worked_hours'])
                csv_source=True
            except (InvalidOperation,ValueError): pass
        payroll=Decimal(str(r['payroll_hours'])) if r['payroll_hours'] is not None else None
        diff=payroll-tot if payroll is not None and tot is not None else None
        notes=[]
        if not uid: notes.append('Noch keine eindeutige Shiftbase-Zuordnung')
        elif uid not in known_users: notes.append('Zugeordneter Shiftbase-Benutzer fehlt in der API-Antwort')
        if not selected and uid: notes.append('Keine Zeiteinträge im ausgewählten Monat')
        if selected and not complete and not csv_source: notes.append('Die API liefert keine berechenbare Arbeitszeit; Shiftbase-CSV importieren')
        if csv_source: notes.append('Arbeitszeit aus Shiftbase-CSV vom '+str(saved['captured_at'])[:10]+'; keine Live-API-Summe')
        if r['payroll_hours'] is None: notes.append('Kein Abrechnungswert in der Cloud für diesen Monat')
        if r['vacation_days'] not in (None,'','0'): notes.append('Urlaub in Cloud nur als Tagesanzahl gespeichert, Shiftbase-Abwesenheitsdaten prüfen')
        if r['sick_days'] not in (None,''): notes.append('Krankheit aus Cloud und Shiftbase getrennt abstimmen')
        if diff is not None and abs(diff)>=Decimal('0.01'):
            notes.append('Unterschied zum Lohnwert – Zeitkonto/Abwesenheit/Erfassungsfehler prüfen; Originalzeiten unverändert')
        result.append({'driver_id':r['driver_id'],'external_driver_id':r['external_driver_id'],
            'fahrer':r['name'],'shiftbase_user_id':uid,'shiftbase_name':_sb_user_display(known_users[uid]) if uid in known_users else None,
            'payroll_hours':float(payroll) if payroll is not None else None,
            'timesheet_hours':round(float(tot),2) if tot is not None else None,
            'difference':round(float(diff),2) if diff is not None else None,
            'worked_hours_cloud':r['worked_hours'],'vacation_days_cloud':r['vacation_days'] or '',
            'sick_days_cloud':r['sick_days'] or '', 'absences':absence_by_user.get(uid,[]) if uid else [],
            'timesheets':len(selected),'source':'shiftbase_csv' if csv_source else ('api' if tot is not None else 'nicht_berechenbar'),'notes':notes,
            'status':'ungeklärt' if diff is None else ('gleich' if abs(diff)<Decimal('0.01') else 'abweichung')})
    return {'year':year,'month':month,'readonly':True,'results':result,
            'api_users':len(users),'api_timesheets':len(times),'api_absences':len(absences),
            'ignored_entries':len(ignored),'users':known_users,
            'diagnostic':{'missing_user_ids':missing_user_ids,'missing_dates':missing_dates,
                          'missing_hour_units':missing_hour_units,
                          'example_field_names':example_fields,'nested_field_names':nested_example_fields,
                          'unknown_time_field_types':unknown_time_field_types}}


def _sb_enrich_mapped_timesheets(times, mapped_ids, max_lookups=40):
    """GET details only for mapped people; never modifies any Shiftbase entry.

    Public list endpoints sometimes leave datetime empty. Detail may carry explicit
    computed hours / full clock values. If it doesn't, retain an unknown hour
    rather than fabricate one. To avoid 40 futile calls, stop after 2 no-results.
    """
    stats={'detail_checked':0,'detail_resolved':0,'detail_unavailable':0,'detail_skipped':0}
    if not mapped_ids or os.environ.get('SHIFTBASE_DETAIL_LOOKUP','1').strip() == '0':
        return times,stats
    checked_no_result=0
    for entry in times:
        uid,day,hours,entry_id=_sb_timesheet_parts(entry)
        if uid not in mapped_ids or hours is not None or not entry_id:
            continue
        if stats['detail_checked'] >= max_lookups or checked_no_result>=2:
            stats['detail_skipped'] += 1
            continue
        stats['detail_checked']+=1
        try:
            detail=_shiftbase_read_json('timesheet_detail',{'_detail_id':entry_id})
        except ShiftbaseIntegrationError:
            stats['detail_unavailable']+=1
            checked_no_result+=1
            continue
        if isinstance(detail,dict):
            # Shiftbase typically wraps records under Timesheet.
            candidate = _sb_get(detail,'Timesheet')
            if not isinstance(candidate,dict):
                candidate=_sb_get(detail,'data')
            if not isinstance(candidate,dict):
                candidate=detail
            candidate_hours=_sb_hours(candidate)
            if candidate_hours is not None and Decimal(0) <= candidate_hours <= Decimal(24):
                # Keeping original User/date/id avoids accidental cross-employee mixups.
                # Put explicit hours in the inner Timesheet; _sb_hours prefers them.
                ts=_sb_get(entry,'Timesheet')
                if isinstance(ts,dict):
                    ts['duration_hours']=str(candidate_hours)
                else:
                    entry['duration_hours']=str(candidate_hours)
                stats['detail_resolved']+=1
                checked_no_result=0
                continue
        checked_no_result+=1
    return times,stats


def _sb_header(text):
    text = unicodedata.normalize('NFKD',str(text or '').casefold())
    text = ''.join(ch for ch in text if not unicodedata.combining(ch))
    return re.sub(r'[^a-z0-9]','',text)


def _sb_import_hours(value):
    """Parse an explicitly labelled Worked/Gearbeitet value; not gross shift time."""
    if isinstance(value,bool):
        return None
    text=str(value if value is not None else '').strip().lower().replace('std.','').replace('stunden','').replace('hours','').strip()
    if not text: return None
    m=re.fullmatch(r'(\d{1,3}):(\d{2})(?::(\d{2}))?',text)
    if m:
        h,minutes,sec=int(m.group(1)),int(m.group(2)),int(m.group(3) or 0)
        if minutes>=60 or sec>=60: return None
        return Decimal(h)+Decimal(minutes)/60+Decimal(sec)/3600
    if not re.fullmatch(r'\d{1,4}(?:[,.]\d{1,4})?',text):
        return None
    n=_sb_number(text)
    return n if n is not None and Decimal(0)<=n<=Decimal(744) else None


def _sb_ensure_csv_snapshot_table(conn):
    conn.execute("""CREATE TABLE IF NOT EXISTS shiftbase_csv_snapshots (
        driver_id INTEGER NOT NULL, year INTEGER NOT NULL, month INTEGER NOT NULL,
        shiftbase_user_id TEXT NOT NULL, worked_hours TEXT NOT NULL,
        entry_count INTEGER NOT NULL, captured_at TEXT NOT NULL,
        PRIMARY KEY(driver_id,year,month)
    )""")


def _sb_save_csv_snapshot(conn, result, driver_id):
    _sb_ensure_csv_snapshot_table(conn)
    conn.execute("""INSERT INTO shiftbase_csv_snapshots
        (driver_id,year,month,shiftbase_user_id,worked_hours,entry_count,captured_at)
        VALUES(?,?,?,?,?,?,?)
        ON CONFLICT(driver_id,year,month) DO UPDATE SET
        shiftbase_user_id=excluded.shiftbase_user_id,
        worked_hours=excluded.worked_hours,
        entry_count=excluded.entry_count,
        captured_at=excluded.captured_at""",
        (driver_id,result['year'],result['month'],result['uid'],str(result['hours']),result['matched'],now_iso()))
    conn.commit()


def _sb_csv_snapshots(conn,year,month):
    _sb_ensure_csv_snapshot_table(conn)
    return {int(row['driver_id']):dict(row) for row in conn.execute(
        'SELECT * FROM shiftbase_csv_snapshots WHERE year=? AND month=?',(year,month)).fetchall()}


def _sb_csv_report_for_driver(raw_bytes,driver_id,year,month):
    """Process official Shiftbase Timesheet detail CSV in memory for ONE driver.

    Must have an actual worked-hours column. Never substitute paid time, scheduled
    hours, standing time or clocked span. Do not store uploaded private report.
    """
    if not raw_bytes or len(raw_bytes)>5_000_000:
        raise ShiftbaseIntegrationError('Bitte eine CSV-Datei bis 5 MB hochladen.')
    text=None
    for encoding in ('utf-8-sig','utf-16','cp1252'):
        try:
            text=raw_bytes.decode(encoding)
            if '\x00' in text: text=None; continue
            break
        except UnicodeError: pass
    if text is None:
        raise ShiftbaseIntegrationError('CSV-Codierung nicht erkannt. Aus Shiftbase als CSV exportieren.')
    lines=text.splitlines()
    if not lines or len(lines)>20000:
        raise ShiftbaseIntegrationError('Die Datei ist leer oder enthält zu viele Zeilen.')
    best=None
    for delim in (';',',','\t'):
        parsed=list(csv.reader(io.StringIO(text),delimiter=delim))
        # Shiftbase exports may have one or two preamble lines above the column headings.
        for header_index in range(min(8,len(parsed))):
            cols=parsed[header_index]
            names=[_sb_header(c) for c in cols]
            score=sum(any(x in names for x in group) for group in (
                ('worked','workedhours','gearbeitet','gearbeitetestunden','arbeitsstunden','gearbeitetezeit','geleistetestunden'),
                ('userid','benutzerid','mitarbeiterid','employeeid','name','mitarbeiter','employee'),
                ('date','datum','arbeitsdatum'),))
            if best is None or score>best[0]:best=(score,parsed,header_index)
    if best is None or best[0]<3:
        raise ShiftbaseIntegrationError('CSV-Spalten nicht erkannt. Bitte den Shiftbase-Bericht „Arbeitszeitprotokoll – Details“ mit Benutzer-ID, Datum und „Gearbeitet“ exportieren.')
    _, parsed, first=best
    cols=[_sb_header(c) for c in parsed[first]]
    def idx(*names):
        for n in names:
            if n in cols:return cols.index(n)
        return None
    iwork=idx('worked','workedhours','gearbeitet','gearbeitetestunden','arbeitsstunden','gearbeitetezeit','geleistetestunden')
    iid=idx('userid','benutzerid','mitarbeiterid','employeeid')
    iname=idx('name','mitarbeiter','employee','mitarbeitername','employeename')
    idate=idx('date','datum','arbeitsdatum')
    its=idx('timesheetid','arbeitszeiteintragid','zeiteintragid')
    istatus=idx('status','genehmigungsstatus')
    if iwork is None or idate is None or (iid is None and iname is None):
        raise ShiftbaseIntegrationError('Es fehlen die Spalten „Gearbeitet“, Datum oder Mitarbeiter/Benutzer-ID.')
    with db_conn() as conn:
        _sb_ensure_mapping_table(conn)
        mapping=_sb_mapping(conn)
        d=conn.execute('SELECT name FROM drivers WHERE id=?',(driver_id,)).fetchone()
        monthrow=conn.execute('SELECT payroll_hours FROM monthly_data WHERE driver_id=? AND year=? AND month=?',(driver_id,year,month)).fetchone()
    if not d:raise ShiftbaseIntegrationError('Fahrer existiert nicht in deiner Cloud.')
    uid=mapping.get(driver_id)
    if not uid:raise ShiftbaseIntegrationError('Fahrer muss zuerst mit Shiftbase verknüpft sein.')
    fname=str(d['name'])
    wanted_name=_sb_header(fname)
    matched=0; failed=0; seen=set(); total=Decimal(0); dayvalues={}; omitted=0
    for row in parsed[first+1:]:
        if not row or not any(c.strip() for c in row):continue
        def cell(i):return row[i].strip() if i is not None and i<len(row) else ''
        if iid is not None:
            if cell(iid)!=uid:continue
        elif _sb_header(cell(iname))!=wanted_name:continue
        rawdate=cell(idate)
        # Date is required so the correct payroll month is guaranteed.
        day=_sb_day(rawdate)
        if not day:
            m=re.fullmatch(r'(\d{1,2})\.(\d{1,2})\.(\d{4})',rawdate)
            if m:
                try: day=shiftbase_date(int(m.group(3)),int(m.group(2)),int(m.group(1))).isoformat()
                except ValueError: pass
        if not day:
            failed+=1;continue
        if not day.startswith(f'{year:04d}-{month:02d}-'):
            omitted+=1;continue
        if istatus is not None and _sb_header(cell(istatus)) in {'declined','rejected','abgelehnt','abgewiesen'}:
            omitted+=1;continue
        record_id=cell(its)
        if record_id:
            if record_id in seen:
                omitted+=1;continue
            seen.add(record_id)
        value=_sb_import_hours(cell(iwork))
        if value is None or value>Decimal(24):
            failed+=1;continue
        total+=value
        dayvalues[day]=dayvalues.get(day,Decimal(0))+value
        matched+=1
    if failed:
        raise ShiftbaseIntegrationError(f'{failed} Einträge von {fname} sind im CSV nicht eindeutig auswertbar. Keine Monatssumme berechnet.')
    if not matched:
        raise ShiftbaseIntegrationError('Für diesen Fahrer und Monat sind im CSV keine passenden Zeiteinträge enthalten. Prüfe den Berichtsfilter und die Benutzer-ID.')
    payroll=Decimal(str(monthrow['payroll_hours'])) if monthrow and monthrow['payroll_hours'] is not None else None
    return {'fahrer':fname,'uid':uid,'year':year,'month':month,'matched':matched,'omitted':omitted,
            'hours':total,'payroll':payroll,'difference':payroll-total if payroll is not None else None,
            'dayvalues':sorted(dayvalues.items()),'identity':'Shiftbase-Benutzer-ID' if iid is not None else 'exakter Name'}


@app.post('/admin/shiftbase/csv-test')
@admin_login_required
def admin_shiftbase_csv_test():
    csrf=session.get('shiftbase_csrf','')
    if not csrf or not hmac.compare_digest(csrf,str(request.form.get('csrf_token',''))):
        abort(403)
    try:
        driver_id=int(request.form.get('driver_id','0'))
        year=int(request.form.get('year','0'))
        month=int(request.form.get('month','0'))
        if not (2020<=year<=2100 and 1<=month<=12):raise ValueError()
    except ValueError:abort(400)
    upload=request.files.get('timesheet_csv')
    if not upload or not str(upload.filename).lower().endswith(('.csv','.txt')):
        error='Bitte eine CSV-Datei aus Shiftbase auswählen.'
        return base_page('Shiftbase CSV-Test','<div class="card"><h2>CSV-Test</h2><div class="flash err">'+shiftbase_escape(error)+'</div></div>','shiftbase'),400
    try:
        result=_sb_csv_report_for_driver(upload.read(5_000_001),driver_id,year,month)
    except ShiftbaseIntegrationError as exc:
        return base_page('Shiftbase CSV-Test','<div class="card"><h2>CSV-Test</h2><div class="flash err">'+shiftbase_escape(str(exc))+'</div><a class="btn small" href="'+url_for('admin_shiftbase_abgleich',year=year,month=month,laden=1)+'">Zurück zum Abgleich</a></div>','shiftbase'),422
    with db_conn() as conn:
        _sb_save_csv_snapshot(conn,result,driver_id)
    def hfmt(x):
        if x is None:return '–'
        minutes=int((x*60).quantize(Decimal('1')))
        return f'{minutes//60}:{minutes%60:02d} h ({x:.2f} Dezimalstunden)'
    page=['<div class="card"><h2>Shiftbase-CSV – '+shiftbase_escape(result['fahrer'])+'</h2>',
          '<p><b>Arbeitszeit aus offizieller CSV:</b> '+shiftbase_escape(hfmt(result['hours']))+'</p>',
          '<p><b>Abrechnung deiner Cloud:</b> '+shiftbase_escape(hfmt(result['payroll']))+'</p>',
          '<p><b>Differenz (Abrechnung minus Arbeitszeit):</b> '+shiftbase_escape(hfmt(result['difference']))+'</p>',
          '<p>Einträge: '+str(result['matched'])+' · Identifikation: '+shiftbase_escape(result['identity'])+'. Nur die geprüfte Monatssumme wurde in deiner Cloud gespeichert. Die CSV-Datei wurde nicht gespeichert und Shiftbase wurde nicht verändert.</p>',
          '<h3>Tageswerte aus Shiftbase</h3><div class="table-wrap"><table><tr><th>Datum</th><th>Gearbeitete Stunden</th></tr>']
    for day,val in result['dayvalues']:
        page.append('<tr><td>'+shiftbase_escape(day)+'</td><td>'+shiftbase_escape(hfmt(val))+'</td></tr>')
    page.append('</table></div><p><a class="btn small" href="'+url_for('admin_shiftbase_abgleich',year=year,month=month,laden=1)+'">Zurück zum Abgleich</a></p></div>')
    return base_page('Shiftbase CSV-Test',''.join(page),'shiftbase')


def _sb_report_for_month(year,month):
    with db_conn() as conn:
        _sb_ensure_mapping_table(conn)
        users,times,absences=_sb_fetch_snapshot(year,month)
        mappings=_sb_mapping(conn)
        times,detail_stats=_sb_enrich_mapped_timesheets(times,set(mappings.values()))
        report=_sb_report(conn,year,month,users,times,absences)
        report['diagnostic']['detail']=detail_stats
        return report


def _sb_params():
    tznow=datetime.now(ZoneInfo('Europe/Berlin')) if ZoneInfo else datetime.now()
    try:
        year=int(request.args.get('year',tznow.year)); month=int(request.args.get('month',tznow.month))
        if year<2020 or year>2100 or month<1 or month>12:raise ValueError()
        return year,month
    except (ValueError,TypeError):
        abort(400,'Ungültiges Jahr oder Monat')


def _sb_csrf_token():
    if not session.get('shiftbase_csrf'):
        session['shiftbase_csrf']=secrets.token_urlsafe(24)
    return session['shiftbase_csrf']


def _sb_simple_home(year,month):
    with db_conn() as conn:
        drivers=_sb_local_month(conn,year,month)
        mappings=_sb_mapping(conn)
    choices=[r for r in drivers if r['driver_id'] in mappings]
    chosen=str(request.args.get('driver_id','')).strip()
    options=''.join('<option value="'+str(r['driver_id'])+'"'+
             (' selected' if chosen==str(r['driver_id']) else '')+'>'+shiftbase_escape(r['name'])+
             ' · Shiftbase '+shiftbase_escape(mappings[r['driver_id']])+'</option>' for r in choices)
    if not choices:
        options='<option value="">Keine Zuordnung vorhanden</option>'
    month_options=''.join('<option value="'+str(m)+'"'+(' selected' if m==month else '')+'>'+MONATE[m]+'</option>' for m in range(1,13))
    h=['<div class="card" style="max-width:940px"><h2>Shiftbase – Monatsabgleich</h2>',
       '<p>Arbeitszeit laut Shiftbase mit den getrennten Abrechnungsstunden vergleichen. Die Vorschau ist rein rechnerisch und ändert keine Arbeitszeit.</p>',
       '<form method="get" action="'+url_for('admin_shiftbase_pruefvorschau')+'" class="grid grid-3" style="align-items:end">',
       '<label>Fahrer<select name="driver_id" required>'+options+'</select></label>',
       '<label>Monat<select name="month" required>'+month_options+'</select></label>',
       '<label>Jahr<input type="number" name="year" min="2020" max="2100" value="'+str(year)+'" required></label>',
       '<div style="grid-column:1/-1"><button class="primary" style="width:auto" type="submit"'+('' if choices else ' disabled')+'>Monat abgleichen</button></div>',
       '</form><p class="muted" style="margin-top:18px">Nur bestätigte tatsächliche Zeitkorrekturen dürfen später einzeln an Shiftbase gesendet werden. Lohnabweichungen bleiben in der Cloud.</p>',
       '<p><a class="btn primary" style="width:auto" href="'+url_for('admin_shiftbase_transfer_dashboard',year=year,month=month)+'">Alle Fahrer auswählen / Monatsübersicht</a></p>',
       '<p><a class="btn small" href="'+url_for('admin_shiftbase_abgleich',year=year,month=month,laden=1,erweitert=1)+'">Zuordnungen und erweiterte Berichte</a></p></div>']
    return base_page('Shiftbase-Abgleich',''.join(h),'shiftbase')


@app.get('/admin/shiftbase')
@admin_login_required
def admin_shiftbase_abgleich():
    year,month=_sb_params()
    if request.args.get('erweitert') != '1':
        return _sb_simple_home(year,month)
    report=None; error=None
    with db_conn() as conn:
        local=_sb_local_month(conn,year,month)
        mapped=_sb_mapping(conn)
    sb_users={}
    if request.args.get('laden')=='1':
        try:
            report=_sb_report_for_month(year,month)
            sb_users=report.pop('users')
        except ShiftbaseIntegrationError as exc:
            error=str(exc)
    h=[]
    h.append('<div class="card"><h2>Shiftbase – erweiterter Lesebericht</h2><p>Die echten Shiftbase-Zeiten bleiben unverändert. Die Spalte Abrechnung wird als gesonderter Lohnwert verglichen. Änderungen an Pausen oder Arbeitszeitnachweisen werden nicht automatisch vorgenommen.</p>')
    h.append(f'<form method="get" class="actions" action="{url_for("admin_shiftbase_abgleich")}">')
    h.append(f'<label>Jahr <input type="number" name="year" min="2020" max="2100" value="{year}" required style="width:110px"></label>')
    h.append(f'<label>Monat <input type="number" name="month" min="1" max="12" value="{month}" required style="width:90px"></label>')
    h.append('<input type="hidden" name="laden" value="1"><button class="primary" style="width:auto">Shiftbase auslesen & vergleichen</button></form>')
    h.append('<p class="muted">Erforderliche Render-Variablen: SHIFTBASE_API_BASE_URL und SHIFTBASE_API_TOKEN. API-Pfad/Authentifizierung nach Shiftbase-Dokumentation prüfen. Für Demo lokal SHIFTBASE_MOCK_DIR setzen.</p>')
    h.append('<p><a class="btn primary" style="width:auto" href="'+url_for('admin_shiftbase_kaan_diagnose',year=year,month=month)+'">Kaan Aysel: 1 echten API-Schichtdatensatz prüfen</a></p>')
    h.append('<p><a class="btn primary" style="width:auto" href="'+url_for('admin_shiftbase_tagesuebersicht',year=year,month=month)+'">Kaan Aysel: Alle Tagesschichten anzeigen</a></p>')
    h.append('<p><a class="btn" style="width:auto" href="'+url_for('admin_shiftbase_api_methodencheck',year=year,month=month)+'">API-Schreibmethoden gefahrlos prüfen (OPTIONS)</a></p>')

    if error: h.append('<div class="flash err">'+shiftbase_escape(error)+'</div>')
    h.append('</div>')
    # CSV fallback: official Shiftbase report already includes calculated net hours.
    with db_conn() as _sb_conn:
        _csv_locals=_sb_local_month(_sb_conn,year,month)
        _csv_mappings=_sb_mapping(_sb_conn)
    _csv_choices=[r for r in _csv_locals if r['driver_id'] in _csv_mappings]
    h.append('<div class="card"><h2>Stunden aus dem offiziellen Shiftbase-Bericht prüfen (CSV)</h2><p>Wenn die API keine vollständigen Zeitwerte liefert: In Shiftbase → Berichte → Arbeitszeitprotokoll detailliert den Monat und den Mitarbeiter auswählen und als <b>CSV</b> exportieren. Die Datei wird nur geprüft und nicht gespeichert.</p>')
    h.append('<form method="post" action="'+url_for('admin_shiftbase_csv_test')+'" enctype="multipart/form-data" class="actions">')
    h.append('<input type="hidden" name="csrf_token" value="'+shiftbase_escape(_sb_csrf_token(),quote=True)+'"><input type="hidden" name="year" value="'+str(year)+'"><input type="hidden" name="month" value="'+str(month)+'">')
    _csv_options=''
    for _r in _csv_choices:
        _selected=' selected' if 'kaan aysel' in _r['name'].casefold() else ''
        _csv_options+='<option value="'+str(_r['driver_id'])+'"'+_selected+'>'+shiftbase_escape(_r['name'])+'</option>'
    h.append('<label>Fahrer <select name="driver_id" required style="max-width:260px">'+_csv_options+'</select></label>')
    h.append('<label>Shiftbase-CSV <input type="file" name="timesheet_csv" accept=".csv,.txt,text/csv" required></label>')
    h.append('<button type="submit" class="primary" style="width:auto"'+('' if _csv_choices else ' disabled')+'>CSV prüfen</button></form></div>')
    if report:
        h.append('<div class="card"><h2>Monatsvergleich</h2>')
        h.append(f'<p>Shiftbase: {report["api_users"]} Benutzer, {report["api_timesheets"]} Zeiteinträge, {report["api_absences"]} Abwesenheiten. Nicht zuordenbare Zeiteinträge: {report["ignored_entries"]}.</p>')
        if report['ignored_entries']:
            diag=report['diagnostic']
            h.append('<div class="flash err"><b>Technische Diagnose der Shiftbase-Daten (ohne Personendaten):</b> '
                     + f'Einträge ohne erkannte Mitarbeiter-ID: {diag["missing_user_ids"]}; ohne erkanntes Datum: {diag["missing_dates"]}. '
                     + 'Die fehlenden API-Felder müssen im Code zugeordnet werden. '
                     + 'Sichtbare Feldnamen (keine Werte): <code>'
                     + shiftbase_escape(', '.join(diag['example_field_names']))+'</code>.')
            if diag['nested_field_names']:
                h.append(' Unterfelder: <code>' + shiftbase_escape(json.dumps(diag['nested_field_names'],ensure_ascii=False)) + '</code>.')
            h.append('</div>')
        if report['diagnostic']['missing_hour_units']:
            detail_stats=report['diagnostic'].get('detail',{})
            h.append('<div class="flash" style="background:#fff8e5;color:#92400e;border:1px solid #f3c77d"><b>API-Zeiten unvollständig:</b> '
                     +str(report['diagnostic']['missing_hour_units'])+' Einträge liefern keine sicher berechenbaren Arbeitsstunden. '
                     +'Einzelabruf: '+str(detail_stats.get('detail_resolved',0))+' zusätzliche Einträge erfolgreich ausgewertet. '
                     +'Falls der Einzelabruf keine Stunden liefert, importiere unten den Shiftbase-CSV-Bericht mit der Spalte <b>Gearbeitet</b>. '
                     +'Die API-Monatssumme wird absichtlich nicht als 0 angezeigt oder erfunden.</div>')
        h.append('<div class="table-wrap"><table><thead><tr><th>Fahrer</th><th>Shiftbase-ID</th><th>Shiftbase Std.</th><th>Abrechnung Std.</th><th>Differenz</th><th>Abwesenheiten</th><th>Hinweise</th></tr></thead><tbody>')
        for r in report['results']:
            fmt=lambda v: '–' if v is None else f'{v:.2f}'.replace('.',',')
            def fmt_work(v):
                if v is None: return '–'
                mins = round(v*60)
                return f'{fmt(v)} ({mins//60}:{mins%60:02d})' 
            desc='; '.join(f'{a["art"]}: {a["von"]}–{a["bis"]} ({a["status"]})' for a in r['absences']) or '–'
            # Link only for securely mapped staff; no timesheet write actions.
            _day_link = ('<a href="'+url_for('admin_shiftbase_tagesuebersicht',year=year,month=month,driver_id=r['driver_id'])+'">Tage anzeigen</a>' if r['shiftbase_user_id'] else '')
            _cells = [shiftbase_escape(str(v)) for v in (r['fahrer'],r['shiftbase_user_id'] or 'nicht zugeordnet',fmt_work(r['timesheet_hours']),fmt(r['payroll_hours']),fmt(r['difference']),desc,'; '.join(r['notes']) or 'OK')]
            _cells[-1] += (' · '+_day_link) if _day_link else ''
            h.append('<tr>'+''.join('<td>'+v+'</td>' for v in _cells)+'</tr>')
        h.append('</tbody></table></div>')
        h.append(f'<p><a class="btn small" href="{url_for("admin_shiftbase_abgleich_csv",year=year,month=month)}">CSV-Prüfbericht herunterladen</a></p></div>')
    h.append('<div class="card"><h2>Fahrer einmalig zuordnen</h2><p>Die ID muss aus Shiftbase stammen. Es erfolgt bewusst keine automatische Zuordnung nur anhand ähnlicher Namen.</p>')
    if sb_users:
        options=''.join(f'<option value="{shiftbase_escape(uid,quote=True)}">{shiftbase_escape(_sb_user_display(x))} (ID {shiftbase_escape(uid)})</option>' for uid,x in sorted(sb_users.items(),key=lambda kv: _sb_user_display(kv[1]).lower()))
        h.append('<p><b>Alle Zuordnungen in einem Schritt speichern:</b> Beliebig viele Fahrer auswählen, anschließend unten einmal „Alle Änderungen speichern“ anklicken. Bereits gespeicherte Einträge bleiben erhalten, sofern sie nicht geändert werden.</p>')
        h.append('<form id="sb-mapping-bulk" method="post" action="'+url_for('admin_shiftbase_mapping_bulk')+'">'
                 '<input type="hidden" name="csrf_token" value="'+shiftbase_escape(_sb_csrf_token(),quote=True)+'">'
                 '<input type="hidden" name="year" value="'+str(year)+'"><input type="hidden" name="month" value="'+str(month)+'">')
        h.append('<div class="table-wrap"><table style="min-width:680px"><tr><th>Fahrer in Cloud</th><th>Shiftbase-Benutzer</th></tr>')
        for r in local:
            selected=mapped.get(r['driver_id'])
            select_options='<option value="">— keine Zuordnung —</option>'
            for uid,u in sorted(sb_users.items(),key=lambda kv: _sb_user_display(kv[1]).lower()):
                select_options+=f'<option value="{shiftbase_escape(uid,quote=True)}" {"selected" if uid==selected else ""}>{shiftbase_escape(_sb_user_display(u))} (ID {shiftbase_escape(uid)})</option>'
            h.append('<tr><td>'+shiftbase_escape(r['name'])+'</td><td><select class="sb-map-select" '
                     'name="map_'+str(r['driver_id'])+'" data-original="'+shiftbase_escape(selected or '',quote=True)+'">'
                     +select_options+'</select></td></tr>')
        h.append('</table></div><div class="actions" style="margin-top:14px">'
                 '<button class="primary" type="submit" id="sb-map-save" style="width:auto">Alle Änderungen speichern</button>'
                 '<span id="sb-map-changed" class="muted" role="status">Noch keine Änderungen</span></div></form>')
        h.append(r"""<script>(function(){const form=document.getElementById('sb-mapping-bulk');if(!form)return;
const fields=Array.from(form.querySelectorAll('.sb-map-select'));
function refresh(){const num=fields.filter(x=>x.value!==x.dataset.original).length;
document.getElementById('sb-map-changed').textContent=num?num+' geänderte Zuordnung(en)':'Noch keine Änderungen';
form.querySelector('#sb-map-save').disabled=!num;}
fields.forEach(x=>x.addEventListener('change',refresh));
form.addEventListener('submit',function(e){refresh();if(form.querySelector('#sb-map-save').disabled)e.preventDefault();});refresh();})();</script>""")
    else:
        h.append('<p class="muted">Klicke zuerst oben auf „Shiftbase auslesen & vergleichen“. Danach werden die Benutzer zur eindeutigen Zuordnung angezeigt.</p>')
    h.append('</div>')
    return base_page('Shiftbase-Abgleich',''.join(h),'shiftbase')


@app.post('/admin/shiftbase/mapping')
@admin_login_required
def admin_shiftbase_mapping():
    csrf=session.get('shiftbase_csrf','')
    if not csrf or not hmac.compare_digest(csrf,str(request.form.get('csrf_token',''))):
        abort(403,'Sicherheitsprüfung fehlgeschlagen')
    try:
        did=int(request.form['driver_id'])
        year=int(request.form['year']); month=int(request.form['month'])
    except (KeyError,ValueError,TypeError):
        abort(400)
    uid=str(request.form.get('shiftbase_user_id','')).strip()
    if uid and not re.fullmatch('[0-9]{1,18}',uid):
        abort(400,'Ungültige Shiftbase-ID')
    with db_conn() as conn:
        _sb_ensure_mapping_table(conn)
        if not conn.execute('SELECT id FROM drivers WHERE id=? AND is_active=1',(did,)).fetchone():
            abort(400,'Fahrer nicht vorhanden')
        conn.execute('DELETE FROM shiftbase_driver_map WHERE driver_id=?',(did,))
        if uid:
            try:
                conn.execute('INSERT INTO shiftbase_driver_map(driver_id,shiftbase_user_id,updated_at) VALUES(?,?,?)',(did,uid,now_iso()))
                conn.commit()
            except Exception:
                # In case a mapping already exists, do not silently assign one employee twice.
                conn.raw_conn.rollback() if hasattr(conn,'raw_conn') else conn.rollback()
                flash('Diese Shiftbase-ID ist bereits einem anderen Fahrer zugeordnet.','err')
                return redirect(url_for('admin_shiftbase_abgleich',year=year,month=month,laden=1))
        else:
            conn.commit()
    flash('Zuordnung gespeichert.','ok')
    return redirect(url_for('admin_shiftbase_abgleich',year=year,month=month,laden=1))


@app.post('/admin/shiftbase/mapping/bulk')
@admin_login_required
def admin_shiftbase_mapping_bulk():
    """Atomically save only changed Cloud↔Shiftbase mappings.

    Validate the entire resulting set before any DELETE/INSERT. Existing
    mappings survive invalid or duplicate choices, including ID swaps.
    """
    _sb_verified_post_csrf(request.form)
    try:
        year = int(request.form.get('year', 0))
        month = int(request.form.get('month', 0))
        if not 2020 <= year <= 2100 or not 1 <= month <= 12:
            raise ValueError('Ungültiger Monat.')
        received = {int(k[4:]): str(v).strip() for k, v in request.form.items()
                    if re.fullmatch(r'map_[0-9]{1,12}', k)}
        if not received or len(received) > 500:
            raise ValueError('Es wurden keine gültigen Fahrer übermittelt.')
        if any(uid and not re.fullmatch(r'[0-9]{1,18}', uid)
               for uid in received.values()):
            raise ValueError('Ungültige Shiftbase-ID.')
        with db_conn() as conn:
            _sb_ensure_mapping_table(conn)
            active = {int(r['id']) for r in conn.execute(
                'SELECT id FROM drivers WHERE is_active=1 AND COALESCE(is_disposition,0)=0'
            ).fetchall()}
            if not set(received).issubset(active):
                raise ValueError('Unbekannter oder inaktiver Fahrer in der Auswahl.')
            existing = _sb_mapping(conn)
            result = dict(existing)
            changed = {did: uid for did, uid in received.items()
                       if existing.get(did, '') != uid}
            for did, uid in changed.items():
                if uid:
                    result[did] = uid
                else:
                    result.pop(did, None)
            if len(set(result.values())) != len(result):
                raise ValueError('Eine Shiftbase-ID ist mehrfach ausgewählt. Nichts wurde gespeichert.')
            if changed:
                # Delete all changed rows first to support legitimate swaps.
                for did in changed:
                    conn.execute('DELETE FROM shiftbase_driver_map WHERE driver_id=?', (did,))
                for did, uid in changed.items():
                    if uid:
                        conn.execute('INSERT INTO shiftbase_driver_map '
                                     '(driver_id,shiftbase_user_id,updated_at) VALUES(?,?,?)',
                                     (did, uid, now_iso()))
                conn.commit()
        flash(str(len(changed))+' Zuordnung(en) gemeinsam gespeichert.' if changed
              else 'Keine Zuordnungen verändert.', 'ok')
    except (ValueError, TypeError) as exc:
        flash('Keine Zuordnung gespeichert: '+str(exc), 'err')
    return redirect(url_for('admin_shiftbase_abgleich', year=year if 'year' in locals() and 2020<=year<=2100 else 2026,
                            month=month if 'month' in locals() and 1<=month<=12 else 11,
                            laden=1, erweitert=1))


@app.get('/admin/shiftbase/export.csv')
@admin_login_required
def admin_shiftbase_abgleich_csv():
    year,month=_sb_params()
    try:
        report=_sb_report_for_month(year,month)
    except ShiftbaseIntegrationError as exc:
        abort(503,str(exc))
    out=io.StringIO()
    writer=csv.writer(out,delimiter=';')
    writer.writerow(['Fahrer','Cloud-ID','Shiftbase-ID','Monat','Shiftbase-Arbeitsstunden','Cloud-Abrechnung','Abrechnung minus Arbeitszeit','Cloud-Urlaubstage (Anzahl)','Cloud-Krankheitstage','Shiftbase-Abwesenheiten','Prüfhinweise'])
    for r in report['results']:
        writer.writerow([r['fahrer'],r['external_driver_id'],r['shiftbase_user_id'],f'{month:02d}/{year}',r['timesheet_hours'],r['payroll_hours'],r['difference'],r['vacation_days_cloud'],r['sick_days_cloud'],json.dumps(r['absences'],ensure_ascii=False),'; '.join(r['notes'])])
    data=io.BytesIO(out.getvalue().encode('utf-8-sig'))
    return send_file(data,mimetype='text/csv',as_attachment=True,download_name=f'shiftbase_abgleich_{year}-{month:02d}.csv')


@app.get('/api/admin/shiftbase-abgleich')
def api_shiftbase_abgleich_json():
    admin_api_required()
    year,month=_sb_params()
    try:
        report=_sb_report_for_month(year,month)
        report.pop('users',None)
        return jsonify(report)
    except ShiftbaseIntegrationError as exc:
        return jsonify({'ok':False,'error':str(exc)}),503


# Einmalige, lesende Shiftbase-API-Formatdiagnose. Nur Kaan Aysel.
# Keine Änderungen an Shiftbase, keine Schlüssel oder fremde Mitarbeiterdaten im Bericht.
_SB_DIAG_TIMING_FIELDS = (
    'date', 'datetime', 'starttime', 'start_time', 'start_datetime',
    'endtime', 'end_time', 'end_datetime', 'break', 'clocked_break',
    'active_clock', 'clock', 'clocked_in', 'clocked_out',
    'worked_hours', 'total_worked_hours', 'hours_worked', 'duration_hours',
    'net_hours', 'total_hours', 'worked_minutes', 'duration_minutes',
    'worked_seconds', 'duration_seconds', 'hours', 'worked', 'duration', 'total',
)

def _sb_diag_safe_value(value, depth=0):
    """Only show whitelisted time values; never pass through names, GPS, IP or notes."""
    if value is None: return None
    if isinstance(value, bool): return value
    if isinstance(value, (int, float)):
        return value if abs(value) < 10**15 else 'Zahl zu groß (ausgeblendet)'
    if isinstance(value, str):
        return value[:90] if len(value) < 90 else 'Langer Text (ausgeblendet)'
    if isinstance(value, dict):
        if depth > 2: return 'Verschachteltes Objekt'
        out={}
        for k, v in list(value.items())[:30]:
            label=str(k)
            if label.casefold() in {'date','datetime','time','timezone','timezone_type','timestamp','value',
                                     'clocked_in','clocked_out','start','end','start_time','end_time','break',
                                     'hours','minutes','seconds','duration','worked_hours','total_hours'}:
                out[label]=_sb_diag_safe_value(v, depth+1)
            else:
                out[label]='[Wert ausgeblendet: '+type(v).__name__+']'
        return out
    if isinstance(value, list):
        return '[Liste, '+str(len(value))+' Elemente; Werte ausgeblendet]'
    return '[Typ: '+type(value).__name__+']'


def _sb_diag_time_fields(ts):
    if not isinstance(ts, dict):
        return {'fehler':'Kein Timesheet-Objekt'}
    fields={}
    for name in _SB_DIAG_TIMING_FIELDS:
        v=_sb_get(ts,name)
        if v is not None:
            fields[name]=_sb_diag_safe_value(v)
    return {
        'alle_timesheet_feldtypen': {str(k):type(v).__name__ for k,v in list(ts.items())[:100]},
        'zeitfelder_mit_werten': fields,
        'berechnete_stunden_der_bisherigen_software': (str(_sb_hours(ts)) if _sb_hours(ts) is not None else 'NICHT BERECHENBAR'),
    }


@app.get('/admin/shiftbase/diagnose-kaan')
@admin_login_required
def admin_shiftbase_kaan_diagnose():
    year,month=_sb_params()
    with db_conn() as conn:
        matches=conn.execute('SELECT id FROM drivers WHERE lower(name)=lower(?) AND is_active=1',('Kaan Aysel',)).fetchall()
        if len(matches)!=1:
            return base_page('Shiftbase – Diagnose Kaan', '<div class="card"><h2>Kein eindeutiger Cloud-Eintrag für Kaan Aysel</h2><p>Bitte zunächst den Fahrer eindeutig anlegen.</p></div>', 'shiftbase'), 422
        uid=_sb_mapping(conn).get(int(matches[0]['id']))
    if not uid:
        return base_page('Shiftbase – Diagnose Kaan', '<div class="card"><h2>Kaan Aysel ist noch nicht zugeordnet</h2><p>Bitte auf der Seite Shiftbase-Abgleich zuerst den Shiftbase-Benutzer zuordnen.</p></div>', 'shiftbase'), 422
    start,end=_sb_month_window(year,month)
    try:
        items=_shiftbase_get_all('timesheets',{'min_date':start,'max_date':end,'user_id':uid})
        selected=[(r,_sb_timesheet_parts(r)) for r in items if _sb_timesheet_parts(r)[0]==uid and _sb_timesheet_parts(r)[1] and start<=_sb_timesheet_parts(r)[1]<=end]
        selected.sort(key=lambda t:t[1][1])
        if not selected:
            diagnostic={'status':'Keine Zeiteinträge für Kaan Aysel im ausgewählten Monat gefunden.','api_zeilen_gesamt':len(items),'monat':f'{year}-{month:02d}'}
        else:
            sample,parts=selected[0]
            ts=_sb_get(sample,'Timesheet')
            if not isinstance(ts,dict): ts=sample
            diagnostic={
              'status':'Nur-Lese-Diagnose abgeschlossen',
              'monat':f'{year}-{month:02d}',
              'fuer_kaan_gefundene_schichten':len(selected),
              'ein_beispiel_aus_der_monatsliste':_sb_diag_time_fields(ts),
              'einzelabruf_desselben_schichtdatensatzes':'nicht versucht',
            }
            ident=parts[3]
            if ident:
                try:
                    single=_shiftbase_read_json('timesheet_detail',{'_detail_id':ident})
                    detail=_sb_get(single,'Timesheet')
                    if not isinstance(detail,dict):
                        detail=_sb_get(single,'data')
                    if not isinstance(detail,dict): detail=single
                    diagnostic['einzelabruf_desselben_schichtdatensatzes']=_sb_diag_time_fields(detail)
                except ShiftbaseIntegrationError as e:
                    diagnostic['einzelabruf_desselben_schichtdatensatzes']='Nicht verfügbar: '+str(e)
    except ShiftbaseIntegrationError as e:
        diagnostic={'status':'API-Abruf fehlgeschlagen', 'hinweis':str(e)}
    dumped=json.dumps(diagnostic,ensure_ascii=False,indent=2)
    back=url_for('admin_shiftbase_abgleich',year=year,month=month,laden=1)
    page=('<div class="card"><h2>Kaan Aysel – Shiftbase-API-Feldprüfung</h2>'
          '<p>Nur Oktober bzw. gewählter Monat, nur Kaan, nur Lesen. Dies zeigt ausschließlich technische Zeitfelder und deren Typen, keine IP-Adressen, GPS, Namen anderer Mitarbeiter oder API-Schlüssel.</p>'
          '<p><b>Bitte einen Screenshot von diesem Bericht schicken.</b> Die Arbeitszeit wird nicht verändert.</p>'
          '<div style="overflow:auto"><pre style="white-space:pre-wrap;word-break:break-word;padding:12px;border-radius:12px;background:#f3f6fb">'+shiftbase_escape(dumped)+'</pre></div>'
          '<a class="btn small" href="'+shiftbase_escape(back,quote=True)+'">Zurück zum Monatsvergleich</a></div>')
    response=make_response(base_page('Kaan Aysel – Shiftbase-Feldprüfung',page,'shiftbase'))
    response.headers['Cache-Control']='no-store'
    response.headers['X-Robots-Tag']='noindex, nofollow'
    return response



# =================== Shiftbase Tagesschichten (nur lesen) ===================

def _sb_dayview_hm(hours):
    """Return HH:MM without inventing unknown/partial source hours."""
    if hours is None:
        return 'nicht verfügbar'
    value = Decimal(str(hours))
    if not value.is_finite() or value < 0:
        return 'nicht verfügbar'
    total_minutes = int((value * Decimal(60)).quantize(Decimal('1')))
    return f'{total_minutes // 60}:{total_minutes % 60:02d}'


def _sb_dayview_clock(value):
    if isinstance(value, str) and re.fullmatch(r'\d{1,2}:\d{2}(?::\d{2})?',value.strip()):
        return value.strip()[:5]
    return '–'


def _sb_dayview_break(value):
    if value is None or value == '':
        return '–'
    minutes = _sb_break_as_minutes(value)
    if minutes is None:
        return 'Format prüfen'
    return f'{int(minutes)} Min.' if minutes == minutes.to_integral_value() else str(minutes)+' Min.'


def _sb_dayview_entries(times, uid, year, month):
    """Filter locally even if Shiftbase ignores the API user_id parameter."""
    start, end = _sb_month_window(year,month)
    records=[]
    for entry in times:
        euid, day, hours, entry_id = _sb_timesheet_parts(entry)
        if euid != uid or day is None or not (start <= day <= end):
            continue
        ts = _sb_get(entry,'Timesheet')
        if not isinstance(ts,dict):
            ts=entry
        # Declined records remain visible in Shiftbase's audit trail but must
        # not count as active actual worked hours in the reconciliation.
        if str(_sb_value(ts,'status') or '').strip().lower() in {'declined','rejected','abgelehnt'}:
            continue
        if str(_sb_get(ts,'deleted') or '').strip().lower() in {'1','true','yes'}:
            continue
        records.append({
            'day':day, 'entry_id':entry_id or '',
            'begin':_sb_dayview_clock(_sb_value(ts,'starttime','start_time')),
            'end':_sb_dayview_clock(_sb_value(ts,'endtime','end_time')),
            'break':_sb_dayview_break(_sb_value(ts,'break')),
            'paid_break':_sb_dayview_break(_sb_value(ts,'paid_break')),
            'hours':hours,
            'status':str(_sb_value(ts,'status') or '–')[:48],
            'deleted':str(_sb_get(ts,'deleted') or '').strip().lower() not in ('', '0', 'false', 'no', 'none', 'null'),
        })
    return sorted(records,key=lambda d:(d['day'],d['begin'],d['entry_id']))


@app.get('/admin/shiftbase/tagesuebersicht')
@admin_login_required
def admin_shiftbase_tagesuebersicht():
    """Admin-only read view. Does not send PATCH/POST/PUT/DELETE to Shiftbase."""
    year, month = _sb_params()
    try:
        driver_id_raw=request.args.get('driver_id','').strip()
        if driver_id_raw:
            if not re.fullmatch(r'[0-9]{1,12}', driver_id_raw):
                abort(400,'Ungültige Fahrer-ID')
            driver_id=int(driver_id_raw)
        else:
            driver_id=None
        with db_conn() as conn:
            _sb_ensure_mapping_table(conn)
            if driver_id is not None:
                match=conn.execute('SELECT id,name,is_active FROM drivers WHERE id=? AND is_active=1',(driver_id,)).fetchone()
            else:
                matches=conn.execute('SELECT id,name,is_active FROM drivers WHERE lower(name)=lower(?) AND is_active=1',('Kaan Aysel',)).fetchall()
                match=matches[0] if len(matches)==1 else None
            if not match:
                abort(404,'Fahrer nicht eindeutig gefunden')
            did=int(match['id'])
            uid=_sb_mapping(conn).get(did)
            # `monthly_data` may be missing; a missing row is not 0 actual hours.
            payroll_row=conn.execute('SELECT payroll_hours FROM monthly_data WHERE driver_id=? AND year=? AND month=?',(did,year,month)).fetchone()
            payroll = Decimal(str(payroll_row['payroll_hours'])) if payroll_row and payroll_row['payroll_hours'] is not None else None
            driver_name=str(match['name'])
        if not uid:
            raise ShiftbaseIntegrationError('Der Fahrer ist noch keiner Shiftbase-ID zugeordnet. Bitte zunächst die Zuordnung speichern.')
        start,end=_sb_month_window(year,month)
        # One bulk GET; keep a local user filter to prevent unrelated rows leaking into this view.
        items=_shiftbase_get_all('timesheets',{'min_date':start,'max_date':end,'user_id':uid})
        rows=_sb_dayview_entries(items,uid,year,month)
        if rows and all(r['hours'] is not None for r in rows):
            total=sum((r['hours'] for r in rows),Decimal('0'))
        else:
            total=None
        # Absences are a separate type of record and never added to actual worked hours.
        absences=_shiftbase_get_all('absentees',{'min_date':start,'max_date':end,'user_id':uid})
        selected_abs=[]
        for ab_entry in absences:
            a = _sb_get(ab_entry,'Absentee')
            if not isinstance(a,dict): a=ab_entry
            u = _sb_get(ab_entry,'User')
            au = (_sb_id(u,'id','user_id') or _sb_id(a,'user_id','user','employee_id') or _sb_id(ab_entry,'user_id','user','employee_id'))
            if au != uid:
                continue
            astart=_sb_day(_sb_value(a,'start_date','min_date','start','date'))
            aend=_sb_day(_sb_value(a,'end_date','max_date','end')) or astart
            if astart and aend and astart<=end and aend>=start:
                selected_abs.append((max(astart,start),min(aend,end),_sb_absence_name(a),str(_sb_value(a,'status') or '–')))
    except ShiftbaseIntegrationError as exc:
        result=('<div class="card"><h2>Shiftbase-Tagesübersicht</h2><div class="flash err">'+shiftbase_escape(str(exc))+'</div>'
                +'<a class="btn small" href="'+url_for('admin_shiftbase_abgleich',year=year,month=month,laden=1)+'">Zurück zum Monatsvergleich</a></div>')
        return base_page('Shiftbase-Tagesübersicht',result,'shiftbase'),422

    h=[]
    h.append('<div class="card"><h2>Schichten von '+shiftbase_escape(driver_name)+' – '+f'{month:02d}/{year}'+'</h2>')
    h.append('<p><b>Shiftbase-ID:</b> '+shiftbase_escape(uid)+' &nbsp; <b>Schichten:</b> '+str(len(rows))+'</p>')
    h.append('<div class="grid grid-3">')
    h.append('<div class="kpi">Arbeitsstunden laut Shiftbase<b>'+_sb_dayview_hm(total)+'</b></div>')
    h.append('<div class="kpi">Abrechnung laut Cloud<b>'+(_sb_dayview_hm(payroll) if payroll is not None else 'nicht hinterlegt')+'</b></div>')
    h.append('<div class="kpi">Abrechnung minus Arbeitsstunden<b>'+(_sb_dayview_hm(payroll-total) if payroll is not None and total is not None and payroll>=total else ('−'+_sb_dayview_hm(total-payroll) if payroll is not None and total is not None else 'nicht berechenbar'))+'</b></div>')
    h.append('</div><p class="muted">Arbeitszeit und vergütete Zeit werden getrennt ausgewiesen. Diese Seite ändert keine Einträge in Shiftbase.</p>')
    h.append('<p><b>API-Schreibstatus:</b> Lesen erfolgreich; tatsächliche PUT-Verifikation nur nach bewusst ausgelöster, belegter Korrektur und erneutem Einzel-GET möglich. Dienstplanänderung ist keine Arbeitszeitkorrektur.</p>')
    h.append('<p><a class="btn primary" style="width:auto" href="'+url_for('admin_shiftbase_monatsabgleich_csv',year=year,month=month,driver_id=did)+'">Ein-Klick-Lohnabgleich (CSV) herunterladen</a></p>')
    h.append('<p><a class="btn primary" style="width:auto" href="'+url_for('admin_shiftbase_pruefvorschau',year=year,month=month,driver_id=did)+'">Abgleichen / Korrekturen prüfen</a></p>')
    h.append('<p class="muted">Der Export enthält die nachgewiesenen Tagesstunden und den gesonderten Abrechnungswert. Keine automatische Veränderung der Arbeitszeitprotokolle.</p>')
    h.append('<p><a class="btn small" href="'+url_for('admin_shiftbase_abgleich',year=year,month=month,laden=1)+'">Zurück zum Monatsvergleich</a></p></div>')
    h.append('<div class="card"><h2>Tagesübersicht</h2>')
    if not rows:
        h.append('<div class="flash err">Für diesen Fahrer wurden im ausgewählten Monat keine Schichten gefunden.</div>')
    elif total is None:
        h.append('<div class="flash err">Mindestens eine Schicht enthält keinen zuverlässig auswertbaren Stundenwert. Die Summe wurde bewusst nicht geschätzt.</div>')
    h.append('<div class="table-wrap"><table style="min-width:900px"><thead><tr><th>Datum</th><th>Beginn</th><th>Ende</th><th>Unbezahlte Pause</th><th>Bezahlte Pause</th><th>Arbeitsstunden</th><th>Status</th></tr></thead><tbody>')
    for row in rows:
        day_label=shiftbase_date.fromisoformat(row['day']).strftime('%d.%m.%Y')
        status=row['status']+(' · gelöscht markiert' if row['deleted'] else '')
        cells=(day_label,row['begin'],row['end'],row['break'],row['paid_break'],_sb_dayview_hm(row['hours']),status)
        h.append('<tr>'+''.join('<td>'+shiftbase_escape(str(value))+'</td>' for value in cells)+'</tr>')
    h.append('</tbody></table></div></div>')
    h.append('<div class="card"><h2>Urlaub / Krankheit / sonstige Abwesenheiten</h2>')
    if selected_abs:
        h.append('<div class="table-wrap"><table style="min-width:650px"><tr><th>Von</th><th>Bis</th><th>Art</th><th>Status</th></tr>')
        for fr,to,kind,status in sorted(selected_abs):
            h.append('<tr>'+''.join('<td>'+shiftbase_escape(str(v))+'</td>' for v in (fr,to,kind,status))+'</tr>')
        h.append('</table></div>')
    else:
        h.append('<p>Keine zugeordneten Abwesenheiten im ausgewählten Zeitraum gefunden. Dies ist keine Bestätigung, dass keine Abwesenheit stattgefunden hat.</p>')
    h.append('<p class="muted">Abwesenheiten sind nicht in der Summe tatsächlich geleisteter Arbeitsstunden enthalten. Abrechnungsrelevante Ausfallzeiten müssen gesondert bewertet werden.</p></div>')
    resp=make_response(base_page('Shiftbase-Tagesübersicht', ''.join(h), 'shiftbase'))
    resp.headers['Cache-Control']='no-store'
    resp.headers['X-Robots-Tag']='noindex, nofollow'
    return resp
# =================== Ende Shiftbase Tagesschichten ===================



# ============== Ein-Klick-Lohnabgleich: keine Timesheet-Schreibzugriffe ==============
def _sb_monthly_reconciliation_data(day_rows, payroll_hours, absence_ranges, year, month):
    """Pure data transformation: never changes real time entries or allocates fictitious time.

    All amounts in hours are Decimal. Absence ranges are inclusive ISO dates;
    statuses are retained and nothing is silently treated as a legal break.
    """
    if not isinstance(day_rows,list):
        raise ValueError('Schichtliste fehlt')
    if any(row.get('hours') is None for row in day_rows):
        raise ValueError('Arbeitsstunden sind nicht vollständig aus Shiftbase abrufbar.')
    # An empty verified month is a legitimate 0:00, e.g. after rejecting an
    # erroneous only entry. Do not invent hours to match payroll.
    actual=sum((Decimal(str(row['hours'])) for row in day_rows),Decimal('0'))
    payroll=Decimal(str(payroll_hours)) if payroll_hours is not None else None
    if payroll is not None and (not payroll.is_finite() or payroll<0):
        raise ValueError('Ungültige Abrechnungsstunden')
    month_first=shiftbase_date(year,month,1).isoformat()
    month_last=_sb_month_window(year,month)[1]
    absence_index={}
    for st, en, kind, status in absence_ranges:
        if not st or not en:
            continue
        if status.strip().lower() in {'declined','abgelehnt','rejected'}:
            continue
        # At most 31 days: range expansion is bounded to selected month.
        b=max(st,month_first); e=min(en,month_last)
        if b>e: continue
        cur=shiftbase_date.fromisoformat(b)
        end=shiftbase_date.fromisoformat(e)
        while cur<=end:
            absence_index.setdefault(cur.isoformat(),[]).append(kind+' ('+status+')')
            cur+=shiftbase_timedelta(days=1)
    detailed=[]
    for row in day_rows:
        day=str(row['day'])
        notes=[]
        begin=str(row.get('begin','–'))
        hours=Decimal(str(row['hours']))
        if hours<0 or not hours.is_finite():
            raise ValueError('Ungültige Stunden in einer Schicht')
        if begin != '–' and re.fullmatch(r'\d{1,2}:\d{2}', begin) and begin<'06:00':
            notes.append('Beginn vor 06:00 – prüfen')
        if hours>10:
            notes.append('Mehr als 10 Arbeitsstunden – prüfen')
        # Break field from Shiftbase is in minutes; unknown breaks are never assumed.
        unpaid=str(row.get('break','–'))
        pause_minutes=None
        if re.fullmatch(r'\d+ Min\.',unpaid):
            pause_minutes=int(unpaid.split()[0])
        if hours>9 and pause_minutes is None:
            notes.append('Pausenwert fehlt – tatsächliche Pause prüfen')
        elif hours>9 and pause_minutes<45:
            notes.append('Pausenaufzeichnung unter 45 Minuten – prüfen')
        if day in absence_index:
            notes.append('Gleichzeitige Abwesenheit – prüfen')
        if row.get('deleted'):
            notes.append('Als gelöscht gekennzeichnet – prüfen')
        detailed.append({**row,'hours_hm':_sb_dayview_hm(hours),
                         'absence':'; '.join(absence_index.get(day,[])),
                         'flags':'; '.join(notes)})
    return {'actual':actual,'payroll':payroll,
            'difference':payroll-actual if payroll is not None else None,
            'rows':detailed,'flag_count':sum(bool(x['flags']) for x in detailed),
            'total_rows':len(detailed)}


def _sb_csv_guard(value):
    """Avoid spreadsheet formula injection in CSV from Shiftbase fields or notes."""
    value=str(value if value is not None else '')
    return "'"+value if value.lstrip().startswith(('=','+','-','@','\t','\r')) else value


@app.get('/admin/shiftbase/lohnbewertung.csv')
@admin_login_required
def admin_shiftbase_monatsabgleich_csv():
    """One-click, admin-only, employee-scoped read-only monthly reconciliation."""
    import io as _io
    import csv as _csv
    year,month=_sb_params()
    driver_id_raw=request.args.get('driver_id','').strip()
    if not re.fullmatch(r'[0-9]{1,12}',driver_id_raw):
        abort(400,'Ungültige Fahrer-ID')
    driver_id=int(driver_id_raw)
    try:
        with db_conn() as conn:
            _sb_ensure_mapping_table(conn)
            driver=conn.execute('SELECT id,name FROM drivers WHERE id=? AND is_active=1',(driver_id,)).fetchone()
            if not driver:
                abort(404,'Fahrer nicht gefunden')
            uid=_sb_mapping(conn).get(driver_id)
            monthly=conn.execute('SELECT payroll_hours FROM monthly_data WHERE driver_id=? AND year=? AND month=?',(driver_id,year,month)).fetchone()
            payroll=monthly['payroll_hours'] if monthly and monthly['payroll_hours'] is not None else None
            driver_name=str(driver['name'])
        if not uid:
            raise ShiftbaseIntegrationError('Fahrer noch nicht Shiftbase zugeordnet.')
        start,end=_sb_month_window(year,month)
        times=_shiftbase_get_all('timesheets',{'min_date':start,'max_date':end,'user_id':uid})
        rows=_sb_dayview_entries(times,uid,year,month)
        absences=_shiftbase_get_all('absentees',{'min_date':start,'max_date':end,'user_id':uid})
        abs_ranges=[]
        for a in absences:
            sub=_sb_get(a,'Absentee')
            if not isinstance(sub,dict): sub=a
            au=_sb_id(_sb_get(a,'User'),'id','user_id') or _sb_id(sub,'user_id','user','employee_id') or _sb_id(a,'user_id','user','employee_id')
            if au!=uid: continue
            fr=_sb_day(_sb_value(sub,'start_date','min_date','start','date'))
            to=_sb_day(_sb_value(sub,'end_date','max_date','end')) or fr
            if fr and to:
                abs_ranges.append((fr,to,_sb_absence_name(sub),str(_sb_value(sub,'status') or 'unbekannt')))
        result=_sb_monthly_reconciliation_data(rows,payroll,abs_ranges,year,month)
    except (ShiftbaseIntegrationError,ValueError,ArithmeticError) as exc:
        return base_page('Lohnabgleich nicht möglich',
            '<div class="card"><h2>Lohnabgleich nicht möglich</h2><div class="flash err">'+shiftbase_escape(str(exc))+'</div><p>Es wurden keine Daten verändert.</p></div>',
            'shiftbase'),422

    out=_io.StringIO(newline='')
    w=_csv.writer(out,delimiter=';',quoting=_csv.QUOTE_MINIMAL)
    w.writerow(['Lohnabgleich / Arbeitszeitkontrolle – kein geänderter Arbeitszeitnachweis'])
    w.writerow(['Fahrer',_sb_csv_guard(driver_name)])
    w.writerow(['Shiftbase-ID',uid])
    w.writerow(['Monat',f'{month:02d}/{year}'])
    w.writerow(['Tatsächliche Arbeitsstunden laut Shiftbase',_sb_dayview_hm(result['actual'])])
    w.writerow(['Abrechnungsstunden laut Cloud',_sb_dayview_hm(result['payroll']) if result['payroll'] is not None else 'nicht hinterlegt'])
    w.writerow(['Differenz Abrechnung minus Arbeitsstunden',
                ('−'+_sb_dayview_hm(-result['difference']) if result['difference'] is not None and result['difference']<0
                 else _sb_dayview_hm(result['difference']) if result['difference'] is not None else 'nicht berechenbar')])
    w.writerow(['Hinweis','Abrechnungsdifferenzen sind keine nachträglichen Änderungen tatsächlich geleisteter Arbeitszeit.'])
    w.writerow(['Prüfhinweise',str(result['flag_count'])])
    w.writerow([])
    w.writerow(['Datum','Beginn','Ende','Unbezahlte Pause','Bezahlte Pause','Arbeitsstunden','Status','Abwesenheit','Prüfhinweis'])
    for r in result['rows']:
        w.writerow([_sb_csv_guard(z) for z in (r['day'],r['begin'],r['end'],r['break'],r['paid_break'],
                                                  r['hours_hm'],r['status'],r['absence'],r['flags'])])
    data=_io.BytesIO(('\ufeff'+out.getvalue()).encode('utf-8'))
    data.seek(0)
    filename=f'shiftbase_lohnabgleich_fahrer-{driver_id}_{year}-{month:02d}.csv'
    resp=send_file(data,mimetype='text/csv; charset=utf-8',as_attachment=True,download_name=filename)
    resp.headers['Cache-Control']='private, no-store, max-age=0'
    resp.headers['X-Robots-Tag']='noindex, nofollow'
    return resp
# ============== Ende Ein-Klick-Lohnabgleich ==============



# ============ Shiftbase-Monatsvorschau (hypothetisch) + geprüfte Istkorrekturen ============
# Abrechnungsstunden sind ein Vergleichswert, keine Quelle für erfundene
# Zeiterfassungsdaten. Zeitkorrekturen nur anhand verifizierter Istzeiten.
# Manuelle Änderungen werden ausschließlich als Entwurf lokal gespeichert.

def _sb_review_table(conn):
    conn.execute("""CREATE TABLE IF NOT EXISTS shiftbase_review_drafts (
        driver_id INTEGER NOT NULL,
        year INTEGER NOT NULL,
        month INTEGER NOT NULL,
        timesheet_id TEXT NOT NULL,
        original_json TEXT NOT NULL,
        corrected_json TEXT NOT NULL,
        evidence TEXT NOT NULL,
        updated_at TEXT NOT NULL,
        PRIMARY KEY(driver_id, year, month, timesheet_id)
    )""")


def _sb_review_row_obj(r):
    return {'day': str(r['day']), 'start': str(r['begin']),
            'end': str(r['end']), 'break_minutes': _sb_review_minute_text(r['break']),
            'hours': _sb_dayview_hm(r['hours'])}


def _sb_review_minute_text(value):
    m = re.fullmatch(r'(\d+) Min\.', str(value or '').strip())
    return m.group(1) if m else ''


def _sb_review_minutes(start, end, pause):
    if not re.fullmatch(r'\d{2}:\d{2}', start) or not re.fullmatch(r'\d{2}:\d{2}', end):
        raise ValueError('Uhrzeiten im Format HH:MM angeben.')
    sh, sm = map(int, start.split(':')); eh, em = map(int, end.split(':'))
    if sh>23 or eh>23 or sm>59 or em>59:
        raise ValueError('Ungültige Uhrzeit.')
    if not re.fullmatch(r'\d{1,4}', pause):
        raise ValueError('Pause in ganzen Minuten angeben.')
    pm = int(pause)
    if not 0 <= pm <= 600:
        raise ValueError('Ungültige Pausenlänge.')
    first = sh*60+sm; last = eh*60+em
    if last <= first: last += 24*60  # Bestehende Nachtschicht möglich
    duration = last-first
    if duration>24*60 or duration<=0 or pm>duration:
        raise ValueError('Schichtdauer oder Pause ungültig.')
    return duration-pm, duration, pm


def _sb_review_absence_ranges(raw_absences, uid):
    result=[]
    for a in raw_absences:
        sub=_sb_get(a,'Absentee')
        if not isinstance(sub,dict): sub=a
        user=(_sb_id(_sb_get(a,'User'),'id','user_id')
              or _sb_id(sub,'user_id','user','employee_id')
              or _sb_id(a,'user_id','user','employee_id'))
        if user != uid: continue
        fr=_sb_day(_sb_value(sub,'start_date','min_date','start','date'))
        to=_sb_day(_sb_value(sub,'end_date','max_date','end')) or fr
        if fr and to:
            result.append((fr,to,_sb_absence_name(sub),str(_sb_value(sub,'status') or 'unbekannt')))
    return result


def _sb_review_source(driver_id, year, month, month_snapshot=None):
    if not isinstance(driver_id,int) or driver_id<=0: raise ShiftbaseIntegrationError('Ungültiger Fahrer')
    with db_conn() as conn:
        _sb_review_table(conn)
        driver=conn.execute('SELECT id,name,is_active FROM drivers WHERE id=? AND is_active=1',(driver_id,)).fetchone()
        if not driver: raise ShiftbaseIntegrationError('Fahrer nicht gefunden')
        uid=_sb_mapping(conn).get(driver_id)
        if not uid: raise ShiftbaseIntegrationError('Fahrer muss zuerst mit Shiftbase verbunden werden')
        mr=conn.execute('SELECT payroll_hours,vacation_days,sick_days FROM monthly_data WHERE driver_id=? AND year=? AND month=?',(driver_id,year,month)).fetchone()
        payroll=(Decimal(str(mr['payroll_hours'])) if mr and mr['payroll_hours'] is not None else None)
        vacation_count=str(mr['vacation_days'] or '').strip() if mr else ''
        sick_ranges=str(mr['sick_days'] or '').strip() if mr else ''
        drafts={str(r['timesheet_id']): dict(r) for r in conn.execute(
            'SELECT * FROM shiftbase_review_drafts WHERE driver_id=? AND year=? AND month=?',(driver_id,year,month)).fetchall()}
        name=str(driver['name'])
    start,end=_sb_month_window(year,month)
    times=(month_snapshot[0] if month_snapshot is not None else
           _shiftbase_get_all('timesheets',{'min_date':start,'max_date':end,'user_id':uid}))
    rows=_sb_dayview_entries(times,uid,year,month)
    # Preserve the original API list record of exactly this user and month.
    # Only validated list records may supplement OMITTED fields in the detail GET.
    raw_timesheets={}
    for entry in times:
        entry_uid, entry_day, _, entry_id = _sb_timesheet_parts(entry)
        if entry_uid == uid and entry_id and entry_day and start <= entry_day <= end:
            t = _sb_get(entry, 'Timesheet')
            raw_timesheets[str(entry_id)] = dict(entry)
    absences=(month_snapshot[1] if month_snapshot is not None else
              _shiftbase_get_all('absentees',{'min_date':start,'max_date':end,'user_id':uid}))
    absence_ranges=_sb_review_absence_ranges(absences,uid)
    try:
        result=_sb_monthly_reconciliation_data(rows,payroll,absence_ranges,year,month)
    except (ValueError,InvalidOperation) as exc:
        raise ShiftbaseIntegrationError('Monatsdaten sind unvollständig oder nicht plausibel: '+str(exc)) from exc
    if any(not re.fullmatch(r'[0-9]{1,20}', str(r['entry_id'])) for r in rows):
        raise ShiftbaseIntegrationError('Einige Schichten haben keine eindeutige Timesheet-ID. Änderungen bleiben gesperrt.')
    if len({str(r['entry_id']) for r in rows}) != len(rows):
        raise ShiftbaseIntegrationError('Doppelte Timesheet-IDs gefunden. Änderungen bleiben gesperrt.')
    return {'driver_id':driver_id,'uid':uid,'name':name,'rows':result['rows'],
            'absence_ranges':absence_ranges,'actual':result['actual'],
            'payroll':payroll,'drafts':drafts,'year':year,'month':month,
            'raw_timesheets':raw_timesheets,'vacation_count':vacation_count,
            'sick_ranges':sick_ranges}


def _sb_review_prepare(source, form):
    """User-supplied verified corrections only. Never allocate payroll delta to days."""
    edits={}; errors=[]; warnings=[]
    for r in source['rows']:
        eid=str(r['entry_id'])
        orig=_sb_review_row_obj(r)
        saved=source['drafts'].get(eid)
        # Current page always submits ALL timesheet rows. Changed values require evidence.
        newstart=str(form.get('start_'+eid,orig['start'])).strip()
        newend=str(form.get('end_'+eid,orig['end'])).strip()
        newpause=str(form.get('pause_'+eid,orig['break_minutes'])).strip()
        evidence=str(form.get('evidence_'+eid,'')).strip()[:500]
        accepted=form.get('verified_'+eid)=='1'
        edited=(newstart!=orig['start'] or newend!=orig['end'] or newpause!=orig['break_minutes'])
        if not edited: continue
        if not accepted:
            errors.append(f"{r['day']}: Bestätigung der tatsächlichen Arbeitszeit fehlt.")
        if len(evidence)<15:
            errors.append(f"{r['day']}: Quelle und Grund der Korrektur angeben (mindestens 15 Zeichen).")
        try:
            net,duration,pm=_sb_review_minutes(newstart,newend,newpause)
        except ValueError as exc:
            errors.append(f"{r['day']}: {exc}")
            continue
        if net>600: warnings.append(f"{r['day']}: Mehr als 10 Stunden tatsächliche Arbeitszeit – prüfen.")
        if net>540 and pm<45: warnings.append(f"{r['day']}: Bei mehr als 9 Stunden tatsächlicher Arbeit ist die Pause unter 45 Minuten – prüfen. Keine Pause erfinden.")
        if newstart<'06:00': warnings.append(f"{r['day']}: Beginn vor 06:00 – tatsächliche Startzeit überprüfen.")
        if r.get('absence'): warnings.append(f"{r['day']}: Abwesenheit dokumentiert ({r['absence']}) – Überschneidung klären.")
        if r.get('deleted'): errors.append(f"{r['day']}: Als gelöscht markierter Eintrag darf nicht korrigiert werden.")
        if str(r.get('status','')).lower() in {'approved','bestätigt','genehmigt'}:
            warnings.append(f"{r['day']}: Bereits genehmigter Eintrag – Freigabe-/Änderungsprozess beachten.")
        edits[eid]={'orig':orig,'new':{'day':r['day'],'start':newstart,'end':newend,
                      'break_minutes':newpause,'hours':_sb_dayview_hm(Decimal(net)/Decimal(60))},
                    'evidence':evidence,'minutes':net}
    return edits, errors, warnings


# ------------- Einzelkorrektur bleibt als Legacy-Route; neue Oberfläche sendet geprüfte Tagesänderungen gesammelt -------------
# Wichtig: keine Berechnung von Uhrzeiten aus der Abrechnungssumme.
# Nachweislich falsche Zeiten werden nach manueller Bestätigung einzeln korrigiert.

def _sb_signed_hm(hours):
    if hours is None:
        return '–'
    value=Decimal(str(hours))
    sign='+' if value>0 else ('−' if value<0 else '')
    return sign+_sb_dayview_hm(abs(value))


def _sb_direct_baseline_signature(did, uid, year, month, eid, orig):
    import hashlib as _hashlib
    values=[str(did),str(uid),str(year),str(month),str(eid),str(orig.get('day','')),
            str(orig.get('start','')),str(orig.get('end','')),str(orig.get('break_minutes',''))]
    payload='|'.join(values).encode('utf-8')
    return hmac.new(str(app.secret_key).encode('utf-8'),payload,_hashlib.sha256).hexdigest()



def _sb_interval(row):
    """Local wall-clock interval. Retain overnight shifts (no time alteration)."""
    try:
        day = shiftbase_date.fromisoformat(str(row['day']))
        sh, sm = map(int, str(row['start']).split(':'))
        eh, em = map(int, str(row['end']).split(':'))
        if sh > 23 or eh > 23 or sm > 59 or em > 59:
            raise ValueError()
        begin = _sb_datetime(day.year, day.month, day.day, sh, sm)
        finish = _sb_datetime(day.year, day.month, day.day, eh, em)
        if finish <= begin:
            finish += _sb_timedelta(days=1)
        return begin, finish
    except (TypeError, ValueError, KeyError) as exc:
        raise ShiftbaseIntegrationError('Benachbarte Schicht hat keine zuverlässig lesbaren Uhrzeiten. Ruhezeitprüfung nicht möglich.') from exc


def _sb_rest_violation(rows):
    """Detect overlap and <11h rest between shifts on different dates.

    Same-day split shifts may have a shorter interval; overlapping entries are
    always rejected. Regulatory exceptions are not inferred automatically.
    """
    intervals = []
    for item in rows:
        if item.get('deleted'):
            continue
        start, end = _sb_interval(item)
        intervals.append((start, end, str(item['day'])))
    intervals.sort(key=lambda item: (item[0], item[1]))
    for previous, next_ in zip(intervals, intervals[1:]):
        rest = int((next_[0] - previous[1]).total_seconds() // 60)
        if rest < 0:
            return 'Zeitliche Überschneidung mit einer weiteren Schicht.'
        if previous[2] != next_[2] and rest < 11*60:
            return 'Weniger als 11 Stunden Ruhezeit zur benachbarten Schicht.'
    return None


def _sb_rest_check_before_write(source, timesheet_id, after):
    """Validate all selected-month intervals and boundary-day neighbor entries."""
    start, end = _sb_month_window(source['year'], source['month'])
    checked = []
    for row in source['rows']:
        original = _sb_review_row_obj(row)
        edited = dict(after) if str(row['entry_id']) == str(timesheet_id) else original
        checked.append({**edited, 'deleted': row.get('deleted', False)})
    # For a first/last-day edit, read the adjacent calendar day to avoid
    # missing cross-month rest conflicts. Server-side user filtering remains.
    extra_days = []
    if after['day'] == start:
        extra_days.append((shiftbase_date.fromisoformat(start)-shiftbase_timedelta(days=1)).isoformat())
    if after['day'] == end:
        extra_days.append((shiftbase_date.fromisoformat(end)+shiftbase_timedelta(days=1)).isoformat())
    for boundary in extra_days:
        neighbor = _shiftbase_get_all('timesheets', {'min_date': boundary,
                                    'max_date': boundary, 'user_id': source['uid']})
        for row in _sb_dayview_entries(neighbor,source['uid'],
                       int(boundary[:4]),int(boundary[5:7])):
            original = _sb_review_row_obj(row)
            checked.append({**original,'deleted':row.get('deleted',False)})
    conflict = _sb_rest_violation(checked)
    if conflict:
        raise ShiftbaseIntegrationError(conflict + ' Kein automatischer PUT.')


def _sb_preview_minimum_break(net_minutes):
    """Minimum theoretical break for a proposed net duration, in minutes.

    This is a PLANNING ASSUMPTION, NEVER a statement about an actual break.
    ArbZG §4 also governs placement, 15-minute segments and continuous work.
    """
    return 45 if net_minutes > 540 else (30 if net_minutes > 360 else 0)


def _sb_preview_neighbor_shifts(source, candidate_days):
    """Read, but never modify, adjacent-month shifts for safe rest checks.

    A read failure makes the entire hypothetical allocation unavailable.
    API user_id filtering is backed by an additional local owner/date filter.
    """
    first, last = _sb_month_window(source['year'], source['month'])
    checks = []
    if first in candidate_days:
        checks.append((shiftbase_date.fromisoformat(first) - shiftbase_timedelta(days=1)).isoformat())
    if last in candidate_days:
        checks.append((shiftbase_date.fromisoformat(last) + shiftbase_timedelta(days=1)).isoformat())
    neighbors = []
    for day in checks:
        shared = _SB_PREVIEW_NEIGHBORS.get()
        if shared is not None:
            # The combined monthly view shares these adjacent-day GETs for
            # all employees; every row is still filtered by its Shiftbase ID.
            if day not in shared:
                shared[day] = _shiftbase_get_all('timesheets', {'min_date':day,'max_date':day})
            raw = shared[day]
        else:
            raw = _shiftbase_get_all('timesheets', {'min_date': day, 'max_date': day,
                                                    'user_id': source['uid']})
        for row in _sb_dayview_entries(raw, source['uid'], int(day[:4]), int(day[5:7])):
            # The interval must be known, even for an uneditable neighboring shift.
            item = _sb_review_row_obj(row)
            if not row.get('deleted'):
                _sb_interval(item)
            neighbors.append({**item, 'deleted': row.get('deleted', False)})
    return neighbors


def _sb_preview_proposed_shift(original, current, delta_minutes, rest_rows,
                               original_day_sum, current_day_sum, seed):
    """Return a locally viable proposal, or None. Never touches a database/API.

    A pause increase is an expressly hypothetical planning value, not evidence
    of a pause taken. The original date and same-day/overnight shape are fixed.
    """
    if not delta_minutes:
        return None
    net, _, pause = _sb_review_minutes(current['start'], current['end'], current['break_minutes'])
    new_net = net + delta_minutes
    if (new_net <= 0 or new_net > 600 or
            current_day_sum + delta_minutes > 600 or current_day_sum + delta_minutes <= 0):
        return None
    before_start, before_end = _sb_interval(original)
    current_start, _ = _sb_interval(current)
    if before_start.date() != current_start.date():
        return None
    is_overnight = before_end.date() != before_start.date()
    # Do not propose a change in next month's clock-hours via an overnight
    # shift started on the last day of the selected month.
    month_end = shiftbase_date.fromisoformat(_sb_month_window(
        before_start.year, before_start.month)[1])
    if is_overnight and before_start.date() == month_end:
        return None
    assumed_pause = max(pause, _sb_preview_minimum_break(new_net))
    # Vary both boundaries where possible. A stable per-shift preference avoids
    # a random, ever-changing display; the weights never assert real work.
    fractions = (18, 38, 28, 48, 0, 55)
    first_choice = seed % len(fractions)
    options = fractions[first_choice:] + fractions[:first_choice]
    for fraction in options:
        # Five-minute steps keep the display plausible rather than 07:49 etc.
        start_move = min(45, 5 * ((abs(delta_minutes) * fraction + 250) // 500))
        if delta_minutes > 0:
            new_start = current_start - _sb_timedelta(minutes=start_move)
        else:
            new_start = current_start + _sb_timedelta(minutes=start_move)
        if (new_start.date() != before_start.date() or
                new_start.hour * 60 + new_start.minute < 6 * 60):
            continue
        new_end = new_start + _sb_timedelta(minutes=new_net + assumed_pause)
        if (new_end.date() != before_end.date() or
                (new_end - new_start).total_seconds() > 24 * 3600):
            continue
        proposal = dict(current)
        proposal.update({'start': new_start.strftime('%H:%M'),
                         'end': new_end.strftime('%H:%M'),
                         'break_minutes': str(assumed_pause)})
        if delta_minutes > 0 and proposal['start'] < '06:00':
            continue
        # Enforce rest between days AND detect overlaps with split shifts.
        # The unchanged entries from both boundary months are read-only.
        if _sb_rest_violation([proposal if str(r.get('_preview_id')) == str(current.get('_preview_id'))
                               else r for r in rest_rows]) is None:
            return proposal
    return None


def _sb_preview_allocate_amount(original, current, max_abs_delta, direction,
                                rest_rows, original_day_sum, current_day_sum, seed):
    """Find a feasible change with a 15-minute NET duration, never fake minutes.

    Existing real Shiftbase durations may be irregular (e.g. 7:40). In that
    case a +5 minute change to 7:45 or a -10 minute change to 7:30 is possible;
    requiring a delta divisible by 15 would incorrectly exclude both. Only
    the resulting proposed duration is constrained to a quarter-hour grid.
    """
    old_net, _, _ = _sb_review_minutes(current['start'], current['end'],
                                       current['break_minutes'])
    if max_abs_delta < 1:
        return 0, None
    low = max(15, old_net - max_abs_delta) if direction < 0 else old_net + 1
    high = min(480, old_net + max_abs_delta) if direction > 0 else old_net - 1
    if high < low:
        return 0, None
    # At most six plausible options for the usual 90-minute per-round budget.
    candidates = [net for net in range(((low + 14) // 15) * 15, high + 1, 15)
                  if (net - old_net) * direction > 0]
    for new_net in reversed(candidates) if direction > 0 else candidates:
        amount = abs(new_net - old_net)
        suggestion = _sb_preview_proposed_shift(
            original, current, direction * amount, rest_rows,
            original_day_sum, current_day_sum, seed)
        if suggestion is not None:
            return amount, suggestion
    return 0, None


def _sb_preview_day_review(source, remaining_minutes, rest_rows, known_daily_net,
                           excluded_numbers):
    """Read-only leads for checking missing/incorrect days against real records.

    A payroll discrepancy NEVER proves an unrecorded workday. No candidate is
    part of a correction form, staging table or Shiftbase POST/PUT/DELETE.
    Weekends/holidays and individual regulations require independent review.
    """
    result = {'kind': '', 'required_days': 0, 'candidates': [], 'note': ''}
    remaining_minutes = int(remaining_minutes)
    if abs(remaining_minutes) < 15:
        result['note'] = ('Weniger als 15 Minuten offen – keine künstlichen Arbeitstage oder ' 'Minute-für-Minute-Anpassung. Beleg prüfen.')
        return result
    if remaining_minutes < 0:
        # Existing entries are review leads only. NEVER select or decline a real
        # timesheet solely because its recorded hours exceed payroll hours.
        issues = {str(x['entry_id']):x['reasons']
                  for x in _sb_preview_exclusion_diagnostics(source)}
        existing = []
        try:
            excluded = set(_expand_day_ranges(source.get('sick_ranges','')))
            vac_count = str(source.get('vacation_count','')).strip()
            if vac_count not in ('','0'):
                exact = str(source.get('preview_vacation_days','')).strip()
                vacation = set(_expand_day_ranges(exact)) if exact else set()
                if not exact or len(vacation) != int(vac_count):
                    result.update(kind='check_existing',
                                  note='Urlaubstage nur als Anzahl gespeichert: '
                                       'Vor einer Entfallprüfung konkrete Urlaubstage angeben.')
                    return result
                excluded.update(vacation)
        except (ValueError,TypeError):
            result.update(kind='check_existing',note='Abwesenheitstage nicht eindeutig datiert.')
            return result
        for row in source.get('rows', []):
            day = str(row.get('day',''))
            try:
                day_number = shiftbase_date.fromisoformat(day).day
            except ValueError:
                continue
            if day_number in excluded or row.get('absence'):
                continue
            if any(fr <= day <= to and str(status).lower() not in
                   ('rejected','declined','abgelehnt')
                   for fr,to,_,status in source.get('absence_ranges',[])):
                continue
            eid = str(row.get('entry_id', ''))
            if not re.fullmatch(r'[0-9]{1,20}',eid) or row.get('deleted'):
                continue
            if str(row.get('status', '')).lower() in ('declined','rejected','abgelehnt'):
                continue
            try:
                minutes = int((Decimal(str(row['hours']))*Decimal(60)).quantize(Decimal('1')))
                if minutes <= 0: continue
            except (TypeError,ValueError,InvalidOperation):
                continue
            reasons = issues.get(eid, [])
            existing.append({'day':str(row['day']),'minutes':minutes,
                             'entry_id':eid,'reasons':reasons})
        # Prioritise obvious recording anomalies for investigation, and otherwise
        # lead with entries closest to the remaining excess (not assumed wrong).
        existing.sort(key=lambda x:(0 if x['reasons'] else 1,
                         abs(x['minutes']-abs(remaining_minutes)),x['day']))
        result.update(kind='check_existing',
                      required_days=max(1,(abs(remaining_minutes)+479)//480),
                      candidates=existing[:12],
                      note='Mehr Shiftbase-Stunden als Lohnstunden. Nur möglicherweise '
                           'fehlerhafte oder doppelte Timesheets zur Prüfung gelistet. '
                           'Eine erfasste Schicht bleibt unverändert, bis der Nachweis '
                           'eines Erfassungsfehlers vorliegt und die konkrete Timesheet-ID '
                           'ausdrücklich zur Ablehnung ausgewählt wurde.')
        return result

    # Only propose investigations of FREE days; never invent clock punches.
    occupied = set(known_daily_net) | {str(r.get('day')) for r in source.get('rows',[]) if not r.get('deleted')}
    blocked = set(excluded_numbers)
    first = shiftbase_date(source['year'], source['month'], 1)
    last = shiftbase_date.fromisoformat(_sb_month_window(source['year'], source['month'])[1])
    for start, end, _, status in source.get('absence_ranges', []):
        if str(status).strip().lower() in ('rejected', 'declined', 'abgelehnt'):
            continue
        try:
            beginning = max(shiftbase_date.fromisoformat(start), first)
            ending = min(shiftbase_date.fromisoformat(end), last)
        except (TypeError, ValueError):
            # Unknown absence intervals: cannot confidently nominate free dates.
            result.update(kind='check_missing',
                          note='Abwesenheitsdaten unvollständig. Fehlende Tage nur '
                               'mit Originalnachweis ermitteln.')
            return result
        while beginning <= ending:
            blocked.add(beginning.day)
            beginning += shiftbase_timedelta(days=1)

    recorded_weekdays = {shiftbase_date.fromisoformat(d).weekday()
                         for d in occupied if re.fullmatch(r'\d{4}-\d{2}-\d{2}', d)}
    candidates = []
    cursor = first
    while cursor <= last:
        # Sundays and month boundaries are not automatically nominated: the
        # required Sunday/holiday permissions and adjacent-month records are
        # not proven merely by a local monthly snapshot.
        if (cursor.isoformat() not in occupied and cursor.day not in blocked
                and cursor.weekday() != 6 and cursor not in (first, last)):
            candidates.append(cursor)
        cursor += shiftbase_timedelta(days=1)
    candidates.sort(key=lambda d: (0 if d.weekday() in recorded_weekdays else 1,
                                   1 if d.weekday() == 5 else 0, d.day))

    # Only quarter-hour, reasonably even days of 6 to 8 net hours can be
    # suggested for *checking*. Never create an artificial two-hour shift.
    count = max((remaining_minutes + 479)//480, round(remaining_minutes/450))
    result['kind'] = 'check_missing'
    result['required_days'] = count
    if count <= 0 or count * 360 > remaining_minutes:
        result['note'] = ('Der verbleibende Rest lässt sich nicht in gleichmäßige '
                          'zusätzliche Tage von etwa 6–8 Stunden aufteilen. '
                          'Keine künstliche Kurzschicht erzeugen.')
        return result
    if count > len(candidates):
        result['note'] = ('Für eine gleichmäßige Planung fehlen freie, nicht als '
                          'Abwesenheit markierte Kalendertage. Keine künstlichen '
                          'Arbeitstage anlegen.')
        return result

    # Pure examination hint: quarter-hour hypothetical durations only.
    # A remainder under 15 minutes is left open, never silently adjusted.
    step_total = remaining_minutes // 15
    base, extra = divmod(step_total, count)
    durations = [(base + (1 if i < extra else 0))*15 for i in range(count)]
    if min(durations) < 360 or max(durations) > 480:
        result['note'] = 'Keine gleichmäßigen 6–8-Stunden-Tage für diesen Rest möglich.'
        return result

    nominated = []
    projected = list(rest_rows)
    for day in candidates:
        minutes = durations[len(nominated)] if len(nominated) < count else None
        if minutes is None:
            break
        pause = _sb_preview_minimum_break(minutes)
        # 08:00 is ONLY used to screen hypothetical rest-time conflicts. The
        # times are deliberately NOT displayed or submitted as actual punches.
        end_clock = (_sb_datetime(day.year, day.month, day.day, 8, 0)
                     + _sb_timedelta(minutes=minutes + pause)).strftime('%H:%M')
        tentative = {'day': day.isoformat(), 'start': '08:00', 'end': end_clock,
                     'deleted': False}
        # Conservative 48-hour cap within the available calendar-week window.
        # Adjacent months / other employers are NOT fully covered here.
        week_key = day.isocalendar()[:2]
        weekly = sum(known_daily_net.get(d, 0) for d in known_daily_net
                     if shiftbase_date.fromisoformat(d).isocalendar()[:2] == week_key)
        weekly += sum(x['minutes'] for x in nominated
                      if shiftbase_date.fromisoformat(x['day']).isocalendar()[:2] == week_key)
        if weekly + minutes > 48 * 60:
            continue
        if _sb_rest_violation(projected + [tentative]) is not None:
            continue
        projected.append(tentative)
        nominated.append({'day': day.isoformat(), 'minutes': minutes,
                          'draft_start':'08:00', 'draft_end':end_clock,
                          'draft_break':pause,
                          'label':'Rechnerische Platzhalter-Uhrzeiten, keine Istzeit'})
    result['candidates'] = nominated
    result['note'] = ('Nur mögliche Daten zur Suche in Talex/Originalbelegen, KEINE '
                      'tatsächlich nachgewiesenen Schichten. Feiertage, Sonntags-'
                      'regelungen, Pausen und weitere Schutzvorschriften prüfen. '
                      'Diese Vorschau erzeugt oder sendet keine neuen Tage.'
                      if len(nominated) == count else
                      'Nicht genügend freie Tage mit plausibler Ruhezeit gefunden. '
                      'Nur vollständige Originalarbeitszeitnachweise dürfen '
                      'fehlende Arbeitstage begründen; hier wird nichts angelegt.')
    return result




def _sb_preview_exclusion_diagnostics(source):
    """Explain locally why real existing timesheets cannot be used for arithmetic proposals.

    Read-only and deterministic. The payroll difference is NOT proof that an
    original time entry was inaccurate or that an additional day was worked.
    """
    try:
        sick = set(_expand_day_ranges(source.get('sick_ranges', '')))
    except ValueError:
        sick = set()
    vacation = set()
    raw_vacation = str(source.get('preview_vacation_days') or '').strip()
    if raw_vacation:
        try:
            vacation = set(_expand_day_ranges(raw_vacation))
        except ValueError:
            vacation = set()
    by_day = {}
    parsed = {}
    for row in source.get('rows', []):
        eid = str(row.get('entry_id', ''))
        try:
            original = _sb_review_row_obj(row)
            net, _, _ = _sb_review_minutes(original['start'], original['end'],
                                           original['break_minutes'])
            parsed[eid] = net
            by_day[row['day']] = by_day.get(row['day'], 0) + net
        except (ValueError, TypeError, KeyError):
            parsed[eid] = None
    detail = []
    for row in source.get('rows', []):
        eid = str(row.get('entry_id', ''))
        day = str(row.get('day', ''))
        reasons = []
        try:
            day_num = int(day[-2:])
        except ValueError:
            day_num = -1
        if row.get('deleted') or str(row.get('status', '')).strip().lower() in ('rejected', 'declined', 'abgelehnt'):
            reasons.append('Eintrag gelöscht markiert oder bereits abgelehnt')
        if row.get('absence'):
            reasons.append('Shiftbase-Abwesenheit überschneidet die Schicht')
        if day_num in sick:
            reasons.append('In der Cloud als Krankheitstag geführt')
        if day_num in vacation:
            reasons.append('Als Urlaubstag angegeben')
        if row.get('paid_break') not in ('–', '0 Min.', '0', '0.0 Min.'):
            reasons.append('Bezahlte Pause oder unbekannte Pausenabrechnung')
        net = parsed[eid]
        if net is None:
            reasons.append('Beginn, Ende oder unbezahlte Pause nicht zuverlässig berechenbar')
        else:
            if net > 600:
                reasons.append('Bereits erfasste Netto-Arbeitszeit über 10 Stunden (' +
                               _sb_dayview_hm(Decimal(net) / Decimal(60)) + ')')
            if by_day.get(day, 0) > 600 and net <= 600:
                reasons.append('Alle Schichten dieses Tages zusammen über 10 Netto-Stunden')
            try:
                actual = Decimal(str(row.get('hours'))) * Decimal(60)
                if not actual.is_finite():
                    raise ValueError('Keine endliche Zahl')
                if abs(actual - Decimal(net)) > Decimal('0.51'):
                    reasons.append('Shiftbase-Stundensumme ' + _sb_dayview_hm(row['hours']) +
                                   ' stimmt nicht mit Beginn/Ende/Pause (' +
                                   _sb_dayview_hm(Decimal(net)/Decimal(60)) +
                                   ') überein')
            except (TypeError, InvalidOperation, ValueError):
                reasons.append('Shiftbase-Stundensumme unklar')
        if reasons:
            detail.append({'day': day, 'entry_id': eid, 'reasons': reasons})
    return detail

def _sb_hypothetical_preview(source):
    """Deterministic, hypothetical monthly gap allocation. DISPLAY ONLY.

    This function has no write path; it never changes payroll, real Shiftbase
    timesheets, persisted drafts, or the verified-correction form defaults.
    Calculated suggestions must never be interpreted as observed working time.
    """
    from hashlib import sha256 as _sha256
    result = {'days': {}, 'net_after': source['actual'], 'unallocated': None,
              'blocked_reason': '', 'requested_difference': None,
              'eligible_count': 0, 'excluded_count': 0,
              'day_review': None, 'balance_note': ''}
    if source['payroll'] is None:
        result['blocked_reason'] = 'Keine Cloud-Abrechnungsstunden gespeichert.'
        return result
    difference = source['payroll'] - source['actual']
    result['requested_difference'] = difference
    result['unallocated'] = difference
    if difference == 0:
        return result

    # The Cloud stores only a vacation COUNT, never exact vacation dates.
    # Allow human-supplied dates only for this transient, local calculation.
    # No inferred or persisted vacation dates, no mapping into PUT inputs.
    vacation_days = set()
    raw_count = str(source.get('vacation_count') or '').strip()
    if raw_count not in ('', '0'):
        raw_dates = str(source.get('preview_vacation_days') or '').strip()
        if not raw_dates:
            result['blocked_reason'] = ('Cloud-Urlaub liegt nur als Anzahl (' + raw_count +
                ') vor. Bitte die konkreten Urlaubstage aus dem Originalnachweis '
                'in das optionale Feld eintragen und „Monat abgleichen“ klicken. '
                'Solange sie unbekannt sind, bleibt die Verteilung gesperrt.')
            return result
        try:
            count = int(raw_count)
            if not 1 <= count <= 31:
                raise ValueError('Ungültige Urlaubstage-Anzahl')
            vacation_days = set(_expand_day_ranges(raw_dates))
            if len(vacation_days) != count:
                raise ValueError(f'Erwartet: {count} unterschiedliche Urlaubstage')
            for day in vacation_days:
                shiftbase_date(source['year'], source['month'], day)
        except (TypeError, ValueError) as exc:
            result['blocked_reason'] = 'Urlaubstage für die Vorschau ungültig: ' + str(exc)
            return result
    try:
        sick_days = set(_expand_day_ranges(source.get('sick_ranges', '')))
    except ValueError:
        result['blocked_reason'] = 'Cloud-Krankheitstage sind nicht eindeutig datiert.'
        return result

    originals = {}
    entries = {}
    daily_net = {}
    incomplete_days = set()
    eligible = []
    for row in source['rows']:
        eid = str(row['entry_id'])
        original = _sb_review_row_obj(row)
        originals[eid] = original
        entries[eid] = {**original, '_preview_id': eid, 'deleted': row.get('deleted', False)}
        try:
            net, _, pause = _sb_review_minutes(original['start'], original['end'], original['break_minutes'])
            recorded = Decimal(str(row['hours'])) * Decimal(60)
            if not recorded.is_finite() or abs(recorded - Decimal(net)) > Decimal('0.51'):
                # Shiftbase 'total' and time fields disagree: the proposal
                # must not make up a missing paid break or rounding policy.
                raise ValueError('Summe passt nicht zu den Uhrzeiten')
            daily_net[row['day']] = daily_net.get(row['day'], 0) + net
        except (ValueError, InvalidOperation, TypeError):
            incomplete_days.add(str(row['day']))
            continue
        if (row.get('absence') or row.get('deleted') or
                int(str(row['day'])[-2:]) in sick_days or
                int(str(row['day'])[-2:]) in vacation_days or
                row.get('paid_break') not in ('–', '0 Min.', '0', '0.0 Min.') or
                original['start'] < '06:00' or net > 600):
            continue
        eligible.append(eid)
    # For safety, group daily work across ALL existing shifts, not only those
    # selected for editing. A split shift cannot exceed ten hours in total.
    eligible = [eid for eid in eligible
                if (originals[eid]['day'] not in incomplete_days and
                    daily_net.get(originals[eid]['day'], 601) <= 600)]
    result['eligible_count'] = len(eligible)
    result['excluded_count'] = len(source['rows']) - len(eligible)
    if not eligible:
        result['blocked_reason'] = 'Keine eindeutig planbaren vorhandenen Schichten gefunden.'
        # Missing-day hints are still possible when ALL original clock data is
        # readable and no rest conflict exists; none of them can be sent.

    # Time data for other shifts must be readable: otherwise the 11-hour rest
    # check is incomplete, so no speculative changes are shown.
    try:
        for entry in entries.values():
            if not entry.get('deleted'):
                _sb_interval(entry)
        boundary_rows = _sb_preview_neighbor_shifts(source,
                                    {originals[eid]['day'] for eid in eligible})
        rest_rows = list(entries.values()) + boundary_rows
        original_conflict = _sb_rest_violation(rest_rows)
    except (ShiftbaseIntegrationError, ValueError) as exc:
        result['blocked_reason'] = ('Ruhezeiten können nicht zuverlässig geprüft werden: '
                                    + str(exc))
        if difference < 0:
            result['day_review'] = _sb_preview_day_review(
                source, -int((abs(difference)*Decimal(60)).quantize(Decimal('1'))),
                [],daily_net,sick_days | vacation_days)
        return result
    if original_conflict:
        result['blocked_reason'] = ('Bereits im Ausgangsmonat besteht ein Zeit-/Ruhezeitkonflikt ('
                                    + original_conflict + '). Keine automatische Verteilung.')
        # Still present actual existing entries for manual ERROR investigation;
        # no new hypothetical workday can be safely scheduled while rest fails.
        if difference < 0:
            result['day_review'] = _sb_preview_day_review(
                source, -int((abs(difference)*Decimal(60)).quantize(Decimal('1'))),
                [],daily_net,sick_days | vacation_days)
        return result

    requested_minutes = int((abs(difference) * Decimal(60)).quantize(Decimal('1')))
    direction = 1 if difference > 0 else -1
    if requested_minutes <= 0:
        result['blocked_reason'] = 'Abweichung ist kleiner als eine Minute.'
        return result
    current_day_sum = dict(daily_net)
    seeds = {}
    for eid in eligible:
        raw = (str(source['uid']) + '|' + str(source['year']) + '|' +
               str(source['month']) + '|' + originals[eid]['day'] + '|' + eid)
        seeds[eid] = int.from_bytes(_sha256(raw.encode('utf-8')).digest()[:4], 'big')

    # Fairer distribution: don't inflate a long day while a short, modifiable
    # day remains. For negative differences first reduce longer days. A
    # conservative target of 6–8h avoids creating a 3h outlier just to meet
    # payroll, without claiming that 8h is an absolute legal maximum.
    eligible_days = sorted({originals[eid]['day'] for eid in eligible})
    remaining = requested_minutes
    target_minutes = 0
    if eligible_days:
        desired = (sum(daily_net[d] for d in eligible_days) +
                   direction * requested_minutes) / len(eligible_days)
        # Round the shared target in the SAME direction as the correction.
        # Rounding to nearest could wrongly stop, e.g. 20 x 8:00 at a 158h
        # payroll target (7:54 average) would snap back to 8:00 and leave hours open.
        quarters = int(desired // 15)
        if direction > 0 and desired % 15 > 1e-9:
            quarters += 1
        target_minutes = max(360, min(480, 15*quarters))
        result['balance_note'] = ('Rechenvorschläge: Netto-Dauern nur in 15-Minuten-Schritten, '
            'mit moderater, gleichmäßiger Tagesvariation und bevorzugt 6–8 Netto-Stunden. '
            'Der Monatsrest bleibt sichtbar. Für mehr als 8 Stunden fehlt der Nachweis '
            'des gesetzlichen Ausgleichszeitraums. Keine Uhrzeit und keine Pause '
            'wird durch diese Berechnung zu einer nachgewiesenen Istzeit.')
    # Alternating 15-minute targets avoid the same synthetic duration on each
    # day without introducing unrealistic 3-hour or 9-hour outliers. A target
    # below an already recorded shift cannot trigger a reduction when the
    # payroll gap requires an increase (and vice versa).
    stable_offset = int.from_bytes(_sha256(
        (str(source['uid'])+'|'+str(source['year'])+'|'+str(source['month']))
        .encode('utf-8')).digest()[:2], 'big') % 8
    offsets = (-15, 0, 15, 0, 15, -15, 0, 0)
    day_targets = {day: max(360, min(480,
        target_minutes + offsets[(i+stable_offset)%len(offsets)]))
        for i, day in enumerate(eligible_days)}
    # Existing shifts can already exceed the conservative 8h planning range;
    # they are not shortened or extended merely for aesthetic variation.

    # Two passes: stable varied quarter-hour targets, then exact-target balancing.
    # Conservatively avoid any automatic 8h+ proposals with unverified long-term compensatory averages.
    # Existing day totals and all overlapping entries participate in every
    # rest-time check. Never override a failed feasibility check.
    for pass_no in range(2):
        for _ in range(16):
            if remaining < 1:
                break
            progress = False
            order = sorted(eligible,
                key=lambda eid: ((current_day_sum[originals[eid]['day']]
                                  if direction > 0 else
                                  -current_day_sum[originals[eid]['day']]),
                                 originals[eid]['day'], eid))
            for eid in order:
                if remaining < 1:
                    break
                day = originals[eid]['day']
                day_total = current_day_sum[day]
                limit = day_targets[day] if pass_no == 0 else target_minutes
                room = (limit - day_total if direction > 0
                        else day_total - limit)
                if room <= 0:
                    continue
                if direction > 0:
                    week = shiftbase_date.fromisoformat(day).isocalendar()[:2]
                    weekly = sum(minutes for d, minutes in current_day_sum.items()
                                 if shiftbase_date.fromisoformat(d).isocalendar()[:2] == week)
                    room = min(room, 48 * 60 - weekly)
                if room <= 0:
                    continue
                budget = min(remaining, room, 90)
                original, current = originals[eid], entries[eid]
                amount, changed = _sb_preview_allocate_amount(
                    original, current, budget, direction, rest_rows,
                    daily_net[day], day_total, seeds[eid])
                if not amount or changed is None:
                    continue
                remaining -= amount
                progress = True
                current_day_sum[day] += direction * amount
                entries[eid] = {**changed, '_preview_id': eid}
                rest_rows = [entries[eid] if r.get('_preview_id') == eid else r
                             for r in rest_rows]
            if not progress:
                break

    allocated = 0
    for eid, original in originals.items():
        current = entries[eid]
        if (current['start'], current['end'], current['break_minutes']) == (
                original['start'], original['end'], original['break_minutes']):
            continue
        old_minutes, _, old_pause = _sb_review_minutes(original['start'], original['end'],
                                                     original['break_minutes'])
        new_minutes, _, new_pause = _sb_review_minutes(current['start'], current['end'],
                                                     current['break_minutes'])
        delta = new_minutes - old_minutes
        if not delta:
            continue
        # Only the generated proposals are quarter-hour aligned; unchanged
        # original Shiftbase punches remain untouched, even if non-rounded.
        if new_minutes % 15:
            raise ShiftbaseIntegrationError('Interner Fehler: Vorschlag ist nicht im 15-Minuten-Takt.')
        allocated += delta
        result['days'][eid] = {
            'new_start': current['start'], 'new_end': current['end'],
            'new_pause': current['break_minutes'],
            'new_hours': _sb_dayview_hm(Decimal(new_minutes) / Decimal(60)),
            'delta_minutes': delta,
            'assumed_break_change': new_pause != old_pause,
        }
    result['net_after'] = source['actual'] + Decimal(allocated) / Decimal(60)
    result['unallocated'] = source['payroll'] - result['net_after']
    if remaining:
        if not result['blocked_reason']:
            result['blocked_reason'] = ('Ein Teil der Differenz bleibt unverplant: '
                '15-Minuten-Dauern, gleichmäßige Tageslängen, die konservative '
                '48-Stunden-Wochengrenze (soweit Monatsdaten vorliegen), '
                'Ruhezeiten und vorgeschriebene Pausen erlauben keinen weiteren '
                'vorsichtigen Vorschlag. Das ist kein Nachweis fehlender Arbeit.')
        result['day_review'] = _sb_preview_day_review(
            source, direction*remaining, rest_rows, daily_net,
            sick_days | vacation_days)
    return result


@app.get('/admin/shiftbase/pruefvorschau')
@admin_login_required
def admin_shiftbase_pruefvorschau():
    year,month=_sb_params()
    raw=request.args.get('driver_id','').strip()
    if not re.fullmatch(r'[0-9]{1,12}',raw):
        abort(400,'Fahrer-ID fehlt. Bitte Tagesübersicht öffnen.')
    did=int(raw)
    try:
        source=_sb_review_source(did,year,month)
    except ShiftbaseIntegrationError as exc:
        return base_page('Shiftbase – Tageskorrektur',
            '<div class="card"><h2>Tagesdaten konnten nicht geladen werden</h2><p>'+shiftbase_escape(str(exc))+'</p></div>',
            'shiftbase'),422

    esc=lambda x:shiftbase_escape(str(x if x is not None else ''),quote=True)
    enable=os.environ.get('SHIFTBASE_VERIFIED_WRITE_ENABLED','').strip()=='1'
    try:
        _sb_write_access_checked(source)
        writable=True
    except ShiftbaseIntegrationError:
        writable=False
    # Preview-only values are shown as EDITABLE, locally prefilled suggestions.
    # Only the admin's explicit collective certification button can submit
    # their current values as attested actual time corrections. Nothing is
    # written by merely opening or recomputing this page.
    source['preview_vacation_days'] = str(request.args.get('urlaubs_tage','')).strip()[:100]
    plan=_sb_hypothetical_preview(source)
    with db_conn() as conn:
        choices=[r for r in _sb_local_month(conn,year,month) if r['driver_id'] in _sb_mapping(conn)]
    form_options=''.join('<option value="'+str(r['driver_id'])+'"'+(' selected' if r['driver_id']==did else '')+'>'+shiftbase_escape(r['name'])+'</option>' for r in choices)
    month_options=''.join('<option value="'+str(m)+'"'+(' selected' if m==month else '')+'>'+MONATE[m]+'</option>' for m in range(1,13))
    reply=session.pop('shiftbase_direct_result',None)
    h=['''<style>
.sb-simple{max-width:1200px;margin:auto}
.sb-simple .sb-cards{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:12px;margin:15px 0}
.sb-simple .sb-value{background:#f3f7ff;border:1px solid #e0e7f1;border-radius:13px;padding:14px}
.sb-simple .sb-value strong{display:block;font-size:1.5rem;color:#0f2446;margin-top:3px}
.sb-simple details{margin:10px 0;border:1px solid #dae3ed;background:#fff;border-radius:13px;overflow:hidden}
.sb-simple summary{cursor:pointer;padding:15px;font-weight:700;list-style:none;display:flex;gap:10px;justify-content:space-between;align-items:center}
.sb-simple summary::-webkit-details-marker{display:none}
.sb-simple summary:after{content:'Bearbeiten';color:#1261b0;font-size:.84rem;white-space:nowrap}
.sb-simple .sb-column-head,.sb-simple .sb-day-fields{display:grid;grid-template-columns:1.1fr 1.2fr 1.5fr .7fr 1fr;gap:9px;align-items:center}
.sb-simple .sb-column-head{padding:7px 15px;color:#64748b;font-size:.78rem;font-weight:800}
.sb-simple .sb-day-fields{flex:1;min-width:0}
.sb-simple .sb-day-fields span{overflow-wrap:anywhere}
.sb-simple .sb-hypothetical{color:#a04b00}
.sb-simple .sb-hint{background:#fff8ea;border:1px solid #f2cf8b;padding:11px 13px;border-radius:12px;margin:14px 0}
.sb-simple .sb-status{font-size:.84rem;font-weight:700}
.sb-simple details[open] summary{background:#f2f6fe;border-bottom:1px solid #dae3ed}
.sb-simple .sb-edit{padding:15px;display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:12px}
.sb-simple .sb-wide{grid-column:1/-1}
.sb-simple .sb-edit label{font-size:.9rem;margin:0}
.sb-simple .sb-edit input:not([type=checkbox]){margin-top:6px;width:100%}
.sb-simple .sb-confirm{display:flex;align-items:flex-start;gap:8px;font-weight:500}
.sb-simple .sb-confirm input{width:auto;margin:3px 0 0}
.sb-simple .sb-send{font-size:1rem;padding:13px}
.sb-simple .sb-muted{color:#667085;font-size:.9rem}
.sb-simple .sb-review-grid{display:grid;grid-template-columns:1fr 1.6fr 2.5fr .65fr 1.25fr;gap:10px;align-items:center}
.sb-simple .sb-review-head{font-size:.78rem;color:#64748b;font-weight:800;padding:8px 12px}
.sb-simple .sb-review-day{border:1px solid #dae3ed;background:#fff;border-radius:13px;padding:12px;margin:9px 0}
.sb-simple .sb-review-day.sb-dirty{border-color:#1d6bb5;background:#f6faff}
.sb-simple .sb-times{display:grid;grid-template-columns:1fr 1fr .82fr;gap:5px}
.sb-simple .sb-times label{margin:0;font-weight:700;font-size:.73rem;color:#4b5563}
.sb-simple .sb-times input{margin-top:4px;padding:8px 5px;font-size:.91rem;min-width:0;width:100%}
.sb-simple .sb-review-day .sb-day-status{font-weight:750;font-size:.82rem}
.sb-simple .sb-review-day .sb-original{font-size:.92rem}
 .sb-simple .sb-review-day .sb-suggestion{font-size:.92rem}
.sb-simple .sb-input-cell .sb-field-note{display:block;margin-top:5px;font-size:.74rem;color:#a04b00}
.sb-simple .sb-review-day[data-had-suggestion="1"]{border-left:4px solid #b7791f}
.sb-simple .sb-times input:focus{outline:2px solid #125eb2;outline-offset:1px}
.sb-simple .sb-batch-actions{position:sticky;bottom:8px;z-index:7;background:#fff;border:1px solid #cad6e5;box-shadow:0 6px 26px #0e244124;padding:12px;border-radius:14px;margin-top:16px}
.sb-simple .sb-batch-actions button{width:100%}
.sb-simple .sb-batch-actions .sb-muted{margin:7px 0 0}
@media(max-width:900px){
 .sb-simple .sb-review-head{display:none}
 .sb-simple .sb-review-grid{grid-template-columns:repeat(2,minmax(0,1fr));gap:8px}
 .sb-simple .sb-review-day .sb-input-cell{grid-column:1/-1}
 .sb-simple .sb-review-day .sb-day-status{grid-column:1/-1}
}
@media(max-width:470px){.sb-simple .sb-review-grid{grid-template-columns:1fr}.sb-simple .sb-times{grid-template-columns:1fr 1fr 1fr}}

@media(max-width:750px){.sb-simple .sb-cards,.sb-simple .sb-edit{grid-template-columns:1fr}.sb-simple .sb-column-head{display:none}.sb-simple .sb-day-fields{grid-template-columns:1fr 1fr;gap:5px}.sb-simple summary{align-items:start}.sb-simple .sb-day-fields span:first-child{font-weight:900}}
</style>''',
       '<div class="sb-simple"><div class="card"><h2>Shiftbase – Monatsabgleich</h2>',
       '<form method="get" action="'+url_for('admin_shiftbase_pruefvorschau')+'" class="grid grid-3" style="align-items:end">',
       '<label>Fahrer<select name="driver_id" required>'+form_options+'</select></label>',
       '<label>Monat<select name="month" required>'+month_options+'</select></label>',
       '<label>Jahr<input type="number" name="year" min="2020" max="2100" value="'+str(year)+'" required></label>',
       ('<label style="grid-column:1/-1">Urlaubstage konkret (nur Vorschau, Cloud: '+esc(source['vacation_count'])+' Tage)<input type="text" name="urlaubs_tage" placeholder="z. B. 5-7, 14" value="'+esc(source['preview_vacation_days'])+'"><small class="sb-muted">Nur eingeben, wenn durch Unterlagen bekannt. Werden weder gespeichert noch an Shiftbase gesendet.</small></label>' if source.get('vacation_count') not in ('','0') else ''),
       '<div style="grid-column:1/-1"><button type="submit" class="primary" style="width:auto">Monat abgleichen</button></div></form>',
       '<div class="sb-cards"><div class="sb-value">Shiftbase – Iststunden<strong>'+_sb_dayview_hm(source['actual'])+'</strong></div>',
       '<div class="sb-value">Cloud – Abrechnung<strong>'+(_sb_dayview_hm(source['payroll']) if source['payroll'] is not None else 'nicht hinterlegt')+'</strong></div>',
       '<div class="sb-value">Abrechnung minus Iststunden<strong>'+_sb_signed_hm((source['payroll']-source['actual']) if source['payroll'] is not None else None)+'</strong></div></div>',
       '<div class="sb-hint"><b>Vorschläge sind rechnerische Annahmen, keine nachgewiesenen Arbeitszeiten.</b> Prüfe deshalb jede vorgeschlagene Schicht und Pause anhand von Talex oder anderen Originalnachweisen. Du kannst die Werte direkt in der einzigen Spalte <b>Vorschlag</b> ändern. Es erfolgt keine Übertragung, bevor du mit dem Abschlussbutton bestätigst, dass <b>alle übermittelten Werte tatsächlich geleistete und geprüfte Arbeitszeiten</b> sind. Eine reine Abrechnungsdifferenz ist kein Zeitnachweis.</div>',
       '<div class="sb-cards"><div class="sb-value">Hypothetische Monatssumme<strong>'+_sb_dayview_hm(plan['net_after'])+'</strong></div>',
       '<div class="sb-value">Rechnerisch noch offen<strong>'+_sb_signed_hm(plan['unallocated'])+'</strong></div>',
       '<div class="sb-value">Vorgeschlagene Schichten<strong>'+str(len(plan['days']))+'</strong></div></div>']
    if plan.get('balance_note'):
        h.append('<p class="sb-muted">'+esc(plan['balance_note'])+'</p>')
    if plan['blocked_reason']:
        h.append('<p class="sb-muted">Hinweis zur Planung: '+esc(plan['blocked_reason'])+'</p>')
    if plan.get('day_review') and plan['day_review'].get('kind'):
        dcheck=plan['day_review']
        h.append('<div class="sb-hint"><b>Zusätzliche / entfallende Arbeitstage – Vorschau vor eigener Belegprüfung:</b> '
                 +esc(dcheck.get('note',''))+'<br>Orientierungswert: '
                 +str(dcheck.get('required_days',0))+' Tag(e).')
        if dcheck.get('candidates'):
            h.append('<ul>'+''.join('<li>'+esc(item['day'])+' · '
                +esc(_sb_dayview_hm(Decimal(item['minutes'])/Decimal(60)))
                +' – ausschließlich anhand von Originalbelegen prüfen</li>'
                for item in dcheck['candidates'])+'</ul>')
        h.append('<p><a href="https://app.shiftbase.com/" target="_blank" rel="noopener noreferrer">'+
                 'Shiftbase öffnen – Arbeitszeitprotokoll</a></p></div>')
    # Show exact original data issues, including >10h nights and conflicting API totals.
    # These are not instructions to shorten true recorded work to match payroll.
    diagnostics = _sb_preview_exclusion_diagnostics(source)
    if diagnostics:
        h.append('<details class="sb-diagnose" open><summary>Warum wurden einzelne Schichten ausgeschlossen? ('+
                 str(len(diagnostics))+' auffällige Einträge)</summary><div style="padding:12px"><ul>')
        for item in diagnostics:
            h.append('<li><b>'+esc(item['day'])+'</b>: '+esc('; '.join(item['reasons']))+'</li>')
        h.append('</ul><p class="sb-muted">Diese Probleme betreffen vorhandene Originalerfassungen. '+
                 'Einen falsch erfassten Tag nur nach Prüfung des tatsächlichen Arbeitsnachweises korrigieren; '+
                 'die Lohnabrechnung allein ersetzt keinen Zeitnachweis.</p></div></details>')
    if plan.get('excluded_count'):
        h.append('<p class="sb-muted">Nicht für automatische Rechenvorschläge geeignete Schichten: '+str(plan['excluded_count'])+'. '+
                 'Die genauen Gründe stehen oben. Eine belegte manuelle Korrektur kann in der Tabelle dennoch möglich sein.</p>')
    if source.get('sick_ranges'):
        h.append('<p class="sb-muted">Cloud-Krankheitstage: '+esc(source['sick_ranges'])+' (für hypothetische Änderungen ausgeschlossen).</p>')
    h.append('<p class="sb-muted"><b>Fehlende oder fehlerhafte Arbeitstage:</b> '+
             'Rechnerische Zusatz- oder Entfalltage werden unten jetzt als bearbeitbare '+
             'Prüfkarten angezeigt. Datum, Arbeitsbeginn, Arbeitsende und Pause kannst du '+
             'vor jeder Einzelfreigabe ändern. Eine reine Abrechnungsdifferenz ist kein '+
             'Arbeitszeitnachweis: kein automatisches POST oder Ablehnen.</p>')
    if reply:
        color='ok' if reply.startswith('Erfolg:') else 'err'
        h.append('<div class="flash '+color+'">'+esc(reply)+'</div>')
    if not writable:
        h.append('<div class="flash err">Direktes Senden gesperrt. SHIFTBASE_VERIFIED_WRITE_ENABLED=1 und für alle zugeordneten Fahrer zusätzlich SHIFTBASE_VERIFIED_WRITE_ALL_MAPPED=1 auf Render setzen. Einzeltest-Benutzer: '+esc(source['uid'])+'.</div>')
    h.append('<div class="sb-hint"><b>Ein Ablauf, ein Button:</b> Vorschläge direkt ansehen und bei Bedarf korrigieren. Wenn sämtliche zu sendenden Zeiten und Pausen mit den Talex-Nachweisen übereinstimmen, bestätigst du sie gemeinsam unten. Es werden nur von den ursprünglichen Shiftbase-Daten abweichende Schichten gesendet, keine unveränderten Einträge.</div>')
    h.append('<p class="sb-muted">Die editierbaren Felder sind mit dem rechnerischen Vorschlag vorbelegt (falls verfügbar), sonst mit den ursprünglichen Zeiten. Ein Stern (*) an der Pause bedeutet: nur vom Modell angenommen; die tatsächlich genommene Pause muss vor dem Senden geprüft werden.</p>')
    h.append('<form id="sb-batch-form" method="post" action="'+url_for('admin_shiftbase_stage_review')+'">')
    for key,val in [('csrf_token',_sb_csrf_token()),('driver_id',did),('year',year),('month',month),('urlaubs_tage',source['preview_vacation_days'])]:
        h.append('<input type="hidden" name="'+key+'" value="'+esc(val)+'">')
    h.append('<div class="sb-review-grid sb-review-head"><span>Datum</span><span>Bisher</span><span>Vorschlag (direkt bearbeitbar)</span><span>Diff.</span><span>Status</span></div>')
    for r in source['rows']:
        eid=str(r['entry_id'])
        orig=_sb_review_row_obj(r)
        try:
            readable_date=shiftbase_date.fromisoformat(str(r['day'])).strftime('%d.%m.%Y')
        except ValueError:
            readable_date=str(r['day'])
        suggestion=plan['days'].get(eid)
        before_summary=orig['start']+'–'+orig['end']+' · '+orig['hours']+' Std. · Pause '+orig['break_minutes']+' Min.'
        # Editable 'Vorschlag' is prefilled only in the HTML. The POST still
        # checks every timesheet independently against its signed original,
        # the selected user/month, daily rules, and Shiftbase's live records.
        values = {
            'start': suggestion['new_start'] if suggestion else orig['start'],
            'end': suggestion['new_end'] if suggestion else orig['end'],
            'pause': suggestion['new_pause'] if suggestion else orig['break_minutes'],
        }
        delta_summary = (_sb_signed_hm(Decimal(suggestion['delta_minutes']) / Decimal(60))
                         if suggestion else '0:00')
        status_summary = 'Zu prüfen · rechnerisch' if suggestion else 'Unverändert'
        signed=_sb_direct_baseline_signature(did,source['uid'],year,month,eid,orig)
        try:
            cloud_sick = int(str(r['day'])[-2:]) in set(_expand_day_ranges(source.get('sick_ranges','')))
        except ValueError:
            cloud_sick = True
        unusable=bool(r.get('deleted') or r.get('absence') or cloud_sick or
                      orig['break_minutes']=='' or orig['start']=='–' or orig['end']=='–' or
                      str(r.get('status','')).lower() in {'rejected','declined','abgelehnt'})
        if unusable:
            status_summary='Gesperrt / Klärung nötig'
        h.append('<div class="sb-review-grid sb-review-day'+(' sb-editable-row' if not unusable else '')+'"'+
                 (' data-orig-start="'+esc(orig['start'])+'" data-orig-end="'+esc(orig['end'])+'" data-orig-pause="'+esc(orig['break_minutes'])+'" data-had-suggestion="'+('1' if suggestion else '0')+'"' if not unusable else '')+'>')
        h.append('<strong>'+esc(readable_date)+'</strong><span class="sb-original">'+esc(before_summary)+'</span>')
        if unusable:
            h.append('<span class="sb-input-cell sb-muted">Kein Vorschlag bearbeitbar: Abwesenheit, unvollständige oder gesperrte Schicht.</span>')
        else:
            h.append('<input type="hidden" name="sb_sig_'+esc(eid)+'" value="'+esc(signed)+'">')
            h.append('<div class="sb-input-cell"><div class="sb-times">')
            h.append('<label>Beginn<input type="time" name="sb_start_'+esc(eid)+'" value="'+esc(values['start'])+'" required aria-label="Vorschlag Beginn am '+esc(readable_date)+'"></label>')
            h.append('<label>Ende<input type="time" name="sb_end_'+esc(eid)+'" value="'+esc(values['end'])+'" required aria-label="Vorschlag Ende am '+esc(readable_date)+'"></label>')
            h.append('<label>Pause Min.'+('*' if suggestion and suggestion['assumed_break_change'] else '')+'<input type="number" name="sb_pause_'+esc(eid)+'" min="0" max="600" step="1" value="'+esc(values['pause'])+'" required aria-label="Vorschlag Pause am '+esc(readable_date)+'"></label>')
            h.append('</div>')
            if suggestion and suggestion['assumed_break_change']:
                h.append('<span class="sb-field-note">* Pause rechnerisch ergänzt – mit Nachweis abgleichen.</span>')
            h.append('</div>')
        h.append('<span class="sb-day-diff">'+esc(delta_summary)+'</span><span class="sb-day-status">'+esc(status_summary)+'</span></div>')
    h.append('<input type="hidden" name="confirmed_batch" value="actual_work_verified_using_records">')
    h.append('<div class="sb-batch-actions"><button class="primary" type="submit" name="mode" value="start"'+('' if writable else ' disabled')+'>Geprüfte Istzeiten senden · mit Fortschrittsanzeige</button>')
    h.append('<p class="sb-muted"><span id="sb-changed-count">Änderungen werden gezählt …</span> Nur die nach Talex überprüften Istzeiten bestätigen. Nicht geänderte Schichten und reine Lohnabweichungen werden niemals gesendet.</p></div>')
    h.append('</form>')
    h.append(_sb_day_candidate_cards(source,plan,_sb_csrf_token()))
    h.append(_SB_DAY_PROPOSAL_JS)
    h.append(_sb_day_ops_html(source,_sb_csrf_token()))
    h.append('<p><a class="btn small" href="'+url_for('admin_shiftbase_transfer_dashboard',year=year,month=month)+'">Alle Fahrer / Gesamtversand</a></p>')
    h.append('<p><a class="btn small" href="'+url_for('admin_shiftbase_vorschlaege_pruefliste_csv',driver_id=did,year=year,month=month,urlaubs_tage=source['preview_vacation_days'])+'">Vorschläge als unverbindliche Prüfliste (CSV)</a></p>')
    h.append(r"""<script>
(function(){
  const form=document.getElementById('sb-batch-form');
  if(!form) return;
  const rows=Array.from(form.querySelectorAll('.sb-editable-row'));
  function signedHours(minutes){
    if(!Number.isFinite(minutes))return '–';
    const abs=Math.abs(minutes), h=Math.floor(abs/60), m=abs%60;
    return (minutes>0?'+':minutes<0?'−':'')+h+':'+String(m).padStart(2,'0');
  }
  function netMinutes(s,e,p){
    if(!/^\d{2}:\d{2}$/.test(s)||!/^\d{2}:\d{2}$/.test(e)||!/^\d+$/.test(p))return null;
    const sm=Number(s.slice(0,2))*60+Number(s.slice(3)),em=Number(e.slice(0,2))*60+Number(e.slice(3)),pm=Number(p);
    const span=(em<=sm?em+1440:em)-sm;
    return (span>0&&pm<=span&&pm>=0)?span-pm:null;
  }
  function refresh(){
    let count=0;
    rows.forEach(function(row){
      const eidInput=row.querySelector('input[name^="sb_start_"]');
      if(!eidInput)return;
      const eid=eidInput.name.slice('sb_start_'.length);
      const s=form.elements.namedItem('sb_start_'+eid),e=form.elements.namedItem('sb_end_'+eid),p=form.elements.namedItem('sb_pause_'+eid);
      const changed=(s.value!==row.dataset.origStart||e.value!==row.dataset.origEnd||p.value!==row.dataset.origPause);
      row.classList.toggle('sb-dirty',changed);
      const label=row.querySelector('.sb-day-status');
      if(label)label.textContent=changed?'Zu prüfen · wird bei Bestätigung gesendet':
        (row.dataset.hadSuggestion==='1'?'Zurück auf Original':'Unverändert');
      const oldNet=netMinutes(row.dataset.origStart,row.dataset.origEnd,row.dataset.origPause);
      const newNet=netMinutes(s.value,e.value,p.value);
      const diff=row.querySelector('.sb-day-diff');
      if(diff)diff.textContent=(oldNet===null||newNet===null)?'–':signedHours(newNet-oldNet);
      if(changed)count++;
    });
    const info=document.getElementById('sb-changed-count');
    if(info)info.textContent=count?count+' vorgeschlagene oder angepasste Schicht(en) zur Übertragung.':'Keine Änderung gegenüber Shiftbase.';
  }
  rows.forEach(function(row){
    row.querySelectorAll('input[type=time],input[type=number]').forEach(function(el){el.addEventListener('input',refresh);el.addEventListener('change',refresh);});
  });
  form.addEventListener('submit',function(e){
    refresh();
    const count=form.querySelectorAll('.sb-editable-row.sb-dirty').length;
    if(!count){e.preventDefault();alert('Keine Änderung gegenüber Shiftbase. Es gibt nichts zu senden.');return;}
    // Avoid accidental double-submission; no additional confirmation popup.
    const btn=form.querySelector('.sb-batch-actions button[type="submit"]');
    if(btn){btn.disabled=true;btn.textContent='Prüfung wird vorbereitet …';}
  });
  refresh();
})();
</script>""")
    h.append('<p class="sb-muted">Nach dem Senden liest die Cloud die Schicht erneut aus. Wenn Shiftbase die Änderung nicht bestätigt, erscheint ein Fehler statt einer Erfolgsmeldung.</p>')
    with db_conn() as conn:
        _sb_put_audit_table(conn)
        recent=conn.execute('SELECT * FROM shiftbase_verified_writes WHERE driver_id=? AND year=? AND month=? ORDER BY written_at DESC LIMIT 5',(did,year,month)).fetchall()
    if recent:
        h.append('<details><summary>Letzte Übertragungen anzeigen</summary><div style="padding:15px">')
        for log in recent:
            h.append('<p>'+esc(log['written_at'])+' · '+esc(log['timesheet_id'])+' · '+esc(log['result'])+'</p>')
        h.append('</div></details>')
    h.append('</div></div>')
    resp=make_response(base_page('Shiftbase – Zeiten korrigieren',''.join(h),'shiftbase'))
    resp.headers['Cache-Control']='private, no-store, max-age=0'
    resp.headers['X-Robots-Tag']='noindex, nofollow'
    return resp


def _sb_write_access_checked(source):
    """Require explicit global opt-in, a unique active driver mapping and exact UID.

    The historical single-user restriction remains the default. Enabling all
    mapped users requires a second, deliberate Render environment flag.
    """
    if os.environ.get('SHIFTBASE_VERIFIED_WRITE_ENABLED','').strip() != '1':
        raise ShiftbaseIntegrationError('Der Shiftbase-Schreibzugriff ist nicht aktiviert.')
    driver_id = int(source.get('driver_id') or 0)
    uid = str(source.get('uid') or '')
    if driver_id <= 0 or not re.fullmatch(r'[0-9]{1,20}', uid):
        raise ShiftbaseIntegrationError('Mitarbeiterzuordnung nicht eindeutig.')
    with db_conn() as conn:
        d = conn.execute('SELECT id,name,is_active,is_disposition FROM drivers WHERE id=?',(driver_id,)).fetchone()
        mappings = _sb_mapping(conn)
    if (not d or int(d['is_active']) != 1 or int(d['is_disposition'] or 0) != 0
            or mappings.get(driver_id) != uid or len(set(mappings.values())) != len(mappings)):
        raise ShiftbaseIntegrationError('Nur aktive, eindeutig zugeordnete Fahrer dürfen korrigiert werden.')
    if os.environ.get('SHIFTBASE_VERIFIED_WRITE_ALL_MAPPED','').strip() == '1':
        return
    if uid != os.environ.get('SHIFTBASE_VERIFIED_WRITE_USER_ID','').strip():
        raise ShiftbaseIntegrationError('Schreibzugriff derzeit nur für die konfigurierte Test-Benutzer-ID freigegeben. Für alle Fahrer SHIFTBASE_VERIFIED_WRITE_ALL_MAPPED=1 setzen.')


def _sb_verified_write_one(form, source, did, year, month, eid):
    """Only Talex-checked, expressly confirmed actual times can be PUT.

    Never accepts data from _sb_hypothetical_preview. One remote PUT, then GET.
    Caller may be the single-day UI or the verified batch action.
    """
    _sb_write_access_checked(source)
    if not re.fullmatch(r'\d{1,20}', str(eid)):
        raise ShiftbaseIntegrationError('Ungültige Timesheet-ID.')
    if form.get('certified')!='yes':
        raise ShiftbaseIntegrationError('Bestätigung des Originalnachweises fehlt.')
    evidence=str(form.get('evidence','')).strip()[:400]
    if len(evidence)<15:
        raise ShiftbaseIntegrationError('Belegquelle und Korrekturgrund fehlen.')
    row=next((r for r in source['rows'] if str(r['entry_id'])==eid),None)
    if row is None: raise ShiftbaseIntegrationError('Schicht nicht gefunden.')
    orig=_sb_review_row_obj(row)
    expected_sig=_sb_direct_baseline_signature(did,source['uid'],year,month,eid,orig)
    if not hmac.compare_digest(str(form.get('original_sig','')),expected_sig):
        raise ShiftbaseIntegrationError('Die Schicht wurde inzwischen geändert. Seite neu laden.')
    if row.get('absence') or row.get('deleted'):
        raise ShiftbaseIntegrationError('Abwesenheit bzw. gelöschter Eintrag: erst klären.')
    try:
        sick_days = set(_expand_day_ranges(source.get('sick_ranges','')))
    except ValueError as exc:
        raise ShiftbaseIntegrationError('Cloud-Krankheitsdaten unklar: kein PUT.') from exc
    if int(str(row['day'])[-2:]) in sick_days:
        raise ShiftbaseIntegrationError('Der Tag ist in der Cloud als Krankheitstag erfasst; kein PUT.')
    if source.get('vacation_count') not in ('','0') and form.get('vacation_ack')!='yes':
        raise ShiftbaseIntegrationError('Cloud-Urlaubstage sind nicht datumsgenau hinterlegt. Bitte bestätigen, dass dieser Tag kein Urlaubstag ist.')
    if str(row.get('status','')).lower() in {'approved','bestätigt','genehmigt'} and form.get('approved_ack')!='yes':
        raise ShiftbaseIntegrationError('Genehmigten Eintrag ausdrücklich bestätigen.')
    start=str(form.get('start','')).strip();end=str(form.get('end','')).strip();pause=str(form.get('pause','')).strip()
    if start==orig['start'] and end==orig['end'] and pause==orig['break_minutes']:
        raise ShiftbaseIntegrationError('Keine Änderung eingegeben.')
    try:
        net,span,pm=_sb_review_minutes(start,end,pause)
    except ValueError as exc:
        raise ShiftbaseIntegrationError('Uhrzeit oder Pause ungültig: '+str(exc)) from exc
    if start<'06:00' or net>600 or (net>540 and pm<45) or (net>360 and pm<30):
        raise ShiftbaseIntegrationError('Zeiten liegen außerhalb der eingestellten Prüfgrenzen.')
    if str(row.get('status','')).lower() in {'declined','abgelehnt','rejected'}:
        raise ShiftbaseIntegrationError('Abgelehnten Eintrag zunächst klären.')
    ts=_sb_ts_detail(eid)
    _sb_assert_timesheet_owner(ts,source['uid'],eid)
    if any(_sb_get(ts,k) is not None for k in ('clocked_in','clocked_out')):
        raise ShiftbaseIntegrationError('Gestempelte Schicht: Stempelkorrektur erforderlich.')
    live=_sb_live_snapshot(ts)
    if live!={k:str(v) for k,v in orig.items() if k in ('day','start','end','break_minutes')}:
        raise ShiftbaseIntegrationError('Originaleintrag wurde bereits geändert; bitte neu laden.')
    paid_pause=_sb_break_as_minutes(_sb_get(ts,'paid_break'))
    if paid_pause is None or paid_pause != 0:
        raise ShiftbaseIntegrationError('Bezahlte Pause unklar oder vorhanden: muss zuerst gesondert geprüft werden.')
    after={'day':orig['day'],'start':start,'end':end,'break_minutes':str(pm),'hours':_sb_dayview_hm(Decimal(net)/Decimal(60))}
    _sb_rest_check_before_write(source,eid,after)
    payload=_sb_update_payload(ts,eid,after,expected_uid=source['uid'],
                               monthly_entry=source['raw_timesheets'].get(eid))
    write_id=secrets.token_hex(16)
    with db_conn() as conn:
        _sb_put_audit_table(conn)
        conn.execute('INSERT INTO shiftbase_verified_writes(id,driver_id,shiftbase_user_id,year,month,timesheet_id,before_json,after_json,proof_ref,reason,written_at,result) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)',
          (write_id,did,source['uid'],year,month,eid,json.dumps(orig,ensure_ascii=False),json.dumps(after,ensure_ascii=False),evidence,evidence,now_iso(),'VORBEREITET – noch nicht übertragen'))
        conn.commit()
    try:
        status=_sb_put_timesheet(eid,payload)
        after_detail=_sb_ts_detail(eid)
        _sb_assert_timesheet_owner(after_detail,source['uid'],eid)
        checked=_sb_live_snapshot(after_detail)
        if checked!={k:str(v) for k,v in after.items() if k in ('day','start','end','break_minutes')}:
            raise ShiftbaseIntegrationError('PUT gesendet, aber Rücklesen bestätigt die Änderungen nicht. Bitte direkt in Shiftbase prüfen.')
    except ShiftbaseIntegrationError:
        with db_conn() as conn:
            conn.execute('UPDATE shiftbase_verified_writes SET result=? WHERE id=?',('Unbestätigt – vor erneutem Senden in Shiftbase prüfen',write_id))
            conn.commit()
        raise
    with db_conn() as conn:
        conn.execute('UPDATE shiftbase_verified_writes SET result=? WHERE id=?',('PUT '+str(status)+' – GET bestätigt',write_id))
        conn.execute('DELETE FROM shiftbase_review_drafts WHERE driver_id=? AND year=? AND month=? AND timesheet_id=?',(did,year,month,eid))
        conn.commit()

    # Reflect the verified GET outcome in this request's user/month-only source.
    # An unconfirmed/failed PUT never reaches this point.
    row.update({'begin': after['start'], 'end': after['end'],
                'break': str(pm) + ' Min.', 'hours': Decimal(net) / Decimal(60)})
    return orig['day']


def _sb_verified_post_scope(form):
    expected_csrf = str(session.get('shiftbase_csrf',''))
    supplied_csrf = str(form.get('csrf_token',''))
    if not expected_csrf or not supplied_csrf or not hmac.compare_digest(supplied_csrf,expected_csrf):
        abort(403,'Sitzung abgelaufen; bitte Seite neu laden.')
    try:
        did = int(form.get('driver_id',''))
        year = int(form.get('year',''))
        month = int(form.get('month',''))
    except (ValueError,TypeError):
        abort(400,'Ungültige Mitarbeiter- oder Monatsdaten.')
    if did <= 0 or not 2020 <= year <= 2100 or not 1 <= month <= 12:
        abort(400,'Ungültige Mitarbeiter- oder Monatsdaten.')
    return did,year,month


@app.post('/admin/shiftbase/direkt-senden')
@admin_login_required
def admin_shiftbase_direct_put():
    did,year,month = _sb_verified_post_scope(request.form)
    eid = str(request.form.get('timesheet_id','')).strip()
    if not re.fullmatch(r'\d{1,20}',eid):
        abort(400,'Ungültige Timesheet-ID.')
    try:
        source = _sb_review_source(did,year,month)
        day = _sb_verified_write_one(request.form,source,did,year,month,eid)
        session['shiftbase_direct_result'] = ('Erfolg: '+str(day)+
             ' in Shiftbase korrigiert und durch erneuten GET bestätigt.')
    except ShiftbaseIntegrationError as exc:
        session['shiftbase_direct_result'] = 'Fehler: '+str(exc)
    return redirect(url_for('admin_shiftbase_pruefvorschau',year=year,month=month,driver_id=did))


def _sb_verified_inline_batch_preflight(source, form, did, year, month):
    """Validate a ONE-click collectively attested proposal or manual edit.

    UI may prefill tentative numbers from _sb_hypothetical_preview, but the
    submit button explicitly certifies every changed value as checked against
    original time records. It is not a claim that the numerical model is proof.
    Each change is rechecked against the newly read Shiftbase source.
    """
    if form.get('confirmed_batch') != 'actual_work_verified_using_records':
        raise ShiftbaseIntegrationError('Bestätigung, dass geänderte Zeiten anhand von Arbeitszeitnachweisen geprüft sind, fehlt.')
    _sb_write_access_checked(source)
    rows=source['rows']
    if len(rows)>200:
        raise ShiftbaseIntegrationError('Zu viele Schichten für eine Sammelkorrektur.')
    vacation=set()
    if source.get('vacation_count') not in ('','0'):
        raw=str(form.get('urlaubs_tage','')).strip()
        try:
            count=int(str(source['vacation_count']))
            vacation=set(_expand_day_ranges(raw)) if raw else set()
            if not (1<=count<=31) or len(vacation)!=count:
                raise ValueError('Urlaubstage unvollständig')
            for n in vacation:
                shiftbase_date(year,month,n)
        except (ValueError,TypeError) as exc:
            raise ShiftbaseIntegrationError('Cloud-Urlaubstage sind nur als Anzahl gespeichert. Bitte konkrete Urlaubstage oben angeben und Monat neu abgleichen, sonst kein Sammel-PUT.') from exc
    try:
        sick=set(_expand_day_ranges(source.get('sick_ranges','')))
    except ValueError as exc:
        raise ShiftbaseIntegrationError('Cloud-Krankheitstage unklar – keine Sammelkorrektur.') from exc

    submissions=[]
    planned={}
    for r in rows:
        eid=str(r['entry_id'])
        orig=_sb_review_row_obj(r)
        start_key='sb_start_'+eid
        end_key='sb_end_'+eid
        pause_key='sb_pause_'+eid
        signature_key='sb_sig_'+eid
        present=[k in form for k in (start_key,end_key,pause_key,signature_key)]
        if not any(present):
            planned[eid]={**orig,'deleted':r.get('deleted',False)}
            continue
        if not all(present):
            raise ShiftbaseIntegrationError('Unvollständige Zeiteingaben für '+str(r['day'])+'. Kein PUT.')
        signature=str(form.get(signature_key,''))
        expected=_sb_direct_baseline_signature(did,source['uid'],year,month,eid,orig)
        if not hmac.compare_digest(signature,expected):
            raise ShiftbaseIntegrationError('Originaldaten '+str(r['day'])+' haben sich verändert. Bitte Monatsansicht neu laden.')
        values={name:str(form.get(k,'')).strip() for name,k in (
            ('start',start_key),('end',end_key),('pause',pause_key))}
        changed=(values['start'],values['end'],values['pause']) != (
            orig['start'],orig['end'],orig['break_minutes'])
        after={**orig}
        if changed:
            if (r.get('absence') or r.get('deleted') or
                int(str(r['day'])[-2:]) in sick or int(str(r['day'])[-2:]) in vacation or
                str(r.get('status','')).lower() in {'rejected','declined','abgelehnt'}):
                raise ShiftbaseIntegrationError('Tag '+str(r['day'])+' ist nicht für Zeitkorrekturen freigegeben.')
            net,span,pm=_sb_review_minutes(values['start'],values['end'],values['pause'])
            if net<=0 or values['start']<'06:00' or net>600 or (net>540 and pm<45) or (net>360 and pm<30):
                raise ShiftbaseIntegrationError('Zeit-/Pausengrenzen am '+str(r['day'])+' nicht erfüllt. Keine Übertragung.')
            after={**orig,'start':values['start'],'end':values['end'],
                   'break_minutes':str(pm),'hours':_sb_dayview_hm(Decimal(net)/Decimal(60))}
            evidence=('Sammelbestätigung des Administrators: laut eigener Erklärung nach Prüfung anhand '
                      'von Arbeitszeitnachweisen als Istzeit bestätigt; kein individueller '
                      'Belegverweis in der Cloud erfasst.')
            # Collective attestation is a user assertion, not automatic verification of records.
            data={'original_sig':signature,'certified':'yes','evidence':evidence,
                  'start':values['start'],'end':values['end'],'pause':str(pm),
                  'vacation_ack':'yes' if source.get('vacation_count') not in ('','0') else '',
                  'approved_ack':'yes'}
            submissions.append((eid,data))
        planned[eid]={**after,'deleted':r.get('deleted',False)}

    if not submissions:
        raise ShiftbaseIntegrationError('Keine geänderten, anhand von Belegen geprüften Zeiten eingegeben; kein PUT.')
    if len(submissions)>40:
        raise ShiftbaseIntegrationError('Maximal 40 Schichtkorrekturen in einem Vorgang.')
    # Check the complete proposed actual-times result, not just each shift alone.
    daily={}
    pauses={}
    for r in rows:
        eid=str(r['entry_id'])
        item=planned[eid]
        if item.get('deleted'): continue
        try:
            net,_,br=_sb_review_minutes(item['start'],item['end'],str(item['break_minutes']))
        except ValueError as exc:
            raise ShiftbaseIntegrationError('Unlesbare benachbarte Zeiten am '+str(r['day'])+'. Kein PUT.') from exc
        daily[item['day']]=daily.get(item['day'],0)+net
        pauses[item['day']]=pauses.get(item['day'],0)+br
    for day,net in daily.items():
        if net>600:
            raise ShiftbaseIntegrationError('Am '+day+' überschreiten alle Schichten zusammen 10 Stunden tatsächliche Arbeitszeit.')
        if (net>540 and pauses[day]<45) or (net>360 and pauses[day]<30):
            raise ShiftbaseIntegrationError('Die dokumentierten Pausen am '+day+' sind bei mehreren Schichten nicht ausreichend belegt.')
    conflict=_sb_rest_violation(list(planned.values()))
    if conflict:
        raise ShiftbaseIntegrationError('Zusammengerechnete Änderungen: '+conflict+' Kein PUT.')
    return submissions


@app.post('/admin/shiftbase/gepruefte-sammelkorrektur')
@admin_login_required
def admin_shiftbase_verified_batch():
    # Backward-compatible old URL: never perform a synchronous multi-PUT request.
    return _sb_stage_review_impl()


# ---------------- Ende einfache Direktkorrektur ----------------


@app.get('/admin/shiftbase/vorschlaege-pruefliste.csv')
@admin_login_required
def admin_shiftbase_vorschlaege_pruefliste_csv():
    """Export the hypothetical comparison for reviewing directly in Shiftbase.

    No POST or PUT, no persistence, and a clear label that all proposed times
    are UNVERIFIED until checked against an original attendance record.
    """
    import csv as _csv
    import io as _io
    year,month=_sb_params()
    raw=str(request.args.get('driver_id','')).strip()
    if not re.fullmatch(r'\d{1,12}',raw):
        abort(400,'Ungültige Fahrer-ID.')
    did=int(raw)
    try:
        source=_sb_review_source(did,year,month)
    except ShiftbaseIntegrationError as exc:
        abort(422,'Shiftbase-Daten können nicht gelesen werden: '+str(exc))
    source['preview_vacation_days']=str(request.args.get('urlaubs_tage','')).strip()[:100]
    plan=_sb_hypothetical_preview(source)
    buf=_io.StringIO(newline='')
    writer=_csv.writer(buf,delimiter=';')
    writer.writerow(['UNVERBINDLICHE PRÜFLISTE – KEIN ARBEITSZEITNACHWEIS – KEIN TIMESHEET-IMPORT'])
    writer.writerow(['Fahrer',_sb_csv_guard(source['name']),'Shiftbase-Benutzer-ID',source['uid']])
    writer.writerow(['Monat',f'{year}-{month:02d}'])
    writer.writerow(['Tatsächliche Shiftbase-Monatsstunden',_sb_dayview_hm(source['actual'])])
    writer.writerow(['Cloud-Abrechnungsstunden',_sb_dayview_hm(source['payroll']) if source['payroll'] is not None else 'nicht vorhanden'])
    writer.writerow(['Nicht verteilte Rechendifferenz',_sb_signed_hm(plan['unallocated'])])
    writer.writerow(['Hinweis','Rechnerische Zeiten NICHT ohne Talex-/Originalbeleg in Shiftbase übertragen.'])
    writer.writerow([])
    writer.writerow(['Datum','Timesheet-ID','Bisher Beginn','Bisher Ende','Bisher Pause (Min)',
                     'Hypothetisch Beginn','Hypothetisch Ende','Hypothetisch Pause (Min)',
                     'Hypothetische Differenz','Status','Talex-Beleg/Notiz (manuell ausfüllen)'])
    for row in source['rows']:
        eid=str(row['entry_id'])
        orig=_sb_review_row_obj(row)
        proposal=plan['days'].get(eid)
        status='UNGEPRÜFTER RECHENVORSCHLAG' if proposal else 'Unverändert / nicht geeignet'
        writer.writerow([_sb_csv_guard(x) for x in (
            orig['day'],eid,orig['start'],orig['end'],orig['break_minutes'],
            proposal['new_start'] if proposal else '',
            proposal['new_end'] if proposal else '',
            proposal['new_pause'] if proposal else '',
            _sb_signed_hm(Decimal(proposal['delta_minutes'])/Decimal(60)) if proposal else '',
            status,'')])
    handle=_io.BytesIO(('\ufeff'+buf.getvalue()).encode('utf-8'))
    handle.seek(0)
    response=send_file(handle,mimetype='text/csv; charset=utf-8',as_attachment=True,
                      download_name=f'shiftbase_unverbindliche_pruefliste_{did}_{year}_{month:02d}.csv')
    response.headers['Cache-Control']='private, no-store, max-age=0'
    response.headers['X-Robots-Tag']='noindex, nofollow'
    return response


@app.get('/admin/shiftbase/pruefvorschau.csv')
@admin_login_required
def admin_shiftbase_pruefvorschau_csv():
    """Manual review drafts only. NOT a Shiftbase work-hours import."""
    import io as _io
    import csv as _csv
    year,month=_sb_params()
    raw=request.args.get('driver_id','').strip()
    if not re.fullmatch(r'[0-9]{1,12}',raw):abort(400,'Ungültige Fahrer-ID')
    did=int(raw)
    with db_conn() as conn:
        _sb_review_table(conn)
        driver=conn.execute('SELECT name FROM drivers WHERE id=? AND is_active=1',(did,)).fetchone()
        if not driver:abort(404)
        data=conn.execute('SELECT * FROM shiftbase_review_drafts WHERE driver_id=? AND year=? AND month=? ORDER BY timesheet_id',(did,year,month)).fetchall()
    out=_io.StringIO(newline='')
    w=_csv.writer(out,delimiter=';')
    w.writerow(['Manuell geprüfte Korrektur-ENTWÜRFE, kein Arbeitszeitnachweis und kein Shiftbase-Import'])
    w.writerow(['Fahrer',_sb_csv_guard(driver['name'])])
    w.writerow(['Monat',f'{month:02d}/{year}'])
    w.writerow([])
    w.writerow(['Timesheet-ID','Datum','Alt Beginn','Alt Ende','Alt Pause (Min.)','Neu Beginn','Neu Ende','Neu Pause (Min.)','Begründung/Quelle','Zuletzt gespeichert'])
    for r in data:
        orig=json.loads(r['original_json']);new=json.loads(r['corrected_json'])
        w.writerow([_sb_csv_guard(x) for x in [r['timesheet_id'],new['day'],orig['start'],orig['end'],orig['break_minutes'],
                    new['start'],new['end'],new['break_minutes'],r['evidence'],r['updated_at']]])
    data=_io.BytesIO(('\ufeff'+out.getvalue()).encode('utf-8'))
    data.seek(0)
    response=send_file(data,mimetype='text/csv; charset=utf-8',as_attachment=True,
                       download_name=f'shiftbase_gepruefte_entwuerfe_{did}_{year}_{month:02d}.csv')
    response.headers['Cache-Control']='private, no-store, max-age=0'
    return response



# =========== Echte Shiftbase-PUT-Schnittstelle: nur geprüfte Einzelkorrekturen ==========
# Dokumentiert in Shiftbase "Edit timesheet":
# PUT https://api.shiftbase.com/api/timesheets/{timesheetId}
# Anders als eine Lohnstundensumme ist eine bestätigte Tageszeit ein Tatsachennachweis.
# Nie automatisch Monatsdifferenzen auf rückwirkende Schichten verteilen.

def _sb_put_audit_table(conn):
    conn.execute("""CREATE TABLE IF NOT EXISTS shiftbase_verified_writes (
        id TEXT PRIMARY KEY,
        driver_id INTEGER NOT NULL,
        shiftbase_user_id TEXT NOT NULL,
        year INTEGER NOT NULL,
        month INTEGER NOT NULL,
        timesheet_id TEXT NOT NULL,
        before_json TEXT NOT NULL,
        after_json TEXT NOT NULL,
        proof_ref TEXT NOT NULL,
        reason TEXT NOT NULL,
        written_at TEXT NOT NULL,
        result TEXT NOT NULL
    )""")


def _sb_ts_detail(timesheet_id):
    """Read one Shiftbase timesheet and unwrap its API response envelope.

    Observed account response can use {"data": {"Timesheet": {...}, ...},
    "meta": {...}} (and may contain a second data/meta wrapper). The monthly
    list has a different shape. Never use a guessed ID or substitute the ID
    requested in the URL: _sb_assert_timesheet_owner must verify the actual
    returned Timesheet.id and user_id BEFORE any PUT.
    """
    response = _shiftbase_read_json('timesheet_detail', {'_detail_id': str(timesheet_id)})
    if not isinstance(response, dict):
        raise ShiftbaseIntegrationError('Shiftbase-Einzelabruf ist kein JSON-Objekt. Kein PUT.')

    layer = response
    parents = []
    seen = set()
    ts = None
    envelope_user_ids = set()
    # Only traverse documented, structural wrapper names; don't search all
    # child objects (User, Rates etc. are not Timesheet records).
    for depth in range(8):
        if not isinstance(layer, dict) or id(layer) in seen:
            break
        seen.add(id(layer))
        parents.append(layer)

        user = layer.get('User')
        if isinstance(user, dict):
            user_id = _sb_id(user, 'id', 'user_id')
            if user_id:
                envelope_user_ids.add(str(user_id))

        candidate = layer.get('Timesheet')
        if isinstance(candidate, dict):
            # The Timesheet value can itself be wrapped in data/meta.
            layer = candidate
            continue

        # This identifies a timesheet payload, not an API wrapper. Explicitly
        # require a real record ID and relevant timesheet fields.
        if (_sb_id(layer, 'id', 'timesheet_id') is not None and
            ('date' in layer or 'starttime' in layer or 'endtime' in layer) and
            ('user_id' in layer or 'starttime' in layer or 'endtime' in layer)):
            ts = dict(layer)
            break

        data = layer.get('data')
        if isinstance(data, dict):
            layer = data
            continue
        break

    if ts is None:
        # Avoid exposing values, names, tokens or sensitive information in UI.
        chain = ' -> '.join(','.join(sorted(str(k)[:32] for k in node.keys())[:8])
                            for node in parents[:6])
        raise ShiftbaseIntegrationError(
            'Timesheet konnte nicht aus data/Timesheet entpackt werden. '
            'Antwort-Struktur (nur Feldnamen): ' + chain + '. Kein PUT.')

    if len(envelope_user_ids) > 1:
        raise ShiftbaseIntegrationError('Widersprüchliche Benutzer-IDs in der API-Antwort. Kein PUT.')
    if envelope_user_ids:
        ts['_sb_envelope_user_id'] = next(iter(envelope_user_ids))

    # Diagnostic metadata: structural only, no secrets or private data.
    ts['_sb_detail_root_id'] = _sb_id(response, 'id', 'timesheet_id')
    ts['_sb_detail_root_fields'] = sorted(str(k)[:48] for k in response.keys())[:35]
    ts['_sb_detail_timesheet_fields'] = sorted(str(k)[:48] for k in ts.keys()
                                             if not str(k).startswith('_sb_'))[:65]
    return ts


def _sb_assert_timesheet_owner(ts, expected_uid, timesheet_id):
    """Strictly verify the user of one GET /timesheets/{id} response.

    The monthly collection and single-item endpoints have different envelopes.
    A missing user_id may be supplied by nested User.id, but an *actual mismatch*
    is never ignored. Return a readable diagnostic without revealing tokens.
    """
    if not isinstance(ts,dict):
        raise ShiftbaseIntegrationError('Einzelabruf liefert keinen Timesheet-Datensatz. Kein PUT.')
    expected=str(expected_uid).strip()
    entry_id=str(_sb_id(ts,'id','timesheet_id') or '').strip()
    requested_id=str(timesheet_id).strip()
    def _sb_safe_ident(value):
        value=str(value or '').strip()
        return value if re.fullmatch(r'[0-9]{1,20}',value) else '(fehlt oder nicht numerisch)'
    if entry_id!=requested_id:
        root_id=_sb_safe_ident(_sb_get(ts,'_sb_detail_root_id'))
        fields=_sb_get(ts,'_sb_detail_root_fields') or []
        nested=_sb_get(ts,'_sb_detail_timesheet_fields') or []
        raise ShiftbaseIntegrationError(
            'ID-Diagnose – kein PUT: Angeforderte Timesheet-ID '+_sb_safe_ident(requested_id)+
            ', im Einzelabruf Timesheet.id '+_sb_safe_ident(entry_id)+
            ', oberste Ebene id '+root_id+'. Root-Felder: '+', '.join(fields[:16])+
            '. Timesheet-Felder: '+', '.join(nested[:24])+'. '
            'Kein Schreibzugriff, bis die IDs eindeutig uebereinstimmen.'
        )
    sources={}
    def record(label,value):
        if isinstance(value,dict):
            value=_sb_id(value,'id','user_id')
        if value is None or str(value).strip() in ('','null','None'):
            return
        txt=str(value).strip()
        # IDs are decimal identifiers, not floating-point quantities.
        if not re.fullmatch(r'\d{1,20}',txt):
            raise ShiftbaseIntegrationError(label+' enthält keine gültige Shiftbase-Benutzer-ID. Kein PUT.')
        sources[label]=str(int(txt))
    record('Timesheet.user_id',_sb_get(ts,'user_id'))
    record('Timesheet.User.id',_sb_get(ts,'User'))
    record('Einzelabruf.User.id',_sb_get(ts,'_sb_envelope_user_id'))
    if not sources:
        raise ShiftbaseIntegrationError(
            'Der Einzelabruf enthält keine erkennbare Benutzer-ID. '
            'Bitte API-Detailstruktur prüfen; kein PUT ausgeführt.')
    unique=set(sources.values())
    if len(unique)!=1:
        raise ShiftbaseIntegrationError(
            'Widersprüchliche Mitarbeiter-IDs innerhalb der Shiftbase-API-Antwort '
            '('+', '.join(sources.keys())+'). Kein PUT; API-Daten prüfen.')
    actual=next(iter(unique))
    if actual!=str(int(expected)):
        raise ShiftbaseIntegrationError(
            'Shiftbase meldet für diese Schicht eine andere Benutzer-ID '
            '(Einzelabruf '+actual+', Cloud-Zuordnung '+expected+'). '
            'Kein PUT. Bitte Mitarbeiterzuordnung und Schicht in Shiftbase prüfen.')
    return actual


def _sb_clean_clock(v):
    s=str(v or '').strip()
    if re.fullmatch(r'\d{1,2}:\d{2}(?::\d{2})?',s):
        hh,mm,*ss=[int(x) for x in s.split(':')]
        if hh<=23 and mm<=59 and (not ss or ss[0]==0):
            # UI edits are minute-precise. A nonzero source second must not
            # be silently rounded away and subsequently overwritten.
            return f'{hh:02d}:{mm:02d}'
    return ''


def _sb_live_snapshot(ts):
    day=_sb_day(_sb_get(ts,'date'))
    start=_sb_clean_clock(_sb_get(ts,'starttime'))
    end=_sb_clean_clock(_sb_get(ts,'endtime'))
    br=_sb_get(ts,'break')
    p=_sb_break_as_minutes(br)
    if not day or not start or not end or p is None or p!=p.to_integral_value():
        raise ShiftbaseIntegrationError('Live-Datensatz hat nicht auswertbare Zeit- oder Pausenwerte.')
    return {'day':day,'start':start,'end':end,'break_minutes':str(int(p))}


def _sb_update_payload(ts, timesheet_id, new, expected_uid=None, monthly_entry=None):
    """Build a flat Timesheet PUT body from verified API data only.

    The previous hard-coded ('id','date','department_id','team_id','shift_id')
    mandatory tuple was NOT an API-validated schema and wrongly rejected
    absent/null optional fields before any HTTP attempt. Only source fields
    which actually exist in the detail/list records are included. Values from
    the month list fill MISSING keys only, never explicit null values.

    The Shiftbase documentation site is JavaScript rendered; this adapter
    deliberately does not claim that nullable fields are required/accepted.
    On HTTP validation error, no speculative fallback PUT is attempted.
    """
    if str(_sb_id(ts, 'id', 'timesheet_id') or '') != str(timesheet_id):
        raise ShiftbaseIntegrationError('Timesheet-ID weicht vom Einzelabruf ab. Kein PUT.')
    if expected_uid is None:
        raise ShiftbaseIntegrationError('Schreibvorgang ohne bestätigte Benutzer-ID abgelehnt.')
    _sb_assert_timesheet_owner(ts, expected_uid, timesheet_id)
    original = _sb_live_snapshot(ts)
    if str(new.get('day')) != original['day']:
        raise ShiftbaseIntegrationError('Monats-/Tageswechsel in einer Korrektur ist unzulässig.')
    if not isinstance(monthly_entry, dict):
        monthly_entry = {}
    if monthly_entry:
        list_uid, list_day, _, list_id = _sb_timesheet_parts(monthly_entry)
        if (str(list_id) != str(timesheet_id) or str(list_uid) != str(expected_uid)
                or str(list_day) != original['day']):
            raise ShiftbaseIntegrationError('Monatsliste und Einzelabruf widersprechen sich bei ID, Mitarbeiter oder Datum. Kein PUT.')
    # Required for the local correction operation, not an invented claim
    # about mandatory attributes in the remote PUT schema.
    user_id = str(_sb_id(ts, 'user_id') or _sb_get(ts, '_sb_envelope_user_id') or '')
    if user_id != str(expected_uid):
        raise ShiftbaseIntegrationError('Benutzer-ID fehlt oder weicht ab; kein PUT.')
    payload = {'id': _sb_get(ts, 'id'), 'user_id': _sb_get(ts, 'user_id') or user_id,
               'date': original['day']}
    # Whitelist only editable/pass-through Timesheet request attributes;
    # don't echo API response fields like total, status, creator or GPS.
    monthly_ts = _sb_get(monthly_entry, 'Timesheet')
    if not isinstance(monthly_ts, dict):
        monthly_ts = monthly_entry
    pass_through = ('account_id', 'team_id', 'department_id', 'shift_id',
                    'roster_id', 'rate_card_id', 'paid_break', 'meals',
                    'kilometers', 'note')
    for key in pass_through:
        if key in ts:
            payload[key] = ts[key]  # includes explicit JSON null, not invented
        elif key in monthly_ts:
            payload[key] = monthly_ts[key]
    payload['starttime'] = new['start'] + ':00'
    payload['endtime'] = new['end'] + ':00'
    payload['break'] = str(int(new['break_minutes']))
    return payload

def _sb_put_timesheet(timesheet_id, payload):
    """Exactly one PUT; inspect HTTP/JSON outcome. No automatic retry."""
    if os.environ.get('SHIFTBASE_MOCK_DIR', '').strip():
        raise ShiftbaseIntegrationError('Schreibvorgänge im Demo-Modus deaktiviert.')
    if os.environ.get('SHIFTBASE_VERIFIED_WRITE_ENABLED', '').strip() != '1':
        raise ShiftbaseIntegrationError('Schreibzugriff ist nicht freigeschaltet.')
    cfg = _shiftbase_config()
    raw = cfg['token'].strip()
    prefix = os.environ.get('SHIFTBASE_AUTH_PREFIX', 'API').strip().upper()
    header_name = os.environ.get('SHIFTBASE_AUTH_HEADER', 'Authorization').strip()
    if header_name.lower() != 'authorization' or prefix != 'API':
        raise ShiftbaseIntegrationError('Schreibadapter erwartet Authorization: API <token>.')
    if raw.lower().startswith('api '):
        raw = raw[4:].strip()
    if not re.fullmatch(r'\d{1,20}', str(timesheet_id)):
        raise ShiftbaseIntegrationError('Ungültige Shiftbase-Timesheet-ID.')
    url = cfg['base'] + '/timesheets/' + quote(str(timesheet_id), safe='')
    data = json.dumps(payload, ensure_ascii=False, separators=(',', ':')).encode('utf-8')
    headers = {
        'Authorization': 'API ' + raw, 'Content-Type': 'application/json',
        'Accept': 'application/json',
        'User-Agent': 'PlusMinusCloud-VerifiedTimesheetCorrection/2.0'}
    try:
        status, raw_response = _sb_http_request('PUT', url, headers, 20,
                                                payload=data, max_bytes=1_000_000)
        if status not in (200, 201, 204):
            raise ShiftbaseIntegrationError('Shiftbase PUT HTTP ' + str(status) + '; GET-Kontrolle erforderlich.')
        if raw_response.strip():
            try:
                result = json.loads(raw_response.decode('utf-8'))
            except (UnicodeError, ValueError) as exc:
                raise ShiftbaseIntegrationError('PUT lieferte kein gültiges JSON; GET-Kontrolle erforderlich.') from exc
            if isinstance(result, dict):
                # Don't mistake an HTTP 200 with application-level failure for success.
                if result.get('success') is False or result.get('ok') is False or result.get('error'):
                    raise ShiftbaseIntegrationError('PUT-API meldet trotz HTTP-Erfolg einen Anwendungsfehler; in Shiftbase prüfen.')
        return status
    except HTTPError as exc:
        # Never include server-returned personal data or token in an error.
        try:
            body = exc.read(4096)
            parsed = json.loads(body.decode('utf-8'))
            # Field names only: useful for debugging 422, no arbitrary values.
            error_fields = []
            if isinstance(parsed, dict):
                details = parsed.get('errors') or parsed.get('validation_errors')
                if isinstance(details, dict):
                    error_fields = [str(k)[:36] for k in details if re.fullmatch(r'[A-Za-z_][A-Za-z0-9_]{0,35}', str(k))]
            suffix = (' Validierungsfelder: ' + ', '.join(error_fields[:12]) + '.') if error_fields else ''
        except (ValueError, UnicodeError, OSError):
            suffix = ''
        raise ShiftbaseIntegrationError('Shiftbase PUT HTTP ' + str(exc.code) + '.' + suffix +
                  ' Keine automatische Wiederholung; Berechtigungen und API-Schema prüfen.') from exc
    except (URLError, TimeoutError, OSError) as exc:
        raise ShiftbaseIntegrationError('PUT-Verbindung unklar/fehlgeschlagen. Vor erneutem Versuch Original in Shiftbase prüfen.') from exc

@app.post('/admin/shiftbase/verified-put')
@admin_login_required
def admin_shiftbase_put_verified():
    # Exakt EINE überprüfte Korrektur mit belegter Istzeit; kein Batch/Autobalancing.
    if os.environ.get('SHIFTBASE_VERIFIED_WRITE_ENABLED','').strip()!='1':
        abort(403,'Shiftbase-Schreibtest ist bei Render nicht freigeschaltet.')
    expected_csrf=str(session.get('shiftbase_csrf',''))
    supplied_csrf=str(request.form.get('csrf_token',''))
    if not expected_csrf or not supplied_csrf or not hmac.compare_digest(supplied_csrf,expected_csrf):
        abort(403,'Ungültiger CSRF-Schutz.')
    try:
        did=int(request.form.get('driver_id',''))
        year=int(request.form.get('year',''))
        month=int(request.form.get('month',''))
    except (ValueError,TypeError): abort(400,'Ungültige Monats- oder Mitarbeiterkennung.')
    if did<=0 or not (2020<=year<=2100) or not (1<=month<=12): abort(400)
    eid=str(request.form.get('timesheet_id','')).strip()
    if not re.fullmatch(r'\d{1,20}',eid): abort(400,'Ungültige Timesheet-ID.')
    if request.form.get('certified')!='yes': abort(400,'Prüfbestätigung fehlt.')
    proof=str(request.form.get('proof_ref','')).strip()[:200]
    if len(proof)<6:abort(400,'Konkreten Beleg zur Korrektur angeben.')
    # Refresh all read-only data & draft from database; never trust changed client fields.
    try:
        source=_sb_review_source(did,year,month)
        if (source['uid']!=os.environ.get('SHIFTBASE_VERIFIED_WRITE_USER_ID','').strip()
                or source['uid']!='1338173' or normalize(source['name'])!='kaan aysel'):
            abort(403,'Nur Kaan Aysel (1338173) ist für den Test freigegeben.')
        saved=source['drafts'].get(eid)
        selected=next((r for r in source['rows'] if str(r['entry_id'])==eid),None)
        if not saved or not selected:
            raise ShiftbaseIntegrationError('Kein gespeicherter Entwurf für diese Schicht.')
        before=json.loads(saved['original_json'])
        after=json.loads(saved['corrected_json'])
        reason=str(saved['evidence']).strip()
        if len(reason)<15:
            raise ShiftbaseIntegrationError('Gespeicherte Korrektur hat keinen hinreichenden Beleggrund.')
        if (str(before.get('day'))!=str(selected['day']) or
            str(after.get('day'))!=str(selected['day'])):
            raise ShiftbaseIntegrationError('Korrektur-Datum stimmt nicht mit dem aktuellen Tag überein.')
        if selected.get('absence') or selected.get('deleted'):
            raise ShiftbaseIntegrationError('Abwesenheit bzw. gelöschter Eintrag: nur manuelle Klärung, kein PUT.')
        try:
            sick_days=set(_expand_day_ranges(source.get('sick_ranges','')))
        except ValueError as exc:
            raise ShiftbaseIntegrationError('Cloud-Krankheitsdaten unklar; kein PUT.') from exc
        if int(str(selected['day'])[-2:]) in sick_days:
            raise ShiftbaseIntegrationError('Cloud-Krankheitstag darf nicht über PUT korrigiert werden.')
        if source.get('vacation_count') not in ('','0'):
            raise ShiftbaseIntegrationError('Alte Entwurfsübertragung bei Urlaubstagen gesperrt. Bitte die neue Einzelkorrektur benutzen.')
        if (after.get('start')==before.get('start') and after.get('end')==before.get('end') and
            str(after.get('break_minutes'))==str(before.get('break_minutes'))):
            raise ShiftbaseIntegrationError('Keine Änderung vorhanden.')
        # The sample proof must refer to actual time, not target payroll balance.
        try:
            net,span,pause=_sb_review_minutes(after['start'],after['end'],str(after['break_minutes']))
        except (ValueError, KeyError, TypeError) as exc:
            raise ShiftbaseIntegrationError('Korrekturentwurf hat ungültige Zeit- oder Pausenwerte.') from exc
        if after['start']<'06:00' or net>600 or (net>540 and pause<45) or (net>360 and pause<30):
            raise ShiftbaseIntegrationError('Korrektur verletzt die vereinbarten Planungs- bzw. Pausenprüfungen.')
        ts=_sb_ts_detail(eid)
        _sb_assert_timesheet_owner(ts,source['uid'],eid)
        live=_sb_live_snapshot(ts)
        if live != {k:str(v) for k,v in before.items() if k in ('day','start','end','break_minutes')}:
            raise ShiftbaseIntegrationError('Shiftbase hat sich seit Erstellung des Entwurfs geändert. Erneut prüfen, kein PUT.')
        if any(_sb_get(ts,k) is not None for k in ('clocked_in','clocked_out')):
            raise ShiftbaseIntegrationError('Gestempelter Datensatz: Korrektur muss über Stempelkorrekturprozess erfolgen.')
        _sb_rest_check_before_write(source,eid,after)
        payload=_sb_update_payload(ts,eid,after,expected_uid=source['uid'],
                                   monthly_entry=source['raw_timesheets'].get(eid))
        # Audit intent must be durable BEFORE sending the remote PUT.
        audit_id=secrets.token_hex(16)
        with db_conn() as conn:
            _sb_put_audit_table(conn)
            conn.execute('INSERT INTO shiftbase_verified_writes(id,driver_id,shiftbase_user_id,year,month,timesheet_id,before_json,after_json,proof_ref,reason,written_at,result) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)',
                    (audit_id,did,source['uid'],year,month,eid,
                     json.dumps(before,ensure_ascii=False),json.dumps(after,ensure_ascii=False),proof,reason,now_iso(),'VORBEREITET: Noch kein PUT gesendet'))
            conn.commit()
        # One PUT, followed by a GET. Never retry automatically if connection breaks.
        try:
            status=_sb_put_timesheet(eid,payload)
            after_detail=_sb_ts_detail(eid)
            _sb_assert_timesheet_owner(after_detail,source['uid'],eid)
            reread=_sb_live_snapshot(after_detail)
            expected={k:str(v) for k,v in after.items() if k in ('day','start','end','break_minutes')}
            if reread!=expected:
                raise ShiftbaseIntegrationError('PUT angenommen, aber GET zeigt abweichende Werte. Weitere Änderungen stoppen.')
        except ShiftbaseIntegrationError:
            with db_conn() as conn:
                conn.execute('UPDATE shiftbase_verified_writes SET result=? WHERE id=?',
                             ('UNBESTÄTIGT / Prüfen in Shiftbase bevor erneut gesendet wird',audit_id))
                conn.commit()
            raise
        with db_conn() as conn:
            conn.execute('UPDATE shiftbase_verified_writes SET result=? WHERE id=?',
                         ('PUT '+str(status)+' / GET bestätigt',audit_id))
            conn.execute('DELETE FROM shiftbase_review_drafts WHERE driver_id=? AND year=? AND month=? AND timesheet_id=?',
                         (did,year,month,eid))
            conn.commit()
        session['shiftbase_put_result']='Schicht '+str(selected['day'])+' erfolgreich übertragen und erneut ausgelesen.'
    except ShiftbaseIntegrationError as exc:
        session['shiftbase_put_result']='Fehler: '+str(exc)
    return redirect(url_for('admin_shiftbase_pruefvorschau',driver_id=did,year=year,month=month))


# ========== Shiftbase-Methodencheck: ausschliesslich HTTP OPTIONS (kein Schreibaufruf) ==========
def _sb_options_check(path: str) -> dict:
    """Probe OPTIONS only. No POST, PUT, PATCH or DELETE; never displays response body."""
    cfg = _shiftbase_config()
    if cfg.get('mock_dir'):
        return {'http': 'Demo-Modus', 'allow': '', 'cors_methods': ''}
    if not re.fullmatch(r'/timesheets(?:/[0-9]{1,20})?', path):
        raise ShiftbaseIntegrationError('Ungueltiger Timesheet-Testpfad.')
    ah = os.environ.get('SHIFTBASE_AUTH_HEADER', 'Authorization').strip()
    if ah.lower() not in {'authorization', 'x-api-key', 'x-auth-token'}:
        raise ShiftbaseIntegrationError('Ungültige Authentifizierungskonfiguration.')
    raw = cfg['token'].strip()
    prefix = os.environ.get('SHIFTBASE_AUTH_PREFIX','API').strip().upper()
    if ah.lower() == 'authorization':
        if prefix == 'API':
            value = 'API ' + (raw[4:].strip() if raw.lower().startswith('api ') else raw)
        elif prefix == 'BEARER':
            value = 'Bearer ' + (raw[7:].strip() if raw.lower().startswith('bearer ') else raw)
        else:
            raise ShiftbaseIntegrationError('Unbekanntes Auth-Praefix.')
    else:
        value = raw
    headers = {ah: value, 'Accept': 'application/json', 'User-Agent':'PlusMinusCloud-ShiftbaseMethodencheck/1.0'}
    req = Request(cfg['base'] + path, headers=headers, method='OPTIONS')
    try:
        with build_opener(_ShiftbaseNoRedirect()).open(req, timeout=12) as res:
            status = res.status
            hdr = res.headers
    except HTTPError as exc:
        status = exc.code
        hdr = exc.headers
    except (URLError, OSError, TimeoutError) as exc:
        raise ShiftbaseIntegrationError('OPTIONS-Test: keine Verbindung zur Shiftbase-API.') from exc
    # Deliberately do not return any response body, auth headers, user data or token.
    def allowed_header(name):
        v = str(hdr.get(name, '') or '')
        # Only method names and separators allowed, to prevent arbitrary header reflection.
        return v[:220] if re.fullmatch(r'[A-Za-z, \-]{0,220}', v) else '(nicht auswertbar)'
    return {'http': str(status), 'allow': allowed_header('Allow'), 'cors_methods': allowed_header('Access-Control-Allow-Methods')}


@app.get('/admin/shiftbase/api-methodencheck')
@admin_login_required
def admin_shiftbase_api_methodencheck():
    """Non-mutating test that investigates HTTP methods for Shiftbase timesheets."""
    year, month = _sb_params()
    found_id = None
    message = ''
    # Restrict the sample to an already mapped employee: Kaan Aysel, if present.
    try:
        with db_conn() as conn:
            locals_ = _sb_local_month(conn, year, month)
            mapping = _sb_mapping(conn)
        kaan = next((r for r in locals_ if normalize(r['name']) == 'kaan aysel'), None)
        if kaan and kaan['driver_id'] in mapping:
            uid = str(mapping[kaan['driver_id']])
            first = f'{year:04d}-{month:02d}-01'
            last = f'{year:04d}-{month:02d}-{__import__("calendar").monthrange(year,month)[1]:02d}'
            rows = _shiftbase_get_all('timesheets',{'min_date':first,'max_date':last,'user_id':uid})
            for row in rows:
                rid, day, _, ident = _sb_timesheet_parts(row)
                if str(rid) == uid and ident and re.fullmatch(r'[0-9]{1,20}',str(ident)) and day and first <= day <= last:
                    found_id = str(ident)
                    break
        else:
            message = 'Kein zugeordneter Fahrer Kaan Aysel im ausgewählten Monat.'
    except (ShiftbaseIntegrationError, ValueError, TypeError, KeyError) as exc:
        message = f'Einzeltest nicht möglich: {type(exc).__name__}. Die Sammlung kann trotzdem geprüft werden.'

    paths = ['/timesheets'] + (['/timesheets/'+found_id] if found_id else [])
    results = []
    for path in paths:
        try:
            result = _sb_options_check(path)
            results.append((('Einzelner Zeiteintrag' if found_id and path.endswith('/'+found_id) else 'Zeiterfassungs-Sammlung'), result))
        except ShiftbaseIntegrationError as exc:
            results.append(('Zeiteinträge', {'http':'Fehler', 'allow':'', 'cors_methods':''}))
            message = (message + ' ' if message else '') + str(exc)
    h=['<div class="card"><h2>Shiftbase – API-Methodencheck</h2>',
       '<p>Dieser Test verwendet <b>ausschließlich HTTP OPTIONS</b> und verändert weder Arbeitszeiten noch Personal- oder Lohndaten. Er zeigt, welche HTTP-Methoden der API-Server eventuell ankündigt.</p>',
       '<p class="muted"><b>Wichtig:</b> Ein OPTIONS-Ergebnis allein beweist keinen funktionierenden Schreibzugriff. Auch ein fehlender Allow-Header schließt ihn nicht sicher aus. Ein echter Schreibtest wäre nur auf einem eigens angelegten, unproduktiven Testeintrag mit bestätigtem Update-Endpunkt sinnvoll.</p>']
    if message:
        h.append('<p class="flash err">'+shiftbase_escape(message)+'</p>')
    h.append('<div class="table-wrap"><table style="min-width:620px"><thead><tr><th>Geprüft</th><th>HTTP</th><th>Allow</th><th>CORS-Methoden</th></tr></thead><tbody>')
    for title, r in results:
        h.append('<tr>'+''.join('<td>'+shiftbase_escape(str(v))+'</td>' for v in (title,r['http'],r['allow'] or '–',r['cors_methods'] or '–'))+'</tr>')
    h.append('</tbody></table></div>')
    h.append('<p>Schicke mir einen Screenshot dieser Tabelle. API-Token und Mitarbeiterdaten werden hier nicht angezeigt.</p>')
    h.append('<p><a class="btn" href="'+url_for('admin_shiftbase_abgleich',year=year,month=month)+'">Zurück zum Shiftbase-Abgleich</a></p></div>')
    return base_page('Shiftbase API-Methodencheck', ''.join(h), 'shiftbase')

# ========== Ende Methodencheck ==========



# ========== Resumable Shiftbase transfer (one remote operation per request) ==========
# The individual review form is the only source of certified factual corrections.
# Hypothetical monthly hours can never be added directly to the dispatch queue.

def _sb_queue_schema(conn):
    conn.execute("""CREATE TABLE IF NOT EXISTS shiftbase_review_queue (
        driver_id INTEGER NOT NULL, year INTEGER NOT NULL, month INTEGER NOT NULL,
        shiftbase_user_id TEXT NOT NULL, source_json TEXT NOT NULL,
        corrections_json TEXT NOT NULL, created_at TEXT NOT NULL,
        PRIMARY KEY(driver_id,year,month)
    )""")
    conn.execute("""CREATE TABLE IF NOT EXISTS shiftbase_transfer_runs (
        id TEXT PRIMARY KEY, year INTEGER NOT NULL, month INTEGER NOT NULL,
        created_at TEXT NOT NULL, state TEXT NOT NULL, message TEXT NOT NULL
    )""")
    conn.execute("""CREATE TABLE IF NOT EXISTS shiftbase_transfer_sources (
        run_id TEXT NOT NULL, driver_id INTEGER NOT NULL, source_json TEXT NOT NULL,
        PRIMARY KEY(run_id,driver_id)
    )""")
    conn.execute("""CREATE TABLE IF NOT EXISTS shiftbase_transfer_tasks (
        id TEXT PRIMARY KEY, run_id TEXT NOT NULL, ordinal INTEGER NOT NULL,
        driver_id INTEGER NOT NULL, shiftbase_user_id TEXT NOT NULL,
        timesheet_id TEXT NOT NULL, baseline_json TEXT NOT NULL,
        target_json TEXT NOT NULL, signature TEXT NOT NULL,
        payload_json TEXT NOT NULL DEFAULT '', audit_id TEXT NOT NULL DEFAULT '',
        state TEXT NOT NULL, message TEXT NOT NULL, updated_at TEXT NOT NULL
    )""")


def _sb_queue_form_certified(source, form, did, year, month):
    # Use existing central batch validator. It checks signed originals, all
    # split shifts, absences, daily work/breaks and rest across the whole month.
    submissions = _sb_verified_inline_batch_preflight(source,form,did,year,month)
    rows = {str(row['entry_id']): row for row in source['rows']}
    corrections = []
    for eid, data in submissions:
        original = _sb_review_row_obj(rows[eid])
        corrections.append({
            'timesheet_id': eid, 'day': original['day'], 'before': original,
            'after': {'day':original['day'], 'start':data['start'],
                      'end':data['end'],'break_minutes':data['pause']},
            'signature':data['original_sig'],
        })
    return corrections


def _sb_create_transfer_run_direct(prepared, year, month):
    """Atomic, immediate transfer-run creation from freshly checked records.

    The discontinued 'Vormerken' workflow is NOT used. Durable transfer
    tasks and sources remain essential for progress and safe interruption
    recovery; no API PUT is performed in this function.
    """
    if not prepared or len(prepared) > 150:
        raise ShiftbaseIntegrationError('Keine geprüften Änderungen ausgewählt.')
    ids = [int(did) for did, _, _ in prepared]
    if len(set(ids)) != len(ids):
        raise ShiftbaseIntegrationError('Fahrer wurde doppelt ausgewählt.')
    run_id = secrets.token_hex(16)
    with db_conn() as conn:
        _sb_queue_schema(conn)
        ordinal = 0
        # Preflight all tasks BEFORE creating any part of the transfer run.
        for did, source, updates in prepared:
            if (int(source['driver_id']) != did or
                    int(source['year']) != year or int(source['month']) != month):
                raise ShiftbaseIntegrationError('Falscher Mitarbeiter oder Monat.')
            _sb_write_access_checked(source)
            if not 1 <= len(updates) <= 40:
                raise ShiftbaseIntegrationError('Ungültige Anzahl geprüfter Änderungen.')
            if len({str(u['timesheet_id']) for u in updates}) != len(updates):
                raise ShiftbaseIntegrationError('Doppelte Timesheet-ID.')
            for u in updates:
                if not re.fullmatch(r'[0-9]{1,20}',str(u['timesheet_id'])):
                    raise ShiftbaseIntegrationError('Ungültige Timesheet-ID.')
            active = conn.execute(
                'SELECT t.id FROM shiftbase_transfer_tasks t '
                'JOIN shiftbase_transfer_runs r ON t.run_id=r.id '
                'WHERE t.driver_id=? AND r.year=? AND r.month=? '
                'AND t.state NOT IN (?,?,?) LIMIT 1',
                (did,year,month,'confirmed','uncertain','error')).fetchone()
            if active:
                raise ShiftbaseIntegrationError('Für '+str(source['name'])+
                    ' läuft bereits eine Übertragung. Vorhandene Fortschrittsseite öffnen.')
        conn.execute('INSERT INTO shiftbase_transfer_runs(id,year,month,created_at,state,message) '
                     'VALUES(?,?,?,?,?,?)',
                     (run_id,year,month,now_iso(),'ready','Wartet auf sichere Übertragung'))
        for did, source, updates in prepared:
            conn.execute('INSERT INTO shiftbase_transfer_sources(run_id,driver_id,source_json) '
                         'VALUES(?,?,?)',
                         (run_id,did,json.dumps(source,default=str,ensure_ascii=False)))
            for item in updates:
                ordinal += 1
                conn.execute('INSERT INTO shiftbase_transfer_tasks '
                    '(id,run_id,ordinal,driver_id,shiftbase_user_id,timesheet_id,baseline_json,target_json,'
                    'signature,state,message,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)',
                    (secrets.token_hex(16),run_id,ordinal,did,str(source['uid']),
                     str(item['timesheet_id']),
                     json.dumps(item['before'],ensure_ascii=False),
                     json.dumps(item['after'],ensure_ascii=False),
                     item['signature'],'pending','Wartet auf Einzelprüfung',now_iso()))
        conn.commit()
    return run_id


def _sb_stage_review_impl():
    did,year,month = _sb_verified_post_scope(request.form)
    try:
        if request.form.get('mode','start') != 'start':
            raise ShiftbaseIntegrationError('Die Vormerkfunktion ist abgeschaltet. Bitte direkt senden.')
        source = _sb_review_source(did,year,month)
        corrections = _sb_queue_form_certified(source,request.form,did,year,month)
        run_id = _sb_create_transfer_run_direct([(did,source,corrections)],year,month)
        return redirect(url_for('admin_shiftbase_transfer_view',run_id=run_id,autostart=1))
    except (ShiftbaseIntegrationError,ValueError,TypeError) as exc:
        session['shiftbase_direct_result'] = 'Keine Übertragung: '+str(exc)
        return redirect(url_for('admin_shiftbase_pruefvorschau',driver_id=did,year=year,month=month,
                                urlaubs_tage=str(request.form.get('urlaubs_tage',''))[:100]))


@app.post('/admin/shiftbase/transfer/review')
@admin_login_required
def admin_shiftbase_stage_review():
    return _sb_stage_review_impl()




@app.get('/admin/shiftbase/transfer/overview')
@admin_login_required
def admin_shiftbase_transfer_dashboard():
    year,month=_sb_params()
    with db_conn() as conn:
        _sb_queue_schema(conn)
        local=_sb_local_month(conn,year,month)
        mapping=_sb_mapping(conn)
        recent_runs=[dict(r) for r in conn.execute(
            'SELECT id,year,month,created_at,state FROM shiftbase_transfer_runs '
            'WHERE year=? AND month=? ORDER BY created_at DESC LIMIT 8',(year,month)).fetchall()]
    eligible=[r for r in local if r['driver_id'] in mapping]
    esc=lambda v:shiftbase_escape(str(v),quote=True)
    h=['''<style>
.sb-overview{max-width:1140px;margin:auto}.sb-overview .sb-toolbar{display:flex;flex-wrap:wrap;gap:9px;align-items:center;margin:12px 0}
.sb-overview .sb-toolbar button,.sb-overview .sb-toolbar a{width:auto}.sb-overview table{min-width:690px}
.sb-overview .sb-fine{font-size:12px;color:#667085}.sb-overview .sb-ok{color:#067647;font-weight:800}
.sb-overview input[type=checkbox]{width:18px;height:18px}
.sb-overview .sb-cell{max-width:350px;overflow-wrap:break-word}
.sb-overview tr.sb-match td,.sb-overview tr.sb-match:hover td{background:#eaf8ef!important}
.sb-overview tr.sb-mismatch td,.sb-overview tr.sb-mismatch:hover td{background:#fff0f0!important}
.sb-overview tr.sb-unknown td,.sb-overview tr.sb-unknown:hover td{background:#fff9e9!important}
</style>''',
       '<div class="sb-overview"><div class="card"><h2>Shiftbase – Monatsübersicht für alle Fahrer</h2>',
       '<p>Du kannst einzelne oder alle zugeordneten Fahrer auswählen. Der Monatsdatenabruf wird für die ausgewählten Fahrer zusammengefasst; die Vorschläge werden danach je Fahrer separat berechnet. <b>Rechenvorschläge sind keine nachgewiesenen Istzeiten.</b></p>',
       '<details class="sb-hint"><summary><b>Arbeitszeitregeln und Grenzen der automatischen Planung anzeigen</b></summary>'
       '<p><b>ArbZG §§ 3–5:</b> regulär bis 8 Netto-Stunden je Werktag; bis 10 nur mit gesetzlichem Ausgleich, den eine einzelne Monatsansicht nicht vollständig nachweist. '
       'Mehr als 6 Netto-Stunden: mindestens 30 Minuten echte Pause; mehr als 9 Stunden: mindestens 45 Minuten, in Abschnitten von mindestens 15 Minuten. '
       'Nicht länger als 6 Stunden ohne echte Pause. Zwischen Schichten grundsätzlich 11 Stunden ununterbrochene Ruhe. '
       'Die Cloud plant neue Netto-Dauern nur in 15-Minuten-Schritten und konservativ höchstens 8 Stunden pro Tag bzw. 48 Stunden je im Monat sichtbarer Kalenderwoche.</p>'
       '<p>Die Lage echter Pausen, Ausgleichszeiträume, andere Arbeitsverhältnisse und arbeitsfreie Sonntage/Feiertage '
       'kann die Cloud aus einem Monat nicht vollständig nachweisen. Für Verkehrsbetriebe gibt es Ausnahmen, einschließlich '
       'Ersatzruhetagen, die nicht automatisch vorausgesetzt werden. '
       '<a href="https://www.gesetze-im-internet.de/arbzg/" target="_blank" rel="noopener noreferrer">Gesetzestext (ArbZG)</a>. '
       'Unveränderte Originalschichten werden nicht auf Viertelstunden umgeschrieben.</p></details>',
       '<form action="'+url_for('admin_shiftbase_transfer_dashboard')+'" method="get" class="actions" id="sb-month-filter">',
       '<label>Jahr<input name="year" type="number" min="2020" max="2100" value="'+str(year)+'" style="width:110px"></label>',
       '<label>Monat<select name="month" style="width:155px">'+''.join('<option value="'+str(m)+'"'+(' selected' if m==month else '')+'>'+MONATE[m]+'</option>' for m in range(1,13))+'</select></label>',
       '<noscript><button type="submit" class="primary">Monat anzeigen</button></noscript></form>',
       '<p>'+str(len(eligible))+' aktive, eindeutig zugeordnete Fahrer in dieser Übersicht. Alle übrigen Mitarbeiter bleiben ausgeschlossen, bis sie korrekt zugeordnet sind.</p>',
       '<label>Fahrer suchen<input type="search" id="sb-search" placeholder="Name eingeben …" style="max-width:380px"></label>',
       '<div class="sb-toolbar"><button type="button" id="sb-all" class="primary">Alle auswählen</button>',
       '<button type="button" id="sb-none">Auswahl aufheben</button>',
       '<button type="button" id="sb-preview-all" class="primary">Vorschläge für ALLE Fahrer erstellen</button>',
       '<button type="button" id="sb-preview">Vorschläge für Auswahl erstellen</button></div>',
       '<div id="sb-read-progress" role="status" class="sb-fine">Noch keine Vorschau geladen.</div>',
       '<div class="table-wrap"><table><thead><tr><th>Auswahl</th><th>Fahrer</th><th>Abrechnung</th><th>Shiftbase / Differenz</th><th>Aktion</th></tr></thead><tbody>']
    for driver in eligible:
        did=int(driver['driver_id'])
        preview=url_for('admin_shiftbase_pruefvorschau',year=year,month=month,driver_id=did)
        h.append('<tr data-driver="'+str(did)+'"><td><input type="checkbox" name="driver_id" value="'+str(did)+'" aria-label="'+esc(driver['name'])+' wählen"></td>'
                 '<td><b>'+esc(driver['name'])+'</b><div class="sb-fine">Shiftbase-ID '+esc(mapping[did])+'</div></td>'
                 '<td>'+esc(_sb_dayview_hm(driver['payroll_hours']) if driver['payroll_hours'] is not None else '–')+'</td>'
                 '<td class="sb-cell" data-preview="'+str(did)+'">Noch nicht berechnet</td>'
                 '<td><a href="'+esc(preview)+'">Zeiten prüfen</a></td></tr>')
    h.append('</tbody></table></div><p class="sb-fine">Grün: Abrechnung und Shiftbase-Ist stimmen überein. Rot: Abweichung. Gelb: Daten nicht eindeutig abrufbar. Die Ampel erscheint nach dem Berechnen der Vorschau.</p>')
    h.append('<form id="sb-bulk-review-form" action="'+url_for('admin_shiftbase_bulk_review')+'" method="post" style="margin-top:20px">'
             '<input type="hidden" name="csrf_token" value="'+esc(_sb_csrf_token())+'">'
             '<input type="hidden" name="year" value="'+str(year)+'"><input type="hidden" name="month" value="'+str(month)+'">'
             '<div class="card"><h3>Gemeinsame Prüfansicht – rechnerische Vorschläge für alle gewählten Fahrer</h3>'
             '<p class="sb-fine"><b>Wichtig:</b> Ein berechneter Vorschlag ist kein Arbeitszeitnachweis. '
             'Vergleiche die vorgeschlagenen Zeiten und Pausen mit den tatsächlichen Arbeitszeitnachweisen. '
             '<b>Ein Klick auf „Geprüfte Istzeiten senden“ ist die direkte Freigabe der angezeigten Korrekturen;</b> '
             'ein zusätzliches Häkchen oder Bestätigungsfenster gibt es nicht. Unveränderte und gesperrte Schichten werden nicht übertragen.</p>'
             '<div class="actions"><button type="button" id="sb-expand-proposals">Alle Fahrerdetails öffnen</button>'
             '<button type="button" id="sb-collapse-proposals">Alle Fahrerdetails schließen</button></div>'
             '<div id="sb-bulk-review-results" role="region" aria-label="Monatsvorschläge"></div>'
             '<div id="sb-bulk-review-count" class="sb-fine"></div>'
             '<div class="actions" style="margin-top:14px">'
             '<button type="submit" name="mode" value="start" class="primary" style="width:auto">Geprüfte Istzeiten direkt senden · Fortschrittsanzeige</button>'
             '</div></div></form>'
             '<div class="card"><h3>Neue / möglicherweise fehlerhafte Arbeitstage – einzeln kontrollieren</h3>'
             '<p class="sb-fine">Automatisch vorgeschlagene Tage und Fehlbuchungen stehen hier als einzelne, editierbare Prüfaufträge. '
             'Sie werden nicht gemeinsam mit den bestehenden PUT-Korrekturen versendet. '
             'Neue Tage dürfen ausschließlich anhand tatsächlicher Nachweise eingetragen werden; bei Fehlbuchungen '
             'muss die konkrete Timesheet-ID nachweislich falsch sein. Die API-Einzeltest-Freigabe bleibt getrennt.</p>'
             '<div id="sb-bulk-day-actions"></div></div>')
    h.append(_SB_DAY_PROPOSAL_JS)
    h.append(r'''<script>
(function(){
const root=document.querySelector('.sb-overview');if(!root)return;
// Monat und Jahr bestimmen immer den Kontext: nach jeder Auswahl ohne weiteren Button neu laden.
const monthFilter=root.querySelector('#sb-month-filter');
const monthInput=monthFilter.querySelector('select[name="month"]');
const yearInput=monthFilter.querySelector('input[name="year"]');
let yearNavigationTimer;
const updateMonth=()=>{if(monthFilter.reportValidity())monthFilter.requestSubmit();};
monthInput.addEventListener('change',updateMonth);
yearInput.addEventListener('change',updateMonth);
yearInput.addEventListener('input',()=>{
 clearTimeout(yearNavigationTimer);
 if(/^\d{4}$/.test(yearInput.value)&&yearInput.checkValidity())
  yearNavigationTimer=setTimeout(updateMonth,550);
});
const checks=()=>Array.from(root.querySelectorAll('input[name="driver_id"]:checked'));
const boxes=()=>Array.from(root.querySelectorAll('tr[data-driver] input[name="driver_id"]'));
root.querySelector('#sb-all').onclick=()=>boxes().forEach(x=>x.checked=true);
root.querySelector('#sb-none').onclick=()=>boxes().forEach(x=>x.checked=false);
const progress=root.querySelector('#sb-read-progress');
function paintDiff(did,minutes){
 const row=root.querySelector('tr[data-driver="'+did+'"]');
 if(!row)return;
 row.classList.remove('sb-match','sb-mismatch','sb-unknown');
 row.classList.add(minutes===null||minutes===undefined?'sb-unknown':
   Math.abs(minutes)<1?'sb-match':'sb-mismatch');
}
async function readTrafficLights(){
 try{
  const params=new URLSearchParams({csrf_token:'CSRF',year:'YYYY',month:'MM'});
  const res=await fetch('MONTHSTATUS',{method:'POST',body:params,credentials:'same-origin',cache:'no-store'});
  const data=await res.json();if(!res.ok)throw Error(data.error||'Stundenabruf fehlgeschlagen');
  for(const driver of data.drivers){
   const cell=root.querySelector('[data-preview="'+driver.driver_id+'"]');
   if(cell&&cell.textContent==='Noch nicht berechnet') cell.textContent=driver.summary;
   paintDiff(driver.driver_id,driver.difference_minutes);
  }
  if(!loaded)progress.textContent='Monatsstunden aktualisiert. Du kannst jetzt Vorschläge für alle oder ausgewählte Fahrer erstellen.';
 }catch(e){if(!loaded)progress.textContent='Stundenstatus konnte nicht geladen werden: '+e.message;}
}

const result=document.getElementById('sb-bulk-review-results');
const reviewForm=document.getElementById('sb-bulk-review-form');
const counter=document.getElementById('sb-bulk-review-count');
const esc=s=>String(s==null?'':s).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const signed=v=>{const n=Math.abs(v);return (v>0?'+':v<0?'−':'')+Math.floor(n/60)+':'+String(n%60).padStart(2,'0');};
function net(s,e,p){if(!/^\d{2}:\d{2}$/.test(s)||!/^\d{2}:\d{2}$/.test(e)||!/^\d+$/.test(p))return null;
 const a=Number(s.slice(0,2))*60+Number(s.slice(3)),b=Number(e.slice(0,2))*60+Number(e.slice(3)),z=Number(p);
 const d=(b<=a?b+1440:b)-a;return d>0&&d<=1440&&z<=d?d-z:null;}
root.querySelector('#sb-search').addEventListener('input',function(){const term=this.value.toLocaleLowerCase('de');root.querySelectorAll('tr[data-driver]').forEach(row=>row.style.display=row.textContent.toLocaleLowerCase('de').includes(term)?'':'none');});
let loaded=false;
function recalc(){let drivers=0,changes=0;
 result.querySelectorAll('.sb-driver-review').forEach(panel=>{
  let count=0;
  panel.querySelectorAll('.sb-review-shift').forEach(row=>{
   const fields=Array.from(row.querySelectorAll('input[data-field]'));
   const dirty=fields.some(x=>x.value!==x.dataset.original);
   row.classList.toggle('sb-dirty',dirty);
   const nums=fields.map(x=>x.value);
   const old=fields.map(x=>x.dataset.original);
   const oldNet=net(old[0],old[1],old[2]),newNet=net(nums[0],nums[1],nums[2]);
   const diff=row.querySelector('.sb-row-diff');if(diff)diff.textContent=oldNet===null||newNet===null?'–':signed(newNet-oldNet);
   if(dirty)count++;
  });
  panel.querySelector('.sb-driver-count').textContent=count+' geänderte Schichten';
  const candidate=panel.querySelector('input.sb-driver-send');
  const ready=count>0&&panel.dataset.blocked!=='1';
  candidate.disabled=!ready;
  if(ready){drivers++;changes+=count;}
 });
 counter.textContent=drivers+' Fahrer mit Änderungen · '+changes+' zu sendende Schichtänderungen. Vor dem Senden mit Originalnachweisen abgleichen.';
}
async function load(all){
 if(all) boxes().forEach(x=>x.checked=true);
 const ids=checks().map(x=>x.value);
 if(!ids.length){progress.textContent='Bitte Fahrer auswählen.';return;}
 loaded=false;result.innerHTML='';root.querySelector('#sb-bulk-day-actions').innerHTML='';counter.textContent='';
 const buttons=[root.querySelector('#sb-preview'),root.querySelector('#sb-preview-all')];buttons.forEach(x=>x.disabled=true);
 progress.textContent='Lese gemeinsame Shiftbase-Monatsdaten und berechne Vorschläge für '+ids.length+' Fahrer …';
 try{
  const body=new URLSearchParams({csrf_token:'CSRF',year:'YYYY',month:'MM'});
  ids.forEach(id=>body.append('driver_id',id));
  const response=await fetch('BULKPREVIEW',{method:'POST',body,credentials:'same-origin',cache:'no-store'});
  const data=await response.json();if(!response.ok)throw Error(data.error||'Abruf fehlgeschlagen');
  const dayActions=root.querySelector('#sb-bulk-day-actions');
  dayActions.innerHTML='';
  for(const item of data.drivers){
   const cell=root.querySelector('[data-preview="'+item.driver_id+'"]');if(cell)cell.textContent=item.summary||item.error||'Nicht verfügbar';
   paintDiff(item.driver_id,item.error?null:item.difference_minutes);
   if(item.error){result.insertAdjacentHTML('beforeend','<p class="flash err">'+esc(item.name)+': '+esc(item.error)+'</p>');continue;}
   const panel=document.createElement('details');panel.className='sb-driver-review';panel.dataset.did=item.driver_id;panel.dataset.blocked=item.blocked?'1':'0';
   panel.style.cssText='border:1px solid #d9dee8;border-radius:12px;padding:12px;margin:10px 0;background:#fff';
   let rows='';
   for(const r of item.rows){
    if(!r.editable){rows+='<tr><td>'+esc(r.day)+'</td><td>'+esc(r.original.start)+'–'+esc(r.original.end)+' (Pause '+esc(r.original.break_minutes)+')</td><td colspan="3">Gesperrt / unvollständig – keine Änderung</td></tr>';continue;}
    const prefix='d_'+item.driver_id+'_';
    const field=(name,type,val,orig,minmax)=>'<input data-field="'+name+'" data-original="'+esc(orig)+'" type="'+type+'" name="'+prefix+'sb_'+name+'_'+esc(r.id)+'" value="'+esc(val)+'" '+(minmax||'')+' required aria-label="'+name+' '+esc(r.day)+'">';
    rows+='<tr class="sb-review-shift"><td>'+esc(r.day)+'</td><td>'+esc(r.original.start)+'–'+esc(r.original.end)+' · Pause '+esc(r.original.break_minutes)+'</td>'+
    '<td><input type="hidden" name="'+prefix+'sb_sig_'+esc(r.id)+'" value="'+esc(r.signature)+'"><div style="display:grid;grid-template-columns:1fr 1fr 90px;gap:6px">'+
    field('start','time',r.proposed.start,r.original.start,'')+field('end','time',r.proposed.end,r.original.end,'')+field('pause','number',r.proposed.pause,r.original.break_minutes,'min="0" max="600"')+'</div></td>'+
    '<td class="sb-row-diff">'+esc(r.diff)+'</td><td>'+(r.assumed_break?'<b style="color:#b54708">Pause nur angenommen!</b>':'Prüfen')+'</td></tr>';
   }
   const sourceDiagnostics=(item.diagnostics||[]);
   const diagnosticsText=sourceDiagnostics.length
     ? '<div class="sb-hint"><b>Ursache der ausgeschlossenen oder auffälligen Originalschichten:</b><ul>'+
       sourceDiagnostics.map(x=>'<li>'+esc(x.day)+': '+esc((x.reasons||[]).join('; '))+'</li>').join('')+
       '</ul><small>Eine Lohndifferenz ist kein Beleg für eine tatsächlich andere Arbeitszeit.</small></div>' : '';
   const review=item.day_review;
   // Independent per-day forms are outside the timesheet correction form.
   // The operator can change the dates and real times, and must enter proof.
   if(review&&review.kind&&(review.candidates||[]).length){
    const wrapper=document.createElement('details');wrapper.style.cssText='border:1px solid #d9dee8;padding:12px;margin:10px 0;border-radius:12px';
    const meta=item.ops_metadata||{};
    const field=(name,type,value,extra='')=>'<label>'+esc(name.replaceAll('_',' '))+'<input name="'+name+'" type="'+type+'" value="'+esc(value||'')+'" '+extra+' required></label>';
    const hidden='<input type="hidden" name="csrf_token" value="CSRF"><input type="hidden" name="driver_id" value="'+esc(item.driver_id)+'">'+
      '<input type="hidden" name="year" value="YYYY"><input type="hidden" name="month" value="MM">';
    let cards='';
    (review.candidates||[]).forEach((lead,i)=>{
     const create=review.kind==='check_missing',eid=String(lead.entry_id||'');
     if(!create&&!/^\d{1,20}$/.test(eid))return;
     let fields='';
     if(create){
      if(!lead.draft_start||!lead.draft_end)return;
      fields='<input type="hidden" name="operation" value="create"><div class="grid grid-3">'+
        field('work_day','date',lead.day,'min="YYYY-MM-01" max="MONTHEND"')+
        field('work_start','time',lead.draft_start,'step="900"')+
        field('work_end','time',lead.draft_end,'step="900"')+
        field('work_break','number',lead.draft_break,'min="0" max="90" step="15"')+
        field('work_department_id','number',meta.department_id,'min="1"')+
        field('work_team_id','number',meta.team_id,'min="1"')+
        field('work_shift_id','number',meta.shift_id,'min="1"')+'</div>'+field('work_proof','text','','minlength="15" maxlength="500" placeholder="Originalbeleg, echte Zeiten und Pause"')+
        '<p style="font-size:12px;color:#92400e">Rechnerischer Platzhalter '+esc(lead.minutes)+' Minuten netto. Zeiten und Pausen vor dem Senden anhand des Nachweises ändern.</p>';
     }else{
      fields='<input type="hidden" name="operation" value="decline"><input type="hidden" name="decline_id" value="'+esc(eid)+'">'+
        '<p>Eintrag '+esc(eid)+' · '+esc(lead.day)+' · '+esc(lead.minutes)+' Minuten. '+esc((lead.reasons||[]).join('; '))+'</p>'+
        field('decline_proof','text','','minlength="15" maxlength="500" placeholder="Beweis für Fehler/Duplikat"');
     }
     cards+='<form class="sb-proposed-day" method="post" action="DAYACTION" style="padding:12px;margin:10px 0;background:#f8fbff;border:1px solid #d6e4f2;border-radius:11px">'+
       hidden+'<b>'+esc(create?'Neuer Arbeitstag – Entwurf '+(i+1):'Mögliche Fehlbuchung – prüfen')+'</b>'+fields+
       '<div class="actions"><button type="submit" name="day_submit_mode" value="check">Nur prüfen – nichts senden</button></div>'+
       (item.ops_live?'<label style="display:flex;align-items:center;gap:8px"><input style="width:auto" type="checkbox" name="one_live_write" value="yes">Echten Arbeitsnachweis geprüft – genau diese Aktion freigeben</label>'+
        '<div class="actions"><button class="primary" type="submit" name="day_submit_mode" value="live">Diesen Tag einzeln senden</button></div>':'')+
       '<p class="sb-day-proposal-result" role="status"></p></form>';
    });
    wrapper.innerHTML='<summary style="cursor:pointer;font-weight:800">'+esc(item.name)+' · '+esc(review.candidates.length)+' vorgeschlagene Tagesprüfungen</summary><p>'+esc(review.note||'')+'</p>'+cards;
    dayActions.appendChild(wrapper);
   }
   const reviewText=review&&review.kind
     ? '<div class="sb-hint"><b>Fehlende / überzählige Arbeitstage – unten als kontrollierbare Tagesaktionen:</b> '
       +esc(review.note)+'<p>Orientierungswert: '+esc(review.required_days)+' Tag(e). '
       +(review.candidates||[]).map(x=>esc(x.day)+' ('+esc(Math.floor(x.minutes/60))+':'+String(x.minutes%60).padStart(2,'0')+')').join(', ')
       +'</p><small>Einzelne, editierbare Prüfaufträge stehen weiter unten. '+
       'Originalarbeitszeiten und Krankheit/Urlaub beachten. '+
       'Originalbelege vor jedem Einzelsenden prüfen. '+
       'Diese Tage werden nicht automatisch gesendet.</small></div>' : '';
   panel.innerHTML='<summary style="cursor:pointer;font-weight:800">'+esc(item.name)+' · '+esc(item.summary)+' · <span class="sb-driver-count">0 geänderte Schichten</span></summary>'+
    (item.balance_note?'<p class="sb-fine">'+esc(item.balance_note)+'</p>':'')+
    (item.blocked?'<p class="flash err">'+esc(item.blocked)+'</p>':'')+diagnosticsText+reviewText+
    '<div class="table-wrap" style="margin:10px 0"><table style="min-width:820px"><thead><tr><th>Datum</th><th>Original</th><th>Vorschlag / korrigierbar (Beginn, Ende, Pause)</th><th>Diff.</th><th>Hinweis</th></tr></thead><tbody>'+rows+'</tbody></table></div>'+
    '<input type="hidden" class="sb-driver-send" name="driver_id" value="'+item.driver_id+'" disabled>'+
    '<div class="sb-fine">Rechnerische Vorschläge · vor dem direkten Versand auf tatsächlich geleistete Zeiten prüfen.</div>';
   result.appendChild(panel);
  }
  loaded=true;result.querySelectorAll('input[data-field]').forEach(el=>el.addEventListener('change',recalc));
  result.querySelectorAll('input[data-field]').forEach(el=>el.addEventListener('input',recalc));
  recalc();progress.textContent='Vorschläge für '+data.drivers.length+' Fahrer geladen – es wurde NICHTS an Shiftbase gesendet.';
 }catch(e){progress.textContent='Vorschau fehlgeschlagen: '+e.message;result.innerHTML='';}
 finally{buttons.forEach(x=>x.disabled=false);}
}
readTrafficLights();
root.querySelector('#sb-preview').onclick=()=>load(false);
root.querySelector('#sb-preview-all').onclick=()=>load(true);
root.querySelector('#sb-expand-proposals').onclick=()=>result.querySelectorAll('.sb-driver-review').forEach(x=>x.open=true);
root.querySelector('#sb-collapse-proposals').onclick=()=>result.querySelectorAll('.sb-driver-review').forEach(x=>x.open=false);
reviewForm.addEventListener('submit',e=>{
 recalc();const targets=Array.from(result.querySelectorAll('input.sb-driver-send:not(:disabled)'));
 if(!loaded||!targets.length){
  e.preventDefault();
  progress.textContent=loaded?'Keine veränderbaren Schichtkorrekturen zum Senden vorhanden.':'Bitte zuerst Vorschläge für die gewünschten Fahrer erstellen.';
  return;
 }
 for(const panel of result.querySelectorAll('.sb-driver-review')){
  const selected=Boolean(panel.querySelector('.sb-driver-send:not(:disabled)'));
  for(const row of panel.querySelectorAll('.sb-review-shift')){
   if(!selected||!row.classList.contains('sb-dirty')) row.querySelectorAll('input').forEach(x=>x.disabled=true);
  }
 }
 reviewForm.querySelectorAll('button[type=submit]').forEach(x=>x.disabled=true);
 const submit=document.createElement('input');submit.type='hidden';submit.name='mode';submit.value='start';reviewForm.appendChild(submit);
 const userAction=document.createElement('input');userAction.type='hidden';userAction.name='reviewed_send_action';userAction.value='administrator_clicked_reviewed_times';reviewForm.appendChild(userAction);
});
})();
</script>'''.replaceAll('CSRF',esc(_sb_csrf_token())).replaceAll('YYYY',str(year)).replaceAll('MM',str(month)).replace('BULKPREVIEW',url_for('admin_shiftbase_bulk_preview')).replace('MONTHSTATUS',url_for('admin_shiftbase_month_status'))
       .replaceAll('DAYACTION',url_for('admin_shiftbase_day_operation')).replaceAll('MONTHEND',_sb_month_window(year,month)[1]))
    if recent_runs:
        h.append('<h3>Letzte Übertragungen wieder öffnen</h3><p class="sb-fine">Bei Browserabbruch die bisherige Übertragung über ihren Link fortsetzen. Es werden keine PUTs automatisch wiederholt.</p>')
        for r in recent_runs:
            h.append('<p><a href="'+url_for('admin_shiftbase_transfer_view',run_id=r['id'])+'">'
                     +esc(r['created_at'])+' · Versandauftrag '+esc(r['id'][:8])+' …</a></p>')
    h.append('<p><a href="'+url_for('admin_shiftbase_abgleich',year=year,month=month)+'">Zurück zum einfachen Monatsabgleich</a></p></div></div>')
    return base_page('Shiftbase – alle Fahrer',''.join(h),'shiftbase')


def _sb_bulk_month_snapshot(year, month):
    """Two shared, unmodified Shiftbase collections instead of two per driver.

    Always filter each returned entry by its ACTUAL user/month downstream;
    never trust remote collection filters for ownership.
    """
    start, end = _sb_month_window(year, month)
    times = _shiftbase_get_all('timesheets', {'min_date':start,'max_date':end})
    absences = _shiftbase_get_all('absentees', {'min_date':start,'max_date':end})
    return times, absences


def _sb_bulk_driver_ids(form):
    raw=form.getlist('driver_id')
    if not raw or len(raw)>150 or any(not re.fullmatch(r'[0-9]{1,12}',x) for x in raw):
        raise ShiftbaseIntegrationError('Bitte gültige Fahrer auswählen (maximal 150).')
    ids=[int(x) for x in raw]
    if len(ids)!=len(set(ids)):
        raise ShiftbaseIntegrationError('Fahrer doppelt ausgewählt.')
    with db_conn() as conn:
        mapping=_sb_mapping(conn)
        eligible={r['driver_id'] for r in _sb_local_month(conn, int(form['year']), int(form['month']))
                  if r['driver_id'] in mapping}
    if not set(ids).issubset(eligible):
        raise ShiftbaseIntegrationError('Nur aktive, eindeutig zugeordnete Fahrer sind erlaubt.')
    return ids


@app.post('/admin/shiftbase/transfer/month-status')
@admin_login_required
def admin_shiftbase_month_status():
    """Lightweight READ-ONLY color status for every mapped driver this month.

    One combined Shiftbase GET, no hypothetical time allocation, no PUT.
    Unknown/unreadable months are explicitly neutral, never shown as matching.
    """
    _sb_verified_post_csrf(request.form)
    try:
        year=int(request.form.get('year',0)); month=int(request.form.get('month',0))
        if not 2020 <= year <= 2100 or not 1 <= month <= 12:
            raise ValueError('Ungültiger Monat')
        with db_conn() as conn:
            local=_sb_local_month(conn,year,month)
            mapping=_sb_mapping(conn)
        start,end=_sb_month_window(year,month)
        times=_shiftbase_get_all('timesheets',{'min_date':start,'max_date':end})
        result=[]
        for driver in local:
            did=int(driver['driver_id'])
            if did not in mapping:
                continue
            payroll=driver['payroll_hours']
            record={'driver_id':did,'difference_minutes':None,'summary':'Keine vollständigen Stundenangaben'}
            try:
                rows=_sb_dayview_entries(times,str(mapping[did]),year,month)
                if payroll is None or any(r['hours'] is None for r in rows):
                    record['summary']='Abrechnungs- oder Schichtstunden fehlen – bitte prüfen'
                else:
                    total=sum((Decimal(str(r['hours'])) for r in rows),Decimal('0'))
                    delta=Decimal(str(payroll))-total
                    if not total.is_finite() or total<0 or not delta.is_finite():
                        raise ValueError('Ungültige Stunden')
                    record['difference_minutes']=int((delta*Decimal(60)).quantize(Decimal('1')))
                    record['summary']='Ist '+_sb_dayview_hm(total)+' · Lohn '+_sb_dayview_hm(payroll)+' · Abweichung '+_sb_signed_hm(delta)
            except (ValueError,InvalidOperation,TypeError):
                record['summary']='Shiftbase-Stunden unvollständig – bitte prüfen'
            result.append(record)
        response=make_response(jsonify({'drivers':result,'year':year,'month':month}))
        response.headers['Cache-Control']='private, no-store'
        return response
    except (ValueError,TypeError,ShiftbaseIntegrationError) as exc:
        return jsonify({'error':str(exc)}),422


@app.post('/admin/shiftbase/transfer/bulk-preview')
@admin_login_required
def admin_shiftbase_bulk_preview():
    _sb_verified_post_csrf(request.form)
    neighbor_token = _SB_PREVIEW_NEIGHBORS.set({})
    try:
        year=int(request.form['year']);month=int(request.form['month'])
        if not 2020<=year<=2100 or not 1<=month<=12: raise ValueError('Ungültiger Monat')
        ids=_sb_bulk_driver_ids(request.form)
        snapshot=_sb_bulk_month_snapshot(year,month)
        results=[]
        for did in ids:
            try:
                source=_sb_review_source(did,year,month,month_snapshot=snapshot)
                plan=_sb_hypothetical_preview(source)
                blocked=plan['blocked_reason'] if not plan['days'] else ''
                if source.get('vacation_count') not in ('','0'):
                    blocked=('Urlaubstage sind in der Cloud nur als Anzahl gespeichert. '
                             'Einzelansicht öffnen und belegte Urlaubstage eingeben.')
                rows=[]
                for r in source['rows']:
                    eid=str(r['entry_id']); orig=_sb_review_row_obj(r)
                    suggestion=plan['days'].get(eid)
                    try: sick=int(str(r['day'])[-2:]) in set(_expand_day_ranges(source.get('sick_ranges','')))
                    except ValueError: sick=True
                    editable=not bool(r.get('deleted') or r.get('absence') or sick or
                        orig['break_minutes']=='' or orig['start']=='–' or orig['end']=='–' or
                        str(r.get('status','')).lower() in {'rejected','declined','abgelehnt'})
                    proposed={'start':suggestion['new_start'] if suggestion else orig['start'],
                              'end':suggestion['new_end'] if suggestion else orig['end'],
                              'pause':str(suggestion['new_pause']) if suggestion else orig['break_minutes']}
                    rows.append({'id':eid,'day':str(r['day']),'original':orig,'proposed':proposed,
                                 'editable':editable,'signature':_sb_direct_baseline_signature(did,source['uid'],year,month,eid,orig)
                                 if editable else '',
                                 'diff':_sb_signed_hm(Decimal(suggestion['delta_minutes'])/Decimal(60)) if suggestion else '0:00',
                                 'assumed_break':bool(suggestion and suggestion['assumed_break_change'])})
                diagnostics=_sb_preview_exclusion_diagnostics(source)
                diagnostic_by_id={x['entry_id']:x['reasons'] for x in diagnostics}
                for item in rows:
                    item['source_warnings']=diagnostic_by_id.get(item['id'],[])
                summary=('Ist '+_sb_dayview_hm(source['actual'])+' · Lohn '+
                         (_sb_dayview_hm(source['payroll']) if source['payroll'] is not None else '–')+
                         ' · Vorschläge '+str(len(plan['days']))+
                         ' · Rest '+_sb_signed_hm(plan['unallocated']))
                if plan.get('day_review') and plan['day_review'].get('kind'):
                    summary += (' · '+str(plan['day_review']['required_days'])+
                                ' mögliche Tage nur zur Belegprüfung')
                delta_minutes = int(((source['payroll']-source['actual'])*Decimal(60)).quantize(Decimal('1'))) if source['payroll'] is not None else None
                results.append({'driver_id':did,'name':source['name'],'summary':summary,
                                'difference_minutes':delta_minutes,
                                'blocked':blocked,'rows':rows,
                                'balance_note':plan.get('balance_note',''),
                                'day_review':plan.get('day_review'),
                                'ops_metadata':_sb_day_metadata_defaults(source),
                                'ops_live':bool(_sb_day_ops_experimental_available(source) or
                                   (os.environ.get('SHIFTBASE_TIMESHEET_WRITE_SCHEMA_CONFIRMED','')=='1'
                                    and os.environ.get('SHIFTBASE_VERIFIED_WRITE_ENABLED','')=='1'
                                    and not os.environ.get('SHIFTBASE_MOCK_DIR',''))),
                                'diagnostics':diagnostics})
            except (ShiftbaseIntegrationError,ValueError,TypeError,KeyError) as exc:
                with db_conn() as conn:
                    row=conn.execute('SELECT name FROM drivers WHERE id=?',(did,)).fetchone()
                results.append({'driver_id':did,'name':str(row['name']) if row else str(did),
                                'error':str(exc)})
        response=make_response(jsonify({'drivers':results,'year':year,'month':month}))
        response.headers['Cache-Control']='private, no-store'
        return response
    except (ShiftbaseIntegrationError,ValueError,TypeError,KeyError) as exc:
        return jsonify({'error':str(exc)}),422
    finally:
        _SB_PREVIEW_NEIGHBORS.reset(neighbor_token)


@app.post('/admin/shiftbase/transfer/bulk-review')
@admin_login_required
def admin_shiftbase_bulk_review():
    """Stage admin-submitted, reviewed actual times from multiple drivers in one click.

    Re-fetch the live monthly snapshot, re-run original signed-source and
    rest/break/absence checks independently for each driver. No PUT here.
    All staging occurs in one database transaction or none at all.
    """
    _sb_verified_post_csrf(request.form)
    try:
        year=int(request.form['year']);month=int(request.form['month'])
        if not 2020<=year<=2100 or not 1<=month<=12: raise ValueError('Ungültiger Monat')
        if request.form.get('reviewed_send_action') != 'administrator_clicked_reviewed_times':
            raise ShiftbaseIntegrationError('Bitte die geprüften Zeiten über die Schaltfläche der gemeinsamen Prüfansicht senden.')
        ids=_sb_bulk_driver_ids(request.form)
        mode=str(request.form.get('mode','start'))
        if mode!='start':
            raise ShiftbaseIntegrationError('Die Vormerkfunktion ist abgeschaltet. Bitte direkt senden.')
        snapshot=_sb_bulk_month_snapshot(year,month)
        prepared=[]
        for did in ids:
            prefix='d_'+str(did)+'_'
            subform={key[len(prefix):]:value for key,value in request.form.items() if key.startswith(prefix)}
            subform['confirmed_batch']='actual_work_verified_using_records'
            source=_sb_review_source(did,year,month,month_snapshot=snapshot)
            corrections=_sb_queue_form_certified(source,subform,did,year,month)
            prepared.append((did,source,corrections))
        run_id=_sb_create_transfer_run_direct(prepared,year,month)
        return redirect(url_for('admin_shiftbase_transfer_view',run_id=run_id,autostart=1))
    except (ShiftbaseIntegrationError,ValueError,TypeError,KeyError) as exc:
        return base_page('Shiftbase – gemeinsame Prüfung fehlgeschlagen',
             '<div class="card"><h2>Keine Übertragung gestartet</h2><p>'+shiftbase_escape(str(exc))+
             '</p><p>Es wurden keine ungeprüften Zeitvorschläge gesendet. Bitte korrigieren und neu prüfen.</p>'
             '<a href="'+url_for('admin_shiftbase_transfer_dashboard',year=year if 'year' in locals() else 2026,
                                month=month if 'month' in locals() else 11)+'">Zurück zur Monatsübersicht</a></div>',
             'shiftbase'),422


@app.get('/admin/shiftbase/transfer/preview')
@admin_login_required
def admin_shiftbase_transfer_preview():
    year,month=_sb_params()
    raw=str(request.args.get('driver_id','')).strip()
    if not re.fullmatch(r'[0-9]{1,12}',raw): abort(400)
    try:
        source=_sb_review_source(int(raw),year,month)
        plan=_sb_hypothetical_preview(source)
        result=('Shiftbase '+_sb_dayview_hm(source['actual'])+' · Abrechnung '
                +(_sb_dayview_hm(source['payroll']) if source['payroll'] is not None else '–')
                +' · ungeprüfte Vorschläge '+str(len(plan['days']))
                +' · verbleibend '+_sb_signed_hm(plan['unallocated']))
        return jsonify({'result':result,'proposals':len(plan['days'])})
    except ShiftbaseIntegrationError as exc:
        return jsonify({'error':str(exc)}),422


@app.post('/admin/shiftbase/transfer/start')
@admin_login_required
def admin_shiftbase_transfer_start():
    # Legacy bookmarked endpoint: the separate Vormerken queue was removed.
    _sb_verified_post_csrf(request.form)
    return base_page('Shiftbase – Direktversand',
        '<div class="card"><h2>Bitte die direkte Monatsprüfung verwenden</h2>'
        '<p>Die frühere Vormerkfunktion wurde entfernt. Neue Aufträge werden '
        'nach der Arbeitszeitprüfung direkt mit Fortschrittsanzeige angelegt.</p>'
        '<a href="'+url_for('admin_shiftbase_transfer_dashboard')+'">Zur Monatsübersicht</a></div>',
        'shiftbase'),410


def _sb_verified_post_csrf(form):
    expected=str(session.get('shiftbase_csrf',''))
    provided=str(form.get('csrf_token',''))
    if not expected or not provided or not hmac.compare_digest(expected,provided):
        abort(403,'Sitzung abgelaufen.')


def _sb_run_record(run_id):
    if not re.fullmatch(r'[a-f0-9]{32}',run_id):abort(404)
    with db_conn() as conn:
        run=conn.execute('SELECT * FROM shiftbase_transfer_runs WHERE id=?',(run_id,)).fetchone()
        if not run: abort(404)
        tasks=[dict(t) for t in conn.execute('SELECT * FROM shiftbase_transfer_tasks WHERE run_id=? ORDER BY ordinal',(run_id,)).fetchall()]
    return dict(run),tasks


def _sb_run_state(run_id):
    """Read compact progress without copying every signed timesheet JSON blob."""
    if not re.fullmatch(r'[a-f0-9]{32}',run_id):
        abort(404)
    with db_conn() as conn:
        run=conn.execute('SELECT year,month FROM shiftbase_transfer_runs WHERE id=?',
                         (run_id,)).fetchone()
        if not run:
            abort(404)
        summary=conn.execute("""SELECT COUNT(*) AS total,
            COALESCE(SUM(CASE WHEN state='confirmed' THEN 1 ELSE 0 END),0) AS confirmed
            FROM shiftbase_transfer_tasks WHERE run_id=?""",(run_id,)).fetchone()
        flagged=conn.execute('SELECT message FROM shiftbase_transfer_tasks '
                             'WHERE run_id=? AND state IN (?,?) ORDER BY ordinal LIMIT 1',
                             (run_id,'uncertain','error')).fetchone()
        active=conn.execute('SELECT ordinal,driver_id,timesheet_id,state FROM shiftbase_transfer_tasks '
                            'WHERE run_id=? AND state<>? ORDER BY ordinal LIMIT 1',
                            (run_id,'confirmed')).fetchone()
        recent=conn.execute('SELECT driver_id,timesheet_id,state,message FROM shiftbase_transfer_tasks '
                            'WHERE run_id=? ORDER BY ordinal DESC LIMIT 40',(run_id,)).fetchall()
    total=int(summary['total'] or 0)
    done=int(summary['confirmed'] or 0)
    return {'total':total,'confirmed':done,'finished':active is None and total>0,
            'blocked':bool(flagged),'error':str(flagged['message']) if flagged else '',
            'next':(str(active['ordinal'])+' / '+str(total)+' · Mitarbeiter '+str(active['driver_id'])+
                    ', Schicht '+str(active['timesheet_id'])+' · '+str(active['state'])) if active else 'Alles bestätigt',
            'tasks':[dict(x) for x in reversed(recent)],
            'run_id':run_id,'year':run['year'],'month':run['month']}


@app.get('/admin/shiftbase/transfer/run/<run_id>')
@admin_login_required
def admin_shiftbase_transfer_view(run_id):
    run,tasks=_sb_run_record(run_id)
    csrf=shiftbase_escape(_sb_csrf_token(),quote=True)
    autostart=(request.args.get('autostart')=='1')
    h=['''<style>
.sb-transfer{max-width:950px;margin:auto}.sb-transfer progress{width:100%;height:25px;accent-color:#1665d8}
.sb-transfer .sb-big{font-weight:900;font-size:1.3rem;color:#0f2446;margin:14px 0}
.sb-transfer pre{white-space:pre-wrap;max-height:300px;overflow:auto;border-radius:10px;background:#f4f6fb;padding:12px;font-size:.85rem}
.sb-transfer button{max-width:450px}
</style>''',
       '<div class="sb-transfer"><div class="card"><h2>Shiftbase – überprüfte Korrekturen übertragen</h2>',
       '<p>Beschleunigter Versand: HTTPS-Verbindungen werden wiederverwendet, pro Schicht erfolgen Vorbereitung, PUT und bestätigender GET soweit möglich in einer Browseranfrage. Unabhängige Mitarbeiter können begrenzt parallel übertragen werden; ohne erneuten PUT bei Unsicherheit. Original-GET, genau ein PUT und bestätigender GET bleiben erhalten. Bei Verbindungsabbruch wird <b>kein PUT automatisch wiederholt</b>.</p>',
       '<div id="sb-transfer-label" class="sb-big">Bereit zur Übertragung</div>',
       '<progress id="sb-transfer-progress" value="0" max="'+str(max(len(tasks),1))+'"></progress>',
       '<p id="sb-transfer-current" role="status">'+str(len(tasks))+' geprüfte Schichtkorrektur(en).</p>',
       '<div id="sb-transfer-error" class="flash err" style="display:none"></div>',
       '<button type="button" class="primary" id="sb-transfer-go">Übertragung starten / fortsetzen</button>',
       '<pre id="sb-transfer-details" aria-live="polite"></pre>',
       '<p>Bei einer Unterbrechung diesen Link erneut öffnen. Falls eine PUT-Antwort verloren ging, wird zunächst nur der Stand in Shiftbase überprüft.</p>',
       '<p><a href="'+url_for('admin_shiftbase_transfer_dashboard',year=run['year'],month=run['month'])+'">Zurück zur Fahrerübersicht</a></p>',
       '</div></div>',
       '''<script>
(function(){
const root=document.querySelector('.sb-transfer');
const btn=root.querySelector('#sb-transfer-go');
const bar=root.querySelector('#sb-transfer-progress');
const label=root.querySelector('#sb-transfer-label');
const state=root.querySelector('#sb-transfer-current');
const err=root.querySelector('#sb-transfer-error');
const details=root.querySelector('#sb-transfer-details');
const base='/admin/shiftbase/transfer/run/RUNID';
const token='CSRF';
const shouldAutostart=AUTOSTART;
let running=false;
async function getJSON(url,init){const r=await fetch(url,{credentials:'same-origin',cache:'no-store',...(init||{})}); const j=await r.json();if(!r.ok)throw new Error(j.error||('HTTP '+r.status));return j;}
function paint(j){
bar.max=Math.max(j.total,1);bar.value=j.confirmed;
label.textContent=j.confirmed+' / '+j.total+' Schichten durch GET bestätigt';
state.textContent=j.next;
err.style.display=j.error?'block':'none';err.textContent=j.error||'';
details.textContent=(j.tasks||[]).map(x=>'Fahrer '+x.driver_id+' · Schicht '+x.timesheet_id+': '+x.state+' · '+x.message).join('\\n');
}
async function read(){const j=await getJSON(base+'/status');paint(j);return j;}
async function tick(initialState){
 if(running)return;running=true;btn.disabled=true;
 try{
  // One response per remote operation: POST already returns full progress.
  // The original UI performed an extra GET and 250-ms sleep every time.
  let current=initialState||await read();
  while(!current.finished&&!current.blocked){
   current=await getJSON(base+'/step',{method:'POST',headers:{'Content-Type':'application/x-www-form-urlencoded'},body:'csrf_token='+encodeURIComponent(token)});
   paint(current);
   if(current.finished||current.blocked||current.pause)break;
   // Rare case: another browser tab is currently using the same task.
   if(current.retry_after_ms){await new Promise(resolve=>setTimeout(resolve,current.retry_after_ms));}
  }
 }catch(e){
  err.style.display='block';
  err.textContent='Verbindung unterbrochen: '+e.message+'. Status neu laden; PUT niemals blind wiederholen.';
 }finally{running=false;btn.disabled=false;}
}
btn.addEventListener('click',()=>tick());
read().then(j=>{if(shouldAutostart&&!j.finished&&!j.blocked)tick(j);}).catch(e=>{err.style.display='block';err.textContent='Status kann nicht geladen werden: '+e.message;});
})();
</script>'''.replace('RUNID',run_id).replace('CSRF',csrf).replace('AUTOSTART','true' if autostart else 'false')]
    response=make_response(base_page('Shiftbase – Übertragungsfortschritt',''.join(h),'shiftbase'))
    response.headers['Cache-Control']='private, no-store'
    return response


@app.get('/admin/shiftbase/transfer/run/<run_id>/status')
@admin_login_required
def admin_shiftbase_transfer_status(run_id):
    return jsonify(_sb_run_state(run_id))


def _sb_task_transition(task_id, old, new, message='', payload=None, audit_id=None):
    # Optimistic state transition works for SQLite and PostgreSQL. Exactly one
    # worker can claim a state. No external I/O occurs in a DB transaction.
    with db_conn() as conn:
        query='UPDATE shiftbase_transfer_tasks SET state=?,message=?,updated_at=?'
        args=[new,message,now_iso()]
        if payload is not None:
            query+=',payload_json=?';args.append(json.dumps(payload,ensure_ascii=False))
        if audit_id is not None:
            query+=',audit_id=?';args.append(audit_id)
        query+=' WHERE id=? AND state=? RETURNING id'
        args.extend([task_id,old])
        result=conn.execute(query,tuple(args)).fetchone()
        conn.commit()
    return bool(result)


def _sb_task_context(task):
    with db_conn() as conn:
        data=conn.execute('SELECT source_json FROM shiftbase_transfer_sources WHERE run_id=? AND driver_id=?',
                          (task['run_id'],task['driver_id'])).fetchone()
    if data is None:
        raise ShiftbaseIntegrationError('Gespeicherte Ausgangsdaten fehlen.')
    source=json.loads(data['source_json'])
    if (int(source['driver_id'])!=int(task['driver_id']) or
        str(source['uid'])!=str(task['shiftbase_user_id'])):
        raise ShiftbaseIntegrationError('Gespeicherter Mitarbeiter stimmt nicht überein.')
    _sb_write_access_checked(source)
    before=json.loads(task['baseline_json'])
    after=json.loads(task['target_json'])
    eid=str(task['timesheet_id'])
    if (not re.fullmatch(r'[0-9]{1,20}',eid) or
            str(before.get('day'))!=str(after.get('day')) or
            not str(before['day']).startswith(f"{int(source['year']):04d}-{int(source['month']):02d}-")):
        raise ShiftbaseIntegrationError('Timesheet oder Monat passen nicht zur Prüfung.')
    expected=_sb_direct_baseline_signature(int(task['driver_id']),source['uid'],
                       int(source['year']),int(source['month']),eid,before)
    if not hmac.compare_digest(expected,str(task['signature'])):
        raise ShiftbaseIntegrationError('Signatur der Ausgangswerte ungültig.')
    return source,before,after,eid


def _sb_prepare_task(task):
    source,before,after,eid=_sb_task_context(task)
    net,span,pm=_sb_review_minutes(after['start'],after['end'],str(after['break_minutes']))
    if (net<=0 or after['start']<'06:00' or net>600 or
            (net>540 and pm<45) or (net>360 and pm<30)):
        raise ShiftbaseIntegrationError('Korrigierte Uhrzeit oder Pause verletzt Sicherheitsgrenzen.')
    row=next((r for r in source['rows'] if str(r['entry_id'])==eid),None)
    if row is None or row.get('absence') or row.get('deleted'):
        raise ShiftbaseIntegrationError('Schicht im Ausgangsmonat fehlt oder ist gesperrt.')
    if _sb_review_row_obj(row) != before:
        raise ShiftbaseIntegrationError('Prüfstand stimmt nicht mit der Originalschicht überein.')
    ts=_sb_ts_detail(eid)
    _sb_assert_timesheet_owner(ts,source['uid'],eid)
    if _sb_live_snapshot(ts)!={k:str(v) for k,v in before.items() if k in ('day','start','end','break_minutes')}:
        raise ShiftbaseIntegrationError('Shiftbase-Datensatz wurde inzwischen geändert. Kein PUT.')
    if any(_sb_get(ts,k) is not None for k in ('clocked_in','clocked_out')):
        raise ShiftbaseIntegrationError('Gestempelte Schicht: Korrekturprozess in Shiftbase verwenden.')
    pause=_sb_break_as_minutes(_sb_get(ts,'paid_break'))
    if pause is None or pause!=0:
        raise ShiftbaseIntegrationError('Bezahlte Pause unklar. Kein PUT.')
    complete={**after,'hours':_sb_dayview_hm(Decimal(net)/Decimal(60))}
    # The complete month was checked at stage; cross-month boundaries still
    # require a live neighbor check for the two affected boundary dates.
    _sb_rest_check_before_write(source,eid,complete)
    payload=_sb_update_payload(ts,eid,complete,expected_uid=source['uid'],
                               monthly_entry=source['raw_timesheets'].get(eid))
    return payload,source,before,after,eid


def _sb_fast_dispatch_task(task, read_timeout=8):
    """Advance one task through all available phases, without any PUT retry.

    Each transition is durably committed before the following network action.
    Interruption after marking 'sending' can ONLY lead to GET reconciliation.
    Different employees can be processed independently, but never two tasks
    for the same employee at the same time.
    """
    token=_SB_STEP_READ_TIMEOUT.set(read_timeout)
    try:
        current=dict(task)
        for _ in range(4):
            old=current['state']
            if old in ('confirmed','uncertain','error','sending','checking','preparing'):
                if old in ('sending','checking','preparing') and _sb_task_is_stale(current):
                    _sb_task_dispatch_one(current)
                break
            _sb_task_dispatch_one(current)
            with db_conn() as conn:
                next_row=conn.execute('SELECT * FROM shiftbase_transfer_tasks WHERE id=?',
                                      (task['id'],)).fetchone()
            if not next_row:
                break
            current=dict(next_row)
            # On uncertain network result, the state remains 'sending'. Do
            # not poll it or issue another PUT within the same HTTP request.
            if current['state']==old:
                break
    finally:
        _SB_STEP_READ_TIMEOUT.reset(token)


def _sb_task_is_stale(task, seconds=65):
    """Only recover a supposedly in-flight operation after its timeout window."""
    try:
        changed=datetime.fromisoformat(str(task['updated_at']))
        if changed.tzinfo is None:
            changed=changed.replace(tzinfo=timezone.utc)
        return (datetime.now(timezone.utc)-changed).total_seconds() >= seconds
    except (ValueError,TypeError,KeyError):
        return False


def _sb_task_dispatch_one(task):
    state=task['state']; tid=task['id']; eid=str(task['timesheet_id'])
    if state=='pending':
        if not _sb_task_transition(tid,'pending','preparing','Original wird nachgelesen'):
            return
        try:
            payload,source,before,after,eid=_sb_prepare_task(task)
            # Persist audit intent before any PUT; task is still not sent.
            audit_id=secrets.token_hex(16)
            with db_conn() as conn:
                _sb_put_audit_table(conn)
                conn.execute('INSERT INTO shiftbase_verified_writes'
                             '(id,driver_id,shiftbase_user_id,year,month,timesheet_id,before_json,after_json,proof_ref,reason,written_at,result) '
                             'VALUES(?,?,?,?,?,?,?,?,?,?,?,?)',
                             (audit_id,task['driver_id'],source['uid'],source['year'],source['month'],eid,
                              json.dumps(before,ensure_ascii=False),json.dumps(after,ensure_ascii=False),
                              'Sammelbestätigung geprüfter Istzeiten',
                              'Korrektur vom Administrator nach Arbeitszeitnachweis freigegeben',
                              now_iso(),'Vorbereitet – PUT noch nicht gestartet'))
                conn.commit()
            _sb_task_transition(tid,'preparing','prepared','Original geprüft; bereit für PUT',payload,audit_id)
        except (ShiftbaseIntegrationError,ValueError,TypeError,KeyError) as exc:
            _sb_task_transition(tid,'preparing','error',str(exc))
        return
    if state=='prepared':
        # This state is committed BEFORE the network request. A process death
        # between sending and receiving can never cause an automatic second PUT.
        if not _sb_task_transition(tid,'prepared','sending','PUT möglicherweise unterwegs; noch nicht bestätigt'):
            return
        try:
            _sb_task_context(task)
            status=_sb_put_timesheet(eid,json.loads(task['payload_json']))
            _sb_task_transition(tid,'sending','verifying','PUT HTTP '+str(status)+'; GET-Kontrolle steht aus')
        except (ShiftbaseIntegrationError,ValueError,TypeError) as exc:
            # Keep 'sending'. The next step is a read-only GET, never another PUT.
            with db_conn() as conn:
                conn.execute('UPDATE shiftbase_transfer_tasks SET message=?,updated_at=? WHERE id=? AND state=?',
                             ('PUT-Ergebnis unklar: '+str(exc)+'; zuerst nur GET prüfen',now_iso(),tid,'sending'))
                conn.commit()
        return
    if state=='sending':
        # Another browser tab must not GET while the original PUT is in flight.
        # After a worker loss, reconcile using GET; never send that PUT again.
        if _sb_task_is_stale(task):
            _sb_task_transition(tid,'sending','verifying',
                                'PUT-Antwort unbekannt; nur Shiftbase-GET zur Wiederaufnahme')
        return
    if state in ('sent','verifying'):
        if not _sb_task_transition(tid,state,'checking','Lese Shiftbase erneut – kein PUT'):
            return
        try:
            source,before,after,eid=_sb_task_context(task)
            ts=_sb_ts_detail(eid)
            _sb_assert_timesheet_owner(ts,source['uid'],eid)
            expected={k:str(v) for k,v in after.items() if k in ('day','start','end','break_minutes')}
            observed=_sb_live_snapshot(ts)
            if observed!=expected:
                raise ShiftbaseIntegrationError('GET bestätigt die Zielwerte nicht. Übertragung angehalten; Shiftbase manuell prüfen. Kein erneuter PUT.')
            if _sb_task_transition(tid,'checking','confirmed','PUT durch erneuten GET bestätigt'):
                with db_conn() as conn:
                    if task['audit_id']:
                        conn.execute('UPDATE shiftbase_verified_writes SET result=? WHERE id=?',
                                     ('PUT gesendet – GET bestätigt',task['audit_id']))
                    # Update the worker snapshot after verified GET so all later
                    # rest checks see the already changed preceding shifts.
                    for recorded in source['rows']:
                        if str(recorded['entry_id']) == eid:
                            net,_,_= _sb_review_minutes(after['start'],after['end'],str(after['break_minutes']))
                            recorded['begin']=after['start']
                            recorded['end']=after['end']
                            recorded['break']=str(after['break_minutes'])+' Min.'
                            recorded['hours']=str(Decimal(net)/Decimal(60))
                            break
                    conn.execute('UPDATE shiftbase_transfer_sources SET source_json=? WHERE run_id=? AND driver_id=?',
                                 (json.dumps(source,default=str,ensure_ascii=False),task['run_id'],task['driver_id']))
                    conn.commit()
        except ShiftbaseIntegrationError as exc:
            _sb_task_transition(tid,'checking','uncertain',str(exc))
            if task['audit_id']:
                with db_conn() as conn:
                    conn.execute('UPDATE shiftbase_verified_writes SET result=? WHERE id=?',
                                 ('Unbestätigt: in Shiftbase manuell prüfen',task['audit_id']))
                    conn.commit()
        return
    if state=='checking':
        # Don't interfere with an active GET from another browser tab.
        if _sb_task_is_stale(task):
            _sb_task_transition(tid,'checking','verifying','GET nach Unterbrechung erneut prüfen')
        return
    if state=='preparing':
        # This is read-only preparation; don't race another active request.
        if _sb_task_is_stale(task):
            _sb_task_transition(tid,'preparing','pending','Vorbereitung nach Unterbrechung wiederholen')
        return


@app.post('/admin/shiftbase/transfer/run/<run_id>/step')
@admin_login_required
def admin_shiftbase_transfer_step(run_id):
    _sb_verified_post_csrf(request.form)
    if not re.fullmatch(r'[a-f0-9]{32}',run_id): abort(404)
    with db_conn() as conn:
        run=conn.execute('SELECT id FROM shiftbase_transfer_runs WHERE id=?',(run_id,)).fetchone()
        if not run: abort(404)
        flagged=conn.execute('SELECT id FROM shiftbase_transfer_tasks WHERE run_id=? '
                             'AND state IN (?,?) LIMIT 1',(run_id,'error','uncertain')).fetchone()
        candidates=[dict(r) for r in conn.execute('SELECT * FROM shiftbase_transfer_tasks '
                    'WHERE run_id=? AND state<>? ORDER BY ordinal', (run_id,'confirmed')).fetchall()]
    if not candidates:
        return jsonify(_sb_run_state(run_id))
    if flagged:
        return jsonify(_sb_run_state(run_id))
    try:
        read_timeout=max(3,min(9,int(os.environ.get('SHIFTBASE_STEP_READ_TIMEOUT','8'))))
        workers=max(1,min(3,int(os.environ.get('SHIFTBASE_PARALLEL_WORKERS','2'))))
    except ValueError:
        read_timeout=8;workers=2
    # Only the earliest outstanding task per employee is eligible. This
    # preserves per-employee sequence/rest checks and prevents racing edits.
    chosen=[];seen=set()
    for item in candidates:
        did=int(item['driver_id'])
        if did not in seen:
            seen.add(did)
            chosen.append(item)
            if len(chosen)>=workers:break
    def work(item):
        try:
            _sb_fast_dispatch_task(item,read_timeout)
        except Exception:
            # Do not retry PUT. Current durable state is decisive.
            app.logger.exception('Shiftbase transfer interrupted: run=%s task=%s',run_id,item['id'])
            with db_conn() as conn:
                current=conn.execute('SELECT state FROM shiftbase_transfer_tasks WHERE id=?',
                                     (item['id'],)).fetchone()
                if current and current['state'] in ('pending','prepared','preparing'):
                    conn.execute('UPDATE shiftbase_transfer_tasks SET state=?,message=?,updated_at=? '
                                 'WHERE id=? AND state=?',
                                 ('error','Fehler vor PUT – bitte prüfen.',now_iso(),item['id'],current['state']))
                elif current and current['state'] in ('sending','verifying','checking'):
                    conn.execute('UPDATE shiftbase_transfer_tasks SET message=? WHERE id=?',
                                 ('Vorgang unklar – nur GET-Abgleich oder manuelle Prüfung; kein neuer PUT.',item['id']))
                conn.commit()
    # Bounded concurrency is safe across different Shiftbase user IDs. Never
    # process multiple tasks of the same driver together.
    if len(chosen)>1:
        from concurrent.futures import ThreadPoolExecutor
        with ThreadPoolExecutor(max_workers=len(chosen)) as executor:
            list(executor.map(work,chosen))
    else:
        work(chosen[0])
    result=_sb_run_state(run_id)
    result['pause']=bool(result['blocked'])
    result['retry_after_ms']=(1200 if result.get('next') and 'sending' in result['next'] else 0)
    return jsonify(result)



# ========== Erweiterung: manuell belegte Arbeitstage und Ablehnung ==========
# IMPORTANT: This module does not generate timesheets from payroll differences.
# It requires operator-entered ACTUAL start/end/breaks and an identifiable
# original evidence reference; hypothetical dates are never posted.
# The official Shiftbase UI documents manual addition/decline. Its public
# Stoplight API does not expose a verifiable POST/decline schema without login.
# Thus new API adapters require an additional *explicit* Render opt-in for the
# known flat-field request shape; existing verified PUT remains untouched.

def _sb_day_ops_table(conn):
    conn.execute('''CREATE TABLE IF NOT EXISTS shiftbase_day_operations (
        id TEXT PRIMARY KEY,
        driver_id INTEGER NOT NULL,
        shiftbase_user_id TEXT NOT NULL,
        year INTEGER NOT NULL,
        month INTEGER NOT NULL,
        day TEXT NOT NULL,
        action TEXT NOT NULL,
        timesheet_id TEXT NOT NULL DEFAULT '',
        proposed_json TEXT NOT NULL,
        proof_ref TEXT NOT NULL,
        state TEXT NOT NULL,
        message TEXT NOT NULL,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL
    )''')
    conn.execute('''CREATE INDEX IF NOT EXISTS idx_shiftbase_day_ops
                    ON shiftbase_day_operations(driver_id, day, action, state)''')
    # Serialises simultaneous browser submissions across Render workers.
    conn.execute('''CREATE UNIQUE INDEX IF NOT EXISTS uq_shiftbase_day_ops_intent
                    ON shiftbase_day_operations(driver_id, day, action, timesheet_id)''')
    # Atomic one-shot ticket across Render workers and PostgreSQL connections.
    conn.execute('''CREATE TABLE IF NOT EXISTS shiftbase_day_ops_test_slots (
        shiftbase_user_id TEXT NOT NULL,
        action TEXT NOT NULL,
        operation_id TEXT NOT NULL,
        created_at TEXT NOT NULL,
        PRIMARY KEY (shiftbase_user_id, action)
    )''')


def _sb_day_ops_enabled(action):
    setting = ('SHIFTBASE_TIMESHEET_MANUAL_CREATE_ENABLED' if action == 'create'
               else 'SHIFTBASE_TIMESHEET_MANUAL_DECLINE_ENABLED')
    if os.environ.get(setting, '').strip() != '1':
        raise ShiftbaseIntegrationError(
            'Manuelle Timesheet-'+('Anlage' if action == 'create' else 'Ablehnung')+
            ' ist noch nicht separat freigeschaltet. Bitte den API-Adapter zuerst '
            'mit dem dokumentierten Schema des Shiftbase-Kontos abgleichen ('+setting+').')
    if os.environ.get('SHIFTBASE_TIMESHEET_WRITE_SCHEMA_CONFIRMED', '').strip() != '1':
        raise ShiftbaseIntegrationError(
            'Das neue POST-/Ablehnungsformat wurde für diesen Shiftbase-Account noch '
            'nicht bestätigt. Erst nach API-Schemaabgleich auf Render '
            'SHIFTBASE_TIMESHEET_WRITE_SCHEMA_CONFIRMED=1 setzen.')
    if os.environ.get('SHIFTBASE_MOCK_DIR', '').strip():
        raise ShiftbaseIntegrationError('Keine API-Schreiboperation im Demo-Modus.')


def _sb_day_ops_experimental_available(source):
    """Test one mapped Shiftbase user only, never the full employee population."""
    return (os.environ.get('SHIFTBASE_DAY_OPS_EXPERIMENTAL_LIVE', '').strip() == '1'
            and os.environ.get('SHIFTBASE_VERIFIED_WRITE_ENABLED', '').strip() == '1'
            and re.fullmatch(r'[0-9]{1,20}', str(source.get('uid') or '')) is not None
            and str(source.get('uid')) == os.environ.get('SHIFTBASE_DAY_OPS_TEST_USER_ID', '').strip()
            and not os.environ.get('SHIFTBASE_MOCK_DIR', '').strip())


def _sb_day_ops_execution(form, source, action):
    """Check-only works out of the box. Live writes need explicit one-user opt-in."""
    choice = str(form.get('day_submit_mode', '')).strip()
    if choice not in ('check', 'live'):
        raise ShiftbaseIntegrationError('Bitte zuerst „Nur prüfen“ oder „Echten Einzeltest“ wählen.')
    did = int(source.get('driver_id') or 0)
    uid = str(source.get('uid') or '')
    if did < 1 or not re.fullmatch(r'[0-9]{1,20}', uid):
        raise ShiftbaseIntegrationError('Keine eindeutige Shiftbase-Mitarbeiter-ID.')
    with db_conn() as conn:
        employee = conn.execute('SELECT id,is_active,is_disposition FROM drivers WHERE id=?', (did,)).fetchone()
        mapping = _sb_mapping(conn)
    if not employee or int(employee['is_active']) != 1 or int(employee['is_disposition'] or 0) != 0 \
            or mapping.get(did) != uid or len(set(mapping.values())) != len(mapping):
        raise ShiftbaseIntegrationError('Fahrer nicht eindeutig aktiv mit Shiftbase verknüpft.')
    if choice == 'check':
        return 'check'
    if str(form.get('one_live_write', '')) != 'yes':
        raise ShiftbaseIntegrationError('Für den einmaligen Live-Test zuerst das Kästchen am Formular setzen.')
    # Preserve the same global user mapping/write guard as verified timesheet PUT.
    _sb_write_access_checked(source)
    if _sb_day_ops_experimental_available(source):
        return 'experimental'
    # The existing production flags still work if the account API format was
    # actually verified. Never pretend this is true just to make a trial pass.
    _sb_day_ops_enabled(action)
    return 'verified'


def _sb_day_ops_validate_date(source, raw):
    try:
        day = shiftbase_date.fromisoformat(str(raw).strip())
    except ValueError as exc:
        raise ShiftbaseIntegrationError('Ungültiges Arbeitsdatum (YYYY-MM-DD).') from exc
    if day.year != source['year'] or day.month != source['month']:
        raise ShiftbaseIntegrationError('Datum liegt nicht im ausgewählten Monat.')
    if day > (datetime.now(ZoneInfo('Europe/Berlin')).date() if ZoneInfo else shiftbase_date.today()):
        raise ShiftbaseIntegrationError('Zukünftige tatsächliche Arbeitszeiten dürfen nicht eingetragen werden.')
    return day


def _sb_day_ops_absence_guard(source, day, form=None):
    d = day.isoformat()
    try:
        sick = set(_expand_day_ranges(source.get('sick_ranges', '')))
    except ValueError as exc:
        raise ShiftbaseIntegrationError('Cloud-Krankheitstage sind nicht eindeutig. Keine Anlage.') from exc
    if day.day in sick:
        raise ShiftbaseIntegrationError('Tag ist in der Cloud als krank vermerkt. Keine Anlage.')
    # Cloud stores vacation as a NUMBER, not specific dates. Without a reliable
    # day-by-day record we cannot prove that any selected date is free.
    vacation_count = str(source.get('vacation_count', '')).strip()
    if vacation_count not in ('', '0'):
        entered = str((form or {}).get('urlaubs_tage','')).strip()
        if not entered:
            raise ShiftbaseIntegrationError('Cloud-Urlaub enthält nur eine Tagesanzahl. '
                'Vor einer Anlage alle Urlaubstage aus Originalunterlagen angeben.')
        try:
            known_days = set(_expand_day_ranges(entered))
            count = int(vacation_count)
            if count <= 0 or count > 31 or len(known_days) != count:
                raise ValueError('Die Anzahl der konkreten Urlaubstage stimmt nicht mit der Cloud überein.')
            for n in known_days:
                shiftbase_date(source['year'],source['month'],n)
        except (ValueError,TypeError) as exc:
            raise ShiftbaseIntegrationError('Urlaubstage nicht eindeutig geprüft: '+str(exc)) from exc
        if day.day in known_days:
            raise ShiftbaseIntegrationError('Das Datum ist ein bestätigter Urlaubstag. Keine Anlage.')
    for fr, to, description, status in source.get('absence_ranges', []):
        if fr <= d <= to and str(status).strip().lower() not in ('declined','rejected','abgelehnt'):
            raise ShiftbaseIntegrationError('Shiftbase führt an diesem Tag eine Abwesenheit ('+
                                           str(description)[:60]+'). Keine Anlage.')


def _sb_day_ops_clock_checks(start, end, pause):
    net, duration, pm = _sb_review_minutes(start, end, str(pause))
    if net <= 0 or net > 480:
        raise ShiftbaseIntegrationError('Neue Schicht benötigt 0:15 bis höchstens 8:00 Netto-Arbeitszeit.')
    if net % 15 or pm % 15 or int(start[3:]) % 15 or int(end[3:]) % 15:
        raise ShiftbaseIntegrationError('Beginn, Ende, Netto-Dauer und Pause müssen im 15-Minuten-Takt liegen.')
    if net > 360 and pm < 30:
        raise ShiftbaseIntegrationError('Bei mehr als 6 Stunden sind mindestens 30 Minuten Pause nötig.')
    if net > 540 and pm < 45:
        raise ShiftbaseIntegrationError('Bei mehr als 9 Stunden sind mindestens 45 Minuten Pause nötig.')
    if start < '06:00':
        raise ShiftbaseIntegrationError('Neue Schicht beginnt vor 06:00: bitte individuell prüfen und manuell in Shiftbase erfassen.')
    return net, duration, pm


def _sb_day_ops_neighbor_checks(source, item, net):
    '''One read-only cross-month lookaround + rest/overlap and weekly 48 h gate.'''
    day = shiftbase_date.fromisoformat(item['day'])
    beg = (day-shiftbase_timedelta(days=7)).isoformat()
    finish = (day+shiftbase_timedelta(days=7)).isoformat()
    remote = _shiftbase_get_all('timesheets', {'min_date':beg, 'max_date':finish,
                                                'user_id':source['uid']})
    around=[]
    week_net=net
    week_start=day-shiftbase_timedelta(days=day.weekday())
    week_end=week_start+shiftbase_timedelta(days=6)
    for entry in remote:
        uid, d, hours, eid = _sb_timesheet_parts(entry)
        if uid != source['uid'] or not d or not beg <= d <= finish:
            continue
        ts=_sb_get(entry,'Timesheet')
        if not isinstance(ts,dict): ts=entry
        status=str(_sb_value(ts,'status') or '').lower()
        if status in ('declined','rejected','abgelehnt'):
            continue
        if str(_sb_get(ts,'deleted') or '').strip().lower() in ('1','true','yes'):
            continue
        if d == item['day']:
            raise ShiftbaseIntegrationError('Auf diesem Tag existiert bereits eine Shiftbase-Arbeitsschicht. Kein Duplikat erzeugen.')
        if hours is None:
            raise ShiftbaseIntegrationError('Nachbarschicht ohne auswertbare Stunden: keine sichere Ruhezeit-/Wochenprüfung.')
        if week_start <= shiftbase_date.fromisoformat(d) <= week_end:
            week_net += int((Decimal(hours)*Decimal(60)).quantize(Decimal('1')))
        original = {
            'day':d,
            'start':_sb_dayview_clock(_sb_value(ts,'starttime','start_time')),
            'end':_sb_dayview_clock(_sb_value(ts,'endtime','end_time')),
            'deleted':False,
        }
        around.append(original)
    if week_net > 48*60:
        raise ShiftbaseIntegrationError('Mit diesem Tag würde die konservative 48-Stunden-Wochengrenze überschritten.')
    conflict=_sb_rest_violation(around+[item])
    if conflict:
        raise ShiftbaseIntegrationError('Keine Anlage: '+conflict)


def _sb_day_ops_write_native(method, path, payload):
    '''One HTTP write, never retries; do not trust HTTP 2xx alone.'''
    cfg=_shiftbase_config()
    if cfg['mock_dir']:
        raise ShiftbaseIntegrationError('Schreibzugriff im Demo-Modus gesperrt.')
    if os.environ.get('SHIFTBASE_AUTH_HEADER','Authorization').strip().lower()!='authorization' or \
       os.environ.get('SHIFTBASE_AUTH_PREFIX','API').strip().upper()!='API':
        raise ShiftbaseIntegrationError('Timesheet-Schreibadapter erwartet Authorization: API <token>.')
    raw_token=cfg['token'].strip()
    if raw_token.lower().startswith('api '): raw_token=raw_token[4:].strip()
    if method not in ('POST','PUT') or not (path == '/timesheets' or
        (method=='PUT' and re.fullmatch(r'/timesheets/[0-9]{1,20}',path))):
        raise ShiftbaseIntegrationError('Nicht zugelassener Timesheet-Schreibpfad.')
    headers={'Authorization':'API '+raw_token,
             'Accept':'application/json','Content-Type':'application/json',
             'User-Agent':'PlusMinusCloud-VerifiedDayOperations/1.0'}
    data=json.dumps(payload, ensure_ascii=False, separators=(',',':')).encode('utf-8')
    try:
        status, body=_sb_http_request(method, cfg['base']+path, headers, 20,
                                      payload=data, max_bytes=1_000_000)
    except HTTPError as exc:
        # Show only JSON field names, NEVER error text or raw values (may contain PII).
        keys=''
        try:
            parsed=json.loads(exc.read(4096).decode('utf-8'))
            if isinstance(parsed,dict):
                keys='; Antwortfelder: '+', '.join(sorted(str(k)[:32] for k in parsed.keys())[:8])
        except (ValueError, UnicodeError, OSError):
            pass
        raise ShiftbaseIntegrationError(
            'Shiftbase '+method+' HTTP '+str(exc.code)+keys+'. API-Schreibschema oder '
            'Berechtigung prüfen; keine automatische Wiederholung.') from exc
    except (URLError,OSError,TimeoutError) as exc:
        raise ShiftbaseIntegrationError(
            'Verbindung beim '+method+' unklar. Vor einem neuen Schreibversuch direkt in Shiftbase prüfen.') from exc
    if status not in (200,201,204):
        raise ShiftbaseIntegrationError('Shiftbase '+method+' HTTP '+str(status)+'. Ergebnis nicht bestätigt.')
    if not body.strip():return status,{}
    try:
        result=json.loads(body.decode('utf-8'))
    except (UnicodeError,ValueError) as exc:
        raise ShiftbaseIntegrationError('Shiftbase '+method+' lieferte kein lesbares JSON. Nur GET-Kontrolle.') from exc
    if isinstance(result,dict) and (result.get('success') is False or result.get('ok') is False or result.get('error')):
        raise ShiftbaseIntegrationError('Shiftbase meldet einen API-Anwendungsfehler. Nur GET-Kontrolle.')
    return status,result


def _sb_day_ops_audit_start(source, day, action, proposed, proof, timesheet_id='', experimental=False):
    with db_conn() as conn:
        _sb_day_ops_table(conn)
        rows=conn.execute('''SELECT id,state FROM shiftbase_day_operations
                             WHERE driver_id=? AND day=? AND action=?
                             AND (timesheet_id=? OR action='create')
                             ORDER BY created_at DESC LIMIT 20''',
                          (source['driver_id'],day,action,str(timesheet_id))).fetchall()
        if rows:
            raise ShiftbaseIntegrationError(
                'Für diesen Tag und diese Aktion existiert bereits ein Übertragungsversuch. '
                'Zuerst Shiftbase und das Prüfprotokoll kontrollieren; keine unbemerkte Doppelübertragung.')
        ident=secrets.token_hex(16)
        if experimental:
            # Both SQLite and PostgreSQL enforce this unique one-shot slot
            # atomically, even across simultaneous Render requests/workers.
            conn.execute('''INSERT INTO shiftbase_day_ops_test_slots
                (shiftbase_user_id,action,operation_id,created_at)
                VALUES(?,?,?,?) ON CONFLICT(shiftbase_user_id,action) DO NOTHING''',
                (source['uid'],action,ident,now_iso()))
            slot=conn.execute('''SELECT operation_id FROM shiftbase_day_ops_test_slots
                                 WHERE shiftbase_user_id=? AND action=?''',
                              (source['uid'],action)).fetchone()
            if slot is None or str(slot['operation_id'])!=ident:
                raise ShiftbaseIntegrationError(
                    'Für diese Aktion wurde für die Test-Mitarbeiter-ID bereits ein Live-Test reserviert. '
                    'Vor erneutem Test zuerst Ergebnis und API-Schema auswerten.')
            # Keep previous non-experimental attempts visible as an additional
            # reason to stop rather than blindly repeat an uncertain PUT/POST.
            past=conn.execute('''SELECT id FROM shiftbase_day_operations
                                  WHERE shiftbase_user_id=? AND action=? LIMIT 1''',
                              (source['uid'],action)).fetchone()
            if past:
                raise ShiftbaseIntegrationError('Für diesen Fahrer ist bereits ein Schreibversuch protokolliert.')
        conn.execute('''INSERT INTO shiftbase_day_operations
            (id,driver_id,shiftbase_user_id,year,month,day,action,timesheet_id,
             proposed_json,proof_ref,state,message,created_at,updated_at)
             VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)''',
            (ident,source['driver_id'],source['uid'],source['year'],source['month'],
             day,action,str(timesheet_id),json.dumps(proposed,ensure_ascii=False),
             proof,'sending','Schreibvorgang vorbereitet; Ergebnis noch unbekannt',now_iso(),now_iso()))
        conn.commit()
    return ident


def _sb_day_ops_audit_finish(ident, state, message):
    with db_conn() as conn:
        conn.execute('UPDATE shiftbase_day_operations SET state=?,message=?,updated_at=? WHERE id=?',
                     (state,str(message)[:300],now_iso(),ident))
        conn.commit()


def _sb_day_ops_create(form, source):
    execution=_sb_day_ops_execution(form,source,'create')
    day=_sb_day_ops_validate_date(source,form.get('work_day',''))
    _sb_day_ops_absence_guard(source,day,form)
    if day.weekday()==6:
        raise ShiftbaseIntegrationError('Neue Sonntagsarbeit ist wegen Ersatzruhetag-/Ausnahmeprüfung nur direkt in Shiftbase zu erfassen.')
    start=str(form.get('work_start','')).strip()
    end=str(form.get('work_end','')).strip()
    pause=str(form.get('work_break','')).strip()
    net,span,pm=_sb_day_ops_clock_checks(start,end,pause)
    evidence=str(form.get('work_proof','')).strip()[:500]
    if len(evidence)<15:
        raise ShiftbaseIntegrationError('Für den tatsächlich geleisteten Arbeitstag Beleg/Quelle (mind. 15 Zeichen) eingeben.')
    # Confirm the mapped Shiftbase user exists in the LIVE users collection;
    # never trust a typed or stale mapping alone for a new time record.
    users=_shiftbase_get_all('users')
    matches=[]
    for entry in users:
        embedded=_sb_get(entry,'User')
        uid=(_sb_id(embedded,'id','user_id') if isinstance(embedded,dict) else None)
        uid=uid or _sb_id(entry,'id','user_id','employee_id')
        if uid==source['uid']:
            matches.append(entry)
    if len(matches)!=1:
        raise ShiftbaseIntegrationError('Shiftbase-Benutzer nicht eindeutig im aktuellen Benutzerabruf vorhanden. Kein POST.')
    metadata={}
    for field in ('department_id','team_id','shift_id'):
        value=str(form.get('work_'+field,'')).strip()
        if not re.fullmatch(r'[0-9]{1,20}',value):
            raise ShiftbaseIntegrationError(field+' muss eine gültige Shiftbase-ID aus der Abteilung/Schicht sein.')
        metadata[field]=int(value)
    item={'day':day.isoformat(),'start':start,'end':end,'break_minutes':str(pm),'deleted':False}
    _sb_day_ops_neighbor_checks(source,item,net)
    if execution=='check':
        return ('Vorprüfung bestanden für '+item['day']+' ('+start+'–'+end+
                ', '+str(pm)+' Minuten Pause, '+_sb_dayview_hm(Decimal(net)/Decimal(60))+
                ' netto). Kein POST gesendet und nichts gespeichert. '
                'Das API-Schreibschema selbst wird erst beim ausdrücklich aktivierten Live-Einzeltest geprüft.')
    # Experimental live tests use the unconfirmed candidate request shape;
    # never claim this is an authenticated official schema without a readback.
    # Only the official flat-field Timesheet resource is targeted. This is an
    # opt-in adapter until the account's authenticated Stoplight schema is checked.
    payload={'user_id':int(source['uid']),'date':item['day'],
             'starttime':start+':00','endtime':end+':00','break':str(pm),
             'paid_break':'0','note':evidence[:200],**metadata}
    ident=_sb_day_ops_audit_start(source,item['day'],'create',payload,evidence,
                                  experimental=(execution=='experimental'))
    try:
        _sb_day_ops_write_native('POST','/timesheets',payload)
        # Never resend POST if the acknowledgement/readback is missing.
        updated=_shiftbase_get_all('timesheets',{'min_date':item['day'],
                                                 'max_date':item['day'],
                                                 'user_id':source['uid']})
        found=[]
        for entry in updated:
            uid,date,_,entry_id=_sb_timesheet_parts(entry)
            if uid!=source['uid'] or date!=item['day'] or not entry_id:continue
            ts=_sb_ts_detail(entry_id)
            _sb_assert_timesheet_owner(ts,source['uid'],entry_id)
            if _sb_live_snapshot(ts)=={'day':item['day'],'start':start,'end':end,'break_minutes':str(pm)}:
                found.append(entry_id)
        if len(set(found))!=1:
            raise ShiftbaseIntegrationError('POST-Ausgang nicht eindeutig über GET bestätigt; bitte Schicht direkt in Shiftbase überprüfen.')
    except Exception as exc:
        _sb_day_ops_audit_finish(ident,'uncertain','POST/GET nicht bestätigt – in Shiftbase prüfen')
        if isinstance(exc,ShiftbaseIntegrationError):raise
        raise ShiftbaseIntegrationError('POST oder Rücklesen fehlgeschlagen; keine automatische Wiederholung.') from exc
    _sb_day_ops_audit_finish(ident,'confirmed','POST und GET bestätigt; Timesheet-ID '+str(found[0]))
    return 'Arbeitstag '+item['day']+' in Shiftbase angelegt und per GET bestätigt.'


def _sb_day_ops_decline(form,source):
    execution=_sb_day_ops_execution(form,source,'decline')
    eid=str(form.get('decline_id','')).strip()
    if not re.fullmatch(r'[0-9]{1,20}',eid):
        raise ShiftbaseIntegrationError('Timesheet-ID für Ablehnung ungültig.')
    row=next((r for r in source['rows'] if str(r.get('entry_id'))==eid),None)
    if row is None:
        raise ShiftbaseIntegrationError('Timesheet gehört nicht zur ausgewählten Person und zum Monat.')
    evidence=str(form.get('decline_proof','')).strip()[:500]
    if len(evidence)<15:
        raise ShiftbaseIntegrationError('Für die Fehl- oder Doppelerfassung Beleg/Grund (mind. 15 Zeichen) eingeben.')
    ts=_sb_ts_detail(eid)
    _sb_assert_timesheet_owner(ts,source['uid'],eid)
    original=_sb_live_snapshot(ts)
    if original['day']!=str(row['day']):
        raise ShiftbaseIntegrationError('Timesheet-Datum stimmt nicht mit dem Monatsabruf überein.')
    live_status=str(_sb_get(ts,'status') or row.get('status') or '').strip().lower()
    if live_status in ('declined','rejected','abgelehnt'):
        raise ShiftbaseIntegrationError('Dieser Timesheet-Eintrag wurde bereits abgelehnt.')
    if live_status in ('approved','genehmigt','bestätigt'):
        raise ShiftbaseIntegrationError('Bereits genehmigte Schicht: Ablehnung nur nach gesonderter Prüfung direkt in Shiftbase.')
    if any(_sb_get(ts,k) not in (None,'') for k in ('clocked_in','clocked_out')):
        raise ShiftbaseIntegrationError('Gestempelte Schicht: Ablehnung nur nach Prüfung der Stempelnachweise direkt in Shiftbase.')
    current=_sb_review_row_obj(row)
    if original!={k:current[k] for k in ('day','start','end','break_minutes')}:
        raise ShiftbaseIntegrationError('Originalschicht wurde verändert. Bitte erneut abrufen.')
    payload=_sb_update_payload(ts,eid,original,expected_uid=source['uid'],
                              monthly_entry=source.get('raw_timesheets',{}).get(eid))
    payload['status']='Declined'
    if execution=='check':
        return ('Vorprüfung bestanden für Timesheet '+eid+' vom '+original['day']+
                '. Eintrag gehört zum richtigen Fahrer und hat einen geeigneten Status. '
                'Kein PUT gesendet; der Eintrag bleibt unverändert.')
    ident=_sb_day_ops_audit_start(source,original['day'],'decline',payload,evidence,eid,
                                  experimental=(execution=='experimental'))
    try:
        _sb_day_ops_write_native('PUT','/timesheets/'+eid,payload)
        checked=_sb_ts_detail(eid)
        _sb_assert_timesheet_owner(checked,source['uid'],eid)
        current_status=str(_sb_get(checked,'status') or '').strip().lower()
        if current_status not in ('declined','rejected','abgelehnt'):
            raise ShiftbaseIntegrationError('PUT-Ausgang nicht durch GET bestätigt. Keine Wiederholung; direkt in Shiftbase prüfen.')
        if _sb_live_snapshot(checked)!=original:
            raise ShiftbaseIntegrationError('Ablehnungs-GET zeigt unerwartet veränderte Uhrzeiten; bitte direkt in Shiftbase prüfen.')
    except Exception as exc:
        _sb_day_ops_audit_finish(ident,'uncertain','Statusänderung nicht durch GET bestätigt – manuell prüfen')
        if isinstance(exc,ShiftbaseIntegrationError):raise
        raise ShiftbaseIntegrationError('Ablehnungsversuch unklar; bitte in Shiftbase prüfen.') from exc
    _sb_day_ops_audit_finish(ident,'confirmed','Ablehnung per GET bestätigt')
    return 'Eintrag '+eid+' wurde in Shiftbase abgelehnt und per GET bestätigt (nicht gelöscht).'


@app.post('/admin/shiftbase/arbeitstage/aktion')
@admin_login_required
def admin_shiftbase_day_operation():
    _sb_verified_post_csrf(request.form)
    raw=str(request.form.get('driver_id','')).strip()
    try:
        did=int(raw)
        year=int(str(request.form.get('year','')))
        month=int(str(request.form.get('month','')))
        if not re.fullmatch(r'[0-9]{1,12}',raw) or did<=0 or year<2020 or year>2100 or month<1 or month>12:
            raise ValueError()
    except (ValueError,TypeError):
        abort(400,'Ungültige Mitarbeiter-/Monatsangaben.')
    mode=str(request.form.get('operation','')).strip()
    if mode not in ('create','decline'):
        abort(400,'Unbekannte Aktion.')
    try:
        source=_sb_review_source(did,year,month)
        if mode=='create':
            message=_sb_day_ops_create(request.form,source)
        else:
            message=_sb_day_ops_decline(request.form,source)
        message=('Testprüfung: ' if str(request.form.get('day_submit_mode',''))=='check'
                 else 'Erfolg: ')+message
        if request.accept_mimetypes.best == 'application/json':
            return jsonify({'ok':True,'message':message,'operation':mode})
        session['shiftbase_direct_result']=message
    except ShiftbaseIntegrationError as exc:
        message='Fehler: '+str(exc)
        if request.accept_mimetypes.best == 'application/json':
            return jsonify({'ok':False,'message':message,'operation':mode}),422
        session['shiftbase_direct_result']=message
    return redirect(url_for('admin_shiftbase_pruefvorschau',driver_id=did,year=year,month=month),code=303)



def _sb_day_metadata_defaults(source):
    """Only prefill metadata if every observed entry for this user agrees."""
    defaults = {}
    for key in ('department_id','team_id','shift_id'):
        observed = set()
        for row in source.get('raw_timesheets',{}).values():
            ts = _sb_get(row,'Timesheet')
            if not isinstance(ts,dict): ts = row
            value = _sb_get(ts,key)
            if value is not None and re.fullmatch(r'[0-9]{1,20}',str(value)):
                observed.add(str(value))
        defaults[key] = next(iter(observed)) if len(observed)==1 else ''
    return defaults


def _sb_day_candidate_cards(source, plan, csrf):
    """Standalone EDITABLE forms for hypothetical day leads.

    They do not nest inside the verified existing-timesheet form. Any live
    operation goes through the original individually locked / audited API gate.
    """
    from markupsafe import escape as _escape
    esc = lambda value: str(_escape(str(value if value is not None else '')))
    review = plan.get('day_review') or {}
    if review.get('kind') not in ('check_missing','check_existing'):
        return ''
    candidates = review.get('candidates') or []
    meta = _sb_day_metadata_defaults(source)
    live = (_sb_day_ops_experimental_available(source) or
            (os.environ.get('SHIFTBASE_TIMESHEET_WRITE_SCHEMA_CONFIRMED','')=='1'
             and os.environ.get('SHIFTBASE_VERIFIED_WRITE_ENABLED','')=='1'
             and not os.environ.get('SHIFTBASE_MOCK_DIR','')))
    first,last = _sb_month_window(source['year'],source['month'])
    head = '<input type="hidden" name="csrf_token" value="'+esc(csrf)+'">' + \
           '<input type="hidden" name="driver_id" value="'+esc(source['driver_id'])+'">' + \
           '<input type="hidden" name="year" value="'+esc(source['year'])+'">' + \
           '<input type="hidden" name="month" value="'+esc(source['month'])+'">'
    raw_dates = str(source.get('preview_vacation_days') or '')
    html=['<section class="sb-planned-days" style="margin:18px 0;padding:15px;border:1px solid #d5e2f0;border-radius:15px;background:#f7fbff">',
          '<h3>Arbeitstage aus dem Monatsabgleich – direkt kontrollierbar</h3>',
          '<p><b>Planung, KEINE bestätigte Istzeit:</b> '+esc(review.get('note',''))+'</p>',
          '<p>Jede Karte ist unabhängig bearbeitbar. Daten und Zeiten können vor der Prüfung geändert werden. '
          'Die tatsächlichen Uhrzeiten und Pausen sowie die Belegquelle müssen von dir kontrolliert werden. '
          '<b>Es wird nichts automatisch angelegt oder abgelehnt.</b></p>']
    if not candidates:
        html.append('<p>Kein rechtlich und rechnerisch ausreichend plausibler Tag gefunden. '
                    'Der offene Rest bleibt ungeklärt.</p>')
    for index,lead in enumerate(candidates):
        kind = review['kind']
        eid = str(lead.get('entry_id',''))
        if kind=='check_existing' and not re.fullmatch(r'[0-9]{1,20}',eid):
            continue
        duration = int(lead.get('minutes',0))
        if kind=='check_missing' and not (360<=duration<=480 and duration%15==0):
            continue
        html.append('<form class="sb-proposed-day" method="post" action="'+esc(url_for('admin_shiftbase_day_operation'))+'" '
                    'style="background:white;border:1px solid #cddbeb;padding:12px;border-radius:12px;margin:12px 0">'+head)
        if kind=='check_missing':
            html.append('<h4>Zusätzlichen Tag nach Belegprüfung erfassen – Entwurf '+str(index+1)+'</h4>'
                        '<input type="hidden" name="operation" value="create">')
            if raw_dates:
                html.append('<input type="hidden" name="urlaubs_tage" value="'+esc(raw_dates)+'">')
            html.append('<div class="grid grid-3">'
                        '<label>Datum (änderbar)<input type="date" name="work_day" value="'+esc(lead['day'])+'" min="'+first+'" max="'+last+'" required></label>'
                        '<label>Beginn – nur Platzhalter<input type="time" name="work_start" value="'+esc(lead.get('draft_start','08:00'))+'" step="900" required></label>'
                        '<label>Ende – nur Platzhalter<input type="time" name="work_end" value="'+esc(lead.get('draft_end','16:30'))+'" step="900" required></label>'
                        '<label>Pause (Minuten)<input type="number" name="work_break" value="'+esc(lead.get('draft_break',30))+'" min="0" max="90" step="15" required></label>'
                        '<label>Shiftbase-Abteilungs-ID<input type="number" name="work_department_id" value="'+esc(meta['department_id'])+'" min="1" required></label>'
                        '<label>Shiftbase-Team-ID<input type="number" name="work_team_id" value="'+esc(meta['team_id'])+'" min="1" required></label>'
                        '<label>Shiftbase-Schichtart-ID<input type="number" name="work_shift_id" value="'+esc(meta['shift_id'])+'" min="1" required></label>'
                        '</div><p><b>Rechnerischer Richtwert: '+esc(_sb_dayview_hm(Decimal(duration)/Decimal(60)))+' netto.</b> '
                        '08:00 und die Endzeit sind Platzhalter, keine tatsächlichen Stempelzeiten. '
                        'Nicht über belegte Zeiten hinaus ergänzen.</p>'
                        '<label>Originalnachweis/Quelle (Pflicht)<input type="text" name="work_proof" minlength="15" maxlength="500" '
                        'placeholder="Beleg mit tatsächlichem Arbeitsbeginn, Ende und Pause" required></label>')
        else:
            html.append('<h4>Mögliche Fehlbuchung prüfen – Timesheet '+esc(eid)+'</h4>'
                        '<input type="hidden" name="operation" value="decline">'
                        '<input type="hidden" name="decline_id" value="'+esc(eid)+'">'
                        '<p><b>Originaldatum '+esc(lead['day'])+' · '+esc(_sb_dayview_hm(Decimal(duration)/Decimal(60)))+'</b></p>'
                        + ('<p>Prüfgründe: '+esc('; '.join(lead.get('reasons',[])))+'</p>' if lead.get('reasons') else '')+
                        '<p>Nur ablehnen, wenn genau diese Schicht nachweislich falsch oder doppelt ist. '
                        'Tatsächlich geleistete Arbeitszeit darf nicht wegen einer Lohndifferenz verschwinden.</p>'
                        '<label>Fehler-/Doppelnachweis (Pflicht)<input type="text" name="decline_proof" minlength="15" maxlength="500" '
                        'placeholder="Konkreter Beleg, warum diese Timesheet-ID falsch ist" required></label>')
        html.append('<div class="actions" style="margin-top:10px">'
                    '<button type="submit" name="day_submit_mode" value="check">Nur prüfen – nichts senden</button></div>')
        if live:
            html.append('<label style="margin-top:9px;display:flex;gap:8px;align-items:center">'
                        '<input type="checkbox" name="one_live_write" value="yes" style="width:auto">'
                        'Ich habe die Zeiten bzw. den Fehler mit Originalbelegen geprüft und will genau diesen Eintrag senden.</label>'
                        '<div class="actions"><button type="submit" name="day_submit_mode" value="live" class="primary">'
                        'Diesen geprüften Tag einzeln an Shiftbase senden</button></div>')
        else:
            html.append('<p style="color:#92400e">Live-Anlage/Ablehnung noch nicht freigeschaltet. '
                        'Die Vorprüfung ist sofort nutzbar; der separate experimentelle Einzeltest bleibt wie bisher möglich.</p>')
        html.append('<p class="sb-day-proposal-result" aria-live="polite" style="font-size:13px"></p></form>')
    html.append('</section>')
    return ''.join(html)

_SB_DAY_PROPOSAL_JS = r"""<script>
(function(){
  document.addEventListener('submit',async function(e){
   const form=e.target;if(!form.matches('.sb-proposed-day'))return;
   e.preventDefault();
   if(!form.reportValidity())return;
   const mode=(e.submitter&&e.submitter.value)||'check';
   const data=new FormData(form);data.set('day_submit_mode',mode);
   const output=form.querySelector('.sb-day-proposal-result');
   const buttons=[...form.querySelectorAll('button[type="submit"]')];
   buttons.forEach(b=>b.disabled=true);
   output.textContent='Prüfung läuft …';
   try{
     const response=await fetch(form.action,{method:'POST',body:data,credentials:'same-origin',
       headers:{Accept:'application/json'},cache:'no-store'});
     const answer=await response.json();
     output.textContent=answer.message||'Unbekanntes Ergebnis.';
     output.style.color=response.ok?'#067647':'#b42318';
     if(response.ok&&mode==='live'){
       output.textContent+=' Bitte Monatsdaten neu laden und die Shiftbase-Bestätigung kontrollieren.';
       form.querySelectorAll('input,button').forEach(el=>el.disabled=true);
     }
   }catch(err){output.textContent='Verbindung unterbrochen. Bei Live-Versand NICHT wiederholen, zuerst Shiftbase und Prüfprotokoll kontrollieren.';output.style.color='#b42318';}
   finally{if(mode!=='live')buttons.forEach(b=>b.disabled=false);}
 });
})();
</script>"""

def _sb_day_ops_html(source,csrf):
    '''Explicit operator-entered additions and individual reject controls.'''
    from markupsafe import escape as _escape
    escape=lambda value:str(_escape(str(value if value is not None else '')))
    did=source['driver_id']; year=source['year']; month=source['month']
    action=url_for('admin_shiftbase_day_operation')
    csrf_fields=(''.join('<input type="hidden" name="'+k+'" value="'+escape(v)+'">'
                  for k,v in (('csrf_token',csrf),('driver_id',did),('year',year),('month',month))))
    can_test_live=_sb_day_ops_experimental_available(source)
    # The older full production opt-in remains independent of experimental testing.
    verified_live=(os.environ.get('SHIFTBASE_TIMESHEET_WRITE_SCHEMA_CONFIRMED','')=='1'
                   and not os.environ.get('SHIFTBASE_MOCK_DIR','')
                   and os.environ.get('SHIFTBASE_VERIFIED_WRITE_ENABLED','')=='1')
    show_live=can_test_live or verified_live
    test_buttons=('<button type="submit" name="day_submit_mode" value="check" '
                  'style="width:auto">Nur prüfen (kein Schreiben)</button>')
    live_buttons=('<label style="display:flex;align-items:center;gap:8px;margin:10px 0;font-size:13px">'
                  '<input type="checkbox" name="one_live_write" value="yes" style="width:auto">'
                  'Dieser einzelne Eintrag ist anhand eines Originalbelegs geprüft; ein echter Shiftbase-Schreibversuch ist gewollt.</label>'
                  '<button type="submit" name="day_submit_mode" value="live" '
                  'class="primary" style="width:auto">Echten Einzeltest an Shiftbase senden</button>') if show_live else ''
    metadata_defaults={}
    # Prefill IDs only when every known value in THIS employee/month agrees.
    # The operator still needs to verify the actual department and shift.
    for key in ('department_id','team_id','shift_id'):
        vals=set()
        for entry in source.get('raw_timesheets',{}).values():
            ts=_sb_get(entry,'Timesheet')
            if not isinstance(ts,dict):ts=entry
            value=_sb_get(ts,key)
            if value is not None and re.fullmatch(r'[0-9]{1,20}',str(value)):
                vals.add(str(value))
        metadata_defaults[key]=next(iter(vals)) if len(vals)==1 else ''
    html=['<details class="sb-day-manager"><summary>Freie manuelle Eingabe – nachgewiesenen Tag hinzufügen / Eintrag ablehnen</summary>',
          '<div style="padding:15px">',
          '<p class="sb-muted"><b>Keine automatische Anpassung an Lohnstunden:</b> Neue Tage nur mit tatsächlich belegten Start-/Endzeiten, Pausen, Abteilung, Team und Schichtart. '
          'Bei bestehenden Fehl-/Doppelerfassungen wird ein Eintrag abgelehnt, nicht gelöscht. '
          '„Nur prüfen“ macht keine API-Schreibanfrage. Für genau einen echten Testfahrer ist eine separate '
          'experimentelle Render-Freigabe möglich; POST/PUT sind bis zum erfolgreichen Test nicht als API-kompatibel bestätigt.</p>']
    if can_test_live:
        html.append('<p style="padding:10px;background:#fff4e7;border-radius:9px"><b>Experimenteller Live-Test freigeschaltet '
                    'für Shiftbase-ID '+escape(source['uid'])+'</b>. Nur einen nachgewiesenen Eintrag testen. '
                    'Ein 2xx ist kein Erfolgsbeleg; danach folgt eine GET-Kontrolle.</p>')
    elif not show_live:
        html.append('<p style="padding:10px;background:#eff6ff;border-radius:9px"><b>Sicherer Vorprüfungsmodus:</b> '
                    'Beide Funktionen können ohne Änderung in Shiftbase getestet werden. '
                    'Für einen echten Einzeltest in Render SHIFTBASE_DAY_OPS_EXPERIMENTAL_LIVE=1 '
                    'und SHIFTBASE_DAY_OPS_TEST_USER_ID auf die Shiftbase-ID des gewünschten Testfahrers setzen. '
                    'Der vorhandene globale Schreibschutz bleibt erforderlich.</p>')
    html.append('<h3>Arbeitszeit nachtragen (nur nach Originalbeleg)</h3>')
    html.append('<form method="post" action="'+escape(action)+'" class="grid grid-3" style="align-items:end">'+csrf_fields+
                '<input type="hidden" name="operation" value="create">'+
                '<label>Arbeitstag<input type="date" name="work_day" min="'+str(year)+'-'+str(month).zfill(2)+'-01" max="'+_sb_month_window(year,month)[1]+'" required></label>'+ 
                '<label>Beginn<input type="time" name="work_start" step="900" required></label>'+ 
                '<label>Ende<input type="time" name="work_end" step="900" required></label>'+ 
                '<label>Unbezahlte Pause (Min.)<input type="number" name="work_break" min="0" max="90" step="15" value="30" required></label>'+ 
                '<label>Shiftbase-Abteilungs-ID<input type="number" name="work_department_id" value="'+escape(metadata_defaults['department_id'])+'" min="1" step="1" required></label>'+ 
                '<label>Shiftbase-Team-ID<input type="number" name="work_team_id" value="'+escape(metadata_defaults['team_id'])+'" min="1" step="1" required></label>'+ 
                '<label>Shiftbase-Schichtart-ID<input type="number" name="work_shift_id" value="'+escape(metadata_defaults['shift_id'])+'" min="1" step="1" required></label>'+ 
                '<label style="grid-column:span 2">Originalnachweis und Begründung<input type="text" name="work_proof" minlength="15" maxlength="500" placeholder="z.B. Talex-Bericht 14.10., Fahrtendienst tatsächlich geleistet" required></label>'+ 
                '<div style="grid-column:1/-1;display:flex;gap:10px;flex-wrap:wrap;align-items:center">'+test_buttons+'</div>'+ 
                ('<div style="grid-column:1/-1">'+live_buttons+'</div>' if show_live else '')+'</form>')
    html.append('<h3 style="margin-top:25px">Falsche / doppelte Schicht ablehnen</h3>')
    html.append('<p class="sb-muted">Nur bei belegter Fehl- oder Doppelerfassung; bereits genehmigte oder gestempelte Istzeiten nicht ohne vorherige Klärung ablehnen.</p>')
    for row in source['rows']:
        if row.get('deleted') or str(row.get('status','')).lower() in ('declined','rejected','abgelehnt'):
            continue
        eid=str(row.get('entry_id',''))
        if not re.fullmatch(r'[0-9]{1,20}',eid):continue
        html.append('<form method="post" action="'+escape(action)+'" style="display:flex;gap:8px;align-items:center;flex-wrap:wrap;margin:8px 0;padding:9px;border:1px solid #dce3ec;border-radius:9px">'+
                    csrf_fields+'<input type="hidden" name="operation" value="decline"><input type="hidden" name="decline_id" value="'+escape(eid)+'">'+
                    '<strong>'+escape(row['day'])+'</strong><span>'+escape(row.get('begin',''))+'–'+escape(row.get('end',''))+' · ID '+escape(eid)+'</span>'+ 
                    '<input type="text" style="min-width:250px;flex:1" name="decline_proof" minlength="15" maxlength="500" placeholder="Fehlernachweis / Ablehnungsgrund (mind. 15 Zeichen)" required>'+ 
                    '<div style="display:flex;gap:9px;flex-wrap:wrap;align-items:center">'+test_buttons+'</div>'+ 
                    ('<div style="width:100%">'+live_buttons+'</div>' if show_live else '')+'</form>')
    with db_conn() as conn:
        _sb_day_ops_table(conn)
        history=conn.execute('''SELECT day, action, state, message, updated_at FROM shiftbase_day_operations
                                WHERE driver_id=? AND year=? AND month=? ORDER BY created_at DESC LIMIT 12''',
                             (did,year,month)).fetchall()
    if history:
        html.append('<details><summary>Prüfprotokoll der letzten Anlage-/Ablehnungsversuche</summary><ul style="padding:14px">')
        for operation in history:
            html.append('<li>'+escape(operation['day'])+' · '+escape(operation['action'])+' · <b>'+
                        escape(operation['state'])+'</b> · '+escape(operation['message'])+'</li>')
        html.append('</ul></details>')
    html.append('<p class="sb-muted">Experimenteller Test (ein Fahrer): '
                'SHIFTBASE_DAY_OPS_EXPERIMENTAL_LIVE=1 und SHIFTBASE_DAY_OPS_TEST_USER_ID=&lt;Shiftbase-ID&gt;. '
                'Die vorhandene SHIFTBASE_VERIFIED_WRITE_ENABLED- und Benutzerfreigabe bleiben Pflicht. '
                'SHIFTBASE_TIMESHEET_WRITE_SCHEMA_CONFIRMED muss für den experimentellen Test NICHT auf 1 gesetzt werden. '
                'Einmalversuch ohne automatischen Retry und mit GET-Nachkontrolle; bestehende Korrekturen unverändert.</p></div></details>')
    return ''.join(html)


# ========== Vertrauliche DATEV-Lohnzettel: Einzelseiten und sichere Zuordnung ==========
# Hinweis: Die Shiftbase Public API dokumentiert keinen bestaetigten Upload fuer
# persoenliche Mitarbeiterdateien. Deshalb KEIN automatischer API-Upload an einen
# geratenen Endpoint. Dateien werden nur nach Admin-Pruefung privat ausgegeben.
# Eine globale Firmen-Datei darf NIE verwendet werden (fuer alle sichtbar).
import hashlib as _sbpay_hashlib
import shutil as _sbpay_shutil
import unicodedata as _sbpay_unicodedata
from markupsafe import escape as _sbpay_escape
try:
    from pypdf import PdfWriter as _SbpayWriter
except Exception:
    _SbpayWriter = None

_SBPAY_MONTHS = {
    'januar': 1, 'februar': 2, 'maerz': 3, 'marz': 3, 'märz': 3, 'märz': 3,
    'april': 4, 'mai': 5, 'juni': 6, 'juli': 7, 'august': 8,
    'september': 9, 'oktober': 10, 'november': 11, 'dezember': 12,
}
_SBPAY_ROOT = DATA_ROOT / 'private_shiftbase_payroll'


def _sbpay_secure_dir(directory):
    directory.mkdir(mode=0o700, parents=True, exist_ok=True)
    try:
        os.chmod(directory, 0o700)
    except OSError:
        pass


def _sbpay_norm(name):
    text = _sbpay_unicodedata.normalize('NFKD', str(name or '').casefold())
    text = ''.join(ch for ch in text if not _sbpay_unicodedata.combining(ch))
    text = text.replace('ß', 'ss')
    return re.sub(r'[^a-z0-9]+', ' ', text).strip()


def _sbpay_period(text):
    # Recognize the official DATEV heading; do not derive it from the upload name.
    m = re.search(r'\bf[uü]r\s+(Januar|Februar|M[aä]rz|April|Mai|Juni|Juli|August|September|Oktober|November|Dezember)\s+(20\d{2})\b',
                  text, re.I)
    if not m:
        return None
    month_key = _sbpay_norm(m.group(1)).replace(' ', '')
    return (int(m.group(2)), _SBPAY_MONTHS.get(month_key))


def _sbpay_identity(text, layout_text=None):
    """Find one unambiguous DATEV recipient and payroll personnel number.

    A DATEV PDF's reading order can differ across pypdf versions and PDF
    producers. In some files the recipient, postal code and *Pers.-Nr.* are
    concatenated; in others they are separate layout lines. Both variants
    must identify the SAME person, otherwise fail closed. In particular,
    neither the employer's address nor a fuzzy name match is accepted.
    """
    texts = [str(text or '')]
    if layout_text and layout_text not in texts:
        texts.append(str(layout_text))

    personal_numbers = set()
    for body in texts:
        # The starred field identifies the RECIPIENT, not the personnel
        # numbers in other areas of the payroll statement.
        personal_numbers.update(re.findall(
            r'\*\s*Pers\s*\.?\s*[-–]?\s*Nr\s*\.?\s*(\d{1,10})\s*\*', body, re.I))
    if len(personal_numbers) != 1:
        return '', ''

    candidates = set()
    for body in texts:
        lines = body.splitlines()
        for line in lines:
            if not re.search(r'\*\s*Pers\s*\.?\s*[-–]?\s*Nr\s*\.', line, re.I):
                continue
            # DATEV's compact extraction combines recipient+ZIP+address
            # before the *Pers.-Nr.* marker on a single line.
            marker = re.search(r'\*\s*Pers\s*\.?\s*[-–]?\s*Nr\s*\.', line, re.I)
            prefix = line[:marker.start()]
            prefix = re.split(r'B\s*/\s*N\s*$', prefix, maxsplit=1, flags=re.I)[0]
            match = re.match(r'^\s*([^\d\n]{4,110}?)(?=\d{5}\b)', prefix)
            if match:
                candidate = ' '.join(match.group(1).split())
                if _sbpay_recipient_name_ok(candidate):
                    candidates.add(candidate)

        # DATEV's spatial layout instead has the recipient/address block
        # *below* the personal-number field, usually: NAME, STREET, ZIP CITY.
        # Require all three lines to avoid mistaking the employer, headings,
        # pay types, or other people for the recipient.
        marker_indices = [i for i, line in enumerate(lines)
                          if re.search(r'\*\s*Pers\s*\.?\s*[-–]?\s*Nr\s*\.', line, re.I)]
        for marker_i in marker_indices:
            stop = min(len(lines), marker_i + 45)
            for i in range(marker_i + 1, stop - 2):
                first = lines[i].strip()
                if re.search(r'^(Brutto[ -]Bez[uü]ge|Lohnart\b)', first, re.I):
                    break
                second = lines[i+1].strip()
                third = lines[i+2].strip()
                if (re.match(r'^\d{5}\s+\S', third) and
                        re.search(r'\d', second) and
                        not re.search(r'\b(B/N|Hinweise|Pers[. -]*Nr)\b', second, re.I) and
                        _sbpay_recipient_name_ok(first)):
                    candidates.add(' '.join(first.split()))

    # Accept formatting differences, but never two different identities.
    normalized = {_sbpay_norm(value) for value in candidates}
    if len(normalized) != 1:
        return '', ''
    # Prefer a clean layout name; both methods must have agreed above.
    chosen = min(candidates, key=lambda v: (len(v), v))
    return chosen, next(iter(personal_numbers))


def _sbpay_recipient_name_ok(candidate):
    value = ' '.join(str(candidate or '').split())
    words = value.split()
    if not 2 <= len(words) <= 7 or not 4 <= len(value) <= 95:
        return False
    if re.search(r'[\d@*/:=<>]', value):
        return False
    if re.search(r'\b(Taxiunternehmen|Abrechnung|Gesamt|Hinweise|Bezeichnungen|Personal|Kirchensteuer)\b', value, re.I):
        return False
    # Accept accented, hyphenated and apostrophized names, but no address or
    # alphanumeric pay codes. This is not a similarity-based match.
    return all(re.fullmatch(r"[^\W\d_][^\d@*/:=<>]*", word, re.UNICODE) is not None
               for word in words)


def _sbpay_identity_from_page(page):
    """Use one identical fail-closed parser for import, previews and sends."""
    raw = page.extract_text() or ''
    name, number = _sbpay_identity(raw)
    if name and number:
        return name, number
    try:
        layout = page.extract_text(extraction_mode='layout') or ''
    except (TypeError, ValueError, NotImplementedError):
        layout = ''
    return _sbpay_identity(raw, layout)


def _sbpay_schema(conn):
    conn.execute('''CREATE TABLE IF NOT EXISTS shiftbase_payroll_batches (
        id TEXT PRIMARY KEY, year INTEGER NOT NULL, month INTEGER NOT NULL,
        page_count INTEGER NOT NULL, source_sha256 TEXT NOT NULL UNIQUE,
        created_at TEXT NOT NULL)''')
    conn.execute('''CREATE TABLE IF NOT EXISTS shiftbase_payroll_pages (
        batch_id TEXT NOT NULL, page_no INTEGER NOT NULL,
        employee_name TEXT NOT NULL, personal_no TEXT NOT NULL,
        source_pages TEXT NOT NULL, file_pages INTEGER NOT NULL,
        driver_id INTEGER, shiftbase_user_id TEXT NOT NULL DEFAULT '',
        match_type TEXT NOT NULL DEFAULT 'blocked',
        approved INTEGER NOT NULL DEFAULT 0, approved_at TEXT,
        relative_path TEXT NOT NULL, page_sha256 TEXT NOT NULL,
        PRIMARY KEY(batch_id, page_no))''')


def _sbpay_token_check():
    _sb_verified_post_csrf(request.form)


def _sbpay_drivers(conn):
    _sb_ensure_mapping_table(conn)
    return [dict(r) for r in conn.execute('''
        SELECT d.id, d.name, m.shiftbase_user_id
        FROM drivers d JOIN shiftbase_driver_map m ON d.id=m.driver_id
        WHERE d.is_active=1 AND COALESCE(d.is_disposition,0)=0
        ORDER BY d.name COLLATE NOCASE
    ''').fetchall()]


def _sbpay_matching(name, number, drivers, other_names, other_numbers):
    # Name alone never suffices without a valid DATEV personal number and
    # uniqueness of this recipient across all pages in the batch.
    if not name or not number or other_numbers[number] != 1 or other_names[_sbpay_norm(name)] != 1:
        return None
    found = [r for r in drivers if _sbpay_norm(r['name']) == _sbpay_norm(name)]
    return found[0] if len(found) == 1 else None


def _sbpay_no_cache(response):
    response.headers['Cache-Control'] = 'private, no-store, max-age=0'
    response.headers['Pragma'] = 'no-cache'
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['X-Robots-Tag'] = 'noindex, nofollow'
    response.headers['Referrer-Policy'] = 'no-referrer'
    return response


@app.route('/admin/shiftbase/lohnzettel', methods=['GET', 'POST'])
@admin_login_required
def admin_shiftbase_payroll():
    # Import a DATEV batch, split exactly one recipient per PDF, no Shiftbase write.
    if request.method == 'POST':
        _sbpay_token_check()
        upload = request.files.get('payroll_pdf')
        if not upload or not str(upload.filename or '').lower().endswith('.pdf'):
            abort(400, 'Bitte eine PDF-Datei auswählen.')
        content = upload.stream.read(50 * 1024 * 1024 + 1)
        if len(content) > 50 * 1024 * 1024 or not content.startswith(b'%PDF-'):
            abort(400, 'Nur eine PDF bis 50 MB ist zulässig.')
        if PdfReader is None or _SbpayWriter is None:
            abort(503, 'Die PDF-Bibliothek pypdf fehlt auf Render. Bitte requirements.txt ergänzen.')
        try:
            source = PdfReader(io.BytesIO(content), strict=True)
            if source.is_encrypted:
                raise ValueError('Passwortgeschützte PDFs werden nicht automatisch verarbeitet.')
            if not 1 <= len(source.pages) <= 300:
                raise ValueError('Der Import muss 1 bis 300 Seiten enthalten.')
            details = []
            for index, page in enumerate(source.pages):
                extracted = page.extract_text() or ''
                name, number = _sbpay_identity_from_page(page)
                period = _sbpay_period(extracted)
                if not period or None in period:
                    raise ValueError(f'Abrechnungsmonat auf Seite {index + 1} nicht eindeutig erkannt.')
                if period != _sbpay_period(source.pages[0].extract_text() or ''):
                    raise ValueError('Verschiedene Abrechnungsmonate in einer Datei.')
                if not name or not number:
                    raise ValueError(f'Seite {index + 1}: Empfänger und DATEV-Personalnummer konnten nicht sicher gelesen werden. Bitte die originale Text-PDF statt eines Scans verwenden; nichts wurde importiert.')
                writer = _SbpayWriter()
                writer.add_page(page)
                buffer = io.BytesIO()
                writer.write(buffer)
                individual = buffer.getvalue()
                test_reader = PdfReader(io.BytesIO(individual), strict=True)
                test_name, test_no = _sbpay_identity_from_page(test_reader.pages[0])
                if len(test_reader.pages) != 1 or test_name != name or test_no != number:
                    raise ValueError(f'Der isolierte Einzelseiten-Test für Seite {index + 1} ist fehlgeschlagen.')
                if len(individual) > 5 * 1024 * 1024:
                    raise ValueError(f'Seite {index+1} ist größer als die 5-MB-Grenze von Shiftbase.')
                details.append((name, number, individual))
            # A payroll recipient can occupy several consecutive DATEV pages.
            # Group every page belonging to that verified personal number into
            # a SINGLE file; do not drop follow-up pages with back-pay details.
            from collections import OrderedDict as _sbpay_ordered
            people = _sbpay_ordered()
            for idx, (name, number, _single) in enumerate(details, start=1):
                found = people.get(number)
                if found:
                    if _sbpay_norm(found['name']) != _sbpay_norm(name):
                        raise ValueError('Eine Personalnummer erscheint mit unterschiedlichen Namen. Import gestoppt.')
                    found['source_pages'].append(idx)
                else:
                    people[number]={'name':name, 'source_pages':[idx]}
            grouped=[]
            for number, data in people.items():
                writer=_SbpayWriter()
                for original_idx in data['source_pages']:
                    writer.add_page(source.pages[original_idx - 1])
                group_stream=io.BytesIO()
                writer.write(group_stream)
                merged=group_stream.getvalue()
                proof=PdfReader(io.BytesIO(merged),strict=True)
                if len(proof.pages)!=len(data['source_pages']):
                    raise ValueError('Mehrseitiger Lohnzettel wurde unvollständig zusammengeführt.')
                for pg in proof.pages:
                    check_name,check_number=_sbpay_identity_from_page(pg)
                    if check_number != number or _sbpay_norm(check_name) != _sbpay_norm(data['name']):
                        raise ValueError('Mehrseitiger Lohnzettel enthält fremde Mitarbeiterdaten.')
                if len(merged) > 5 * 1024 * 1024:
                    raise ValueError('Eine vollständige Mitarbeiter-PDF ist größer als 5 MB.')
                grouped.append((data['name'], number, merged, data['source_pages']))
            details=grouped
        except Exception as exc:
            # No PDF contents, personal details, or tokens are shown in errors.
            msg = str(exc) if isinstance(exc, ValueError) else 'Die PDF konnte nicht zuverlässig gelesen werden.'
            flash(msg if len(msg) < 180 else 'Die PDF enthält nicht unterstützte Seiten.', 'err')
            return redirect(url_for('admin_shiftbase_payroll'))
        digest = _sbpay_hashlib.sha256(content).hexdigest()
        with db_conn() as conn:
            _sbpay_schema(conn)
            previous = conn.execute('SELECT id FROM shiftbase_payroll_batches WHERE source_sha256=?',
                                    (digest,)).fetchone()
        if previous:
            try:
                verified, blocked = _sbpay_prepare_batch_checked(previous['id'])
                flash(f'Bekannte PDF geoeffnet: {verified} Empfaenger versandbereit, {blocked} gesperrt.', 'ok')
            except Exception:
                flash('Bekannte PDF geoeffnet. Shiftbase-Abgleich aktuell nicht erreichbar; bei Bedarf unten erneut pruefen.', 'err')
            return redirect(url_for('admin_shiftbase_payroll_batch', batch_id=previous['id']))
        from collections import Counter as _sbpay_counter
        from secrets import token_hex as _sbpay_token_hex
        names = _sbpay_counter(_sbpay_norm(d[0]) for d in details)
        numbers = _sbpay_counter(d[1] for d in details)
        batch_id = _sbpay_token_hex(16)
        parent = _SBPAY_ROOT / batch_id
        _sbpay_secure_dir(parent)
        try:
            with db_conn() as conn:
                _sbpay_schema(conn)
                drivers = _sbpay_drivers(conn)
                year, month = _sbpay_period(source.pages[0].extract_text() or '')
                conn.execute('INSERT INTO shiftbase_payroll_batches '
                             '(id, year, month, page_count, source_sha256, created_at) VALUES(?,?,?,?,?,?)',
                             (batch_id, year, month, len(source.pages), digest, now_iso()))
                for name, number, data, source_pages in details:
                    page_no = source_pages[0]
                    path = parent / f'blatt_{page_no:03d}.pdf'
                    with open(path, 'xb') as f:
                        os.chmod(path, 0o600)
                        f.write(data)
                    driver = _sbpay_matching(name, number, drivers, names, numbers)
                    matched = bool(driver)
                    relative_path = f'{batch_id}/blatt_{page_no:03d}.pdf'
                    conn.execute('''INSERT INTO shiftbase_payroll_pages
                        (batch_id,page_no,employee_name,personal_no,source_pages,file_pages,
                         driver_id,shiftbase_user_id,match_type,approved,relative_path,page_sha256)
                        VALUES(?,?,?,?,?,?,?,?,?,?,?,?)''',
                        (batch_id, page_no, name, number, json.dumps(source_pages), len(source_pages),
                         int(driver['id']) if matched else None,
                         str(driver['shiftbase_user_id']) if matched else '',
                         'exact' if matched else 'blocked', 0, relative_path,
                         _sbpay_hashlib.sha256(data).hexdigest()))
                conn.commit()
        except Exception:
            _sbpay_shutil.rmtree(parent, ignore_errors=True)
            raise
        try:
            verified, blocked = _sbpay_prepare_batch_checked(batch_id)
            flash(f'{len(details)} Einzelabrechnungen aus {len(source.pages)} Seiten erstellt. '
                  f'{verified} eindeutig zugeordnet und auswählbar, {blocked} gesperrt. Noch nichts gesendet.', 'ok')
        except Exception:
            flash(f'{len(details)} Einzelabrechnungen aus {len(source.pages)} Seiten erstellt. '
                  'Der automatische Shiftbase-Abgleich war nicht erreichbar. '
                  'Nichts versendet; Zuordnungen koennen erneut geprueft werden.', 'err')
        return redirect(url_for('admin_shiftbase_payroll_batch', batch_id=batch_id))

    with db_conn() as conn:
        _sbpay_schema(conn)
        batches = conn.execute('SELECT id,year,month,page_count,created_at FROM shiftbase_payroll_batches '
                               'ORDER BY created_at DESC LIMIT 15').fetchall()
    token = str(_sbpay_escape(_sb_csrf_token()))
    h = ['<div class="card" style="max-width:1150px"><h2>Lohnzettel in Shiftbase hochladen</h2>',
         '<p>Gesamt-PDF aus DATEV hochladen. Die Cloud trennt alle Mitarbeiterabrechnungen, '
         'findet die passenden Shiftbase-IDs und zeigt dir danach eine einzige Liste zum Auswaehlen und Senden.</p>',
         '<p class="muted" style="font-size:13px">Nur eindeutig abgeglichene Mitarbeiter sind auswaehlbar. '
         'Keine Datei wird vor deinem Klick auf "Ausgewaehlte senden" uebertragen.</p>',
         '<form method="post" enctype="multipart/form-data" class="actions" style="align-items:end">',
         '<input type="hidden" name="csrf_token" value="'+token+'">',
         '<label style="max-width:550px">DATEV-Lohnabrechnung (PDF)'
         '<input type="file" name="payroll_pdf" accept="application/pdf,.pdf" required></label>',
         '<button class="primary" style="width:auto">PDF hochladen und Empfaenger erkennen</button></form>',
         '<p class="muted" style="font-size:13px">Der ursprüngliche Gesamtbeleg wird nicht gespeichert. '
         'Die Einzeldateien liegen getrennt vom öffentlichen Webverzeichnis in einem geschützten '
         'Datenordner. Für Render sollte ein persistentes, nur administrativ zugängliches Volume verwendet werden.</p></div>',
         '<div class="card" style="max-width:1150px"><h2>Bereits eingelesene Abrechnungen</h2>']
    if batches:
        h.append('<div class="table-wrap"><table style="min-width:650px"><thead><tr>'
                 '<th>Monat</th><th>Seiten</th><th>Import</th><th>Aktion</th></tr></thead><tbody>')
        for row in batches:
            link = url_for('admin_shiftbase_payroll_batch',batch_id=row['id'])
            h.append('<tr><td>'+str(row['month']).zfill(2)+'/'+str(row['year'])+'</td><td>'+str(row['page_count'])+'</td>'
                     '<td>'+str(_sbpay_escape(row['created_at']))+'</td><td><a href="'+link+'">Empfaenger anzeigen</a></td></tr>')
        h.append('</tbody></table></div>')
    else:
        h.append('<p class="muted">Noch keine PDF importiert.</p>')
    h.append('</div>')
    return _sbpay_no_cache(make_response(base_page('Lohnzettel für Shiftbase', ''.join(h), 'shiftbase_payroll')))


def _sbpay_batch_data(conn, batch_id):
    if not re.fullmatch(r'[a-f0-9]{32}', batch_id or ''):
        abort(404)
    _sbpay_schema(conn)
    batch = conn.execute('SELECT * FROM shiftbase_payroll_batches WHERE id=?',(batch_id,)).fetchone()
    if not batch:
        abort(404)
    entries = conn.execute('SELECT * FROM shiftbase_payroll_pages WHERE batch_id=? ORDER BY page_no',(batch_id,)).fetchall()
    return batch, entries



def _sbpay_prepare_batch_checked(batch_id):
    """Read-only identity check after import. Returns (verified, blocked).

    No browser upload is started here; it only approves exact local matches
    after a fresh official Shiftbase user-list read. Ambiguities fail closed.
    """
    from collections import Counter as _C
    with db_conn() as conn:
        _, rows = _sbpay_batch_data(conn, batch_id)
        drivers = _sbpay_drivers(conn)
        mapped = {int(d['id']): d for d in drivers}
        pdf_names = _C(_sbpay_norm(r['employee_name']) for r in rows)
        pdf_numbers = _C(str(r['personal_no']) for r in rows)
    users = _sbpay_cached_users(force=True)
    profile_pairs = []
    for item in users:
        profile = _sb_get(item, 'User')
        if not isinstance(profile, dict):
            profile = item
        profile_pairs.append((_sb_id(profile, 'id', 'user_id'),
                              _sbpay_norm(_sb_user_display(profile))))
    uid_counts = _C(uid for uid, name in profile_pairs if uid)
    name_counts = _C(name for uid, name in profile_pairs if name)
    user_pairs = set(profile_pairs)
    passed = 0
    blocked = 0
    with db_conn() as conn:
        _sbpay_livecheck_schema(conn)
        _, rows = _sbpay_batch_data(conn, batch_id)
        for row in rows:
            page_no = int(row['page_no'])
            employee_name = _sbpay_norm(row['employee_name'])
            personal_no = str(row['personal_no'])
            did = int(row['driver_id']) if row['driver_id'] else 0
            driver = mapped.get(did)
            uid = str(row['shiftbase_user_id'] or '')
            exact = (row['match_type'] == 'exact' and driver is not None and
                     _sbpay_norm(driver['name']) == employee_name)
            # Manual review is respected but never accepted on a name mismatch
            # in the current Shiftbase user directory.
            reviewed = bool(row['approved']) or exact
            ok = (reviewed and driver is not None and
                  uid == str(driver['shiftbase_user_id']) and
                  re.fullmatch(r'[0-9]{1,20}', uid) is not None and
                  pdf_names[employee_name] == 1 and
                  pdf_numbers[personal_no] == 1 and
                  uid_counts[uid] == 1 and name_counts[employee_name] == 1 and
                  (uid, employee_name) in user_pairs)
            if ok and exact and not row['approved']:
                conn.execute("""UPDATE shiftbase_payroll_pages
                  SET approved=1, approved_at=? WHERE batch_id=? AND page_no=?""",
                  (now_iso(), batch_id, page_no))
            passed += int(ok)
            blocked += int(not ok)
            conn.execute("""INSERT INTO shiftbase_payroll_livechecks
              (batch_id,page_no,shiftbase_user_id,page_sha256,status,checked_at)
              VALUES(?,?,?,?,?,?) ON CONFLICT(batch_id,page_no) DO UPDATE SET
                shiftbase_user_id=excluded.shiftbase_user_id,
                page_sha256=excluded.page_sha256,
                status=excluded.status,checked_at=excluded.checked_at""",
                (batch_id, page_no, uid, row['page_sha256'],
                 'verified' if ok else 'blocked', now_iso()))
        conn.commit()
    return passed, blocked


@app.post('/admin/shiftbase/lohnzettel/<batch_id>/prepare')
@admin_login_required
def admin_shiftbase_payroll_prepare(batch_id):
    """Optional recheck if Shiftbase was unavailable during upload."""
    _sbpay_token_check()
    try:
        passed, blocked = _sbpay_prepare_batch_checked(batch_id)
    except Exception:
        flash('Shiftbase-Benutzerliste derzeit nicht erreichbar. Nichts freigegeben oder gesendet.', 'err')
        return redirect(url_for('admin_shiftbase_payroll_batch', batch_id=batch_id))
    flash(f'{passed} eindeutig zugeordnet, {blocked} gesperrt. Noch nichts hochgeladen.', 'ok')
    return redirect(url_for('admin_shiftbase_payroll_batch', batch_id=batch_id))


@app.get('/admin/shiftbase/lohnzettel/<batch_id>')
@admin_login_required
def admin_shiftbase_payroll_batch(batch_id):
    """One clear admin flow: inspect recognized PDFs, select recipients, send."""
    with db_conn() as conn:
        batch, rows = _sbpay_batch_data(conn, batch_id)
        drivers = _sbpay_drivers(conn)
        _sbpay_delivery_schema(conn)
        _sbpay_livecheck_schema(conn)
        history = {int(r['page_no']): dict(r) for r in conn.execute(
            'SELECT * FROM shiftbase_payroll_deliveries WHERE batch_id=?',
            (batch_id,)).fetchall()}
        checked = {int(r['page_no']): dict(r) for r in conn.execute(
            'SELECT * FROM shiftbase_payroll_livechecks WHERE batch_id=?',
            (batch_id,)).fetchall()}
    mapping = {int(d['id']): d for d in drivers}
    from collections import Counter as _sbpay_count
    mapped_ids = _sbpay_count(int(r['driver_id']) for r in rows if r['driver_id'])
    pay_names = _sbpay_count(_sbpay_norm(r['employee_name']) for r in rows)
    pay_numbers = _sbpay_count(str(r['personal_no']) for r in rows)
    can_upload = _sbpay_upload_contract() is not None
    items = []
    ready_count = blocked_count = finished_count = unclear_count = 0
    for row in rows:
        number = int(row['page_no'])
        did = int(row['driver_id']) if row['driver_id'] else 0
        driver = mapping.get(did)
        correct = bool(driver and str(driver['shiftbase_user_id']) == str(row['shiftbase_user_id'])
                       and (row['match_type'] != 'exact' or
                            _sbpay_norm(driver['name']) == _sbpay_norm(row['employee_name'])))
        proof = checked.get(number, {})
        unique = (mapped_ids[did] == 1 and
                  pay_names[_sbpay_norm(row['employee_name'])] == 1 and
                  pay_numbers[str(row['personal_no'])] == 1)
        verified = (bool(row['approved']) and correct and unique and
                    proof.get('status') == 'verified' and
                    proof.get('shiftbase_user_id') == str(row['shiftbase_user_id']) and
                    proof.get('page_sha256') == row['page_sha256'])
        delivery = history.get(number, {})
        state = delivery.get('state', '')
        eligible = bool(verified and not state)
        if eligible:
            ready_count += 1
            status, color = 'Bereit', '#e8f8ef'
        elif state == 'confirmed':
            finished_count += 1
            status, color = 'Uebertragung bestaetigt', '#e8f8ef'
        elif state == 'observed_ui':
            finished_count += 1
            status, color = 'Im Mitarbeiterprofil gesehen', '#e8f8ef'
        elif state:
            unclear_count += 1
            status, color = 'Ergebnis pruefen – nicht erneut senden', '#fff0ed'
        else:
            blocked_count += 1
            status, color = ('Noch nicht mit Shiftbase abgeglichen' if correct and unique
                             else 'Zuordnung unklar – gesperrt'), '#fff7e8'
        items.append((row, driver if correct else None, eligible, status, color))
    token = str(_sbpay_escape(_sb_csrf_token()))
    period = f'{int(batch["month"]):02d}/{int(batch["year"])}'
    h = ['<div class="card" style="max-width:1320px">',
         '<h2>Lohnzettel '+period+' – Mitarbeiter auswaehlen und senden</h2>',
         '<p>Die Gesamt-PDF wurde automatisch in getrennte Mitarbeiterabrechnungen aufgeteilt. '
         'Waehle alle oder einzelne gruen markierte Mitarbeiter aus und klicke auf <b>Ausgewaehlte PDFs senden</b>. '
         'Unklare Zuordnungen sind aus Sicherheitsgruenden nicht auswaehlbar.</p>',
         '<div class="grid grid-4" style="margin:15px 0">',
         '<div class="kpi">Originalseiten<b>'+str(batch['page_count'])+'</b></div>',
         '<div class="kpi">Einzel-PDFs<b>'+str(len(rows))+'</b></div>',
         '<div class="kpi">Bereit<b>'+str(ready_count)+'</b></div>',
         '<div class="kpi">Versendet / pruefen<b>'+str(finished_count)+' / '+str(unclear_count)+'</b></div>',
         '</div>']
    if not can_upload:
        h.append('<div class="flash err"><b>Shiftbase-Upload noch nicht einsatzbereit.</b> '
                 'Bitte die gueltige Browser-Sitzung und Playwright/Chromium auf Render einrichten. '
                 'Die Einzel-PDFs koennen geprueft werden; es wird nichts gesendet.</div>')
    if blocked_count:
        h.append('<div class="muted" style="margin-bottom:12px">'+str(blocked_count)+' nicht versandbereite '
                 'Abrechnungen bleiben gesperrt. <form method="post" '
                 'style="display:inline" action="'+url_for('admin_shiftbase_payroll_prepare',batch_id=batch_id)+'">'
                 '<input type="hidden" name="csrf_token" value="'+token+'">'
                 '<button type="submit" class="btn small" style="width:auto">Zuordnungen erneut pruefen</button>'
                 '</form></div>')
    h.append('<div class="actions" style="margin-bottom:12px;gap:8px">'
             '<button type="button" id="sbpay-all" style="width:auto">Alle Versandbereiten auswaehlen</button>'
             '<button type="button" id="sbpay-none" style="width:auto">Auswahl aufheben</button>'
             '<button type="button" class="primary" id="sbpay-send" '
             + ('disabled ' if not can_upload or not ready_count else '')
             + 'style="width:auto">Ausgewaehlte PDFs senden (0)</button></div>')
    h.append('<div style="margin:12px 0;padding:12px;background:#f6f9ff;border:1px solid #d8e5f8;border-radius:12px">'
             '<div style="font-size:13px;font-weight:750">Fortschritt</div>'
             '<progress id="sbpay-meter" max="1" value="0" style="width:100%;height:19px"></progress>'
             '<p id="sbpay-progress" role="status" aria-live="polite" '
             'style="margin:4px 0;color:#344054">Noch kein Versand gestartet.</p></div>')
    h.append('<label style="max-width:460px">Mitarbeiter suchen'
             '<input id="sbpay-find" type="search" placeholder="Name oder Personalnummer" autocomplete="off">'
             '</label>')
    h.append('<div class="table-wrap"><table id="sbpay-table" style="min-width:800px">'
             '<thead><tr><th style="width:75px">Auswahl</th><th>Mitarbeiter / erkannte PDF</th>'
             '<th>Shiftbase-Zuordnung</th><th>PDF</th><th>Status</th><th>Unklar?</th>'
             '</tr></thead><tbody>')
    for row, driver, eligible, status, color in items:
        page_no = int(row['page_no'])
        display_name = str(_sbpay_escape(row['employee_name']))
        source_pages = ', '.join(str(int(p)) for p in json.loads(row['source_pages']))
        target = (str(_sbpay_escape(driver['name']))+'<small style="display:block;color:#667085">ID '
                  +str(_sbpay_escape(row['shiftbase_user_id']))+'</small>') if driver else 'Nicht eindeutig'
        url = url_for('admin_shiftbase_payroll_pdf',batch_id=batch_id,page_no=page_no)
        checkbox = ('<input type="checkbox" class="sbpay-choice" value="'+str(page_no)+'" '
                    'aria-label="'+display_name+' zum Senden auswaehlen" '
                    'style="width:20px;height:20px"'+('' if eligible and can_upload else ' disabled')+'>')
        preview = ('<a class="btn small" target="_blank" rel="noopener noreferrer" '
                   'href="'+url+'">PDF ansehen ('+str(int(row['file_pages']))+' S.)</a>')
        manual = ''
        if not eligible and not history.get(page_no):
            manual = ['<details><summary>Zuordnung korrigieren</summary>',
                      '<form method="post" action="'+url_for('admin_shiftbase_payroll_assign',batch_id=batch_id,page_no=page_no)+'">',
                      '<input type="hidden" name="csrf_token" value="'+token+'">',
                      '<select name="driver_id" required><option value="">Fahrer waehlen</option>']
            for candidate in drivers:
                selected = ' selected' if int(candidate['id']) == int(row['driver_id'] or 0) else ''
                manual.append('<option value="'+str(candidate['id'])+'"'+selected+'>'+str(_sbpay_escape(candidate['name']))
                              +' · ID '+str(_sbpay_escape(candidate['shiftbase_user_id']))+'</option>')
            manual.extend(['</select><label style="font-size:12px">PDF-Namen eingeben'
                           '<input name="confirmed_pdf_name" autocomplete="off" required></label>',
                           '<label style="display:flex;gap:6px;align-items:center;font-size:12px">'
                           '<input type="checkbox" name="identity_confirmed" value="yes" required style="width:auto">'
                           'Identitaet anhand der Personalunterlagen geprueft</label>',
                           '<button style="width:auto">Zuordnung speichern</button></form></details>'])
            manual = ''.join(manual)
        h.append('<tr style="background:'+color+'" data-page="'+str(page_no)+'">'
                 '<td>'+checkbox+'</td><td><b>'+display_name+'</b>'
                 '<small style="display:block;color:#667085">Personal-Nr. '+str(_sbpay_escape(row['personal_no']))
                 +' · Originalseiten '+str(_sbpay_escape(source_pages))+'</small></td>'
                 '<td>'+target+'</td><td>'+preview+'</td>'
                 '<td class="sbpay-status"><b>'+str(_sbpay_escape(status))+'</b></td>'
                 '<td>'+manual+'</td></tr>')
    h.append('</tbody></table></div>')
    h.append(_sbpay_simple_send_script(batch_id, token))
    h.append('<p class="muted" style="font-size:12px;margin-top:12px">'
             'Es werden nur die ausgewaehlten, eindeutig verifizierten Mitarbeiter-PDFs '
             'in die jeweilige persoenliche Shiftbase-Dateiablage hochgeladen. '
             'Bei einem unklaren Ergebnis wird der Versand angehalten; kein automatischer Neuversand.</p>')
    h.append('<a class="btn small" href="'+url_for('admin_shiftbase_payroll')+'">Weitere PDF hochladen</a></div>')
    return _sbpay_no_cache(make_response(base_page('Lohnzettel auswaehlen und senden',''.join(h),'shiftbase_payroll')))


@app.post('/admin/shiftbase/lohnzettel/<batch_id>/resync')
@admin_login_required
def admin_shiftbase_payroll_resync(batch_id):
    _sbpay_token_check()
    from collections import Counter as _C
    with db_conn() as conn:
        _, rows = _sbpay_batch_data(conn,batch_id)
        drivers = _sbpay_drivers(conn)
        names = _C(_sbpay_norm(r['employee_name']) for r in rows)
        numbers = _C(r['personal_no'] for r in rows)
        # Do not overwrite a manually reviewed or already approved decision.
        reserved={int(r['driver_id']) for r in rows if r['driver_id'] and (r['approved'] or r['match_type']=='manual')}
        updated=0
        for r in rows:
            if r['approved'] or r['match_type']=='manual':
                continue
            match=_sbpay_matching(r['employee_name'],r['personal_no'],drivers,names,numbers)
            if match and int(match['id']) not in reserved:
                conn.execute('''UPDATE shiftbase_payroll_pages SET
                    driver_id=?,shiftbase_user_id=?,match_type='exact',approved=0,approved_at=NULL
                    WHERE batch_id=? AND page_no=?''',
                    (int(match['id']),str(match['shiftbase_user_id']),batch_id,r['page_no']))
                reserved.add(int(match['id']))
                updated+=1
            else:
                conn.execute('''UPDATE shiftbase_payroll_pages SET
                    driver_id=NULL,shiftbase_user_id='',match_type='blocked',approved=0,approved_at=NULL
                    WHERE batch_id=? AND page_no=?''', (batch_id,r['page_no']))
        conn.commit()
    flash(f'{updated} eindeutige Zuordnungen aktualisiert. Zur Freigabe bitte prüfen.', 'ok')
    return redirect(url_for('admin_shiftbase_payroll_batch',batch_id=batch_id))


@app.post('/admin/shiftbase/lohnzettel/<batch_id>/approve-exact')
@admin_login_required
def admin_shiftbase_payroll_approve_exact(batch_id):
    _sbpay_token_check()
    if request.form.get('reviewed_all') != 'yes':
        abort(400, 'Bitte erst die Namen und IDs prüfen.')
    with db_conn() as conn:
        batch, rows = _sbpay_batch_data(conn, batch_id)
        drivers = _sbpay_drivers(conn)
        mapped={int(x['id']):x for x in drivers}
        from collections import Counter as _C
        names=_C(_sbpay_norm(x['employee_name']) for x in rows)
        nums=_C(x['personal_no'] for x in rows)
        updated=0
        for row in rows:
            if row['match_type']!='exact' or row['driver_id'] not in mapped:
                continue
            drv=mapped[row['driver_id']]
            if (str(drv['shiftbase_user_id']) != row['shiftbase_user_id'] or
                    _sbpay_norm(drv['name']) != _sbpay_norm(row['employee_name']) or
                    names[_sbpay_norm(row['employee_name'])] != 1 or nums[row['personal_no']] != 1):
                continue
            conn.execute('UPDATE shiftbase_payroll_pages SET approved=1,approved_at=? WHERE batch_id=? AND page_no=?',
                         (now_iso(), batch_id, row['page_no']))
            updated+=1
        conn.commit()
    flash(f'{updated} eindeutige Einzelseiten zur Ausgabe freigegeben. Kein Upload an Shiftbase.', 'ok')
    return redirect(url_for('admin_shiftbase_payroll_batch',batch_id=batch_id))


@app.post('/admin/shiftbase/lohnzettel/<batch_id>/assign/<int:page_no>')
@admin_login_required
def admin_shiftbase_payroll_assign(batch_id, page_no):
    _sbpay_token_check()
    try:
        driver_id=int(request.form.get('driver_id') or '0')
    except ValueError:
        abort(400)
    if request.form.get('identity_confirmed') != 'yes':
        abort(400, 'Identitätsbestätigung fehlt.')
    with db_conn() as conn:
        batch, rows = _sbpay_batch_data(conn,batch_id)
        row=next((x for x in rows if int(x['page_no'])==page_no),None)
        if not row:
            abort(404)
        if not _sbpay_norm(row['employee_name']) or not row['personal_no']:
            abort(409, 'Mitarbeiter-Identität unvollständig.')
        if _sbpay_norm(request.form.get('confirmed_pdf_name')) != _sbpay_norm(row['employee_name']):
            abort(400, 'Der eingegebene Name stimmt nicht mit der PDF überein.')
        drivers={int(x['id']):x for x in _sbpay_drivers(conn)}
        target=drivers.get(driver_id)
        if not target or not re.fullmatch(r'[0-9]{1,20}',str(target['shiftbase_user_id'])):
            abort(400, 'Nur aktiv zugeordnete Shiftbase-Fahrer können ausgewählt werden.')
        used=conn.execute('SELECT page_no FROM shiftbase_payroll_pages WHERE batch_id=? AND driver_id=? AND page_no<>?',
                          (batch_id,driver_id,page_no)).fetchone()
        if used:
            abort(409, 'Ein anderer Lohnzettel ist diesem Fahrer bereits zugeordnet.')
        conn.execute('''UPDATE shiftbase_payroll_pages
            SET driver_id=?,shiftbase_user_id=?,match_type='manual',approved=1,approved_at=?
            WHERE batch_id=? AND page_no=?''',
            (driver_id,str(target['shiftbase_user_id']),now_iso(),batch_id,page_no))
        conn.commit()
    flash('Einzelne, manuell überprüfte Zuordnung freigegeben. Noch nichts an Shiftbase gesendet.', 'ok')
    return redirect(url_for('admin_shiftbase_payroll_batch',batch_id=batch_id))


@app.get('/admin/shiftbase/lohnzettel/<batch_id>/blatt/<int:page_no>')
@admin_login_required
def admin_shiftbase_payroll_pdf(batch_id, page_no):
    with db_conn() as conn:
        batch, rows = _sbpay_batch_data(conn,batch_id)
        row=next((x for x in rows if int(x['page_no'])==page_no),None)
        if row is None:
            abort(404)
        # Preview is admin-only. Download is additionally blocked until
        # explicit approval, and revokes if current Shiftbase mapping changes.
        if request.args.get('download') == '1':
            mapping = _sb_mapping(conn)
            if not row['approved'] or not row['driver_id'] or mapping.get(int(row['driver_id'])) != row['shiftbase_user_id']:
                abort(403, 'Empfänger muss vor dem Download erneut geprüft werden.')
            other=conn.execute('SELECT page_no FROM shiftbase_payroll_pages WHERE batch_id=? AND driver_id=? AND page_no<>?',
                               (batch_id,int(row['driver_id']),page_no)).fetchone()
            if other:
                abort(403, 'Mehrdeutige Fahrerzuordnung.')
    expected = f'{batch_id}/blatt_{page_no:03d}.pdf'
    if row['relative_path'] != expected:
        abort(403)
    path = _SBPAY_ROOT / expected
    if not path.is_file() or path.is_symlink():
        abort(404)
    try:
        content=path.read_bytes()
        if _sbpay_hashlib.sha256(content).hexdigest()!=row['page_sha256']:
            abort(409, 'Das Einzelblatt wurde seit dem Import verändert.')
        reader=PdfReader(io.BytesIO(content),strict=True)
        if reader.is_encrypted or len(reader.pages)!=int(row['file_pages']):
            abort(409, 'Die Anzahl der Mitarbeiterseiten ist nicht korrekt.')
        for page in reader.pages:
            actual_name,actual_number=_sbpay_identity_from_page(page)
            if actual_name!=row['employee_name'] or actual_number!=row['personal_no']:
                abort(409, 'Eine Mitarbeiterseite enthält einen abweichenden Empfänger.')
    except (OSError, ValueError) as exc:
        abort(409, 'Die Einzelseite kann nicht sicher verifiziert werden.')
    download=request.args.get('download')=='1'
    filename=secure_filename('Lohnabrechnung_'+str(batch['year'])+'_'+str(batch['month']).zfill(2)+'_PersNr_'+str(row['personal_no'])+'_'+str(row['employee_name'])+'.pdf')
    response=send_file(io.BytesIO(content),mimetype='application/pdf',as_attachment=download,
                       download_name=filename if download else f'Pruefblatt_{page_no:03d}.pdf',
                       max_age=0)
    return _sbpay_no_cache(response)

# --- Sichere persoenliche Lohnzettel-Zustellung (strikt empfaengergebunden) ---
# Die oeffentliche Shiftbase-API dokumentiert am 16.11.2026 keinen verifizierten
# Personalakten-Upload. Ohne ausdruecklich vorgegebenen, verifizierten API-Vertrag
# bleibt jeder automatische Versand absichtlich gesperrt. Nie Firmen-Dateien nutzen.
import uuid as _sbpay_uuid


def _sbpay_delivery_schema(conn):
    conn.execute('''CREATE TABLE IF NOT EXISTS shiftbase_payroll_deliveries (
        batch_id TEXT NOT NULL, page_no INTEGER NOT NULL,
        attempt_id TEXT NOT NULL UNIQUE, driver_id INTEGER NOT NULL,
        shiftbase_user_id TEXT NOT NULL, page_sha256 TEXT NOT NULL,
        state TEXT NOT NULL, document_id TEXT NOT NULL DEFAULT '',
        started_at TEXT NOT NULL, updated_at TEXT NOT NULL,
        PRIMARY KEY (batch_id, page_no))''')


def _sbpay_upload_contract():
    """Return only a completely configured and explicitly confirmed contract.

    The upload endpoint is intentionally NOT guessed. Settings are permitted only
    through Render environment variables. Paths stay under the existing Shiftbase
    API host and must contain the verified recipient's ID as a whole path segment.
    """
    if os.environ.get('SHIFTBASE_PERSONAL_FILE_UPLOAD_ENABLED', '0').strip() != '1':
        return _sbpay_browser_contract()
    if os.environ.get('SHIFTBASE_PERSONAL_FILE_SCHEMA_VERIFIED', '0').strip() != '1':
        return _sbpay_browser_contract()
    names = {
        'post': 'SHIFTBASE_PERSONAL_FILE_POST_PATH',
        'get': 'SHIFTBASE_PERSONAL_FILE_VERIFY_PATH',
        'file': 'SHIFTBASE_PERSONAL_FILE_FIELD',
        'title': 'SHIFTBASE_PERSONAL_FILE_TITLE_FIELD',
        'visible': 'SHIFTBASE_PERSONAL_FILE_VISIBLE_FIELD',
        'response_doc': 'SHIFTBASE_PERSONAL_FILE_RESPONSE_DOC_KEY',
        'response_owner': 'SHIFTBASE_PERSONAL_FILE_RESPONSE_OWNER_KEY',
        'verify_doc': 'SHIFTBASE_PERSONAL_FILE_VERIFY_DOC_KEY',
        'verify_owner': 'SHIFTBASE_PERSONAL_FILE_VERIFY_OWNER_KEY',
        'verify_visible': 'SHIFTBASE_PERSONAL_FILE_VERIFY_VISIBLE_KEY',
    }
    result = {k: os.environ.get(v, '').strip() for k, v in names.items()}
    if not all(result.values()):
        return None
    for key in ('post','get'):
        path = result[key]
        if (not path.startswith('/') or path.startswith('//') or
                '?' in path or '#' in path or '\\' in path or
                '..' in path or '://' in path or
                '{user_id}' not in path):
            return None
        if key == 'get' and '{file_id}' not in path:
            return None
        if key == 'post' and '{file_id}' in path:
            return None
        if not re.search(r'(?<=/)\{user_id\}(?=/|$)', path):
            return None
        if key == 'get' and not re.search(r'(?<=/)\{file_id\}(?=/|$)',path):
            return None
    for key in ('file', 'title', 'visible'):
        if not re.fullmatch(r'[A-Za-z_][A-Za-z_0-9]{0,60}',result[key]):
            return None
    for key in ('response_doc','response_owner','verify_doc','verify_owner','verify_visible'):
        if not re.fullmatch(r'[a-zA-Z_][a-zA-Z_0-9]*(?:\.[a-zA-Z_][a-zA-Z_0-9]*){0,3}',result[key]):
            return None
    if len({result['file'],result['title'],result['visible']}) != 3:
        return None
    # Do not display a live-send button with a missing token, a mock server,
    # a different API host, or an unverified authorization setup.
    try:
        cfg = _shiftbase_config()
        if cfg['mock_dir'] or urlsplit(cfg['base']).hostname != 'api.shiftbase.com':
            return None
    except (ShiftbaseIntegrationError, KeyError):
        return None
    if (os.environ.get('SHIFTBASE_AUTH_HEADER','Authorization').strip().lower() != 'authorization' or
            os.environ.get('SHIFTBASE_AUTH_PREFIX','API').strip().upper() != 'API'):
        return None
    return result


def _sbpay_nested(obj, key):
    for segment in key.split('.'):
        if not isinstance(obj, dict):
            return None
        obj = obj.get(segment)
    return obj


def _sbpay_verified_pdf(conn, batch_id, page_no):
    """Private PDF fully revalidated immediately before possible external upload."""
    batch, entries = _sbpay_batch_data(conn, batch_id)
    row = next((x for x in entries if int(x['page_no']) == int(page_no)), None)
    if row is None or not int(row['approved'] or 0) or not row['driver_id']:
        raise ShiftbaseIntegrationError('Keine freigegebene Mitarbeiterabrechnung.')
    driver_id = int(row['driver_id'])
    mapped = {int(x['id']): x for x in _sbpay_drivers(conn)}
    drv = mapped.get(driver_id)
    if (not drv or str(drv['shiftbase_user_id']) != str(row['shiftbase_user_id']) or
            not re.fullmatch(r'[0-9]{1,20}', str(row['shiftbase_user_id']))):
        raise ShiftbaseIntegrationError('Die aktuelle Mitarbeiter-ID stimmt nicht mehr mit der Freigabe ueberein.')
    # Automated (exact) matches require PDF/Cloud name identity. Manual matches
    # additionally require the earlier individually approved mapping record.
    if row['match_type'] == 'exact' and _sbpay_norm(drv['name']) != _sbpay_norm(row['employee_name']):
        raise ShiftbaseIntegrationError('Der Name entspricht nicht mehr der freigegebenen Zuordnung.')
    if row['match_type'] not in ('exact','manual'):
        raise ShiftbaseIntegrationError('Ungepruefte oder unklare Zuordnung.')
    duplicate = conn.execute('''SELECT page_no FROM shiftbase_payroll_pages
        WHERE batch_id=? AND driver_id=? AND page_no<>?''',
        (batch_id,driver_id,page_no)).fetchone()
    if duplicate:
        raise ShiftbaseIntegrationError('Mehrere Abrechnungen sind derselben Person zugeordnet.')
    relative = f'{batch_id}/blatt_{int(page_no):03d}.pdf'
    if row['relative_path'] != relative:
        raise ShiftbaseIntegrationError('Unzulaessiger Datei-Pfad.')
    path = _SBPAY_ROOT / relative
    if path.is_symlink() or not path.is_file():
        raise ShiftbaseIntegrationError('PDF fehlt oder ist kein regulaeres Dokument.')
    content = path.read_bytes()
    if not content.startswith(b'%PDF-') or len(content) > 5 * 1024 * 1024:
        raise ShiftbaseIntegrationError('Ungueltiges PDF oder Datei groesser als 5 MB.')
    if _sbpay_hashlib.sha256(content).hexdigest() != row['page_sha256']:
        raise ShiftbaseIntegrationError('Integritaetspruefung der PDF ist fehlgeschlagen.')
    if PdfReader is None:
        raise ShiftbaseIntegrationError('pypdf ist nicht installiert.')
    pdf = PdfReader(io.BytesIO(content), strict=True)
    if pdf.is_encrypted or len(pdf.pages) != int(row['file_pages']):
        raise ShiftbaseIntegrationError('Die PDF-Seiten stimmen nicht mit der Freigabe ueberein.')
    for page in pdf.pages:
        name, personal_no = _sbpay_identity_from_page(page)
        if (name != row['employee_name'] or personal_no != row['personal_no']):
            raise ShiftbaseIntegrationError('Die PDF enthaelt eine andere Mitarbeiter-Identitaet.')
    return batch, row, dict(drv), content


import time as _sbpay_time
_SBPAY_USER_CACHE_LOCK = threading.Lock()
_SBPAY_USER_CACHE = {'until': 0.0, 'users': ()}


def _sbpay_cached_users(force=False):
    """Avoid fetching the same full staff directory for every bulk PDF.

    The explicit preparation always fetches fresh users. Per-upload ID checks
    use a short-lived snapshot (at most 40 seconds) AND verify the employee's
    actual profile ID and name in the authenticated browser immediately before
    the write. No recipient is chosen solely by this cache.
    """
    if not force:
        with _SBPAY_USER_CACHE_LOCK:
            if _sbpay_time.monotonic() < _SBPAY_USER_CACHE['until']:
                return list(_SBPAY_USER_CACHE['users'])
    users = _shiftbase_get_all('users')
    with _SBPAY_USER_CACHE_LOCK:
        _SBPAY_USER_CACHE['users'] = tuple(users)
        _SBPAY_USER_CACHE['until'] = _sbpay_time.monotonic() + 40.0
    return list(users)


def _sbpay_assert_shiftbase_recipient(user_id, employee_name):
    """Read the current real Shiftbase account before uploading confidential data."""
    users = _sbpay_cached_users()
    matching = []
    same_named = []
    target_name = _sbpay_norm(employee_name)
    for item in users:
        user = _sb_get(item,'User')
        if not isinstance(user,dict):
            user = item
        uid = _sb_id(user,'id','user_id')
        if uid == str(user_id):
            matching.append(user)
        if _sbpay_norm(_sb_user_display(user)) == target_name:
            same_named.append(user)
    # Never send a payslip if two Shiftbase profiles use the same name,
    # even when one of them carries the ID previously mapped in the Cloud.
    if (len(matching) != 1 or len(same_named) != 1 or
            _sb_id(same_named[0],'id','user_id') != str(user_id)):
        raise ShiftbaseIntegrationError('Empfaenger in der aktuellen Shiftbase-Benutzerliste nicht eindeutig verifizierbar. Kein Upload.')


def _sbpay_multipart(parts, file_key, filename, data):
    boundary = 'SBPay' + _sbpay_uuid.uuid4().hex
    buffer = io.BytesIO()
    for name, value in parts:
        buffer.write(('--'+boundary+'\r\nContent-Disposition: form-data; name="'+name+'"\r\n\r\n'+value+'\r\n').encode('utf-8'))
    buffer.write(('--'+boundary+'\r\nContent-Disposition: form-data; name="'+file_key+'"; filename="'+filename+'"\r\nContent-Type: application/pdf\r\n\r\n').encode('utf-8'))
    buffer.write(data)
    buffer.write(('\r\n--'+boundary+'--\r\n').encode('ascii'))
    return 'multipart/form-data; boundary='+boundary, buffer.getvalue()


def _sbpay_upload_once(contract, batch, row, content):
    """One permitted POST, followed by an independent GET; never retry POST."""
    config = _shiftbase_config()
    if config['mock_dir']:
        raise ShiftbaseIntegrationError('Automatische Lohnzettel-Uploads im Shiftbase-Mockmodus verboten.')
    if urlsplit(config['base']).hostname not in ('api.shiftbase.com',):
        raise ShiftbaseIntegrationError('Der automatische Upload ist nur zum offiziellen Shiftbase-API-Host zulaessig.')
    if os.environ.get('SHIFTBASE_AUTH_HEADER','Authorization').strip().lower() != 'authorization' or os.environ.get('SHIFTBASE_AUTH_PREFIX','API').strip().upper() != 'API':
        raise ShiftbaseIntegrationError('Der Upload setzt die offizielle API-Token-Authentifizierung voraus.')
    user_id = str(row['shiftbase_user_id'])
    _sbpay_assert_shiftbase_recipient(user_id,row['employee_name'])
    title = f'Lohnabrechnung {int(batch["month"]):02d}/{int(batch["year"])}'
    # Field names and response schemas are explicit provider instructions,
    # not inferred from the Shiftbase personal-file UI.
    ct, data = _sbpay_multipart(
        [(contract['title'],title),(contract['visible'],'1')],
        contract['file'], 'Lohnabrechnung.pdf',content)
    token = config['token'].strip()
    if token.lower().startswith('api '):
        token = token[4:].strip()
    headers = {'Authorization':'API '+token,'Content-Type':ct,
               'Accept':'application/json', 'User-Agent':'PlusMinusCloud-PrivatePayroll/1.0'}
    post_path = contract['post'].replace('{user_id}',user_id)
    if not post_path.startswith('/'):
        raise ShiftbaseIntegrationError('Ungueltiger Upload-Pfad.')
    try:
        status, raw = _sb_http_request('POST',config['base']+post_path,headers,35,
                                       payload=data,max_bytes=200_000)
    except HTTPError as exc:
        raise ShiftbaseIntegrationError(f'Shiftbase Upload HTTP {int(exc.code)}. Nicht automatisch erneut senden.') from exc
    except (URLError,OSError,TimeoutError) as exc:
        raise ShiftbaseIntegrationError('Upload-Ergebnis wegen Verbindungsfehler unklar. Nicht erneut senden.') from exc
    if status not in (200,201):
        raise ShiftbaseIntegrationError('Die API hat keinen eindeutig erfolgreichen Upload bestaetigt.')
    try:
        answer = json.loads(raw.decode('utf-8'))
    except (ValueError,UnicodeError) as exc:
        raise ShiftbaseIntegrationError('Upload-Antwort nicht eindeutig lesbar. Kein erneuter Versuch.') from exc
    document_id = str(_sbpay_nested(answer,contract['response_doc']) or '').strip()
    response_owner = str(_sbpay_nested(answer,contract['response_owner']) or '').strip()
    if (not re.fullmatch(r'[0-9A-Za-z_-]{1,100}',document_id) or
            response_owner != user_id):
        raise ShiftbaseIntegrationError('API-Antwort enthaelt keine eindeutige Empfaenger- und Dokument-ID.')
    verify_path = (contract['get'].replace('{user_id}',user_id)
                   .replace('{file_id}',quote(document_id,safe='')))
    get_headers = dict(headers)
    get_headers.pop('Content-Type',None)
    try:
        _, verify_raw = _sb_http_request('GET',config['base']+verify_path,get_headers,20,
                                         max_bytes=200_000)
        record = json.loads(verify_raw.decode('utf-8'))
    except (HTTPError, URLError, OSError, TimeoutError, ValueError, UnicodeError) as exc:
        raise ShiftbaseIntegrationError('Upload erfolgt moeglicherweise, aber GET-Kontrolle nicht erfolgreich. Nicht erneut senden.') from exc
    seen_document = str(_sbpay_nested(record,contract['verify_doc']) or '').strip()
    seen_owner = str(_sbpay_nested(record,contract['verify_owner']) or '').strip()
    seen_visible = _sbpay_nested(record,contract['verify_visible'])
    if seen_document != document_id or seen_owner != user_id or seen_visible not in (True,1,'1','true','True'):
        raise ShiftbaseIntegrationError('GET-Pruefung von Dokument, Empfaenger oder Mitarbeitersichtbarkeit fehlgeschlagen.')
    return document_id



# --- Optionaler Shiftbase-Browserversand: keine undokumentierten REST-Endpunkte ---
# Die offizielle Shiftbase-Hilfe beschreibt den Mitarbeiter-Dateidialog, aber
# keinen belegten Public-API-Endpunkt. Dieser Adapter verwendet ausschließlich
# den authentifizierten Webdialog und stoppt bei unklarer UI. KEINE automatische
# Anmeldung mit ungesicherten Zugangsdaten, KEINE Firmenablage.
import base64 as _sbpay_base64
from urllib.parse import urlparse as _sbpay_urlparse


def _sbpay_browser_contract():
    """Optionale Browserautomatisierung; niemals ohne explizite Render-Secrets."""
    if os.environ.get('SHIFTBASE_PAYROLL_WEB_ENABLED', '').strip() != '1':
        return None
    encoded = os.environ.get('SHIFTBASE_PAYROLL_WEB_SESSION_B64', '').strip()
    if not encoded or len(encoded) > 200_000:
        return None
    try:
        state = json.loads(_sbpay_base64.b64decode(encoded, validate=True).decode('utf-8'))
        if not isinstance(state, dict) or not isinstance(state.get('cookies'), list):
            return None
        if len(state['cookies']) == 0:
            return None
        # Shiftbase session state never includes other websites. This prevents
        # accidentally forwarding authentication tokens from unrelated apps.
        for cookie in state['cookies']:
            domain = str(cookie.get('domain','')).lstrip('.').lower()
            if domain not in ('shiftbase.com','app.shiftbase.com') and not domain.endswith('.shiftbase.com'):
                return None
        origins = state.get('origins',[])
        if not isinstance(origins,list):
            return None
        for origin in origins:
            uri = _sbpay_urlparse(str(origin.get('origin','')))
            if uri.scheme != 'https' or (uri.hostname or '').lower() not in ('shiftbase.com','app.shiftbase.com'):
                return None
    except (ValueError, TypeError, KeyError, UnicodeError):
        return None
    # The recipient and the send mode are always chosen inside the protected
    # admin interface. No hard-coded test employee or environment bulk toggle.
    # Both paths still require individual approval, a live ID check and one
    # persistent attempt per private PDF.
    return {'mode':'browser', 'state':state,
            'origin':'https://app.shiftbase.com'}


def _sbpay_ui_strict_locator(locators, label):
    """Return one unambiguous visible UI element; never take a random match."""
    for loc in locators:
        try:
            n = loc.count()
            if n == 1 and loc.is_visible():
                return loc
        except Exception:
            continue
    raise ShiftbaseIntegrationError('Shiftbase-Weboberflaeche: '+label+' nicht eindeutig gefunden. Kein Upload.')


def _sbpay_browser_upload_once(contract, batch, row, content, before_submit=None):
    """Exactly one page-scope employee upload. No retries and no hidden API calls.

    Does not claim GET/API confirmation: result means that the file is visible
    in the personal-files UI after upload. The recipient's own view must be
    independently checked before considering employee visibility proven.
    """
    user_id = str(row['shiftbase_user_id'])
    employee_name = str(row['employee_name'])
    _sbpay_assert_shiftbase_recipient(user_id, employee_name)
    try:
        from playwright.sync_api import sync_playwright
    except ImportError as exc:
        raise ShiftbaseIntegrationError('Playwright fehlt. Bitte Render-Build um Chromium erweitern.') from exc
    from re import escape as regex_escape
    title = f'Lohnabrechnung {int(batch["month"]):02d}/{int(batch["year"])}'
    # Never include the employee name, amount or personal number in the remote
    # filename. They are already inside the protected PDF.
    file_name = f'Lohnabrechnung_{int(batch["year"])}_{int(batch["month"]):02d}.pdf'
    with sync_playwright() as engine:
        try:
            browser = engine.chromium.launch(headless=True, args=['--no-sandbox','--disable-dev-shm-usage'])
        except Exception as exc:
            raise ShiftbaseIntegrationError('Chromium steht auf Render nicht zur Verfuegung.') from exc
        try:
            context = browser.new_context(storage_state=contract['state'], accept_downloads=False,
                                          service_workers='block')
            page = context.new_page()
            page.set_default_timeout(14_000)
            target = contract['origin'] + '/universal/employees/' + user_id
            page.goto(target, wait_until='domcontentloaded', timeout=25_000)
            current = _sbpay_urlparse(page.url)
            if current.scheme != 'https' or current.hostname != 'app.shiftbase.com':
                raise ShiftbaseIntegrationError('Browser wurde zu einer anderen Domain umgeleitet. Kein Upload.')
            # Deep link is officially documented. Its target must not silently
            # become a different employee or a generic company files area.
            if (not re.search(r'(?<![0-9])'+regex_escape(user_id)+r'(?![0-9])',current.path) or
                    'login' in current.path.casefold()):
                raise ShiftbaseIntegrationError('Mitarbeiter-ID fehlt nach der Profilnavigation; Sitzung moeglicherweise abgelaufen. Kein Upload.')
            # Confirm the exact name exists on the employee profile; the REST
            # user-list validation happened immediately before browser open.
            name = page.get_by_text(employee_name, exact=True)
            try:
                name.first.wait_for(state='visible', timeout=20_000)
            except Exception as exc:
                raise ShiftbaseIntegrationError('Der Name ist im Mitarbeiterprofil nicht sichtbar; kein Upload.') from exc
            if name.count() < 1 or not name.first.is_visible():
                raise ShiftbaseIntegrationError('Der Mitarbeitername ist auf der Zielseite nicht exakt sichtbar.')
            files_tab = _sbpay_ui_strict_locator([
                page.get_by_role('tab', name=re.compile(r'^(Dateien|Files)$',re.I)),
                page.get_by_role('link', name=re.compile(r'^(Dateien|Files)$',re.I)),
                page.get_by_role('button', name=re.compile(r'^(Dateien|Files)$',re.I)),
            ],'persoenlicher Dateien-Tab')
            files_tab.click()
            page.wait_for_load_state('domcontentloaded')
            # Abort on another employee after changing tabs.
            if name.count() < 1 or not name.first.is_visible():
                raise ShiftbaseIntegrationError('Mitarbeiterprofil nach Tabwechsel nicht mehr identifizierbar.')
            # A matching title may indicate a previous upload. Never silently
            # overwrite or duplicate a payslip for this month.
            if page.get_by_text(title, exact=True).count():
                raise ShiftbaseIntegrationError('Lohnzettel dieses Monats bereits im Profil sichtbar; vor neuem Versand pruefen.')
            add_button = _sbpay_ui_strict_locator([
                page.get_by_role('button', name=re.compile(r'^(Datei hinzufuegen|Datei hinzufügen|Add file)$',re.I)),
            ], 'Datei-hinzufuegen-Schaltflaeche')
            add_button.click()
            uploads = page.locator('input[type="file"]')
            if uploads.count() != 1:
                raise ShiftbaseIntegrationError('Der persönliche Upload-Dialog enthaelt kein eindeutiges Dateifeld.')
            # Never click save before the exact PDF contents have been assigned.
            uploads.set_input_files({'name':file_name, 'mimeType':'application/pdf','buffer':content})
            title_field = _sbpay_ui_strict_locator([
                page.get_by_role('textbox', name=re.compile(r'^(Titel|Title)$',re.I)),
                page.locator('input[name="title"]'),
            ],'Dokumenttitel')
            title_field.fill(title)
            visible = _sbpay_ui_strict_locator([
                page.get_by_role('checkbox',name=re.compile(r'(Für Mitarbeiter sichtbar|Visible for employee|Zichtbaar voor medewerker)',re.I)),
            ], 'Sichtbarkeit fuer Mitarbeiter')
            if not visible.is_checked():
                visible.check()
            if not visible.is_checked() or title_field.input_value() != title:
                raise ShiftbaseIntegrationError('Mitarbeitersichtbarkeit oder Dokumenttitel vor dem Upload ungueltig.')
            save_button = _sbpay_ui_strict_locator([
                page.get_by_role('button', name=re.compile(r'^(Speichern|Save|Hochladen|Upload)$',re.I)),
            ],'Speichern im Mitarbeiterprofil')
            if before_submit is None:
                raise ShiftbaseIntegrationError('Vor dem Upload fehlt die persistente Schreibsperre.')
            before_submit()       # Persist 'sending' BEFORE network-changing action
            save_button.click()   # The ONLY external write in this operation
            try:
                page.get_by_text(title, exact=True).first.wait_for(state='visible',timeout=20_000)
            except Exception as exc:
                raise ShiftbaseIntegrationError('Upload-Ergebnis unklar: Dokumenttitel danach nicht sichtbar. Nicht erneut senden.') from exc
            if name.count() < 1 or not name.first.is_visible():
                raise ShiftbaseIntegrationError('Nach Upload kann das Mitarbeiterprofil nicht erneut bestaetigt werden.')
            # No provider file-ID or verified REST GET is available. Explicit
            # UI-only state is used by the caller. Never treat as GET-confirmed.
            return 'ui:'+_sbpay_uuid.uuid4().hex
        finally:
            try:
                browser.close()
            except Exception:
                pass



def _sbpay_simple_send_script(batch_id, csrf_token):
    """One visible send action, always one verified recipient per server request."""
    route = url_for('admin_shiftbase_payroll_upload_step', batch_id=batch_id)
    script = r"""<script>(function(){
const boxes=[...document.querySelectorAll('.sbpay-choice:not(:disabled)')];
const all=document.getElementById('sbpay-all');
const none=document.getElementById('sbpay-none');
const send=document.getElementById('sbpay-send');
const meter=document.getElementById('sbpay-meter');
const info=document.getElementById('sbpay-progress');
const search=document.getElementById('sbpay-find');
const rows=[...document.querySelectorAll('#sbpay-table tbody tr')];
if(!send||!meter||!info)return;
let sending=false;
function chosen(){return boxes.filter(b=>b.checked&&!b.disabled);}
function update(){
 const n=chosen().length;
 send.textContent='Ausgewaehlte PDFs senden ('+n+')';
 send.disabled=sending||n===0||DISABLED;
 if(all)all.disabled=sending;
 if(none)none.disabled=sending;
}
boxes.forEach(b=>b.addEventListener('change',update));
if(all)all.addEventListener('click',()=>{boxes.forEach(b=>b.checked=true);update();});
if(none)none.addEventListener('click',()=>{boxes.forEach(b=>b.checked=false);update();});
if(search)search.addEventListener('input',()=>{
 const query=search.value.trim().toLocaleLowerCase('de');
 rows.forEach(r=>{r.style.display=!query||r.textContent.toLocaleLowerCase('de').includes(query)?'':'none';});
});
send.addEventListener('click',async()=>{
 if(sending)return;
 const picked=chosen().map(b=>b.value);
 if(!picked.length)return;
 sending=true;update();
 meter.max=picked.length;meter.value=0;
 info.textContent='0 von '+picked.length+' Mitarbeitern verarbeitet. Bitte diese Seite waehrend des Versands offen lassen.';
 let complete=0, failed=false;
 for(const number of picked){
  const params=new URLSearchParams();
  params.set('csrf_token',CSRF);params.set('mode','single');params.set('page_no',number);
  try{
   const response=await fetch(ROUTE,{method:'POST',body:params,credentials:'same-origin',cache:'no-store'});
   const result=await response.json();
   if(!response.ok||result.error||result.done){
    info.textContent='Gestoppt bei PDF '+number+': '+(result.error||'Unbekannte Antwort')+
        '. Bereits bearbeitete Personen bitte in Shiftbase kontrollieren.';
    failed=true;break;
   }
   if(result.state!=='confirmed'&&result.state!=='observed_ui'){
    info.textContent='Gestoppt bei PDF '+number+': Status '+(result.state||'unbekannt')+
        '. Bei unklarem Ergebnis nicht erneut senden!';
    failed=true;break;
   }
   const checkbox=boxes.find(b=>b.value===number);
   if(checkbox){
    checkbox.checked=false;checkbox.disabled=true;
    const cell=checkbox.closest('tr')?.querySelector('.sbpay-status');
    if(cell)cell.textContent=result.state==='confirmed'?'API-bestaetigt':'Im persoenlichen Profil gesehen';
   }
   complete++;meter.value=complete;
   info.textContent=complete+' von '+picked.length+' PDFs verarbeitet.';
  }catch(error){
   info.textContent='Verbindung unterbrochen bei PDF '+number+
      '. Keine erneute Uebertragung starten, bevor die persoenliche Shiftbase-Akte kontrolliert wurde.';
   failed=true;break;
  }
 }
 sending=false;update();
 if(!failed){
  info.textContent='Alle '+complete+' ausgewaehlten PDFs bearbeitet. Der aktuelle Status wird geladen.';
  window.location.reload();
 }
});
update();
})();</script>"""
    return script.replace('CSRF', json.dumps(str(_sb_csrf_token())))\
                 .replace('ROUTE', json.dumps(route))\
                 .replace('DISABLED', 'false' if _sbpay_upload_contract() else 'true')


@app.post('/admin/shiftbase/lohnzettel/<batch_id>/upload-next')
@admin_login_required
def admin_shiftbase_payroll_upload_step(batch_id):
    _sbpay_token_check()
    contract = _sbpay_upload_contract()
    if not contract:
        return _sbpay_no_cache(jsonify({'error':'Kein verifizierter Shiftbase-Personalakten-API-Vertrag konfiguriert.'})), 503
    # Explicit admin-side choice: exactly one identified page OR all eligible
    # pages in a sequential run. An unset/invalid mode must NEVER imply bulk.
    mode = (request.form.get('mode') or '').strip()
    if mode not in ('single', 'all'):
        return _sbpay_no_cache(jsonify({'error': 'Einzel- oder Gesamtversand muss explizit gewaehlt werden.'})), 400
    requested_page = None
    if mode == 'single':
        raw_page = (request.form.get('page_no') or '').strip()
        if not re.fullmatch(r'[1-9][0-9]{0,5}', raw_page):
            return _sbpay_no_cache(jsonify({'error': 'Eine eindeutige Mitarbeiter-PDF ist erforderlich.'})), 400
        requested_page = int(raw_page)
    elif request.form.get('page_no'):
        return _sbpay_no_cache(jsonify({'error': 'Unzulaessige Einzelseite beim Gesamtversand.'})), 400
    # Claim one row BEFORE network activity; UNIQUE(batch_id,page_no) makes every
    # attempt at most once, including timeouts, lost HTTP replies, or page reloads.
    with db_conn() as conn:
        batch, rows = _sbpay_batch_data(conn, batch_id)
        _sbpay_delivery_schema(conn)
        existing = {int(r['page_no']) for r in conn.execute(
            'SELECT page_no FROM shiftbase_payroll_deliveries WHERE batch_id=?',
            (batch_id,)).fetchall()}
        current = _sb_mapping(conn)
        _sbpay_livecheck_schema(conn)
        livechecks = {int(r['page_no']): dict(r) for r in conn.execute(
            'SELECT * FROM shiftbase_payroll_livechecks WHERE batch_id=?',
            (batch_id,)).fetchall()}
        def allowed(row):
            page = int(row['page_no'])
            did = row['driver_id']
            if page in existing or not did or not row['approved']:
                return False
            if mode == 'single' and page != requested_page:
                return False
            if current.get(int(did)) != str(row['shiftbase_user_id']):
                return False
            live = livechecks.get(page, {})
            return (live.get('status') == 'verified' and
                    live.get('shiftbase_user_id') == str(row['shiftbase_user_id']) and
                    live.get('page_sha256') == str(row['page_sha256']))
        row = next((r for r in rows if allowed(r)), None)
        if row is None:
            if mode == 'single':
                return _sbpay_no_cache(jsonify({'error':
                    'Diese Mitarbeiter-PDF ist nicht freigegeben, nicht live geprueft oder wurde bereits versucht.'})), 409
            return _sbpay_no_cache(jsonify({'done': True}))
        page_no=int(row['page_no'])
        attempt_id=_sbpay_uuid.uuid4().hex
        conn.execute('''INSERT INTO shiftbase_payroll_deliveries
          (batch_id,page_no,attempt_id,driver_id,shiftbase_user_id,page_sha256,state,started_at,updated_at)
          VALUES(?,?,?,?,?,?,?,?,?) ON CONFLICT(batch_id,page_no) DO NOTHING''',
          (batch_id,page_no,attempt_id,int(row['driver_id']),str(row['shiftbase_user_id']),
           str(row['page_sha256']),'preparing' if contract.get('mode')=='browser' else 'sending',
           now_iso(),now_iso()))
        conn.commit()
        claimed=conn.execute('''SELECT attempt_id FROM shiftbase_payroll_deliveries
            WHERE batch_id=? AND page_no=?''',(batch_id,page_no)).fetchone()
        if not claimed or claimed['attempt_id']!=attempt_id:
            return _sbpay_no_cache(jsonify({'done':False,'state':'bereits in Bearbeitung'}))
    # Preflight is outside the transaction. Errors are recorded and never retried.
    document_id=''
    try:
        with db_conn() as conn:
            batch, row, driver, content = _sbpay_verified_pdf(conn,batch_id,page_no)
        if contract.get('mode') == 'browser':
            def mark_before_browser_save():
                # An interrupted connection after this point is UNKNOWN, never
                # automatically resent; the file might already exist in Shiftbase.
                with db_conn() as wconn:
                    changed = wconn.execute('''UPDATE shiftbase_payroll_deliveries SET
                      state='sending', updated_at=? WHERE batch_id=? AND page_no=?
                      AND attempt_id=? AND state='preparing' ''',
                      (now_iso(),batch_id,page_no,attempt_id))
                    wconn.commit()
                    if getattr(changed,'rowcount',1) == 0:
                        raise ShiftbaseIntegrationError('Schreibsperre nicht mehr gueltig.')
            document_id = _sbpay_browser_upload_once(contract,batch,row,content,
                                                       before_submit=mark_before_browser_save)
            state='observed_ui'
        else:
            document_id = _sbpay_upload_once(contract,batch,row,content)
            state='confirmed'
    except Exception:
        # Before Save, a browser attempt is provably write-free. Remove only
        # that preflight claim so an expired session can be fixed safely.
        if contract.get('mode') == 'browser':
            with db_conn() as rconn:
                current_state = rconn.execute('''SELECT state FROM shiftbase_payroll_deliveries
                  WHERE batch_id=? AND page_no=? AND attempt_id=?''',
                  (batch_id,page_no,attempt_id)).fetchone()
                if current_state and current_state['state'] == 'preparing':
                    rconn.execute('''DELETE FROM shiftbase_payroll_deliveries
                      WHERE batch_id=? AND page_no=? AND attempt_id=? AND state='preparing' ''',
                      (batch_id,page_no,attempt_id))
                    rconn.commit()
                    return _sbpay_no_cache(jsonify({'done':False,'error':
                        'Browser-Vorpruefung fehlgeschlagen. Kein Upload gestartet. '
                        'Shiftbase-Anmeldung, Browser und Mitarbeiterseite pruefen.'})), 409
        # After Save could have started, never retry this employee automatically.
        state='unknown'
    with db_conn() as conn:
        _sbpay_delivery_schema(conn)
        conn.execute('''UPDATE shiftbase_payroll_deliveries
            SET state=?,document_id=?,updated_at=?
            WHERE batch_id=? AND page_no=? AND attempt_id=?''',
            (state,document_id,now_iso(),batch_id,page_no,attempt_id))
        conn.commit()
    return _sbpay_no_cache(jsonify({'done':False,'state':state}))


def _sbpay_livecheck_schema(conn):
    conn.execute('''CREATE TABLE IF NOT EXISTS shiftbase_payroll_livechecks (
        batch_id TEXT NOT NULL, page_no INTEGER NOT NULL,
        shiftbase_user_id TEXT NOT NULL, page_sha256 TEXT NOT NULL,
        status TEXT NOT NULL, checked_at TEXT NOT NULL,
        PRIMARY KEY(batch_id,page_no))''')


@app.post('/admin/shiftbase/lohnzettel/<batch_id>/livecheck')
@admin_login_required
def admin_shiftbase_payroll_livecheck(batch_id):
    """Read-only comparison against the real Shiftbase users resource."""
    _sbpay_token_check()
    with db_conn() as conn:
        batch, rows = _sbpay_batch_data(conn,batch_id)
        current = _sb_mapping(conn)
    try:
        users = _shiftbase_get_all('users')
        from collections import Counter as _sbpay_counter_users
        normalized = []
        for entry in users:
            person = _sb_get(entry,'User')
            if not isinstance(person,dict):
                person = entry
            normalized.append((_sb_id(person,'id','user_id'),_sbpay_norm(_sb_user_display(person))))
        id_counts = _sbpay_counter_users(uid for uid, name in normalized if uid)
        name_counts = _sbpay_counter_users(name for uid, name in normalized if name)
        pairs = set(normalized)
    except ShiftbaseIntegrationError:
        flash('Shiftbase-Benutzer konnten nicht gelesen werden. Nichts wurde hochgeladen.', 'err')
        return redirect(url_for('admin_shiftbase_payroll_batch',batch_id=batch_id))
    passed = 0
    with db_conn() as conn:
        _sbpay_livecheck_schema(conn)
        for row in rows:
            uid = str(row['shiftbase_user_id'] or '')
            name = _sbpay_norm(row['employee_name'])
            did = int(row['driver_id']) if row['driver_id'] else 0
            ok = (bool(row['approved']) and current.get(did) == uid and
                  re.fullmatch(r'[0-9]{1,20}',uid) is not None and
                  id_counts[uid] == 1 and name_counts[name] == 1 and
                  (uid,name) in pairs)
            status = 'verified' if ok else 'blocked'
            passed += int(ok)
            conn.execute('''INSERT INTO shiftbase_payroll_livechecks
              (batch_id,page_no,shiftbase_user_id,page_sha256,status,checked_at)
              VALUES(?,?,?,?,?,?) ON CONFLICT(batch_id,page_no) DO UPDATE SET
                shiftbase_user_id=excluded.shiftbase_user_id,
                page_sha256=excluded.page_sha256,
                status=excluded.status,checked_at=excluded.checked_at''',
                (batch_id,int(row['page_no']),uid,str(row['page_sha256']),status,now_iso()))
        conn.commit()
    flash(f'{passed} von {len(rows)} freigegebenen Abrechnungen anhand der aktuellen Shiftbase-Benutzerliste eindeutig bestätigt. Kein Datei-Upload.', 'ok')
    return redirect(url_for('admin_shiftbase_payroll_batch',batch_id=batch_id))


# ========== Ende vertrauliche DATEV-Lohnzettel ==========

# ========== Ende Erweiterung Arbeitstage ==========

# ========== End resumable transfer ==========

# ============ Ende Shiftbase-Pruefvorschau ============

# =================== ENDE: Shiftbase-Lohnabgleich ===================

if __name__ == "__main__":
    ensure_paths()
    with db_conn() as conn:
        recalc_all(conn); conn.commit()
    port = int(os.environ.get("PORT", "5050"))
    app.run(host="0.0.0.0", port=port, debug=False)
















