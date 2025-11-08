# utils/can_tracking/constants.py

"""
Shared Constants for CAN Tracking
Centralized location for all constants to avoid duplication

⚠️ IMPORTANT: All status values MUST match the database ENUM exactly!
Database table: arrivals.status
"""

# CAN Status Display Mapping
# ⚠️ Keys MUST match database ENUM values EXACTLY (case-sensitive)
STATUS_DISPLAY = {
    'REQUEST_STATUS': 'Request/Pending',
    'CONFIRMED_STATUS': 'Confirmed',                    # ✅ ADDED (was missing)
    'CUSTOM_CLEARANCE_STATUS': 'Custom Clearance',      # ✅ FIXED: CUSTOM not CUSTOMER
    'WH_ARRIVAL_STATUS': 'Warehouse Arrival',
    'STOCKED_IN_STATUS': 'Stocked In',
    'PARTIALLY_STOCKED_IN_STATUS': 'Partially Stocked In',
    'PICKED_UP_STATUS': 'Picked Up'
}

# Reverse mapping for status conversion (from display format to DB format)
# This is used when the view returns lowercase/snake_case status values
STATUS_REVERSE_MAP = {
    'pending': 'REQUEST_STATUS',
    'request': 'REQUEST_STATUS',
    'confirmed': 'CONFIRMED_STATUS',
    'custom_clearance': 'CUSTOM_CLEARANCE_STATUS',      # ✅ FIXED
    'warehouse_arrival': 'WH_ARRIVAL_STATUS',
    'stocked_in': 'STOCKED_IN_STATUS',
    'partially_stocked_in': 'PARTIALLY_STOCKED_IN_STATUS',
    'picked_up': 'PICKED_UP_STATUS'
}

# All status values for dropdown (these will be used in SQL UPDATE)
# ⚠️ These MUST be valid ENUM values from the database
STATUS_VALUES = list(STATUS_DISPLAY.keys())

# Threshold days
URGENT_DAYS_THRESHOLD = 7
CRITICAL_DAYS_THRESHOLD = 14