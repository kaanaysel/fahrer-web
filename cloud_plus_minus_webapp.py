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
label{display:block;font-weight:800;margin-bottom:6px}input,select,textarea,button,.btn{width:100%;padding:11px 12px;border:1px solid #c7ceda;border-radius:12px;font-size:15px;background:#fff}textarea{min-height:42px;resize:vertical}button,.btn{cursor:pointer;text-decoration:none;text-align:center;display:inline-block;background:#f8fafc;font-weight:800}.btn.primary,button.primary{background:linear-gradient(135deg,var(--blue),var(--blue2));border-color:var(--blue);color:#fff}.btn.danger,button.danger{background:#fff1f0;border-color:#fda29b;color:#b42318}.btn.small{width:auto;padding:8px 11px;border-radius:10px;font-size:13px}.actions{display:flex;gap:10px;flex-wrap:wrap;align-items:center}.actions .btn,.actions button{width:auto}.table-wrap{overflow:auto;border:1px solid var(--line);border-radius:18px;background:#fff}table{border-collapse:separate;border-spacing:0;width:100%;min-width:1180px}th,td{padding:12px;border-bottom:1px solid #edf0f5;text-align:left;vertical-align:middle}th{position:sticky;top:0;background:#f3f6fb;color:#344054;font-size:13px;z-index:1}tr:hover td{background:#fbfdff}.flash{padding:12px 14px;border-radius:14px;margin-bottom:14px;font-weight:700}.flash.ok{background:#ecfdf3;color:#067647;border:1px solid #abefc6}.flash.err{background:#fff1f0;color:#b42318;border:1px solid #fecdca}.login-wrap{max-width:520px;margin:8vh auto;padding:24px}.driver-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(210px,1fr));gap:14px}.month-card{padding:16px;border:1px solid var(--line);border-radius:18px;background:#fff;text-decoration:none}.month-card strong{display:block;color:#123e7c;font-size:1.1rem;margin-bottom:6px}.right{text-align:right}.nowrap{white-space:nowrap}.item-row{display:flex;gap:8px;align-items:center;margin-bottom:6px;padding:6px 8px;border:1px solid #edf0f5;border-radius:12px;background:#fbfdff}.item-row form{margin-left:auto}.mini-form{display:grid;grid-template-columns:110px 90px minmax(160px,1fr) auto;gap:8px;align-items:center}.sum-box{font-size:13px;margin-top:8px;color:var(--muted)}.admin-info{min-width:240px}.admin-info textarea{min-height:86px;font-size:14px;background:#fffef7;border-color:#f6d98b}.download-note{font-size:12px;color:var(--muted);margin-top:4px}.driver-row.row-base td{background:#ffffff}.driver-row.row-alt td{background:#f3f6fb}.driver-row:hover td{background:#eaf1fb!important}.adjustment-list{margin-top:12px;padding-top:10px;border-top:1px dashed #cfd6e3}.delete-month-btn{font-size:11px!important;padding:5px 8px!important;border-radius:9px!important;opacity:.82}.delete-month-btn:hover{opacity:1}.admin-info textarea.carried{background:#f5f8ff;border-color:#b8c8f0}.months-table{table-layout:fixed;min-width:1120px}.months-table th,.months-table td{padding:9px 8px}.col-admin{width:185px}.col-driver{width:135px}.col-hours{width:78px}.col-payroll{width:88px}.col-v{width:74px}.col-adjust{width:390px}.col-small{width:70px}.col-action{width:120px}.months-table input[name=worked_hours],.months-table input[name=payroll_hours],.months-table input[name=v_hours]{padding:12px 9px;font-size:16px}.months-table input[name=worked_hours]{max-width:76px}.months-table input[name=payroll_hours]{max-width:86px}.months-table input[name=v_hours]{max-width:72px}.mini-form{grid-template-columns:92px 74px minmax(120px,1fr) 112px auto}.dropzone{position:relative;border:2px dashed #b8c4d6;background:#f8fafc;border-radius:12px;padding:8px 10px;text-align:center;font-size:12px;color:#475467;cursor:pointer}.dropzone.dragover{border-color:#067647;background:#ecfdf3;color:#067647}.dropzone input[type=file]{position:absolute;inset:0;opacity:0;cursor:pointer}.file-pill{display:inline-flex;align-items:center;gap:6px;padding:5px 8px;border-radius:999px;background:#eef4ff;color:#123e7c;font-size:12px;margin-top:6px}.file-pill form{display:inline;margin:0}.file-remove{width:auto!important;padding:3px 7px!important;border-radius:999px!important;font-size:11px!important}.compact-save{display:flex;flex-direction:column;gap:7px;align-items:flex-start}.mobile-row-title{display:none;font-weight:900;color:#0f2446;margin-bottom:8px}
@media(max-width:900px){.shell{display:block}.side{position:relative;height:auto}.main{padding:14px}.grid-2,.grid-3,.grid-4{grid-template-columns:1fr}.top{display:block}.title{font-size:1.55rem}.mini-form{grid-template-columns:1fr}.table-wrap.mobile-cards{overflow:visible;border:0;background:transparent}.months-table{min-width:0;display:block}.months-table thead{display:none}.months-table tbody,.months-table tr,.months-table td{display:block;width:100%}.months-table tr{margin-bottom:14px;border:1px solid var(--line);border-radius:18px;background:#fff;box-shadow:var(--shadow);overflow:hidden}.months-table td{border-bottom:1px solid #edf0f5;padding:10px 12px}.months-table td::before{content:attr(data-label);display:block;font-size:12px;font-weight:900;color:#667085;margin-bottom:5px}.months-table .mobile-row-title{display:block}.months-table input[name=worked_hours],.months-table input[name=payroll_hours],.months-table input[name=v_hours]{max-width:100%;width:100%}.admin-info{min-width:0}.col-adjust{width:auto}.compact-save{flex-direction:row;flex-wrap:wrap}.item-row{align-items:flex-start}.side .muted{display:none}}
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


def signed_class(v: float) -> str:
    v = float(v or 0)
    return "pos" if v > 0 else "neg" if v < 0 else "zero"


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


def compute_difference(worked: float, payroll: float, v: float, bonus: float, deduction: float) -> float:
    return round(float(worked) - (float(payroll) + abs(float(v))) + float(bonus) + float(deduction), 2)


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

# ---------------- database ----------------
def db_conn() -> sqlite3.Connection:
    ensure_paths()
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys=ON")
    conn.executescript("""
    CREATE TABLE IF NOT EXISTS drivers(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        external_driver_id INTEGER UNIQUE,
        name TEXT NOT NULL,
        username TEXT NOT NULL UNIQUE,
        password_hash TEXT NOT NULL,
        starting_balance REAL NOT NULL DEFAULT 0,
        is_active INTEGER NOT NULL DEFAULT 1,
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
        bonus_hours REAL NOT NULL DEFAULT 0,
        bonus_comment TEXT NOT NULL DEFAULT '',
        deduction_hours REAL NOT NULL DEFAULT 0,
        deduction_comment TEXT NOT NULL DEFAULT '',
        adjustment_hours REAL NOT NULL DEFAULT 0,
        comment TEXT NOT NULL DEFAULT '',
        admin_info TEXT NOT NULL DEFAULT '',
        admin_info_carried INTEGER NOT NULL DEFAULT 0,
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
    """)

    cols = {r[1] for r in conn.execute("PRAGMA table_info(drivers)").fetchall()}
    if "starting_balance" not in cols:
        conn.execute("ALTER TABLE drivers ADD COLUMN starting_balance REAL NOT NULL DEFAULT 0")

    cols = {r[1] for r in conn.execute("PRAGMA table_info(monthly_data)").fetchall()}
    for name, ddl in {
        "bonus_hours":"ALTER TABLE monthly_data ADD COLUMN bonus_hours REAL NOT NULL DEFAULT 0",
        "bonus_comment":"ALTER TABLE monthly_data ADD COLUMN bonus_comment TEXT NOT NULL DEFAULT ''",
        "deduction_hours":"ALTER TABLE monthly_data ADD COLUMN deduction_hours REAL NOT NULL DEFAULT 0",
        "deduction_comment":"ALTER TABLE monthly_data ADD COLUMN deduction_comment TEXT NOT NULL DEFAULT ''",
        "admin_info":"ALTER TABLE monthly_data ADD COLUMN admin_info TEXT NOT NULL DEFAULT ''",
        "admin_info_carried":"ALTER TABLE monthly_data ADD COLUMN admin_info_carried INTEGER NOT NULL DEFAULT 0",
    }.items():
        if name not in cols:
            conn.execute(ddl)

    conn.commit()
    return conn


def audit(conn: sqlite3.Connection, action: str, details: str = "", actor: str = "admin") -> None:
    conn.execute("INSERT INTO audit_log(actor, action, details, created_at) VALUES(?,?,?,?)", (actor, action, details, now_iso()))


def get_driver_by_db_id(conn: sqlite3.Connection, driver_id: int) -> Optional[sqlite3.Row]:
    return conn.execute("SELECT * FROM drivers WHERE id=?", (driver_id,)).fetchone()


def next_external_id(conn: sqlite3.Connection) -> int:
    row = conn.execute("SELECT MAX(external_driver_id) AS m FROM drivers").fetchone()
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


def get_or_create_month_row(conn: sqlite3.Connection, driver_id: int, year: int, month: int, carry_admin_info: bool = True) -> int:
    row = conn.execute(
        "SELECT id FROM monthly_data WHERE driver_id=? AND year=? AND month=?",
        (driver_id, year, month),
    ).fetchone()
    if row:
        monthly_id = int(row["id"])
    else:
        cur = conn.execute(
            "INSERT INTO monthly_data(driver_id, year, month, updated_at) VALUES(?,?,?,?)",
            (driver_id, year, month, now_iso()),
        )
        monthly_id = int(cur.lastrowid)

    if carry_admin_info:
        maybe_carry_admin_info(conn, monthly_id, driver_id, year, month)
    return monthly_id

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
        diff = compute_difference(r["worked_hours"], r["payroll_hours"], r["v_hours"], r["bonus_hours"], r["deduction_hours"])
        new_balance = round(balance + diff, 2)
        conn.execute("UPDATE monthly_data SET difference_hours=?, previous_balance=?, new_balance=? WHERE id=?", (diff, round(balance,2), new_balance, r["id"]))
        balance = new_balance


def recalc_all(conn: sqlite3.Connection) -> None:
    for d in conn.execute("SELECT id FROM drivers ORDER BY id").fetchall():
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
        driver["name"], fmt_hours(row["worked_hours"]), fmt_hours(row["payroll_hours"]), fmt_hours(abs(row["v_hours"])),
        format_value_comment(row["bonus_hours"], row["bonus_comment"], hours=True), format_value_comment(row["deduction_hours"], row["deduction_comment"], hours=True),
        fmt_signed(row["difference_hours"]), fmt_signed(row["previous_balance"]), fmt_signed(row["new_balance"])
    ]], extra_story=extra_story)
    ts = now_iso()
    existing = conn.execute("SELECT id FROM documents WHERE driver_id=? AND year=? AND month=?", (driver_id, year, month)).fetchone()
    if existing:
        conn.execute("UPDATE documents SET filename=?, original_filename=?, relative_path=?, uploaded_at=? WHERE id=?", (safe_name, safe_name, str(relative_path), ts, existing["id"]))
        return int(existing["id"])
    cur = conn.execute("INSERT INTO documents(driver_id,year,month,filename,original_filename,relative_path,uploaded_at) VALUES(?,?,?,?,?,?,?)", (driver_id,year,month,safe_name,safe_name,str(relative_path),ts))
    return int(cur.lastrowid)


