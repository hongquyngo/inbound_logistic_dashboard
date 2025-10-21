"""
Vendor Performance Analysis Page - Clean Version

Tabs:
1. Order Analysis - Track PO lifecycle (po_date based)
2. Invoice Analysis - Analyze invoices and payments (inv_date based)  
3. Product Mix - Product-level analysis

Version: 2.1
Last Updated: 2025-10-21
"""

import streamlit as st
import pandas as pd
from datetime import datetime
import logging
from typing import Optional

# Explicit imports
from utils.auth import AuthManager
from utils.vendor_performance.data_access import VendorPerformanceDAO
from utils.vendor_performance.exceptions import DataAccessError

# Import tab modules
from utils.vendor_performance.tabs import tab_order_analysis
from utils.vendor_performance.tabs import tab_invoice_analysis
from utils.vendor_performance.tabs import tab_product_mix

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Page config
st.set_page_config(
    page_title="Vendor Performance Analysis",
    page_icon="📈",
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
st.title("📈 Vendor Performance Analysis")
st.markdown("Multi-dimensional analytics: Orders, Invoices, and Products")

# ==================== GLOBAL FILTERS SECTION ====================
st.markdown("---")
st.subheader("🔧 Global Configuration")

col1, col2 = st.columns([3, 1])

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
    # Legal Entity filter (NEW)
    try:
        entity_options = dao.get_entity_list()
    except Exception as e:
        logger.warning(f"Failed to load entity list: {e}")
        entity_options = []
    
    entity_display_options = ["All Entities"] + entity_options
    selected_entity_display = st.selectbox(
        "Legal Entity",
        entity_display_options,
        help="Filter by legal entity (buyer company)"
    )

# Advanced filters (collapsed by default)
with st.expander("⚙️ Advanced Filters", expanded=False):
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
selected_vendor_name: Optional[str] = None
if selected_vendor_display != "All Vendors":
    if ' - ' in selected_vendor_display:
        _, selected_vendor_name = selected_vendor_display.split(' - ', 1)
        selected_vendor_name = selected_vendor_name.strip()
    else:
        selected_vendor_name = selected_vendor_display.strip()

# Extract entity ID
selected_entity_id: Optional[int] = None
if selected_entity_display != "All Entities":
    try:
        # Assume format "ID - Name" or just fetch ID from database
        selected_entity_id = dao.get_entity_id_by_display(selected_entity_display)
    except Exception as e:
        logger.warning(f"Could not extract entity ID: {e}")

# Build common filters dict
common_filters = {
    'vendor_name': selected_vendor_name,
    'entity_id': selected_entity_id,
    'vendor_types': vendor_types if vendor_types else None,
    'vendor_locations': vendor_locations if vendor_locations else None,
    'payment_terms': payment_terms if payment_terms else None
}

# Store in session state for tabs to access
st.session_state['vendor_filters'] = common_filters
st.session_state['selected_vendor_display'] = selected_vendor_display

st.markdown("---")

# ==================== TABS SECTION ====================
tabs = st.tabs([
    "📈 Order Analysis",
    "💰 Invoice Analysis",
    "📦 Product Mix"
])

with tabs[0]:
    try:
        tab_order_analysis.render(
            dao=dao,
            filters=common_filters,
            vendor_display=selected_vendor_display
        )
    except Exception as e:
        st.error(f"Error rendering Order Analysis tab: {str(e)}")
        logger.error(f"Order Analysis tab error: {e}", exc_info=True)

with tabs[1]:
    try:
        tab_invoice_analysis.render(
            dao=dao,
            filters=common_filters,
            vendor_display=selected_vendor_display
        )
    except Exception as e:
        st.error(f"Error rendering Invoice Analysis tab: {str(e)}")
        logger.error(f"Invoice Analysis tab error: {e}", exc_info=True)

with tabs[2]:
    try:
        tab_product_mix.render(
            dao=dao,
            filters=common_filters,
            vendor_display=selected_vendor_display
        )
    except Exception as e:
        st.error(f"Error rendering Product Mix tab: {str(e)}")
        logger.error(f"Product Mix tab error: {e}", exc_info=True)

# ==================== FOOTER ====================
st.markdown("---")
col1, col2, col3 = st.columns([2, 1, 1])

with col1:
    st.caption(f"Report generated on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

with col2:
    if st.button("🔄 Refresh Data"):
        # Clear all caches
        st.cache_data.clear()
        st.rerun()

with col3:
    if st.button("📋 Help"):
        st.info("""
        **Vendor Performance Analysis - User Guide:**
        
        **Three Analysis Views:**
        
        **1. Order Analysis (PO-centric)**
        - Tracks purchase orders by PO date
        - Shows order entry value and fulfillment status
        - Conversion rate: How much of ordered value has been invoiced
        - Backlog: Orders not yet fully invoiced
        
        **2. Invoice Analysis (Payment-centric)**
        - Analyzes invoices by invoice date
        - Payment status and aging
        - Outstanding amounts
        - Different from orders because invoices may be for older POs
        
        **3. Product Mix (Product-level)**
        - Product performance analysis
        - Can be analyzed by order date, invoice date, or delivery date
        - Visual treemap and detailed drill-down
        
        **Key Concepts:**
        - **Order Entry Value**: Total PO value (based on po_date)
        - **Invoiced Value**: Amount invoiced (based on inv_date) 
        - **Conversion Rate**: Invoiced / Ordered × 100%
        - **Backlog**: Outstanding uninvoiced amount (based on ETD)
        
        **Tips:**
        - Each tab has its own date filter for focused analysis
        - Use entity filter to analyze specific legal entities
        - Export data for offline analysis
        - Refresh to get latest updates
        """)