import pandas as pd
import matplotlib.pyplot as plt


df = pd.read_csv("pharmacy_sales_dummy_1500.csv")

df["Sales"] = df["Quantity Sold"] * df["Selling Price"]

category = df.groupby("Category")["Sales"].sum()

plt.figure(figsize=(7,7))
plt.pie(
    category,
    labels=category.index,
    autopct="%1.1f%%",
    startangle=90
)

plt.title("Category Wise Sales")
plt.axis("equal")
plt.show()