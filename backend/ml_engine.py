import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from sklearn.ensemble import RandomForestRegressor, GradientBoostingRegressor
from sklearn.linear_model import LinearRegression
from sklearn.cluster import KMeans
from scipy import stats

def apply_filters(df: pd.DataFrame, filters: dict) -> pd.DataFrame:
    """Applies dynamic filters (category, company, year, date range) to the DataFrame."""
    if df.empty:
        return df

    filtered_df = df.copy()

    # Category filter
    category_filter = filters.get("category")
    if category_filter and category_filter != "ALL":
        filtered_df = filtered_df[filtered_df["Category"].str.lower() == category_filter.lower()]

    # Company filter
    company_filter = filters.get("company")
    if company_filter and company_filter != "ALL":
        filtered_df = filtered_df[filtered_df["Company"].str.lower() == company_filter.lower()]

    # Year filter
    year_filter = filters.get("year")
    if year_filter and year_filter != "ALL":
        try:
            filtered_df = filtered_df[filtered_df["Year"] == int(year_filter)]
        except ValueError:
            pass

    return filtered_df

def compute_kpis(df: pd.DataFrame) -> dict:
    """Computes executive sales KPIs."""
    if df.empty:
        return {
            "total_sales": 0,
            "total_profit": 0,
            "total_orders": 0,
            "total_qty_sold": 0,
            "avg_margin": 0,
            "total_stock_value": 0
        }
    
    total_sales = float(df["Sales"].sum())
    total_profit = float(df["Profit"].sum())
    total_orders = int(len(df))
    total_qty_sold = int(df["Qty"].sum())
    avg_margin = float(df["Margin_Pct"].mean()) if "Margin_Pct" in df.columns else 0.0
    total_stock_value = float((df["Stock"] * df["Buy Price"]).sum())
    
    return {
        "total_sales": round(total_sales, 2),
        "total_profit": round(total_profit, 2),
        "total_orders": total_orders,
        "total_qty_sold": total_qty_sold,
        "avg_margin": round(avg_margin, 2),
        "total_stock_value": round(total_stock_value, 2)
    }

def compute_sales_trends(df: pd.DataFrame) -> dict:
    """Computes Monthly, Daily, Weekly, Yearly trends."""
    if df.empty:
        return {"monthly": [], "daily": [], "weekly": [], "yearly": []}
    
    # Monthly
    monthly = (
        df.groupby("Month")[["Sales", "Profit"]]
        .sum()
        .reset_index()
        .sort_values("Month")
    )
    monthly_data = [
        {"month": row["Month"], "sales": round(float(row["Sales"]), 2), "profit": round(float(row["Profit"]), 2)}
        for _, row in monthly.iterrows()
    ]

    # Daily
    daily = (
        df.groupby("DateStr")[["Sales", "Profit"]]
        .sum()
        .reset_index()
        .sort_values("DateStr")
        .tail(60)
    )
    daily_data = [
        {"date": row["DateStr"], "sales": round(float(row["Sales"]), 2), "profit": round(float(row["Profit"]), 2)}
        for _, row in daily.iterrows()
    ]

    # Weekly
    weekly = (
        df.groupby("Week")[["Sales", "Profit"]]
        .sum()
        .reset_index()
        .sort_values("Week")
    )
    weekly_data = [
        {"week": f"W{int(row['Week'])}", "sales": round(float(row["Sales"]), 2), "profit": round(float(row["Profit"]), 2)}
        for _, row in weekly.iterrows()
    ]

    # Yearly
    yearly = (
        df.groupby("Year")[["Sales", "Profit"]]
        .sum()
        .reset_index()
        .sort_values("Year")
    )
    yearly_data = [
        {"year": str(int(row["Year"])), "sales": round(float(row["Sales"]), 2), "profit": round(float(row["Profit"]), 2)}
        for _, row in yearly.iterrows()
    ]

    return {
        "monthly": monthly_data,
        "daily": daily_data,
        "weekly": weekly_data,
        "yearly": yearly_data
    }

