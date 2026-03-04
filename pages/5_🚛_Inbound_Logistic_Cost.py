# pages/5_🚛_Inbound_Logistic_Cost.py
# Inbound Logistics Cost — List, CRUD, Analytics.
# Structure mirrors pages/7___Vendor_Invoice.py exactly.

import streamlit as st
import pandas as pd
import io
import logging
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from typing import Dict, Optional

from utils.auth import AuthManager
from utils.inbound_cost import (
    get_recent_costs,
    get_filter_options,
    CostService,
    get_cost_trend_monthly,
    get_cost_by_courier,
    get_cost_by_charge_type,
    get_cost_by_warehouse,
)
from utils.inbound_cost.cost_dialogs import (
    create_cost_dialog,
    view_cost_dialog,
    edit_cost_dialog,
    delete_cost_dialog,
    attachments_dialog,
)

logger = logging.getLogger(__name__)

st.set_page_config(
    page_title="Inbound Logistic Cost",
    page_icon="🚛",
    layout="wide",
    initial_sidebar_state="expanded",
)


# ============================================================================
# STATE
# ============================================================================

@dataclass
class CostPageState:
    _table_key: int = 0
    last_created_cost: Optional[Dict] = None
    last_deleted_cost: Optional[int] = None


def _init_state():
    if "cost_state" not in st.session_state:
        st.session_state.cost_state = CostPageState()


# ============================================================================
# MAIN
# ============================================================================

def main():
    _init_state()
    AuthManager().require_auth()

    # Recover signals written by dialogs
    state = st.session_state.cost_state
    created = st.session_state.pop("_last_created_cost", None)
    if created:
        state.last_created_cost = created
    deleted = st.session_state.pop("_last_deleted_cost", None)
    if deleted:
        state.last_deleted_cost = deleted

    _header_fragment()

    tab_list, tab_analytics = st.tabs(["📋 Cost List", "📈 Analytics"])
    with tab_list:
        _list_fragment()
    with tab_analytics:
        _analytics_fragment()


# ── Header ───────────────────────────────────────────────────────────────────

@st.fragment
def _header_fragment():
    state = st.session_state.cost_state

    title_col, btn_col = st.columns([5, 1])
    with title_col:
        st.title("🚛 Inbound Logistic Cost")
        st.caption(
            "Manage international & local charges for every "
            "Cargo Arrival Note (CAN)."
        )
    with btn_col:
        st.markdown("<br>", unsafe_allow_html=True)
        if st.button("➕ Add Cost Entry", type="primary", width="stretch"):
            create_cost_dialog()

    if state.last_created_cost:
        c = state.last_created_cost
        st.success(
            f"✅ **Created:** #{c['id']} | "
            f"{c['category']} — {c['type']} | "
            f"Amount: {c['amount']:,.2f}"
        )
        state.last_created_cost = None

    if state.last_deleted_cost:
        st.info(f"🗑️ Cost entry #{state.last_deleted_cost} deleted.")
        state.last_deleted_cost = None


# ============================================================================
# LIST FRAGMENT
# ============================================================================

