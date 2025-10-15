"""
Column Configuration Module for CAN Tracking
Handles column selection UI and presets
"""

from typing import List, Dict
import streamlit as st

# ============================================
# COLUMN DEFINITIONS & PRESETS
# ============================================

# All available columns mapped to display names
COLUMN_DEFINITIONS = {
    # Basic CAN Information
    'arrival_note_number': 'CAN Number',
    'arrival_date': 'Arrival Date',
    'creator': 'Creator',
    'days_since_arrival': 'Days Since Arrival',
    'can_status': 'CAN Status',
    
    # PO Information
    'po_number': 'PO Number',
    'external_ref_number': 'External Ref',
    'po_type': 'PO Type',
    'payment_term': 'Payment Term',
    
    # Warehouse Information (THÊM MỚI)
    'warehouse_name': 'Warehouse',
    'warehouse_address': 'Warehouse Address',
    'warehouse_zipcode': 'Warehouse ZIP',
    'warehouse_company_name': 'Warehouse Company',
    'warehouse_country_name': 'Warehouse Country',
    'warehouse_state_name': 'Warehouse State',
    
    # Vendor Information
    'vendor': 'Vendor',
    'vendor_code': 'Vendor Code',
    'vendor_type': 'Vendor Type',
    'vendor_location_type': 'Vendor Location',
    'vendor_country_name': 'Vendor Country',
    'vendor_street': 'Vendor Street',
    'vendor_zip_code': 'Vendor ZIP',
    'vendor_state_province': 'Vendor State',
    'vendor_contact_name': 'Vendor Contact',
    'vendor_contact_email': 'Vendor Email',
    'vendor_contact_phone': 'Vendor Phone',
    
    # Consignee Information
    'consignee': 'Consignee',
    'consignee_code': 'Consignee Code',
    'consignee_street': 'Consignee Street',
    'consignee_zip_code': 'Consignee ZIP',
    'consignee_state_province': 'Consignee State',
    'consignee_country_name': 'Consignee Country',
    'buyer_contact_name': 'Buyer Contact',
    'buyer_contact_email': 'Buyer Email',
    'buyer_contact_phone': 'Buyer Phone',
    
    # Ship To & Bill To
    'ship_to_company_name': 'Ship To Company',
    'ship_to_contact_name': 'Ship To Contact',
    'ship_to_contact_email': 'Ship To Email',
    'bill_to_company_name': 'Bill To Company',
    'bill_to_contact_name': 'Bill To Contact',
    'bill_to_contact_email': 'Bill To Email',
    
    # Product Information
    'product_name': 'Product Name',
    'pt_code': 'PT Code',
    'brand': 'Brand',
    'package_size': 'Package Size',
    'hs_code': 'HS Code',
    'shelf_life': 'Shelf Life',
    'standard_uom': 'Standard UOM',
    
    # Quantity & UOM
    'buying_uom': 'Buying UOM',
    'uom_conversion': 'UOM Conversion',
    'buying_quantity': 'Buying Quantity',
    'standard_quantity': 'Standard Quantity',
    
    # Cost Information
    'buying_unit_cost': 'Buying Unit Cost',
    'standard_unit_cost': 'Standard Unit Cost',
    'landed_cost': 'Landed Cost',
    'landed_cost_usd': 'Landed Cost USD',
    'vat_gst': 'VAT/GST',
    
    # Quantity Flow
    'total_arrived_quantity': 'Total Arrived',
    'arrival_quantity': 'Arrival Quantity',
    'total_stocked_in': 'Total Stocked In',
    'pending_quantity': 'Pending Quantity',
    'pending_value_usd': 'Pending Value USD',
    'pending_percent': 'Pending %',
    
    # Invoice Information
    'total_invoiced_quantity': 'Total Invoiced Qty',
    'total_standard_invoiced_quantity': 'Total Std Invoiced',
    'invoice_count': 'Invoice Count',
    'invoiced_percent': 'Invoiced %',
    'invoice_status': 'Invoice Status',
    'uninvoiced_quantity': 'Uninvoiced Qty',
    
    # Status & Tracking
    'stocked_in_status': 'Stock-in Status',
    'days_pending': 'Days Pending',
    
    # PO Line Status
    'po_line_total_arrived_qty': 'PO Line Total Arrived',
    'po_line_total_invoiced_buying_qty': 'PO Line Total Invoiced',
    'po_line_pending_invoiced_qty': 'PO Line Pending Invoice',
    'po_line_pending_arrival_qty': 'PO Line Pending Arrival',
    'po_line_status': 'PO Line Status',
    'po_line_is_over_delivered': 'Over Delivered',
    'po_line_is_over_invoiced': 'Over Invoiced',
    'po_line_arrival_completion_percent': 'PO Line Arrival %',
    'po_line_invoice_completion_percent': 'PO Line Invoice %',
}

