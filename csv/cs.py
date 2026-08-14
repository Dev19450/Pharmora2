import pandas as pd


input_file = "pharmacy_sales_dummy_1500.csv"

df = pd.read_csv(input_file)

df.columns = (
    df.columns
      .str.strip()
      .str.lower()
      .str.replace("_", " ", regex=False)
      .str.replace("-", " ", regex=False)
)

# Your required output columns and possible input names
mapping = {

    "Date": [
        "date",
        "bill date",
        "invoice date",
        "sale date",
        "sales date",
        "billing date",
        "transaction date",
        "order date",
        "created date",
        "purchase date"
    ],

    "Medicine": [
        "medicine",
        "medicine name",
        "product",
        "product name",
        "drug",
        "drug name",
        "item",
        "item name",
        "medicine description",
        "description",
        "product description",
        "generic name",
        "brand name",
        "sku name"
    ],

    "Category": [
        "category",
        "medicine category",
        "product category",
        "drug category",
        "group",
        "item category",
        "department",
        "classification",
        "type"
    ],

    "Company": [
        "company",
        "manufacturer",
        "manufactured by",
        "brand",
        "brand name",
        "company name",
        "mfg company",
        "pharma company",
        "supplier company"
    ],

    "Batch No": [
        "batch",
        "batch no",
        "batch number",
        "batch id",
        "lot",
        "lot no",
        "lot number",
        "lot id",
        "production batch"
    ],

    "Qty": [
        "qty",
        "quantity",
        "quantity sold",
        "sale quantity",
        "sales qty",
        "purchase qty",
        "units",
        "unit",
        "pieces",
        "nos",
        "no of units",
        "pack qty",
        "item qty"
    ],

    "Sell Price": [
        "selling price",
        "sale price",
        "sales price",
        "mrp",
        "retail price",
        "selling rate",
        "rate",
        "unit price",
        "price",
        "amount",
        "retail rate",
        "selling amount"
    ],

    "Buy Price": [
        "purchase price",
        "buying price",
        "buy price",
        "cost price",
        "purchase rate",
        "buying rate",
        "cost",
        "cost rate",
        "wholesale price",
        "landing cost",
        "purchase amount"
    ],

    "Stock": [
        "stock",
        "current stock",
        "available stock",
        "stock qty",
        "inventory",
        "inventory qty",
        "balance stock",
        "closing stock",
        "opening stock",
        "in stock",
        "available quantity"
    ],

    "Expiry": [
        "expiry",
        "expiry date",
        "expire date",
        "expiration date",
        "expiration",
        "exp date",
        "exp",
        "use before",
        "best before",
        "expiry dt"
    ],

    "Supplier": [
        "supplier",
        "supplier name",
        "vendor",
        "vendor name",
        "distributor",
        "dealer",
        "wholesaler",
        "supplier company",
        "purchased from"
    ],

    "Invoice No": [
        "invoice no",
        "invoice number",
        "invoice",
        "bill no",
        "bill number",
        "bill",
        "receipt no",
        "receipt number",
        "order no",
        "order number",
        "transaction no"
    ],

    "GST": [
        "gst",
        "gst %",
        "gst rate",
        "tax",
        "tax %",
        "cgst",
        "sgst",
        "igst",
        "vat"
    ],

    "HSN": [
        "hsn",
        "hsn code",
        "hsn number",
        "sac",
        "product code",
        "item code"
    ],

    "Discount": [
        "discount",
        "discount %",
        "discount amount",
        "disc",
        "offer",
        "offer amount",
        "rebate"
    ],

    "Total": [
        "total",
        "total amount",
        "net amount",
        "grand total",
        "final amount",
        "amount",
        "value",
        "bill amount"
    ]
}

# Create empty dataframe
output_df = pd.DataFrame()

# Copy matched columns
for new_col, possible_names in mapping.items():

    found = False

    for col in possible_names:

        if col in df.columns:
            output_df[new_col] = df[col]
            found = True
            print(f"Matched: {col} -> {new_col}")
            break

    if not found:
        output_df[new_col] = ""
        print(f"Not Found: {new_col}")

# Save new CSV
output_df.to_csv("mapped_output.csv", index=False)

print("New CSV Generated Successfully!")