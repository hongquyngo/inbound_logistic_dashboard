# pages/2_📦_CAN_Tracking.py

"""
Container Arrival Note (CAN) Tracking Page - Batch Update Version
Features:
- Stage multiple CAN edits locally
- Review all changes before applying
- Batch database update and email notifications
- Visual indicators for pending changes
"""

import streamlit as st
from datetime import datetime
import sys
from pathlib import Path
import pandas as pd
import time

sys.path.append(str(Path(__file__).parent.parent))

from utils.auth import AuthManager
from utils.can_tracking.constants import URGENT_DAYS_THRESHOLD, CRITICAL_DAYS_THRESHOLD
from utils.can_tracking.data_service import CANDataService
from utils.can_tracking.filters import render_filters, build_sql_params
from utils.can_tracking.formatters import render_metrics, render_detail_list
from utils.can_tracking.analytics import render_analytics_tab
from utils.can_tracking.pending_changes import get_pending_manager

# ============================================
# TIMING HELPER
# ============================================
def _init_page_timing():
    """Initialize page timing"""
    if '_page_timing' not in st.session_state:
        st.session_state._page_timing = {}
    st.session_state._page_timing['page_start'] = time.time()
    st.session_state._page_timing['steps'] = []

def _log_step(step_name: str):
    """Log a timing step"""
    if '_page_timing' in st.session_state:
        elapsed = time.time() - st.session_state._page_timing['page_start']
        st.session_state._page_timing['steps'].append({
            'step': step_name,
            'elapsed': elapsed,
            'timestamp': datetime.now().strftime('%H:%M:%S.%f')[:-3]
        })

_init_page_timing()

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

if 'user_email' not in st.session_state:
    st.session_state.user_email = auth_manager.get_user_email() if hasattr(auth_manager, 'get_user_email') else 'system'

if 'user_keycloak_id' not in st.session_state:
    st.session_state.user_keycloak_id = auth_manager.get_user_keycloak_id()

# ============================================
# INITIALIZE SERVICES
# ============================================
can_service = CANDataService()
pending_manager = get_pending_manager()

# ============================================
# HEADER
# ============================================
st.title("📦 Container Arrival Note (CAN) Tracking")

# Show pending changes alert if any
if pending_manager.has_pending_changes():
    count = pending_manager.get_change_count()
    st.warning(f"""
    🟡 **{count} pending change{'s' if count > 1 else ''}** - Changes are staged locally and not yet saved to database.
    Click **Apply Changes** at the bottom of the table to commit.
    """)

st.markdown("""
Track container arrivals and manage stock-in operations with real-time status updates,
financial analytics, and supply chain visibility.
""")

# ============================================
# FILTERS SECTION
# ============================================
st.markdown("## 🔍 Filters")

_log_step("Before get_filter_options")
filter_options = can_service.get_filter_options()
_log_step("After get_filter_options")

if not filter_options:
    st.error("Failed to load filter options. Please refresh the page.")
    st.stop()

default_date_range = can_service.get_date_range_defaults(filter_options)
filters = render_filters(filter_options, default_date_range)

query_parts, params = build_sql_params(filters)

# ============================================
# LOAD DATA WITH CACHING
# ============================================

@st.cache_data(ttl=300, show_spinner=False)
def get_cached_can_data(query_parts: str, params_tuple: tuple) -> pd.DataFrame:
    """Wrapper function for caching CAN data"""
    params_dict = dict(params_tuple) if params_tuple else {}
    return can_service.load_can_data(query_parts, params_dict)

_log_step("Before load CAN data")
with st.spinner("📦 Loading CAN data..."):
    try:
        params_tuple = tuple(sorted(params.items())) if params else ()
        
        # Check if we have locally updated DataFrame
        if '_can_df_for_fragment' in st.session_state:
            can_df = st.session_state['_can_df_for_fragment']
            _log_step("Used local DataFrame")
        else:
            can_df = get_cached_can_data(query_parts, params_tuple)
            _log_step("Loaded from database/cache")
            
    except Exception as e:
        st.error(f"❌ Failed to load data: {str(e)}")
        st.exception(e)
        st.stop()

# ============================================
# DISPLAY RESULTS
# ============================================
_log_step("Before render results")

