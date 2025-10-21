"""
Invoice Analysis Tab - Clean Version

Analyzes invoices by invoice date
Focuses on payment status, aging, and cash flow
All deprecations fixed

Version: 2.1
Last Updated: 2025-10-21
"""

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime, timedelta
from typing import TYPE_CHECKING, Dict, Any

from ..visualizations import render_chart
from ..constants import format_currency, format_percentage, COLORS

if TYPE_CHECKING:
    from ..data_access import VendorPerformanceDAO


def render(
    dao: 'VendorPerformanceDAO',
    filters: Dict[str, Any],
    vendor_display: str
) -> None:
    """
    Render Invoice Analysis Tab
    
    Args:
        dao: Data access object
        filters: Global filters
        vendor_display: Selected vendor display string
    """
    st.subheader("💰 Invoice Analysis")
    st.markdown("*Analyze invoices and payments by invoice date*")
    
    # ==================== TAB-LEVEL DATE FILTER ====================
    st.markdown("---")
    st.markdown("#### 📅 Invoice Period Configuration")
    
    col1, col2, col3, col4 = st.columns([2, 1, 1, 1])
    
    with col1:
        date_range_option = st.selectbox(
            "Time Range",
            ["Last 3 Months", "Last 6 Months", "Last 12 Months", "Custom"],
            index=1,
            key="invoice_date_range"
        )
    
    # Calculate date range
    end_date = datetime.now().date()
    
    if date_range_option == "Custom":
        with col2:
            start_date = st.date_input(
                "From",
                value=end_date - timedelta(days=180),
                key="invoice_start_date"
            )
        with col3:
            end_date = st.date_input(
                "To",
                value=end_date,
                key="invoice_end_date"
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
        view_type = st.selectbox(
            "View",
            ["Summary", "Aging Analysis", "Payment Status"],
            index=0,
            key="invoice_view"
        )
    
    # Info box
    st.info("""
    💰 **Invoice Period Analysis**: This analyzes invoices issued in the selected period.
    
    - **Total Invoiced**: Invoice value (based on `inv_date`)
    - **Paid**: Amount paid to date
    - **Outstanding**: Unpaid amount
    - **Payment Rate**: Paid / Invoiced × 100%
    
    ⚠️ Note: These invoices may be for orders from different periods.
    """)
    
    st.markdown("---")
    
    # ==================== LOAD DATA ====================
    
    with st.spinner("Loading invoice data..."):
        try:
            # Get summary data
            summary_df = dao.get_invoice_summary(
                start_date=datetime.combine(start_date, datetime.min.time()),
                end_date=datetime.combine(end_date, datetime.min.time()),
                filters=filters
            )
            
            # Get detail data
            detail_df = dao.get_invoice_detail(
                start_date=datetime.combine(start_date, datetime.min.time()),
                end_date=datetime.combine(end_date, datetime.min.time()),
                filters=filters
            )
            
        except Exception as e:
            st.error(f"Error loading data: {str(e)}")
            return
    
    if summary_df.empty:
        st.warning("No invoice data found for the selected criteria")
        return
    
    # ==================== SUMMARY METRICS ====================
    
    st.markdown("### 🎯 Invoice Summary")
    
    # Aggregate totals
    total_invoiced = summary_df['total_invoiced_value'].sum()
    total_paid = summary_df['total_paid'].sum()
    total_outstanding = summary_df['total_outstanding'].sum()
    overdue_amount = summary_df['overdue_amount'].sum()
    avg_payment_rate = summary_df['payment_rate'].mean()
    total_invoices = summary_df['total_invoices'].sum()
    
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
            help="Vendors with invoices in period"
        )
    
    with col2:
        st.metric(
            "Total Invoices",
            f"{int(total_invoices):,}",
            help="Invoices issued in period"
        )
    
    with col3:
        st.metric(
            "Total Invoiced",
            format_currency(total_invoiced, compact=True),
            help="Total invoice value"
        )
    
    with col4:
        st.metric(
            "Paid",
            format_currency(total_paid, compact=True),
            delta=f"{(total_paid/total_invoiced*100):.1f}%" if total_invoiced > 0 else None,
            help="Amount paid"
        )
    
    with col5:
        st.metric(
            "Outstanding",
            format_currency(total_outstanding, compact=True),
            delta=f"{(total_outstanding/total_invoiced*100):.1f}%" if total_invoiced > 0 else None,
            delta_color="inverse",
            help="Unpaid amount"
        )
    
    with col6:
        st.metric(
            "Overdue",
            format_currency(overdue_amount, compact=True),
            delta="⚠️" if overdue_amount > 0 else "✔",
            delta_color="inverse" if overdue_amount > 0 else "normal",
            help="Overdue invoices"
        )
    
    st.markdown("---")
    
    # ==================== CONDITIONAL VIEWS ====================
    
    if view_type == "Summary":
        _render_summary_view(summary_df, detail_df, vendor_display, filters)
    elif view_type == "Aging Analysis":
        _render_aging_view(detail_df, vendor_display)
    else:  # Payment Status
        _render_payment_status_view(summary_df, detail_df, vendor_display)


