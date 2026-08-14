import os
import re
import json
import sqlite3
import hashlib
import hmac
from datetime import datetime, timedelta
from functools import wraps
from flask import Blueprint, request, jsonify, session

try:
    from .models import get_db_connection
    from .otp_service import (
        normalize_email,
        normalize_phone,
        is_valid_email,
        is_valid_phone,
        generate_secure_otp,
        hash_otp,
        verify_otp_hash,
        notification_service,
        APP_ENV
    )
except ImportError:
    from models import get_db_connection
    from otp_service import (
        normalize_email,
        normalize_phone,
        is_valid_email,
        is_valid_phone,
        generate_secure_otp,
        hash_otp,
        verify_otp_hash,
        notification_service,
        APP_ENV
    )

auth_bp = Blueprint('auth', __name__)

OTP_EXPIRY_MINUTES = int(os.environ.get("OTP_EXPIRY_MINUTES", 5))
OTP_MAX_ATTEMPTS = int(os.environ.get("OTP_MAX_ATTEMPTS", 5))
OTP_RESEND_COOLDOWN_SECONDS = int(os.environ.get("OTP_RESEND_COOLDOWN", 60))

# ==============================================================================
# Server-Side Rate Limiting
# ==============================================================================

def check_rate_limit(action_key: str, max_requests: int, window_seconds: int) -> tuple[bool, str]:
    conn = get_db_connection()
    cursor = conn.cursor()
    now = datetime.utcnow()
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
# Dual-Channel Registration & OTP Dispatch
# ==============================================================================

@auth_bp.route('/api/auth/register', methods=['POST'])
@auth_bp.route('/api/auth/send-otp', methods=['POST'])
def initiate_registration_or_send_otp():
    """
    Generates two distinct cryptographic 6-digit OTPs (one for Email, one for Mobile)
    and returns exact provider acceptance status without fake 'sent' affirmations.
    """
    data = request.json or {}
    name = data.get("name", "").strip()
    raw_email = data.get("email", "")
    raw_phone = data.get("phone", "")
    password = data.get("password", "")
    role = data.get("role", "owner").lower()
    store_name = data.get("store_name", "Pharmora Pharmacy").strip()
    purpose = data.get("purpose", "registration")

    email = normalize_email(raw_email)
    phone = normalize_phone(raw_phone)
    client_ip = request.remote_addr or "127.0.0.1"

    if not is_valid_email(email):
        return jsonify({"success": False, "error": "Please provide a valid Email Address."}), 400

    if not is_valid_phone(phone):
        return jsonify({"success": False, "error": "Please provide a valid 10-15 digit Mobile Phone Number (e.g. +91 9876543210)."}), 400

    # Rate limiting
    allowed_email, msg = check_rate_limit(f"otp:email:{email}", 5, 3600)
    if not allowed_email:
        return jsonify({"success": False, "error": "Too many OTP requests for this email. Please wait an hour before trying again."}), 429

    allowed_phone, msg = check_rate_limit(f"otp:phone:{phone}", 5, 3600)
    if not allowed_phone:
        return jsonify({"success": False, "error": "Too many OTP requests for this phone number. Please wait an hour before trying again."}), 429

    allowed_ip, msg = check_rate_limit(f"otp:ip:{client_ip}", 15, 3600)
    if not allowed_ip:
        return jsonify({"success": False, "error": "Too many verification requests from this IP address."}), 429

    conn = get_db_connection()
    cursor = conn.cursor()

    if purpose == "registration":
        cursor.execute("SELECT id FROM users WHERE email = ?", (email,))
        if cursor.fetchone():
            conn.close()
            return jsonify({"success": False, "error": "An account with this Email Address is already registered. Please sign in."}), 400

        cursor.execute("SELECT id FROM users WHERE phone = ?", (phone,))
        if cursor.fetchone():
            conn.close()
            return jsonify({"success": False, "error": "An account with this Mobile Phone Number is already registered. Please sign in."}), 400

    # Generate TWO independent 6-digit cryptographic OTPs
    email_otp = generate_secure_otp()
    phone_otp = generate_secure_otp()

    email_otp_hash = hash_otp(email_otp)
    phone_otp_hash = hash_otp(phone_otp)

    now = datetime.utcnow()
    expires_at = (now + timedelta(minutes=OTP_EXPIRY_MINUTES)).isoformat()

    # Clear prior pending OTP challenge for this user
    cursor.execute("DELETE FROM otp_verifications WHERE email = ? OR phone = ?", (email, phone))

    cursor.execute('''
        INSERT INTO otp_verifications (
            email, phone, email_otp_hash, phone_otp_hash, email_verified, phone_verified,
            email_last_sent_at, phone_last_sent_at, last_sent_at, email_attempts, phone_attempts,
            max_attempts, expires_at, created_at, purpose
        ) VALUES (?, ?, ?, ?, 0, 0, ?, ?, ?, 0, 0, ?, ?, ?, ?)
    ''', (
        email, phone, email_otp_hash, phone_otp_hash,
        now.isoformat(), now.isoformat(), now.isoformat(),
        OTP_MAX_ATTEMPTS, expires_at, now.isoformat(), purpose
    ))

    conn.commit()
    conn.close()

    # Dispatch to providers with actual status return
    dispatch_results = notification_service.send_dual_otps(
        email=email,
        phone=phone,
        user_name=name or "Pharmora Partner",
        email_otp=email_otp,
        phone_otp=phone_otp,
        expiry_minutes=OTP_EXPIRY_MINUTES
    )

    response_payload = {
        "success": True,
        "message": "Verification code requests processed.",
        "target_email": email,
        "target_phone": phone,
        "email": dispatch_results["email"],
        "mobile": dispatch_results["mobile"],
        "cooldown_seconds": OTP_RESEND_COOLDOWN_SECONDS,
        "expires_in_minutes": OTP_EXPIRY_MINUTES
    }

    if APP_ENV == "development":
        response_payload["dev_email_otp"] = email_otp
        response_payload["dev_phone_otp"] = phone_otp

    return jsonify(response_payload)


