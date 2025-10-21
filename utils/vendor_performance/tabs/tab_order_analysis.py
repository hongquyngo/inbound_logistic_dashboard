"""
Order Analysis Tab - Fixed Deprecations

Analyzes purchase orders by PO date
Tracks order lifecycle: Order Entry → Invoice → Payment

Version: 2.1
Last Updated: 2025-10-21
"""

import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
from typing import TYPE_CHECKING, Dict, Any

from ..calculations import PerformanceCalculator
from ..visualizations import ChartFactory, render_chart
from ..constants import format_currency, format_percentage, COLORS

if TYPE_CHECKING:
    from ..data_access import VendorPerformanceDAO


def render(
    dao: 'VendorPerformanceDAO',
    filters: Dict[str, Any],
    vendor_display: str
) -> None:
    """
    Render Order Analysis Tab
    
    Args:
        dao: Data access object
        filters: Global filters
        vendor_display: Selected vendor display string
    """
    st.subheader("📈 Order Analysis")
    st.markdown("*Track purchase orders by PO date through their full lifecycle*")
    
    # ==================== TAB-LEVEL DATE FILTER ====================
    st.markdown("---")
    st.markdown("#### 📅 Order Period Configuration")
    
    col1, col2, col3, col4 = st.columns([2, 1, 1, 1])
    
    with col1:
        date_range_option = st.selectbox(
            "Time Range",
            ["Last 3 Months", "Last 6 Months", "Last 12 Months", "Custom"],
            index=1,
            key="order_date_range"
        )
    
    # Calculate date range
    end_date = datetime.now().date()
    
    if date_range_option == "Custom":
        with col2:
            start_date = st.date_input(
                "From",
                value=end_date - timedelta(days=180),
                key="order_start_date"
            )
        with col3:
            end_date = st.date_input(
                "To",
                value=end_date,
                key="order_end_date"
            )
    else:
        months_map = {
            "Last 3 Months": 3,
            "Last 6 Months": 6,
            "Last 12 Months": 12
        }
        months = months_map[date_range_option]
        start_date = end_date - timedelta(days=months * 30)
        
        with col2:
            st.metric("From", start_date.strftime("%Y-%m-%d"))
        with col3:
            st.metric("To", end_date.strftime("%Y-%m-%d"))
    
    with col4:
        grouping_period = st.selectbox(
            "Group By",
            ["Monthly", "Quarterly", "Yearly"],
            index=0,
            key="order_grouping"
        )
    
    # Info box explaining the analysis
    st.info("""
    📊 **Order Cohort Analysis**: This tracks all purchase orders created between the selected dates.
    
    - **Order Entry**: Total PO value (based on `po_date`)
    - **Invoiced**: Amount invoiced **to date** for these POs (regardless of invoice date)
    - **Conversion Rate**: Invoiced / Order Entry × 100% (meaningful metric)
    - **Outstanding**: Orders not yet fully invoiced
    """)
    
    st.markdown("---")
    
    # ==================== LOAD DATA ====================
    
    with st.spinner("Loading order data..."):
        try:
            # Get summary data
            summary_df = dao.get_order_cohort_summary(
                start_date=datetime.combine(start_date, datetime.min.time()),
                end_date=datetime.combine(end_date, datetime.min.time()),
                filters=filters
            )
            
            # Get detail data for charts
            detail_df = dao.get_order_cohort_detail(
                start_date=datetime.combine(start_date, datetime.min.time()),
                end_date=datetime.combine(end_date, datetime.min.time()),
                filters=filters
            )
            
        except Exception as e:
            st.error(f"Error loading data: {str(e)}")
            return
    
    if summary_df.empty:
        st.warning("No order data found for the selected criteria")
        return
    
    # ==================== SUMMARY METRICS ====================
    
    st.markdown("### 🎯 Order Cohort Summary")
    
    # Aggregate totals
    total_order = summary_df['total_order_value'].sum()
    total_invoiced = summary_df['total_invoiced_value'].sum()
    total_outstanding = summary_df['outstanding_value'].sum()
    avg_conversion = summary_df['conversion_rate'].mean()
    total_pos = summary_df['total_pos'].sum()
    
    # Fix vendor count: if specific vendor selected, show 1, otherwise show actual count
    if vendor_display != "All Vendors" and filters.get('vendor_name'):
        vendor_count = 1
    else:
        vendor_count = len(summary_df)
    
    col1, col2, col3, col4, col5, col6 = st.columns(6)
    
    with col1:
        st.metric(
            "Vendors",
            f"{vendor_count:,}",
            help="Number of vendors with orders in period"
        )
    
    with col2:
        st.metric(
            "Total POs",
            f"{int(total_pos):,}",
            help="Purchase orders created in period"
        )
    
    with col3:
        st.metric(
            "Order Entry",
            format_currency(total_order, compact=True),
            help="Total PO value"
        )
    
    with col4:
        st.metric(
            "Invoiced",
            format_currency(total_invoiced, compact=True),
            delta=f"{(total_invoiced/total_order*100):.1f}%" if total_order > 0 else None,
            help="Amount invoiced to date"
        )
    
    with col5:
        st.metric(
            "Outstanding",
            format_currency(total_outstanding, compact=True),
            delta=f"{(total_outstanding/total_order*100):.1f}%" if total_order > 0 else None,
            delta_color="inverse",
            help="Not yet invoiced"
        )
    
    with col6:
        conversion_delta = avg_conversion - 90
        st.metric(
            "Avg Conversion",
            f"{avg_conversion:.1f}%",
            delta=f"{conversion_delta:+.1f}% vs 90%",
            delta_color="normal" if avg_conversion >= 90 else "inverse",
            help="Average conversion rate"
        )
    
    st.markdown("---")
    
    # ==================== VISUALIZATION ====================
    
    if vendor_display == "All Vendors":
        _render_all_vendors_view(summary_df, detail_df, grouping_period, start_date, end_date)
    else:
        vendor_name = filters.get('vendor_name')
        _render_single_vendor_view(summary_df, detail_df, vendor_name, grouping_period)


