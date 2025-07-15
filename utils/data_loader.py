# utils/data_loader.py - Data loading module for inbound logistics

import pandas as pd
import streamlit as st
from sqlalchemy import text
from .db import get_db_engine
import logging
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

class InboundDataLoader:
    """Load and process inbound logistics data from database"""
    
    def __init__(self):
        self.engine = get_db_engine()
    
    @st.cache_data(ttl=300)  # Cache for 5 minutes
    def load_po_data(_self, filters=None):
        """Load purchase order data from purchase_order_full_view"""
        try:
            # Base query
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
                vendor_contact_name,
                vendor_contact_email,
                vendor_contact_phone,
                
                -- Legal entity
                legal_entity,
                legal_entity_code,
                
                -- Ship/Bill to info
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
            
            # Apply filters if provided
            params = {}
            
            if filters:
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
                
                if filters.get('created_by'):
                    query += " AND created_by = :created_by"
                    params['created_by'] = filters['created_by']
                
                if filters.get('vendors'):
                    query += " AND vendor_name IN :vendors"
                    params['vendors'] = tuple(filters['vendors'])
                
                if filters.get('status'):
                    query += " AND status IN :status"
                    params['status'] = tuple(filters['status'])
                
                if filters.get('products'):
                    query += " AND product_name IN :products"
                    params['products'] = tuple(filters['products'])
                
                if filters.get('brands'):
                    query += " AND brand IN :brands"
                    params['brands'] = tuple(filters['brands'])
                
                # New filters
                if filters.get('pt_codes'):
                    query += " AND pt_code IN :pt_codes"
                    params['pt_codes'] = tuple(filters['pt_codes'])
                
                if filters.get('vendor_types'):
                    query += " AND vendor_type IN :vendor_types"
                    params['vendor_types'] = tuple(filters['vendor_types'])
                
                if filters.get('vendor_location_types'):
                    query += " AND vendor_location_type IN :vendor_location_types"
                    params['vendor_location_types'] = tuple(filters['vendor_location_types'])
                
                # Special filters
                if filters.get('overdue_only'):
                    query += " AND etd < CURDATE() AND status != 'COMPLETED'"
                
                if filters.get('over_delivered_only'):
                    query += " AND is_over_delivered = 'Y'"
                
                if filters.get('critical_products'):
                    # Products with high gap in outbound
                    query += """ AND product_name IN (
                        SELECT DISTINCT product_pn 
                        FROM delivery_full_view 
                        WHERE product_gap_quantity > 1000
                    )"""
            
            # Order by
            query += " ORDER BY po_date DESC, po_number DESC, po_line_id DESC"
            
            # Execute query
            with _self.engine.connect() as conn:
                df = pd.read_sql(text(query), conn, params=params)
            
            logger.info(f"Loaded {len(df)} PO records")
            return df
            
        except Exception as e:
            logger.error(f"Error loading PO data: {e}", exc_info=True)
            st.error(f"Failed to load purchase order data: {str(e)}")
            return pd.DataFrame()

    @st.cache_data(ttl=300)
    def load_can_pending_data(_self, filters=None):
        """Load CAN data from can_tracking_full_view with optional pending filter"""
        try:
            # Base query using can_tracking_full_view
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
                
                -- Vendor info with details
                vendor,
                vendor_code,
                vendor_type,
                vendor_location_type,
                vendor_street,
                vendor_zip_code,
                vendor_state_province,
                vendor_country_code,
                vendor_country_name,
                vendor_contact_name,
                vendor_contact_email,
                vendor_contact_phone,
                
                -- Consignee info with details
                consignee,
                consignee_code,
                consignee_street,
                consignee_zip_code,
                consignee_state_province,
                consignee_country_code,
                consignee_country_name,
                buyer_contact_name,
                buyer_contact_email,
                buyer_contact_phone,
                
                -- Ship To & Bill To
                ship_to_company_name,
                ship_to_company_code,
                ship_to_contact_name,
                ship_to_contact_email,
                bill_to_company_name,
                bill_to_company_code,
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
                landed_cost,
                usd_landed_cost_currency_exchange_rate,
                landed_cost_usd,
                
                -- Quantity flow
                total_arrived_quantity,
                arrival_quantity,
                total_stocked_in,
                pending_quantity,
                pending_value_usd,
                pending_percent,
                days_since_arrival,
                days_pending,
                
                -- Status
                stocked_in_status,
                can_status
                
            FROM can_tracking_full_view
            WHERE 1=1
            """
            
            # Apply filters if provided
            params = {}
            
            # Default filter - only show pending items (same as old view behavior)
            if not filters or filters.get('pending_only', True):
                query += " AND pending_quantity > 0"
            
            if filters:
                if filters.get('arrival_date_from'):
                    query += " AND arrival_date >= :arrival_date_from"
                    params['arrival_date_from'] = filters['arrival_date_from']
                
                if filters.get('arrival_date_to'):
                    query += " AND arrival_date <= :arrival_date_to"
                    params['arrival_date_to'] = filters['arrival_date_to']
                
                if filters.get('vendors'):
                    query += " AND vendor IN :vendors"
                    params['vendors'] = tuple(filters['vendors'])
                
                if filters.get('vendor_types'):
                    query += " AND vendor_type IN :vendor_types"
                    params['vendor_types'] = tuple(filters['vendor_types'])
                
                if filters.get('vendor_location_types'):
                    query += " AND vendor_location_type IN :vendor_location_types"
                    params['vendor_location_types'] = tuple(filters['vendor_location_types'])
                
                if filters.get('consignees'):
                    query += " AND consignee IN :consignees"
                    params['consignees'] = tuple(filters['consignees'])
                
                if filters.get('products'):
                    query += " AND product_name IN :products"
                    params['products'] = tuple(filters['products'])
                
                if filters.get('can_status'):
                    query += " AND can_status IN :can_status"
                    params['can_status'] = tuple(filters['can_status'])
                
                if filters.get('stocked_in_status'):
                    query += " AND stocked_in_status IN :stocked_in_status"
                    params['stocked_in_status'] = tuple(filters['stocked_in_status'])
                
                # Days since arrival filter
                if filters.get('min_days_pending'):
                    query += " AND days_since_arrival >= :min_days"
                    params['min_days'] = filters['min_days_pending']
                
                if filters.get('max_days_pending'):
                    query += " AND days_since_arrival <= :max_days"
                    params['max_days'] = filters['max_days_pending']
                
                # PO type filter
                if filters.get('po_types'):
                    query += " AND po_type IN :po_types"
                    params['po_types'] = tuple(filters['po_types'])
            
            # Order by urgency
            query += " ORDER BY days_since_arrival DESC, pending_value_usd DESC"
            
            # Execute query
            with _self.engine.connect() as conn:
                df = pd.read_sql(text(query), conn, params=params)
            
            logger.info(f"Loaded {len(df)} CAN records")
            return df
            
        except Exception as e:
            logger.error(f"Error loading CAN data: {e}")
            st.error(f"Failed to load CAN data: {str(e)}")
            return pd.DataFrame()
    
    def get_filter_options(self):
        """Get unique values for filters"""
        try:
            queries = {
                'vendors': """
                    SELECT DISTINCT vendor_name 
                    FROM purchase_order_full_view 
                    WHERE vendor_name IS NOT NULL 
                    ORDER BY vendor_name
                """,
                'products': """
                    SELECT DISTINCT product_name 
                    FROM purchase_order_full_view 
                    WHERE product_name IS NOT NULL 
                    ORDER BY product_name
                """,
                'pt_codes': """
                    SELECT DISTINCT pt_code 
                    FROM purchase_order_full_view 
                    WHERE pt_code IS NOT NULL 
                    ORDER BY pt_code
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
                'po_types': """
                    SELECT DISTINCT po_type 
                    FROM can_tracking_full_view 
                    WHERE po_type IS NOT NULL 
                    ORDER BY po_type
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
    
    def get_vendor_list(self):
        """Get list of vendors with active POs"""
        try:
            query = text("""
            SELECT DISTINCT 
                vendor_name,
                vendor_type,
                vendor_location_type,
                COUNT(DISTINCT po_number) as active_pos,
                SUM(outstanding_arrival_amount_usd) as outstanding_value,
                MIN(etd) as next_etd
            FROM purchase_order_full_view
            WHERE status NOT IN ('COMPLETED', 'CANCELLED')
            GROUP BY vendor_name, vendor_type, vendor_location_type
            ORDER BY outstanding_value DESC
            """)
            
            with self.engine.connect() as conn:
                df = pd.read_sql(query, conn)
            
            return df
            
        except Exception as e:
            logger.error(f"Error getting vendor list: {e}")
            return pd.DataFrame()
    
    def get_overdue_pos(self):
        """Get overdue purchase orders"""
        try:
            query = text("""
            SELECT 
                po_number,
                vendor_name,
                vendor_location_type,
                COUNT(DISTINCT po_line_id) as line_items,
                SUM(pending_standard_arrival_quantity) as pending_qty,
                SUM(outstanding_arrival_amount_usd) as outstanding_value,
                MIN(etd) as original_etd,
                DATEDIFF(CURDATE(), MIN(etd)) as days_overdue,
                GROUP_CONCAT(DISTINCT pt_code SEPARATOR ', ') as products
            FROM purchase_order_full_view
            WHERE etd < CURDATE()
                AND status NOT IN ('COMPLETED', 'CANCELLED')
                AND pending_standard_arrival_quantity > 0
            GROUP BY po_number, vendor_name, vendor_location_type
            ORDER BY days_overdue DESC
            """)
            
            with self.engine.connect() as conn:
                df = pd.read_sql(query, conn)
            
            return df
            
        except Exception as e:
            logger.error(f"Error getting overdue POs: {e}")
            return pd.DataFrame()
    
    def get_pending_stockin_summary(self, pending_only=True):
        """Get summary of pending stock-in by warehouse/location"""
        try:
            query = """
            SELECT 
                can_status,
                vendor_location_type,
                COUNT(DISTINCT arrival_note_number) as can_count,
                COUNT(*) as line_items,
                SUM(pending_quantity) as total_pending_qty,
                SUM(pending_value_usd) as total_pending_value,
                AVG(days_since_arrival) as avg_days_pending,
                MAX(days_since_arrival) as max_days_pending
            FROM can_tracking_full_view
            WHERE 1=1
            """
            
            if pending_only:
                query += " AND pending_quantity > 0"
            
            query += """
            GROUP BY can_status, vendor_location_type
            ORDER BY total_pending_value DESC
            """
            
            query = text(query)
            
            with self.engine.connect() as conn:
                df = pd.read_sql(query, conn)
            
            return df
            
        except Exception as e:
            logger.error(f"Error getting pending stock-in summary: {e}")
            return pd.DataFrame()
    
    def get_vendor_performance_metrics(self, vendor_name=None, months=6):
        """Get vendor performance metrics"""
        try:
            query = """
            SELECT 
                vendor_name,
                vendor_type,
                vendor_location_type,
                COUNT(DISTINCT po_number) as total_pos,
                
                -- Completion metrics
                SUM(CASE WHEN status = 'COMPLETED' THEN 1 ELSE 0 END) as completed_pos,
                AVG(arrival_completion_percent) as avg_completion_rate,
                
                -- On-time metrics
                SUM(CASE WHEN eta >= etd AND status = 'COMPLETED' THEN 1 ELSE 0 END) as on_time_deliveries,
                
                -- Over-delivery metrics
                SUM(CASE WHEN is_over_delivered = 'Y' THEN 1 ELSE 0 END) as over_deliveries,
                AVG(CASE WHEN is_over_delivered = 'Y' 
                    THEN (total_standard_arrived_quantity - standard_quantity) / standard_quantity * 100 
                    ELSE 0 END) as avg_over_delivery_percent,
                
                -- Financial metrics
                SUM(total_amount_usd) as total_po_value,
                SUM(outstanding_invoiced_amount_usd) as outstanding_invoices
                
            FROM purchase_order_full_view
            WHERE po_date >= DATE_SUB(CURDATE(), INTERVAL :months MONTH)
            """
            
            params = {'months': months}
            
            if vendor_name:
                query += " AND vendor_name = :vendor_name"
                params['vendor_name'] = vendor_name
            
            query += " GROUP BY vendor_name, vendor_type, vendor_location_type ORDER BY total_po_value DESC"
            
            with self.engine.connect() as conn:
                df = pd.read_sql(text(query), conn, params=params)
            
            # Calculate on-time delivery rate
            if not df.empty:
                df['on_time_rate'] = (df['on_time_deliveries'] / df['completed_pos'] * 100).fillna(0)
                df['completion_rate'] = (df['completed_pos'] / df['total_pos'] * 100).fillna(0)
            
            return df
            
        except Exception as e:
            logger.error(f"Error getting vendor performance: {e}")
            return pd.DataFrame()
    
    def get_product_demand_vs_incoming(self):
        """Get product demand vs incoming supply analysis with current stock"""
        try:
            query = text("""
            WITH product_demand AS (
                -- Get demand and current GAP from delivery view
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
                -- Get incoming from PO view
                SELECT 
                    product_name as product_pn,
                    pt_code,
                    SUM(pending_standard_arrival_quantity) as incoming_qty,
                    MIN(etd) as next_arrival_date,
                    COUNT(DISTINCT po_number) as pending_po_count
                FROM purchase_order_full_view
                WHERE status != 'COMPLETED'
                    AND pending_standard_arrival_quantity > 0
                GROUP BY product_name, pt_code
            )
            SELECT 
                COALESCE(d.product_pn, s.product_pn) as product,
                COALESCE(d.pt_code, s.pt_code) as pt_code,
                
                -- Demand & Stock
                COALESCE(d.total_demand, 0) as total_demand,
                COALESCE(d.current_stock, 0) as current_stock,
                COALESCE(s.incoming_qty, 0) as incoming_supply,
                
                -- Total available (current + incoming)
                COALESCE(d.current_stock, 0) + COALESCE(s.incoming_qty, 0) as total_available,
                
                -- GAP Analysis
                COALESCE(d.current_gap, d.total_demand) as current_gap_qty,
                
                -- Net requirement after considering incoming
                GREATEST(0, COALESCE(d.total_demand, 0) - COALESCE(d.current_stock, 0) - COALESCE(s.incoming_qty, 0)) as net_requirement,
                
                -- Coverage analysis
                COALESCE(d.current_fulfill_rate, 0) as current_coverage_percent,
                CASE 
                    WHEN COALESCE(d.total_demand, 0) = 0 THEN 100
                    ELSE ROUND((COALESCE(d.current_stock, 0) + COALESCE(s.incoming_qty, 0)) / COALESCE(d.total_demand, 0) * 100, 2)
                END as total_coverage_percent,
                
                -- Supply info
                s.next_arrival_date,
                COALESCE(s.pending_po_count, 0) as pending_po_count,
                
                -- Status
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
            ORDER BY net_requirement DESC, current_gap_qty DESC
            """)
            
            with self.engine.connect() as conn:
                df = pd.read_sql(query, conn)
            
            return df
            
        except Exception as e:
            logger.error(f"Error getting product demand vs incoming: {e}")
            return pd.DataFrame()
    
    def get_po_timeline_data(self, weeks_ahead=8):
        """Get PO timeline data for visualization"""
        try:
            today = datetime.now().date()
            end_date = today + timedelta(weeks=weeks_ahead)
            
            query = text("""
            SELECT 
                DATE(etd) as arrival_date,
                vendor_name,
                vendor_location_type,
                COUNT(DISTINCT po_number) as po_count,
                COUNT(po_line_id) as line_items,
                SUM(pending_standard_arrival_quantity) as arrival_qty,
                SUM(outstanding_arrival_amount_usd) as arrival_value,
                GROUP_CONCAT(DISTINCT pt_code SEPARATOR ', ') as products
            FROM purchase_order_full_view
            WHERE etd >= :today
                AND etd <= :end_date
                AND status != 'COMPLETED'
                AND pending_standard_arrival_quantity > 0
            GROUP BY DATE(etd), vendor_name, vendor_location_type
            ORDER BY arrival_date, vendor_name
            """)
            
            with self.engine.connect() as conn:
                df = pd.read_sql(query, conn, params={
                    'today': today,
                    'end_date': end_date
                })
            
            return df
            
        except Exception as e:
            logger.error(f"Error getting PO timeline: {e}")
            return pd.DataFrame()
    
    def get_financial_summary(self):
        """Get financial summary for dashboard"""
        try:
            query = text("""
            SELECT 
                -- Outstanding amounts
                SUM(outstanding_arrival_amount_usd) as total_outstanding_arrival,
                SUM(outstanding_invoiced_amount_usd) as total_outstanding_invoice,
                
                -- By currency
                currency,
                COUNT(DISTINCT po_number) as po_count,
                SUM(total_amount) as total_amount_local,
                AVG(usd_exchange_rate) as avg_exchange_rate
                
            FROM purchase_order_full_view
            WHERE status != 'COMPLETED'
            GROUP BY currency
            ORDER BY total_amount_local DESC
            """)
            
            with self.engine.connect() as conn:
                df = pd.read_sql(query, conn)
            
            return df
            
        except Exception as e:
            logger.error(f"Error getting financial summary: {e}")
            return pd.DataFrame()
    
    def get_supply_chain_health_summary(self):
        """Get supply chain health metrics for dashboard"""
        try:
            query = text("""
            WITH supply_analysis AS (
                SELECT 
                    p.pt_code,
                    p.product_pn,
                    p.total_demand,
                    p.current_stock,
                    p.current_gap_qty,
                    COALESCE(inc.incoming_qty, 0) as incoming_supply,
                    p.current_stock + COALESCE(inc.incoming_qty, 0) as total_available,
                    GREATEST(0, p.total_demand - p.current_stock - COALESCE(inc.incoming_qty, 0)) as net_requirement,
                    CASE 
                        WHEN p.total_demand = 0 THEN 'No Demand'
                        WHEN p.current_stock >= p.total_demand THEN 'Sufficient Stock'
                        WHEN (p.current_stock + COALESCE(inc.incoming_qty, 0)) >= p.total_demand THEN 'Will be Sufficient'
                        WHEN COALESCE(inc.incoming_qty, 0) > 0 THEN 'Partial Coverage'
                        ELSE 'Need to Order'
                    END as supply_status
                FROM (
                    SELECT 
                        product_pn,
                        pt_code,
                        SUM(product_total_remaining_demand) as total_demand,
                        SUM(total_instock_all_warehouses) as current_stock,
                        MAX(product_gap_quantity) as current_gap_qty
                    FROM delivery_full_view
                    WHERE product_total_remaining_demand > 0
                    GROUP BY product_pn, pt_code
                ) p
                LEFT JOIN (
                    SELECT 
                        product_name as product_pn,
                        pt_code,
                        SUM(pending_standard_arrival_quantity) as incoming_qty
                    FROM purchase_order_full_view
                    WHERE status != 'COMPLETED'
                        AND pending_standard_arrival_quantity > 0
                    GROUP BY product_name, pt_code
                ) inc ON p.product_pn = inc.product_pn AND p.pt_code = inc.pt_code
            )
            SELECT 
                COUNT(CASE WHEN supply_status = 'Need to Order' THEN 1 END) as products_need_order,
                COUNT(CASE WHEN supply_status = 'Partial Coverage' THEN 1 END) as products_partial_coverage,
                COUNT(CASE WHEN supply_status = 'Will be Sufficient' THEN 1 END) as products_will_be_sufficient,
                COUNT(CASE WHEN supply_status = 'Sufficient Stock' THEN 1 END) as products_sufficient_stock,
                COUNT(*) as total_active_products,
                SUM(net_requirement) as total_net_requirement,
                AVG(CASE WHEN total_demand > 0 
                    THEN (current_stock + incoming_supply) / total_demand * 100 
                    ELSE 100 END) as avg_coverage_percent
            FROM supply_analysis
            """)
            
            with self.engine.connect() as conn:
                result = conn.execute(query).fetchone()
                
            return {
                'products_need_order': result[0] or 0,
                'products_partial_coverage': result[1] or 0,
                'products_will_be_sufficient': result[2] or 0,
                'products_sufficient_stock': result[3] or 0,
                'total_active_products': result[4] or 0,
                'total_net_requirement': result[5] or 0,
                'avg_coverage_percent': result[6] or 0
            }
            
        except Exception as e:
            logger.error(f"Error getting supply chain health: {e}")
            return {}

    def load_po_data_for_customs(self, filters=None):
        """Load PO data specifically for customs clearance (international vendors only)"""
        try:
            query = """
            SELECT *
            FROM purchase_order_full_view
            WHERE vendor_location_type = 'International'
                AND status NOT IN ('COMPLETED')
            """
            
            params = {}
            
            if filters:
                if filters.get('etd_from'):
                    query += " AND etd >= :etd_from"
                    params['etd_from'] = filters['etd_from']
                
                if filters.get('etd_to'):
                    query += " AND etd <= :etd_to"
                    params['etd_to'] = filters['etd_to']
            
            query += " ORDER BY etd, vendor_country_name, po_number"
            
            with self.engine.connect() as conn:
                df = pd.read_sql(text(query), conn, params=params)
            
            return df
            
        except Exception as e:
            logger.error(f"Error loading customs PO data: {e}")
            return pd.DataFrame()

    def get_overdue_pos_by_creator(self, creator_email):
            """Get overdue POs for a specific creator"""
            try:
                query = text("""
                SELECT 
                    po_number,
                    vendor_name,
                    vendor_country_name,
                    COUNT(DISTINCT po_line_id) as line_items,
                    SUM(pending_standard_arrival_quantity) as pending_qty,
                    SUM(outstanding_arrival_amount_usd) as outstanding_value,
                    MIN(etd) as original_etd,
                    DATEDIFF(CURDATE(), MIN(etd)) as days_overdue,
                    GROUP_CONCAT(DISTINCT pt_code SEPARATOR ', ') as products
                FROM purchase_order_full_view
                WHERE created_by = :creator_email
                    AND etd < CURDATE()
                    AND status NOT IN ('COMPLETED')
                    AND pending_standard_arrival_quantity > 0
                GROUP BY po_number, vendor_name, vendor_country_name
                ORDER BY days_overdue DESC
                """)
                
                with self.engine.connect() as conn:
                    df = pd.read_sql(query, conn, params={'creator_email': creator_email})
                
                return df
                
            except Exception as e:
                logger.error(f"Error getting overdue POs for creator: {e}")
                return pd.DataFrame()

    def get_pending_cans_by_creator(self, creator_email):
            """Get pending CAN items for POs created by specific person"""
            try:
                query = text("""
                SELECT DISTINCT
                    can.*
                FROM can_tracking_full_view can
                INNER JOIN purchase_order_full_view po ON can.po_number = po.po_number
                WHERE po.created_by = :creator_email
                    AND can.days_since_arrival > 7
                    AND can.pending_quantity > 0
                ORDER BY can.days_since_arrival DESC
                """)
                
                with self.engine.connect() as conn:
                    df = pd.read_sql(query, conn, params={'creator_email': creator_email})
                
                return df
                
            except Exception as e:
                logger.error(f"Error getting pending CANs for creator: {e}")
                return pd.DataFrame()

    def get_can_vendor_summary(self, pending_only=True):
        """Get vendor summary for CANs"""
        try:
            query = """
            SELECT 
                vendor,
                vendor_type,
                vendor_location_type,
                vendor_country_name,
                COUNT(DISTINCT arrival_note_number) as can_count,
                COUNT(*) as line_items,
                SUM(pending_quantity) as total_pending_qty,
                SUM(pending_value_usd) as total_pending_value,
                AVG(days_since_arrival) as avg_days_pending,
                MAX(days_since_arrival) as max_days_pending
            FROM can_tracking_full_view
            WHERE 1=1
            """
            
            if pending_only:
                query += " AND pending_quantity > 0"
            
            query += """
            GROUP BY vendor, vendor_type, vendor_location_type, vendor_country_name
            ORDER BY total_pending_value DESC
            """
            
            query = text(query)
            
            with self.engine.connect() as conn:
                df = pd.read_sql(query, conn)
            
            return df
            
        except Exception as e:
            logger.error(f"Error getting CAN vendor summary: {e}")
            return pd.DataFrame()
        
    def load_po_data_for_customs(self, filters=None):
            """Load PO data specifically for customs clearance (international vendors only)"""
            try:
                query = """
                SELECT *
                FROM purchase_order_full_view
                WHERE vendor_location_type = 'International'
                    AND status NOT IN ('COMPLETED')
                    AND pending_standard_arrival_quantity > 0
                """
                
                params = {}
                
                if filters:
                    if filters.get('etd_from'):
                        query += " AND etd >= :etd_from"
                        params['etd_from'] = filters['etd_from']
                    
                    if filters.get('etd_to'):
                        query += " AND etd <= :etd_to"
                        params['etd_to'] = filters['etd_to']
                
                query += " ORDER BY etd, vendor_country_name, po_number"
                
                with self.engine.connect() as conn:
                    df = pd.read_sql(text(query), conn, params=params)
                
                return df
                
            except Exception as e:
                logger.error(f"Error loading customs PO data: {e}")
                return pd.DataFrame()

    def load_can_data_for_customs(self, filters=None):
            """Load CAN data specifically for customs clearance (international vendors only)"""
            try:
                # Base query - international CANs with pending items
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
                    
                    -- Vendor info with details
                    vendor,
                    vendor_code,
                    vendor_type,
                    vendor_location_type,
                    vendor_country_code,
                    vendor_country_name,
                    vendor_contact_name,
                    vendor_contact_email,
                    vendor_contact_phone,
                    
                    -- Product info
                    product_name,
                    brand,
                    package_size,
                    pt_code,
                    hs_code,
                    shelf_life,
                    standard_uom,
                    
                    -- Quantity & Cost
                    buying_quantity,
                    standard_quantity,
                    pending_quantity,
                    pending_value_usd,
                    days_since_arrival,
                    
                    -- Status
                    stocked_in_status,
                    can_status
                    
                FROM can_tracking_full_view
                WHERE vendor_location_type = 'International'
                    AND pending_quantity > 0
                """
                
                params = {}
                
                if filters:
                    if filters.get('arrival_date_from'):
                        query += " AND arrival_date >= :arrival_date_from"
                        params['arrival_date_from'] = filters['arrival_date_from']
                    
                    if filters.get('arrival_date_to'):
                        query += " AND arrival_date <= :arrival_date_to"
                        params['arrival_date_to'] = filters['arrival_date_to']
                
                query += " ORDER BY arrival_date, vendor_country_name, arrival_note_number"
                
                with self.engine.connect() as conn:
                    df = pd.read_sql(text(query), conn, params=params)
                
                return df
                
            except Exception as e:
                logger.error(f"Error loading customs CAN data: {e}")
                return pd.DataFrame()

    def get_international_shipment_summary(self, weeks_ahead=4):
            """Get summary of international shipments (POs and CANs) for customs"""
            try:
                today = datetime.now().date()
                end_date = today + timedelta(weeks=weeks_ahead)
                
                query = text("""
                WITH po_summary AS (
                    SELECT 
                        'Purchase Orders' as shipment_type,
                        COUNT(DISTINCT po_number) as count,
                        COUNT(DISTINCT vendor_name) as vendor_count,
                        COUNT(DISTINCT vendor_country_name) as country_count,
                        SUM(outstanding_arrival_amount_usd) as total_value_usd
                    FROM purchase_order_full_view
                    WHERE vendor_location_type = 'International'
                        AND status NOT IN ('COMPLETED')
                        AND etd >= :today
                        AND etd <= :end_date
                        AND pending_standard_arrival_quantity > 0
                ),
                can_summary AS (
                    SELECT 
                        'Container Arrivals' as shipment_type,
                        COUNT(DISTINCT arrival_note_number) as count,
                        COUNT(DISTINCT vendor) as vendor_count,
                        COUNT(DISTINCT vendor_country_name) as country_count,
                        SUM(pending_value_usd) as total_value_usd
                    FROM can_tracking_full_view
                    WHERE vendor_location_type = 'International'
                        AND pending_quantity > 0
                        AND arrival_date >= :today
                        AND arrival_date <= :end_date
                ),
                combined_summary AS (
                    SELECT * FROM po_summary
                    UNION ALL
                    SELECT * FROM can_summary
                )
                SELECT 
                    MAX(CASE WHEN shipment_type = 'Purchase Orders' THEN count ELSE 0 END) as po_count,
                    MAX(CASE WHEN shipment_type = 'Container Arrivals' THEN count ELSE 0 END) as can_count,
                    COUNT(DISTINCT shipment_type) as shipment_types,
                    SUM(vendor_count) as total_vendors,
                    MAX(country_count) as total_countries,
                    SUM(total_value_usd) as total_value
                FROM combined_summary
                """)
                
                with self.engine.connect() as conn:
                    result = pd.read_sql(query, conn, params={
                        'today': today,
                        'end_date': end_date
                    })
                    
                if not result.empty:
                    return result.iloc[0].to_dict()
                else:
                    return {
                        'po_count': 0,
                        'can_count': 0,
                        'shipment_types': 0,
                        'total_vendors': 0,
                        'total_countries': 0,
                        'total_value': 0
                    }
                    
            except Exception as e:
                logger.error(f"Error getting international shipment summary: {e}")
                return {
                    'po_count': 0,
                    'can_count': 0,
                    'shipment_types': 0,
                    'total_vendors': 0,
                    'total_countries': 0,
                    'total_value': 0
                }
            

        

