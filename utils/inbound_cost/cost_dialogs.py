# utils/inbound_cost/cost_dialogs.py
# All @st.dialog functions for Inbound Logistic Cost module.
# Pattern mirrors utils/vendor_invoice/invoice_dialogs.py

import streamlit as st
import pandas as pd
import logging
from typing import Optional, Dict

from .cost_data import (
    get_cost_by_id,
    get_cost_type_options,
    get_arrival_options,
    get_vendor_options,
    create_cost_entry,
    update_cost_entry,
    delete_cost_entry,
)
from ..s3_utils import S3Manager

logger = logging.getLogger(__name__)

# ─── Shared helpers ──────────────────────────────────────────────────────────

def _auth_user():
    from utils.auth import AuthManager
    return AuthManager().get_current_user()

def _invalidate():
    st.session_state["_invalidate_cost_cache"] = True

def _fmt_amount(amount, currency):
    if amount is None:
        return "N/A"
    return f"{amount:,.2f} {currency or ''}"


# ============================================================================
# VIEW DIALOG
# ============================================================================

@st.dialog("🔍 Cost Entry Detail", width="large")
def view_cost_dialog(cost_id: int):
    entry = get_cost_by_id(cost_id)
    if not entry:
        st.error("Cost entry not found.")
        return

    # Header badge
    cat_color = "🟦" if entry.get("category") == "INTERNATIONAL" else "🟩"
    st.markdown(
        f"### {cat_color} {entry.get('logistic_charge', '—')} "
        f"&nbsp;|&nbsp; CAN: `{entry.get('can_number', '—')}`"
    )
    st.markdown("---")

    # ── Costs & currency ─────────────────────────────────────────────────────
    c1, c2, c3 = st.columns(3)
    c1.metric("Amount", _fmt_amount(entry.get("amount"), entry.get("currency_code")))
    c2.metric("Amount (USD)", f"${entry.get('amount_usd', 0):,.2f}" if entry.get("amount_usd") else "N/A")
    c3.metric("Cost / Unit (USD)", f"${entry.get('cost_per_unit_usd', 0):,.6f}" if entry.get("cost_per_unit_usd") else "N/A")

    st.markdown("---")

    # ── Arrival info ──────────────────────────────────────────────────────────
    st.markdown("#### 🚢 Arrival / Shipment")
    r1c1, r1c2, r1c3, r1c4 = st.columns(4)
    r1c1.markdown(f"**CAN #**\n\n{entry.get('can_number','—')}")
    r1c2.markdown(f"**Arrival Date**\n\n{str(entry.get('arrival_date','—'))[:10]}")
    r1c3.markdown(f"**Ship Method**\n\n{entry.get('ship_method','—')}")
    r1c4.markdown(f"**Status**\n\n{entry.get('arrival_status','—')}")

    r2c1, r2c2, r2c3, r2c4 = st.columns(4)
    r2c1.markdown(f"**Sender**\n\n{entry.get('sender','—')}")
    r2c2.markdown(f"**Receiver**\n\n{entry.get('receiver','—')}")
    r2c3.markdown(f"**Shipment Type**\n\n{entry.get('shipment_type','—')}")
    r2c4.markdown(f"**Courier**\n\n{entry.get('courier','—')}")

    st.markdown("---")

    # ── Warehouse & products ──────────────────────────────────────────────────
    wc1, wc2 = st.columns(2)
    with wc1:
        st.markdown("#### 🏭 Warehouse")
        st.markdown(
            f"**{entry.get('warehouse_name','—')}**  \n"
            f"{entry.get('warehouse_state','')} {entry.get('warehouse_country','')}"
        )
    with wc2:
        st.markdown("#### 📦 Products in CAN")
        codes = (entry.get("product_codes") or "—")
        names = (entry.get("product_names") or "—")
        st.caption(f"Codes: {codes}")
        st.caption(f"Names: {names}")

    # ── Arrival context ───────────────────────────────────────────────────────
    st.markdown("---")
    ac1, ac2 = st.columns(2)
    ac1.metric("Total Arrival Qty", f"{entry.get('total_arrival_qty', 0):,.0f}")
    ac2.metric("Lines in CAN", entry.get("arrival_line_count", "—"))

    # ── Documents ────────────────────────────────────────────────────────────
    doc_count = entry.get("doc_count", 0)
    if doc_count and int(doc_count) > 0:
        st.markdown("---")
        st.markdown(f"#### 📎 Attachments ({doc_count})")
        paths = (entry.get("doc_paths") or "").split("|")
        names = (entry.get("doc_names") or "").split("|")
        try:
            s3 = S3Manager()
            for p, n in zip(paths, names):
                p, n = p.strip(), n.strip()
                if not p:
                    continue
                url = s3.get_presigned_url(p)
                if url:
                    st.markdown(f"📄 [{n}]({url})")
                else:
                    st.caption(f"📄 {n} *(preview unavailable)*")
        except Exception as e:
            st.caption(f"Could not load document links: {e}")

    # ── Audit ─────────────────────────────────────────────────────────────────
    st.markdown("---")
    au1, au2, au3 = st.columns(3)
    au1.caption(f"Created by: {entry.get('cost_created_by','—')}")
    au2.caption(f"Created: {str(entry.get('cost_created_date','—'))[:19]}")
    au3.caption(f"Modified: {str(entry.get('cost_modified_date','—'))[:19]}")

    st.markdown("---")
    if st.button("Close", use_container_width=True):
        st.rerun()


