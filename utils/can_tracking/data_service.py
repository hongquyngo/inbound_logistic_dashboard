# utils/can_tracking/data_service.py

"""
CAN Data Service - Data Access Layer

Handles all data operations for Container Arrival Note (CAN) tracking,
including loading, filtering, and providing filter options.

This service encapsulates database queries and data transformations,
keeping business logic separate from presentation layer.
"""

import pandas as pd
import streamlit as st
from sqlalchemy import text
from datetime import datetime, timedelta
from utils.db import get_db_engine
import logging

logger = logging.getLogger(__name__)


class CANDataService:
    """
    Service class for CAN data operations
    
    Provides methods for:
    - Loading CAN data from database
    - Getting filter options
    - Applying filters to dataframes
    - Getting date range defaults
    """
    
    def __init__(self):
        """Initialize service with database engine"""
        self.engine = get_db_engine()
    
    @st.cache_data(ttl=300)
    def load_can_data(_self, pending_only=True):
        """
        Load CAN data from can_tracking_full_view
        
        Args:
            pending_only (bool): If True, only load items with pending_quantity > 0
            
        Returns:
            pd.DataFrame: CAN data with all relevant columns
            
        Raises:
            Exception: If database query fails
        """
        try:
            # Base query from can_tracking_full_view
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
                
                -- Vendor info
                vendor,
                vendor_code,
                vendor_type,
                vendor_location_type,
                vendor_country_name,
                vendor_contact_name,
                vendor_contact_email,
                vendor_contact_phone,
                
                -- Consignee info
                consignee,
                consignee_code,
                
                -- Product info
                product_name,
                brand,
                package_size,
                pt_code,
                hs_code,
                standard_uom,
                
                -- Quantity & UOM
                buying_uom,
                uom_conversion,
                buying_quantity,
                standard_quantity,
                
                -- Cost info
                landed_cost,
                landed_cost_usd,
                
                -- Quantity flow
                total_arrived_quantity,
                arrival_quantity,
                total_stocked_in,
                pending_quantity,
                pending_value_usd,
                pending_percent,
                days_since_arrival,
                
                -- Status
                stocked_in_status,
                can_status
                
            FROM can_tracking_full_view
            WHERE 1=1
            """
            
            # Apply pending filter if requested
            if pending_only:
                query += " AND pending_quantity > 0"
            
            # Order by urgency and value
            query += " ORDER BY days_since_arrival DESC, pending_value_usd DESC"
            
            # Execute query
            with _self.engine.connect() as conn:
                df = pd.read_sql(text(query), conn)
            
            logger.info(f"Loaded {len(df)} CAN records (pending_only={pending_only})")
            return df
            
        except Exception as e:
            logger.error(f"Error loading CAN data: {e}", exc_info=True)
            raise Exception(f"Failed to load CAN data: {str(e)}")
    
    @st.cache_data(ttl=300)
    def get_filter_options(_self):
        """
        Get distinct values for all filter dropdowns
        
        Returns:
            dict: Dictionary containing lists of unique values for each filter:
                - vendors: List of vendor names
                - vendor_types: List of vendor types
                - vendor_location_types: List of vendor location types
                - consignees: List of consignee names
                - products: List of product names
                - can_statuses: List of CAN statuses
                - stocked_in_statuses: List of stock-in statuses
        """
        try:
            queries = {
                'vendors': """
                    SELECT DISTINCT vendor 
                    FROM can_tracking_full_view 
                    WHERE vendor IS NOT NULL 
                    ORDER BY vendor
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
                'consignees': """
                    SELECT DISTINCT consignee 
                    FROM can_tracking_full_view 
                    WHERE consignee IS NOT NULL 
                    ORDER BY consignee
                """,
                'products': """
                    SELECT DISTINCT product_name 
                    FROM can_tracking_full_view 
                    WHERE product_name IS NOT NULL 
                    ORDER BY product_name
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
            
            options = {}
            with _self.engine.connect() as conn:
                for key, query in queries.items():
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
                # Default to last 30 days if no data
                end_date = datetime.now().date()
                start_date = end_date - timedelta(days=30)
                return (start_date, end_date)
            
            # Ensure arrival_date is datetime
            df['arrival_date'] = pd.to_datetime(df['arrival_date'])
            
            # Get min and max from data
            min_date = df['arrival_date'].min().date()
            max_date = df['arrival_date'].max().date()
            
            return (min_date, max_date)
            
        except Exception as e:
            logger.warning(f"Error getting date range defaults: {e}")
            # Fallback to last 30 days
            end_date = datetime.now().date()
            start_date = end_date - timedelta(days=30)
            return (start_date, end_date)
    
    def apply_filters(self, df, filters):
        """
        Apply filters to CAN dataframe
        
        Args:
            df (pd.DataFrame): Source CAN dataframe
            filters (dict): Filter parameters:
                - arrival_date_from (datetime.date)
                - arrival_date_to (datetime.date)
                - vendors (list)
                - vendor_types (list)
                - vendor_location_types (list)
                - consignees (list)
                - products (list)
                - can_statuses (list)
                - stocked_in_statuses (list)
                
        Returns:
            pd.DataFrame: Filtered dataframe
        """
        try:
            if df is None or df.empty:
                return df
            
            # Start with all data
            filtered_df = df.copy()
            
            # Ensure arrival_date is datetime
            filtered_df['arrival_date'] = pd.to_datetime(filtered_df['arrival_date'])
            
            # Apply date range filter
            if filters.get('arrival_date_from'):
                filtered_df = filtered_df[
                    filtered_df['arrival_date'].dt.date >= filters['arrival_date_from']
                ]
            
            if filters.get('arrival_date_to'):
                filtered_df = filtered_df[
                    filtered_df['arrival_date'].dt.date <= filters['arrival_date_to']
                ]
            
            # Apply vendor filters
            if filters.get('vendors'):
                filtered_df = filtered_df[filtered_df['vendor'].isin(filters['vendors'])]
            
            if filters.get('vendor_types'):
                filtered_df = filtered_df[
                    filtered_df['vendor_type'].isin(filters['vendor_types'])
                ]
            
            if filters.get('vendor_location_types'):
                filtered_df = filtered_df[
                    filtered_df['vendor_location_type'].isin(filters['vendor_location_types'])
                ]
            
            # Apply consignee filter
            if filters.get('consignees'):
                filtered_df = filtered_df[
                    filtered_df['consignee'].isin(filters['consignees'])
                ]
            
            # Apply product filter
            if filters.get('products'):
                filtered_df = filtered_df[
                    filtered_df['product_name'].isin(filters['products'])
                ]
            
            # Apply status filters
            if filters.get('can_statuses'):
                filtered_df = filtered_df[
                    filtered_df['can_status'].isin(filters['can_statuses'])
                ]
            
            if filters.get('stocked_in_statuses'):
                filtered_df = filtered_df[
                    filtered_df['stocked_in_status'].isin(filters['stocked_in_statuses'])
                ]
            
            logger.info(
                f"Applied filters: {len(df)} -> {len(filtered_df)} records "
                f"({len(filtered_df)/len(df)*100:.1f}% retained)"
            )
            
            return filtered_df
            
        except Exception as e:
            logger.error(f"Error applying filters: {e}", exc_info=True)
            # Return original dataframe if filtering fails
            return df