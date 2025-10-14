"""
Purchase Order Tracking Dashboard
Clean, refactored main page - orchestration only
"""

import streamlit as st
from datetime import datetime
import sys
from pathlib import Path

# Add utils to path
sys.path.append(str(Path(__file__).parent.parent))

from utils.auth import AuthManager
from utils.po_tracking.data_service import PODataService
from utils.po_tracking.filters import render_filters, build_sql_params
from utils.po_tracking.formatters import render_metrics, render_detail_list
from utils.po_tracking.analytics import render_analytics_tab

# Page config
st.set_page_config(
    page_title="PO Tracking",
    page_icon="📊",
    layout="wide"
)

# Check authentication
auth_manager = AuthManager()
if not auth_manager.check_session():
    st.warning("⚠️ Please login to access this page")
    st.stop()

# Initialize data service
data_service = PODataService()

# Page title
st.title("📊 Purchase Order Tracking")

# ====================
# 1. FILTERS SECTION
# ====================
filter_options = data_service.get_filter_options()
filters = render_filters(filter_options)

# Build SQL query from filters
query_parts, params = build_sql_params(filters)

# ====================
# 2. LOAD DATA
# ====================
with st.spinner("Loading PO data..."):
    try:
        po_df = data_service.load_po_data(query_parts, params)
    except Exception as e:
        st.error(f"Failed to load data: {str(e)}")
        st.stop()

# ====================
# 3. DISPLAY RESULTS
# ====================
if po_df is not None and not po_df.empty:
    # Display metrics
    render_metrics(po_df)
    
    # Create tabs (only 2 tabs now)
    tab1, tab2 = st.tabs(["📋 Detailed List", "📈 Analytics"])
    
    with tab1:
        render_detail_list(po_df)
    
    with tab2:
        render_analytics_tab(po_df, data_service)
    
else:
    st.info("No purchase order data found for the selected filters")

# Footer
st.markdown("---")
st.caption(f"Last updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")