# ============================================================================
# CREATE DIALOG
# ============================================================================

@st.dialog("➕ Add Inbound Cost Entry", width="large")
def create_cost_dialog():
    user = _auth_user()

    st.markdown("### New Logistics Cost Entry")
    st.caption("Add an international or local charge to a Cargo Arrival Note (CAN).")
    st.markdown("---")

    # ── Cost type ─────────────────────────────────────────────────────────────
    types_df = get_cost_type_options()
    if types_df.empty:
        st.error("Cannot load cost types from database.")
        return

    intl_types = types_df[types_df["type"] == "INTERNATIONAL"]
    local_types = types_df[types_df["type"] == "LOCAL"]

    cat_col, type_col = st.columns(2)
    with cat_col:
        category = st.selectbox(
            "Category *",
            ["INTERNATIONAL", "LOCAL"],
            key="cc_category",
            help="INTERNATIONAL = freight/ocean/air; LOCAL = customs, trucking, etc.",
        )
    with type_col:
        subset = intl_types if category == "INTERNATIONAL" else local_types
        if subset.empty:
            st.warning(f"No {category} cost types defined.")
            return
        type_options = {row["name"]: row["id"] for _, row in subset.iterrows()}
        selected_type_name = st.selectbox("Charge Type *", list(type_options.keys()), key="cc_type")
        selected_type_id = type_options[selected_type_name]

    # ── Arrival (CAN) selection ───────────────────────────────────────────────
    st.markdown("#### Cargo Arrival Note (CAN)")
    arrivals_df = get_arrival_options()
    if arrivals_df.empty:
        st.error("Cannot load arrivals from database.")
        return

    # Search box to narrow CAN list
    can_search = st.text_input("Search CAN", placeholder="Type CAN # or sender…", key="cc_can_search")
    if can_search:
        mask = (
            arrivals_df["arrival_note_number"].str.contains(can_search, case=False, na=False)
            | arrivals_df["sender"].str.contains(can_search, case=False, na=False)
        )
        arrivals_df = arrivals_df[mask]

    if arrivals_df.empty:
        st.info("No CANs match the search.")
        return

    arrivals_df["label"] = arrivals_df.apply(
        lambda r: (
            f"{r['arrival_note_number']}  |  "
            f"{str(r['arrival_date'])[:10]}  |  "
            f"{r.get('sender','?')} → {r.get('receiver','?')}  |  "
            f"{r.get('warehouse_name','?')}"
        ),
        axis=1,
    )
    can_label_map = dict(zip(arrivals_df["label"], arrivals_df["id"]))
    selected_can_label = st.selectbox("Select CAN *", list(can_label_map.keys()), key="cc_can")
    selected_arrival_id = can_label_map[selected_can_label]

    # ── Amount & vendor ───────────────────────────────────────────────────────
    st.markdown("---")
    amt_col, vendor_col = st.columns(2)
    with amt_col:
        amount = st.number_input(
            "Amount *",
            min_value=0.01, step=0.01, format="%.2f",
            key="cc_amount",
            help="Enter amount in the CAN's charge currency (set on the arrival record)",
        )
    with vendor_col:
        vendors_df = get_vendor_options()
        vendor_options = {"— Not specified —": None}
        if not vendors_df.empty:
            vendor_options.update({
                f"{r['name']} ({r['company_code']})": r["id"]
                for _, r in vendors_df.iterrows()
            })
        selected_vendor_label = st.selectbox(
            "Logistics Vendor / Courier", list(vendor_options.keys()), key="cc_vendor"
        )
        selected_vendor_id = vendor_options[selected_vendor_label]

    st.markdown("---")

    # ── Actions ───────────────────────────────────────────────────────────────
    col_save, col_cancel = st.columns(2)
    with col_cancel:
        if st.button("Cancel", use_container_width=True, key="cc_cancel"):
            st.rerun()
    with col_save:
        if st.button("💾 Save", type="primary", use_container_width=True, key="cc_save"):
            if amount <= 0:
                st.error("Amount must be greater than 0.")
                return

            keycloak_id = getattr(user, "keycloak_id", None) or getattr(user, "id", "unknown")
            ok, new_id, err = create_cost_entry(
                cost_type_id=selected_type_id,
                arrival_type=category,
                arrival_id=selected_arrival_id,
                vendor_id=selected_vendor_id,
                amount=amount,
                created_by=keycloak_id,
            )
            if ok:
                st.success(f"✅ Cost entry #{new_id} created successfully!")
                _invalidate()
                # Clear cache for arrivals view
                get_cost_type_options.clear()
                st.session_state["_last_created_cost"] = {
                    "id": new_id,
                    "type": selected_type_name,
                    "amount": amount,
                    "category": category,
                }
                st.rerun()
            else:
                st.error(f"❌ {err}")


