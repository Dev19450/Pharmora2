import unittest
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "backend"))

from app import app
from models import get_db_connection
from auth import (
    normalize_email,
    normalize_phone,
    is_valid_email,
    is_valid_phone
)

class PharmoraAuthTestCase(unittest.TestCase):
    def setUp(self):
        self.app = app.test_client()
        self.app.testing = True

        # Clear test database tables before each test
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM users WHERE email LIKE '%@test.com' OR email LIKE '%@pharmora.health' OR email = 'owner@pharma.com'")
        cursor.execute("DELETE FROM rate_limits")
        conn.commit()
        conn.close()

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

    def test_direct_registration_and_session(self):
        """Verify direct user registration without OTP verification."""
        test_email = "direct_doctor@pharmora.health"
        test_phone = "+919876500099"

        # 1. Direct registration
        reg_res = self.app.post('/api/auth/register', json={
            "name": "Dr. Direct User",
            "email": test_email,
            "phone": test_phone,
            "password": "SecurePassword123",
            "store_name": "Direct Pharmacy",
            "role": "owner"
        })
        self.assertEqual(reg_res.status_code, 200)
        data = json.loads(reg_res.data)
        self.assertTrue(data.get("success"))
        self.assertEqual(data['user']['email'], test_email)

        # 2. Check active session (/api/auth/me)
        me_res = self.app.get('/api/auth/me')
        self.assertEqual(me_res.status_code, 200)
        me_data = json.loads(me_res.data)
        self.assertEqual(me_data['user']['email'], test_email)

        # 3. Logout
        logout_res = self.app.post('/api/auth/logout')
        self.assertEqual(logout_res.status_code, 200)

        # 4. Check session after logout
        me_after_logout = self.app.get('/api/auth/me')
        self.assertEqual(me_after_logout.status_code, 401)

    def test_registration_duplicate_prevention(self):
        """Verify duplicate email or phone cannot be re-registered."""
        # First register an account
        self.app.post('/api/auth/register', json={
            "name": "Dr. First User",
            "email": "unique_owner@test.com",
            "phone": "+919811223344",
            "password": "owner123Password",
            "store_name": "Unique Pharmacy",
            "role": "owner"
        })

        # Try to register duplicate email
        res = self.app.post('/api/auth/register', json={
            "name": "Dr. Duplicate",
            "email": "unique_owner@test.com",
            "phone": "+919999988888",
            "password": "password123",
            "store_name": "Dup Pharmacy",
            "role": "owner"
        })
        self.assertEqual(res.status_code, 400)
        data = json.loads(res.data)
        self.assertFalse(data.get("success"))

    def test_login_flow(self):
        """Test authentication via registered email and phone number."""
        test_email = "registered_owner@test.com"
        test_phone = "+919811223344"
        test_pass = "owner123"

        # Register user first
        self.app.post('/api/auth/register', json={
            "name": "Dr. Sarah",
            "email": test_email,
            "phone": test_phone,
            "password": test_pass,
            "store_name": "HealthCare Central",
            "role": "owner"
        })

        # 1. Login with registered email
        login_res = self.app.post('/api/auth/login', json={
            "identifier": test_email,
            "password": test_pass
        })
        self.assertEqual(login_res.status_code, 200)
        data = json.loads(login_res.data)
        self.assertTrue(data.get("success"))
        self.assertEqual(data['user']['role'], 'owner')

        # 2. Login with phone number
        phone_login_res = self.app.post('/api/auth/login', json={
            "identifier": "9811223344",
            "password": test_pass
        })
        self.assertEqual(phone_login_res.status_code, 200)

        # 3. Login with incorrect password -> Expect 401
        bad_login = self.app.post('/api/auth/login', json={
            "identifier": test_email,
            "password": "wrongpassword"
        })
        self.assertEqual(bad_login.status_code, 401)

    def test_landing_page_accessible_and_logout(self):
        """Verify that landing page is publicly accessible and logout clears session."""
        test_email = "landing_test@test.com"
        test_pass = "pass1234"

        # Register and login
        self.app.post('/api/auth/register', json={
            "name": "Dr. Landing",
            "email": test_email,
            "phone": "+919811009988",
            "password": test_pass,
            "store_name": "Landing Pharmacy",
            "role": "owner"
        })

        # 1. Check that active session exists
        me_res = self.app.get('/api/auth/me')
        self.assertEqual(me_res.status_code, 200)
        self.assertTrue(json.loads(me_res.data).get("success"))

        # 2. Visit landing page (/) - should succeed
        home_res = self.app.get('/')
        self.assertEqual(home_res.status_code, 200)
        self.assertIn(b"PHARMORA", home_res.data)

        # 3. Explicit logout
        logout_res = self.app.post('/api/auth/logout')
        self.assertEqual(logout_res.status_code, 200)

        # 4. Verify that session is now cleared
        me_after_logout = self.app.get('/api/auth/me')
        self.assertEqual(me_after_logout.status_code, 401)
        self.assertFalse(json.loads(me_after_logout.data).get("success"))

    def test_unauthenticated_dashboard_redirects(self):
        """Verify that accessing protected dashboard without login redirects to /login."""
        dash_res = self.app.get('/dashboard', follow_redirects=False)
        self.assertEqual(dash_res.status_code, 302)
        self.assertIn('/login', dash_res.headers.get('Location', ''))

if __name__ == '__main__':
    unittest.main()
