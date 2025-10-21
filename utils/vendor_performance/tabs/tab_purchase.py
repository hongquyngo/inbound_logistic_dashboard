"""
Purchase Analysis Tab for Vendor Performance

Analyzes purchase patterns, trends, and period comparisons.
"""

import streamlit as st
import pandas as pd
import plotly.express as px
from plotly.subplots import make_subplots
import plotly.graph_objects as go

from ..calculations import PerformanceCalculator
from ..visualizations import ChartFactory

# Standard Plotly config
PLOTLY_CONFIG = {'displaylogo': False, 'displayModeBar': True}


def render(
    po_data: pd.DataFrame,
    period_type: str,
    selected_vendor: str
) -> None:
    """
    Render Purchase Analysis Tab
    
    Args:
        po_data: DataFrame with PO data
        period_type: 'Monthly', 'Quarterly', or 'Yearly'
        selected_vendor: Selected vendor name or "All Vendors"
    """
    st.subheader("💰 Purchase Value Analysis")
    
    if po_data.empty or 'po_date' not in po_data.columns:
        st.warning("No purchase order data available for analysis")
        return
    
    # Aggregate by period
    calc = PerformanceCalculator()
    period_analysis = calc.aggregate_by_period(
        po_data,
        period_type.lower(),
        'po_date'
    )
    
    if period_analysis.empty:
        st.info("No data available for the selected period")
        return
    
    if selected_vendor != "All Vendors":
        _render_vendor_analysis(period_analysis, po_data, selected_vendor, period_type)
    else:
        _render_all_vendors_analysis(period_analysis, po_data, period_type)


def _render_vendor_analysis(
    period_analysis: pd.DataFrame,
    po_data: pd.DataFrame,
    vendor_name: str,
    period_type: str
) -> None:
    """
    Show purchase analysis for specific vendor
    
    Args:
        period_analysis: Aggregated period data
        po_data: Raw PO data
        vendor_name: Vendor name
        period_type: Period type
    """
    vendor_period_data = period_analysis[period_analysis['Vendor'] == vendor_name]
    
    if vendor_period_data.empty:
        st.info(f"No period data available for {vendor_name}")
        return
    
    # Create trend charts
    fig = make_subplots(
        rows=2, cols=1,
        subplot_titles=(
            f'Purchase Value Trend - {vendor_name}',
            'PO Count and Product Diversity'
        ),
        specs=[[{"secondary_y": False}], [{"secondary_y": True}]]
    )
    
    # Purchase value trend
    fig.add_trace(
        go.Bar(
            x=vendor_period_data['Period'],
            y=vendor_period_data['Total Value'],
            name='Purchase Value',
            marker_color='#3498db'
        ),
        row=1, col=1
    )
    
    # PO count
    fig.add_trace(
        go.Scatter(
            x=vendor_period_data['Period'],
            y=vendor_period_data['PO Count'],
            mode='lines+markers',
            name='PO Count',
            line=dict(color='#e74c3c', width=3)
        ),
        row=2, col=1
    )
    
    # Product diversity
    fig.add_trace(
        go.Scatter(
            x=vendor_period_data['Period'],
            y=vendor_period_data['Products'],
            mode='lines+markers',
            name='Unique Products',
            line=dict(color='#2ecc71', width=3)
        ),
        row=2, col=1,
        secondary_y=True
    )
    
    fig.update_layout(height=600)
    st.plotly_chart(fig, use_container_width=True, config=PLOTLY_CONFIG)
    
    # Period comparison table
    st.markdown("#### Period-over-Period Analysis")
    _render_period_comparison(vendor_period_data)


def _render_all_vendors_analysis(
    period_analysis: pd.DataFrame,
    po_data: pd.DataFrame,
    period_type: str
) -> None:
    """
    Show purchase analysis for all vendors
    
    Args:
        period_analysis: Aggregated period data
        po_data: Raw PO data
        period_type: Period type
    """
    st.markdown("#### Purchase Value Analysis - All Vendors")
    
    # Create tabs for different views
    analysis_tabs = st.tabs(["📊 Top Vendors", "📈 Trends", "🌍 By Location", "💼 By Type"])
    
    with analysis_tabs[0]:
        _render_top_vendors(period_analysis)
    
    with analysis_tabs[1]:
        _render_trends(period_analysis)
    
    with analysis_tabs[2]:
        _render_by_location(po_data)
    
    with analysis_tabs[3]:
        _render_by_type(po_data)


def _render_top_vendors(period_analysis: pd.DataFrame) -> None:
    """Render top vendors analysis"""
    st.markdown("##### Top Vendors by Period")
    
    # Get latest period
    latest_period = period_analysis['Period'].max()
    latest_vendors = period_analysis[
        period_analysis['Period'] == latest_period
    ].nlargest(10, 'Total Value')
    
    if latest_vendors.empty:
        st.info("No vendor data available")
        return
    
    # Create bar chart
    chart_factory = ChartFactory()
    fig = chart_factory.create_comparison_bar(
        latest_vendors,
        x_col='Total Value',
        y_col='Vendor',
        color_col='Total Value',
        orientation='h',
        title=f"Top 10 Vendors - {latest_period}"
    )
    
    st.plotly_chart(fig, use_container_width=True, config=PLOTLY_CONFIG)
    
    # Summary table
    st.markdown("##### Vendor Comparison Details")
    comparison_df = latest_vendors[['Vendor', 'PO Count', 'Total Value', 'Products']].copy()
    comparison_df['Avg PO Value'] = comparison_df['Total Value'] / comparison_df['PO Count']
    
    st.dataframe(comparison_df, use_container_width=True, hide_index=True)


