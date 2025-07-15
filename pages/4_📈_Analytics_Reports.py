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
                f"{vendor_data.get('avg_lead_time', 0):.1f} days",
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
        all_vendors = data_loader.get_vendor_list()
        if not all_vendors.empty:
            vendor_options = ["All Vendors"] + all_vendors['vendor_name'].tolist()
            selected_vendor = st.selectbox("Select Vendor", vendor_options)
        else:
            selected_vendor = "All Vendors"
    
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
    
    # Load vendor performance data
    with st.spinner("Analyzing vendor performance..."):
        if selected_vendor == "All Vendors":
            vendor_metrics = data_loader.get_vendor_performance_metrics(months=months_back)
            po_df = data_loader.load_po_data()
        else:
            vendor_metrics = data_loader.get_vendor_performance_metrics(
                vendor_name=selected_vendor, 
                months=months_back
            )
            po_df = data_loader.load_po_data({'vendors': [selected_vendor]})
    
    if not vendor_metrics.empty and po_df is not None:
        # Add performance score calculation
        vendor_metrics['performance_score'] = (
            vendor_metrics['on_time_rate'] * 0.4 +
            vendor_metrics['completion_rate'] * 0.4 +
            (100 - vendor_metrics['avg_over_delivery_percent'].fillna(0)) * 0.2
        ).round(1)
        
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
            
            if selected_vendor != "All Vendors":
                # Single vendor detailed view
                vendor_data = vendor_metrics.iloc[0]
                
                # Key metrics
                col1, col2, col3, col4 = st.columns(4)
                
                with col1:
                    st.metric(
                        "Total Purchase Value",
                        f"${vendor_data['total_po_value']:,.0f}",
                        help="Total value of all POs in the period"
                    )
                
                with col2:
                    st.metric(
                        "On-Time Delivery",
                        f"{vendor_data['on_time_rate']:.1f}%",
                        delta=f"{vendor_data['on_time_rate'] - 80:.1f}%" if vendor_data['on_time_rate'] >= 80 else None,
                        delta_color="normal" if vendor_data['on_time_rate'] >= 80 else "inverse"
                    )
                
                with col3:
                    st.metric(
                        "Completion Rate",
                        f"{vendor_data['completion_rate']:.1f}%",
                        help="Percentage of POs fully completed"
                    )
                
                with col4:
                    st.metric(
                        "Performance Score",
                        f"{vendor_data['performance_score']:.1f}%",
                        help="Overall performance score (weighted)"
                    )
                
                # Additional metrics
                st.markdown("---")
                col1, col2, col3, col4 = st.columns(4)
                
                with col1:
                    st.metric("Total POs", f"{vendor_data['total_pos']:,}")
                
                with col2:
                    st.metric("Completed POs", f"{vendor_data['completed_pos']:,}")
                
                with col3:
                    st.metric("Over Deliveries", f"{vendor_data['over_deliveries']:,}")
                
                with col4:
                    st.metric(
                        "Outstanding Amount",
                        f"${vendor_data['outstanding_invoices']:,.0f}"
                    )
                
            else:
                # All vendors comparison view
                st.markdown("### Top Performing Vendors")
                
                top_vendors = vendor_metrics.nlargest(10, 'performance_score')
                
                # Performance matrix scatter plot
                fig_matrix = px.scatter(
                    top_vendors,
                    x='on_time_rate',
                    y='completion_rate',
                    size='total_po_value',
                    color='performance_score',
                    hover_data=['vendor_name', 'total_pos', 'vendor_type', 'vendor_location_type'],
                    labels={
                        'on_time_rate': 'On-Time Delivery Rate (%)',
                        'completion_rate': 'PO Completion Rate (%)',
                        'performance_score': 'Performance Score'
                    },
                    title="Vendor Performance Matrix (Size = PO Value)",
                    color_continuous_scale='RdYlGn'
                )
                
                # Add quadrant lines
                fig_matrix.add_hline(y=80, line_dash="dash", line_color="gray", opacity=0.5)
                fig_matrix.add_vline(x=80, line_dash="dash", line_color="gray", opacity=0.5)
                
                # Add quadrant labels
                fig_matrix.add_annotation(x=95, y=95, text="⭐ Top Performers", showarrow=False)
                fig_matrix.add_annotation(x=95, y=50, text="⚡ Fast but Incomplete", showarrow=False)
                fig_matrix.add_annotation(x=50, y=95, text="🎯 Complete but Slow", showarrow=False)
                fig_matrix.add_annotation(x=50, y=50, text="⚠️ Need Improvement", showarrow=False)
                
                st.plotly_chart(fig_matrix, use_container_width=True)
            
            # Vendor comparison table
            st.markdown("### Vendor Performance Metrics")
            
            # Prepare display data
            display_metrics = vendor_metrics[[
                'vendor_name', 'vendor_type', 'vendor_location_type',
                'total_pos', 'completed_pos', 'on_time_rate', 
                'completion_rate', 'over_deliveries', 'avg_over_delivery_percent',
                'total_po_value', 'outstanding_invoices', 'performance_score'
            ]].copy()
            
            # Rename columns for display
            display_metrics.columns = [
                'Vendor', 'Type', 'Location', 'Total POs', 'Completed',
                'On-Time %', 'Completion %', 'Over Del.', 'Avg Over %',
                'Total Value', 'Outstanding', 'Score'
            ]
            
            # Format numeric columns
            display_metrics['Total Value'] = display_metrics['Total Value'].apply(lambda x: f"${x:,.0f}")
            display_metrics['Outstanding'] = display_metrics['Outstanding'].apply(lambda x: f"${x:,.0f}")
            
            # Apply conditional formatting
            st.dataframe(
                display_metrics.style.format({
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
                ),
                use_container_width=True,
                hide_index=True
            )
        
        with tabs[1]:  # Purchase Analysis Tab
            st.subheader("💰 Purchase Value Analysis")
            
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
                'brand': 'nunique',
                'product_name': 'nunique'
            }).reset_index()
            
            period_analysis.columns = ['Period', 'Vendor', 'PO Count', 'Total Value', 
                                     'Line Items', 'Brands', 'Products']
            
            # Create time series chart
            if selected_vendor != "All Vendors":
                vendor_period_data = period_analysis[period_analysis['Vendor'] == selected_vendor]
                
                fig_trend = make_subplots(
                    rows=2, cols=1,
                    subplot_titles=(f'Purchase Value Trend - {selected_vendor}', 
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
                # Top vendors by period
                st.markdown("#### Top Vendors by Purchase Value")
                
                # Get latest period data
                latest_period = period_analysis['Period'].max()
                latest_vendors = period_analysis[period_analysis['Period'] == latest_period].nlargest(10, 'Total Value')
                
                fig_top = px.bar(
                    latest_vendors,
                    x='Total Value',
                    y='Vendor',
                    orientation='h',
                    title=f"Top 10 Vendors - {latest_period.strftime('%Y-%m')}",
                    color='Total Value',
                    color_continuous_scale='Blues'
                )
                st.plotly_chart(fig_top, use_container_width=True)
        
        with tabs[2]:  # Performance Trends Tab
            st.subheader("📈 Performance Trends")
            
            # Calculate rolling performance metrics
            po_df['month'] = pd.to_datetime(po_df['po_date']).dt.to_period('M').dt.to_timestamp()
            
            # Monthly performance calculation
            monthly_performance = po_df.groupby(['month', 'vendor_name']).apply(
                lambda x: pd.Series({
                    'on_time_deliveries': ((x['eta'] >= x['etd']) & (x['status'] == 'COMPLETED')).sum(),
                    'total_deliveries': (x['status'] == 'COMPLETED').sum(),
                    'avg_lead_time': (pd.to_datetime(x['eta']) - pd.to_datetime(x['etd'])).dt.days.mean(),
                    'over_deliveries': (x['is_over_delivered'] == 'Y').sum(),
                    'total_value': x['total_amount_usd'].sum()
                })
            ).reset_index()
            
            # Calculate rates
            monthly_performance['on_time_rate'] = (
                monthly_performance['on_time_deliveries'] / 
                monthly_performance['total_deliveries'].replace(0, np.nan) * 100
            ).fillna(0)
            
            if selected_vendor != "All Vendors":
                vendor_perf = monthly_performance[monthly_performance['vendor_name'] == selected_vendor]
                
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
        
        with tabs[3]:  # Product Analysis Tab
            st.subheader("📦 Product Mix Analysis")
            
            if selected_vendor != "All Vendors":
                # Product performance for specific vendor
                vendor_po_df = po_df[po_df['vendor_name'] == selected_vendor]
                
                # Product summary
                product_analysis = vendor_po_df.groupby(['product_name', 'pt_code', 'brand']).agg({
                    'po_line_id': 'count',
                    'standard_quantity': 'sum',
                    'total_amount_usd': 'sum',
                    'standard_unit_cost': 'mean',
                    'etd': 'count'
                }).reset_index()
                
                product_analysis.columns = ['Product', 'PT Code', 'Brand', 'Order Lines', 
                                          'Total Qty', 'Total Value', 'Avg Unit Cost', 'PO Count']
                
                # Top products chart
                top_products = product_analysis.nlargest(15, 'Total Value')
                
                fig_products = px.treemap(
                    top_products,
                    path=['Brand', 'Product'],
                    values='Total Value',
                    title=f"Product Mix by Value - {selected_vendor}",
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
                st.markdown("#### Price Trend Analysis")
                
                # Get top 5 products by value
                top_5_products = product_analysis.nlargest(5, 'Total Value')['Product'].tolist()
                
                price_trend_data = vendor_po_df[vendor_po_df['product_name'].isin(top_5_products)].copy()
                price_trend_data['month'] = pd.to_datetime(price_trend_data['po_date']).dt.to_period('M').dt.to_timestamp()
                
                price_trend = price_trend_data.groupby(['month', 'product_name'])['standard_unit_cost'].mean().reset_index()
                
                fig_price = px.line(
                    price_trend,
                    x='month',
                    y='standard_unit_cost',
                    color='product_name',
                    title="Unit Price Trends - Top 5 Products",
                    labels={'standard_unit_cost': 'Unit Cost (USD)', 'product_name': 'Product'}
                )
                st.plotly_chart(fig_price, use_container_width=True)
        
        with tabs[4]:  # Payment Analysis Tab
            st.subheader("💳 Payment Terms & Financial Analysis")
            
            if selected_vendor != "All Vendors":
                vendor_po_df = po_df[po_df['vendor_name'] == selected_vendor]
                
                # Payment terms summary
                payment_summary = vendor_po_df.groupby('payment_term').agg({
                    'po_number': 'nunique',
                    'total_amount_usd': 'sum',
                    'outstanding_invoiced_amount_usd': 'sum'
                }).reset_index()
                
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
                st.markdown("#### Currency Exposure")
                
                currency_summary = vendor_po_df.groupby('currency').agg({
                    'total_amount': 'sum',
                    'total_amount_usd': 'sum',
                    'po_number': 'nunique'
                }).reset_index()
                
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
                    if selected_vendor != "All Vendors":
                        # Prepare data for export
                        vendor_data = vendor_metrics[vendor_metrics['vendor_name'] == selected_vendor]
                        
                        # Get purchase history
                        purchase_history = po_df[po_df['vendor_name'] == selected_vendor][[
                            'po_number', 'po_date', 'etd', 'eta', 'status',
                            'total_amount_usd', 'currency', 'payment_term',
                            'arrival_completion_percent', 'invoice_completion_percent'
                        ]].copy()
                        
                        # Get product analysis
                        product_data = po_df[po_df['vendor_name'] == selected_vendor].groupby(['product_name', 'brand']).agg({
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
                                filename=f"vendor_report_{selected_vendor}_{datetime.now().strftime('%Y%m%d')}.xlsx"
                            )
                            
                            st.download_button(
                                label="📥 Download Excel Report",
                                data=excel_file,
                                file_name=f"vendor_report_{selected_vendor}_{datetime.now().strftime('%Y%m%d')}.xlsx",
                                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                            )
                            
                            st.success("✅ Report generated successfully!")
                        
                        elif report_format == "PDF Report":
                            st.info("PDF report generation would be implemented here")
                        
                        else:  # PowerPoint
                            st.info("PowerPoint presentation generation would be implemented here")
                    
                    else:
                        st.warning("Please select a specific vendor to generate detailed report")

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
            
            shortage_display = shortage_df[[
                'pt_code', 'product', 'total_demand', 'current_stock',
                'incoming_supply', 'total_available', 'net_requirement', 
                'total_coverage_percent', 'supply_status', 'next_arrival_date'
            ]].copy()
            
            if 'next_arrival_date' in shortage_display.columns:
                shortage_display['next_arrival_date'] = pd.to_datetime(
                    shortage_display['next_arrival_date']
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