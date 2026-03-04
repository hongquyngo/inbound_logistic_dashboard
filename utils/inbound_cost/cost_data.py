# utils/inbound_cost/cost_data.py
# All DB queries for Inbound Logistic Cost module
# Primary source: inbound_logistic_charge_full_view

import pandas as pd
from sqlalchemy import text
import streamlit as st
import logging
from datetime import datetime, date
from typing import Dict, List, Optional, Tuple

from ..db import get_db_engine

logger = logging.getLogger(__name__)


# ============================================================================
# READ — LIST / DETAIL
# ============================================================================

@st.cache_data(ttl=60, show_spinner=False)
def get_inbound_costs(limit: int = 500) -> pd.DataFrame:
    """
    Load cost entries from inbound_logistic_charge_full_view.
    Returns flat DataFrame ready for display/filtering.
    """
    try:
        engine = get_db_engine()
        query = text("""
        SELECT
            cost_id,
            cost_type_id,
            logistic_charge,
            category,
            arrival_id,
            can_number,
            arrival_date,
            arrival_year,
            arrival_month,
            is_date_adjusted,
            arrival_status,
            ship_method,
            ttl_weight,
            dimension,
            warehouse_id,
            warehouse_name,
            warehouse_country,
            sender_id,
            sender,
            sender_code,
            sender_country,
            receiver_id,
            receiver,
            receiver_code,
            receiver_country,
            shipment_type,
            logistics_vendor_id,
            courier,
            courier_code,
            amount,
            currency_code,
            usd_exchange_rate,
            amount_usd,
            total_arrival_qty,
            arrival_line_count,
            cost_per_unit_usd,
            product_codes,
            product_names,
            doc_count,
            doc_paths,
            doc_names,
            cost_created_by,
            cost_created_date,
            cost_modified_date
        FROM inbound_logistic_charge_full_view
        ORDER BY arrival_date DESC, cost_id ASC
        LIMIT :limit
        """)
        with engine.connect() as conn:
            df = pd.read_sql(query, conn, params={"limit": limit})
        return df
    except Exception as e:
        logger.error(f"Error loading inbound costs: {e}")
        return pd.DataFrame()


@st.cache_data(ttl=120, show_spinner=False)
def get_cost_type_options() -> pd.DataFrame:
    """Master list of delivery cost types (INTERNATIONAL + LOCAL)."""
    try:
        engine = get_db_engine()
        query = text("""
        SELECT id, name, type
        FROM delivery_cost_entity
        WHERE delete_flag = 0
        ORDER BY type, name
        """)
        with engine.connect() as conn:
            return pd.read_sql(query, conn)
    except Exception as e:
        logger.error(f"Error loading cost types: {e}")
        return pd.DataFrame()


@st.cache_data(ttl=120, show_spinner=False)
def get_arrival_options(limit: int = 300) -> pd.DataFrame:
    """Recent arrivals for dropdown selection in create/edit dialog."""
    try:
        engine = get_db_engine()
        query = text("""
        SELECT
            a.id,
            a.arrival_note_number,
            DATE(COALESCE(a.adjust_arrival_date, a.arrival_date)) AS arrival_date,
            a.status,
            s.english_name AS sender,
            r.english_name AS receiver,
            wh.name AS warehouse_name
        FROM arrivals a
        LEFT JOIN companies s  ON a.sender_id   = s.id
        LEFT JOIN companies r  ON a.receiver_id = r.id
        LEFT JOIN warehouses wh ON a.warehouse_id = wh.id
        WHERE a.delete_flag = 0
        ORDER BY a.arrival_date DESC
        LIMIT :limit
        """)
        with engine.connect() as conn:
            return pd.read_sql(query, conn, params={"limit": limit})
    except Exception as e:
        logger.error(f"Error loading arrivals: {e}")
        return pd.DataFrame()


@st.cache_data(ttl=300, show_spinner=False)
def get_vendor_options() -> pd.DataFrame:
    """Logistics vendor (courier / forwarder) options."""
    try:
        engine = get_db_engine()
        query = text("""
        SELECT id, english_name AS name, company_code
        FROM companies
        WHERE delete_flag = 0
        ORDER BY english_name
        """)
        with engine.connect() as conn:
            return pd.read_sql(query, conn)
    except Exception as e:
        logger.error(f"Error loading vendors: {e}")
        return pd.DataFrame()