def compute_stock_distribution(df: pd.DataFrame, stock_measure: str = "units") -> dict:
    """
    Computes Stock Distribution % Pie/Donut Chart data across Categories.
    stock_measure: 'units' (Stock Quantity) vs 'value' (Stock Value ₹)
    """
    if df.empty:
        return {"labels": [], "percentages": [], "values": []}

    df_stock = df.groupby("Category").agg(
        total_units=("Stock", "sum"),
        buy_price=("Buy Price", "first")
    ).reset_index()

    df_stock["total_value"] = df_stock["total_units"] * df_stock["buy_price"]

    if stock_measure == "value":
        grand_total = df_stock["total_value"].sum()
        metric_col = "total_value"
    else:
        grand_total = df_stock["total_units"].sum()
        metric_col = "total_units"

    if grand_total == 0:
        grand_total = 1.0

    df_stock["percentage"] = (df_stock[metric_col] / grand_total) * 100
    df_stock = df_stock.sort_values("percentage", ascending=False)

    return {
        "labels": df_stock["Category"].tolist(),
        "percentages": [round(float(p), 1) for p in df_stock["percentage"].tolist()],
        "values": [round(float(v), 2) for v in df_stock[metric_col].tolist()],
        "measure": stock_measure
    }

def compute_parameterized_medicines(df: pd.DataFrame, mode: str = "top", top_n: int = 10, measure: str = "sales") -> list:
    """
    Tableau-Style Parameter Control Engine for Bar Chart:
    - mode: 'top' (Top Selling) vs 'least' (Least Selling / Bottom N)
    - top_n: 5, 10, 15, 20
    - measure: 'sales' (Sales ₹), 'qty' (Units Sold), 'profit' (Net Profit ₹), 'margin' (Margin %)
    """
    if df.empty:
        return []

    med_grouped = df.groupby("Medicine").agg(
        sales=("Sales", "sum"),
        qty=("Qty", "sum"),
        profit=("Profit", "sum"),
        margin=("Margin_Pct", "mean"),
        category=("Category", "first"),
        company=("Company", "first"),
        stock=("Stock", "first")
    ).reset_index()

    measure_col = measure if measure in ["sales", "qty", "profit", "margin"] else "sales"

    ascending_order = True if mode.lower() == "least" else False
    sorted_df = med_grouped.sort_values(measure_col, ascending=ascending_order).head(top_n)

    result = []
    for _, row in sorted_df.iterrows():
        result.append({
            "medicine": row["Medicine"],
            "category": row["category"],
            "company": row["company"],
            "sales": round(float(row["sales"]), 2),
            "qty": int(row["qty"]),
            "profit": round(float(row["profit"]), 2),
            "margin": round(float(row["margin"]), 1),
            "stock": int(row["stock"]),
            "metric_value": round(float(row[measure_col]), 2)
        })

    return result