def export_month_pdf(conn: sqlite3.Connection, year: int, month: int) -> Path:
    rows = conn.execute("SELECT m.*, d.name FROM monthly_data m JOIN drivers d ON d.id=m.driver_id WHERE m.year=? AND m.month=? ORDER BY d.name COLLATE NOCASE", (year, month)).fetchall()
    pdf_rows = [[
        f"{MONATE[month]} {year}",
        r["admin_info"] or "-",
        r["name"],
        fmt_hours(r["worked_hours"]),
        fmt_hours(r["payroll_hours"]),
        fmt_hours(abs(r["v_hours"])),
        format_value_comment(r["bonus_hours"], r["bonus_comment"], True),
        format_value_comment(r["deduction_hours"], r["deduction_comment"], True),
        fmt_signed(r["difference_hours"]),
        fmt_signed(r["previous_balance"]),
        fmt_signed(r["new_balance"]),
    ] for r in rows]
    if not pdf_rows:
        pdf_rows = [[f"{MONATE[month]} {year}", "-", "Keine Einträge", "-", "-", "-", "-", "-", "-", "-", "-"]]
    path = EXPORT_DIR / str(year) / f"{month:02d}_{MONATE[month]}_{year}.pdf"
    create_pdf_report(path, f"Monatsübersicht {MONATE[month]} {year}", "Admin-Übersicht inklusive interner Allgemeiner Infos", ["Monat","Allgemeine Infos","Fahrer","Stunden","Abrechnung","V","Zuschüsse","Abzüge","Differenz","Aktueller Stand","Neuer Stand"], pdf_rows)
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
        entries.append({"page":page_no,"name":driver_name,"personalnummer":personalnummer,"month_name":month_name,"year":year,"month":month_num,"v_source_amount":round(v_amount,2),"v_hours":round(v_amount/14.0,2)})
    return entries


