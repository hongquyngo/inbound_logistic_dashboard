"""
Financial Performance Tab

Deep dive into order entry and invoiced values:
- YTD metrics
- Periodic trend
- Cumulative performance
- Monthly breakdown table
"""

import streamlit as st
import pandas as pd
from datetime import datetime
from typing import Optional

from ..calculations import PerformanceCalculator
from ..visualizations import ChartFactory
from ..constants import COLORS, format_currency, format_percentage, PLOTLY_CONFIG


def render(
    vendor_summary: pd.DataFrame,
    po_data: pd.DataFrame,
    period_type: str,
    selected_vendor: str
) -> None:
    """
    Render Financial Performance Tab
    
    Args:
        vendor_summary: Vendor summary data
        po_data: PO data
        period_type: Period type (Monthly/Quarterly/Yearly)
        selected_vendor: Selected vendor name
    """
    st.subheader("💰 Financial Performance")
    
    if po_data.empty:
        st.warning("No purchase order data available")
        return
    
    if selected_vendor == "All Vendors":
        st.info("Please select a specific vendor to view detailed financial performance")
        _render_all_vendors_financial(po_data, period_type)
        return
    
    _render_single_vendor_financial(vendor_summary, po_data, period_type, selected_vendor)


def _render_single_vendor_financial(
    vendor_summary: pd.DataFrame,
    po_data: pd.DataFrame,
    period_type: str,
    vendor_name: str
) -> None:
    """
    Show financial performance for single vendor
    
    Args:
        vendor_summary: Vendor summary data
        po_data: PO data
        period_type: Period type
        vendor_name: Vendor name
    """
    # Filter vendor data
    vendor_po = po_data[po_data['vendor_name'] == vendor_name].copy()
    
    if vendor_po.empty:
        st.warning(f"No purchase orders found for {vendor_name}")
        return
    
    vendor_data = vendor_summary[vendor_summary['vendor_name'] == vendor_name]
    if not vendor_data.empty:
        vendor_data = vendor_data.iloc[0]
    
    calc = PerformanceCalculator()
    
    # View mode selector
    view_col1, view_col2, view_col3 = st.columns([1, 1, 2])
    
    with view_col1:
        chart_view = st.selectbox(
            "Chart View",
            ["Periodic (By Month)", "Cumulative (YTD)"],
            help="Switch between period-by-period or cumulative view"
        )
    
    with view_col2:
        comparison_period = st.selectbox(
            "Compare With",
            ["None", "Previous Period", "Last Year"],
            help="Add comparison baseline"
        )
    
    # Top KPI Cards
    st.markdown("### 🎯 YTD Performance")
    
    col1, col2, col3, col4 = st.columns(4)
    
    ytd_order = vendor_po['total_order_value_usd'].sum()
    ytd_invoiced = vendor_po['invoiced_amount_usd'].sum()
    ytd_pending = vendor_po['pending_delivery_usd'].sum()
    ytd_conversion = calc.calculate_conversion_rate(ytd_invoiced, ytd_order)
    
    with col1:
        st.metric(
            "YTD Order Entry",
            format_currency(ytd_order),
            help="Year-to-date order value"
        )
    
    with col2:
        st.metric(
            "YTD Invoiced",
            format_currency(ytd_invoiced),
            delta=f"{ytd_conversion:.1f}% converted",
            help="Year-to-date invoiced value"
        )
    
    with col3:
        st.metric(
            "YTD Pending",
            format_currency(ytd_pending),
            delta=f"{(ytd_pending/ytd_order*100):.1f}%",
            delta_color="inverse",
            help="Outstanding delivery"
        )
    
    with col4:
        st.metric(
            "Avg Monthly Value",
            format_currency(ytd_order / 12),  # Approximate
            help="Average monthly order value"
        )
    
    st.markdown("---")
    
    # Aggregate by period
    period_data = calc.aggregate_by_period(
        vendor_po,
        period_type.lower(),
        'po_date'
    )
    
    if period_data.empty:
        st.info("No period data available")
        return
    
    # Filter for selected vendor only
    period_data = period_data[period_data['Vendor'] == vendor_name]
    
    # Charts
    chart_factory = ChartFactory()
    
    show_cumulative = "Cumulative" in chart_view
    
    st.markdown(f"### 📈 {chart_view}")
    
    fig_trend = chart_factory.create_financial_trend_chart(
        period_data,
        show_cumulative=show_cumulative
    )
    st.plotly_chart(fig_trend, width='stretch', config=PLOTLY_CONFIG)
    
    # Comparison chart (if selected)
    if comparison_period != "None":
        st.markdown(f"### 📊 Comparison: {comparison_period}")
        
        if comparison_period == "Previous Period":
            # Compare last 2 periods
            if len(period_data) >= 2:
                current = period_data.iloc[-1:]
                previous = period_data.iloc[-2:-1]
                
                fig_comp = chart_factory.create_period_comparison_bars(current, previous)
                st.plotly_chart(fig_comp, width='stretch', config=PLOTLY_CONFIG)
            else:
                st.info("Not enough data for comparison")
        
        elif comparison_period == "Last Year":
            # This would require more complex date logic
            st.info("Last year comparison will be implemented in next version")
    
    st.markdown("---")
    
    # Monthly breakdown table
    st.markdown("### 📋 Period Breakdown")
    
    _render_period_breakdown_table(period_data)
    
    # Export button
    st.markdown("---")
    col1, col2, col3 = st.columns([2, 1, 1])
    
    with col3:
        csv = period_data.to_csv(index=False).encode('utf-8')
        st.download_button(
            label="📥 Download Data",
            data=csv,
            file_name=f"financial_performance_{vendor_name}_{datetime.now().strftime('%Y%m%d')}.csv",
            mime='text/csv'
        )


