import os
import io
import json
import pandas as pd
from datetime import datetime
from flask import Flask, render_template, request, jsonify, send_file, Response, session, redirect, url_for, make_response

try:
    from .column_mapper import clean_and_map_dataframe
    from . import ml_engine as ml
    from . import report_generator as rep
    from .auth import auth_bp
except ImportError:
    from column_mapper import clean_and_map_dataframe
    import ml_engine as ml
    import report_generator as rep
    from auth import auth_bp

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.dirname(BASE_DIR)
TEMPLATES_DIR = os.path.join(PROJECT_DIR, "frontend", "templates")
STATIC_DIR = os.path.join(PROJECT_DIR, "frontend", "static")
DATASETS_DIR = os.path.join(PROJECT_DIR, "datasets")
DEFAULT_CSV = os.path.join(DATASETS_DIR, "pharmacy_sales_dummy_1500.csv")

app = Flask(__name__, template_folder=TEMPLATES_DIR, static_folder=STATIC_DIR)
app.secret_key = "pharma_ai_super_secret_session_key_2026"
app.config['MAX_CONTENT_LENGTH'] = 32 * 1024 * 1024

app.register_blueprint(auth_bp)

# User-scoped in-memory storage manager
USER_STORES = {}
DEMO_CONTACT_REQUESTS = []

def get_default_demo_invoices():
    return [
        {
            "invoice_no": "INV-2026-1001",
            "date": "2026-07-28 14:30:00",
            "customer_name": "Vikram Sethi",
            "customer_phone": "9811223344",
            "billed_by": "Dr. Sarah Jenkins",
            "store_name": "HealthCare Central Pharmacy",
            "payment_mode": "UPI",
            "items": [
                {"medicine": "Azithromycin 500", "category": "Antibiotic", "company": "Sun Pharma", "batch": "B2424", "qty": 2, "unit_price": 135.97, "line_total": 271.94, "previous_stock": 346, "remaining_stock": 344},
                {"medicine": "Crocin", "category": "Painkiller", "company": "Glenmark", "batch": "B5422", "qty": 5, "unit_price": 122.50, "line_total": 612.50, "previous_stock": 236, "remaining_stock": 231}
            ],
            "subtotal": 884.44,
            "discount_pct": 5.0,
            "discount_amount": 44.22,
            "tax_amount": 100.83,
            "grand_total": 941.05
        },
        {
            "invoice_no": "INV-2026-1002",
            "date": "2026-07-29 09:15:00",
            "customer_name": "Priya Sharma",
            "customer_phone": "9876543210",
            "billed_by": "Rajesh Kumar",
            "store_name": "HealthCare Central Pharmacy",
            "payment_mode": "Cash",
            "items": [
                {"medicine": "Telmisartan", "category": "Heart", "company": "Sun Pharma", "batch": "B4257", "qty": 3, "unit_price": 60.10, "line_total": 180.30, "previous_stock": 13, "remaining_stock": 10},
                {"medicine": "Vitamin D3", "category": "Vitamin", "company": "Mankind", "batch": "B6881", "qty": 1, "unit_price": 546.75, "line_total": 546.75, "previous_stock": 194, "remaining_stock": 193}
            ],
            "subtotal": 727.05,
            "discount_pct": 0.0,
            "discount_amount": 0.0,
            "tax_amount": 87.25,
            "grand_total": 814.30
        }
    ]

