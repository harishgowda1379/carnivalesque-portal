from flask import Flask, render_template, request, jsonify, session, redirect, send_file
from flask_wtf.csrf import CSRFProtect
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from werkzeug.security import generate_password_hash, check_password_hash
import bcrypt
import portalocker
import pandas as pd
import json
import os
import secrets
import threading
import time
from functools import wraps
import qrcode
from io import BytesIO
from datetime import datetime

app = Flask(__name__)
app.secret_key = secrets.token_hex(32)
csrf = CSRFProtect(app)
limiter = Limiter(
    app=app,
    key_func=get_remote_address,
    default_limits=["100 per minute"]
)

# ---------------- CONFIG ---------------- #

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# QR Code Base URL - Set this to your server's IP/domain for mobile access
# Leave as None to auto-detect, or set manually like: "http://192.168.1.100:5000"
QR_CODE_BASE_URL = os.environ.get('QR_CODE_BASE_URL', None)

EXCEL_PATH = os.path.join(BASE_DIR, "data", "registrations.xlsx")
COLUMN_MAP_PATH = os.path.join(BASE_DIR, "data", "column_map.json")
STATUS_PATH = os.path.join(BASE_DIR, "data", "status.json")
EVENT_CODES_PATH = os.path.join(BASE_DIR, "data", "event_codes.json")
EVENT_RATINGS_PATH = os.path.join(BASE_DIR, "data", "event_ratings.json")

# Simple passwords (plaintext) - for immediate functionality
USERS = {
    "register": {"password": "reg123", "role": "register"},
    "coordinator": {"password": "coord123", "role": "coordinator"},
    "certificate": {"password": "cert123", "role": "certificate"},
    "admin": {"password": "admin123", "role": "admin"},
    "superadmin": {"password": "super123", "role": "super_admin"}
}

# Event Team Requirements (Min/Max team members)
EVENT_TEAM_REQUIREMENTS = {
    # 5 Star Events
    "Fashion Walk": {"min": 10, "max": 12},
    "Football - Men": {"min": 7, "max": 12},
    
    # 4 Star Events
    "Battle of Bands": {"min": 8, "max": 10},
    "Group Dance": {"min": 8, "max": 10},
    "Throw Ball - M&W": {"min": 9, "max": 12},
    "Kabaddi - M&W": {"min": 7, "max": 12},
    "Tug of War - M&W": {"min": 8, "max": 10},
    "Volley Ball - Men": {"min": 6, "max": 9},
    "Group Singing": {"min": 6, "max": 8},
    "Mime": {"min": 6, "max": 8},
    
    # 2 Star Events
    "IPL Auction": {"min": 3, "max": 3},
    "Synergy Squad": {"min": 3, "max": 3},
    "Decrypt-X": {"min": 2, "max": 2},
    "Treasure Hunt": {"min": 3, "max": 3},
    "Murder Mystery": {"min": 4, "max": 4},
    "Film Quiz": {"min": 3, "max": 3},
    "DANCE BATTLE": {"min": 1, "max": 1},
    "Duet Dance": {"min": 2, "max": 2},
    "Cosplay": {"min": 1, "max": 1},
    "Reel Making": {"min": 2, "max": 2},
    "BGMI": {"min": 4, "max": 4},
    "COD Mobile": {"min": 4, "max": 4},
    
    # 1 Star Events
    "Solo Singing": {"min": 1, "max": 1},
    "Solo Instrumental": {"min": 1, "max": 1},
    "Solo Dance": {"min": 1, "max": 1},
    "Mono Act": {"min": 1, "max": 1},
    "Mehendi": {"min": 1, "max": 1},
    "Face Painting": {"min": 1, "max": 1},
    "Pencil Sketching": {"min": 1, "max": 1},
    "Photography": {"min": 1, "max": 1},
    "SHORT FILM REVIEW": {"min": 1, "max": 1},
    "JAM - JUST A MINUTE": {"min": 1, "max": 1},
    "Carrom -  M&W": {"min": 1, "max": 1},
    "Chess - M&W": {"min": 1, "max": 1},
    "FC26": {"min": 1, "max": 1}
}

