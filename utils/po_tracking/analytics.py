"""
Combined Analytics Tab
Merges Analytics and Financial views into a single comprehensive tab
"""

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime


def render_analytics_tab(po_df: pd.DataFrame, data_service):
    """
    Render combined analytics tab (merged from old Analytics + Financial)
    
    Args:
        po_df: Purchase order dataframe
        data_service: PODataService instance for loading additional data
    """
    
    # Section 1: Vendor Performance Overview
    st.markdown("### 📊 Vendor Performance Overview")
    col1, col2 = st.columns(2)
    
    with col1:
        render_status_by_vendor_type(po_df)
    
    with col2:
        render_vendor_location_performance(po_df)
    
    st.markdown("---")
    
    # Section 2: Financial Analysis
    st.markdown("### 💰 Financial Overview")
    col1, col2 = st.columns(2)
    
    with col1:
        render_currency_exposure(po_df)
    
    with col2:
        render_payment_terms_analysis(po_df)
    
    # Outstanding by vendor
    render_top_vendors_outstanding(po_df)
    
    st.markdown("---")
    
    # Section 3: Supply & Demand Analysis
    st.markdown("### 📦 Supply & Demand Analysis")
    
    demand_df = data_service.get_product_demand_vs_incoming()
    
    if not demand_df.empty:
        render_supply_demand_metrics(demand_df)
        render_supply_demand_chart(demand_df)
        render_supply_demand_table(demand_df)
    else:
        st.info("No demand data available for analysis")


def render_status_by_vendor_type(po_df: pd.DataFrame):
    """Render PO status distribution by vendor type"""
    st.markdown("#### Status by Vendor Type")
    
    status_vendor_summary = po_df.groupby(['status', 'vendor_type']).agg({
        'po_line_id': 'count'
    }).reset_index()
    
    fig = px.bar(
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
    fig.update_layout(height=350)
    st.plotly_chart(fig, use_container_width=True)


def render_vendor_location_performance(po_df: pd.DataFrame):
    """Render vendor performance by location"""
    st.markdown("#### Performance by Vendor Location")
    
    location_summary = po_df.groupby('vendor_location_type').agg({
        'po_number': 'nunique',
        'arrival_completion_percent': 'mean'
    }).reset_index()
    
    location_summary.columns = ['Location', 'PO Count', 'Avg Completion %']
    
    fig = go.Figure()
    
    fig.add_trace(go.Bar(
        x=location_summary['Location'],
        y=location_summary['Avg Completion %'],
        name='Avg Completion %',
        text=location_summary['Avg Completion %'].round(1),
        textposition='outside',
        marker_color=['#2ecc71', '#e74c3c']
    ))
    
    fig.update_layout(
        title='Average Completion Rate by Vendor Location',
        yaxis_title='Completion %',
        height=350
    )
    st.plotly_chart(fig, use_container_width=True)


def render_currency_exposure(po_df: pd.DataFrame):
    """Render currency exposure by vendor type"""
    st.markdown("#### Currency Exposure by Vendor Type")
    
    currency_vendor_summary = po_df.groupby(['currency', 'vendor_type']).agg({
        'total_amount_usd': 'sum',
        'po_number': 'nunique'
    }).reset_index()
    
    fig = px.bar(
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
    fig.update_layout(height=350)
    st.plotly_chart(fig, use_container_width=True)


def render_payment_terms_analysis(po_df: pd.DataFrame):
    """Render payment terms analysis by location"""
    st.markdown("#### Payment Terms by Location")
    
    payment_location_summary = po_df.groupby(['payment_term', 'vendor_location_type']).agg({
        'outstanding_invoiced_amount_usd': 'sum',
        'po_number': 'nunique'
    }).reset_index()
    
    payment_location_summary = payment_location_summary.sort_values(
        'outstanding_invoiced_amount_usd', ascending=False
    ).head(10)
    
    fig = px.bar(
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
    fig.update_xaxes(tickangle=-45)
    fig.update_layout(height=350)
    st.plotly_chart(fig, use_container_width=True)


def render_top_vendors_outstanding(po_df: pd.DataFrame):
    """Render top 10 vendors by outstanding amount"""
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
    
    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=vendor_outstanding['Vendor Display'],
        y=vendor_outstanding['outstanding_arrival_amount_usd'],
        name='Arrival Outstanding',
        marker_color='#2e7d32'
    ))
    fig.add_trace(go.Bar(
        x=vendor_outstanding['Vendor Display'],
        y=vendor_outstanding['outstanding_invoiced_amount_usd'],
        name='Invoice Outstanding',
        marker_color='#f44336'
    ))
    
    fig.update_layout(
        barmode='stack',
        xaxis_title="Vendor",
        yaxis_title="Outstanding Amount (USD)",
        height=400
    )
    fig.update_xaxes(tickangle=-45)
    st.plotly_chart(fig, use_container_width=True)


def render_supply_demand_metrics(demand_df: pd.DataFrame):
    """Render supply & demand summary metrics"""
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


def render_supply_demand_chart(demand_df: pd.DataFrame):
    """Render supply vs demand chart for top products"""
    shortage_df = demand_df[demand_df['net_requirement'] > 0].head(15)
    
    if not shortage_df.empty:
        fig = go.Figure()
        
        fig.add_trace(go.Bar(
            x=shortage_df['pt_code'],
            y=shortage_df['current_stock'],
            name='Current Stock',
            marker_color='#2ecc71',
            text=shortage_df['current_stock'].round(0),
            textposition='inside'
        ))
        
        fig.add_trace(go.Bar(
            x=shortage_df['pt_code'],
            y=shortage_df['incoming_supply'],
            name='Incoming Supply',
            marker_color='#3498db',
            text=shortage_df['incoming_supply'].round(0),
            textposition='inside'
        ))
        
        fig.add_trace(go.Bar(
            x=shortage_df['pt_code'],
            y=shortage_df['net_requirement'],
            name='Net Requirement',
            marker_color='#e74c3c',
            text=shortage_df['net_requirement'].round(0),
            textposition='inside'
        ))
        
        fig.update_layout(
            title='Top 15 Products - Supply vs Demand Analysis',
            xaxis_title='PT Code',
            yaxis_title='Quantity',
            barmode='stack',
            hovermode='x unified',
            height=450
        )
        st.plotly_chart(fig, use_container_width=True)


def render_supply_demand_table(demand_df: pd.DataFrame):
    """Render detailed supply & demand table"""
    shortage_df = demand_df[demand_df['net_requirement'] > 0].head(15)
    
    if not shortage_df.empty:
        display_cols = [
            'pt_code', 'product', 'total_demand', 'current_stock', 
            'incoming_supply', 'total_available', 'net_requirement',
            'current_coverage_percent', 'total_coverage_percent', 
            'next_arrival_date_eta', 'supply_status'
        ]
        
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
            .map(lambda x: 'background-color: #ffcccb' if x == 'Need to Order' 
                        else 'background-color: #ffe4b5' if x == 'Partial Coverage'
                        else 'background-color: #90ee90' if x == 'Will be Sufficient'
                        else '', subset=['supply_status']),
            use_container_width=True
        )
        
        st.caption("""
        **Legend:**
        - **Current Stock**: Current inventory across all warehouses
        - **Incoming Supply**: Products arriving from pending POs
        - **Net Requirement**: Additional quantity needed = Demand - Current Stock - Incoming Supply
        - **Supply Status**:
          - 🔴 Need to Order: Immediate ordering required
          - 🟡 Partial Coverage: Incoming supply insufficient
          - 🟢 Will be Sufficient: Incoming supply will meet demand
        """)