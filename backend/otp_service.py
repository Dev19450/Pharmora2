import os
import re
import hmac
import hashlib
import secrets
import smtplib
import urllib.request
import urllib.parse
import json
import logging
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, timedelta

logger = logging.getLogger("pharmora.otp")
logging.basicConfig(level=logging.INFO)

SECRET_KEY = os.environ.get("SECRET_KEY", "pharmora_super_secret_cryptographic_key_2026")
APP_ENV = os.environ.get("APP_ENV", "development")

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

def generate_secure_otp() -> str:
    """Generates a cryptographically secure 6-digit OTP with leading zero support."""
    return f"{secrets.randbelow(1_000_000):06d}"

def hash_otp(otp: str, salt: str = SECRET_KEY) -> str:
    """Computes a cryptographically secure HMAC-SHA256 hash of the OTP."""
    return hmac.new(salt.encode('utf-8'), otp.encode('utf-8'), hashlib.sha256).hexdigest()

def verify_otp_hash(provided_otp: str, stored_hash: str, salt: str = SECRET_KEY) -> bool:
    """Constant-time comparison of the provided OTP against the stored hash."""
    if not provided_otp or not stored_hash:
        return False
    computed_hash = hash_otp(provided_otp, salt)
    return hmac.compare_digest(computed_hash, stored_hash)


# ==============================================================================
# Email Notification Providers Architecture
# ==============================================================================

class BaseEmailProvider:
    provider_name = "base"
    def send_otp(self, to_email: str, user_name: str, otp: str, expiry_minutes: int = 5) -> tuple[bool, str]:
        raise NotImplementedError

    def send_test(self, to_email: str) -> tuple[bool, str]:
        raise NotImplementedError

class SMTPProvider(BaseEmailProvider):
    provider_name = "smtp"

    def __init__(self):
        self.host = os.environ.get("SMTP_HOST", "")
        self.port = int(os.environ.get("SMTP_PORT", 587))
        self.username = os.environ.get("SMTP_USERNAME", "")
        self.password = os.environ.get("SMTP_PASSWORD", "")
        self.from_addr = os.environ.get("EMAIL_FROM", "Pharmora Security <noreply@pharmora.health>")

    def send_otp(self, to_email: str, user_name: str, otp: str, expiry_minutes: int = 5) -> tuple[bool, str]:
        if not self.host or not self.username or not self.password:
            return False, "SMTP credentials missing in configuration (SMTP_HOST / SMTP_USERNAME / SMTP_PASSWORD)."

        subject = "Your Pharmora Verification Code"
        text_content = f"""Hello {user_name},

Welcome to Pharmora.

Your verification code is: {otp}

This code expires in {expiry_minutes} minutes.

For your security, do not share this code with anyone.
If you did not request this verification, you can safely ignore this email.

Regards,
Pharmora - Intelligent Pharmacy Growth Partner"""

        html_content = f"""
        <!DOCTYPE html>
        <html>
        <body style="font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif; background-color: #0F0F0F; color: #F8F8F8; padding: 24px; margin: 0;">
          <div style="max-width: 500px; margin: 0 auto; background: #202020; border-radius: 12px; border: 1px solid rgba(93,214,44,0.35); padding: 28px; box-shadow: 0 10px 30px rgba(0,0,0,0.6);">
            <div style="text-align: center; margin-bottom: 20px;">
              <h1 style="color: #5DD62C; margin: 0; font-size: 26px; font-weight: 800; letter-spacing: -0.5px;">Pharmora</h1>
              <p style="color: #a3a3a3; font-size: 13px; margin-top: 4px;">Intelligent Pharmacy Growth Partner</p>
            </div>
            
            <p style="font-size: 15px; color: #F8F8F8;">Hello <strong>{user_name}</strong>,</p>
            <p style="font-size: 14px; color: #d4d4d4;">Please use the verification code below to authenticate your Pharmora email address:</p>
            
            <div style="background: rgba(93,214,44,0.12); border: 1px dashed #5DD62C; border-radius: 10px; padding: 18px; text-align: center; margin: 24px 0;">
              <span style="font-family: monospace; font-size: 34px; font-weight: 800; letter-spacing: 8px; color: #5DD62C;">{otp}</span>
            </div>
            
            <p style="font-size: 13px; color: #a3a3a3;">This verification code is valid for <strong>{expiry_minutes} minutes</strong> and can only be used once.</p>
            <p style="font-size: 12px; color: #737373; margin-top: 20px; border-top: 1px solid rgba(255,255,255,0.08); padding-top: 14px;">
              For your security, never share this OTP with anyone. If you did not request this code, you can safely disregard this email.
            </p>
          </div>
        </body>
        </html>
        """

        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = self.from_addr
        msg["To"] = to_email
        msg.attach(MIMEText(text_content, "plain"))
        msg.attach(MIMEText(html_content, "html"))

        try:
            logger.info(f"Connecting to SMTP server {self.host}:{self.port} to send OTP to {to_email}...")
            with smtplib.SMTP(self.host, self.port, timeout=10) as server:
                server.starttls()
                server.login(self.username, self.password)
                server.sendmail(self.from_addr, [to_email], msg.as_string())
            logger.info(f"✓ SMTP accepted email delivery for {to_email}")
            return True, "Email dispatched successfully via SMTP server."
        except Exception as e:
            logger.error(f"✕ SMTP delivery error for {to_email}: {e}")
            return False, f"SMTP delivery failed: {str(e)}"

    def send_test(self, to_email: str) -> tuple[bool, str]:
        return self.send_otp(to_email, "Pharmora Admin", "123456", expiry_minutes=5)