# ============================================================================
# EDIT DIALOG
# ============================================================================

@st.dialog("✏️ Edit Cost Entry", width="large")
def edit_cost_dialog(cost_id: int):
    user = _auth_user()
    entry = get_cost_by_id(cost_id)
    if not entry:
        st.error("Cost entry not found.")
        return

    st.markdown(
        f"### Editing Cost `#{cost_id}` — "
        f"CAN: **{entry.get('can_number','—')}**"
    )
    st.caption(
        f"Arrival: {str(entry.get('arrival_date',''))[:10]}  |  "
        f"Shipment: {entry.get('shipment_type','—')}"
    )
    st.markdown("---")

    # ── Cost type (only within same category) ─────────────────────────────────
    types_df = get_cost_type_options()
    current_cat = entry.get("category", "INTERNATIONAL")
    subset = types_df[types_df["type"] == current_cat]
    type_options = {row["name"]: row["id"] for _, row in subset.iterrows()}

    current_type_name = entry.get("logistic_charge", "")
    default_idx = list(type_options.keys()).index(current_type_name) if current_type_name in type_options else 0

    type_col, _ = st.columns(2)
    with type_col:
        st.caption(f"Category: **{current_cat}** (cannot change on existing entry)")
        selected_type_name = st.selectbox(
            "Charge Type *",
            list(type_options.keys()),
            index=default_idx,
            key="ec_type",
        )
        selected_type_id = type_options[selected_type_name]

    # ── Amount ────────────────────────────────────────────────────────────────
    amt_col, curr_col = st.columns(2)
    with amt_col:
        new_amount = st.number_input(
            "Amount *",
            value=float(entry.get("amount", 0.0)),
            min_value=0.01, step=0.01, format="%.2f",
            key="ec_amount",
        )
    with curr_col:
        st.text_input(
            "Currency",
            value=entry.get("currency_code", "—"),
            disabled=True,
            key="ec_currency",
            help="Currency is determined by the arrival record and cannot be changed here.",
        )
        if entry.get("amount_usd"):
            ratio = (new_amount / float(entry.get("amount", 1))) if entry.get("amount") else 1
            st.caption(f"≈ USD {float(entry.get('amount_usd', 0)) * ratio:,.2f}")

    # ── Vendor ────────────────────────────────────────────────────────────────
    vendors_df = get_vendor_options()
    vendor_options = {"— Not specified —": None}
    if not vendors_df.empty:
        vendor_options.update({
            f"{r['name']} ({r['company_code']})": r["id"]
            for _, r in vendors_df.iterrows()
        })

    current_vendor_id = entry.get("logistics_vendor_id")
    default_vendor_label = "— Not specified —"
    if current_vendor_id:
        for label, vid in vendor_options.items():
            if vid == current_vendor_id:
                default_vendor_label = label
                break

    vendor_idx = list(vendor_options.keys()).index(default_vendor_label) if default_vendor_label in vendor_options else 0
    selected_vendor_label = st.selectbox(
        "Logistics Vendor / Courier",
        list(vendor_options.keys()),
        index=vendor_idx,
        key="ec_vendor",
    )
    selected_vendor_id = vendor_options[selected_vendor_label]

    st.markdown("---")

    # ── Change summary ────────────────────────────────────────────────────────
    changes = []
    if selected_type_id != entry.get("cost_type_id"):
        changes.append(f"Charge type: **{entry.get('logistic_charge')}** → **{selected_type_name}**")
    if abs(new_amount - float(entry.get("amount", 0))) > 0.001:
        changes.append(f"Amount: **{entry.get('amount'):,.2f}** → **{new_amount:,.2f}**")
    if selected_vendor_id != current_vendor_id:
        changes.append(f"Vendor: **{entry.get('courier','—')}** → **{selected_vendor_label}**")

    if changes:
        st.info("**Changes to save:**\n\n" + "\n\n".join(f"• {c}" for c in changes))
    else:
        st.caption("No changes detected.")

    col_save, col_cancel = st.columns(2)
    with col_cancel:
        if st.button("Cancel", use_container_width=True, key="ec_cancel"):
            st.rerun()
    with col_save:
        disabled = len(changes) == 0
        if st.button(
            "💾 Save Changes", type="primary",
            use_container_width=True, key="ec_save",
            disabled=disabled,
        ):
            keycloak_id = getattr(user, "keycloak_id", None) or getattr(user, "id", "unknown")
            ok, err = update_cost_entry(
                cost_id=cost_id,
                cost_type_id=selected_type_id,
                vendor_id=selected_vendor_id,
                amount=new_amount,
                updated_by=keycloak_id,
            )
            if ok:
                st.success(f"✅ Cost entry #{cost_id} updated!")
                _invalidate()
                st.rerun()
            else:
                st.error(f"❌ {err}")