def get_user_store(user_id=None):
    """
    Retrieves or initializes isolated data store for the active user session:
    - New users start with a clean slate (0 records, 0 invoices).
    - Demo users (owner@pharma.com) load default demo data if no custom file exists.
    - Saved user CSVs are automatically reloaded per user account.
    """
    global USER_STORES
    if not user_id:
        user_obj = session.get('user')
        user_id = user_obj.get('id') if user_obj else None
    if not user_id:
        user_id = "default"

    user_str = str(user_id)
    if user_str not in USER_STORES:
        user_store_dir = os.path.join(DATASETS_DIR, "user_data")
        os.makedirs(user_store_dir, exist_ok=True)
        
        user_csv = os.path.join(user_store_dir, f"user_{user_str}_sales.csv")
        user_inv_file = os.path.join(user_store_dir, f"user_{user_str}_invoices.json")
        user_stock_file = os.path.join(user_store_dir, f"user_{user_str}_stock_log.json")

        df = pd.DataFrame()
        mapping_info = {}
        invoices = []
        stock_log = []

        user_email = session.get('user', {}).get('email', '')
        is_demo_account = user_email in ("owner@pharma.com", "manager@pharma.com", "staff@pharma.com")

        if os.path.exists(user_csv):
            try:
                raw_df = pd.read_csv(user_csv)
                df, mapping_info = clean_and_map_dataframe(raw_df)
            except Exception:
                df = pd.DataFrame()
        elif is_demo_account and os.path.exists(DEFAULT_CSV):
            try:
                raw_df = pd.read_csv(DEFAULT_CSV)
                df, mapping_info = clean_and_map_dataframe(raw_df)
            except Exception:
                df = pd.DataFrame()

        if os.path.exists(user_inv_file):
            try:
                with open(user_inv_file, "r") as f:
                    invoices = json.load(f)
            except Exception:
                invoices = []
        elif is_demo_account:
            invoices = get_default_demo_invoices()

        if os.path.exists(user_stock_file):
            try:
                with open(user_stock_file, "r") as f:
                    stock_log = json.load(f)
            except Exception:
                stock_log = []

        inv_store = {inv["invoice_no"]: inv for inv in invoices}
        counter = 1000
        for inv in invoices:
            try:
                num = int(inv["invoice_no"].split("-")[-1])
                if num > counter:
                    counter = num
            except Exception:
                pass

        USER_STORES[user_str] = {
            "df": df,
            "mapping_info": mapping_info,
            "invoices": invoices,
            "invoice_store": inv_store,
            "stock_log": stock_log,
            "invoice_counter": counter
        }

    return USER_STORES[user_str]

def save_user_store(user_id=None):
    """Persists active user data store to disk in datasets/user_data/."""
    store = get_user_store(user_id)
    if not user_id:
        user_obj = session.get('user')
        user_id = user_obj.get('id') if user_obj else "default"
    
    user_str = str(user_id)
    user_store_dir = os.path.join(DATASETS_DIR, "user_data")
    os.makedirs(user_store_dir, exist_ok=True)

    user_csv = os.path.join(user_store_dir, f"user_{user_str}_sales.csv")
    if not store["df"].empty:
        store["df"].to_csv(user_csv, index=False)
    elif os.path.exists(user_csv):
        try:
            os.remove(user_csv)
        except Exception:
            pass

    user_inv_file = os.path.join(user_store_dir, f"user_{user_str}_invoices.json")
    with open(user_inv_file, "w") as f:
        json.dump(store["invoices"], f, indent=2)

    user_stock_file = os.path.join(user_store_dir, f"user_{user_str}_stock_log.json")
    with open(user_stock_file, "w") as f:
        json.dump(store["stock_log"], f, indent=2)


# ==============================================================================
# Page Routes & Navigation
# ==============================================================================

@app.route('/')
def home():
    """Render the official Pharmora SaaS Landing / Home page."""
    return render_template('landing.html')

@app.route('/dashboard')
def dashboard():
    """Render the main Pharmora Analytics, POS, & Management Dashboard (Protected: requires login)."""
    if not session.get('user'):
        target_tab = request.args.get('tab', '')
        auth_mode = request.args.get('auth', 'login')
        if target_tab:
            return redirect(url_for('login_route', tab=target_tab, auth=auth_mode))
        return redirect(url_for('login_route', auth=auth_mode))
    return render_template('index.html')

@app.route('/login')
def login_route():
    """Direct route for Login modal / screen."""
    if session.get('user'):
        target_tab = request.args.get('tab', '')
        if target_tab:
            return redirect(url_for('dashboard', tab=target_tab))
        return redirect(url_for('dashboard'))
    return render_template('index.html')

@app.route('/register')
def register_route():
    """Direct route for Account Registration modal / screen."""
    if session.get('user'):
        return redirect(url_for('dashboard'))
    return render_template('index.html')

