import os
from datetime import datetime, date
from flask import (
    Flask, render_template, request, redirect, url_for, session, 
    jsonify, send_file, flash, make_response
)
from config import Config
from db import db
from auth import login_required, is_rate_limited, record_failed_attempt, reset_attempts
from services.billing import calculate_invoice_totals, number_to_indian_words
from services.pdf_generator import generate_invoice_pdf
import io

app = Flask(__name__)
app.config.from_object(Config)

# Jinja template filters
@app.template_filter('currency')
def currency_filter(val):
    try:
        f = float(val or 0.0)
        return f"₹{f:,.2f}"
    except (ValueError, TypeError):
        return "₹0.00"

@app.template_filter('format_date')
def date_filter(val):
    if not val:
        return "—"
    try:
        s = str(val)[:10]
        return datetime.strptime(s, "%Y-%m-%d").strftime("%d %b %Y")
    except Exception:
        return str(val)[:10]

# Context processor for templates
@app.context_processor
def inject_global_data():
    hour = datetime.now().hour
    if hour < 12:
        greeting = "Good Morning"
    elif hour < 17:
        greeting = "Good Afternoon"
    else:
        greeting = "Good Evening"
        
    return {
        "business_name": Config.BUSINESS_NAME,
        "business_tagline": Config.BUSINESS_TAGLINE,
        "business_phone": Config.BUSINESS_PHONE,
        "greeting": greeting,
        "current_date_formatted": datetime.now().strftime("%a, %d %b %Y"),
        "logged_in_user": session.get("user_name", "Admin") if session.get("user_id") else None,
        "is_supabase_connected": db.is_supabase_ready
    }

# -----------------------------------------------------------------------------
# Authentication Routes
# -----------------------------------------------------------------------------
@app.route("/login", methods=["GET", "POST"])
def login():
    if session.get("user_id"):
        return redirect(url_for("dashboard"))

    error = None
    if request.method == "POST":
        ip = request.remote_addr or "127.0.0.1"
        limited, wait_seconds = is_rate_limited(ip)
        if limited:
            error = f"Too many failed login attempts. Please wait {wait_seconds} seconds before trying again."
            return render_template("login.html", error=error)

        email = request.form.get("email", "").strip()
        password = request.form.get("password", "")
        remember = bool(request.form.get("remember"))

        user = db.verify_user(email, password)
        if user:
            reset_attempts(ip)
            session.clear()
            session["user_id"] = user["id"]
            session["user_email"] = user["email"]
            session["user_name"] = user.get("name", "Admin")
            session.permanent = remember

            next_url = request.args.get("next")
            return redirect(next_url or url_for("dashboard"))
        else:
            record_failed_attempt(ip)
            error = "Invalid email or password. Please verify your credentials."

    return render_template("login.html", error=error)

@app.route("/logout")
def logout():
    session.clear()
    flash("You have been securely logged out.", "info")
    return redirect(url_for("login"))

# -----------------------------------------------------------------------------
# Dashboard Route (STRICT RULE: NO FAKE DATA)
# -----------------------------------------------------------------------------
@app.route("/")
@app.route("/dashboard")
@login_required
def dashboard():
    stats = db.get_dashboard_stats()
    # Recent 5 invoices
    recent_invoices = db.get_invoices(limit=5)
    return render_template("dashboard.html", stats=stats, recent_invoices=recent_invoices)

# -----------------------------------------------------------------------------
# Create Bill Page (Opening or refreshing NEVER creates an invoice)
# -----------------------------------------------------------------------------
@app.route("/create-bill")
@login_required
def create_bill():
    provisional_invoice_number = db.generate_next_invoice_number()
    today_str = date.today().isoformat()
    # Load all active products and services
    products = db.get_products(active_only=True)
    user_draft = db.get_draft(session["user_id"])
    return render_template(
        "create_bill.html", 
        provisional_number=provisional_invoice_number,
        today_date=today_str,
        products=products,
        draft=user_draft
    )

# -----------------------------------------------------------------------------
# API: Save and Finalize Invoice (ONLY THIS CREATES A BILL)
# -----------------------------------------------------------------------------
@app.route("/api/invoices/generate", methods=["POST"])
@login_required
def api_generate_invoice():
    data = request.get_json() or {}
    
    items = data.get("items", [])
    if not items or len(items) == 0:
        return jsonify({"success": False, "error": "Invoice must contain at least one line item."}), 400

    cust_name = data.get("customer_name", "").strip()
    if not cust_name:
        return jsonify({"success": False, "error": "Customer name is required."}), 400

    # Server-side Decimal-Safe Recalculation
    recalc = calculate_invoice_totals(
        items=items,
        discount_val=data.get("discount_amount", 0.0),
        discount_type=data.get("discount_type", "fixed"),
        tax_percent=data.get("tax_percent", 0.0),
        cash_adv=data.get("cash_advance", 0.0),
        upi_adv=data.get("upi_advance", 0.0),
        bank_adv=data.get("bank_advance", 0.0)
    )

    invoice_data = {
        "invoice_number": data.get("invoice_number"),
        "invoice_date": data.get("invoice_date") or date.today().isoformat(),
        "customer_id": data.get("customer_id"),
        "customer_name": cust_name,
        "customer_phone": data.get("customer_phone", "").strip(),
        "customer_address": data.get("customer_address", "").strip(),
        "payment_type": data.get("payment_type", "Cash"),
        "subtotal": recalc["subtotal"],
        "discount_amount": recalc["discount_amount"],
        "discount_type": recalc["discount_type"],
        "tax_percent": recalc["tax_percent"],
        "tax_amount": recalc["tax_amount"],
        "net_amount": recalc["net_amount"],
        "cash_advance": recalc["cash_advance"],
        "upi_advance": recalc["upi_advance"],
        "bank_advance": recalc["bank_advance"],
        "total_advance": recalc["total_advance"],
        "balance_due": recalc["balance_due"],
        "payment_status": recalc["payment_status"],
        "notes": data.get("notes", "").strip(),
        "amount_in_words": recalc["amount_in_words"]
    }

    try:
        result = db.save_invoice(invoice_data, recalc["items"])
        # Clear draft after successful creation
        db.clear_draft(session["user_id"])
        return jsonify(result)
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

