

CREATE DATABASE IF NOT EXISTS retail_supply_chain;
USE retail_supply_chain;

-- 1. DIMENSION TABLE: Products
CREATE TABLE dim_products (
    product_id VARCHAR(20) PRIMARY KEY,
    product_name VARCHAR(100) NOT NULL,
    category VARCHAR(50) NOT NULL,
    unit_cost DECIMAL(10, 2) NOT NULL,
    unit_price DECIMAL(10, 2) NOT NULL
);

-- 2. DIMENSION TABLE: Customers
CREATE TABLE dim_customers (
    customer_id VARCHAR(20) PRIMARY KEY,
    customer_name VARCHAR(100),
    region VARCHAR(50) NOT NULL,
    signup_date DATE
);

-- 3. FACT TABLE: Orders & Inventory Logs
CREATE TABLE fact_orders (
    order_id VARCHAR(25),
    product_id VARCHAR(20),
    customer_id VARCHAR(20),
    order_date DATE NOT NULL,
    order_quantity INT NOT NULL,
    shipped_quantity INT NOT NULL,
    warehouse_stock INT NOT NULL,
    revenue DECIMAL(12, 2) NOT NULL,
    PRIMARY KEY (order_id, product_id),
    FOREIGN KEY (product_id) REFERENCES dim_products(product_id),
    FOREIGN KEY (customer_id) REFERENCES dim_customers(customer_id)
);

-- 4. STAGING TABLE: External ERP Invoice Log (For Data Reconciliation)
CREATE TABLE erp_invoice_log (
    order_id VARCHAR(25),
    product_id VARCHAR(20),
    invoiced_amount DECIMAL(12, 2)
);

-- Create B-Tree Indexes for Query Optimization (Reduces execution latency)
CREATE INDEX idx_orders_date ON fact_orders(order_date);
CREATE INDEX idx_orders_product ON fact_orders(product_id);
CREATE INDEX idx_customers_region ON dim_customers(region);


SELECT 
    f.order_id,
    f.product_id,
    f.order_date,
    f.revenue AS recorded_revenue
FROM fact_orders f
LEFT JOIN erp_invoice_log e 
    ON f.order_id = e.order_id 
   AND f.product_id = e.product_id
WHERE e.order_id IS NULL;

-- QUERY 2: Month-over-Month (MoM) Revenue Growth using CTE & LAG() Window Function
WITH monthly_sales AS (
    SELECT 
        DATE_FORMAT(order_date, '%Y-%m-01') AS sales_month,
        SUM(revenue) AS total_revenue,
        COUNT(DISTINCT order_id) AS total_orders
    FROM fact_orders
    GROUP BY DATE_FORMAT(order_date, '%Y-%m-01')
)
SELECT 
    sales_month,
    total_revenue,
    LAG(total_revenue, 1) OVER (ORDER BY sales_month) AS prev_month_revenue,
    ROUND(
        ((total_revenue - LAG(total_revenue, 1) OVER (ORDER BY sales_month)) 
        / NULLIF(LAG(total_revenue, 1) OVER (ORDER BY sales_month), 0)) * 100, 2
    ) AS mom_growth_percentage
FROM monthly_sales
ORDER BY sales_month;

-- QUERY 3: Rank Top-Performing SKUs by Category Using RANK() Window Function
WITH sku_performance AS (
    SELECT 
        p.category,
        p.product_id,
        p.product_name,
        SUM(f.order_quantity) AS units_sold,
        SUM(f.revenue) AS total_revenue,
        SUM(f.revenue - (f.order_quantity * p.unit_cost)) AS gross_profit
    FROM fact_orders f
    INNER JOIN dim_products p ON f.product_id = p.product_id
    GROUP BY p.category, p.product_id, p.product_name
)
SELECT 
    category,
    product_id,
    product_name,
    units_sold,
    total_revenue,
    gross_profit,
    RANK() OVER (PARTITION BY category ORDER BY gross_profit DESC) AS category_profit_rank
FROM sku_performance
WHERE category_profit_rank <= 5;

-- QUERY 4: Stockout Risk & Fulfillment SLA Classification using CASE Statements
SELECT 
    p.category,
    p.product_id,
    p.product_name,
    AVG(f.warehouse_stock) AS avg_warehouse_stock,
    SUM(CASE WHEN f.warehouse_stock = 0 THEN 1 ELSE 0 END) AS stockout_incidents,
    CASE 
        WHEN SUM(CASE WHEN f.warehouse_stock = 0 THEN 1 ELSE 0 END) > 10 THEN 'Critical Stockout Risk'
        WHEN SUM(CASE WHEN f.warehouse_stock = 0 THEN 1 ELSE 0 END) BETWEEN 3 AND 10 THEN 'Moderate Risk'
        ELSE 'Healthy Inventory'
    END AS inventory_health_status
FROM fact_orders f
JOIN dim_products p ON f.product_id = p.product_id
GROUP BY p.category, p.product_id, p.product_name
ORDER BY stockout_incidents DESC;