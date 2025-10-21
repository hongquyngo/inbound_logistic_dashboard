"""
Product Mix Analysis Tab

Analyze performance by product:
- Product-level order entry and invoiced values
- Product treemap
- Product detail drill-down
"""

import streamlit as st
import pandas as pd
import plotly.express as px
from datetime import datetime
from typing import TYPE_CHECKING

from ..visualizations import ChartFactory
from ..calculations import PerformanceCalculator
from ..constants import format_currency, format_percentage, PLOTLY_CONFIG, COLORS
from ..exceptions import DataAccessError

if TYPE_CHECKING:
    from ..data_access import VendorPerformanceDAO


def render(
    po_data: pd.DataFrame,
    selected_vendor: str,
    dao: 'VendorPerformanceDAO'
) -> None:
    """
    Render Product Mix Tab
    
    Args:
        po_data: PO data
        selected_vendor: Selected vendor name
        dao: Data access object (for product summary query)
    """
    st.subheader("📦 Product Mix Analysis")
    
    if selected_vendor == "All Vendors":
        st.info("Please select a specific vendor to view product analysis")
        return
    
    if po_data.empty:
        st.info(f"No purchase orders found for {selected_vendor}")
        return
    
    # Filter vendor data
    vendor_po = po_data[po_data['vendor_name'] == selected_vendor]
    
    if vendor_po.empty:
        st.info(f"No purchase orders found for {selected_vendor}")
        return
    
    # Get product summary
    try:
        # Use DAO to get product summary with proper aggregation
        product_summary = dao.get_product_summary(
            vendor_name=selected_vendor,
            months=12  # Get last 12 months
        )
    except Exception as e:
        st.error(f"Error loading product data: {str(e)}")
        # Fallback to manual aggregation
        product_summary = _manual_product_aggregation(vendor_po)
    
    if product_summary.empty:
        st.info("No product data available")
        return
    
    _render_product_analysis(product_summary, vendor_po, selected_vendor)


def _manual_product_aggregation(vendor_po: pd.DataFrame) -> pd.DataFrame:
    """
    Manually aggregate product data if DAO fails
    
    Args:
        vendor_po: Vendor PO data
        
    Returns:
        Product summary dataframe
    """
    calc = PerformanceCalculator()
    
    product_summary = vendor_po.groupby(['product_name', 'pt_code', 'brand']).agg({
        'po_number': 'nunique',
        'standard_quantity': 'sum',
        'total_order_value_usd': 'sum',
        'invoiced_amount_usd': 'sum',
        'pending_delivery_usd': 'sum',
        'po_date': 'max'
    }).reset_index()
    
    product_summary.columns = [
        'product_name', 'pt_code', 'brand', 'po_count',
        'total_ordered_qty', 'total_order_value', 'total_invoiced_value',
        'pending_value', 'last_order_date'
    ]
    
    # Calculate conversion rate
    product_summary['conversion_rate'] = product_summary.apply(
        lambda row: calc.calculate_conversion_rate(
            row['total_invoiced_value'],
            row['total_order_value']
        ),
        axis=1
    )
    
    return product_summary


def _render_product_analysis(
    product_summary: pd.DataFrame,
    vendor_po: pd.DataFrame,
    vendor_name: str
) -> None:
    """
    Render product analysis sections
    
    Args:
        product_summary: Product summary data
        vendor_po: Vendor PO data
        vendor_name: Vendor name
    """
    # Portfolio summary cards
    st.markdown("### 🎯 Product Portfolio Summary")
    
    col1, col2, col3, col4 = st.columns(4)
    
    total_products = len(product_summary)
    total_brands = product_summary['brand'].nunique()
    avg_conversion = product_summary['conversion_rate'].mean()
    total_order_value = product_summary['total_order_value'].sum()
    
    with col1:
        st.metric("Products", f"{total_products:,}")
    
    with col2:
        st.metric("Brands", f"{total_brands:,}")
    
    with col3:
        st.metric("Avg Conversion", f"{avg_conversion:.1f}%")
    
    with col4:
        st.metric("Total Value", format_currency(total_order_value, compact=True))
    
    st.markdown("---")
    
    # Treemap
    st.markdown("### 📊 Product Mix by Value")
    
    chart_factory = ChartFactory()
    fig_treemap = chart_factory.create_product_treemap(product_summary, top_n=15)
    st.plotly_chart(fig_treemap, width='stretch', config=PLOTLY_CONFIG)
    
    st.markdown("---")
    
    # Product performance table
    st.markdown("### 📋 Product Performance Details")
    
    _render_product_table(product_summary, vendor_po, vendor_name)


