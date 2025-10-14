"""
Column Configuration Module
Handles column selection UI and presets for PO tracking
"""

from typing import List, Dict, Set
import streamlit as st

# ============================================
# COLUMN DEFINITIONS & PRESETS
# ============================================

# All available columns mapped to display names
COLUMN_DEFINITIONS = {
    # Basic Information
    'po_number': 'PO Number',
    'external_ref_number': 'External Ref',
    'po_date': 'PO Date',
    'created_by': 'Created By',
    'status': 'Status',
    'po_notes': 'PO Notes',
    'po_type': 'PO Type',
    'legal_entity': 'Legal Entity',
    'legal_entity_code': 'Legal Entity Code',
    
    # Vendor Information
    'vendor_name': 'Vendor Name',
    'vendor_code': 'Vendor Code',
    'vendor_type': 'Vendor Type',
    'vendor_location_type': 'Vendor Location',
    'vendor_country_name': 'Vendor Country',
    'vendor_contact_name': 'Vendor Contact',
    'vendor_contact_email': 'Contact Email',
    'vendor_contact_phone': 'Contact Phone',
    
    # Product Details
    'pt_code': 'PT Code',
    'product_name': 'Product Name',
    'brand': 'Brand',
    'package_size': 'Package Size',
    'hs_code': 'HS Code',
    'vendor_product_code': 'Vendor Product Code',
    'shelf_life': 'Shelf Life',
    'storage_condition': 'Storage Condition',
    
    # Quantities & UOM
    'buying_quantity': 'Buying Quantity',
    'standard_quantity': 'Standard Quantity',
    'buying_uom': 'Buying UOM',
    'standard_uom': 'Standard UOM',
    'uom_conversion': 'UOM Conversion',
    'moq': 'MOQ',
    'spq': 'SPQ',
    'pending_standard_arrival_quantity': 'Pending Arrival',
    'pending_buying_invoiced_quantity': 'Pending Invoice',
    'total_standard_arrived_quantity': 'Total Arrived',
    'total_buying_invoiced_quantity': 'Total Invoiced',
    
    # Financial & Pricing
    'purchase_unit_cost': 'Purchase Unit Cost',
    'standard_unit_cost': 'Standard Cost',
    'total_amount': 'Total Amount',
    'currency': 'Currency',
    'total_amount_usd': 'Total USD',
    'usd_exchange_rate': 'Exchange Rate',
    'outstanding_invoiced_amount_usd': 'Outstanding Invoice USD',
    'outstanding_arrival_amount_usd': 'Outstanding Arrival USD',
    'invoiced_amount_usd': 'Invoiced USD',
    'arrival_amount_usd': 'Arrival USD',
    'payment_term': 'Payment Term',
    'trade_term': 'Trade Term',
    'vat_gst_percent': 'VAT/GST %',
    
    # Dates & Timeline
    'etd': 'ETD',
    'eta': 'ETA',
    'last_invoice_date': 'Last Invoice Date',
    'po_line_created_date': 'PO Line Created',
    'ci_numbers': 'CI Numbers',
    
    # Status & Tracking
    'arrival_completion_percent': 'Arrival %',
    'invoice_completion_percent': 'Invoice %',
    'is_over_delivered': 'Over Delivered',
    'is_over_invoiced': 'Over Invoiced',
    'has_cancellation': 'Has Cancellation',
}

# Column groups for organized display
COLUMN_GROUPS = {
    'Basic Information': [
        'po_number', 'external_ref_number', 'po_date', 
        'created_by', 'status', 'po_notes', 'po_type',
        'legal_entity', 'legal_entity_code'
    ],
    'Vendor Information': [
        'vendor_name', 'vendor_code', 'vendor_type',
        'vendor_location_type', 'vendor_country_name',
        'vendor_contact_name', 'vendor_contact_email',
        'vendor_contact_phone'
    ],
    'Product Details': [
        'pt_code', 'product_name', 'brand', 'package_size',
        'hs_code', 'vendor_product_code', 'shelf_life',
        'storage_condition'
    ],
    'Quantities & UOM': [
        'buying_quantity', 'standard_quantity', 'buying_uom',
        'standard_uom', 'uom_conversion', 'moq', 'spq',
        'pending_standard_arrival_quantity',
        'pending_buying_invoiced_quantity',
        'total_standard_arrived_quantity',
        'total_buying_invoiced_quantity'
    ],
    'Financial & Pricing': [
        'purchase_unit_cost', 'standard_unit_cost',
        'total_amount', 'currency', 'total_amount_usd',
        'usd_exchange_rate', 'outstanding_invoiced_amount_usd',
        'outstanding_arrival_amount_usd', 'invoiced_amount_usd',
        'arrival_amount_usd', 'payment_term', 'trade_term',
        'vat_gst_percent'
    ],
    'Dates & Timeline': [
        'etd', 'eta', 'last_invoice_date', 
        'po_line_created_date', 'ci_numbers'
    ],
    'Status & Tracking': [
        'arrival_completion_percent', 'invoice_completion_percent',
        'is_over_delivered', 'is_over_invoiced', 'has_cancellation'
    ]
}

