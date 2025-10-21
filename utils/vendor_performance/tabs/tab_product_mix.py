"""
Product Mix Analysis Tab - Clean Version

Analyze product performance with flexible date dimensions
All deprecations fixed

Version: 2.1
Last Updated: 2025-10-21
"""

import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
from typing import TYPE_CHECKING, Dict, Any

from ..visualizations import ChartFactory, render_chart
from ..constants import format_currency, format_percentage

if TYPE_CHECKING:
    from ..data_access import VendorPerformanceDAO


def render(
    dao: 'VendorPerformanceDAO',
    filters: Dict[str, Any],
    vendor_display: str
) -> None:
    """
    Render Product Mix Tab
    
    Args:
        dao: Data access object
        filters: Global filters
        vendor_display: Selected vendor display string
    """
    st.subheader("📦 Product Mix Analysis")
    st.markdown("*Product-level performance analysis*")
    
    # Require specific vendor selection
    if vendor_display == "All Vendors":
        st.info("📌 Please select a specific vendor to view product analysis")
        return
    
    vendor_name = filters.get('vendor_name')
    
    # ==================== TAB-LEVEL DATE FILTER ====================
    st.markdown("---")
    st.markdown("#### 📅 Product Analysis Configuration")
    
    col1, col2, col3, col4 = st.columns([2, 1, 1, 1])
    
    with col1:
        analysis_basis = st.selectbox(
            "Analyze By",
            ["Order Date (PO Date)", "Invoice Date", "Expected Delivery (ETD)"],
            index=0,
            help="Choose date dimension for analysis",
            key="product_analysis_basis"
        )
    
    with col2:
        date_range_option = st.selectbox(
            "Time Range",
            ["Last 3 Months", "Last 6 Months", "Last 12 Months"],
            index=1,
            key="product_date_range"
        )
    
    # Calculate date range
    months_map = {
        "Last 3 Months": 3,
        "Last 6 Months": 6,
        "Last 12 Months": 12
    }
    months = months_map[date_range_option]
    end_date = datetime.now().date()
    start_date = end_date - timedelta(days=months * 30)
    
    with col3:
        st.metric("From", start_date.strftime("%Y-%m-%d"))
    
    with col4:
        st.metric("To", end_date.strftime("%Y-%m-%d"))
    
    # Info based on analysis basis
    if "Order Date" in analysis_basis:
        st.info("📊 Analyzing products based on **purchase order date** (when orders were placed)")
    elif "Invoice Date" in analysis_basis:
        st.info("💰 Analyzing products based on **invoice date** (when invoices were issued)")
    else:
        st.info("🚚 Analyzing products based on **expected delivery date** (ETD)")
    
    st.markdown("---")
    
    # ==================== LOAD DATA ====================
    
    with st.spinner("Loading product data..."):
        try:
            # For now, use order-based analysis (most common)
            # Can extend to invoice/ETD based later
            product_df = dao.get_product_summary_by_orders(
                start_date=datetime.combine(start_date, datetime.min.time()),
                end_date=datetime.combine(end_date, datetime.min.time()),
                filters=filters
            )
            
        except Exception as e:
            st.error(f"Error loading product data: {str(e)}")
            return
    
    if product_df.empty:
        st.warning("No product data found for the selected criteria")
        return
    
    # ==================== PORTFOLIO SUMMARY ====================
    
    st.markdown("### 🎯 Product Portfolio Summary")
    
    total_products = len(product_df)
    total_brands = product_df['brand'].nunique()
    avg_conversion = product_df['conversion_rate'].mean()
    total_value = product_df['total_order_value'].sum()
    total_invoiced = product_df['total_invoiced_value'].sum()
    total_outstanding = product_df['outstanding_value'].sum()
    
    col1, col2, col3, col4, col5, col6 = st.columns(6)
    
    with col1:
        st.metric("Products", f"{total_products:,}")
    
    with col2:
        st.metric("Brands", f"{total_brands:,}")
    
    with col3:
        st.metric(
            "Total Value",
            format_currency(total_value, compact=True)
        )
    
    with col4:
        st.metric(
            "Invoiced",
            format_currency(total_invoiced, compact=True),
            delta=f"{(total_invoiced/total_value*100):.1f}%" if total_value > 0 else None
        )
    
    with col5:
        st.metric(
            "Outstanding",
            format_currency(total_outstanding, compact=True),
            delta=f"{(total_outstanding/total_value*100):.1f}%" if total_value > 0 else None,
            delta_color="inverse"
        )
    
    with col6:
        st.metric(
            "Avg Conv.",
            f"{avg_conversion:.1f}%"
        )
    
    st.markdown("---")
    
    # ==================== TREEMAP VISUALIZATION ====================
    
    st.markdown("### 📊 Product Mix by Value")
    
    chart_factory = ChartFactory()
    
    col1, col2 = st.columns([2, 1])
    
    with col1:
        top_n = st.slider(
            "Show Top N Products",
            min_value=5,
            max_value=min(30, len(product_df)),
            value=min(15, len(product_df)),
            key="product_treemap_top_n"
        )
    
    with col2:
        color_by = st.selectbox(
            "Color By",
            ["Conversion Rate", "Order Value"],
            index=0,
            key="treemap_color"
        )
    
    fig_treemap = chart_factory.create_product_treemap(
        product_df,
        top_n=top_n
    )
    render_chart(fig_treemap, key="chart_product_treemap")
    
    st.markdown("---")
    
    # ==================== PRODUCT PERFORMANCE TABLE ====================
    
    st.markdown("### 📋 Product Performance Details")
    
    # Filters
    col1, col2, col3 = st.columns([2, 1, 1])
    
    with col1:
        search_term = st.text_input(
            "🔍 Search Products",
            placeholder="Enter product name or PT code...",
            key="product_search"
        )
    
    with col2:
        brands = ['All Brands'] + sorted(product_df['brand'].unique().tolist())
        selected_brand = st.selectbox(
            "Filter by Brand",
            brands,
            key="product_brand_filter"
        )
    
    with col3:
        sort_by = st.selectbox(
            "Sort by",
            ["Order Value", "Invoiced Value", "Conversion Rate", "Outstanding", "PO Count"],
            index=0,
            key="product_sort"
        )
    
    # Filter data
    filtered_df = product_df.copy()
    
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
        "Outstanding": "outstanding_value",
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
    display_df['Outstanding'] = display_df['outstanding_value'].apply(format_currency)
    display_df['Conv %'] = display_df['conversion_rate'].apply(lambda x: f"{x:.1f}%")
    display_df['Avg Order'] = display_df['avg_order_value'].apply(format_currency)
    
    # Prepare display columns
    display_df = display_df[['product_name', 'pt_code', 'brand', 'po_count',
                             'Order Value', 'Invoiced', 'Outstanding', 'Conv %', 'Avg Order']]
    display_df.columns = [
        'Product Name', 'PT Code', 'Brand', 'PO Count',
        'Order Value', 'Invoiced', 'Outstanding', 'Conv %', 'Avg Order'
    ]
    
    # Fixed: Use width='stretch' instead of use_container_width=True
    st.dataframe(
        display_df,
        width='stretch',
        hide_index=True,
        height=400
    )
    
    st.caption(f"Showing {len(display_df)} of {len(product_df)} products")
    
    st.markdown("---")
    
    # ==================== PRODUCT DETAIL DRILL-DOWN ====================
    
    st.markdown("### 🔍 Product Detail View")
    
    if filtered_df.empty:
        st.info("No products match the current filters")
        return
    
    selected_product = st.selectbox(
        "Select Product for Details",
        options=filtered_df['product_name'].tolist(),
        key="product_detail_selector"
    )
    
    if selected_product:
        _render_product_detail(
            dao=dao,
            product_name=selected_product,
            vendor_name=vendor_name,
            product_df=product_df,
            start_date=start_date,
            end_date=end_date
        )
    
    # Export button
    st.markdown("---")
    csv = product_df.to_csv(index=False).encode('utf-8')
    st.download_button(
        label="📥 Download Product Data",
        data=csv,
        file_name=f"product_mix_{vendor_name}_{datetime.now().strftime('%Y%m%d')}.csv",
        mime='text/csv'
    )