@st.fragment
def _list_fragment():
    state = st.session_state.cost_state

    # ── Pre-load data so CAN# options can be derived from it ─────────────────
    _limit = st.session_state.get("cf_limit", 500)
    raw_df = get_recent_costs(limit=int(_limit))
    opts   = get_filter_options()

    # ── Filters (no st.form — widgets react immediately within fragment) ──────
    with st.expander("🔍 Search & Filters", expanded=True):

        # Row 1: Date range + Max Records
        rc1, rc2 = st.columns([3, 1])
        with rc1:
            date_filter = st.selectbox(
                "Date Range",
                ["Last 30 days", "Last 90 days", "Last 6 months",
                 "This Year", "All Time", "Custom…"],
                key="cf_date",
            )
        with rc2:
            limit = st.number_input(
                "Max Records",
                min_value=50, max_value=2000, value=500, step=50, key="cf_limit"
            )

        # Custom date pickers — shown immediately when "Custom…" is selected
        custom_from = None
        custom_to   = None
        if date_filter == "Custom…":
            cd1, cd2, _ = st.columns([2, 2, 2])
            with cd1:
                custom_from = st.date_input(
                    "From date",
                    key="cf_custom_from",
                    value=(datetime.now() - timedelta(days=30)).date(),
                )
            with cd2:
                custom_to = st.date_input(
                    "To date",
                    key="cf_custom_to",
                    value=datetime.now().date(),
                )

        # Row 2: CAN # multiselect + Charge Type
        rm1, rm2 = st.columns(2)
        with rm1:
            can_options = (
                sorted(raw_df["can_number"].dropna().unique().tolist())
                if not raw_df.empty else []
            )
            can_filter = st.multiselect(
                "CAN #",
                options=can_options,
                default=[],
                key="cf_can",
                placeholder="All CAN numbers",
            )
        with rm2:
            charge_filter = st.multiselect(
                "Charge Type",
                options=opts.get("charge_types", []),
                default=[],
                key="cf_charge",
                placeholder="All charge types",
            )

        # Row 3: Category + Courier + Warehouse
        fm1, fm2, fm3 = st.columns(3)
        with fm1:
            category_filter = st.multiselect(
                "Category",
                options=["INTERNATIONAL", "LOCAL"],
                default=[],
                key="cf_category",
                placeholder="All categories",
            )
        with fm2:
            courier_filter = st.multiselect(
                "Courier",
                options=opts.get("couriers", []),
                default=[],
                key="cf_courier",
                placeholder="All couriers",
            )
        with fm3:
            warehouse_filter = st.multiselect(
                "Warehouse",
                options=opts.get("warehouses", []),
                default=[],
                key="cf_warehouse",
                placeholder="All warehouses",
            )

        # Reset button
        _, reset_col = st.columns([5, 1])
        with reset_col:
            if st.button("🔄 Reset", width="stretch", key="cf_reset"):
                for k in ["cf_date", "cf_can", "cf_charge", "cf_category",
                          "cf_courier", "cf_warehouse",
                          "cf_custom_from", "cf_custom_to", "cf_limit"]:
                    st.session_state.pop(k, None)
                st.rerun(scope="fragment")

    # Reload if limit changed
    if int(limit) != int(_limit):
        raw_df = get_recent_costs(limit=int(limit))

    # ── Apply filters ─────────────────────────────────────────────────────────
    df = _apply_filters(
        raw_df, date_filter, can_filter,
        charge_filter, category_filter, courier_filter, warehouse_filter,
        custom_from=custom_from, custom_to=custom_to,
    )

    # ── Summary metrics ───────────────────────────────────────────────────────
    _show_summary_metrics(df)

    if df.empty:
        st.info("No cost entries match the current filters.")
        return

    st.markdown("### 📋 Cost Entries")
    disp = CostService.prepare_display_df(df)

    # ── Dataframe with row selection ──────────────────────────────────────────
    event = st.dataframe(
        disp.drop(columns=["cost_id"]),
        width="stretch",
        hide_index=True,
        selection_mode="single-row",
        on_select="rerun",
        key=f"cost_table_{state._table_key}",
        column_config={
            "CAN #":       st.column_config.TextColumn(width="medium"),
            "Category":    st.column_config.TextColumn(width="small"),
            "Charge Type": st.column_config.TextColumn(width="large"),
            "Courier":     st.column_config.TextColumn(width="large"),
            "Amount":      st.column_config.TextColumn(width="medium"),
            "USD":         st.column_config.TextColumn(width="medium"),
            "$/Unit":      st.column_config.TextColumn(width="medium"),
            "Date":        st.column_config.TextColumn(width="small"),
            "Warehouse":   st.column_config.TextColumn(width="medium"),
            "Ship Method": st.column_config.TextColumn(width="small"),
            "Docs":        st.column_config.NumberColumn(width="small"),
        },
    )

    # ── Action bar ────────────────────────────────────────────────────────────
    sel_rows = event.selection.rows
    if sel_rows:
        idx     = sel_rows[0]
        sel_id  = int(disp.iloc[idx]["cost_id"])
        sel_can = disp.iloc[idx].get("CAN #", "—")

        info_col, clear_col = st.columns([8, 1])
        with info_col:
            st.markdown(f"**Selected:** CAN `{sel_can}` — entry `#{sel_id}`")
        with clear_col:
            if st.button("✖ Clear", width="stretch", key="cost_clear"):
                state._table_key += 1
                st.rerun(scope="fragment")

        ac1, ac2, ac3, ac4, _ = st.columns([1, 1, 1, 1, 3])
        with ac1:
            if st.button("👁️ View",       width="stretch", key="cost_view"):
                view_cost_dialog(sel_id)
        with ac2:
            if st.button("✏️ Edit",        width="stretch", key="cost_edit"):
                edit_cost_dialog(sel_id)
        with ac3:
            if st.button("📎 Attachments", width="stretch", key="cost_att"):
                attachments_dialog(sel_id)
        with ac4:
            if st.button("🗑️ Delete",      width="stretch", key="cost_delete"):
                delete_cost_dialog(sel_id)

    _show_export(disp)


