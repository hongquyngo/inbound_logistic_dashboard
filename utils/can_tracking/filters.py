# utils/can_tracking/filters.py

"""
Filter UI Components and SQL Builder for CAN Tracking
Handles all filter rendering and SQL query building with exclusion logic
"""

import streamlit as st
from datetime import datetime, timedelta
from typing import Dict, Tuple, Any, List


def render_filters(filter_options: Dict[str, Any], default_date_range: Tuple) -> Dict[str, Any]:
    """
    Render all filter UI components for CAN tracking
    
    Args:
        filter_options: Dictionary with all available filter options
        default_date_range: Default date range tuple (min_date, max_date)
        
    Returns:
        Dictionary with all filter values and exclusion flags
    """
    with st.expander("🔍 Filters", expanded=True):
        # ROW 1: Date Range | Warehouse | Stock-in Status | CAN Status
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.markdown("**📅 Date Range**")
            arrival_date_range = st.date_input(
                "Arrival Date Range",
                value=default_date_range,
                label_visibility="collapsed"
            )
        
        with col2:
            st.markdown("**🏭 Warehouse**")
            warehouse_options = filter_options.get('warehouses', [])
            selected_warehouses = st.multiselect(
                "Warehouses",
                options=warehouse_options,
                default=None,
                placeholder="All warehouses",
                label_visibility="collapsed"
            )
        
        with col3:
            st.markdown("**📋 Stock-in Status**")
            stockin_status_options = filter_options.get('stocked_in_statuses', [])
            selected_stockin_status = st.multiselect(
                "Stock-in Status",
                options=stockin_status_options,
                default=['partially_stocked_in'],
                placeholder="All statuses",
                label_visibility="collapsed"
            )
        
        with col4:
            label_col, excl_col = st.columns([5, 1])
            with label_col:
                st.markdown("**📊 CAN Status**")
            with excl_col:
                excl_can_statuses = st.checkbox("Excl", key="excl_can_status")
            
            can_status_options = filter_options.get('can_statuses', [])
            selected_can_statuses = st.multiselect(
                "CAN Status",
                options=can_status_options,
                default=None,
                placeholder="All statuses",
                label_visibility="collapsed"
            )
        
        # ROW 2: Vendors | Vendor Location | Vendor Type
        col1, col2, col3 = st.columns(3)
        
        with col1:
            label_col, excl_col = st.columns([5, 1])
            with label_col:
                st.markdown("**🏢 Vendors**")
            with excl_col:
                excl_vendors = st.checkbox("Excl", key="excl_vendors")
            
            vendor_options = filter_options.get('vendors', [])
            selected_vendors = st.multiselect(
                "Vendors",
                options=vendor_options,
                default=None,
                placeholder="All vendors",
                label_visibility="collapsed"
            )
        
        with col2:
            st.markdown("**🌍 Vendor Location**")
            vendor_location_options = filter_options.get('vendor_location_types', [])
            selected_vendor_locations = st.multiselect(
                "Vendor Location",
                options=vendor_location_options,
                default=None,
                placeholder="All locations",
                label_visibility="collapsed"
            )
        
        with col3:
            st.markdown("**🪪 Vendor Type**")
            vendor_type_options = filter_options.get('vendor_types', [])
            selected_vendor_types = st.multiselect(
                "Vendor Types",
                options=vendor_type_options,
                default=None,
                placeholder="All types",
                label_visibility="collapsed"
            )
        
        # ROW 3: Consignees | Products | Brands
        col1, col2, col3 = st.columns(3)
        
        with col1:
            st.markdown("**📦 Consignees**")
            consignee_options = filter_options.get('consignees', [])
            selected_consignees = st.multiselect(
                "Consignees",
                options=consignee_options,
                default=None,
                placeholder="All consignees",
                label_visibility="collapsed"
            )
        
        with col2:
            label_col, excl_col = st.columns([5, 1])
            with label_col:
                st.markdown("**🏷️ Products**")
            with excl_col:
                excl_products = st.checkbox("Excl", key="excl_products")
            
            product_options = filter_options.get('products', [])
            selected_products = st.multiselect(
                "Products",
                options=product_options,
                default=None,
                placeholder="Search products...",
                label_visibility="collapsed"
            )
        
        with col3:
            label_col, excl_col = st.columns([5, 1])
            with label_col:
                st.markdown("**🎨 Brands**")
            with excl_col:
                excl_brands = st.checkbox("Excl", key="excl_brands")
            
            brand_options = filter_options.get('brands', [])
            selected_brands = st.multiselect(
                "Brands",
                options=brand_options,
                default=None,
                placeholder="All brands",
                label_visibility="collapsed"
            )
    
    return {
        'arrival_date_from': arrival_date_range[0] if len(arrival_date_range) > 0 else None,
        'arrival_date_to': arrival_date_range[1] if len(arrival_date_range) > 1 else arrival_date_range[0],
        'warehouses': selected_warehouses if selected_warehouses else None,
        'vendors': selected_vendors if selected_vendors else None,
        'excl_vendors': excl_vendors,
        'vendor_types': selected_vendor_types if selected_vendor_types else None,
        'vendor_locations': selected_vendor_locations if selected_vendor_locations else None,
        'consignees': selected_consignees if selected_consignees else None,
        'products': selected_products if selected_products else None,
        'excl_products': excl_products,
        'brands': selected_brands if selected_brands else None,
        'excl_brands': excl_brands,
        'can_statuses': selected_can_statuses if selected_can_statuses else None,
        'excl_can_statuses': excl_can_statuses,
        'stocked_in_statuses': selected_stockin_status if selected_stockin_status else None
    }

