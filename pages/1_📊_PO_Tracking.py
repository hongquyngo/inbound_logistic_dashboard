# pages/1_📊_PO_Tracking.py

import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
from utils.auth import AuthManager
from utils.data_loader import InboundDataLoader
import plotly.express as px
import plotly.graph_objects as go

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

# Initialize data loader
data_loader = InboundDataLoader()

st.title("📊 Purchase Order Tracking")

# Get filter options FIRST (đặt trước khi tạo filters)
filter_options = data_loader.get_filter_options()

# Filter Section
with st.expander("🔍 Filters", expanded=True):
    col1, col2, col3 = st.columns(3)
    
    with col1:
        # Date range type
        date_type = st.radio(
            "Date Type",
            options=['PO Date', 'ETD', 'ETA'],
            index=1,
            horizontal=True
        )
        
        # IMPROVED: Dynamic date range based on database
        date_ranges = filter_options.get('date_ranges', {})
        
        # Determine min/max dates based on selected date type
        if date_type == 'PO Date':
            db_min_date = date_ranges.get('min_po_date')
            db_max_date = date_ranges.get('max_po_date')
        elif date_type == 'ETD':
            db_min_date = date_ranges.get('min_etd')
            db_max_date = date_ranges.get('max_etd')
        else:  # ETA
            db_min_date = date_ranges.get('min_eta')
            db_max_date = date_ranges.get('max_eta')
        
        # Set default min/max with fallback
        if db_min_date:
            min_date = db_min_date
        else:
            min_date = datetime.now().date() - timedelta(days=365)
            
        if db_max_date:
            max_date = db_max_date
        else:
            max_date = datetime.now().date() + timedelta(days=365)
        
        # Date range input with dynamic min/max
        date_range = st.date_input(
            f"{date_type} Range",
            value=(min_date, max_date),
            min_value=min_date,
            max_value=max_date,
            help=f"Available data range: {min_date} to {max_date}"
        )
    
    with col2:
        # Legal Entity filter với format Code - Name
        legal_entity_options = filter_options.get('legal_entities', [])
        
        selected_legal_entities = st.multiselect(
            "Legal Entity (Buyer)",
            options=legal_entity_options,
            default=None,
            placeholder="All legal entities"
        )
        
        # Vendor filter với format Code - Name
        vendor_options = filter_options.get('vendors', [])
        
        selected_vendors = st.multiselect(
            "Vendors",
            options=vendor_options,
            default=None,
            placeholder="All vendors"
        )

    with col3:
        # Products (hiển thị format PT Code - Name)
        selected_products = st.multiselect(
            "Products",
            options=filter_options.get('products', []),
            default=None,
            placeholder="Search products..."
        )
        
        # Không cần selected_pt_codes nữa vì đã gộp chung
        selected_pt_codes = []  # Keep empty for compatibility
        
        # Brand filter
        selected_brands = st.multiselect(
            "Brands",
            options=filter_options.get('brands', []),
            default=None,
            placeholder="All brands"
        )


    # Second row of filters
    col4, col5, col6 = st.columns(3)
    
    with col4:
        # IMPROVED: Dynamic status filter from database
        status_options = filter_options.get('po_statuses', [
            'PENDING', 'IN_PROCESS', 'PENDING_INVOICING', 
            'PENDING_RECEIPT', 'COMPLETED', 'OVER_DELIVERED'
        ])
        
        selected_status = st.multiselect(
            "PO Status",
            options=status_options,
            default=None,
            placeholder="All statuses"
        )
        
        # Payment terms filter
        selected_payment_terms = st.multiselect(
            "Payment Terms",
            options=filter_options.get('payment_terms', []),
            default=None,
            placeholder="All payment terms"
        )
    
    with col5:
        # IMPROVED: Vendor Category filter from purchase_order_full_view
        vendor_category_options = filter_options.get('vendor_types', ['Internal', 'External'])
        selected_vendor_categories = st.multiselect(
            "Vendor Category",
            options=vendor_category_options,
            default=None,
            placeholder="All categories",
            help="Internal: Vendor companies under PTH | External: Not under PTH"
        )
        
        # IMPROVED: Vendor Location filter from purchase_order_full_view
        vendor_location_options = filter_options.get('vendor_location_types', ['Domestic', 'International'])
        selected_vendor_locations = st.multiselect(
            "Vendor Location",
            options=vendor_location_options,
            default=None,
            placeholder="All locations",
            help="Domestic: Same country | International: Cross-border"
        )
    
    with col6:
        # IMPROVED: Dynamic special filters based on data availability
        special_filter_stats = filter_options.get('special_filter_stats', {})
        
        # Build special filter options dynamically
        special_filter_options = []
        
        if special_filter_stats.get('overdue_count', 0) > 0:
            special_filter_options.append(f"Overdue Only ({special_filter_stats['overdue_count']} items)")
        
        if special_filter_stats.get('over_delivered_count', 0) > 0:
            special_filter_options.append(f"Over-delivered Only ({special_filter_stats['over_delivered_count']} items)")
        
        if special_filter_stats.get('over_invoiced_count', 0) > 0:
            special_filter_options.append(f"Over-invoiced Only ({special_filter_stats['over_invoiced_count']} items)")
        
        # Critical Products luôn available vì check từ delivery_full_view
        special_filter_options.append("Critical Products Only")
        
        special_filters = st.multiselect(
            "Special Filters",
            options=special_filter_options,
            default=None,
            help="Select special conditions to filter"
        )
        
        # Completion range
        completion_range = st.slider(
            "Arrival Completion %",
            min_value=0,
            max_value=100,
            value=(0, 100),
            step=10
        )

