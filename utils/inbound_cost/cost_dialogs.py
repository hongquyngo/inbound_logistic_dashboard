# utils/inbound_cost/cost_dialogs.py
# All @st.dialog functions for Inbound Logistic Cost module.
# Pattern mirrors utils/vendor_invoice/invoice_dialogs.py
#
# IMPORT RULE: Only intra-package imports at module level.
# S3Manager (and anything that pulls config) is imported LAZILY inside functions.

import streamlit as st
import pandas as pd
import logging
from typing import Dict, List, Optional

# ── Module-level constants (must be defined before use in any function) ───────
ALLOWED_EXTENSIONS_DISPLAY = ["pdf", "png", "jpg", "jpeg"]

from .cost_data import (
    get_cost_by_id,
    get_cost_type_options,
    get_arrival_options,
    get_vendor_options,
    create_cost_entry,
    update_cost_entry,
    delete_cost_entry,
    get_cost_attachments,
    save_cost_media_records,
    delete_cost_attachment,
)
from .cost_attachments import (
    validate_uploaded_files,
    prepare_files_for_upload,
    upload_files_to_s3,
    cleanup_failed_uploads,
    get_presigned_url,
    get_file_icon,
    format_file_size,
    summarize_files,
)
from .cost_service import CostService
from .cost_calculator import recalculate_landed_cost

logger = logging.getLogger(__name__)


# ============================================================================
# SHARED HELPERS
# ============================================================================

def _get_user():
    """Get current authenticated user from session."""
    try:
        from utils.auth import AuthManager
        return AuthManager().get_current_user()
    except Exception:
        return None


def _keycloak_id(user) -> str:
    if user is None:
        return "unknown"
    return (
        getattr(user, "keycloak_id", None)
        or getattr(user, "id", None)
        or "unknown"
    )


def _invalidate_cache():
    """
    Clear all cost-related @st.cache_data caches immediately.
    Direct clearing avoids the previous flag mechanism which required
    an extra full-page rerun to take effect.
    """
    from .cost_data import (          # noqa: PLC0415
        get_recent_costs, get_filter_options,
        get_cost_trend_monthly, get_cost_by_courier,
        get_cost_by_charge_type, get_cost_by_warehouse,
        get_cost_type_options, get_arrival_options,
    )
    for fn in (
        get_recent_costs, get_filter_options,
        get_cost_trend_monthly, get_cost_by_courier,
        get_cost_by_charge_type, get_cost_by_warehouse,
        get_cost_type_options, get_arrival_options,
    ):
        fn.clear()
    # Also clear dialog-level caches
    _cached_cost_types.clear()
    _cached_arrivals.clear()
    _cached_vendors.clear()


def _run_recalculate(arrival_id, context: str = "") -> None:
    """
    Call recalculate_landed_cost and surface result as a Streamlit notification.
    Swallows exceptions so that UI flow is never blocked by recalculation errors.
    """
    if not arrival_id:
        logger.warning(f"_run_recalculate: no arrival_id for context '{context}'")
        return
    try:
        ok, msg, stats = recalculate_landed_cost(int(arrival_id))
        if ok:
            st.toast(
                f"🔄 Landed cost recalculated — "
                f"{stats['details_updated']} line(s) updated "
                f"[{stats['allocation_method']}]",
                icon="✅",
            )
            logger.info(f"[{context}] {msg}")
        else:
            st.warning(f"⚠️ Landed cost recalculation issue: {msg}")
            logger.error(f"[{context}] {msg}")
    except Exception as exc:
        logger.error(f"[{context}] Unexpected recalculation error: {exc}")
        st.warning("⚠️ Could not recalculate landed cost — please check logs.")


def _fmt(amount, currency="") -> str:
    if amount is None or (isinstance(amount, float) and pd.isna(amount)):
        return "—"
    return f"{float(amount):,.2f} {currency}".strip()


# ============================================================================
# CACHED DB CALLS (avoid hitting DB on every dialog rerun)
# ============================================================================

@st.cache_data(ttl=120, show_spinner=False)
def _cached_cost_types() -> pd.DataFrame:
    return get_cost_type_options()


@st.cache_data(ttl=120, show_spinner=False)
def _cached_arrivals() -> pd.DataFrame:
    return get_arrival_options(limit=500)