def _render_summary_view(
    summary_df: pd.DataFrame,
    detail_df: pd.DataFrame,
    vendor_display: str,
    filters: Dict[str, Any]
) -> None:
    """Render summary view"""
    
    if vendor_display == "All Vendors":
        st.markdown("### 📊 Top Vendors by Invoice Value")
        
        top_vendors = summary_df.nlargest(10, 'total_invoiced_value')
        
        col1, col2 = st.columns(2)
        
        with col1:
            # Invoice value chart
            fig = px.bar(
                top_vendors.sort_values('total_invoiced_value'),
                x='total_invoiced_value',
                y='vendor',
                orientation='h',
                title="Top 10 Vendors - Invoice Value",
                labels={'total_invoiced_value': 'Invoice Value (USD)', 'vendor': ''},
                color='payment_rate',
                color_continuous_scale='RdYlGn',
                range_color=[0, 100]
            )
            fig.update_layout(height=400)
            render_chart(fig, key="chart_invoice_vendors")
        
        with col2:
            # Payment status breakdown
            status_summary = summary_df.agg({
                'fully_paid_count': 'sum',
                'partially_paid_count': 'sum',
                'unpaid_count': 'sum'
            })
            
            fig_status = go.Figure(data=[go.Pie(
                labels=['Fully Paid', 'Partially Paid', 'Unpaid'],
                values=[
                    status_summary['fully_paid_count'],
                    status_summary['partially_paid_count'],
                    status_summary['unpaid_count']
                ],
                marker=dict(colors=[COLORS['success'], COLORS['warning'], COLORS['danger']]),
                hole=0.4
            )])
            fig_status.update_layout(
                title="Payment Status Distribution",
                height=400
            )
            render_chart(fig_status, key="chart_payment_status")
        
        st.markdown("---")
        
        # Summary table
        st.markdown("### 📋 Vendor Invoice Summary")
        
        display_df = summary_df.copy()
        display_df['total_invoiced_value'] = display_df['total_invoiced_value'].apply(format_currency)
        display_df['total_paid'] = display_df['total_paid'].apply(format_currency)
        display_df['total_outstanding'] = display_df['total_outstanding'].apply(format_currency)
        display_df['payment_rate'] = display_df['payment_rate'].apply(lambda x: f"{x:.1f}%")
        
        display_cols = [
            'vendor', 'vendor_code', 'total_invoices',
            'total_invoiced_value', 'total_paid', 'total_outstanding',
            'payment_rate', 'fully_paid_count', 'unpaid_count'
        ]
        
        # Fixed: Use width='stretch' instead of use_container_width=True
        st.dataframe(
            display_df[display_cols],
            width='stretch',
            hide_index=True,
            height=400
        )
    
    else:
        # Single vendor view
        vendor_name = filters.get('vendor_name')
        vendor_data = summary_df[summary_df['vendor'] == vendor_name]
        
        if vendor_data.empty:
            st.warning(f"No invoice data for vendor: {vendor_name}")
            return
        
        vendor_data = vendor_data.iloc[0]
        
        st.markdown("### 💹 Vendor Invoice Performance")
        
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.metric(
                "Total Invoices",
                f"{int(vendor_data['total_invoices']):,}"
            )
        
        with col2:
            st.metric(
                "Total Invoiced",
                format_currency(vendor_data['total_invoiced_value'])
            )
        
        with col3:
            st.metric(
                "Paid",
                format_currency(vendor_data['total_paid']),
                delta=f"{vendor_data['payment_rate']:.1f}%"
            )
        
        with col4:
            st.metric(
                "Outstanding",
                format_currency(vendor_data['total_outstanding']),
                delta=f"{(vendor_data['total_outstanding']/vendor_data['total_invoiced_value']*100):.1f}%",
                delta_color="inverse"
            )
        
        st.markdown("---")
        
        # Invoice detail table
        st.markdown("### 📋 Invoice Details")
        
        vendor_detail = detail_df[detail_df['vendor'] == vendor_name].copy()
        vendor_detail = vendor_detail.sort_values('inv_date', ascending=False)
        
        # Format
        vendor_detail['inv_date'] = pd.to_datetime(vendor_detail['inv_date']).dt.strftime('%Y-%m-%d')
        vendor_detail['due_date'] = pd.to_datetime(vendor_detail['due_date']).dt.strftime('%Y-%m-%d')
        vendor_detail['calculated_invoiced_amount_usd'] = vendor_detail['calculated_invoiced_amount_usd'].apply(format_currency)
        vendor_detail['total_payment_made'] = vendor_detail['total_payment_made'].apply(format_currency)
        vendor_detail['outstanding_amount'] = vendor_detail['outstanding_amount'].apply(format_currency)
        
        display_cols = [
            'inv_number', 'inv_date', 'due_date', 'product_name',
            'calculated_invoiced_amount_usd', 'total_payment_made',
            'outstanding_amount', 'payment_status', 'aging_status'
        ]
        
        # Fixed: Use width='stretch' instead of use_container_width=True
        st.dataframe(
            vendor_detail[display_cols],
            width='stretch',
            hide_index=True,
            height=400
        )


