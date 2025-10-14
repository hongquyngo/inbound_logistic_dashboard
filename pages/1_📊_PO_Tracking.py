"""
Purchase Order Tracking Dashboard
Enhanced with column selection and ETD/ETA editing
"""

import streamlit as st
from datetime import datetime
import sys
from pathlib import Path
import pandas as pd

# Add utils to path
sys.path.append(str(Path(__file__).parent.parent))

from utils.auth import AuthManager
from utils.po_tracking.data_service import PODataService
from utils.po_tracking.filters import render_filters, build_sql_params
from utils.po_tracking.formatters import render_metrics, render_detail_list
from utils.po_tracking.analytics import render_analytics_tab

# ============================================
# PAGE CONFIGURATION
# ============================================
st.set_page_config(
    page_title="PO Tracking",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ============================================
# AUTHENTICATION
# ============================================
auth_manager = AuthManager()
if not auth_manager.check_session():
    st.warning("⚠️ Please login to access this page")
    st.stop()

# Store user info in session state for audit trail
if 'user_email' not in st.session_state:
    st.session_state.user_email = auth_manager.get_user_email() if hasattr(auth_manager, 'get_user_email') else 'system'

# Ensure keycloak_id is available for database operations
if 'user_keycloak_id' not in st.session_state:
    st.session_state.user_keycloak_id = auth_manager.get_user_keycloak_id()

# ============================================
# INITIALIZE SERVICES
# ============================================
data_service = PODataService()

# ============================================
# HEADER
# ============================================
st.title("📊 Purchase Order Tracking")
st.markdown("""
Track and manage purchase orders with real-time status updates, 
financial analytics, and supply chain visibility.
""")

st.markdown("---")

# ============================================
# FILTERS SECTION
# ============================================
st.markdown("## 🔍 Filters")

filter_options = data_service.get_filter_options()

if not filter_options:
    st.error("Failed to load filter options. Please refresh the page.")
    st.stop()

filters = render_filters(filter_options)

# Build SQL query from filters
query_parts, params = build_sql_params(filters)

# ============================================
# LOAD DATA
# ============================================
st.markdown("---")

with st.spinner("🔄 Loading purchase order data..."):
    try:
        po_df = data_service.load_po_data(query_parts, params)
    except Exception as e:
        st.error(f"❌ Failed to load data: {str(e)}")
        st.exception(e)
        st.stop()

# ============================================
# DISPLAY RESULTS
# ============================================
if po_df is not None and not po_df.empty:
    # Show metrics
    st.markdown("## 📈 Key Metrics")
    render_metrics(po_df)
    
    st.markdown("---")
    
    # Create tabs
    tab1, tab2 = st.tabs(["📋 Detailed List", "📊 Analytics"])
    
    with tab1:
        # Pass data_service for ETD/ETA editing
        render_detail_list(po_df, data_service=data_service)
    
    with tab2:
        render_analytics_tab(po_df, data_service)
    
else:
    st.info("""
    ℹ️ No purchase order data found for the selected filters.
    
    **Suggestions:**
    - Try adjusting your filter criteria
    - Check if the date range is too narrow
    - Verify vendor or product selections
    """)

# ============================================
# FOOTER
# ============================================
st.markdown("---")

footer_col1, footer_col2, footer_col3 = st.columns(3)

with footer_col1:
    st.caption(f"🕐 Last updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

with footer_col2:
    if po_df is not None and not po_df.empty:
        st.caption(f"📊 Loaded {len(po_df):,} records")

with footer_col3:
    if 'user_email' in st.session_state:
        st.caption(f"👤 {st.session_state.user_email}")

# ============================================
# SIDEBAR INFO
# ============================================
with st.sidebar:
    st.markdown("## ℹ️ About")
    st.markdown("""
    **Purchase Order Tracking Dashboard**
    
    This dashboard provides:
    - Real-time PO status monitoring
    - Financial analytics & reporting
    - Supply & demand analysis
    - ETD/ETA date management
    - Customizable column views
    
    **Features:**
    - ✏️ Edit ETD/ETA dates directly
    - 📊 Flexible column selection
    - 💰 Financial insights
    - 📦 Supply chain visibility
    - 📥 Export to CSV/Excel
    """)
    
    st.markdown("---")
    
    st.markdown("## 🔄 Actions")
    
    if st.button("🔃 Refresh Data", use_container_width=True):
        st.cache_data.clear()
        st.rerun()
    
    if st.button("🏠 Reset Filters", use_container_width=True):
        # Clear filter-related session state
        for key in list(st.session_state.keys()):
            if key.startswith('filter_') or key.startswith('excl_'):
                del st.session_state[key]
        st.rerun()
    
    st.markdown("---")
    
    # Data quality indicators
    if po_df is not None and not po_df.empty:
        st.markdown("## 📊 Data Quality")
        
        # Check for overdue POs
        if 'etd' in po_df.columns:
            overdue_count = sum(pd.to_datetime(po_df['etd'], errors='coerce') < datetime.now())
            if overdue_count > 0:
                st.warning(f"⚠️ {overdue_count} overdue ETDs")
        
        # Check for over-delivered
        if 'is_over_delivered' in po_df.columns:
            over_delivered = sum(po_df['is_over_delivered'] == 'Y')
            if over_delivered > 0:
                st.info(f"ℹ️ {over_delivered} over-delivered")
        
        # Check for cancellations
        if 'has_cancellation' in po_df.columns:
            cancellations = sum(po_df['has_cancellation'] == 'Y')
            if cancellations > 0:
                st.info(f"ℹ️ {cancellations} with cancellations")