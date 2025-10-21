"""
Overview Tab - Simplified Dashboard

Shows snapshot of vendor performance in one screen:
- Key metrics (6 cards)
- Conversion rate gauge
- Alerts
- Top products
"""

import streamlit as st
import pandas as pd
from datetime import datetime
from typing import Optional

from ..calculations import PerformanceCalculator
from ..visualizations import ChartFactory
from ..constants import (
    COLORS, format_currency, format_percentage, 
    get_conversion_tier, PLOTLY_CONFIG
)


def render(
    vendor_summary: pd.DataFrame,
    po_data: pd.DataFrame,
    selected_vendor: str
) -> None:
    """
    Render Overview Tab
    
    Args:
        vendor_summary: Vendor summary data
        po_data: PO data
        selected_vendor: Selected vendor name
    """
    st.subheader("📊 Performance Overview")
    
    if vendor_summary.empty:
        st.warning("No vendor data available")
        return
    
    calc = PerformanceCalculator()
    
    if selected_vendor == "All Vendors":
        _render_all_vendors_overview(vendor_summary, calc)
    else:
        _render_single_vendor_overview(vendor_summary, po_data, selected_vendor, calc)


def _render_all_vendors_overview(
    vendor_summary: pd.DataFrame,
    calc: PerformanceCalculator
) -> None:
    """
    Show overview for all vendors
    
    Args:
        vendor_summary: All vendor summary data
        calc: Calculator instance
    """
    st.markdown("### Overall Performance Summary")
    
    # Top 6 KPIs
    col1, col2, col3, col4, col5, col6 = st.columns(6)
    
    total_vendors = len(vendor_summary)
    total_order = vendor_summary['total_order_value'].sum()
    total_invoiced = vendor_summary['total_invoiced_value'].sum()
    total_pending = vendor_summary['pending_delivery_value'].sum()
    avg_conversion = vendor_summary['conversion_rate'].mean()
    total_pos = vendor_summary['total_pos'].sum()
    
    with col1:
        st.metric(
            "Total Vendors",
            f"{total_vendors:,}",
            help="Number of active vendors"
        )
    
    with col2:
        st.metric(
            "💵 Total Order Entry",
            format_currency(total_order, compact=True),
            help="Total value of all purchase orders"
        )
    
    with col3:
        st.metric(
            "📮 Invoiced Value",
            format_currency(total_invoiced, compact=True),
            delta=f"{(total_invoiced/total_order*100):.1f}% of order" if total_order > 0 else None,
            help="Total invoiced amount"
        )
    
    with col4:
        st.metric(
            "⏳ Pending Delivery",
            format_currency(total_pending, compact=True),
            delta=f"{(total_pending/total_order*100):.1f}%" if total_order > 0 else None,
            delta_color="inverse",
            help="Outstanding delivery value"
        )
    
    with col5:
        conversion_delta = avg_conversion - 90
        st.metric(
            "🎯 Avg Conversion",
            f"{avg_conversion:.1f}%",
            delta=f"{conversion_delta:+.1f}% vs target",
            delta_color="normal" if avg_conversion >= 90 else "inverse",
            help="Average order to invoice conversion"
        )
    
    with col6:
        st.metric(
            "📦 Total POs",
            f"{int(total_pos):,}",
            help="Total purchase orders"
        )
    
    st.markdown("---")
    
    # Conversion Rate Progress Bar
    st.markdown("#### 📊 Order Entry → Invoice Conversion")
    conversion_pct = (total_invoiced / total_order * 100) if total_order > 0 else 0
    
    progress_col1, progress_col2 = st.columns([3, 1])
    
    with progress_col1:
        st.progress(min(conversion_pct / 100, 1.0))
        st.caption(
            f"{format_currency(total_invoiced)} / {format_currency(total_order)} "
            f"({conversion_pct:.1f}%)"
        )
    
    with progress_col2:
        tier = get_conversion_tier(conversion_pct)
        st.markdown(f"**{tier}**")
        if conversion_pct < 90:
            st.caption("⚠️ Below target (90%)")
    
    st.markdown("---")
    
    # Top Vendors
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("### Top 10 Vendors by Order Value")
        chart_factory = ChartFactory()
        fig = chart_factory.create_vendor_comparison_chart(
            vendor_summary,
            top_n=10,
            metric='total_order_value'
        )
        st.plotly_chart(fig, width='stretch', config=PLOTLY_CONFIG)
    
    with col2:
        st.markdown("### Conversion Rate Distribution")
        top_10 = vendor_summary.nlargest(10, 'total_order_value')
        
        # Create simple bar chart for conversion rates
        import plotly.express as px
        fig_conv = px.bar(
            top_10.sort_values('conversion_rate'),
            x='conversion_rate',
            y='vendor_name',
            orientation='h',
            title="Top 10 Vendors - Conversion Rate",
            labels={'conversion_rate': 'Conversion %', 'vendor_name': ''},
            color='conversion_rate',
            color_continuous_scale='RdYlGn'
        )
        fig_conv.update_layout(height=400, showlegend=False)
        st.plotly_chart(fig_conv, width='stretch', config=PLOTLY_CONFIG)


