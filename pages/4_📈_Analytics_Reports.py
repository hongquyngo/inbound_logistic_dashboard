# pages/4_📈_Analytics_Reports.py

import streamlit as st
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from utils.auth import AuthManager
from utils.data_loader import InboundDataLoader
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import io
import xlsxwriter
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter, A4
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, PageBreak
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch

# Page config
st.set_page_config(
    page_title="Analytics & Reports",
    page_icon="📈",
    layout="wide"
)

# Check authentication
auth_manager = AuthManager()
if not auth_manager.check_session():
    st.warning("⚠️ Please login to access this page")
    st.stop()

# Initialize data loader
data_loader = InboundDataLoader()

st.title("📈 Analytics & Reports")
st.markdown("Comprehensive analytics for inbound logistics performance")

# Report type selection
report_type = st.selectbox(
    "Select Report Type",
    [
        "📊 Executive Dashboard",
        "🏭 Vendor Performance Analysis",
        "📦 Inventory Pipeline Report",
        "💰 Financial Analytics",
        "📈 Trend Analysis",
        "🎯 Custom Report Builder"
    ]
)

st.markdown("---")

def export_vendor_report_to_excel(vendor_data, performance_data, purchase_history, product_analysis, filename="vendor_report.xlsx"):
    """Export comprehensive vendor report to Excel"""
    output = io.BytesIO()
    
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        workbook = writer.book
        
        # Define formats
        header_format = workbook.add_format({
            'bold': True,
            'bg_color': '#4472C4',
            'font_color': 'white',
            'align': 'center',
            'valign': 'vcenter',
            'border': 1
        })
        
        currency_format = workbook.add_format({'num_format': '$#,##0.00'})
        percent_format = workbook.add_format({'num_format': '0.0%'})
        date_format = workbook.add_format({'num_format': 'yyyy-mm-dd'})
        
        # 1. Summary Sheet
        summary_df = pd.DataFrame({
            'Metric': ['Total Purchase Value', 'Number of POs', 'On-Time Delivery Rate', 
                      'Completion Rate', 'Average Lead Time', 'Outstanding Amount'],
            'Value': [
                f"${vendor_data['total_po_value'].sum():,.2f}",
                f"{vendor_data['total_pos'].sum()}",
                f"{vendor_data['on_time_rate'].mean():.1f}%",
                f"{vendor_data['completion_rate'].mean():.1f}%",
                f"{vendor_data.get('avg_lead_time_days', 0):.1f} days",
                f"${vendor_data['outstanding_invoices'].sum():,.2f}"
            ]
        })
        summary_df.to_excel(writer, sheet_name='Summary', index=False)
        
        # 2. Performance Metrics Sheet
        performance_data.to_excel(writer, sheet_name='Performance Metrics', index=False)
        
        # 3. Purchase History Sheet
        purchase_history.to_excel(writer, sheet_name='Purchase History', index=False)
        
        # 4. Product Analysis Sheet
        product_analysis.to_excel(writer, sheet_name='Product Analysis', index=False)
        
        # Format sheets
        for sheet_name in writer.sheets:
            worksheet = writer.sheets[sheet_name]
            worksheet.set_column('A:Z', 15)  # Set column width
            
            # Add header formatting
            for col_num, value in enumerate(performance_data.columns.values):
                worksheet.write(0, col_num, value, header_format)
    
    output.seek(0)
    return output

if report_type == "📊 Executive Dashboard":
    st.header("📊 Executive Dashboard")
    
    # Date range selector
    col1, col2, col3 = st.columns([1, 1, 3])
    with col1:
        start_date = st.date_input(
            "From",
            value=datetime.now().date() - timedelta(days=30),
            max_value=datetime.now().date()
        )
    with col2:
        end_date = st.date_input(
            "To",
            value=datetime.now().date(),
            max_value=datetime.now().date()
        )
    
    # Load data
    filters = {
        'date_from': start_date,
        'date_to': end_date
    }
    
    with st.spinner("Loading executive metrics..."):
        po_df = data_loader.load_po_data(filters)
        can_df = data_loader.load_can_pending_data()
        vendor_performance = data_loader.get_vendor_performance_metrics()
    
    if po_df is not None and not po_df.empty:
        # Executive KPIs
        st.subheader("Key Performance Indicators")
        
        col1, col2, col3, col4, col5 = st.columns(5)
        
        with col1:
            total_spend = po_df['total_amount_usd'].sum()
            st.metric("Total Spend", f"${total_spend/1000000:.1f}M")
        
        with col2:
            active_vendors = po_df['vendor_name'].nunique()
            st.metric("Active Vendors", f"{active_vendors}")
        
        with col3:
            avg_completion = po_df['arrival_completion_percent'].mean()
            st.metric("Avg Completion Rate", f"{avg_completion:.1f}%")
        
        with col4:
            overdue_value = po_df[po_df['etd'] < datetime.now().date()]['outstanding_arrival_amount_usd'].sum()
            st.metric("Overdue Value", f"${overdue_value/1000:.0f}K", delta_color="inverse")
        
        with col5:
            if can_df is not None and not can_df.empty:
                stockin_backlog = can_df['pending_value_usd'].sum()
                st.metric("Stock-in Backlog", f"${stockin_backlog/1000:.0f}K")
            else:
                st.metric("Stock-in Backlog", "$0")
        
        # Create executive charts
        fig = make_subplots(
            rows=2, cols=2,
            subplot_titles=('PO Status Distribution', 'Top 10 Vendors by Value',
                          'Monthly Trend', 'Category Spend'),
            specs=[[{'type': 'domain'}, {'type': 'bar'}],
                   [{'type': 'scatter'}, {'type': 'domain'}]]
        )
        
        # 1. PO Status Pie Chart
        status_summary = po_df['status'].value_counts()
        fig.add_trace(
            go.Pie(labels=status_summary.index, values=status_summary.values, name="Status"),
            row=1, col=1
        )
        
        # 2. Top Vendors Bar Chart
        top_vendors = po_df.groupby('vendor_name')['total_amount_usd'].sum().nlargest(10)
        fig.add_trace(
            go.Bar(x=top_vendors.values, y=top_vendors.index, orientation='h', name="Spend"),
            row=1, col=2
        )
        
        # 3. Monthly Trend Line Chart
        po_df['month'] = pd.to_datetime(po_df['po_date']).dt.to_period('M').dt.to_timestamp()
        monthly_trend = po_df.groupby('month').agg({
            'po_number': 'nunique',
            'total_amount_usd': 'sum'
        }).reset_index()
        
        fig.add_trace(
            go.Scatter(x=monthly_trend['month'], y=monthly_trend['total_amount_usd'],
                      mode='lines+markers', name="Monthly Spend"),
            row=2, col=1
        )
        
        # 4. Category Spend (by Brand)
        brand_spend = po_df.groupby('brand')['total_amount_usd'].sum().nlargest(8)
        fig.add_trace(
            go.Pie(labels=brand_spend.index, values=brand_spend.values, name="Brand"),
            row=2, col=2
        )
        
        fig.update_layout(height=800, showlegend=False)
        st.plotly_chart(fig, use_container_width=True)

