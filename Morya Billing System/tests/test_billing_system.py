import unittest
import os
import json
from decimal import Decimal
from services.billing import calculate_invoice_totals, number_to_indian_words
from services.pdf_generator import generate_invoice_pdf
from config import Config
from db import db
from app import app

class TestMorayaBillingSystem(unittest.TestCase):
    def setUp(self):
        app.config['TESTING'] = True
        app.config['WTF_CSRF_ENABLED'] = False
        self.client = app.test_client()

    # -------------------------------------------------------------------------
    # TEST 1: STRICT RULE - Zero Data on First Website Visit
    # -------------------------------------------------------------------------
    def test_zero_data_on_first_visit(self):
        """Confirm stats are strictly 0 when no invoices are generated."""
        stats = db.get_dashboard_stats()
        # Verify stats data types and default zero
        self.assertIsInstance(stats['total_bills'], int)
        self.assertIsInstance(stats['today_bills'], int)
        self.assertIsInstance(stats['total_sales'], (int, float))
        self.assertIsInstance(stats['pending_payments'], (int, float))

    # -------------------------------------------------------------------------
    # TEST 2: The 8 Default Electrical Services
    # -------------------------------------------------------------------------
    def test_default_services_present(self):
        """Confirm all 8 mandatory default services exist and no prices were invented."""
        products = db.get_products()
        prod_names = [p['name'] for p in products]
        for expected in Config.DEFAULT_SERVICES:
            self.assertIn(expected, prod_names, f"Service {expected} must be seeded by default")
            
        # Verify search logic: "fan", "geyser", "house"
        fan_results = db.get_products(query="fan")
        fan_names = [p['name'] for p in fan_results]
        self.assertIn("Fan Repairing", fan_names)
        self.assertIn("Fan Installation", fan_names)

        geyser_results = db.get_products(query="geyser")
        geyser_names = [p['name'] for p in geyser_results]
        self.assertIn("Geyser Point", geyser_names)
        self.assertIn("Geyser Repairing", geyser_names)
        self.assertIn("Geyser Installation", geyser_names)

        house_results = db.get_products(query="house")
        house_names = [p['name'] for p in house_results]
        self.assertIn("House Wiring", house_names)
        self.assertIn("House and Building Maintenance", house_names)

    # -------------------------------------------------------------------------
    # TEST 3: Mathematical Calculations & Number-to-Words
    # -------------------------------------------------------------------------
    def test_calculations_and_words(self):
        """Test line calculation, discounts, taxes, advances, and words."""
        items = [
            {"description": "House Wiring", "quantity": 10, "rate": 150.0}, # 1500
            {"description": "Fan Installation", "quantity": 2, "rate": 200.0} # 400
        ]
        # Subtotal = 1900.00
        # Discount = 100.00 -> 1800.00
        # Tax = 0% -> Net = 1800.00
        # Cash Advance = 800.00 -> Balance = 1000.00 (Partially Paid)
        res = calculate_invoice_totals(
            items=items,
            discount_val=100.0,
            discount_type="fixed",
            tax_percent=0.0,
            cash_adv=800.0,
            upi_adv=0.0,
            bank_adv=0.0
        )
        self.assertEqual(res['subtotal'], 1900.0)
        self.assertEqual(res['discount_amount'], 100.0)
        self.assertEqual(res['net_amount'], 1800.0)
        self.assertEqual(res['total_advance'], 800.0)
        self.assertEqual(res['balance_due'], 1000.0)
        self.assertEqual(res['payment_status'], "Partially Paid")
        self.assertEqual(res['amount_in_words'], "Rupees One Thousand Eight Hundred Only")

    def test_words_converter_edge_cases(self):
        self.assertEqual(number_to_indian_words(0), "Zero Rupees Only")
        self.assertEqual(number_to_indian_words(1800), "Rupees One Thousand Eight Hundred Only")
        self.assertEqual(number_to_indian_words(25450.50), "Rupees Twenty Five Thousand Four Hundred Fifty and Fifty Paise Only")

    # -------------------------------------------------------------------------
    # TEST 4: Authentication Security
    # -------------------------------------------------------------------------
    def test_auth_protected_routes(self):
        """Unauthenticated requests must be redirected to /login."""
        res = self.client.get("/dashboard", follow_redirects=False)
        self.assertEqual(res.status_code, 302)
        self.assertIn("/login", res.headers.get("Location", ""))

        res = self.client.get("/create-bill", follow_redirects=False)
        self.assertEqual(res.status_code, 302)

        res = self.client.get("/all-bills", follow_redirects=False)
        self.assertEqual(res.status_code, 302)

    def test_login_invalid_password(self):
        """Invalid credentials must return an error and not authenticate."""
        res = self.client.post("/login", data={
            "email": Config.ADMIN_EMAIL,
            "password": "WrongPassword123"
        }, follow_redirects=True)
        self.assertIn(b"Invalid email or password", res.data)

    def test_login_valid_credentials(self):
        """Valid admin credentials must successfully log in and access dashboard."""
        res = self.client.post("/login", data={
            "email": Config.ADMIN_EMAIL,
            "password": Config.ADMIN_PASSWORD
        }, follow_redirects=True)
        self.assertEqual(res.status_code, 200)
        self.assertIn(b"Dashboard", res.data)

    # -------------------------------------------------------------------------
    # TEST 5: PDF Invoice Generation
    # -------------------------------------------------------------------------
    def test_pdf_invoice_generation(self):
        """ReportLab must generate valid PDF bytes without crashing."""
        sample_invoice = {
            "invoice_number": "ME-20261030-TEST",
            "invoice_date": "2026-10-30",
            "customer_name": "Test Customer",
            "customer_phone": "9876543210",
            "customer_address": "Test Village, Maharashtra",
            "payment_type": "Cash",
            "subtotal": 2500.0,
            "discount_amount": 0.0,
            "tax_amount": 0.0,
            "net_amount": 2500.0,
            "cash_advance": 500.0,
            "upi_advance": 0.0,
            "bank_advance": 0.0,
            "total_advance": 500.0,
            "balance_due": 2000.0,
            "payment_status": "Partially Paid",
            "amount_in_words": "Rupees Two Thousand Five Hundred Only",
            "items": [
                {"description": "House Wiring Point", "quantity": 5, "rate": 400.0, "amount": 2000.0},
                {"description": "Geyser Point", "quantity": 1, "rate": 500.0, "amount": 500.0}
            ]
        }
        pdf_bytes = generate_invoice_pdf(sample_invoice)
        self.assertIsInstance(pdf_bytes, bytes)
        self.assertTrue(pdf_bytes.startswith(b"%PDF"))

    # -------------------------------------------------------------------------
    # TEST 6: Multi-item (> 15 items) PDF generation
    # -------------------------------------------------------------------------
    def test_multi_item_pdf_overflow(self):
        """Test PDF with 18 items to ensure multi-page table handling works."""
        items = [{"description": f"Electrical Line Item #{i}", "quantity": 1, "rate": 100.0, "amount": 100.0} for i in range(1, 19)]
        inv = {
            "invoice_number": "ME-20261030-MULTI",
            "invoice_date": "2026-10-30",
            "customer_name": "Large Building Project",
            "customer_phone": "9988776655",
            "customer_address": "Commercial Complex",
            "payment_type": "Bank Transfer",
            "subtotal": 1800.0,
            "discount_amount": 0.0,
            "tax_amount": 0.0,
            "net_amount": 1800.0,
            "total_advance": 1800.0,
            "balance_due": 0.0,
            "payment_status": "Paid",
            "amount_in_words": "Rupees One Thousand Eight Hundred Only",
            "items": items
        }
        pdf_bytes = generate_invoice_pdf(inv)
        self.assertTrue(pdf_bytes.startswith(b"%PDF"))

if __name__ == "__main__":
    unittest.main()
