import os
import sqlite3
import json
import hashlib
from datetime import datetime

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "datasets", "pharmora_auth.db")
LEGACY_USERS_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "datasets", "users.json")

def get_db_connection():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH, timeout=30.0)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout = 30000")
    return conn

def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()

    # 1. Users Table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            phone TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            role TEXT NOT NULL DEFAULT 'owner',
            store_name TEXT NOT NULL DEFAULT 'Pharmora Pharmacy',
            email_verified INTEGER NOT NULL DEFAULT 1,
            phone_verified INTEGER NOT NULL DEFAULT 1,
            email_verified_at TEXT NULL,
            phone_verified_at TEXT NULL,
            status TEXT NOT NULL DEFAULT 'ACTIVE',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
    ''')

    # 2. OTP Verifications Table (Dual Channel Architecture)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS otp_verifications (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NULL,
            email TEXT NOT NULL,
            phone TEXT NOT NULL,
            email_otp_hash TEXT NOT NULL,
            phone_otp_hash TEXT NOT NULL,
            email_verified INTEGER NOT NULL DEFAULT 0,
            phone_verified INTEGER NOT NULL DEFAULT 0,
            email_verified_at TEXT NULL,
            phone_verified_at TEXT NULL,
            email_last_sent_at TEXT NOT NULL DEFAULT '',
            phone_last_sent_at TEXT NOT NULL DEFAULT '',
            last_sent_at TEXT NOT NULL DEFAULT '',
            email_attempts INTEGER NOT NULL DEFAULT 0,
            phone_attempts INTEGER NOT NULL DEFAULT 0,
            max_attempts INTEGER NOT NULL DEFAULT 5,
            expires_at TEXT NOT NULL,
            created_at TEXT NOT NULL,
            purpose TEXT NOT NULL DEFAULT 'registration',
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    ''')

    # 3. Rate Limits Table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS rate_limits (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            action_key TEXT UNIQUE NOT NULL,
            count INTEGER NOT NULL DEFAULT 1,
            first_attempt_at TEXT NOT NULL,
            last_attempt_at TEXT NOT NULL
        )
    ''')

    # Ensure all migration columns are present in users
    try:
        cursor.execute("ALTER TABLE users ADD COLUMN email_verified_at TEXT")
    except sqlite3.OperationalError:
        pass
    try:
        cursor.execute("ALTER TABLE users ADD COLUMN phone_verified_at TEXT")
    except sqlite3.OperationalError:
        pass
    try:
        cursor.execute("ALTER TABLE users ADD COLUMN email_verified INTEGER NOT NULL DEFAULT 1")
    except sqlite3.OperationalError:
        pass
    try:
        cursor.execute("ALTER TABLE users ADD COLUMN phone_verified INTEGER NOT NULL DEFAULT 1")
    except sqlite3.OperationalError:
        pass

    # Ensure all migration columns are present in otp_verifications
    try:
        cursor.execute("ALTER TABLE otp_verifications ADD COLUMN last_sent_at TEXT DEFAULT ''")
    except sqlite3.OperationalError:
        pass
    try:
        cursor.execute("ALTER TABLE otp_verifications ADD COLUMN email_last_sent_at TEXT DEFAULT ''")
    except sqlite3.OperationalError:
        pass
    try:
        cursor.execute("ALTER TABLE otp_verifications ADD COLUMN phone_last_sent_at TEXT DEFAULT ''")
    except sqlite3.OperationalError:
        pass
    try:
        cursor.execute("ALTER TABLE otp_verifications ADD COLUMN email_attempts INTEGER NOT NULL DEFAULT 0")
    except sqlite3.OperationalError:
        pass
    try:
        cursor.execute("ALTER TABLE otp_verifications ADD COLUMN phone_attempts INTEGER NOT NULL DEFAULT 0")
    except sqlite3.OperationalError:
        pass

    conn.commit()

    # Seed initial demo users if table is empty
    cursor.execute("SELECT COUNT(*) as count FROM users")
    count = cursor.fetchone()['count']
    if count == 0:
        seed_default_users(cursor, conn)

    conn.close()

def seed_default_users(cursor, conn):
    default_users = [
        {
            "name": "Dr. Sarah Jenkins",
            "email": "owner@pharma.com",
            "phone": "+919811223344",
            "password_hash": hashlib.sha256("owner123".encode()).hexdigest(),
            "role": "owner",
            "store_name": "HealthCare Central Pharmacy"
        },
        {
            "name": "Rajesh Kumar",
            "email": "manager@pharma.com",
            "phone": "+919876543210",
            "password_hash": hashlib.sha256("manager123".encode()).hexdigest(),
            "role": "manager",
            "store_name": "HealthCare Central Pharmacy"
        },
        {
            "name": "Amit Sharma",
            "email": "staff@pharma.com",
            "phone": "+919988776655",
            "password_hash": hashlib.sha256("staff123".encode()).hexdigest(),
            "role": "staff",
            "store_name": "HealthCare Central Pharmacy"
        }
    ]

    if os.path.exists(LEGACY_USERS_FILE):
        try:
            with open(LEGACY_USERS_FILE, "r") as f:
                legacy = json.load(f)
                for email, u in legacy.items():
                    if not any(d['email'] == email for d in default_users):
                        phone = u.get("phone", "9800000000")
                        if not phone.startswith("+91"):
                            phone = f"+91{phone.lstrip('0')}"
                        default_users.append({
                            "name": u.get("name", "Pharmora User"),
                            "email": email,
                            "phone": phone,
                            "password_hash": u.get("password_hash", hashlib.sha256("password123".encode()).hexdigest()),
                            "role": u.get("role", "owner"),
                            "store_name": u.get("store_name", "Pharmora Pharmacy")
                        })
        except Exception:
            pass

    now = datetime.utcnow().isoformat()
    for u in default_users:
        try:
            cursor.execute('''
                INSERT INTO users (name, email, phone, password_hash, role, store_name, email_verified, phone_verified, email_verified_at, phone_verified_at, status, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, 1, 1, ?, ?, 'ACTIVE', ?, ?)
            ''', (u['name'], u['email'], u['phone'], u['password_hash'], u['role'], u['store_name'], now, now, now, now))
        except sqlite3.IntegrityError:
            pass

    conn.commit()

# Initialize tables
init_db()
