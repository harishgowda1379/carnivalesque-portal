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
from datetime import datetime, timedelta

app = Flask(__name__)
app.secret_key = secrets.token_hex(32)
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(hours=2)  # Session timeout
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

# Secure hashed passwords using bcrypt
USERS = {
    "register": {"password_hash": bcrypt.hashpw(b"reg123", bcrypt.gensalt()).decode(), "role": "register"},
    "coordinator": {"password_hash": bcrypt.hashpw(b"coord123", bcrypt.gensalt()).decode(), "role": "coordinator"},
    "certificate": {"password_hash": bcrypt.hashpw(b"cert123", bcrypt.gensalt()).decode(), "role": "certificate"},
    "admin": {"password_hash": bcrypt.hashpw(b"admin123", bcrypt.gensalt()).decode(), "role": "admin"},
    "superadmin": {"password_hash": bcrypt.hashpw(b"super123", bcrypt.gensalt()).decode(), "role": "super_admin"}
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
    "FC26": {"min": 1, "max": 1},
    "FC26 EA SPORTS": {"min": 1, "max": 1},
    # Additional event variations to handle different naming in Excel
    "Carrom (Men)": {"min": 1, "max": 1},
    "Chess (Men)": {"min": 1, "max": 1},
    "Carrom (Women)": {"min": 1, "max": 1},
    "Chess (Women)": {"min": 1, "max": 1}
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
    # Validate file path and size
    if not os.path.exists(EXCEL_PATH):
        raise FileNotFoundError("Excel file not found")
    
    file_size = os.path.getsize(EXCEL_PATH)
    if file_size > 50 * 1024 * 1024:  # 50MB limit
        raise ValueError("Excel file too large")
    
    # Ensure file is within allowed directory
    real_path = os.path.realpath(EXCEL_PATH)
    allowed_dir = os.path.realpath(BASE_DIR)
    if not real_path.startswith(allowed_dir):
        raise ValueError("Invalid file path")
    
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

    # Handle team_members columns
    for col in mapping.get("team_members", []):
        if col in row and pd.notna(row[col]):
            member = str(row[col]).strip()
            if member.lower() not in seen:
                team.append(member)
                seen.add(member.lower())

    # Also check for "participants" and "students" columns directly in Excel
    for col in row.index:
        col_lower = str(col).lower()
        if col_lower in ["participants", "students"] and pd.notna(row[col]):
            member = str(row[col]).strip()
            if member and member.lower() not in seen:
                team.append(member)
                seen.add(member.lower())

    return team

# ---------------- TEAM OVERRIDES ---------------- #

def get_team_for_reg(reg_no, row, mapping, status):
    """
    Returns team list for a registration number.
    Priority:
      1) status[reg_no]['team_override'] if present and non-empty (for recently edited teams)
      2) extracted team from Excel row (primary source)
    """
    try:
        # First check for override (for recently edited teams)
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
        # Fallback to Excel data
        excel_team = extract_team(row, mapping) if row is not None else []
        if excel_team:  # If Excel has team data, use it
            return excel_team
    except Exception:
        pass

    return []

# ---------------- ROUTES ---------------- #

@app.route("/")
def login_page():
    return render_template("login.html")

@app.route("/login")
def login_get():
    return render_template("login.html")

@csrf.exempt
@app.route("/login", methods=["POST"])
@limiter.limit("5 per minute")
def login():
    # Accept JSON or form data
    data = request.get_json(silent=True)
    if not data:
        data = request.form

    username = (data.get("username") or "").strip()
    password = (data.get("password") or "").strip()

    # Input validation
    if not username or not password:
        return jsonify({
            "success": False,
            "error": "Username and password required"
        }), 400

    # Length limits
    if len(username) > 50 or len(password) > 100:
        return jsonify({
            "success": False,
            "error": "Invalid input length"
        }), 400

    user = USERS.get(username)
    if not user:
        return jsonify({
            "success": False,
            "error": "Invalid username or password"
        }), 401

    # Verify password using bcrypt
    try:
        if not bcrypt.checkpw(password.encode(), user["password_hash"].encode()):
            return jsonify({
                "success": False,
                "error": "Invalid username or password"
            }), 401
    except Exception:
        return jsonify({
            "success": False,
            "error": "Authentication failed"
        }), 500

    # Set session
    session["username"] = username
    session["role"] = user["role"]
    session.permanent = True

    return jsonify({
        "success": True,
        "role": user["role"],
        "redirect": f"/{user['role'].replace('_', '-')}"
    })

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

@app.route("/get_column_map")
@login_required
def get_column_map():
    mapping = load_column_map()
    return jsonify(mapping or {})

@app.route("/save_column_map", methods=["POST"])
@role_required("admin")
def save_mapping():
    try:
        data = request.get_json()
        
        if not data:
            return jsonify({"error": "Request body must be valid JSON"}), 400
        
        # Validate required fields
        required_fields = ["reg_no", "event", "college"]
        for field in required_fields:
            if field not in data:
                return jsonify({"error": f"Missing required field: {field}"}), 400
        
        save_column_map(data)
        return jsonify({"success": True})
        
    except Exception as e:
        return jsonify({"error": f"Server error: {str(e)}"}), 500

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
        # Get unique events from Excel file ONLY (this is the source of truth)
        df = load_excel()
        mapping = load_column_map()
        
        if mapping and mapping.get("event") in df.columns:
            events = df[mapping["event"]].dropna().unique().tolist()
            events = [e for e in events if str(e).strip()]  # Remove empty values
            return jsonify(sorted(events))  # Sort alphabetically
        else:
            return jsonify([])
    except Exception as e:
        return jsonify([])

@csrf.exempt
@app.route("/get_event_requirements")
def get_event_requirements():
    """Get min/max team requirements for an event"""
    event = request.args.get("event") or (request.json.get("event") if request.is_json else None)
    if not event:
        return jsonify({"error": "Event name required"}), 400
    
    # Input validation
    if len(event) > 100:
        return jsonify({"error": "Invalid event name length"}), 400
    
    requirements = None
    event_lower = event.lower()
    
    # Try exact match first
    if event in EVENT_TEAM_REQUIREMENTS:
        requirements = EVENT_TEAM_REQUIREMENTS[event]
    else:
        # Try case-insensitive match
        for key, value in EVENT_TEAM_REQUIREMENTS.items():
            if key.lower() == event_lower:
                requirements = value
                break
    
    # If still not found, use default
    if not requirements:
        requirements = {"min": 1, "max": 20}
    
    return jsonify(requirements)

@app.route("/add_college", methods=["POST"])
def add_college():
    """Add a new college to the list"""
    data = request.get_json(silent=True) or {}
    college = data.get("college", "").strip()
    
    if not college:
        return jsonify({"success": False, "error": "College name is required"}), 400
    
    # Load existing colleges
    try:
        colleges_path = os.path.join(BASE_DIR, "data", "colleges.json")
        colleges = []
        
        if os.path.exists(colleges_path):
            with open(colleges_path, 'r') as f:
                colleges = json.load(f)
        
        # Add new college if not exists
        if college not in colleges:
            colleges.append(college)
            
            # Save to file
            with open(colleges_path, 'w') as f:
                json.dump(colleges, f, indent=2)
            
            return jsonify({"success": True, "message": "College added successfully"})
        else:
            return jsonify({"success": True, "message": "College already exists"})
            
    except Exception as e:
        return jsonify({"success": False, "error": "Failed to save college"}), 500

@csrf.exempt
@app.route("/get_colleges")
def get_colleges():
    """Get list of colleges for dropdown"""
    # Default colleges list
    default_colleges = [
        "A P S COLLEGE OF ENGINEERING",
        "ACHARYA BANGLORE BUSINESS SCHOOL",
        "ACHARYA INSTITUTE OF GRADUATE STUDIES",
        "ACHARYA INSTITUTE OF MANAGEMENT STUDIES",
        "ACS ENGINEERING COLLEGE",
        "ADITYA INSTITUTE OF MANAGEMENT STUDIES & RESEARCH",
        "AGRAGAMI INSTITUTE OF COMPUTER & ADVANCED MANAGEMENT STUDIES",
        "ALLIANCE UNIVERSITY CITY CAMPUS",
        "ALLIANCE UNIVERSITY MAIN CAMPUS",
        "AMC ENGINEERING COLLEGE",
        "AMITY EDUCATION GROUP",
        "AMITY GLOBAL BUSINESS SCHOOL BANGALORE",
        "APS COLLEGE OF COMMERCE",
        "ARIHANT GROUPS OF INSTITUTION",
        "BALDWIN METHODIST COLLEGE",
        "BALDWIN WOMENS METHODIST COLLEGE",
        "BANASWDI COLLEGE OF NURSING",
        "BANGALORE INSTITUTE OF TECHNOLOGY",
        "BAPU COLLEGE",
        "BASAWESHWARA COLLEGE OF ARTS COMMERCE AND SCIENCE",
        "BBMP FIRST GRADE COLLEGE, BINNIPETE",
        "BBMP FIRST GRADE COLLEGE FOR WOMEN, FRAZER TOWN",
        "BEL FIRST GRADE COLLEGE",
        "BES COLLEGE",
        "BET SADATHUNNISA COLLEGE",
        "BGS COLLEGE OF ENGINEERING",
        "BGS INSTITUTE OF MANAGEMENT",
        "BHARATH MATHA COLLEGE FOR WOMEN",
        "BISHOP COTTON ACADEMY OF PROFESSIONAL MANAGEMENT",
        "BISHOP COTTON WOMEN'S CHRISTIAN COLLEGE",
        "BMS COLLEGE OF ARCHITECTURE",
        "BMS COLLEGE OF COMMERCE & MANAGEMENT",
        "BMS COLLEGE OF ENGINEERING",
        "BMS COLLEGE OF LAW",
        "BMS COLLEGE OF WOMEN",
        "BNM DEGREE COLLEGE",
        "BNMIT",
        "BRINDAVAN GROUP OF INSTITUTIONS",
        "C.B. BHANDARI JAIN COLLEGE",
        "CES INSTITUTE OF FASHION TECHNOLOGY",
        "CHARAN DEGREE COLLEGE",
        "CHRIS CANADIAN DEGREE COLLEGE",
        "CHRIST (DEEEMED TO BE UNIVERSITY)YESHWANTHAPUR CAMPUS",
        "CHRIST ACADEMY INSTITUTE OF ADVANCED STUDIES AND LAW",
        "CHRIST THE KING COLLEGE",
        "CHRIST UNIVERSITY BANNERGHATTA CAMPUS",
        "CHRIST UNIVERSITY KENGERI CAMPUS",
        "CHRIST UNIVERSITY MAIN CAMPUS",
        "CITY COLLEGE JAYANAGAR",
        "CMR UNIVERSITY (CITY CAMPUS)",
        "CMR UNIVERSITY (LAKESIDE CAMPUS)",
        "CMR UNIVERSITY OMBR CAMPUS",
        "CMRIT MARATHALI",
        "COMMUNITY INSTITUTE OF COMMERCE AND MANAGEMENT",
        "CREO VALLEY",
        "DAYANADA SAGAR UNIVERSITY",
        "DAYANANDA SAGAR UNIVERSITY (DSU) - CITY CAMPUS",
        "DON BOSCO COLLEGE",
        "DON BOSCO INSTITUTE OF TECHNOLOGY",
        "DR. AMBEDKAR INSTITUTE OF MANAGEMENT STUDIES",
        "EAST WEST SCHOOL OF BUSINESS MANAGEMENT",
        "EBENIZER GROUP OF INSTITUTION",
        "FLORENCE GROUP OF INSTITUTION",
        "GIBS BUSINESS SCHOOL",
        "GLOBAL ACADMEY OF TECHNOLOGY",
        "GOPALAN COLLEGE OF COMMERCE",
        "GOVERNMENT FIRST GRADE COLLEGE YELAHANKA",
        "IBMR IBS",
        "IFIM COLLEGE",
        "IIBS BANGALORE R.T.NAGAR CAMPUS",
        "INDIAN INSTITUTE OF PSYCHOLOGY AND RESEARCH",
        "INTERNATIONAL INSTITUTE OF FASHION DESIGN",
        "INTERNATIONAL INSTITUTE OF INFORMATION TECHNOLOGY, BANGALORE",
        "ISBR",
        "JAIN  UNIVERSITY  SCHOOL OF SCIENCES",
        "JAIN CMS BUSINESS SCHOOL",
        "JAIN COLLEGE",
        "JAIN UNIVERSITY JP NAGAR CAMPUS",
        "JAIN UNIVERSITY RAGIGUDDA CAMPUS",
        "JD INSTITUTE OF FASHION TEWCHNOLOGY",
        "JNANA JYOTHI DEGREE COLLEGE",
        "JYOTHY INSTITUTE OF COMMERCE AND MANAGEMENT",
        "JYOTHY INSTITUTE OF TECHNOLOGY",
        "JYOTI NIVAS COLLEGE",
        "KAIRALEE NIKETAN GOLDEN JUBILEE DEGREE COLLEGE",
        "KIET COLLEGE OF EDUCATION",
        "KLE SOCOIETY S NIJALINGAPPA COLLEGE",
        "KNS INSTUTITE OF TECHNOLOGY",
        "KRISTU JAYANTI",
        "KRUPANIDHI DEGREE COLLEGE CARMELARAM ROAD",
        "KRUPANIDHI GROUP OF INSTITUTIONS",
        "KSSEM",
        "LOYALA DEGREE COLLEGE",
        "MAHARANI LAKSHMI AMMANNI COLLEGE FOR WOMEN",
        "MANIPAL ACADEMY OF HIGHER EDUCATION, MAHE BENGALURU",
        "MES COLLEGE OF ARTS, COMMERCE & SCIENCE",
        "MES INSTITUTE OF MANAGEMENT",
        "MKPM RV INSTITUTE OF LEGAL STUDIES",
        "MONTFORT COLLEGE",
        "MOUNT CARMEL COLLEGE",
        "MS RAMAIAH COLLEGE OF ARTS, SCIENCE & COMMERCE",
        "MVJ COLLEGE OF ENGINEERING",
        "NEW HORIZON COLLEGE - KASTURINAGAR",
        "NEW HORIZON COLLEGE OF ENGINEERING",
        "NMKRV COLLEGE FOR WOMEN",
        "NOBLE COLLLEGE",
        "PADMA COLLEGE OF MANAGEMENT & SCIENCE",
        "PEARL ACADEMY",
        "PES UNIVERSITY",
        "PES UNIVERSITY ELECTRONIC CITY CAMPUS",
        "PRESIDENCY COLLEGE",
        "PRESIDENCY UNIVERSITY",
        "R V INSTITUTE OF MANAGEMENT",
        "R.B.N.M.S.S FIRST GRADE COLLEGE",
        "RAJAJINAGAR FIRST GRADE COLLEGE OF COMMERC",
        "RAJARAJESHWARI ENGINEERING COLLEGE",
        "RAMAIAH UNIVERSITY OF APPLIED SCIENCES",
        "RAMAIAH UNIVERSITY OF APPLIED SCIENCES",
        "RANI SARALADEVI DEGREE COLLEGE",
        "RR.INSTITUTE OF TECHNOLOGY",
        "RS COLLEGE OF MANAGEMENT & SCIENCE",
        "RV COLLEGE OF ARCHIETURE",
        "SAMBHRAM INSTITUTE OF TECHONOLOGY",
        "SAPTHAGIRI COLLEGE OF ENGINEEERING",
        "SEA COLLEGE OF SCIENCE, COMMERCE AND ARTS",
        "SESHADRIPURAM COLLEGE",
        "SESHADRIPURAM FIRST GRADE COLLEGE",
        "SHAKUNTALA DEVI COLLEGE",
        "SHREE BALAJI DEGREE COLLEGE",
        "SINDHI COLLEGE",
        "SIR M. VISVESVARAYA INSTITUTE OF TECHNOLOGY",
        "SMSG JAIN COLLEGE",
        "SOUNDARYA INSTITUTE OF MANAGEMENT AND SCIENCE",
        "SREE OMKAR GROUP OF INSTITUTIONS",
        "SRI KRISHNA DEGREE COLLEGE",
        "SRI KRISHNA INSITUTE OF TECHNOLOGY",
        "SRI REVANNA INSTIUTE OF TECHNOLOGY",
        "SRI SAI COLLEGE FOR WOMEN",
        "SRI VENKATESHWARA COLLEGE OF ENGINEERING",
        "SRI VENKATESHWARA FIRST GRADE COLLEGE",
        "SRUSHTI DEGREE COLLEGE",
        "SSMRV COLLEGE",
        "SSR COLEGE FOR WOMEN",
        "ST ANNES DEGREE COLLEGE FOR WOMEN",
        "ST. CLARET COLLEGE",
        "ST. FRANCIS DE SALES",
        "ST. GEORGE COLLEGE OF MANAGEMENT & SCIENCE",
        "ST. JOHNS MEDICAL COLLEGE",
        "ST. JOSEPH COLLEGE OF COMMERCE",
        "ST. JOSEPH COLLEGE OF LAW",
        "ST. JOSEPH INSTITUTE OF MANAGEMENT",
        "ST. JOSEPH'S UNIVERSITY",
        "ST. PAULS COLLEGE",
        "ST. VINCENT PALLOTTI COLLEGE",
        "SURANA COLLEGE - PEENYA CAMPUS",
        "SUVIDYA COLLEGE",
        "SWAMY VIVEKANANDA RURAL FIRST GRADE COLLEGE",
        "T JOHN COLLEGE",
        "TAPASYA DEGREE & PUC COLLEGE, CHANDAPURA",
        "THE KINGDOM COLLEGE",
        "THE NATIONAL DEGREE COLLEGE",
        "THE OXFORD COLLEGE OF BUSINESS MANAGEMENT",
        "THE OXFORD COLLEGE OF ENGINEERING",
        "TRANSCEND GROUP OF INSTITUTIONS",
        "UNITED INTERNATIONAL DEGREE COLLEGE",
        "VEMANA IT",
        "VIJAYA COLLEGE, JAYANAGAR",
        "VIJAYA COLLEGE, RV ROAD",
        "VIJAYA VITTALA INSTUITE OF TECHNOLOGY",
        "VV PURAM COLLEGE OF ARTS & COMMERCE",
        "Others"
    ]
    
    # Load custom colleges from file
    try:
        colleges_path = os.path.join(BASE_DIR, "data", "colleges.json")
        custom_colleges = []
        
        if os.path.exists(colleges_path):
            with open(colleges_path, 'r') as f:
                custom_colleges = json.load(f)
        
        # Combine default and custom colleges, remove duplicates
        all_colleges = default_colleges.copy()
        for college in custom_colleges:
            if college not in all_colleges:
                all_colleges.append(college)
        
        return jsonify(all_colleges)
        
    except Exception as e:
        return jsonify(default_colleges)


@app.route("/get_event_codes_admin")
@role_required("admin")
def get_event_codes_admin():
    """Get all event codes for admin"""
    try:
        codes = load_event_codes()
        return jsonify(codes)
    except Exception as e:
        return jsonify({})

@app.route("/save_event_codes_admin", methods=["POST"])
@role_required("admin")
def save_event_codes_admin():
    """Save event codes from admin panel"""
    try:
        data = request.get_json(silent=True) or {}
        
        if not data:
            return jsonify({"error": "No codes provided"}), 400
        
        # Save the codes
        save_event_codes(data)
        
        return jsonify({"success": True, "message": f"Saved {len(data)} event codes"})
    except Exception as e:
        return jsonify({"error": "Failed to save event codes"}), 500

@app.route("/change_user_password", methods=["POST"])
@role_required("admin", "super_admin")
def change_user_password():
    """Change password for a user"""
    try:
        data = request.get_json(silent=True) or {}
        user = data.get("user")
        new_password = data.get("new_password")
        
        if not user or not new_password:
            return jsonify({"error": "User and password required"}), 400
        
        # Input validation
        if len(user) > 50 or len(new_password) > 100:
            return jsonify({"error": "Invalid input length"}), 400
        
        if len(new_password) < 6:
            return jsonify({"error": "Password must be at least 6 characters"}), 400
        
        # Update the password with bcrypt hash
        USERS[user]["password_hash"] = bcrypt.hashpw(new_password.encode(), bcrypt.gensalt()).decode()
        
        return jsonify({"success": True, "message": f"Password updated for {user}"})
    except Exception as e:
        return jsonify({"error": "Failed to update password"}), 500
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
        "event": str(row[mapping["event"]]) if pd.notna(row[mapping["event"]]) else "Unknown Event",
        "college": str(row[mapping["college"]]) if pd.notna(row[mapping["college"]]) else "Unknown College",
        "team": team,
        "team_size": len(team)
    })




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

    # Update Excel file
    try:
        # Find the row index
        idx = df[df[mapping["reg_no"]] == reg_no].index[0]
        
        # Update team member columns
        team_members_cols = mapping.get("team_members", [])
        for i, name in enumerate(cleaned):
            if i < len(team_members_cols):
                df.at[idx, team_members_cols[i]] = name
        
        # Clear any extra team member columns
        for i in range(len(cleaned), len(team_members_cols)):
            df.at[idx, team_members_cols[i]] = ""
        
        # Update team leader if exists
        if "team_leader" in mapping and cleaned:
            df.at[idx, mapping["team_leader"]] = cleaned[0]
        
        # Save to Excel
        df.to_excel(EXCEL_PATH, index=False)
    except Exception as e:
        return jsonify({"error": f"Failed to update Excel: {str(e)}"})

    # Also save to status for backup
    status = load_status()
    status.setdefault(reg_no, {})
    status[reg_no]["event"] = event
    status[reg_no]["team_override"] = cleaned
    save_status(status)

    return jsonify({"success": True, "team_size": len(cleaned)})

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

    # Get actual events from Excel file
    try:
        df = load_excel()
        mapping = load_column_map()
        
        if mapping and mapping.get("event") in df.columns:
            excel_events = df[mapping["event"]].dropna().unique().tolist()
            excel_events = [e for e in excel_events if str(e).strip()]
        else:
            excel_events = []
    except:
        excel_events = []
    
    # Check if event exists in Excel
    if event not in excel_events:
        return jsonify({"success": False, "error": "Event not found in system"}), 400

    # For now, accept any non-empty code (or you can load from event_codes.json if it has codes)
    event_codes = load_event_codes()
    
    # If code exists in codes file, verify it; otherwise accept any code
    if event in event_codes:
        if event_codes[event].upper() == code.upper():
            session["verified_event"] = event
            return jsonify({"success": True})
        else:
            return jsonify({"success": False, "error": "Invalid code"}), 401
    else:
        # Event not in codes file, accept any non-empty code
        if code.strip():
            session["verified_event"] = event
            return jsonify({"success": True})
        else:
            return jsonify({"success": False, "error": "Code required"}), 400