@app.route('/pos')
def pos_shortcut():
    """Direct shortcut route to POS Billing & Checkout tab (Protected)."""
    if not session.get('user'):
        return redirect(url_for('login_route', tab='tab-pos'))
    return redirect(url_for('dashboard', tab='tab-pos'))

@app.route('/stock')
def stock_shortcut():
    """Direct shortcut route to Add/Replenish Stock tab (Protected)."""
    if not session.get('user'):
        return redirect(url_for('login_route', tab='tab-add-stock'))
    return redirect(url_for('dashboard', tab='tab-add-stock'))

@app.route('/ai-forecast')
@app.route('/ai_forecast')
def ai_forecast_shortcut():
    """Direct shortcut route to AI Forecast tab (Protected)."""
    if not session.get('user'):
        return redirect(url_for('login_route', tab='tab-ai-forecast'))
    return redirect(url_for('dashboard', tab='tab-ai-forecast'))

@app.route('/seasonal-advisor')
@app.route('/seasonal_advisor')
def seasonal_advisor_shortcut():
    """Direct shortcut route to Seasonal Advisor tab (Protected)."""
    if not session.get('user'):
        return redirect(url_for('login_route', tab='tab-seasonal'))
    return redirect(url_for('dashboard', tab='tab-seasonal'))

@app.route('/pharmacy-assistant')
@app.route('/pharmacy_assistant')
def pharmacy_assistant_shortcut():
    """Direct shortcut route to New Pharmacy Assistant tab (Protected)."""
    if not session.get('user'):
        return redirect(url_for('login_route', tab='tab-assistant'))
    return redirect(url_for('dashboard', tab='tab-assistant'))

@app.route('/pricing')
def pricing_route():
    """Pricing anchor navigation."""
    return redirect('/#pricing')

@app.route('/about')
def about_route():
    """About Us anchor navigation."""
    return redirect('/#about')

@app.route('/contact')
def contact_route():
    """Contact anchor navigation."""
    return redirect('/#contact')

@app.route('/api/contact', methods=['POST'])
def handle_contact_inquiry():
    """Handle Demo Booking & Contact Inquiries from Landing Page."""
    global DEMO_CONTACT_REQUESTS
    data = request.json or {}
    name = data.get("name", "").strip()
    email = data.get("email", "").strip()
    phone = data.get("phone", "").strip()
    store_name = data.get("store_name", "").strip()
    message = data.get("message", "").strip()

    if not name or (not email and not phone):
        return jsonify({"success": False, "error": "Please provide your name and at least an email or mobile phone number."}), 400

    entry = {
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "name": name,
        "email": email,
        "phone": phone,
        "store_name": store_name,
        "message": message
    }
    DEMO_CONTACT_REQUESTS.append(entry)

    return jsonify({
        "success": True,
        "message": f"Thank you, {name}! Your demo request has been received. A Pharmora specialist will reach out to you shortly."
    })


# ==============================================================================
# Analytics, Dashboard & Tableau Controls
# ==============================================================================