def _render_aging_view(detail_df: pd.DataFrame, vendor_display: str) -> None:
    """Render aging analysis view"""
    
    st.markdown("### ⏰ Invoice Aging Analysis")
    
    # Define aging buckets
    def get_aging_bucket(days: int) -> str:
        if days < 0:
            return "Not Yet Due"
        elif days <= 30:
            return "0-30 Days"
        elif days <= 60:
            return "31-60 Days"
        elif days <= 90:
            return "61-90 Days"
        else:
            return ">90 Days"
    
    aging_df = detail_df.copy()
    aging_df['aging_bucket'] = aging_df['days_overdue'].apply(get_aging_bucket)
    
    # Aging summary
    aging_summary = aging_df.groupby('aging_bucket').agg({
        'inv_number': 'count',
        'outstanding_amount': 'sum'
    }).reset_index()
    
    aging_summary.columns = ['Aging Bucket', 'Invoice Count', 'Outstanding Amount']
    
    # Reorder buckets
    bucket_order = ["Not Yet Due", "0-30 Days", "31-60 Days", "61-90 Days", ">90 Days"]
    aging_summary['Aging Bucket'] = pd.Categorical(
        aging_summary['Aging Bucket'],
        categories=bucket_order,
        ordered=True
    )
    aging_summary = aging_summary.sort_values('Aging Bucket')
    
    col1, col2 = st.columns(2)
    
    with col1:
        # Aging bar chart
        fig_aging = px.bar(
            aging_summary,
            x='Aging Bucket',
            y='Outstanding Amount',
            title="Outstanding Amount by Aging",
            labels={'Outstanding Amount': 'Amount (USD)'},
            color='Aging Bucket',
            color_discrete_map={
                "Not Yet Due": COLORS['success'],
                "0-30 Days": COLORS['info'],
                "31-60 Days": COLORS['warning'],
                "61-90 Days": COLORS['danger'],
                ">90 Days": "#c0392b"
            }
        )
        fig_aging.update_layout(height=400, showlegend=False)
        render_chart(fig_aging, key="chart_aging_bar")
    
    with col2:
        # Aging pie chart
        fig_pie = go.Figure(data=[go.Pie(
            labels=aging_summary['Aging Bucket'],
            values=aging_summary['Outstanding Amount'],
            hole=0.4
        )])
        fig_pie.update_layout(
            title="Outstanding Amount Distribution",
            height=400
        )
        render_chart(fig_pie, key="chart_aging_pie")
    
    st.markdown("---")
    
    # Aging table
    st.markdown("### 📊 Aging Breakdown")
    
    display_summary = aging_summary.copy()
    display_summary['Outstanding Amount'] = display_summary['Outstanding Amount'].apply(format_currency)
    
    # Fixed: Use width='stretch' instead of use_container_width=True
    st.dataframe(
        display_summary,
        width='stretch',
        hide_index=True
    )