@st.cache_data(ttl=300, show_spinner=False)
def get_filter_options() -> Dict:
    """Distinct values for filter dropdowns — cached 5 min."""
    try:
        engine = get_db_engine()
        with engine.connect() as conn:
            couriers = pd.read_sql(
                text("SELECT DISTINCT courier FROM inbound_logistic_charge_full_view "
                     "WHERE courier IS NOT NULL ORDER BY courier"), conn
            )["courier"].tolist()

            warehouses = pd.read_sql(
                text("SELECT DISTINCT warehouse_name FROM inbound_logistic_charge_full_view "
                     "WHERE warehouse_name IS NOT NULL ORDER BY warehouse_name"), conn
            )["warehouse_name"].tolist()

            categories = pd.read_sql(
                text("SELECT DISTINCT category FROM inbound_logistic_charge_full_view "
                     "WHERE category IS NOT NULL ORDER BY category"), conn
            )["category"].tolist()

            charge_types = pd.read_sql(
                text("SELECT DISTINCT logistic_charge FROM inbound_logistic_charge_full_view "
                     "WHERE logistic_charge IS NOT NULL ORDER BY logistic_charge"), conn
            )["logistic_charge"].tolist()

        return {
            "couriers": couriers,
            "warehouses": warehouses,
            "categories": categories,
            "charge_types": charge_types,
        }
    except Exception as e:
        logger.error(f"Error loading filter options: {e}")
        return {"couriers": [], "warehouses": [], "categories": [], "charge_types": []}


def get_cost_by_id(cost_id: int) -> Optional[Dict]:
    """Fetch single cost entry (for view/edit dialogs)."""
    try:
        engine = get_db_engine()
        query = text("""
        SELECT *
        FROM inbound_logistic_charge_full_view
        WHERE cost_id = :cost_id
        """)
        with engine.connect() as conn:
            row = conn.execute(query, {"cost_id": cost_id}).mappings().fetchone()
        return dict(row) if row else None
    except Exception as e:
        logger.error(f"Error loading cost {cost_id}: {e}")
        return None


# ============================================================================
# WRITE — CREATE / UPDATE / DELETE
# ============================================================================

def create_cost_entry(
    cost_type_id: int,
    arrival_type: str,         # 'INTERNATIONAL' | 'LOCAL'
    arrival_id: int,
    vendor_id: Optional[int],
    amount: float,
    created_by: str,
) -> Tuple[bool, int, str]:
    """
    Insert new record into arrival_delivery_cost_entity.
    Returns (success, new_id, error_message).
    """
    try:
        engine = get_db_engine()
        with engine.begin() as conn:
            # Set the correct FK column based on arrival type
            intl_id  = arrival_id if arrival_type == "INTERNATIONAL" else None
            local_id = arrival_id if arrival_type == "LOCAL"         else None

            query = text("""
            INSERT INTO arrival_delivery_cost_entity (
                type_id,
                intl_arrival_id,
                local_arrival_id,
                vendor_id,
                amount,
                delete_flag,
                created_by,
                created_date,
                modified_date
            ) VALUES (
                :type_id,
                :intl_arrival_id,
                :local_arrival_id,
                :vendor_id,
                :amount,
                b'0',
                :created_by,
                NOW(),
                NOW()
            )
            """)
            result = conn.execute(query, {
                "type_id":          cost_type_id,
                "intl_arrival_id":  intl_id,
                "local_arrival_id": local_id,
                "vendor_id":        vendor_id,
                "amount":           amount,
                "created_by":       created_by,
            })
            new_id = result.lastrowid
        logger.info(f"Created cost entry {new_id}")
        return True, new_id, ""
    except Exception as e:
        error = f"Failed to create cost entry: {e}"
        logger.error(error)
        return False, 0, error


def update_cost_entry(
    cost_id: int,
    cost_type_id: int,
    vendor_id: Optional[int],
    amount: float,
    updated_by: str,
) -> Tuple[bool, str]:
    """Update amount, type, and vendor on an existing cost entry."""
    try:
        engine = get_db_engine()
        with engine.begin() as conn:
            query = text("""
            UPDATE arrival_delivery_cost_entity
            SET type_id       = :type_id,
                vendor_id     = :vendor_id,
                amount        = :amount,
                modified_date = NOW()
            WHERE id          = :cost_id
              AND delete_flag = b'0'
            """)
            result = conn.execute(query, {
                "cost_id":   cost_id,
                "type_id":   cost_type_id,
                "vendor_id": vendor_id,
                "amount":    amount,
            })
            if result.rowcount == 0:
                return False, "Cost entry not found or already deleted"
        logger.info(f"Updated cost entry {cost_id}")
        return True, ""
    except Exception as e:
        error = f"Failed to update cost entry: {e}"
        logger.error(error)
        return False, error