@app.route('/api/dashboard/full', methods=['GET'])
def get_full_dashboard():
    """Returns complete JSON analytics payload for user dataset with dynamic Tableau parameters."""
    store = get_user_store()
    df = store["df"]
    mapping_info = store["mapping_info"]

    mode = request.args.get("mode", "top")
    top_n = int(request.args.get("top_n", 10))
    measure = request.args.get("measure", "sales")
    stock_measure = request.args.get("stock_measure", "units")

    if df.empty:
        return jsonify({
            "is_empty": True,
            "kpis": ml.compute_kpis(df),
            "sales_trends": ml.compute_sales_trends(df),
            "product_analytics": ml.compute_product_analytics(df),
            "stock_expiry": ml.compute_stock_and_expiry_dashboard(df),
            "abc_xyz": {"matrix": [], "summary": {"abc_counts": {}, "xyz_counts": {}}},
            "forecasting": {"predictions": {}, "demand_forecast": [], "recommendations": []},
            "seasonal": {
                "rainy": {"season": "Rainy Season", "action": "No Data", "medicines": [], "reason": "Upload sales data to activate seasonal forecast."},
                "summer": {"season": "Summer Season", "action": "No Data", "medicines": [], "reason": "Upload sales data to activate seasonal forecast."},
                "winter": {"season": "Winter Season", "action": "No Data", "medicines": [], "reason": "Upload sales data to activate seasonal forecast."}
            },
            "anomalies": [],
            "clustering": {"clusters": []},
            "stock_distribution": {"labels": [], "percentages": [], "values": [], "measure": stock_measure},
            "parameterized_medicines": [],
            "filter_options": {"categories": [], "companies": [], "years": []},
            "mapping_info": mapping_info,
            "record_count": 0,
            "total_record_count": 0
        })

    filters = {
        "category": request.args.get("category", "ALL"),
        "company": request.args.get("company", "ALL"),
        "year": request.args.get("year", "ALL")
    }

    filtered_df = ml.apply_filters(df, filters)

    kpis = ml.compute_kpis(filtered_df)
    sales_trends = ml.compute_sales_trends(filtered_df)
    product_analytics = ml.compute_product_analytics(filtered_df)
    stock_expiry = ml.compute_stock_and_expiry_dashboard(filtered_df)
    abc_xyz = ml.compute_abc_xyz_analysis(filtered_df)
    forecasting = ml.run_ml_forecasting(filtered_df)
    seasonal = ml.get_seasonal_recommendations(filtered_df)
    anomalies = ml.detect_sales_anomalies(filtered_df)
    clustering = ml.run_kmeans_clustering(filtered_df)

    stock_distribution = ml.compute_stock_distribution(filtered_df, stock_measure)
    parameterized_meds = ml.compute_parameterized_medicines(filtered_df, mode, top_n, measure)
    filter_options = ml.get_filter_options(df)

    return jsonify({
        "is_empty": False,
        "kpis": kpis,
        "sales_trends": sales_trends,
        "product_analytics": product_analytics,
        "stock_expiry": stock_expiry,
        "abc_xyz": abc_xyz,
        "forecasting": forecasting,
        "seasonal": seasonal,
        "anomalies": anomalies,
        "clustering": clustering,
        "stock_distribution": stock_distribution,
        "parameterized_medicines": parameterized_meds,
        "filter_options": filter_options,
        "mapping_info": mapping_info,
        "record_count": len(filtered_df),
        "total_record_count": len(df)
    })

@app.route('/api/dataset/reset', methods=['POST'])
def reset_user_dataset():
    """Reset current user's workspace to a clean slate (0 records, 0 invoices)."""
    user_obj = session.get('user')
    user_id = user_obj.get('id') if user_obj else "default"
    user_str = str(user_id)

    USER_STORES[user_str] = {
        "df": pd.DataFrame(),
        "mapping_info": {},
        "invoices": [],
        "invoice_store": {},
        "stock_log": [],
        "invoice_counter": 1000
    }
    save_user_store(user_id)

    return jsonify({
        "success": True,
        "message": "Your workspace has been reset to a clean slate (0 records, 0 invoices)."
    })

@app.route('/api/dataset/load-sample', methods=['POST'])
def load_sample_dataset():
    """Load sample dummy dataset for quick exploration."""
    user_obj = session.get('user')
    user_id = user_obj.get('id') if user_obj else "default"
    user_str = str(user_id)

    if os.path.exists(DEFAULT_CSV):
        raw_df = pd.read_csv(DEFAULT_CSV)
        df, mapping_info = clean_and_map_dataframe(raw_df)
    else:
        df, mapping_info = pd.DataFrame(), {}

    invoices = get_default_demo_invoices()
    USER_STORES[user_str] = {
        "df": df,
        "mapping_info": mapping_info,
        "invoices": invoices,
        "invoice_store": {inv["invoice_no"]: inv for inv in invoices},
        "stock_log": [],
        "invoice_counter": 1000 + len(invoices)
    }
    save_user_store(user_id)

    return jsonify({
        "success": True,
        "message": f"Sample dataset with {len(df)} records loaded successfully!",
        "record_count": len(df)
    })


# ==============================================================================
# Stock Management & Replenishment
# ==============================================================================