elif report_type == "🏭 Vendor Performance Analysis":
    st.header("🏭 Vendor Performance Analysis")
    st.markdown("Comprehensive vendor analysis for procurement meetings and negotiations")
    
    # Analysis configuration
    col1, col2, col3 = st.columns([2, 1, 1])
    
    with col1:
        # Vendor selection
        filter_options = data_loader.get_filter_options()
        vendor_options = filter_options.get('vendors', [])  # Format: "CODE - NAME"
        
        if vendor_options:
            vendor_display_options = ["All Vendors"] + vendor_options
            selected_vendor_display = st.selectbox("Select Vendor", vendor_display_options)
        else:
            selected_vendor_display = "All Vendors"
            st.warning("No vendors found in database")
    
    with col2:
        # Period selection
        period_type = st.selectbox(
            "Analysis Period",
            ["Monthly", "Quarterly", "Yearly", "Custom"]
        )
    
    with col3:
        if period_type == "Custom":
            months_back = st.number_input("Months Back", min_value=1, max_value=24, value=6)
        else:
            months_back = {"Monthly": 12, "Quarterly": 12, "Yearly": 36}[period_type]
    
    # Comparison options
    compare_previous = st.checkbox("Compare with Previous Period", value=True)
    
    # Extract vendor name for queries
    selected_vendor_name = None
    if selected_vendor_display != "All Vendors":
        if ' - ' in selected_vendor_display:
            _, selected_vendor_name = selected_vendor_display.split(' - ', 1)
            selected_vendor_name = selected_vendor_name.strip()
        else:
            selected_vendor_name = selected_vendor_display.strip()
    
    # Debug info (optional - can be removed in production)
    with st.expander("Debug Info", expanded=False):
        st.write(f"Selected display: {selected_vendor_display}")
        st.write(f"Extracted vendor name: {selected_vendor_name}")
    
    # Load vendor performance data
    with st.spinner("Analyzing vendor performance..."):
        try:
            if selected_vendor_display == "All Vendors":
                vendor_metrics = data_loader.get_vendor_performance_metrics(months=months_back)
                po_df = data_loader.load_po_data()
            else:
                # Get vendor metrics using extracted name
                vendor_metrics = data_loader.get_vendor_performance_metrics(
                    vendor_name=selected_vendor_name, 
                    months=months_back
                )
                
                # Load PO data with vendor filter in display format
                po_df = data_loader.load_po_data({'vendors': [selected_vendor_display]})
                
            # Validate data
            if vendor_metrics is None:
                vendor_metrics = pd.DataFrame()
            if po_df is None:
                po_df = pd.DataFrame()
                
        except Exception as e:
            st.error(f"Error loading vendor data: {str(e)}")
            vendor_metrics = pd.DataFrame()
            po_df = pd.DataFrame()
    
    # Check if we have data to work with
    if not vendor_metrics.empty and not po_df.empty:
        # Tab layout for different analyses
        tabs = st.tabs([
            "📊 Overview", 
            "💰 Purchase Analysis", 
            "📈 Performance Trends",
            "📦 Product Analysis",
            "💳 Payment Analysis",
            "📄 Export Report"
        ])
        
        with tabs[0]:  # Overview Tab
            st.subheader("Performance Overview")
            
            if selected_vendor_display != "All Vendors":
                # Single vendor detailed view
                if len(vendor_metrics) > 0:
                    vendor_data = vendor_metrics.iloc[0]
                    
                    # Key metrics
                    col1, col2, col3, col4 = st.columns(4)
                    
                    with col1:
                        st.metric(
                            "Total Purchase Value",
                            f"${vendor_data.get('total_po_value', 0):,.0f}",
                            help="Total value of all POs in the period"
                        )
                    
                    with col2:
                        st.metric(
                            "On-Time Delivery",
                            f"{vendor_data.get('on_time_rate', 0):.1f}%",
                            delta=f"{vendor_data.get('on_time_rate', 0) - 80:.1f}%" if vendor_data.get('on_time_rate', 0) >= 80 else None,
                            delta_color="normal" if vendor_data.get('on_time_rate', 0) >= 80 else "inverse"
                        )
                    
                    with col3:
                        st.metric(
                            "Completion Rate",
                            f"{vendor_data.get('completion_rate', 0):.1f}%",
                            help="Percentage of POs fully completed"
                        )
                    
                    with col4:
                        # Calculate performance score
                        performance_score = (
                            vendor_data.get('on_time_rate', 0) * 0.4 +
                            vendor_data.get('completion_rate', 0) * 0.4 +
                            (100 - vendor_data.get('avg_over_delivery_percent', 0)) * 0.2
                        )
                        st.metric(
                            "Performance Score",
                            f"{performance_score:.1f}%",
                            help="Overall performance score (weighted)"
                        )
                    
                    # Additional metrics
                    st.markdown("---")
                    col1, col2, col3, col4 = st.columns(4)
                    
                    with col1:
                        st.metric("Total POs", f"{vendor_data.get('total_pos', 0):,}")
                    
                    with col2:
                        st.metric("Completed POs", f"{vendor_data.get('completed_pos', 0):,}")
                    
                    with col3:
                        st.metric("Over Deliveries", f"{vendor_data.get('over_delivery_pos', 0):,}")
                    
                    with col4:
                        st.metric(
                            "Outstanding Amount",
                            f"${vendor_data.get('outstanding_invoices', 0):,.0f}"
                        )
                else:
                    st.warning("No performance data available for the selected vendor")
                
            else:
                # All vendors comparison view - IMPROVED
                # Calculate performance scores
                vendor_metrics['performance_score'] = (
                    vendor_metrics['on_time_rate'] * 0.4 +
                    vendor_metrics['completion_rate'] * 0.4 +
                    (100 - vendor_metrics['avg_over_delivery_percent'].fillna(0)) * 0.2
                ).round(1)
                
                # Overall summary metrics for all vendors
                st.markdown("### Overall Vendor Performance Summary")
                col1, col2, col3, col4, col5, col6 = st.columns(6)
                
                with col1:
                    st.metric(
                        "Total Vendors",
                        f"{len(vendor_metrics):,}",
                        help="Total number of active vendors"
                    )
                
                with col2:
                    total_po_value = vendor_metrics['total_po_value'].sum()
                    st.metric(
                        "Total Spend",
                        f"${total_po_value/1000000:.1f}M",
                        help="Total purchase value across all vendors"
                    )
                
                with col3:
                    avg_on_time = vendor_metrics['on_time_rate'].mean()
                    st.metric(
                        "Avg On-Time Rate",
                        f"{avg_on_time:.1f}%",
                        delta=f"{avg_on_time - 80:.1f}%" if avg_on_time >= 80 else f"{avg_on_time - 80:.1f}%",
                        delta_color="normal" if avg_on_time >= 80 else "inverse"
                    )
                
                with col4:
                    avg_completion = vendor_metrics['completion_rate'].mean()
                    st.metric(
                        "Avg Completion",
                        f"{avg_completion:.1f}%",
                        help="Average PO completion rate"
                    )
                
                with col5:
                    high_performers = len(vendor_metrics[vendor_metrics['performance_score'] >= 80])
                    st.metric(
                        "High Performers",
                        f"{high_performers}",
                        help="Vendors with score ≥ 80%"
                    )
                
                with col6:
                    total_outstanding = vendor_metrics['outstanding_invoices'].sum()
                    st.metric(
                        "Total Outstanding",
                        f"${total_outstanding/1000000:.1f}M",
                        help="Total outstanding invoices"
                    )
                
                st.markdown("---")
                
                # Two columns layout for charts
                col1, col2 = st.columns(2)
                
                with col1:
                    st.markdown("### Top Performing Vendors")
                    
                    top_vendors = vendor_metrics.nlargest(10, 'performance_score')
                    
                    if not top_vendors.empty:
                        # Performance matrix scatter plot with vendor names
                        fig_matrix = px.scatter(
                            top_vendors,
                            x='on_time_rate',
                            y='completion_rate',
                            size='total_po_value',
                            color='performance_score',
                            text='vendor_name',
                            hover_data=['total_pos', 'vendor_type', 'vendor_location_type', 'total_po_value'],
                            labels={
                                'on_time_rate': 'On-Time Delivery Rate (%)',
                                'completion_rate': 'PO Completion Rate (%)',
                                'performance_score': 'Performance Score'
                            },
                            title="Vendor Performance Matrix (Size = PO Value)",
                            color_continuous_scale='RdYlGn',
                            size_max=50
                        )
                        
                        # Update text position
                        fig_matrix.update_traces(
                            textposition='top center',
                            textfont_size=8
                        )
                        
                        # Add quadrant lines
                        fig_matrix.add_hline(y=80, line_dash="dash", line_color="gray", opacity=0.5)
                        fig_matrix.add_vline(x=80, line_dash="dash", line_color="gray", opacity=0.5)
                        
                        # Add quadrant labels
                        fig_matrix.add_annotation(x=95, y=95, text="⭐ Top Performers", showarrow=False, font=dict(size=10))
                        fig_matrix.add_annotation(x=95, y=50, text="⚡ Fast but Incomplete", showarrow=False, font=dict(size=10))
                        fig_matrix.add_annotation(x=50, y=95, text="🎯 Complete but Slow", showarrow=False, font=dict(size=10))
                        fig_matrix.add_annotation(x=50, y=50, text="⚠️ Need Improvement", showarrow=False, font=dict(size=10))
                        
                        fig_matrix.update_layout(height=500)
                        st.plotly_chart(fig_matrix, use_container_width=True)
                
                with col2:
                    st.markdown("### Vendor Distribution by Type")
                    
                    # Vendor distribution charts
                    vendor_type_dist = vendor_metrics.groupby(['vendor_type', 'vendor_location_type']).agg({
                        'vendor_name': 'count',
                        'total_po_value': 'sum'
                    }).reset_index()
                    
                    fig_dist = px.sunburst(
                        vendor_type_dist,
                        path=['vendor_type', 'vendor_location_type'],
                        values='total_po_value',
                        title='Vendor Distribution by Type and Location (Value)',
                        color='total_po_value',
                        color_continuous_scale='Blues'
                    )
                    fig_dist.update_layout(height=500)
                    st.plotly_chart(fig_dist, use_container_width=True)
                
                # Performance distribution
                st.markdown("---")
                st.markdown("### Performance Distribution Analysis")
                
                col1, col2 = st.columns(2)
                
                with col1:
                    # Performance score distribution
                    fig_score_dist = px.histogram(
                        vendor_metrics,
                        x='performance_score',
                        nbins=20,
                        title='Vendor Performance Score Distribution',
                        labels={'performance_score': 'Performance Score (%)', 'count': 'Number of Vendors'},
                        color_discrete_sequence=['#3498db']
                    )
                    fig_score_dist.add_vline(x=80, line_dash="dash", line_color="red", 
                                           annotation_text="Target: 80%", annotation_position="top right")
                    st.plotly_chart(fig_score_dist, use_container_width=True)
                
                with col2:
                    # Lead time analysis
                    fig_lead_time = px.box(
                        vendor_metrics,
                        x='vendor_location_type',
                        y='avg_lead_time_days',
                        color='vendor_type',
                        title='Lead Time Distribution by Vendor Type',
                        labels={'avg_lead_time_days': 'Average Lead Time (Days)'}
                    )
                    st.plotly_chart(fig_lead_time, use_container_width=True)
            
            # Vendor comparison table
            st.markdown("### Vendor Performance Metrics")
            
            if not vendor_metrics.empty:
                # Prepare display data
                display_metrics = vendor_metrics[[
                    'vendor_name', 'vendor_type', 'vendor_location_type',
                    'total_pos', 'completed_pos', 'on_time_rate', 
                    'completion_rate', 'avg_over_delivery_percent',
                    'total_po_value', 'outstanding_invoices'
                ]].copy()
                
                # Add performance score
                display_metrics['performance_score'] = (
                    display_metrics['on_time_rate'] * 0.4 +
                    display_metrics['completion_rate'] * 0.4 +
                    (100 - display_metrics['avg_over_delivery_percent'].fillna(0)) * 0.2
                ).round(1)
                
                # Add performance tier
                display_metrics['performance_tier'] = display_metrics['performance_score'].apply(
                    lambda x: '⭐ Excellent' if x >= 90 else '✅ Good' if x >= 75 else '⚠️ Fair' if x >= 60 else '❌ Poor'
                )
                
                # Sort by performance score
                display_metrics = display_metrics.sort_values('performance_score', ascending=False)
                
                # Rename columns for display
                display_metrics.columns = [
                    'Vendor', 'Type', 'Location', 'Total POs', 'Completed',
                    'On-Time %', 'Completion %', 'Avg Over %',
                    'Total Value', 'Outstanding', 'Score', 'Tier'
                ]
                
                # Format numeric columns
                display_metrics['Total Value'] = display_metrics['Total Value'].apply(lambda x: f"${x:,.0f}")
                display_metrics['Outstanding'] = display_metrics['Outstanding'].apply(lambda x: f"${x:,.0f}")
                
                # Apply conditional formatting
                def style_dataframe(df):
                    return df.style.format({
                        'On-Time %': '{:.1f}%',
                        'Completion %': '{:.1f}%',
                        'Avg Over %': '{:.1f}%',
                        'Score': '{:.1f}%'
                    }).background_gradient(
                        subset=['Score'], 
                        cmap='RdYlGn',
                        vmin=0,
                        vmax=100
                    ).apply(
                        lambda x: ['background-color: #ffcccc' if v < 80 else '' 
                                  for v in x], 
                        subset=['On-Time %', 'Completion %'],
                        axis=1
                    ).apply(
                        lambda x: ['background-color: #d4f8d4' if 'Excellent' in str(v) 
                                  else 'background-color: #fff3cd' if 'Good' in str(v)
                                  else 'background-color: #ffe4b5' if 'Fair' in str(v)
                                  else 'background-color: #ffcccc' if 'Poor' in str(v)
                                  else '' for v in x],
                        subset=['Tier'],
                        axis=1
                    )
                
                # Display options
                col1, col2, col3 = st.columns([1, 1, 2])
                
                with col1:
                    show_all = st.checkbox("Show All Vendors", value=False)
                    if not show_all:
                        num_vendors = st.slider("Number of Vendors", 10, 50, 20)
                        display_metrics = display_metrics.head(num_vendors)
                
                with col2:
                    filter_tier = st.multiselect(
                        "Filter by Tier",
                        options=['⭐ Excellent', '✅ Good', '⚠️ Fair', '❌ Poor'],
                        default=None
                    )
                    if filter_tier:
                        display_metrics = display_metrics[display_metrics['Tier'].isin(filter_tier)]
                
                with col3:
                    # Export button
                    csv = display_metrics.to_csv(index=False).encode('utf-8')
                    st.download_button(
                        label="📥 Download Performance Metrics",
                        data=csv,
                        file_name=f"vendor_performance_metrics_{datetime.now().strftime('%Y%m%d')}.csv",
                        mime='text/csv'
                    )
                
                # Display the styled dataframe
                st.dataframe(
                    style_dataframe(display_metrics),
                    use_container_width=True,
                    height=600,
                    hide_index=True
                )
                
                # Summary statistics
                st.markdown("---")
                st.markdown("#### Performance Summary Statistics")
                
                col1, col2, col3, col4 = st.columns(4)
                
                with col1:
                    tier_dist = display_metrics['Tier'].value_counts()
                    st.markdown("**Tier Distribution**")
                    for tier, count in tier_dist.items():
                        st.write(f"{tier}: {count}")
                
                with col2:
                    st.markdown("**Average Metrics**")
                    st.write(f"On-Time: {vendor_metrics['on_time_rate'].mean():.1f}%")
                    st.write(f"Completion: {vendor_metrics['completion_rate'].mean():.1f}%")
                    st.write(f"Lead Time: {vendor_metrics['avg_lead_time_days'].mean():.1f} days")
                
                with col3:
                    st.markdown("**By Location**")
                    location_avg = vendor_metrics.groupby('vendor_location_type')['performance_score'].mean()
                    for loc, avg in location_avg.items():
                        st.write(f"{loc}: {avg:.1f}%")
                
                with col4:
                    st.markdown("**By Type**")
                    type_avg = vendor_metrics.groupby('vendor_type')['performance_score'].mean()
                    for vtype, avg in type_avg.items():
                        st.write(f"{vtype}: {avg:.1f}%")
        
        with tabs[1]:  # Purchase Analysis Tab
            st.subheader("💰 Purchase Value Analysis")
            
            if not po_df.empty and 'po_date' in po_df.columns:
                # Time series analysis
                po_df['period'] = pd.to_datetime(po_df['po_date'])
                
                if period_type == "Monthly":
                    po_df['period'] = po_df['period'].dt.to_period('M').dt.to_timestamp()
                    period_label = "Month"
                elif period_type == "Quarterly":
                    po_df['period'] = po_df['period'].dt.to_period('Q').dt.to_timestamp()
                    period_label = "Quarter"
                else:  # Yearly
                    po_df['period'] = po_df['period'].dt.to_period('Y').dt.to_timestamp()
                    period_label = "Year"
                
                # Aggregate by period
                period_analysis = po_df.groupby(['period', 'vendor_name']).agg({
                    'po_number': 'nunique',
                    'total_amount_usd': 'sum',
                    'po_line_id': 'count',
                    'brand': lambda x: x.nunique() if pd.api.types.is_object_dtype(x) else 0,
                    'product_name': 'nunique'
                }).reset_index()
                
                period_analysis.columns = ['Period', 'Vendor', 'PO Count', 'Total Value', 
                                         'Line Items', 'Brands', 'Products']
                
                # Create time series chart
                if selected_vendor_display != "All Vendors" and selected_vendor_name:
                    vendor_period_data = period_analysis[period_analysis['Vendor'] == selected_vendor_name]
                    
                    if not vendor_period_data.empty:
                        fig_trend = make_subplots(
                            rows=2, cols=1,
                            subplot_titles=(f'Purchase Value Trend - {selected_vendor_name}', 
                                          'PO Count and Product Diversity'),
                            specs=[[{"secondary_y": False}], [{"secondary_y": True}]]
                        )
                        
                        # Purchase value trend
                        fig_trend.add_trace(
                            go.Bar(x=vendor_period_data['Period'], 
                                  y=vendor_period_data['Total Value'],
                                  name='Purchase Value',
                                  marker_color='#3498db'),
                            row=1, col=1
                        )
                        
                        # PO count and products
                        fig_trend.add_trace(
                            go.Scatter(x=vendor_period_data['Period'], 
                                     y=vendor_period_data['PO Count'],
                                     mode='lines+markers',
                                     name='PO Count',
                                     line=dict(color='#e74c3c', width=3)),
                            row=2, col=1
                        )
                        
                        fig_trend.add_trace(
                            go.Scatter(x=vendor_period_data['Period'], 
                                     y=vendor_period_data['Products'],
                                     mode='lines+markers',
                                     name='Unique Products',
                                     line=dict(color='#2ecc71', width=3)),
                            row=2, col=1, secondary_y=True
                        )
                        
                        fig_trend.update_layout(height=600)
                        st.plotly_chart(fig_trend, use_container_width=True)
                        
                        # Period comparison table
                        st.markdown("#### Period-over-Period Analysis")
                        
                        # Calculate period-over-period changes
                        vendor_period_data = vendor_period_data.sort_values('Period')
                        vendor_period_data['Value Change %'] = vendor_period_data['Total Value'].pct_change() * 100
                        vendor_period_data['PO Change %'] = vendor_period_data['PO Count'].pct_change() * 100
                        
                        # Format for display
                        display_period = vendor_period_data[['Period', 'Total Value', 'Value Change %', 
                                                           'PO Count', 'PO Change %', 'Products']].copy()
                        display_period['Period'] = display_period['Period'].dt.strftime('%Y-%m')
                        display_period['Total Value'] = display_period['Total Value'].apply(lambda x: f"${x:,.0f}")
                        
                        st.dataframe(
                            display_period.style.format({
                                'Value Change %': '{:.1f}%',
                                'PO Change %': '{:.1f}%'
                            }).apply(
                                lambda x: ['color: green' if v > 0 else 'color: red' if v < 0 else '' 
                                          for v in x], 
                                subset=['Value Change %', 'PO Change %'],
                                axis=1
                            ),
                            use_container_width=True,
                            hide_index=True
                        )
                    else:
                        st.info("No period data available for the selected vendor")
                
                else:
                    # Top vendors by period - IMPROVED for All Vendors
                    st.markdown("#### Purchase Value Analysis - All Vendors")
                    
                    if not period_analysis.empty:
                        # Create tabs for different views
                        analysis_tabs = st.tabs(["📊 Top Vendors", "📈 Trends", "🌍 By Location", "💼 By Type"])
                        
                        with analysis_tabs[0]:  # Top Vendors
                            # Get latest period data
                            latest_period = period_analysis['Period'].max()
                            latest_vendors = period_analysis[period_analysis['Period'] == latest_period].nlargest(10, 'Total Value')
                            
                            if not latest_vendors.empty:
                                # Top vendors bar chart
                                fig_top = px.bar(
                                    latest_vendors,
                                    x='Total Value',
                                    y='Vendor',
                                    orientation='h',
                                    title=f"Top 10 Vendors - {latest_period.strftime('%Y-%m')}",
                                    color='Total Value',
                                    color_continuous_scale='Blues',
                                    text='Total Value'
                                )
                                
                                # Format text on bars
                                fig_top.update_traces(
                                    texttemplate='$%{text:,.0f}',
                                    textposition='inside'
                                )
                                
                                fig_top.update_layout(
                                    height=500,
                                    showlegend=False,
                                    xaxis_title="Total Purchase Value (USD)"
                                )
                                st.plotly_chart(fig_top, use_container_width=True)
                                
                                # Vendor comparison table
                                st.markdown("##### Vendor Comparison Details")
                                comparison_df = latest_vendors[['Vendor', 'PO Count', 'Total Value', 'Line Items', 'Products', 'Brands']].copy()
                                comparison_df['Avg PO Value'] = comparison_df['Total Value'] / comparison_df['PO Count']
                                comparison_df['Total Value'] = comparison_df['Total Value'].apply(lambda x: f"${x:,.0f}")
                                comparison_df['Avg PO Value'] = comparison_df['Avg PO Value'].apply(lambda x: f"${x:,.0f}")
                                
                                st.dataframe(
                                    comparison_df,
                                    use_container_width=True,
                                    hide_index=True
                                )
                            else:
                                st.info("No vendor data available for the latest period")
                        
                        with analysis_tabs[1]:  # Trends
                            # Overall trend analysis
                            st.markdown("##### Purchase Value Trends Over Time")
                            
                            # Aggregate total by period
                            period_totals = period_analysis.groupby('Period').agg({
                                'Total Value': 'sum',
                                'PO Count': 'sum',
                                'Vendor': 'nunique',
                                'Products': 'sum'
                            }).reset_index()
                            
                            # Create dual axis chart
                            fig_trend = make_subplots(
                                rows=2, cols=1,
                                subplot_titles=('Total Purchase Value Trend', 'PO Volume and Vendor Count'),
                                specs=[[{"secondary_y": False}], [{"secondary_y": True}]]
                            )
                            
                            # Purchase value trend
                            fig_trend.add_trace(
                                go.Bar(
                                    x=period_totals['Period'],
                                    y=period_totals['Total Value'],
                                    name='Total Value',
                                    marker_color='#3498db'
                                ),
                                row=1, col=1
                            )
                            
                            # PO count and vendor count
                            fig_trend.add_trace(
                                go.Scatter(
                                    x=period_totals['Period'],
                                    y=period_totals['PO Count'],
                                    mode='lines+markers',
                                    name='PO Count',
                                    line=dict(color='#e74c3c', width=3)
                                ),
                                row=2, col=1
                            )
                            
                            fig_trend.add_trace(
                                go.Scatter(
                                    x=period_totals['Period'],
                                    y=period_totals['Vendor'],
                                    mode='lines+markers',
                                    name='Active Vendors',
                                    line=dict(color='#2ecc71', width=3)
                                ),
                                row=2, col=1, secondary_y=True
                            )
                            
                            fig_trend.update_yaxes(title_text="PO Count", row=2, col=1, secondary_y=False)
                            fig_trend.update_yaxes(title_text="Vendor Count", row=2, col=1, secondary_y=True)
                            
                            fig_trend.update_layout(height=600, showlegend=True)
                            st.plotly_chart(fig_trend, use_container_width=True)
                            
                            # Growth metrics
                            if len(period_totals) > 1:
                                st.markdown("##### Growth Metrics")
                                col1, col2, col3 = st.columns(3)
                                
                                # Calculate growth rates
                                period_totals = period_totals.sort_values('Period')
                                latest_value = period_totals.iloc[-1]['Total Value']
                                previous_value = period_totals.iloc[-2]['Total Value']
                                value_growth = ((latest_value - previous_value) / previous_value * 100) if previous_value > 0 else 0
                                
                                latest_po = period_totals.iloc[-1]['PO Count']
                                previous_po = period_totals.iloc[-2]['PO Count']
                                po_growth = ((latest_po - previous_po) / previous_po * 100) if previous_po > 0 else 0
                                
                                avg_monthly_value = period_totals['Total Value'].mean()
                                
                                with col1:
                                    st.metric(
                                        "Period-over-Period Growth",
                                        f"{value_growth:.1f}%",
                                        delta=f"${latest_value - previous_value:,.0f}",
                                        delta_color="normal" if value_growth > 0 else "inverse"
                                    )
                                
                                with col2:
                                    st.metric(
                                        "PO Volume Growth",
                                        f"{po_growth:.1f}%",
                                        delta=f"{latest_po - previous_po:,} POs",
                                        delta_color="normal" if po_growth > 0 else "inverse"
                                    )
                                
                                with col3:
                                    st.metric(
                                        "Avg Monthly Spend",
                                        f"${avg_monthly_value/1000000:.1f}M",
                                        help="Average monthly purchase value"
                                    )
                        
                        with analysis_tabs[2]:  # By Location
                            st.markdown("##### Purchase Analysis by Vendor Location")
                            
                            # Get vendor location data from po_df
                            if 'vendor_location_type' in po_df.columns:
                                location_analysis = po_df.groupby(['period', 'vendor_location_type']).agg({
                                    'total_amount_usd': 'sum',
                                    'po_number': 'nunique',
                                    'vendor_name': 'nunique'
                                }).reset_index()
                                
                                # Create stacked area chart
                                fig_location = px.area(
                                    location_analysis,
                                    x='period',
                                    y='total_amount_usd',
                                    color='vendor_location_type',
                                    title='Purchase Value by Vendor Location Over Time',
                                    labels={'total_amount_usd': 'Purchase Value (USD)', 'vendor_location_type': 'Location'},
                                    color_discrete_map={
                                        'Domestic': '#3498db',
                                        'International': '#e67e22'
                                    }
                                )
                                st.plotly_chart(fig_location, use_container_width=True)
                                
                                # Location summary
                                location_summary = po_df.groupby('vendor_location_type').agg({
                                    'total_amount_usd': 'sum',
                                    'po_number': 'nunique',
                                    'vendor_name': 'nunique',
                                    'outstanding_arrival_amount_usd': 'sum'
                                }).reset_index()
                                
                                col1, col2 = st.columns(2)
                                
                                with col1:
                                    # Pie chart for value distribution
                                    fig_pie = px.pie(
                                        location_summary,
                                        values='total_amount_usd',
                                        names='vendor_location_type',
                                        title='Value Distribution by Location'
                                    )
                                    st.plotly_chart(fig_pie, use_container_width=True)
                                
                                with col2:
                                    # Summary table
                                    location_summary['% of Total'] = (location_summary['total_amount_usd'] / location_summary['total_amount_usd'].sum() * 100).round(1)
                                    location_summary['Avg PO Value'] = location_summary['total_amount_usd'] / location_summary['po_number']
                                    
                                    display_location = location_summary[['vendor_location_type', 'vendor_name', 'po_number', 'total_amount_usd', '% of Total']].copy()
                                    display_location.columns = ['Location', 'Vendors', 'POs', 'Total Value', '% Share']
                                    display_location['Total Value'] = display_location['Total Value'].apply(lambda x: f"${x:,.0f}")
                                    display_location['% Share'] = display_location['% Share'].apply(lambda x: f"{x}%")
                                    
                                    st.dataframe(display_location, use_container_width=True, hide_index=True)
                        
                        with analysis_tabs[3]:  # By Type
                            st.markdown("##### Purchase Analysis by Vendor Type")
                            
                            # Get vendor type data from po_df
                            if 'vendor_type' in po_df.columns:
                                type_analysis = po_df.groupby(['period', 'vendor_type']).agg({
                                    'total_amount_usd': 'sum',
                                    'po_number': 'nunique',
                                    'vendor_name': 'nunique'
                                }).reset_index()
                                
                                # Create line chart for trends by type
                                fig_type_trend = px.line(
                                    type_analysis,
                                    x='period',
                                    y='total_amount_usd',
                                    color='vendor_type',
                                    title='Purchase Trends by Vendor Type',
                                    labels={'total_amount_usd': 'Purchase Value (USD)', 'vendor_type': 'Vendor Type'},
                                    markers=True,
                                    color_discrete_map={
                                        'Internal': '#2ecc71',
                                        'External': '#3498db'
                                    }
                                )
                                st.plotly_chart(fig_type_trend, use_container_width=True)
                                
                                # Type comparison
                                type_summary = po_df.groupby('vendor_type').agg({
                                    'total_amount_usd': 'sum',
                                    'po_number': 'nunique',
                                    'vendor_name': 'nunique',
                                    'payment_term': lambda x: x.mode()[0] if len(x) > 0 else 'N/A'
                                }).reset_index()
                                
                                # Display metrics
                                col1, col2, col3, col4 = st.columns(4)
                                
                                for idx, vendor_type in enumerate(type_summary['vendor_type'].unique()):
                                    type_data = type_summary[type_summary['vendor_type'] == vendor_type].iloc[0]
                                    col = [col1, col2, col3, col4][idx % 4]
                                    
                                    with col:
                                        st.metric(
                                            f"{vendor_type} Vendors",
                                            f"{type_data['vendor_name']:,}",
                                            help=f"Total {vendor_type.lower()} vendors"
                                        )
                                        st.metric(
                                            "Total Value",
                                            f"${type_data['total_amount_usd']/1000000:.1f}M"
                                        )
                                        st.metric(
                                            "Common Payment Term",
                                            type_data['payment_term']
                                        )
                    else:
                        st.info("No period analysis data available")
            else:
                st.warning("No purchase order data available for analysis")
        
        with tabs[2]:  # Performance Trends Tab
            st.subheader("📈 Performance Trends")
            
            if not po_df.empty and all(col in po_df.columns for col in ['po_date', 'eta', 'etd', 'status']):
                # Calculate rolling performance metrics
                po_df['month'] = pd.to_datetime(po_df['po_date']).dt.to_period('M').dt.to_timestamp()
                
                # Monthly performance calculation
                monthly_performance = po_df.groupby(['month', 'vendor_name']).apply(
                    lambda x: pd.Series({
                        'on_time_deliveries': ((pd.to_datetime(x['eta']) <= pd.to_datetime(x['etd'])) & 
                                             (x['status'] == 'COMPLETED')).sum(),
                        'total_deliveries': (x['status'] == 'COMPLETED').sum(),
                        'avg_lead_time': (pd.to_datetime(x['eta']) - pd.to_datetime(x['etd'])).dt.days.mean() 
                                        if len(x) > 0 else 0,
                        'over_deliveries': (x.get('is_over_delivered', 'N') == 'Y').sum() 
                                         if 'is_over_delivered' in x.columns else 0,
                        'total_value': x['total_amount_usd'].sum()
                    })
                ).reset_index()
                
                # Calculate rates
                monthly_performance['on_time_rate'] = (
                    monthly_performance['on_time_deliveries'] / 
                    monthly_performance['total_deliveries'].replace(0, np.nan) * 100
                ).fillna(0)
                
                if selected_vendor_display != "All Vendors" and selected_vendor_name:
                    vendor_perf = monthly_performance[monthly_performance['vendor_name'] == selected_vendor_name]
                    
                    if not vendor_perf.empty:
                        # Create performance trend charts
                        fig_perf = make_subplots(
                            rows=2, cols=2,
                            subplot_titles=('On-Time Delivery Rate', 'Average Lead Time',
                                          'Over-Delivery Trend', 'Monthly Value'),
                            specs=[[{}, {}], [{}, {}]]
                        )
                        
                        # On-time rate
                        fig_perf.add_trace(
                            go.Scatter(x=vendor_perf['month'], y=vendor_perf['on_time_rate'],
                                     mode='lines+markers', name='On-Time Rate',
                                     line=dict(color='#2ecc71', width=3)),
                            row=1, col=1
                        )
                        fig_perf.add_hline(y=80, line_dash="dash", line_color="red", 
                                         opacity=0.5, row=1, col=1)
                        
                        # Lead time
                        fig_perf.add_trace(
                            go.Scatter(x=vendor_perf['month'], y=vendor_perf['avg_lead_time'],
                                     mode='lines+markers', name='Lead Time (days)',
                                     line=dict(color='#3498db', width=3)),
                            row=1, col=2
                        )
                        
                        # Over-deliveries
                        fig_perf.add_trace(
                            go.Bar(x=vendor_perf['month'], y=vendor_perf['over_deliveries'],
                                  name='Over-Deliveries', marker_color='#e74c3c'),
                            row=2, col=1
                        )
                        
                        # Monthly value
                        fig_perf.add_trace(
                            go.Bar(x=vendor_perf['month'], y=vendor_perf['total_value'],
                                  name='Monthly Value', marker_color='#9b59b6'),
                            row=2, col=2
                        )
                        
                        fig_perf.update_layout(height=700, showlegend=False)
                        st.plotly_chart(fig_perf, use_container_width=True)
                    else:
                        st.info("No performance trend data available for the selected vendor")
                else:
                    st.info("Please select a specific vendor to view performance trends")
            else:
                st.warning("Insufficient data for performance trend analysis")
        
        with tabs[3]:  # Product Analysis Tab
            st.subheader("📦 Product Mix Analysis")
            
            if selected_vendor_display != "All Vendors" and selected_vendor_name and not po_df.empty:
                # Filter PO data for selected vendor
                vendor_po_df = po_df[po_df['vendor_name'] == selected_vendor_name]
                
                if not vendor_po_df.empty:
                    # Product summary
                    product_analysis = vendor_po_df.groupby(['product_name', 'pt_code', 'brand']).agg({
                        'po_line_id': 'count',
                        'standard_quantity': 'sum',
                        'total_amount_usd': 'sum',
                        'standard_unit_cost': 'mean'
                    }).reset_index()
                    
                    product_analysis.columns = ['Product', 'PT Code', 'Brand', 'Order Lines', 
                                              'Total Qty', 'Total Value', 'Avg Unit Cost']
                    
                    # Top products chart
                    top_products = product_analysis.nlargest(15, 'Total Value')
                    
                    if not top_products.empty:
                        fig_products = px.treemap(
                            top_products,
                            path=['Brand', 'Product'],
                            values='Total Value',
                            title=f"Product Mix by Value - {selected_vendor_name}",
                            color='Total Qty',
                            color_continuous_scale='Viridis'
                        )
                        st.plotly_chart(fig_products, use_container_width=True)
                        
                        # Product details table
                        st.markdown("#### Product Purchase Details")
                        
                        display_products = product_analysis.sort_values('Total Value', ascending=False).head(20)
                        display_products['Total Value'] = display_products['Total Value'].apply(lambda x: f"${x:,.0f}")
                        display_products['Avg Unit Cost'] = display_products['Avg Unit Cost'].apply(lambda x: f"${x:.2f}")
                        display_products['Total Qty'] = display_products['Total Qty'].apply(lambda x: f"{x:,.0f}")
                        
                        st.dataframe(
                            display_products,
                            use_container_width=True,
                            hide_index=True
                        )
                        
                        # Price trend analysis
                        if 'po_date' in vendor_po_df.columns:
                            st.markdown("#### Price Trend Analysis")
                            
                            # Get top 5 products by value
                            top_5_products = product_analysis.nlargest(5, 'Total Value')['Product'].tolist()
                            
                            price_trend_data = vendor_po_df[vendor_po_df['product_name'].isin(top_5_products)].copy()
                            
                            if not price_trend_data.empty:
                                price_trend_data['month'] = pd.to_datetime(price_trend_data['po_date']).dt.to_period('M').dt.to_timestamp()
                                
                                price_trend = price_trend_data.groupby(['month', 'product_name'])['standard_unit_cost'].mean().reset_index()
                                
                                if not price_trend.empty:
                                    fig_price = px.line(
                                        price_trend,
                                        x='month',
                                        y='standard_unit_cost',
                                        color='product_name',
                                        title="Unit Price Trends - Top 5 Products",
                                        labels={'standard_unit_cost': 'Unit Cost (USD)', 'product_name': 'Product'}
                                    )
                                    st.plotly_chart(fig_price, use_container_width=True)
                    else:
                        st.info("No product data available for analysis")
                else:
                    st.info("No purchase orders found for the selected vendor")
            else:
                st.info("Please select a specific vendor to view product analysis")
        
        with tabs[4]:  # Payment Analysis Tab
            st.subheader("💳 Payment Terms & Financial Analysis")
            
            if selected_vendor_display != "All Vendors" and selected_vendor_name and not po_df.empty:
                vendor_po_df = po_df[po_df['vendor_name'] == selected_vendor_name]
                
                if not vendor_po_df.empty and 'payment_term' in vendor_po_df.columns:
                    # Payment terms summary
                    payment_summary = vendor_po_df.groupby('payment_term').agg({
                        'po_number': 'nunique',
                        'total_amount_usd': 'sum',
                        'outstanding_invoiced_amount_usd': 'sum'
                    }).reset_index()
                    
                    if not payment_summary.empty:
                        payment_summary['paid_percentage'] = (
                            (payment_summary['total_amount_usd'] - payment_summary['outstanding_invoiced_amount_usd']) / 
                            payment_summary['total_amount_usd'] * 100
                        ).fillna(0)
                        
                        # Payment terms distribution
                        col1, col2 = st.columns(2)
                        
                        with col1:
                            fig_payment_dist = px.pie(
                                payment_summary,
                                values='total_amount_usd',
                                names='payment_term',
                                title="Value Distribution by Payment Terms"
                            )
                            st.plotly_chart(fig_payment_dist, use_container_width=True)
                        
                        with col2:
                            fig_payment_status = px.bar(
                                payment_summary,
                                x='payment_term',
                                y='outstanding_invoiced_amount_usd',
                                color='paid_percentage',
                                title="Outstanding Amounts by Payment Terms",
                                color_continuous_scale='RdYlGn_r'
                            )
                            st.plotly_chart(fig_payment_status, use_container_width=True)
                    
                    # Currency analysis
                    if 'currency' in vendor_po_df.columns:
                        st.markdown("#### Currency Exposure")
                        
                        currency_summary = vendor_po_df.groupby('currency').agg({
                            'total_amount': 'sum',
                            'total_amount_usd': 'sum',
                            'po_number': 'nunique'
                        }).reset_index()
                        
                        if not currency_summary.empty:
                            col1, col2 = st.columns([1, 2])
                            
                            with col1:
                                st.dataframe(
                                    currency_summary.rename(columns={
                                        'currency': 'Currency',
                                        'total_amount': 'Local Amount',
                                        'total_amount_usd': 'USD Amount',
                                        'po_number': 'PO Count'
                                    }).style.format({
                                        'Local Amount': '{:,.0f}',
                                        'USD Amount': '${:,.0f}'
                                    }),
                                    use_container_width=True,
                                    hide_index=True
                                )
                            
                            with col2:
                                fig_currency = px.pie(
                                    currency_summary,
                                    values='total_amount_usd',
                                    names='currency',
                                    title="Purchase Value by Currency"
                                )
                                st.plotly_chart(fig_currency, use_container_width=True)
                else:
                    st.info("No payment data available for the selected vendor")
            else:
                st.info("Please select a specific vendor to view payment analysis")
        
        with tabs[5]:  # Export Report Tab
            st.subheader("📄 Export Vendor Report")
            st.markdown("Generate comprehensive vendor report for meetings and negotiations")
            
            # Report configuration
            col1, col2 = st.columns(2)
            
            with col1:
                report_format = st.selectbox(
                    "Report Format",
                    ["Excel (Multi-sheet)", "PDF Report", "PowerPoint Presentation"]
                )
                
                include_sections = st.multiselect(
                    "Include Sections",
                    ["Executive Summary", "Performance Metrics", "Purchase History", 
                     "Product Analysis", "Payment Analysis", "Recommendations"],
                    default=["Executive Summary", "Performance Metrics", "Purchase History", "Product Analysis"]
                )
            
            with col2:
                report_period = st.selectbox(
                    "Report Period",
                    ["Last 3 Months", "Last 6 Months", "Last 12 Months", "Year to Date"]
                )
                
                include_charts = st.checkbox("Include Charts & Visualizations", value=True)
                include_comparisons = st.checkbox("Include Period Comparisons", value=True)
            
            # Generate report button
            if st.button("🚀 Generate Report", type="primary"):
                with st.spinner("Generating vendor report..."):
                    if selected_vendor_display != "All Vendors" and selected_vendor_name:
                        # Prepare data for export
                        if not vendor_metrics.empty:
                            vendor_data = vendor_metrics[vendor_metrics['vendor_name'] == selected_vendor_name]
                            
                            if not vendor_data.empty and not po_df.empty:
                                # Get purchase history
                                vendor_po_data = po_df[po_df['vendor_name'] == selected_vendor_name]
                                
                                # Select relevant columns if they exist
                                history_columns = ['po_number', 'po_date', 'etd', 'eta', 'status',
                                                 'total_amount_usd', 'currency', 'payment_term']
                                
                                # Add optional columns if they exist
                                optional_cols = ['arrival_completion_percent', 'invoice_completion_percent']
                                for col in optional_cols:
                                    if col in vendor_po_data.columns:
                                        history_columns.append(col)
                                
                                # Filter columns that actually exist
                                existing_cols = [col for col in history_columns if col in vendor_po_data.columns]
                                purchase_history = vendor_po_data[existing_cols].copy()
                                
                                # Get product analysis
                                product_data = vendor_po_data.groupby(['product_name', 'brand']).agg({
                                    'standard_quantity': 'sum',
                                    'total_amount_usd': 'sum',
                                    'po_line_id': 'count'
                                }).reset_index()
                                
                                if report_format == "Excel (Multi-sheet)":
                                    excel_file = export_vendor_report_to_excel(
                                        vendor_data, 
                                        vendor_metrics,
                                        purchase_history,
                                        product_data,
                                        filename=f"vendor_report_{selected_vendor_name}_{datetime.now().strftime('%Y%m%d')}.xlsx"
                                    )
                                    
                                    st.download_button(
                                        label="📥 Download Excel Report",
                                        data=excel_file,
                                        file_name=f"vendor_report_{selected_vendor_name}_{datetime.now().strftime('%Y%m%d')}.xlsx",
                                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                                    )
                                    
                                    st.success("✅ Report generated successfully!")
                                
                                elif report_format == "PDF Report":
                                    st.info("PDF report generation would be implemented here")
                                
                                else:  # PowerPoint
                                    st.info("PowerPoint presentation generation would be implemented here")
                            else:
                                st.warning("Insufficient data to generate report")
                        else:
                            st.warning("No vendor metrics available for report generation")
                    else:
                        st.warning("Please select a specific vendor to generate detailed report")
    
    else:
        # No data available
        st.warning("No data available for vendor performance analysis. Please check:")
        st.write("- Vendor selection is valid")
        st.write("- Selected time period contains data")
        st.write("- Database connection is working")
        
        # Show what data we have
        with st.expander("Data Status"):
            st.write(f"Vendor metrics empty: {vendor_metrics.empty if vendor_metrics is not None else 'None'}")
            st.write(f"PO data empty: {po_df.empty if po_df is not None else 'None'}")
            if po_df is not None and not po_df.empty:
                st.write(f"PO data shape: {po_df.shape}")
                st.write(f"Unique vendors in PO data: {po_df['vendor_name'].nunique() if 'vendor_name' in po_df.columns else 'N/A'}")