# --------------------------------------------------
# 📋 GET REPORTED TEAMS (PROTECTED)
# --------------------------------------------------
@csrf.exempt
@event_verified_required
@app.route("/get_reported_teams", methods=["POST"])
@event_verified_required
def get_reported_teams():
    df = load_excel()
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
            if mapping.get("college") and mapping["college"] in df.columns:
                college = str(row.iloc[0][mapping["college"]])

            # Extract contact/phone number from Excel using mapped column
            contact = ""
            row_data = row.iloc[0]
            
            # Use the mapped contact column name from column_map.json
            if mapping.get("contact"):
                contact_col = mapping["contact"]
                
                # Try exact match first
                if contact_col in df.columns:
                    val = row_data[contact_col]
                    if pd.notna(val):
                        contact = str(val).strip()
                # If not found, try case-insensitive match
                else:
                    for col in df.columns:
                        if col.strip().lower() == contact_col.strip().lower():
                            val = row_data[col]
                            if pd.notna(val):
                                contact = str(val).strip()
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
@event_verified_required
@app.route("/end_event", methods=["POST"])
def end_event():
    data = request.get_json(silent=True) or {}
    winners = data.get("winners", {})
    event = data.get("event")

    if not winners:
        return jsonify({"error": "No winners selected"}), 400

    status = load_status()
    
    # If event is provided in request, use it
    if event:
        # Verify event matches current event in session
        pass
    else:
        # Try to get event from first winner's data
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


