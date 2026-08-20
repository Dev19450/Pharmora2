import os
import re
import json
import sqlite3
import hashlib
import hmac
from datetime import datetime, timezone, timedelta
from functools import wraps
from flask import Blueprint, request, jsonify, session

try:
    from .models import get_db_connection
except ImportError:
    from models import get_db_connection

auth_bp = Blueprint('auth', __name__)

EMAIL_REGEX = re.compile(r'^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$')
PHONE_REGEX = re.compile(r'^\+?[0-9]{10,15}$')

def normalize_email(email: str) -> str:
    """Normalizes an email address to lowercase and stripped string."""
    return email.strip().lower() if email else ""

def normalize_phone(phone: str) -> str:
    """
    Normalizes a mobile number to international E.164 standard format.
    For 10-digit Indian numbers, prepends +91.
    """
    if not phone:
        return ""
    cleaned = re.sub(r'[\s\-\(\)]', '', phone.strip())
    if cleaned.startswith("+"):
        return cleaned
    if cleaned.startswith("0") and len(cleaned) == 11:
        return f"+91{cleaned[1:]}"
    if len(cleaned) == 10 and cleaned.isdigit():
        return f"+91{cleaned}"
    return f"+{cleaned}" if cleaned.isdigit() else cleaned

def is_valid_email(email: str) -> bool:
    if not email:
        return False
    return bool(EMAIL_REGEX.match(normalize_email(email)))

def is_valid_phone(phone: str) -> bool:
    if not phone:
        return False
    norm = normalize_phone(phone)
    return bool(PHONE_REGEX.match(norm)) and len(re.sub(r'\D', '', norm)) >= 10

# ==============================================================================
# Server-Side Rate Limiting
# ==============================================================================

def check_rate_limit(action_key: str, max_requests: int, window_seconds: int) -> tuple[bool, str]:
    conn = get_db_connection()
    cursor = conn.cursor()
    now = datetime.now(timezone.utc)
    window_start = (now - timedelta(seconds=window_seconds)).isoformat()

    cursor.execute("SELECT count, first_attempt_at FROM rate_limits WHERE action_key = ?", (action_key,))
    row = cursor.fetchone()

    if not row:
        cursor.execute(
            "INSERT INTO rate_limits (action_key, count, first_attempt_at, last_attempt_at) VALUES (?, 1, ?, ?)",
            (action_key, now.isoformat(), now.isoformat())
        )
        conn.commit()
        conn.close()
        return True, ""

    count = row['count']
    first_attempt_at = row['first_attempt_at']

    if first_attempt_at < window_start:
        cursor.execute(
            "UPDATE rate_limits SET count = 1, first_attempt_at = ?, last_attempt_at = ? WHERE action_key = ?",
            (now.isoformat(), now.isoformat(), action_key)
        )
        conn.commit()
        conn.close()
        return True, ""

    if count >= max_requests:
        conn.close()
        return False, "Rate limit exceeded. Please wait before trying again."

    cursor.execute(
        "UPDATE rate_limits SET count = count + 1, last_attempt_at = ? WHERE action_key = ?",
        (now.isoformat(), action_key)
    )
    conn.commit()
    conn.close()
    return True, ""


# ==============================================================================
# Authentication Middleware
# ==============================================================================

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user' not in session or not session['user']:
            return jsonify({"success": False, "error": "Authentication required. Please sign in."}), 401
        return f(*args, **kwargs)
    return decorated_function


# ==============================================================================
# Direct Account Registration (No OTP)
# ==============================================================================

