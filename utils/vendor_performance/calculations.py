"""
Calculation Logic for Vendor Performance - Fixed & Cleaned

FIXES APPLIED:
1. ✅ Fixed conversion rate cap: 110% → 100%
2. ✅ Removed unused functions
3. ✅ Improved validation logic
4. ✅ Better error messages

Version: 3.0
Last Updated: 2025-10-22
"""

import pandas as pd
import numpy as np
from typing import Dict, Any, Optional
import logging

from .exceptions import CalculationError, ValidationError

logger = logging.getLogger(__name__)


class PerformanceCalculator:
    """Calculator for vendor performance metrics"""
    
    @staticmethod
    def calculate_conversion_rate(
        invoiced_value: float,
        order_value: float,
        max_rate: float = 100.0  # ✅ FIXED: Changed from 110.0 to 100.0
    ) -> float:
        """
        Calculate conversion rate with validation
        
        Formula: (Invoiced / Order Entry) × 100%
        Capped at 100% (over-invoicing handled separately via is_over_invoiced flag)
        
        Args:
            invoiced_value: Total invoiced amount (must be >= 0)
            order_value: Total order value (must be > 0)
            max_rate: Maximum allowed rate (default 100%)
            
        Returns:
            Conversion rate percentage (0-100)
            
        Raises:
            ValidationError: If inputs are invalid
            
        Examples:
            >>> calculate_conversion_rate(90000, 100000)
            90.0
            >>> calculate_conversion_rate(110000, 100000)  # Over-invoiced
            100.0
        """
        try:
            invoiced_value = float(invoiced_value) if invoiced_value is not None else 0.0
            order_value = float(order_value) if order_value is not None else 0.0
        except (TypeError, ValueError) as e:
            raise ValidationError(f"Invalid numeric values: {e}")
        
        if invoiced_value < 0:
            logger.warning(f"Negative invoiced value: {invoiced_value}, setting to 0")
            invoiced_value = 0
        
        if order_value < 0:
            logger.warning(f"Negative order value: {order_value}, setting to 0")
            order_value = 0
        
        if pd.isna(order_value) or order_value == 0:
            return 0.0
        
        rate = (invoiced_value / order_value * 100)
        
        # Cap at maximum (default 100%)
        if rate > max_rate:
            logger.debug(
                f"Conversion rate {rate:.1f}% exceeds cap {max_rate:.1f}%, "
                f"capping at {max_rate:.1f}%"
            )
            rate = max_rate
        
        return round(rate, 1)
    
    @staticmethod
    def calculate_payment_rate(
        paid_value: float,
        invoiced_value: float,
        max_rate: float = 100.0
    ) -> float:
        """
        Calculate payment rate
        
        Formula: (Paid / Invoiced) × 100%
        
        Args:
            paid_value: Total paid amount
            invoiced_value: Total invoiced amount
            max_rate: Maximum allowed rate (default 100%)
            
        Returns:
            Payment rate percentage (0-100)
            
        Examples:
            >>> calculate_payment_rate(80000, 100000)
            80.0
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
            Aggregated DataFrame with columns:
            - Period: Period start date
            - PO Count / Order Value / Invoiced Value / etc.
            
        Raises:
            CalculationError: If aggregation fails
            
        Examples:
            >>> df = aggregate_by_period(order_df, 'monthly', 'po_date')
            >>> print(df.columns)
            ['Period', 'PO Count', 'Order Value', 'Invoiced Value', 'Conversion Rate']
        """
        if df.empty:
            return pd.DataFrame()
        
        try:
            work_df = df.copy()
            
            if date_column not in work_df.columns:
                raise ValidationError(f"Column {date_column} not found in dataframe")
            
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
            
            # Build aggregation dictionary dynamically
            agg_dict = {}
            
            if 'po_number' in work_df.columns:
                agg_dict['po_number'] = 'nunique'
            
            # Handle both column names for order value
            if 'total_order_value' in work_df.columns:
                agg_dict['total_order_value'] = 'sum'
            elif 'total_amount_usd' in work_df.columns:
                agg_dict['total_amount_usd'] = 'sum'
            
            # Handle invoice value columns (support both naming conventions)
            if 'invoiced_amount_usd' in work_df.columns:
                agg_dict['invoiced_amount_usd'] = 'sum'
            elif 'total_invoiced_value' in work_df.columns:
                agg_dict['total_invoiced_value'] = 'sum'
            
            if 'outstanding_invoiced_amount_usd' in work_df.columns:
                agg_dict['outstanding_invoiced_amount_usd'] = 'sum'
            elif 'outstanding_value' in work_df.columns:
                agg_dict['outstanding_value'] = 'sum'
            
            if 'po_line_id' in work_df.columns:
                agg_dict['po_line_id'] = 'count'
            
            if 'product_name' in work_df.columns:
                agg_dict['product_name'] = 'nunique'
            
            if not agg_dict:
                raise ValidationError("No aggregatable columns found in dataframe")
            
            # Perform aggregation
            aggregated = work_df.groupby(group_cols).agg(agg_dict).reset_index()
            
            # Rename columns to standard names
            column_rename = {
                'po_number': 'PO Count',
                'total_order_value': 'Order Value',
                'total_amount_usd': 'Order Value',
                'invoiced_amount_usd': 'Invoiced Value',
                'total_invoiced_value': 'Invoiced Value',  # Support cohort query
                'outstanding_invoiced_amount_usd': 'Pending Delivery',
                'outstanding_value': 'Pending Delivery',  # Support cohort query
                'po_line_id': 'Line Items',
                'product_name': 'Products',
                'period': 'Period'
            }
            
            rename_dict = {k: v for k, v in column_rename.items() if k in aggregated.columns}
            aggregated.rename(columns=rename_dict, inplace=True)
            
            # Calculate conversion rate if both values exist
            if 'Order Value' in aggregated.columns and 'Invoiced Value' in aggregated.columns:
                aggregated['Conversion Rate'] = (
                    aggregated['Invoiced Value'] / 
                    aggregated['Order Value'].replace(0, np.nan) * 100
                ).fillna(0)
                
                # Cap at 100%
                aggregated['Conversion Rate'] = aggregated['Conversion Rate'].clip(upper=100.0)
                aggregated['Conversion Rate'] = aggregated['Conversion Rate'].round(1)
            
            # Rename vendor column if exists
            if 'vendor_name' in aggregated.columns:
                aggregated.rename(columns={'vendor_name': 'Vendor'}, inplace=True)
            
            logger.info(
                f"Aggregated {len(df)} records into {len(aggregated)} "
                f"{period_type} periods"
            )
            return aggregated
            
        except ValidationError:
            raise
        except Exception as e:
            logger.error(f"Error aggregating by period: {e}", exc_info=True)
            raise CalculationError(
                "Failed to aggregate data by period", 
                {'error': str(e), 'period_type': period_type}
            )
    
    @staticmethod
    def calculate_outstanding(
        order_value: float,
        invoiced_value: float
    ) -> float:
        """
        Calculate outstanding amount
        
        Formula: Order Value - Invoiced Value
        
        Args:
            order_value: Total order value
            invoiced_value: Total invoiced value
            
        Returns:
            Outstanding amount (>= 0)
        """
        try:
            order_value = float(order_value) if order_value is not None else 0.0
            invoiced_value = float(invoiced_value) if invoiced_value is not None else 0.0
        except (TypeError, ValueError):
            return 0.0
        
        outstanding = order_value - invoiced_value
        return max(0.0, outstanding)  # Ensure non-negative
    
    @staticmethod
    def calculate_health_score(
        conversion_rate: float,
        payment_rate: float
    ) -> Dict[str, Any]:
        """
        Calculate overall vendor health score
        
        Args:
            conversion_rate: Conversion rate percentage
            payment_rate: Payment rate percentage
            
        Returns:
            Dictionary with:
            - score: Overall score (0-100)
            - rating: Text rating (Excellent/Good/Fair/Poor)
            - color: Color code for UI
        """
        # Simple average of rates
        score = (conversion_rate + payment_rate) / 2
        
        # Determine rating
        if score >= 90:
            rating = 'Excellent'
            color = 'success'
        elif score >= 80:
            rating = 'Good'
            color = 'warning'
        elif score >= 70:
            rating = 'Fair'
            color = 'info'
        else:
            rating = 'Poor'
            color = 'danger'
        
        return {
            'score': round(score, 1),
            'rating': rating,
            'color': color
        }
    
    @staticmethod
    def validate_currency_value(
        value: float,
        max_reasonable: float = 1_000_000_000  # $1B
    ) -> tuple[bool, Optional[str]]:
        """
        Validate if currency value is reasonable
        
        Args:
            value: Value to validate
            max_reasonable: Maximum reasonable value
            
        Returns:
            Tuple of (is_valid, warning_message)
            
        Examples:
            >>> validate_currency_value(100000)
            (True, None)
            >>> validate_currency_value(2e12)
            (False, "Value $2,000,000,000,000 exceeds reasonable maximum")
        """
        if pd.isna(value):
            return True, None
        
        if value < 0:
            return False, f"Negative value ${value:,.2f} is not valid"
        
        if value > max_reasonable:
            return False, (
                f"Value ${value:,.0f} exceeds reasonable maximum "
                f"${max_reasonable:,.0f}. Please verify currency unit."
            )
        
        return True, None


# ==================== HELPER FUNCTIONS ====================

def safe_divide(numerator: float, denominator: float, default: float = 0.0) -> float:
    """
    Safely divide two numbers, returning default if denominator is 0
    
    Args:
        numerator: Numerator
        denominator: Denominator
        default: Default value if division by zero
        
    Returns:
        Result of division or default
    """
    if pd.isna(denominator) or denominator == 0:
        return default
    return numerator / denominator


def safe_percentage(value: float, total: float, decimals: int = 1) -> float:
    """
    Safely calculate percentage
    
    Args:
        value: Part value
        total: Total value
        decimals: Decimal places
        
    Returns:
        Percentage (0-100)
    """
    if pd.isna(total) or total == 0:
        return 0.0
    
    pct = (value / total * 100)
    return round(pct, decimals)