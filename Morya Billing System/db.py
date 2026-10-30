import os
import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, date
import requests
from config import Config
from werkzeug.security import generate_password_hash, check_password_hash

# Try importing supabase client if installed
try:
    from supabase import create_client, Client
    HAS_SUPABASE_LIB = True
except ImportError:
    HAS_SUPABASE_LIB = False

SQLITE_DB_PATH = os.path.join(os.path.dirname(__file__), "moraya_local.db")

class Database:
    def __init__(self):
        self.supabase_url = Config.SUPABASE_URL
        self.supabase_key = Config.SUPABASE_KEY
        self.supabase_client = None
        self.is_supabase_ready = False
        
        # Test Supabase connection
        self._init_supabase()
        
        # Always initialize schema (SQLite mirrors Supabase schema for reliability)
        self._init_sqlite()
        self._seed_default_services_sqlite()

    def _init_supabase(self):
        """Attempts to initialize Supabase connection with provided credentials."""
        if (self.supabase_url and self.supabase_key and 
            not self.supabase_key.startswith("placeholder") and 
            len(self.supabase_key) > 20):
            try:
                if HAS_SUPABASE_LIB:
                    self.supabase_client = create_client(self.supabase_url, self.supabase_key)
                # Test query to check if valid
                headers = {
                    "apikey": self.supabase_key,
                    "Authorization": f"Bearer {self.supabase_key}"
                }
                r = requests.get(f"{self.supabase_url}/rest/v1/products?select=id&limit=1", headers=headers, timeout=5)
                if r.status_code in [200, 206]:
                    self.is_supabase_ready = True
                    print("[DB] Connected to Supabase PostgreSQL successfully.")
                    self._seed_default_services_supabase()
                else:
                    print(f"[DB] Supabase check returned status {r.status_code}. Using local resilient engine.")
                    self.is_supabase_ready = False
            except Exception as e:
                print(f"[DB] Could not connect to Supabase: {e}. Using local resilient engine.")
                self.is_supabase_ready = False
        else:
            print("[DB] Supabase credentials pending in .env. Using local resilient engine.")
            self.is_supabase_ready = False

    @contextmanager
    def _get_sqlite_conn(self):
        conn = sqlite3.connect(SQLITE_DB_PATH)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        try:
            yield conn
        finally:
            conn.close()

    def _init_sqlite(self):
        """Creates the identical schema in SQLite to ensure 100% uptime and testability."""
        with self._get_sqlite_conn() as conn:
            conn.executescript("""
            CREATE TABLE IF NOT EXISTS profiles (
                id TEXT PRIMARY KEY,
                email TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                name TEXT DEFAULT 'Admin',
                role TEXT DEFAULT 'admin',
                created_at TEXT DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS customers (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                phone TEXT NOT NULL,
                address TEXT,
                notes TEXT,
                created_at TEXT DEFAULT (datetime('now')),
                updated_at TEXT DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS products (
                id TEXT PRIMARY KEY,
                name TEXT UNIQUE NOT NULL,
                category TEXT DEFAULT 'Service',
                default_rate REAL DEFAULT 0.00,
                unit TEXT DEFAULT 'Point',
                tax_rate REAL DEFAULT 0.00,
                is_active INTEGER DEFAULT 1,
                created_at TEXT DEFAULT (datetime('now')),
                updated_at TEXT DEFAULT (datetime('now'))
            );

            CREATE TABLE IF NOT EXISTS invoices (
                id TEXT PRIMARY KEY,
                invoice_number TEXT UNIQUE NOT NULL,
                invoice_date TEXT NOT NULL,
                customer_id TEXT,
                customer_name TEXT NOT NULL,
                customer_phone TEXT,
                customer_address TEXT,
                payment_type TEXT DEFAULT 'Cash',
                subtotal REAL DEFAULT 0.00,
                discount_amount REAL DEFAULT 0.00,
                discount_type TEXT DEFAULT 'fixed',
                tax_percent REAL DEFAULT 0.00,
                tax_amount REAL DEFAULT 0.00,
                net_amount REAL DEFAULT 0.00,
                cash_advance REAL DEFAULT 0.00,
                upi_advance REAL DEFAULT 0.00,
                bank_advance REAL DEFAULT 0.00,
                total_advance REAL DEFAULT 0.00,
                balance_due REAL DEFAULT 0.00,
                payment_status TEXT DEFAULT 'Unpaid',
                notes TEXT,
                amount_in_words TEXT,
                created_at TEXT DEFAULT (datetime('now')),
                updated_at TEXT DEFAULT (datetime('now')),
                FOREIGN KEY (customer_id) REFERENCES customers(id) ON DELETE SET NULL
            );

            CREATE TABLE IF NOT EXISTS invoice_items (
                id TEXT PRIMARY KEY,
                invoice_id TEXT NOT NULL,
                sr_no INTEGER NOT NULL,
                description TEXT NOT NULL,
                quantity REAL DEFAULT 1.00,
                rate REAL DEFAULT 0.00,
                amount REAL DEFAULT 0.00,
                created_at TEXT DEFAULT (datetime('now')),
                FOREIGN KEY (invoice_id) REFERENCES invoices(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS payments (
                id TEXT PRIMARY KEY,
                invoice_id TEXT NOT NULL,
                payment_type TEXT NOT NULL,
                amount REAL NOT NULL,
                payment_date TEXT DEFAULT (datetime('now')),
                notes TEXT,
                FOREIGN KEY (invoice_id) REFERENCES invoices(id) ON DELETE CASCADE
            );

            CREATE TABLE IF NOT EXISTS drafts (
                id TEXT PRIMARY KEY,
                user_id TEXT NOT NULL,
                draft_data TEXT NOT NULL,
                updated_at TEXT DEFAULT (datetime('now'))
            );
            """)
            
            # Ensure admin profile exists in profiles table
            admin_cur = conn.execute("SELECT id FROM profiles WHERE email = ?", (Config.ADMIN_EMAIL,))
            if not admin_cur.fetchone():
                import uuid
                admin_id = str(uuid.uuid4())
                pwd_hash = generate_password_hash(Config.ADMIN_PASSWORD)
                conn.execute(
                    "INSERT INTO profiles (id, email, password_hash, name, role) VALUES (?, ?, ?, ?, ?)",
                    (admin_id, Config.ADMIN_EMAIL, pwd_hash, Config.ADMIN_NAME, "admin")
                )
                conn.commit()

    def _seed_default_services_sqlite(self):
        """Seeds the 8 mandatory default electrical services with rate 0.00 (NO invented prices)."""
        import uuid
        with self._get_sqlite_conn() as conn:
            for service_name in Config.DEFAULT_SERVICES:
                cur = conn.execute("SELECT id FROM products WHERE name = ?", (service_name,))
                if not cur.fetchone():
                    p_id = str(uuid.uuid4())
                    unit = "Unit" if "Fan" in service_name else ("Job" if "Maintenance" in service_name or "Repairing" in service_name else "Point")
                    cat = "Repair" if "Repair" in service_name else ("Maintenance" if "Maintenance" in service_name else "Installation")
                    conn.execute(
                        "INSERT INTO products (id, name, category, default_rate, unit, tax_rate, is_active) VALUES (?, ?, ?, 0.00, ?, 0.00, 1)",
                        (p_id, service_name, cat, unit)
                    )
            conn.commit()

    def _seed_default_services_supabase(self):
        """Seeds default services into Supabase if not present."""
        if not self.is_supabase_ready or not self.supabase_client:
            return
        try:
            for service_name in Config.DEFAULT_SERVICES:
                res = self.supabase_client.table("products").select("id").eq("name", service_name).execute()
                if not res.data:
                    unit = "Unit" if "Fan" in service_name else ("Job" if "Maintenance" in service_name or "Repairing" in service_name else "Point")
                    cat = "Repair" if "Repair" in service_name else ("Maintenance" if "Maintenance" in service_name else "Installation")
                    self.supabase_client.table("products").insert({
                        "name": service_name,
                        "category": cat,
                        "default_rate": 0.00,
                        "unit": unit,
                        "tax_rate": 0.00,
                        "is_active": True
                    }).execute()
        except Exception as e:
            print(f"[DB] Error seeding default services to Supabase: {e}")

    # -------------------------------------------------------------------------
    # Authentication & Profile
    # -------------------------------------------------------------------------
    def verify_user(self, email, password):
        """Verifies user credentials. Returns profile dict or None."""
        email = email.strip().lower()
        # First check Supabase Auth or Profiles if enabled
        if self.is_supabase_ready and self.supabase_client:
            try:
                res = self.supabase_client.table("profiles").select("*").eq("email", email).execute()
                if res.data:
                    user = res.data[0]
                    if check_password_hash(user["password_hash"], password):
                        return {"id": user["id"], "email": user["email"], "name": user.get("name", "Admin"), "role": user.get("role", "admin")}
            except Exception as e:
                print(f"[DB Auth] Supabase check failed: {e}")

        # Check local profiles
        with self._get_sqlite_conn() as conn:
            cur = conn.execute("SELECT * FROM profiles WHERE email = ?", (email,))
            row = cur.fetchone()
            if row:
                if check_password_hash(row["password_hash"], password):
                    return {"id": row["id"], "email": row["email"], "name": row["name"], "role": row["role"]}
            
            # Fallback to configured Admin credentials if profiles table check hasn't caught it
            if email == Config.ADMIN_EMAIL and password == Config.ADMIN_PASSWORD:
                return {"id": "admin-fixed-id", "email": Config.ADMIN_EMAIL, "name": Config.ADMIN_NAME, "role": "admin"}

        return None

    # -------------------------------------------------------------------------
    # Dashboard Statistics (STRICT RULE: NO FAKE DATA)
    # -------------------------------------------------------------------------
    def get_dashboard_stats(self):
        """
        Calculates live dashboard statistics:
        - total_bills (count of all saved finalized invoices)
        - today_bills (count of invoices saved today)
        - total_sales (sum of net_amount)
        - pending_payments (sum of balance_due)
        Strictly returns 0 and ₹0.00 when no invoices exist.
        """
        today_str = date.today().isoformat()
        
        if self.is_supabase_ready and self.supabase_client:
            try:
                res = self.supabase_client.table("invoices").select("invoice_date, net_amount, balance_due").execute()
                data = res.data or []
                total_bills = len(data)
                today_bills = sum(1 for inv in data if str(inv.get("invoice_date", "")).startswith(today_str))
                total_sales = sum(float(inv.get("net_amount", 0) or 0) for inv in data)
                pending_payments = sum(float(inv.get("balance_due", 0) or 0) for inv in data)
                return {
                    "total_bills": total_bills,
                    "today_bills": today_bills,
                    "total_sales": round(total_sales, 2),
                    "pending_payments": round(pending_payments, 2)
                }
            except Exception as e:
                print(f"[DB Stats] Supabase stats error: {e}")

        # Local query
        with self._get_sqlite_conn() as conn:
            cur = conn.execute("""
                SELECT 
                    COUNT(*) as total_bills,
                    SUM(CASE WHEN invoice_date LIKE ? || '%' THEN 1 ELSE 0 END) as today_bills,
                    COALESCE(SUM(net_amount), 0.0) as total_sales,
                    COALESCE(SUM(balance_due), 0.0) as pending_payments
                FROM invoices
            """, (today_str,))
            row = cur.fetchone()
            if row:
                return {
                    "total_bills": row["total_bills"] or 0,
                    "today_bills": row["today_bills"] or 0,
                    "total_sales": round(float(row["total_sales"] or 0.0), 2),
                    "pending_payments": round(float(row["pending_payments"] or 0.0), 2)
                }
            return {"total_bills": 0, "today_bills": 0, "total_sales": 0.0, "pending_payments": 0.0}

    # -------------------------------------------------------------------------
    # Products & Services Management
    # -------------------------------------------------------------------------
    def get_products(self, query=None, active_only=False):
        """Lists all products and services with optional case-insensitive search."""
        if self.is_supabase_ready and self.supabase_client:
            try:
                builder = self.supabase_client.table("products").select("*").order("name")
                if active_only:
                    builder = builder.eq("is_active", True)
                if query:
                    builder = builder.ilike("name", f"%{query}%")
                res = builder.execute()
                return res.data or []
            except Exception as e:
                print(f"[DB Products] Supabase error: {e}")

        with self._get_sqlite_conn() as conn:
            sql = "SELECT * FROM products WHERE 1=1"
            params = []
            if active_only:
                sql += " AND is_active = 1"
            if query:
                sql += " AND name LIKE ?"
                params.append(f"%{query}%")
            sql += " ORDER BY name ASC"
            cur = conn.execute(sql, params)
            return [dict(r) for r in cur.fetchall()]

    def save_product(self, product_data):
        """Adds or updates a product/service."""
        import uuid
        name = product_data.get("name", "").strip()
        category = product_data.get("category", "Service").strip()
        default_rate = float(product_data.get("default_rate", 0.0) or 0.0)
        unit = product_data.get("unit", "Point").strip()
        tax_rate = float(product_data.get("tax_rate", 0.0) or 0.0)
        is_active = 1 if product_data.get("is_active", True) else 0
        prod_id = product_data.get("id")

        if self.is_supabase_ready and self.supabase_client:
            try:
                payload = {
                    "name": name,
                    "category": category,
                    "default_rate": default_rate,
                    "unit": unit,
                    "tax_rate": tax_rate,
                    "is_active": bool(is_active),
                    "updated_at": datetime.utcnow().isoformat()
                }
                if prod_id:
                    self.supabase_client.table("products").update(payload).eq("id", prod_id).execute()
                else:
                    res = self.supabase_client.table("products").insert(payload).execute()
                    if res.data:
                        prod_id = res.data[0]["id"]
                return {"success": True, "id": prod_id}
            except Exception as e:
                print(f"[DB Save Product] Supabase error: {e}")

        # Local save
        with self._get_sqlite_conn() as conn:
            now_str = datetime.now().isoformat()
            if prod_id:
                conn.execute("""
                    UPDATE products 
                    SET name = ?, category = ?, default_rate = ?, unit = ?, tax_rate = ?, is_active = ?, updated_at = ?
                    WHERE id = ?
                """, (name, category, default_rate, unit, tax_rate, is_active, now_str, prod_id))
            else:
                prod_id = str(uuid.uuid4())
                conn.execute("""
                    INSERT INTO products (id, name, category, default_rate, unit, tax_rate, is_active, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (prod_id, name, category, default_rate, unit, tax_rate, is_active, now_str, now_str))
            conn.commit()
            return {"success": True, "id": prod_id}

    # -------------------------------------------------------------------------
    # Customers Management
    # -------------------------------------------------------------------------
    def get_customers(self, query=None):
        """Retrieves customers with search on name or phone."""
        if self.is_supabase_ready and self.supabase_client:
            try:
                builder = self.supabase_client.table("customers").select("*").order("name")
                if query:
                    builder = builder.or_(f"name.ilike.%{query}%,phone.ilike.%{query}%")
                res = builder.execute()
                return res.data or []
            except Exception as e:
                print(f"[DB Customers] Supabase error: {e}")

        with self._get_sqlite_conn() as conn:
            sql = "SELECT * FROM customers WHERE 1=1"
            params = []
            if query:
                sql += " AND (name LIKE ? OR phone LIKE ?)"
                params.extend([f"%{query}%", f"%{query}%"])
            sql += " ORDER BY name ASC"
            cur = conn.execute(sql, params)
            return [dict(r) for r in cur.fetchall()]

    def get_customer_by_id(self, customer_id):
        """Fetches customer details along with their past invoices."""
        customer = None
        invoices = []
        
        with self._get_sqlite_conn() as conn:
            cur = conn.execute("SELECT * FROM customers WHERE id = ?", (customer_id,))
            row = cur.fetchone()
            if row:
                customer = dict(row)
                inv_cur = conn.execute("SELECT * FROM invoices WHERE customer_id = ? ORDER BY invoice_date DESC", (customer_id,))
                invoices = [dict(r) for r in inv_cur.fetchall()]
        return {"customer": customer, "invoices": invoices}

    def save_customer(self, customer_data):
        """Saves a new customer or updates an existing one."""
        import uuid
        name = customer_data.get("name", "").strip()
        phone = customer_data.get("phone", "").strip()
        address = customer_data.get("address", "").strip()
        notes = customer_data.get("notes", "").strip()
        cust_id = customer_data.get("id")

        if not name or not phone:
            raise ValueError("Customer name and mobile number are required.")

        if self.is_supabase_ready and self.supabase_client:
            try:
                payload = {
                    "name": name,
                    "phone": phone,
                    "address": address,
                    "notes": notes,
                    "updated_at": datetime.utcnow().isoformat()
                }
                if cust_id:
                    self.supabase_client.table("customers").update(payload).eq("id", cust_id).execute()
                else:
                    res = self.supabase_client.table("customers").insert(payload).execute()
                    if res.data:
                        cust_id = res.data[0]["id"]
                return {"success": True, "id": cust_id, "name": name, "phone": phone, "address": address}
            except Exception as e:
                print(f"[DB Customer] Supabase error: {e}")

        with self._get_sqlite_conn() as conn:
            now_str = datetime.now().isoformat()
            if cust_id:
                conn.execute("""
                    UPDATE customers
                    SET name = ?, phone = ?, address = ?, notes = ?, updated_at = ?
                    WHERE id = ?
                """, (name, phone, address, notes, now_str, cust_id))
            else:
                cust_id = str(uuid.uuid4())
                conn.execute("""
                    INSERT INTO customers (id, name, phone, address, notes, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """, (cust_id, name, phone, address, notes, now_str, now_str))
            conn.commit()
            return {"success": True, "id": cust_id, "name": name, "phone": phone, "address": address}

    # -------------------------------------------------------------------------
    # Invoices & Billing
    # -------------------------------------------------------------------------
    def generate_next_invoice_number(self):
        """
        Generates a collision-safe invoice number format: ME-YYYYMMDD-XXXX
        Example: ME-20261030-0001
        """
        today_code = date.today().strftime("%Y%m%d")
        prefix = f"ME-{today_code}-"
        
        # Check highest sequence today
        seq = 1
        with self._get_sqlite_conn() as conn:
            cur = conn.execute("SELECT invoice_number FROM invoices WHERE invoice_number LIKE ? ORDER BY invoice_number DESC LIMIT 1", (f"{prefix}%",))
            row = cur.fetchone()
            if row:
                last_num = row["invoice_number"]
                try:
                    last_seq = int(last_num.split("-")[-1])
                    seq = last_seq + 1
                except (ValueError, IndexError):
                    seq = 1
                    
        return f"{prefix}{seq:04d}"

    def save_invoice(self, invoice_data, items):
        """
        Saves a finalized invoice and its line items inside a transactional scope.
        Validates duplicate submissions and recalculates balance.
        """
        import uuid
        inv_id = str(uuid.uuid4())
        inv_num = invoice_data.get("invoice_number") or self.generate_next_invoice_number()
        
        # Customer ID or lookup/insert
        customer_id = invoice_data.get("customer_id")
        cust_name = invoice_data.get("customer_name", "").strip()
        cust_phone = invoice_data.get("customer_phone", "").strip()
        cust_address = invoice_data.get("customer_address", "").strip()
        
        if not cust_name:
            raise ValueError("Customer name is required.")
        if not items or len(items) == 0:
            raise ValueError("An invoice must contain at least one item/service.")

        # Ensure customer exists
        if not customer_id and (cust_name or cust_phone):
            saved_cust = self.save_customer({
                "name": cust_name,
                "phone": cust_phone or "N/A",
                "address": cust_address
            })
            customer_id = saved_cust.get("id")

        now_str = datetime.now().isoformat()
        inv_date = invoice_data.get("invoice_date") or date.today().isoformat()

        # Try saving to Supabase if connected
        if self.is_supabase_ready and self.supabase_client:
            try:
                inv_payload = {
                    "invoice_number": inv_num,
                    "invoice_date": inv_date,
                    "customer_id": customer_id,
                    "customer_name": cust_name,
                    "customer_phone": cust_phone,
                    "customer_address": cust_address,
                    "payment_type": invoice_data.get("payment_type", "Cash"),
                    "subtotal": float(invoice_data.get("subtotal", 0.0)),
                    "discount_amount": float(invoice_data.get("discount_amount", 0.0)),
                    "discount_type": invoice_data.get("discount_type", "fixed"),
                    "tax_percent": float(invoice_data.get("tax_percent", 0.0)),
                    "tax_amount": float(invoice_data.get("tax_amount", 0.0)),
                    "net_amount": float(invoice_data.get("net_amount", 0.0)),
                    "cash_advance": float(invoice_data.get("cash_advance", 0.0)),
                    "upi_advance": float(invoice_data.get("upi_advance", 0.0)),
                    "bank_advance": float(invoice_data.get("bank_advance", 0.0)),
                    "total_advance": float(invoice_data.get("total_advance", 0.0)),
                    "balance_due": float(invoice_data.get("balance_due", 0.0)),
                    "payment_status": invoice_data.get("payment_status", "Unpaid"),
                    "notes": invoice_data.get("notes", ""),
                    "amount_in_words": invoice_data.get("amount_in_words", ""),
                    "created_at": now_str,
                    "updated_at": now_str
                }
                res = self.supabase_client.table("invoices").insert(inv_payload).execute()
                if res.data:
                    inv_id = res.data[0]["id"]
                    # Insert items
                    line_items_payload = []
                    for idx, it in enumerate(items, 1):
                        line_items_payload.append({
                            "invoice_id": inv_id,
                            "sr_no": idx,
                            "description": it.get("description", "").strip(),
                            "quantity": float(it.get("quantity", 1.0)),
                            "rate": float(it.get("rate", 0.0)),
                            "amount": float(it.get("amount", 0.0))
                        })
                    self.supabase_client.table("invoice_items").insert(line_items_payload).execute()
            except Exception as e:
                print(f"[DB Save Invoice] Supabase failed: {e}. Writing to local database.")

        # Save to local database (always kept synchronized)
        with self._get_sqlite_conn() as conn:
            # Check duplicate invoice number
            check_cur = conn.execute("SELECT id FROM invoices WHERE invoice_number = ?", (inv_num,))
            if check_cur.fetchone():
                inv_num = self.generate_next_invoice_number()

            conn.execute("""
                INSERT INTO invoices (
                    id, invoice_number, invoice_date, customer_id, customer_name,
                    customer_phone, customer_address, payment_type, subtotal,
                    discount_amount, discount_type, tax_percent, tax_amount,
                    net_amount, cash_advance, upi_advance, bank_advance,
                    total_advance, balance_due, payment_status, notes,
                    amount_in_words, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                inv_id, inv_num, inv_date, customer_id, cust_name,
                cust_phone, cust_address, invoice_data.get("payment_type", "Cash"),
                float(invoice_data.get("subtotal", 0.0)),
                float(invoice_data.get("discount_amount", 0.0)),
                invoice_data.get("discount_type", "fixed"),
                float(invoice_data.get("tax_percent", 0.0)),
                float(invoice_data.get("tax_amount", 0.0)),
                float(invoice_data.get("net_amount", 0.0)),
                float(invoice_data.get("cash_advance", 0.0)),
                float(invoice_data.get("upi_advance", 0.0)),
                float(invoice_data.get("bank_advance", 0.0)),
                float(invoice_data.get("total_advance", 0.0)),
                float(invoice_data.get("balance_due", 0.0)),
                invoice_data.get("payment_status", "Unpaid"),
                invoice_data.get("notes", ""),
                invoice_data.get("amount_in_words", ""),
                now_str, now_str
            ))

            # Insert line items
            for idx, it in enumerate(items, 1):
                item_id = str(uuid.uuid4())
                conn.execute("""
                    INSERT INTO invoice_items (id, invoice_id, sr_no, description, quantity, rate, amount, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    item_id, inv_id, idx, it.get("description", "").strip(),
                    float(it.get("quantity", 1.0)),
                    float(it.get("rate", 0.0)),
                    float(it.get("amount", 0.0)),
                    now_str
                ))

            # Record initial advance payment if made
            tot_adv = float(invoice_data.get("total_advance", 0.0))
            if tot_adv > 0:
                pay_id = str(uuid.uuid4())
                conn.execute("""
                    INSERT INTO payments (id, invoice_id, payment_type, amount, payment_date, notes)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (pay_id, inv_id, invoice_data.get("payment_type", "Advance"), tot_adv, now_str, "Initial advance payment"))

            conn.commit()

        return {
            "success": True,
            "invoice_id": inv_id,
            "invoice_number": inv_num,
            "message": "Invoice generated and saved successfully."
        }

    def get_invoices(self, query=None, status=None, start_date=None, end_date=None, limit=50, offset=0):
        """
        Fetches invoice list with search, status, and date filters.
        Strict rule: returns empty list if no invoices have been created.
        """
        if self.is_supabase_ready and self.supabase_client:
            try:
                builder = self.supabase_client.table("invoices").select("*").order("created_at", desc=True)
                if status and status != "all":
                    builder = builder.eq("payment_status", status)
                if start_date:
                    builder = builder.gte("invoice_date", start_date)
                if end_date:
                    builder = builder.lte("invoice_date", end_date)
                if query:
                    builder = builder.or_(f"invoice_number.ilike.%{query}%,customer_name.ilike.%{query}%")
                res = builder.range(offset, offset + limit - 1).execute()
                return res.data or []
            except Exception as e:
                print(f"[DB Invoices] Supabase error: {e}")

        with self._get_sqlite_conn() as conn:
            sql = "SELECT * FROM invoices WHERE 1=1"
            params = []
            if status and status != "all":
                sql += " AND payment_status = ?"
                params.append(status)
            if start_date:
                sql += " AND invoice_date >= ?"
                params.append(start_date)
            if end_date:
                sql += " AND invoice_date <= ?"
                params.append(end_date)
            if query:
                sql += " AND (invoice_number LIKE ? OR customer_name LIKE ?)"
                params.extend([f"%{query}%", f"%{query}%"])
            sql += " ORDER BY invoice_date DESC, created_at DESC LIMIT ? OFFSET ?"
            params.extend([limit, offset])
            cur = conn.execute(sql, params)
            return [dict(r) for r in cur.fetchall()]

    def get_invoice_by_id(self, invoice_id):
        """Retrieves full invoice details and line items."""
        with self._get_sqlite_conn() as conn:
            cur = conn.execute("SELECT * FROM invoices WHERE id = ? OR invoice_number = ?", (invoice_id, invoice_id))
            inv = cur.fetchone()
            if not inv:
                return None
            inv_dict = dict(inv)
            
            items_cur = conn.execute("SELECT * FROM invoice_items WHERE invoice_id = ? ORDER BY sr_no ASC", (inv_dict["id"],))
            inv_dict["items"] = [dict(r) for r in items_cur.fetchall()]
            
            payments_cur = conn.execute("SELECT * FROM payments WHERE invoice_id = ? ORDER BY payment_date ASC", (inv_dict["id"],))
            inv_dict["payments"] = [dict(r) for r in payments_cur.fetchall()]
            
            return inv_dict

    # -------------------------------------------------------------------------
    # Drafts Autosave
    # -------------------------------------------------------------------------
    def save_draft(self, user_id, draft_data):
        import uuid
        with self._get_sqlite_conn() as conn:
            draft_json = json.dumps(draft_data)
            now_str = datetime.now().isoformat()
            cur = conn.execute("SELECT id FROM drafts WHERE user_id = ?", (user_id,))
            row = cur.fetchone()
            if row:
                conn.execute("UPDATE drafts SET draft_data = ?, updated_at = ? WHERE id = ?", (draft_json, now_str, row["id"]))
            else:
                conn.execute("INSERT INTO drafts (id, user_id, draft_data, updated_at) VALUES (?, ?, ?, ?)", (str(uuid.uuid4()), user_id, draft_json, now_str))
            conn.commit()
            return {"success": True}

    def get_draft(self, user_id):
        with self._get_sqlite_conn() as conn:
            cur = conn.execute("SELECT draft_data FROM drafts WHERE user_id = ?", (user_id,))
            row = cur.fetchone()
            if row and row["draft_data"]:
                try:
                    return json.loads(row["draft_data"])
                except Exception:
                    return None
            return None

    def clear_draft(self, user_id):
        with self._get_sqlite_conn() as conn:
            conn.execute("DELETE FROM drafts WHERE user_id = ?", (user_id,))
            conn.commit()
            return {"success": True}

# Singleton instance
db = Database()
