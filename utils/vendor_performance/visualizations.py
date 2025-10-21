"""
Visualization Factory for Vendor Performance

Creates consistent, styled charts for vendor performance analysis.
"""

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from typing import Optional, List, Dict, Any
import logging

logger = logging.getLogger(__name__)


class ChartFactory:
    """Factory class for creating standardized charts"""
    
    # Standard color palette
    COLORS = {
        'primary': '#3498db',
        'success': '#2ecc71',
        'warning': '#f39c12',
        'danger': '#e74c3c',
        'info': '#9b59b6',
        'secondary': '#95a5a6'
    }
    
    @staticmethod
    def create_performance_matrix(vendor_metrics: pd.DataFrame, top_n: int = 10) -> go.Figure:
        """
        Create scatter plot matrix showing vendor performance
        
        Args:
            vendor_metrics: DataFrame with vendor metrics
            top_n: Number of top vendors to show
            
        Returns:
            Plotly figure
        """
        if vendor_metrics.empty:
            return go.Figure()
        
        # Get top vendors by performance score
        top_vendors = vendor_metrics.nlargest(top_n, 'performance_score')
        
        fig = px.scatter(
            top_vendors,
            x='on_time_rate',
            y='completion_rate',
            size='total_po_value',
            color='performance_score',
            text='vendor_name',
            hover_data=['total_pos', 'vendor_type', 'vendor_location_type', 'total_po_value'],
            labels={
                'on_time_rate': 'On-Time Delivery Rate (%)',
                'completion_rate': 'PO Completion Rate (%)',
                'performance_score': 'Performance Score'
            },
            title="Vendor Performance Matrix (Size = PO Value)",
            color_continuous_scale='RdYlGn',
            size_max=50
        )
        
        # Update text position
        fig.update_traces(
            textposition='top center',
            textfont_size=8
        )
        
        # Add quadrant lines
        fig.add_hline(y=80, line_dash="dash", line_color="gray", opacity=0.5)
        fig.add_vline(x=80, line_dash="dash", line_color="gray", opacity=0.5)
        
        # Add quadrant labels
        fig.add_annotation(x=95, y=95, text="⭐ Top Performers", showarrow=False, font=dict(size=10))
        fig.add_annotation(x=95, y=50, text="⚡ Fast but Incomplete", showarrow=False, font=dict(size=10))
        fig.add_annotation(x=50, y=95, text="🎯 Complete but Slow", showarrow=False, font=dict(size=10))
        fig.add_annotation(x=50, y=50, text="⚠️ Need Improvement", showarrow=False, font=dict(size=10))
        
        ChartFactory._apply_standard_layout(fig)
        return fig
    
    @staticmethod
    def create_vendor_distribution(vendor_metrics: pd.DataFrame) -> go.Figure:
        """
        Create sunburst chart showing vendor distribution by type and location
        
        Args:
            vendor_metrics: DataFrame with vendor metrics
            
        Returns:
            Plotly figure
        """
        if vendor_metrics.empty:
            return go.Figure()
        
        # Aggregate by type and location
        vendor_dist = vendor_metrics.groupby(['vendor_type', 'vendor_location_type']).agg({
            'vendor_name': 'count',
            'total_po_value': 'sum'
        }).reset_index()
        
        fig = px.sunburst(
            vendor_dist,
            path=['vendor_type', 'vendor_location_type'],
            values='total_po_value',
            title='Vendor Distribution by Type and Location (Value)',
            color='total_po_value',
            color_continuous_scale='Blues'
        )
        
        ChartFactory._apply_standard_layout(fig)
        return fig
    
    @staticmethod
    def create_trend_chart(
        time_series_df: pd.DataFrame,
        metrics: List[str],
        chart_type: str = 'line'
    ) -> go.Figure:
        """
        Create time series trend chart
        
        Args:
            time_series_df: DataFrame with time series data
            metrics: List of metric column names to plot
            chart_type: 'line' or 'bar'
            
        Returns:
            Plotly figure
        """
        if time_series_df.empty:
            return go.Figure()
        
        fig = go.Figure()
        
        colors = [ChartFactory.COLORS['primary'], ChartFactory.COLORS['success'], 
                  ChartFactory.COLORS['warning'], ChartFactory.COLORS['danger']]
        
        for idx, metric in enumerate(metrics):
            if metric not in time_series_df.columns:
                continue
            
            color = colors[idx % len(colors)]
            
            if chart_type == 'line':
                fig.add_trace(go.Scatter(
                    x=time_series_df['Period'],
                    y=time_series_df[metric],
                    mode='lines+markers',
                    name=metric,
                    line=dict(color=color, width=3),
                    marker=dict(size=8)
                ))
            else:  # bar
                fig.add_trace(go.Bar(
                    x=time_series_df['Period'],
                    y=time_series_df[metric],
                    name=metric,
                    marker_color=color
                ))
        
        fig.update_layout(
            title="Trend Analysis",
            xaxis_title="Period",
            yaxis_title="Value",
            hovermode='x unified'
        )
        
        ChartFactory._apply_standard_layout(fig)
        return fig
    
    @staticmethod
    def create_comparison_bar(
        data: pd.DataFrame,
        x_col: str,
        y_col: str,
        color_col: Optional[str] = None,
        orientation: str = 'h',
        title: str = "Comparison Chart"
    ) -> go.Figure:
        """
        Create horizontal or vertical bar chart for comparisons
        
        Args:
            data: DataFrame with data
            x_col: Column for x-axis
            y_col: Column for y-axis
            color_col: Column for color coding
            orientation: 'h' for horizontal, 'v' for vertical
            title: Chart title
            
        Returns:
            Plotly figure
        """
        if data.empty:
            return go.Figure()
        
        fig = px.bar(
            data,
            x=x_col if orientation == 'v' else y_col,
            y=y_col if orientation == 'v' else x_col,
            color=color_col,
            orientation=orientation,
            title=title,
            color_continuous_scale='Blues' if color_col else None
        )
        
        # Add text on bars
        fig.update_traces(
            texttemplate='%{value:,.0f}' if orientation == 'h' else '%{y:,.0f}',
            textposition='inside'
        )
        
        ChartFactory._apply_standard_layout(fig)
        return fig
    
    @staticmethod
    def create_performance_trends(vendor_data: pd.DataFrame, vendor_name: str) -> go.Figure:
        """
        Create multi-panel chart showing various performance trends
        
        Args:
            vendor_data: Monthly vendor performance data
            vendor_name: Name of vendor
            
        Returns:
            Plotly figure with subplots
        """
        if vendor_data.empty:
            return go.Figure()
        
        fig = make_subplots(
            rows=2, cols=2,
            subplot_titles=('On-Time Delivery Rate', 'Average Lead Time',
                          'Over-Delivery Trend', 'Monthly Value'),
            specs=[[{}, {}], [{}, {}]]
        )
        
        # On-time rate
        if 'on_time_rate' in vendor_data.columns:
            fig.add_trace(
                go.Scatter(
                    x=vendor_data['month'], 
                    y=vendor_data['on_time_rate'],
                    mode='lines+markers', 
                    name='On-Time Rate',
                    line=dict(color=ChartFactory.COLORS['success'], width=3)
                ),
                row=1, col=1
            )
            fig.add_hline(y=80, line_dash="dash", line_color="red", opacity=0.5, row=1, col=1)
        
        # Lead time
        if 'avg_lead_time' in vendor_data.columns:
            fig.add_trace(
                go.Scatter(
                    x=vendor_data['month'], 
                    y=vendor_data['avg_lead_time'],
                    mode='lines+markers', 
                    name='Lead Time (days)',
                    line=dict(color=ChartFactory.COLORS['primary'], width=3)
                ),
                row=1, col=2
            )
        
        # Over-deliveries
        if 'over_deliveries' in vendor_data.columns:
            fig.add_trace(
                go.Bar(
                    x=vendor_data['month'], 
                    y=vendor_data['over_deliveries'],
                    name='Over-Deliveries', 
                    marker_color=ChartFactory.COLORS['danger']
                ),
                row=2, col=1
            )
        
        # Monthly value
        if 'total_value' in vendor_data.columns:
            fig.add_trace(
                go.Bar(
                    x=vendor_data['month'], 
                    y=vendor_data['total_value'],
                    name='Monthly Value', 
                    marker_color=ChartFactory.COLORS['info']
                ),
                row=2, col=2
            )
        
        fig.update_layout(
            height=700, 
            showlegend=False,
            title_text=f"Performance Trends - {vendor_name}"
        )
        
        return fig
    
    @staticmethod
    def create_distribution_histogram(
        data: pd.DataFrame,
        column: str,
        bins: int = 20,
        title: str = "Distribution"
    ) -> go.Figure:
        """
        Create histogram showing data distribution
        
        Args:
            data: DataFrame with data
            column: Column to plot
            bins: Number of bins
            title: Chart title
            
        Returns:
            Plotly figure
        """
        if data.empty or column not in data.columns:
            return go.Figure()
        
        fig = px.histogram(
            data,
            x=column,
            nbins=bins,
            title=title,
            labels={column: column.replace('_', ' ').title()},
            color_discrete_sequence=[ChartFactory.COLORS['primary']]
        )
        
        ChartFactory._apply_standard_layout(fig)
        return fig
    
    @staticmethod
    def create_box_plot(
        data: pd.DataFrame,
        x_col: str,
        y_col: str,
        color_col: Optional[str] = None,
        title: str = "Distribution Analysis"
    ) -> go.Figure:
        """
        Create box plot for distribution analysis
        
        Args:
            data: DataFrame with data
            x_col: Column for x-axis (categories)
            y_col: Column for y-axis (values)
            color_col: Column for color coding
            title: Chart title
            
        Returns:
            Plotly figure
        """
        if data.empty:
            return go.Figure()
        
        fig = px.box(
            data,
            x=x_col,
            y=y_col,
            color=color_col,
            title=title
        )
        
        ChartFactory._apply_standard_layout(fig)
        return fig
    
    @staticmethod
    def create_treemap(
        data: pd.DataFrame,
        path_columns: List[str],
        value_column: str,
        color_column: Optional[str] = None,
        title: str = "Hierarchical View"
    ) -> go.Figure:
        """
        Create treemap for hierarchical data
        
        Args:
            data: DataFrame with data
            path_columns: List of columns defining hierarchy
            value_column: Column for size
            color_column: Column for color
            title: Chart title
            
        Returns:
            Plotly figure
        """
        if data.empty:
            return go.Figure()
        
        fig = px.treemap(
            data,
            path=path_columns,
            values=value_column,
            color=color_column,
            title=title,
            color_continuous_scale='Viridis'
        )
        
        ChartFactory._apply_standard_layout(fig)
        return fig
    
    @staticmethod
    def _apply_standard_layout(fig: go.Figure) -> None:
        """
        Apply standard layout styling to figure
        
        Args:
            fig: Plotly figure to style
        """
        fig.update_layout(
            font=dict(family="Arial, sans-serif", size=12),
            plot_bgcolor='white',
            paper_bgcolor='white',
            margin=dict(l=50, r=50, t=80, b=50),
            hovermode='closest',
            # Add config to remove warnings
            modebar={'orientation': 'v'}
        )
        
        fig.update_xaxes(showgrid=True, gridwidth=1, gridcolor='LightGray')
        fig.update_yaxes(showgrid=True, gridwidth=1, gridcolor='LightGray')