"""Local SQLite authentication for AI Quest."""

import hashlib
import hmac
import secrets
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "data" / "ai_quest.db"
OTP_VALIDITY_MINUTES = 5
MAX_OTP_ATTEMPTS = 5
PBKDF2_ITERATIONS = 200_000


def get_connection():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(DB_PATH)
    connection.row_factory = sqlite3.Row
    return connection


def initialize_auth_database():
    with get_connection() as connection:
        connection.execute("""
            CREATE TABLE IF NOT EXISTS user_accounts (
                user_id INTEGER PRIMARY KEY AUTOINCREMENT,
                full_name TEXT NOT NULL,
                email TEXT NOT NULL COLLATE NOCASE UNIQUE,
                password_hash TEXT NOT NULL,
                password_salt TEXT NOT NULL,
                is_verified INTEGER NOT NULL DEFAULT 0,
                otp_hash TEXT,
                otp_salt TEXT,
                otp_expires_at TEXT,
                otp_attempts INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL
            )
        """)
        connection.commit()


def hash_value(value, salt):
    return hashlib.pbkdf2_hmac(
        "sha256", value.encode("utf-8"), salt.encode("utf-8"), PBKDF2_ITERATIONS
    ).hex()


def _new_otp_values():
    otp = f"{secrets.randbelow(1_000_000):06d}"
    salt = secrets.token_hex(16)
    otp_hash = hash_value(otp, salt)
    expires = (datetime.now(timezone.utc) + timedelta(minutes=OTP_VALIDITY_MINUTES)).isoformat()
    return otp, salt, otp_hash, expires


def create_account(full_name, email, password):
    full_name = (full_name or "").strip()
    email = (email or "").strip().lower()
    if not full_name or not email or not password:
        return False, "Please fill in all fields.", None
    if "@" not in email or "." not in email.rsplit("@", 1)[-1]:
        return False, "Enter a valid email address.", None
    if len(password) < 8:
        return False, "Password must contain at least 8 characters.", None

    password_salt = secrets.token_hex(16)
    password_hash = hash_value(password, password_salt)
    otp, otp_salt, otp_hash, expires = _new_otp_values()
    try:
        with get_connection() as connection:
            connection.execute("""
                INSERT INTO user_accounts
                (full_name, email, password_hash, password_salt, is_verified,
                 otp_hash, otp_salt, otp_expires_at, otp_attempts, created_at)
                VALUES (?, ?, ?, ?, 0, ?, ?, ?, 0, ?)
            """, (full_name, email, password_hash, password_salt, otp_hash,
                  otp_salt, expires, datetime.now(timezone.utc).isoformat()))
            connection.commit()
        return True, "Account created. Verify your OTP.", otp
    except sqlite3.IntegrityError:
        return False, "An account with this email already exists.", None


def _verify_and_consume_otp(connection, row, entered_otp):
    if not row["otp_hash"] or not row["otp_salt"] or not row["otp_expires_at"]:
        return False, "Please request a new OTP."
    if row["otp_attempts"] >= MAX_OTP_ATTEMPTS:
        return False, "Too many incorrect attempts. Request a new OTP."
    try:
        expires = datetime.fromisoformat(row["otp_expires_at"])
        if expires.tzinfo is None:
            expires = expires.replace(tzinfo=timezone.utc)
    except (TypeError, ValueError):
        return False, "OTP is invalid. Request a new OTP."
    if datetime.now(timezone.utc) > expires:
        return False, "OTP expired. Request a new OTP."
    if not (entered_otp or "").isdigit() or len(entered_otp) != 6:
        connection.execute("UPDATE user_accounts SET otp_attempts = otp_attempts + 1 WHERE user_id = ?", (row["user_id"],))
        connection.commit()
        return False, "Enter the 6-digit OTP."
    candidate = hash_value(entered_otp, row["otp_salt"])
    if not hmac.compare_digest(candidate, row["otp_hash"]):
        connection.execute("UPDATE user_accounts SET otp_attempts = otp_attempts + 1 WHERE user_id = ?", (row["user_id"],))
        connection.commit()
        return False, "Incorrect OTP. Please try again."
    return True, "OTP verified."


