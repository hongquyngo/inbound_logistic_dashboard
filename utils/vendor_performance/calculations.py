"""
Calculation Logic for Vendor Performance - Updated

Focused on key business metrics with proper validation
"""

import pandas as pd
import numpy as np
from typing import Dict, Any, List, Optional
import logging

from .exceptions import CalculationError, ValidationError

logger = logging.getLogger(__name__)


class PerformanceCalculator:
    """Calculator for vendor performance metrics"""
    
    @staticmethod
    def calculate_conversion_rate(
        invoiced_value: float,
        order_value: float,
        max_rate: float = 110.0
    ) -> float:
        """
        Calculate conversion rate with validation
        
        Args:
            invoiced_value: Total invoiced amount (must be >= 0)
            order_value: Total order value (must be > 0)
            max_rate: Maximum allowed rate (default 110%)
            
        Returns:
            Conversion rate percentage (0-max_rate)
            
        Raises:
            ValidationError: If inputs are invalid
        """
        # Type validation
        try:
            invoiced_value = float(invoiced_value) if invoiced_value is not None else 0.0
            order_value = float(order_value) if order_value is not None else 0.0
        except (TypeError, ValueError) as e:
            raise ValidationError(f"Invalid numeric values: {e}")
        
        # Business logic validation
        if invoiced_value < 0:
            logger.warning(f"Negative invoiced value: {invoiced_value}")
            invoiced_value = 0
        
        if order_value < 0:
            logger.warning(f"Negative order value: {order_value}")
            order_value = 0
        
        # Calculate rate
        if pd.isna(order_value) or order_value == 0:
            return 0.0
        
        rate = (invoiced_value / order_value * 100)
        
        # Cap at maximum
        rate = min(rate, max_rate)
        
        return round(rate, 1)
    
    @staticmethod
    def calculate_payment_rate(
        paid_value: float,
        invoiced_value: float,
        max_rate: float = 100.0
    ) -> float:
        """
        Calculate payment rate
        
        Args:
            paid_value: Total paid amount
            invoiced_value: Total invoiced amount
            max_rate: Maximum allowed rate
            
        Returns:
            Payment rate percentage
        """
        try:
            paid_value = float(paid_value) if paid_value is not None else 0.0
            invoiced_value = float(invoiced_value) if invoiced_value is not None else 0.0
        except (TypeError, ValueError):
            return 0.0
        
        if paid_value < 0 or invoiced_value < 0:
            return 0.0
        
        if invoiced_value == 0:
            return 0.0
        
        rate = (paid_value / invoiced_value * 100)
        return round(min(rate, max_rate), 1)
    
    @staticmethod
    def aggregate_by_period(
        df: pd.DataFrame,
        period_type: str = 'monthly',
        date_column: str = 'po_date'
    ) -> pd.DataFrame:
        """
        Aggregate data by time period
        
        Args:
            df: DataFrame with data
            period_type: 'monthly', 'quarterly', 'yearly'
            date_column: Date column name
            
        Returns:
            Aggregated DataFrame
            
        Raises:
            CalculationError: If aggregation fails
        """
        if df.empty:
            return pd.DataFrame()
        
        try:
            work_df = df.copy()
            
            # Ensure date column exists and is datetime
            if date_column not in work_df.columns:
                raise ValidationError(f"Column {date_column} not found")
            
            work_df[date_column] = pd.to_datetime(work_df[date_column])
            
            # Create period column
            period_map = {
                'monthly': 'M',
                'quarterly': 'Q',
                'yearly': 'Y'
            }
            
            period_code = period_map.get(period_type.lower(), 'M')
            work_df['period'] = work_df[date_column].dt.to_period(period_code).dt.start_time
            
            # Determine grouping columns
            group_cols = ['period']
            if 'vendor_name' in work_df.columns:
                group_cols.append('vendor_name')
            
            # Aggregate with proper column selection
            agg_dict = {}
            
            if 'po_number' in work_df.columns:
                agg_dict['po_number'] = 'nunique'
            
            if 'total_order_value_usd' in work_df.columns:
                agg_dict['total_order_value_usd'] = 'sum'
            elif 'total_amount_usd' in work_df.columns:
                agg_dict['total_amount_usd'] = 'sum'
            
            if 'invoiced_amount_usd' in work_df.columns:
                agg_dict['invoiced_amount_usd'] = 'sum'
            
            if 'outstanding_invoiced_amount_usd' in work_df.columns:
                agg_dict['outstanding_invoiced_amount_usd'] = 'sum'
            
            if 'po_line_id' in work_df.columns:
                agg_dict['po_line_id'] = 'count'
            
            if 'product_name' in work_df.columns:
                agg_dict['product_name'] = 'nunique'
            
            aggregated = work_df.groupby(group_cols).agg(agg_dict).reset_index()
            
            # Rename columns to standard names
            column_rename = {
                'po_number': 'PO Count',
                'total_order_value_usd': 'Order Value',
                'total_amount_usd': 'Order Value',
                'invoiced_amount_usd': 'Invoiced Value',
                'outstanding_invoiced_amount_usd': 'Pending Delivery',
                'po_line_id': 'Line Items',
                'product_name': 'Products',
                'period': 'Period'
            }
            
            # Only rename columns that exist
            rename_dict = {k: v for k, v in column_rename.items() if k in aggregated.columns}
            aggregated.rename(columns=rename_dict, inplace=True)
            
            # Calculate conversion rate if both columns exist
            if 'Order Value' in aggregated.columns and 'Invoiced Value' in aggregated.columns:
                aggregated['Conversion Rate'] = (
                    aggregated['Invoiced Value'] / aggregated['Order Value'].replace(0, np.nan) * 100
                ).fillna(0).round(1)
            
            # Add Vendor column if exists in grouping
            if 'vendor_name' in aggregated.columns:
                aggregated.rename(columns={'vendor_name': 'Vendor'}, inplace=True)
            
            logger.info(f"Aggregated {len(df)} records into {len(aggregated)} periods")
            return aggregated
            
        except Exception as e:
            logger.error(f"Error aggregating by period: {e}", exc_info=True)
            raise CalculationError("Failed to aggregate data by period", {'error': str(e)})
    
    @staticmethod
    def calculate_aging_metrics(
        invoice_date: pd.Timestamp,
        due_date: pd.Timestamp,
        payment_status: str,
        current_date: Optional[pd.Timestamp] = None
    ) -> Dict[str, Any]:
        """
        Calculate invoice aging metrics
        
        Args:
            invoice_date: Invoice issuance date
            due_date: Payment due date
            payment_status: Payment status
            current_date: Current date (default: today)
            
        Returns:
            Dictionary with aging metrics
        """
        if current_date is None:
            current_date = pd.Timestamp.now()
        
        # Calculate days
        invoice_age = (current_date - invoice_date).days if pd.notna(invoice_date) else 0
        days_overdue = (current_date - due_date).days if pd.notna(due_date) else 0
        
        # Determine aging bucket
        if payment_status == 'Fully Paid':
            aging_status = 'Paid'
        elif days_overdue < 0:
            aging_status = 'Not Yet Due'
        elif days_overdue <= 30:
            aging_status = '0-30 Days'
        elif days_overdue <= 60:
            aging_status = '31-60 Days'
        elif days_overdue <= 90:
            aging_status = '61-90 Days'
        else:
            aging_status = '>90 Days'
        
        return {
            'invoice_age_days': invoice_age,
            'days_overdue': max(0, days_overdue),
            'aging_status': aging_status,
            'is_overdue': days_overdue > 0 and payment_status != 'Fully Paid'
        }
    
    @staticmethod
    def calculate_summary_stats(df: pd.DataFrame, value_columns: List[str]) -> Dict[str, float]:
        """
        Calculate summary statistics for given columns
        
        Args:
            df: DataFrame
            value_columns: List of column names
            
        Returns:
            Dictionary with summary stats
        """
        stats = {}
        
        for col in value_columns:
            if col in df.columns:
                stats[f'{col}_total'] = df[col].sum()
                stats[f'{col}_mean'] = df[col].mean()
                stats[f'{col}_median'] = df[col].median()
                stats[f'{col}_min'] = df[col].min()
                stats[f'{col}_max'] = df[col].max()
        
        return stats
    
    @staticmethod
    def calculate_growth_metrics(
        current_value: float,
        previous_value: float
    ) -> Dict[str, Any]:
        """
        Calculate period-over-period growth
        
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
            'growth_amount': round(current_value - previous_value, 2),
            'is_growth': current_value > previous_value
        }
    
    @staticmethod
    def identify_performance_issues(
        conversion_rate: float,
        payment_rate: float,
        days_overdue: int,
        outstanding_amount: float
    ) -> List[Dict[str, Any]]:
        """
        Identify performance issues
        
        Args:
            conversion_rate: Order to invoice conversion rate
            payment_rate: Payment completion rate
            days_overdue: Days overdue
            outstanding_amount: Outstanding amount
            
        Returns:
            List of issue dictionaries
        """
        issues = []
        
        # Low conversion
        if conversion_rate < 80:
            issues.append({
                'type': 'low_conversion',
                'severity': 'warning' if conversion_rate >= 70 else 'critical',
                'message': f'Low conversion rate: {conversion_rate:.1f}%',
                'value': conversion_rate
            })
        
        # Low payment rate
        if payment_rate < 80:
            issues.append({
                'type': 'low_payment',
                'severity': 'warning' if payment_rate >= 70 else 'critical',
                'message': f'Low payment rate: {payment_rate:.1f}%',
                'value': payment_rate
            })
        
        # Overdue invoices
        if days_overdue > 30:
            issues.append({
                'type': 'overdue',
                'severity': 'warning' if days_overdue <= 60 else 'critical',
                'message': f'Invoice overdue by {days_overdue} days',
                'value': days_overdue
            })
        
        # High outstanding
        if outstanding_amount > 100000:
            issues.append({
                'type': 'high_outstanding',
                'severity': 'warning',
                'message': f'High outstanding amount: ${outstanding_amount:,.0f}',
                'value': outstanding_amount
            })
        
        return issues