# Other report types remain the same...
elif report_type == "📦 Inventory Pipeline Report":
    st.header("📦 Inventory Pipeline Report")
    
    # Load pipeline data
    with st.spinner("Loading inventory pipeline data..."):
        pipeline_df = data_loader.get_product_demand_vs_incoming()
        po_timeline = data_loader.get_po_timeline_data(weeks_ahead=12)
    
    if not pipeline_df.empty:
        # Pipeline summary metrics
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            products_at_risk = len(pipeline_df[pipeline_df['total_coverage_percent'] < 50])
            st.metric("Products at Risk", products_at_risk, 
                     help="Products with <50% coverage")
        
        with col2:
            total_shortage = pipeline_df[pipeline_df['net_requirement'] > 0]['net_requirement'].sum()
            st.metric("Total Net Requirement", f"{total_shortage:,.0f} units")
        
        with col3:
            avg_coverage = pipeline_df['total_coverage_percent'].mean()
            st.metric("Avg Coverage", f"{avg_coverage:.1f}%")
        
        with col4:
            critical_products = len(pipeline_df[pipeline_df['net_requirement'] > 1000])
            st.metric("Critical Products", critical_products,
                     help="Net requirement > 1000 units")
        
        # Product shortage analysis
        st.subheader("🚨 Product Supply Analysis")
        
        # Filter for products needing attention
        shortage_df = pipeline_df[pipeline_df['net_requirement'] > 0].head(20)
        
        if not shortage_df.empty:
            fig_shortage = px.bar(
                shortage_df,
                x='pt_code',
                y=['total_demand', 'current_stock', 'incoming_supply'],
                title="Top 20 Products with Net Requirements",
                labels={'value': 'Quantity', 'pt_code': 'Product'},
                barmode='group',
                color_discrete_map={
                    'total_demand': '#e74c3c',
                    'current_stock': '#3498db', 
                    'incoming_supply': '#2ecc71'
                }
            )
            st.plotly_chart(fig_shortage, use_container_width=True)
            
            # Detailed shortage table
            st.markdown("#### Supply Status Details")
            
            # Select columns that exist
            display_columns = ['pt_code', 'product', 'total_demand', 'current_stock',
                             'incoming_supply', 'total_available', 'net_requirement', 
                             'total_coverage_percent', 'supply_status']
            
            # Add optional columns if they exist
            if 'next_arrival_date_eta' in shortage_df.columns:
                display_columns.append('next_arrival_date_eta')
            elif 'next_arrival_date_etd' in shortage_df.columns:
                display_columns.append('next_arrival_date_etd')
            
            # Filter existing columns
            existing_cols = [col for col in display_columns if col in shortage_df.columns]
            shortage_display = shortage_df[existing_cols].copy()
            
            # Format date columns if they exist
            for col in shortage_display.columns:
                if 'next_arrival_date' in col:
                    shortage_display[col] = pd.to_datetime(
                        shortage_display[col]
                    ).dt.strftime('%Y-%m-%d')
            
            st.dataframe(
                shortage_display.style.format({
                    'total_demand': '{:,.0f}',
                    'current_stock': '{:,.0f}',
                    'incoming_supply': '{:,.0f}',
                    'total_available': '{:,.0f}',
                    'net_requirement': '{:,.0f}',
                    'total_coverage_percent': '{:.1f}%'
                }).background_gradient(
                    subset=['total_coverage_percent'], 
                    cmap='RdYlGn',
                    vmin=0,
                    vmax=100
                ),
                use_container_width=True,
                hide_index=True
            )
        
        # Pipeline timeline
        st.markdown("---")
        st.subheader("📅 Incoming Supply Timeline")
        
        if not po_timeline.empty:
            # Create weekly summary
            po_timeline['week'] = pd.to_datetime(po_timeline['arrival_date']).dt.to_period('W').dt.to_timestamp()
            weekly_pipeline = po_timeline.groupby('week').agg({
                'arrival_qty': 'sum',
                'arrival_value': 'sum',
                'po_count': 'sum'
            }).reset_index()
            
            # Create dual-axis chart
            fig_timeline = make_subplots(specs=[[{"secondary_y": True}]])
            
            fig_timeline.add_trace(
                go.Bar(x=weekly_pipeline['week'], y=weekly_pipeline['arrival_qty'],
                      name='Arrival Quantity', marker_color='#3498db'),
                secondary_y=False,
            )
            
            fig_timeline.add_trace(
                go.Scatter(x=weekly_pipeline['week'], y=weekly_pipeline['arrival_value'],
                          mode='lines+markers', name='Value (USD)', 
                          line=dict(color='#e74c3c', width=3)),
                secondary_y=True,
            )
            
            fig_timeline.update_xaxes(title_text="Week")
            fig_timeline.update_yaxes(title_text="Quantity", secondary_y=False)
            fig_timeline.update_yaxes(title_text="Value (USD)", secondary_y=True)
            fig_timeline.update_layout(title="Weekly Incoming Supply Forecast")
            
            st.plotly_chart(fig_timeline, use_container_width=True)

