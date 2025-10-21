"""
Payment Analysis Tab

Shows payment terms and financial analysis.
"""

import streamlit as st
import pandas as pd
import plotly.express as px


def render(po_data: pd.DataFrame, selected_vendor: str) -> None:
    """
    Render Payment Analysis Tab
    
    Args:
        po_data: DataFrame with PO data
        selected_vendor: Selected vendor name
    """
    st.subheader("💳 Payment Terms & Financial Analysis")
    
    if selected_vendor == "All Vendors" or po_data.empty:
        st.info("Please select a specific vendor to view payment analysis")
        return
    
    vendor_po = po_data[po_data['vendor_name'] == selected_vendor]
    
    if vendor_po.empty or 'payment_term' not in vendor_po.columns:
        st.info(f"No payment data available for {selected_vendor}")
        return
    
    # Payment terms summary
    payment_summary = vendor_po.groupby('payment_term').agg({
        'po_number': 'nunique',
        'total_amount_usd': 'sum',
        'outstanding_invoiced_amount_usd': 'sum'
    }).reset_index()
    
    if payment_summary.empty:
        st.info("No payment terms data available")
        return
    
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
        # Use config parameter for Plotly configuration
        st.plotly_chart(
            fig_payment_dist, 
            use_container_width=True,
            config={'displayModeBar': True, 'displaylogo': False}
        )
    
    with col2:
        fig_payment_status = px.bar(
            payment_summary,
            x='payment_term',
            y='outstanding_invoiced_amount_usd',
            color='paid_percentage',
            title="Outstanding Amounts by Payment Terms",
            color_continuous_scale='RdYlGn_r'
        )
        # Use config parameter for Plotly configuration
        st.plotly_chart(
            fig_payment_status, 
            use_container_width=True,
            config={'displayModeBar': True, 'displaylogo': False}
        )
    
    # Currency analysis
    if 'currency' in vendor_po.columns:
        st.markdown("#### Currency Exposure")
        _render_currency_analysis(vendor_po)


def _render_currency_analysis(vendor_po: pd.DataFrame) -> None:
    """Render currency exposure analysis"""
    currency_summary = vendor_po.groupby('currency').agg({
        'total_amount': 'sum',
        'total_amount_usd': 'sum',
        'po_number': 'nunique'
    }).reset_index()
    
    if currency_summary.empty:
        return
    
    col1, col2 = st.columns([1, 2])
    
    with col1:
        display_df = currency_summary.copy()
        display_df.columns = ['Currency', 'Local Amount', 'USD Amount', 'PO Count']
        st.dataframe(display_df, use_container_width=True, hide_index=True)
    
    with col2:
        fig_currency = px.pie(
            currency_summary,
            values='total_amount_usd',
            names='currency',
            title="Purchase Value by Currency"
        )
        # Use config parameter for Plotly configuration
        st.plotly_chart(
            fig_currency, 
            use_container_width=True,
            config={'displayModeBar': True, 'displaylogo': False}
        )