# ==============================================================================
# Granular Channel Verification Endpoints
# ==============================================================================

@auth_bp.route('/api/auth/verify-email-otp', methods=['POST'])
def verify_email_otp_only():
    """Verifies only the Email 6-digit OTP code."""
    data = request.json or {}
    email = normalize_email(data.get("email", ""))
    code = data.get("otp_code", "").strip()

    if not code or len(code) != 6 or not code.isdigit():
        return jsonify({"success": False, "error": "Please enter a valid 6-digit numeric email verification code."}), 400

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute('''
        SELECT id, email_otp_hash, email_verified, email_attempts, max_attempts, expires_at
        FROM otp_verifications
        WHERE email = ?
        ORDER BY id DESC LIMIT 1
    ''', (email,))
    row = cursor.fetchone()

    if not row:
        conn.close()
        return jsonify({"success": False, "error": "No active email verification challenge found. Please request a new code."}), 400

    rec_id = row['id']
    if row['email_verified'] == 1:
        conn.close()
        return jsonify({"success": True, "message": "Email already verified.", "email_verified": True})

    now = datetime.utcnow().isoformat()
    if now > row['expires_at']:
        conn.close()
        return jsonify({"success": False, "error": "Email verification code has expired. Please resend code."}), 400

    if row['email_attempts'] >= row['max_attempts']:
        conn.close()
        return jsonify({"success": False, "error": "Maximum email verification attempts exceeded. Please request a fresh code."}), 400

    if not verify_otp_hash(code, row['email_otp_hash']):
        new_attempts = row['email_attempts'] + 1
        remaining = row['max_attempts'] - new_attempts
        cursor.execute("UPDATE otp_verifications SET email_attempts = ? WHERE id = ?", (new_attempts, rec_id))
        conn.commit()
        conn.close()
        if remaining <= 0:
            return jsonify({"success": False, "error": "Incorrect code. Maximum attempts reached. Please request a new email code."}), 400
        return jsonify({"success": False, "error": f"Incorrect email code. {remaining} attempts remaining."}), 400

    # Mark email verified
    cursor.execute("UPDATE otp_verifications SET email_verified = 1, email_verified_at = ? WHERE id = ?", (now, rec_id))
    conn.commit()
    conn.close()

    return jsonify({"success": True, "message": "Email verified successfully!", "email_verified": True})


