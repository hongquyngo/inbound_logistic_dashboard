# utils/can_tracking/analytics.py

"""
CAN Analytics - Metrics & Visualizations with Fragment Support

Handles all calculations and chart generation for CAN tracking analytics.
Charts are wrapped in fragments for isolated rendering.
"""

import streamlit as st
import pandas as pd
import plotly.express as px
import logging

logger = logging.getLogger(__name__)


# ============================================================================
# METRICS CALCULATION
# ============================================================================

def calculate_metrics(df, show_pending_only, urgent_threshold=7, critical_threshold=14):
    """
    Calculate dashboard metrics for CAN tracking
    
    Args:
        df (pd.DataFrame): CAN dataframe
        show_pending_only (bool): Whether showing only pending items
        urgent_threshold (int): Days threshold for urgent items
        critical_threshold (int): Days threshold for critical items
        
    Returns:
        dict: Dictionary of calculated metrics
    """
    try:
        if df is None or df.empty:
            return {
                'total_items': 0,
                'pending_items': 0,
                'total_value': 0,
                'arrived_value': 0,
                'urgent_items': 0,
                'critical_items': 0,
                'avg_days': 0,
                'avg_days_all': 0,
                'unique_cans': 0,
                'completed_cans': 0
            }
        
        metrics = {
            'total_items': len(df),
            'pending_items': len(df[df['pending_quantity'] > 0]),
            'total_value': df['pending_value_usd'].sum(),
            'arrived_value': df['landed_cost_usd'].sum() if 'landed_cost_usd' in df.columns else 0,
            'urgent_items': len(df[
                (df['days_since_arrival'] > urgent_threshold) & 
                (df['pending_quantity'] > 0)
            ]),
            'critical_items': len(df[
                (df['days_since_arrival'] > critical_threshold) & 
                (df['pending_quantity'] > 0)
            ]),
            'avg_days': df['days_since_arrival'].mean() if len(df) > 0 else 0,
            'avg_days_all': df['days_since_arrival'].mean() if len(df) > 0 else 0,
            'unique_cans': df['arrival_note_number'].nunique(),
            'completed_cans': df[df['pending_quantity'] == 0]['arrival_note_number'].nunique() if not show_pending_only else 0
        }
        
        # Calculate average days for pending items separately if showing all items
        if not show_pending_only and metrics['pending_items'] > 0:
            pending_df = df[df['pending_quantity'] > 0]
            metrics['avg_days'] = pending_df['days_since_arrival'].mean()
        
        return metrics
        
    except Exception as e:
        logger.error(f"Error calculating metrics: {e}")
        return {
            'total_items': 0,
            'pending_items': 0,
            'total_value': 0,
            'arrived_value': 0,
            'urgent_items': 0,
            'critical_items': 0,
            'avg_days': 0,
            'avg_days_all': 0,
            'unique_cans': 0,
            'completed_cans': 0
        }


# ============================================================================
# FRAGMENT-WRAPPED ANALYTICS RENDERER
# ============================================================================

def render_analytics_tab(can_df: pd.DataFrame) -> None:
    """
    Entry point for analytics tab - stores data and calls fragment
    
    Args:
        can_df: CAN dataframe
    """
    st.subheader("📊 CAN Analytics & Trends")
    
    analytics_df = can_df[can_df['pending_quantity'] > 0]
    
    if analytics_df.empty:
        st.info("ℹ️ No pending items to analyze with the selected filters")
        return
    
    # Store data for fragment access
    st.session_state['_analytics_df'] = analytics_df
    
    # Render analytics fragment
    _render_analytics_fragment()


