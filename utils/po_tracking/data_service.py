"""
Data Service for PO Tracking
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
            logger.error(f"Error getting filter options: {e}")
            return {}
    
    @st.cache_data(ttl=300)
    def load_po_data(_self, query_parts: str, params: Dict[str, Any]) -> pd.DataFrame:
        """
        Load PO data with filters applied in SQL
        
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
                
                -- Terms
                payment_term,
                trade_term,
                vat_gst_percent,
                
                -- Status
                status,
                is_over_delivered,
                is_over_invoiced,
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
            
            # Order by
            base_query += " ORDER BY po_date DESC, po_number DESC, po_line_id DESC"
            
            # Execute query
            with _self.engine.connect() as conn:
                df = pd.read_sql(text(base_query), conn, params=params)
            
            logger.info(f"Loaded {len(df)} PO records")
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
        Update ETD/ETA dates for a PO line
        
        Args:
            po_line_id: PO line ID to update
            adjust_etd: New adjusted ETD
            adjust_eta: New adjusted ETA
            reason: Reason for the change (for logging)
            
        Returns:
            bool: True if successful, False otherwise
        """
        try:
            # Get current user from session state
            user_email = st.session_state.get('user_email', 'system')
            
            update_query = text("""
                UPDATE product_purchase_orders 
                SET 
                    adjust_etd = :adjust_etd,
                    adjust_eta = :adjust_eta,
                    updated_by = :updated_by,
                    updated_date = NOW()
                WHERE 
                    id = :po_line_id
                    AND delete_flag = 0
            """)
            
            with self.engine.begin() as conn:
                result = conn.execute(
                    update_query,
                    {
                        'po_line_id': po_line_id,
                        'adjust_etd': adjust_etd,
                        'adjust_eta': adjust_eta,
                        'updated_by': user_email
                    }
                )
                
                rows_affected = result.rowcount
                
                if rows_affected > 0:
                    logger.info(
                        f"Updated PO line {po_line_id} dates: "
                        f"ETD={adjust_etd}, ETA={adjust_eta}, "
                        f"Reason={reason}, User={user_email}"
                    )
                    return True
                else:
                    logger.warning(f"No rows updated for PO line {po_line_id}")
                    return False
            
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
            logger.error(f"Error getting product demand vs incoming: {e}")
            return pd.DataFrame()