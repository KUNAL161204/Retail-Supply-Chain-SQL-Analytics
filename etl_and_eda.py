import numpy as np
import pandas as pd


def generate_and_clean_retail_data(num_rows=100000):
  """Generates synthetic retail supply chain data, cleans missing values,

  downcasts data types to optimize memory, and performs exploratory data
  analysis.
  """
  np.random.seed(42)

  # 1. Generate Raw Transactional Dataset
  categories = [
      'Electronics',
      'Apparel',
      'Home & Kitchen',
      'FMCG',
      'Automotive',
  ]
  regions = ['North', 'South', 'East', 'West']

  df = pd.DataFrame({
      'order_id': [f'ORD-{100000 + i}' for i in range(num_rows)],
      'product_id': [
          f'SKU-{np.random.randint(100, 500)}' for _ in range(num_rows)
      ],
      'customer_id': [
          f'CUST-{np.random.randint(1000, 9999)}' for _ in range(num_rows)
      ],
      'category': np.random.choice(
          categories, size=num_rows, p=[0.25, 0.20, 0.20, 0.25, 0.10]
      ),
      'region': np.random.choice(regions, size=num_rows),
      'order_date': pd.to_datetime('2025-01-01') + pd.to_timedelta(
          np.random.randint(0, 365, size=num_rows), unit='D'
      ),
      'order_quantity': np.random.randint(1, 25, size=num_rows),
      'unit_price': np.round(np.random.uniform(10.0, 500.0, size=num_rows), 2),
      'warehouse_stock': np.random.randint(0, 200, size=num_rows),
  })

  # Compute revenue
  df['revenue'] = np.round(df['order_quantity'] * df['unit_price'], 2)

  # 2. Data Cleaning & Memory Optimization
  initial_mem = df.memory_usage(deep=True).sum() / (1024**2)

  # Remove duplicate (order_id, product_id) combinations
  df.drop_duplicates(subset=['order_id', 'product_id'], inplace=True)

  # Optimize data types (downcasting numeric and converting strings to category)
  df['category'] = df['category'].astype('category')
  df['region'] = df['region'].astype('category')
  df['order_quantity'] = pd.to_numeric(df['order_quantity'], downcast='integer')
  df['warehouse_stock'] = pd.to_numeric(
      df['warehouse_stock'], downcast='integer'
  )
  df['unit_price'] = pd.to_numeric(df['unit_price'], downcast='float')
  df['revenue'] = pd.to_numeric(df['revenue'], downcast='float')

  optimized_mem = df.memory_usage(deep=True).sum() / (1024**2)
  print(
      f'Memory reduced from {initial_mem:.2f} MB to {optimized_mem:.2f} MB'
      f' ({(1 - optimized_mem/initial_mem)*100:.1f}% reduction)'
  )

  # 3. Exploratory Data Analysis (EDA): Monthly Revenue & Stockout Rate
  df['year_month'] = df['order_date'].dt.to_period('M')
  monthly_summary = (
      df.groupby('year_month', observed=False)
      .agg(
          total_revenue=('revenue', 'sum'),
          total_orders=('order_id', 'count'),
          stockout_events=('warehouse_stock', lambda x: (x == 0).sum()),
      )
      .reset_index()
  )

  monthly_summary['mom_revenue_growth_%'] = (
      monthly_summary['total_revenue'].pct_change() * 100
  ).round(2)
  print('\n--- Monthly Revenue & Stockout Summary ---')
  print(monthly_summary.head(6))

  # Save cleaned summary report
  monthly_summary.to_csv('monthly_kpi_summary.csv', index=False)
  print('\nSaved cleaned KPI output to monthly_kpi_summary.csv')


if __name__ == '__main__':
  generate_and_clean_retail_data()