# Default Event Access Codes (6-character alphanumeric)
# Event codes for all events (matching user's exact list)
DEFAULT_EVENT_CODES = {
    # 5 Star Events
    "Fashion Walk": "FASHWK",
    "Football - Men": "FTBMEN",
    
    # 4 Star Events
    "Battle of Bands": "BATBND",
    "Group Dance": "GRPDNC",
    "Throw Ball - M&W": "THBLLM",
    "Kabaddi - M&W": "KABDMW",
    "Tug of War - M&W": "TUGWMW",
    "Volley Ball - Men": "VOLBMN",
    "Group Singing": "GRPSNG",
    "Mime": "MIME",
    
    # 2 Star Events
    "IPL Auction": "IPLAUC",
    "Synergy Squad": "SYNSQD",
    "Decrypt-X": "DECRYX",
    "Treasure Hunt": "TRESHT",
    "Murder Mystery": "MURMYS",
    "Film Quiz": "FILMQZ",
    "DANCE BATTLE": "DNCBTL",
    "Duet Dance": "DUETDC",
    "Cosplay": "COSPLY",
    "Reel Making": "REELMK",
    "BGMI": "BGMIES",
    "COD Mobile": "CODMBL",
    
    # 1 Star Events
    "Solo Singing": "SOLOSG",
    "Solo Instrumental": "SOLINS",
    "Solo Dance": "SOLODC",
    "Mono Act": "MONACT",
    "Mehendi": "MEHEND",
    "Face Painting": "FACEPT",
    "Pencil Sketching": "PENSKT",
    "Photography": "PHOTOG",
    "SHORT FILM REVIEW": "SHTFLR",
    "JAM - JUST A MINUTE": "JAMMIN",
    "Carrom -  M&W": "CARROMW",
    "Chess - M&W": "CHSSMW",
    "FC26": "FC26GM"
}

# ---------------- SECURITY DECORATORS ---------------- #

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'role' not in session:
            return jsonify({"error": "Authentication required"}), 401
        return f(*args, **kwargs)
    return decorated_function

def role_required(*allowed_roles):
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if 'role' not in session:
                return jsonify({"error": "Authentication required"}), 401
            if session['role'] not in allowed_roles:
                return jsonify({"error": "Insufficient permissions"}), 403
            return f(*args, **kwargs)
        return decorated_function
    return decorator

def page_role_required(*allowed_roles):
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if 'role' not in session or session['role'] not in allowed_roles:
                return redirect('/')
            return f(*args, **kwargs)
        return decorated_function
    return decorator

# ---------------- UTILITIES ---------------- #

def load_excel():
    return pd.read_excel(EXCEL_PATH)

def load_column_map():
    if not os.path.exists(COLUMN_MAP_PATH):
        return None
    with open(COLUMN_MAP_PATH, "r") as f:
        return json.load(f)

def save_column_map(data):
    with portalocker.Lock(COLUMN_MAP_PATH, 'w') as f:
        json.dump(data, f, indent=4)

def load_status():
    if not os.path.exists(STATUS_PATH):
        with open(STATUS_PATH, "w") as f:
            json.dump({}, f)
        return {}

    try:
        with open(STATUS_PATH, "r") as f:
            content = f.read().strip()
            return json.loads(content) if content else {}
    except json.JSONDecodeError:
        with open(STATUS_PATH, "w") as f:
            json.dump({}, f)
        return {}

def save_status(data):
    with portalocker.Lock(STATUS_PATH, 'w') as f:
        json.dump(data, f, indent=4)

def load_event_codes():
    # Load codes from file, or initialize with defaults
    if not os.path.exists(EVENT_CODES_PATH):
        # If file doesn't exist, initialize with default codes
        if DEFAULT_EVENT_CODES:
            save_event_codes(DEFAULT_EVENT_CODES.copy())
        return DEFAULT_EVENT_CODES.copy()
    
    try:
        with open(EVENT_CODES_PATH, "r") as f:
            content = f.read().strip()
            file_codes = json.loads(content) if content else {}
            
            # Merge with defaults: file codes take precedence, but add any missing defaults
            merged_codes = DEFAULT_EVENT_CODES.copy()
            merged_codes.update(file_codes)
            
            # If defaults were added, save the merged version
            if merged_codes != file_codes:
                save_event_codes(merged_codes)
            
            return merged_codes
    except json.JSONDecodeError:
        # If file is corrupted, use defaults
        if DEFAULT_EVENT_CODES:
            save_event_codes(DEFAULT_EVENT_CODES.copy())
        return DEFAULT_EVENT_CODES.copy()

def save_event_codes(data):
    with portalocker.Lock(EVENT_CODES_PATH, 'w') as f:
        json.dump(data, f, indent=4)

def load_event_ratings():
    if not os.path.exists(EVENT_RATINGS_PATH):
        return {}
    try:
        with open(EVENT_RATINGS_PATH, "r") as f:
            content = f.read().strip()
            return json.loads(content) if content else {}
    except json.JSONDecodeError:
        return {}