@app.route('/api/stock/add', methods=['POST'])
def add_medicine_stock():
    """
    Add / Replenish Medicine Stock Endpoint:
    - Supports adding stock to existing inventory or creating a new medicine.
    - Works even if the initial dataset is empty.
    """
    store = get_user_store()
    df = store["df"]

    data = request.json or {}
    mode = data.get("mode", "existing") # 'existing' or 'new'
    med_name = data.get("medicine", "").strip()
    added_qty = int(data.get("added_qty") if data.get("added_qty") is not None else data.get("qty", 0))

    if not med_name:
        return jsonify({"error": "Medicine name is required."}), 400
    if added_qty <= 0:
        return jsonify({"error": "Added quantity must be greater than 0."}), 400

    user_name = session.get('user', {}).get('name', 'Pharmacist Admin')
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    today = datetime.now()

    if mode == "existing" and not df.empty:
        mask = df["Medicine"].str.lower() == med_name.lower()
        if not mask.any():
            return jsonify({"error": f"Medicine '{med_name}' not found in current inventory. Use 'new' mode to add a new medicine."}), 404

        indices = df[mask].index
        prev_stock = int(df.at[indices[0], "Stock"])
        new_stock = prev_stock + added_qty

        df.loc[mask, "Stock"] = new_stock

        if data.get("batch"):
            df.loc[mask, "Batch"] = data.get("batch").strip()
        if data.get("expiry"):
            try:
                df.loc[mask, "Expiry"] = pd.to_datetime(data.get("expiry"))
            except Exception:
                pass

        category = str(df.at[indices[0], "Category"])
        company = str(df.at[indices[0], "Company"])

        log_entry = {
            "timestamp": now_str,
            "medicine": med_name,
            "category": category,
            "company": company,
            "mode": "Replenish Existing Stock",
            "previous_stock": prev_stock,
            "added_qty": added_qty,
            "new_stock": new_stock,
            "user": user_name
        }
        store["stock_log"].insert(0, log_entry)
        save_user_store()

        return jsonify({
            "message": f"Successfully added {added_qty} strips to {med_name}! Stock updated from {prev_stock} to {new_stock} strips.",
            "medicine": med_name,
            "previous_stock": prev_stock,
            "added_qty": added_qty,
            "new_stock": new_stock,
            "log": log_entry
        })

    else:
        # Mode: new medicine creation (or first medicine in clean slate)
        category = data.get("category", "General").strip() or "General"
        company = data.get("company", "Generic Pharma").strip() or "Generic Pharma"
        batch = data.get("batch", "B1001").strip() or "B1001"
        buy_price = float(data.get("buy_price", 50.0))
        sell_price = float(data.get("sell_price", 80.0))
        supplier = data.get("supplier", "Main Distributor").strip() or "Main Distributor"
        expiry_str = data.get("expiry", "")
        
        try:
            expiry_dt = pd.to_datetime(expiry_str) if expiry_str else today + pd.Timedelta(days=500)
        except Exception:
            expiry_dt = today + pd.Timedelta(days=500)

        new_row = {
            "Date": today,
            "Medicine": med_name,
            "Category": category,
            "Company": company,
            "Batch": batch,
            "Qty": 0,
            "Sell Price": sell_price,
            "Buy Price": buy_price,
            "Stock": added_qty,
            "Expiry": expiry_dt,
            "Supplier": supplier,
            "Invoice No": "INITIAL-STOCK",
            "GST": float(data.get("gst", 12.0)),
            "HSN": str(data.get("hsn", "3004")),
            "Discount": 0.0,
            "Total": 0.0,
            "Sales": 0.0,
            "Cost": 0.0,
            "Profit": 0.0,
            "Margin_Pct": ((sell_price - buy_price) / sell_price * 100) if sell_price > 0 else 0,
            "Year": today.year,
            "Month": today.strftime("%Y-%m"),
            "Week": today.isocalendar()[1],
            "DayName": today.strftime("%A"),
            "DateStr": today.strftime("%Y-%m-%d")
        }

        if df.empty:
            store["df"] = pd.DataFrame([new_row])
        else:
            store["df"] = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)

        log_entry = {
            "timestamp": now_str,
            "medicine": med_name,
            "category": category,
            "company": company,
            "mode": "New Medicine Added",
            "previous_stock": 0,
            "added_qty": added_qty,
            "new_stock": added_qty,
            "user": user_name
        }
        store["stock_log"].insert(0, log_entry)
        save_user_store()

        return jsonify({
            "message": f"Successfully created new medicine '{med_name}' with initial stock of {added_qty} strips!",
            "medicine": med_name,
            "previous_stock": 0,
            "added_qty": added_qty,
            "new_stock": added_qty,
            "log": log_entry
        })