if can_df is not None and not can_df.empty:
    st.markdown("## 📈 Key Metrics")
    render_metrics(can_df, URGENT_DAYS_THRESHOLD, CRITICAL_DAYS_THRESHOLD)
    _log_step("After render_metrics")
    
    tab1, tab2 = st.tabs(["📋 Detailed List", "📊 Analytics"])
    
    with tab1:
        render_detail_list(can_df, data_service=can_service)
        _log_step("After render_detail_list")
    
    with tab2:
        render_analytics_tab(can_df)
        _log_step("After render_analytics_tab")

else:
    st.info("""
    ℹ️ No CAN data found for the selected filters.
    
    **Suggestions:**
    - Try adjusting your filter criteria
    - Check if the date range is too narrow
    - Verify vendor or product selections
    """)

_log_step("Page render complete")

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
    
    st.markdown("## 🔄 Actions")
    
    if st.button("📃 Refresh Data", use_container_width=True):
        # Clear both cache and local state
        st.cache_data.clear()
        if '_can_df_for_fragment' in st.session_state:
            del st.session_state['_can_df_for_fragment']
        if '_analytics_df' in st.session_state:
            del st.session_state['_analytics_df']
        st.rerun()
    
    if st.button("🏠 Reset Filters", use_container_width=True):
        for key in list(st.session_state.keys()):
            if key.startswith('excl_'):
                del st.session_state[key]
        st.rerun()
    
    # Pending changes section
    if pending_manager.has_pending_changes():
        st.markdown("---")
        st.markdown("## 🟡 Pending Changes")
        
        changes = pending_manager.get_all_changes()
        for an, change in changes.items():
            with st.expander(f"📦 {an}", expanded=False):
                st.caption(f"Product: {change.product_name}")
                for c in change.get_changes_summary():
                    st.text(f"• {c}")
                if change.reason:
                    st.caption(f"Reason: {change.reason}")
    
    st.markdown("---")
    
    if can_df is not None and not can_df.empty:
        st.markdown("## 📊 Data Quality")
        
        if 'arrival_date' in can_df.columns:
            overdue_count = sum(pd.to_datetime(can_df['arrival_date'], errors='coerce') < datetime.now())
            if overdue_count > 0:
                st.warning(f"⚠️ {overdue_count} overdue arrivals")
        
        pending_df = can_df[can_df['pending_quantity'] > 0]
        urgent_items = len(pending_df[pending_df['days_since_arrival'] > URGENT_DAYS_THRESHOLD])
        if urgent_items > 0:
            st.warning(f"⚠️ {urgent_items} urgent items (>{URGENT_DAYS_THRESHOLD}d)")
        
        critical_items = len(pending_df[pending_df['days_since_arrival'] > CRITICAL_DAYS_THRESHOLD])
        if critical_items > 0:
            st.error(f"🚨 {critical_items} critical items (>{CRITICAL_DAYS_THRESHOLD}d)")
    
    # ============================================
    # TIMING DEBUG SECTION
    # ============================================
    st.markdown("---")
    st.markdown("## ⏱️ Performance Debug")
    
    if '_page_timing' in st.session_state and st.session_state._page_timing.get('steps'):
        steps = st.session_state._page_timing['steps']
        with st.expander("Page Load Timing", expanded=False):
            prev_elapsed = 0
            for step in steps:
                delta = step['elapsed'] - prev_elapsed
                color = "🟢" if delta < 0.5 else "🟡" if delta < 1.0 else "🔴"
                st.text(f"{color} {step['step']}: +{delta:.3f}s (total: {step['elapsed']:.3f}s)")
                prev_elapsed = step['elapsed']
            
            if steps:
                total = steps[-1]['elapsed']
                st.markdown(f"**Total page load: {total:.3f}s**")
    
    # Show last batch timing if available
    if '_timing_logs' in st.session_state and st.session_state._timing_logs:
        with st.expander("Last Batch Timing", expanded=False):
            for log in st.session_state._timing_logs:
                color = "🟢" if log['elapsed'] < 0.5 else "🟡" if log['elapsed'] < 1.0 else "🔴"
                extra = f" - {log['extra']}" if log['extra'] else ""
                st.text(f"{color} {log['operation']}: {log['elapsed']:.3f}s{extra}")