def _render_trends(period_analysis: pd.DataFrame) -> None:
    """Render trend analysis"""
    st.markdown("##### Purchase Value Trends Over Time")
    
    # Aggregate by period
    period_totals = period_analysis.groupby('Period').agg({
        'Total Value': 'sum',
        'PO Count': 'sum',
        'Vendor': 'nunique'
    }).reset_index()
    
    # Create dual axis chart
    fig = make_subplots(
        rows=2, cols=1,
        subplot_titles=('Total Purchase Value Trend', 'PO Volume and Vendor Count'),
        specs=[[{"secondary_y": False}], [{"secondary_y": True}]]
    )
    
    # Purchase value
    fig.add_trace(
        go.Bar(
            x=period_totals['Period'],
            y=period_totals['Total Value'],
            name='Total Value',
            marker_color='#3498db'
        ),
        row=1, col=1
    )
    
    # PO count
    fig.add_trace(
        go.Scatter(
            x=period_totals['Period'],
            y=period_totals['PO Count'],
            mode='lines+markers',
            name='PO Count',
            line=dict(color='#e74c3c', width=3)
        ),
        row=2, col=1
    )
    
    # Vendor count
    fig.add_trace(
        go.Scatter(
            x=period_totals['Period'],
            y=period_totals['Vendor'],
            mode='lines+markers',
            name='Active Vendors',
            line=dict(color='#2ecc71', width=3)
        ),
        row=2, col=1,
        secondary_y=True
    )
    
    fig.update_layout(height=600)
    st.plotly_chart(fig, use_container_width=True, config=PLOTLY_CONFIG)
    
    # Growth metrics
    if len(period_totals) > 1:
        _render_growth_metrics(period_totals)


def _render_by_location(po_data: pd.DataFrame) -> None:
    """Render analysis by vendor location"""
    st.markdown("##### Purchase Analysis by Vendor Location")
    
    if 'vendor_location_type' not in po_data.columns:
        st.info("Location data not available")
        return
    
    # Aggregate by location
    location_summary = po_data.groupby('vendor_location_type').agg({
        'total_amount_usd': 'sum',
        'po_number': 'nunique',
        'vendor_name': 'nunique',
        'outstanding_arrival_amount_usd': 'sum'
    }).reset_index()
    
    col1, col2 = st.columns(2)
    
    with col1:
        # Pie chart
        fig = px.pie(
            location_summary,
            values='total_amount_usd',
            names='vendor_location_type',
            title='Value Distribution by Location'
        )
        st.plotly_chart(fig, use_container_width=True, config=PLOTLY_CONFIG)
    
    with col2:
        # Summary table
        location_summary['% of Total'] = (
            location_summary['total_amount_usd'] / location_summary['total_amount_usd'].sum() * 100
        ).round(1)
        
        display_df = location_summary[[
            'vendor_location_type', 'vendor_name', 'po_number', 'total_amount_usd', '% of Total'
        ]].copy()
        display_df.columns = ['Location', 'Vendors', 'POs', 'Total Value', '% Share']
        
        st.dataframe(display_df, use_container_width=True, hide_index=True)


def _render_by_type(po_data: pd.DataFrame) -> None:
    """Render analysis by vendor type"""
    st.markdown("##### Purchase Analysis by Vendor Type")
    
    if 'vendor_type' not in po_data.columns:
        st.info("Vendor type data not available")
        return
    
    # Aggregate by type
    type_summary = po_data.groupby('vendor_type').agg({
        'total_amount_usd': 'sum',
        'po_number': 'nunique',
        'vendor_name': 'nunique'
    }).reset_index()
    
    # Display metrics
    cols = st.columns(len(type_summary))
    
    for idx, row in type_summary.iterrows():
        with cols[idx]:
            st.metric(
                f"{row['vendor_type']} Vendors",
                f"{row['vendor_name']:,}",
                help=f"Total {row['vendor_type'].lower()} vendors"
            )
            st.metric(
                "Total Value",
                f"${row['total_amount_usd']/1000000:.1f}M"
            )


def _render_period_comparison(vendor_period_data: pd.DataFrame) -> None:
    """Render period-over-period comparison"""
    # Calculate changes
    comparison_df = vendor_period_data.sort_values('Period').copy()
    comparison_df['Value Change %'] = comparison_df['Total Value'].pct_change() * 100
    comparison_df['PO Change %'] = comparison_df['PO Count'].pct_change() * 100
    
    # Format for display
    display_df = comparison_df[[
        'Period', 'Total Value', 'Value Change %',
        'PO Count', 'PO Change %', 'Products'
    ]].copy()
    
    st.dataframe(display_df, use_container_width=True, hide_index=True)


def _render_growth_metrics(period_totals: pd.DataFrame) -> None:
    """Render growth metrics"""
    st.markdown("##### Growth Metrics")
    
    period_totals = period_totals.sort_values('Period')
    latest_value = period_totals.iloc[-1]['Total Value']
    previous_value = period_totals.iloc[-2]['Total Value']
    value_growth = ((latest_value - previous_value) / previous_value * 100) if previous_value > 0 else 0
    
    latest_po = period_totals.iloc[-1]['PO Count']
    previous_po = period_totals.iloc[-2]['PO Count']
    po_growth = ((latest_po - previous_po) / previous_po * 100) if previous_po > 0 else 0
    
    avg_monthly_value = period_totals['Total Value'].mean()
    
    col1, col2, col3 = st.columns(3)
    
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
            "Avg Period Spend",
            f"${avg_monthly_value/1000000:.1f}M",
            help="Average purchase value per period"
        )