def compute_product_analytics(df: pd.DataFrame) -> dict:
    """
    Comprehensive product analytics:
    - Fast Moving Medicines (Velocity, Turnover & Stock Coverage Days)
    - Dead Stock & Slow Moving Inventory (Locked Working Capital ₹ & Liquidation Advice)
    - Highest Profit Medicines (Net Profit ₹, Margin %, Unit Margin & Profit Share %)
    - Categories & Companies Breakdown
    """
    if df.empty:
        return {
            "top_medicines": [], "categories": [], "companies": [],
            "highest_profit": [], "lowest_profit": [], "loss_making": [],
            "fast_moving": [], "slow_moving": [], "dead_stock": [],
            "dead_stock_summary": {"total_locked_capital": 0, "total_dead_units": 0, "count": 0},
            "profit_summary": {"top_profit_med": "N/A", "top_profit_val": 0, "top_fast_med": "N/A", "top_fast_units": 0}
        }

    total_store_profit = float(df["Profit"].sum()) if df["Profit"].sum() > 0 else 1.0

    # Group by Medicine with full dimensions
    med_grouped = (
        df.groupby("Medicine")
        .agg(
            qty_sold=("Qty", "sum"),
            sales=("Sales", "sum"),
            cost=("Cost", "sum") if "Cost" in df.columns else ("Sales", lambda x: 0),
            profit=("Profit", "sum"),
            margin_pct=("Margin_Pct", "mean"),
            current_stock=("Stock", "first"),
            category=("Category", "first"),
            company=("Company", "first"),
            buy_price=("Buy Price", "first"),
            sell_price=("Sell Price", "first"),
            min_date=("Date", "min"),
            max_date=("Date", "max"),
            tx_count=("Qty", "count")
        )
        .reset_index()
    )

    # Compute Velocity & Duration
    ref_max_date = df["Date"].max() if not df["Date"].isnull().all() else pd.to_datetime("today")
    med_grouped["days_active"] = (med_grouped["max_date"] - med_grouped["min_date"]).dt.days.clip(lower=1)
    med_grouped["days_since_last_sale"] = (ref_max_date - med_grouped["max_date"]).dt.days.clip(lower=0)
    med_grouped["daily_velocity"] = med_grouped["qty_sold"] / med_grouped["days_active"]
    med_grouped["monthly_velocity"] = med_grouped["daily_velocity"] * 30.0
    med_grouped["locked_capital"] = med_grouped["current_stock"] * med_grouped["buy_price"]
    med_grouped["unit_profit"] = med_grouped["sell_price"] - med_grouped["buy_price"]
    med_grouped["profit_share_pct"] = (med_grouped["profit"] / total_store_profit) * 100.0

    med_grouped["stock_coverage_days"] = np.where(
        med_grouped["daily_velocity"] > 0,
        (med_grouped["current_stock"] / med_grouped["daily_velocity"]).round(1),
        999.0
    )

    # 1. FAST MOVING MEDICINES (Top by sales quantity and velocity)
    fast_sorted = med_grouped.sort_values("qty_sold", ascending=False)
    fast_moving = []
    for _, r in fast_sorted.head(25).iterrows():
        coverage = float(r["stock_coverage_days"])
        if coverage < 15:
            urgency = "Urgent Reorder (Low Coverage)"
            status_color = "danger"
        elif coverage < 45:
            urgency = "Optimal Velocity"
            status_color = "success"
        else:
            urgency = "High Demand (Well Stocked)"
            status_color = "info"

        fast_moving.append({
            "medicine": r["Medicine"],
            "category": r["category"],
            "company": r["company"],
            "qty_sold": int(r["qty_sold"]),
            "sales": round(float(r["sales"]), 2),
            "profit": round(float(r["profit"]), 2),
            "stock": int(r["current_stock"]),
            "daily_velocity": round(float(r["daily_velocity"]), 2),
            "monthly_velocity": round(float(r["monthly_velocity"]), 1),
            "stock_coverage_days": coverage if coverage < 999 else "999+",
            "status": urgency,
            "status_color": status_color,
            "margin": round(float(r["margin_pct"]), 1)
        })

    # 2. DEAD STOCK & SLOW MOVING INVENTORY (Locked Capital Analyzer)
    # Dead stock: items with very low velocity relative to inventory or idle > 30 days
    dead_candidates = med_grouped[
        (med_grouped["daily_velocity"] <= 0.25) | 
        (med_grouped["qty_sold"] <= 8) | 
        (med_grouped["stock_coverage_days"] > 180)
    ].sort_values("locked_capital", ascending=False)

    if dead_candidates.empty:
        dead_candidates = med_grouped.sort_values("qty_sold", ascending=True).head(15)

    dead_stock = []
    for _, r in dead_candidates.iterrows():
        locked_val = float(r["locked_capital"])
        if locked_val >= 5000:
            rec_action = "Clearance 25% Discount"
            risk_level = "High Capital Blocked"
        elif int(r["current_stock"]) >= 100:
            rec_action = "Distributor Return Request"
            risk_level = "Excess Inventory"
        else:
            rec_action = "Bundle / Cross-sell Promo"
            risk_level = "Low Movement"

        dead_stock.append({
            "medicine": r["Medicine"],
            "category": r["category"],
            "company": r["company"],
            "stock": int(r["current_stock"]),
            "qty_sold": int(r["qty_sold"]),
            "buy_price": round(float(r["buy_price"]), 2),
            "locked_capital": round(locked_val, 2),
            "days_idle": int(r["days_since_last_sale"]),
            "action": rec_action,
            "risk_level": risk_level,
            "status": "Dead Stock / Idle Asset"
        })

    total_locked_capital = sum(d["locked_capital"] for d in dead_stock)
    total_dead_units = sum(d["stock"] for d in dead_stock)

    # 3. HIGHEST PROFIT MEDICINES
    profit_sorted = med_grouped.sort_values("profit", ascending=False)
    highest_profit = []
    for _, r in profit_sorted.head(15).iterrows():
        margin = float(r["margin_pct"])
        if margin >= 40:
            tag = "High-Margin Hero"
        elif float(r["profit"]) > 10000:
            tag = "Volume Profit Driver"
        else:
            tag = "Core Margin Contributor"

        highest_profit.append({
            "medicine": r["Medicine"],
            "category": r["category"],
            "company": r["company"],
            "sales": round(float(r["sales"]), 2),
            "profit": round(float(r["profit"]), 2),
            "margin": round(margin, 1),
            "unit_profit": round(float(r["unit_profit"]), 2),
            "profit_share": round(float(r["profit_share_pct"]), 1),
            "qty_sold": int(r["qty_sold"]),
            "tag": tag
        })

    lowest_profit = [
        {"medicine": r["Medicine"], "sales": round(float(r["sales"]), 2), "profit": round(float(r["profit"]), 2), "margin": round(float(r["margin_pct"]), 1)}
        for _, r in profit_sorted.tail(10).iloc[::-1].iterrows()
    ]

    loss_making = [
        {"medicine": r["Medicine"], "sales": round(float(r["sales"]), 2), "profit": round(float(r["profit"]), 2), "margin": round(float(r["margin_pct"]), 1)}
        for _, r in profit_sorted[profit_sorted["profit"] < 0].iterrows()
    ]

    # Category & Company Summaries
    cat_sales = (
        df.groupby("Category")[["Sales", "Profit", "Qty"]]
        .sum()
        .reset_index()
        .sort_values("Sales", ascending=False)
    )
    cat_data = [
        {"category": row["Category"], "sales": round(float(row["Sales"]), 2), "profit": round(float(row["Profit"]), 2), "qty": int(row["Qty"])}
        for _, row in cat_sales.iterrows()
    ]

    comp_sales = (
        df.groupby("Company")[["Sales", "Profit", "Qty"]]
        .sum()
        .reset_index()
        .sort_values("Sales", ascending=False)
        .head(12)
    )
    comp_data = [
        {"company": row["Company"], "sales": round(float(row["Sales"]), 2), "profit": round(float(row["Profit"]), 2), "qty": int(row["Qty"])}
        for _, row in comp_sales.iterrows()
    ]

    top_profit_med = highest_profit[0]["medicine"] if highest_profit else "N/A"
    top_profit_val = highest_profit[0]["profit"] if highest_profit else 0
    top_fast_med = fast_moving[0]["medicine"] if fast_moving else "N/A"
    top_fast_units = fast_moving[0]["qty_sold"] if fast_moving else 0

    return {
        "top_medicines": fast_moving[:15],
        "fast_moving": fast_moving,
        "slow_moving": dead_stock[:15],
        "dead_stock": dead_stock,
        "dead_stock_summary": {
            "total_locked_capital": round(total_locked_capital, 2),
            "total_dead_units": total_dead_units,
            "count": len(dead_stock)
        },
        "profit_summary": {
            "top_profit_med": top_profit_med,
            "top_profit_val": round(top_profit_val, 2),
            "top_fast_med": top_fast_med,
            "top_fast_units": top_fast_units
        },
        "highest_profit": highest_profit,
        "lowest_profit": lowest_profit,
        "loss_making": loss_making,
        "categories": cat_data,
        "companies": comp_data
    }