def _render_product_table(
    product_summary: pd.DataFrame,
    vendor_po: pd.DataFrame,
    vendor_name: str
) -> None:
    """
    Render product performance table with drill-down
    
    Args:
        product_summary: Product summary data
        vendor_po: Vendor PO data
        vendor_name: Vendor name
    """
    # Filters
    col1, col2, col3 = st.columns([2, 1, 1])
    
    with col1:
        search_term = st.text_input(
            "🔍 Search Products",
            placeholder="Enter product name or PT code..."
        )
    
    with col2:
        brands = ['All Brands'] + sorted(product_summary['brand'].unique().tolist())
        selected_brand = st.selectbox("Filter by Brand", brands)
    
    with col3:
        sort_by = st.selectbox(
            "Sort by",
            ["Order Value", "Invoiced Value", "Conversion Rate", "PO Count"],
            index=0
        )
    
    # Filter data
    filtered_df = product_summary.copy()
    
    if search_term:
        filtered_df = filtered_df[
            filtered_df['product_name'].str.contains(search_term, case=False, na=False) |
            filtered_df['pt_code'].str.contains(search_term, case=False, na=False)
        ]
    
    if selected_brand != 'All Brands':
        filtered_df = filtered_df[filtered_df['brand'] == selected_brand]
    
    # Sort
    sort_column_map = {
        "Order Value": "total_order_value",
        "Invoiced Value": "total_invoiced_value",
        "Conversion Rate": "conversion_rate",
        "PO Count": "po_count"
    }
    filtered_df = filtered_df.sort_values(
        sort_column_map[sort_by],
        ascending=False
    )
    
    # Display table
    display_df = filtered_df.copy()
    
    # Format for display
    display_df['Order Value'] = display_df['total_order_value'].apply(format_currency)
    display_df['Invoiced'] = display_df['total_invoiced_value'].apply(format_currency)
    display_df['Pending'] = display_df['pending_value'].apply(format_currency)
    display_df['Conv %'] = display_df['conversion_rate'].apply(lambda x: f"{x:.1f}%")
    
    display_columns = [
        'product_name', 'pt_code', 'brand', 'po_count',
        'Order Value', 'Invoiced', 'Pending', 'Conv %'
    ]
    
    # Rename columns for display
    display_df = display_df[display_columns]
    display_df.columns = [
        'Product Name', 'PT Code', 'Brand', 'PO Count',
        'Order Value', 'Invoiced', 'Pending', 'Conv %'
    ]
    
    # Show data with selection
    st.dataframe(
        display_df,
        width='stretch',
        hide_index=True,
        height=400
    )
    
    st.caption(f"Showing {len(display_df)} of {len(product_summary)} products")
    
    # Product drill-down
    st.markdown("---")
    st.markdown("### 🔍 Product Detail View")
    
    selected_product = st.selectbox(
        "Select Product for Details",
        options=filtered_df['product_name'].tolist(),
        key="product_detail_selector"
    )
    
    if selected_product:
        _render_product_detail(selected_product, vendor_po, product_summary)


def _render_product_detail(
    product_name: str,
    vendor_po: pd.DataFrame,
    product_summary: pd.DataFrame
) -> None:
    """
    Render detailed view for a single product
    
    Args:
        product_name: Product name
        vendor_po: Vendor PO data
        product_summary: Product summary data
    """
    # Get product data
    product_data = product_summary[product_summary['product_name'] == product_name]
    
    if product_data.empty:
        return
    
    product_data = product_data.iloc[0]
    
    # Product summary cards
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric(
            "Total Order Value",
            format_currency(product_data['total_order_value'])
        )
    
    with col2:
        st.metric(
            "Invoiced Value",
            format_currency(product_data['total_invoiced_value']),
            delta=f"{product_data['conversion_rate']:.1f}%"
        )
    
    with col3:
        st.metric(
            "Pending Delivery",
            format_currency(product_data['pending_value'])
        )
    
    with col4:
        st.metric(
            "Number of POs",
            f"{int(product_data['po_count']):,}"
        )
    
    # Product PO history
    product_po = vendor_po[vendor_po['product_name'] == product_name].copy()
    
    if not product_po.empty:
        st.markdown("#### 📈 Monthly Performance")
        
        # Aggregate by month
        product_po['month'] = pd.to_datetime(product_po['po_date']).dt.to_period('M').dt.to_timestamp()
        
        monthly = product_po.groupby('month').agg({
            'total_order_value_usd': 'sum',
            'invoiced_amount_usd': 'sum'
        }).reset_index()
        
        # Create chart
        fig = px.line(
            monthly,
            x='month',
            y=['total_order_value_usd', 'invoiced_amount_usd'],
            labels={
                'value': 'Value (USD)',
                'month': 'Month',
                'variable': 'Metric'
            },
            title=f"Monthly Trend - {product_name}"
        )
        
        fig.update_layout(
            hovermode='x unified',
            legend=dict(
                title="",
                orientation="h",
                yanchor="bottom",
                y=1.02,
                xanchor="right",
                x=1
            )
        )
        
        # Rename legend labels
        fig.for_each_trace(lambda t: t.update(
            name='Order Entry' if 'order' in t.name else 'Invoiced'
        ))
        
        st.plotly_chart(fig, width='stretch', config=PLOTLY_CONFIG)
        
        # Recent POs table
        st.markdown("#### 📋 Recent Purchase Orders")
        
        # Convert po_date to datetime for proper sorting
        product_po_sorted = product_po.copy()
        product_po_sorted['po_date'] = pd.to_datetime(product_po_sorted['po_date'])
        
        recent_po = product_po_sorted.sort_values('po_date', ascending=False).head(10)[
            ['po_number', 'po_date', 'standard_quantity', 'total_order_value_usd', 'status']
        ].copy()
        
        recent_po['po_date'] = recent_po['po_date'].dt.strftime('%Y-%m-%d')
        recent_po['total_order_value_usd'] = recent_po['total_order_value_usd'].apply(format_currency)
        
        recent_po.columns = ['PO Number', 'Date', 'Quantity', 'Value', 'Status']
        
        st.dataframe(recent_po, width='stretch', hide_index=True)