def build_sql_params(filters: Dict[str, Any]) -> Tuple[str, Dict[str, Any]]:
    query_parts = []
    params = {}
    
    # Date range filter
    if filters.get('arrival_date_from'):
        query_parts.append("arrival_date >= :date_from")
        params['date_from'] = filters['arrival_date_from']
    
    if filters.get('arrival_date_to'):
        query_parts.append("arrival_date <= :date_to")
        params['date_to'] = filters['arrival_date_to']
    
    def add_filter(column: str, values: List, exclude: bool, param_name: str):
        if not values:
            return
        operator = "NOT IN" if exclude else "IN"
        
        # Xử lý đặc biệt cho các cột ghép (Code - Name)
        if column in ['vendor', 'consignee']:
            names = []
            for val in values:
                if ' - ' in val:
                    # Lấy phần Name sau dấu ' - '
                    names.append(val.split(' - ', 1)[1].strip())
                else:
                    names.append(val.strip())
            
            if names:
                query_parts.append(f"{column} {operator} :{param_name}")
                params[param_name] = tuple(names)

        elif column == 'product_name':
            product_names = []
            for val in values:
                parts = val.split(' | ')
                if len(parts) >= 2:
                    product_names.append(parts[1].strip())
            if product_names:
                query_parts.append(f"product_name {operator} :{param_name}")
                params[param_name] = tuple(product_names)

        else:
            # Các cột đơn giản như vendor_location_type, warehouse_name...
            query_parts.append(f"{column} {operator} :{param_name}")
            params[param_name] = tuple(values)
    
    # Áp dụng các filter theo đúng tên cột trong SQL View
    add_filter('warehouse_name', filters.get('warehouses'), False, 'wh_names')
    add_filter('vendor', filters.get('vendors'), filters.get('excl_vendors'), 'v_names')
    add_filter('consignee', filters.get('consignees'), False, 'c_names')
    add_filter('product_name', filters.get('products'), filters.get('excl_products'), 'p_names')
    add_filter('brand', filters.get('brands'), filters.get('excl_brands'), 'b_names')
    add_filter('vendor_type', filters.get('vendor_types'), False, 'v_types')
    add_filter('vendor_location_type', filters.get('vendor_locations'), False, 'v_locs')
    add_filter('can_status', filters.get('can_statuses'), filters.get('excl_can_statuses'), 'can_stats')
    add_filter('stocked_in_status', filters.get('stocked_in_statuses'), False, 'stock_stats')
    
    return " AND ".join(query_parts) if query_parts else "", params

