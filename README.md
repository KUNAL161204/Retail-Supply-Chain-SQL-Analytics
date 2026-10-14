# Enterprise Retail Supply Chain & Revenue SQL Analytics
**Scale:** 500,000+ Transactional Orders | 25,000 Customers | 500 SKUs | Star Schema Data Warehouse

An end-to-end **Data Analytics & Data Engineering** project built on a **Medallion Architecture (Bronze -> Silver -> Gold)**. It processes **500,000+ retail supply chain orders**, optimizes memory usage by **~60%** in Python, structures a relational **Star Schema** with **B-Tree Indexing**, reconciles unbilled ERP revenue leakage using SQL anti-joins, segments customers via **RFM Window Functions**, and serves insights through an interactive **Streamlit & Plotly BI Web Application**.

---

## Executive KPI Dashboard Preview
![Executive KPI Dashboard](dashboard_preview.png)

---

## System Architecture & Data Pipeline

1. **Bronze Layer (Multi-Source Ingestion — `etl_and_eda.py`)**
   - Ingests **500,000 transactional order records** (`fact_orders`), **491,000 finance invoice logs** (`erp_invoice_log`), **25,000 customer profiles** (`dim_customers`), and **500 product SKUs** (`dim_products`).
2. **Silver Layer (Cleaning, Deduplication & Memory Downcasting)**
   - Enforces composite primary key integrity `(order_id, product_id)` and downcasts 64-bit numeric columns (`int64` -> `int8/int16`, `float64` -> `float32`), cutting in-memory footprint by **~60%**.
   - Loads relational tables into a **Star Schema SQL Warehouse** and builds **B-Tree Indexes** (`idx_orders_date`, `idx_orders_product`, `idx_orders_customer`) for sub-second analytical aggregations.
3. **Gold Layer (Production SQL Analytics — `schema_and_analytics.sql`)**
   - **Query 1 — ERP Revenue Leakage Audit (`LEFT JOIN ... WHERE e.order_id IS NULL`)**: Reconciles shipped warehouse orders against finance ERP invoices, uncovering **~9,000 unbilled orders** across categories and regions.
   - **Query 2 — Time-Series Revenue & Margin Growth (`CTE` + `LAG()`)**: Computes monthly revenue, gross profit margin %, stockout counts, and Month-over-Month (MoM) growth rates.
   - **Query 3 — Category SKU Profitability Ranking (`CTE` + `RANK() OVER (PARTITION BY category ...)`)**: Identifies the top 5 profit-generating SKUs per product line.
   - **Query 4 — Customer RFM Segmentation (`CTE` + `NTILE(4)`)**: Scores 25,000 customers on Recency, Frequency, and Monetary value to classify cohorts into *Champions, Loyal Customers, Potential Loyalists, and At-Risk*.
   - **Query 5 — Supply Chain SLA & Stockout Matrix (`CASE WHEN`)**: Tracks vendor lead-time SLA breach rates and warehouse stockout incidents (`warehouse_stock = 0`) across regions.
4. **Interactive BI Web App & Live SQL Workbench (`app.py`)**
   - Built with **Streamlit & Plotly**, featuring dynamic Region/Category filters, downloadable ERP audit CSVs, and an interactive **Live SQL Query Workbench**.

---

## How to Run Locally
```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Run the 500,000-row ETL & SQL Pipeline
python etl_and_eda.py

# 3. Launch the Interactive BI Dashboard & Live SQL Workbench
streamlit run app.py
