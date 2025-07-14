# pages/4_📈_Analytics_Reports.py

import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
from utils.auth import AuthManager
from utils.data_loader import InboundDataLoader
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots

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
        
        # Risk Analysis Section
        st.markdown("---")
        st.subheader("⚠️ Risk Analysis")
        
        col1, col2 = st.columns(2)
        
        with col1:
            # Overdue Analysis
            overdue_df = po_df[po_df['etd'] < datetime.now().date()]
            if not overdue_df.empty:
                st.markdown("#### Overdue POs by Vendor")
                overdue_by_vendor = overdue_df.groupby('vendor_name').agg({
                    'po_number': 'nunique',
                    'outstanding_arrival_amount_usd': 'sum'
                }).reset_index()
                overdue_by_vendor.columns = ['Vendor', 'PO Count', 'Value USD']
                overdue_by_vendor = overdue_by_vendor.sort_values('Value USD', ascending=False).head(10)
                
                fig_overdue = px.bar(overdue_by_vendor, x='Value USD', y='Vendor',
                                   orientation='h', color='Value USD',
                                   color_continuous_scale='Reds')
                st.plotly_chart(fig_overdue, use_container_width=True)
            else:
                st.info("No overdue POs in the selected period")
        
        with col2:
            # Currency Exposure
            st.markdown("#### Currency Exposure")
            currency_exposure = po_df.groupby('currency')['total_amount_usd'].sum()
            
            fig_currency = px.pie(values=currency_exposure.values, 
                                names=currency_exposure.index,
                                title="Outstanding Value by Currency")
            st.plotly_chart(fig_currency, use_container_width=True)

