# pages/2_📦_CAN_Tracking.py

"""
Container Arrival Note (CAN) Tracking Page

Comprehensive interface for tracking container arrivals and managing stock-in operations.

Key Features:
- Real-time tracking with flexible filtering
- Column configuration with presets
- Dashboard metrics overview
- Analytics and trends visualization
- Exclusion filtering for precise data control
"""

import streamlit as st
import pandas as pd
from datetime import datetime
from utils.auth import AuthManager
from utils.can_tracking.data_service import CANDataService
from utils.can_tracking.column_config import render_column_selector, get_column_display_name
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
st.markdown("Track container arrivals and monitor stock-in operations with advanced filtering")

# ============================================================================
# DATA LOADING
# ============================================================================

with st.spinner("Loading CAN data..."):
    try:
        can_df = can_service.load_can_data()
        filter_options = can_service.get_filter_options()
    except Exception as e:
        st.error(f"Failed to load CAN data: {str(e)}")
        if st.button("🔄 Retry"):
            st.rerun()
        st.stop()

# ============================================================================
# FILTERS
# ============================================================================

if can_df is not None and not can_df.empty:
    with st.expander("🔍 Filters", expanded=True):
        # ====================================================================
        # ROW 1: Date Range | Warehouse | Stock-in Status | CAN Status (Excl)
        # ====================================================================
        col1, col2, col3, col4 = st.columns(4)
        
        # Get default date range
        default_date_range = can_service.get_date_range_defaults(can_df)
        
        with col1:
            st.markdown("**📅 Date Range**")
            arrival_date_range = st.date_input(
                "Arrival Date Range",
                value=default_date_range,
                label_visibility="collapsed"
            )
        
        with col2:
            # Warehouse filter
            st.markdown("**🏭 Warehouse**")
            warehouse_options = filter_options.get('warehouses', [])
            selected_warehouses = st.multiselect(
                "Warehouses",
                options=warehouse_options,
                default=None,
                placeholder="All warehouses",
                label_visibility="collapsed"
            )
        
        with col3:
            # Stock-in Status filter (default: partially_stocked_in for pending items)
            st.markdown("**📋 Calculated Stock-in Status**")
            stockin_status_options = filter_options.get('stocked_in_statuses', [])
            selected_stockin_status = st.multiselect(
                "Calculated Stock-in Status",
                options=stockin_status_options,
                default=['partially_stocked_in'],  # Default: show only pending items
                placeholder="All statuses",
                label_visibility="collapsed"
            )
        
        with col4:
            # CAN Status filter with exclusion
            label_col, excl_col = st.columns([5, 1])
            with label_col:
                st.markdown("**📊 CAN Status**")
            with excl_col:
                excl_can_statuses = st.checkbox("Excl", key="excl_can_status")
            
            can_status_options = filter_options.get('can_statuses', [])
            selected_can_statuses = st.multiselect(
                "CAN Status",
                options=can_status_options,
                default=None,
                placeholder="All statuses",
                label_visibility="collapsed"
            )
        
        # ====================================================================
        # ROW 2: Vendors (Excl) | Vendor Location | Vendor Type
        # ====================================================================
        col1, col2, col3 = st.columns(3)
        
        with col1:
            # Vendor filter with exclusion
            label_col, excl_col = st.columns([5, 1])
            with label_col:
                st.markdown("**🏢 Vendors**")
            with excl_col:
                excl_vendors = st.checkbox("Excl", key="excl_vendors")
            
            vendor_options = filter_options.get('vendors', [])
            selected_vendors = st.multiselect(
                "Vendors",
                options=vendor_options,
                default=None,
                placeholder="All vendors",
                label_visibility="collapsed"
            )
        
        with col2:
            # Vendor Location filter (no exclusion - only 2 values)
            st.markdown("**🌍 Vendor Location**")
            vendor_location_options = filter_options.get('vendor_location_types', [])
            selected_vendor_locations = st.multiselect(
                "Vendor Location",
                options=vendor_location_options,
                default=None,
                placeholder="All locations",
                label_visibility="collapsed"
            )
        
        with col3:
            st.markdown("**🏪 Vendor Type**")
            vendor_type_options = filter_options.get('vendor_types', [])
            selected_vendor_types = st.multiselect(
                "Vendor Types",
                options=vendor_type_options,
                default=None,
                placeholder="All types",
                label_visibility="collapsed"
            )
        
        # ====================================================================
        # ROW 3: Consignees | Products (Excl) | Brands (Excl)
        # ====================================================================
        col1, col2, col3 = st.columns(3)
        
        with col1:
            # Consignee filter
            st.markdown("**📦 Consignees**")
            consignee_options = filter_options.get('consignees', [])
            selected_consignees = st.multiselect(
                "Consignees",
                options=consignee_options,
                default=None,
                placeholder="All consignees",
                label_visibility="collapsed"
            )
        
        with col2:
            # Product filter with exclusion
            label_col, excl_col = st.columns([5, 1])
            with label_col:
                st.markdown("**🏷️ Products**")
            with excl_col:
                excl_products = st.checkbox("Excl", key="excl_products")
            
            product_options = filter_options.get('products', [])
            selected_products = st.multiselect(
                "Products",
                options=product_options,
                default=None,
                placeholder="Search products...",
                label_visibility="collapsed"
            )
        
        with col3:
            # Brand filter with exclusion
            label_col, excl_col = st.columns([5, 1])
            with label_col:
                st.markdown("**🎨 Brands**")
            with excl_col:
                excl_brands = st.checkbox("Excl", key="excl_brands")
            
            brand_options = filter_options.get('brands', [])
            selected_brands = st.multiselect(
                "Brands",
                options=brand_options,
                default=None,
                placeholder="All brands",
                label_visibility="collapsed"
            )

    # ========================================================================
    # APPLY FILTERS
    # ========================================================================
    
    filter_dict = {
        'arrival_date_from': arrival_date_range[0] if len(arrival_date_range) > 0 else None,
        'arrival_date_to': arrival_date_range[1] if len(arrival_date_range) > 1 else arrival_date_range[0],
        'warehouses': selected_warehouses if selected_warehouses else None,
        'vendors': selected_vendors if selected_vendors else None,
        'excl_vendors': excl_vendors,
        'vendor_types': selected_vendor_types if selected_vendor_types else None,
        'vendor_locations': selected_vendor_locations if selected_vendor_locations else None,
        'consignees': selected_consignees if selected_consignees else None,
        'products': selected_products if selected_products else None,
        'excl_products': excl_products,
        'brands': selected_brands if selected_brands else None,
        'excl_brands': excl_brands,
        'can_statuses': selected_can_statuses if selected_can_statuses else None,
        'excl_can_statuses': excl_can_statuses,
        'stocked_in_statuses': selected_stockin_status if selected_stockin_status else None
    }
    
    filtered_df = can_service.apply_filters(can_df, filter_dict)
    
    # Show filter results
    if len(filtered_df) < len(can_df):
        st.info(f"📊 Showing {len(filtered_df):,} of {len(can_df):,} items based on filters")
    
    # ========================================================================
    # DASHBOARD METRICS
    # ========================================================================
    
    if not filtered_df.empty:
        # Calculate metrics on filtered data
        # Note: Default filter shows only 'partially_stocked_in' items
        pending_df = filtered_df[filtered_df['pending_quantity'] > 0]
        
        metrics = calculate_metrics(filtered_df, False, URGENT_DAYS_THRESHOLD, CRITICAL_DAYS_THRESHOLD)
        
        col1, col2, col3, col4, col5, col6 = st.columns(6)
        
        with col1:
            st.metric(
                "Total Items", 
                f"{metrics['total_items']:,}",
                delta=f"{metrics['pending_items']} pending" if metrics['pending_items'] > 0 else "All completed"
            )
        
        with col2:
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
            st.metric(
                "Avg Days Since Arrival",
                f"{metrics['avg_days_all']:.1f}",
                delta=f"{metrics['avg_days']:.1f} for pending" if metrics['avg_days'] > 0 else None
            )
        
        with col6:
            st.metric(
                "Total CANs",
                f"{metrics['unique_cans']:,}",
                delta=f"{metrics['completed_cans']} completed" if metrics['completed_cans'] > 0 else None
            )

        # ====================================================================
        # COLUMN CONFIGURATION
        # ====================================================================
        
        selected_columns = render_column_selector()
        
        # ====================================================================
        # TABS
        # ====================================================================
        
        tab1, tab2 = st.tabs(["📋 CAN List", "📊 Analytics"])
        
        # ====================================================================
        # TAB 1: CAN LIST
        # ====================================================================
        
        with tab1:
            st.subheader("📋 Container Arrival Items")
            
            if not filtered_df.empty and selected_columns:
                # Filter dataframe to selected columns (only available columns)
                available_columns = [col for col in selected_columns if col in filtered_df.columns]
                display_df = filtered_df[available_columns].copy()
                
                # Format date columns
                if 'arrival_date' in display_df.columns:
                    display_df['arrival_date'] = pd.to_datetime(display_df['arrival_date']).dt.strftime('%Y-%m-%d')
                
                # Configure column display
                column_config = {}
                
                # Numeric columns
                numeric_cols = {
                    'days_since_arrival': st.column_config.NumberColumn(
                        get_column_display_name('days_since_arrival'),
                        format="%d days"
                    ),
                    'days_pending': st.column_config.NumberColumn(
                        get_column_display_name('days_pending'),
                        format="%d days"
                    ),
                    'pending_value_usd': st.column_config.NumberColumn(
                        get_column_display_name('pending_value_usd'),
                        format="$%,.0f"
                    ),
                    'landed_cost_usd': st.column_config.NumberColumn(
                        get_column_display_name('landed_cost_usd'),
                        format="$%,.0f"
                    ),
                    'pending_percent': st.column_config.NumberColumn(
                        get_column_display_name('pending_percent'),
                        format="%.0f%%"
                    ),
                    'invoiced_percent': st.column_config.NumberColumn(
                        get_column_display_name('invoiced_percent'),
                        format="%.0f%%"
                    ),
                    'pending_quantity': st.column_config.NumberColumn(
                        get_column_display_name('pending_quantity'),
                        format="%,.0f"
                    ),
                    'arrival_quantity': st.column_config.NumberColumn(
                        get_column_display_name('arrival_quantity'),
                        format="%,.2f"
                    ),
                    'buying_quantity': st.column_config.NumberColumn(
                        get_column_display_name('buying_quantity'),
                        format="%,.2f"
                    ),
                    'standard_quantity': st.column_config.NumberColumn(
                        get_column_display_name('standard_quantity'),
                        format="%,.2f"
                    ),
                    'po_line_arrival_completion_percent': st.column_config.NumberColumn(
                        get_column_display_name('po_line_arrival_completion_percent'),
                        format="%.0f%%"
                    ),
                    'po_line_invoice_completion_percent': st.column_config.NumberColumn(
                        get_column_display_name('po_line_invoice_completion_percent'),
                        format="%.0f%%"
                    )
                }
                
                # Add configured columns that exist in display
                for col, config in numeric_cols.items():
                    if col in available_columns:
                        column_config[col] = config
                
                # Display data
                st.dataframe(
                    display_df,
                    hide_index=True,
                    use_container_width=True,
                    column_config=column_config
                )
                
                # Download button
                st.download_button(
                    label="📥 Download Full List",
                    data=filtered_df.to_csv(index=False).encode('utf-8'),
                    file_name=f"can_tracking_{datetime.now().strftime('%Y%m%d_%H%M')}.csv",
                    mime='text/csv'
                )
            else:
                if not selected_columns:
                    st.info("📋 Please select at least one column to display")
                else:
                    st.info("No data available for the selected filters")
        
        # ====================================================================
        # TAB 2: ANALYTICS
        # ====================================================================
        
        with tab2:
            st.subheader("📊 CAN Analytics & Trends")
            
            # Filter to only pending items for analytics
            analytics_df = filtered_df[filtered_df['pending_quantity'] > 0]
            
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
    st.warning("⚠️ No CAN data available")

# ============================================================================
# FOOTER
# ============================================================================

st.markdown("---")
st.caption(f"Last updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")