@st.fragment
def _render_analytics_fragment() -> None:
    """
    Fragment for analytics charts - renders independently
    """
    analytics_df = st.session_state.get('_analytics_df')
    
    if analytics_df is None or analytics_df.empty:
        st.info("ℹ️ No pending items to analyze")
        return
    
    # Row 1: Days Pending + Vendor Location
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("#### Days Pending Distribution")
        fig1 = create_days_pending_chart(analytics_df)
        if fig1:
            st.plotly_chart(fig1, use_container_width=True, key="chart_days_pending")
        else:
            st.info("No data available for this chart")
    
    with col2:
        st.markdown("#### Value by Vendor Location")
        fig2 = create_vendor_location_chart(analytics_df)
        if fig2:
            st.plotly_chart(fig2, use_container_width=True, key="chart_vendor_location")
        else:
            st.info("No data available for this chart")
    
    st.markdown("---")
    
    # Row 2: Top Vendors
    st.markdown("#### Top 10 Vendors by Pending Value")
    fig3, vendor_table = create_vendor_analysis_chart(analytics_df)
    if fig3:
        st.plotly_chart(fig3, use_container_width=True, key="chart_vendor_analysis")
        
        if vendor_table is not None and not vendor_table.empty:
            st.dataframe(vendor_table, use_container_width=True, hide_index=True)
    else:
        st.info("No vendor data available")
    
    st.markdown("---")
    
    # Row 3: Daily Trend
    st.markdown("#### Daily Arrival Trend (Last 30 days)")
    fig4 = create_daily_trend_chart(analytics_df)
    if fig4:
        st.plotly_chart(fig4, use_container_width=True, key="chart_daily_trend")
    else:
        st.info("No trend data available")


# ============================================================================
# CHART GENERATION FUNCTIONS
# ============================================================================

def create_days_pending_chart(df):
    """
    Create days pending distribution bar chart
    
    Args:
        df (pd.DataFrame): CAN dataframe
        
    Returns:
        plotly.graph_objects.Figure: Bar chart or None if no data
    """
    try:
        if df is None or df.empty:
            return None
        
        # Create bins for days pending
        bins = [0, 3, 7, 14, 30, float('inf')]
        labels = ['0-3 days', '4-7 days', '8-14 days', '15-30 days', '>30 days']
        
        df_copy = df.copy()
        df_copy['days_category'] = pd.cut(
            df_copy['days_since_arrival'], 
            bins=bins, 
            labels=labels,
            include_lowest=True
        )
        
        # Aggregate by category
        category_summary = df_copy.groupby('days_category', observed=True).agg({
            'can_line_id': 'count',
            'pending_value_usd': 'sum'
        }).reset_index()
        
        if category_summary.empty:
            return None
        
        category_summary.columns = ['Days Category', 'Item Count', 'Total Value']
        
        # Create bar chart with color coding
        color_map = {
            '0-3 days': '#2ecc71',      # Green
            '4-7 days': '#f39c12',      # Orange
            '8-14 days': '#e67e22',     # Dark Orange
            '15-30 days': '#e74c3c',    # Red
            '>30 days': '#c0392b'       # Dark Red
        }
        
        fig = px.bar(
            category_summary,
            x='Days Category',
            y='Item Count',
            title='Items by Days Pending',
            color='Days Category',
            color_discrete_map=color_map,
            hover_data={'Total Value': ':$,.0f'}
        )
        
        fig.update_layout(
            xaxis_title='Days Pending',
            yaxis_title='Number of Items',
            showlegend=False
        )
        
        return fig
        
    except Exception as e:
        logger.error(f"Error creating days pending chart: {e}")
        return None


def create_vendor_location_chart(df):
    """
    Create vendor location type pie chart
    
    Args:
        df (pd.DataFrame): CAN dataframe
        
    Returns:
        plotly.graph_objects.Figure: Pie chart or None if no data
    """
    try:
        if df is None or df.empty:
            return None
        
        # Aggregate by vendor location type
        location_summary = df.groupby('vendor_location_type').agg({
            'can_line_id': 'count',
            'pending_value_usd': 'sum'
        }).reset_index()
        
        if location_summary.empty:
            return None
        
        location_summary.columns = ['Location Type', 'Item Count', 'Total Value']
        
        # Create pie chart
        fig = px.pie(
            location_summary,
            values='Total Value',
            names='Location Type',
            title='Pending Value by Vendor Location',
            hover_data={'Item Count': True},
            labels={'Total Value': 'Pending Value (USD)'}
        )
        
        fig.update_traces(
            textposition='inside',
            textinfo='percent+label',
            hovertemplate='<b>%{label}</b><br>' +
                         'Value: $%{value:,.0f}<br>' +
                         'Items: %{customdata[0]}<br>' +
                         '<extra></extra>'
        )
        
        return fig
        
    except Exception as e:
        logger.error(f"Error creating vendor location chart: {e}")
        return None