@auth_bp.route('/api/auth/register', methods=['POST'])
def register():
    """Direct user account registration without OTP verification."""
    data = request.json or {}
    name = data.get("name", "").strip()
    raw_email = data.get("email", "").strip()
    raw_phone = data.get("phone", "").strip()
    password = data.get("password", "")
    role = data.get("role", "owner").lower()
    store_name = data.get("store_name", "Pharmora Pharmacy").strip()

    if not name:
        return jsonify({"success": False, "error": "Please enter your Full Name."}), 400

    email = normalize_email(raw_email)
    phone = normalize_phone(raw_phone)

    if not is_valid_email(email):
        return jsonify({"success": False, "error": "Please provide a valid Email Address."}), 400

    if not is_valid_phone(phone):
        return jsonify({"success": False, "error": "Please provide a valid 10-15 digit Mobile Phone Number (e.g. +91 9876543210)."}), 400

    if not password or len(password) < 4:
        return jsonify({"success": False, "error": "Password must be at least 4 characters long."}), 400

    client_ip = request.remote_addr or "127.0.0.1"
    allowed_ip, _ = check_rate_limit(f"reg:ip:{client_ip}", 20, 3600)
    if not allowed_ip:
        return jsonify({"success": False, "error": "Too many registration attempts. Please try again later."}), 429

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute("SELECT id FROM users WHERE email = ?", (email,))
    if cursor.fetchone():
        conn.close()
        return jsonify({"success": False, "error": "An account with this Email Address is already registered. Please sign in."}), 400

    cursor.execute("SELECT id FROM users WHERE phone = ?", (phone,))
    if cursor.fetchone():
        conn.close()
        return jsonify({"success": False, "error": "An account with this Mobile Phone Number is already registered. Please sign in."}), 400

    now = datetime.now(timezone.utc).isoformat()
    pwd_hash = hashlib.sha256(password.encode('utf-8')).hexdigest()

    try:
        cursor.execute('''
            INSERT INTO users (
                name, email, phone, password_hash, role, store_name,
                email_verified, phone_verified, email_verified_at, phone_verified_at,
                status, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, 1, 1, ?, ?, 'ACTIVE', ?, ?)
        ''', (name, email, phone, pwd_hash, role, store_name, now, now, now, now))
        user_id = cursor.lastrowid
        conn.commit()
    except sqlite3.IntegrityError:
        conn.close()
        return jsonify({"success": False, "error": "An account with this Email or Mobile Number already exists."}), 400

    conn.close()

    user_payload = {
        "id": user_id,
        "name": name,
        "email": email,
        "phone": phone,
        "role": role,
        "store_name": store_name
    }

    session['user'] = user_payload

    return jsonify({
        "success": True,
        "message": f"Welcome to Pharmora, {name}! Your account is registered.",
        "user": user_payload
    })


# ==============================================================================
# Standard Login, Session Check, and Logout
# ==============================================================================

@auth_bp.route('/api/auth/login', methods=['POST'])
def login():
    data = request.json or {}
    identifier = data.get("identifier", "").strip() or data.get("email", "").strip() or data.get("phone", "").strip()
    password = data.get("password", "")
    client_ip = request.remote_addr or "127.0.0.1"

    if not identifier or not password:
        return jsonify({"success": False, "error": "Please enter your Email / Mobile Phone Number and Password."}), 400

    allowed, _ = check_rate_limit(f"login:ip:{client_ip}", 20, 3600)
    if not allowed:
        return jsonify({"success": False, "error": "Too many login attempts. Account temporarily locked for 1 hour."}), 429

    conn = get_db_connection()
    cursor = conn.cursor()

    norm_email = normalize_email(identifier)
    norm_phone = normalize_phone(identifier)

    cursor.execute('''
        SELECT id, name, email, phone, password_hash, role, store_name, status
        FROM users
        WHERE email = ? OR phone = ?
    ''', (norm_email, norm_phone))

    user_row = cursor.fetchone()
    conn.close()

    if not user_row:
        return jsonify({"success": False, "error": "No account found with this Email or Mobile Number. Please click 'Create Account' above to register."}), 401

    if user_row['status'] in ('LOCKED', 'SUSPENDED'):
        return jsonify({"success": False, "error": "This account is currently locked. Please contact support."}), 403

    computed_hash = hashlib.sha256(password.encode('utf-8')).hexdigest()
    if not hmac.compare_digest(computed_hash, user_row['password_hash']):
        return jsonify({"success": False, "error": "Incorrect password. Please verify and try again."}), 401

    user_payload = {
        "id": user_row['id'],
        "name": user_row['name'],
        "email": user_row['email'],
        "phone": user_row['phone'],
        "role": user_row['role'],
        "store_name": user_row['store_name']
    }

    session['user'] = user_payload

    return jsonify({
        "success": True,
        "message": f"Welcome back, {user_row['name']}!",
        "user": user_payload
    })


@auth_bp.route('/api/auth/me', methods=['GET'])
def get_current_user():
    user = session.get('user')
    if not user:
        return jsonify({"success": False, "user": None}), 401
    return jsonify({"success": True, "user": user})


@auth_bp.route('/api/auth/logout', methods=['POST'])
def logout():
    session.clear()
    response = jsonify({"success": True, "message": "Signed out successfully."})
    response.delete_cookie('session')
    return response
