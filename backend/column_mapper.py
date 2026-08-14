import pandas as pd
import numpy as np

# Comprehensive column mapping dictionary combining cs.py and real-world pharmacy ERP exports
COLUMN_MAPPING = {
    "Date": [
        "date", "bill date", "invoice date", "sale date", "sales date",
        "billing date", "transaction date", "order date", "created date", "purchase date"
    ],
    "Medicine": [
        "medicine", "medicine name", "product", "product name", "drug",
        "drug name", "item", "item name", "medicine description", "description",
        "product description", "generic name", "brand name", "sku name"
    ],
    "Category": [
        "category", "medicine category", "product category", "drug category",
        "group", "item category", "department", "classification", "type"
    ],
    "Company": [
        "company", "manufacturer", "manufactured by", "brand", "brand name",
        "company name", "mfg company", "pharma company", "supplier company"
    ],
    "Batch": [
        "batch", "batch no", "batch number", "batch id", "lot", "lot no",
        "lot number", "lot id", "production batch"
    ],
    "Qty": [
        "qty", "quantity", "quantity sold", "units sold", "sale quantity", "sales qty",
        "purchase qty", "units", "unit", "pieces", "nos", "no of units",
        "pack qty", "item qty"
    ],
    "Sell Price": [
        "selling price", "sale price", "sales price", "mrp", "retail price",
        "selling rate", "rate", "unit price", "price", "amount", "retail rate",
        "selling amount"
    ],
    "Buy Price": [
        "purchase price", "buying price", "buy price", "cost price", "purchase rate",
        "buying rate", "cost", "cost rate", "wholesale price", "landing cost",
        "purchase amount"
    ],
    "Stock": [
        "stock", "current stock", "available stock", "stock qty", "inventory",
        "inventory qty", "balance stock", "closing stock", "opening stock",
        "in stock", "available quantity"
    ],
    "Expiry": [
        "expiry", "expiry date", "expire date", "expiration date", "expiration",
        "exp date", "exp", "use before", "best before", "expiry dt"
    ],
    "Supplier": [
        "supplier", "supplier name", "vendor", "vendor name", "distributor",
        "dealer", "wholesaler", "supplier company", "purchased from"
    ],
    "Invoice No": [
        "invoice no", "invoice number", "invoice", "bill no", "bill number",
        "bill", "receipt no", "receipt number", "order no", "order number", "transaction no"
    ],
    "GST": [
        "gst", "gst %", "gst rate", "tax", "tax %", "cgst", "sgst", "igst", "vat"
    ],
    "HSN": [
        "hsn", "hsn code", "hsn number", "sac", "product code", "item code"
    ],
    "Discount": [
        "discount", "discount %", "discount amount", "disc", "offer", "offer amount", "rebate"
    ],
    "Total": [
        "total", "total amount", "net amount", "grand total", "final amount", "amount", "value", "bill amount"
    ]
}

def clean_and_map_dataframe(df_raw: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    """
    Standardizes raw sales dataframe columns, cleans types, fills missing values,
    and computes derived fields like Sales, Profit, Profit Margin.
    """
    df = df_raw.copy()
    
    # Normalize original column names for matching
    df.columns = (
        df.columns
        .astype(str)
        .str.strip()
        .str.lower()
        .str.replace("_", " ", regex=False)
        .str.replace("-", " ", regex=False)
    )
    
    mapped_df = pd.DataFrame()
    matched_info = {}
    
    # Perform column mapping
    for target_col, aliases in COLUMN_MAPPING.items():
        found = False
        for alias in aliases:
            if alias in df.columns:
                mapped_df[target_col] = df[alias]
                matched_info[target_col] = {"status": "MATCHED", "original": alias}
                found = True
                break
        if not found:
            matched_info[target_col] = {"status": "NOT_FOUND", "original": None}
            if target_col in ["Qty", "Sell Price", "Buy Price", "Stock", "GST", "Discount"]:
                mapped_df[target_col] = 0
            elif target_col == "Medicine":
                mapped_df[target_col] = "Unknown Medicine"
            elif target_col == "Category":
                mapped_df[target_col] = "General"
            elif target_col == "Company":
                mapped_df[target_col] = "Generic Pharma"
            else:
                mapped_df[target_col] = ""

    # Clean data types
    # Date parsing with multiple format fallbacks
    mapped_df["Date"] = pd.to_datetime(mapped_df["Date"], errors="coerce", dayfirst=True)
    mapped_df["Date"] = mapped_df["Date"].fillna(pd.to_datetime("today"))
    
    # Expiry parsing
    mapped_df["Expiry"] = pd.to_datetime(mapped_df["Expiry"], errors="coerce", dayfirst=True)
    
    # Numeric conversions
    for col in ["Qty", "Sell Price", "Buy Price", "Stock", "GST", "Discount"]:
        mapped_df[col] = pd.to_numeric(mapped_df[col], errors="coerce").fillna(0)
    
    # Fill text nulls
    mapped_df["Medicine"] = mapped_df["Medicine"].astype(str).fillna("Unknown Medicine")
    mapped_df["Category"] = mapped_df["Category"].astype(str).fillna("General")
    mapped_df["Company"] = mapped_df["Company"].astype(str).fillna("Generic Pharma")
    mapped_df["Batch"] = mapped_df["Batch"].astype(str).fillna("B0000")
    mapped_df["Supplier"] = mapped_df["Supplier"].astype(str).fillna("Direct Supplier")

    # Compute derived analytical fields
    mapped_df["Sales"] = mapped_df["Qty"] * mapped_df["Sell Price"]
    mapped_df["Cost"] = mapped_df["Qty"] * mapped_df["Buy Price"]
    mapped_df["Profit"] = mapped_df["Sales"] - mapped_df["Cost"]
    
    # Margin %
    mapped_df["Margin_Pct"] = np.where(
        mapped_df["Sales"] > 0,
        (mapped_df["Profit"] / mapped_df["Sales"]) * 100,
        0
    )
    
    # Date helper columns
    mapped_df["Year"] = mapped_df["Date"].dt.year
    mapped_df["Month"] = mapped_df["Date"].dt.to_period("M").astype(str)
    mapped_df["Week"] = mapped_df["Date"].dt.isocalendar().week.astype(int)
    mapped_df["DayName"] = mapped_df["Date"].dt.day_name()
    mapped_df["DateStr"] = mapped_df["Date"].dt.strftime("%Y-%m-%d")

    return mapped_df, matched_info
