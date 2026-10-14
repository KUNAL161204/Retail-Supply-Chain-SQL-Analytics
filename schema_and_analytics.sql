-- ============================================================================
-- ENTERPRISE RETAIL SUPPLY CHAIN & REVENUE ANALYTICS (STAR SCHEMA & SQL MARTS)
-- Compatible with: MySQL 8.0+ / PostgreSQL / SQLite 3.35+
-- Scale: 500,000+ Fact Order Records | 25,000 Customers | 500 SKUs
-- ============================================================================

-- 1. DIMENSION TABLE: Products (500 SKUs)
CREATE TABLE IF NOT EXISTS dim_products (
    product_id VARCHAR(20) PRIMARY KEY,
    product_name VARCHAR(100) NOT NULL,
    category VARCHAR(50) NOT NULL,
    unit_cost DECIMAL(10, 2) NOT NULL,
    unit_price DECIMAL(10, 2) NOT NULL,
    target_lead_time_days INT NOT NULL
);

-- 2. DIMENSION TABLE: Customers (25,000 Customers)
CREATE TABLE IF NOT EXISTS dim_customers (
    customer_id VARCHAR(20) PRIMARY KEY,
    region VARCHAR(50) NOT NULL,
    acquisition_channel VARCHAR(50) NOT NULL,
    signup_date DATE NOT NULL
);

-- 3. FACT TABLE: Orders & Supply Chain Logs (500,000+ Rows)
CREATE TABLE IF NOT EXISTS fact_orders (
    order_id VARCHAR(25),
    product_id VARCHAR(20),
    customer_id VARCHAR(20),
    order_date DATE NOT NULL,
    order_quantity INT NOT NULL,
    warehouse_stock INT NOT NULL,
    actual_lead_time_days INT NOT NULL,
    revenue DECIMAL(12, 2) NOT NULL,
    cogs DECIMAL(12, 2) NOT NULL,
    gross_profit DECIMAL(12, 2) NOT NULL,
    PRIMARY KEY (order_id, product_id),
    FOREIGN KEY (product_id) REFERENCES dim_products(product_id),
    FOREIGN KEY (customer_id) REFERENCES dim_customers(customer_id)
);

-- 4. STAGING TABLE: ERP Finance Invoice Log (For Revenue Leakage Reconciliation)
CREATE TABLE IF NOT EXISTS erp_invoice_log (
    order_id VARCHAR(25),
    product_id VARCHAR(20),
    invoiced_amount DECIMAL(12, 2),
    invoice_status VARCHAR(30),
    PRIMARY KEY (order_id, product_id)
);

-- ============================================================================
-- B-TREE INDEXING FOR HIGH-SPEED ANALYTICAL QUERIES
-- ============================================================================
CREATE INDEX IF NOT EXISTS idx_orders_date ON fact_orders(order_date);
CREATE INDEX IF NOT EXISTS idx_orders_product ON fact_orders(product_id);
CREATE INDEX IF NOT EXISTS idx_orders_customer ON fact_orders(customer_id);
CREATE INDEX IF NOT EXISTS idx_customers_region ON dim_customers(region);

-- ============================================================================
-- GOLD LAYER ANALYTICAL SQL QUERIES
-- ============================================================================

-- QUERY 1: ERP Revenue Leakage Audit (LEFT JOIN Anti-Join)
-- Identifies shipped orders in fact_orders missing from ERP finance invoices
SELECT 
    p.category,
    c.region,
    COUNT(f.order_id) AS unbilled_order_count,
    ROUND(SUM(f.revenue), 2) AS leaked_revenue_usd,
    ROUND(AVG(f.revenue), 2) AS avg_unbilled_order_value
FROM fact_orders f
INNER JOIN dim_products p ON f.product_id = p.product_id
INNER JOIN dim_customers c ON f.customer_id = c.customer_id
LEFT JOIN erp_invoice_log e 
    ON f.order_id = e.order_id 
   AND f.product_id = e.product_id
WHERE e.order_id IS NULL
GROUP BY p.category, c.region
ORDER BY leaked_revenue_usd DESC;