def create_vendor_analysis_chart(df):
    """
    Create top 10 vendors by pending value bar chart
    
    Args:
        df (pd.DataFrame): CAN dataframe
        
    Returns:
        tuple: (plotly.graph_objects.Figure, pd.DataFrame) - Chart and vendor table,
               or (None, None) if no data
    """
    try:
        if df is None or df.empty:
            return None, None
        
        # Aggregate by vendor
        vendor_analysis = df.groupby([
            'vendor', 
            'vendor_type', 
            'vendor_location_type'
        ]).agg({
            'arrival_note_number': 'nunique',
            'can_line_id': 'count',
            'pending_quantity': 'sum',
            'pending_value_usd': 'sum',
            'days_since_arrival': 'mean'
        }).reset_index()
        
        if vendor_analysis.empty:
            return None, None
        
        vendor_analysis.columns = [
            'Vendor', 'Type', 'Location', 'CAN Count', 
            'Line Items', 'Total Quantity', 'Total Value', 
            'Avg Days Pending'
        ]
        
        # Sort by value and take top 10
        vendor_analysis = vendor_analysis.sort_values('Total Value', ascending=False).head(10)
        
        # Create bar chart
        fig = px.bar(
            vendor_analysis,
            x='Vendor',
            y='Total Value',
            color='Avg Days Pending',
            title='Top 10 Vendors by Pending Value',
            hover_data=['Type', 'Location', 'CAN Count', 'Line Items'],
            color_continuous_scale='Reds',
            labels={'Total Value': 'Pending Value (USD)', 'Avg Days Pending': 'Avg Days'}
        )
        
        fig.update_layout(
            xaxis_title='Vendor',
            yaxis_title='Pending Value (USD)',
            xaxis_tickangle=-45
        )
        
        # Format table for display
        vendor_table = vendor_analysis.copy()
        vendor_table['Total Value'] = vendor_table['Total Value'].apply(lambda x: f"${x:,.0f}")
        vendor_table['Avg Days Pending'] = vendor_table['Avg Days Pending'].apply(lambda x: f"{x:.1f}")
        
        return fig, vendor_table
        
    except Exception as e:
        logger.error(f"Error creating vendor analysis chart: {e}")
        return None, None


def create_daily_trend_chart(df):
    """
    Create daily arrival trend line chart (last 30 days)
    
    Args:
        df (pd.DataFrame): CAN dataframe
        
    Returns:
        plotly.graph_objects.Figure: Line chart or None if no data
    """
    try:
        if df is None or df.empty:
            return None
        
        # Ensure arrival_date is datetime
        df_copy = df.copy()
        df_copy['arrival_date'] = pd.to_datetime(df_copy['arrival_date'])
        
        # Create daily summary
        daily_summary = df_copy.groupby([
            df_copy['arrival_date'].dt.date, 
            'vendor_location_type'
        ]).agg({
            'arrival_note_number': 'nunique',
            'can_line_id': 'count',
            'pending_value_usd': 'sum'
        }).reset_index()
        
        if daily_summary.empty:
            return None
        
        daily_summary.columns = [
            'Date', 'Location Type', 'CAN Count', 
            'Line Items', 'Value'
        ]
        
        # Create line chart
        fig = px.line(
            daily_summary,
            x='Date',
            y='CAN Count',
            color='Location Type',
            title='Daily CAN Count by Vendor Location',
            markers=True,
            hover_data={'Line Items': True, 'Value': ':$,.0f'},
            labels={'CAN Count': 'Number of CANs'}
        )
        
        fig.update_layout(
            xaxis_title='Arrival Date',
            yaxis_title='Number of CANs',
            hovermode='x unified'
        )
        
        return fig
        
    except Exception as e:
        logger.error(f"Error creating daily trend chart: {e}")
        return None