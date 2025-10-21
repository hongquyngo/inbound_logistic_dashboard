"""
Data Access Layer for Vendor Performance - Refactored

Simplified queries focused on key business metrics:
- Order Entry Value
- Invoiced Value
- Pending Delivery
- Conversion Rate
"""

import pandas as pd
import logging
from datetime import datetime, timedelta
from sqlalchemy import text
from typing import Optional, Dict, List, Any
import streamlit as st

from ..db import get_db_engine
from .exceptions import DataAccessError, ValidationError

logger = logging.getLogger(__name__)


class VendorPerformanceDAO:
    """Simplified Data Access Object for Vendor Performance"""
    
    def __init__(self):
        """Initialize DAO with database engine"""
        try:
            self.engine = get_db_engine()
        except Exception as e:
            logger.error(f"Failed to initialize database engine: {e}")
            raise DataAccessError("Database connection failed", {'error': str(e)})
    
    @st.cache_data(ttl=300)
    def get_vendor_list(_self) -> List[str]:
        """
        Get list of vendors in format "CODE - NAME"
        
        Returns:
            List of vendor display strings
            
        Raises:
            DataAccessError: If query fails
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
            logger.error(f"Error getting vendor list: {e}", exc_info=True)
            raise DataAccessError("Failed to load vendor list", {'error': str(e)})
    
    @st.cache_data(ttl=300)
    def get_vendor_summary(
        _self, 
        vendor_name: Optional[str] = None,
        months: int = 6
    ) -> pd.DataFrame:
        """
        Get simplified vendor summary metrics
        
        Focused metrics:
        - Total Order Entry Value
        - Total Invoiced Value
        - Pending Delivery Value
        - Conversion Rate
        - PO Count
        
        Args:
            vendor_name: Specific vendor (None for all)
            months: Lookback period
            
        Returns:
            DataFrame with vendor summary
            
        Raises:
            DataAccessError: If query fails
        """
        try:
            # Simplified query - calculate in SQL for performance
            query = """
            SELECT 
                vendor_name,
                vendor_code,
                vendor_type,
                vendor_location_type,
                
                -- Order Entry Metrics
                COUNT(DISTINCT po_number) as total_pos,
                SUM(total_amount_usd) as total_order_value,
                
                -- Invoiced Metrics
                SUM(invoiced_amount_usd) as total_invoiced_value,
                SUM(outstanding_invoiced_amount_usd) as pending_delivery_value,
                
                -- Conversion Rate (calculated in SQL)
                ROUND(
                    SUM(invoiced_amount_usd) / NULLIF(SUM(total_amount_usd), 0) * 100,
                    1
                ) as conversion_rate,
                
                -- Date info
                MIN(po_date) as first_po_date,
                MAX(po_date) as last_po_date,
                MAX(last_invoice_date) as last_invoice_date,
                
                -- Average PO value
                AVG(total_amount_usd) as avg_po_value
                
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
            ORDER BY total_order_value DESC
            """
            
            with _self.engine.connect() as conn:
                df = pd.read_sql(text(query), conn, params=params)
            
            if df.empty:
                logger.warning(f"No vendor data found for the last {months} months")
                return df
            
            # Fill NaN values
            df['conversion_rate'] = df['conversion_rate'].fillna(0)
            df['avg_po_value'] = df['avg_po_value'].fillna(0)
            
            logger.info(f"Retrieved summary for {len(df)} vendors")
            return df
            
        except Exception as e:
            logger.error(f"Error getting vendor summary: {e}", exc_info=True)
            raise DataAccessError("Failed to load vendor summary", {'error': str(e)})
    
    @st.cache_data(ttl=300)
    def get_po_data(
        _self, 
        vendor_name: Optional[str] = None,
        months: int = 6,
        filters: Optional[Dict[str, Any]] = None
    ) -> pd.DataFrame:
        """
        Load PO data with essential columns only
        
        Args:
            vendor_name: Specific vendor filter
            months: Lookback period
            filters: Additional filters
            
        Returns:
            DataFrame with PO data
            
        Raises:
            DataAccessError: If query fails
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
                
                -- Product info
                product_name,
                pt_code,
                brand,
                
                -- Quantities
                standard_uom,
                buying_uom,
                standard_quantity,
                buying_quantity,
                
                -- Financial - CORE METRICS
                total_amount_usd as total_order_value_usd,
                invoiced_amount_usd,
                outstanding_invoiced_amount_usd as pending_delivery_usd,
                
                -- Conversion calculation
                ROUND(
                    invoiced_amount_usd / NULLIF(total_amount_usd, 0) * 100,
                    1
                ) as conversion_rate,
                
                currency,
                usd_exchange_rate,
                
                -- Dates
                etd,
                eta,
                last_invoice_date,
                
                -- Terms
                payment_term,
                
                -- Status
                status,
                invoice_completion_percent,
                arrival_completion_percent
                
            FROM purchase_order_full_view
            WHERE po_date >= DATE_SUB(CURDATE(), INTERVAL :months MONTH)
                AND po_date <= CURDATE()
            """
            
            params = {'months': months}
            
            # Vendor filter
            if vendor_name:
                query += " AND vendor_name = :vendor_name"
                params['vendor_name'] = vendor_name
            
            # Additional filters
            if filters:
                if filters.get('vendor_types'):
                    placeholders = ', '.join([f':vtype_{i}' for i in range(len(filters['vendor_types']))])
                    query += f" AND vendor_type IN ({placeholders})"
                    for i, vtype in enumerate(filters['vendor_types']):
                        params[f'vtype_{i}'] = vtype
                
                if filters.get('vendor_locations'):
                    placeholders = ', '.join([f':vloc_{i}' for i in range(len(filters['vendor_locations']))])
                    query += f" AND vendor_location_type IN ({placeholders})"
                    for i, vloc in enumerate(filters['vendor_locations']):
                        params[f'vloc_{i}'] = vloc
                
                if filters.get('payment_terms'):
                    placeholders = ', '.join([f':pterm_{i}' for i in range(len(filters['payment_terms']))])
                    query += f" AND payment_term IN ({placeholders})"
                    for i, pterm in enumerate(filters['payment_terms']):
                        params[f'pterm_{i}'] = pterm
            
            query += " ORDER BY po_date DESC, po_number DESC"
            
            with _self.engine.connect() as conn:
                df = pd.read_sql(text(query), conn, params=params)
            
            # Fill NaN in conversion rate
            df['conversion_rate'] = df['conversion_rate'].fillna(0)
            
            logger.info(f"Loaded {len(df)} PO records")
            return df
            
        except Exception as e:
            logger.error(f"Error loading PO data: {e}", exc_info=True)
            raise DataAccessError("Failed to load PO data", {'error': str(e)})
    
    @st.cache_data(ttl=300)
    def get_product_summary(
        _self,
        vendor_name: str,
        months: int = 6
    ) -> pd.DataFrame:
        """
        Get product-level summary for a vendor
        
        Args:
            vendor_name: Vendor name
            months: Lookback period
            
        Returns:
            DataFrame with product summary
            
        Raises:
            DataAccessError: If query fails
        """
        if not vendor_name:
            raise ValidationError("vendor_name is required for product summary")
        
        try:
            query = text("""
            SELECT 
                product_name,
                pt_code,
                brand,
                
                -- Order metrics
                COUNT(DISTINCT po_number) as po_count,
                SUM(standard_quantity) as total_ordered_qty,
                
                -- Financial metrics
                SUM(total_amount_usd) as total_order_value,
                SUM(invoiced_amount_usd) as total_invoiced_value,
                SUM(outstanding_invoiced_amount_usd) as pending_value,
                
                -- Conversion
                ROUND(
                    SUM(invoiced_amount_usd) / NULLIF(SUM(total_amount_usd), 0) * 100,
                    1
                ) as conversion_rate,
                
                -- Average unit cost
                AVG(standard_unit_cost_usd) as avg_unit_cost_usd,
                
                -- Latest order date
                MAX(po_date) as last_order_date
                
            FROM purchase_order_full_view
            WHERE vendor_name = :vendor_name
                AND po_date >= DATE_SUB(CURDATE(), INTERVAL :months MONTH)
            GROUP BY product_name, pt_code, brand
            ORDER BY total_order_value DESC
            """)
            
            with _self.engine.connect() as conn:
                df = pd.read_sql(query, conn, params={'vendor_name': vendor_name, 'months': months})
            
            df['conversion_rate'] = df['conversion_rate'].fillna(0)
            
            logger.info(f"Retrieved {len(df)} products for vendor {vendor_name}")
            return df
            
        except Exception as e:
            logger.error(f"Error getting product summary: {e}", exc_info=True)
            raise DataAccessError(
                "Failed to load product summary", 
                {'vendor': vendor_name, 'error': str(e)}
            )
    
    def get_filter_options(self) -> Dict[str, List[str]]:
        """
        Get available filter options
        
        Returns:
            Dictionary with filter options
        """
        try:
            queries = {
                'vendor_types': """
                    SELECT DISTINCT vendor_type 
                    FROM purchase_order_full_view 
                    WHERE vendor_type IS NOT NULL 
                    ORDER BY vendor_type
                """,
                'vendor_locations': """
                    SELECT DISTINCT vendor_location_type 
                    FROM purchase_order_full_view 
                    WHERE vendor_location_type IS NOT NULL 
                    ORDER BY vendor_location_type
                """,
                'payment_terms': """
                    SELECT DISTINCT payment_term 
                    FROM purchase_order_full_view 
                    WHERE payment_term IS NOT NULL 
                    ORDER BY payment_term
                """,
                'brands': """
                    SELECT DISTINCT brand 
                    FROM purchase_order_full_view 
                    WHERE brand IS NOT NULL 
                    ORDER BY brand
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
    
    @staticmethod
    def _extract_vendor_name(vendor_display: str) -> str:
        """Extract vendor name from 'CODE - NAME' format"""
        if ' - ' in vendor_display:
            _, name = vendor_display.split(' - ', 1)
            return name.strip()
        return vendor_display.strip()