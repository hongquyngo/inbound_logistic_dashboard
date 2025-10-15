"""
Data Service for PO Tracking - Updated with Sorting
Handles all database operations with proper SQL parameterization
"""

import pandas as pd
import streamlit as st
from sqlalchemy import text
from datetime import datetime, timedelta, date
import logging
from typing import Dict, List, Optional, Any

logger = logging.getLogger(__name__)

# Constants for SQL injection prevention
ALLOWED_DATE_COLUMNS = {
    'po_date': 'po_date',
    'etd': 'etd',
    'eta': 'eta'
}


class PODataService:
    """Handles all database operations for PO tracking"""
    
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
                'legal_entities': """
                    SELECT DISTINCT 
                        CONCAT(legal_entity_code, ' - ', legal_entity) as display_value
                    FROM purchase_order_full_view 
                    WHERE legal_entity IS NOT NULL 
                        AND legal_entity_code IS NOT NULL
                    ORDER BY legal_entity_code
                """,
                'vendors': """
                    SELECT DISTINCT
                        CONCAT(vendor_code, ' - ', vendor_name) as display_value
                    FROM purchase_order_full_view 
                    WHERE vendor_name IS NOT NULL 
                        AND vendor_code IS NOT NULL
                    ORDER BY vendor_name
                """,
                'products': """
                    SELECT DISTINCT 
                        CONCAT(
                            pt_code, ' | ', 
                            product_name, ' | ', 
                            COALESCE(package_size, 'N/A'), ' (',
                            COALESCE(brand, 'No Brand'), ')'
                        ) as display_value
                    FROM purchase_order_full_view 
                    WHERE pt_code IS NOT NULL 
                        AND product_name IS NOT NULL
                    ORDER BY pt_code
                """,
                'brands': """
                    SELECT DISTINCT brand 
                    FROM purchase_order_full_view 
                    WHERE brand IS NOT NULL 
                    ORDER BY brand
                """,
                'creators': """
                    SELECT DISTINCT created_by
                    FROM purchase_order_full_view 
                    WHERE created_by IS NOT NULL 
                    ORDER BY created_by
                """,
                'payment_terms': """
                    SELECT DISTINCT payment_term 
                    FROM purchase_order_full_view 
                    WHERE payment_term IS NOT NULL 
                    ORDER BY payment_term
                """,
                'po_statuses': """
                    SELECT DISTINCT status 
                    FROM purchase_order_full_view 
                    WHERE status IS NOT NULL 
                    ORDER BY 
                        CASE status
                            WHEN 'PENDING' THEN 1
                            WHEN 'IN_PROCESS' THEN 2
                            WHEN 'PENDING_INVOICING' THEN 3
                            WHEN 'PENDING_RECEIPT' THEN 4
                            WHEN 'COMPLETED' THEN 5
                            WHEN 'OVER_DELIVERED' THEN 6
                            ELSE 7
                        END
                """,
                'vendor_types': """
                    SELECT DISTINCT vendor_type 
                    FROM purchase_order_full_view 
                    WHERE vendor_type IS NOT NULL 
                    ORDER BY vendor_type
                """,
                'vendor_location_types': """
                    SELECT DISTINCT vendor_location_type 
                    FROM purchase_order_full_view 
                    WHERE vendor_location_type IS NOT NULL 
                    ORDER BY vendor_location_type
                """,
                'date_ranges': """
                    SELECT 
                        MIN(po_date) as min_po_date,
                        MAX(po_date) as max_po_date,
                        MIN(etd) as min_etd,
                        MAX(etd) as max_etd,
                        MIN(eta) as min_eta,
                        MAX(eta) as max_eta
                    FROM purchase_order_full_view
                    WHERE po_date IS NOT NULL
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
                                    'min_po_date': result[0],
                                    'max_po_date': result[1],
                                    'min_etd': result[2],
                                    'max_etd': result[3],
                                    'min_eta': result[4],
                                    'max_eta': result[5]
                                }
                        else:
                            result = conn.execute(text(query))
                            options[key] = [row[0] for row in result]
                    except Exception as e:
                        logger.warning(f"Could not get {key} options: {e}")
                        options[key] = {} if key == 'date_ranges' else []
            
            return options
            
        except Exception as e:
            logger.error(f"Error getting filter options: {e}", exc_info=True)
            st.error("⚠️ Failed to load filter options. Please refresh the page.")
            return {
                'legal_entities': [],
                'vendors': [],
                'products': [],
                'brands': [],
                'creators': [],
                'payment_terms': [],
                'po_statuses': [],
                'vendor_types': [],
                'vendor_location_types': [],
                'date_ranges': {}
            }
    
    @st.cache_data(ttl=300)
    def load_po_data(_self, query_parts: str, params: Dict[str, Any]) -> pd.DataFrame:
        """
        Load PO data with filters applied in SQL
        Sorted by: vendor_name ASC, po_date ASC (oldest first)
        
        Args:
            query_parts: WHERE clause conditions
            params: SQL parameters
            
        Returns:
            DataFrame with PO data
        """
        try:
            base_query = """
            SELECT 
                po_line_id,
                po_number,
                external_ref_number,
                po_date,
                created_by,
                
                -- Vendor info
                vendor_name,
                vendor_code,
                vendor_type,
                vendor_location_type,
                vendor_country_name,
                vendor_contact_name,
                vendor_contact_email,
                vendor_contact_phone,
                
                -- Legal entity
                legal_entity,
                legal_entity_code,
                
                -- Ship/Bill to
                ship_to_company_name,
                ship_to_contact_name,
                bill_to_company_name,
                
                -- Product info
                product_name,
                pt_code,
                brand,
                package_size,
                hs_code,
                vendor_product_code,
                shelf_life,
                storage_condition,
                
                -- Quantities & UOM
                standard_uom,
                buying_uom,
                uom_conversion,
                moq,
                spq,
                buying_quantity,
                standard_quantity,
                
                -- Pricing
                purchase_unit_cost,
                standard_unit_cost,
                total_amount,
                currency,
                usd_exchange_rate,
                total_amount_usd,
                
                -- Status tracking
                total_standard_arrived_quantity,
                total_buying_invoiced_quantity,
                pending_standard_arrival_quantity,
                pending_buying_invoiced_quantity,
                
                -- Financial
                invoiced_amount_usd,
                outstanding_invoiced_amount_usd,
                arrival_amount_usd,
                outstanding_arrival_amount_usd,
                
                -- Dates
                etd,
                eta,
                last_invoice_date,
                po_line_created_date,
                
                -- Terms
                payment_term,
                trade_term,
                vat_gst_percent,
                
                -- PO info
                po_notes,
                po_type,
                
                -- Status
                status,
                is_over_delivered,
                is_over_invoiced,
                has_cancellation,
                arrival_completion_percent,
                invoice_completion_percent,
                
                -- CI numbers
                ci_numbers
                
            FROM purchase_order_full_view
            WHERE 1=1
            """
            
            # Add filter conditions
            if query_parts:
                base_query += f" AND {query_parts}"
            
            # ✅ NEW: Order by vendor_name ASC, po_date ASC (oldest first)
            base_query += """
            ORDER BY 
                vendor_name ASC,
                po_date ASC,
                po_line_id ASC
            """
            
            # Execute query
            with _self.engine.connect() as conn:
                df = pd.read_sql(text(base_query), conn, params=params)
            
            logger.info(f"Loaded {len(df)} PO records (sorted by vendor, po_date)")
            return df
            
        except Exception as e:
            logger.error(f"Error loading PO data: {e}", exc_info=True)
            st.error(f"Failed to load purchase order data: {str(e)}")
            return pd.DataFrame()
    
    def update_po_line_dates(
        self, 
        po_line_id: int, 
        adjust_etd: date, 
        adjust_eta: date,
        reason: Optional[str] = None
    ) -> bool:
        """
        Update ETD/ETA dates for a PO line and update the PO header
        
        Args:
            po_line_id: PO line ID to update
            adjust_etd: New adjusted ETD
            adjust_eta: New adjusted ETA
            reason: Reason for the change (for logging)
            
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            # Get current user's keycloak_id from session state
            user_keycloak_id = st.session_state.get('user_keycloak_id')
            user_email = st.session_state.get('user_email', 'unknown')
            
            if not user_keycloak_id:
                logger.error("No keycloak_id found in session state")
                return False
            
            # Use transaction to update both tables atomically
            with self.engine.begin() as conn:
                # Step 1: Update PO line dates and counters
                update_line_query = text("""
                    UPDATE product_purchase_orders 
                    SET 
                        adjust_etd = :adjust_etd,
                        adjust_eta = :adjust_eta,
                        etd_update_count = etd_update_count + 1,
                        eta_update_count = eta_update_count + 1
                    WHERE 
                        id = :po_line_id
                        AND delete_flag = 0
                """)
                
                result = conn.execute(
                    update_line_query,
                    {
                        'po_line_id': po_line_id,
                        'adjust_etd': adjust_etd,
                        'adjust_eta': adjust_eta
                    }
                )
                
                rows_affected = result.rowcount
                
                if rows_affected == 0:
                    logger.warning(f"No PO line found with id {po_line_id}")
                    return False
                
                # Step 2: Update PO header with updated_by (keycloak_id) and updated_date
                update_header_query = text("""
                    UPDATE purchase_orders po
                    INNER JOIN product_purchase_orders ppo 
                        ON po.id = ppo.purchase_order_id
                    SET 
                        po.updated_by = :updated_by,
                        po.updated_date = NOW()
                    WHERE 
                        ppo.id = :po_line_id
                        AND po.delete_flag = 0
                """)
                
                conn.execute(
                    update_header_query,
                    {
                        'po_line_id': po_line_id,
                        'updated_by': user_keycloak_id
                    }
                )
                
                # Log the change with user info and reason
                logger.info(
                    f"Updated PO line {po_line_id} dates: "
                    f"adjust_etd={adjust_etd}, adjust_eta={adjust_eta}, "
                    f"Reason='{reason}', User={user_email} (keycloak_id: {user_keycloak_id}), "
                    f"Updated header with user tracking"
                )
                
                return True
            
        except Exception as e:
            logger.error(f"Error updating PO line dates: {e}", exc_info=True)
            return False
    
    @st.cache_data(ttl=300)
    def get_product_demand_vs_incoming(_self) -> pd.DataFrame:
        """Get product demand vs incoming supply analysis"""
        try:
            query = text("""
            WITH product_demand AS (
                SELECT 
                    product_pn,
                    pt_code,
                    product_id,
                    SUM(product_total_remaining_demand) as total_demand,
                    SUM(total_instock_all_warehouses) as current_stock,
                    MAX(product_gap_quantity) as current_gap,
                    MAX(product_fulfill_rate_percent) as current_fulfill_rate
                FROM delivery_full_view
                WHERE product_total_remaining_demand > 0
                GROUP BY product_pn, pt_code, product_id
            ),
            incoming_supply AS (
                SELECT 
                    product_name as product_pn,
                    pt_code,
                    SUM(pending_standard_arrival_quantity) as incoming_qty,
                    MIN(etd) as next_arrival_date_etd,
                    MIN(eta) as next_arrival_date_eta,
                    COUNT(DISTINCT po_number) as pending_po_count
                FROM purchase_order_full_view
                WHERE status != 'COMPLETED'
                    AND pending_standard_arrival_quantity > 0
                GROUP BY product_name, pt_code
            )
            SELECT 
                COALESCE(d.product_pn, s.product_pn) as product,
                COALESCE(d.pt_code, s.pt_code) as pt_code,
                COALESCE(d.total_demand, 0) as total_demand,
                COALESCE(d.current_stock, 0) as current_stock,
                COALESCE(s.incoming_qty, 0) as incoming_supply,
                COALESCE(d.current_stock, 0) + COALESCE(s.incoming_qty, 0) as total_available,
                GREATEST(0, COALESCE(d.total_demand, 0) - COALESCE(d.current_stock, 0) - COALESCE(s.incoming_qty, 0)) as net_requirement,
                COALESCE(d.current_fulfill_rate, 0) as current_coverage_percent,
                CASE 
                    WHEN COALESCE(d.total_demand, 0) = 0 THEN 100
                    ELSE ROUND((COALESCE(d.current_stock, 0) + COALESCE(s.incoming_qty, 0)) / COALESCE(d.total_demand, 0) * 100, 2)
                END as total_coverage_percent,
                s.next_arrival_date_eta,
                COALESCE(s.pending_po_count, 0) as pending_po_count,
                CASE 
                    WHEN COALESCE(d.total_demand, 0) = 0 THEN 'No Demand'
                    WHEN COALESCE(d.current_stock, 0) >= COALESCE(d.total_demand, 0) THEN 'Sufficient Stock'
                    WHEN (COALESCE(d.current_stock, 0) + COALESCE(s.incoming_qty, 0)) >= COALESCE(d.total_demand, 0) THEN 'Will be Sufficient'
                    WHEN COALESCE(s.incoming_qty, 0) > 0 THEN 'Partial Coverage'
                    ELSE 'Need to Order'
                END as supply_status
            FROM product_demand d
            LEFT JOIN incoming_supply s 
                ON d.product_pn = s.product_pn AND d.pt_code = s.pt_code
            WHERE COALESCE(d.total_demand, 0) > 0 
                OR COALESCE(s.incoming_qty, 0) > 0
            ORDER BY net_requirement DESC
            """)
            
            with _self.engine.connect() as conn:
                df = pd.read_sql(query, conn)
            
            return df
            
        except Exception as e:
            logger.error(f"Error getting product demand vs incoming: {e}", exc_info=True)
            return pd.DataFrame()