-- QUERY 2: Month-over-Month (MoM) Revenue Growth & Margin (CTE + LAG Window Function)
WITH monthly_kpis AS (
    SELECT 
        SUBSTR(order_date, 1, 7) AS year_month,
        COUNT(DISTINCT order_id) AS total_orders,
        ROUND(SUM(revenue), 2) AS total_revenue,
        ROUND(SUM(gross_profit), 2) AS total_profit,
        ROUND((SUM(gross_profit) / NULLIF(SUM(revenue), 0)) * 100, 2) AS gross_margin_pct,
        SUM(CASE WHEN warehouse_stock = 0 THEN 1 ELSE 0 END) AS stockout_events
    FROM fact_orders
    GROUP BY SUBSTR(order_date, 1, 7)
)
SELECT 
    year_month,
    total_orders,
    total_revenue,
    total_profit,
    gross_margin_pct,
    stockout_events,
    LAG(total_revenue, 1) OVER (ORDER BY year_month) AS prev_month_revenue,
    ROUND(
        ((total_revenue - LAG(total_revenue, 1) OVER (ORDER BY year_month)) 
        / NULLIF(LAG(total_revenue, 1) OVER (ORDER BY year_month), 0)) * 100, 2
    ) AS mom_revenue_growth_pct
FROM monthly_kpis
ORDER BY year_month;

-- QUERY 3: Top 5 Profit-Generating SKUs per Category (CTE + RANK Window Function)
WITH sku_summary AS (
    SELECT 
        p.category,
        p.product_id,
        p.product_name,
        SUM(f.order_quantity) AS total_units_sold,
        ROUND(SUM(f.revenue), 2) AS total_revenue,
        ROUND(SUM(f.gross_profit), 2) AS total_profit,
        SUM(CASE WHEN f.warehouse_stock = 0 THEN 1 ELSE 0 END) AS stockout_count
    FROM fact_orders f
    INNER JOIN dim_products p ON f.product_id = p.product_id
    GROUP BY p.category, p.product_id, p.product_name
),
ranked_skus AS (
    SELECT 
        *,
        RANK() OVER (PARTITION BY category ORDER BY total_profit DESC) AS profit_rank_in_category
    FROM sku_summary
)
SELECT * FROM ranked_skus
WHERE profit_rank_in_category <= 5
ORDER BY category, profit_rank_in_category;

-- QUERY 4: Customer RFM Segmentation (CTE + NTILE(4) Window Function)
WITH customer_rfm_raw AS (
    SELECT 
        c.customer_id,
        c.region,
        CAST(JULIANDAY('2026-01-01') - JULIANDAY(MAX(f.order_date)) AS INT) AS recency_days,
        COUNT(DISTINCT f.order_id) AS frequency_orders,
        ROUND(SUM(f.revenue), 2) AS monetary_spend
    FROM dim_customers c
    INNER JOIN fact_orders f ON c.customer_id = f.customer_id
    GROUP BY c.customer_id, c.region
),
rfm_scores AS (
    SELECT 
        *,
        NTILE(4) OVER (ORDER BY recency_days DESC) AS r_score,
        NTILE(4) OVER (ORDER BY frequency_orders ASC) AS f_score,
        NTILE(4) OVER (ORDER BY monetary_spend ASC) AS m_score
    FROM customer_rfm_raw
)
SELECT 
    CASE 
        WHEN (r_score + f_score + m_score) >= 10 THEN 'Champions'
        WHEN (r_score + f_score + m_score) BETWEEN 7 AND 9 THEN 'Loyal Customers'
        WHEN (r_score + f_score + m_score) BETWEEN 5 AND 6 THEN 'Potential Loyalists'
        ELSE 'At-Risk / Churned'
    END AS customer_segment,
    COUNT(customer_id) AS customer_count,
    ROUND(AVG(recency_days), 1) AS avg_recency_days,
    ROUND(AVG(frequency_orders), 1) AS avg_orders,
    ROUND(AVG(monetary_spend), 2) AS avg_ltv_usd,
    ROUND(SUM(monetary_spend), 2) AS segment_total_revenue
FROM rfm_scores
GROUP BY customer_segment
ORDER BY segment_total_revenue DESC;

-- QUERY 5: Regional Supply Chain SLA & Stockout Health Matrix
SELECT 
    c.region,
    p.category,
    COUNT(f.order_id) AS total_orders,
    ROUND(AVG(f.actual_lead_time_days), 2) AS avg_lead_time_days,
    ROUND(
        SUM(CASE WHEN f.actual_lead_time_days > p.target_lead_time_days THEN 1.0 ELSE 0.0 END) 
        * 100.0 / COUNT(f.order_id), 2
    ) AS sla_breach_rate_pct,
    ROUND(
        SUM(CASE WHEN f.warehouse_stock = 0 THEN 1.0 ELSE 0.0 END) 
        * 100.0 / COUNT(f.order_id), 2
    ) AS stockout_rate_pct,
    ROUND(SUM(f.revenue), 2) AS total_revenue
FROM fact_orders f
INNER JOIN dim_products p ON f.product_id = p.product_id
INNER JOIN dim_customers c ON f.customer_id = c.customer_id
GROUP BY c.region, p.category
ORDER BY c.region, total_revenue DESC;