# Default columns shown on first load
DEFAULT_COLUMNS = [
    'po_number', 'vendor_name', 'vendor_location_type',
    'po_date', 'etd', 'eta', 'pt_code', 'product_name',
    'buying_quantity', 'pending_standard_arrival_quantity',
    'arrival_completion_percent', 'outstanding_arrival_amount_usd',
    'status', 'created_by'
]

# Preset configurations
PRESET_ESSENTIAL = [
    'po_number', 'po_date', 'vendor_name', 'product_name',
    'pt_code', 'etd', 'eta', 'status', 'buying_quantity',
    'arrival_completion_percent'
]

PRESET_FINANCIAL = [
    'po_number', 'vendor_name', 'product_name', 'currency',
    'total_amount_usd', 'outstanding_invoiced_amount_usd',
    'outstanding_arrival_amount_usd', 'payment_term',
    'arrival_completion_percent', 'invoice_completion_percent',
    'status'
]

PRESET_TRACKING = [
    'po_number', 'vendor_name', 'product_name', 'etd', 'eta',
    'pending_standard_arrival_quantity', 'pending_buying_invoiced_quantity',
    'arrival_completion_percent', 'invoice_completion_percent',
    'status', 'last_invoice_date'
]

# ============================================
# MAIN FUNCTIONS
# ============================================

def initialize_column_selection() -> None:
    """Initialize column selection in session state if not exists"""
    if 'selected_columns' not in st.session_state:
        st.session_state.selected_columns = DEFAULT_COLUMNS.copy()


def render_column_selector() -> List[str]:
    """
    Render column configuration widget with expander
    Returns: List of selected column names
    """
    initialize_column_selection()
    
    selected_cols = st.session_state.selected_columns
    total_cols = len(COLUMN_DEFINITIONS)
    selected_count = len(selected_cols)
    
    with st.expander(f"🔽 Column Configuration ({selected_count}/{total_cols} columns selected)", 
                     expanded=False):
        
        # Quick Presets
        st.markdown("**Quick Presets:**")
        col1, col2, col3, col4, col5 = st.columns(5)
        
        with col1:
            if st.button("📦 Essential", use_container_width=True, key="preset_essential"):
                st.session_state.selected_columns = PRESET_ESSENTIAL.copy()
                st.rerun()
        
        with col2:
            if st.button("💰 Financial", use_container_width=True, key="preset_financial"):
                st.session_state.selected_columns = PRESET_FINANCIAL.copy()
                st.rerun()
        
        with col3:
            if st.button("📊 Tracking", use_container_width=True, key="preset_tracking"):
                st.session_state.selected_columns = PRESET_TRACKING.copy()
                st.rerun()
        
        with col4:
            if st.button("✅ Select All", use_container_width=True, key="select_all"):
                st.session_state.selected_columns = list(COLUMN_DEFINITIONS.keys())
                st.rerun()
        
        with col5:
            if st.button("🗑️ Clear All", use_container_width=True, key="clear_all"):
                st.session_state.selected_columns = []
                st.rerun()
        
        st.markdown("---")
        
        # Render grouped checkboxes
        for group_name, columns in COLUMN_GROUPS.items():
            group_selected = sum(1 for col in columns if col in selected_cols)
            
            st.markdown(f"**{group_name}** ({group_selected}/{len(columns)})")
            
            # Create columns for checkboxes (3 per row)
            num_cols = 3
            for i in range(0, len(columns), num_cols):
                cols = st.columns(num_cols)
                for j, col_key in enumerate(columns[i:i+num_cols]):
                    if col_key in COLUMN_DEFINITIONS:
                        with cols[j]:
                            is_selected = col_key in selected_cols
                            if st.checkbox(
                                COLUMN_DEFINITIONS[col_key],
                                value=is_selected,
                                key=f"col_{col_key}"
                            ):
                                if col_key not in selected_cols:
                                    selected_cols.append(col_key)
                            else:
                                if col_key in selected_cols:
                                    selected_cols.remove(col_key)
            
            st.markdown("")  # spacing
        
        st.markdown("---")
        
        # Bottom buttons
        col1, col2 = st.columns([3, 1])
        with col1:
            if st.button("🔄 Reset to Default", use_container_width=True):
                st.session_state.selected_columns = DEFAULT_COLUMNS.copy()
                st.rerun()
        
        with col2:
            if st.button("✓ Apply", type="primary", use_container_width=True):
                st.session_state.selected_columns = selected_cols
                st.rerun()
    
    return st.session_state.selected_columns


def get_selected_columns() -> List[str]:
    """Get currently selected columns from session state"""
    initialize_column_selection()
    return st.session_state.selected_columns


def get_column_display_name(col_key: str) -> str:
    """Get display name for a column key"""
    return COLUMN_DEFINITIONS.get(col_key, col_key)