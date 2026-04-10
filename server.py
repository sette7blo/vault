#!/usr/bin/env python3
"""
Vault — Self-hosted Gift Card Wallet
Backend: Flask + SQLite
"""

from flask import Flask, request, jsonify, send_from_directory, make_response
from flask_cors import CORS
import sqlite3, os, json, io, math
from PIL import Image, ImageDraw

app = Flask(__name__, static_folder=".")
CORS(app)
DB = os.environ.get("DB_PATH", "vault.db")

def get_db():
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    with get_db() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS templates (
                id          TEXT PRIMARY KEY,
                name        TEXT NOT NULL,
                col1        TEXT NOT NULL DEFAULT '#1E88E5',
                col2        TEXT,
                bg_mode     TEXT NOT NULL DEFAULT 'gradient',
                grad_dir    TEXT NOT NULL DEFAULT '↘',
                text_color  TEXT NOT NULL DEFAULT 'light',
                font_style  TEXT NOT NULL DEFAULT 'normal',
                pattern     TEXT NOT NULL DEFAULT 'none',
                created_at  TEXT DEFAULT (datetime('now'))
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS cards (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                tmpl_id     TEXT NOT NULL REFERENCES templates(id),
                card_number TEXT NOT NULL,
                pin         TEXT,
                balance     REAL NOT NULL DEFAULT 0,
                nickname    TEXT,
                barcode_fmt TEXT NOT NULL DEFAULT 'code128',
                created_at  TEXT DEFAULT (datetime('now'))
            )
        """)
        # Migration: add barcode_fmt to existing databases
        cols = [r[1] for r in conn.execute("PRAGMA table_info(cards)").fetchall()]
        if 'barcode_fmt' not in cols:
            conn.execute("ALTER TABLE cards ADD COLUMN barcode_fmt TEXT NOT NULL DEFAULT 'code128'")
        conn.execute("""
            CREATE TABLE IF NOT EXISTS transactions (
                id          TEXT PRIMARY KEY,
                card_id     INTEGER NOT NULL REFERENCES cards(id) ON DELETE CASCADE,
                amount      REAL NOT NULL,
                bal_after   REAL NOT NULL,
                note        TEXT NOT NULL DEFAULT 'Purchase',
                txn_date    TEXT NOT NULL,
                created_at  TEXT DEFAULT (datetime('now'))
            )
        """)
        conn.commit()

# ── TEMPLATES ──

@app.route("/api/templates", methods=["GET"])
def list_templates():
    with get_db() as conn:
        rows = conn.execute("SELECT * FROM templates ORDER BY created_at ASC").fetchall()
    return jsonify([dict(r) for r in rows])

@app.route("/api/templates", methods=["POST"])
def create_template():
    d = request.get_json()
    with get_db() as conn:
        conn.execute(
            "INSERT INTO templates (id,name,col1,col2,bg_mode,grad_dir,text_color,font_style,pattern) VALUES (?,?,?,?,?,?,?,?,?)",
            (d["id"], d["name"], d.get("col1","#1E88E5"), d.get("col2"),
             d.get("bgMode","gradient"), d.get("gradDir","↘"),
             d.get("textColor","light"), d.get("fontStyle","normal"), d.get("pattern","none"))
        )
        conn.commit()
        row = conn.execute("SELECT * FROM templates WHERE id=?", (d["id"],)).fetchone()
    return jsonify(dict(row)), 201

@app.route("/api/templates/<tmpl_id>", methods=["PATCH"])
def update_template(tmpl_id):
    d = request.get_json()
    fields, vals = [], []
    for k, col in [("name","name"),("col1","col1"),("col2","col2"),("bgMode","bg_mode"),("gradDir","grad_dir"),("textColor","text_color"),("fontStyle","font_style"),("pattern","pattern")]:
        if k in d: fields.append(f"{col}=?"); vals.append(d[k])
    if not fields: return jsonify({"error":"nothing to update"}), 400
    vals.append(tmpl_id)
    with get_db() as conn:
        conn.execute(f"UPDATE templates SET {', '.join(fields)} WHERE id=?", vals)
        conn.commit()
        row = conn.execute("SELECT * FROM templates WHERE id=?", (tmpl_id,)).fetchone()
    return jsonify(dict(row)) if row else (jsonify({"error":"not found"}), 404)

@app.route("/api/templates/<tmpl_id>", methods=["DELETE"])
def delete_template(tmpl_id):
    with get_db() as conn:
        n = conn.execute("SELECT COUNT(*) as n FROM cards WHERE tmpl_id=?", (tmpl_id,)).fetchone()["n"]
        if n > 0: return jsonify({"error": f"{n} card(s) use this template"}), 409
        conn.execute("DELETE FROM templates WHERE id=?", (tmpl_id,))
        conn.commit()
    return jsonify({"deleted": tmpl_id})

# ── CARDS ──

@app.route("/api/cards", methods=["GET"])
def list_cards():
    with get_db() as conn:
        rows = conn.execute("""
            SELECT c.*, (c.balance + COALESCE(SUM(t.amount), 0)) AS initial_balance
            FROM cards c
            LEFT JOIN transactions t ON t.card_id = c.id
            GROUP BY c.id
            ORDER BY c.created_at DESC
        """).fetchall()
    return jsonify([dict(r) for r in rows])

@app.route("/api/cards", methods=["POST"])
def add_card():
    d = request.get_json()
    with get_db() as conn:
        cur = conn.execute(
            "INSERT INTO cards (tmpl_id,card_number,pin,balance,nickname,barcode_fmt) VALUES (?,?,?,?,?,?)",
            (d["tmplId"], d["card_number"], d.get("pin",""), float(d.get("balance",0)), d.get("nickname",""), d.get("barcodeFormat","code128"))
        )
        conn.commit()
        row = conn.execute("SELECT * FROM cards WHERE id=?", (cur.lastrowid,)).fetchone()
    return jsonify(dict(row)), 201

@app.route("/api/cards/<int:card_id>", methods=["PATCH"])
def update_card(card_id):
    d = request.get_json()
    fields, vals = [], []
    for k in ("card_number","pin","balance","nickname"):
        if k in d: fields.append(f"{k}=?"); vals.append(d[k])
    if "tmplId" in d: fields.append("tmpl_id=?"); vals.append(d["tmplId"])
    if "barcodeFormat" in d: fields.append("barcode_fmt=?"); vals.append(d["barcodeFormat"])
    if not fields: return jsonify({"error":"nothing to update"}), 400
    vals.append(card_id)
    with get_db() as conn:
        conn.execute(f"UPDATE cards SET {', '.join(fields)} WHERE id=?", vals)
        conn.commit()
        row = conn.execute("SELECT * FROM cards WHERE id=?", (card_id,)).fetchone()
    return jsonify(dict(row)) if row else (jsonify({"error":"not found"}), 404)

@app.route("/api/cards/<int:card_id>", methods=["DELETE"])
def delete_card(card_id):
    with get_db() as conn:
        conn.execute("DELETE FROM transactions WHERE card_id=?", (card_id,))
        conn.execute("DELETE FROM cards WHERE id=?", (card_id,))
        conn.commit()
    return jsonify({"deleted": card_id})

# ── TRANSACTIONS ──

@app.route("/api/cards/<int:card_id>/transactions", methods=["GET"])
def list_transactions(card_id):
    with get_db() as conn:
        rows = conn.execute(
            "SELECT * FROM transactions WHERE card_id=? ORDER BY txn_date DESC, created_at DESC",
            (card_id,)
        ).fetchall()
    return jsonify([dict(r) for r in rows])

@app.route("/api/cards/<int:card_id>/transactions", methods=["POST"])
def add_transaction(card_id):
    d = request.get_json()
    with get_db() as conn:
        conn.execute(
            "INSERT INTO transactions (id,card_id,amount,bal_after,note,txn_date) VALUES (?,?,?,?,?,?)",
            (d["id"], card_id, float(d["amount"]), float(d["balAfter"]), d.get("note","Purchase"), d["date"])
        )
        conn.execute("UPDATE cards SET balance=? WHERE id=?", (float(d["balAfter"]), card_id))
        conn.commit()
        row = conn.execute("SELECT * FROM transactions WHERE id=?", (d["id"],)).fetchone()
    return jsonify(dict(row)), 201

@app.route("/api/transactions/<txn_id>", methods=["PATCH"])
def update_transaction(txn_id):
    d = request.get_json()
    fields, vals = [], []
    for k, col in [("amount","amount"),("balAfter","bal_after"),("note","note"),("date","txn_date")]:
        if k in d: fields.append(f"{col}=?"); vals.append(d[k])
    if not fields: return jsonify({"error":"nothing to update"}), 400
    vals.append(txn_id)
    with get_db() as conn:
        conn.execute(f"UPDATE transactions SET {', '.join(fields)} WHERE id=?", vals)
        conn.commit()
        row = conn.execute("SELECT * FROM transactions WHERE id=?", (txn_id,)).fetchone()
    return jsonify(dict(row)) if row else (jsonify({"error":"not found"}), 404)

@app.route("/api/transactions/<txn_id>", methods=["DELETE"])
def delete_transaction(txn_id):
    with get_db() as conn:
        tx = conn.execute("SELECT * FROM transactions WHERE id=?", (txn_id,)).fetchone()
        if tx:
            conn.execute("UPDATE cards SET balance = balance + ? WHERE id=?", (tx["amount"], tx["card_id"]))
        conn.execute("DELETE FROM transactions WHERE id=?", (txn_id,))
        conn.commit()
    return jsonify({"deleted": txn_id})

# ── ICONS ──

def _build_icon(size):
    """Generate vault icon PNG at given size using Pillow."""
    s = size / 180
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)

    # Gradient blue background (vertical, #1565C0 → #0D47A1 top, #42A5F5 bottom-right)
    for y in range(size):
        t = y / size
        r = int(21  + (33  - 21 ) * t)
        g = int(101 + (165 - 101) * t)
        b = int(192 + (245 - 192) * t)
        d.line([(0, y), (size - 1, y)], fill=(r, g, b, 255))

    def rr(x0, y0, x1, y1, rad, fill, outline=None, ow=1):
        d.rounded_rectangle([x0, y0, x1, y1], radius=rad, fill=fill, outline=outline, width=ow)

    W = (255, 255, 255)

    # ── Back card (offset top-right, darker) ──
    bx, by = int(35*s), int(28*s)
    bw, bh = int(122*s), int(76*s)
    rr(bx, by, bx+bw, by+bh, int(9*s), (10, 42, 110, 170))
    # Back card stripe
    d.rectangle([bx, by+int(24*s), bx+bw, by+int(38*s)], fill=(6, 20, 55, 90))

    # ── Front card ──
    fx, fy = int(8*s), int(62*s)
    fw, fh = int(130*s), int(82*s)
    rr(fx, fy, fx+fw, fy+fh, int(10*s), (30, 86, 176, 255))
    # Front card stripe
    d.rectangle([fx, fy+int(24*s), fx+fw, fy+int(38*s)], fill=(6, 18, 60, 100))
    # EMV chip hint
    rr(fx+int(10*s), fy+int(48*s), fx+int(34*s), fy+int(70*s), int(4*s),
       (255,255,255,50), outline=(255,255,255,80), ow=max(1,int(1.5*s)))

    # ── Vault combination dial ──
    dcx, dcy = int(118*s), int(103*s)
    # Outer guide ring (very faint)
    r_out = int(38*s)
    d.ellipse([dcx-r_out, dcy-r_out, dcx+r_out, dcy+r_out],
              outline=(255,255,255,38), width=max(1,int(s)))

    # 8 tick marks
    r_t_out, r_t_in = int(36*s), int(29*s)
    for i, (heavy, angle_deg) in enumerate([(True,0),(False,45),(True,90),(False,135),
                                             (True,180),(False,225),(True,270),(False,315)]):
        a = math.radians(angle_deg - 90)
        x1 = dcx + r_t_out * math.cos(a);  y1 = dcy + r_t_out * math.sin(a)
        x2 = dcx + r_t_in  * math.cos(a);  y2 = dcy + r_t_in  * math.sin(a)
        alpha = 150 if heavy else 80
        d.line([(x1, y1), (x2, y2)], fill=(255,255,255,alpha), width=max(1, int((2 if heavy else 1.2)*s)))

    # Main ring
    r_main = int(30*s)
    d.ellipse([dcx-r_main, dcy-r_main, dcx+r_main, dcy+r_main],
              outline=(255,255,255,195), width=max(2,int(3*s)))

    # Inner ring
    r_inner = int(16*s)
    d.ellipse([dcx-r_inner, dcy-r_inner, dcx+r_inner, dcy+r_inner],
              outline=(255,255,255,110), width=max(1,int(1.5*s)))

    # Center hub
    r_hub = int(7*s)
    d.ellipse([dcx-r_hub, dcy-r_hub, dcx+r_hub, dcy+r_hub], fill=(255,255,255,210))

    # Indicator dot at 12 o'clock on main ring
    ind_y = dcy - r_main - int(1*s)
    r_ind = int(5*s)
    d.ellipse([dcx-r_ind, ind_y-r_ind, dcx+r_ind, ind_y+r_ind], fill=(255,255,255,240))

    return img


@app.route("/favicon.svg")
def favicon_svg():
    # Square SVG icon (used by browsers for the tab)
    svg = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 180 180">
  <defs>
    <linearGradient id="bg" x1="0" y1="0" x2="1" y2="1">
      <stop offset="0%" stop-color="#1565C0"/>
      <stop offset="100%" stop-color="#42A5F5"/>
    </linearGradient>
  </defs>
  <rect width="180" height="180" rx="36" fill="url(#bg)"/>
  <!-- back card -->
  <rect x="35" y="28" width="122" height="76" rx="9" fill="#0A2A6E" opacity=".68"/>
  <rect x="35" y="52" width="122" height="14" fill="#061535" opacity=".35"/>
  <!-- front card -->
  <rect x="8" y="62" width="130" height="82" rx="10" fill="#1E56B0"/>
  <rect x="8" y="86" width="130" height="14" fill="#06123C" opacity=".38"/>
  <!-- chip -->
  <rect x="18" y="110" width="24" height="22" rx="4" fill="rgba(255,255,255,.18)" stroke="rgba(255,255,255,.3)" stroke-width="1.5"/>
  <!-- outer guide -->
  <circle cx="118" cy="103" r="38" fill="none" stroke="white" stroke-width="1" opacity=".15"/>
  <!-- ticks N/E/S/W -->
  <g stroke="white" stroke-linecap="round" stroke-width="2.5" opacity=".6">
    <line x1="118" y1="65"  x2="118" y2="74"/>
    <line x1="156" y1="103" x2="147" y2="103"/>
    <line x1="118" y1="141" x2="118" y2="132"/>
    <line x1="80"  y1="103" x2="89"  y2="103"/>
  </g>
  <!-- ordinal ticks -->
  <g stroke="white" stroke-linecap="round" stroke-width="1.5" opacity=".32">
    <line x1="144.9" y1="76.1" x2="138.9" y2="82.1"/>
    <line x1="144.9" y1="129.9" x2="138.9" y2="123.9"/>
    <line x1="91.1" y1="129.9" x2="97.1" y2="123.9"/>
    <line x1="91.1" y1="76.1"  x2="97.1" y2="82.1"/>
  </g>
  <!-- main ring -->
  <circle cx="118" cy="103" r="30" fill="rgba(255,255,255,.07)" stroke="white" stroke-width="3" opacity=".78"/>
  <!-- inner ring -->
  <circle cx="118" cy="103" r="16" fill="rgba(255,255,255,.1)" stroke="white" stroke-width="1.5" opacity=".45"/>
  <!-- hub -->
  <circle cx="118" cy="103" r="7" fill="white" opacity=".82"/>
  <!-- indicator -->
  <circle cx="118" cy="72" r="5" fill="white" opacity=".95"/>
</svg>"""
    resp = make_response(svg)
    resp.headers["Content-Type"] = "image/svg+xml"
    resp.headers["Cache-Control"] = "public, max-age=86400"
    return resp


@app.route("/apple-touch-icon.png")
@app.route("/apple-touch-icon-precomposed.png")
def apple_touch_icon():
    img = _build_icon(180)
    # Paste onto white background (iOS expects no transparency)
    bg = Image.new("RGB", (180, 180), (21, 101, 192))
    bg.paste(img, mask=img.split()[3])
    buf = io.BytesIO()
    bg.save(buf, format="PNG", optimize=True)
    buf.seek(0)
    resp = make_response(buf.read())
    resp.headers["Content-Type"] = "image/png"
    resp.headers["Cache-Control"] = "public, max-age=86400"
    return resp


@app.route("/icon-512.png")
def icon_512():
    img = _build_icon(512)
    bg = Image.new("RGB", (512, 512), (21, 101, 192))
    bg.paste(img, mask=img.split()[3])
    buf = io.BytesIO()
    bg.save(buf, format="PNG", optimize=True)
    buf.seek(0)
    resp = make_response(buf.read())
    resp.headers["Content-Type"] = "image/png"
    resp.headers["Cache-Control"] = "public, max-age=86400"
    return resp


# ── STATIC ──

@app.route("/")
def index():
    with get_db() as conn:
        templates = [dict(r) for r in conn.execute("SELECT * FROM templates ORDER BY created_at ASC").fetchall()]
        cards     = [dict(r) for r in conn.execute("""
            SELECT c.*, (c.balance + COALESCE(SUM(t.amount), 0)) AS initial_balance
            FROM cards c
            LEFT JOIN transactions t ON t.card_id = c.id
            GROUP BY c.id
            ORDER BY c.created_at DESC
        """).fetchall()]
    init_json = json.dumps({"templates": templates, "cards": cards})
    with open(os.path.join(app.static_folder, "index.html"), "r") as f:
        html = f.read()
    html = html.replace("</head>", f'<script>window.__VAULT_INIT__={init_json};</script>\n</head>', 1)
    resp = make_response(html)
    resp.headers["Content-Type"] = "text/html; charset=utf-8"
    resp.headers["Cache-Control"] = "no-store, no-cache, must-revalidate"
    return resp

if __name__ == "__main__":
    init_db()
    print("\n  Vault is running → http://localhost:8080\n")
    app.run(host="0.0.0.0", port=8080)
