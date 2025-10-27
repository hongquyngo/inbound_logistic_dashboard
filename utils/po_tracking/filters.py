"""
Filter UI Components and SQL Builder - Enhanced with PO Number Filter
Handles all filter rendering and SQL query building with exclusion logic
"""

import streamlit as st
from datetime import datetime, timedelta
from typing import Dict, Tuple, Any, List

# Constants
ALLOWED_DATE_COLUMNS = {
    'po_date': 'po_date',
    'etd': 'etd',
    'eta': 'eta'
}


def render_filters(filter_options: Dict[str, Any]) -> Dict[str, Any]:
    """
    Render all filter UI components
    
    Args:
        filter_options: Dictionary with all available filter options
        
    Returns:
        Dictionary with all filter values and exclusion flags
    """
    with st.expander("🔍 Filters", expanded=True):
        # Date Range
        col1, col2 = st.columns([1, 3])
        
        with col1:
            date_type = st.radio(
                "Date Type",
                options=['PO Date', 'ETD', 'ETA'],
                index=1,
                horizontal=True
            )
        
        with col2:
            # Get date ranges
            date_ranges = filter_options.get('date_ranges', {})
            date_type_lower = date_type.lower().replace(' ', '_')
            
            if date_type_lower == 'po_date':
                db_min_date = date_ranges.get('min_po_date')
                db_max_date = date_ranges.get('max_po_date')
            elif date_type_lower == 'etd':
                db_min_date = date_ranges.get('min_etd')
                db_max_date = date_ranges.get('max_etd')
            else:
                db_min_date = date_ranges.get('min_eta')
                db_max_date = date_ranges.get('max_eta')
            
            min_date = db_min_date if db_min_date else datetime.now().date() - timedelta(days=365)
            max_date = db_max_date if db_max_date else datetime.now().date() + timedelta(days=365)
            
            date_range = st.date_input(
                f"{date_type} Range",
                value=(min_date, max_date),
                min_value=min_date,
                max_value=max_date
            )
        
        # Organization & Vendor
        col1, col2, col3 = st.columns(3)
        
        with col1:
            label_col, excl_col = st.columns([5, 1])
            with label_col:
                st.markdown("**Legal Entity**")
            with excl_col:
                excl_legal_entities = st.checkbox("Excl", key="excl_le")
            legal_entities = st.multiselect(
                "Legal Entity",
                options=filter_options.get('legal_entities', []),
                default=None,
                placeholder="All",
                label_visibility="collapsed"
            )
        
        with col2:
            label_col, excl_col = st.columns([5, 1])
            with label_col:
                st.markdown("**Vendors**")
            with excl_col:
                excl_vendors = st.checkbox("Excl", key="excl_vendors")
            vendors = st.multiselect(
                "Vendors",
                options=filter_options.get('vendors', []),
                default=None,
                placeholder="All",
                label_visibility="collapsed"
            )
        
        with col3:
            label_col, excl_col = st.columns([5, 1])
            with label_col:
                st.markdown("**Vendor Location**")
            with excl_col:
                excl_vendor_locations = st.checkbox("Excl", key="excl_loc")
            vendor_locations = st.multiselect(
                "Vendor Location",
                options=filter_options.get('vendor_location_types', ['Domestic', 'International']),
                default=None,
                placeholder="All",
                label_visibility="collapsed"
            )
        
        # 🆕 PO Number, Products & Brands (same row - 3 columns)
        col1, col2, col3 = st.columns(3)
        
        with col1:
            label_col, excl_col = st.columns([6, 1])
            with label_col:
                st.markdown("**PO Numbers**")
            with excl_col:
                excl_po_numbers = st.checkbox("Excl", key="excl_po_numbers")
            po_numbers = st.multiselect(
                "PO Numbers",
                options=filter_options.get('po_numbers', []),
                default=None,
                placeholder="Search PO numbers...",
                label_visibility="collapsed"
            )
        
        with col2:
            label_col, excl_col = st.columns([6, 1])
            with label_col:
                st.markdown("**Products**")
            with excl_col:
                excl_products = st.checkbox("Excl", key="excl_products")
            products = st.multiselect(
                "Products",
                options=filter_options.get('products', []),
                default=None,
                placeholder="Search products...",
                label_visibility="collapsed"
            )
        
        with col3:
            label_col, excl_col = st.columns([6, 1])
            with label_col:
                st.markdown("**Brands**")
            with excl_col:
                excl_brands = st.checkbox("Excl", key="excl_brands")
            brands = st.multiselect(
                "Brands",
                options=filter_options.get('brands', []),
                default=None,
                placeholder="All",
                label_visibility="collapsed"
            )
        
        # Status & Terms
        col1, col2, col3 = st.columns(3)
        
        with col1:
            label_col, excl_col = st.columns([5, 1])
            with label_col:
                st.markdown("**PO Status**")
            with excl_col:
                excl_status = st.checkbox("Excl", key="excl_status", value=True)  # Default checked
            status = st.multiselect(
                "PO Status",
                options=filter_options.get('po_statuses', []),
                default=['CANCELLED', 'COMPLETED'],  # Default exclude these
                placeholder="All",
                label_visibility="collapsed"
            )
        
        with col2:
            label_col, excl_col = st.columns([5, 1])
            with label_col:
                st.markdown("**Payment Terms**")
            with excl_col:
                excl_payment_terms = st.checkbox("Excl", key="excl_pmt")
            payment_terms = st.multiselect(
                "Payment Terms",
                options=filter_options.get('payment_terms', []),
                default=None,
                placeholder="All",
                label_visibility="collapsed"
            )
        
        with col3:
            label_col, excl_col = st.columns([5, 1])
            with label_col:
                st.markdown("**Created By**")
            with excl_col:
                excl_creators = st.checkbox("Excl", key="excl_creators")
            creators = st.multiselect(
                "Created By",
                options=filter_options.get('creators', []),
                default=None,
                placeholder="All",
                label_visibility="collapsed"
            )
    
    return {
        'date_type': date_type,
        'date_range': date_range,
        'legal_entities': legal_entities,
        'excl_legal_entities': excl_legal_entities,
        'vendors': vendors,
        'excl_vendors': excl_vendors,
        'po_numbers': po_numbers,
        'excl_po_numbers': excl_po_numbers,
        'products': products,
        'excl_products': excl_products,
        'brands': brands,
        'excl_brands': excl_brands,
        'status': status,
        'excl_status': excl_status,
        'payment_terms': payment_terms,
        'excl_payment_terms': excl_payment_terms,
        'vendor_locations': vendor_locations,
        'excl_vendor_locations': excl_vendor_locations,
        'creators': creators,
        'excl_creators': excl_creators
    }


