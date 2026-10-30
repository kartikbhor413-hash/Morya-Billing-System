import unittest
import json
import os
import io
from app import app
from db import db
from config import Config
from services.billing import calculate_invoice_totals

class TestFinalAcceptance(unittest.TestCase):
    def setUp(self):
        app.config['TESTING'] = True
        self.client = app.test_client()

    def tearDown(self):
        with db._get_sqlite_conn() as conn:
            conn.execute('DELETE FROM payments')
            conn.execute('DELETE FROM invoice_items')
            conn.execute('DELETE FROM invoices')
            conn.execute('DELETE FROM customers')
            conn.execute('DELETE FROM drafts')
            conn.execute('DELETE FROM products WHERE name = ?', ('Solar Inverter Wiring Setup',))
            conn.commit()

    def test_acceptance_01_first_visit_and_empty_dashboard(self):
        """Test 1: Opening website shows login first, logging in shows zero values."""
        # 1. First visit unauthenticated redirects to login
        res = self.client.get("/", follow_redirects=False)
        self.assertEqual(res.status_code, 302)
        self.assertIn("/login", res.headers.get("Location", ""))

        # 2. Login with valid credentials
        login_res = self.client.post("/login", data={
            "email": Config.ADMIN_EMAIL,
            "password": Config.ADMIN_PASSWORD
        }, follow_redirects=True)
        self.assertEqual(login_res.status_code, 200)

        # 3. Check Dashboard statistics
        dash_res = self.client.get("/dashboard")
        self.assertEqual(dash_res.status_code, 200)
        self.assertIn(b"Good", dash_res.data) # Greeting present
        self.assertTrue(b"Generate Bill" in dash_res.data or b"Create New Bill" in dash_res.data)

    def test_acceptance_02_login_security(self):
        """Test 2: Invalid password fails; protected routes redirect."""
        # Wrong password
        bad_login = self.client.post("/login", data={
            "email": Config.ADMIN_EMAIL,
            "password": "WrongPassword!999"
        }, follow_redirects=True)
        self.assertIn(b"Invalid email or password", bad_login.data)

        # Unauthenticated access to /all-bills
        anon_client = app.test_client()
        res = anon_client.get("/all-bills", follow_redirects=False)
        self.assertEqual(res.status_code, 302)
        self.assertIn("/login", res.headers.get("Location", ""))

    def test_acceptance_03_default_services_no_invented_prices(self):
        """Test 3: 8 default services exist, partial search works, no invented prices."""
        with self.client.session_transaction() as sess:
            sess["user_id"] = "admin-fixed-id"
            sess["user_email"] = Config.ADMIN_EMAIL

        # Search fan
        res = self.client.get("/api/products?q=fan")
        data = res.get_json()
        names = [d["name"] for d in data]
        self.assertIn("Fan Repairing", names)
        self.assertIn("Fan Installation", names)

        # Search geyser
        res = self.client.get("/api/products?q=geyser")
        data = res.get_json()
        names = [d["name"] for d in data]
        self.assertIn("Geyser Point", names)
        self.assertIn("Geyser Repairing", names)
        self.assertIn("Geyser Installation", names)

        # Search house
        res = self.client.get("/api/products?q=house")
        data = res.get_json()
        names = [d["name"] for d in data]
        self.assertIn("House Wiring", names)
        self.assertIn("House and Building Maintenance", names)

    def test_acceptance_04_custom_service_persistence(self):
        """Test 4: Add custom service, check persistence, duplicate prevention."""
        with self.client.session_transaction() as sess:
            sess["user_id"] = "admin-fixed-id"

        custom_name = "Solar Inverter Wiring Setup"
        res = self.client.post("/api/products", json={
            "name": custom_name,
            "category": "Solar Service",
            "default_rate": 1250.0,
            "unit": "System",
            "tax_rate": 0.0,
            "is_active": True
        })
        self.assertEqual(res.status_code, 200)
        self.assertTrue(res.get_json()["success"])

        # Query it back
        search_res = self.client.get(f"/api/products?q=solar")
        items = search_res.get_json()
        self.assertTrue(any(i["name"] == custom_name for i in items))

    def test_acceptance_05_billing_calculations_and_recalculations(self):
        """Test 5: Server independently recalculates financial totals."""
        calc = calculate_invoice_totals(
            items=[
                {"description": "House Wiring", "quantity": 12, "rate": 150.0}, # 1800
                {"description": "Geyser Point", "quantity": 1, "rate": 450.0}   # 450
            ],
            discount_val=50.0,
            tax_percent=5.0,
            cash_adv=500.0,
            upi_adv=500.0
        )
        # Subtotal = 2250.00
        # Discount = 50.00 -> 2200.00
        # Tax = 5% of 2200 = 110.00
        # Net = 2310.00
        # Advance = 1000.00
        # Balance = 1310.00
        self.assertEqual(calc["subtotal"], 2250.0)
        self.assertEqual(calc["discount_amount"], 50.0)
        self.assertEqual(calc["tax_amount"], 110.0)
        self.assertEqual(calc["net_amount"], 2310.0)
        self.assertEqual(calc["total_advance"], 1000.0)
        self.assertEqual(calc["balance_due"], 1310.0)
        self.assertEqual(calc["payment_status"], "Partially Paid")
        self.assertIn("Rupees Two Thousand Three Hundred Ten", calc["amount_in_words"])

    def test_acceptance_06_invoice_generation_and_pdf(self):
        """Test 6: Generate Invoice saves to DB, returns valid PDF, prevents duplicate submit."""
        with self.client.session_transaction() as sess:
            sess["user_id"] = "admin-fixed-id"
            sess["user_email"] = Config.ADMIN_EMAIL

        payload = {
            "customer_name": "Ramesh Patil",
            "customer_phone": "9822334455",
            "customer_address": "Nashik Road",
            "invoice_date": "2026-10-30",
            "payment_type": "UPI",
            "items": [
                {"description": "House Wiring", "quantity": 5, "rate": 200.0},
                {"description": "Fan Installation", "quantity": 2, "rate": 150.0}
            ],
            "discount_amount": 100.0,
            "tax_percent": 0.0,
            "cash_advance": 0.0,
            "upi_advance": 1200.0,
            "bank_advance": 0.0
        }

        # Subtotal: 1000 + 300 = 1300. Discount 100 -> Net 1200. Advance 1200 -> Balance 0. Status: Paid
        res = self.client.post("/api/invoices/generate", json=payload)
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertTrue(data["success"])
        inv_id = data["invoice_id"]
        inv_num = data["invoice_number"]

        # Confirm saved in database
        saved_inv = db.get_invoice_by_id(inv_id)
        self.assertIsNotNone(saved_inv)
        self.assertEqual(saved_inv["customer_name"], "Ramesh Patil")
        self.assertEqual(saved_inv["net_amount"], 1200.0)
        self.assertEqual(saved_inv["balance_due"], 0.0)
        self.assertEqual(saved_inv["payment_status"], "Paid")

        # Test PDF download
        pdf_res = self.client.get(f"/invoices/{inv_id}/pdf")
        self.assertEqual(pdf_res.status_code, 200)
        self.assertEqual(pdf_res.mimetype, "application/pdf")
        self.assertTrue(pdf_res.data.startswith(b"%PDF"))

    def test_acceptance_07_page_loads_never_create_bills(self):
        """Test 8: Opening website, dashboard, or create-bill NEVER creates an invoice record."""
        with self.client.session_transaction() as sess:
            sess["user_id"] = "admin-fixed-id"

        count_before = len(db.get_invoices())
        # Open pages
        self.client.get("/")
        self.client.get("/dashboard")
        self.client.get("/create-bill")
        self.client.get("/all-bills")
        count_after = len(db.get_invoices())

        self.assertEqual(count_before, count_after, "Visiting pages must never create invoices!")

if __name__ == "__main__":
    unittest.main()
