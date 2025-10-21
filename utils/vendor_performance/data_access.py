"""
Data Access Layer for Vendor Performance - Refactored with Multi-Date Logic

Supports three date dimensions:
1. Order Analysis: po_date based
2. Invoice Analysis: inv_date based  
3. Backlog Analysis: ETD based
"""

import pandas as pd
import logging
from datetime import datetime, timedelta
from sqlalchemy import text
from typing import Optional, Dict, List, Any, Tuple
import streamlit as st

from ..db import get_db_engine
from .exceptions import DataAccessError, ValidationError

logger = logging.getLogger(__name__)


class VendorPerformanceDAO:
    """Data Access Object for Vendor Performance with multi-date support"""
    
    def __init__(self):
        """Initialize DAO with database engine"""
        try:
            self.engine = get_db_engine()
        except Exception as e:
            logger.error(f"Failed to initialize database engine: {e}")
            raise DataAccessError("Database connection failed", {'error': str(e)})
    
    # ==================== UTILITY METHODS ====================
    
    @staticmethod
    def _build_date_filter(
        date_field: str,
        start_date: datetime,
        end_date: datetime
    ) -> Tuple[str, Dict[str, Any]]:
        """
        Build date range filter clause
        
        Args:
            date_field: Name of date column
            start_date: Start date
            end_date: End date
            
        Returns:
            Tuple of (SQL clause, parameters dict)
        """
        clause = f"{date_field} BETWEEN :start_date AND :end_date"
        params = {
            'start_date': start_date.strftime('%Y-%m-%d'),
            'end_date': end_date.strftime('%Y-%m-%d')
        }
        return clause, params
    
    @staticmethod
    def _build_filter_clause(
        filters: Dict[str, Any],
        vendor_column: str = 'vendor_name'
    ) -> Tuple[str, Dict[str, Any]]:
        """
        Build WHERE clause from filters
        
        Args:
            filters: Filter dictionary
            vendor_column: Name of vendor column in the view ('vendor_name' or 'vendor')
            
        Returns:
            Tuple of (SQL clause, parameters dict)
        """
        clauses = []
        params = {}
        
        if filters.get('vendor_name'):
            clauses.append(f"{vendor_column} = :vendor_name")
            params['vendor_name'] = filters['vendor_name']
        
        if filters.get('entity_id'):
            clauses.append("legal_entity_id = :entity_id")
            params['entity_id'] = filters['entity_id']
        
        if filters.get('vendor_types'):
            type_clauses = []
            for i, vtype in enumerate(filters['vendor_types']):
                param_name = f'vtype_{i}'
                type_clauses.append(f":{param_name}")
                params[param_name] = vtype
            clauses.append(f"vendor_type IN ({','.join(type_clauses)})")
        
        if filters.get('vendor_locations'):
            loc_clauses = []
            for i, vloc in enumerate(filters['vendor_locations']):
                param_name = f'vloc_{i}'
                loc_clauses.append(f":{param_name}")
                params[param_name] = vloc
            clauses.append(f"vendor_location_type IN ({','.join(loc_clauses)})")
        
        if filters.get('payment_terms'):
            term_clauses = []
            for i, pterm in enumerate(filters['payment_terms']):
                param_name = f'pterm_{i}'
                term_clauses.append(f":{param_name}")
                params[param_name] = pterm
            clauses.append(f"payment_term IN ({','.join(term_clauses)})")
        
        where_clause = " AND ".join(clauses) if clauses else "1=1"
        return where_clause, params
    
    # ==================== REFERENCE DATA ====================
    
    @st.cache_data(ttl=300)
    def get_vendor_list(_self) -> List[str]:
        """Get list of vendors in format 'CODE - NAME'"""
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
    def get_entity_list(_self) -> List[str]:
        """Get list of legal entities"""
        try:
            query = text("""
                SELECT DISTINCT 
                    CONCAT(legal_entity_code, ' - ', legal_entity) as entity_display
                FROM purchase_order_full_view
                WHERE legal_entity IS NOT NULL 
                    AND legal_entity_code IS NOT NULL
                ORDER BY legal_entity
            """)
            
            with _self.engine.connect() as conn:
                result = conn.execute(query)
                entities = [row[0] for row in result]
            
            logger.info(f"Retrieved {len(entities)} entities")
            return entities
            
        except Exception as e:
            logger.error(f"Error getting entity list: {e}", exc_info=True)
            return []
    
    def get_entity_id_by_display(self, display_string: str) -> Optional[int]:
        """Extract entity ID from display string"""
        try:
            # Assume format "CODE - NAME"
            code = display_string.split(' - ')[0].strip()
            
            query = text("""
                SELECT DISTINCT legal_entity_id
                FROM purchase_order_full_view
                WHERE legal_entity_code = :code
                LIMIT 1
            """)
            
            with self.engine.connect() as conn:
                result = conn.execute(query, {'code': code})
                row = result.fetchone()
                return row[0] if row else None
                
        except Exception as e:
            logger.error(f"Error getting entity ID: {e}")
            return None
    
    def get_filter_options(self) -> Dict[str, List[str]]:
        """Get available filter options"""
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
    
    # ==================== ORDER ANALYSIS QUERIES ====================
    
    @st.cache_data(ttl=300)
    def get_order_cohort_summary(
        _self,
        start_date: datetime,
        end_date: datetime,
        filters: Optional[Dict[str, Any]] = None
    ) -> pd.DataFrame:
        """
        Get order cohort summary (POs placed in period)
        
        Tracks POs by po_date and shows ALL invoices for those POs
        
        Args:
            start_date: Start of period
            end_date: End of period
            filters: Additional filters
            
        Returns:
            DataFrame with vendor-level summary
        """
        try:
            # Build filter clauses
            filter_clause, filter_params = _self._build_filter_clause(
                filters or {},
                vendor_column='vendor_name'  # purchase_order_full_view uses 'vendor_name'
            )
            
            query = f"""
            WITH order_cohort AS (
                -- POs in selected period
                SELECT 
                    po_line_id,
                    po_number,
                    vendor_id,
                    vendor_name,
                    vendor_code,
                    vendor_type,
                    vendor_location_type,
                    legal_entity_id,
                    legal_entity,
                    po_date,
                    total_amount_usd,
                    buying_quantity,
                    standard_quantity,
                    payment_term
                FROM purchase_order_full_view
                WHERE po_date BETWEEN :start_date AND :end_date
                    AND ({filter_clause})
            ),
            cohort_invoices AS (
                -- ALL invoices for POs in cohort
                SELECT 
                    pif.po_number,
                    pif.vendor_id,
                    SUM(pif.calculated_invoiced_amount_usd) as invoiced_value,
                    SUM(pif.outstanding_amount) as outstanding_payment
                FROM purchase_invoice_full_view pif
                WHERE pif.po_number IN (SELECT po_number FROM order_cohort)
                    AND pif.invoice_status NOT IN ('Cancelled', 'PO Cancelled')
                GROUP BY pif.po_number, pif.vendor_id
            )
            SELECT 
                oc.vendor_id,
                oc.vendor_name,
                oc.vendor_code,
                oc.vendor_type,
                oc.vendor_location_type,
                oc.legal_entity_id,
                oc.legal_entity,
                
                -- Order metrics
                COUNT(DISTINCT oc.po_number) as total_pos,
                SUM(oc.total_amount_usd) as total_order_value,
                
                -- Invoice metrics
                COALESCE(SUM(ci.invoiced_value), 0) as total_invoiced_value,
                
                -- Outstanding
                SUM(oc.total_amount_usd) - COALESCE(SUM(ci.invoiced_value), 0) as outstanding_value,
                
                -- Conversion rate
                ROUND(
                    COALESCE(SUM(ci.invoiced_value), 0) / 
                    NULLIF(SUM(oc.total_amount_usd), 0) * 100,
                    1
                ) as conversion_rate,
                
                -- Payment outstanding
                COALESCE(SUM(ci.outstanding_payment), 0) as payment_outstanding,
                
                -- Dates
                MIN(oc.po_date) as first_po_date,
                MAX(oc.po_date) as last_po_date,
                
                -- Average PO value
                AVG(oc.total_amount_usd) as avg_po_value
                
            FROM order_cohort oc
            LEFT JOIN cohort_invoices ci ON oc.po_number = ci.po_number
            GROUP BY 
                oc.vendor_id, oc.vendor_name, oc.vendor_code,
                oc.vendor_type, oc.vendor_location_type,
                oc.legal_entity_id, oc.legal_entity
            ORDER BY total_order_value DESC
            """
            
            params = {
                'start_date': start_date.strftime('%Y-%m-%d'),
                'end_date': end_date.strftime('%Y-%m-%d'),
                **filter_params
            }
            
            with _self.engine.connect() as conn:
                df = pd.read_sql(text(query), conn, params=params)
            
            df['conversion_rate'] = df['conversion_rate'].fillna(0)
            
            logger.info(f"Retrieved order cohort summary: {len(df)} vendors")
            return df
            
        except Exception as e:
            logger.error(f"Error getting order cohort summary: {e}", exc_info=True)
            raise DataAccessError("Failed to load order summary", {'error': str(e)})
    
    @st.cache_data(ttl=300)
    def get_order_cohort_detail(
        _self,
        start_date: datetime,
        end_date: datetime,
        filters: Optional[Dict[str, Any]] = None
    ) -> pd.DataFrame:
        """
        Get detailed PO data for order cohort analysis
        
        Returns PO-level details with current invoice status
        """
        try:
            filter_clause, filter_params = _self._build_filter_clause(
                filters or {}, 
                vendor_column='vendor'  # purchase_invoice_full_view uses 'vendor'
            )
            
            query = f"""
            SELECT 
                po_line_id,
                po_number,
                external_ref_number,
                po_date,
                vendor_name,
                vendor_code,
                vendor_type,
                vendor_location_type,
                legal_entity,
                product_name,
                pt_code,
                brand,
                standard_uom,
                buying_uom,
                buying_quantity,
                standard_quantity,
                total_amount_usd,
                invoiced_amount_usd,
                outstanding_invoiced_amount_usd,
                ROUND(
                    invoiced_amount_usd / NULLIF(total_amount_usd, 0) * 100,
                    1
                ) as line_conversion_rate,
                currency,
                payment_term,
                etd,
                eta,
                status,
                invoice_completion_percent
            FROM purchase_order_full_view
            WHERE po_date BETWEEN :start_date AND :end_date
                AND ({filter_clause})
            ORDER BY po_date DESC, po_number DESC
            """
            
            params = {
                'start_date': start_date.strftime('%Y-%m-%d'),
                'end_date': end_date.strftime('%Y-%m-%d'),
                **filter_params
            }
            
            with _self.engine.connect() as conn:
                df = pd.read_sql(text(query), conn, params=params)
            
            df['line_conversion_rate'] = df['line_conversion_rate'].fillna(0)
            
            logger.info(f"Retrieved order detail: {len(df)} PO lines")
            return df
            
        except Exception as e:
            logger.error(f"Error getting order detail: {e}", exc_info=True)
            raise DataAccessError("Failed to load order detail", {'error': str(e)})
    
    # ==================== INVOICE ANALYSIS QUERIES ====================
    
    @st.cache_data(ttl=300)
    def get_invoice_summary(
        _self,
        start_date: datetime,
        end_date: datetime,
        filters: Optional[Dict[str, Any]] = None
    ) -> pd.DataFrame:
        """
        Get invoice summary (invoices dated in period)
        
        Args:
            start_date: Start of period
            end_date: End of period
            filters: Additional filters
            
        Returns:
            DataFrame with vendor-level invoice summary
        """
        try:
            filter_clause, filter_params = _self._build_filter_clause(
                filters or {},
                vendor_column='vendor_name'  # purchase_order_full_view uses 'vendor_name'
            )
            
            query = f"""
            SELECT 
                vendor_id,
                vendor,
                vendor_code,
                vendor_type,
                vendor_location_type,
                legal_entity_id,
                legal_entity,
                
                -- Invoice counts
                COUNT(DISTINCT inv_number) as total_invoices,
                COUNT(DISTINCT pi_line_id) as total_invoice_lines,
                
                -- Invoice amounts
                SUM(calculated_invoiced_amount_usd) as total_invoiced_value,
                SUM(total_payment_made) as total_paid,
                SUM(outstanding_amount) as total_outstanding,
                
                -- Payment metrics
                ROUND(
                    SUM(total_payment_made) / NULLIF(SUM(calculated_invoiced_amount_usd), 0) * 100,
                    1
                ) as payment_rate,
                
                -- Status counts
                SUM(CASE WHEN payment_status = 'Fully Paid' THEN 1 ELSE 0 END) as fully_paid_count,
                SUM(CASE WHEN payment_status = 'Partially Paid' THEN 1 ELSE 0 END) as partially_paid_count,
                SUM(CASE WHEN payment_status = 'Unpaid' THEN 1 ELSE 0 END) as unpaid_count,
                
                -- Aging
                AVG(invoice_age_days) as avg_invoice_age,
                SUM(CASE WHEN aging_status = 'Overdue' THEN outstanding_amount ELSE 0 END) as overdue_amount,
                
                -- Dates
                MIN(inv_date) as first_invoice_date,
                MAX(inv_date) as last_invoice_date,
                MAX(last_payment_date) as last_payment_date
                
            FROM purchase_invoice_full_view
            WHERE inv_date BETWEEN :start_date AND :end_date
                AND invoice_status NOT IN ('Cancelled', 'PO Cancelled')
                AND ({filter_clause})
            GROUP BY 
                vendor_id, vendor, vendor_code,
                vendor_type, vendor_location_type,
                legal_entity_id, legal_entity
            ORDER BY total_invoiced_value DESC
            """
            
            params = {
                'start_date': start_date.strftime('%Y-%m-%d'),
                'end_date': end_date.strftime('%Y-%m-%d'),
                **filter_params
            }
            
            with _self.engine.connect() as conn:
                df = pd.read_sql(text(query), conn, params=params)
            
            df['payment_rate'] = df['payment_rate'].fillna(0)
            
            logger.info(f"Retrieved invoice summary: {len(df)} vendors")
            return df
            
        except Exception as e:
            logger.error(f"Error getting invoice summary: {e}", exc_info=True)
            raise DataAccessError("Failed to load invoice summary", {'error': str(e)})
    
    @st.cache_data(ttl=300)
    def get_invoice_detail(
        _self,
        start_date: datetime,
        end_date: datetime,
        filters: Optional[Dict[str, Any]] = None
    ) -> pd.DataFrame:
        """Get detailed invoice data"""
        try:
            filter_clause, filter_params = _self._build_filter_clause(
                filters or {}, 
                vendor_column='vendor'  # purchase_invoice_full_view uses 'vendor'
            )
            
            query = f"""
            SELECT 
                pi_line_id,
                inv_number,
                commercial_inv_number,
                inv_date,
                due_date,
                vendor,
                vendor_code,
                legal_entity,
                po_number,
                product_name,
                pt_code,
                brand,
                invoiced_quantity,
                calculated_invoiced_amount_usd,
                total_payment_made,
                outstanding_amount,
                payment_status,
                payment_ratio,
                invoice_age_days,
                days_overdue,
                aging_status,
                payment_term,
                invoiced_currency
            FROM purchase_invoice_full_view
            WHERE inv_date BETWEEN :start_date AND :end_date
                AND invoice_status NOT IN ('Cancelled', 'PO Cancelled')
                AND ({filter_clause})
            ORDER BY inv_date DESC, inv_number DESC
            """
            
            params = {
                'start_date': start_date.strftime('%Y-%m-%d'),
                'end_date': end_date.strftime('%Y-%m-%d'),
                **filter_params
            }
            
            with _self.engine.connect() as conn:
                df = pd.read_sql(text(query), conn, params=params)
            
            logger.info(f"Retrieved invoice detail: {len(df)} invoice lines")
            return df
            
        except Exception as e:
            logger.error(f"Error getting invoice detail: {e}", exc_info=True)
            raise DataAccessError("Failed to load invoice detail", {'error': str(e)})
    
    # ==================== PRODUCT ANALYSIS QUERIES ====================
    
    @st.cache_data(ttl=300)
    def get_product_summary_by_orders(
        _self,
        start_date: datetime,
        end_date: datetime,
        filters: Optional[Dict[str, Any]] = None
    ) -> pd.DataFrame:
        """
        Get product summary based on orders (po_date)
        
        Returns product-level metrics for POs in period
        """
        try:
            filter_clause, filter_params = _self._build_filter_clause(filters or {})
            
            query = f"""
            WITH product_orders AS (
                SELECT 
                    product_id,
                    product_name,
                    pt_code,
                    brand,
                    vendor_name,
                    po_number,
                    total_amount_usd,
                    invoiced_amount_usd,
                    standard_quantity
                FROM purchase_order_full_view
                WHERE po_date BETWEEN :start_date AND :end_date
                    AND ({filter_clause})
            )
            SELECT 
                product_id,
                product_name,
                pt_code,
                brand,
                vendor_name,
                
                COUNT(DISTINCT po_number) as po_count,
                SUM(standard_quantity) as total_ordered_qty,
                SUM(total_amount_usd) as total_order_value,
                SUM(invoiced_amount_usd) as total_invoiced_value,
                SUM(total_amount_usd - invoiced_amount_usd) as outstanding_value,
                
                ROUND(
                    SUM(invoiced_amount_usd) / NULLIF(SUM(total_amount_usd), 0) * 100,
                    1
                ) as conversion_rate,
                
                AVG(total_amount_usd) as avg_order_value
                
            FROM product_orders
            GROUP BY product_id, product_name, pt_code, brand, vendor_name
            ORDER BY total_order_value DESC
            """
            
            params = {
                'start_date': start_date.strftime('%Y-%m-%d'),
                'end_date': end_date.strftime('%Y-%m-%d'),
                **filter_params
            }
            
            with _self.engine.connect() as conn:
                df = pd.read_sql(text(query), conn, params=params)
            
            df['conversion_rate'] = df['conversion_rate'].fillna(0)
            
            logger.info(f"Retrieved product summary: {len(df)} products")
            return df
            
        except Exception as e:
            logger.error(f"Error getting product summary: {e}", exc_info=True)
            raise DataAccessError("Failed to load product summary", {'error': str(e)})