@app.route('/api/stock/log', methods=['GET'])
def get_stock_addition_log():
    """Returns log of stock additions for active user."""
    store = get_user_store()
    return jsonify({"logs": store["stock_log"]})


# ==============================================================================
# POS Billing & Customer Invoicing
# ==============================================================================

@app.route('/api/pos/sell', methods=['POST'])
def pos_sell():
    """
    POS Checkout & Automatic Inventory Stock Deduction API:
    - Deducts sold Qty from live user inventory.
    - Saves invoice to user invoice store.
    """
    store = get_user_store()
    df = store["df"]

    if df.empty:
        return jsonify({"error": "No medicines in inventory. Please add stock or upload a product sheet before billing."}), 400

    data = request.json or {}
    customer_name = data.get("customer_name", "Walk-in Customer").strip() or "Walk-in Customer"
    customer_phone = data.get("customer_phone", "N/A").strip() or "N/A"
    discount_pct = float(data.get("discount_pct", 0.0))
    payment_mode = data.get("payment_mode", "Cash").strip()
    items = data.get("items", [])

    if not items:
        return jsonify({"error": "Please add at least one medicine item to checkout."}), 400

    validation_errors = []
    for item in items:
        med_name = item.get("medicine")
        qty = int(item.get("qty", 1))

        mask = df["Medicine"].str.lower() == med_name.lower()
        if not mask.any():
            validation_errors.append(f"Medicine '{med_name}' not found in store inventory.")
            continue

        available_stock = int(df.loc[mask, "Stock"].iloc[0])
        if qty > available_stock:
            validation_errors.append(f"Insufficient stock for '{med_name}'! Available: {available_stock} strips, Requested: {qty}.")

    if validation_errors:
        return jsonify({"error": "Stock Validation Failed", "details": validation_errors}), 400

    store["invoice_counter"] += 1
    invoice_no = f"INV-2026-{store['invoice_counter']}"
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    billed_by = session.get('user', {}).get('name', 'Pharma Staff')
    store_name = session.get('user', {}).get('store_name', 'HealthCare Central Pharmacy')

    invoice_items = []
    subtotal = 0.0
    new_sales_rows = []

    for item in items:
        med_name = item.get("medicine")
        qty = int(item.get("qty", 1))

        idx = df[df["Medicine"].str.lower() == med_name.lower()].index[0]
        
        current_stock = int(df.at[idx, "Stock"])
        remaining_stock = current_stock - qty

        # AUTOMATIC STOCK DEDUCTION
        df.at[idx, "Stock"] = remaining_stock

        sell_price = float(df.at[idx, "Sell Price"])
        buy_price = float(df.at[idx, "Buy Price"])
        cat = str(df.at[idx, "Category"])
        comp = str(df.at[idx, "Company"])
        batch = str(df.at[idx, "Batch"])
        supplier = str(df.at[idx, "Supplier"])

        line_total = round(qty * sell_price, 2)
        subtotal += line_total

        invoice_items.append({
            "medicine": med_name,
            "category": cat,
            "company": comp,
            "batch": batch,
            "qty": qty,
            "unit_price": sell_price,
            "line_total": line_total,
            "previous_stock": current_stock,
            "remaining_stock": remaining_stock
        })

        today = datetime.now()
        new_row = {
            "Date": today,
            "Medicine": med_name,
            "Category": cat,
            "Company": comp,
            "Batch": batch,
            "Qty": qty,
            "Sell Price": sell_price,
            "Buy Price": buy_price,
            "Stock": remaining_stock,
            "Expiry": today + pd.Timedelta(days=500),
            "Supplier": supplier,
            "Invoice No": invoice_no,
            "GST": 12,
            "HSN": "3004",
            "Discount": discount_pct,
            "Total": line_total,
            "Sales": line_total,
            "Cost": qty * buy_price,
            "Profit": line_total - (qty * buy_price),
            "Margin_Pct": ((line_total - (qty * buy_price)) / line_total * 100) if line_total > 0 else 0,
            "Year": today.year,
            "Month": today.strftime("%Y-%m"),
            "Week": today.isocalendar()[1],
            "DayName": today.strftime("%A"),
            "DateStr": today.strftime("%Y-%m-%d")
        }
        new_sales_rows.append(new_row)

    if new_sales_rows:
        new_df = pd.DataFrame(new_sales_rows)
        store["df"] = pd.concat([df, new_df], ignore_index=True)

    discount_amount = round(subtotal * (discount_pct / 100.0), 2)
    taxable_amount = subtotal - discount_amount
    tax_amount = round(taxable_amount * 0.12, 2)
    grand_total = round(taxable_amount + tax_amount, 2)

    invoice_payload = {
        "invoice_no": invoice_no,
        "date": now_str,
        "customer_name": customer_name,
        "customer_phone": customer_phone,
        "billed_by": billed_by,
        "store_name": store_name,
        "payment_mode": payment_mode,
        "items": invoice_items,
        "subtotal": subtotal,
        "discount_pct": discount_pct,
        "discount_amount": discount_amount,
        "tax_amount": tax_amount,
        "grand_total": grand_total
    }

    store["invoice_store"][invoice_no] = invoice_payload
    store["invoices"].insert(0, invoice_payload)
    save_user_store()

    return jsonify({
        "message": f"Invoice {invoice_no} generated successfully! Stock automatically deducted.",
        "invoice": invoice_payload
    })