# Column groups for organized display
COLUMN_GROUPS = {
    'Basic CAN Information': [
        'arrival_note_number', 'arrival_date', 'creator',
        'days_since_arrival', 'can_status'
    ],
    'PO Information': [
        'po_number', 'external_ref_number', 'po_type', 'payment_term'
    ],
    'Warehouse Information': [
        'warehouse_name', 'warehouse_address', 'warehouse_zipcode',
        'warehouse_company_name', 'warehouse_country_name',
        'warehouse_state_name'
    ],
    'Vendor Information': [
        'vendor', 'vendor_code', 'vendor_type', 'vendor_location_type',
        'vendor_country_name', 'vendor_street', 'vendor_zip_code',
        'vendor_state_province', 'vendor_contact_name',
        'vendor_contact_email', 'vendor_contact_phone'
    ],
    'Consignee Information': [
        'consignee', 'consignee_code', 'consignee_street',
        'consignee_zip_code', 'consignee_state_province',
        'consignee_country_name', 'buyer_contact_name',
        'buyer_contact_email', 'buyer_contact_phone'
    ],
    'Ship To & Bill To': [
        'ship_to_company_name', 'ship_to_contact_name',
        'ship_to_contact_email', 'bill_to_company_name',
        'bill_to_contact_name', 'bill_to_contact_email'
    ],
    'Product Information': [
        'product_name', 'pt_code', 'brand', 'package_size',
        'hs_code', 'shelf_life', 'standard_uom'
    ],
    'Quantity & UOM': [
        'buying_uom', 'uom_conversion', 'buying_quantity',
        'standard_quantity'
    ],
    'Cost Information': [
        'buying_unit_cost', 'standard_unit_cost', 'landed_cost',
        'landed_cost_usd', 'vat_gst'
    ],
    'Quantity Flow': [
        'total_arrived_quantity', 'arrival_quantity', 'total_stocked_in',
        'pending_quantity', 'pending_value_usd', 'pending_percent'
    ],
    'Invoice Information': [
        'total_invoiced_quantity', 'total_standard_invoiced_quantity',
        'invoice_count', 'invoiced_percent', 'invoice_status',
        'uninvoiced_quantity'
    ],
    'Status & Tracking': [
        'stocked_in_status', 'days_pending'
    ],
    'PO Line Status': [
        'po_line_total_arrived_qty', 'po_line_total_invoiced_buying_qty',
        'po_line_pending_invoiced_qty', 'po_line_pending_arrival_qty',
        'po_line_status', 'po_line_is_over_delivered',
        'po_line_is_over_invoiced', 'po_line_arrival_completion_percent',
        'po_line_invoice_completion_percent'
    ]
}

# Default columns shown on first load
DEFAULT_COLUMNS = [
    'arrival_note_number', 'arrival_date', 'days_since_arrival',
    'warehouse_name', 'vendor', 'vendor_location_type', 'po_number',
    'product_name', 'pt_code', 'pending_quantity',
    'pending_value_usd', 'pending_percent', 'can_status'
]