# Apply filters button
if st.button("🔄 Apply Filters", type="primary", use_container_width=True):
    st.session_state.filters_applied = True

# Prepare filters - giữ nguyên format "CODE - NAME" như products
filters = {
    'date_from': date_range[0] if len(date_range) >= 1 else None,
    'date_to': date_range[1] if len(date_range) >= 2 else date_range[0],
    'legal_entities': selected_legal_entities if selected_legal_entities else None,  # Giữ nguyên format
    'vendors': selected_vendors if selected_vendors else None,  # Giữ nguyên format
    'pt_codes': selected_pt_codes if selected_pt_codes else None,
    'brands': selected_brands if selected_brands else None,
    'products': selected_products if selected_products else None,  # Giữ nguyên format
    'status': selected_status if selected_status else None,
    'payment_terms': selected_payment_terms if selected_payment_terms else None,
    'vendor_types': selected_vendor_categories if selected_vendor_categories else None,
    'vendor_location_types': selected_vendor_locations if selected_vendor_locations else None,
    # Process special filters
    'overdue_only': any('Overdue Only' in f for f in special_filters),
    'over_delivered_only': any('Over-delivered Only' in f for f in special_filters),
    'over_invoiced_only': any('Over-invoiced Only' in f for f in special_filters),
    'critical_products': 'Critical Products Only' in special_filters
}

# Adjust date filter based on date type
if date_type == 'ETD':
    filters['etd_from'] = filters.pop('date_from')
    filters['etd_to'] = filters.pop('date_to')
elif date_type == 'ETA':
    filters['eta_from'] = filters.pop('date_from')
    filters['eta_to'] = filters.pop('date_to')


# Load data
with st.spinner("Loading PO data..."):
    po_df = data_loader.load_po_data(filters)