def build_sql_params(filters: Dict[str, Any]) -> Tuple[str, Dict[str, Any]]:
    """
    Convert UI filters to SQL WHERE clauses and parameters
    Handles exclusion logic (NOT IN vs IN)
    
    Args:
        filters: Dictionary from render_filters()
        
    Returns:
        Tuple of (query_parts_string, params_dict)
    """
    query_parts = []
    params = {}
    
    # Date range filter
    date_range = filters.get('date_range')
    date_type = filters.get('date_type', 'ETD').lower().replace(' ', '_')
    
    # Validate date_type
    date_column = ALLOWED_DATE_COLUMNS.get(date_type, 'etd')
    
    if date_range:
        if len(date_range) >= 1:
            query_parts.append(f"{date_column} >= :date_from")
            params['date_from'] = date_range[0]
        if len(date_range) >= 2:
            query_parts.append(f"{date_column} <= :date_to")
            params['date_to'] = date_range[1]
    
    # Helper function to add filter with exclusion logic
    def add_filter(column: str, values: List, exclude: bool, param_name: str):
        if values:
            operator = "NOT IN" if exclude else "IN"
            
            # Handle different column types
            if column in ['vendor_name', 'vendor_code']:
                # Parse "CODE - NAME" format
                codes = []
                names = []
                for val in values:
                    if ' - ' in val:
                        code, name = val.split(' - ', 1)
                        codes.append(code.strip())
                        names.append(name.strip())
                    else:
                        names.append(val)
                
                if codes and names:
                    query_parts.append(
                        f"(vendor_name {operator} :{param_name}_names OR vendor_code {operator} :{param_name}_codes)"
                    )
                    params[f'{param_name}_names'] = tuple(names)
                    params[f'{param_name}_codes'] = tuple(codes)
                elif names:
                    query_parts.append(f"vendor_name {operator} :{param_name}_names")
                    params[f'{param_name}_names'] = tuple(names)
                    
            elif column in ['legal_entity', 'legal_entity_code']:
                # Parse "CODE - NAME" format
                codes = []
                names = []
                for val in values:
                    if ' - ' in val:
                        code, name = val.split(' - ', 1)
                        codes.append(code.strip())
                        names.append(name.strip())
                    else:
                        names.append(val)
                
                if codes and names:
                    query_parts.append(
                        f"(legal_entity {operator} :{param_name}_names OR legal_entity_code {operator} :{param_name}_codes)"
                    )
                    params[f'{param_name}_names'] = tuple(names)
                    params[f'{param_name}_codes'] = tuple(codes)
                elif names:
                    query_parts.append(f"legal_entity {operator} :{param_name}_names")
                    params[f'{param_name}_names'] = tuple(names)
                    
            elif column in ['product_name', 'pt_code']:
                # Parse "PT_CODE | Name | Size (Brand)" format
                pt_codes = []
                product_names = []
                for val in values:
                    parts = val.split(' | ')
                    if len(parts) >= 2:
                        pt_code = parts[0].strip()
                        product_name = parts[1].strip()
                        pt_codes.append(pt_code)
                        product_names.append(product_name)
                
                if pt_codes and product_names:
                    query_parts.append(
                        f"(pt_code {operator} :{param_name}_codes OR product_name {operator} :{param_name}_names)"
                    )
                    params[f'{param_name}_codes'] = tuple(pt_codes)
                    params[f'{param_name}_names'] = tuple(product_names)
                elif pt_codes:
                    query_parts.append(f"pt_code {operator} :{param_name}_codes")
                    params[f'{param_name}_codes'] = tuple(pt_codes)
            else:
                # Simple column filter
                query_parts.append(f"{column} {operator} :{param_name}")
                params[param_name] = tuple(values)
    
    # Apply all filters
    add_filter('legal_entity', filters.get('legal_entities'), 
               filters.get('excl_legal_entities', False), 'legal_entities')
    
    add_filter('vendor_name', filters.get('vendors'),
               filters.get('excl_vendors', False), 'vendors')
    
    add_filter('po_number', filters.get('po_numbers'),
               filters.get('excl_po_numbers', False), 'po_numbers')
    
    add_filter('product_name', filters.get('products'),
               filters.get('excl_products', False), 'products')
    
    add_filter('brand', filters.get('brands'),
               filters.get('excl_brands', False), 'brands')
    
    add_filter('status', filters.get('status'),
               filters.get('excl_status', False), 'status')
    
    add_filter('payment_term', filters.get('payment_terms'),
               filters.get('excl_payment_terms', False), 'payment_terms')
    
    add_filter('vendor_location_type', filters.get('vendor_locations'),
               filters.get('excl_vendor_locations', False), 'vendor_locations')
    
    add_filter('created_by', filters.get('creators'),
               filters.get('excl_creators', False), 'creators')
    
    # Join all parts
    query_string = " AND ".join(query_parts) if query_parts else ""
    
    return query_string, params