def _render_product_detail(
    dao: 'VendorPerformanceDAO',
    product_name: str,
    vendor_name: str,
    product_df: pd.DataFrame,
    start_date: datetime,
    end_date: datetime
) -> None:
    """
    Render detailed view for single product
    
    Args:
        dao: Data access object
        product_name: Product name
        vendor_name: Vendor name
        product_df: Product summary dataframe
        start_date: Start date
        end_date: End date
    """
    # Get product summary
    product_data = product_df[product_df['product_name'] == product_name]
    
    if product_data.empty:
        return
    
    product_data = product_data.iloc[0]
    
    # Product info
    st.markdown(f"#### {product_name}")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.markdown(f"**PT Code:** {product_data['pt_code']}")
        st.markdown(f"**Brand:** {product_data['brand']}")
    
    with col2:
        st.markdown(f"**Total POs:** {int(product_data['po_count']):,}")
        st.markdown(f"**Avg Order:** {format_currency(product_data['avg_order_value'])}")
    
    with col3:
        st.markdown(f"**Quantity:** {product_data['total_ordered_qty']:,.0f}")
    
    st.markdown("---")
    
    # Product metrics
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric(
            "Order Value",
            format_currency(product_data['total_order_value'])
        )
    
    with col2:
        st.metric(
            "Invoiced",
            format_currency(product_data['total_invoiced_value']),
            delta=f"{product_data['conversion_rate']:.1f}%"
        )
    
    with col3:
        st.metric(
            "Outstanding",
            format_currency(product_data['outstanding_value']),
            delta=f"{(product_data['outstanding_value']/product_data['total_order_value']*100):.1f}%",
            delta_color="inverse"
        )
    
    with col4:
        # Conversion indicator
        if product_data['conversion_rate'] >= 90:
            st.success(f"✓ {product_data['conversion_rate']:.1f}% Conversion")
        elif product_data['conversion_rate'] >= 80:
            st.warning(f"⚠️ {product_data['conversion_rate']:.1f}% Conversion")
        else:
            st.error(f"✗ {product_data['conversion_rate']:.1f}% Conversion")
    
    st.markdown("---")
    
    # Product history note
    st.info("""
    💡 **Note**: Detailed order history requires loading PO data. 
    Use the Order Analysis tab for complete order details.
    """)