def save_event_ratings(data):
    with portalocker.Lock(EVENT_RATINGS_PATH, 'w') as f:
        json.dump(data, f, indent=4)

# Points system based on star rating
POINTS_SYSTEM = {
    5: {"1st": 80, "2nd": 75, "3rd": 70},
    4: {"1st": 75, "2nd": 70, "3rd": 65},
    3: {"1st": 70, "2nd": 65, "3rd": 60},
    2: {"1st": 65, "2nd": 60, "3rd": 55},
    1: {"1st": 60, "2nd": 55, "3rd": 50}
}

# ---------------- TEAM EXTRACTION ---------------- #

def extract_team(row, mapping):
    team = []
    seen = set()

    leader_col = mapping.get("team_leader")
    if leader_col and pd.notna(row.get(leader_col)):
        leader = str(row[leader_col]).strip()
        if leader.lower() not in seen:
            team.append(leader)
            seen.add(leader.lower())

    for col in mapping.get("team_members", []):
        if col in row and pd.notna(row[col]):
            member = str(row[col]).strip()
            if member.lower() not in seen:
                team.append(member)
                seen.add(member.lower())

    return team

# ---------------- TEAM OVERRIDES ---------------- #

def get_team_for_reg(reg_no, row, mapping, status):
    """
    Returns team list for a registration number.
    Priority:
      1) status[reg_no]['team_override'] if present and non-empty
      2) extracted team from Excel row
    """
    try:
        override = status.get(reg_no, {}).get("team_override")
        if isinstance(override, list) and len([x for x in override if str(x).strip()]) > 0:
            # normalize + drop blanks
            out = []
            seen = set()
            for name in override:
                name = str(name).strip()
                if not name:
                    continue
                key = name.lower()
                if key in seen:
                    continue
                seen.add(key)
                out.append(name)
            return out
    except Exception:
        pass

    try:
        return extract_team(row, mapping) if row is not None else []
    except Exception:
        return []

# ---------------- ROUTES ---------------- #

@app.route("/")
def login_page():
    return render_template("login.html")

@app.route("/login", methods=["POST"])
@limiter.limit("5 per minute")
def login():
    # ---------------- DEBUG ----------------
    print("====== LOGIN REQUEST ======")
    print("Method:", request.method)
    print("Headers:", dict(request.headers))
    print("Form:", request.form)
    print("JSON:", request.get_json(silent=True))
    print("Raw data:", request.data)
    print("===========================")

    # -------- ACCEPT JSON OR FORM ----------
    data = request.get_json(silent=True)
    if not data:
        data = request.form

    username = (data.get("username") or "").strip()
    password = (data.get("password") or "").strip()

    print(f"Username received: '{username}'")
    print(f"Password received: '{password}'")
    print("Available users:", list(USERS.keys()))

    # -------- VALIDATION ----------
    if not username or not password:
        print("❌ Missing credentials")
        return jsonify({
            "success": False,
            "error": "Username and password required"
        }), 400

    user = USERS.get(username)
    print("User found:", bool(user))

    if not user:
        print("❌ Username not found")
        return jsonify({
            "success": False,
            "error": "Invalid username or password"
        }), 401

    print("Stored password:", user["password"])
    print("Password match:", user["password"] == password)

    # -------- PASSWORD CHECK ----------
    if user["password"] != password:
        print("❌ Password mismatch")
        return jsonify({
            "success": False,
            "error": "Invalid username or password"
        }), 401

    # -------- LOGIN SUCCESS ----------
    session.clear()                     # 🔑 IMPORTANT
    session["logged_in"] = True
    session["username"] = username
    session["role"] = user["role"]
    session.permanent = True

    print(f"✅ LOGIN SUCCESS | Role: {user['role']}")

    return jsonify({
        "success": True,
        "role": user["role"]
    }), 200

# ---------- PAGE ROUTES ---------- #

@app.route("/register-desk")
@page_role_required("register")
def register_desk_page():
    return render_template("register_desk.html")



@app.route("/certificate")
@page_role_required("certificate")
def certificate_page():
    return render_template("certificate.html")

@app.route("/admin")
@page_role_required("admin")
def admin_page():
    return render_template("admin.html")

@app.route("/super-admin")
@page_role_required("super_admin")
def super_admin_page():
    return render_template("super_admin.html")

@app.route("/coordinator")
def coordinator_page():
    return render_template("coordinator.html")

# ---------- ADMIN APIs ---------- #

