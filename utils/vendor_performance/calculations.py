"""
Simplified Calculation Logic for Vendor Performance

Focused on key business metrics:
- Order Entry vs Invoiced
- Conversion Rate
- Pending Delivery
- Trends
"""

import pandas as pd
import numpy as np
from typing import Dict, Any, List
import logging

from .exceptions import CalculationError, ValidationError
from .constants import format_currency, format_percentage, CONVERSION_THRESHOLDS

logger = logging.getLogger(__name__)


class PerformanceCalculator:
    """Simplified calculator for vendor performance metrics"""
    
    @staticmethod
    def calculate_conversion_rate(
        invoiced_value: float,
        order_value: float
    ) -> float:
        """
        Calculate conversion rate (Invoiced / Order * 100)
        
        Args:
            invoiced_value: Total invoiced amount
            order_value: Total order entry amount
            
        Returns:
            Conversion rate percentage
        """
        if pd.isna(order_value) or order_value == 0:
            return 0.0
        
        rate = (invoiced_value / order_value * 100)
        return round(rate, 1)
    
    @staticmethod
    def calculate_pending_delivery(
        order_value: float,
        invoiced_value: float
    ) -> float:
        """
        Calculate pending delivery value
        
        Args:
            order_value: Total order value
            invoiced_value: Total invoiced value
            
        Returns:
            Pending delivery amount
        """
        pending = order_value - invoiced_value
        return max(0, round(pending, 2))
    
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
            period_type: 'monthly', 'quarterly', 'yearly'
            date_column: Date column name
            
        Returns:
            Aggregated DataFrame
            
        Raises:
            CalculationError: If aggregation fails
        """
        if po_df.empty:
            return pd.DataFrame()
        
        try:
            df = po_df.copy()
            
            # Ensure date column is datetime
            if date_column not in df.columns:
                raise ValidationError(f"Column {date_column} not found in DataFrame")
            
            df[date_column] = pd.to_datetime(df[date_column])
            
            # Create period column
            period_map = {
                'monthly': 'M',
                'quarterly': 'Q',
                'yearly': 'Y'
            }
            
            period_code = period_map.get(period_type.lower(), 'M')
            df['period'] = df[date_column].dt.to_period(period_code).dt.start_time
            
            # Aggregate
            aggregated = df.groupby(['period', 'vendor_name']).agg({
                'po_number': 'nunique',
                'total_order_value_usd': 'sum',
                'invoiced_amount_usd': 'sum',
                'pending_delivery_usd': 'sum',
                'po_line_id': 'count',
                'product_name': 'nunique'
            }).reset_index()
            
            # Rename columns
            aggregated.columns = [
                'Period', 'Vendor', 'PO Count', 'Order Value', 
                'Invoiced Value', 'Pending Delivery',
                'Line Items', 'Products'
            ]
            
            # Calculate conversion rate
            aggregated['Conversion Rate'] = aggregated.apply(
                lambda row: PerformanceCalculator.calculate_conversion_rate(
                    row['Invoiced Value'], 
                    row['Order Value']
                ),
                axis=1
            )
            
            logger.info(f"Aggregated {len(df)} records into {len(aggregated)} periods")
            return aggregated
            
        except Exception as e:
            logger.error(f"Error aggregating by period: {e}", exc_info=True)
            raise CalculationError("Failed to aggregate data by period", {'error': str(e)})
    
    @staticmethod
    def calculate_growth_metrics(
        current_value: float,
        previous_value: float
    ) -> Dict[str, Any]:
        """
        Calculate growth metrics
        
        Args:
            current_value: Current period value
            previous_value: Previous period value
            
        Returns:
            Dictionary with growth metrics
        """
        if previous_value == 0 or pd.isna(previous_value):
            growth_rate = 0 if current_value == 0 else 100
        else:
            growth_rate = ((current_value - previous_value) / previous_value * 100)
        
        return {
            'current': round(current_value, 2),
            'previous': round(previous_value, 2),
            'growth_rate': round(growth_rate, 1),
            'growth_amount': round(current_value - previous_value, 2)
        }
    
    @staticmethod
    def calculate_vendor_comparison(
        vendor_df: pd.DataFrame,
        all_vendors_df: pd.DataFrame
    ) -> Dict[str, Any]:
        """
        Calculate vendor comparison vs overall average
        
        Args:
            vendor_df: Single vendor data
            all_vendors_df: All vendors data
            
        Returns:
            Comparison metrics
        """
        if vendor_df.empty or all_vendors_df.empty:
            return {}
        
        vendor_metrics = {
            'order_value': vendor_df['total_order_value'].sum(),
            'invoiced_value': vendor_df['total_invoiced_value'].sum(),
            'conversion_rate': PerformanceCalculator.calculate_conversion_rate(
                vendor_df['total_invoiced_value'].sum(),
                vendor_df['total_order_value'].sum()
            ),
            'po_count': vendor_df['total_pos'].sum()
        }
        
        avg_metrics = {
            'avg_order_value': all_vendors_df['total_order_value'].mean(),
            'avg_conversion_rate': all_vendors_df['conversion_rate'].mean(),
            'avg_po_count': all_vendors_df['total_pos'].mean()
        }
        
        return {
            'vendor': vendor_metrics,
            'average': avg_metrics,
            'vs_average': {
                'conversion_diff': round(
                    vendor_metrics['conversion_rate'] - avg_metrics['avg_conversion_rate'], 
                    1
                ),
                'value_diff_pct': round(
                    (vendor_metrics['order_value'] / avg_metrics['avg_order_value'] - 1) * 100,
                    1
                ) if avg_metrics['avg_order_value'] > 0 else 0
            }
        }
    
    @staticmethod
    def identify_alerts(vendor_summary: pd.Series) -> List[Dict[str, Any]]:
        """
        Identify performance alerts
        
        Args:
            vendor_summary: Vendor summary data
            
        Returns:
            List of alerts
        """
        alerts = []
        
        # Low conversion rate
        conversion_rate = vendor_summary.get('conversion_rate', 0)
        if conversion_rate < CONVERSION_THRESHOLDS['fair']:
            alerts.append({
                'type': 'low_conversion',
                'severity': 'warning',
                'message': f'Conversion rate {conversion_rate:.1f}% below target ({CONVERSION_THRESHOLDS["fair"]}%)',
                'value': conversion_rate
            })
        
        # High pending delivery
        pending = vendor_summary.get('pending_delivery_value', 0)
        if pending > 100000:  # > $100K
            alerts.append({
                'type': 'high_pending',
                'severity': 'warning',
                'message': f'High pending delivery: {format_currency(pending)}',
                'value': pending
            })
        
        # No recent orders (if last_po_date available)
        if 'last_po_date' in vendor_summary:
            last_po = pd.to_datetime(vendor_summary['last_po_date'])
            days_since = (pd.Timestamp.now() - last_po).days
            if days_since > 90:
                alerts.append({
                    'type': 'inactive',
                    'severity': 'info',
                    'message': f'No orders in last {days_since} days',
                    'value': days_since
                })
        
        return alerts
    
    @staticmethod
    def calculate_cumulative(df: pd.DataFrame, value_column: str) -> pd.DataFrame:
        """
        Calculate cumulative sum for time series
        
        Args:
            df: DataFrame with period data
            value_column: Column to accumulate
            
        Returns:
            DataFrame with cumulative column added
        """
        if df.empty or value_column not in df.columns:
            return df
        
        df = df.sort_values('Period')
        df[f'{value_column}_cumulative'] = df[value_column].cumsum()
        
        return df
    
    @staticmethod
    def format_summary_stats(vendor_summary: pd.Series) -> Dict[str, str]:
        """
        Format summary statistics for display
        
        Args:
            vendor_summary: Vendor summary data
            
        Returns:
            Formatted statistics
        """
        return {
            'Total Order Value': format_currency(vendor_summary.get('total_order_value', 0)),
            'Invoiced Value': format_currency(vendor_summary.get('total_invoiced_value', 0)),
            'Pending Delivery': format_currency(vendor_summary.get('pending_delivery_value', 0)),
            'Conversion Rate': format_percentage(vendor_summary.get('conversion_rate', 0)),
            'Total POs': f"{vendor_summary.get('total_pos', 0):,}",
            'Avg PO Value': format_currency(vendor_summary.get('avg_po_value', 0))
        }