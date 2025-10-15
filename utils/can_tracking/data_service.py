# utils/can_tracking/data_service.py

"""
CAN Data Service - Data Access Layer

Handles all data operations for Container Arrival Note (CAN) tracking,
including loading, filtering, and providing filter options.
"""

import pandas as pd
import streamlit as st
from sqlalchemy import text
from datetime import datetime, timedelta
from utils.db import get_db_engine
import logging

logger = logging.getLogger(__name__)


class CANDataService:
    """Service class for CAN data operations"""
    
    def __init__(self):
        """Initialize service with database engine"""
        self.engine = get_db_engine()
    
    @st.cache_data(ttl=300)
    def load_can_data(_self):
        """
        Load ALL CAN data from can_tracking_full_view
        No pending_only parameter - always load all data
        
        Returns:
            pd.DataFrame: CAN data with all relevant columns
        """
        try:
            query = """
            SELECT 
                arrival_note_number,
                creator,
                can_line_id,
                arrival_date,
                
                -- PO info
                po_number,
                external_ref_number,
                po_type,
                payment_term,

                    -- Warehouse info ✅ (ĐÃ THÊM)
                warehouse_id,
                warehouse_name,
                warehouse_address,
                warehouse_zipcode,
                warehouse_company_name,
                warehouse_country_name,
                warehouse_state_name,
                
                -- Vendor info
                vendor,
                vendor_code,
                vendor_type,
                vendor_location_type,
                vendor_country_name,
                vendor_street,
                vendor_zip_code,
                vendor_state_province,
                vendor_contact_name,
                vendor_contact_email,
                vendor_contact_phone,
                
                -- Consignee info
                consignee,
                consignee_code,
                consignee_street,
                consignee_zip_code,
                consignee_state_province,
                consignee_country_name,
                buyer_contact_name,
                buyer_contact_email,
                buyer_contact_phone,
                
                -- Ship To & Bill To
                ship_to_company_name,
                ship_to_contact_name,
                ship_to_contact_email,
                bill_to_company_name,
                bill_to_contact_name,
                bill_to_contact_email,
                
                -- Product info
                product_name,
                brand,
                package_size,
                pt_code,
                hs_code,
                shelf_life,
                standard_uom,
                
                -- Quantity & UOM
                buying_uom,
                uom_conversion,
                buying_quantity,
                standard_quantity,
                
                -- Cost info
                buying_unit_cost,
                standard_unit_cost,
                vat_gst,
                landed_cost,
                landed_cost_usd,
                usd_landed_cost_currency_exchange_rate,
                
                -- Quantity flow
                total_arrived_quantity,
                arrival_quantity,
                total_stocked_in,
                pending_quantity,
                pending_value_usd,
                pending_percent,
                days_since_arrival,
                days_pending,
                
                -- Invoice info
                total_invoiced_quantity,
                total_standard_invoiced_quantity,
                invoice_count,
                invoiced_percent,
                invoice_status,
                uninvoiced_quantity,
                
                -- Status
                stocked_in_status,
                can_status,
                
                -- PO Line Status
                po_line_total_arrived_qty,
                po_line_total_invoiced_buying_qty,
                po_line_total_invoiced_standard_qty,
                po_line_pending_invoiced_qty,
                po_line_pending_arrival_qty,
                po_line_status,
                po_line_is_over_delivered,
                po_line_is_over_invoiced,
                po_line_arrival_completion_percent,
                po_line_invoice_completion_percent
                
            FROM can_tracking_full_view
            ORDER BY days_since_arrival DESC, pending_value_usd DESC
            """
            
            with _self.engine.connect() as conn:
                df = pd.read_sql(text(query), conn)
            
            logger.info(f"Loaded {len(df)} CAN records")
            return df
            
        except Exception as e:
            logger.error(f"Error loading CAN data: {e}", exc_info=True)
            raise Exception(f"Failed to load CAN data: {str(e)}")
    
    @st.cache_data(ttl=300)
    def get_filter_options(_self):
        """
        Get distinct values for all filter dropdowns with formatted display
        
        Returns:
            dict: Dictionary with formatted filter options
        """
        try:
            options = {}
            
            with _self.engine.connect() as conn:
                # Vendors (formatted as "CODE - NAME")
                vendor_query = """
                    SELECT DISTINCT 
                        vendor_code,
                        vendor
                    FROM can_tracking_full_view 
                    WHERE vendor IS NOT NULL 
                      AND vendor_code IS NOT NULL
                    ORDER BY vendor
                """
                result = conn.execute(text(vendor_query))
                vendors = [f"{row[0]} - {row[1]}" for row in result]
                options['vendors'] = vendors
                
                # Consignees (formatted as "CODE - NAME")
                consignee_query = """
                    SELECT DISTINCT 
                        consignee_code,
                        consignee
                    FROM can_tracking_full_view 
                    WHERE consignee IS NOT NULL 
                      AND consignee_code IS NOT NULL
                    ORDER BY consignee
                """
                result = conn.execute(text(consignee_query))
                consignees = [f"{row[0]} - {row[1]}" for row in result]
                options['consignees'] = consignees
                
                # Products (formatted as "PT_CODE | Name | Size (Brand)")
                product_query = """
                    SELECT DISTINCT 
                        pt_code,
                        product_name,
                        package_size,
                        brand
                    FROM can_tracking_full_view 
                    WHERE product_name IS NOT NULL 
                      AND pt_code IS NOT NULL
                    ORDER BY pt_code
                """
                result = conn.execute(text(product_query))
                products = []
                for row in result:
                    pt_code, name, size, brand = row
                    size_str = f" | {size}" if size else ""
                    brand_str = f" ({brand})" if brand else ""
                    products.append(f"{pt_code} | {name}{size_str}{brand_str}")
                options['products'] = products
                
                # Simple filters
                simple_filters = {
                    'warehouses': """
                        SELECT DISTINCT warehouse_name 
                        FROM can_tracking_full_view 
                        WHERE warehouse_name IS NOT NULL 
                        ORDER BY warehouse_name
                    """,
                    'vendor_types': """
                        SELECT DISTINCT vendor_type 
                        FROM can_tracking_full_view 
                        WHERE vendor_type IS NOT NULL 
                        ORDER BY vendor_type
                    """,
                    'vendor_location_types': """
                        SELECT DISTINCT vendor_location_type 
                        FROM can_tracking_full_view 
                        WHERE vendor_location_type IS NOT NULL 
                        ORDER BY vendor_location_type
                    """,
                    'brands': """
                        SELECT DISTINCT brand 
                        FROM can_tracking_full_view 
                        WHERE brand IS NOT NULL 
                        ORDER BY brand
                    """,
                    'can_statuses': """
                        SELECT DISTINCT can_status 
                        FROM can_tracking_full_view 
                        WHERE can_status IS NOT NULL 
                        ORDER BY can_status
                    """,
                    'stocked_in_statuses': """
                        SELECT DISTINCT stocked_in_status 
                        FROM can_tracking_full_view 
                        WHERE stocked_in_status IS NOT NULL 
                        ORDER BY stocked_in_status
                    """
                }
                
                for key, query in simple_filters.items():
                    try:
                        result = conn.execute(text(query))
                        options[key] = [row[0] for row in result]
                    except Exception as e:
                        logger.warning(f"Could not get {key} options: {e}")
                        options[key] = []
            
            return options
            
        except Exception as e:
            logger.error(f"Error getting filter options: {e}", exc_info=True)
            return {}
    
    def get_date_range_defaults(self, df):
        """
        Get default date range based on data
        
        Args:
            df (pd.DataFrame): CAN dataframe
            
        Returns:
            tuple: (min_date, max_date) as datetime.date objects
        """
        try:
            if df is None or df.empty:
                end_date = datetime.now().date()
                start_date = end_date - timedelta(days=30)
                return (start_date, end_date)
            
            df['arrival_date'] = pd.to_datetime(df['arrival_date'])
            min_date = df['arrival_date'].min().date()
            max_date = df['arrival_date'].max().date()
            
            return (min_date, max_date)
            
        except Exception as e:
            logger.warning(f"Error getting date range defaults: {e}")
            end_date = datetime.now().date()
            start_date = end_date - timedelta(days=30)
            return (start_date, end_date)
    
    def apply_filters(self, df, filters):
        """
        Apply filters to CAN dataframe with exclusion logic
        
        Args:
            df (pd.DataFrame): Source CAN dataframe
            filters (dict): Filter parameters with exclusion flags
                
        Returns:
            pd.DataFrame: Filtered dataframe
        """
        try:
            if df is None or df.empty:
                return df
            
            filtered_df = df.copy()
            filtered_df['arrival_date'] = pd.to_datetime(filtered_df['arrival_date'])
            
            # Date range filter
            if filters.get('arrival_date_from'):
                filtered_df = filtered_df[
                    filtered_df['arrival_date'].dt.date >= filters['arrival_date_from']
                ]
            
            if filters.get('arrival_date_to'):
                filtered_df = filtered_df[
                    filtered_df['arrival_date'].dt.date <= filters['arrival_date_to']
                ]
            
            # Helper function for exclusion logic
            def apply_filter_with_exclusion(df, column, values, exclude=False, parse_format=None):
                if not values:
                    return df
                
                if parse_format == 'code_name':
                    # Parse "CODE - NAME" format
                    codes = []
                    names = []
                    for val in values:
                        if ' - ' in val:
                            code, name = val.split(' - ', 1)
                            codes.append(code.strip())
                            names.append(name.strip())
                    
                    if exclude:
                        if codes and names:
                            mask = ~(df[f'{column}_code'].isin(codes) | df[column].isin(names))
                        else:
                            mask = ~df[column].isin(names)
                    else:
                        if codes and names:
                            mask = df[f'{column}_code'].isin(codes) | df[column].isin(names)
                        else:
                            mask = df[column].isin(names)
                    
                    return df[mask]
                
                elif parse_format == 'product':
                    # Parse "PT_CODE | Name | Size (Brand)" format
                    pt_codes = []
                    product_names = []
                    for val in values:
                        parts = val.split(' | ')
                        if len(parts) >= 2:
                            pt_codes.append(parts[0].strip())
                            product_names.append(parts[1].strip())
                    
                    if exclude:
                        mask = ~(df['pt_code'].isin(pt_codes) | df['product_name'].isin(product_names))
                    else:
                        mask = df['pt_code'].isin(pt_codes) | df['product_name'].isin(product_names)
                    
                    return df[mask]
                
                else:
                    # Simple filter
                    if exclude:
                        return df[~df[column].isin(values)]
                    else:
                        return df[df[column].isin(values)]
            
            # Apply vendor filter
            if filters.get('vendors'):
                filtered_df = apply_filter_with_exclusion(
                    filtered_df, 
                    'vendor', 
                    filters['vendors'],
                    filters.get('excl_vendors', False),
                    parse_format='code_name'
                )
            
            # Apply consignee filter
            if filters.get('consignees'):
                filtered_df = apply_filter_with_exclusion(
                    filtered_df,
                    'consignee',
                    filters['consignees'],
                    filters.get('excl_consignees', False),
                    parse_format='code_name'
                )
            
            # Apply product filter
            if filters.get('products'):
                filtered_df = apply_filter_with_exclusion(
                    filtered_df,
                    'product_name',
                    filters['products'],
                    filters.get('excl_products', False),
                    parse_format='product'
                )
            
            # Apply simple filters with exclusion
            simple_filters = [
                ('warehouse_name', 'warehouses', None),  # Warehouse filter (no exclusion)
                ('vendor_type', 'vendor_types', 'excl_vendor_types'),
                ('vendor_location_type', 'vendor_locations', None),  # No exclusion for vendor location
                ('brand', 'brands', 'excl_brands'),  # Brand with exclusion
                ('can_status', 'can_statuses', 'excl_can_statuses'),  # CAN status with exclusion
                ('stocked_in_status', 'stocked_in_statuses', None)  # No exclusion for stock-in status
            ]
            
            for column, filter_key, excl_key in simple_filters:
                if filters.get(filter_key):
                    exclude = filters.get(excl_key, False) if excl_key else False
                    filtered_df = apply_filter_with_exclusion(
                        filtered_df,
                        column,
                        filters[filter_key],
                        exclude
                    )
            
            logger.info(
                f"Applied filters: {len(df)} -> {len(filtered_df)} records "
                f"({len(filtered_df)/len(df)*100:.1f}% retained)"
            )
            
            return filtered_df
            
        except Exception as e:
            logger.error(f"Error applying filters: {e}", exc_info=True)
            return df