if po_df is not None and not po_df.empty:
    # Apply completion range filter
    po_df = po_df[(po_df['arrival_completion_percent'] >= completion_range[0]) & 
                  (po_df['arrival_completion_percent'] <= completion_range[1])]
    
    # Display metrics
    col1, col2, col3, col4, col5, col6 = st.columns(6)
    
    with col1:
        st.metric("Total POs", f"{po_df['po_number'].nunique():,}")
    
    with col2:
        st.metric("Total Lines", f"{len(po_df):,}")
    
    with col3:
        total_value = po_df['total_amount_usd'].sum()
        st.metric("Total Value", f"${total_value/1000000:.1f}M")
    
    with col4:
        outstanding_value = po_df['outstanding_arrival_amount_usd'].sum()
        st.metric("Outstanding", f"${outstanding_value/1000000:.1f}M")
    
    with col5:
        overdue_count = len(po_df[po_df['etd'] < datetime.now().date()])
        st.metric("Overdue Items", f"{overdue_count:,}", delta_color="inverse")
    
    with col6:
        avg_completion = po_df['arrival_completion_percent'].mean()
        st.metric("Avg Completion", f"{avg_completion:.1f}%")
    
    # Create tabs
    tab1, tab2, tab3, tab4, tab5 = st.tabs(["📊 Summary View", "📅 Pivot View", "📈 Analytics", "📋 Detailed List", "💰 Financial View"])
    
    with tab1:
        # Summary by vendor
        st.subheader("📊 Vendor Summary")
        
        vendor_summary = po_df.groupby(['vendor_name', 'vendor_type', 'vendor_location_type']).agg({
            'po_number': 'nunique',
            'po_line_id': 'count',
            'total_amount_usd': 'sum',
            'outstanding_arrival_amount_usd': 'sum',
            'arrival_completion_percent': 'mean',
            'is_over_delivered': lambda x: (x == 'Y').sum()
        }).round(2).reset_index()
        
        vendor_summary.columns = ['Vendor', 'Category', 'Location', 'PO Count', 'Line Items', 
                                 'Total Value', 'Outstanding', 'Avg Completion %', 'Over Deliveries']
        vendor_summary = vendor_summary.sort_values('Outstanding', ascending=False)
        
        # Add vendor type indicators
        # vendor_summary['Type'] = vendor_summary['Category'] + ' - ' + vendor_summary['Location']
        
        # Format currency columns
        for col in ['Total Value', 'Outstanding']:
            vendor_summary[col] = vendor_summary[col].apply(lambda x: f"${x:,.0f}")
        
        st.dataframe(
            vendor_summary.style.format({'Avg Completion %': '{:.1f}%'}),
            use_container_width=True
        )
        
        # Download button
        csv = vendor_summary.to_csv(index=False).encode('utf-8')
        st.download_button(
            label="📥 Download Vendor Summary",
            data=csv,
            file_name=f"vendor_summary_{datetime.now().strftime('%Y%m%d')}.csv",
            mime='text/csv'
        )
    
    with tab2:
        # Pivot View
        st.subheader(f"📅 PO Schedule - Pivot View")
        
        # View period selector - đặt trong tab
        col1, col2, col3 = st.columns([2, 2, 3])

        with col1:
            view_period = st.radio(
                "View Period:",
                options=["daily", "weekly", "monthly"],
                index=1,
                horizontal=True
            )
        with col2:
            group_by_vendor = st.checkbox("Group by Vendor", value=False)
        with col3:
            show_intl_only = st.checkbox("International Vendors Only", value=False)

        
        # Get date type from main filter
        date_type_lower = date_type.lower().replace(' ', '_')  # Convert "PO Date" to "po_date"
        
        # Filter data if needed
        pivot_data = po_df.copy()
        if show_intl_only:
            pivot_data = pivot_data[pivot_data['vendor_location_type'] == 'International']
        
        # Get pivoted data
        pivot_df = data_loader.pivot_po_data(pivot_data, view_period, date_type_lower)
        
        if not pivot_df.empty:
            st.markdown(f"**Showing {view_period} view based on {date_type}**")
            
            if group_by_vendor:
                # Create pivot table grouped by vendor
                pivot_table = pivot_df.pivot_table(
                    index='Vendor',
                    columns='Period',
                    values=['Total Quantity', 'Pending Quantity', 'Outstanding USD'],
                    aggfunc='sum',
                    fill_value=0
                )
                
                # Display options
                value_type = st.selectbox(
                    "Select Metric to Display",
                    options=['Total Quantity', 'Pending Quantity', 'Outstanding USD'],
                    index=2
                )
                
                # Display selected value type
                display_table = pivot_table[value_type]
                
                # Format based on value type
                if 'USD' in value_type:
                    st.dataframe(
                        display_table.style.format("${:,.0f}").background_gradient(cmap='Blues'),
                        use_container_width=True,
                        height=600
                    )
                else:
                    st.dataframe(
                        display_table.style.format("{:,.0f}").background_gradient(cmap='Greens'),
                        use_container_width=True,
                        height=600
                    )
                    
                # Show totals
                st.markdown("#### Period Totals")
                period_totals = pivot_df.groupby('Period').agg({
                    'Total Quantity': 'sum',
                    'Pending Quantity': 'sum',
                    'Outstanding USD': 'sum',
                    'PO Count': 'sum',
                    'Line Items': 'sum'
                }).reset_index()
                
                st.dataframe(
                    period_totals.style.format({
                        'Total Quantity': '{:,.0f}',
                        'Pending Quantity': '{:,.0f}',
                        'Outstanding USD': '${:,.0f}',
                        'PO Count': '{:,.0f}',
                        'Line Items': '{:,.0f}'
                    }),
                    use_container_width=True
                )
            else:
                # Display regular pivot view
                # Format currency columns
                format_dict = {
                    'PO Count': '{:,.0f}',
                    'Line Items': '{:,.0f}',
                    'Total Quantity': '{:,.0f}',
                    'Pending Quantity': '{:,.0f}',
                    'Total Value USD': '${:,.0f}',
                    'Outstanding USD': '${:,.0f}',
                    'Avg Completion %': '{:.1f}%'
                }
                
                # Apply conditional formatting
                def highlight_vendor_location(row):
                    if row['Location'] == 'International':
                        return ['background-color: #ffe4b5'] * len(row)
                    return [''] * len(row)
                
                def highlight_completion(val):
                    if pd.isna(val):
                        return ''
                    if val < 50:
                        return 'color: red; font-weight: bold'
                    elif val < 80:
                        return 'color: orange'
                    return 'color: green'
                
                styled_df = pivot_df.style.format(format_dict)
                styled_df = styled_df.apply(highlight_vendor_location, axis=1)
                styled_df = styled_df.map(highlight_completion, subset=['Avg Completion %'])
                styled_df = styled_df.background_gradient(subset=['Outstanding USD'], cmap='Reds')
                
                st.dataframe(styled_df, use_container_width=True, height=600)
            
            # Summary metrics for pivot
            st.markdown("---")
            col1, col2, col3, col4, col5 = st.columns(5)
            
            with col1:
                total_periods = pivot_df['Period'].nunique()
                st.metric("Total Periods", f"{total_periods}")
            
            with col2:
                total_vendors = pivot_df['Vendor'].nunique()
                st.metric("Active Vendors", f"{total_vendors}")
            
            with col3:
                intl_vendors = pivot_df[pivot_df['Location'] == 'International']['Vendor'].nunique()
                st.metric("International", f"{intl_vendors}")
            
            with col4:
                if pivot_df['Total Quantity'].sum() > 0:
                    avg_pending = pivot_df['Pending Quantity'].sum() / pivot_df['Total Quantity'].sum() * 100
                else:
                    avg_pending = 0
                st.metric("Avg Pending %", f"{avg_pending:.1f}%")
            
            with col5:
                total_outstanding = pivot_df['Outstanding USD'].sum()
                st.metric("Total Outstanding", f"${total_outstanding/1000000:.1f}M")
            
            # Download button
            csv = pivot_df.to_csv(index=False).encode('utf-8')
            st.download_button(
                label="📥 Download Pivot View",
                data=csv,
                file_name=f"po_pivot_{date_type_lower}_{view_period}_{datetime.now().strftime('%Y%m%d')}.csv",
                mime='text/csv'
            )
        else:
            st.info(f"No data available for {view_period} pivot view")


    with tab3:
        # Analytics
        col1, col2 = st.columns(2)
        
        with col1:
            # PO Timeline
            st.subheader("📅 PO Timeline (Next 8 weeks)")
            
            timeline_df = data_loader.get_po_timeline_data(weeks_ahead=8)
            
            if not timeline_df.empty:
                # Create weekly summary with vendor location
                timeline_df['week'] = pd.to_datetime(timeline_df['arrival_date']).dt.to_period('W').dt.start_time
                
                # Separate by vendor location type
                weekly_summary = timeline_df.groupby(['week', 'vendor_location_type']).agg({
                    'po_count': 'sum',
                    'arrival_value': 'sum'
                }).reset_index()
                
                fig1 = go.Figure()
                
                # Add bars for domestic and international
                for location in ['Domestic', 'International']:
                    location_data = weekly_summary[weekly_summary['vendor_location_type'] == location]
                    if not location_data.empty:
                        fig1.add_trace(go.Bar(
                            x=location_data['week'],
                            y=location_data['po_count'],
                            name=f'{location} POs',
                            yaxis='y'
                        ))
                
                # Add value line
                total_weekly = timeline_df.groupby('week').agg({
                    'arrival_value': 'sum'
                }).reset_index()
                
                fig1.add_trace(go.Scatter(
                    x=total_weekly['week'],
                    y=total_weekly['arrival_value'],
                    name='Total Value (USD)',
                    yaxis='y2',
                    line=dict(color='#f44336', width=3),
                    mode='lines+markers'
                ))
                
                fig1.update_layout(
                    xaxis_title="Week",
                    yaxis=dict(title="PO Count", side="left"),
                    yaxis2=dict(title="Value (USD)", overlaying="y", side="right"),
                    hovermode='x unified',
                    height=400,
                    barmode='stack'
                )
                st.plotly_chart(fig1, use_container_width=True)
            else:
                st.info("No upcoming arrivals in the selected period")
        
        with col2:
            # Status Distribution by Vendor Type
            st.subheader("📊 PO Status by Vendor Type")
            
            status_vendor_summary = po_df.groupby(['status', 'vendor_type']).agg({
                'po_line_id': 'count'
            }).reset_index()
            
            fig2 = px.bar(
                status_vendor_summary,
                x='status',
                y='po_line_id',
                color='vendor_type',
                title='PO Lines by Status and Vendor Type',
                labels={'po_line_id': 'Line Count', 'vendor_type': 'Vendor Category'},
                color_discrete_map={
                    'Internal': '#2ecc71',
                    'External': '#3498db'
                }
            )
            st.plotly_chart(fig2, use_container_width=True)
        
        # Vendor Performance by Location
        st.markdown("---")
        col1, col2 = st.columns(2)
        
        with col1:
            st.subheader("🌍 Vendor Performance by Location")
            
            location_summary = po_df.groupby('vendor_location_type').agg({
                'po_number': 'nunique',
                'outstanding_arrival_amount_usd': 'sum',
                'arrival_completion_percent': 'mean',
                'is_over_delivered': lambda x: (x == 'Y').sum()
            }).reset_index()
            
            location_summary.columns = ['Location', 'PO Count', 'Outstanding Value', 
                                       'Avg Completion %', 'Over Deliveries']
            
            # Create comparison chart
            fig3 = go.Figure()
            
            fig3.add_trace(go.Bar(
                x=location_summary['Location'],
                y=location_summary['Avg Completion %'],
                name='Avg Completion %',
                text=location_summary['Avg Completion %'].round(1),
                textposition='outside',
                marker_color=['#2ecc71', '#e74c3c']
            ))
            
            fig3.update_layout(
                title='Average Completion Rate by Vendor Location',
                yaxis_title='Completion %',
                height=350
            )
            st.plotly_chart(fig3, use_container_width=True)
        
        with col2:
            st.subheader("📦 Outstanding Value by Location")
            
            fig4 = px.pie(
                location_summary,
                values='Outstanding Value',
                names='Location',
                title='Outstanding Amount Distribution',
                color_discrete_map={
                    'Domestic': '#3498db',
                    'International': '#e67e22'
                }
            )
            st.plotly_chart(fig4, use_container_width=True)
        
        # Product demand vs incoming
        st.markdown("---")
        st.subheader("🔍 Product Supply & Demand Analysis")
        
        demand_df = data_loader.get_product_demand_vs_incoming()
        
        if not demand_df.empty:
            # Metrics summary
            col1, col2, col3, col4 = st.columns(4)
            
            with col1:
                products_need_order = len(demand_df[demand_df['supply_status'] == 'Need to Order'])
                st.metric("Products Need Order", products_need_order, delta_color="inverse")
            
            with col2:
                partial_coverage = len(demand_df[demand_df['supply_status'] == 'Partial Coverage'])
                st.metric("Partial Coverage", partial_coverage)
            
            with col3:
                will_be_sufficient = len(demand_df[demand_df['supply_status'] == 'Will be Sufficient'])
                st.metric("Will be Sufficient", will_be_sufficient, delta_color="normal")
            
            with col4:
                avg_coverage = demand_df['total_coverage_percent'].mean()
                st.metric("Avg Total Coverage", f"{avg_coverage:.1f}%")
            
            # Show products with net requirement > 0
            shortage_df = demand_df[demand_df['net_requirement'] > 0].head(15)
            
            if not shortage_df.empty:
                # Stacked bar chart showing current stock, incoming supply, and gap
                fig5 = go.Figure()
                
                fig5.add_trace(go.Bar(
                    x=shortage_df['pt_code'],
                    y=shortage_df['current_stock'],
                    name='Current Stock',
                    marker_color='#2ecc71',
                    text=shortage_df['current_stock'].round(0),
                    textposition='inside'
                ))
                
                fig5.add_trace(go.Bar(
                    x=shortage_df['pt_code'],
                    y=shortage_df['incoming_supply'],
                    name='Incoming Supply',
                    marker_color='#3498db',
                    text=shortage_df['incoming_supply'].round(0),
                    textposition='inside'
                ))
                
                fig5.add_trace(go.Bar(
                    x=shortage_df['pt_code'],
                    y=shortage_df['net_requirement'],
                    name='Net Requirement',
                    marker_color='#e74c3c',
                    text=shortage_df['net_requirement'].round(0),
                    textposition='inside'
                ))
                
                fig5.update_layout(
                    title='Top 15 Products - Supply vs Demand Analysis',
                    xaxis_title='PT Code',
                    yaxis_title='Quantity',
                    barmode='stack',
                    hovermode='x unified',
                    height=450
                )
                st.plotly_chart(fig5, use_container_width=True)
                
                # Detailed table with all metrics
                display_cols = ['pt_code', 'product', 'total_demand', 'current_stock', 
                              'incoming_supply', 'total_available', 'net_requirement',
                              'current_coverage_percent', 'total_coverage_percent', 
                              'next_arrival_date_eta', 'supply_status']
                
                # Rename column for display
                shortage_df_display = shortage_df[display_cols].copy()
                shortage_df_display.rename(columns={'next_arrival_date_eta': 'Next Arrival (ETA)'}, inplace=True)
                
                st.dataframe(
                    shortage_df_display.style.format({
                        'total_demand': '{:,.0f}',
                        'current_stock': '{:,.0f}',
                        'incoming_supply': '{:,.0f}',
                        'total_available': '{:,.0f}',
                        'net_requirement': '{:,.0f}',
                        'current_coverage_percent': '{:.1f}%',
                        'total_coverage_percent': '{:.1f}%'
                    }).background_gradient(subset=['total_coverage_percent'], cmap='RdYlGn')
                    .apply(lambda x: ['background-color: #ffcccb' if v == 'Need to Order' 
                                    else 'background-color: #ffe4b5' if v == 'Partial Coverage'
                                    else 'background-color: #90ee90' if v == 'Will be Sufficient'
                                    else '' for v in x], subset=['supply_status']),
                    use_container_width=True
                )
                    
                st.caption("""
                **Legend:**
                - **Current Stock**: Tồn kho hiện tại tại tất cả warehouses
                - **Incoming Supply**: Hàng đang về từ POs (pending arrival)
                - **Net Requirement**: Số lượng cần đặt thêm = Demand - Current Stock - Incoming Supply
                - **Supply Status**:
                  - 🔴 Need to Order: Cần đặt hàng ngay
                  - 🟡 Partial Coverage: Có hàng về nhưng chưa đủ
                  - 🟢 Will be Sufficient: Hàng về sẽ đủ đáp ứng
                """)
            else:
                st.success("✅ All products have sufficient coverage (current stock + incoming supply)")
        else:
            st.info("No demand data available for analysis")
    with tab4:
        # Detailed list
        st.subheader("📋 Detailed PO List")
        
        # Column selection with new fields
        default_columns = ['po_number', 'vendor_name', 'vendor_type', 'vendor_location_type',
                          'po_date', 'etd', 'eta', 'pt_code', 'product_name', 
                          'buying_quantity', 'pending_standard_arrival_quantity',
                          'arrival_completion_percent', 'outstanding_arrival_amount_usd',
                          'status', 'payment_term', 'is_over_delivered']
        
        display_columns = st.multiselect(
            "Select columns to display",
            options=po_df.columns.tolist(),
            default=[col for col in default_columns if col in po_df.columns]
        )
        
        if display_columns:
            display_df = po_df[display_columns].copy()
            
            # Format date columns
            date_columns = ['po_date', 'etd', 'eta', 'last_invoice_date']
            for col in date_columns:
                if col in display_df.columns:
                    display_df[col] = pd.to_datetime(display_df[col]).dt.strftime('%Y-%m-%d')
            
            # Apply conditional formatting
            def highlight_status(val):
                if val == 'COMPLETED':
                    return 'background-color: #90ee90'
                elif val == 'OVER_DELIVERED':
                    return 'background-color: #ffcccb'
                elif val == 'PENDING':
                    return 'background-color: #ffe4b5'
                return ''
            
            def highlight_vendor_type(val):
                if val == 'International':
                    return 'color: #e74c3c; font-weight: bold'
                return ''
            
            styled_df = display_df.style
            
            if 'status' in display_df.columns:
                styled_df = styled_df.applymap(highlight_status, subset=['status'])
            
            if 'vendor_location_type' in display_df.columns:
                styled_df = styled_df.applymap(highlight_vendor_type, subset=['vendor_location_type'])
            
            st.dataframe(styled_df, use_container_width=True)
            
            # Export button
            csv = display_df.to_csv(index=False).encode('utf-8')
            st.download_button(
                label="📥 Download Detailed List",
                data=csv,
                file_name=f"po_detailed_list_{datetime.now().strftime('%Y%m%d')}.csv",
                mime='text/csv'
            )
    
    with tab5:
        # Financial view
        st.subheader("💰 Financial Analysis")
        
        # Currency exposure by vendor type
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown("#### Currency Exposure by Vendor Type")
            
            currency_vendor_summary = po_df.groupby(['currency', 'vendor_type']).agg({
                'total_amount': 'sum',
                'total_amount_usd': 'sum',
                'po_number': 'nunique'
            }).reset_index()
            
            # Create stacked bar chart
            fig6 = px.bar(
                currency_vendor_summary,
                x='currency',
                y='total_amount_usd',
                color='vendor_type',
                title='Outstanding Value by Currency and Vendor Type',
                labels={'total_amount_usd': 'USD Amount', 'vendor_type': 'Vendor Category'},
                color_discrete_map={
                    'Internal': '#2ecc71',
                    'External': '#3498db'
                }
            )
            st.plotly_chart(fig6, use_container_width=True)
        
        with col2:
            st.markdown("#### Payment Terms by Location")
            
            payment_location_summary = po_df.groupby(['payment_term', 'vendor_location_type']).agg({
                'outstanding_invoiced_amount_usd': 'sum',
                'po_number': 'nunique'
            }).reset_index()
            
            payment_location_summary = payment_location_summary.sort_values(
                'outstanding_invoiced_amount_usd', ascending=False
            ).head(10)
            
            fig7 = px.bar(
                payment_location_summary,
                x='payment_term',
                y='outstanding_invoiced_amount_usd',
                color='vendor_location_type',
                title='Top 10 Payment Terms by Location',
                labels={
                    'outstanding_invoiced_amount_usd': 'Outstanding Invoice USD',
                    'vendor_location_type': 'Vendor Location'
                },
                color_discrete_map={
                    'Domestic': '#3498db',
                    'International': '#e67e22'
                }
            )
            fig7.update_xaxes(tickangle=-45)
            st.plotly_chart(fig7, use_container_width=True)
        
        # Outstanding by vendor with type info
        st.markdown("---")
        st.markdown("#### Top 10 Vendors by Outstanding Amount")
        
        vendor_outstanding = po_df.groupby(['vendor_name', 'vendor_type', 'vendor_location_type']).agg({
            'outstanding_arrival_amount_usd': 'sum',
            'outstanding_invoiced_amount_usd': 'sum',
            'po_number': 'nunique'
        }).reset_index()
        
        vendor_outstanding['Total Outstanding'] = (
            vendor_outstanding['outstanding_arrival_amount_usd'] + 
            vendor_outstanding['outstanding_invoiced_amount_usd']
        )
        vendor_outstanding['Vendor Display'] = (
            vendor_outstanding['vendor_name'] + ' (' + 
            vendor_outstanding['vendor_type'] + ' - ' + 
            vendor_outstanding['vendor_location_type'] + ')'
        )
        vendor_outstanding = vendor_outstanding.sort_values('Total Outstanding', ascending=False).head(10)
        
        # Create stacked bar chart
        fig8 = go.Figure()
        fig8.add_trace(go.Bar(
            x=vendor_outstanding['Vendor Display'],
            y=vendor_outstanding['outstanding_arrival_amount_usd'],
            name='Arrival',
            marker_color='#2e7d32'
        ))
        fig8.add_trace(go.Bar(
            x=vendor_outstanding['Vendor Display'],
            y=vendor_outstanding['outstanding_invoiced_amount_usd'],
            name='Invoice',
            marker_color='#f44336'
        ))
        
        fig8.update_layout(
            barmode='stack',
            xaxis_title="Vendor",
            yaxis_title="Outstanding Amount (USD)",
            height=500
        )
        fig8.update_xaxes(tickangle=-45)
        st.plotly_chart(fig8, use_container_width=True)

else:
    st.info("No purchase order data found for the selected filters")

# Footer
st.markdown("---")
st.caption(f"Last updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")