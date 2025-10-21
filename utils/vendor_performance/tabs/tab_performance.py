"""
Performance Trends Tab

Shows vendor performance trends over time.
"""

import streamlit as st
import pandas as pd
import numpy as np
from plotly.subplots import make_subplots
import plotly.graph_objects as go

from ..visualizations import ChartFactory

# Standard Plotly config
PLOTLY_CONFIG = {'displaylogo': False, 'displayModeBar': True}


def render(
    vendor_metrics: pd.DataFrame,
    po_data: pd.DataFrame,
    selected_vendor: str
) -> None:
    """
    Render Performance Trends Tab
    
    Args:
        vendor_metrics: DataFrame with vendor metrics
        po_data: DataFrame with PO data
        selected_vendor: Selected vendor name
    """
    st.subheader("📈 Performance Trends")
    
    if po_data.empty or not all(col in po_data.columns for col in ['po_date', 'eta', 'etd', 'status']):
        st.warning("Insufficient data for performance trend analysis")
        return
    
    if selected_vendor == "All Vendors":
        st.info("Please select a specific vendor to view performance trends")
        return
    
    # Calculate monthly performance
    monthly_performance = _calculate_monthly_performance(po_data, selected_vendor)
    
    if monthly_performance.empty:
        st.info(f"No performance trend data available for {selected_vendor}")
        return
    
    # Create performance trend charts
    chart_factory = ChartFactory()
    fig = chart_factory.create_performance_trends(monthly_performance, selected_vendor)
    
    st.plotly_chart(fig, use_container_width=True, config=PLOTLY_CONFIG)
    
    # Performance summary table
    st.markdown("#### Monthly Performance Summary")
    _render_performance_summary(monthly_performance)


def _calculate_monthly_performance(
    po_data: pd.DataFrame,
    vendor_name: str
) -> pd.DataFrame:
    """Calculate monthly performance metrics"""
    vendor_po = po_data[po_data['vendor_name'] == vendor_name].copy()
    
    if vendor_po.empty:
        return pd.DataFrame()
    
    vendor_po['month'] = pd.to_datetime(vendor_po['po_date']).dt.to_period('M').dt.to_timestamp()
    
    # Aggregate by month
    monthly = vendor_po.groupby('month').apply(
        lambda x: pd.Series({
            'on_time_deliveries': ((pd.to_datetime(x['eta']) >= pd.to_datetime(x['etd'])) & 
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
    monthly['on_time_rate'] = (
        monthly['on_time_deliveries'] / 
        monthly['total_deliveries'].replace(0, np.nan) * 100
    ).fillna(0)
    
    return monthly


def _render_performance_summary(monthly_performance: pd.DataFrame) -> None:
    """Render performance summary table"""
    display_df = monthly_performance[[
        'month', 'total_deliveries', 'on_time_deliveries',
        'on_time_rate', 'avg_lead_time', 'over_deliveries', 'total_value'
    ]].copy()
    
    display_df.columns = [
        'Month', 'Total Deliveries', 'On-Time',
        'On-Time Rate %', 'Avg Lead Time', 'Over Deliveries', 'Total Value'
    ]
    
    st.dataframe(display_df, use_container_width=True, hide_index=True)