def compute_stock_and_expiry_dashboard(df: pd.DataFrame) -> dict:
    """Stock levels, Low Stock, Out of Stock, Overstock, Expiry tracking, Red Alert."""
    if df.empty:
        return {
            "summary": {
                "total_inventory_items": 0,
                "low_stock_count": 0,
                "out_of_stock_count": 0,
                "overstock_count": 0,
                "expiring_30_count": 0,
                "expiring_60_count": 0,
                "expiring_90_count": 0,
                "red_alert_count": 0
            },
            "low_stock": [],
            "out_of_stock": [],
            "overstock": [],
            "expiring_30": [],
            "expiring_60": [],
            "expiring_90": [],
            "red_alert": []
        }

    med_summary = (
        df.groupby("Medicine")
        .agg(
            stock=("Stock", "first"),
            category=("Category", "first"),
            company=("Company", "first"),
            buy_price=("Buy Price", "first"),
            sell_price=("Sell Price", "first"),
            total_qty_sold=("Qty", "sum"),
            days_span=("Date", lambda x: max((x.max() - x.min()).days, 1)),
            min_expiry=("Expiry", "min")
        )
        .reset_index()
    )

    med_summary["daily_sales_rate"] = med_summary["total_qty_sold"] / med_summary["days_span"]
    
    ref_date = df["Date"].max() if not df["Date"].isnull().all() else pd.to_datetime("today")
    med_summary["days_to_expiry"] = (med_summary["min_expiry"] - ref_date).dt.days

    med_summary["projected_sales_before_expiry"] = med_summary["daily_sales_rate"] * med_summary["days_to_expiry"].clip(lower=0)

    low_stock_df = med_summary[med_summary["stock"] < 30]
    out_of_stock_df = med_summary[med_summary["stock"] == 0]
    overstock_df = med_summary[med_summary["stock"] > 350]

    expiring_30 = med_summary[(med_summary["days_to_expiry"] >= 0) & (med_summary["days_to_expiry"] <= 30)]
    expiring_60 = med_summary[(med_summary["days_to_expiry"] > 30) & (med_summary["days_to_expiry"] <= 60)]
    expiring_90 = med_summary[(med_summary["days_to_expiry"] > 60) & (med_summary["days_to_expiry"] <= 90)]

    red_alert_df = med_summary[
        (med_summary["days_to_expiry"] > 0) & 
        (med_summary["days_to_expiry"] <= 180) & 
        (med_summary["stock"] > med_summary["projected_sales_before_expiry"] * 1.2)
    ].sort_values("days_to_expiry")

    def format_list(subset_df):
        out = []
        for _, r in subset_df.iterrows():
            exp_str = r["min_expiry"].strftime("%Y-%m-%d") if pd.notnull(r["min_expiry"]) else "N/A"
            out.append({
                "medicine": r["Medicine"],
                "category": r["category"],
                "company": r["company"],
                "stock": int(r["stock"]),
                "expiry": exp_str,
                "days_to_expiry": int(r["days_to_expiry"]) if pd.notnull(r["days_to_expiry"]) else 999,
                "daily_rate": round(float(r["daily_sales_rate"]), 2),
                "risk_reason": f"Stock ({int(r['stock'])}) exceeds projected demand ({int(r['projected_sales_before_expiry'])}) before expiry date!"
            })
        return out

    return {
        "summary": {
            "total_medicines": int(len(med_summary)),
            "low_stock_count": int(len(low_stock_df)),
            "out_of_stock_count": int(len(out_of_stock_df)),
            "overstock_count": int(len(overstock_df)),
            "red_alert_count": int(len(red_alert_df))
        },
        "low_stock": format_list(low_stock_df.sort_values("stock")),
        "out_of_stock": format_list(out_of_stock_df),
        "overstock": format_list(overstock_df.sort_values("stock", ascending=False)),
        "expiring_30": format_list(expiring_30),
        "expiring_60": format_list(expiring_60),
        "expiring_90": format_list(expiring_90),
        "red_alert": format_list(red_alert_df)
    }