@auth_bp.route('/api/auth/verify-phone-otp', methods=['POST'])
def verify_phone_otp_only():
    """Verifies only the Mobile 6-digit OTP code."""
    data = request.json or {}
    phone = normalize_phone(data.get("phone", ""))
    code = data.get("otp_code", "").strip()

    if not code or len(code) != 6 or not code.isdigit():
        return jsonify({"success": False, "error": "Please enter a valid 6-digit numeric mobile verification code."}), 400

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute('''
        SELECT id, phone_otp_hash, phone_verified, phone_attempts, max_attempts, expires_at
        FROM otp_verifications
        WHERE phone = ?
        ORDER BY id DESC LIMIT 1
    ''', (phone,))
    row = cursor.fetchone()

    if not row:
        conn.close()
        return jsonify({"success": False, "error": "No active mobile verification challenge found. Please request a new code."}), 400

    rec_id = row['id']
    if row['phone_verified'] == 1:
        conn.close()
        return jsonify({"success": True, "message": "Mobile number already verified.", "phone_verified": True})

    now = datetime.utcnow().isoformat()
    if now > row['expires_at']:
        conn.close()
        return jsonify({"success": False, "error": "Mobile verification code has expired. Please resend code."}), 400

    if row['phone_attempts'] >= row['max_attempts']:
        conn.close()
        return jsonify({"success": False, "error": "Maximum mobile verification attempts exceeded. Please request a fresh code."}), 400

    if not verify_otp_hash(code, row['phone_otp_hash']):
        new_attempts = row['phone_attempts'] + 1
        remaining = row['max_attempts'] - new_attempts
        cursor.execute("UPDATE otp_verifications SET phone_attempts = ? WHERE id = ?", (new_attempts, rec_id))
        conn.commit()
        conn.close()
        if remaining <= 0:
            return jsonify({"success": False, "error": "Incorrect code. Maximum attempts reached. Please request a new mobile code."}), 400
        return jsonify({"success": False, "error": f"Incorrect mobile code. {remaining} attempts remaining."}), 400

    # Mark phone verified
    cursor.execute("UPDATE otp_verifications SET phone_verified = 1, phone_verified_at = ? WHERE id = ?", (now, rec_id))
    conn.commit()
    conn.close()

    return jsonify({"success": True, "message": "Mobile number verified successfully!", "phone_verified": True})


