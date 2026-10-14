import sqlite3
import time
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

def run_enterprise_etl(num_orders=500000):
    start_time = time.time()
    np.random.seed(42)
    print(f"==================================================================")
    print(f"STARTING MEDALLION ETL PIPELINE (Target Scale: {num_orders:,} Orders)")
    print(f"==================================================================")

    # -------------------------------------------------------------------------
    # 1. BRONZE LAYER: Generate Relational Multi-Table Datasets
    # -------------------------------------------------------------------------
    categories = ['Electronics', 'Apparel', 'Home & Kitchen', 'FMCG', 'Automotive']
    cat_weights = [0.28, 0.22, 0.20, 0.18, 0.12]
    regions = ['North', 'West', 'South', 'East']
    reg_weights = [0.32, 0.28, 0.24, 0.16]
    channels = ['Organic Search', 'Paid Ads', 'B2B Direct', 'Referral', 'Marketplace']

    # A. dim_products (500 SKUs)
    num_skus = 500
    sku_cats = np.random.choice(categories, size=num_skus, p=cat_weights)
    base_prices = {'Electronics': 320, 'Automotive': 210, 'Home & Kitchen': 140, 'Apparel': 65, 'FMCG': 28}
    unit_prices = np.array([np.round(np.random.uniform(base_prices[c]*0.6, base_prices[c]*1.6), 2) for c in sku_cats])
    margin_factors = np.random.uniform(0.55, 0.78, size=num_skus)
    unit_costs = np.round(unit_prices * margin_factors, 2)

    dim_products = pd.DataFrame({
        'product_id': [f'SKU-{1000 + i}' for i in range(num_skus)],
        'product_name': [f'{sku_cats[i]} Pro Item {1000 + i}' for i in range(num_skus)],
        'category': sku_cats,
        'unit_cost': unit_costs,
        'unit_price': unit_prices,
        'target_lead_time_days': np.random.choice([3, 5, 7], size=num_skus, p=[0.4, 0.4, 0.2])
    })

    # B. dim_customers (25,000 Customers)
    num_customers = 25000
    dim_customers = pd.DataFrame({
        'customer_id': [f'CUST-{10000 + i}' for i in range(num_customers)],
        'region': np.random.choice(regions, size=num_customers, p=reg_weights),
        'acquisition_channel': np.random.choice(channels, size=num_customers),
        'signup_date': (pd.to_datetime('2024-01-01') + pd.to_timedelta(np.random.randint(0, 365, size=num_customers), unit='D')).strftime('%Y-%m-%d')
    })

    # C. fact_orders (500,000 Transactional Records with Q4 Festive Demand Surge)
    month_probs = np.array([0.065, 0.065, 0.075, 0.075, 0.08, 0.08, 0.08, 0.085, 0.09, 0.105, 0.105, 0.095])
    month_probs = month_probs / month_probs.sum()
    months = np.random.choice(range(1, 13), size=num_orders, p=month_probs)
    days = np.random.randint(1, 29, size=num_orders)
    order_dates = pd.to_datetime({'year': 2025, 'month': months, 'day': days}).dt.strftime('%Y-%m-%d')

    sku_indices = np.random.randint(0, num_skus, size=num_orders)
    cust_indices = np.random.randint(0, num_customers, size=num_orders)
    quantities = np.random.randint(1, 15, size=num_orders)

    selected_prices = unit_prices[sku_indices]
    selected_costs = unit_costs[sku_indices]
    revenues = np.round(quantities * selected_prices, 2)
    cogs = np.round(quantities * selected_costs, 2)
    profits = np.round(revenues - cogs, 2)

    # Simulate realistic ~4.5% stockout rate & lead-time distribution
    warehouse_stock = np.where(np.random.rand(num_orders) < 0.045, 0, np.random.randint(5, 250, size=num_orders))
    actual_lead_time = np.random.randint(1, 11, size=num_orders)

    fact_orders = pd.DataFrame({
        'order_id': [f'ORD-{1000000 + i}' for i in range(num_orders)],
        'product_id': dim_products['product_id'].values[sku_indices],
        'customer_id': dim_customers['customer_id'].values[cust_indices],
        'order_date': order_dates,
        'order_quantity': quantities,
        'warehouse_stock': warehouse_stock,
        'actual_lead_time_days': actual_lead_time,
        'revenue': revenues,
        'cogs': cogs,
        'gross_profit': profits
    })

    # -------------------------------------------------------------------------
    # 2. SILVER LAYER: Data Cleaning & Memory Optimization
    # -------------------------------------------------------------------------
    raw_mem = fact_orders.memory_usage(deep=True).sum() / (1024 ** 2)
    fact_orders.drop_duplicates(subset=['order_id', 'product_id'], inplace=True)

    # Downcast numeric types for memory optimization
    for col in ['order_quantity', 'warehouse_stock', 'actual_lead_time_days']:
        fact_orders[col] = pd.to_numeric(fact_orders[col], downcast='integer')
    for col in ['revenue', 'cogs', 'gross_profit']:
        fact_orders[col] = pd.to_numeric(fact_orders[col], downcast='float')

    opt_mem = fact_orders.memory_usage(deep=True).sum() / (1024 ** 2)
    mem_saved_pct = (1 - opt_mem / raw_mem) * 100
    print(f"[SILVER LAYER] Cleaned {len(fact_orders):,} rows | RAM reduced from {raw_mem:.2f} MB -> {opt_mem:.2f} MB ({mem_saved_pct:.1f}% saved)")

    # D. erp_invoice_log (Simulate 98.2% billed, 1.8% unbilled revenue leakage)
    billed_mask = np.random.rand(len(fact_orders)) >= 0.018
    erp_invoice_log = pd.DataFrame({
        'order_id': fact_orders.loc[billed_mask, 'order_id'].values,
        'product_id': fact_orders.loc[billed_mask, 'product_id'].values,
        'invoiced_amount': fact_orders.loc[billed_mask, 'revenue'].values,
        'invoice_status': 'Billed'
    })

    # -------------------------------------------------------------------------
    # 3. WAREHOUSE LAYER: Load into Star Schema SQLite DB & Build B-Tree Indexes
    # -------------------------------------------------------------------------
    conn = sqlite3.connect('supply_chain_warehouse.db')
    cursor = conn.cursor()

    dim_products.to_sql('dim_products', conn, if_exists='replace', index=False)
    dim_customers.to_sql('dim_customers', conn, if_exists='replace', index=False)
    fact_orders.to_sql('fact_orders', conn, if_exists='replace', index=False)
    erp_invoice_log.to_sql('erp_invoice_log', conn, if_exists='replace', index=False)

    # Create B-Tree indexes for sub-second SQL execution
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_orders_date ON fact_orders(order_date);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_orders_product ON fact_orders(product_id);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_orders_customer ON fact_orders(customer_id);")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_erp_order_prod ON erp_invoice_log(order_id, product_id);")
    conn.commit()
    print("[WAREHOUSE LAYER] Loaded Star Schema tables & built B-Tree indexes in supply_chain_warehouse.db")

    # -------------------------------------------------------------------------
    # 4. GOLD LAYER: Execute Production SQL Queries & Export KPI Marts
    # -------------------------------------------------------------------------
    with open('schema_and_analytics.sql', 'r', encoding='utf-8') as f:
        sql_script = f.read()

    queries = [q.strip() for q in sql_script.split('-- QUERY ') if q.strip()]
    
    q1_erp_leakage = "SELECT" + queries[1].split("SELECT", 1)[1]
    q2_monthly_kpis = "WITH" + queries[2].split("WITH", 1)[1]
    q3_top_skus = "WITH" + queries[3].split("WITH", 1)[1]
    q4_rfm_segments = "WITH" + queries[4].split("WITH", 1)[1]
    q5_regional_sla = "SELECT" + queries[5].split("SELECT", 1)[1]

    df_leakage = pd.read_sql_query(q1_erp_leakage, conn)
    df_monthly = pd.read_sql_query(q2_monthly_kpis, conn)
    df_top_skus = pd.read_sql_query(q3_top_skus, conn)
    df_rfm = pd.read_sql_query(q4_rfm_segments, conn)
    df_sla = pd.read_sql_query(q5_regional_sla, conn)

    df_leakage.to_csv('gold_erp_leakage.csv', index=False)
    df_monthly.to_csv('gold_monthly_kpis.csv', index=False)
    df_top_skus.to_csv('gold_sku_rankings.csv', index=False)
    df_rfm.to_csv('gold_rfm_segments.csv', index=False)
    df_sla.to_csv('gold_regional_sla.csv', index=False)
    conn.close()
    print("[GOLD LAYER] Exported 5 SQL Analytical Marts (CSV) for BI Consumption")

    # -------------------------------------------------------------------------
    # 5. VISUALIZATION: Generate 4-Panel Executive KPI Dashboard Preview
    # -------------------------------------------------------------------------
    fig, axes = plt.subplots(2, 2, figsize=(15, 9))
    fig.suptitle(f'Enterprise Retail Supply Chain & Revenue SQL Analytics ({num_orders:,} Orders)', fontsize=15, fontweight='bold')

    # Chart 1: Monthly Revenue & Profit Trend
    axes[0, 0].plot(df_monthly['year_month'], df_monthly['total_revenue'] / 1e6, marker='o', linewidth=2.5, color='#1f77b4', label='Revenue ()')
    axes[0, 0].plot(df_monthly['year_month'], df_monthly['total_profit'] / 1e6, marker='s', linewidth=2, color='#2ca02c', label='Gross Profit ()')
    axes[0, 0].set_title('Monthly Revenue & Gross Profit Trend ($ Millions)', fontweight='bold')
    axes[0, 0].tick_params(axis='x', rotation=45)
    axes[0, 0].legend()
    axes[0, 0].grid(True, linestyle='--', alpha=0.5)

    # Chart 2: Customer RFM Segmentation Revenue
    axes[0, 1].barh(df_rfm['customer_segment'], df_rfm['segment_total_revenue'] / 1e6, color=['#2b5c8f', '#388e3c', '#f57c00', '#d32f2f'])
    axes[0, 1].set_title('Revenue Contribution by Customer RFM Segment ($ Millions)', fontweight='bold')
    axes[0, 1].grid(True, axis='x', linestyle='--', alpha=0.5)

    # Chart 3: Unbilled ERP Revenue Leakage by Category
    leak_cat = df_leakage.groupby('category')['leaked_revenue_usd'].sum().sort_values(ascending=True) / 1e3
    axes[1, 0].barh(leak_cat.index, leak_cat.values, color='#c62828')
    axes[1, 0].set_title('Unbilled ERP Revenue Leakage Identified via SQL LEFT JOIN ($ Thousands)', fontweight='bold')
    axes[1, 0].grid(True, axis='x', linestyle='--', alpha=0.5)

    # Chart 4: Regional SLA Breach Rate vs Stockout Rate
    reg_summary = df_sla.groupby('region')[['sla_breach_rate_pct', 'stockout_rate_pct']].mean()
    x = np.arange(len(reg_summary.index))
    axes[1, 1].bar(x - 0.18, reg_summary['sla_breach_rate_pct'], width=0.35, label='SLA Breach %', color='#ff9800')
    axes[1, 1].bar(x + 0.18, reg_summary['stockout_rate_pct'], width=0.35, label='Stockout Rate %', color='#6a1b9a')
    axes[1, 1].set_xticks(x)
    axes[1, 1].set_xticklabels(reg_summary.index)
    axes[1, 1].set_title('Regional Supply Chain SLA Breach % vs Stockout Rate %', fontweight='bold')
    axes[1, 1].legend()
    axes[1, 1].grid(True, axis='y', linestyle='--', alpha=0.5)

    plt.tight_layout()
    plt.savefig('dashboard_preview.png', dpi=160)
    print(f"[COMPLETED] Pipeline finished in {time.time() - start_time:.2f}s! Generated dashboard_preview.png")

if __name__ == '__main__':
    run_enterprise_etl(500000)