@app.route("/get_excel_columns")
@login_required
def get_excel_columns():
    df = load_excel()
    return jsonify(df.columns.tolist())

@app.route("/save_column_map", methods=["POST"])
@role_required("admin")
def save_mapping():
    save_column_map(request.json)
    return jsonify({"success": True})

@app.route("/set_event_code", methods=["POST"])
@role_required("admin")
def set_event_code():
    event = request.json.get("event")
    code = request.json.get("code")
    
    if not event or not code:
        return jsonify({"error": "Event and code are required"})
    
    if len(code) != 6:
        return jsonify({"error": "Code must be exactly 6 characters"})
    
    event_codes = load_event_codes()
    event_codes[event] = code.upper()
    save_event_codes(event_codes)
    return jsonify({"success": True})

@csrf.exempt
@app.route("/get_events")
def get_events():
    try:
        df = load_excel()
        mapping = load_column_map()

        if not mapping or "event" not in mapping:
            return jsonify([])

        return jsonify(df[mapping["event"]].dropna().unique().tolist())
    except Exception as e:
        print("GET_EVENTS ERROR:", e)
        return jsonify([])

@csrf.exempt
@app.route("/get_event_requirements")
def get_event_requirements():
    """Get min/max team requirements for an event"""
    event = request.args.get("event") or (request.json.get("event") if request.is_json else None)
    if not event:
        return jsonify({"error": "Event name required"}), 400
    
    event = event.strip()
    
    # Try exact match first
    requirements = EVENT_TEAM_REQUIREMENTS.get(event)
    
    # If not found, try case-insensitive match
    if not requirements:
        event_lower = event.lower()
        for key, value in EVENT_TEAM_REQUIREMENTS.items():
            if key.lower() == event_lower:
                requirements = value
                print(f"Matched '{event}' to '{key}' (case-insensitive)")
                break
    
    # If still not found, use default (ALWAYS return something so fields show)
    if not requirements:
        requirements = {"min": 1, "max": 20}
        print(f"Event '{event}' not found in requirements, using default min=1, max=20")
    else:
        print(f"Found requirements for '{event}': {requirements}")
    
    return jsonify(requirements)


@app.route("/init_event_codes", methods=["POST"])
@role_required("admin")
def init_event_codes():
    """Initialize event codes from Excel events"""
    try:
        df = load_excel()
        mapping = load_column_map()
        if not mapping:
            return jsonify({"error": "Column mapping not set"})
        
        events = df[mapping["event"]].dropna().unique().tolist()
        event_codes = load_event_codes()
        
        import random
        import string
        new_codes = {}
        
        for event in events:
            if event not in event_codes:
                # Generate a code if not exists
                code = ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))
                event_codes[event] = code
                new_codes[event] = code
        
        if new_codes:
            save_event_codes(event_codes)
            return jsonify({"success": True, "new_codes": new_codes, "message": f"Generated {len(new_codes)} new codes"})
        else:
            return jsonify({"success": True, "message": "All events already have codes"})
    except Exception as e:
        return jsonify({"error": str(e)})

# ✅ EVENT-WISE ADMIN DASHBOARD
@app.route("/admin_dashboard")
def admin_dashboard():
    df = load_excel()
    mapping = load_column_map()
    status = load_status()

    events = {}

    for reg_no, data in status.items():
        event = data.get("event")
        if not event:
            continue

        events.setdefault(event, {
            "event_started": False,
            "event_ended": False,
            "winners": {}
        })

        if data.get("event_started"):
            events[event]["event_started"] = True

        if data.get("event_ended"):
            events[event]["event_ended"] = True

        if "position" in data:
            row = df[df[mapping["reg_no"]] == reg_no]
            team = []
            if not row.empty:
                team = extract_team(row.iloc[0], mapping)

            events[event]["winners"][data["position"]] = {
                "reg_no": reg_no,
                "team": team
            }

    return jsonify(events)

# ---------- REGISTRATION DESK ---------- #

from flask_wtf.csrf import CSRFProtect

@csrf.exempt
@app.route("/get_registration", methods=["POST"])
def get_registration():
    data = request.get_json(silent=True)
    if not data:
        return jsonify({"error": "No data received"}), 400

    reg_no = data.get("regNo") or data.get("reg_no")
    if not reg_no:
        return jsonify({"error": "Registration number missing"}), 400

    df = load_excel()
    mapping = load_column_map()
    status = load_status()

    row = df[df[mapping["reg_no"]] == reg_no]
    if row.empty:
        return jsonify({"error": "Not found"}), 404

    row = row.iloc[0]
    team = get_team_for_reg(reg_no, row, mapping, status)

    return jsonify({
        "success": True,
        "event": row[mapping["event"]],
        "college": row[mapping["college"]],
        "team": team,
        "team_size": len(team)
    })