def _render_all_vendors_view(
    summary_df: pd.DataFrame,
    detail_df: pd.DataFrame,
    grouping_period: str,
    start_date: datetime,
    end_date: datetime
) -> None:
    """Render view for all vendors"""
    
    st.markdown("### 📊 Top Vendors by Order Value")
    
    # Top 10 vendors
    top_vendors = summary_df.nlargest(10, 'total_order_value')
    
    chart_factory = ChartFactory()
    
    col1, col2 = st.columns(2)
    
    with col1:
        fig_vendors = chart_factory.create_vendor_comparison_chart(
            top_vendors,
            top_n=10,
            metric='total_order_value'
        )
        render_chart(fig_vendors, key="chart_vendors_order")
    
    with col2:
        # Conversion rate distribution
        import plotly.express as px
        
        fig_conv = px.bar(
            top_vendors.sort_values('conversion_rate'),
            x='conversion_rate',
            y='vendor_name',
            orientation='h',
            title="Top 10 Vendors - Conversion Rate",
            labels={'conversion_rate': 'Conversion %', 'vendor_name': ''},
            color='conversion_rate',
            color_continuous_scale='RdYlGn',
            range_color=[0, 100]
        )
        fig_conv.update_layout(height=400, showlegend=False)
        render_chart(fig_conv, key="chart_conversion_order")
    
    st.markdown("---")
    
    # Aggregate trend
    st.markdown("### 📈 Overall Order Trend")
    
    calc = PerformanceCalculator()
    period_data = calc.aggregate_by_period(
        detail_df,
        grouping_period.lower(),
        'po_date'
    )
    
    if not period_data.empty:
        # Aggregate across all vendors
        trend_data = period_data.groupby('Period').agg({
            'Order Value': 'sum',
            'Invoiced Value': 'sum',
            'Pending Delivery': 'sum',
            'PO Count': 'sum'
        }).reset_index()
        
        trend_data['Conversion Rate'] = (
            trend_data['Invoiced Value'] / trend_data['Order Value'] * 100
        ).round(1)
        
        fig_trend = chart_factory.create_financial_trend_chart(
            trend_data,
            show_cumulative=False
        )
        render_chart(fig_trend, key="chart_trend_order")
    
    st.markdown("---")
    
    # Summary table
    st.markdown("### 📋 Vendor Summary Table")
    
    display_df = summary_df.copy()
    display_df['total_order_value'] = display_df['total_order_value'].apply(format_currency)
    display_df['total_invoiced_value'] = display_df['total_invoiced_value'].apply(format_currency)
    display_df['outstanding_value'] = display_df['outstanding_value'].apply(format_currency)
    display_df['conversion_rate'] = display_df['conversion_rate'].apply(lambda x: f"{x:.1f}%")
    
    display_cols = [
        'vendor_name', 'vendor_code', 'vendor_type',
        'total_pos', 'total_order_value', 'total_invoiced_value',
        'outstanding_value', 'conversion_rate'
    ]
    
    # Use new width parameter instead of deprecated use_container_width
    st.dataframe(
        display_df[display_cols],
        width='stretch',
        hide_index=True,
        height=400
    )


