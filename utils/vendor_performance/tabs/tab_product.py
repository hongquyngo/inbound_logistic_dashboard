"""
Product Analysis Tab

Shows product mix and purchasing patterns.
"""

import streamlit as st
import pandas as pd
import plotly.express as px

from ..visualizations import ChartFactory

# Standard Plotly config
PLOTLY_CONFIG = {'displaylogo': False, 'displayModeBar': True}


def render(po_data: pd.DataFrame, selected_vendor: str) -> None:
    """
    Render Product Analysis Tab
    
    Args:
        po_data: DataFrame with PO data
        selected_vendor: Selected vendor name
    """
    st.subheader("📦 Product Mix Analysis")
    
    if selected_vendor == "All Vendors" or po_data.empty:
        st.info("Please select a specific vendor to view product analysis")
        return
    
    # Filter for selected vendor
    vendor_po = po_data[po_data['vendor_name'] == selected_vendor]
    
    if vendor_po.empty:
        st.info(f"No purchase orders found for {selected_vendor}")
        return
    
    # Product summary
    product_analysis = vendor_po.groupby(['product_name', 'pt_code', 'brand']).agg({
        'po_line_id': 'count',
        'standard_quantity': 'sum',
        'total_amount_usd': 'sum',
        'standard_unit_cost': 'mean'
    }).reset_index()
    
    product_analysis.columns = [
        'Product', 'PT Code', 'Brand', 'Order Lines',
        'Total Qty', 'Total Value', 'Avg Unit Cost'
    ]
    
    # Top products treemap
    top_products = product_analysis.nlargest(15, 'Total Value')
    
    if not top_products.empty:
        chart_factory = ChartFactory()
        fig = chart_factory.create_treemap(
            top_products,
            path_columns=['Brand', 'Product'],
            value_column='Total Value',
            color_column='Total Qty',
            title=f"Product Mix by Value - {selected_vendor}"
        )
        st.plotly_chart(fig, use_container_width=True, config=PLOTLY_CONFIG)
        
        # Product details table
        st.markdown("#### Product Purchase Details")
        
        display_products = product_analysis.sort_values('Total Value', ascending=False).head(20)
        st.dataframe(display_products, use_container_width=True, hide_index=True)
        
        # Price trend analysis
        if 'po_date' in vendor_po.columns:
            _render_price_trends(vendor_po, top_products['Product'].tolist()[:5])


def _render_price_trends(vendor_po: pd.DataFrame, top_products: list) -> None:
    """Render price trend analysis"""
    st.markdown("#### Price Trend Analysis")
    
    price_trend_data = vendor_po[vendor_po['product_name'].isin(top_products)].copy()
    
    if price_trend_data.empty:
        return
    
    price_trend_data['month'] = pd.to_datetime(
        price_trend_data['po_date']
    ).dt.to_period('M').dt.to_timestamp()
    
    price_trend = price_trend_data.groupby(
        ['month', 'product_name']
    )['standard_unit_cost'].mean().reset_index()
    
    if not price_trend.empty:
        fig = px.line(
            price_trend,
            x='month',
            y='standard_unit_cost',
            color='product_name',
            title="Unit Price Trends - Top 5 Products",
            labels={'standard_unit_cost': 'Unit Cost (USD)', 'product_name': 'Product'}
        )
        st.plotly_chart(fig, use_container_width=True, config=PLOTLY_CONFIG)