@csrf.exempt
@app.route("/update_team_members", methods=["POST"])
def update_team_members():
    reg_no = request.json.get("reg_no")
    team = request.json.get("team")

    if not reg_no:
        return jsonify({"error": "reg_no is required"})
    if not isinstance(team, list):
        return jsonify({"error": "team must be a list"})

    # normalize + validate
    cleaned = []
    seen = set()
    for name in team:
        name = str(name).strip()
        if not name:
            continue
        key = name.lower()
        if key in seen:
            continue
        seen.add(key)
        cleaned.append(name)

    if len(cleaned) == 0:
        return jsonify({"error": "At least one team member name is required"})
    if len(cleaned) > 20:
        return jsonify({"error": "Maximum 20 team members allowed"})

    df = load_excel()
    mapping = load_column_map()
    if not mapping:
        return jsonify({"error": "Column mapping not set. Please contact admin."})

    row = df[df[mapping["reg_no"]] == reg_no]
    if row.empty:
        return jsonify({"error": "Registration not found"})

    row0 = row.iloc[0]
    event = row0[mapping["event"]]

    status = load_status()
    status.setdefault(reg_no, {})
    # keep event in status for consistency
    status[reg_no]["event"] = event
    status[reg_no]["team_override"] = cleaned
    save_status(status)

    return jsonify({"success": True, "team_size": len(cleaned)})

@csrf.exempt
@app.route("/mark_reported", methods=["POST"])
def mark_reported():
    reg_no = request.json["reg_no"]

    df = load_excel()
    mapping = load_column_map()
    status = load_status()

    row = df[df[mapping["reg_no"]] == reg_no]
    if row.empty:
        return jsonify({"error": "Registration not found"})

    event = row.iloc[0][mapping["event"]]

    # 🔒 EVENT LOCK CHECK
    for s in status.values():
        if s.get("event") == event and s.get("event_ended"):
            return jsonify({"error": "Event already completed. Reporting locked."})

    status.setdefault(reg_no, {})
    status[reg_no].update({
        "event": event,
        "reported": True,
        "event_started": False,
        "event_ended": False
    })

    save_status(status)
    return jsonify({"success": True})

# ---------- EVENT COORDINATOR ---------- #