def verify_otp(email, entered_otp):
    email = (email or "").strip().lower()
    with get_connection() as connection:
        row = connection.execute("SELECT * FROM user_accounts WHERE email = ?", (email,)).fetchone()
        if not row:
            return False, "Account not found."
        if row["is_verified"]:
            return False, "This account is already verified."
        ok, message = _verify_and_consume_otp(connection, row, (entered_otp or "").strip())
        if not ok:
            return False, message
        connection.execute("""
            UPDATE user_accounts SET is_verified = 1, otp_hash = NULL, otp_salt = NULL,
            otp_expires_at = NULL, otp_attempts = 0 WHERE user_id = ?
        """, (row["user_id"],))
        connection.commit()
        return True, "Email verification successful."


def login_user(email, password):
    email = (email or "").strip().lower()
    with get_connection() as connection:
        row = connection.execute("SELECT * FROM user_accounts WHERE email = ?", (email,)).fetchone()
    if not row:
        return False, "Invalid email or password.", None
    if not row["is_verified"]:
        return False, "Please verify your email using the OTP first.", None
    candidate = hash_value(password or "", row["password_salt"])
    if not hmac.compare_digest(candidate, row["password_hash"]):
        return False, "Invalid email or password.", None
    return True, "Login successful.", {"user_id": row["user_id"], "full_name": row["full_name"], "email": row["email"]}


def request_password_reset(email):
    email = (email or "").strip().lower()
    if not email:
        return False, "Enter your registered email address.", None
    otp, otp_salt, otp_hash, expires = _new_otp_values()
    with get_connection() as connection:
        row = connection.execute("SELECT user_id, is_verified FROM user_accounts WHERE email = ?", (email,)).fetchone()
        if not row or not row["is_verified"]:
            return False, "No verified account was found with that email.", None
        connection.execute("""
            UPDATE user_accounts SET otp_hash = ?, otp_salt = ?, otp_expires_at = ?, otp_attempts = 0
            WHERE user_id = ?
        """, (otp_hash, otp_salt, expires, row["user_id"]))
        connection.commit()
    return True, "Password reset OTP generated. It is valid for 5 minutes.", otp


def reset_password_with_otp(email, entered_otp, new_password):
    email = (email or "").strip().lower()
    if len(new_password or "") < 8:
        return False, "New password must contain at least 8 characters."
    with get_connection() as connection:
        row = connection.execute("SELECT * FROM user_accounts WHERE email = ?", (email,)).fetchone()
        if not row or not row["is_verified"]:
            return False, "Verified account not found."
        ok, message = _verify_and_consume_otp(connection, row, (entered_otp or "").strip())
        if not ok:
            return False, message
        salt = secrets.token_hex(16)
        password_hash = hash_value(new_password, salt)
        connection.execute("""
            UPDATE user_accounts SET password_hash = ?, password_salt = ?, otp_hash = NULL,
            otp_salt = NULL, otp_expires_at = NULL, otp_attempts = 0 WHERE user_id = ?
        """, (password_hash, salt, row["user_id"]))
        connection.commit()
    return True, "Password reset successful. You can now log in with your new password."


def change_password(user_id, current_password, new_password):
    if len(new_password or "") < 8:
        return False, "New password must contain at least 8 characters."
    with get_connection() as connection:
        row = connection.execute("SELECT * FROM user_accounts WHERE user_id = ?", (user_id,)).fetchone()
        if not row:
            return False, "User account not found."
        candidate = hash_value(current_password or "", row["password_salt"])
        if not hmac.compare_digest(candidate, row["password_hash"]):
            return False, "Current password is incorrect."
        salt = secrets.token_hex(16)
        password_hash = hash_value(new_password, salt)
        connection.execute("UPDATE user_accounts SET password_hash = ?, password_salt = ? WHERE user_id = ?",
                           (password_hash, salt, user_id))
        connection.commit()
    return True, "Password changed successfully."


if __name__ == "__main__":
    initialize_auth_database()
    print("Authentication database initialized successfully.")
    print("Database:", DB_PATH)
