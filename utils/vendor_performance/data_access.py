"""
Data Access Layer for Vendor Performance

Handles all database queries and data fetching for vendor performance analysis.
"""

import pandas as pd
import logging
from datetime import datetime, timedelta
from sqlalchemy import text
from typing import Optional, Dict, List, Any, Tuple
import streamlit as st

from ..db import get_db_engine

logger = logging.getLogger(__name__)


class VendorPerformanceDAO:
    """Data Access Object for Vendor Performance queries"""
    
    def __init__(self):
        """Initialize DAO with database engine"""
        self.engine = get_db_engine()
    
    @st.cache_data(ttl=300)
    def get_vendor_list(_self) -> List[str]:
        """
        Get list of vendors with their codes in format "CODE - NAME"
        
        Returns:
            List of vendor display strings
        """
        try:
            query = text("""
                SELECT DISTINCT 
                    CONCAT(vendor_code, ' - ', vendor_name) as vendor_display
                FROM purchase_order_full_view
                WHERE vendor_name IS NOT NULL 
                    AND vendor_code IS NOT NULL
                ORDER BY vendor_name
            """)
            
            with _self.engine.connect() as conn:
                result = conn.execute(query)
                vendors = [row[0] for row in result]
            
            logger.info(f"Retrieved {len(vendors)} vendors")
            return vendors
            
        except Exception as e:
            logger.error(f"Error getting vendor list: {e}")
            return []
    
    @st.cache_data(ttl=300)
    def get_vendor_metrics(
        _self, 
        vendor_name: Optional[str] = None,
        months: int = 6
    ) -> pd.DataFrame:
        """
        Get comprehensive vendor performance metrics
        
        Args:
            vendor_name: Specific vendor to filter (None for all vendors)
            months: Number of months to look back
            
        Returns:
            DataFrame with vendor performance metrics
        """
        try:
            query = """
            SELECT 
                vendor_name,
                vendor_code,
                vendor_type,
                vendor_location_type,
                
                -- PO counts (distinct POs, not lines)
                COUNT(DISTINCT po_number) as total_pos,
                COUNT(DISTINCT CASE WHEN status = 'COMPLETED' THEN po_number END) as completed_pos,
                COUNT(DISTINCT CASE WHEN status = 'PENDING' THEN po_number END) as pending_pos,
                COUNT(DISTINCT CASE WHEN status = 'IN_PROCESS' THEN po_number END) as in_process_pos,
                
                -- Line-level counts
                COUNT(*) as total_po_lines,
                
                -- Completion percentages
                AVG(arrival_completion_percent) as avg_arrival_completion,
                AVG(invoice_completion_percent) as avg_invoice_completion,
                
                -- On-time delivery (PO level)
                COUNT(DISTINCT CASE 
                    WHEN eta >= etd AND status = 'COMPLETED' 
                    THEN po_number 
                END) as on_time_deliveries,
                
                -- Late deliveries
                COUNT(DISTINCT CASE 
                    WHEN eta < etd AND status = 'COMPLETED' 
                    THEN po_number 
                END) as late_deliveries,
                
                -- Over-delivery metrics
                SUM(CASE WHEN is_over_delivered = 'Y' THEN 1 ELSE 0 END) as over_delivery_lines,
                COUNT(DISTINCT CASE WHEN is_over_delivered = 'Y' THEN po_number END) as over_delivery_pos,
                
                AVG(CASE 
                    WHEN is_over_delivered = 'Y' 
                    THEN ((total_standard_arrived_quantity - standard_quantity) / NULLIF(standard_quantity, 0)) * 100 
                    ELSE NULL 
                END) as avg_over_delivery_percent,
                
                -- Lead time (in days)
                AVG(CASE 
                    WHEN status = 'COMPLETED' AND eta IS NOT NULL AND etd IS NOT NULL
                    THEN DATEDIFF(eta, etd)
                    ELSE NULL
                END) as avg_lead_time_days,
                
                -- Financial metrics
                SUM(total_amount_usd) as total_po_value,
                SUM(outstanding_arrival_amount_usd) as outstanding_arrival_value,
                SUM(outstanding_invoiced_amount_usd) as outstanding_invoices,
                SUM(invoiced_amount_usd) as total_invoiced,
                
                -- Payment progress
                AVG(CASE 
                    WHEN total_amount_usd > 0 
                    THEN (invoiced_amount_usd / total_amount_usd) * 100
                    ELSE NULL
                END) as avg_payment_progress,
                
                -- Additional info
                MIN(po_date) as first_po_date,
                MAX(po_date) as last_po_date,
                COUNT(DISTINCT currency) as currency_count,
                COUNT(DISTINCT payment_term) as payment_term_count
                
            FROM purchase_order_full_view
            WHERE po_date >= DATE_SUB(CURDATE(), INTERVAL :months MONTH)
                AND po_date <= CURDATE()
            """
            
            params = {'months': months}
            
            # Add vendor filter if specified
            if vendor_name:
                query += " AND vendor_name = :vendor_name"
                params['vendor_name'] = vendor_name
            
            query += """
            GROUP BY vendor_name, vendor_code, vendor_type, vendor_location_type
            ORDER BY total_po_value DESC
            """
            
            with _self.engine.connect() as conn:
                df = pd.read_sql(text(query), conn, params=params)
            
            if df.empty:
                logger.warning(f"No vendor metrics found for the last {months} months")
                return df
            
            # Calculate derived rates
            df['on_time_rate'] = df.apply(
                lambda row: (row['on_time_deliveries'] / row['completed_pos'] * 100) 
                if row['completed_pos'] > 0 else 0, 
                axis=1
            ).round(1)
            
            df['completion_rate'] = (
                df['completed_pos'] / df['total_pos'] * 100
            ).fillna(0).round(1)
            
            df['over_delivery_rate'] = df.apply(
                lambda row: (row['over_delivery_pos'] / row['completed_pos'] * 100) 
                if row['completed_pos'] > 0 else 0,
                axis=1
            ).round(1)
            
            df['late_delivery_rate'] = df.apply(
                lambda row: (row['late_deliveries'] / row['completed_pos'] * 100) 
                if row['completed_pos'] > 0 else 0,
                axis=1
            ).round(1)
            
            df['avg_over_delivery_percent'] = df['avg_over_delivery_percent'].fillna(0).round(1)
            df['avg_lead_time_days'] = df['avg_lead_time_days'].fillna(0).round(1)
            
            # Backward compatibility
            df['over_deliveries'] = df['over_delivery_pos']
            
            logger.info(f"Retrieved metrics for {len(df)} vendors")
            return df
            
        except Exception as e:
            logger.error(f"Error getting vendor metrics: {e}", exc_info=True)
            return pd.DataFrame()
    
    @st.cache_data(ttl=300)
    def get_po_data(_self, filters: Optional[Dict[str, Any]] = None) -> pd.DataFrame:
        """
        Load purchase order data with optional filters
        
        Args:
            filters: Dictionary of filter conditions
            
        Returns:
            DataFrame with PO data
        """
        try:
            query = """
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
                
                -- Product info
                product_name,
                pt_code,
                brand,
                package_size,
                
                -- Quantities & UOM
                standard_uom,
                buying_uom,
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
                pending_standard_arrival_quantity,
                
                -- Financial
                invoiced_amount_usd,
                outstanding_invoiced_amount_usd,
                outstanding_arrival_amount_usd,
                
                -- Dates
                etd,
                eta,
                
                -- Terms
                payment_term,
                
                -- Status
                status,
                is_over_delivered,
                arrival_completion_percent,
                invoice_completion_percent
                
            FROM purchase_order_full_view
            WHERE 1=1
            """
            
            params = {}
            
            if filters:
                # Vendor filter
                if filters.get('vendors'):
                    vendor_codes = []
                    vendor_names = []
                    for vendor_display in filters['vendors']:
                        if ' - ' in vendor_display:
                            code, name = vendor_display.split(' - ', 1)
                            vendor_codes.append(code.strip())
                            vendor_names.append(name.strip())
                        else:
                            vendor_names.append(vendor_display)
                    
                    query += " AND (vendor_name IN :vendor_names OR vendor_code IN :vendor_codes)"
                    params['vendor_names'] = tuple(vendor_names)
                    params['vendor_codes'] = tuple(vendor_codes)
                
                # Date filters
                if filters.get('date_from'):
                    query += " AND po_date >= :date_from"
                    params['date_from'] = filters['date_from']
                
                if filters.get('date_to'):
                    query += " AND po_date <= :date_to"
                    params['date_to'] = filters['date_to']
                
                if filters.get('etd_from'):
                    query += " AND etd >= :etd_from"
                    params['etd_from'] = filters['etd_from']
                
                if filters.get('etd_to'):
                    query += " AND etd <= :etd_to"
                    params['etd_to'] = filters['etd_to']
            
            query += " ORDER BY po_date DESC, po_number DESC"
            
            with _self.engine.connect() as conn:
                df = pd.read_sql(text(query), conn, params=params)
            
            logger.info(f"Loaded {len(df)} PO records")
            return df
            
        except Exception as e:
            logger.error(f"Error loading PO data: {e}", exc_info=True)
            return pd.DataFrame()
    
    def get_filter_options(self) -> Dict[str, Any]:
        """
        Get available filter options from database
        
        Returns:
            Dictionary with filter options
        """
        try:
            queries = {
                'vendors': """
                    SELECT DISTINCT
                        CONCAT(vendor_code, ' - ', vendor_name) as vendor_display
                    FROM purchase_order_full_view 
                    WHERE vendor_name IS NOT NULL 
                        AND vendor_code IS NOT NULL
                    ORDER BY vendor_name
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
                'brands': """
                    SELECT DISTINCT brand 
                    FROM purchase_order_full_view 
                    WHERE brand IS NOT NULL 
                    ORDER BY brand
                """,
                'payment_terms': """
                    SELECT DISTINCT payment_term 
                    FROM purchase_order_full_view 
                    WHERE payment_term IS NOT NULL 
                    ORDER BY payment_term
                """
            }
            
            options = {}
            with self.engine.connect() as conn:
                for key, query in queries.items():
                    try:
                        result = conn.execute(text(query))
                        options[key] = [row[0] for row in result]
                    except Exception as e:
                        logger.warning(f"Could not get {key} options: {e}")
                        options[key] = []
            
            return options
            
        except Exception as e:
            logger.error(f"Error getting filter options: {e}")
            return {}
    
    def _extract_vendor_name(self, vendor_display: str) -> str:
        """
        Extract vendor name from display format "CODE - NAME"
        
        Args:
            vendor_display: Vendor in display format
            
        Returns:
            Vendor name only
        """
        if ' - ' in vendor_display:
            _, name = vendor_display.split(' - ', 1)
            return name.strip()
        return vendor_display.strip()