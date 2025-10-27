"""
Financial Analysis Tab - Fixed & Cleaned

FIXES APPLIED:
1. ✅ Removed dangerous auto VND→USD conversion
2. ✅ Implemented _validate_financial_data function
3. ✅ Fixed currency formatting with proper validation
4. ✅ Improved error handling
5. ✅ Removed unused code

Version: 3.0
Last Updated: 2025-10-22
"""

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import plotly.express as px
from datetime import datetime, timedelta
from typing import TYPE_CHECKING, Dict, Any, Optional, Tuple
import logging

from ..constants import COLORS, CHART_HEIGHTS
from ..exceptions import DataAccessError, ValidationError

if TYPE_CHECKING:
    from ..data_access import VendorPerformanceDAO

logger = logging.getLogger(__name__)


def render(
    dao: 'VendorPerformanceDAO',
    filters: Dict[str, Any],
    vendor_display: str
) -> None:
    """Render Financial Analysis Tab with validated metrics"""
    
    st.subheader("💰 Financial Analysis")
    st.markdown("*Comprehensive financial metrics with clear date dimensions*")
    
    # Date configuration
    st.markdown("---")
    date_config = _render_date_configuration()
    
    # Key concepts
    with st.expander("📊 Understanding Financial Metrics", expanded=False):
        _render_metrics_explanation()
    
    st.markdown("---")
    
    # Load data with validation
    try:
        with st.spinner("Loading financial data..."):
            order_data, invoice_data, period_data = _load_all_data(
                dao, 
                date_config['start_date'],
                date_config['end_date'],
                date_config['period_type'],
                filters
            )
            
            # Validate data
            _validate_financial_data(order_data, invoice_data)
            
    except DataAccessError as e:
        st.error(f"Error loading data: {str(e)}")
        logger.error(f"Data loading failed: {e}", exc_info=True)
        return
    except ValidationError as e:
        st.warning(f"Data validation issue: {str(e)}")
        logger.warning(f"Validation failed: {e}")
    
    # Summary metrics
    st.markdown("### 🎯 Financial Summary")
    metrics = _calculate_summary_metrics(order_data, invoice_data, vendor_display)
    _render_summary_metrics(metrics)
    
    st.markdown("---")
    
    # Financial trends
    st.markdown("### 📈 Financial Trends")
    
    if not period_data.empty:
        if date_config['chart_type'] == "Period Breakdown":
            _render_period_breakdown_chart(period_data, date_config['period_type'])
        else:
            _render_cumulative_chart(period_data, date_config['period_type'])
    else:
        st.info("No data available for the selected period")
    
    st.markdown("---")
    
    # Conversion analysis
    st.markdown("### 🔄 Conversion Analysis")
    _render_conversion_gauges(metrics)
    
    st.markdown("---")
    
    # Detailed views
    if vendor_display == "All Vendors":
        st.markdown("### 🏢 Vendor Comparison")
        _render_vendor_comparison(order_data)
    else:
        st.markdown("### 📊 Vendor Details")
        _render_vendor_details(order_data, invoice_data, filters.get('vendor_name'))
    
    # Export
    st.markdown("---")
    _render_export_section(period_data, order_data, invoice_data, date_config)


# ==================== DATE CONFIGURATION ====================

def _render_date_configuration() -> Dict[str, Any]:
    """Render date configuration controls"""
    
    st.markdown("#### 📅 Analysis Period Configuration")
    
    col1, col2, col3, col4 = st.columns([2, 1, 1, 1])
    
    with col1:
        date_range_option = st.selectbox(
            "Time Range",
            ["This Year", "Last 3 Months", "Last 6 Months", "Last 12 Months", "Custom"],
            index=0,
            key="financial_date_range"
        )
    
    today = datetime.now().date()
    
    if date_range_option == "Custom":
        with col2:
            start_date = st.date_input(
                "From",
                value=today - timedelta(days=180),
                key="financial_start_date"
            )
        with col3:
            end_date = st.date_input(
                "To",
                value=today,
                key="financial_end_date"
            )
    elif date_range_option == "This Year":
        start_date = datetime(today.year, 1, 1).date()
        end_date = today
    else:
        months_map = {
            "Last 3 Months": 3,
            "Last 6 Months": 6,
            "Last 12 Months": 12
        }
        months = months_map[date_range_option]
        end_date = today
        start_date = today - timedelta(days=months * 30)
    
    with col2 if date_range_option != "Custom" else col3:
        period_type = st.selectbox(
            "Group By",
            ["Monthly", "Quarterly", "Yearly"],
            index=0,
            key="financial_period"
        )
    
    with col3 if date_range_option != "Custom" else col4:
        chart_type = st.selectbox(
            "Chart Type",
            ["Period Breakdown", "Cumulative"],
            index=0,
            key="financial_chart_type"
        )
    
    if date_range_option != "Custom":
        st.caption(f"📅 Period: {start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')}")
    
    return {
        'start_date': start_date,
        'end_date': end_date,
        'period_type': period_type.lower(),
        'chart_type': chart_type,
        'date_range_option': date_range_option
    }


