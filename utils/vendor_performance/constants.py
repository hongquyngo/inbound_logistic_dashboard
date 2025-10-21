"""
Shared Constants for Vendor Performance Module

Contains all configuration, thresholds, and display mappings.
"""

from typing import Dict, List

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

# ==================== COLUMN DISPLAY NAMES ====================
COLUMN_DISPLAY_NAMES = {
    # Vendor info
    'vendor_name': 'Vendor',
    'vendor_code': 'Code',
    'vendor_type': 'Type',
    'vendor_location_type': 'Location',
    
    # Order metrics
    'total_pos': 'Total POs',
    'total_po_value': 'Total Order Value',
    'total_invoiced': 'Invoiced Value',
    'pending_delivery': 'Pending Delivery',
    'conversion_rate': 'Conversion %',
    
    # Product info
    'product_name': 'Product',
    'brand': 'Brand',
    'pt_code': 'PT Code',
    
    # Quantity
    'standard_quantity': 'Order Qty',
    'total_standard_arrived_quantity': 'Arrived Qty',
    'total_buying_invoiced_quantity': 'Invoiced Qty',
    
    # Financial
    'total_amount_usd': 'Order Value',
    'invoiced_amount_usd': 'Invoiced Value',
    'outstanding_invoiced_amount_usd': 'Outstanding',
    'currency': 'Currency',
    'payment_term': 'Payment Terms',
    
    # Status
    'status': 'Status',
    'invoice_completion_percent': 'Invoice %',
    'arrival_completion_percent': 'Arrival %',
    
    # Dates
    'po_date': 'PO Date',
    'etd': 'ETD',
    'eta': 'ETA',
    'last_invoice_date': 'Last Invoice'
}

# ==================== STATUS DISPLAY ====================
STATUS_LABELS = {
    'COMPLETED': '✅ Completed',
    'IN_PROCESS': '🔄 In Process',
    'PENDING': '⏳ Pending',
    'PENDING_INVOICING': '📋 Pending Invoice',
    'PENDING_RECEIPT': '📦 Pending Receipt',
    'OVER_DELIVERED': '⚠️ Over Delivered',
    'CANCELLED': '❌ Cancelled',
    'PARTIALLY_CANCELLED_COMPLETED': '✅ Partially Cancelled (Completed)',
    'PARTIALLY_CANCELLED_PROCESSING': '🔄 Partially Cancelled (Processing)'
}

STATUS_COLORS = {
    'COMPLETED': COLORS['success'],
    'IN_PROCESS': COLORS['info'],
    'PENDING': COLORS['warning'],
    'PENDING_INVOICING': COLORS['warning'],
    'PENDING_RECEIPT': COLORS['warning'],
    'OVER_DELIVERED': COLORS['danger'],
    'CANCELLED': COLORS['secondary'],
    'PARTIALLY_CANCELLED_COMPLETED': COLORS['success'],
    'PARTIALLY_CANCELLED_PROCESSING': COLORS['info']
}

# ==================== CONVERSION RATE LABELS ====================
def get_conversion_tier(rate: float) -> str:
    """Get conversion tier label based on rate"""
    if rate >= CONVERSION_THRESHOLDS['excellent']:
        return "⭐ Excellent"
    elif rate >= CONVERSION_THRESHOLDS['good']:
        return "✅ Good"
    elif rate >= CONVERSION_THRESHOLDS['fair']:
        return "⚠️ Fair"
    else:
        return "❌ Poor"

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
    'YTD': 'ytd',
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

# ==================== EXPORT FORMATS ====================
EXPORT_FORMATS = [
    'Excel (Multi-sheet)',
    'CSV (Data Only)',
    'PDF (Report)'
]

EXPORT_SECTIONS = [
    'Executive Summary',
    'Financial Metrics',
    'Purchase History',
    'Product Analysis',
    'Recommendations'
]

# ==================== ALERTS CONFIGURATION ====================
ALERT_TYPES = {
    'pending_long': {
        'icon': '⚠️',
        'color': COLORS['warning'],
        'threshold': PENDING_DAYS_THRESHOLDS['critical']
    },
    'low_conversion': {
        'icon': '📉',
        'color': COLORS['danger'],
        'threshold': CONVERSION_THRESHOLDS['fair']
    },
    'high_outstanding': {
        'icon': '💰',
        'color': COLORS['warning'],
        'threshold': 100000  # $100K
    }
}

# ==================== FORMATTER FUNCTIONS ====================
def format_currency(value: float, compact: bool = False) -> str:
    """Format currency value"""
    if pd.isna(value) or value is None:
        return "$0"
    
    if compact:
        if abs(value) >= 1_000_000:
            return f"${value/1_000_000:.1f}M"
        elif abs(value) >= 1_000:
            return f"${value/1_000:.1f}K"
    
    return f"${value:,.0f}"

def format_percentage(value: float, decimals: int = 1) -> str:
    """Format percentage value"""
    if pd.isna(value) or value is None:
        return "0.0%"
    return f"{value:.{decimals}f}%"

def format_number(value: float, decimals: int = 0) -> str:
    """Format number with thousand separators"""
    if pd.isna(value) or value is None:
        return "0"
    if decimals == 0:
        return f"{value:,.0f}"
    return f"{value:,.{decimals}f}"

# Import pandas for type checking
import pandas as pd