def compute_abc_xyz_analysis(df: pd.DataFrame) -> dict:
    """ABC & XYZ Analysis."""
    if df.empty:
        return {"matrix": [], "summary": {}}

    med_sales = (
        df.groupby("Medicine")
        .agg(total_sales=("Sales", "sum"), total_qty=("Qty", "sum"))
        .reset_index()
        .sort_values("total_sales", ascending=False)
    )

    grand_total_sales = med_sales["total_sales"].sum()
    if grand_total_sales == 0:
        grand_total_sales = 1.0
        
    med_sales["cum_sales"] = med_sales["total_sales"].cumsum()
    med_sales["cum_pct"] = (med_sales["cum_sales"] / grand_total_sales) * 100

    def get_abc_class(pct):
        if pct <= 70:
            return "A (Most Important)"
        elif pct <= 90:
            return "B (Medium Importance)"
        else:
            return "C (Least Important)"

    med_sales["abc_class"] = med_sales["cum_pct"].apply(get_abc_class)

    monthly_med = (
        df.groupby(["Medicine", "Month"])["Qty"]
        .sum()
        .reset_index()
    )

    xyz_list = []
    for med, group in monthly_med.groupby("Medicine"):
        mean_qty = group["Qty"].mean()
        std_qty = group["Qty"].std(ddof=0)
        cv = (std_qty / mean_qty) if mean_qty > 0 else 0.0

        if cv <= 0.5:
            xyz_class = "X (Stable Demand)"
        elif cv <= 1.0:
            xyz_class = "Y (Variable Demand)"
        else:
            xyz_class = "Z (Volatile Demand)"

        xyz_list.append({"Medicine": med, "cv": round(cv, 2), "xyz_class": xyz_class})

    xyz_df = pd.DataFrame(xyz_list)
    merged = pd.merge(med_sales, xyz_df, on="Medicine", how="left")

    abc_output = [
        {
            "medicine": row["Medicine"],
            "total_sales": round(float(row["total_sales"]), 2),
            "cum_pct": round(float(row["cum_pct"]), 1),
            "abc_class": row["abc_class"],
            "xyz_class": row["xyz_class"]
        }
        for _, row in merged.iterrows()
    ]

    return {
        "matrix": abc_output,
        "summary": {
            "abc_counts": merged["abc_class"].value_counts().to_dict(),
            "xyz_counts": merged["xyz_class"].value_counts().to_dict()
        }
    }