def _render_metrics_explanation():
    """Render explanation of financial metrics"""
    st.markdown("""
    ### Date Dimensions Explained:
    
    | Metric | Date Field | Description |
    |--------|------------|-------------|
    | **Order Entry** | PO Date | Value when PO was created |
    | **Invoice Amount** | Invoice Date | Value when invoice issued |
    | **Payment** | Payment Date | Actual payment received |
    
    ### Key Formulas:
    - **Conversion Rate** = (Invoiced / Order Entry) × 100% (max 100%)
    - **Payment Rate** = (Paid / Invoiced) × 100%
    - **Outstanding** = Order Entry - Invoiced
    """)


# ==================== DATA LOADING & VALIDATION ====================

def _load_all_data(
    dao: 'VendorPerformanceDAO',
    start_date: datetime.date,
    end_date: datetime.date,
    period_type: str,
    filters: Dict[str, Any]
) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Load all required data with validation"""
    
    start_dt = datetime.combine(start_date, datetime.min.time())
    end_dt = datetime.combine(end_date, datetime.min.time())
    
    # Load order data (PO date based)
    order_data = dao.get_order_summary_validated(
        start_date=start_dt,
        end_date=end_dt,
        filters=filters
    )
    
    # Load invoice data (invoice date based)
    invoice_data = dao.get_invoice_summary(
        start_date=start_dt,
        end_date=end_dt,
        filters=filters
    )
    
    # Aggregate by period for trends
    from ..calculations import PerformanceCalculator
    
    if not order_data.empty:
        # Add date column for aggregation
        order_data['po_date'] = pd.to_datetime(start_date)
        period_data = PerformanceCalculator.aggregate_by_period(
            order_data,
            period_type=period_type,
            date_column='po_date'
        )
    else:
        period_data = pd.DataFrame()
    
    return order_data, invoice_data, period_data


def _validate_financial_data(
    order_data: pd.DataFrame,
    invoice_data: pd.DataFrame
) -> None:
    """
    Validate financial data for common issues
    
    NEW FUNCTION: Implemented to validate data quality
    
    Raises:
        ValidationError: If critical data validation fails
    """
    issues = []
    
    # Check 1: Non-empty dataframes
    if order_data.empty and invoice_data.empty:
        raise ValidationError(
            "No data available for the selected period and filters",
            {'order_rows': 0, 'invoice_rows': 0}
        )
    
    # Check 2: Reasonable value ranges
    if not order_data.empty:
        max_order = order_data['total_order_value'].max()
        if max_order > 1_000_000_000:  # >$1B
            warning_msg = (
                f"⚠️ SUSPICIOUS VALUE: ${max_order:.2e}. "
                "This may indicate currency mismatch or data quality issue. "
                "Please investigate the source data."
            )
            issues.append(warning_msg)
            logger.error(warning_msg)
        
        # Check for negative values
        if (order_data['total_order_value'] < 0).any():
            issues.append("❌ Found negative order values - data quality issue")
    
    # Check 3: Invoice consistency
    if not invoice_data.empty and not order_data.empty:
        total_invoiced = invoice_data['total_invoiced_value'].sum()
        total_ordered = order_data['total_order_value'].sum()
        
        if total_invoiced > total_ordered * 1.5:  # >150% invoiced
            issues.append(
                f"⚠️ Invoice amount (${total_invoiced:,.0f}) significantly "
                f"exceeds order amount (${total_ordered:,.0f}). "
                "This may indicate data issues."
            )
    
    # Check 4: Conversion rate reasonableness
    if not order_data.empty and 'conversion_rate' in order_data.columns:
        max_conv = order_data['conversion_rate'].max()
        if max_conv > 100:
            issues.append(
                f"❌ Conversion rate exceeds 100% ({max_conv:.1f}%) - "
                "this should be capped in the query"
            )
    
    # Log and display warnings
    if issues:
        warning_msg = "Data validation warnings detected:\n" + "\n".join(issues)
        logger.warning(warning_msg)
        
        with st.expander("⚠️ Data Quality Warnings", expanded=False):
            for issue in issues:
                st.warning(issue)


# ==================== METRICS CALCULATION ====================

def _calculate_summary_metrics(
    order_data: pd.DataFrame,
    invoice_data: pd.DataFrame,
    vendor_display: str
) -> Dict[str, Any]:
    """Calculate summary metrics"""
    
    metrics = {
        'total_order_value': 0,
        'total_invoiced_value': 0,
        'outstanding_value': 0,
        'conversion_rate': 0,
        'total_paid': 0,
        'payment_rate': 0,
        'vendor_count': 0
    }
    
    if not order_data.empty:
        metrics['total_order_value'] = order_data['total_order_value'].sum()
        metrics['total_invoiced_value'] = order_data['total_invoiced_value'].sum()
        metrics['outstanding_value'] = order_data['outstanding_value'].sum()
        metrics['vendor_count'] = len(order_data)
        
        if metrics['total_order_value'] > 0:
            metrics['conversion_rate'] = min(
                (metrics['total_invoiced_value'] / metrics['total_order_value'] * 100),
                100.0  # Cap at 100%
            )
    
    if not invoice_data.empty:
        metrics['total_paid'] = invoice_data['total_paid'].sum()
        total_inv = invoice_data['total_invoiced_value'].sum()
        
        if total_inv > 0:
            metrics['payment_rate'] = min(
                (metrics['total_paid'] / total_inv * 100),
                100.0  # Cap at 100%
            )
    
    return metrics


def _render_summary_metrics(metrics: Dict[str, Any]):
    """Render summary metrics cards"""
    
    col1, col2, col3, col4, col5 = st.columns(5)
    
    with col1:
        st.metric(
            "Order Entry",
            _format_currency_safe(metrics['total_order_value'], compact=True)
        )
    
    with col2:
        st.metric(
            "Invoiced",
            _format_currency_safe(metrics['total_invoiced_value'], compact=True),
            delta=f"{metrics['conversion_rate']:.1f}%"
        )
    
    with col3:
        st.metric(
            "Outstanding",
            _format_currency_safe(metrics['outstanding_value'], compact=True),
            delta=f"-{(metrics['outstanding_value']/metrics['total_order_value']*100):.1f}%" 
                if metrics['total_order_value'] > 0 else "0%",
            delta_color="inverse"
        )
    
    with col4:
        st.metric(
            "Paid",
            _format_currency_safe(metrics['total_paid'], compact=True),
            delta=f"{metrics['payment_rate']:.1f}%"
        )
    
    with col5:
        st.metric(
            "Vendors",
            f"{metrics['vendor_count']:,}"
        )


# ==================== CHART RENDERING ====================

def _render_period_breakdown_chart(period_data: pd.DataFrame, period_type: str):
    """Render period breakdown chart with dual axis"""
    
    fig = make_subplots(specs=[[{"secondary_y": True}]])
    
    # Order Entry bars
    fig.add_trace(
        go.Bar(
            x=period_data['Period'],
            y=period_data['Order Value'],
            name='Order Entry',
            marker_color=COLORS['primary'],
            opacity=0.7
        ),
        secondary_y=False
    )
    
    # Invoiced Value bars (with safety check)
    if 'Invoiced Value' in period_data.columns:
        fig.add_trace(
            go.Bar(
                x=period_data['Period'],
                y=period_data['Invoiced Value'],
                name='Invoiced Value',
                marker_color=COLORS['success'],
                opacity=0.7
            ),
            secondary_y=False
        )
    else:
        logger.warning("'Invoiced Value' column not found in period_data")
    
    # Conversion Rate line
    if 'Conversion Rate' in period_data.columns:
        fig.add_trace(
            go.Scatter(
                x=period_data['Period'],
                y=period_data['Conversion Rate'],
                name='Conversion Rate %',
                line=dict(color=COLORS['danger'], width=3, dash='dash'),
                yaxis='y2'
            ),
            secondary_y=True
        )
        
        # Target line
        fig.add_hline(
            y=90, 
            line_dash="dot", 
            line_color="gray",
            annotation_text="Target: 90%",
            secondary_y=True
        )
    
    fig.update_yaxes(title_text="Value (USD)", secondary_y=False)
    fig.update_yaxes(title_text="Conversion Rate (%)", secondary_y=True, range=[0, 110])
    
    fig.update_layout(
        title="Order Entry vs Invoiced Trend",
        xaxis_title="Period",
        hovermode='x unified',
        height=CHART_HEIGHTS['standard'],
        showlegend=True
    )
    
    st.plotly_chart(fig, width="stretch", key="period_chart")


def _render_cumulative_chart(period_data: pd.DataFrame, period_type: str):
    """Render cumulative chart"""
    
    # Safety check for required columns
    required_cols = ['Period', 'Order Value', 'Invoiced Value']
    missing_cols = [col for col in required_cols if col not in period_data.columns]
    
    if missing_cols:
        st.warning(f"Missing columns for cumulative chart: {', '.join(missing_cols)}")
        logger.warning(f"Cannot render cumulative chart - missing columns: {missing_cols}")
        return
    
    df = period_data.copy()
    df['Cumulative Order'] = df['Order Value'].cumsum()
    df['Cumulative Invoiced'] = df['Invoiced Value'].cumsum()
    
    fig = go.Figure()
    
    fig.add_trace(go.Scatter(
        x=df['Period'],
        y=df['Cumulative Order'],
        mode='lines+markers',
        name='Cumulative Order Entry',
        line=dict(color=COLORS['primary'], width=3),
        fill='tozeroy'
    ))
    
    fig.add_trace(go.Scatter(
        x=df['Period'],
        y=df['Cumulative Invoiced'],
        mode='lines+markers',
        name='Cumulative Invoiced',
        line=dict(color=COLORS['success'], width=3),
        fill='tozeroy'
    ))
    
    fig.update_layout(
        title="Cumulative Financial Performance",
        xaxis_title="Period",
        yaxis_title="Cumulative Value (USD)",
        hovermode='x unified',
        height=CHART_HEIGHTS['standard'],
        showlegend=True
    )
    
    st.plotly_chart(fig, width="stretch", key="cumulative_chart")


def _render_conversion_gauges(metrics: Dict[str, Any]):
    """Render conversion rate gauges"""
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        fig = go.Figure(go.Indicator(
            mode="gauge+number",
            value=metrics['conversion_rate'],
            title={'text': "Order → Invoice"},
            gauge={
                'axis': {'range': [0, 100]},
                'bar': {'color': _get_gauge_color(metrics['conversion_rate'])},
                'steps': [
                    {'range': [0, 80], 'color': "rgba(255, 255, 255, 0.1)"},
                    {'range': [80, 90], 'color': "rgba(255, 255, 0, 0.1)"},
                    {'range': [90, 100], 'color': "rgba(0, 255, 0, 0.1)"}
                ],
                'threshold': {
                    'line': {'color': "red", 'width': 4},
                    'thickness': 0.75,
                    'value': 90
                }
            }
        ))
        fig.update_layout(height=250, margin=dict(l=20, r=20, t=40, b=20))
        st.plotly_chart(fig, width="stretch", key="gauge_conversion")
    
    with col2:
        fig = go.Figure(go.Indicator(
            mode="gauge+number",
            value=metrics['payment_rate'],
            title={'text': "Invoice → Payment"},
            gauge={
                'axis': {'range': [0, 100]},
                'bar': {'color': _get_gauge_color(metrics['payment_rate'])},
                'steps': [
                    {'range': [0, 80], 'color': "rgba(255, 255, 255, 0.1)"},
                    {'range': [80, 90], 'color': "rgba(255, 255, 0, 0.1)"},
                    {'range': [90, 100], 'color': "rgba(0, 255, 0, 0.1)"}
                ]
            }
        ))
        fig.update_layout(height=250, margin=dict(l=20, r=20, t=40, b=20))
        st.plotly_chart(fig, width="stretch", key="gauge_payment")
    
    with col3:
        health_score = (metrics['conversion_rate'] + metrics['payment_rate']) / 2
        
        if health_score >= 90:
            st.success(f"### ✅ Excellent\n**Score: {health_score:.1f}%**")
        elif health_score >= 80:
            st.warning(f"### ⚠️ Good\n**Score: {health_score:.1f}%**")
        else:
            st.error(f"### ❌ Needs Attention\n**Score: {health_score:.1f}%**")
        
        st.caption("Based on conversion and payment rates")


def _render_vendor_comparison(order_data: pd.DataFrame):
    """Render vendor comparison view"""
    
    if order_data.empty:
        st.info("No vendor data available")
        return
    
    top_vendors = order_data.nlargest(10, 'total_order_value').copy()
    
    fig = px.bar(
        top_vendors.sort_values('total_order_value'),
        x='total_order_value',
        y='vendor_name',
        orientation='h',
        title="Top 10 Vendors by Order Value",
        labels={'total_order_value': 'Order Value (USD)', 'vendor_name': ''},
        color='conversion_rate',
        color_continuous_scale='RdYlGn',
        range_color=[0, 100]
    )
    
    fig.update_layout(height=400, showlegend=False)
    st.plotly_chart(fig, width="stretch", key="vendor_comparison")


def _render_vendor_details(
    order_data: pd.DataFrame,
    invoice_data: pd.DataFrame,
    vendor_name: Optional[str]
):
    """Render single vendor details"""
    
    if vendor_name and not order_data.empty:
        vendor_order = order_data[order_data['vendor_name'] == vendor_name]
        if not vendor_order.empty:
            vendor_order = vendor_order.iloc[0]
            
            col1, col2, col3 = st.columns(3)
            
            with col1:
                st.markdown(f"**Vendor:** {vendor_name}")
                st.markdown(f"**Code:** {vendor_order.get('vendor_code', 'N/A')}")
            
            with col2:
                st.markdown(f"**Type:** {vendor_order.get('vendor_type', 'N/A')}")
                st.markdown(f"**Location:** {vendor_order.get('vendor_location_type', 'N/A')}")
            
            with col3:
                st.markdown(f"**Total POs:** {vendor_order.get('total_pos', 0):,.0f}")
                st.markdown(f"**Conv Rate:** {vendor_order.get('conversion_rate', 0):.1f}%")
    else:
        st.info("Select a specific vendor to view details")


def _render_export_section(
    period_data: pd.DataFrame,
    order_data: pd.DataFrame,
    invoice_data: pd.DataFrame,
    date_config: Dict[str, Any]
):
    """Render export buttons"""
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        if not period_data.empty:
            csv = period_data.to_csv(index=False).encode('utf-8')
            st.download_button(
                label="📥 Download Period Data",
                data=csv,
                file_name=f"financial_period_{datetime.now().strftime('%Y%m%d')}.csv",
                mime='text/csv'
            )
    
    with col2:
        if not order_data.empty:
            csv = order_data.to_csv(index=False).encode('utf-8')
            st.download_button(
                label="📥 Download Order Data",
                data=csv,
                file_name=f"order_data_{datetime.now().strftime('%Y%m%d')}.csv",
                mime='text/csv'
            )
    
    with col3:
        if not invoice_data.empty:
            csv = invoice_data.to_csv(index=False).encode('utf-8')
            st.download_button(
                label="📥 Download Invoice Data",
                data=csv,
                file_name=f"invoice_data_{datetime.now().strftime('%Y%m%d')}.csv",
                mime='text/csv'
            )


# ==================== UTILITY FUNCTIONS ====================

def _format_currency_safe(value: float, compact: bool = True) -> str:
    """
    Format currency with safety checks
    
    FIXED: Removed dangerous auto VND→USD conversion
    Instead: Validate and warn about suspicious values
    
    Args:
        value: Amount in USD (from database view's total_amount_usd)
        compact: Use K/M notation
        
    Returns:
        Formatted currency string
    """
    if pd.isna(value) or value is None:
        return "$0"
    
    # ✅ FIXED: Log suspicious values but DON'T auto-convert
    if value > 1_000_000_000:  # Over $1B - suspicious
        logger.error(
            f"⚠️ SUSPICIOUS VALUE: ${value:,.2e}. "
            f"This may indicate currency mismatch or data quality issue. "
            f"Please investigate the source data."
        )
        # Return with warning prefix but keep original value
        if compact and abs(value) >= 1_000_000_000:
            return f"⚠️ ${value/1_000_000_000:.1f}B"
        return f"⚠️ ${value:,.0f}"
    
    # Normal formatting for reasonable values
    if compact:
        if abs(value) >= 1_000_000:
            return f"${value/1_000_000:.1f}M"
        elif abs(value) >= 1_000:
            return f"${value/1_000:.1f}K"
    
    return f"${value:,.0f}"


def _get_gauge_color(value: float) -> str:
    """Get color for gauge based on value"""
    if value >= 90:
        return COLORS['success']
    elif value >= 80:
        return COLORS['warning']
    else:
        return COLORS['danger']