class ResendProvider(BaseEmailProvider):
    provider_name = "resend"

    def __init__(self):
        self.api_key = os.environ.get("RESEND_API_KEY", "")
        self.from_addr = os.environ.get("EMAIL_FROM", "Pharmora <onboarding@resend.dev>")

    def send_otp(self, to_email: str, user_name: str, otp: str, expiry_minutes: int = 5) -> tuple[bool, str]:
        if not self.api_key:
            return False, "Resend API key missing in environment configuration (RESEND_API_KEY)."

        url = "https://api.resend.com/emails"
        payload = {
            "from": self.from_addr,
            "to": [to_email],
            "subject": "Your Pharmora Verification Code",
            "html": f"""
              <div style="font-family: sans-serif; background: #0F0F0F; color: #F8F8F8; padding: 24px;">
                <h2 style="color: #5DD62C;">Pharmora Authentication</h2>
                <p>Hello {user_name}, your 6-digit email verification code is:</p>
                <h1 style="font-family: monospace; letter-spacing: 6px; color: #5DD62C;">{otp}</h1>
                <p>Valid for {expiry_minutes} minutes. Do not share with anyone.</p>
              </div>
            """
        }

        try:
            req = urllib.request.Request(
                url,
                data=json.dumps(payload).encode('utf-8'),
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json"
                },
                method="POST"
            )
            with urllib.request.urlopen(req, timeout=10) as resp:
                if resp.status in (200, 201):
                    logger.info(f"✓ Resend accepted email delivery for {to_email}")
                    return True, "Email dispatched successfully via Resend API."
            return False, "Resend API returned non-200 status."
        except Exception as e:
            logger.error(f"✕ Resend API error for {to_email}: {e}")
            return False, f"Resend API error: {str(e)}"

    def send_test(self, to_email: str) -> tuple[bool, str]:
        return self.send_otp(to_email, "Pharmora Admin", "123456", expiry_minutes=5)

class ConsoleEmailProvider(BaseEmailProvider):
    provider_name = "dev-console"

    def send_otp(self, to_email: str, user_name: str, otp: str, expiry_minutes: int = 5) -> tuple[bool, str]:
        if APP_ENV == "development":
            logger.info(f"📧 [DEV EMAIL OTP DISPATCH] To: {to_email} | Name: {user_name} | OTP Code: {otp} (Expires in {expiry_minutes}m)")
            return True, "Development local dispatch accepted (logged in server console)."
        else:
            return False, "Live email provider is not configured. Please configure SMTP or Resend credentials in .env."

    def send_test(self, to_email: str) -> tuple[bool, str]:
        return self.send_otp(to_email, "Pharmora Admin", "123456", expiry_minutes=5)


# ==============================================================================
# SMS Notification Providers Architecture (MSG91 & Console)
# ==============================================================================

class BaseSMSProvider:
    provider_name = "base"
    def send_otp(self, to_phone: str, otp: str, expiry_minutes: int = 5) -> tuple[bool, str]:
        raise NotImplementedError

    def send_test(self, to_phone: str) -> tuple[bool, str]:
        raise NotImplementedError