def delete_cost_entry(cost_id: int, deleted_by: str) -> Tuple[bool, str]:
    """Soft-delete a cost entry."""
    try:
        engine = get_db_engine()
        with engine.begin() as conn:
            query = text("""
            UPDATE arrival_delivery_cost_entity
            SET delete_flag   = b'1',
                modified_date = NOW()
            WHERE id          = :cost_id
              AND delete_flag = b'0'
            """)
            result = conn.execute(query, {"cost_id": cost_id})
            if result.rowcount == 0:
                return False, "Cost entry not found or already deleted"
        logger.info(f"Deleted cost entry {cost_id} by {deleted_by}")
        return True, "Cost entry deleted successfully"
    except Exception as e:
        error = f"Failed to delete cost entry: {e}"
        logger.error(error)
        return False, error


# ============================================================================
# ANALYTICS QUERIES
# ============================================================================

@st.cache_data(ttl=300, show_spinner=False)
def get_cost_summary_by_courier() -> pd.DataFrame:
    """Aggregate cost by courier for analytics charts."""
    try:
        engine = get_db_engine()
        query = text("""
        SELECT
            COALESCE(courier, 'Unknown') AS courier,
            category,
            COUNT(*)                     AS entry_count,
            SUM(amount_usd)              AS total_usd,
            AVG(amount_usd)              AS avg_usd
        FROM inbound_logistic_charge_full_view
        WHERE amount_usd IS NOT NULL
        GROUP BY courier, category
        ORDER BY total_usd DESC
        """)
        with engine.connect() as conn:
            return pd.read_sql(query, conn)
    except Exception as e:
        logger.error(f"Error in cost_summary_by_courier: {e}")
        return pd.DataFrame()


@st.cache_data(ttl=300, show_spinner=False)
def get_cost_trend_monthly() -> pd.DataFrame:
    """Monthly cost trend split by category."""
    try:
        engine = get_db_engine()
        query = text("""
        SELECT
            arrival_year,
            arrival_month,
            category,
            CONCAT(arrival_year, '-', LPAD(arrival_month, 2, '0')) AS month_label,
            COUNT(*)             AS entry_count,
            SUM(amount_usd)      AS total_usd
        FROM inbound_logistic_charge_full_view
        WHERE amount_usd IS NOT NULL
          AND arrival_year IS NOT NULL
        GROUP BY arrival_year, arrival_month, category
        ORDER BY arrival_year DESC, arrival_month DESC
        LIMIT 36
        """)
        with engine.connect() as conn:
            return pd.read_sql(query, conn)
    except Exception as e:
        logger.error(f"Error in cost_trend_monthly: {e}")
        return pd.DataFrame()


@st.cache_data(ttl=300, show_spinner=False)
def get_cost_by_charge_type() -> pd.DataFrame:
    """Breakdown by individual charge type."""
    try:
        engine = get_db_engine()
        query = text("""
        SELECT
            logistic_charge,
            category,
            COUNT(*)          AS entry_count,
            SUM(amount_usd)   AS total_usd,
            AVG(cost_per_unit_usd) AS avg_cost_per_unit
        FROM inbound_logistic_charge_full_view
        WHERE amount_usd IS NOT NULL
        GROUP BY logistic_charge, category
        ORDER BY total_usd DESC
        """)
        with engine.connect() as conn:
            return pd.read_sql(query, conn)
    except Exception as e:
        logger.error(f"Error in cost_by_charge_type: {e}")
        return pd.DataFrame()


@st.cache_data(ttl=300, show_spinner=False)
def get_cost_by_warehouse() -> pd.DataFrame:
    """Cost aggregated by destination warehouse."""
    try:
        engine = get_db_engine()
        query = text("""
        SELECT
            COALESCE(warehouse_name, 'Unknown') AS warehouse,
            warehouse_country,
            category,
            COUNT(*)          AS entry_count,
            SUM(amount_usd)   AS total_usd
        FROM inbound_logistic_charge_full_view
        WHERE amount_usd IS NOT NULL
        GROUP BY warehouse_name, warehouse_country, category
        ORDER BY total_usd DESC
        """)
        with engine.connect() as conn:
            return pd.read_sql(query, conn)
    except Exception as e:
        logger.error(f"Error in cost_by_warehouse: {e}")
        return pd.DataFrame()