@auth_bp.route('/api/auth/verify-otp', methods=['POST'])
def verify_otp_and_complete_auth():
    """
    Verifies Email OTP, Mobile OTP, or completes full account registration once both channels are verified.
    """
    data = request.json or {}
    email = normalize_email(data.get("email", ""))
    phone = normalize_phone(data.get("phone", ""))
    email_code = data.get("email_otp", "").strip() or data.get("otp_code", "").strip()
    phone_code = data.get("phone_otp", "").strip() or data.get("otp_code", "").strip()

    name = data.get("name", "").strip()
    password = data.get("password", "")
    role = data.get("role", "owner").lower()
    store_name = data.get("store_name", "Pharmora Pharmacy").strip()
    purpose = data.get("purpose", "registration")

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute('''
        SELECT id, email_otp_hash, phone_otp_hash, email_verified, phone_verified, expires_at,
               email_attempts, phone_attempts, max_attempts
        FROM otp_verifications
        WHERE email = ? OR phone = ?
        ORDER BY id DESC LIMIT 1
    ''', (email, phone))
    row = cursor.fetchone()

    if not row:
        conn.close()
        return jsonify({"success": False, "error": "No active verification challenge found. Please request a new code."}), 400

    rec_id = row['id']
    now = datetime.utcnow().isoformat()

    if now > row['expires_at']:
        cursor.execute("DELETE FROM otp_verifications WHERE id = ?", (rec_id,))
        conn.commit()
        conn.close()
        return jsonify({"success": False, "error": "Verification codes have expired (5-minute limit). Please request new codes."}), 400

    email_verified = row['email_verified'] == 1
    phone_verified = row['phone_verified'] == 1

    # Verify Email Code if provided and not yet verified
    if not email_verified and email_code:
        if verify_otp_hash(email_code, row['email_otp_hash']):
            email_verified = True
            cursor.execute("UPDATE otp_verifications SET email_verified = 1, email_verified_at = ? WHERE id = ?", (now, rec_id))
        else:
            new_attempts = row['email_attempts'] + 1
            cursor.execute("UPDATE otp_verifications SET email_attempts = ? WHERE id = ?", (new_attempts, rec_id))
            conn.commit()
            conn.close()
            return jsonify({"success": False, "error": "Incorrect Email verification code."}), 400

    # Verify Phone Code if provided and not yet verified
    if not phone_verified and phone_code:
        if verify_otp_hash(phone_code, row['phone_otp_hash']):
            phone_verified = True
            cursor.execute("UPDATE otp_verifications SET phone_verified = 1, phone_verified_at = ? WHERE id = ?", (now, rec_id))
        else:
            new_attempts = row['phone_attempts'] + 1
            cursor.execute("UPDATE otp_verifications SET phone_attempts = ? WHERE id = ?", (new_attempts, rec_id))
            conn.commit()
            conn.close()
            return jsonify({"success": False, "error": "Incorrect Mobile verification code."}), 400

    conn.commit()

    # If both channels are verified, activate account and establish session
    if email_verified and phone_verified:
        user_obj = None

        if purpose == "registration":
            if not name or not password:
                conn.close()
                return jsonify({"success": True, "email_verified": True, "phone_verified": True, "message": "Both channels verified. Registration details required."})

            pwd_hash = hashlib.sha256(password.encode('utf-8')).hexdigest()
            try:
                cursor.execute('''
                    INSERT INTO users (name, email, phone, password_hash, role, store_name, email_verified, phone_verified, email_verified_at, phone_verified_at, status, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, 1, 1, ?, ?, 'ACTIVE', ?, ?)
                ''', (name, email, phone, pwd_hash, role, store_name, now, now, now, now))
                user_id = cursor.lastrowid
            except sqlite3.IntegrityError:
                cursor.execute("SELECT id FROM users WHERE email = ? OR phone = ?", (email, phone))
                user_id = cursor.fetchone()['id']

            user_obj = {
                "id": user_id,
                "name": name,
                "email": email,
                "phone": phone,
                "role": role,
                "store_name": store_name
            }
        else:
            cursor.execute("SELECT id, name, email, phone, role, store_name FROM users WHERE email = ? OR phone = ?", (email, phone))
            u_row = cursor.fetchone()
            if u_row:
                user_obj = {
                    "id": u_row['id'],
                    "name": u_row['name'],
                    "email": u_row['email'],
                    "phone": u_row['phone'],
                    "role": u_row['role'],
                    "store_name": u_row['store_name']
                }

        # Clear challenge
        cursor.execute("DELETE FROM otp_verifications WHERE id = ?", (rec_id,))
        conn.commit()
        conn.close()

        if user_obj:
            session.permanent = True
            session['user'] = user_obj

        return jsonify({
            "success": True,
            "fully_verified": True,
            "email_verified": True,
            "phone_verified": True,
            "message": "Account fully verified and authenticated!",
            "user": user_obj
        })

    conn.close()
    return jsonify({
        "success": True,
        "fully_verified": False,
        "email_verified": email_verified,
        "phone_verified": phone_verified,
        "message": "Partial verification successful. Please complete the remaining channel."
    })


# ==============================================================================
# Independent Channel Resend Endpoint
# ==============================================================================

