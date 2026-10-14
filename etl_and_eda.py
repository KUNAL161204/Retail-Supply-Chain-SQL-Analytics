import pandas as pd
import numpy as np
import matplotlib.pyplot as plt

np.random.seed(42)
num_rows = 100000
categories = ['Electronics', 'Apparel', 'Home & Kitchen', 'FMCG', 'Automotive']
regions = ['North', 'South', 'East', 'West']

df = pd.DataFrame({
    'order_id': [f'ORD-{100000 + i}' for i in range(num_rows)],
    'product_id': [f'SKU-{np.random.randint(100, 500)}' for _ in range(num_rows)],
    'customer_id': [f'CUST-{np.random.randint(1000, 9999)}' for _ in range(num_rows)],
    'category': np.random.choice(categories, size=num_rows, p=[0.25, 0.20, 0.20, 0.25, 0.10]),
    'region': np.random.choice(regions, size=num_rows),
    'order_date': pd.to_datetime('2025-01-01') + pd.to_timedelta(np.random.randint(0, 365, size=num_rows), unit='D'),
    'order_quantity': np.random.randint(1, 25, size=num_rows),
    'unit_price': np.round(np.random.uniform(10.0, 500.0, size=num_rows), 2),
    'warehouse_stock': np.random.randint(0, 200, size=num_rows)
})
df['revenue'] = np.round(df['order_quantity'] * df['unit_price'], 2)

# Clean & Optimize Memory
df.drop_duplicates(subset=['order_id', 'product_id'], inplace=True)
df['category'] = df['category'].astype('category')
df['region'] = df['region'].astype('category')
df['order_quantity'] = pd.to_numeric(df['order_quantity'], downcast='integer')
df['warehouse_stock'] = pd.to_numeric(df['warehouse_stock'], downcast='integer')
df['unit_price'] = pd.to_numeric(df['unit_price'], downcast='float')
df['revenue'] = pd.to_numeric(df['revenue'], downcast='float')

# Monthly KPI Aggregation
df['year_month'] = df['order_date'].dt.to_period('M').astype(str)
monthly = df.groupby('year_month', observed=False).agg(
    total_revenue=('revenue', 'sum'),
    total_orders=('order_id', 'count'),
    stockout_events=('warehouse_stock', lambda x: (x == 0).sum())
).reset_index()
monthly['mom_revenue_growth_%'] = (monthly['total_revenue'].pct_change() * 100).round(2)
monthly.to_csv('monthly_kpi_summary.csv', index=False)

# Generate 2x2 Executive KPI Dashboard Preview
fig, axes = plt.subplots(2, 2, figsize=(14, 8))
fig.suptitle('Retail Supply Chain & Sales Analytics - Executive KPI Dashboard (100K Orders)', fontsize=14, fontweight='bold')

# Plot 1: Monthly Revenue Trend
axes[0, 0].plot(monthly['year_month'], monthly['total_revenue'] / 1e6, marker='o', color='#1f77b4', linewidth=2)
axes[0, 0].set_title('Monthly Revenue Trend ($ Millions)', fontweight='bold')
axes[0, 0].tick_params(axis='x', rotation=45)
axes[0, 0].grid(True, linestyle='--', alpha=0.5)

# Plot 2: Revenue by Category
cat_rev = df.groupby('category', observed=False)['revenue'].sum().sort_values() / 1e6
axes[0, 1].barh(cat_rev.index.astype(str), cat_rev.values, color='#2ca02c')
axes[0, 1].set_title('Total Revenue by Product Category ($ Millions)', fontweight='bold')
axes[0, 1].grid(True, axis='x', linestyle='--', alpha=0.5)

# Plot 3: Regional Order Share
reg_rev = df.groupby('region', observed=False)['revenue'].sum()
axes[1, 0].pie(reg_rev.values, labels=reg_rev.index.astype(str), autopct='%1.1f%%', startangle=140, colors=['#4c72b0', '#55a868', '#c44e52', '#8172b2'])
axes[1, 0].set_title('Regional Revenue Share', fontweight='bold')

# Plot 4: Stockout Incidents by Category
stockouts = df[df['warehouse_stock'] == 0].groupby('category', observed=False).size().sort_values(ascending=False)
axes[1, 1].bar(stockouts.index.astype(str), stockouts.values, color='#d62728')
axes[1, 1].set_title('Stockout Incidents (Warehouse Stock = 0) by Category', fontweight='bold')
axes[1, 1].tick_params(axis='x', rotation=20)
axes[1, 1].grid(True, axis='y', linestyle='--', alpha=0.5)

plt.tight_layout()
plt.savefig('dashboard_preview.png', dpi=150)
print('Generated monthly_kpi_summary.csv and dashboard_preview.png successfully!')