# ============================================================================
# ANALYTICS FRAGMENT
# ============================================================================

@st.fragment
def _analytics_fragment():
    period_col, _ = st.columns([1, 3])
    with period_col:
        period = st.selectbox(
            "Period",
            ["Last 3 months", "Last 6 months", "Last 12 months", "All Time"],
            key="cost_period",
        )

    months_map = {"Last 3 months": 3, "Last 6 months": 6,
                  "Last 12 months": 12, "All Time": 9999}
    months_back = months_map[period]

    # Data
    trend_df   = get_cost_trend_monthly()
    courier_df = get_cost_by_courier()
    charge_df  = get_cost_by_charge_type()
    wh_df      = get_cost_by_warehouse()

    # Filter trend by period
    if not trend_df.empty and months_back < 9999:
        from datetime import date as _date
        today = _date.today()
        y, m = today.year, today.month - months_back
        while m <= 0:
            y -= 1; m += 12
        trend_df = trend_df[
            (trend_df["arrival_year"] > y)
            | ((trend_df["arrival_year"] == y) & (trend_df["arrival_month"] >= m))
        ]

    # KPIs from full list
    raw_df = get_recent_costs(limit=2000)
    if not raw_df.empty:
        m_df = raw_df.copy()
        if months_back < 9999:
            m_df["arrival_date"] = pd.to_datetime(m_df["arrival_date"])
            cutoff = pd.Timestamp.now() - timedelta(days=months_back * 30)
            m_df = m_df[m_df["arrival_date"] >= cutoff]
        kpis = CostService.compute_kpis(m_df)
    else:
        kpis = CostService.compute_kpis(pd.DataFrame())

    st.markdown("### 📊 Key Metrics")
    k1, k2, k3, k4, k5 = st.columns(5)
    k1.metric("Total Entries",    f"{kpis['total_entries']:,}")
    k2.metric("Unique CANs",      f"{kpis['unique_cans']:,}")
    k3.metric("Total (USD)",      f"${kpis['total_usd']:,.0f}")
    k4.metric("International",    f"${kpis['intl_usd']:,.0f}")
    k5.metric("Local",            f"${kpis['local_usd']:,.0f}")

    st.markdown("---")

    # ── Row 1: Trend + Category split ─────────────────────────────────────────
    tr_col, cat_col = st.columns(2)

    with tr_col:
        st.markdown("#### 📈 Monthly Cost Trend (USD)")
        if not trend_df.empty:
            pivot = (
                trend_df.groupby(["month_label", "category"])["total_usd"]
                .sum().unstack(fill_value=0).sort_index()
            )
            st.bar_chart(pivot, width="stretch")
        else:
            st.caption("No trend data available.")

    with cat_col:
        st.markdown("#### 🔵 INTL vs 🟢 LOCAL Breakdown")
        if not charge_df.empty:
            cat_tbl = (
                charge_df.groupby(["logistic_charge", "category"])["total_usd"]
                .sum().reset_index()
                .sort_values("total_usd", ascending=False)
                .head(15)
            )
            cat_tbl["total_usd"] = cat_tbl["total_usd"].apply(lambda x: f"${x:,.0f}")
            cat_tbl.columns = ["Charge Type", "Category", "Total USD"]
            st.dataframe(cat_tbl, width="stretch", hide_index=True)

    st.markdown("---")

    # ── Row 2: Courier + Warehouse ────────────────────────────────────────────
    cour_col, wh_col = st.columns(2)

    with cour_col:
        st.markdown("#### 🚚 Top Couriers (USD)")
        if not courier_df.empty:
            top = (
                courier_df.groupby("courier")["total_usd"]
                .sum().sort_values(ascending=False).head(12).reset_index()
            )
            top.columns = ["Courier", "Total USD"]
            st.bar_chart(top.set_index("Courier"), width="stretch")

            tbl = (
                courier_df.groupby(["courier", "category"])
                .agg(total_usd=("total_usd", "sum"), entries=("entry_count", "sum"))
                .reset_index().sort_values("total_usd", ascending=False).head(20)
            )
            tbl["total_usd"] = tbl["total_usd"].apply(lambda x: f"${x:,.0f}")
            tbl.columns = ["Courier", "Category", "Total USD", "Entries"]
            st.dataframe(tbl, width="stretch", hide_index=True)
        else:
            st.caption("No courier data.")

    with wh_col:
        st.markdown("#### 🏭 Cost by Warehouse")
        if not wh_df.empty:
            wh_top = (
                wh_df.groupby("warehouse")["total_usd"]
                .sum().sort_values(ascending=False).reset_index()
            )
            wh_top.columns = ["Warehouse", "Total USD"]
            st.bar_chart(wh_top.set_index("Warehouse"), width="stretch")

            wh_tbl = wh_df.sort_values("total_usd", ascending=False).head(20).copy()
            wh_tbl["total_usd"] = wh_tbl["total_usd"].apply(lambda x: f"${x:,.0f}")
            wh_tbl.columns = [c.replace("_", " ").title() for c in wh_tbl.columns]
            st.dataframe(wh_tbl, width="stretch", hide_index=True)
        else:
            st.caption("No warehouse data.")

    st.markdown("---")

    # ── Row 3: Charge type table ───────────────────────────────────────────────
    st.markdown("#### 📋 Charge Type Detail")
    if not charge_df.empty:
        tbl = charge_df.copy().sort_values("total_usd", ascending=False)
        tbl["total_usd"]        = tbl["total_usd"].apply(lambda x: f"${x:,.0f}")
        tbl["avg_cost_per_unit"] = tbl["avg_cost_per_unit"].apply(
            lambda x: f"${x:,.6f}" if pd.notna(x) else "—"
        )
        tbl.columns = ["Charge Type", "Category", "Entries", "Total USD", "Avg $/Unit"]
        st.dataframe(tbl, width="stretch", hide_index=True)


