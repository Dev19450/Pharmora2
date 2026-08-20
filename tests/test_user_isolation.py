import unittest
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "backend"))

from app import app
from models import get_db_connection

class UserDataIsolationTestCase(unittest.TestCase):
    def setUp(self):
        self.app = app.test_client()
        self.app.testing = True

        # Clean test accounts if exist
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM users WHERE email IN ('new_doc_a@pharmora.health', 'new_doc_b@pharmora.health')")
        cursor.execute("DELETE FROM rate_limits")
        conn.commit()
        conn.close()

    def test_new_user_starts_with_clean_slate_and_is_isolated(self):
        """Verify that newly registered users start with 0 records and datasets are isolated per user."""
        user_a_email = "new_doc_a@pharmora.health"
        user_a_phone = "+919111111111"
        user_b_email = "new_doc_b@pharmora.health"
        user_b_phone = "+919222222222"

        # 1. Register User A
        reg_a = self.app.post('/api/auth/register', json={
            "name": "Dr. User A",
            "email": user_a_email,
            "phone": user_a_phone,
            "password": "Password123",
            "store_name": "Pharmacy A",
            "role": "owner"
        })
        self.assertEqual(reg_a.status_code, 200)
        data_a = json.loads(reg_a.data)
        self.assertTrue(data_a.get("success"))

        # 2. Check User A Dashboard -> Expect Clean Slate (0 records, is_empty = True)
        dash_a = self.app.get('/api/dashboard/full')
        self.assertEqual(dash_a.status_code, 200)
        dash_a_data = json.loads(dash_a.data)
        self.assertTrue(dash_a_data.get("is_empty"))
        self.assertEqual(dash_a_data.get("record_count"), 0)
        self.assertEqual(dash_a_data.get("kpis", {}).get("total_sales"), 0)

        # 3. Add a medicine for User A via /api/stock/add
        add_res = self.app.post('/api/stock/add', json={
            "mode": "new",
            "medicine": "User A Special Medicine",
            "category": "Antibiotic",
            "company": "Pharma A",
            "added_qty": 50,
            "buy_price": 40.0,
            "sell_price": 70.0
        })
        self.assertEqual(add_res.status_code, 200)

        # Verify User A now has 1 record
        dash_a_after = self.app.get('/api/dashboard/full')
        dash_a_after_data = json.loads(dash_a_after.data)
        self.assertFalse(dash_a_after_data.get("is_empty"))
        self.assertEqual(dash_a_after_data.get("record_count"), 1)

        # 4. User A Logout
        self.app.post('/api/auth/logout')

        # 5. Register User B
        reg_b = self.app.post('/api/auth/register', json={
            "name": "Dr. User B",
            "email": user_b_email,
            "phone": user_b_phone,
            "password": "Password123",
            "store_name": "Pharmacy B",
            "role": "owner"
        })
        self.assertEqual(reg_b.status_code, 200)

        # 6. Check User B Dashboard -> Expect Clean Slate (0 records, DOES NOT see User A's medicine!)
        dash_b = self.app.get('/api/dashboard/full')
        self.assertEqual(dash_b.status_code, 200)
        dash_b_data = json.loads(dash_b.data)
        self.assertTrue(dash_b_data.get("is_empty"))
        self.assertEqual(dash_b_data.get("record_count"), 0)

        # 7. Test User B Reset Endpoint
        reset_res = self.app.post('/api/dataset/reset')
        self.assertEqual(reset_res.status_code, 200)
        reset_data = json.loads(reset_res.data)
        self.assertTrue(reset_data.get("success"))

if __name__ == '__main__':
    unittest.main()
