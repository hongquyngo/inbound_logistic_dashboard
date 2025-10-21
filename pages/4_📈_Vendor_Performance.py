"""
Vendor Performance Analysis Page - Refactored

Simplified dashboard focused on key business metrics:
- Order Entry Value
- Invoiced Value  
- Pending Delivery
- Conversion Rate

3 Tabs:
1. Overview - Snapshot dashboard
2. Financial Performance - Order entry vs invoiced trends
3. Product Mix - Product-level analysis
"""

import streamlit as st
import pandas as pd
from datetime import datetime
import logging

# Explicit imports
from utils.auth import AuthManager
from utils.vendor_performance.data_access import VendorPerformanceDAO
from utils.vendor_performance.calculations import PerformanceCalculator
from utils.vendor_performance.exceptions import DataAccessError, VendorPerformanceError

# Import tab modules
from utils.vendor_performance.tabs import tab_overview
from utils.vendor_performance.tabs import tab_financial
from utils.vendor_performance.tabs import tab_product

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
try:
    dao = VendorPerformanceDAO()
except Exception as e:
    st.error("Failed to initialize database connection")
    logger.error(f"DAO initialization failed: {e}")
    st.stop()

# Header
st.title("🏭 Vendor Performance Analysis")
st.markdown("Simplified analytics focused on order entry, invoiced value, and conversion rates")

# ==================== FILTERS SECTION ====================
st.markdown("---")
st.subheader("🔧 Configuration")

col1, col2, col3 = st.columns([2, 1, 1])

with col1:
    # Vendor selection
    try:
        vendor_options = dao.get_vendor_list()
    except DataAccessError as e:
        st.error("Failed to load vendor list")
        logger.error(f"Vendor list error: {e}")
        vendor_options = []
    
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

# Advanced filters (collapsed by default)
with st.expander("🔍 Advanced Filters", expanded=False):
    col1, col2, col3 = st.columns(3)
    
    try:
        filter_options = dao.get_filter_options()
    except Exception as e:
        logger.warning(f"Failed to load filter options: {e}")
        filter_options = {}
    
    with col1:
        vendor_types = st.multiselect(
            "Vendor Type",
            options=filter_options.get('vendor_types', []),
            default=None
        )
    
    with col2:
        vendor_locations = st.multiselect(
            "Vendor Location",
            options=filter_options.get('vendor_locations', []),
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

# ==================== LOAD DATA ====================
st.markdown("---")

with st.spinner("Loading vendor performance data..."):
    try:
        # Load vendor summary
        vendor_summary = dao.get_vendor_summary(
            vendor_name=selected_vendor_name,
            months=months_back
        )
        
        # Load PO data
        po_data = dao.get_po_data(
            vendor_name=selected_vendor_name,
            months=months_back,
            filters={
                'vendor_types': vendor_types if vendor_types else None,
                'vendor_locations': vendor_locations if vendor_locations else None,
                'payment_terms': payment_terms if payment_terms else None
            }
        )
        
        # Validate data
        if vendor_summary is None:
            vendor_summary = pd.DataFrame()
        if po_data is None:
            po_data = pd.DataFrame()
        
    except DataAccessError as e:
        st.error(f"Failed to load data: {str(e)}")
        logger.error(f"Data loading error: {e}", exc_info=True)
        vendor_summary = pd.DataFrame()
        po_data = pd.DataFrame()
    except Exception as e:
        st.error(f"Unexpected error: {str(e)}")
        logger.error(f"Unexpected error: {e}", exc_info=True)
        vendor_summary = pd.DataFrame()
        po_data = pd.DataFrame()

# Check if we have data
if vendor_summary.empty and po_data.empty:
    st.warning("⚠️ No data available for the selected criteria. Please adjust your filters.")
    st.stop()

# ==================== DATA SUMMARY ====================
col1, col2, col3, col4 = st.columns(4)

with col1:
    vendor_count = len(vendor_summary) if not vendor_summary.empty else 0
    st.metric("Vendors Loaded", f"{vendor_count:,}")

with col2:
    po_count = len(po_data) if not po_data.empty else 0
    st.metric("PO Records", f"{po_count:,}")

with col3:
    if not vendor_summary.empty:
        total_value = vendor_summary['total_order_value'].sum()
        st.metric("Total Order Value", f"${total_value/1000000:.1f}M")
    else:
        st.metric("Total Order Value", "$0")

with col4:
    if not vendor_summary.empty:
        avg_conversion = vendor_summary['conversion_rate'].mean()
        st.metric(
            "Avg Conversion", 
            f"{avg_conversion:.1f}%",
            delta=f"{avg_conversion - 90:.1f}% vs target",
            delta_color="normal" if avg_conversion >= 90 else "inverse"
        )
    else:
        st.metric("Avg Conversion", "N/A")

# ==================== TABS ====================
st.markdown("---")

tabs = st.tabs([
    "📊 Overview",
    "💰 Financial Performance",
    "📦 Product Mix"
])

with tabs[0]:
    try:
        tab_overview.render(
            vendor_summary,
            po_data,
            selected_vendor_name or "All Vendors"
        )
    except Exception as e:
        st.error(f"Error rendering Overview tab: {str(e)}")
        logger.error(f"Overview tab error: {e}", exc_info=True)

with tabs[1]:
    try:
        tab_financial.render(
            vendor_summary,
            po_data,
            period_type,
            selected_vendor_name or "All Vendors"
        )
    except Exception as e:
        st.error(f"Error rendering Financial Performance tab: {str(e)}")
        logger.error(f"Financial tab error: {e}", exc_info=True)

with tabs[2]:
    try:
        tab_product.render(
            po_data,
            selected_vendor_name or "All Vendors",
            dao  # Pass DAO for product summary query
        )
    except Exception as e:
        st.error(f"Error rendering Product Mix tab: {str(e)}")
        logger.error(f"Product tab error: {e}", exc_info=True)

# ==================== FOOTER ====================
st.markdown("---")
col1, col2, col3 = st.columns([2, 1, 1])

with col1:
    st.caption(f"Report generated on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

with col2:
    if st.button("🔄 Refresh Data"):
        # Clear specific caches
        try:
            dao.get_vendor_list.clear()
            dao.get_vendor_summary.clear()
            dao.get_po_data.clear()
            dao.get_product_summary.clear()
        except:
            pass
        st.rerun()

with col3:
    if st.button("📋 Help"):
        st.info("""
        **Vendor Performance Analysis - User Guide:**
        
        **Overview Tab:**
        - Quick snapshot of vendor performance
        - Key metrics: Order Value, Invoiced, Pending, Conversion
        - Alerts and top products
        
        **Financial Performance Tab:**
        - Detailed order entry vs invoiced trends
        - Periodic and cumulative views
        - Monthly breakdown table
        - Period-over-period comparison
        
        **Product Mix Tab:**
        - Product-level performance
        - Visual treemap of product portfolio
        - Product detail drill-down
        - Recent order history
        
        **Key Metrics:**
        - **Order Entry Value**: Total value of purchase orders
        - **Invoiced Value**: Amount actually delivered/invoiced
        - **Pending Delivery**: Outstanding amount (Order - Invoiced)
        - **Conversion Rate**: Invoiced / Order Entry × 100%
        
        **Tips:**
        - Target conversion rate: ≥ 90%
        - Use filters to narrow down analysis
        - Download data for offline analysis
        - Refresh data to get latest updates
        """)