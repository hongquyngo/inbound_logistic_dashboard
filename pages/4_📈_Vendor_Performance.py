"""
Vendor Performance Analysis Page

Main page for vendor performance analytics and reporting.
"""

import streamlit as st
import pandas as pd
from datetime import datetime
import logging

# Explicit imports from vendor_performance modules
from utils.auth import AuthManager
from utils.vendor_performance.data_access import VendorPerformanceDAO
from utils.vendor_performance.calculations import PerformanceCalculator

# Import tab modules directly
from utils.vendor_performance.tabs import tab_overview
from utils.vendor_performance.tabs import tab_purchase
from utils.vendor_performance.tabs import tab_performance
from utils.vendor_performance.tabs import tab_product
from utils.vendor_performance.tabs import tab_payment
from utils.vendor_performance.tabs import tab_export

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Page config
st.set_page_config(
    page_title="Vendor Performance Analysis",
    page_icon="🏭",
    layout="wide"
)

# Check authentication
auth_manager = AuthManager()
if not auth_manager.check_session():
    st.warning("⚠️ Please login to access this page")
    st.stop()

# Initialize DAO
dao = VendorPerformanceDAO()

# Header
st.title("🏭 Vendor Performance Analysis")
st.markdown("Comprehensive analytics for vendor performance, purchasing patterns, and negotiations")

# Filters Section
st.markdown("---")
st.subheader("📊 Analysis Configuration")

col1, col2, col3 = st.columns([2, 1, 1])

with col1:
    # Vendor selection
    vendor_options = dao.get_vendor_list()
    
    if vendor_options:
        vendor_display_options = ["All Vendors"] + vendor_options
        selected_vendor_display = st.selectbox(
            "Select Vendor",
            vendor_display_options,
            help="Choose a specific vendor or view all vendors"
        )
    else:
        selected_vendor_display = "All Vendors"
        st.warning("No vendors found in database")

with col2:
    # Period selection
    period_type = st.selectbox(
        "Analysis Period",
        ["Monthly", "Quarterly", "Yearly"],
        help="Grouping period for time series analysis"
    )

with col3:
    # Time range
    months_back = st.number_input(
        "Months Back",
        min_value=1,
        max_value=24,
        value=6,
        help="Number of months to analyze"
    )

# Advanced filters (optional)
with st.expander("🔍 Advanced Filters", expanded=False):
    col1, col2, col3 = st.columns(3)
    
    with col1:
        # Get filter options
        filter_options = dao.get_filter_options()
        
        vendor_types = st.multiselect(
            "Vendor Type",
            options=filter_options.get('vendor_types', []),
            default=None
        )
    
    with col2:
        vendor_locations = st.multiselect(
            "Vendor Location",
            options=filter_options.get('vendor_location_types', []),
            default=None
        )
    
    with col3:
        payment_terms = st.multiselect(
            "Payment Terms",
            options=filter_options.get('payment_terms', []),
            default=None
        )

# Extract vendor name from display format
selected_vendor_name = None
if selected_vendor_display != "All Vendors":
    if ' - ' in selected_vendor_display:
        _, selected_vendor_name = selected_vendor_display.split(' - ', 1)
        selected_vendor_name = selected_vendor_name.strip()
    else:
        selected_vendor_name = selected_vendor_display.strip()

# Load data
st.markdown("---")

with st.spinner("Loading vendor performance data..."):
    try:
        # Load vendor metrics
        if selected_vendor_name:
            vendor_metrics = dao.get_vendor_metrics(
                vendor_name=selected_vendor_name,
                months=months_back
            )
            
            # Load PO data with vendor filter
            po_data = dao.get_po_data({
                'vendors': [selected_vendor_display]
            })
        else:
            # Load all vendors
            vendor_metrics = dao.get_vendor_metrics(months=months_back)
            po_data = dao.get_po_data()
        
        # Validate data
        if vendor_metrics is None:
            vendor_metrics = pd.DataFrame()
        if po_data is None:
            po_data = pd.DataFrame()
        
        # Apply advanced filters if specified
        if not po_data.empty:
            if vendor_types:
                po_data = po_data[po_data['vendor_type'].isin(vendor_types)]
            if vendor_locations:
                po_data = po_data[po_data['vendor_location_type'].isin(vendor_locations)]
            if payment_terms:
                po_data = po_data[po_data['payment_term'].isin(payment_terms)]
        
    except Exception as e:
        logger.error(f"Error loading vendor data: {e}")
        st.error(f"Failed to load data: {str(e)}")
        vendor_metrics = pd.DataFrame()
        po_data = pd.DataFrame()

# Check if we have data
if vendor_metrics.empty and po_data.empty:
    st.warning("⚠️ No data available for the selected criteria. Please adjust your filters.")
    st.stop()

# Data summary
col1, col2, col3, col4 = st.columns(4)

with col1:
    st.metric("Vendors Loaded", len(vendor_metrics))

with col2:
    st.metric("PO Records", len(po_data))

with col3:
    if not vendor_metrics.empty:
        total_value = vendor_metrics['total_po_value'].sum()
        st.metric("Total Value", f"${total_value/1000000:.1f}M")
    else:
        st.metric("Total Value", "$0")

with col4:
    if not vendor_metrics.empty:
        avg_score = vendor_metrics.get('on_time_rate', pd.Series([0])).mean()
        st.metric("Avg On-Time Rate", f"{avg_score:.1f}%")
    else:
        st.metric("Avg On-Time Rate", "N/A")

# Tabs
st.markdown("---")

tabs = st.tabs([
    "📊 Overview",
    "💰 Purchase Analysis",
    "📈 Performance Trends",
    "📦 Product Analysis",
    "💳 Payment Analysis",
    "📄 Export Report"
])

with tabs[0]:
    tab_overview.render(vendor_metrics, po_data, selected_vendor_name or "All Vendors")

with tabs[1]:
    tab_purchase.render(po_data, period_type, selected_vendor_name or "All Vendors")

with tabs[2]:
    tab_performance.render(vendor_metrics, po_data, selected_vendor_name or "All Vendors")

with tabs[3]:
    tab_product.render(po_data, selected_vendor_name or "All Vendors")

with tabs[4]:
    tab_payment.render(po_data, selected_vendor_name or "All Vendors")

with tabs[5]:
    tab_export.render(vendor_metrics, po_data, selected_vendor_name or "All Vendors")

# Footer
st.markdown("---")
col1, col2, col3 = st.columns([2, 1, 1])

with col1:
    st.caption(f"Report generated on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

with col2:
    if st.button("🔄 Refresh Data"):
        st.cache_data.clear()
        st.rerun()

with col3:
    if st.button("📋 Help"):
        st.info("""
        **How to use Vendor Performance Analysis:**
        
        1. Select a vendor or view all vendors
        2. Choose analysis period (Monthly/Quarterly/Yearly)
        3. Set time range (months back to analyze)
        4. Navigate through tabs for different insights
        5. Export reports from the Export tab
        
        **Tips:**
        - Use Overview tab for quick summary
        - Purchase Analysis shows spending patterns
        - Performance Trends reveal delivery reliability
        - Product Analysis shows product mix
        - Payment Analysis tracks financial terms
        """)