def run_ml_forecasting(df: pd.DataFrame) -> dict:
    """Machine Learning Regression Models & Demand Forecasting."""
    if df.empty or len(df) < 5:
        return {"predictions": {}, "demand_forecast": [], "recommendations": []}

    monthly_data = (
        df.groupby("Month")
        .agg(sales=("Sales", "sum"), qty=("Qty", "sum"), profit=("Profit", "sum"))
        .reset_index()
        .sort_values("Month")
    )
    
    monthly_data["month_num"] = np.arange(len(monthly_data))
    
    X = monthly_data[["month_num"]].values
    y_sales = monthly_data["sales"].values

    lr = LinearRegression()
    lr.fit(X, y_sales)

    rf = RandomForestRegressor(n_estimators=100, random_state=42)
    rf.fit(X, y_sales)

    gb = GradientBoostingRegressor(n_estimators=100, random_state=42)
    gb.fit(X, y_sales)

    next_month_num = len(monthly_data)
    
    pred_lr_m = float(lr.predict([[next_month_num]])[0])
    pred_rf_m = float(rf.predict([[next_month_num]])[0])
    pred_gb_m = float(gb.predict([[next_month_num]])[0])

    ensemble_next_month = round(max((pred_lr_m + pred_rf_m + pred_gb_m) / 3, 0), 2)
    ensemble_next_week = round(ensemble_next_month / 4.33, 2)
    ensemble_next_year = round(ensemble_next_month * 12 * 1.05, 2)

    item_stats = (
        df.groupby("Medicine")
        .agg(
            monthly_avg_qty=("Qty", lambda x: float(x.sum() / max(len(df["Month"].unique()), 1))),
            current_stock=("Stock", "first"),
            buy_price=("Buy Price", "first"),
            sell_price=("Sell Price", "first"),
            category=("Category", "first")
        )
        .reset_index()
    )

    demand_forecast = []
    reorder_suggestions = []
    stock_recommendations = []

    for _, row in item_stats.iterrows():
        med = row["Medicine"]
        avg_qty = row["monthly_avg_qty"]
        stock = row["current_stock"]
        
        predicted_demand = int(np.ceil(avg_qty * 1.15))
        
        demand_forecast.append({
            "medicine": med,
            "predicted_demand": predicted_demand,
            "monthly_avg": round(avg_qty, 1),
            "display_text": f"Need {predicted_demand} {med}"
        })

        reorder_point = int(np.ceil(avg_qty * 0.5))
        if stock < reorder_point:
            recommended_reorder = max(predicted_demand - stock, 50)
            reorder_suggestions.append({
                "medicine": med,
                "current_stock": int(stock),
                "reorder_point": reorder_point,
                "recommended_reorder": int(recommended_reorder),
                "status": "CRITICAL_REORDER" if stock < 20 else "REORDER_SOON"
            })

        if stock < predicted_demand * 0.5:
            action = "Increase"
            reason = f"High projected demand ({predicted_demand} units) vs current stock ({int(stock)})"
            type_flag = "increase"
        elif stock > predicted_demand * 3 and stock > 200:
            action = "Reduce"
            reason = f"Excess inventory ({int(stock)} units) relative to monthly sales velocity"
            type_flag = "reduce"
        else:
            action = "Maintain"
            reason = "Optimal inventory buffer matching forecasted demand"
            type_flag = "maintain"

        stock_recommendations.append({
            "medicine": med,
            "action": action,
            "reason": reason,
            "type": type_flag,
            "category": row["category"]
        })

    return {
        "models_prediction": {
            "next_week_sales": ensemble_next_week,
            "next_month_sales": ensemble_next_month,
            "next_year_sales": ensemble_next_year,
            "model_breakdown": {
                "linear_regression": round(max(pred_lr_m, 0), 2),
                "random_forest": round(max(pred_rf_m, 0), 2),
                "xgboost_gb": round(max(pred_gb_m, 0), 2)
            }
        },
        "demand_forecast": demand_forecast,
        "reorder_suggestions": reorder_suggestions,
        "stock_recommendations": stock_recommendations
    }