def _render_all_vendors_financial(
    po_data: pd.DataFrame,
    period_type: str
) -> None:
    """
    Show financial overview for all vendors
    
    Args:
        po_data: PO data
        period_type: Period type
    """
    calc = PerformanceCalculator()
    
    # Aggregate all vendors
    period_data = calc.aggregate_by_period(
        po_data,
        period_type.lower(),
        'po_date'
    )
    
    if period_data.empty:
        return
    
    # Sum across all vendors per period
    total_by_period = period_data.groupby('Period').agg({
        'Order Value': 'sum',
        'Invoiced Value': 'sum',
        'Pending Delivery': 'sum',
        'PO Count': 'sum'
    }).reset_index()
    
    # Calculate conversion rate
    total_by_period['Conversion Rate'] = total_by_period.apply(
        lambda row: calc.calculate_conversion_rate(
            row['Invoiced Value'],
            row['Order Value']
        ),
        axis=1
    )
    
    st.markdown("### 📈 Overall Purchase Trend")
    
    chart_factory = ChartFactory()
    fig = chart_factory.create_financial_trend_chart(total_by_period, show_cumulative=False)
    st.plotly_chart(fig, width='stretch', config=PLOTLY_CONFIG)
    
    st.markdown("### 📈 Cumulative Performance")
    fig_cum = chart_factory.create_financial_trend_chart(total_by_period, show_cumulative=True)
    st.plotly_chart(fig_cum, width='stretch', config=PLOTLY_CONFIG)


def _render_period_breakdown_table(period_data: pd.DataFrame) -> None:
    """
    Render detailed period breakdown table
    
    Args:
        period_data: Period aggregated data
    """
    # Prepare display dataframe
    display_df = period_data.copy()
    display_df = display_df.sort_values('Period', ascending=False)
    
    # Format columns
    display_df['Period'] = pd.to_datetime(display_df['Period']).dt.strftime('%Y-%m')
    display_df['Order Value'] = display_df['Order Value'].apply(lambda x: format_currency(x))
    display_df['Invoiced Value'] = display_df['Invoiced Value'].apply(lambda x: format_currency(x))
    display_df['Pending Delivery'] = display_df['Pending Delivery'].apply(lambda x: format_currency(x))
    display_df['Conversion Rate'] = display_df['Conversion Rate'].apply(lambda x: f"{x:.1f}%")
    
    # Select columns
    display_columns = [
        'Period', 'PO Count', 'Order Value', 
        'Invoiced Value', 'Conversion Rate', 'Pending Delivery'
    ]
    
    display_df = display_df[display_columns]
    
    # Display with conditional formatting
    st.dataframe(
        display_df,
        width='stretch',
        hide_index=True,
        height=400
    )
    
    # Summary stats
    st.markdown("---")
    st.markdown("#### Summary Statistics")
    
    col1, col2, col3, col4 = st.columns(4)
    
    # Calculate from original data
    total_order = period_data['Order Value'].sum()
    total_invoiced = period_data['Invoiced Value'].sum()
    avg_conversion = period_data['Conversion Rate'].mean()
    total_po = period_data['PO Count'].sum()
    
    with col1:
        st.metric("Total Order Value", format_currency(total_order))
    
    with col2:
        st.metric("Total Invoiced", format_currency(total_invoiced))
    
    with col3:
        st.metric("Avg Conversion", f"{avg_conversion:.1f}%")
    
    with col4:
        st.metric("Total POs", f"{int(total_po):,}")