def guess_driver_match(conn: sqlite3.Connection, source_name: str) -> Tuple[Optional[int], str]:
    drivers = conn.execute("SELECT id,name FROM drivers WHERE is_active=1").fetchall()
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


def admin_api_required() -> None:
    token = request.headers.get("X-Admin-Token", "")
    if not ADMIN_API_TOKEN or token != ADMIN_API_TOKEN:
        abort(401)

# ---------------- templates ----------------
def base_page(title: str, body: str, active: str = "dashboard") -> str:
    nav = [
        ("dashboard","Dashboard",url_for("admin_dashboard")), ("drivers","Fahrer",url_for("admin_drivers")),
        ("months","Monatsdaten",url_for("admin_months")), ("import","PDF-Import",url_for("admin_import_pdf")),
        ("exports","Export/Backup",url_for("admin_exports")), ("portal","Fahrerportal",url_for("driver_login")),
    ]
    flashes = "".join(f'<div class="flash {"ok" if c=="ok" else "err"}">{m}</div>' for c,m in get_flashed_messages(with_categories=True))
    return render_template_string("""
    <!doctype html><html lang="de"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{{ title }}</title><style>{{ css }}</style></head><body>
    <div class="shell"><aside class="side"><div class="brand">± Plus/Minus Cloud</div><div class="nav">{% for key,label,href in nav %}<a class="{{ 'active' if key==active else '' }}" href="{{ href }}">{{ label }}</a>{% endfor %}<a href="{{ url_for('admin_logout') }}">Logout Admin</a></div><p class="muted" style="color:#bdd2f4;margin-top:24px">Zentrale Cloud-Datenbank. Keine manuelle Synchronisation.</p></aside>
    <main class="main"><div class="top"><div><div class="title">{{ title }}</div><div class="subtitle">Änderungen werden direkt auf dem Server gespeichert und sind sofort auf allen PCs sichtbar.</div></div><span class="badge">Live Cloud</span></div>{{ flashes|safe }}{{ body|safe }}</main></div></body></html>
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
    with db_conn() as conn:
        recalc_all(conn); conn.commit()
        k = conn.execute("SELECT COUNT(*) drivers, COALESCE(SUM(is_active),0) active FROM drivers").fetchone()
        m = conn.execute("SELECT COUNT(*) cnt FROM monthly_data").fetchone()["cnt"]
        docs = conn.execute("SELECT COUNT(*) cnt FROM documents").fetchone()["cnt"]
        latest = conn.execute("SELECT m.*, d.name FROM monthly_data m JOIN drivers d ON d.id=m.driver_id ORDER BY m.updated_at DESC LIMIT 8").fetchall()
        balances = conn.execute("SELECT d.id,d.name,d.starting_balance,(SELECT new_balance FROM monthly_data m WHERE m.driver_id=d.id ORDER BY year DESC, month DESC, id DESC LIMIT 1) bal FROM drivers d WHERE d.is_active=1 ORDER BY d.name COLLATE NOCASE").fetchall()
    body = render_template_string("""
    <div class="grid grid-4"><div class="kpi">Fahrer<b>{{ k['active'] }}</b><span class="muted">aktiv</span></div><div class="kpi">Monatsdaten<b>{{ m }}</b><span class="muted">gespeichert</span></div><div class="kpi">PDFs<b>{{ docs }}</b><span class="muted">im Portal</span></div><div class="kpi">Sync<b>0</b><span class="muted">manuelle Schritte</span></div></div>
    <div class="grid grid-2"><div class="card"><h2>Aktuelle Salden</h2><div class="table-wrap"><table style="min-width:420px"><tr><th>Fahrer</th><th class="right">Saldo</th></tr>{% for r in balances %}<tr><td>{{ r['name'] }}</td><td class="right {{ signed_class(r['bal'] if r['bal'] is not none else r['starting_balance']) }}">{{ fmt_signed(r['bal'] if r['bal'] is not none else r['starting_balance']) }}</td></tr>{% endfor %}</table></div></div>
    <div class="card"><h2>Letzte Änderungen</h2><div class="table-wrap"><table style="min-width:560px"><tr><th>Fahrer</th><th>Monat</th><th>Differenz</th><th>Neu</th></tr>{% for r in latest %}<tr><td>{{ r['name'] }}</td><td>{{ months[r['month']] }} {{ r['year'] }}</td><td class="{{ signed_class(r['difference_hours']) }}">{{ fmt_signed(r['difference_hours']) }}</td><td class="{{ signed_class(r['new_balance']) }}">{{ fmt_signed(r['new_balance']) }}</td></tr>{% endfor %}</table></div></div></div>
    """, k=k, m=m, docs=docs, latest=latest, balances=balances, months=MONATE, fmt_signed=fmt_signed, signed_class=signed_class)
    return base_page("Dashboard", body, "dashboard")


@app.route("/admin/drivers", methods=["GET","POST"])
@admin_login_required
def admin_drivers():
    with db_conn() as conn:
        if request.method == "POST":
            action = request.form.get("action")
            ts = now_iso()
            if action == "create":
                name = request.form.get("name", "").strip(); username = request.form.get("username", "").strip() or slugify(name); password = request.form.get("password", "").strip(); start = parse_hours(request.form.get("starting_balance", "0"))
                if not name or not password:
                    flash("Name und Passwort sind Pflicht.", "err")
                else:
                    ext = next_external_id(conn); username = make_unique_username(conn, username)
                    conn.execute("INSERT INTO drivers(external_driver_id,name,username,password_hash,starting_balance,is_active,created_at,updated_at) VALUES(?,?,?,?,?,1,?,?)", (ext,name,username,generate_password_hash(password),start,ts,ts)); audit(conn,"driver_create",name); conn.commit(); flash("Fahrer angelegt.", "ok")
            elif action == "update":
                did = int(request.form["driver_id"]); name = request.form.get("name", "").strip(); username = request.form.get("username", "").strip(); start = parse_hours(request.form.get("starting_balance", "0")); active = 1 if request.form.get("is_active") == "on" else 0
                username = make_unique_username(conn, username or name, exclude_id=did)
                conn.execute("UPDATE drivers SET name=?,username=?,starting_balance=?,is_active=?,updated_at=? WHERE id=?", (name,username,start,active,ts,did))
                pw = request.form.get("password", "").strip()
                if pw:
                    conn.execute("UPDATE drivers SET password_hash=?,updated_at=? WHERE id=?", (generate_password_hash(pw),ts,did))
                recalc_driver(conn,did); audit(conn,"driver_update",name); conn.commit(); flash("Fahrer gespeichert.", "ok")
            elif action == "delete":
                did = int(request.form["driver_id"]); conn.execute("DELETE FROM drivers WHERE id=?", (did,)); audit(conn,"driver_delete",str(did)); conn.commit(); flash("Fahrer gelöscht.", "ok")
        drivers = conn.execute("SELECT d.*, COALESCE((SELECT new_balance FROM monthly_data m WHERE m.driver_id=d.id ORDER BY year DESC,month DESC,id DESC LIMIT 1), d.starting_balance) AS balance FROM drivers d ORDER BY d.name COLLATE NOCASE").fetchall()
    body = render_template_string("""
    <div class="card"><h2>Neuen Fahrer anlegen</h2><form method="post" class="grid grid-4"><input type="hidden" name="action" value="create"><div><label>Name</label><input name="name" required></div><div><label>Benutzername</label><input name="username" placeholder="automatisch"></div><div><label>Passwort</label><input name="password" required></div><div><label>Anfangssaldo</label><input name="starting_balance" value="0"></div><button class="primary">Anlegen</button></form></div>
    <div class="card"><h2>Fahrer verwalten</h2><div class="table-wrap"><table><tr><th>Name</th><th>Benutzername</th><th>Anfang</th><th>Aktueller Saldo</th><th>Aktiv</th><th>Neues Passwort</th><th>Aktion</th></tr>{% for d in drivers %}<tr><form method="post"><input type="hidden" name="action" value="update"><input type="hidden" name="driver_id" value="{{ d['id'] }}"><td><input name="name" value="{{ d['name'] }}"></td><td><input name="username" value="{{ d['username'] }}"></td><td><input name="starting_balance" value="{{ fmt_signed(d['starting_balance']) }}"></td><td class="{{ signed_class(d['balance']) }} nowrap">{{ fmt_signed(d['balance']) }}</td><td><input style="width:auto" type="checkbox" name="is_active" {% if d['is_active'] %}checked{% endif %}></td><td><input name="password" placeholder="leer lassen"></td><td class="actions"><button class="small primary">Speichern</button></form><form method="post" onsubmit="return confirm('Fahrer wirklich löschen?')"><input type="hidden" name="action" value="delete"><input type="hidden" name="driver_id" value="{{ d['id'] }}"><button class="small danger">Löschen</button></form></td></tr>{% endfor %}</table></div></div>
    """, drivers=drivers, fmt_signed=fmt_signed, signed_class=signed_class)
    return base_page("Fahrer", body, "drivers")


@app.route("/admin/months", methods=["GET","POST"])
@admin_login_required
def admin_months():
    year = int(request.values.get("year") or datetime.now().year)
    month = int(request.values.get("month") or datetime.now().month)
    with db_conn() as conn:
        if request.method == "POST":
            action = request.form.get("action")
            if action in {"save", "delete", "add_adjustment", "delete_adjustment", "delete_adjustment_file"}:
                did = int(request.form["driver_id"])

                if action == "delete":
                    conn.execute("DELETE FROM monthly_data WHERE driver_id=? AND year=? AND month=?", (did, year, month))
                    recalc_driver(conn, did)
                    audit(conn, "month_delete", f"{did} {year}-{month}")
                    conn.commit()
                    flash("Monatsdatensatz gelöscht.", "ok")

                elif action == "save":
                    worked = parse_hours(request.form.get("worked_hours", "0"))
                    payroll = parse_hours(request.form.get("payroll_hours", "0"))
                    v = abs(parse_hours(request.form.get("v_hours", "0")))
                    admin_info = request.form.get("admin_info", "").strip()
                    monthly_id = get_or_create_month_row(conn, did, year, month)
                    conn.execute("UPDATE monthly_data SET worked_hours=?, payroll_hours=?, v_hours=?, admin_info=?, admin_info_carried=0, updated_at=? WHERE id=?", (worked, payroll, v, admin_info, now_iso(), monthly_id))
                    recalc_month_adjustments(conn, monthly_id)
                    recalc_driver(conn, did)
                    create_driver_pdf(conn, did, year, month)
                    audit(conn, "month_save", f"{did} {year}-{month}")
                    conn.commit()
                    flash("Stunden/Allgemeine Infos gespeichert und Fahrer-PDF automatisch aktualisiert.", "ok")

                elif action == "add_adjustment":
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
                            monthly_id = get_or_create_month_row(conn, did, year, month)
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
                            recalc_month_adjustments(conn, monthly_id)
                            recalc_driver(conn, did)
                            create_driver_pdf(conn, did, year, month)
                            audit(conn, "adjustment_add", f"{did} {year}-{month} {kind} {hours} {note}")
                            conn.commit()
                            flash("Position hinzugefügt und automatisch verrechnet.", "ok")

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
        drivers = conn.execute("SELECT * FROM drivers WHERE is_active=1 ORDER BY name COLLATE NOCASE").fetchall()
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

    body = render_template_string("""
    <div class="card">
      <form method="get" class="actions" id="month-filter-form">
        <div><label>Jahr</label><input name="year" value="{{ year }}" onchange="this.form.submit()"></div>
        <div><label>Monat</label><select name="month" onchange="this.form.submit()">{% for n,m in months.items() %}<option value="{{ n }}" {% if n==month %}selected{% endif %}>{{ m }}</option>{% endfor %}</select></div>
        <noscript><button class="primary">Anzeigen</button></noscript>
        <a class="btn" href="{{ url_for('download_month_export', year=year, month=month) }}">Monats-PDF herunterladen</a>
        <div class="download-note">Der PDF-Button lädt die Datei direkt herunter.</div>
      </form>
    </div>
    <div class="card"><h2>{{ months[month] }} {{ year }}</h2><div class="table-wrap mobile-cards"><table class="months-table">
      <thead><tr><th class="col-admin">Allgemeine Infos<br><span class="muted">nur Admin</span></th><th class="col-driver">Fahrer</th><th class="col-hours">Stunden</th><th class="col-payroll">Abrechnung</th><th class="col-v">V</th><th class="col-adjust">Zuschüsse / Abzüge</th><th class="col-small">Diff</th><th class="col-small">Alt</th><th class="col-small">Neu</th><th class="col-action">Aktion</th></tr></thead><tbody>
      {% for d in drivers %}
      {% set r = rows.get(d['id']) %}
      {% set items = adjustments.get(d['id'], []) %}
      <tr class="driver-row {{ 'row-alt' if loop.index0 % 2 else 'row-base' }}">
        <td class="admin-info" data-label="Allgemeine Infos"><textarea class="{{ 'carried' if r and r['admin_info_carried'] else '' }}" form="save-{{ d['id'] }}" name="admin_info" placeholder="Interne Infos, nur für Admin sichtbar">{{ r['admin_info'] if r else '' }}</textarea>{% if r and r['admin_info_carried'] %}<div class="download-note">aus Vormonat übernommen</div>{% endif %}</td>
        <td class="nowrap" data-label="Fahrer"><div class="mobile-row-title">{{ d['name'] }}</div><b>{{ d['name'] }}</b></td>
        <td data-label="Stunden"><form method="post" id="save-{{ d['id'] }}"><input type="hidden" name="action" value="save"><input type="hidden" name="driver_id" value="{{ d['id'] }}"><input name="worked_hours" value="{{ r['worked_hours'] if r else '' }}"></form></td>
        <td data-label="Abrechnung"><input form="save-{{ d['id'] }}" name="payroll_hours" value="{{ r['payroll_hours'] if r else '' }}"></td>
        <td data-label="V"><input form="save-{{ d['id'] }}" name="v_hours" value="{{ r['v_hours'] if r else '' }}"></td>
        <td data-label="Zuschüsse / Abzüge">
          <form method="post" class="mini-form" enctype="multipart/form-data"><input type="hidden" name="action" value="add_adjustment"><input type="hidden" name="driver_id" value="{{ d['id'] }}"><select name="kind"><option value="deduction">Abzug</option><option value="bonus">Zuschuss</option></select><input name="item_hours" placeholder="Std."><input name="item_note" placeholder="Grund, z.B. Auto dreckig"><label class="dropzone">Bild/Datei<input type="file" name="item_file" accept="image/*,.pdf"></label><button class="small primary">Hinzufügen</button></form>
          {% if r %}<div class="sum-box">Summe Zuschüsse: <span class="pos">{{ fmt_hours(r['bonus_hours']) }}</span><br>Summe Abzüge: <span class="neg">{{ fmt_hours(r['deduction_hours']) }}</span></div>{% endif %}
          <div class="adjustment-list">
          {% if items %}
            {% for it in items %}
              <div class="item-row">
                <span class="{{ 'pos' if it['kind']=='bonus' else 'neg' }}">{{ '+' if it['kind']=='bonus' else '-' }}{{ fmt_hours(it['hours']) }}</span>
                <span>{{ it['note'] }}</span>
                {% for f in adjustment_files.get(it['id'], []) %}<span class="file-pill">📎 {{ f['original_filename'] or f['filename'] }}<form method="post"><input type="hidden" name="action" value="delete_adjustment_file"><input type="hidden" name="driver_id" value="{{ d['id'] }}"><input type="hidden" name="file_id" value="{{ f['id'] }}"><button class="file-remove danger" onclick="return confirm('Bild/Datei entfernen?')">entfernen</button></form></span>{% endfor %}
                <form method="post"><input type="hidden" name="action" value="delete_adjustment"><input type="hidden" name="driver_id" value="{{ d['id'] }}"><input type="hidden" name="item_id" value="{{ it['id'] }}"><button class="small danger" onclick="return confirm('Position löschen?')">x</button></form>
              </div>
            {% endfor %}
          {% else %}
            <div class="muted">Keine Positionen</div>
          {% endif %}
          </div>
        </td>
        <td data-label="Diff" class="{{ signed_class(r['difference_hours']) if r else '' }} nowrap">{{ fmt_signed(r['difference_hours']) if r else '-' }}</td>
        <td data-label="Alt" class="nowrap">{{ fmt_signed(r['previous_balance']) if r else '-' }}</td>
        <td data-label="Neu" class="{{ signed_class(r['new_balance']) if r else '' }} nowrap">{{ fmt_signed(r['new_balance']) if r else '-' }}</td>
        <td data-label="Aktion" class="actions compact-save"><button form="save-{{ d['id'] }}" class="small primary">Speichern</button>{% if r %}<form method="post" onsubmit="return confirm('Datensatz löschen?')"><input type="hidden" name="action" value="delete"><input type="hidden" name="driver_id" value="{{ d['id'] }}"><button class="small danger delete-month-btn">Monat löschen</button></form>{% endif %}</td>
      </tr>
      {% endfor %}
    </tbody></table></div></div>
    <script>
    document.querySelectorAll('.dropzone input[type="file"]').forEach(function(input){
      var zone = input.closest('.dropzone');
      input.addEventListener('change', function(){ zone.childNodes[0].nodeValue = input.files.length ? input.files[0].name : 'Bild/Datei'; });
      ['dragenter','dragover'].forEach(function(ev){ zone.addEventListener(ev, function(e){ e.preventDefault(); zone.classList.add('dragover'); }); });
      ['dragleave','drop'].forEach(function(ev){ zone.addEventListener(ev, function(){ zone.classList.remove('dragover'); }); });
    });
    </script>
    """, year=year, month=month, months=MONATE, drivers=drivers, rows=rows, adjustments=adjustments, adjustment_files=adjustment_files, fmt_signed=fmt_signed, fmt_hours=fmt_hours, signed_class=signed_class)
    return base_page("Monatsdaten", body, "months")


@app.route("/admin/import-pdf", methods=["GET","POST"])
@admin_login_required
def admin_import_pdf():
    results: List[Dict[str,Any]] = []
    with db_conn() as conn:
        if request.method == "POST":
            f = request.files.get("file")
            if not f or not f.filename.lower().endswith(".pdf"):
                flash("Bitte eine PDF hochladen.", "err")
            else:
                tmp = DATA_ROOT / "tmp_import.pdf"; f.save(tmp)
                try:
                    entries = extract_payroll_entries_from_pdf(tmp)
                    for e in entries:
                        did, status = guess_driver_match(conn, e["name"])
                        if did and e.get("year") and e.get("month"):
                            monthly_id = get_or_create_month_row(conn, did, int(e["year"]), int(e["month"]))
                            conn.execute("UPDATE monthly_data SET v_hours=?, updated_at=? WHERE id=?", (abs(float(e["v_hours"])), now_iso(), monthly_id))
                            recalc_month_adjustments(conn, monthly_id)
                            recalc_driver(conn,did); create_driver_pdf(conn,did,e["year"],e["month"])
                            status += " · importiert"
                        results.append({**e,"driver_id":did,"status":status})
                    conn.commit(); flash(f"PDF-Import fertig: {len(results)} Einträge erkannt.", "ok")
                except Exception as ex:
                    flash(str(ex), "err")
                try: tmp.unlink()
                except Exception: pass
    body = render_template_string("""
    <div class="card"><h2>Lohn-PDF importieren</h2><p class="muted">Importiert Verpflegungszuschuss als V-Stunden, ordnet Fahrer automatisch zu und erzeugt Fahrer-PDFs neu.</p><form method="post" enctype="multipart/form-data"><input type="file" name="file" accept="application/pdf" required><button class="primary" style="margin-top:12px">Importieren</button></form></div>
    {% if results %}<div class="card"><h2>Import-Ergebnis</h2><div class="table-wrap"><table><tr><th>Seite</th><th>Name in PDF</th><th>Monat</th><th>V-Betrag</th><th>V-Stunden</th><th>Status</th></tr>{% for r in results %}<tr><td>{{ r.page }}</td><td>{{ r.name }}</td><td>{{ months.get(r.month, r.month) }} {{ r.year }}</td><td>{{ r.v_source_amount }}</td><td>{{ r.v_hours }}</td><td>{{ r.status }}</td></tr>{% endfor %}</table></div></div>{% endif %}
    """, results=results, months=MONATE)
    return base_page("PDF-Import", body, "import")


@app.get("/admin/exports")
@admin_login_required
def admin_exports():
    with db_conn() as conn:
        years = [r["year"] for r in conn.execute("SELECT DISTINCT year FROM monthly_data ORDER BY year DESC").fetchall()]
    body = render_template_string("""
    <div class="card"><h2>Export & Backup</h2><div class="actions"><a class="btn primary" href="{{ url_for('download_backup_json') }}">Backup JSON herunterladen</a><a class="btn" href="{{ url_for('download_backup_csv') }}">Monatsdaten CSV herunterladen</a></div></div>
    <div class="card"><h2>Monats-PDFs</h2><div class="driver-grid">{% for y in years %}{% for m,n in months.items() %}<a class="month-card" href="{{ url_for('download_month_export', year=y, month=m) }}"><strong>{{ n }} {{ y }}</strong>PDF herunterladen</a>{% endfor %}{% endfor %}</div></div>
    """, years=years, months=MONATE)
    return base_page("Export/Backup", body, "exports")

# ---------------- driver portal ----------------
@app.route("/login", methods=["GET","POST"])
def driver_login():
    error = ""
    if request.method == "POST":
        username = request.form.get("username", "").strip(); password = request.form.get("password", "")
        with db_conn() as conn:
            row = conn.execute("SELECT * FROM drivers WHERE lower(username)=lower(?) AND is_active=1", (username,)).fetchone()
            if not row or not check_password_hash(row["password_hash"], password):
                error = "Login fehlgeschlagen."
            else:
                session.clear(); session["driver_db_id"] = int(row["id"]); session["driver_name"] = row["name"]
                return redirect(url_for("driver_years"))
    return render_template_string("""<!doctype html><html lang="de"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Fahrer Login</title><style>{{ css }}</style></head><body><div class="login-wrap"><div class="card"><div class="title">Fahrer-Login</div><p class="muted">Hier siehst du nur deine eigenen Monatsdaten und PDFs.</p>{% if error %}<div class="flash err">{{ error }}</div>{% endif %}<form method="post"><label>Benutzername</label><input name="username" required><label style="margin-top:12px">Passwort</label><input name="password" type="password" required><button class="primary" style="margin-top:14px">Einloggen</button></form><p><a href="{{ url_for('admin_login') }}">Admin Login</a></p></div></div></body></html>""", css=BASE_CSS, error=error)


@app.get("/logout")
def driver_logout():
    session.clear()
    return redirect(url_for("driver_login"))


@app.get("/jahre")
@driver_login_required
def driver_years():
    did = int(session["driver_db_id"])
    with db_conn() as conn:
        driver = get_driver_by_db_id(conn,did)
        years = conn.execute("SELECT year, COUNT(*) cnt FROM monthly_data WHERE driver_id=? GROUP BY year ORDER BY year DESC", (did,)).fetchall()
        latest = conn.execute("SELECT new_balance FROM monthly_data WHERE driver_id=? ORDER BY year DESC, month DESC, id DESC LIMIT 1", (did,)).fetchone()
    bal = latest["new_balance"] if latest else driver["starting_balance"]
    return render_template_string("""<!doctype html><html lang="de"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Fahrerportal</title><style>{{ css }}</style></head><body><main class="main"><div class="top"><div><div class="title">Fahrerportal</div><div class="subtitle">Angemeldet als <span class="badge">{{ session['driver_name'] }}</span></div></div><a class="btn small" href="{{ url_for('driver_logout') }}">Logout</a></div><div class="card"><h2>Aktueller Stand: <span class="{{ signed_class(bal) }}">{{ fmt_signed(bal) }}</span></h2><div class="driver-grid">{% for y in years %}<a class="month-card" href="{{ url_for('driver_months_for_year', year=y['year']) }}"><strong>{{ y['year'] }}</strong>{{ y['cnt'] }} Monat(e)</a>{% endfor %}</div></div></main></body></html>""", css=BASE_CSS, years=years, bal=bal, fmt_signed=fmt_signed, signed_class=signed_class)


@app.get("/jahr/<int:year>")
@driver_login_required
def driver_months_for_year(year:int):
    did = int(session["driver_db_id"])
    with db_conn() as conn:
        rows = conn.execute("SELECT m.*, doc.id AS doc_id FROM monthly_data m LEFT JOIN documents doc ON doc.driver_id=m.driver_id AND doc.year=m.year AND doc.month=m.month WHERE m.driver_id=? AND m.year=? ORDER BY m.month", (did,year)).fetchall()
    return render_template_string("""<!doctype html><html lang="de"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{{ year }}</title><style>{{ css }}</style></head><body><main class="main"><div class="top"><div><div class="title">{{ year }}</div><div class="subtitle">{{ session['driver_name'] }}</div></div><div class="actions"><a class="btn small" href="{{ url_for('driver_years') }}">Zurück</a><a class="btn small" href="{{ url_for('driver_logout') }}">Logout</a></div></div><div class="card"><div class="driver-grid">{% for r in rows %}<a class="month-card" href="{{ url_for('driver_month_detail', year=year, month=r['month']) }}"><strong>{{ months[r['month']] }}</strong><div>Differenz: <span class="{{ signed_class(r['difference_hours']) }}">{{ fmt_signed(r['difference_hours']) }}</span></div><div>Neuer Stand: <span class="{{ signed_class(r['new_balance']) }}">{{ fmt_signed(r['new_balance']) }}</span></div></a>{% endfor %}</div></div></main></body></html>""", css=BASE_CSS, rows=rows, year=year, months=MONATE, fmt_signed=fmt_signed, signed_class=signed_class)


@app.get("/jahr/<int:year>/<int:month>")
@driver_login_required
def driver_month_detail(year:int, month:int):
    did = int(session["driver_db_id"])
    with db_conn() as conn:
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
    return render_template_string("""<!doctype html><html lang="de"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Monatsdetails</title><style>{{ css }}</style></head><body><main class="main"><div class="top"><div><div class="title">{{ months[month] }} {{ year }}</div><div class="subtitle">{{ session['driver_name'] }}</div></div><div class="actions"><a class="btn small" href="{{ url_for('driver_months_for_year', year=year) }}">Zurück</a><a class="btn small" href="{{ url_for('driver_logout') }}">Logout</a></div></div><div class="card"><div class="grid grid-3"><div class="kpi">Stunden<b>{{ fmt_hours(r['worked_hours']) }}</b></div><div class="kpi">Abrechnung<b>{{ fmt_hours(r['payroll_hours']) }}</b></div><div class="kpi">V<b>{{ fmt_hours(r['v_hours']) }}</b></div><div class="kpi">Zuschüsse<b>{{ fmt_hours(r['bonus_hours']) }}</b><span class="muted">{{ r['bonus_comment'] or '-' }}</span></div><div class="kpi">Abzüge<b>{{ fmt_hours(r['deduction_hours']) }}</b><span class="muted">{{ r['deduction_comment'] or '-' }}</span></div><div class="kpi">Differenz<b class="{{ signed_class(r['difference_hours']) }}">{{ fmt_signed(r['difference_hours']) }}</b></div><div class="kpi">Alter Stand<b>{{ fmt_signed(r['previous_balance']) }}</b></div><div class="kpi">Neuer Stand<b class="{{ signed_class(r['new_balance']) }}">{{ fmt_signed(r['new_balance']) }}</b></div></div><h3>Einzelne Zuschüsse / Abzüge</h3>{% if items %}{% for it in items %}<div class="item-row"><span class="{{ 'pos' if it['kind']=='bonus' else 'neg' }}">{{ '+' if it['kind']=='bonus' else '-' }}{{ fmt_hours(it['hours']) }}</span><span>{{ it['note'] }}</span></div>{% endfor %}{% else %}<p class="muted">Keine Positionen vorhanden.</p>{% endif %}{% if doc %}<p><a class="btn primary" style="width:auto;margin-top:14px" href="{{ url_for('download_pdf', document_id=doc['id']) }}">PDF herunterladen</a></p>{% endif %}</div></main></body></html>""", css=BASE_CSS, r=r, doc=doc, items=items, year=year, month=month, months=MONATE, fmt_hours=fmt_hours, fmt_signed=fmt_signed, signed_class=signed_class)


@app.get("/pdf/<int:document_id>")
@driver_login_required
def download_pdf(document_id:int):
    """Always regenerates the PDF before download so the driver receives the newest version."""
    did = int(session["driver_db_id"])
    with db_conn() as conn:
        doc = conn.execute("SELECT * FROM documents WHERE id=? AND driver_id=?", (document_id,did)).fetchone()
        if not doc:
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
            "drivers":[dict(r) for r in conn.execute("SELECT id,external_driver_id,name,username,starting_balance,is_active,created_at,updated_at FROM drivers").fetchall()],
            "monthly_data":[dict(r) for r in conn.execute("SELECT * FROM monthly_data").fetchall()],
            "adjustment_items":[dict(r) for r in conn.execute("SELECT * FROM adjustment_items").fetchall()],
            "adjustment_files":[dict(r) for r in conn.execute("SELECT * FROM adjustment_files").fetchall()],
            "documents":[dict(r) for r in conn.execute("SELECT * FROM documents").fetchall()],
            "created_at":now_iso()
        }
    buf = io.BytesIO(json.dumps(data, ensure_ascii=False, indent=2).encode("utf-8"))
    return send_file(buf, mimetype="application/json", as_attachment=True, download_name=f"plus_minus_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json")


@app.get("/admin/month-data.csv")
@admin_login_required
def download_backup_csv():
    with db_conn() as conn:
        rows = conn.execute("SELECT d.name,m.* FROM monthly_data m JOIN drivers d ON d.id=m.driver_id ORDER BY m.year,m.month,d.name COLLATE NOCASE").fetchall()
    out = io.StringIO(); w = csv.writer(out, delimiter=";")
    w.writerow(["Fahrer","Jahr","Monat","Allgemeine Infos nur Admin","Stunden","Abrechnung","V","Zuschuss Summe","Zuschuss Details","Abzug Summe","Abzug Details","Differenz","Alter Stand","Neuer Stand"])
    for r in rows:
        w.writerow([r["name"],r["year"],r["month"],r["admin_info"],r["worked_hours"],r["payroll_hours"],r["v_hours"],r["bonus_hours"],r["bonus_comment"],r["deduction_hours"],r["deduction_comment"],r["difference_hours"],r["previous_balance"],r["new_balance"]])
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
            final = make_unique_username(conn, username, int(existing["id"])); conn.execute("UPDATE drivers SET name=?, username=?, password_hash=?, starting_balance=?, is_active=1, updated_at=? WHERE id=?", (name,final,generate_password_hash(password),start,ts,existing["id"])); did=int(existing["id"])
        else:
            final = make_unique_username(conn, username); cur=conn.execute("INSERT INTO drivers(external_driver_id,name,username,password_hash,starting_balance,is_active,created_at,updated_at) VALUES(?,?,?,?,?,1,?,?)", (ext_id,name,final,generate_password_hash(password),start,ts,ts)); did=int(cur.lastrowid)
        recalc_driver(conn,did); conn.commit()
    return jsonify({"ok":True,"driver_db_id":did,"username":final})


@app.get("/api/admin/drivers")
def api_drivers():
    admin_api_required()
    with db_conn() as conn:
        rows = conn.execute("SELECT id, external_driver_id, name, username, starting_balance, is_active FROM drivers ORDER BY name COLLATE NOCASE").fetchall()
        return jsonify({"drivers":[dict(r) for r in rows]})


@app.get("/api/admin/month-data")
def api_month_data():
    admin_api_required()
    with db_conn() as conn:
        rows = conn.execute("SELECT d.external_driver_id,d.name,m.year,m.month,m.worked_hours AS stunden,m.payroll_hours AS abrechnung,m.v_hours AS v,m.bonus_hours AS zuschuesse,m.bonus_comment AS zuschuss_kommentar,m.deduction_hours AS abzuege,m.deduction_comment AS abzug_kommentar,m.difference_hours AS differenz,m.previous_balance AS aktueller_stand,m.new_balance AS neuer_stand FROM monthly_data m JOIN drivers d ON d.id=m.driver_id ORDER BY d.external_driver_id,m.year,m.month").fetchall()
        return jsonify({"rows":[dict(r) for r in rows]})


@app.post("/api/admin/upsert-month-data")
def api_upsert_month_data():
    admin_api_required(); p = request.get_json(force=True)
    ext = int(p["external_driver_id"]); year=int(p["year"]); month=int(p["month"])
    with db_conn() as conn:
        d = conn.execute("SELECT * FROM drivers WHERE external_driver_id=? AND is_active=1", (ext,)).fetchone()
        if not d:
            abort(400, "Fahrer nicht vorhanden")
        worked=float(p.get("worked_hours",p.get("stunden",0)) or 0); payroll=float(p.get("payroll_hours",p.get("abrechnung",0)) or 0); v=abs(float(p.get("v_hours",p.get("v",0)) or 0)); bonus=float(p.get("bonus_hours",p.get("zuschuesse",0)) or 0); deduction=float(p.get("deduction_hours",p.get("abzuege",0)) or 0)
        diff=compute_difference(worked,payroll,v,bonus,deduction); ts=now_iso(); did=int(d["id"])
        existing=conn.execute("SELECT id FROM monthly_data WHERE driver_id=? AND year=? AND month=?", (did,year,month)).fetchone()
        vals=(worked,payroll,v,bonus,str(p.get("bonus_comment",p.get("zuschuss_kommentar",'')) or ''),deduction,str(p.get("deduction_comment",p.get("abzug_kommentar",'')) or ''),bonus+deduction,str(p.get("comment",'' ) or ''),diff,ts,did,year,month)
        if existing:
            conn.execute("UPDATE monthly_data SET worked_hours=?,payroll_hours=?,v_hours=?,bonus_hours=?,bonus_comment=?,deduction_hours=?,deduction_comment=?,adjustment_hours=?,comment=?,difference_hours=?,updated_at=? WHERE driver_id=? AND year=? AND month=?", vals)
        else:
            conn.execute("INSERT INTO monthly_data(worked_hours,payroll_hours,v_hours,bonus_hours,bonus_comment,deduction_hours,deduction_comment,adjustment_hours,comment,difference_hours,updated_at,driver_id,year,month) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)", vals)
        recalc_driver(conn,did); create_driver_pdf(conn,did,year,month); conn.commit()
    return jsonify({"ok":True})


@app.post("/api/admin/upload-pdf")
def api_upload_pdf():
    admin_api_required(); ext=int(request.form["external_driver_id"]); year=int(request.form["year"]); month=int(request.form["month"]); upload=request.files.get("file")
    if not upload or not upload.filename.lower().endswith(".pdf"):
        abort(400,"PDF-Datei fehlt")
    with db_conn() as conn:
        d=conn.execute("SELECT * FROM drivers WHERE external_driver_id=? AND is_active=1", (ext,)).fetchone()
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




