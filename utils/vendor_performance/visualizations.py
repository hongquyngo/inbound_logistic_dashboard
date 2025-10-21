"""
Visualization Factory for Vendor Performance - Updated

Standardized charts for order, invoice, and product analysis
"""

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
from typing import Optional, List
import logging

from .constants import COLORS, CHART_HEIGHTS, format_currency

logger = logging.getLogger(__name__)


class ChartFactory:
    """Factory for creating standardized charts"""
    
    @staticmethod
    def create_financial_trend_chart(
        period_data: pd.DataFrame,
        show_cumulative: bool = False
    ) -> go.Figure:
        """
        Create Order Entry vs Invoiced trend chart
        
        Args:
            period_data: Period aggregated data
            show_cumulative: Show cumulative values
            
        Returns:
            Plotly figure
        """
        if period_data.empty:
            return ChartFactory._create_empty_figure("No data available")
        
        df = period_data.copy()
        df = df.sort_values('Period')
        
        if show_cumulative:
            # Cumulative chart
            df['Cumulative Order'] = df['Order Value'].cumsum()
            df['Cumulative Invoiced'] = df['Invoiced Value'].cumsum()
            
            fig = go.Figure()
            
            fig.add_trace(go.Scatter(
                x=df['Period'],
                y=df['Cumulative Order'],
                mode='lines+markers',
                name='Cumulative Order Entry',
                line=dict(color=COLORS['primary'], width=3),
                fill='tozeroy',
                fillcolor='rgba(52, 152, 219, 0.1)'
            ))
            
            fig.add_trace(go.Scatter(
                x=df['Period'],
                y=df['Cumulative Invoiced'],
                mode='lines+markers',
                name='Cumulative Invoiced',
                line=dict(color=COLORS['success'], width=3),
                fill='tozeroy',
                fillcolor='rgba(46, 204, 113, 0.1)'
            ))
            
            title = "Cumulative Financial Performance"
            
        else:
            # Periodic chart (dual axis)
            fig = make_subplots(specs=[[{"secondary_y": True}]])
            
            # Order Entry bars
            fig.add_trace(
                go.Bar(
                    x=df['Period'],
                    y=df['Order Value'],
                    name='Order Entry',
                    marker_color=COLORS['primary'],
                    opacity=0.7,
                    hovertemplate='<b>Order Entry</b><br>%{y:$,.0f}<extra></extra>'
                ),
                secondary_y=False
            )
            
            # Invoiced Value bars
            fig.add_trace(
                go.Bar(
                    x=df['Period'],
                    y=df['Invoiced Value'],
                    name='Invoiced Value',
                    marker_color=COLORS['success'],
                    opacity=0.7,
                    hovertemplate='<b>Invoiced</b><br>%{y:$,.0f}<extra></extra>'
                ),
                secondary_y=False
            )
            
            # Conversion Rate line (if exists)
            if 'Conversion Rate' in df.columns:
                fig.add_trace(
                    go.Scatter(
                        x=df['Period'],
                        y=df['Conversion Rate'],
                        name='Conversion Rate %',
                        line=dict(color=COLORS['danger'], width=3, dash='dash'),
                        yaxis='y2',
                        hovertemplate='<b>Conversion</b><br>%{y:.1f}%<extra></extra>'
                    ),
                    secondary_y=True
                )
                
                # Add target line for conversion rate
                fig.add_hline(
                    y=90, 
                    line_dash="dot", 
                    line_color="gray",
                    annotation_text="Target: 90%",
                    secondary_y=True
                )
            
            fig.update_yaxes(title_text="Value (USD)", secondary_y=False)
            fig.update_yaxes(title_text="Conversion Rate (%)", secondary_y=True, range=[0, 110])
            
            title = "Order Entry vs Invoiced Trend"
        
        fig.update_layout(
            title=title,
            xaxis_title="Period",
            hovermode='x unified',
            height=CHART_HEIGHTS['standard'],
            legend=dict(
                orientation="h",
                yanchor="bottom",
                y=1.02,
                xanchor="right",
                x=1
            )
        )
        
        ChartFactory._apply_standard_layout(fig)
        return fig
    
    @staticmethod
    def create_product_treemap(
        product_data: pd.DataFrame,
        top_n: int = 15
    ) -> go.Figure:
        """
        Create treemap showing product mix by value
        
        Args:
            product_data: Product summary data
            top_n: Number of top products to show
            
        Returns:
            Plotly figure
        """
        if product_data.empty:
            return ChartFactory._create_empty_figure("No product data")
        
        # Get top products
        top_products = product_data.nlargest(top_n, 'total_order_value').copy()
        
        # Calculate percentage
        total = top_products['total_order_value'].sum()
        top_products['pct'] = (top_products['total_order_value'] / total * 100).round(1)
        
        # Create labels with value and percentage
        top_products['label'] = top_products.apply(
            lambda row: f"{row['product_name']}<br>{format_currency(row['total_order_value'])}<br>{row['pct']:.1f}%",
            axis=1
        )
        
        fig = px.treemap(
            top_products,
            path=['brand', 'product_name'],
            values='total_order_value',
            color='conversion_rate',
            color_continuous_scale='RdYlGn',
            color_continuous_midpoint=85,
            title=f"Top {top_n} Products by Order Value",
            hover_data={
                'total_order_value': ':,.0f',
                'total_invoiced_value': ':,.0f',
                'conversion_rate': ':.1f'
            }
        )
        
        fig.update_traces(
            textposition='middle center',
            textfont_size=11
        )
        
        fig.update_layout(height=CHART_HEIGHTS['large'])
        ChartFactory._apply_standard_layout(fig)
        
        return fig
    
    @staticmethod
    def create_vendor_comparison_chart(
        vendor_summary: pd.DataFrame,
        top_n: int = 10,
        metric: str = 'total_order_value'
    ) -> go.Figure:
        """
        Create horizontal bar chart comparing vendors
        
        Args:
            vendor_summary: Vendor summary data
            top_n: Number of vendors to show
            metric: Metric to compare
            
        Returns:
            Plotly figure
        """
        if vendor_summary.empty:
            return ChartFactory._create_empty_figure("No vendor data")
        
        # Get top vendors
        top_vendors = vendor_summary.nlargest(top_n, metric).copy()
        top_vendors = top_vendors.sort_values(metric)  # Sort for horizontal bar
        
        # Determine vendor name column
        vendor_col = 'vendor_name' if 'vendor_name' in top_vendors.columns else 'vendor'
        
        # Color by conversion rate if available
        if 'conversion_rate' in top_vendors.columns:
            color_col = 'conversion_rate'
            color_range = [0, 100]
        else:
            color_col = None
            color_range = None
        
        fig = go.Figure()
        
        fig.add_trace(go.Bar(
            x=top_vendors[metric],
            y=top_vendors[vendor_col],
            orientation='h',
            marker=dict(
                color=top_vendors[color_col] if color_col else COLORS['primary'],
                colorscale='RdYlGn' if color_col else None,
                colorbar=dict(title="Conv %") if color_col else None,
                cmin=color_range[0] if color_range else None,
                cmax=color_range[1] if color_range else None
            ),
            text=top_vendors[metric].apply(lambda x: format_currency(x)),
            textposition='inside',
            hovertemplate='<b>%{y}</b><br>Value: %{x:,.0f}<extra></extra>'
        ))
        
        metric_titles = {
            'total_order_value': 'Order Value',
            'total_invoiced_value': 'Invoiced Value',
            'outstanding_value': 'Outstanding'
        }
        
        fig.update_layout(
            title=f"Top {top_n} Vendors by {metric_titles.get(metric, metric)}",
            xaxis_title="Value (USD)",
            yaxis_title="",
            height=CHART_HEIGHTS['standard'],
            showlegend=False
        )
        
        ChartFactory._apply_standard_layout(fig)
        return fig
    
    @staticmethod
    def create_conversion_gauge(conversion_rate: float) -> go.Figure:
        """
        Create gauge chart for conversion rate
        
        Args:
            conversion_rate: Conversion rate percentage
            
        Returns:
            Plotly figure
        """
        fig = go.Figure(go.Indicator(
            mode="gauge+number+delta",
            value=conversion_rate,
            delta={'reference': 90, 'position': "top"},
            title={'text': "Conversion Rate"},
            domain={'x': [0, 1], 'y': [0, 1]},
            gauge={
                'axis': {'range': [None, 100], 'tickwidth': 1},
                'bar': {'color': ChartFactory._get_gauge_color(conversion_rate)},
                'steps': [
                    {'range': [0, 80], 'color': "rgba(231, 76, 60, 0.1)"},
                    {'range': [80, 90], 'color': "rgba(243, 156, 18, 0.1)"},
                    {'range': [90, 100], 'color': "rgba(46, 204, 113, 0.1)"}
                ],
                'threshold': {
                    'line': {'color': "black", 'width': 2},
                    'thickness': 0.75,
                    'value': 90
                }
            }
        ))
        
        fig.update_layout(
            height=CHART_HEIGHTS['compact'],
            margin=dict(l=20, r=20, t=40, b=20)
        )
        
        return fig
    
    @staticmethod
    def create_period_comparison_bars(
        current_data: pd.DataFrame,
        previous_data: pd.DataFrame
    ) -> go.Figure:
        """
        Create grouped bar chart comparing current vs previous period
        
        Args:
            current_data: Current period aggregated data
            previous_data: Previous period aggregated data
            
        Returns:
            Plotly figure
        """
        if current_data.empty:
            return ChartFactory._create_empty_figure("No data for comparison")
        
        # Aggregate totals
        current_total = current_data['Order Value'].sum()
        current_invoiced = current_data['Invoiced Value'].sum()
        
        if not previous_data.empty:
            previous_total = previous_data['Order Value'].sum()
            previous_invoiced = previous_data['Invoiced Value'].sum()
        else:
            previous_total = 0
            previous_invoiced = 0
        
        fig = go.Figure()
        
        categories = ['Order Entry', 'Invoiced Value']
        
        fig.add_trace(go.Bar(
            name='Previous Period',
            x=categories,
            y=[previous_total, previous_invoiced],
            marker_color=COLORS['secondary'],
            text=[format_currency(previous_total), format_currency(previous_invoiced)],
            textposition='outside'
        ))
        
        fig.add_trace(go.Bar(
            name='Current Period',
            x=categories,
            y=[current_total, current_invoiced],
            marker_color=COLORS['primary'],
            text=[format_currency(current_total), format_currency(current_invoiced)],
            textposition='outside'
        ))
        
        fig.update_layout(
            title="Period-over-Period Comparison",
            yaxis_title="Value (USD)",
            barmode='group',
            height=CHART_HEIGHTS['compact']
        )
        
        ChartFactory._apply_standard_layout(fig)
        return fig
    
    @staticmethod
    def _create_empty_figure(message: str) -> go.Figure:
        """Create empty figure with message"""
        fig = go.Figure()
        fig.add_annotation(
            text=message,
            xref="paper", yref="paper",
            x=0.5, y=0.5,
            showarrow=False,
            font=dict(size=16, color="gray")
        )
        fig.update_layout(
            xaxis=dict(visible=False),
            yaxis=dict(visible=False),
            height=CHART_HEIGHTS['standard']
        )
        return fig
    
    @staticmethod
    def _get_gauge_color(value: float) -> str:
        """Get color for gauge based on value"""
        if value >= 90:
            return COLORS['success']
        elif value >= 80:
            return COLORS['warning']
        else:
            return COLORS['danger']
    
    @staticmethod
    def _apply_standard_layout(fig: go.Figure) -> None:
        """Apply standard layout styling"""
        fig.update_layout(
            font=dict(family="Arial, sans-serif", size=12),
            plot_bgcolor='white',
            paper_bgcolor='white',
            margin=dict(l=50, r=50, t=80, b=50),
            hovermode='closest'
        )
        
        fig.update_xaxes(
            showgrid=True,
            gridwidth=1,
            gridcolor='rgba(0, 0, 0, 0.1)'
        )
        fig.update_yaxes(
            showgrid=True,
            gridwidth=1,
            gridcolor='rgba(0, 0, 0, 0.1)'
        )