def _render_payment_status_view(
    summary_df: pd.DataFrame,
    detail_df: pd.DataFrame,
    vendor_display: str
) -> None:
    """Render payment status view"""
    
    st.markdown("### 💳 Payment Status Analysis")
    
    # Payment status summary
    status_counts = detail_df['payment_status'].value_counts()
    status_amounts = detail_df.groupby('payment_status')['outstanding_amount'].sum()
    
    col1, col2 = st.columns(2)
    
    with col1:
        # Status count
        fig_count = go.Figure(data=[go.Pie(
            labels=status_counts.index,
            values=status_counts.values,
            marker=dict(colors=[
                COLORS['success'] if s == 'Fully Paid'
                else COLORS['warning'] if s == 'Partially Paid'
                else COLORS['danger']
                for s in status_counts.index
            ]),
            hole=0.4
        )])
        fig_count.update_layout(
            title="Invoice Count by Status",
            height=400
        )
        render_chart(fig_count, key="chart_status_count")
    
    with col2:
        # Status amount
        fig_amount = px.bar(
            x=status_amounts.index,
            y=status_amounts.values,
            title="Outstanding Amount by Status",
            labels={'x': 'Payment Status', 'y': 'Outstanding (USD)'},
            color=status_amounts.index,
            color_discrete_map={
                'Fully Paid': COLORS['success'],
                'Partially Paid': COLORS['warning'],
                'Unpaid': COLORS['danger']
            }
        )
        fig_amount.update_layout(height=400, showlegend=False)
        render_chart(fig_amount, key="chart_status_amount")
    
    st.markdown("---")
    
    # Payment timeline
    st.markdown("### 📅 Payment Timeline")
    
    timeline_df = detail_df.copy()
    timeline_df['inv_date'] = pd.to_datetime(timeline_df['inv_date'])
    timeline_df = timeline_df.sort_values('inv_date')
    
    # Aggregate by invoice date
    timeline_agg = timeline_df.groupby(timeline_df['inv_date'].dt.to_period('M')).agg({
        'calculated_invoiced_amount_usd': 'sum',
        'total_payment_made': 'sum',
        'outstanding_amount': 'sum'
    }).reset_index()
    
    timeline_agg['inv_date'] = timeline_agg['inv_date'].dt.to_timestamp()
    
    fig_timeline = go.Figure()
    
    fig_timeline.add_trace(go.Bar(
        x=timeline_agg['inv_date'],
        y=timeline_agg['calculated_invoiced_amount_usd'],
        name='Invoiced',
        marker_color=COLORS['primary']
    ))
    
    fig_timeline.add_trace(go.Bar(
        x=timeline_agg['inv_date'],
        y=timeline_agg['total_payment_made'],
        name='Paid',
        marker_color=COLORS['success']
    ))
    
    fig_timeline.update_layout(
        title="Invoice vs Payment Timeline",
        xaxis_title="Month",
        yaxis_title="Amount (USD)",
        barmode='group',
        height=400,
        hovermode='x unified'
    )
    
    render_chart(fig_timeline, key="chart_payment_timeline")