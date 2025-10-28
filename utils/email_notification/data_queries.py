# utils/email_notification/data_queries.py
"""
Centralized database queries for email notification system - IMPROVED VERSION
Added: Buying Legal Entity filtering capability
"""

import pandas as pd
from sqlalchemy import text
from utils.db import get_db_engine
import logging
from typing import Optional, List

logger = logging.getLogger(__name__)


class EmailNotificationQueries:
    """Handle all database queries for email notification domain"""
    
    def __init__(self):
        self.engine = get_db_engine()
    
    # ========================
    # NEW: BUYING LEGAL ENTITY QUERIES
    # ========================
    
    def get_legal_entities(self):
        """Get list of all legal entities (buying companies)"""
        try:
            query = text("""
            SELECT DISTINCT 
                legal_entity,
                legal_entity_code,
                COUNT(DISTINCT po_number) as po_count,
                SUM(outstanding_arrival_amount_usd) as total_value
            FROM purchase_order_full_view
            WHERE legal_entity IS NOT NULL 
                AND legal_entity != ''
                AND status NOT IN ('COMPLETED', 'CANCELLED')
            GROUP BY legal_entity, legal_entity_code
            ORDER BY legal_entity
            """)
            
            with self.engine.connect() as conn:
                df = pd.read_sql(query, conn)
            
            return df
            
        except Exception as e:
            logger.error(f"Error getting legal entities: {e}")
            return pd.DataFrame()
    
    def _build_entity_filter(self, legal_entities: Optional[List[str]] = None) -> str:
        """
        Build WHERE clause for legal entity filter
        Returns: SQL WHERE clause string
        """
        if legal_entities is None or len(legal_entities) == 0:
            return ""  # No filter
        
        # Escape single quotes in entity names
        escaped_entities = [entity.replace("'", "''") for entity in legal_entities]
        entities_str = "', '".join(escaped_entities)
        
        return f"AND legal_entity IN ('{entities_str}')"
    
    # ========================
    # VENDOR QUERIES - IMPROVED
    # ========================
    
    def get_vendors_with_active_pos(self, date_type='etd', 
                                   legal_entities: Optional[List[str]] = None):
        """Get list of vendors with active POs and their contact information"""
        try:
            date_column = date_type.lower() if date_type.lower() in ['etd', 'eta'] else 'etd'
            entity_filter = self._build_entity_filter(legal_entities)
            
            query = text(f"""
            SELECT 
                vendor_name,
                vendor_code,
                vendor_type,
                vendor_location_type,
                vendor_country_name,
                vendor_contact_email as vendor_email,
                vendor_contact_name as contact_name,
                vendor_contact_phone as contact_phone,
                COUNT(DISTINCT po_number) as active_pos,
                SUM(outstanding_arrival_amount_usd) as outstanding_value,
                MIN({date_column}) as next_{date_column},
                GROUP_CONCAT(DISTINCT created_by SEPARATOR ', ') as po_creators
            FROM purchase_order_full_view
            WHERE status NOT IN ('COMPLETED', 'CANCELLED')
                AND pending_standard_arrival_quantity > 0
                AND vendor_contact_email IS NOT NULL 
                AND vendor_contact_email != ''
                {entity_filter}
            GROUP BY vendor_name, vendor_code, vendor_type, 
                    vendor_location_type, vendor_country_name,
                    vendor_contact_email, vendor_contact_name, 
                    vendor_contact_phone
            ORDER BY outstanding_value DESC
            """)
            
            with self.engine.connect() as conn:
                df = pd.read_sql(query, conn)
            
            # Validate email addresses
            df = df[df['vendor_email'].apply(lambda x: '@' in str(x) if x else False)]
            
            # Remove duplicates based on vendor_name and email
            df = df.drop_duplicates(subset=['vendor_name', 'vendor_email'])
            
            return df
            
        except Exception as e:
            logger.error(f"Error getting vendor list: {e}")
            return pd.DataFrame()
    
    def get_vendor_contacts(self, vendor_names, 
                           legal_entities: Optional[List[str]] = None):
        """Get all contacts for specified vendor names"""
        try:
            if not vendor_names:
                return pd.DataFrame()
            
            entity_filter = self._build_entity_filter(legal_entities)
            
            query = text(f"""
            SELECT 
                CONCAT(vendor_name, '_', vendor_contact_email) as contact_id,
                vendor_name,
                vendor_code,
                vendor_type,
                vendor_location_type,
                vendor_country_name,
                vendor_contact_email as vendor_email,
                vendor_contact_name as contact_name,
                vendor_contact_phone as contact_phone,
                COUNT(DISTINCT po_number) as active_pos,
                SUM(outstanding_arrival_amount_usd) as outstanding_value
            FROM purchase_order_full_view
            WHERE vendor_name IN :vendor_names
                AND vendor_contact_email IS NOT NULL
                AND vendor_contact_email != ''
                AND status NOT IN ('COMPLETED', 'CANCELLED')
                AND pending_standard_arrival_quantity > 0
                {entity_filter}
            GROUP BY vendor_name, vendor_code, vendor_type, 
                    vendor_location_type, vendor_country_name,
                    vendor_contact_email, vendor_contact_name, 
                    vendor_contact_phone
            ORDER BY vendor_name, vendor_contact_name
            """)
            
            with self.engine.connect() as conn:
                df = pd.read_sql(query, conn, params={'vendor_names': tuple(vendor_names)})
            
            # Validate emails
            df = df[df['vendor_email'].apply(lambda x: '@' in str(x) if x else False)]
            
            # Remove duplicates
            df = df.drop_duplicates(subset=['vendor_name', 'vendor_email'])
            
            return df
            
        except Exception as e:
            logger.error(f"Error getting vendor contacts: {e}")
            return pd.DataFrame()
    
    def get_vendor_pos(self, vendor_name: str, weeks_ahead: int = 4, 
                      date_type: str = 'etd', include_overdue: bool = True,
                      legal_entities: Optional[List[str]] = None):
        """Get POs for a specific vendor including overdue and upcoming based on ETD or ETA"""
        try:
            date_column = date_type.lower() if date_type.lower() in ['etd', 'eta'] else 'etd'
            entity_filter = self._build_entity_filter(legal_entities)
            
            query = f"""
            SELECT *
            FROM purchase_order_full_view
            WHERE vendor_name = :vendor_name
                AND status NOT IN ('COMPLETED', 'CANCELLED')
                AND pending_standard_arrival_quantity > 0
                {entity_filter}
            """
            
            params = {'vendor_name': vendor_name}
            
            if include_overdue:
                # Include all POs: overdue + upcoming
                query += f"""
                    AND (
                        {date_column} < CURDATE()  -- Overdue
                        OR ({date_column} >= CURDATE() AND {date_column} <= DATE_ADD(CURDATE(), INTERVAL :weeks WEEK))
                    )
                """
                params['weeks'] = weeks_ahead
            else:
                # Only upcoming POs
                query += f"""
                    AND {date_column} >= CURDATE()
                    AND {date_column} <= DATE_ADD(CURDATE(), INTERVAL :weeks WEEK)
                """
                params['weeks'] = weeks_ahead
            
            query += f" ORDER BY {date_column}, po_number"
            
            with self.engine.connect() as conn:
                df = pd.read_sql(text(query), conn, params=params)
            
            return df
            
        except Exception as e:
            logger.error(f"Error getting vendor POs: {e}")
            return pd.DataFrame()
    
    # ========================
    # CREATOR QUERIES - IMPROVED
    # ========================
    
    def get_creators_list(self, weeks_ahead=4, date_type='etd',
                         legal_entities: Optional[List[str]] = None):
        """Get list of PO creators with active orders"""
        try:
            date_column = date_type.lower()
            entity_filter = self._build_entity_filter(legal_entities)
            
            query = text(f"""
            SELECT DISTINCT 
                e.id,
                e.keycloak_id,
                CONCAT(e.first_name, ' ', e.last_name) as name,
                e.email,
                COUNT(DISTINCT po.po_number) as active_pos,
                SUM(po.outstanding_arrival_amount_usd) as total_outstanding_value,
                COUNT(DISTINCT CASE WHEN po.vendor_location_type = 'International' THEN po.po_number END) as international_pos,
                e.manager_id,
                m.email as manager_email,
                CONCAT(m.first_name, ' ', m.last_name) as manager_name
            FROM employees e
            LEFT JOIN employees m ON e.manager_id = m.id
            INNER JOIN purchase_order_full_view po ON po.created_by = e.email
            WHERE po.status NOT IN ('COMPLETED')
                AND po.{date_column} >= CURDATE()
                AND po.{date_column} <= DATE_ADD(CURDATE(), INTERVAL :weeks WEEK)
                AND po.pending_standard_arrival_quantity > 0
                {entity_filter}
            GROUP BY e.id, e.keycloak_id, e.first_name, e.last_name, 
                     e.email, e.manager_id, m.email, m.first_name, m.last_name
            ORDER BY name
            """)
            
            with self.engine.connect() as conn:
                df = pd.read_sql(query, conn, params={'weeks': weeks_ahead})
            return df
            
        except Exception as e:
            logger.error(f"Error loading creators list: {e}")
            return pd.DataFrame()
    
    def get_creators_overdue(self, date_type='etd',
                            legal_entities: Optional[List[str]] = None):
        """Get list of creators with overdue POs or pending CAN items"""
        try:
            date_column = date_type.lower()
            entity_filter = self._build_entity_filter(legal_entities)
            
            query = text(f"""
            WITH overdue_pos AS (
                SELECT 
                    created_by as email,
                    COUNT(DISTINCT po_number) as overdue_pos,
                    SUM(outstanding_arrival_amount_usd) as overdue_value
                FROM purchase_order_full_view
                WHERE {date_column} < CURDATE()
                    AND status NOT IN ('COMPLETED', 'CANCELLED')
                    AND pending_standard_arrival_quantity > 0
                    {entity_filter}
                GROUP BY created_by
            ),
            pending_cans AS (
                SELECT 
                    po.created_by as email,
                    COUNT(DISTINCT can.arrival_note_number) as pending_cans,
                    SUM(can.pending_value_usd) as pending_can_value
                FROM purchase_order_full_view po
                INNER JOIN can_tracking_full_view can ON can.po_number = po.po_number
                WHERE can.pending_quantity > 0
                    {entity_filter.replace('legal_entity', 'po.legal_entity')}
                GROUP BY po.created_by
            )
            SELECT DISTINCT 
                e.id,
                e.keycloak_id,
                CONCAT(e.first_name, ' ', e.last_name) as name,
                e.email,
                COALESCE(op.overdue_pos, 0) as overdue_pos,
                COALESCE(op.overdue_value, 0) as overdue_value,
                COALESCE(pc.pending_cans, 0) as pending_cans,
                COALESCE(pc.pending_can_value, 0) as pending_can_value,
                e.manager_id,
                m.email as manager_email,
                CONCAT(m.first_name, ' ', m.last_name) as manager_name
            FROM employees e
            LEFT JOIN employees m ON e.manager_id = m.id
            LEFT JOIN overdue_pos op ON op.email = e.email
            LEFT JOIN pending_cans pc ON pc.email = e.email
            WHERE (op.overdue_pos > 0 OR pc.pending_cans > 0)
            ORDER BY name
            """)
            
            with self.engine.connect() as conn:
                df = pd.read_sql(query, conn)
            return df
            
        except Exception as e:
            logger.error(f"Error loading creators with overdue items: {e}")
            return pd.DataFrame()
    
    def get_creators_with_pending_cans(self, 
                                      legal_entities: Optional[List[str]] = None):
        """Get list of creators with pending stock-in items"""
        try:
            entity_filter = self._build_entity_filter(legal_entities)
            
            query = text(f"""
            SELECT DISTINCT 
                e.id,
                e.keycloak_id,
                CONCAT(e.first_name, ' ', e.last_name) as name,
                e.email,
                COUNT(DISTINCT can.arrival_note_number) as pending_cans,
                SUM(can.pending_quantity) as total_pending_qty,
                SUM(can.pending_value_usd) as total_pending_value,
                MAX(can.days_since_arrival) as max_days_pending,
                COUNT(DISTINCT CASE WHEN can.days_since_arrival > 7 THEN can.arrival_note_number END) as urgent_cans,
                COUNT(DISTINCT CASE WHEN can.days_since_arrival > 14 THEN can.arrival_note_number END) as critical_cans,
                e.manager_id,
                m.email as manager_email,
                CONCAT(m.first_name, ' ', m.last_name) as manager_name
            FROM employees e
            LEFT JOIN employees m ON e.manager_id = m.id
            INNER JOIN purchase_order_full_view po ON po.created_by = e.email
            INNER JOIN can_tracking_full_view can ON can.po_number = po.po_number
            WHERE can.pending_quantity > 0
                {entity_filter.replace('legal_entity', 'po.legal_entity')}
            GROUP BY e.id, e.keycloak_id, e.first_name, e.last_name, 
                     e.email, e.manager_id, m.email, m.first_name, m.last_name
            ORDER BY urgent_cans DESC, total_pending_value DESC
            """)
            
            with self.engine.connect() as conn:
                df = pd.read_sql(query, conn)
            return df
            
        except Exception as e:
            logger.error(f"Error loading creators with pending CANs: {e}")
            return pd.DataFrame()
    
    # ========================
    # PO DATA QUERIES - IMPROVED
    # ========================
    
    def get_pos_by_creator(self, creator_email: str, weeks_ahead: int = 4, 
                          date_type: str = 'etd',
                          legal_entities: Optional[List[str]] = None):
        """Get POs created by specific user for upcoming period"""
        try:
            date_column = date_type.lower()
            entity_filter = self._build_entity_filter(legal_entities)
            
            query = text(f"""
            SELECT *
            FROM purchase_order_full_view
            WHERE created_by = :creator_email
                AND status NOT IN ('COMPLETED')
                AND {date_column} >= CURDATE()
                AND {date_column} <= DATE_ADD(CURDATE(), INTERVAL :weeks WEEK)
                AND pending_standard_arrival_quantity > 0
                {entity_filter}
            ORDER BY {date_column}, vendor_name, po_number
            """)
            
            with self.engine.connect() as conn:
                df = pd.read_sql(query, conn, params={
                    'creator_email': creator_email,
                    'weeks': weeks_ahead
                })
            return df
            
        except Exception as e:
            logger.error(f"Error getting POs by creator: {e}")
            return pd.DataFrame()
    
    def get_overdue_pos_by_creator(self, creator_email: str, date_type: str = 'etd',
                                  legal_entities: Optional[List[str]] = None):
        """Get overdue POs for specific creator"""
        try:
            date_column = date_type.lower()
            entity_filter = self._build_entity_filter(legal_entities)
            
            query = text(f"""
            SELECT *,
                DATEDIFF(CURDATE(), {date_column}) as days_overdue
            FROM purchase_order_full_view
            WHERE created_by = :creator_email
                AND {date_column} < CURDATE()
                AND status NOT IN ('COMPLETED')
                AND pending_standard_arrival_quantity > 0
                {entity_filter}
            ORDER BY {date_column}, vendor_name, po_number
            """)
            
            with self.engine.connect() as conn:
                df = pd.read_sql(query, conn, params={'creator_email': creator_email})
            return df
            
        except Exception as e:
            logger.error(f"Error getting overdue POs: {e}")
            return pd.DataFrame()
    
    def get_pending_cans_by_creator(self, creator_email: str,
                                   legal_entities: Optional[List[str]] = None):
        """Get pending container arrival notes for specific creator"""
        try:
            entity_filter = self._build_entity_filter(legal_entities)
            
            query = text(f"""
            SELECT 
                can.*,
                po.buying_legal_entity
            FROM can_tracking_full_view can
            INNER JOIN purchase_order_full_view po ON can.po_number = po.po_number
            WHERE po.created_by = :creator_email
                AND can.pending_quantity > 0
                {entity_filter.replace('legal_entity', 'po.legal_entity')}
            ORDER BY can.days_since_arrival DESC, can.pending_value_usd DESC
            """)
            
            with self.engine.connect() as conn:
                df = pd.read_sql(query, conn, params={'creator_email': creator_email})
            return df
            
        except Exception as e:
            logger.error(f"Error getting pending CANs: {e}")
            return pd.DataFrame()
    
    def get_international_pos(self, weeks_ahead: int = 4, date_type: str = 'etd',
                             legal_entities: Optional[List[str]] = None):
        """Get international POs for custom clearance"""
        try:
            date_column = date_type.lower()
            entity_filter = self._build_entity_filter(legal_entities)
            
            query = text(f"""
            SELECT *
            FROM purchase_order_full_view
            WHERE vendor_location_type = 'International'
                AND status NOT IN ('COMPLETED')
                AND {date_column} >= CURDATE()
                AND {date_column} <= DATE_ADD(CURDATE(), INTERVAL :weeks WEEK)
                AND pending_standard_arrival_quantity > 0
                {entity_filter}
            ORDER BY {date_column}, vendor_name, po_number
            """)
            
            with self.engine.connect() as conn:
                df = pd.read_sql(query, conn, params={'weeks': weeks_ahead})
            return df
            
        except Exception as e:
            logger.error(f"Error getting international POs: {e}")
            return pd.DataFrame()