@st.cache_data(ttl=300, show_spinner=False)
def _cached_vendors() -> pd.DataFrame:
    return get_vendor_options()



# ============================================================================
# DOCUMENT VIEWER HELPER
# ============================================================================

def _render_cost_documents(cost_id: int):
    """
    Render all S3 documents attached to a cost entry.
    - Image (PNG/JPG) : inline preview + download button
    - PDF             : open-in-tab link + download button
    - Other           : download button only
    Source: arrival_cost_medias JOIN medias (fresh DB query, not cached view string).
    """
    att_df = get_cost_attachments(cost_id)

    if att_df.empty:
        st.info("No documents attached to this cost entry.")
        return

    for _, row in att_df.iterrows():
        filename = (row.get("filename") or "file").strip()
        s3_key   = (row.get("s3_key")   or "").strip()
        created  = str(row.get("created_date") or "")[:10]
        uploader = (row.get("uploaded_by") or row.get("created_by") or "—").strip()
        ext      = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
        icon     = get_file_icon(filename)

        with st.container(border=True):
            header_col, btn_col = st.columns([6, 2])

            with header_col:
                st.markdown(f"##### {icon} {filename}")
                st.caption(f"Uploaded by **{uploader}** · {created}")

            with btn_col:
                url = get_presigned_url(s3_key) if s3_key else None
                if url:
                    st.link_button("⬇️ Download", url=url, width="stretch")
                else:
                    st.caption("⚠️ URL unavailable")

            # ── Inline preview ──────────────────────────────────────────
            if ext in ("png", "jpg", "jpeg") and s3_key:
                with st.expander("🖼️ Preview", expanded=True):
                    try:
                        from .cost_s3 import CostS3Manager
                        content = CostS3Manager().download_file(s3_key)
                        if content:
                            st.image(content, use_container_width=True)
                        else:
                            st.caption("Could not load image from S3.")
                    except Exception as e:
                        st.caption(f"Preview error: {e}")

            elif ext == "pdf":
                if url:
                    st.markdown(
                        f'<a href="{url}" target="_blank" style="font-size:0.85em;color:#0066cc;">🔗 Open PDF in new tab</a>',
                        unsafe_allow_html=True,
                    )


# ============================================================================
# VIEW DIALOG
# ============================================================================

@st.dialog("🔍 Cost Entry Detail", width="large")
def view_cost_dialog(cost_id: int):
    entry = get_cost_by_id(cost_id)
    if not entry:
        st.error("Cost entry not found.")
        return

    cat_badge = "🟦 INTERNATIONAL" if entry.get("category") == "INTERNATIONAL" else "🟩 LOCAL"
    st.markdown(f"### {cat_badge} — {entry.get('logistic_charge', '—')}")
    st.caption(f"Cost entry **#{cost_id}** | CAN: **{entry.get('can_number', '—')}**")
    st.markdown("---")

    # ── Amounts ──────────────────────────────────────────────────────────────
    c1, c2, c3 = st.columns(3)
    c1.metric("Amount", _fmt(entry.get("amount"), entry.get("currency_code", "")))
    c2.metric("Amount (USD)", f"${float(entry.get('amount_usd') or 0):,.2f}"
              if entry.get("amount_usd") else "—")
    c3.metric("Cost / Unit (USD)", f"${float(entry.get('cost_per_unit_usd') or 0):,.6f}"
              if entry.get("cost_per_unit_usd") else "—")

    st.markdown("---")

    # ── Arrival / Shipment ────────────────────────────────────────────────────
    st.markdown("#### 🚢 Arrival / Shipment")
    r1, r2, r3, r4 = st.columns(4)
    r1.markdown(f"**CAN #**\n\n{entry.get('can_number','—')}")
    r2.markdown(f"**Date**\n\n{str(entry.get('arrival_date','—'))[:10]}")
    r3.markdown(f"**Ship Method**\n\n{entry.get('ship_method','—') or '—'}")
    r4.markdown(f"**Status**\n\n{entry.get('arrival_status','—') or '—'}")

    r5, r6, r7, r8 = st.columns(4)
    r5.markdown(f"**Sender**\n\n{entry.get('sender','—') or '—'}")
    r6.markdown(f"**Receiver**\n\n{entry.get('receiver','—') or '—'}")
    r7.markdown(f"**Shipment**\n\n{entry.get('shipment_type','—') or '—'}")
    r8.markdown(f"**Courier**\n\n{entry.get('courier','—') or '—'}")

    st.markdown("---")

    # ── Warehouse + Products ──────────────────────────────────────────────────
    wc1, wc2 = st.columns(2)
    with wc1:
        st.markdown("#### 🏭 Warehouse")
        st.markdown(
            f"**{entry.get('warehouse_name','—')}**  \n"
            f"{entry.get('warehouse_state','') or ''} "
            f"{entry.get('warehouse_country','') or ''}"
        )
    with wc2:
        st.markdown("#### 📦 Products in CAN")
        st.caption(f"Codes : {entry.get('product_codes','—') or '—'}")
        st.caption(f"Names : {entry.get('product_names','—') or '—'}")

    # ── Arrival context ───────────────────────────────────────────────────────
    st.markdown("---")
    ac1, ac2 = st.columns(2)
    ac1.metric("Total Arrival Qty", f"{float(entry.get('total_arrival_qty') or 0):,.0f}")
    ac2.metric("Lines in CAN",      entry.get("arrival_line_count", "—"))

    # ── Documents ─────────────────────────────────────────────────────────────
    doc_count = int(entry.get("doc_count") or 0)
    st.markdown("---")
    st.markdown(f"#### 📎 Documents ({doc_count})")
    _render_cost_documents(cost_id)

    # ── Audit ─────────────────────────────────────────────────────────────────
    st.markdown("---")
    a1, a2, a3 = st.columns(3)
    a1.caption(f"Created by: {entry.get('cost_created_by','—')}")
    a2.caption(f"Created:    {str(entry.get('cost_created_date','—'))[:19]}")
    a3.caption(f"Modified:   {str(entry.get('cost_modified_date','—'))[:19]}")

    st.markdown("---")
    if st.button("Close", width="stretch", key="view_close"):
        st.rerun()


