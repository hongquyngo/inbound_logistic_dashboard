# pages/2_📦_CAN_Tracking.py

"""
Container Arrival Note (CAN) Tracking Page

Simplified and clean interface for tracking container arrivals and pending stock-in operations.

Key Features:
- Real-time pending stock-in tracking
- Simplified filtering system
- Dashboard metrics overview
- Basic analytics and trends
"""

import streamlit as st
import pandas as pd
from datetime import datetime
from utils.auth import AuthManager
from utils.can_tracking.data_service import CANDataService
from utils.can_tracking.analytics import (
    calculate_metrics,
    create_days_pending_chart,
    create_vendor_location_chart,
    create_vendor_analysis_chart,
    create_daily_trend_chart
)

# ============================================================================
# PAGE CONFIGURATION
# ============================================================================

st.set_page_config(
    page_title="CAN Tracking",
    page_icon="📦",
    layout="wide"
)

# ============================================================================
# AUTHENTICATION
# ============================================================================

auth_manager = AuthManager()
if not auth_manager.check_session():
    st.warning("⚠️ Please login to access this page")
    st.stop()

# ============================================================================
# CONSTANTS
# ============================================================================

URGENT_DAYS_THRESHOLD = 7
CRITICAL_DAYS_THRESHOLD = 14

# ============================================================================
# INITIALIZE SERVICES
# ============================================================================

can_service = CANDataService()

# ============================================================================
# PAGE HEADER
# ============================================================================

st.title("📦 Container Arrival Note (CAN) Tracking")
st.markdown("Track container arrivals and monitor pending stock-in operations")

# ============================================================================
# VIEW TOGGLE
# ============================================================================

col1, col2 = st.columns([1, 3])
with col1:
    show_pending_only = st.checkbox(
        "Show Pending Items Only", 
        value=True,
        help="Uncheck to see all items including completed stock-in"
    )
with col2:
    if not show_pending_only:
        st.info("ℹ️ Showing all items (including completed)")

# ============================================================================
# DATA LOADING
# ============================================================================

with st.spinner("Loading CAN data..."):
    try:
        can_df = can_service.load_can_data(pending_only=show_pending_only)
        filter_options = can_service.get_filter_options()
    except Exception as e:
        st.error(f"Failed to load CAN data: {str(e)}")
        st.stop()

# ============================================================================
# DASHBOARD METRICS
# ============================================================================