elif report_type == "💰 Financial Analytics":
    st.header("💰 Financial Analytics")
    
    # Load financial data
    with st.spinner("Loading financial data..."):
        po_df = data_loader.load_po_data()
        financial_summary = data_loader.get_financial_summary()
    
    if po_df is not None and not po_df.empty:
        # Financial KPIs
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            total_committed = po_df['total_amount_usd'].sum()
            st.metric("Total Committed", f"${total_committed/1000000:.1f}M")
        
        with col2:
            outstanding_arrival = po_df['outstanding_arrival_amount_usd'].sum()
            st.metric("Outstanding Arrivals", f"${outstanding_arrival/1000000:.1f}M")
        
        with col3:
            outstanding_invoice = po_df['outstanding_invoiced_amount_usd'].sum()
            st.metric("Outstanding Invoices", f"${outstanding_invoice/1000000:.1f}M")
        
        with col4:
            paid_percentage = (1 - outstanding_invoice / total_committed) * 100 if total_committed > 0 else 0
            st.metric("Payment Progress", f"{paid_percentage:.1f}%")
        
        # Currency exposure analysis
        st.subheader("💱 Currency Exposure Analysis")
        
        if not financial_summary.empty:
            col1, col2 = st.columns(2)
            
            with col1:
                # Currency distribution pie chart
                fig_currency = px.pie(
                    financial_summary,
                    values='total_amount_local',
                    names='currency',
                    title="PO Value by Currency"
                )
                st.plotly_chart(fig_currency, use_container_width=True)
            
            with col2:
                # Currency details table
                currency_display = financial_summary[['currency', 'po_count', 
                                                    'total_amount_local', 
                                                    'avg_exchange_rate']].copy()
                
                currency_display['total_amount_local'] = currency_display['total_amount_local'].apply(
                    lambda x: f"{x:,.0f}"
                )
                currency_display['avg_exchange_rate'] = currency_display['avg_exchange_rate'].apply(
                    lambda x: f"{x:.4f}" if x else "N/A"
                )
                
                st.dataframe(currency_display, use_container_width=True, hide_index=True)
        
        # Payment terms analysis
        st.markdown("---")
        st.subheader("📋 Payment Terms Analysis")
        
        payment_analysis = po_df.groupby('payment_term').agg({
            'po_number': 'nunique',
            'total_amount_usd': 'sum',
            'outstanding_invoiced_amount_usd': 'sum'
        }).reset_index()
        
        payment_analysis['paid_percentage'] = (
            (payment_analysis['total_amount_usd'] - payment_analysis['outstanding_invoiced_amount_usd']) / 
            payment_analysis['total_amount_usd'] * 100
        ).fillna(0)
        
        fig_payment = px.bar(
            payment_analysis,
            x='payment_term',
            y='outstanding_invoiced_amount_usd',
            color='paid_percentage',
            title="Outstanding Amount by Payment Terms",
            labels={'outstanding_invoiced_amount_usd': 'Outstanding USD'},
            color_continuous_scale='RdYlGn_r'
        )
        st.plotly_chart(fig_payment, use_container_width=True)
        
        # Cash flow projection
        st.markdown("---")
        st.subheader("💸 Cash Flow Projection")
        
        # Create monthly projection
        po_df['month'] = pd.to_datetime(po_df['etd']).dt.to_period('M').dt.to_timestamp()
        
        monthly_cashflow = po_df.groupby('month').agg({
            'outstanding_arrival_amount_usd': 'sum',
            'outstanding_invoiced_amount_usd': 'sum'
        }).reset_index()
        
        fig_cashflow = go.Figure()
        fig_cashflow.add_trace(go.Bar(
            x=monthly_cashflow['month'],
            y=monthly_cashflow['outstanding_arrival_amount_usd'],
            name='Expected Arrivals',
            marker_color='#3498db'
        ))
        fig_cashflow.add_trace(go.Bar(
            x=monthly_cashflow['month'],
            y=monthly_cashflow['outstanding_invoiced_amount_usd'],
            name='Expected Payments',
            marker_color='#e74c3c'
        ))
        
        fig_cashflow.update_layout(
            title="Monthly Cash Flow Projection",
            xaxis_title="Month",
            yaxis_title="Amount (USD)",
            barmode='group'
        )
        st.plotly_chart(fig_cashflow, use_container_width=True)

