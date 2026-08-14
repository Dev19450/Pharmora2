from flask import (
    Flask,
    render_template,
    request,
    send_file,
    jsonify
)

app = Flask(__name__)

import os
import pandas as pd
import numpy as np

import plotly
import plotly.express as px
import plotly.graph_objects as go

import json
from datetime import datetime

df = pd.read_csv("pharmacy_sales_dummy_1500.csv")


df["Sales"] = df["Quantity Sold"] * df["Selling Price"]

df["Profit"] = (
    df["Selling Price"] -
    df["Purchase Price"]
) * df["Quantity Sold"]


df["Date"] = pd.to_datetime(
    df["Date"],
    format="%d-%m-%Y"
)

df["Month"] = df["Date"].dt.to_period("M").astype(str)

monthly = (
    df.groupby("Month")["Sales"]
    .sum()
    .reset_index()
)

monthly_fig = px.line(
    monthly,
    x="Month",
    y="Sales",
    title="Monthly Sales Trend",
    markers=True
)

daily = (
    df.groupby("Date")["Sales"]
    .sum()
    .reset_index()
)

daily_fig = px.line(
    daily,
    x="Date",
    y="Sales",
    title="Daily Sales"
)

df["Week"] = df["Date"].dt.isocalendar().week

weekly = (
    df.groupby("Week")["Sales"]
    .sum()
    .reset_index()
)

weekly_fig = px.line(
    weekly,
    x="Week",
    y="Sales",
    title="Weekly Sales"
)

df["Year"] = df["Date"].dt.year

yearly = (
    df.groupby("Year")["Sales"]
    .sum()
    .reset_index()
)

yearly_fig = px.line(
    yearly,
    x="Year",
    y="Sales",
    title="Yearly Sales"
)

medicine = (
    df.groupby("Medicine Name")["Quantity Sold"]
    .sum()
    .sort_values(ascending=False)
    .head(10)
    .reset_index()
)

medicine_fig = px.bar(
    medicine,
    x="Medicine Name",
    y="Quantity Sold",
    title="Top Selling Medicines",
    color="Quantity Sold"
)

category = (
    df.groupby("Category")["Sales"]
    .sum()
    .reset_index()
)

category_fig = px.pie(
    category,
    names="Category",
    values="Sales",
    title="Category-wise Sales"
)

company = (
    df.groupby("Company")["Sales"]
    .sum()
    .sort_values(ascending=False)
    .head(10)
    .reset_index()
)

company_fig = px.bar(
    company,
    x="Company",
    y="Sales",
    title="Company-wise Sales",
    color="Sales"
)

low = df[df["Stock"] < 20]

low_stock_fig = px.bar(
    low,
    x="Stock",
    y="Medicine Name",
    orientation="h",
    title="Low Stock Medicines",
    color="Stock"
)

stock = (
    df.groupby("Category")["Stock"]
    .sum()
    .reset_index()
)

stock_fig = px.pie(
    stock,
    names="Category",
    values="Stock",
    title="Stock Distribution"
)

monthly_chart = monthly_fig.to_html(full_html=False, include_plotlyjs='cdn')

daily_chart = daily_fig.to_html(full_html=False, include_plotlyjs=False)

weekly_chart = weekly_fig.to_html(full_html=False, include_plotlyjs=False)

yearly_chart = yearly_fig.to_html(full_html=False, include_plotlyjs=False)

medicine_chart = medicine_fig.to_html(full_html=False, include_plotlyjs=False)

category_chart = category_fig.to_html(full_html=False, include_plotlyjs=False)

company_chart = company_fig.to_html(full_html=False, include_plotlyjs=False)

low_stock_chart = low_stock_fig.to_html(full_html=False, include_plotlyjs=False)

stock_chart = stock_fig.to_html(full_html=False, include_plotlyjs=False)

@app.route("/")
def dashboard():
    return render_template(
        "dashboard.html",

        monthly_chart=monthly_chart,
        daily_chart=daily_chart,
        weekly_chart=weekly_chart,
        yearly_chart=yearly_chart,

        medicine_chart=medicine_chart,
        category_chart=category_chart,
        company_chart=company_chart,

        low_stock_chart=low_stock_chart,
        stock_chart=stock_chart
    )


if __name__ == "__main__":
    app.run(debug=True)