# ============================================================================
# CREATE DIALOG
# ============================================================================

@st.dialog("➕ Add Inbound Cost Entry", width="large")
def create_cost_dialog():
    user = _get_user()
    st.markdown("### New Logistics Cost Entry")
    st.caption("Add an international or local charge to a Cargo Arrival Note (CAN).")
    st.markdown("---")

    # ── Step 1: Charge type ───────────────────────────────────────────────────
    types_df = _cached_cost_types()
    if types_df.empty:
        st.error("Cannot load charge types from database.")
        return

    cat_col, type_col = st.columns(2)
    with cat_col:
        category = st.selectbox(
            "Category *",
            ["INTERNATIONAL", "LOCAL"],
            key="cc_category",
            help="INTERNATIONAL = freight/ocean/air  |  LOCAL = customs, trucking, etc.",
        )
    with type_col:
        subset = types_df[types_df["type"] == category]
        if subset.empty:
            st.warning(f"No {category} charge types defined in master data.")
            return
        type_map = {row["name"]: row["id"] for _, row in subset.iterrows()}
        sel_type_name = st.selectbox("Charge Type *", list(type_map.keys()), key="cc_type")
        sel_type_id   = type_map[sel_type_name]

    # ── Step 2: Select CAN ────────────────────────────────────────────────────
    st.markdown("#### Cargo Arrival Note (CAN)")
    arrivals_df = _cached_arrivals()
    if arrivals_df.empty:
        st.error("Cannot load arrivals from database.")
        return

    can_search = st.text_input(
        "Search CAN", placeholder="CAN number or sender name…", key="cc_can_search"
    )
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
    can_map      = dict(zip(arrivals_df["label"], arrivals_df["id"]))
    sel_can_lbl  = st.selectbox("Select CAN *", list(can_map.keys()), key="cc_can")
    sel_arr_id   = can_map[sel_can_lbl]

    # ── Step 3: Amount + Vendor ───────────────────────────────────────────────
    st.markdown("---")
    amt_col, vendor_col = st.columns(2)
    with amt_col:
        amount = st.number_input(
            "Amount *",
            min_value=0.01, step=0.01, format="%.2f", key="cc_amount",
            help="Enter in the CAN's charge currency (set on the arrival record).",
        )
    with vendor_col:
        vendors_df = _cached_vendors()
        vendor_map = {"— Not specified —": None}
        if not vendors_df.empty:
            vendor_map.update({
                f"{r['name']} ({r['company_code']})": r["id"]
                for _, r in vendors_df.iterrows()
            })
        sel_vendor_lbl = st.selectbox(
            "Logistics Vendor / Courier", list(vendor_map.keys()), key="cc_vendor"
        )
        sel_vendor_id = vendor_map[sel_vendor_lbl]

    # ── Step 4: Attachments (optional) ───────────────────────────────────────
    st.markdown("---")
    with st.expander("📎 Attach Documents (optional)", expanded=False):
        uploaded = st.file_uploader(
            "Upload files",
            type=ALLOWED_EXTENSIONS_DISPLAY,
            accept_multiple_files=True,
            key="cc_files",
        )
        if uploaded:
            ok, errs, meta = validate_uploaded_files(uploaded)
            if errs:
                for e in errs:
                    st.error(e)
            else:
                summary = summarize_files(meta)
                st.success(
                    f"✅ {summary['count']} file(s) ready — "
                    f"{summary['total_size_formatted']} — "
                    f"Types: {', '.join(summary['types'])}"
                )

    # ── Actions ───────────────────────────────────────────────────────────────
    st.markdown("---")
    save_col, cancel_col = st.columns(2)
    with cancel_col:
        if st.button("Cancel", width="stretch", key="cc_cancel"):
            st.rerun()
    with save_col:
        if st.button("💾 Save", type="primary", width="stretch", key="cc_save"):
            valid, err_msg = CostService.validate_new_entry(sel_type_id, sel_arr_id, amount)
            if not valid:
                st.error(err_msg)
                return

            uid = _keycloak_id(user)

            # Upload files if any
            s3_keys = []
            if uploaded:
                ok, errs, meta = validate_uploaded_files(uploaded)
                if not ok:
                    for e in errs:
                        st.error(e)
                    return
                prepared         = prepare_files_for_upload(uploaded)
                s3_keys, failed  = upload_files_to_s3(prepared)
                if failed:
                    st.warning(f"⚠️ {len(failed)} file(s) failed to upload: {', '.join(failed)}")

            # Create cost entry
            ok, new_id, db_err = create_cost_entry(
                cost_type_id=sel_type_id,
                arrival_type=category,
                arrival_id=sel_arr_id,
                vendor_id=sel_vendor_id,
                amount=amount,
                created_by=uid,
            )
            if not ok:
                cleanup_failed_uploads(s3_keys)
                st.error(f"❌ {db_err}")
                return

            # Link attachments
            if s3_keys:
                att_ok, _, att_err = save_cost_media_records(new_id, s3_keys, uid)
                if not att_ok:
                    st.warning(f"⚠️ Entry saved but attachments failed: {att_err}")

            st.success(f"✅ Cost entry #{new_id} created — {category} / {sel_type_name}")
            _invalidate_cache()

            # ── Recalculate landed cost for this arrival ───────────────────
            _run_recalculate(sel_arr_id, f"create #{new_id}")
            st.session_state["_last_created_cost"] = {
                "id":       new_id,
                "type":     sel_type_name,
                "category": category,
                "amount":   amount,
            }
            st.rerun()