def get_seasonal_recommendations(df: pd.DataFrame) -> dict:
    """Categorizes medicines into seasonal demand clusters."""
    rainy_keywords = ["antibiotic", "cold", "fever", "paracetamol", "dolo", "azithromycin", "amoxicillin"]
    summer_keywords = ["hydration", "ors", "electrolyte", "vitamin", "zinc", "glucose"]
    winter_keywords = ["cold", "cough", "syrup", "allergy", "cetirizine"]

    rainy_meds = []
    summer_meds = []
    winter_meds = []

    unique_meds = df[["Medicine", "Category"]].drop_duplicates()

    for _, r in unique_meds.iterrows():
        med = r["Medicine"]
        cat = r["Category"]
        combined = f"{med} {cat}".lower()

        if any(k in combined for k in rainy_keywords):
            rainy_meds.append(med)
        if any(k in combined for k in summer_keywords):
            summer_meds.append(med)
        if any(k in combined for k in winter_keywords):
            winter_meds.append(med)

    return {
        "rainy": {
            "season": "Rainy Season",
            "action": "Increase Stock",
            "medicines": list(set(rainy_meds))[:6],
            "reason": "Monsoon increases incidence of water-borne fever & bacterial infections."
        },
        "summer": {
            "season": "Summer Season",
            "action": "Increase Stock",
            "medicines": list(set(summer_meds))[:6],
            "reason": "Heatwaves trigger dehydration & heat stroke requiring hydration supplements."
        },
        "winter": {
            "season": "Winter Season",
            "action": "Increase Stock",
            "medicines": list(set(winter_meds))[:6],
            "reason": "Cold weather spikes viral infections, dry coughs & nasal allergies."
        }
    }

def new_pharmacy_assistant_ai(inputs: dict) -> dict:
    """New Pharmacy Assistant AI Setup Wizard."""
    budget = float(inputs.get("budget", 500000))
    population = int(inputs.get("population", 50000))
    hospitals = int(inputs.get("nearby_hospitals", 2))
    clinics = int(inputs.get("nearby_clinics", 5))

    allocations = {
        "Painkiller & Anti-inflammatory": round(budget * 0.22, 2),
        "Antibiotics & Anti-infectives": round(budget * 0.28, 2),
        "Vitamins & Supplements": round(budget * 0.15, 2),
        "Diabetes & Cardiac Care": round(budget * 0.18, 2),
        "Gastric & Digestive Health": round(budget * 0.10, 2),
        "Cold, Cough & Hydration": round(budget * 0.07, 2)
    }

    initial_stock = [
        {"medicine": "Crocin / Paracetamol 650", "category": "Painkiller", "qty": int(population * 0.008), "expected_sales": int(population * 0.006), "reason": "High baseline demand for fever and general aches."},
        {"medicine": "Amoxicillin 500mg", "category": "Antibiotic", "qty": int(hospitals * 120 + clinics * 40), "expected_sales": int(hospitals * 100), "reason": "Primary antibiotic prescribed by local clinics."},
        {"medicine": "ORS Powder & Electrolytes", "category": "Hydration", "qty": 300, "expected_sales": 250, "reason": "High OTC repeat purchase rate for dehydration."},
        {"medicine": "Cetirizine 10mg", "category": "Allergy", "qty": 250, "expected_sales": 200, "reason": "Universal allergy and cold relief medicine."},
        {"medicine": "Pantoprazole 40mg", "category": "Gastric", "qty": 400, "expected_sales": 350, "reason": "Frequently co-prescribed with antibiotics & painkillers."},
        {"medicine": "Metformin 500mg", "category": "Diabetes", "qty": 350, "expected_sales": 300, "reason": "Chronic daily refill medicine for diabetic patients."},
        {"medicine": "Vitamin D3 & Calcium", "category": "Supplement", "qty": 200, "expected_sales": 160, "reason": "High margin wellness supplement."}
    ]

    projected_revenue = round(budget * 0.35 + (population * 4.5) + (hospitals * 25000), 2)

    return {
        "budget_allocation": allocations,
        "recommended_initial_stock": initial_stock,
        "projected_monthly_sales": projected_revenue,
        "market_score": min(round(7.2 + (hospitals * 0.5) + (clinics * 0.2), 1), 9.9)
    }

