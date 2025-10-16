# utils/can_tracking/data_service.py

"""
CAN Data Service - Clean Version
Handles all database operations for CAN tracking with proper error handling
"""

import pandas as pd
import streamlit as st
from sqlalchemy import text
from datetime import datetime, timedelta, date
import logging
from typing import Dict, List, Optional, Any, Tuple

logger = logging.getLogger(__name__)


class CANDataService:
    """Handles all database operations for CAN tracking"""
    
    def __init__(self, engine=None):
        from utils.db import get_db_engine
        self.engine = engine or get_db_engine()
    
    @st.cache_data(ttl=3600)
    def get_filter_options(_self) -> Dict[str, Any]:
        """
        Get all filter options for dropdowns
        Returns: dict with all filter options
        """
        try:
            queries = {
                'warehouses': """
                    SELECT DISTINCT warehouse_name
                    FROM can_tracking_full_view
                    WHERE warehouse_name IS NOT NULL
                    ORDER BY warehouse_name
                """,
                'vendors': """
                    SELECT DISTINCT 
                        CONCAT(vendor_code, ' - ', vendor) as display_value
                    FROM can_tracking_full_view
                    WHERE vendor IS NOT NULL 
                        AND vendor_code IS NOT NULL
                    ORDER BY vendor
                """,
                'consignees': """
                    SELECT DISTINCT 
                        CONCAT(consignee_code, ' - ', consignee) as display_value
                    FROM can_tracking_full_view
                    WHERE consignee IS NOT NULL 
                        AND consignee_code IS NOT NULL
                    ORDER BY consignee
                """,
                'products': """
                    SELECT DISTINCT 
                        CONCAT(
                            pt_code, ' | ', 
                            product_name, ' | ', 
                            COALESCE(package_size, 'N/A'), ' (',
                            COALESCE(brand, 'No Brand'), ')'
                        ) as display_value
                    FROM can_tracking_full_view
                    WHERE pt_code IS NOT NULL 
                        AND product_name IS NOT NULL
                    ORDER BY pt_code
                """,
                'brands': """
                    SELECT DISTINCT brand
                    FROM can_tracking_full_view
                    WHERE brand IS NOT NULL
                    ORDER BY brand
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
                """,
                'date_ranges': """
                    SELECT 
                        MIN(arrival_date) as min_arrival_date,
                        MAX(arrival_date) as max_arrival_date
                    FROM can_tracking_full_view
                    WHERE arrival_date IS NOT NULL
                """
            }
            
            options = {}
            with _self.engine.connect() as conn:
                for key, query in queries.items():
                    try:
                        if key == 'date_ranges':
                            result = conn.execute(text(query)).fetchone()
                            if result:
                                options[key] = {
                                    'min_arrival_date': result[0],
                                    'max_arrival_date': result[1]
                                }
                            else:
                                options[key] = {}
                        else:
                            result = conn.execute(text(query))
                            options[key] = [row[0] for row in result]
                    except Exception as e:
                        logger.warning(f"Could not get {key} options: {e}")
                        options[key] = {} if key == 'date_ranges' else []
            
            return options
            
        except Exception as e:
            logger.error(f"Error getting filter options: {e}", exc_info=True)
            return {
                'warehouses': [],
                'vendors': [],
                'consignees': [],
                'products': [],
                'brands': [],
                'vendor_types': [],
                'vendor_location_types': [],
                'can_statuses': [],
                'stocked_in_statuses': [],
                'date_ranges': {}
            }
    
    def get_date_range_defaults(self, filter_options: Dict[str, Any]) -> Tuple[date, date]:
        """
        Get default date range based on filter options
        
        Args:
            filter_options: Filter options dict
            
        Returns:
            tuple: (min_date, max_date)
        """
        try:
            date_ranges = filter_options.get('date_ranges', {})
            
            # Check if dict is empty or invalid
            if not date_ranges or not isinstance(date_ranges, dict):
                logger.warning("date_ranges is empty or not a dict")
                end_date = datetime.now().date()
                start_date = end_date - timedelta(days=30)
                return (start_date, end_date)
            
            min_date = date_ranges.get('min_arrival_date')
            max_date = date_ranges.get('max_arrival_date')
            
            if min_date and max_date:
                return (min_date, max_date)
            else:
                end_date = datetime.now().date()
                start_date = end_date - timedelta(days=30)
                return (start_date, end_date)
                
        except Exception as e:
            logger.error(f"Error getting date range defaults: {e}", exc_info=True)
            end_date = datetime.now().date()
            start_date = end_date - timedelta(days=30)
            return (start_date, end_date)
    
    def load_can_data(self, query_parts: str, params: Dict[str, Any]) -> pd.DataFrame:
        """
        Load CAN data with filters applied in SQL
        
        Args:
            query_parts: WHERE clause conditions
            params: SQL parameters
            
        Returns:
            DataFrame with CAN data
        """
        try:
            base_query = """
            SELECT 
                arrival_note_number,
                creator,
                can_line_id,
                arrival_date,
                
                po_number,
                external_ref_number,
                po_type,
                payment_term,
                
                warehouse_id,
                warehouse_name,
                warehouse_address,
                warehouse_zipcode,
                warehouse_company_name,
                warehouse_country_name,
                warehouse_state_name,
                
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
                
                consignee,
                consignee_code,
                consignee_street,
                consignee_zip_code,
                consignee_state_province,
                consignee_country_name,
                buyer_contact_name,
                buyer_contact_email,
                buyer_contact_phone,
                
                ship_to_company_name,
                ship_to_contact_name,
                ship_to_contact_email,
                bill_to_company_name,
                bill_to_contact_name,
                bill_to_contact_email,
                
                product_name,
                brand,
                package_size,
                pt_code,
                hs_code,
                shelf_life,
                standard_uom,
                
                buying_uom,
                uom_conversion,
                buying_quantity,
                standard_quantity,
                
                buying_unit_cost,
                standard_unit_cost,
                vat_gst,
                landed_cost,
                landed_cost_usd,
                usd_landed_cost_currency_exchange_rate,
                
                total_arrived_quantity,
                arrival_quantity,
                total_stocked_in,
                pending_quantity,
                pending_value_usd,
                pending_percent,
                days_since_arrival,
                days_pending,
                
                total_invoiced_quantity,
                total_standard_invoiced_quantity,
                invoice_count,
                invoiced_percent,
                invoice_status,
                uninvoiced_quantity,
                
                stocked_in_status,
                can_status,
                
                po_line_total_arrived_qty,
                po_line_total_invoiced_buying_qty,
                po_line_pending_invoiced_qty,
                po_line_pending_arrival_qty,
                po_line_status,
                po_line_is_over_delivered,
                po_line_is_over_invoiced,
                po_line_arrival_completion_percent,
                po_line_invoice_completion_percent
                
            FROM can_tracking_full_view
            WHERE 1=1
            """
            
            if query_parts:
                base_query += f" AND {query_parts}"
            
            base_query += """
            ORDER BY 
                days_since_arrival DESC,
                pending_value_usd DESC,
                can_line_id ASC
            """
            
            with self.engine.connect() as conn:
                df = pd.read_sql(text(base_query), conn, params=params)
            
            logger.info(f"Loaded {len(df)} CAN records with SQL filtering")
            return df
            
        except Exception as e:
            logger.error(f"Error loading CAN data: {e}", exc_info=True)
            st.error(f"Failed to load CAN data: {str(e)}")
            return pd.DataFrame()
    
    def update_can_details(
        self,
        arrival_note_number: str,
        adjust_arrival_date: date,
        new_status: str,
        new_warehouse_id: int,
        reason: Optional[str] = None
    ) -> bool:
        """
        Update CAN arrival date, status, and warehouse
        
        Args:
            arrival_note_number: CAN number
            adjust_arrival_date: New adjusted arrival date
            new_status: New CAN status
            new_warehouse_id: New warehouse ID
            reason: Reason for the change
            
        Returns:
            bool: True if successful
        """
        try:
            user_keycloak_id = st.session_state.get('user_keycloak_id')
            user_email = st.session_state.get('user_email', 'unknown')
            
            if not user_keycloak_id:
                logger.error("No keycloak_id found in session state")
                return False
            
            with self.engine.begin() as conn:
                update_query = text("""
                    UPDATE arrivals
                    SET 
                        adjust_arrival_date = :adjust_arrival_date,
                        status = :new_status,
                        warehouse_id = :new_warehouse_id,
                        arrival_date_update_count = arrival_date_update_count + 1,
                        updated_by = :updated_by
                    WHERE 
                        arrival_note_number = :arrival_note_number
                        AND delete_flag = 0
                """)
                
                result = conn.execute(
                    update_query,
                    {
                        'arrival_note_number': arrival_note_number,
                        'adjust_arrival_date': adjust_arrival_date,
                        'new_status': new_status,
                        'new_warehouse_id': new_warehouse_id,
                        'updated_by': user_keycloak_id
                    }
                )
                
                rows_affected = result.rowcount
                
                if rows_affected == 0:
                    logger.warning(f"No CAN found with number {arrival_note_number}")
                    return False
                
                logger.info(
                    f"Updated CAN {arrival_note_number}: "
                    f"adjust_arrival_date={adjust_arrival_date}, "
                    f"status={new_status}, "
                    f"warehouse_id={new_warehouse_id}, "
                    f"Reason='{reason}', User={user_email}"
                )
                
                return True
            
        except Exception as e:
            logger.error(f"Error updating CAN: {e}", exc_info=True)
            return False
    
    def get_warehouse_options(self) -> List[Dict[str, Any]]:
        """Get all warehouse options for dropdown"""
        try:
            query = text("""
                SELECT 
                    id,
                    name
                FROM warehouses
                WHERE delete_flag = 0
                ORDER BY name
            """)
            
            with self.engine.connect() as conn:
                result = conn.execute(query)
                warehouses = [{'id': row[0], 'name': row[1]} for row in result]
            
            return warehouses
            
        except Exception as e:
            logger.error(f"Error getting warehouse options: {e}", exc_info=True)
            return []
    
    def get_warehouse_name(self, warehouse_id: int) -> str:
        """Get warehouse name by ID"""
        try:
            query = text("""
                SELECT name
                FROM warehouses
                WHERE id = :warehouse_id
                AND delete_flag = 0
                LIMIT 1
            """)
            
            with self.engine.connect() as conn:
                result = conn.execute(query, {'warehouse_id': warehouse_id}).fetchone()
                if result:
                    return result[0]
            
            return 'N/A'
            
        except Exception as e:
            logger.error(f"Error getting warehouse name: {e}", exc_info=True)
            return 'N/A'