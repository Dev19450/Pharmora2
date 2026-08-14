import os
import io
import json
import pandas as pd
from datetime import datetime
from flask import Flask, render_template, request, jsonify, send_file, Response, session

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
INVOICE_HISTORY_FILE = os.path.join(DATASETS_DIR, "invoice_history.json")

app = Flask(__name__, template_folder=TEMPLATES_DIR, static_folder=STATIC_DIR)
app.secret_key = "pharma_ai_super_secret_session_key_2026"
app.config['MAX_CONTENT_LENGTH'] = 32 * 1024 * 1024

app.register_blueprint(auth_bp)

# Global active dataset, Invoice store & Stock Addition Log
ACTIVE_DF = pd.DataFrame()
LAST_MAPPING_INFO = {}
INVOICE_STORE = {}
INVOICE_HISTORY = []
STOCK_ADDITION_LOG = []
INVOICE_COUNTER = 1001

def load_invoice_history():
    global INVOICE_HISTORY, INVOICE_STORE, INVOICE_COUNTER
    if not os.path.exists(INVOICE_HISTORY_FILE):
        default_invoices = [
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
        save_invoice_history(default_invoices)
        INVOICE_HISTORY = default_invoices
    else:
        try:
            with open(INVOICE_HISTORY_FILE, "r") as f:
                INVOICE_HISTORY = json.load(f)
        except Exception as e:
            print(f"Error loading invoice history: {e}")
            INVOICE_HISTORY = []

    for inv in INVOICE_HISTORY:
        INVOICE_STORE[inv["invoice_no"]] = inv
        try:
            num = int(inv["invoice_no"].split("-")[-1])
            if num > INVOICE_COUNTER:
                INVOICE_COUNTER = num
        except Exception:
            pass

def save_invoice_history(history_list=None):
    if history_list is None:
        history_list = INVOICE_HISTORY
    os.makedirs(os.path.dirname(INVOICE_HISTORY_FILE), exist_ok=True)
    with open(INVOICE_HISTORY_FILE, "w") as f:
        json.dump(history_list, f, indent=2)

def load_initial_dataset():
    global ACTIVE_DF, LAST_MAPPING_INFO
    if os.path.exists(DEFAULT_CSV):
        try:
            raw_df = pd.read_csv(DEFAULT_CSV)
            ACTIVE_DF, LAST_MAPPING_INFO = clean_and_map_dataframe(raw_df)
            print(f"Loaded default dataset with {len(ACTIVE_DF)} records.")
        except Exception as e:
            print(f"Error loading default CSV: {e}")
    load_invoice_history()

load_initial_dataset()

@app.route('/')
def index():
    """Render main application page."""
    return render_template('index.html')

@app.route('/api/dashboard/full', methods=['GET'])
def get_full_dashboard():
    """Returns complete JSON analytics payload for active dataset with dynamic Tableau parameters."""
    global ACTIVE_DF, LAST_MAPPING_INFO
    if ACTIVE_DF.empty:
        return jsonify({"error": "No dataset loaded"}), 400

    filters = {
        "category": request.args.get("category", "ALL"),
        "company": request.args.get("company", "ALL"),
        "year": request.args.get("year", "ALL")
    }

    filtered_df = ml.apply_filters(ACTIVE_DF, filters)

    mode = request.args.get("mode", "top")
    top_n = int(request.args.get("top_n", 10))
    measure = request.args.get("measure", "sales")
    stock_measure = request.args.get("stock_measure", "units")

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
    filter_options = ml.get_filter_options(ACTIVE_DF)

    return jsonify({
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
        "mapping_info": LAST_MAPPING_INFO,
        "record_count": len(filtered_df),
        "total_record_count": len(ACTIVE_DF)
    })

@app.route('/api/stock/add', methods=['POST'])
def add_medicine_stock():
    """
    Add / Replenish Medicine Stock Endpoint:
    - Allows adding additional stock to an existing medicine at ANY time.
    - Also supports adding a completely new medicine entry to inventory.
    - Updates ACTIVE_DF instantly and records entry in STOCK_ADDITION_LOG.
    """
    global ACTIVE_DF, STOCK_ADDITION_LOG

    if ACTIVE_DF.empty:
        return jsonify({"error": "No dataset loaded."}), 400

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

    if mode == "existing":
        mask = ACTIVE_DF["Medicine"].str.lower() == med_name.lower()
        if not mask.any():
            return jsonify({"error": f"Medicine '{med_name}' not found in current inventory. Use 'new' mode to add a new medicine."}), 404

        # Get current stock
        indices = ACTIVE_DF[mask].index
        prev_stock = int(ACTIVE_DF.at[indices[0], "Stock"])
        new_stock = prev_stock + added_qty

        # Update Stock across all rows for this medicine in ACTIVE_DF
        ACTIVE_DF.loc[mask, "Stock"] = new_stock

        # Optional update of batch or expiry if provided
        if data.get("batch"):
            ACTIVE_DF.loc[mask, "Batch"] = data.get("batch").strip()
        if data.get("expiry"):
            try:
                ACTIVE_DF.loc[mask, "Expiry"] = pd.to_datetime(data.get("expiry"))
            except Exception:
                pass

        category = str(ACTIVE_DF.at[indices[0], "Category"])
        company = str(ACTIVE_DF.at[indices[0], "Company"])

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
        STOCK_ADDITION_LOG.insert(0, log_entry)

        return jsonify({
            "message": f"Successfully added {added_qty} strips to {med_name}! Stock updated from {prev_stock} to {new_stock} strips.",
            "medicine": med_name,
            "previous_stock": prev_stock,
            "added_qty": added_qty,
            "new_stock": new_stock,
            "log": log_entry
        })

    else:
        # Mode: new medicine creation
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

        # Build complete new dataframe row
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

        ACTIVE_DF = pd.concat([ACTIVE_DF, pd.DataFrame([new_row])], ignore_index=True)

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
        STOCK_ADDITION_LOG.insert(0, log_entry)

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
    """Returns log of stock additions/replenishments."""
    global STOCK_ADDITION_LOG
    return jsonify({"logs": STOCK_ADDITION_LOG})

@app.route('/api/pos/sell', methods=['POST'])
def pos_sell():
    """
    POS Checkout & Automatic Inventory Stock Deduction API:
    - Validates stock.
    - Deducts sold Qty directly from live inventory (`Stock = Stock - Qty`).
    - Appends sales record to ACTIVE_DF so dashboard updates instantly.
    - Saves invoice record to invoice_history.json.
    - Returns formatted Customer Invoice JSON with remaining stock calculations.
    """
    global ACTIVE_DF, INVOICE_STORE, INVOICE_HISTORY, INVOICE_COUNTER

    if ACTIVE_DF.empty:
        return jsonify({"error": "No dataset loaded."}), 400

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

        mask = ACTIVE_DF["Medicine"].str.lower() == med_name.lower()
        if not mask.any():
            validation_errors.append(f"Medicine '{med_name}' not found in store inventory.")
            continue

        available_stock = int(ACTIVE_DF.loc[mask, "Stock"].iloc[0])
        if qty > available_stock:
            validation_errors.append(f"Insufficient stock for '{med_name}'! Available: {available_stock} strips, Requested: {qty}.")

    if validation_errors:
        return jsonify({"error": "Stock Validation Failed", "details": validation_errors}), 400

    INVOICE_COUNTER += 1
    invoice_no = f"INV-2026-{INVOICE_COUNTER}"
    now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    billed_by = session.get('user', {}).get('name', 'Pharma Staff')
    store_name = session.get('user', {}).get('store_name', 'HealthCare Central Pharmacy')

    invoice_items = []
    subtotal = 0.0
    new_sales_rows = []

    for item in items:
        med_name = item.get("medicine")
        qty = int(item.get("qty", 1))

        idx = ACTIVE_DF[ACTIVE_DF["Medicine"].str.lower() == med_name.lower()].index[0]
        
        current_stock = int(ACTIVE_DF.at[idx, "Stock"])
        remaining_stock = current_stock - qty

        # AUTOMATIC STOCK DEDUCTION
        ACTIVE_DF.at[idx, "Stock"] = remaining_stock

        sell_price = float(ACTIVE_DF.at[idx, "Sell Price"])
        buy_price = float(ACTIVE_DF.at[idx, "Buy Price"])
        cat = str(ACTIVE_DF.at[idx, "Category"])
        comp = str(ACTIVE_DF.at[idx, "Company"])
        batch = str(ACTIVE_DF.at[idx, "Batch"])
        supplier = str(ACTIVE_DF.at[idx, "Supplier"])

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
        ACTIVE_DF = pd.concat([ACTIVE_DF, new_df], ignore_index=True)

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

    INVOICE_STORE[invoice_no] = invoice_payload
    INVOICE_HISTORY.insert(0, invoice_payload)
    save_invoice_history()

    return jsonify({
        "message": f"Invoice {invoice_no} generated successfully! Stock automatically deducted.",
        "invoice": invoice_payload
    })

@app.route('/api/pos/history', methods=['GET'])
def get_invoice_history():
    """Returns searchable historical customer invoices audit list."""
    global INVOICE_HISTORY

    q = request.args.get("q", "").strip().lower()
    payment_mode = request.args.get("payment_mode", "ALL").strip()

    filtered_history = []
    total_revenue = 0.0

    for inv in INVOICE_HISTORY:
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
    """Download printable Customer Invoice Receipt PDF for any past transaction."""
    invoice = INVOICE_STORE.get(invoice_no)
    if not invoice:
        for inv in INVOICE_HISTORY:
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

@app.route('/api/upload', methods=['POST'])
def upload_sales_sheet():
    """Dynamic Sales Sheet CSV/XLSX Upload Endpoint."""
    global ACTIVE_DF, LAST_MAPPING_INFO
    
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
        ACTIVE_DF = mapped_df
        LAST_MAPPING_INFO = mapping_info

        return jsonify({
            "message": f"Successfully processed and mapped {len(mapped_df)} sales records!",
            "mapping_summary": mapping_info,
            "record_count": len(mapped_df)
        })

    except Exception as e:
        return jsonify({"error": f"Failed to process sales sheet: {str(e)}"}), 500

@app.route('/api/export/mapped-csv', methods=['GET'])
def export_mapped_csv():
    """Download mapped CSV (like mapped_output.csv in cs.py)."""
    global ACTIVE_DF
    if ACTIVE_DF.empty:
        return jsonify({"error": "No dataset loaded"}), 400
    
    csv_data = ACTIVE_DF.to_csv(index=False)
    return Response(
        csv_data,
        mimetype="text/csv",
        headers={"Content-disposition": "attachment; filename=mapped_output.csv"}
    )

@app.route('/api/assistant/new-pharmacy', methods=['POST'])
def new_pharmacy_assistant():
    """API for the New Pharmacy Owner Assistant Wizard."""
    data = request.json or {}
    result = ml.new_pharmacy_assistant_ai(data)
    return jsonify(result)

@app.route('/api/chatbot', methods=['POST'])
def chatbot_query():
    """Natural Language Chatbot API."""
    global ACTIVE_DF
    data = request.json or {}
    query = data.get("query", "")
    response = ml.process_chatbot_query(query, ACTIVE_DF)
    return jsonify(response)

@app.route('/api/export/<file_format>', methods=['GET'])
def export_report(file_format):
    """Report Generator Download Endpoint (PDF, Excel, CSV)."""
    global ACTIVE_DF
    if ACTIVE_DF.empty:
        return jsonify({"error": "No dataset available for export"}), 400

    df = ACTIVE_DF
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
    app.run(host='127.0.0.1', port=5000, debug=True)