class MSG91Provider(BaseSMSProvider):
    provider_name = "msg91"

    def __init__(self):
        self.auth_key = os.environ.get("MSG91_AUTH_KEY", "")
        self.template_id = os.environ.get("MSG91_TEMPLATE_ID", "")
        self.sender_id = os.environ.get("MSG91_SENDER_ID", "PHRMOR")

    def send_otp(self, to_phone: str, otp: str, expiry_minutes: int = 5) -> tuple[bool, str]:
        if not self.auth_key:
            return False, "MSG91_AUTH_KEY is not configured in .env."

        # Normalize mobile number format for MSG91 (e.g. 919876543210)
        clean_mobile = re.sub(r'\D', '', to_phone)

        url = f"https://control.msg91.com/api/v5/otp?template_id={self.template_id}&mobile={clean_mobile}&authkey={self.auth_key}&otp={otp}"
        payload = {
            "OTP": otp,
            "expiry": str(expiry_minutes)
        }

        try:
            logger.info(f"Sending SMS OTP via MSG91 API to {clean_mobile}...")
            req = urllib.request.Request(
                url,
                data=json.dumps(payload).encode('utf-8'),
                headers={
                    "Content-Type": "application/json",
                    "authkey": self.auth_key
                },
                method="POST"
            )
            with urllib.request.urlopen(req, timeout=10) as response:
                res_data = json.loads(response.read().decode('utf-8'))
                if res_data.get("type") == "success" or response.status == 200:
                    logger.info(f"✓ MSG91 accepted SMS delivery for {to_phone}")
                    return True, "SMS accepted by MSG91 gateway."
                err_msg = res_data.get("message", "MSG91 rejected delivery request.")
                logger.error(f"✕ MSG91 delivery rejected for {to_phone}: {err_msg}")
                return False, f"MSG91 gateway rejected: {err_msg}"
        except Exception as e:
            logger.error(f"✕ MSG91 connection error for {to_phone}: {e}")
            return False, f"MSG91 delivery failure: {str(e)}"

    def send_test(self, to_phone: str) -> tuple[bool, str]:
        return self.send_otp(to_phone, "123456", expiry_minutes=5)

class ConsoleSMSProvider(BaseSMSProvider):
    provider_name = "dev-console"

    def send_otp(self, to_phone: str, otp: str, expiry_minutes: int = 5) -> tuple[bool, str]:
        if APP_ENV == "development":
            logger.info(f"📱 [DEV SMS OTP DISPATCH] To: {to_phone} | SMS: Your Pharmora verification code is {otp}. Valid for {expiry_minutes} mins.")
            return True, "Development local dispatch accepted (logged in server console)."
        else:
            return False, "Live SMS provider is not configured. Please configure MSG91 credentials in .env."

    def send_test(self, to_phone: str) -> tuple[bool, str]:
        return self.send_otp(to_phone, "123456", expiry_minutes=5)


# ==============================================================================
# Unified Notification Service Orchestrator
# ==============================================================================

class NotificationService:
    def __init__(self):
        self.reload_providers()

    def reload_providers(self):
        # Email Provider Selection
        email_prov = os.environ.get("EMAIL_PROVIDER", "").lower()
        if (email_prov == "smtp" or os.environ.get("SMTP_HOST")) and os.environ.get("SMTP_HOST") and os.environ.get("SMTP_USERNAME"):
            self.email_provider = SMTPProvider()
        elif (email_prov == "resend" or os.environ.get("RESEND_API_KEY")) and os.environ.get("RESEND_API_KEY"):
            self.email_provider = ResendProvider()
        else:
            self.email_provider = ConsoleEmailProvider()

        # SMS Provider Selection
        sms_prov = os.environ.get("SMS_PROVIDER", "").lower()
        if (sms_prov == "msg91" or os.environ.get("MSG91_AUTH_KEY")) and os.environ.get("MSG91_AUTH_KEY"):
            self.sms_provider = MSG91Provider()
        else:
            self.sms_provider = ConsoleSMSProvider()

    def send_email_otp(self, email: str, user_name: str, email_otp: str, expiry_minutes: int = 5) -> tuple[bool, str, str]:
        """Sends OTP to email channel and returns (accepted, provider_name, message)."""
        self.reload_providers()
        accepted, msg = self.email_provider.send_otp(email, user_name, email_otp, expiry_minutes)
        return accepted, self.email_provider.provider_name, msg

    def send_sms_otp(self, phone: str, phone_otp: str, expiry_minutes: int = 5) -> tuple[bool, str, str]:
        """Sends OTP to mobile SMS channel and returns (accepted, provider_name, message)."""
        self.reload_providers()
        accepted, msg = self.sms_provider.send_otp(phone, phone_otp, expiry_minutes)
        return accepted, self.sms_provider.provider_name, msg

    def send_dual_otps(self, email: str, phone: str, user_name: str, email_otp: str, phone_otp: str, expiry_minutes: int = 5) -> dict:
        """Dispatches independent OTP challenges to both email and phone channels."""
        self.reload_providers()
        email_ok, email_prov, email_msg = self.send_email_otp(email, user_name, email_otp, expiry_minutes)
        phone_ok, phone_prov, phone_msg = self.send_sms_otp(phone, phone_otp, expiry_minutes)

        return {
            "email": {
                "requested": bool(email),
                "provider": email_prov,
                "providerAccepted": email_ok,
                "message": email_msg
            },
            "mobile": {
                "requested": bool(phone),
                "provider": phone_prov,
                "providerAccepted": phone_ok,
                "message": phone_msg
            }
        }

notification_service = NotificationService()