def event_verified_required(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        data = request.get_json(silent=True) or {}
        event = data.get("event")

        if not event or session.get("verified_event") != event:
            return jsonify({"error": "Event not verified"}), 403

        return f(*args, **kwargs)
    return wrapper


# --------------------------------------------------
# 📌 GET EVENTS (PUBLIC)
# --------------------------------------------------
# --------------------------------------------------
# 🔑 VERIFY EVENT ACCESS CODE
# --------------------------------------------------
@csrf.exempt
@app.route("/verify_event_code", methods=["POST"])
@limiter.limit("10 per minute")
def verify_event_code():
    data = request.get_json(silent=True) or {}
    event = data.get("event")
    code = data.get("code")

    if not event or not code:
        return jsonify({"success": False, "error": "Event and code required"}), 400

    event_codes = load_event_codes()

    if event not in event_codes:
        return jsonify({"success": False, "error": "Event code not configured"}), 400

    if event_codes[event].upper() == code.upper():
        session["verified_event"] = event   # 🔐 LOCK EVENT
        return jsonify({"success": True})

    return jsonify({"success": False, "error": "Invalid code"}), 401


# --------------------------------------------------
# 📋 GET REPORTED TEAMS (PROTECTED)
# --------------------------------------------------
@csrf.exempt
@event_verified_required
@app.route("/get_reported_teams", methods=["POST"])
def get_reported_teams():
    data = request.get_json(silent=True) or {}
    event = data.get("event")

    df = load_excel()
    mapping = load_column_map()
    status = load_status()

    result = []
    event_started = False

    for reg_no, info in status.items():
        if info.get("reported") and info.get("event") == event:
            event_started |= info.get("event_started", False)

            row = df[df[mapping["reg_no"]] == reg_no]
            if row.empty:
                continue

            team = get_team_for_reg(reg_no, row.iloc[0], mapping, status)

            college = ""
            if mapping.get("college") and mapping["college"] in row.iloc[0]:
                college = str(row.iloc[0][mapping["college"]])

            # Extract contact/phone number from Excel
            contact = ""
            row_data = row.iloc[0]
            
            # Try to find contact/phone column in mapping first
            if mapping.get("contact"):
                contact_col = mapping["contact"]
                if contact_col in row_data and pd.notna(row_data[contact_col]):
                    contact = str(row_data[contact_col]).strip()
            
            # If not in mapping, try to find by column name pattern
            if not contact:
                for col in df.columns:
                    col_lower = str(col).lower()
                    if any(keyword in col_lower for keyword in ["contact", "phone", "mobile", "number"]):
                        if col in row_data and pd.notna(row_data[col]):
                            contact = str(row_data[col]).strip()
                            break

            result.append({
                "reg_no": reg_no,
                "team": team,
                "team_size": len(team),
                "college": college,
                "contact": contact
            })

    return jsonify({"teams": result, "event_started": event_started})


# --------------------------------------------------
# ▶ START EVENT (PROTECTED)
# --------------------------------------------------
@csrf.exempt
@event_verified_required
@app.route("/start_event", methods=["POST"])
def start_event():
    data = request.get_json(silent=True) or {}
    event = data.get("event")

    status = load_status()

    # Block restart if already completed
    for s in status.values():
        if s.get("event") == event and s.get("event_ended"):
            return jsonify({"error": "Event already completed"}), 400

    for reg in status:
        if status[reg].get("event") == event:
            status[reg]["event_started"] = True

    save_status(status)
    return jsonify({"success": True})


# --------------------------------------------------
# 🏁 END EVENT & ASSIGN WINNERS (PROTECTED)
# --------------------------------------------------
@csrf.exempt
@event_verified_required
@app.route("/end_event", methods=["POST"])
def end_event():
    data = request.get_json(silent=True) or {}
    winners = data.get("winners", {})

    if not winners:
        return jsonify({"error": "No winners selected"}), 400

    status = load_status()
    first_reg = next(iter(winners))
    event = status.get(first_reg, {}).get("event")

    if not event:
        return jsonify({"error": "Invalid winner data"}), 400

    # Block duplicate ending
    for s in status.values():
        if s.get("event") == event and s.get("event_ended"):
            return jsonify({"error": "Event already completed"}), 400

    for reg_no, pos in winners.items():
        status[reg_no]["event_ended"] = True
        status[reg_no]["position"] = pos

    save_status(status)
    return jsonify({"success": True})


# ---------- CERTIFICATE TEAM ---------- #

@csrf.exempt
@app.route("/completed_events")
def completed_events():
    status = load_status()
    completed = {}
    
    try:
        df = load_excel()
        mapping = load_column_map()
    except:
        df = None
        mapping = None
    
    for reg_no, data in status.items():
        if data.get("event_ended"):
            team = []
            
            if df is not None and not df.empty and mapping and mapping.get("reg_no"):
                try:
                    row = df[df[mapping["reg_no"]] == reg_no]
                    if not row.empty:
                        team = get_team_for_reg(reg_no, row.iloc[0], mapping, status)
                except:
                    team = []
            
            completed[reg_no] = {
                "event": data.get("event", ""),
                "position": data.get("position"),
                "team": team
            }
    
    return jsonify(completed)

# ---------- SUPER ADMIN APIs ---------- #

@app.route("/get_event_ratings")
def get_event_ratings():
    return jsonify(load_event_ratings())

@app.route("/set_event_rating", methods=["POST"])
def set_event_rating():
    event = request.json.get("event")
    rating = request.json.get("rating")
    
    if not event:
        return jsonify({"error": "Event name is required"})
    
    if rating not in [1, 2, 3, 4, 5]:
        return jsonify({"error": "Rating must be between 1 and 5"})
    
    ratings = load_event_ratings()
    ratings[event] = rating
    save_event_ratings(ratings)
    return jsonify({"success": True})

@app.route("/super_admin_dashboard")
def super_admin_dashboard():
    df = load_excel()
    mapping = load_column_map()
    status = load_status()
    ratings = load_event_ratings()

    events = {}

    for reg_no, data in status.items():
        event = data.get("event")
        if not event:
            continue

        events.setdefault(event, {
            "event_started": False,
            "event_ended": False,
            "winners": {},
            "rating": ratings.get(event, 3)  # Default to 3 stars
        })

        if data.get("event_started"):
            events[event]["event_started"] = True

        if data.get("event_ended"):
            events[event]["event_ended"] = True

        if "position" in data:
            row = df[df[mapping["reg_no"]] == reg_no]
            team = []
            college = ""
            if not row.empty:
                row0 = row.iloc[0]
                team = extract_team(row0, mapping)
                try:
                    if mapping.get("college") and mapping["college"] in row0:
                        college = str(row0[mapping["college"]]) if pd.notna(row0[mapping["college"]]) else ""
                except Exception:
                    college = ""

            events[event]["winners"][data["position"]] = {
                "reg_no": reg_no,
                "team": team,
                "college": college
            }

    return jsonify(events)

@app.route("/calculate_champion")
def calculate_champion():
    status = load_status()
    ratings = load_event_ratings()
    df = load_excel()
    mapping = load_column_map()
    
    college_points = {}
    
    for reg_no, data in status.items():
        if not data.get("event_ended") or "position" not in data:
            continue
        
        event = data.get("event")
        position = data.get("position")
        rating = ratings.get(event, 3)  # Default to 3 stars
        
        # Get college name
        college = ""
        try:
            row = df[df[mapping["reg_no"]] == reg_no]
            if not row.empty:
                college = str(row.iloc[0][mapping["college"]]) if pd.notna(row.iloc[0][mapping["college"]]) else ""
        except:
            pass
        
        if not college:
            continue
        
        # Calculate points
        points = POINTS_SYSTEM.get(rating, POINTS_SYSTEM[3])
        position_key = "1st" if position == 1 else "2nd" if position == 2 else "3rd"
        points_awarded = points.get(position_key, 0)
        
        college_points.setdefault(college, {"total": 0, "wins": []})
        college_points[college]["total"] += points_awarded
        college_points[college]["wins"].append({
            "event": event,
            "position": position,
            "points": points_awarded,
            "rating": rating
        })
    
    # Sort by total points
    sorted_colleges = sorted(college_points.items(), key=lambda x: x[1]["total"], reverse=True)
    
    result = []
    for college, data in sorted_colleges:
        result.append({
            "college": college,
            "total_points": data["total"],
            "wins": data["wins"]
        })
    
    return jsonify({"champions": result})

# ---------- SPOT REGISTRATION ---------- #

@app.route("/spot-registration")
def spot_registration_page():
    return render_template("spot_registration.html")

@app.route("/qr-code")
def generate_qr_code():
    """Generate QR code that links to spot registration page"""
    # Use configured base URL if set, otherwise auto-detect
    if QR_CODE_BASE_URL:
        base_url = QR_CODE_BASE_URL.rstrip('/')
    else:
        # Get the base URL from request - use scheme and host for mobile compatibility
        # Check if we have a forwarded host (for proxies/load balancers)
        host = request.headers.get('X-Forwarded-Host') or request.headers.get('Host') or request.host
        
        # Get scheme (http/https) - check for forwarded protocol
        scheme = request.headers.get('X-Forwarded-Proto') or request.scheme
        
        # Construct full URL
        base_url = f"{scheme}://{host}".rstrip('/')
        
        # For local development, if host is localhost/127.0.0.1, try to get actual IP
        # This helps when accessing from mobile on same network
        if 'localhost' in host.lower() or '127.0.0.1' in host:
            import socket
            try:
                # Connect to a remote address to get local IP
                s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                # Doesn't actually connect, just determines local IP
                s.connect(('8.8.8.8', 80))
                local_ip = s.getsockname()[0]
                s.close()
                
                # Use the local IP with the port from request
                port = request.environ.get('SERVER_PORT', '5000')
                base_url = f"{scheme}://{local_ip}:{port}"
            except Exception as e:
                print(f"Could not determine local IP: {e}")
                # Fall back to original URL
    
    spot_reg_url = f"{base_url}/spot-registration"
    
    print(f"QR Code URL: {spot_reg_url}")  # Debug: print the URL being used
    
    # Create QR code
    qr = qrcode.QRCode(
        version=1,
        error_correction=qrcode.constants.ERROR_CORRECT_L,
        box_size=10,
        border=4,
    )
    qr.add_data(spot_reg_url)
    qr.make(fit=True)
    
    # Create image
    img = qr.make_image(fill_color="black", back_color="white")
    
    # Save to BytesIO
    img_io = BytesIO()
    img.save(img_io, 'PNG')
    img_io.seek(0)
    
    return send_file(img_io, mimetype='image/png')

@csrf.exempt
@app.route("/submit_spot_registration", methods=["POST"])
def submit_spot_registration():
    """Handle spot registration form submission and write to Excel"""
    try:
        data = request.get_json(silent=True) or request.form
        
        event = data.get("event", "").strip()
        college = data.get("college", "").strip()
        contact = data.get("contact", "").strip()
        email = data.get("email", "").strip()
        reg_no = data.get("reg_no", "").strip()
        team_leader = data.get("team_leader", "").strip()
        team_members = data.get("team_members", [])
        
        # Filter out empty team members
        team_members = [m.strip() for m in team_members if m and m.strip()]
        
        # Validation with specific error messages
        if not event:
            return jsonify({"error": "Event name is required. Please select an event."}), 400
        if not college:
            return jsonify({"error": "College name is required"}), 400
        if not contact:
            return jsonify({"error": "Contact number is required"}), 400
        if not email:
            return jsonify({"error": "Email address is required"}), 400
        if not reg_no:
            return jsonify({"error": "Registration number is required"}), 400
        
        # Validate team requirements
        requirements = EVENT_TEAM_REQUIREMENTS.get(event, {"min": 1, "max": 20})
        min_members = requirements["min"]
        max_members = requirements["max"]
        
        # If it's a team event (max > 1), require team leader
        if max_members > 1 and not team_leader:
            return jsonify({"error": "Team leader name is required for team events"}), 400
        
        # Validate team size
        team_size = len(team_members)
        if team_size < min_members:
            return jsonify({"error": f"This event requires at least {min_members} team member{'s' if min_members > 1 else ''}"}), 400
        if team_size > max_members:
            return jsonify({"error": f"This event allows maximum {max_members} team member{'s' if max_members > 1 else ''}"}), 400
        
        # Load existing Excel and column mapping
        df = load_excel()
        mapping = load_column_map()
        
        if not mapping:
            return jsonify({"error": "Column mapping not configured. Please contact admin."}), 500
        
        # Check if registration number already exists
        if reg_no in df[mapping["reg_no"]].values:
            return jsonify({"error": "Registration number already exists"}), 400
        
        # Create new row data
        new_row = {}
        
        # Map all required fields
        new_row[mapping["reg_no"]] = reg_no
        new_row[mapping["event"]] = event
        new_row[mapping["college"]] = college
        
        # Set team leader
        if mapping.get("team_leader"):
            # Use provided team leader, or first team member if not provided
            if team_leader:
                new_row[mapping["team_leader"]] = team_leader
            elif team_members:
                new_row[mapping["team_leader"]] = team_members[0]
            else:
                new_row[mapping["team_leader"]] = ""
        
        # Set team members columns
        if mapping.get("team_members"):
            team_member_cols = mapping["team_members"]
            # Fill team members into available columns
            for i, col in enumerate(team_member_cols):
                if i < len(team_members):
                    new_row[col] = team_members[i]
                else:
                    new_row[col] = ""
        else:
            # If no team_members mapping, try to find columns manually
            for i, member in enumerate(team_members):
                # Try to find columns like "Student 2", "Student 3", etc.
                col_name = f"Student {i + 2}"  # Student 2, 3, 4...
                if col_name in df.columns:
                    new_row[col_name] = member
        
        # Add contact and email if columns exist in Excel
        # Try to find contact/email columns or add them
        contact_col = None
        email_col = None
        
        for col in df.columns:
            col_lower = str(col).lower()
            if "contact" in col_lower or "phone" in col_lower or "mobile" in col_lower:
                contact_col = col
            if "email" in col_lower:
                email_col = col
        
        if contact_col:
            new_row[contact_col] = contact
        if email_col:
            new_row[email_col] = email
        
        # Fill missing columns with empty string
        for col in df.columns:
            if col not in new_row:
                new_row[col] = ""
        
        # Append new row to dataframe
        new_df = pd.DataFrame([new_row])
        df = pd.concat([df, new_df], ignore_index=True)
        
        # Save to Excel with file locking
        # Use a lock file to prevent concurrent writes
        lock_file_path = EXCEL_PATH + '.lock'
        try:
            with portalocker.Lock(lock_file_path, 'w', timeout=5) as lock:
                # Write Excel file while lock is held
                with pd.ExcelWriter(EXCEL_PATH, engine='openpyxl') as writer:
                    df.to_excel(writer, index=False, sheet_name='Sheet1')
        except portalocker.exceptions.LockException:
            return jsonify({"error": "File is locked. Please try again in a moment."}), 503
        
        return jsonify({
            "success": True,
            "message": "Spot registration successful! Your data has been added.",
            "reg_no": reg_no
        })
        
    except Exception as e:
        print(f"SPOT REGISTRATION ERROR: {e}")
        return jsonify({"error": f"Registration failed: {str(e)}"}), 500

# ---------------- RUN ---------------- #

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=False)