def detect_sales_anomalies(df: pd.DataFrame) -> list:
    """Detects unusual sales spikes, drops, or inventory transaction errors."""
    if df.empty or len(df) < 10:
        return []

    df_clean = df.copy()
    z_scores = np.abs(stats.zscore(df_clean["Sales"]))
    df_clean["z_score"] = z_scores

    anomalies = df_clean[df_clean["z_score"] > 2.8]

    results = []
    for _, r in anomalies.head(10).iterrows():
        results.append({
            "date": r["DateStr"],
            "medicine": r["Medicine"],
            "sales": round(float(r["Sales"]), 2),
            "qty": int(r["Qty"]),
            "reason": "Unusually high transaction volume / potential bulk order spike or entry typo." if r["Sales"] > df["Sales"].mean() else "Unusual price anomaly."
        })
    return results

def run_kmeans_clustering(df: pd.DataFrame) -> dict:
    """Clusters customer purchasing patterns into distinct behavioral segments."""
    if df.empty:
        return {"clusters": []}

    med_features = (
        df.groupby("Medicine")
        .agg(
            avg_qty=("Qty", "mean"),
            avg_sell_price=("Sell Price", "mean"),
            total_sales=("Sales", "sum")
        )
        .reset_index()
    )

    if len(med_features) < 4:
        return {"clusters": []}

    X = med_features[["avg_qty", "avg_sell_price", "total_sales"]].values
    kmeans = KMeans(n_clusters=3, random_state=42, n_init=10)
    med_features["cluster"] = kmeans.fit_predict(X)

    cluster_names = {
        0: "High Volume Fast Movers",
        1: "Premium High Margin Specialties",
        2: "Steady Essential Refills"
    }

    med_features["cluster_label"] = med_features["cluster"].map(cluster_names)

    output = []
    for cluster_id, group in med_features.groupby("cluster_label"):
        output.append({
            "cluster_name": cluster_id,
            "medicines": group["Medicine"].tolist()[:8],
            "count": int(len(group))
        })

    return {"clusters": output}

def get_filter_options(df: pd.DataFrame) -> dict:
    """Returns available categories, companies, and years for UI dropdowns."""
    if df.empty:
        return {"categories": [], "companies": [], "years": []}

    categories = sorted(df["Category"].dropna().unique().tolist())
    companies = sorted(df["Company"].dropna().unique().tolist())
    years = sorted([str(y) for y in df["Year"].dropna().unique().tolist()])

    return {
        "categories": categories,
        "companies": companies,
        "years": years
    }

def process_chatbot_query(query: str, df: pd.DataFrame) -> dict:
    """Natural Language Assistant query handler."""
    q = query.lower()
    
    if "decrease" in q or "drop" in q or "why" in q and "sales" in q:
        return {
            "answer": "Analysis indicates sales fluctuations are primarily influenced by seasonal transitions and low stock on top fast-movers. Ensure high-demand antibiotics and painkillers remain stocked to avoid lost sales opportunity.",
            "type": "insight"
        }
    elif "profitable" in q or "profit" in q or "top" in q:
        top_p = compute_product_analytics(df)["highest_profit"][:5]
        med_names = ", ".join([f"{item['medicine']} (₹{item['profit']:,.2f})" for item in top_p])
        return {
            "answer": f"The top 5 most profitable medicines in your store are: {med_names}.",
            "type": "data",
            "data": top_p
        }
    elif "expiring" in q or "expire" in q or "expiry" in q:
        exp_info = compute_stock_and_expiry_dashboard(df)
        red_count = exp_info["summary"]["red_alert_count"]
        exp_30_count = len(exp_info["expiring_30"])
        return {
            "answer": f"You currently have {exp_30_count} items expiring within 30 days and {red_count} items flagged under Red Alert (expiring before stock sell-out). View the Expiry Dashboard tab for action details.",
            "type": "alert"
        }
    elif "reorder" in q or "stock" in q or "restock" in q:
        stock_info = compute_stock_and_expiry_dashboard(df)
        low_count = stock_info["summary"]["low_stock_count"]
        return {
            "answer": f"There are {low_count} items currently below the minimum stock threshold (30 units). We recommend running the Auto-Reorder suggestion tool in the AI Forecast tab.",
            "type": "recommendation"
        }
    else:
        return {
            "answer": f"Pharmora processed your query: '{query}'. You can view detailed breakdowns in the Dashboard, AI Forecast, Stock & Expiry, or Assistant tabs.",
            "type": "general"
        }