@auth_bp.route('/api/auth/resend-channel-otp', methods=['POST'])
@auth_bp.route('/api/auth/resend-otp', methods=['POST'])
def resend_channel_otp():
    """
    Resends a fresh 6-digit OTP to a specific channel ('email' or 'phone') or both,
    enforcing independent 60-second cooldown per channel.
    """
    data = request.json or {}
    email = normalize_email(data.get("email", ""))
    phone = normalize_phone(data.get("phone", ""))
    channel = data.get("channel", "all").lower()

    conn = get_db_connection()
    cursor = conn.cursor()

    cursor.execute('''
        SELECT id, email_last_sent_at, phone_last_sent_at, email_verified, phone_verified
        FROM otp_verifications
        WHERE email = ? OR phone = ?
        ORDER BY id DESC LIMIT 1
    ''', (email, phone))
    row = cursor.fetchone()

    now = datetime.utcnow()
    expires_at = (now + timedelta(minutes=OTP_EXPIRY_MINUTES)).isoformat()

    results = {}

    if channel in ("email", "all") and email:
        # Check email cooldown
        if row and row['email_last_sent_at']:
            last_sent = datetime.fromisoformat(row['email_last_sent_at'])
            elapsed = (now - last_sent).total_seconds()
            if elapsed < OTP_RESEND_COOLDOWN_SECONDS:
                remaining = int(OTP_RESEND_COOLDOWN_SECONDS - elapsed)
                conn.close()
                return jsonify({"success": False, "error": f"Please wait {remaining}s before requesting a new email code.", "remaining_seconds": remaining}), 429

        fresh_email_otp = generate_secure_otp()
        fresh_email_hash = hash_otp(fresh_email_otp)

        if row:
            cursor.execute('''
                UPDATE otp_verifications
                SET email_otp_hash = ?, email_last_sent_at = ?, email_attempts = 0, expires_at = ?
                WHERE id = ?
            ''', (fresh_email_hash, now.isoformat(), expires_at, row['id']))
        else:
            dummy_phone_hash = hash_otp("000000")
            cursor.execute('''
                INSERT INTO otp_verifications (
                    email, phone, email_otp_hash, phone_otp_hash, email_last_sent_at, phone_last_sent_at, last_sent_at,
                    max_attempts, expires_at, created_at, purpose
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'resend')
            ''', (email, phone, fresh_email_hash, dummy_phone_hash, now.isoformat(), now.isoformat(), now.isoformat(), OTP_MAX_ATTEMPTS, expires_at, now.isoformat()))

        conn.commit()
        ok, prov, msg = notification_service.send_email_otp(email, "Pharmora Partner", fresh_email_otp, OTP_EXPIRY_MINUTES)
        results["email"] = {"requested": True, "provider": prov, "providerAccepted": ok, "message": msg}
        if APP_ENV == "development":
            results["dev_email_otp"] = fresh_email_otp

    if channel in ("phone", "mobile", "all") and phone:
        # Check phone cooldown
        if row and row['phone_last_sent_at']:
            last_sent = datetime.fromisoformat(row['phone_last_sent_at'])
            elapsed = (now - last_sent).total_seconds()
            if elapsed < OTP_RESEND_COOLDOWN_SECONDS:
                remaining = int(OTP_RESEND_COOLDOWN_SECONDS - elapsed)
                conn.close()
                return jsonify({"success": False, "error": f"Please wait {remaining}s before requesting a new mobile SMS code.", "remaining_seconds": remaining}), 429

        fresh_phone_otp = generate_secure_otp()
        fresh_phone_hash = hash_otp(fresh_phone_otp)

        if row:
            cursor.execute('''
                UPDATE otp_verifications
                SET phone_otp_hash = ?, phone_last_sent_at = ?, last_sent_at = ?, phone_attempts = 0, expires_at = ?
                WHERE id = ?
            ''', (fresh_phone_hash, now.isoformat(), now.isoformat(), expires_at, row['id']))
        else:
            dummy_email_hash = hash_otp("000000")
            cursor.execute('''
                INSERT INTO otp_verifications (
                    email, phone, email_otp_hash, phone_otp_hash, email_last_sent_at, phone_last_sent_at, last_sent_at,
                    max_attempts, expires_at, created_at, purpose
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'resend')
            ''', (email, phone, dummy_email_hash, fresh_phone_hash, now.isoformat(), now.isoformat(), now.isoformat(), OTP_MAX_ATTEMPTS, expires_at, now.isoformat()))

        conn.commit()
        ok, prov, msg = notification_service.send_sms_otp(phone, fresh_phone_otp, OTP_EXPIRY_MINUTES)
        results["mobile"] = {"requested": True, "provider": prov, "providerAccepted": ok, "message": msg}
        if APP_ENV == "development":
            results["dev_phone_otp"] = fresh_phone_otp

    conn.close()

    return jsonify({
        "success": True,
        "message": f"Fresh verification code request processed for {channel}.",
        "delivery": results,
        "cooldown_seconds": OTP_RESEND_COOLDOWN_SECONDS
    })


