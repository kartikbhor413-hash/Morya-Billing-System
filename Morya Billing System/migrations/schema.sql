-- ====================================================================
-- MORAYA ELECTRIC BILLING SYSTEM - SUPABASE POSTGRESQL SCHEMA
-- Idempotent Migration Script
-- ====================================================================

-- 1. Profiles / Authorized Users
CREATE TABLE IF NOT EXISTS profiles (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email VARCHAR(255) NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    name VARCHAR(255) DEFAULT 'Admin',
    role VARCHAR(50) DEFAULT 'admin',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- 2. Customers Table
CREATE TABLE IF NOT EXISTS customers (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(255) NOT NULL,
    phone VARCHAR(50) NOT NULL,
    address TEXT,
    notes TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_customers_phone ON customers(phone);
CREATE INDEX IF NOT EXISTS idx_customers_name ON customers(name);

-- 3. Products & Services Table
CREATE TABLE IF NOT EXISTS products (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name VARCHAR(255) NOT NULL UNIQUE,
    category VARCHAR(100) DEFAULT 'Service',
    default_rate NUMERIC(12, 2) DEFAULT 0.00,
    unit VARCHAR(50) DEFAULT 'Point',
    tax_rate NUMERIC(5, 2) DEFAULT 0.00,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_products_name ON products(name);
CREATE INDEX IF NOT EXISTS idx_products_active ON products(is_active);

-- 4. Invoices Table
CREATE TABLE IF NOT EXISTS invoices (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    invoice_number VARCHAR(100) NOT NULL UNIQUE,
    invoice_date DATE NOT NULL,
    customer_id UUID REFERENCES customers(id) ON DELETE SET NULL,
    customer_name VARCHAR(255) NOT NULL,
    customer_phone VARCHAR(50),
    customer_address TEXT,
    payment_type VARCHAR(50) NOT NULL DEFAULT 'Cash', -- Cash, UPI, Bank Transfer, Credit
    subtotal NUMERIC(12, 2) NOT NULL DEFAULT 0.00,
    discount_amount NUMERIC(12, 2) NOT NULL DEFAULT 0.00,
    discount_type VARCHAR(20) DEFAULT 'fixed',
    tax_percent NUMERIC(5, 2) DEFAULT 0.00,
    tax_amount NUMERIC(12, 2) NOT NULL DEFAULT 0.00,
    net_amount NUMERIC(12, 2) NOT NULL DEFAULT 0.00,
    cash_advance NUMERIC(12, 2) NOT NULL DEFAULT 0.00,
    upi_advance NUMERIC(12, 2) NOT NULL DEFAULT 0.00,
    bank_advance NUMERIC(12, 2) NOT NULL DEFAULT 0.00,
    total_advance NUMERIC(12, 2) NOT NULL DEFAULT 0.00,
    balance_due NUMERIC(12, 2) NOT NULL DEFAULT 0.00,
    payment_status VARCHAR(50) NOT NULL DEFAULT 'Unpaid', -- Unpaid, Partially Paid, Paid
    notes TEXT,
    amount_in_words TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_invoices_number ON invoices(invoice_number);
CREATE INDEX IF NOT EXISTS idx_invoices_date ON invoices(invoice_date);
CREATE INDEX IF NOT EXISTS idx_invoices_status ON invoices(payment_status);
CREATE INDEX IF NOT EXISTS idx_invoices_customer ON invoices(customer_id);

-- 5. Invoice Line Items Table
CREATE TABLE IF NOT EXISTS invoice_items (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    invoice_id UUID NOT NULL REFERENCES invoices(id) ON DELETE CASCADE,
    sr_no INT NOT NULL,
    description VARCHAR(255) NOT NULL,
    quantity NUMERIC(10, 2) NOT NULL DEFAULT 1.00,
    rate NUMERIC(12, 2) NOT NULL DEFAULT 0.00,
    amount NUMERIC(12, 2) NOT NULL DEFAULT 0.00,
    created_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_invoice_items_invoice ON invoice_items(invoice_id);

-- 6. Payment History Table
CREATE TABLE IF NOT EXISTS payments (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    invoice_id UUID NOT NULL REFERENCES invoices(id) ON DELETE CASCADE,
    payment_type VARCHAR(50) NOT NULL,
    amount NUMERIC(12, 2) NOT NULL,
    payment_date TIMESTAMPTZ DEFAULT NOW(),
    notes TEXT
);

-- 7. Drafts Table (autosave, excluded from business metrics)
CREATE TABLE IF NOT EXISTS drafts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id VARCHAR(100) NOT NULL,
    draft_data JSONB NOT NULL,
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- ====================================================================
-- SEED 8 DEFAULT SERVICES (NO INVENTED PRICES - default_rate = 0.00)
-- ====================================================================
INSERT INTO products (name, category, default_rate, unit, is_active)
VALUES 
    ('House Wiring', 'Electrical Service', 0.00, 'Point', TRUE),
    ('House and Building Maintenance', 'Maintenance', 0.00, 'Job', TRUE),
    ('AC Point', 'Installation', 0.00, 'Point', TRUE),
    ('Geyser Point', 'Installation', 0.00, 'Point', TRUE),
    ('Geyser Repairing', 'Repair Service', 0.00, 'Job', TRUE),
    ('Fan Repairing', 'Repair Service', 0.00, 'Unit', TRUE),
    ('Fan Installation', 'Installation', 0.00, 'Unit', TRUE),
    ('Geyser Installation', 'Installation', 0.00, 'Unit', TRUE)
ON CONFLICT (name) DO NOTHING;

-- Enable Row Level Security (RLS)
ALTER TABLE customers ENABLE ROW LEVEL SECURITY;
ALTER TABLE products ENABLE ROW LEVEL SECURITY;
ALTER TABLE invoices ENABLE ROW LEVEL SECURITY;
ALTER TABLE invoice_items ENABLE ROW LEVEL SECURITY;
ALTER TABLE payments ENABLE ROW LEVEL SECURITY;
ALTER TABLE drafts ENABLE ROW LEVEL SECURITY;

-- Allow authenticated and service role full access policies
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE policyname = 'Allow all for authenticated users on customers') THEN
        CREATE POLICY "Allow all for authenticated users on customers" ON customers FOR ALL USING (true);
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE policyname = 'Allow all for authenticated users on products') THEN
        CREATE POLICY "Allow all for authenticated users on products" ON products FOR ALL USING (true);
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE policyname = 'Allow all for authenticated users on invoices') THEN
        CREATE POLICY "Allow all for authenticated users on invoices" ON invoices FOR ALL USING (true);
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE policyname = 'Allow all for authenticated users on invoice_items') THEN
        CREATE POLICY "Allow all for authenticated users on invoice_items" ON invoice_items FOR ALL USING (true);
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE policyname = 'Allow all for authenticated users on payments') THEN
        CREATE POLICY "Allow all for authenticated users on payments" ON payments FOR ALL USING (true);
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_policies WHERE policyname = 'Allow all for authenticated users on drafts') THEN
        CREATE POLICY "Allow all for authenticated users on drafts" ON drafts FOR ALL USING (true);
    END IF;
END $$;