if can_df is not None and not can_df.empty:
    metrics = calculate_metrics(can_df, show_pending_only, URGENT_DAYS_THRESHOLD, CRITICAL_DAYS_THRESHOLD)
    
    col1, col2, col3, col4, col5, col6 = st.columns(6)
    
    with col1:
        if show_pending_only:
            st.metric("Total Pending Items", f"{metrics['total_items']:,}")
        else:
            st.metric(
                "Total Items", 
                f"{metrics['total_items']:,}",
                delta=f"{metrics['pending_items']} pending" if metrics['pending_items'] > 0 else "All completed"
            )
    
    with col2:
        if show_pending_only:
            st.metric("Total Pending Value", f"${metrics['total_value']/1000:.0f}K")
        else:
            st.metric(
                "Total Arrived Value",
                f"${metrics['arrived_value']/1000:.0f}K",
                delta=f"${metrics['total_value']/1000:.0f}K pending" if metrics['total_value'] > 0 else None
            )
    
    with col3:
        st.metric(
            f"Urgent Items (>{URGENT_DAYS_THRESHOLD} days)", 
            f"{metrics['urgent_items']:,}",
            delta_color="inverse" if metrics['urgent_items'] > 0 else "off"
        )
    
    with col4:
        st.metric(
            f"Critical Items (>{CRITICAL_DAYS_THRESHOLD} days)", 
            f"{metrics['critical_items']:,}",
            delta_color="inverse" if metrics['critical_items'] > 0 else "off"
        )
    
    with col5:
        if show_pending_only:
            st.metric("Avg Days Pending", f"{metrics['avg_days']:.1f}")
        else:
            st.metric(
                "Avg Days Since Arrival",
                f"{metrics['avg_days_all']:.1f}",
                delta=f"{metrics['avg_days']:.1f} for pending" if metrics['avg_days'] > 0 else None
            )
    
    with col6:
        if show_pending_only:
            st.metric("Unique CANs", f"{metrics['unique_cans']:,}")
        else:
            st.metric(
                "Total CANs",
                f"{metrics['unique_cans']:,}",
                delta=f"{metrics['completed_cans']} completed" if metrics['completed_cans'] > 0 else None
            )

    # ========================================================================
    # FILTERS
    # ========================================================================
    
    with st.expander("🔍 Filters", expanded=True):
        col1, col2, col3 = st.columns(3)
        
        # Get default date range
        default_date_range = can_service.get_date_range_defaults(can_df)
        
        with col1:
            st.markdown("**📅 Date & Time**")
            arrival_date_range = st.date_input(
                "Arrival Date Range",
                value=default_date_range
            )
            
            # Stock-in status filter (only for all items view)
            if not show_pending_only:
                stockin_status_options = filter_options.get('stocked_in_statuses', [])
                selected_stockin_status = st.multiselect(
                    "Stock-in Status",
                    options=stockin_status_options,
                    default=None,
                    placeholder="All statuses"
                )
            else:
                selected_stockin_status = []
        
        with col2:
            st.markdown("**🏢 Vendor Information**")
            vendor_options = filter_options.get('vendors', [])
            selected_vendors = st.multiselect(
                "Vendors",
                options=vendor_options,
                default=None,
                placeholder="All vendors"
            )
            
            vendor_type_options = filter_options.get('vendor_types', [])
            selected_vendor_types = st.multiselect(
                "Vendor Types",
                options=vendor_type_options,
                default=None,
                placeholder="All types"
            )
            
            vendor_location_options = filter_options.get('vendor_location_types', [])
            selected_vendor_locations = st.multiselect(
                "Vendor Location",
                options=vendor_location_options,
                default=None,
                placeholder="All locations"
            )
        
        with col3:
            st.markdown("**📦 Product & Status**")
            consignee_options = filter_options.get('consignees', [])
            selected_consignees = st.multiselect(
                "Consignees",
                options=consignee_options,
                default=None,
                placeholder="All consignees"
            )
            
            product_options = filter_options.get('products', [])
            selected_products = st.multiselect(
                "Products",
                options=product_options,
                default=None,
                placeholder="All products"
            )
            
            status_options = filter_options.get('can_statuses', [])
            selected_statuses = st.multiselect(
                "CAN Status",
                options=status_options,
                default=None,
                placeholder="All statuses"
            )

    # ========================================================================
    # APPLY FILTERS
    # ========================================================================
    
    filter_dict = {
        'arrival_date_from': arrival_date_range[0] if len(arrival_date_range) > 0 else None,
        'arrival_date_to': arrival_date_range[1] if len(arrival_date_range) > 1 else arrival_date_range[0],
        'vendors': selected_vendors if selected_vendors else None,
        'vendor_types': selected_vendor_types if selected_vendor_types else None,
        'vendor_location_types': selected_vendor_locations if selected_vendor_locations else None,
        'consignees': selected_consignees if selected_consignees else None,
        'products': selected_products if selected_products else None,
        'can_statuses': selected_statuses if selected_statuses else None,
        'stocked_in_statuses': selected_stockin_status if not show_pending_only and selected_stockin_status else None
    }
    
    filtered_df = can_service.apply_filters(can_df, filter_dict)
    
    # Show filter results
    if len(filtered_df) < len(can_df):
        st.info(f"📊 Showing {len(filtered_df):,} of {len(can_df):,} items based on filters")
    
    # ========================================================================
    # TABS
    # ========================================================================
    
    tab1, tab2 = st.tabs(["📋 Pending List", "📊 Analytics"])
    
    # ========================================================================
    # TAB 1: PENDING LIST
    # ========================================================================
    
    with tab1:
        if show_pending_only:
            st.subheader("📋 Pending Stock-in Items")
        else:
            st.subheader("📋 All Container Arrival Items")
        
        if not filtered_df.empty:
            # Show/hide vendor details toggle
            show_vendor_details = st.checkbox("Show Vendor Details", value=False)
            
            # Select display columns
            if show_vendor_details:
                display_columns = [
                    'arrival_note_number', 'arrival_date', 'days_since_arrival',
                    'vendor', 'vendor_type', 'vendor_location_type', 'vendor_country_name',
                    'consignee', 'po_number', 'product_name', 'pt_code',
                    'pending_quantity', 'pending_value_usd', 'pending_percent'
                ]
            else:
                display_columns = [
                    'arrival_note_number', 'arrival_date', 'days_since_arrival',
                    'vendor', 'po_number', 'product_name', 'pt_code',
                    'pending_quantity', 'pending_value_usd', 'pending_percent'
                ]
            
            # Add stock-in status if showing all items
            if not show_pending_only:
                display_columns.append('stocked_in_status')
            
            display_columns.append('can_status')
            
            # Create display dataframe
            display_df = filtered_df[display_columns].copy()
            
            # Format date column
            display_df['arrival_date'] = pd.to_datetime(display_df['arrival_date']).dt.strftime('%Y-%m-%d')
            
            # Display data
            st.dataframe(
                display_df,
                hide_index=True,
                use_container_width=True,
                column_config={
                    "days_since_arrival": st.column_config.NumberColumn(
                        "Days Since Arrival",
                        help="Number of days since arrival",
                        format="%d days",
                    ),
                    "pending_value_usd": st.column_config.NumberColumn(
                        "Pending Value USD",
                        format="$%,.0f",
                    ),
                    "pending_percent": st.column_config.NumberColumn(
                        "Pending %",
                        format="%.0f%%",
                    ),
                    "pending_quantity": st.column_config.NumberColumn(
                        "Pending Quantity",
                        format="%,.0f",
                    )
                }
            )
            
            # Download button
            file_suffix = "pending" if show_pending_only else "all"
            st.download_button(
                label="📥 Download Full List",
                data=filtered_df.to_csv(index=False).encode('utf-8'),
                file_name=f"can_{file_suffix}_{datetime.now().strftime('%Y%m%d_%H%M')}.csv",
                mime='text/csv'
            )
        else:
            st.info("No data available for the selected filters")
    
    # ========================================================================
    # TAB 2: ANALYTICS
    # ========================================================================
    
    with tab2:
        st.subheader("📊 CAN Analytics & Trends")
        
        if not filtered_df.empty:
            col1, col2 = st.columns(2)
            
            with col1:
                st.markdown("#### Days Pending Distribution")
                fig1 = create_days_pending_chart(filtered_df)
                if fig1:
                    st.plotly_chart(fig1, use_container_width=True)
                else:
                    st.info("No data available for this chart")
            
            with col2:
                st.markdown("#### Value by Vendor Location")
                fig2 = create_vendor_location_chart(filtered_df)
                if fig2:
                    st.plotly_chart(fig2, use_container_width=True)
                else:
                    st.info("No data available for this chart")
            
            st.markdown("---")
            st.markdown("#### Top 10 Vendors by Pending Value")
            
            fig3, vendor_table = create_vendor_analysis_chart(filtered_df)
            if fig3:
                st.plotly_chart(fig3, use_container_width=True)
                
                if vendor_table is not None and not vendor_table.empty:
                    st.dataframe(vendor_table, use_container_width=True, hide_index=True)
            else:
                st.info("No vendor data available")
            
            st.markdown("---")
            st.markdown("#### Daily Arrival Trend (Last 30 days)")
            
            fig4 = create_daily_trend_chart(filtered_df)
            if fig4:
                st.plotly_chart(fig4, use_container_width=True)
            else:
                st.info("No trend data available")
        else:
            st.info("No data available for analytics with the selected filters")

else:
    st.warning("⚠️ No CAN data available")

# ============================================================================
# FOOTER
# ============================================================================

st.markdown("---")
st.caption(f"Last updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")