@app.route('/api/pos/history', methods=['GET'])
def get_invoice_history():
    """Returns searchable historical customer invoices audit list for active user."""
    store = get_user_store()
    history = store["invoices"]

    q = request.args.get("q", "").strip().lower()
    payment_mode = request.args.get("payment_mode", "ALL").strip()

    filtered_history = []
    total_revenue = 0.0

    for inv in history:
        match_q = True
        if q:
            c_name = inv.get("customer_name", "").lower()
            c_phone = inv.get("customer_phone", "").lower()
            inv_no = inv.get("invoice_no", "").lower()
            match_q = (q in c_name or q in c_phone or q in inv_no)

        match_mode = True
        if payment_mode != "ALL":
            match_mode = (inv.get("payment_mode", "Cash").lower() == payment_mode.lower())

        if match_q and match_mode:
            filtered_history.append(inv)
            total_revenue += inv.get("grand_total", 0.0)

    avg_value = round(total_revenue / len(filtered_history), 2) if filtered_history else 0.0

    return jsonify({
        "invoices": filtered_history,
        "summary": {
            "total_count": len(filtered_history),
            "total_revenue": round(total_revenue, 2),
            "avg_invoice_value": avg_value
        }
    })

@app.route('/api/pos/invoice/<invoice_no>', methods=['GET'])
def get_customer_invoice_pdf(invoice_no):
    """Download printable Customer Invoice Receipt PDF for past transaction."""
    store = get_user_store()
    invoice = store["invoice_store"].get(invoice_no)
    if not invoice:
        for inv in store["invoices"]:
            if inv.get("invoice_no") == invoice_no:
                invoice = inv
                break

    if not invoice:
        return jsonify({"error": f"Invoice {invoice_no} not found."}), 404

    pdf_bytes = rep.generate_customer_invoice_pdf(invoice)
    return send_file(
        io.BytesIO(pdf_bytes),
        mimetype="application/pdf",
        as_attachment=True,
        download_name=f"Invoice_{invoice_no}.pdf"
    )


# ==============================================================================
# CSV Upload & File Processing
# ==============================================================================