elif report_type == "📈 Trend Analysis":
    st.header("📈 Trend Analysis")
    
    # Time period selector
    col1, col2 = st.columns([1, 3])
    with col1:
        trend_period = st.selectbox(
            "Analysis Period",
            ["Last 3 Months", "Last 6 Months", "Last 12 Months", "Year to Date"]
        )
    
    # Calculate date range
    if trend_period == "Last 3 Months":
        start_date = datetime.now().date() - timedelta(days=90)
    elif trend_period == "Last 6 Months":
        start_date = datetime.now().date() - timedelta(days=180)
    elif trend_period == "Last 12 Months":
        start_date = datetime.now().date() - timedelta(days=365)
    else:  # Year to Date
        start_date = datetime.now().date().replace(month=1, day=1)
    
    # Load trend data
    filters = {'date_from': start_date, 'date_to': datetime.now().date()}
    
    with st.spinner("Analyzing trends..."):
        po_df = data_loader.load_po_data(filters)
    
    if po_df is not None and not po_df.empty:
        # Create trend visualizations
        po_df['month'] = pd.to_datetime(po_df['po_date']).dt.to_period('M').dt.to_timestamp()
        
        # Monthly trends
        monthly_trends = po_df.groupby('month').agg({
            'po_number': 'nunique',
            'po_line_id': 'count',
            'total_amount_usd': 'sum',
            'vendor_name': 'nunique'
        }).reset_index()
        
        # Create subplots
        fig_trends = make_subplots(
            rows=2, cols=2,
            subplot_titles=('PO Count Trend', 'Total Spend Trend',
                          'Vendor Count Trend', 'Average PO Value Trend')
        )
        
        # 1. PO Count Trend
        fig_trends.add_trace(
            go.Scatter(x=monthly_trends['month'], y=monthly_trends['po_number'],
                      mode='lines+markers', name='PO Count',
                      line=dict(color='#3498db', width=3)),
            row=1, col=1
        )
        
        # 2. Total Spend Trend
        fig_trends.add_trace(
            go.Scatter(x=monthly_trends['month'], y=monthly_trends['total_amount_usd'],
                      mode='lines+markers', name='Total Spend',
                      line=dict(color='#2ecc71', width=3)),
            row=1, col=2
        )
        
        # 3. Vendor Count Trend
        fig_trends.add_trace(
            go.Scatter(x=monthly_trends['month'], y=monthly_trends['vendor_name'],
                      mode='lines+markers', name='Vendor Count',
                      line=dict(color='#e74c3c', width=3)),
            row=2, col=1
        )
        
        # 4. Average PO Value Trend
        monthly_trends['avg_po_value'] = monthly_trends['total_amount_usd'] / monthly_trends['po_number']
        fig_trends.add_trace(
            go.Scatter(x=monthly_trends['month'], y=monthly_trends['avg_po_value'],
                      mode='lines+markers', name='Avg PO Value',
                      line=dict(color='#f39c12', width=3)),
            row=2, col=2
        )
        
        fig_trends.update_layout(height=700, showlegend=False)
        st.plotly_chart(fig_trends, use_container_width=True)
        
        # Seasonality Analysis
        st.markdown("---")
        st.subheader("📊 Seasonality Analysis")
        
        # Extract month name for seasonality
        po_df['month_name'] = pd.to_datetime(po_df['po_date']).dt.strftime('%B')
        po_df['month_num'] = pd.to_datetime(po_df['po_date']).dt.month
        
        seasonality_df = po_df.groupby(['month_num', 'month_name']).agg({
            'total_amount_usd': 'sum',
            'po_number': 'nunique'
        }).reset_index().sort_values('month_num')
        
        col1, col2 = st.columns(2)
        
        with col1:
            fig_seasonal_value = px.bar(
                seasonality_df,
                x='month_name',
                y='total_amount_usd',
                title='Spend by Month',
                labels={'total_amount_usd': 'Total Spend (USD)'},
                color='total_amount_usd',
                color_continuous_scale='Blues'
            )
            st.plotly_chart(fig_seasonal_value, use_container_width=True)
        
        with col2:
            fig_seasonal_count = px.bar(
                seasonality_df,
                x='month_name',
                y='po_number',
                title='PO Count by Month',
                labels={'po_number': 'Number of POs'},
                color='po_number',
                color_continuous_scale='Greens'
            )
            st.plotly_chart(fig_seasonal_count, use_container_width=True)