# ============================================================================
# EDIT DIALOG
# ============================================================================

@st.dialog("✏️ Edit Cost Entry", width="large")
def edit_cost_dialog(cost_id: int):
    user  = _get_user()
    entry = get_cost_by_id(cost_id)
    if not entry:
        st.error("Cost entry not found.")
        return

    st.markdown(
        f"### Edit Cost Entry **#{cost_id}**\n\n"
        f"CAN: **{entry.get('can_number','—')}** | "
        f"Category: **{entry.get('category','—')}** | "
        f"Date: {str(entry.get('arrival_date',''))[:10]}"
    )
    st.markdown("---")

    tab_info, tab_docs = st.tabs(["📋 Cost Info", "📎 Documents"])

    # =========================================================================
    # TAB 1 — COST INFO
    # =========================================================================
    with tab_info:
        # ── Charge type ───────────────────────────────────────────────────────
        types_df    = _cached_cost_types()
        current_cat = entry.get("category", "INTERNATIONAL")
        subset      = types_df[types_df["type"] == current_cat]
        type_map    = {r["name"]: r["id"] for _, r in subset.iterrows()}

        cur_type_name = entry.get("logistic_charge", "")
        default_idx   = list(type_map.keys()).index(cur_type_name)                         if cur_type_name in type_map else 0

        tc, _ = st.columns(2)
        with tc:
            st.caption(f"Category: **{current_cat}** (fixed on existing entry)")
            sel_type_name = st.selectbox(
                "Charge Type *", list(type_map.keys()),
                index=default_idx, key="ec_type"
            )
            sel_type_id = type_map[sel_type_name]

        # ── Amount ────────────────────────────────────────────────────────────
        ac, cc = st.columns(2)
        with ac:
            new_amount = st.number_input(
                "Amount *",
                value=max(float(entry.get("amount") or 0.01), 0.01),
                min_value=0.01, step=0.01, format="%.2f",
                key="ec_amount",
            )
        with cc:
            st.text_input(
                "Currency", value=entry.get("currency_code", "—"),
                disabled=True, key="ec_currency",
                help="Currency is set on the arrival record — not editable here.",
            )
            if entry.get("amount_usd") and entry.get("amount") and float(entry["amount"]) > 0:
                ratio = new_amount / float(entry["amount"])
                st.caption(f"≈ USD {float(entry['amount_usd']) * ratio:,.2f}")

        # ── Vendor ────────────────────────────────────────────────────────────
        vendors_df = _cached_vendors()
        vendor_map = {"— Not specified —": None}
        if not vendors_df.empty:
            vendor_map.update({
                f"{r['name']} ({r['company_code']})": r["id"]
                for _, r in vendors_df.iterrows()
            })

        cur_vendor_id   = entry.get("logistics_vendor_id")
        default_vnd_lbl = next(
            (lbl for lbl, vid in vendor_map.items() if vid == cur_vendor_id),
            "— Not specified —",
        )
        vnd_idx       = list(vendor_map.keys()).index(default_vnd_lbl)                         if default_vnd_lbl in vendor_map else 0
        sel_vendor_lbl = st.selectbox(
            "Logistics Vendor / Courier",
            list(vendor_map.keys()), index=vnd_idx, key="ec_vendor"
        )
        sel_vendor_id = vendor_map[sel_vendor_lbl]

        # ── Change summary ────────────────────────────────────────────────────
        st.markdown("---")
        valid, err_msg, changes = CostService.validate_edit(sel_type_id, new_amount, entry)
        if sel_vendor_id != cur_vendor_id:
            changes.append(f"Vendor: **{entry.get('courier','—')}** → **{sel_vendor_lbl}**")

        if not valid:
            st.error(err_msg)
        elif changes:
            st.info("**Changes to save:**\n\n" + "\n\n".join(f"• {c}" for c in changes))
        else:
            st.caption("No changes detected.")

        # ── Save / Cancel ─────────────────────────────────────────────────────
        save_col, cancel_col = st.columns(2)
        with cancel_col:
            if st.button("Cancel", width="stretch", key="ec_cancel"):
                st.rerun()
        with save_col:
            if st.button(
                "💾 Save Changes", type="primary",
                width="stretch", key="ec_save",
                disabled=(not valid or len(changes) == 0),
            ):
                uid = _keycloak_id(user)
                ok, db_err = update_cost_entry(
                    cost_id=cost_id,
                    cost_type_id=sel_type_id,
                    vendor_id=sel_vendor_id,
                    amount=new_amount,
                    updated_by=uid,
                )
                if ok:
                    st.success(f"✅ Cost entry #{cost_id} updated.")
                    _invalidate_cache()
                    # ── Recalculate landed cost ──────────────────────────
                    _run_recalculate(entry.get("arrival_id"), f"edit #{cost_id}")
                    st.rerun()
                else:
                    st.error(f"❌ {db_err}")

    # =========================================================================
    # TAB 2 — DOCUMENTS
    # =========================================================================
    with tab_docs:
        uid = _keycloak_id(user)

        # ── Existing files ────────────────────────────────────────────────────
        att_df = get_cost_attachments(cost_id)

        if att_df.empty:
            st.info("No documents attached yet.")
        else:
            st.markdown(f"**{len(att_df)} document(s) attached**")
            for _, row in att_df.iterrows():
                filename = (row.get("filename") or "file").strip()
                s3_key   = (row.get("s3_key")   or "").strip()
                created  = str(row.get("created_date") or "")[:10]
                uploader = (row.get("uploaded_by") or row.get("created_by") or "—").strip()
                ext      = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
                icon     = get_file_icon(filename)
                link_id  = row.get("link_id")

                with st.container(border=True):
                    name_col, dl_col, del_col = st.columns([5, 2, 1])

                    with name_col:
                        st.markdown(f"**{icon} {filename}**")
                        st.caption(f"By **{uploader}** · {created}")

                    with dl_col:
                        url = get_presigned_url(s3_key) if s3_key else None
                        if url:
                            st.link_button("⬇️ Download", url=url, width="stretch")
                        else:
                            st.caption("⚠️ URL unavailable")

                    with del_col:
                        if st.button(
                            "🗑️", key=f"ec_del_att_{link_id}",
                            help=f"Remove {filename}",
                        ):
                            ok, msg = delete_cost_attachment(int(link_id))
                            if ok:
                                st.success(f"Removed {filename}")
                                _invalidate_cache()
                                st.rerun()
                            else:
                                st.error(msg)

                    # ── Inline preview ──────────────────────────────────────
                    if ext in ("png", "jpg", "jpeg") and s3_key:
                        with st.expander("🖼️ Preview", expanded=False):
                            try:
                                from .cost_s3 import CostS3Manager
                                img_bytes = CostS3Manager().download_file(s3_key)
                                if img_bytes:
                                    st.image(img_bytes, use_container_width=True)
                                else:
                                    st.caption("Could not load image.")
                            except Exception as e:
                                st.caption(f"Preview error: {e}")
                    elif ext == "pdf":
                        url2 = get_presigned_url(s3_key) if s3_key else None
                        if url2:
                            st.markdown(
                                f'<a href="{url2}" target="_blank" style="font-size:0.85em;">🔗 Open PDF in new tab</a>',
                                unsafe_allow_html=True,
                            )

        # ── Upload new files ──────────────────────────────────────────────────
        st.markdown("---")
        st.markdown("#### ⬆️ Attach New Files")
        new_files = st.file_uploader(
            "Select files (PDF, PNG, JPG — max 10 MB each)",
            type=ALLOWED_EXTENSIONS_DISPLAY,
            accept_multiple_files=True,
            key="ec_new_files",
        )

        if new_files:
            ok_v, errs, meta = validate_uploaded_files(new_files)
            if errs:
                for e in errs:
                    st.error(e)
            else:
                summary = summarize_files(meta)
                st.success(
                    f"✅ {summary['count']} file(s) ready — "
                    f"{summary['total_size_formatted']} — "
                    f"{', '.join(summary['types'])}"
                )
                if st.button(
                    "⬆️ Upload & Attach",
                    type="primary", width="stretch",
                    key="ec_upload_btn",
                ):
                    prepared        = prepare_files_for_upload(new_files)
                    s3_keys, failed = upload_files_to_s3(prepared)
                    if failed:
                        st.warning(f"⚠️ Failed: {', '.join(failed)}")
                    if s3_keys:
                        att_ok, _, att_err = save_cost_media_records(cost_id, s3_keys, uid)
                        if att_ok:
                            st.success(f"✅ {len(s3_keys)} file(s) attached.")
                            _invalidate_cache()
                            st.rerun()
                        else:
                            cleanup_failed_uploads(s3_keys)
                            st.error(f"❌ DB error: {att_err}")


