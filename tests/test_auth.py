import unittest
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "backend"))

from app import app
from models import get_db_connection
from otp_service import (
    generate_secure_otp,
    hash_otp,
    verify_otp_hash,
    normalize_email,
    normalize_phone,
    is_valid_email,
    is_valid_phone
)

class PharmoraAuthTestCase(unittest.TestCase):
    def setUp(self):
        self.app = app.test_client()
        self.app.testing = True

    def test_otp_crypto_generation(self):
        """Verify that generated OTP is always a 6-digit numeric string with leading zero support."""
        for _ in range(50):
            otp = generate_secure_otp()
            self.assertEqual(len(otp), 6)
            self.assertTrue(otp.isdigit())

    def test_otp_hashing_and_verification(self):
        """Verify HMAC-SHA256 constant-time hash verification."""
        otp = "018274"
        otp_hash = hash_otp(otp)
        self.assertNotEqual(otp, otp_hash)
        self.assertTrue(verify_otp_hash("018274", otp_hash))
        self.assertFalse(verify_otp_hash("018275", otp_hash))

    def test_phone_normalization(self):
        """Verify phone normalization into international standard format."""
        self.assertEqual(normalize_phone("9811223344"), "+919811223344")
        self.assertEqual(normalize_phone("09811223344"), "+919811223344")
        self.assertEqual(normalize_phone("+91 98112-23344"), "+919811223344")
        self.assertTrue(is_valid_phone("9811223344"))
        self.assertTrue(is_valid_phone("+919811223344"))
        self.assertFalse(is_valid_phone("123"))

    def test_email_normalization(self):
        """Verify email normalization and regex validation."""
        self.assertEqual(normalize_email("  Sarah@Pharmacy.COM "), "sarah@pharmacy.com")
        self.assertTrue(is_valid_email("sarah@pharmacy.com"))
        self.assertFalse(is_valid_email("invalid-email"))

    def test_dual_channel_registration_flow(self):
        """Full end-to-end registration flow with distinct Email & Mobile OTPs and provider acceptance."""
        test_email = "dual_doctor@pharmora.health"
        test_phone = "+919876500099"

        # Cleanup test user if exists
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM users WHERE email = ? OR phone = ?", (test_email, test_phone))
        cursor.execute("DELETE FROM otp_verifications WHERE email = ? OR phone = ?", (test_email, test_phone))
        cursor.execute("DELETE FROM rate_limits")
        conn.commit()
        conn.close()

        # 1. Initiate registration / send dual OTPs
        reg_res = self.app.post('/api/auth/register', json={
            "name": "Dr. Dual Channel",
            "email": test_email,
            "phone": test_phone,
            "password": "SecurePassword123",
            "store_name": "Dual Pharmacy",
            "role": "owner"
        })
        self.assertEqual(reg_res.status_code, 200)
        data = json.loads(reg_res.data)
        self.assertTrue(data.get("success"))
        
        # Verify provider status structure
        self.assertIn("email", data)
        self.assertIn("mobile", data)
        self.assertTrue(data["email"]["requested"])
        self.assertTrue(data["mobile"]["requested"])

        dev_email_otp = data.get("dev_email_otp")
        dev_phone_otp = data.get("dev_phone_otp")
        self.assertIsNotNone(dev_email_otp)
        self.assertIsNotNone(dev_phone_otp)

        # 2. Verify Email OTP independently
        email_v_res = self.app.post('/api/auth/verify-email-otp', json={
            "email": test_email,
            "otp_code": dev_email_otp
        })
        self.assertEqual(email_v_res.status_code, 200)
        email_v_data = json.loads(email_v_res.data)
        self.assertTrue(email_v_data.get("email_verified"))

        # 3. Verify Mobile OTP independently
        phone_v_res = self.app.post('/api/auth/verify-phone-otp', json={
            "phone": test_phone,
            "otp_code": dev_phone_otp
        })
        self.assertEqual(phone_v_res.status_code, 200)
        phone_v_data = json.loads(phone_v_res.data)
        self.assertTrue(phone_v_data.get("phone_verified"))

        # 4. Complete Registration & activate account
        complete_res = self.app.post('/api/auth/verify-otp', json={
            "email": test_email,
            "phone": test_phone,
            "name": "Dr. Dual Channel",
            "password": "SecurePassword123",
            "store_name": "Dual Pharmacy",
            "role": "owner",
            "purpose": "registration"
        })
        self.assertEqual(complete_res.status_code, 200)
        complete_data = json.loads(complete_res.data)
        self.assertTrue(complete_data.get("fully_verified"))
        self.assertEqual(complete_data['user']['email'], test_email)

        # 5. Check session (/api/auth/me)
        me_res = self.app.get('/api/auth/me')
        self.assertEqual(me_res.status_code, 200)
        me_data = json.loads(me_res.data)
        self.assertEqual(me_data['user']['email'], test_email)

        # 6. Logout
        logout_res = self.app.post('/api/auth/logout')
        self.assertEqual(logout_res.status_code, 200)

    def test_diagnostic_test_endpoints(self):
        """Verify POST /api/auth/test-email and POST /api/auth/test-sms endpoints."""
        email_res = self.app.post('/api/auth/test-email', json={"email": "diag_test@pharmora.health"})
        self.assertEqual(email_res.status_code, 200)
        e_data = json.loads(email_res.data)
        self.assertIn("provider", e_data)

        sms_res = self.app.post('/api/auth/test-sms', json={"phone": "+919876543210"})
        self.assertEqual(sms_res.status_code, 200)
        s_data = json.loads(sms_res.data)
        self.assertIn("provider", s_data)

    def test_login_flow(self):
        """Test authentication via registered email and phone number."""
        # 1. Login with demo owner email
        login_res = self.app.post('/api/auth/login', json={
            "identifier": "owner@pharma.com",
            "password": "owner123"
        })
        self.assertEqual(login_res.status_code, 200)
        data = json.loads(login_res.data)
        self.assertTrue(data.get("success"))
        self.assertEqual(data['user']['role'], 'owner')

        # 2. Login with phone number
        phone_login_res = self.app.post('/api/auth/login', json={
            "identifier": "9811223344",
            "password": "owner123"
        })
        self.assertEqual(phone_login_res.status_code, 200)

        # 3. Login with incorrect password -> Expect 401
        bad_login = self.app.post('/api/auth/login', json={
            "identifier": "owner@pharma.com",
            "password": "wrongpassword"
        })
        self.assertEqual(bad_login.status_code, 401)

    def test_resend_channel_cooldown(self):
        """Verify 60-second resend cooldown for specific channel."""
        email = "cooldown_test_channel@pharmora.health"
        phone = "+919876500077"

        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM users WHERE email = ? OR phone = ?", (email, phone))
        cursor.execute("DELETE FROM otp_verifications WHERE email = ? OR phone = ?", (email, phone))
        cursor.execute("DELETE FROM rate_limits")
        conn.commit()
        conn.close()

        # Send initial OTP
        res1 = self.app.post('/api/auth/register', json={
            "name": "Dr. Cooldown Test",
            "email": email,
            "phone": phone,
            "password": "Password123",
            "store_name": "Cooldown Pharmacy",
            "role": "owner"
        })
        self.assertEqual(res1.status_code, 200)

        # Immediately attempt channel resend -> Expect 429 rate limit
        resend_res = self.app.post('/api/auth/resend-channel-otp', json={
            "email": email,
            "phone": phone,
            "channel": "email"
        })
        self.assertEqual(resend_res.status_code, 429)

if __name__ == '__main__':
    unittest.main()
