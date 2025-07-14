# pages/2_📦_CAN_Management.py

import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
from utils.auth import AuthManager
from utils.data_loader import InboundDataLoader
import plotly.express as px
import plotly.graph_objects as go

# Page config
st.set_page_config(
    page_title="CAN Management",
    page_icon="📦",
    layout="wide"
)

# Check authentication
auth_manager = AuthManager()
if not auth_manager.check_session():
    st.warning("⚠️ Please login to access this page")
    st.stop()

# Initialize data loader
data_loader = InboundDataLoader()

st.title("📦 Container Arrival Note (CAN) Management")
st.markdown("Manage container arrivals and stock-in status")

# View Options
col1, col2, col3 = st.columns([1, 1, 2])
with col1:
    show_pending_only = st.checkbox("Show Pending Items Only", 
                                  value=True,
                                  help="Uncheck to see all items including completed stock-in")
    
with col2:
    if not show_pending_only:
        st.info("Showing all items (including completed)")

# Load data based on view option
with st.spinner("Loading CAN data..."):
    if show_pending_only:
        can_df = data_loader.load_can_pending_data()
        can_summary = data_loader.get_pending_stockin_summary(pending_only=True)
        vendor_summary = data_loader.get_can_vendor_summary(pending_only=True)
    else:
        can_df = data_loader.load_can_pending_data({'pending_only': False})
        can_summary = data_loader.get_pending_stockin_summary(pending_only=False)
        vendor_summary = data_loader.get_can_vendor_summary(pending_only=False)

