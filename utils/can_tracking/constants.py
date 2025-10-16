# utils/can_tracking/constants.py

"""
Shared Constants for CAN Tracking
Centralized location for all constants to avoid duplication
"""

# CAN Status Display Mapping
STATUS_DISPLAY = {
    'REQUEST_STATUS': 'Request/Pending',
    'CUSTOMER_CLEARANCE_STATUS': 'Customer Clearance',
    'WH_ARRIVAL_STATUS': 'Warehouse Arrival',
    'STOCKED_IN_STATUS': 'Stocked In',
    'PARTIALLY_STOCKED_IN_STATUS': 'Partially Stocked In',
    'PICKED_UP_STATUS': 'Picked Up'
}

# Reverse mapping for status conversion
STATUS_REVERSE_MAP = {
    'pending': 'REQUEST_STATUS',
    'stocked_in': 'STOCKED_IN_STATUS',
    'partially_stocked_in': 'PARTIALLY_STOCKED_IN_STATUS',
    'warehouse_arrival': 'WH_ARRIVAL_STATUS',
    'on_delivery': 'CUSTOMER_CLEARANCE_STATUS',
    'picked_up': 'PICKED_UP_STATUS'
}

# All status values for dropdown
STATUS_VALUES = list(STATUS_DISPLAY.keys())

# Threshold days
URGENT_DAYS_THRESHOLD = 7
CRITICAL_DAYS_THRESHOLD = 14