"""
4_📈_Vendor_Performance.py
Main Vendor Performance Analysis Page - Production Version

Features:
- Financial Analysis with validated metrics
- Product Mix Analysis
- Global vendor filtering with entity support

Version: 3.1
Last Updated: 2025-10-21
"""

import streamlit as st
import pandas as pd
from datetime import datetime
import logging
from typing import Optional

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# ==================== PAGE CONFIGURATION ====================

st.set_page_config(
    page_title="Vendor Performance Analysis",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ==================== AUTHENTICATION CHECK ====================

try:
    from utils.auth import AuthManager
    auth_manager = AuthManager()
    if not auth_manager.check_session():
        st.warning("⚠️ Please login to access this page")
        st.stop()
except ImportError:
    logger.warning("Auth module not found, proceeding without authentication")
except Exception as e:
    logger.error(f"Authentication check failed: {e}")
    st.error("Authentication error. Please refresh the page.")
    st.stop()

# ==================== INITIALIZE DAO ====================

try:
    from utils.vendor_performance.data_access import VendorPerformanceDAO
    from utils.vendor_performance.exceptions import DataAccessError, ValidationError
    
    dao = VendorPerformanceDAO()
    logger.info("DAO initialized successfully")
    
except ImportError as e:
    st.error(f"Missing required module: {e}")
    logger.error(f"Import error: {e}")
    st.stop()
except DataAccessError as e:
    st.error(f"Database connection failed: {e}")
    logger.error(f"DAO initialization failed: {e}")
    st.stop()
except Exception as e:
    st.error(f"Unexpected error during initialization: {e}")
    logger.error(f"Unexpected error: {e}", exc_info=True)
    st.stop()

# ==================== HEADER ====================

st.title("📈 Vendor Performance Analysis")
st.markdown("*Financial metrics with validated currency handling and clear date dimensions*")

# Show last update time
st.caption(f"Last data refresh: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

# ==================== GLOBAL FILTERS SECTION ====================

st.markdown("---")
st.subheader("🔧 Global Configuration")

col1, col2, col3 = st.columns([3, 1, 1])

with col1:
    # Vendor selection
    try:
        vendor_options = dao.get_vendor_list()
        logger.info(f"Loaded {len(vendor_options)} vendors")
    except DataAccessError as e:
        st.error("Failed to load vendor list")
        logger.error(f"Vendor list error: {e}")
        vendor_options = []
    except Exception as e:
        st.error("Unexpected error loading vendors")
        logger.error(f"Unexpected error: {e}", exc_info=True)
        vendor_options = []
    
    if vendor_options:
        vendor_display_options = ["All Vendors"] + vendor_options
        selected_vendor_display = st.selectbox(
            "Select Vendor",
            vendor_display_options,
            help="Choose a specific vendor or view all vendors",
            key="global_vendor_select"
        )
    else:
        selected_vendor_display = "All Vendors"
        st.warning("No vendors found in database")

with col2:
    # Legal Entity filter
    try:
        entity_options = dao.get_entity_list()
        logger.info(f"Loaded {len(entity_options)} entities")
    except Exception as e:
        logger.warning(f"Failed to load entity list: {e}")
        entity_options = []
    
    entity_display_options = ["All Entities"] + entity_options
    selected_entity_display = st.selectbox(
        "Legal Entity",
        entity_display_options,
        help="Filter by legal entity (buyer company)",
        key="global_entity_select"
    )

with col3:
    # Quick actions
    st.markdown("#### Quick Actions")
    if st.button("🔄 Refresh Data", key="refresh_btn"):
        st.cache_data.clear()
        st.rerun()

# ==================== ADVANCED FILTERS ====================

with st.expander("⚙️ Advanced Filters", expanded=False):
    try:
        filter_options = dao.get_filter_options()
        logger.debug(f"Loaded filter options: {filter_options.keys()}")
    except Exception as e:
        logger.warning(f"Failed to load filter options: {e}")
        filter_options = {}
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        vendor_types = st.multiselect(
            "Vendor Type",
            options=filter_options.get('vendor_types', []),
            default=None,
            key="filter_vendor_types"
        )
    
    with col2:
        vendor_locations = st.multiselect(
            "Vendor Location",
            options=filter_options.get('vendor_locations', []),
            default=None,
            key="filter_vendor_locations"
        )
    
    with col3:
        payment_terms = st.multiselect(
            "Payment Terms",
            options=filter_options.get('payment_terms', []),
            default=None,
            key="filter_payment_terms"
        )
    
    with col4:
        # Add status filter
        status_options = [
            "COMPLETED", "IN_PROCESS", "PENDING",
            "PENDING_INVOICING", "PENDING_RECEIPT"
        ]
        order_statuses = st.multiselect(
            "Order Status",
            options=status_options,
            default=None,
            key="filter_order_statuses"
        )

# ==================== EXTRACT FILTER VALUES ====================

# Extract vendor name from display format
selected_vendor_name: Optional[str] = None
if selected_vendor_display != "All Vendors":
    if ' - ' in selected_vendor_display:
        # Format: "CODE - NAME"
        parts = selected_vendor_display.split(' - ', 1)
        if len(parts) == 2:
            selected_vendor_name = parts[1].strip()
        else:
            selected_vendor_name = selected_vendor_display.strip()
    else:
        selected_vendor_name = selected_vendor_display.strip()
    
    logger.info(f"Selected vendor: {selected_vendor_name}")

# Extract entity ID
selected_entity_id: Optional[int] = None
if selected_entity_display != "All Entities":
    try:
        selected_entity_id = dao.get_entity_id_by_display(selected_entity_display)
        logger.info(f"Selected entity ID: {selected_entity_id}")
    except Exception as e:
        logger.warning(f"Could not extract entity ID: {e}")

# Build common filters dictionary
common_filters = {
    'vendor_name': selected_vendor_name,
    'entity_id': selected_entity_id,
    'vendor_types': vendor_types if vendor_types else None,
    'vendor_locations': vendor_locations if vendor_locations else None,
    'payment_terms': payment_terms if payment_terms else None,
    'order_statuses': order_statuses if order_statuses else None
}

# Store in session state for tabs to access
st.session_state['vendor_filters'] = common_filters
st.session_state['selected_vendor_display'] = selected_vendor_display

# Log active filters
active_filters = {k: v for k, v in common_filters.items() if v}
if active_filters:
    logger.info(f"Active filters: {active_filters}")

st.markdown("---")

# ==================== TABS SECTION ====================

# Import tab modules
try:
    from utils.vendor_performance.tabs import tab_financial_analysis
    from utils.vendor_performance.tabs import tab_product_mix
    
    tabs_available = True
    logger.info("Tab modules loaded successfully")
    
except ImportError as e:
    st.error(f"Failed to load tab modules: {e}")
    logger.error(f"Tab import error: {e}", exc_info=True)
    tabs_available = False

if tabs_available:
    tabs = st.tabs([
        "💰 Financial Analysis",
        "📦 Product Mix"
    ])
    
    with tabs[0]:
        try:
            tab_financial_analysis.render(
                dao=dao,
                filters=common_filters,
                vendor_display=selected_vendor_display
            )
        except ValidationError as e:
            st.warning(f"Data validation issue: {str(e)}")
            st.info("Try adjusting the date range or filters")
            logger.warning(f"Financial tab validation error: {e}")
        except DataAccessError as e:
            st.error(f"Error loading financial data: {str(e)}")
            logger.error(f"Financial tab data error: {e}")
        except Exception as e:
            st.error(f"Unexpected error in Financial Analysis: {str(e)}")
            logger.error(f"Financial tab error: {e}", exc_info=True)
    
    with tabs[1]:
        try:
            tab_product_mix.render(
                dao=dao,
                filters=common_filters,
                vendor_display=selected_vendor_display
            )
        except DataAccessError as e:
            st.error(f"Error loading product data: {str(e)}")
            logger.error(f"Product tab data error: {e}")
        except Exception as e:
            st.error(f"Unexpected error in Product Mix: {str(e)}")
            logger.error(f"Product tab error: {e}", exc_info=True)
else:
    st.error("Tab modules are not available. Please check the installation.")

# ==================== FOOTER ====================

st.markdown("---")

col1, col2, col3 = st.columns([2, 1, 1])

with col1:
    st.caption("💡 **Tip**: Use date filters within each tab for period-specific analysis")

with col2:
    st.caption("📊 **Data freshness**: Views updated every 5 minutes")

with col3:
    if st.button("📚 Help", key="help_btn"):
        with st.expander("User Guide", expanded=True):
            st.markdown("""
            ## 📈 Vendor Performance Analysis Guide
            
            ### 🎯 Key Metrics Explained
            
            **Financial Metrics:**
            - **Order Entry**: Total PO value based on PO date
            - **Invoice Amount**: Invoice value based on invoice date
            - **Conversion Rate**: (Invoiced / Order Entry) × 100% (max 100%)
            - **Payment Rate**: (Paid / Invoiced) × 100%
            - **Outstanding**: Order Entry - Invoiced
            
            ### 📅 Date Dimensions
            
            Each metric uses specific date fields for accurate tracking:
            
            | Metric | Date Field | Purpose |
            |--------|------------|---------|
            | Order Entry | PO Date | Track when orders placed |
            | Invoice | Invoice Date | Track when invoiced |
            | Backlog | ETD | Track expected delivery |
            | Payment | Payment Date | Track cash flow |
            
            ### 🎨 Visual Indicators
            
            **Color Coding:**
            - 🟢 Green: Good performance (≥90%)
            - 🟡 Yellow: Fair performance (80-90%)
            - 🔴 Red: Needs attention (<80%)
            
            **Delta Indicators:**
            - ⬆️ Up arrow: Positive change
            - ⬇️ Down arrow: Negative change (inverse for Outstanding)
            
            ### 💡 Best Practices
            
            1. **Start with "This Year"** for YTD analysis
            2. **Use Period Breakdown** to spot trends
            3. **Switch to Cumulative** for overall growth
            4. **Filter by vendor** for detailed analysis
            5. **Export data** for offline analysis
            
            ### ⚠️ Data Validation
            
            The system automatically:
            - Validates currency conversions
            - Caps conversion rates at 100%
            - Flags suspicious values (>$1B)
            - Excludes cancelled orders
            
            ### 🔄 Refresh Frequency
            
            - Reference data: Cached 1 hour
            - Transaction data: Cached 5 minutes
            - Manual refresh: Click "Refresh Data"
            
            ### 📞 Support
            
            For issues or questions, contact:
            - Technical Support: IT Help Desk
            - Business Questions: Finance Team
            """)

# Performance monitoring
if logger.isEnabledFor(logging.DEBUG):
    st.caption(f"Debug: Page rendered at {datetime.now()}")