# ============================================================================
# DELETE DIALOG
# ============================================================================

@st.dialog("🗑️ Delete Cost Entry", width="small")
def delete_cost_dialog(cost_id: int):
    user  = _get_user()
    entry = get_cost_by_id(cost_id)
    if not entry:
        st.error("Cost entry not found.")
        return

    st.warning("⚠️ **This action cannot be undone.**")
    st.markdown(
        f"You are about to **permanently delete** entry **#{cost_id}**:\n\n"
        f"- **Charge:**   {entry.get('logistic_charge','—')}\n"
        f"- **Category:** {entry.get('category','—')}\n"
        f"- **CAN:**      {entry.get('can_number','—')}\n"
        f"- **Amount:**   {_fmt(entry.get('amount'), entry.get('currency_code',''))}\n"
        f"- **USD:**      ${float(entry.get('amount_usd') or 0):,.2f}"
    )
    st.markdown("---")

    confirmed = st.checkbox(
        "I confirm I want to delete this cost entry", key="del_confirm"
    )
    del_col, cancel_col = st.columns(2)
    with cancel_col:
        if st.button("Cancel", width="stretch", key="del_cancel"):
            st.rerun()
    with del_col:
        if st.button(
            "🗑️ Delete", type="primary",
            width="stretch", key="del_btn",
            disabled=not confirmed,
        ):
            uid    = _keycloak_id(user)
            ok, msg = delete_cost_entry(cost_id, deleted_by=uid)
            if ok:
                st.success(f"✅ {msg}")
                _invalidate_cache()
                # ── Recalculate landed cost ──────────────────────────────
                _run_recalculate(entry.get("arrival_id"), f"delete #{cost_id}")
                st.session_state["_last_deleted_cost"] = cost_id
                st.rerun()
            else:
                st.error(f"❌ {msg}")