# ============================================================================
# DELETE DIALOG
# ============================================================================

@st.dialog("🗑️ Delete Cost Entry", width="small")
def delete_cost_dialog(cost_id: int):
    user = _auth_user()
    entry = get_cost_by_id(cost_id)
    if not entry:
        st.error("Cost entry not found.")
        return

    st.warning("⚠️ **This action cannot be undone.**")
    st.markdown(
        f"You are about to **delete** cost entry **#{cost_id}**:\n\n"
        f"- **Charge type:** {entry.get('logistic_charge','—')}\n"
        f"- **CAN:** {entry.get('can_number','—')}\n"
        f"- **Amount:** {_fmt_amount(entry.get('amount'), entry.get('currency_code'))}\n"
        f"- **Amount (USD):** ${entry.get('amount_usd', 0):,.2f}"
    )
    st.markdown("---")

    confirm = st.checkbox("I confirm I want to delete this cost entry", key="del_confirm")
    col_del, col_cancel = st.columns(2)
    with col_cancel:
        if st.button("Cancel", use_container_width=True, key="del_cancel"):
            st.rerun()
    with col_del:
        if st.button(
            "🗑️ Delete", type="primary", use_container_width=True,
            key="del_confirm_btn", disabled=not confirm,
        ):
            keycloak_id = getattr(user, "keycloak_id", None) or getattr(user, "id", "unknown")
            ok, msg = delete_cost_entry(cost_id, deleted_by=keycloak_id)
            if ok:
                st.success(f"✅ {msg}")
                _invalidate()
                st.session_state["_last_deleted_cost"] = cost_id
                st.rerun()
            else:
                st.error(f"❌ {msg}")
