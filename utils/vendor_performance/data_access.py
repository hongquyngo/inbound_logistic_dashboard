"""
Data Access Layer for Vendor Performance - Refactored & Fixed

FIXES APPLIED:
1. ✅ Fixed column names to match purchase_order_full_view
2. ✅ Added get_product_summary_by_orders method
3. ✅ Capped conversion rate at 100% in queries
4. ✅ Removed unused methods
5. ✅ Improved error handling

Version: 3.0
Last Updated: 2025-10-22
"""

import pandas as pd
import logging
from datetime import datetime, timedelta
from sqlalchemy import text
from typing import Optional, Dict, List, Any, Tuple
import streamlit as st
from functools import wraps
import time

from ..db import get_db_engine
from .exceptions import DataAccessError, ValidationError

logger = logging.getLogger(__name__)


# ==================== DECORATORS ====================

def validate_date_range(func):
    """Validate date range inputs"""
    @wraps(func)
    def wrapper(*args, **kwargs):
        start_date = kwargs.get('start_date')
        end_date = kwargs.get('end_date')
        
        if start_date and end_date:
            if start_date > end_date:
                raise ValidationError(
                    "Start date must be before end date",
                    {'start_date': start_date, 'end_date': end_date}
                )
            
            days_diff = (end_date - start_date).days
            if days_diff > 365 * 3:
                raise ValidationError(
                    "Date range too large (maximum 3 years allowed)",
                    {'days': days_diff, 'max_days': 365 * 3}
                )
            
            if days_diff > 365:
                logger.warning(f"Large date range requested: {days_diff} days")
        
        return func(*args, **kwargs)
    return wrapper


def monitor_performance(func):
    """Monitor function execution time"""
    @wraps(func)
    def wrapper(*args, **kwargs):
        start_time = time.time()
        func_name = func.__name__
        
        try:
            result = func(*args, **kwargs)
            execution_time = time.time() - start_time
            
            logger.info(
                f"{func_name} executed in {execution_time:.2f}s",
                extra={'execution_time': execution_time, 'function': func_name}
            )
            
            if execution_time > 3.0:  # Lower threshold from 5s to 3s
                logger.warning(
                    f"⚠️ Slow query detected: {func_name} took {execution_time:.2f}s"
                )
            
            return result
            
        except Exception as e:
            execution_time = time.time() - start_time
            logger.error(
                f"{func_name} failed after {execution_time:.2f}s: {str(e)}",
                exc_info=True
            )
            raise
    
    return wrapper


# ==================== MAIN DAO CLASS ====================