@app.route('/api/upload', methods=['POST'])
def upload_sales_sheet():
    """Dynamic Sales Sheet CSV/XLSX Upload Endpoint (Isolated per User)."""
    store = get_user_store()
    
    if 'file' not in request.files:
        return jsonify({"error": "No file uploaded"}), 400

    file = request.files['file']
    if file.filename == '':
        return jsonify({"error": "Selected file is empty"}), 400

    try:
        filename = file.filename.lower()
        if filename.endswith('.csv'):
            raw_df = pd.read_csv(file)
        elif filename.endswith(('.xlsx', '.xls')):
            raw_df = pd.read_excel(file)
        else:
            return jsonify({"error": "Unsupported file format. Please upload a .csv or .xlsx file."}), 400

        mapped_df, mapping_info = clean_and_map_dataframe(raw_df)
        store["df"] = mapped_df
        store["mapping_info"] = mapping_info
        save_user_store()

        return jsonify({
            "message": f"Successfully processed and mapped {len(mapped_df)} sales records!",
            "mapping_summary": mapping_info,
            "record_count": len(mapped_df)
        })

    except Exception as e:
        return jsonify({"error": f"Failed to process sales sheet: {str(e)}"}), 500

@app.route('/api/export/mapped-csv', methods=['GET'])
def export_mapped_csv():
    """Download mapped CSV for active user."""
    store = get_user_store()
    df = store["df"]
    if df.empty:
        return jsonify({"error": "No dataset loaded"}), 400
    
    csv_data = df.to_csv(index=False)
    return Response(
        csv_data,
        mimetype="text/csv",
        headers={"Content-disposition": "attachment; filename=mapped_output.csv"}
    )


# ==============================================================================
# Assistant, Chatbot & Report Exports
# ==============================================================================

@app.route('/api/assistant/new-pharmacy', methods=['POST'])
def new_pharmacy_assistant():
    """API for the New Pharmacy Owner Assistant Wizard."""
    data = request.json or {}
    result = ml.new_pharmacy_assistant_ai(data)
    return jsonify(result)

@app.route('/api/chatbot', methods=['POST'])
def chatbot_query():
    """Natural Language Chatbot API."""
    store = get_user_store()
    df = store["df"]
    data = request.json or {}
    query = data.get("query", "")
    response = ml.process_chatbot_query(query, df)
    return jsonify(response)

@app.route('/api/export/<file_format>', methods=['GET'])
def export_report(file_format):
    """Report Generator Download Endpoint (PDF, Excel, CSV) for active user."""
    store = get_user_store()
    df = store["df"]
    if df.empty:
        return jsonify({"error": "No dataset available for export. Please upload a sales sheet first."}), 400

    kpis = ml.compute_kpis(df)
    stock_info = ml.compute_stock_and_expiry_dashboard(df)
    forecast_info = ml.run_ml_forecasting(df)
    prod_info = ml.compute_product_analytics(df)

    fmt = file_format.lower()
    
    if fmt == 'csv':
        csv_data = rep.generate_csv_report(df)
        return Response(
            csv_data,
            mimetype="text/csv",
            headers={"Content-disposition": "attachment; filename=Pharmora_Sales_Report.csv"}
        )
    elif fmt in ['excel', 'xlsx']:
        excel_bytes = rep.generate_excel_report(df, stock_info, forecast_info, prod_info)
        return send_file(
            io.BytesIO(excel_bytes),
            mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            as_attachment=True,
            download_name="Pharmora_Full_Analytics_Report.xlsx"
        )
    elif fmt == 'pdf':
        pdf_bytes = rep.generate_pdf_report(df, kpis, stock_info, forecast_info, prod_info)
        return send_file(
            io.BytesIO(pdf_bytes),
            mimetype="application/pdf",
            as_attachment=True,
            download_name="Pharmora_Executive_Report.pdf"
        )
    else:
        return jsonify({"error": "Invalid format. Choose 'pdf', 'excel', or 'csv'."}), 400

if __name__ == '__main__':
    print("Starting Pharmora Server on http://127.0.0.1:5000")
    app.run(host='127.0.0.1', port=5000, debug=True, use_reloader=False)