# ============================================================================
# HELPERS
# ============================================================================

def _apply_filters(
    df: pd.DataFrame,
    date_filter:      str,
    can_filter:       list,      # multiselect → list (empty = all)
    charge_filter:    list,
    category_filter:  list,
    courier_filter:   list,
    warehouse_filter: list,
    custom_from=None,
    custom_to=None,
) -> pd.DataFrame:
    if df.empty:
        return df

    if "arrival_date" in df.columns:
        df = df.copy()
        df["arrival_date"] = pd.to_datetime(df["arrival_date"])
        today = pd.Timestamp.now()

        if date_filter == "Custom…":
            if custom_from:
                df = df[df["arrival_date"] >= pd.Timestamp(custom_from)]
            if custom_to:
                df = df[df["arrival_date"] <= pd.Timestamp(custom_to) + timedelta(days=1) - timedelta(seconds=1)]
        elif date_filter != "All Time":
            thresholds = {
                "Last 30 days": 30, "Last 90 days": 90, "Last 6 months": 180,
            }
            if date_filter == "This Year":
                df = df[df["arrival_date"].dt.year == today.year]
            elif date_filter in thresholds:
                df = df[df["arrival_date"] >= today - timedelta(days=thresholds[date_filter])]

    if can_filter:
        df = df[df["can_number"].isin(can_filter)]
    if charge_filter:
        df = df[df["logistic_charge"].isin(charge_filter)]
    if category_filter:
        df = df[df["category"].isin(category_filter)]
    if courier_filter:
        df = df[df["courier"].isin(courier_filter)]
    if warehouse_filter:
        df = df[df["warehouse_name"].isin(warehouse_filter)]

    return df


def _show_summary_metrics(df: pd.DataFrame):
    st.markdown("### 📈 Summary")
    kpis = CostService.compute_kpis(df)
    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Total Entries",  f"{kpis['total_entries']:,}")
    c2.metric("Unique CANs",    f"{kpis['unique_cans']:,}")
    c3.metric("Total (USD)",    f"${kpis['total_usd']:,.0f}")
    c4.metric("International",  f"${kpis['intl_usd']:,.0f}")
    c5.metric("Local",          f"${kpis['local_usd']:,.0f}")


def _show_export(df: pd.DataFrame):
    st.markdown("---")
    st.markdown("### 📥 Export")
    ec1, ec2, _ = st.columns([1, 1, 4])
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")

    with ec1:
        buf = io.BytesIO()
        with pd.ExcelWriter(buf, engine="openpyxl") as w:
            df.to_excel(w, sheet_name="Inbound Costs", index=False)
        st.download_button(
            "📊 Excel", data=buf.getvalue(),
            file_name=f"inbound_costs_{ts}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            width="stretch",
        )
    with ec2:
        st.download_button(
            "📄 CSV", data=df.to_csv(index=False),
            file_name=f"inbound_costs_{ts}.csv",
            mime="text/csv", width="stretch",
        )


# ============================================================================
# ENTRY POINT
# ============================================================================

if __name__ == "__main__":
    main()