# Preset configurations
PRESET_ESSENTIAL = [
    'arrival_note_number', 'arrival_date', 'vendor',
    'po_number', 'product_name', 'pt_code',
    'pending_quantity', 'pending_value_usd', 'can_status'
]

PRESET_FINANCIAL = [
    'arrival_note_number', 'vendor', 'product_name',
    'landed_cost_usd', 'pending_value_usd', 'pending_percent',
    'total_invoiced_quantity', 'invoiced_percent',
    'invoice_status', 'can_status'
]

PRESET_TRACKING = [
    'arrival_note_number', 'arrival_date', 'days_since_arrival',
    'warehouse_name', 'vendor', 'product_name', 'arrival_quantity',
    'total_stocked_in', 'pending_quantity', 'pending_percent',
    'stocked_in_status', 'can_status'
]

PRESET_DETAILED = [
    'arrival_note_number', 'arrival_date', 'warehouse_name', 'vendor',
    'vendor_type', 'vendor_location_type', 'consignee',
    'po_number', 'product_name', 'pt_code', 'brand',
    'arrival_quantity', 'pending_quantity', 'pending_value_usd',
    'days_since_arrival', 'can_status'
]

# ============================================
# MAIN FUNCTIONS
# ============================================

def initialize_column_selection() -> None:
    """Initialize column selection in session state if not exists"""
    if 'can_selected_columns' not in st.session_state:
        st.session_state.can_selected_columns = DEFAULT_COLUMNS.copy()


def render_column_selector() -> List[str]:
    """
    Render column configuration widget with expander
    Returns: List of selected column names
    """
    initialize_column_selection()
    
    selected_cols = st.session_state.can_selected_columns
    total_cols = len(COLUMN_DEFINITIONS)
    selected_count = len(selected_cols)
    
    with st.expander(f"🔽 Column Configuration ({selected_count}/{total_cols} columns selected)", 
                     expanded=False):
        
        # Quick Presets
        st.markdown("**Quick Presets:**")
        col1, col2, col3, col4, col5, col6 = st.columns(6)
        
        with col1:
            if st.button("📦 Essential", use_container_width=True, key="can_preset_essential"):
                st.session_state.can_selected_columns = PRESET_ESSENTIAL.copy()
                st.rerun()
        
        with col2:
            if st.button("💰 Financial", use_container_width=True, key="can_preset_financial"):
                st.session_state.can_selected_columns = PRESET_FINANCIAL.copy()
                st.rerun()
        
        with col3:
            if st.button("📊 Tracking", use_container_width=True, key="can_preset_tracking"):
                st.session_state.can_selected_columns = PRESET_TRACKING.copy()
                st.rerun()
        
        with col4:
            if st.button("🔍 Detailed", use_container_width=True, key="can_preset_detailed"):
                st.session_state.can_selected_columns = PRESET_DETAILED.copy()
                st.rerun()
        
        with col5:
            if st.button("✅ Select All", use_container_width=True, key="can_select_all"):
                st.session_state.can_selected_columns = list(COLUMN_DEFINITIONS.keys())
                st.rerun()
        
        with col6:
            if st.button("🗑️ Clear All", use_container_width=True, key="can_clear_all"):
                st.session_state.can_selected_columns = []
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
                                key=f"can_col_{col_key}"
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
            if st.button("🔄 Reset to Default", use_container_width=True, key="can_reset"):
                st.session_state.can_selected_columns = DEFAULT_COLUMNS.copy()
                st.rerun()
        
        with col2:
            if st.button("✓ Apply", type="primary", use_container_width=True, key="can_apply"):
                st.session_state.can_selected_columns = selected_cols
                st.rerun()
    
    return st.session_state.can_selected_columns


def get_selected_columns() -> List[str]:
    """Get currently selected columns from session state"""
    initialize_column_selection()
    return st.session_state.can_selected_columns


def get_column_display_name(col_key: str) -> str:
    """Get display name for a column key"""
    return COLUMN_DEFINITIONS.get(col_key, col_key)