else:  # Custom Report Builder
    st.header("🎯 Custom Report Builder")
    st.info("This feature allows you to create custom reports based on your specific requirements.")
    
    # Report configuration
    col1, col2 = st.columns([1, 2])
    
    with col1:
        st.subheader("Report Configuration")
        
        # Report name
        report_name = st.text_input("Report Name", value="Custom Report")
        
        # Data source selection
        data_sources = st.multiselect(
            "Select Data Sources",
            ["Purchase Orders", "Container Arrivals", "Vendor Performance", "Financial Data"],
            default=["Purchase Orders"]
        )
        
        # Metrics selection
        st.markdown("#### Select Metrics")
        metrics = {
            "PO Metrics": st.checkbox("PO Count, Value, Status"),
            "Vendor Metrics": st.checkbox("Vendor Performance"),
            "Financial Metrics": st.checkbox("Currency, Payment Terms"),
            "Timeline Metrics": st.checkbox("ETD/ETA Analysis")
        }
        
        # Grouping options
        group_by = st.selectbox(
            "Group By",
            ["Vendor", "Product", "Brand", "Month", "Week", "Status"]
        )
        
        # Chart type
        chart_type = st.selectbox(
            "Visualization Type",
            ["Bar Chart", "Line Chart", "Pie Chart", "Table", "Mixed"]
        )
    
    with col2:
        st.subheader("Report Preview")
        
        if st.button("Generate Report", type="primary"):
            with st.spinner("Generating custom report..."):
                # Load data based on selections
                if "Purchase Orders" in data_sources:
                    po_df = data_loader.load_po_data()
                    
                    if not po_df.empty:
                        # Create sample visualization based on selections
                        if group_by == "Vendor" and chart_type == "Bar Chart":
                            vendor_summary = po_df.groupby('vendor_name')['total_amount_usd'].sum().nlargest(10)
                            
                            fig = px.bar(
                                x=vendor_summary.values,
                                y=vendor_summary.index,
                                orientation='h',
                                title=f"{report_name} - Top Vendors by Value",
                                labels={'x': 'Total Value (USD)', 'y': 'Vendor'}
                            )
                            st.plotly_chart(fig, use_container_width=True)
                        
                        elif group_by == "Month" and chart_type == "Line Chart":
                            po_df['month'] = pd.to_datetime(po_df['po_date']).dt.to_period('M').dt.to_timestamp()
                            monthly_data = po_df.groupby('month')['total_amount_usd'].sum()
                            
                            fig = px.line(
                                x=monthly_data.index,
                                y=monthly_data.values,
                                title=f"{report_name} - Monthly Trend",
                                labels={'x': 'Month', 'y': 'Total Value (USD)'}
                            )
                            st.plotly_chart(fig, use_container_width=True)
                        
                        # Export options
                        st.markdown("---")
                        col1, col2, col3 = st.columns(3)
                        
                        with col1:
                            if st.button("📊 Export to Excel"):
                                st.info("Excel export functionality would be implemented here")
                        
                        with col2:
                            if st.button("📄 Export to PDF"):
                                st.info("PDF export functionality would be implemented here")
                        
                        with col3:
                            if st.button("📧 Email Report"):
                                st.info("Email report functionality would be implemented here")
                else:
                    st.warning("Please select at least one data source and metric")

# Footer with export options
st.markdown("---")
col1, col2, col3 = st.columns([2, 1, 1])

with col1:
    st.caption(f"Report generated on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

with col2:
    if st.button("🖨️ Print Report"):
        st.info("Print functionality would open print dialog")

with col3:
    if st.button("📤 Share Report"):
        st.info("Share functionality would generate shareable link")