def _render_single_vendor_view(
    summary_df: pd.DataFrame,
    detail_df: pd.DataFrame,
    vendor_name: str,
    grouping_period: str
) -> None:
    """Render view for single vendor"""
    
    vendor_data = summary_df[summary_df['vendor_name'] == vendor_name]
    
    if vendor_data.empty:
        st.warning(f"No data found for vendor: {vendor_name}")
        return
    
    vendor_data = vendor_data.iloc[0]
    
    # Vendor info card
    st.markdown("### 🏢 Vendor Information")
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.markdown(f"**Name:** {vendor_data['vendor_name']}")
        st.markdown(f"**Code:** {vendor_data['vendor_code']}")
    
    with col2:
        st.markdown(f"**Type:** {vendor_data['vendor_type']}")
        st.markdown(f"**Location:** {vendor_data['vendor_location_type']}")
    
    with col3:
        st.markdown(f"**First Order:** {vendor_data['first_po_date']}")
        st.markdown(f"**Last Order:** {vendor_data['last_po_date']}")
    
    with col4:
        st.markdown(f"**Total POs:** {int(vendor_data['total_pos']):,}")
        st.markdown(f"**Avg PO Value:** {format_currency(vendor_data['avg_po_value'])}")
    
    st.markdown("---")
    
    # Key metrics
    st.markdown("### 💹 Financial Performance")
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric(
            "Order Entry",
            format_currency(vendor_data['total_order_value'])
        )
    
    with col2:
        st.metric(
            "Invoiced",
            format_currency(vendor_data['total_invoiced_value']),
            delta=f"{vendor_data['conversion_rate']:.1f}%"
        )
    
    with col3:
        st.metric(
            "Outstanding",
            format_currency(vendor_data['outstanding_value']),
            delta=f"{(vendor_data['outstanding_value']/vendor_data['total_order_value']*100):.1f}%",
            delta_color="inverse"
        )
    
    with col4:
        # Conversion gauge
        chart_factory = ChartFactory()
        fig_gauge = chart_factory.create_conversion_gauge(vendor_data['conversion_rate'])
        render_chart(fig_gauge, key="gauge_vendor_conversion")
    
    st.markdown("---")
    
    # Trend chart
    st.markdown("### 📈 Order & Invoice Trend")
    
    calc = PerformanceCalculator()
    vendor_detail = detail_df[detail_df['vendor_name'] == vendor_name]
    
    period_data = calc.aggregate_by_period(
        vendor_detail,
        grouping_period.lower(),
        'po_date'
    )
    
    if not period_data.empty:
        fig_trend = chart_factory.create_financial_trend_chart(
            period_data,
            show_cumulative=False
        )
        render_chart(fig_trend, key="chart_vendor_trend")
    
    st.markdown("---")
    
    # Detail table
    st.markdown("### 📋 Purchase Order Details")
    
    display_df = vendor_detail.copy()
    display_df = display_df.sort_values('po_date', ascending=False)
    
    # Format columns
    display_df['po_date'] = pd.to_datetime(display_df['po_date']).dt.strftime('%Y-%m-%d')
    display_df['total_amount_usd'] = display_df['total_amount_usd'].apply(format_currency)
    display_df['invoiced_amount_usd'] = display_df['invoiced_amount_usd'].apply(format_currency)
    display_df['outstanding_invoiced_amount_usd'] = display_df['outstanding_invoiced_amount_usd'].apply(format_currency)
    display_df['line_conversion_rate'] = display_df['line_conversion_rate'].apply(lambda x: f"{x:.1f}%")
    
    display_cols = [
        'po_number', 'po_date', 'product_name', 'pt_code',
        'standard_quantity', 'total_amount_usd', 'invoiced_amount_usd',
        'outstanding_invoiced_amount_usd', 'line_conversion_rate', 'status'
    ]
    
    # Use new width parameter instead of deprecated use_container_width
    st.dataframe(
        display_df[display_cols],
        width='stretch',
        hide_index=True,
        height=400
    )
    
    # Export button
    csv = display_df.to_csv(index=False).encode('utf-8')
    st.download_button(
        label="📥 Download Order Data",
        data=csv,
        file_name=f"order_analysis_{vendor_name}_{datetime.now().strftime('%Y%m%d')}.csv",
        mime='text/csv'
    )