def _render_single_vendor_overview(
    vendor_summary: pd.DataFrame,
    po_data: pd.DataFrame,
    vendor_name: str,
    calc: PerformanceCalculator
) -> None:
    """
    Show overview for single vendor
    
    Args:
        vendor_summary: Vendor summary data
        po_data: PO data
        vendor_name: Vendor name
        calc: Calculator instance
    """
    vendor_data = vendor_summary[vendor_summary['vendor_name'] == vendor_name]
    
    if vendor_data.empty:
        st.warning(f"No data found for vendor: {vendor_name}")
        return
    
    vendor_data = vendor_data.iloc[0]
    
    # Top section: Key metrics
    st.markdown("### 🎯 Key Performance Metrics")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.metric(
            "💵 Total Order Entry",
            format_currency(vendor_data['total_order_value']),
            help="Total value of all purchase orders"
        )
    
    with col2:
        st.metric(
            "📮 Invoiced Value",
            format_currency(vendor_data['total_invoiced_value']),
            delta=f"{vendor_data['conversion_rate']:.1f}% of order",
            help="Total invoiced and delivered"
        )
    
    with col3:
        st.metric(
            "⏳ Pending Delivery",
            format_currency(vendor_data['pending_delivery_value']),
            delta=f"{(vendor_data['pending_delivery_value']/vendor_data['total_order_value']*100):.1f}%",
            delta_color="inverse",
            help="Outstanding amount"
        )
    
    col4, col5, col6 = st.columns(3)
    
    with col4:
        st.metric(
            "📦 Total POs",
            f"{int(vendor_data['total_pos']):,}",
            help="Number of purchase orders"
        )
    
    with col5:
        st.metric(
            "🎯 Avg PO Value",
            format_currency(vendor_data['avg_po_value']),
            help="Average order size"
        )
    
    with col6:
        last_po = pd.to_datetime(vendor_data['last_po_date'])
        days_ago = (pd.Timestamp.now() - last_po).days
        st.metric(
            "📅 Last Order",
            last_po.strftime('%Y-%m-%d'),
            delta=f"{days_ago} days ago",
            help="Most recent purchase order"
        )
    
    st.markdown("---")
    
    # Conversion gauge and progress
    col1, col2 = st.columns([1, 2])
    
    with col1:
        st.markdown("#### Conversion Rate")
        chart_factory = ChartFactory()
        fig_gauge = chart_factory.create_conversion_gauge(vendor_data['conversion_rate'])
        st.plotly_chart(fig_gauge, width='stretch', config=PLOTLY_CONFIG)
        
        tier = get_conversion_tier(vendor_data['conversion_rate'])
        st.markdown(f"**Performance Tier:** {tier}")
    
    with col2:
        st.markdown("#### 📊 Order → Invoice Breakdown")
        
        # Progress bar
        conversion_pct = vendor_data['conversion_rate']
        st.progress(min(conversion_pct / 100, 1.0))
        st.caption(
            f"{format_currency(vendor_data['total_invoiced_value'])} / "
            f"{format_currency(vendor_data['total_order_value'])} "
            f"({conversion_pct:.1f}%)"
        )
        
        # Breakdown metrics
        st.markdown("")
        metric_col1, metric_col2 = st.columns(2)
        
        with metric_col1:
            st.markdown("**Vendor Info:**")
            st.write(f"• Type: {vendor_data.get('vendor_type', 'N/A')}")
            st.write(f"• Location: {vendor_data.get('vendor_location_type', 'N/A')}")
            st.write(f"• Code: {vendor_data.get('vendor_code', 'N/A')}")
        
        with metric_col2:
            st.markdown("**Status:**")
            if conversion_pct >= 95:
                st.success("⭐ Excellent performance")
            elif conversion_pct >= 90:
                st.info("✅ Good performance")
            elif conversion_pct >= 80:
                st.warning("⚠️ Fair performance")
            else:
                st.error("❌ Needs improvement")
    
    st.markdown("---")
    
    # Alerts section
    alerts = calc.identify_alerts(vendor_data)
    
    if alerts:
        st.markdown("#### ⚠️ Issues & Alerts")
        
        for alert in alerts:
            if alert['severity'] == 'warning':
                st.warning(f"⚠️ {alert['message']}")
            elif alert['severity'] == 'error':
                st.error(f"❌ {alert['message']}")
            else:
                st.info(f"ℹ️ {alert['message']}")
    
    # Top products
    if not po_data.empty:
        vendor_po = po_data[po_data['vendor_name'] == vendor_name]
        
        if not vendor_po.empty:
            st.markdown("---")
            st.markdown("#### 📦 Top 3 Products")
            
            product_summary = vendor_po.groupby('product_name').agg({
                'total_order_value_usd': 'sum',
                'invoiced_amount_usd': 'sum'
            }).reset_index()
            
            product_summary['pct_of_total'] = (
                product_summary['total_order_value_usd'] / 
                product_summary['total_order_value_usd'].sum() * 100
            )
            
            top_3 = product_summary.nlargest(3, 'total_order_value_usd')
            
            for idx, row in top_3.iterrows():
                col1, col2, col3 = st.columns([3, 1, 1])
                
                with col1:
                    st.write(f"**{row['product_name']}**")
                
                with col2:
                    st.write(format_currency(row['total_order_value_usd']))
                
                with col3:
                    st.write(f"{row['pct_of_total']:.1f}%")