# Display metrics
if can_df is not None and not can_df.empty:
    # Top metrics
    col1, col2, col3, col4, col5, col6 = st.columns(6)
    
    with col1:
        total_items = len(can_df)
        if show_pending_only:
            st.metric("Total Pending Items", f"{total_items:,}")
        else:
            pending_items = len(can_df[can_df['pending_quantity'] > 0])
            st.metric("Total Items", f"{total_items:,}", 
                     delta=f"{pending_items} pending" if pending_items > 0 else "All completed")
    
    with col2:
        if show_pending_only:
            total_value = can_df['pending_value_usd'].sum()
            st.metric("Total Pending Value", f"${total_value/1000:.0f}K")
        else:
            pending_value = can_df[can_df['pending_quantity'] > 0]['pending_value_usd'].sum()
            arrived_value = can_df['landed_cost_usd'].sum()
            st.metric("Total Arrived Value", f"${arrived_value/1000:.0f}K",
                     delta=f"${pending_value/1000:.0f}K pending" if pending_value > 0 else None)
    
    with col3:
        urgent_items = len(can_df[(can_df['days_since_arrival'] > 7) & (can_df['pending_quantity'] > 0)])
        st.metric("Urgent Items (>7 days)", f"{urgent_items:,}", 
                 delta_color="inverse" if urgent_items > 0 else "off")
    
    with col4:
        critical_items = len(can_df[(can_df['days_since_arrival'] > 14) & (can_df['pending_quantity'] > 0)])
        st.metric("Critical Items (>14 days)", f"{critical_items:,}",
                 delta_color="inverse" if critical_items > 0 else "off")
    
    with col5:
        if show_pending_only:
            avg_days = can_df['days_since_arrival'].mean()
            st.metric("Avg Days Pending", f"{avg_days:.1f}")
        else:
            avg_days_pending = can_df[can_df['pending_quantity'] > 0]['days_since_arrival'].mean() if not can_df[can_df['pending_quantity'] > 0].empty else 0
            avg_days_all = can_df['days_since_arrival'].mean()
            st.metric("Avg Days Since Arrival", f"{avg_days_all:.1f}",
                     delta=f"{avg_days_pending:.1f} for pending" if avg_days_pending > 0 else None)
    
    with col6:
        unique_cans = can_df['arrival_note_number'].nunique()
        if show_pending_only:
            st.metric("Unique CANs", f"{unique_cans:,}")
        else:
            completed_cans = can_df[can_df['pending_quantity'] == 0]['arrival_note_number'].nunique()
            st.metric("Total CANs", f"{unique_cans:,}",
                     delta=f"{completed_cans} completed" if completed_cans > 0 else None)

    # Filters
    with st.expander("🔍 Filters", expanded=True):
        col1, col2, col3, col4 = st.columns(4)
        
        # Initialize filter variables
        selected_stockin_status = []
        
        with col1:
            # Arrival date range
            arrival_date_range = st.date_input(
                "Arrival Date Range",
                value=(datetime.now().date() - timedelta(days=30), datetime.now().date()),
                max_value=datetime.now().date()
            )
            
            # Days pending range
            max_days = int(can_df['days_since_arrival'].max()) if not can_df.empty else 30
            if show_pending_only:
                days_pending_range = st.slider(
                    "Days Since Arrival",
                    min_value=0,
                    max_value=max_days,
                    value=(0, 30),
                    step=1
                )
            else:
                days_pending_range = st.slider(
                    "Days Since Arrival",
                    min_value=0,
                    max_value=max_days,
                    value=(0, max_days),
                    step=1
                )
                
                # Stock-in status filter for all items view
                stockin_status_options = can_df['stocked_in_status'].unique().tolist() if not can_df.empty else []
                selected_stockin_status = st.multiselect(
                    "Stock-in Status",
                    options=stockin_status_options,
                    default=None,
                    placeholder="All statuses"
                )
        
        with col2:
            # Vendor filters
            vendor_options = sorted(can_df['vendor'].unique().tolist()) if not can_df.empty else []
            selected_vendors = st.multiselect(
                "Vendors",
                options=vendor_options,
                default=None,
                placeholder="All vendors"
            )
            
            vendor_type_options = can_df['vendor_type'].unique().tolist() if not can_df.empty else []
            selected_vendor_types = st.multiselect(
                "Vendor Types",
                options=vendor_type_options,
                default=None,
                placeholder="All types"
            )
            
            vendor_location_options = can_df['vendor_location_type'].unique().tolist() if not can_df.empty else []
            selected_vendor_locations = st.multiselect(
                "Vendor Location",
                options=vendor_location_options,
                default=None,
                placeholder="All locations"
            )
        
        with col3:
            # Consignee & Product filters
            consignee_options = sorted(can_df['consignee'].unique().tolist()) if not can_df.empty else []
            selected_consignees = st.multiselect(
                "Consignees",
                options=consignee_options,
                default=None,
                placeholder="All consignees"
            )
            
            product_options = sorted(can_df['product_name'].unique().tolist()) if not can_df.empty else []
            selected_products = st.multiselect(
                "Products",
                options=product_options,
                default=None,
                placeholder="All products"
            )
            
            status_options = can_df['can_status'].unique().tolist() if not can_df.empty else []
            selected_statuses = st.multiselect(
                "CAN Status",
                options=status_options,
                default=None,
                placeholder="All statuses"
            )
        
        with col4:
            # PO Type & Quick filters
            po_type_options = can_df['po_type'].unique().tolist() if not can_df.empty else []
            selected_po_types = st.multiselect(
                "PO Types",
                options=po_type_options,
                default=None,
                placeholder="All PO types"
            )
            
            quick_filters = st.multiselect(
                "Quick Filters",
                options=[
                    "Urgent Only (>7 days pending)",
                    "Critical Only (>14 days pending)",
                    "High Value (>$10K)",
                    "International Vendors Only",
                    "Internal Vendors Only",
                    "Today's Arrivals"
                ],
                default=None
            )
            
            sort_by = st.selectbox(
                "Sort By",
                options=[
                    "Days Pending (Desc)",
                    "Days Pending (Asc)",
                    "Value (Desc)",
                    "Value (Asc)",
                    "Quantity (Desc)",
                    "Arrival Date (Recent)"
                ],
                index=0
            )

    # Apply filters button
    if st.button("🔄 Apply Filters", type="primary", use_container_width=True):
        st.session_state.filters_applied = True

    # Apply filters to dataframe
    can_df['arrival_date'] = pd.to_datetime(can_df['arrival_date'])
    filtered_df = can_df[
        (can_df['arrival_date'].dt.date >= arrival_date_range[0]) &
        (can_df['arrival_date'].dt.date <= arrival_date_range[1])
    ]
    
    # Days pending filter
    filtered_df = filtered_df[
        (filtered_df['days_since_arrival'] >= days_pending_range[0]) &
        (filtered_df['days_since_arrival'] <= days_pending_range[1])
    ]
    
    # Apply other filters
    if not show_pending_only and selected_stockin_status:
        filtered_df = filtered_df[filtered_df['stocked_in_status'].isin(selected_stockin_status)]
    
    if selected_vendors:
        filtered_df = filtered_df[filtered_df['vendor'].isin(selected_vendors)]
    
    if selected_vendor_types:
        filtered_df = filtered_df[filtered_df['vendor_type'].isin(selected_vendor_types)]
    
    if selected_vendor_locations:
        filtered_df = filtered_df[filtered_df['vendor_location_type'].isin(selected_vendor_locations)]
    
    if selected_consignees:
        filtered_df = filtered_df[filtered_df['consignee'].isin(selected_consignees)]
    
    if selected_products:
        filtered_df = filtered_df[filtered_df['product_name'].isin(selected_products)]
    
    if selected_statuses:
        filtered_df = filtered_df[filtered_df['can_status'].isin(selected_statuses)]
    
    if selected_po_types:
        filtered_df = filtered_df[filtered_df['po_type'].isin(selected_po_types)]
    
    # Quick filters
    if "Urgent Only (>7 days pending)" in quick_filters:
        filtered_df = filtered_df[(filtered_df['days_since_arrival'] > 7) & (filtered_df['pending_quantity'] > 0)]
    
    if "Critical Only (>14 days pending)" in quick_filters:
        filtered_df = filtered_df[(filtered_df['days_since_arrival'] > 14) & (filtered_df['pending_quantity'] > 0)]
    
    if "High Value (>$10K)" in quick_filters:
        filtered_df = filtered_df[filtered_df['pending_value_usd'] > 10000]
    
    if "International Vendors Only" in quick_filters:
        filtered_df = filtered_df[filtered_df['vendor_location_type'] == 'International']
    
    if "Internal Vendors Only" in quick_filters:
        filtered_df = filtered_df[filtered_df['vendor_type'] == 'Internal']
    
    if "Today's Arrivals" in quick_filters:
        filtered_df = filtered_df[filtered_df['arrival_date'].dt.date == datetime.now().date()]
    
    # Apply sorting
    if sort_by == "Days Pending (Desc)":
        filtered_df = filtered_df.sort_values('days_since_arrival', ascending=False)
    elif sort_by == "Days Pending (Asc)":
        filtered_df = filtered_df.sort_values('days_since_arrival', ascending=True)
    elif sort_by == "Value (Desc)":
        filtered_df = filtered_df.sort_values('pending_value_usd', ascending=False)
    elif sort_by == "Value (Asc)":
        filtered_df = filtered_df.sort_values('pending_value_usd', ascending=True)
    elif sort_by == "Quantity (Desc)":
        filtered_df = filtered_df.sort_values('pending_quantity', ascending=False)
    else:  # Arrival Date (Recent)
        filtered_df = filtered_df.sort_values('arrival_date', ascending=False)
    
    # Show filtered results count
    if len(filtered_df) < len(can_df):
        st.info(f"Showing {len(filtered_df)} of {len(can_df)} items based on filters")
    
    # Create tabs
    tab1, tab2, tab3, tab4, tab5 = st.tabs([
        "📋 Pending List", 
        "📊 Analytics", 
        "🎯 Priority Matrix", 
        "📈 Warehouse Performance", 
        "🏢 Vendor Summary"
    ])
    
    with tab1:
        if show_pending_only:
            st.subheader("📋 Pending Stock-in Items")
        else:
            st.subheader("📋 All Container Arrival Items")
        
        # Bulk actions
        with st.container():
            col1, col2, col3 = st.columns([3, 1, 1])
            
            with col1:
                select_all = st.checkbox("Select All Items")
            
            with col2:
                bulk_action = st.selectbox(
                    "Bulk Action",
                    ["Select Action", "Mark for Stock-in", "Generate Report", "Export Selected"],
                    label_visibility="collapsed"
                )
            
            with col3:
                if st.button("Execute", type="secondary", disabled=(bulk_action == "Select Action")):
                    if bulk_action == "Export Selected":
                        file_suffix = "pending" if show_pending_only else "mixed"
                        st.download_button(
                            label="📥 Download Selected",
                            data=filtered_df.to_csv(index=False).encode('utf-8'),
                            file_name=f"{file_suffix}_stockin_{datetime.now().strftime('%Y%m%d_%H%M')}.csv",
                            mime='text/csv'
                        )
                    else:
                        st.info(f"'{bulk_action}' functionality would be implemented in production")
        
        # Show/hide vendor details
        show_vendor_details = st.checkbox("Show Vendor Details", value=False)
        
        # Display columns
        if show_vendor_details:
            display_columns = [
                'arrival_note_number', 'arrival_date', 'days_since_arrival',
                'vendor', 'vendor_type', 'vendor_location_type', 'vendor_country_name',
                'consignee', 'po_number', 'po_type', 'product_name', 'pt_code',
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
        display_df.insert(0, 'Select', select_all)
        
        # Format date column
        display_df['arrival_date'] = display_df['arrival_date'].dt.strftime('%Y-%m-%d')
        
        # Display data editor
        edited_df = st.data_editor(
            display_df,
            hide_index=True,
            use_container_width=True,
            disabled=display_columns,
            column_config={
                "Select": st.column_config.CheckboxColumn(
                    "Select",
                    help="Select items for bulk actions",
                    default=False,
                ),
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
            file_name=f"can_{file_suffix}_full_{datetime.now().strftime('%Y%m%d')}.csv",
            mime='text/csv'
        )
    
    with tab2:
        st.subheader("📊 Pending Stock-in Analytics")
        
        col1, col2 = st.columns(2)
        
        with col1:
            # Days pending distribution
            st.markdown("#### Days Pending Distribution")
            
            bins = [0, 3, 7, 14, 30, float('inf')]
            labels = ['0-3 days', '4-7 days', '8-14 days', '15-30 days', '>30 days']
            filtered_df['days_category'] = pd.cut(filtered_df['days_since_arrival'], bins=bins, labels=labels)
            
            category_summary = filtered_df.groupby('days_category').agg({
                'can_line_id': 'count',
                'pending_value_usd': 'sum'
            }).reset_index()
            
            fig1 = px.bar(
                category_summary,
                x='days_category',
                y='can_line_id',
                title='Items by Days Pending',
                color='days_category',
                color_discrete_map={
                    '0-3 days': '#2ecc71',
                    '4-7 days': '#f39c12',
                    '8-14 days': '#e67e22',
                    '15-30 days': '#e74c3c',
                    '>30 days': '#c0392b'
                }
            )
            st.plotly_chart(fig1, use_container_width=True)
        
        with col2:
            # Vendor location type distribution
            st.markdown("#### Value by Vendor Location")
            
            location_summary = filtered_df.groupby('vendor_location_type').agg({
                'can_line_id': 'count',
                'pending_value_usd': 'sum'
            }).reset_index()
            
            fig2 = px.pie(
                location_summary,
                values='pending_value_usd',
                names='vendor_location_type',
                title='Pending Value by Vendor Location'
            )
            st.plotly_chart(fig2, use_container_width=True)
        
        # Vendor analysis
        st.markdown("---")
        st.markdown("#### Top 10 Vendors by Pending Value")
        
        vendor_analysis = filtered_df.groupby(['vendor', 'vendor_type', 'vendor_location_type']).agg({
            'arrival_note_number': 'nunique',
            'can_line_id': 'count',
            'pending_quantity': 'sum',
            'pending_value_usd': 'sum',
            'days_since_arrival': 'mean'
        }).reset_index()
        
        vendor_analysis.columns = ['Vendor', 'Type', 'Location', 'CAN Count', 'Line Items', 
                                 'Total Quantity', 'Total Value', 'Avg Days Pending']
        vendor_analysis = vendor_analysis.sort_values('Total Value', ascending=False).head(10)
        
        fig3 = px.bar(
            vendor_analysis,
            x='Vendor',
            y='Total Value',
            color='Avg Days Pending',
            title='Vendor Pending Value with Average Days',
            hover_data=['Type', 'Location'],
            color_continuous_scale='Reds'
        )
        st.plotly_chart(fig3, use_container_width=True)
        
        # Format and display vendor table
        vendor_analysis['Total Value'] = vendor_analysis['Total Value'].apply(lambda x: f"${x:,.0f}")
        vendor_analysis['Avg Days Pending'] = vendor_analysis['Avg Days Pending'].apply(lambda x: f"{x:.1f}")
        
        st.dataframe(vendor_analysis, use_container_width=True, hide_index=True)
    
    with tab3:
        st.subheader("🎯 Priority Matrix")
        st.markdown("Items prioritized by value and urgency")
        
        # Create priority matrix
        matrix_df = filtered_df.copy()
        
        # Create scatter plot
        fig4 = px.scatter(
            matrix_df,
            x='days_since_arrival',
            y='pending_value_usd',
            size='pending_quantity',
            color='vendor_location_type',
            hover_data=['arrival_note_number', 'vendor', 'vendor_type', 'product_name', 'pt_code'],
            title='Value vs Days Pending (Size = Quantity)',
            labels={
                'days_since_arrival': 'Days Since Arrival',
                'pending_value_usd': 'Pending Value (USD)',
                'vendor_location_type': 'Vendor Location'
            }
        )
        
        # Add quadrant lines
        fig4.add_hline(y=5000, line_dash="dash", line_color="gray", opacity=0.5)
        fig4.add_vline(x=7, line_dash="dash", line_color="gray", opacity=0.5)
        
        # Add quadrant labels
        fig4.add_annotation(x=3, y=15000, text="Low Priority", showarrow=False)
        fig4.add_annotation(x=15, y=15000, text="Medium Priority", showarrow=False)
        fig4.add_annotation(x=3, y=2000, text="Watch List", showarrow=False)
        fig4.add_annotation(x=15, y=2000, text="High Priority", showarrow=False)
        
        st.plotly_chart(fig4, use_container_width=True)
        
        # Priority recommendations
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown("#### 🔴 High Priority Items")
            high_priority = matrix_df[(matrix_df['days_since_arrival'] > 7) & (matrix_df['pending_value_usd'] < 5000)]
            if not high_priority.empty:
                st.dataframe(
                    high_priority[['arrival_note_number', 'vendor', 'product_name', 
                                 'days_since_arrival', 'pending_value_usd']].head(10),
                    use_container_width=True,
                    hide_index=True
                )
            else:
                st.info("No high priority items found")
        
        with col2:
            st.markdown("#### 🟡 Medium Priority Items")
            medium_priority = matrix_df[(matrix_df['days_since_arrival'] > 7) & (matrix_df['pending_value_usd'] >= 5000)]
            if not medium_priority.empty:
                st.dataframe(
                    medium_priority[['arrival_note_number', 'vendor', 'product_name', 
                                   'days_since_arrival', 'pending_value_usd']].head(10),
                    use_container_width=True,
                    hide_index=True
                )
            else:
                st.info("No medium priority items found")
    
    with tab4:
        st.subheader("📈 Warehouse Performance")
        
        if not can_summary.empty:
            # Performance by CAN status
            st.markdown("#### Processing Performance by Status")
            
            # Create performance summary by status and location
            status_location_summary = can_summary.groupby(['can_status', 'vendor_location_type']).agg({
                'line_items': 'sum',
                'total_pending_value': 'sum',
                'avg_days_pending': 'mean'
            }).reset_index()
            
            fig5 = px.bar(
                status_location_summary,
                x='can_status',
                y='line_items',
                color='vendor_location_type',
                title='Line Items by Status and Vendor Location',
                barmode='group'
            )
            st.plotly_chart(fig5, use_container_width=True)
            
            # Show performance table
            performance_df = can_summary.copy()
            performance_df['total_pending_value'] = performance_df['total_pending_value'].apply(lambda x: f"${x:,.0f}")
            performance_df['avg_days_pending'] = performance_df['avg_days_pending'].apply(lambda x: f"{x:.1f}")
            
            st.dataframe(performance_df, use_container_width=True, hide_index=True)
        
        # Daily arrival trend
        st.markdown("---")
        st.markdown("#### Daily Arrival Trend (Last 30 days)")
        
        # Create daily summary
        daily_df = filtered_df.copy()
        daily_df['arrival_date'] = pd.to_datetime(daily_df['arrival_date'])
        
        daily_summary = daily_df.groupby([daily_df['arrival_date'].dt.date, 'vendor_location_type']).agg({
            'arrival_note_number': 'nunique',
            'can_line_id': 'count',
            'pending_value_usd': 'sum'
        }).reset_index()
        
        daily_summary.columns = ['Date', 'Location Type', 'CAN Count', 'Line Items', 'Value']
        
        # Create line chart
        fig6 = px.line(
            daily_summary,
            x='Date',
            y='CAN Count',
            color='Location Type',
            title='Daily CAN Count by Vendor Location',
            markers=True
        )
        st.plotly_chart(fig6, use_container_width=True)
    
    with tab5:
        st.subheader("🏢 Vendor Summary")
        
        if not vendor_summary.empty:
            # Vendor type distribution
            col1, col2 = st.columns(2)
            
            with col1:
                st.markdown("#### Vendor Type Distribution")
                type_summary = vendor_summary.groupby('vendor_type').agg({
                    'can_count': 'sum',
                    'total_pending_value': 'sum'
                }).reset_index()
                
                fig7 = px.pie(
                    type_summary,
                    values='total_pending_value',
                    names='vendor_type',
                    title='Pending Value by Vendor Type'
                )
                st.plotly_chart(fig7, use_container_width=True)
            
            with col2:
                st.markdown("#### Top Countries by Pending Value")
                country_summary = vendor_summary.groupby('vendor_country_name').agg({
                    'can_count': 'sum',
                    'total_pending_value': 'sum'
                }).reset_index().sort_values('total_pending_value', ascending=False).head(10)
                
                fig8 = px.bar(
                    country_summary,
                    x='vendor_country_name',
                    y='total_pending_value',
                    title='Top 10 Countries by Pending Value'
                )
                st.plotly_chart(fig8, use_container_width=True)
            
            # Vendor detail table
            st.markdown("---")
            st.markdown("#### Vendor Pending Summary")
            
            # Format columns for display
            vendor_display = vendor_summary.copy()
            vendor_display['total_pending_value'] = vendor_display['total_pending_value'].apply(lambda x: f"${x:,.0f}")
            vendor_display['avg_days_pending'] = vendor_display['avg_days_pending'].apply(lambda x: f"{x:.1f}")
            vendor_display['max_days_pending'] = vendor_display['max_days_pending'].apply(lambda x: f"{x:.0f}")
            
            # Rename columns
            vendor_display.columns = ['Vendor', 'Type', 'Location', 'Country', 'CAN Count', 
                                    'Line Items', 'Pending Qty', 'Pending Value', 
                                    'Avg Days', 'Max Days']
            
            st.dataframe(
                vendor_display.sort_values('Pending Value', ascending=False),
                use_container_width=True,
                hide_index=True
            )

else:
    st.warning("No data available")

# Footer
st.markdown("---")
st.caption(f"Last updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")