class VendorPerformanceDAO:
    """
    Data Access Object for Vendor Performance Analytics
    
    Provides secure, validated database access with:
    - SQL injection prevention
    - Input validation
    - Performance monitoring
    - Query caching
    """
    
    VIEW_COLUMN_MAPPING = {
        'purchase_order_full_view': 'vendor_name',
        'purchase_invoice_full_view': 'vendor'
    }
    
    ALLOWED_FILTER_COLUMNS = {
        'vendor_name', 'vendor', 'vendor_type', 
        'vendor_location_type', 'payment_term',
        'legal_entity_id'
    }
    
    def __init__(self):
        """Initialize DAO with database engine"""
        try:
            self.engine = get_db_engine()
            logger.info("VendorPerformanceDAO initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize database engine: {e}")
            raise DataAccessError(
                "Database connection failed", 
                {'error': str(e)}
            )
    
    # ==================== UTILITY METHODS ====================
    
    @staticmethod
    def _get_vendor_column_for_view(view_name: str) -> str:
        """Get correct vendor column name for a database view"""
        if view_name not in VendorPerformanceDAO.VIEW_COLUMN_MAPPING:
            raise ValidationError(
                f"Unknown database view: {view_name}",
                {
                    'requested_view': view_name,
                    'valid_views': list(VendorPerformanceDAO.VIEW_COLUMN_MAPPING.keys())
                }
            )
        return VendorPerformanceDAO.VIEW_COLUMN_MAPPING[view_name]
    
    @staticmethod
    def _validate_column_name(column_name: str) -> None:
        """Validate column name against whitelist"""
        if column_name not in VendorPerformanceDAO.ALLOWED_FILTER_COLUMNS:
            raise ValidationError(
                f"Invalid column name: {column_name}",
                {
                    'requested_column': column_name,
                    'allowed_columns': list(VendorPerformanceDAO.ALLOWED_FILTER_COLUMNS)
                }
            )
    
    @staticmethod
    def _sanitize_string_input(value: str, max_length: int = 200) -> str:
        """Sanitize string input to prevent injection"""
        if not value:
            return ""
        
        sanitized = str(value)[:max_length]
        
        import re
        sanitized = re.sub(r'[^\w\s\-\.]', '', sanitized)
        
        return sanitized.strip()
    
    @staticmethod
    def _build_filter_clause(
        filters: Dict[str, Any],
        vendor_column: str = 'vendor_name'
    ) -> Tuple[str, Dict[str, Any]]:
        """Build WHERE clause from filters with SQL injection prevention"""
        VendorPerformanceDAO._validate_column_name(vendor_column)
        
        clauses = []
        params = {}
        
        if filters.get('vendor_name'):
            vendor_name = VendorPerformanceDAO._sanitize_string_input(
                filters['vendor_name']
            )
            clauses.append(f"{vendor_column} = :vendor_name")
            params['vendor_name'] = vendor_name
        
        if filters.get('entity_id'):
            try:
                entity_id = int(filters['entity_id'])
                clauses.append("legal_entity_id = :entity_id")
                params['entity_id'] = entity_id
            except (ValueError, TypeError):
                logger.warning(f"Invalid entity_id: {filters.get('entity_id')}")
        
        if filters.get('vendor_types'):
            placeholders = []
            for i, vtype in enumerate(filters['vendor_types']):
                param_name = f'vtype_{i}'
                placeholders.append(f":{param_name}")
                params[param_name] = VendorPerformanceDAO._sanitize_string_input(vtype)
            
            if placeholders:
                clauses.append(f"vendor_type IN ({','.join(placeholders)})")
        
        if filters.get('vendor_locations'):
            placeholders = []
            for i, vloc in enumerate(filters['vendor_locations']):
                param_name = f'vloc_{i}'
                placeholders.append(f":{param_name}")
                params[param_name] = VendorPerformanceDAO._sanitize_string_input(vloc)
            
            if placeholders:
                clauses.append(f"vendor_location_type IN ({','.join(placeholders)})")
        
        if filters.get('payment_terms'):
            placeholders = []
            for i, pterm in enumerate(filters['payment_terms']):
                param_name = f'pterm_{i}'
                placeholders.append(f":{param_name}")
                params[param_name] = VendorPerformanceDAO._sanitize_string_input(pterm)
            
            if placeholders:
                clauses.append(f"payment_term IN ({','.join(placeholders)})")
        
        where_clause = " AND ".join(clauses) if clauses else "1=1"
        return where_clause, params
    
    # ==================== REFERENCE DATA ====================
    
    @st.cache_data(ttl=3600)
    def get_vendor_list(_self) -> List[str]:
        """Get list of vendors in format 'CODE - NAME'"""
        try:
            query = text("""
                SELECT DISTINCT 
                    CONCAT(vendor_code, ' - ', vendor_name) as vendor_display
                FROM purchase_order_full_view
                WHERE vendor_name IS NOT NULL 
                    AND vendor_code IS NOT NULL
                    AND vendor_name != ''
                    AND vendor_code != ''
                ORDER BY vendor_name
            """)
            
            with _self.engine.connect() as conn:
                result = conn.execute(query)
                vendors = [row[0] for row in result]
            
            logger.info(f"Retrieved {len(vendors)} vendors from database")
            return vendors
            
        except Exception as e:
            logger.error(f"Error getting vendor list: {e}", exc_info=True)
            raise DataAccessError(
                "Failed to load vendor list", 
                {'error': str(e)}
            )
    
    @st.cache_data(ttl=3600)
    def get_entity_list(_self) -> List[str]:
        """Get list of legal entities in format 'CODE - NAME'"""
        try:
            query = text("""
                SELECT DISTINCT 
                    CONCAT(legal_entity_code, ' - ', legal_entity) as entity_display
                FROM purchase_order_full_view
                WHERE legal_entity IS NOT NULL 
                    AND legal_entity_code IS NOT NULL
                    AND legal_entity != ''
                    AND legal_entity_code != ''
                ORDER BY legal_entity
            """)
            
            with _self.engine.connect() as conn:
                result = conn.execute(query)
                entities = [row[0] for row in result]
            
            logger.info(f"Retrieved {len(entities)} legal entities")
            return entities
            
        except Exception as e:
            logger.error(f"Error getting entity list: {e}", exc_info=True)
            return []
    
    def get_entity_id_by_display(self, display_string: str) -> Optional[int]:
        """Extract entity ID from display string"""
        try:
            if ' - ' not in display_string:
                logger.warning(f"Invalid entity display format: {display_string}")
                return None
            
            code = display_string.split(' - ')[0].strip()
            code = self._sanitize_string_input(code, max_length=50)
            
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
    
    @st.cache_data(ttl=3600)
    def get_filter_options(_self) -> Dict[str, List[str]]:
        """Get available filter options for dropdowns"""
        try:
            queries = {
                'vendor_types': """
                    SELECT DISTINCT vendor_type 
                    FROM purchase_order_full_view 
                    WHERE vendor_type IS NOT NULL 
                        AND vendor_type != ''
                    ORDER BY vendor_type
                """,
                'vendor_locations': """
                    SELECT DISTINCT vendor_location_type 
                    FROM purchase_order_full_view 
                    WHERE vendor_location_type IS NOT NULL
                        AND vendor_location_type != ''
                    ORDER BY vendor_location_type
                """,
                'payment_terms': """
                    SELECT DISTINCT payment_term 
                    FROM purchase_order_full_view 
                    WHERE payment_term IS NOT NULL
                        AND payment_term != ''
                    ORDER BY payment_term
                """
            }
            
            options = {}
            with _self.engine.connect() as conn:
                for key, query in queries.items():
                    try:
                        result = conn.execute(text(query))
                        options[key] = [row[0] for row in result]
                        logger.debug(f"Loaded {len(options[key])} options for {key}")
                    except Exception as e:
                        logger.warning(f"Could not get {key} options: {e}")
                        options[key] = []
            
            return options
            
        except Exception as e:
            logger.error(f"Error getting filter options: {e}")
            return {
                'vendor_types': [],
                'vendor_locations': [],
                'payment_terms': []
            }
    
    # ==================== ORDER ANALYSIS QUERIES ====================
    
    @st.cache_data(ttl=300)
    @validate_date_range
    @monitor_performance
    def get_order_cohort_summary(
        _self,
        start_date: datetime,
        end_date: datetime,
        filters: Optional[Dict[str, Any]] = None
    ) -> pd.DataFrame:
        """
        Get order cohort summary (POs placed in period)
        
        FIXED: Column names corrected to match view
        FIXED: Conversion rate capped at 100%
        """
        try:
            vendor_column = _self._get_vendor_column_for_view('purchase_order_full_view')
            filter_clause, filter_params = _self._build_filter_clause(
                filters or {},
                vendor_column=vendor_column
            )
            
            query = f"""
            WITH order_cohort AS (
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
                
                COUNT(DISTINCT oc.po_number) as total_pos,
                SUM(oc.total_amount_usd) as total_order_value,
                
                COALESCE(SUM(ci.invoiced_value), 0) as total_invoiced_value,
                
                SUM(oc.total_amount_usd) - COALESCE(SUM(ci.invoiced_value), 0) as outstanding_value,
                
                LEAST(
                    ROUND(
                        COALESCE(SUM(ci.invoiced_value), 0) / 
                        NULLIF(SUM(oc.total_amount_usd), 0) * 100,
                        1
                    ),
                    100.0
                ) as conversion_rate,
                
                COALESCE(SUM(ci.outstanding_payment), 0) as payment_outstanding,
                
                MIN(oc.po_date) as first_po_date,
                MAX(oc.po_date) as last_po_date,
                
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
            
            logger.info(f"Retrieved order cohort: {len(df)} vendors")
            return df
            
        except Exception as e:
            logger.error(f"Error getting order cohort: {e}", exc_info=True)
            raise DataAccessError(
                "Failed to load order cohort summary",
                {'error': str(e)}
            )
    
    @st.cache_data(ttl=300)
    @validate_date_range
    @monitor_performance
    def get_product_summary_by_orders(
        _self,
        start_date: datetime,
        end_date: datetime,
        filters: Optional[Dict[str, Any]] = None
    ) -> pd.DataFrame:
        """
        Get product-level summary for orders placed in period
        
        NEW METHOD: Added to support Product Mix analysis
        """
        try:
            vendor_column = _self._get_vendor_column_for_view('purchase_order_full_view')
            filter_clause, filter_params = _self._build_filter_clause(
                filters or {},
                vendor_column=vendor_column
            )
            
            query = f"""
            SELECT 
                product_id,
                product_name,
                pt_code,
                brand,
                
                COUNT(DISTINCT po_number) as po_count,
                SUM(buying_quantity) as total_ordered_qty,
                SUM(total_amount_usd) as total_order_value,
                AVG(total_amount_usd) as avg_order_value,
                
                SUM(invoiced_amount_usd) as total_invoiced_value,
                SUM(outstanding_invoiced_amount_usd) as outstanding_value,
                
                LEAST(
                    ROUND(
                        SUM(invoiced_amount_usd) / 
                        NULLIF(SUM(total_amount_usd), 0) * 100,
                        1
                    ),
                    100.0
                ) as conversion_rate,
                
                MIN(po_date) as first_order_date,
                MAX(po_date) as last_order_date
                
            FROM purchase_order_full_view
            WHERE po_date BETWEEN :start_date AND :end_date
                AND ({filter_clause})
            GROUP BY product_id, product_name, pt_code, brand
            HAVING SUM(total_amount_usd) > 0
            ORDER BY total_order_value DESC
            """
            
            params = {
                'start_date': start_date.strftime('%Y-%m-%d'),
                'end_date': end_date.strftime('%Y-%m-%d'),
                **filter_params
            }
            
            with _self.engine.connect() as conn:
                df = pd.read_sql(text(query), conn, params=params)
            
            if not df.empty:
                max_order_value = df['total_order_value'].max()
                if max_order_value > 1_000_000_000:
                    logger.warning(
                        f"Product with suspicious value detected: "
                        f"${max_order_value:,.0f}. Please verify data."
                    )
            
            logger.info(
                f"Retrieved product summary: {len(df)} products, "
                f"total value: ${df['total_order_value'].sum():,.0f}"
            )
            return df
            
        except Exception as e:
            logger.error(f"Error getting product summary: {e}", exc_info=True)
            raise DataAccessError(
                "Failed to load product summary by orders",
                {'error': str(e)}
            )
    
    # ==================== ADDITIONAL QUERY METHODS ====================
    
    def get_order_summary_validated(
        self,
        start_date: datetime,
        end_date: datetime,
        filters: Optional[Dict[str, Any]] = None
    ) -> pd.DataFrame:
        """Alias for get_order_cohort_summary with validation"""
        return self.get_order_cohort_summary(start_date, end_date, filters)
    
    def get_invoice_summary(
        self,
        start_date: datetime,
        end_date: datetime,
        filters: Optional[Dict[str, Any]] = None
    ) -> pd.DataFrame:
        """Get invoice summary by invoice date"""
        try:
            vendor_column = self._get_vendor_column_for_view('purchase_invoice_full_view')
            filter_clause, filter_params = self._build_filter_clause(
                filters or {},
                vendor_column=vendor_column
            )
            
            query = f"""
            SELECT 
                vendor_id,
                vendor as vendor_name,
                
                COUNT(DISTINCT inv_number) as total_invoices,
                SUM(calculated_invoiced_amount_usd) as total_invoiced_value,
                SUM(total_payment_made) as total_paid,
                SUM(outstanding_amount) as total_outstanding,
                
                LEAST(
                    ROUND(
                        SUM(total_payment_made) / 
                        NULLIF(SUM(calculated_invoiced_amount_usd), 0) * 100,
                        1
                    ),
                    100.0
                ) as payment_rate,
                
                MIN(inv_date) as first_invoice_date,
                MAX(inv_date) as last_invoice_date
                
            FROM purchase_invoice_full_view
            WHERE inv_date BETWEEN :start_date AND :end_date
                AND invoice_status NOT IN ('Cancelled', 'PO Cancelled')
                AND ({filter_clause})
            GROUP BY vendor_id, vendor
            ORDER BY total_invoiced_value DESC
            """
            
            params = {
                'start_date': start_date.strftime('%Y-%m-%d'),
                'end_date': end_date.strftime('%Y-%m-%d'),
                **filter_params
            }
            
            with self.engine.connect() as conn:
                df = pd.read_sql(text(query), conn, params=params)
            
            logger.info(f"Retrieved invoice summary: {len(df)} vendors")
            return df
            
        except Exception as e:
            logger.error(f"Error getting invoice summary: {e}", exc_info=True)
            raise DataAccessError(
                "Failed to load invoice summary",
                {'error': str(e)}
            )