# ==============================================================================
# Diagnostic Provider Test Endpoints
# ==============================================================================

@auth_bp.route('/api/auth/test-email', methods=['POST'])
def test_email_provider():
    """Diagnostic endpoint to verify email delivery acceptance."""
    data = request.json or {}
    email = normalize_email(data.get("email", ""))
    if not is_valid_email(email):
        return jsonify({"success": False, "error": "Please provide a valid destination email address."}), 400

    accepted, prov_name, message = notification_service.send_email_otp(
        email=email,
        user_name="Pharmora Diagnostic Tester",
        email_otp="123456",
        expiry_minutes=5
    )

    return jsonify({
        "success": accepted,
        "provider": prov_name,
        "providerAccepted": accepted,
        "message": message
    })


@auth_bp.route('/api/auth/test-sms', methods=['POST'])
def test_sms_provider():
    """Diagnostic endpoint to verify SMS delivery acceptance via MSG91/configured provider."""
    data = request.json or {}
    phone = normalize_phone(data.get("phone", ""))
    if not is_valid_phone(phone):
        return jsonify({"success": False, "error": "Please provide a valid destination phone number in international format (+91XXXXXXXXXX)."}), 400

    accepted, prov_name, message = notification_service.send_sms_otp(
        phone=phone,
        phone_otp="123456",
        expiry_minutes=5
    )

    return jsonify({
        "success": accepted,
        "provider": prov_name,
        "providerAccepted": accepted,
        "message": message
    })


# ==============================================================================
# Standard Login, Session, and Logout
# ==============================================================================

@auth_bp.route('/api/auth/login', methods=['POST'])
def login():
    data = request.json or {}
    identifier = data.get("identifier", "").strip() or data.get("email", "").strip() or data.get("phone", "").strip()
    password = data.get("password", "")
    client_ip = request.remote_addr or "127.0.0.1"

    if not identifier or not password:
        return jsonify({"success": False, "error": "Please enter your Email / Mobile Phone Number and Password."}), 400

    allowed, _ = check_rate_limit(f"login:ip:{client_ip}", 10, 3600)
    if not allowed:
        return jsonify({"success": False, "error": "Too many login attempts. Account temporarily locked for 1 hour."}), 429

    conn = get_db_connection()
    cursor = conn.cursor()

    norm_email = normalize_email(identifier)
    norm_phone = normalize_phone(identifier)

    cursor.execute('''
        SELECT id, name, email, phone, password_hash, role, store_name, status, email_verified, phone_verified
        FROM users
        WHERE email = ? OR phone = ?
    ''', (norm_email, norm_phone))

    user_row = cursor.fetchone()
    conn.close()

    if not user_row:
        return jsonify({"success": False, "error": "Invalid Email/Mobile Phone Number or Password."}), 401

    if user_row['status'] in ('LOCKED', 'SUSPENDED'):
        return jsonify({"success": False, "error": "This account is currently locked. Please contact support."}), 403

    computed_hash = hashlib.sha256(password.encode('utf-8')).hexdigest()
    if not hmac.compare_digest(computed_hash, user_row['password_hash']):
        return jsonify({"success": False, "error": "Invalid Email/Mobile Phone Number or Password."}), 401

    user_payload = {
        "id": user_row['id'],
        "name": user_row['name'],
        "email": user_row['email'],
        "phone": user_row['phone'],
        "role": user_row['role'],
        "store_name": user_row['store_name']
    }

    session.permanent = True
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
