"""
Calculation and Business Logic for Vendor Performance

Handles all performance calculations, aggregations, and business rules.
"""

import pandas as pd
import numpy as np
from typing import Tuple, Dict, Any
import logging

logger = logging.getLogger(__name__)


class PerformanceCalculator:
    """Calculator for vendor performance metrics and business logic"""
    
    @staticmethod
    def calculate_performance_score(vendor_metrics: pd.DataFrame) -> pd.DataFrame:
        """
        Calculate weighted performance score for vendors
        
        Weights:
        - On-time delivery: 40%
        - Completion rate: 30%
        - No over-delivery penalty: 20%
        - Payment progress: 10%
        
        Args:
            vendor_metrics: DataFrame with vendor metrics
            
        Returns:
            DataFrame with added performance_score column
        """
        if vendor_metrics.empty:
            return vendor_metrics
        
        df = vendor_metrics.copy()
        
        # Ensure required columns exist
        required_cols = ['on_time_rate', 'completion_rate', 'over_delivery_rate', 'avg_payment_progress']
        for col in required_cols:
            if col not in df.columns:
                df[col] = 0
        
        # Calculate weighted score
        df['performance_score'] = (
            df['on_time_rate'] * 0.4 +                          # 40% weight
            df['completion_rate'] * 0.3 +                       # 30% weight
            (100 - df['over_delivery_rate'].clip(upper=100)) * 0.2 +  # 20% weight
            df['avg_payment_progress'].fillna(0).clip(upper=100) * 0.1    # 10% weight
        ).round(1)
        
        logger.info(f"Calculated performance scores for {len(df)} vendors")
        return df
    
    @staticmethod
    def assign_performance_tier(score: float) -> str:
        """
        Categorize vendor performance based on score
        
        Tiers:
        - Excellent: >= 90
        - Good: >= 75
        - Fair: >= 60
        - Poor: < 60
        
        Args:
            score: Performance score (0-100)
            
        Returns:
            Performance tier label
        """
        if score >= 90:
            return "⭐ Excellent"
        elif score >= 75:
            return "✅ Good"
        elif score >= 60:
            return "⚠️ Fair"
        else:
            return "❌ Poor"
    
    @staticmethod
    def calculate_on_time_rate(po_df: pd.DataFrame) -> float:
        """
        Calculate on-time delivery rate
        
        Args:
            po_df: DataFrame with PO data
            
        Returns:
            On-time rate percentage
        """
        if po_df.empty:
            return 0.0
        
        completed = po_df[po_df['status'] == 'COMPLETED']
        if len(completed) == 0:
            return 0.0
        
        on_time = completed[
            (pd.to_datetime(completed['eta']) >= pd.to_datetime(completed['etd']))
        ]
        
        rate = (len(on_time) / len(completed) * 100).round(1)
        return rate
    
    @staticmethod
    def calculate_completion_rate(po_df: pd.DataFrame) -> float:
        """
        Calculate PO completion rate
        
        Args:
            po_df: DataFrame with PO data
            
        Returns:
            Completion rate percentage
        """
        if po_df.empty:
            return 0.0
        
        total_pos = po_df['po_number'].nunique()
        if total_pos == 0:
            return 0.0
        
        completed_pos = po_df[po_df['status'] == 'COMPLETED']['po_number'].nunique()
        
        rate = (completed_pos / total_pos * 100).round(1)
        return rate
    
    @staticmethod
    def calculate_growth_metrics(
        current_df: pd.DataFrame,
        previous_df: pd.DataFrame
    ) -> Dict[str, float]:
        """
        Calculate period-over-period growth metrics
        
        Args:
            current_df: Current period data
            previous_df: Previous period data
            
        Returns:
            Dictionary with growth metrics
        """
        current_value = current_df['total_amount_usd'].sum() if not current_df.empty else 0
        previous_value = previous_df['total_amount_usd'].sum() if not previous_df.empty else 0
        
        current_pos = current_df['po_number'].nunique() if not current_df.empty else 0
        previous_pos = previous_df['po_number'].nunique() if not previous_df.empty else 0
        
        # Calculate growth rates
        value_growth = (
            ((current_value - previous_value) / previous_value * 100) 
            if previous_value > 0 else 0
        )
        
        po_growth = (
            ((current_pos - previous_pos) / previous_pos * 100) 
            if previous_pos > 0 else 0
        )
        
        return {
            'current_value': current_value,
            'previous_value': previous_value,
            'value_growth': round(value_growth, 1),
            'current_pos': current_pos,
            'previous_pos': previous_pos,
            'po_growth': round(po_growth, 1)
        }
    
    @staticmethod
    def aggregate_by_period(
        po_df: pd.DataFrame,
        period_type: str = 'monthly',
        date_column: str = 'po_date'
    ) -> pd.DataFrame:
        """
        Aggregate PO data by time period
        
        Args:
            po_df: DataFrame with PO data
            period_type: 'daily', 'weekly', 'monthly', 'quarterly', 'yearly'
            date_column: Name of date column to use
            
        Returns:
            Aggregated DataFrame by period
        """
        if po_df.empty:
            return pd.DataFrame()
        
        df = po_df.copy()
        df[date_column] = pd.to_datetime(df[date_column])
        
        # Create period column
        if period_type == 'daily':
            df['period'] = df[date_column].dt.date
        elif period_type == 'weekly':
            df['period'] = df[date_column].dt.to_period('W').dt.start_time
        elif period_type == 'monthly':
            df['period'] = df[date_column].dt.to_period('M').dt.start_time
        elif period_type == 'quarterly':
            df['period'] = df[date_column].dt.to_period('Q').dt.start_time
        elif period_type == 'yearly':
            df['period'] = df[date_column].dt.to_period('Y').dt.start_time
        else:
            df['period'] = df[date_column].dt.to_period('M').dt.start_time
        
        # Aggregate by period
        aggregated = df.groupby(['period', 'vendor_name']).agg({
            'po_number': 'nunique',
            'total_amount_usd': 'sum',
            'po_line_id': 'count',
            'brand': lambda x: x.nunique() if pd.api.types.is_object_dtype(x) else 0,
            'product_name': 'nunique'
        }).reset_index()
        
        aggregated.columns = [
            'Period', 'Vendor', 'PO Count', 'Total Value', 
            'Line Items', 'Brands', 'Products'
        ]
        
        logger.info(f"Aggregated {len(df)} records into {len(aggregated)} periods")
        return aggregated
    
    @staticmethod
    def format_currency(value: float, currency: str = 'USD') -> str:
        """
        Format currency value consistently
        
        Args:
            value: Numeric value
            currency: Currency code
            
        Returns:
            Formatted string
        """
        if pd.isna(value):
            return "$0"
        
        if abs(value) >= 1_000_000:
            return f"${value/1_000_000:.1f}M"
        elif abs(value) >= 1_000:
            return f"${value/1_000:.1f}K"
        else:
            return f"${value:.0f}"
    
    @staticmethod
    def format_percentage(value: float) -> str:
        """
        Format percentage value
        
        Args:
            value: Percentage value (0-100)
            
        Returns:
            Formatted string
        """
        if pd.isna(value):
            return "0.0%"
        return f"{value:.1f}%"
    
    @staticmethod
    def get_performance_color(score: float) -> str:
        """
        Get color code for performance score
        
        Args:
            score: Performance score (0-100)
            
        Returns:
            Hex color code
        """
        if score >= 90:
            return "#2ecc71"  # Green - Excellent
        elif score >= 75:
            return "#3498db"  # Blue - Good
        elif score >= 60:
            return "#f39c12"  # Orange - Fair
        else:
            return "#e74c3c"  # Red - Poor
    
    @staticmethod
    def calculate_vendor_summary(vendor_metrics: pd.DataFrame) -> Dict[str, Any]:
        """
        Calculate summary statistics for all vendors
        
        Args:
            vendor_metrics: DataFrame with vendor metrics
            
        Returns:
            Dictionary with summary statistics
        """
        if vendor_metrics.empty:
            return {}
        
        return {
            'total_vendors': len(vendor_metrics),
            'avg_on_time_rate': vendor_metrics['on_time_rate'].mean(),
            'avg_completion_rate': vendor_metrics['completion_rate'].mean(),
            'total_po_value': vendor_metrics['total_po_value'].sum(),
            'total_outstanding': vendor_metrics['outstanding_arrival_value'].sum(),
            'high_performers': len(vendor_metrics[vendor_metrics['performance_score'] >= 80]),
            'poor_performers': len(vendor_metrics[vendor_metrics['performance_score'] < 60])
        }