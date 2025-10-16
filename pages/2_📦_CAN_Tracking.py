# pages/2_📦_CAN_Tracking.py

"""
Container Arrival Note (CAN) Tracking Page - Refactored
Enhanced with column selection, editing functionality, and email notifications
"""

import streamlit as st
from datetime import datetime
import sys
from pathlib import Path
import pandas as pd

# Add utils to path
sys.path.append(str(Path(__file__).parent.parent))

from utils.auth import AuthManager
from utils.can_tracking.constants import URGENT_DAYS_THRESHOLD, CRITICAL_DAYS_THRESHOLD
from utils.can_tracking.data_service import CANDataService
from utils.can_tracking.filters import render_filters, build_sql_params
from utils.can_tracking.formatters import render_metrics, render_detail_list
from utils.can_tracking.analytics import (
    calculate_metrics,
    create_days_pending_chart,
    create_vendor_location_chart,
    create_vendor_analysis_chart,
    create_daily_trend_chart
)

# ============================================
# PAGE CONFIGURATION
# ============================================
st.set_page_config(
    page_title="CAN Tracking",
    page_icon="📦",
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
can_service = CANDataService()

# ============================================
# HEADER
# ============================================
st.title("📦 Container Arrival Note (CAN) Tracking")
st.markdown("""
Track container arrivals and manage stock-in operations with real-time status updates,
financial analytics, and supply chain visibility.
""")

# ============================================
# FILTERS SECTION
# ============================================
st.markdown("## 🔍 Filters")

filter_options = can_service.get_filter_options()

if not filter_options:
    st.error("Failed to load filter options. Please refresh the page.")
    st.stop()

default_date_range = can_service.get_date_range_defaults(filter_options)
filters = render_filters(filter_options, default_date_range)

# Build SQL query from filters
query_parts, params = build_sql_params(filters)

# ============================================
# LOAD DATA
# ============================================

with st.spinner("📦 Loading CAN data..."):
    try:
        can_df = can_service.load_can_data(query_parts, params)
    except Exception as e:
        st.error(f"❌ Failed to load data: {str(e)}")
        st.exception(e)
        st.stop()

# ============================================
# DISPLAY RESULTS
# ============================================
if can_df is not None and not can_df.empty:
    # Show metrics
    st.markdown("## 📈 Key Metrics")
    render_metrics(can_df, URGENT_DAYS_THRESHOLD, CRITICAL_DAYS_THRESHOLD)
    
    # Create tabs
    tab1, tab2 = st.tabs(["📋 Detailed List", "📊 Analytics"])
    
    with tab1:
        # Pass can_service for editing
        render_detail_list(can_df, data_service=can_service)
    
    with tab2:
        st.subheader("📊 CAN Analytics & Trends")
        
        # Filter to only pending items for analytics
        analytics_df = can_df[can_df['pending_quantity'] > 0]
        
        if not analytics_df.empty:
            col1, col2 = st.columns(2)
            
            with col1:
                st.markdown("#### Days Pending Distribution")
                fig1 = create_days_pending_chart(analytics_df)
                if fig1:
                    st.plotly_chart(fig1, use_container_width=True)
                else:
                    st.info("No data available for this chart")
            
            with col2:
                st.markdown("#### Value by Vendor Location")
                fig2 = create_vendor_location_chart(analytics_df)
                if fig2:
                    st.plotly_chart(fig2, use_container_width=True)
                else:
                    st.info("No data available for this chart")
            
            st.markdown("---")
            st.markdown("#### Top 10 Vendors by Pending Value")
            
            fig3, vendor_table = create_vendor_analysis_chart(analytics_df)
            if fig3:
                st.plotly_chart(fig3, use_container_width=True)
                
                if vendor_table is not None and not vendor_table.empty:
                    st.dataframe(vendor_table, use_container_width=True, hide_index=True)
            else:
                st.info("No vendor data available")
            
            st.markdown("---")
            st.markdown("#### Daily Arrival Trend (Last 30 days)")
            
            fig4 = create_daily_trend_chart(analytics_df)
            if fig4:
                st.plotly_chart(fig4, use_container_width=True)
            else:
                st.info("No trend data available")
        else:
            st.info("ℹ️ No pending items to analyze with the selected filters")

else:
    st.info("""
    ℹ️ No CAN data found for the selected filters.
    
    **Suggestions:**
    - Try adjusting your filter criteria
    - Check if the date range is too narrow
    - Verify vendor or product selections
    """)

# ============================================
# FOOTER
# ============================================

footer_col1, footer_col2, footer_col3 = st.columns(3)

with footer_col1:
    st.caption(f"🕐 Last updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

with footer_col2:
    if can_df is not None and not can_df.empty:
        st.caption(f"📊 Loaded {len(can_df):,} records")

with footer_col3:
    if 'user_email' in st.session_state:
        st.caption(f"👤 {st.session_state.user_email}")

# ============================================
# SIDEBAR INFO
# ============================================
with st.sidebar:
    st.markdown("---")
    
    st.markdown("## 📄 Actions")
    
    if st.button("🔃 Refresh Data", use_container_width=True):
        st.cache_data.clear()
        st.rerun()
    
    if st.button("🏠 Reset Filters", use_container_width=True):
        # Clear filter-related session state
        for key in list(st.session_state.keys()):
            if key.startswith('excl_'):
                del st.session_state[key]
        st.rerun()
    
    st.markdown("---")
    
    # Data quality indicators
    if can_df is not None and not can_df.empty:
        st.markdown("## 📊 Data Quality")
        
        # Check for overdue arrivals
        if 'arrival_date' in can_df.columns:
            overdue_count = sum(pd.to_datetime(can_df['arrival_date'], errors='coerce') < datetime.now())
            if overdue_count > 0:
                st.warning(f"⚠️ {overdue_count} overdue arrivals")
        
        # Check for urgent items
        pending_df = can_df[can_df['pending_quantity'] > 0]
        urgent_items = len(pending_df[pending_df['days_since_arrival'] > URGENT_DAYS_THRESHOLD])
        if urgent_items > 0:
            st.warning(f"⚠️ {urgent_items} urgent items (>{URGENT_DAYS_THRESHOLD}d)")
        
        # Check for critical items
        critical_items = len(pending_df[pending_df['days_since_arrival'] > CRITICAL_DAYS_THRESHOLD])
        if critical_items > 0:
            st.error(f"🚨 {critical_items} critical items (>{CRITICAL_DAYS_THRESHOLD}d)")