elif report_type == "🏭 Vendor Performance Analysis":
    st.header("🏭 Vendor Performance Analysis")
    
    # Period selector
    months_back = st.slider("Analysis Period (Months)", 1, 12, 6)
    
    # Load vendor performance data
    with st.spinner("Analyzing vendor performance..."):
        vendor_metrics = data_loader.get_vendor_performance_metrics(months=months_back)
        po_df = data_loader.load_po_data()
    
    if not vendor_metrics.empty:
        # Add performance score
        vendor_metrics['performance_score'] = (
            vendor_metrics['on_time_rate'] * 0.4 +
            vendor_metrics['completion_rate'] * 0.4 +
            (100 - vendor_metrics['avg_over_delivery_percent']) * 0.2
        )
        
        # Display top performers
        st.subheader("🏆 Top Performing Vendors")
        
        top_vendors = vendor_metrics.nlargest(10, 'performance_score')
        
        # Create performance matrix
        fig_matrix = px.scatter(
            top_vendors,
            x='on_time_rate',
            y='completion_rate',
            size='total_po_value',
            color='performance_score',
            hover_data=['vendor_name', 'total_pos'],
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
        
        st.plotly_chart(fig_matrix, use_container_width=True)
        
        # Detailed vendor metrics table
        st.subheader("📊 Detailed Vendor Metrics")
        
        display_metrics = vendor_metrics[['vendor_name', 'total_pos', 'completed_pos',
                                        'on_time_rate', 'completion_rate', 
                                        'over_deliveries', 'total_po_value',
                                        'outstanding_invoices', 'performance_score']]
        
        display_metrics = display_metrics.rename(columns={
            'vendor_name': 'Vendor',
            'total_pos': 'Total POs',
            'completed_pos': 'Completed',
            'on_time_rate': 'On-Time %',
            'completion_rate': 'Completion %',
            'over_deliveries': 'Over Deliveries',
            'total_po_value': 'Total Value USD',
            'outstanding_invoices': 'Outstanding USD',
            'performance_score': 'Score'
        })
        
        # Format columns
        for col in ['On-Time %', 'Completion %', 'Score']:
            display_metrics[col] = display_metrics[col].apply(lambda x: f"{x:.1f}%")
        
        for col in ['Total Value USD', 'Outstanding USD']:
            display_metrics[col] = display_metrics[col].apply(lambda x: f"${x:,.0f}")
        
        st.dataframe(
            display_metrics.style.background_gradient(subset=['Score'], cmap='RdYlGn'),
            use_container_width=True,
            hide_index=True
        )
        
        # Vendor comparison
        st.markdown("---")
        st.subheader("🔍 Vendor Comparison")
        
        selected_vendors = st.multiselect(
            "Select vendors to compare",
            options=vendor_metrics['vendor_name'].tolist(),
            default=vendor_metrics.nlargest(5, 'total_po_value')['vendor_name'].tolist()
        )
        
        if selected_vendors:
            comparison_df = vendor_metrics[vendor_metrics['vendor_name'].isin(selected_vendors)]
            
            # Create radar chart
            categories = ['On-Time Rate', 'Completion Rate', 'Quality Score', 'Value Score', 'Overall']
            
            fig_radar = go.Figure()
            
            for vendor in selected_vendors:
                vendor_data = comparison_df[comparison_df['vendor_name'] == vendor].iloc[0]
                
                values = [
                    vendor_data['on_time_rate'],
                    vendor_data['completion_rate'],
                    100 - vendor_data['avg_over_delivery_percent'],  # Quality score
                    min(vendor_data['total_po_value'] / vendor_metrics['total_po_value'].max() * 100, 100),  # Value score
                    vendor_data['performance_score']
                ]
                
                fig_radar.add_trace(go.Scatterpolar(
                    r=values,
                    theta=categories,
                    fill='toself',
                    name=vendor
                ))
            
            fig_radar.update_layout(
                polar=dict(
                    radialaxis=dict(
                        visible=True,
                        range=[0, 100]
                    )),
                showlegend=True,
                title="Vendor Performance Comparison"
            )
            
            st.plotly_chart(fig_radar, use_container_width=True)

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
            products_at_risk = len(pipeline_df[pipeline_df['coverage_percent'] < 50])
            st.metric("Products at Risk", products_at_risk, 
                     help="Products with <50% coverage")
        
        with col2:
            total_shortage = pipeline_df[pipeline_df['net_shortage'] > 0]['net_shortage'].sum()
            st.metric("Total Shortage", f"{total_shortage:,.0f} units")
        
        with col3:
            avg_coverage = pipeline_df['coverage_percent'].mean()
            st.metric("Avg Coverage", f"{avg_coverage:.1f}%")
        
        with col4:
            critical_products = len(pipeline_df[pipeline_df['net_shortage'] > 1000])
            st.metric("Critical Products", critical_products,
                     help="Shortage > 1000 units")
        
        # Product shortage analysis
        st.subheader("🚨 Product Shortage Analysis")
        
        # Filter for products with shortage
        shortage_df = pipeline_df[pipeline_df['net_shortage'] > 0].head(20)
        
        if not shortage_df.empty:
            fig_shortage = px.bar(
                shortage_df,
                x='pt_code',
                y=['total_demand', 'incoming_supply'],
                title="Top 20 Products with Supply Shortage",
                labels={'value': 'Quantity', 'pt_code': 'Product'},
                barmode='group',
                color_discrete_map={'total_demand': '#e74c3c', 'incoming_supply': '#2ecc71'}
            )
            st.plotly_chart(fig_shortage, use_container_width=True)
            
            # Detailed shortage table
            st.markdown("#### Shortage Details")
            
            shortage_display = shortage_df[['pt_code', 'product', 'total_demand', 
                                          'incoming_supply', 'net_shortage', 
                                          'coverage_percent', 'next_arrival_date']].copy()
            
            shortage_display['next_arrival_date'] = pd.to_datetime(shortage_display['next_arrival_date']).dt.strftime('%Y-%m-%d')
            
            st.dataframe(
                shortage_display.style.format({
                    'total_demand': '{:,.0f}',
                    'incoming_supply': '{:,.0f}',
                    'net_shortage': '{:,.0f}',
                    'coverage_percent': '{:.1f}%'
                }).background_gradient(subset=['coverage_percent'], cmap='RdYlGn'),
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