# --------------------------------------------------
# 🔄 RESET WINNERS (SUPER ADMIN ONLY)
# --------------------------------------------------
@app.route("/reset_winners", methods=["POST"])
@role_required("super_admin")
def reset_winners():
    """Reset winners for an event - allows coordinator to reassign"""
    data = request.get_json(silent=True) or {}
    event = data.get("event")
    
    if not event:
        return jsonify({"error": "Event name required"}), 400
    
    status = load_status()
    reset_count = 0
    
    # Reset event_ended and position for all teams in this event
    for reg_no, team_status in status.items():
        if team_status.get("event") == event and team_status.get("event_ended"):
            team_status["event_ended"] = False
            team_status.pop("position", None)  # Remove position
            reset_count += 1
    
    if reset_count == 0:
        return jsonify({"error": "No winners found for this event"}), 404
    
    save_status(status)
    return jsonify({
        "success": True, 
        "message": f"Reset {reset_count} winner(s) for event '{event}'"
    })


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
            college = ""
            
            if df is not None and not df.empty and mapping and mapping.get("reg_no"):
                try:
                    row = df[df[mapping["reg_no"]] == reg_no]
                    if not row.empty:
                        team = get_team_for_reg(reg_no, row.iloc[0], mapping, status)
                        # Get college name
                        if mapping.get("college") and mapping["college"] in df.columns:
                            college_val = row.iloc[0][mapping["college"]]
                            if pd.notna(college_val):
                                college = str(college_val)
                except:
                    team = []
                    college = ""
            
            completed[reg_no] = {
                "event": data.get("event", ""),
                "position": data.get("position"),
                "team": team,
                "college": college
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
                # Fall back to original URL
                pass
    
    spot_reg_url = f"{base_url}/spot-registration"
    
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
        college_other = data.get("college_other", "").strip()
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
        
        # Handle college mapping - if "Others" was selected, use specify_college field
        if college_other and (college == "Others" or college == "Others (Not in list)"):
            # User selected "Others" and entered custom college name
            new_row[mapping["college"]] = ""  # Leave College Name empty
            if mapping.get("specify_college"):
                new_row[mapping["specify_college"]] = college_other  # Put custom college in Specify College Name
        else:
            # Regular college selection
            new_row[mapping["college"]] = college
            if mapping.get("specify_college"):
                new_row[mapping["specify_college"]] = ""
        
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
            return jsonify({"error": "File is currently being updated by another user. Please wait a moment and try again."}), 503
        except PermissionError as e:
            return jsonify({"error": "Excel file is currently open in another program. Please close Excel and try again."}), 503
        except Exception as e:
            return jsonify({"error": f"Failed to save registration: {str(e)}"}), 500
        
        return jsonify({
            "success": True,
            "message": "Spot registration successful! Your data has been added.",
            "reg_no": reg_no
        })
        
    except Exception as e:
        return jsonify({"error": f"Registration failed: {str(e)}"}), 500

# ---------------- RUN ---------------- #

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=False)