# ============================================================================
# MANAGE ATTACHMENTS DIALOG
# ============================================================================

@st.dialog("📎 Manage Attachments", width="large")
def attachments_dialog(cost_id: int):
    """View existing attachments and upload new ones."""
    user  = _get_user()
    entry = get_cost_by_id(cost_id)
    if not entry:
        st.error("Cost entry not found.")
        return

    st.markdown(
        f"### Attachments — Cost Entry **#{cost_id}**\n\n"
        f"CAN: **{entry.get('can_number','—')}** | "
        f"{entry.get('logistic_charge','—')}"
    )
    st.markdown("---")

    # ── Existing attachments ──────────────────────────────────────────────────
    att_df = get_cost_attachments(cost_id)
    if att_df.empty:
        st.info("No attachments yet.")
    else:
        st.markdown(f"#### Current Attachments ({len(att_df)})")
        for _, row in att_df.iterrows():
            col_icon, col_name, col_date, col_del = st.columns([1, 5, 3, 1])
            with col_icon:
                st.write(get_file_icon(row.get("filename", "")))
            with col_name:
                url = get_presigned_url(row.get("s3_key", ""))
                if url:
                    st.markdown(f"[{row.get('filename','—')}]({url})")
                else:
                    st.write(row.get("filename", "—"))
            with col_date:
                st.caption(str(row.get("created_date", ""))[:10])
            with col_del:
                if st.button("✕", key=f"del_att_{row['link_id']}", help="Remove"):
                    ok, msg = delete_cost_attachment(int(row["link_id"]))
                    if ok:
                        st.success("Removed")
                        st.rerun()
                    else:
                        st.error(msg)

    # ── Upload new ────────────────────────────────────────────────────────────
    st.markdown("---")
    st.markdown("#### Upload New Files")
    new_files = st.file_uploader(
        "Select files",
        type=ALLOWED_EXTENSIONS_DISPLAY,
        accept_multiple_files=True,
        key="att_upload",
    )

    if new_files:
        ok, errs, meta = validate_uploaded_files(new_files)
        if errs:
            for e in errs:
                st.error(e)
        else:
            summary = summarize_files(meta)
            st.success(
                f"✅ {summary['count']} file(s) — "
                f"{summary['total_size_formatted']}"
            )
            if st.button(
                "⬆️ Upload & Link", type="primary",
                width="stretch", key="att_upload_btn"
            ):
                uid        = _keycloak_id(user)
                prepared   = prepare_files_for_upload(new_files)
                s3_keys, failed = upload_files_to_s3(prepared)

                if failed:
                    st.warning(f"⚠️ Upload failed for: {', '.join(failed)}")

                if s3_keys:
                    att_ok, _, att_err = save_cost_media_records(cost_id, s3_keys, uid)
                    if att_ok:
                        st.success(f"✅ {len(s3_keys)} file(s) attached.")
                        _invalidate_cache()
                        st.rerun()
                    else:
                        cleanup_failed_uploads(s3_keys)
                        st.error(f"❌ DB error: {att_err}")

    st.markdown("---")
    if st.button("Close", width="stretch", key="att_close"):
        st.rerun()