# -----------------------------------------------------------------------------
# Saved Invoice Preview Page
# -----------------------------------------------------------------------------
@app.route("/invoices/<invoice_id>")
@login_required
def view_invoice(invoice_id):
    inv = db.get_invoice_by_id(invoice_id)
    if not inv:
        flash("Invoice not found.", "danger")
        return redirect(url_for("all_bills"))
    return render_template("invoice_view.html", invoice=inv)

# -----------------------------------------------------------------------------
# PDF Download / View Route
# -----------------------------------------------------------------------------
@app.route("/invoices/<invoice_id>/pdf")
@login_required
def download_invoice_pdf(invoice_id):
    inv = db.get_invoice_by_id(invoice_id)
    if not inv:
        return "Invoice not found", 404
        
    pdf_bytes = generate_invoice_pdf(inv)
    filename = f"Invoice_{inv['invoice_number']}.pdf"
    
    # If ?download=true is passed, force attachment, otherwise inline
    as_attachment = request.args.get("download", "false").lower() == "true"
    
    return send_file(
        io.BytesIO(pdf_bytes),
        mimetype="application/pdf",
        as_attachment=as_attachment,
        download_name=filename
    )

# -----------------------------------------------------------------------------
# All Bills History Route
# -----------------------------------------------------------------------------
@app.route("/all-bills")
@login_required
def all_bills():
    query = request.args.get("search", "").strip()
    status = request.args.get("status", "all").strip()
    start_date = request.args.get("start_date", "").strip()
    end_date = request.args.get("end_date", "").strip()
    
    invoices = db.get_invoices(
        query=query if query else None,
        status=status if status != "all" else None,
        start_date=start_date if start_date else None,
        end_date=end_date if end_date else None
    )
    return render_template(
        "all_bills.html", 
        invoices=invoices, 
        search=query, 
        status=status,
        start_date=start_date,
        end_date=end_date
    )

# -----------------------------------------------------------------------------
# Products & Services Management Route
# -----------------------------------------------------------------------------
@app.route("/products")
@login_required
def products():
    search = request.args.get("search", "").strip()
    items = db.get_products(query=search if search else None)
    return render_template("products.html", products=items, search=search)

@app.route("/api/products", methods=["GET", "POST"])
@login_required
def api_products():
    if request.method == "GET":
        q = request.args.get("q", "").strip()
        active = request.args.get("active", "false").lower() == "true"
        items = db.get_products(query=q if q else None, active_only=active)
        return jsonify(items)

    data = request.get_json() or {}
    name = data.get("name", "").strip()
    if not name:
        return jsonify({"success": False, "error": "Service name is required."}), 400
    try:
        res = db.save_product(data)
        return jsonify(res)
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

# -----------------------------------------------------------------------------
# Customers Management Route
# -----------------------------------------------------------------------------
@app.route("/customers")
@login_required
def customers():
    search = request.args.get("search", "").strip()
    custs = db.get_customers(query=search if search else None)
    return render_template("customers.html", customers=custs, search=search)

@app.route("/api/customers", methods=["GET", "POST"])
@login_required
def api_customers():
    if request.method == "GET":
        q = request.args.get("q", "").strip()
        custs = db.get_customers(query=q if q else None)
        return jsonify(custs)

    data = request.get_json() or {}
    try:
        res = db.save_customer(data)
        return jsonify(res)
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 400

@app.route("/customers/<customer_id>")
@login_required
def customer_details(customer_id):
    data = db.get_customer_by_id(customer_id)
    if not data or not data["customer"]:
        flash("Customer not found.", "warning")
        return redirect(url_for("customers"))
    return render_template("customer_details.html", customer=data["customer"], invoices=data["invoices"])

# -----------------------------------------------------------------------------
# Draft Autosave API (Excluded from stats)
# -----------------------------------------------------------------------------
@app.route("/api/draft", methods=["GET", "POST", "DELETE"])
@login_required
def api_draft():
    user_id = session["user_id"]
    if request.method == "GET":
        draft = db.get_draft(user_id)
        return jsonify({"draft": draft})
    elif request.method == "POST":
        data = request.get_json() or {}
        res = db.save_draft(user_id, data)
        return jsonify(res)
    elif request.method == "DELETE":
        res = db.clear_draft(user_id)
        return jsonify(res)

# -----------------------------------------------------------------------------
# Live Calculation Utility API
# -----------------------------------------------------------------------------
@app.route("/api/calculate", methods=["POST"])
@login_required
def api_calculate():
    data = request.get_json() or {}
    calc = calculate_invoice_totals(
        items=data.get("items", []),
        discount_val=data.get("discount_amount", 0.0),
        discount_type=data.get("discount_type", "fixed"),
        tax_percent=data.get("tax_percent", 0.0),
        cash_adv=data.get("cash_advance", 0.0),
        upi_adv=data.get("upi_advance", 0.0),
        bank_adv=data.get("bank_advance", 0.0)
    )
    return jsonify(calc)

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
