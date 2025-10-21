"""
Shared Constants for Vendor Performance Module - Clean Version

Contains all configuration, thresholds, and display mappings.
Removed unused functions

Version: 2.1
Last Updated: 2025-10-21
"""

from typing import Dict, List
import pandas as pd

# ==================== PLOTLY CONFIGURATION ====================
PLOTLY_CONFIG = {
    'displaylogo': False,
    'displayModeBar': True,
    'modeBarButtonsToRemove': ['lasso2d', 'select2d'],
    'toImageButtonOptions': {
        'format': 'png',
        'filename': 'vendor_performance',
        'height': 800,
        'width': 1200,
        'scale': 2
    }
}

# ==================== COLOR PALETTE ====================
COLORS = {
    'primary': '#3498db',      # Blue
    'success': '#2ecc71',      # Green
    'warning': '#f39c12',      # Orange
    'danger': '#e74c3c',       # Red
    'info': '#9b59b6',         # Purple
    'secondary': '#95a5a6',    # Gray
    'dark': '#34495e',         # Dark gray
    'light': '#ecf0f1'         # Light gray
}

# ==================== METRICS THRESHOLDS ====================
CONVERSION_THRESHOLDS = {
    'excellent': 95.0,   # >= 95%
    'good': 90.0,        # >= 90%
    'fair': 80.0,        # >= 80%
    'poor': 0.0          # < 80%
}

PENDING_DAYS_THRESHOLDS = {
    'critical': 30,      # > 30 days
    'warning': 15,       # > 15 days
    'normal': 0          # <= 15 days
}

# ==================== DATE DIMENSION MAPPINGS ====================
DATE_DIMENSIONS = {
    'order': {
        'field': 'po_date',
        'label': 'Order Date (PO Date)',
        'description': 'Based on purchase order creation date',
        'view': 'purchase_order_full_view'
    },
    'invoice': {
        'field': 'inv_date',
        'label': 'Invoice Date',
        'description': 'Based on invoice issuance date',
        'view': 'purchase_invoice_full_view'
    },
    'delivery': {
        'field': 'COALESCE(adjust_etd, etd)',
        'label': 'Expected Delivery (ETD)',
        'description': 'Based on expected delivery date',
        'view': 'purchase_order_full_view'
    }
}

# ==================== COLUMN DISPLAY NAMES ====================
COLUMN_DISPLAY_NAMES = {
    # Vendor info
    'vendor_name': 'Vendor',
    'vendor': 'Vendor',
    'vendor_code': 'Code',
    'vendor_type': 'Type',
    'vendor_location_type': 'Location',
    'legal_entity': 'Legal Entity',
    
    # Order metrics
    'total_pos': 'Total POs',
    'total_order_value': 'Order Value',
    'total_invoiced_value': 'Invoiced Value',
    'outstanding_value': 'Outstanding',
    'conversion_rate': 'Conversion %',
    
    # Invoice metrics
    'total_invoices': 'Invoices',
    'total_paid': 'Paid',
    'total_outstanding': 'Outstanding',
    'payment_rate': 'Payment %',
    'overdue_amount': 'Overdue',
    
    # Product info
    'product_name': 'Product',
    'brand': 'Brand',
    'pt_code': 'PT Code',
    
    # Dates
    'po_date': 'PO Date',
    'inv_date': 'Invoice Date',
    'due_date': 'Due Date',
    'etd': 'ETD',
    'eta': 'ETA',
    
    # Status
    'status': 'Status',
    'payment_status': 'Payment Status',
    'aging_status': 'Aging Status'
}

# ==================== STATUS DISPLAY ====================
STATUS_LABELS = {
    # Order statuses
    'COMPLETED': '✅ Completed',
    'IN_PROCESS': '🔄 In Process',
    'PENDING': '⏳ Pending',
    'PENDING_INVOICING': '📋 Pending Invoice',
    'PENDING_RECEIPT': '📦 Pending Receipt',
    'OVER_DELIVERED': '⚠️ Over Delivered',
    'CANCELLED': '✖️ Cancelled',
    
    # Payment statuses
    'Fully Paid': '✅ Fully Paid',
    'Partially Paid': '⚠️ Partially Paid',
    'Unpaid': '❌ Unpaid',
    
    # Aging statuses
    'Current': '✅ Current',
    'Overdue': '⚠️ Overdue',
    'Paid': '✅ Paid'
}

STATUS_COLORS = {
    'COMPLETED': COLORS['success'],
    'IN_PROCESS': COLORS['info'],
    'PENDING': COLORS['warning'],
    'PENDING_INVOICING': COLORS['warning'],
    'PENDING_RECEIPT': COLORS['warning'],
    'OVER_DELIVERED': COLORS['danger'],
    'CANCELLED': COLORS['secondary'],
    
    'Fully Paid': COLORS['success'],
    'Partially Paid': COLORS['warning'],
    'Unpaid': COLORS['danger'],
    
    'Current': COLORS['success'],
    'Overdue': COLORS['danger'],
    'Paid': COLORS['success']
}

# ==================== CONVERSION RATE COLOR HELPER ====================
def get_conversion_color(rate: float) -> str:
    """Get color for conversion rate"""
    if rate >= CONVERSION_THRESHOLDS['excellent']:
        return COLORS['success']
    elif rate >= CONVERSION_THRESHOLDS['good']:
        return COLORS['info']
    elif rate >= CONVERSION_THRESHOLDS['fair']:
        return COLORS['warning']
    else:
        return COLORS['danger']

# ==================== DATE RANGES ====================
DATE_RANGE_OPTIONS = {
    'Last 3 Months': 3,
    'Last 6 Months': 6,
    'Last 12 Months': 12,
    'Custom': 'custom'
}

PERIOD_TYPES = {
    'Monthly': 'monthly',
    'Quarterly': 'quarterly',
    'Yearly': 'yearly'
}

# ==================== CHART SETTINGS ====================
CHART_HEIGHTS = {
    'compact': 300,
    'standard': 400,
    'large': 500,
    'extra_large': 600
}

# ==================== FORMATTER FUNCTIONS ====================
def format_currency(value: float, compact: bool = False) -> str:
    """
    Format currency value
    
    Args:
        value: Numeric value
        compact: Use compact notation (M/K)
        
    Returns:
        Formatted currency string
    """
    if pd.isna(value) or value is None:
        return "$0"
    
    if compact:
        if abs(value) >= 1_000_000:
            return f"${value/1_000_000:.1f}M"
        elif abs(value) >= 1_000:
            return f"${value/1_000:.1f}K"
    
    return f"${value:,.0f}"


def format_percentage(value: float, decimals: int = 1) -> str:
    """
    Format percentage value
    
    Args:
        value: Numeric value
        decimals: Decimal places
        
    Returns:
        Formatted percentage string
    """
    if pd.isna(value) or value is None:
        return "0.0%"
    return f"{value:.{decimals}f}%"


def format_number(value: float, decimals: int = 0) -> str:
    """
    Format number with thousand separators
    
    Args:
        value: Numeric value
        decimals: Decimal places
        
    Returns:
        Formatted number string
    """
    if pd.isna(value) or value is None:
        return "0"
    if decimals == 0:
        return f"{value:,.0f}"
    return f"{value:,.{decimals}f}"