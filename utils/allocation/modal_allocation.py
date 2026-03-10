"""
Create Allocation Modal - v3.0 (Improved UI/UX)
================================================
Modal for creating new allocations with improved progress display.

IMPROVEMENTS in v3.0:
- After success: Dialog stays open, Save button disabled
- User must click Close/Cancel to dismiss
- Clear progress display with st.status()
- Prevents accidental double-submissions
"""
import streamlit as st
import time
from datetime import datetime
import pandas as pd

from .allocation_service import AllocationService
from .supply_data import SupplyData
from .formatters import format_number, format_date
from .validators import AllocationValidator
from .uom_converter import UOMConverter
from .allocation_email import AllocationEmailService
from ..auth import AuthManager


# Initialize services
allocation_service = AllocationService()
supply_data = SupplyData()
validator = AllocationValidator()
uom_converter = UOMConverter()
auth = AuthManager()
email_service = AllocationEmailService()


def get_actor_info() -> dict:
    """Get current user info for email notifications"""
    return {
        'email': st.session_state.user.get('email', ''),
        'name': st.session_state.user.get('full_name', st.session_state.user.get('username', 'Unknown'))
    }


def reset_modal_state():
    """Reset all modal-specific state"""
    st.session_state.allocation_processing = False
    st.session_state.allocation_completed = False
    st.session_state.allocation_result = None
    st.session_state._allocation_data = None


def show_dual_uom_metric(label: str, 
                         standard_qty: float, standard_uom: str,
                         selling_qty: float, selling_uom: str,
                         conversion_ratio: str):
    """Show metric with both standard and selling UOM"""
    if uom_converter.needs_conversion(conversion_ratio):
        st.metric(label, f"{format_number(standard_qty)} {standard_uom}")
        st.caption(f"= {format_number(selling_qty)} {selling_uom}")
    else:
        st.metric(label, f"{format_number(standard_qty)} {standard_uom}")


def format_supply_info_with_real_time_availability(supply, source_type, oc, current_total_selected):
    """Format supply information with real-time availability considering current selections"""
    if source_type == 'INVENTORY':
        info = f"Batch {supply['batch_number']} - Exp: {format_date(supply['expiry_date'])}"
    elif source_type == 'PENDING_CAN':
        info = f"{supply['arrival_note_number']} - Arr: {format_date(supply['arrival_date'])}"
    elif source_type == 'PENDING_PO':
        etd_str = format_date(supply['etd'])
        eta_str = format_date(supply.get('eta')) if supply.get('eta') else 'N/A'
        info = f"{supply['po_number']} - ETD: {etd_str} | ETA: {eta_str}"
    else:
        info = f"{supply['from_warehouse']} → {supply['to_warehouse']}"
    
    # Get quantities
    total_qty = supply.get('total_quantity', 0)
    committed_qty = supply.get('committed_quantity', 0)
    available_qty = supply.get('available_quantity', 0)
    standard_uom = supply.get('uom', 'pcs')
    
    # Format quantity string with real-time context
    if available_qty <= 0:
        qty_str = f"Total: {format_number(total_qty)} | ❌ Fully committed"
    elif committed_qty > 0:
        qty_str = f"Total: {format_number(total_qty)} | Committed: {format_number(committed_qty)} | ✅ Available: {format_number(available_qty)} {standard_uom}"
    else:
        qty_str = f"✅ Available: {format_number(available_qty)} {standard_uom}"
    
    # Add selling UOM if different
    if available_qty > 0 and uom_converter.needs_conversion(oc.get('uom_conversion', '1')):
        qty_selling = uom_converter.convert_quantity(
            available_qty,
            'standard',
            'selling',
            oc.get('uom_conversion', '1')
        )
        selling_uom = oc.get('selling_uom', 'pcs')
        qty_str += f" (= {format_number(qty_selling)} {selling_uom})"
    
    return f"{info} - {qty_str}"


@st.dialog("Create Allocation", width="large")
def show_allocation_modal():
    """Allocation modal with improved UI/UX and progress display"""
    oc = st.session_state.selections['oc_for_allocation']
    
    if not oc:
        st.error("No OC selected")
        if st.button("Close"):
            st.session_state.modals['allocation'] = False
            st.session_state.selections['oc_for_allocation'] = None
            st.rerun()
        return
    
    # Validate user session before allowing allocation
    user_id = st.session_state.user.get('id')
    if not user_id:
        st.error("⚠️ Session error. Please login again.")
        time.sleep(2)
        auth.logout()
        st.switch_page("app.py")
        st.stop()
    
    # Initialize modal state
    if 'allocation_processing' not in st.session_state:
        st.session_state.allocation_processing = False
    if 'allocation_completed' not in st.session_state:
        st.session_state.allocation_completed = False
    if 'allocation_result' not in st.session_state:
        st.session_state.allocation_result = None
    
    is_completed = st.session_state.allocation_completed
    is_processing = st.session_state.allocation_processing
    
    # Header
    st.markdown(f"### Allocate to {oc['oc_number']}")
    
    # Show warning if over-allocated
    if oc.get('is_over_allocated') == 'Yes':
        st.warning(f"⚠️ This OC is already over-allocated! {oc.get('allocation_warning', '')}")
    
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Customer", oc['customer'])
    with col2:
        st.metric("Product", oc['product_name'][:30])
    with col3:
        show_dual_uom_metric(
            "Required",
            oc.get('pending_standard_delivery_quantity', 0),
            oc.get('standard_uom', 'pcs'),
            oc.get('pending_quantity', 0),
            oc.get('selling_uom', 'pcs'),
            oc.get('uom_conversion', '1')
        )
    
    st.divider()
    
    # Get supply summary first
    standard_uom = oc.get('standard_uom', 'pcs')
    supply_summary = supply_data.get_product_supply_summary(oc['product_id'])
    
    # Extract expired info
    has_expired = supply_summary.get('has_expired', False)
    expired_qty = supply_summary.get('expired_supply', 0)
    usable_supply = supply_summary.get('usable_supply', supply_summary['total_supply'])
    
    # ===== EXPIRED INVENTORY WARNING =====
    if has_expired and expired_qty > 0:
        st.warning(
            f"⚠️ **{format_number(expired_qty)} {standard_uom} expired inventory detected!** "
            f"SOFT allocation is limited to usable supply ({format_number(usable_supply)} {standard_uom}). "
            f"For clearance/expired stock orders, select the specific expired batch below using HARD allocation."
        )
    
    # ===== SUPPLY OVERVIEW =====
    st.markdown("**📊 Supply Overview:**")
    num_cols = 5 if has_expired else 4
    supply_cols = st.columns(num_cols)
    
    with supply_cols[0]:
        st.metric(
            "Total Supply",
            f"{format_number(supply_summary['total_supply'])} {standard_uom}",
            help="Total quantity from all sources (including expired inventory)" if has_expired else "Total quantity available from all sources"
        )
    
    col_idx = 1
    if has_expired:
        with supply_cols[col_idx]:
            st.metric(
                "✅ Usable Supply",
                f"{format_number(usable_supply)} {standard_uom}",
                delta=f"-{format_number(expired_qty)} expired",
                delta_color="inverse",
                help="Supply excluding expired inventory. SOFT allocation is capped to this amount."
            )
        col_idx += 1
    
    with supply_cols[col_idx]:
        committed_help = (
            "Already allocated but not yet delivered\n\n"
            "Formula:\n"
            "Committed = Σ MIN(pending_delivery, undelivered_allocated)\n\n"
            "This prevents over-blocking supply when delivery data is incomplete"
        )
        st.metric(
            "Committed",
            f"{format_number(supply_summary['total_committed'])} {standard_uom}",
            help=committed_help
        )
    
    with supply_cols[col_idx + 1]:
        availability_color = "🟢" if supply_summary['coverage_ratio'] > 50 else "🟡" if supply_summary['coverage_ratio'] > 20 else "🔴"
        st.metric(
            f"{availability_color} Available",
            f"{format_number(supply_summary['available'])} {standard_uom}",
            delta=f"{supply_summary['coverage_ratio']:.0f}% of usable" if has_expired else f"{supply_summary['coverage_ratio']:.0f}% of total",
            help="Usable supply minus committed (excludes expired)" if has_expired else "Quantity available for new allocations"
        )
    
    with supply_cols[col_idx + 2]:
        st.metric(
            "Max SOFT Allocation",
            f"{format_number(supply_summary['available'])} {standard_uom}",
            help="Based on usable (non-expired) supply minus committed" if has_expired else "Maximum quantity for SOFT allocation"
        )
    
    # Show warnings if needed
    if supply_summary['available'] <= 0:
        if has_expired and supply_summary.get('total_available', 0) > 0:
            st.error(
                f"❌ No usable supply available for SOFT allocation. "
                f"However, {format_number(supply_summary['total_available'])} {standard_uom} "
                f"exists including expired stock. Select specific expired batches below for HARD allocation."
            )
        else:
            st.error("❌ No supply available for allocation. All supply has been committed to other orders.")
    elif supply_summary['coverage_ratio'] < 20:
        st.warning(f"⚠️ Low supply availability! Only {supply_summary['coverage_ratio']:.0f}% available.")
    
    st.divider()
    
    # Get supply details with availability
    supply_details = supply_data.get_supply_with_availability(oc['product_id'])
    
    if supply_details.empty and supply_summary['available'] <= 0 and not has_expired:
        st.error("⛔ No supply available for this product")
        st.info("All existing supply has been committed. Please check with procurement team.")
        if st.button("Close", use_container_width=True):
            reset_modal_state()
            st.session_state.modals['allocation'] = False
            st.session_state.selections['oc_for_allocation'] = None
            st.rerun()
        return
    
    st.info("ℹ️ **Allocation Rule**: All allocations are made in standard UOM to ensure whole container quantities")
    
    # ============================================================
    # SUPPLY SELECTION - Disabled after completion
    # ============================================================
    st.markdown("**Supply Sources:**")
    
    selected_supplies = []
    total_selected_standard = 0
    
    # Check if supply_details has data before processing
    if supply_details.empty or 'source_type' not in supply_details.columns:
        st.warning("⚠️ No supply sources available for this product")
    else:
        # Group by source type
        for source_type in ['INVENTORY', 'PENDING_CAN', 'PENDING_PO', 'PENDING_WHT']:
            type_supplies = supply_details[supply_details['source_type'] == source_type]
            
            if not type_supplies.empty:
                source_label = {
                    'INVENTORY': '📦 Inventory',
                    'PENDING_CAN': '🚢 Pending CAN',
                    'PENDING_PO': '📋 Pending PO',
                    'PENDING_WHT': '🚚 WH Transfer'
                }.get(source_type, source_type)
                
                # Count expired items for inventory section header
                if source_type == 'INVENTORY' and 'is_expired' in type_supplies.columns:
                    expired_count = int(type_supplies['is_expired'].sum())
                    if expired_count > 0:
                        st.markdown(f"**{source_label}** _(⚠️ {expired_count} expired batch{'es' if expired_count > 1 else ''})_")
                    else:
                        st.markdown(f"**{source_label}**")
                else:
                    st.markdown(f"**{source_label}**")
                
                for idx, supply in type_supplies.iterrows():
                    is_expired_item = bool(supply.get('is_expired', 0))
                    expiry_status = supply.get('expiry_status', 'OK')
                    
                    col1, col2 = st.columns([3, 1])
                    
                    with col1:
                        info = format_supply_info_with_real_time_availability(
                            supply, source_type, oc, total_selected_standard
                        )
                        
                        # Add expired marker to display info
                        if is_expired_item:
                            info = f"⛔ [EXPIRED] {info}"
                        elif expiry_status == 'Expiring Soon':
                            info = f"⚠️ [Expiring Soon] {info}"
                        
                        is_available = supply.get('available_quantity', 0) > 0
                        would_exceed_supply = False
                        if is_available and not is_expired_item:
                            # Non-expired: check against usable supply cap
                            max_selectable = min(
                                supply.get('available_quantity', 0),
                                supply_summary['available'] - total_selected_standard
                            )
                            would_exceed_supply = max_selectable <= 0
                        elif is_available and is_expired_item:
                            # Expired: always selectable for HARD allocation (no usable cap)
                            would_exceed_supply = False
                        
                        if not is_available:
                            help_text = "No quantity available - fully committed"
                        elif would_exceed_supply:
                            help_text = "⚠️ Cannot select - would exceed usable available supply"
                        elif is_expired_item:
                            help_text = "⛔ EXPIRED - Only use for clearance/stock-clear orders (HARD allocation)"
                        else:
                            help_text = None
                        
                        selected = st.checkbox(
                            info,
                            key=f"supply_{idx}_{supply['source_id']}_{source_type}",
                            disabled=(not is_available or would_exceed_supply or is_completed),
                            help=help_text
                        )
                    
                    with col2:
                        if selected and is_available and not would_exceed_supply:
                            pending_standard = oc.get('pending_standard_delivery_quantity', oc['pending_quantity'])
                            available_qty = supply.get('available_quantity', 0)
                            
                            if is_expired_item:
                                # Expired items: cap by available qty and pending, not by usable supply
                                max_qty_standard = min(
                                    available_qty,
                                    pending_standard - total_selected_standard
                                )
                            else:
                                # Non-expired: respect usable supply cap
                                remaining_supply_cap = supply_summary['available'] - total_selected_standard
                                max_qty_standard = min(
                                    available_qty, 
                                    pending_standard - total_selected_standard,
                                    remaining_supply_cap
                                )
                            
                            if uom_converter.needs_conversion(oc.get('uom_conversion', '1')):
                                max_qty_selling = uom_converter.convert_quantity(
                                    max_qty_standard,
                                    'standard',
                                    'selling',
                                    oc.get('uom_conversion', '1')
                                )
                                help_text = f"Max: {format_number(max_qty_standard)} {standard_uom} (= {format_number(max_qty_selling)} {oc.get('selling_uom', 'pcs')})"
                            else:
                                help_text = f"Max: {format_number(max_qty_standard)} {standard_uom}"
                            
                            qty_standard = st.number_input(
                                f"Qty ({standard_uom})",
                                min_value=0.0,
                                max_value=float(max_qty_standard),
                                value=float(max_qty_standard),
                                step=1.0,
                                key=f"qty_{idx}_{supply['source_id']}_{source_type}",
                                help=help_text,
                                disabled=is_completed
                            )
                            
                            if qty_standard > 0:
                                supply_dict = supply.to_dict()
                                supply_dict['is_expired'] = is_expired_item
                                selected_supplies.append({
                                    'source_type': source_type,
                                    'source_id': supply['source_id'],
                                    'quantity': qty_standard,
                                    'supply_info': supply_dict
                                })
                                total_selected_standard += qty_standard
                                
                                # Show expired warning for selected expired item
                                if is_expired_item:
                                    st.caption("⛔ Expired batch - HARD allocation for clearance")
    
    st.divider()
    
    # SOFT allocation option
    st.markdown("**OR**")
    use_soft = st.checkbox("🔄 SOFT Allocation (no specific source)", disabled=is_completed)
    
    if use_soft:
        pending_standard = oc.get('pending_standard_delivery_quantity', oc['pending_quantity'])
        # SOFT allocation uses usable (non-expired) supply as cap
        max_soft_qty = min(pending_standard, supply_summary.get('available', 0))
        
        if max_soft_qty <= 0:
            if has_expired and supply_summary.get('total_available', 0) > 0:
                st.error(
                    "❌ Cannot create SOFT allocation - no usable supply available. "
                    "Remaining supply is expired inventory. Use HARD allocation above to select specific expired batches."
                )
            else:
                st.error("❌ Cannot create SOFT allocation - no supply available")
        else:
            if uom_converter.needs_conversion(oc.get('uom_conversion', '1')):
                max_soft_qty_selling = uom_converter.convert_quantity(
                    max_soft_qty, 'standard', 'selling', oc.get('uom_conversion', '1')
                )
                selling_uom = oc.get('selling_uom', 'pcs')
                help_text = f"Max: {format_number(max_soft_qty)} {standard_uom} (= {format_number(max_soft_qty_selling)} {selling_uom})"
            else:
                help_text = f"Max: {format_number(max_soft_qty)} {standard_uom}"
            
            if max_soft_qty < pending_standard:
                if has_expired:
                    st.warning(
                        f"⚠️ Usable supply ({format_number(supply_summary['available'])} {standard_uom}) "
                        f"is less than pending quantity ({format_number(pending_standard)} {standard_uom}). "
                        f"Expired inventory ({format_number(expired_qty)} {standard_uom}) is excluded from SOFT allocation."
                    )
                else:
                    st.warning(
                        f"⚠️ Available supply ({format_number(supply_summary['available'])} {standard_uom}) "
                        f"is less than pending quantity ({format_number(pending_standard)} {standard_uom})"
                    )
            
            st.caption(f"Allocate quantity in {standard_uom} (standard UOM)")
            soft_qty_standard = st.number_input(
                "Quantity",
                min_value=0.0,
                max_value=float(max_soft_qty),
                value=0.0,
                step=1.0,
                help=help_text,
                disabled=(max_soft_qty <= 0 or is_completed)
            )
            
            if soft_qty_standard > 0:
                selected_supplies = [{
                    'source_type': None,
                    'source_id': None,
                    'quantity': soft_qty_standard,
                    'supply_info': {'type': 'SOFT', 'description': 'No specific source'}
                }]
                total_selected_standard = soft_qty_standard
    
    st.divider()
    
    # Summary section
    col1, col2 = st.columns(2)
    
    with col1:
        if uom_converter.needs_conversion(oc.get('uom_conversion', '1')):
            total_selected_selling = uom_converter.convert_quantity(
                total_selected_standard, 'standard', 'selling', oc.get('uom_conversion', '1')
            )
            selling_uom = oc.get('selling_uom', 'pcs')
            st.metric("Total Selected", f"{format_number(total_selected_standard)} {standard_uom}")
            st.caption(f"= {format_number(total_selected_selling)} {selling_uom}")
        else:
            st.metric("Total Selected", f"{format_number(total_selected_standard)} {standard_uom}")
    
    with col2:
        pending_standard = oc.get('pending_standard_delivery_quantity', oc['pending_quantity'])
        coverage = (total_selected_standard / pending_standard * 100) if pending_standard > 0 else 0
        st.metric("Coverage", f"{coverage:.1f}%")
    
    # Supply availability check
    # Determine if any selected supply is expired (HARD allocation for clearance)
    has_expired_selection = any(
        s.get('supply_info', {}).get('is_expired', False) 
        for s in selected_supplies
    )
    
    if total_selected_standard > 0 and not use_soft:
        if has_expired_selection:
            # Mixed selection with expired: just check total supply (including expired)
            total_available_all = supply_summary.get('total_available', supply_summary.get('available', 0))
            if total_selected_standard > total_available_all + supply_summary.get('expired_supply', 0):
                st.error(
                    f"❌ Total allocation ({format_number(total_selected_standard)} {standard_uom}) "
                    f"exceeds total available supply ({format_number(total_available_all)} {standard_uom})"
                )
            else:
                st.info(
                    f"ℹ️ Selection includes expired inventory. "
                    f"This will be a HARD allocation for clearance purposes."
                )
        elif total_selected_standard > supply_summary.get('available', 0):
            st.error(
                f"❌ Total allocation ({format_number(total_selected_standard)} {standard_uom}) "
                f"exceeds usable available supply ({format_number(supply_summary['available'])} {standard_uom})"
            )
    elif total_selected_standard > 0 and use_soft:
        if total_selected_standard > supply_summary.get('available', 0):
            st.error(
                f"❌ SOFT allocation ({format_number(total_selected_standard)} {standard_uom}) "
                f"exceeds usable available supply ({format_number(supply_summary['available'])} {standard_uom})"
            )
    
    # Over-allocation warning (OC level)
    effective_qty_standard = oc.get('standard_quantity', pending_standard)
    current_effective_allocated = oc.get('total_effective_allocated_qty_standard', 0)
    new_total_effective = current_effective_allocated + total_selected_standard
    
    if new_total_effective > effective_qty_standard:
        over_qty_standard = new_total_effective - effective_qty_standard
        over_pct = (over_qty_standard / effective_qty_standard * 100) if effective_qty_standard > 0 else 0
        max_allowed = effective_qty_standard
        
        if new_total_effective > max_allowed:
            if uom_converter.needs_conversion(oc.get('uom_conversion', '1')):
                over_qty_selling = uom_converter.convert_quantity(
                    over_qty_standard, 'standard', 'selling', oc.get('uom_conversion', '1')
                )
                st.error(
                    f"⚡ Would exceed OC limit by {format_number(over_qty_standard)} {standard_uom} "
                    f"(= {format_number(over_qty_selling)} {oc.get('selling_uom')}) - "
                    f"{over_pct:.1f}% over! Maximum allowed is 100% of OC quantity."
                )
            else:
                st.error(
                    f"⚡ Would exceed OC limit by {format_number(over_qty_standard)} {standard_uom} "
                    f"({over_pct:.1f}% over)! Maximum allowed is 100% of OC quantity."
                )
    
    # Additional fields - disabled after completion
    allocated_etd = st.date_input("Allocated ETD", value=oc['etd'], disabled=is_completed)

    # Validate allocated ETD against PO ETAs
    if not use_soft and selected_supplies:
        max_eta = None
        po_with_max_eta = None
        
        for supply_item in selected_supplies:
            if supply_item['source_type'] == 'PENDING_PO':
                supply_info = supply_item['supply_info']
                if supply_info.get('eta'):
                    try:
                        eta_date = pd.to_datetime(supply_info['eta']).date()
                        if max_eta is None or eta_date > max_eta:
                            max_eta = eta_date
                            po_with_max_eta = supply_info.get('po_number', 'PO')
                    except:
                        pass
        
        if max_eta and allocated_etd < max_eta:
            st.warning(
                f"⚠️ Allocated ETD ({format_date(allocated_etd)}) is earlier than the ETA of {po_with_max_eta} ({format_date(max_eta)}). "
                "The goods won't arrive until the ETA date. Consider adjusting the allocated ETD to be on or after the ETA."
            )

    notes = st.text_area("Notes (optional)", disabled=is_completed)
    
    # ============================================================
    # ACTION BUTTONS
    # ============================================================
    col1, col2 = st.columns(2)
    
    with col1:
        # Determine save eligibility based on selection type
        if has_expired_selection and not use_soft:
            # HARD allocation with expired: check against total supply (including expired)
            can_save = total_selected_standard > 0
        elif use_soft:
            # SOFT allocation: check against usable supply only
            can_save = (
                total_selected_standard > 0 and 
                total_selected_standard <= supply_summary.get('available', float('inf'))
            )
        else:
            # HARD allocation without expired: check against usable supply
            can_save = (
                total_selected_standard > 0 and 
                total_selected_standard <= supply_summary.get('available', float('inf'))
            )
        
        if not can_save and total_selected_standard == 0:
            button_help = "Please select at least one supply source or enter SOFT allocation quantity"
        elif not can_save and total_selected_standard > supply_summary.get('available', 0):
            button_help = f"Total selection exceeds available supply by {format_number(total_selected_standard - supply_summary['available'])} {standard_uom}"
        else:
            button_help = "Click to save allocation"
        
        # Disable Save button if:
        # - Validation failed
        # - Processing in progress  
        # - Already completed
        save_disabled = (
            not can_save or 
            st.session_state.allocation_processing or 
            st.session_state.allocation_completed
        )
        
        if st.button(
            "💾 Save Allocation", 
            type="primary", 
            use_container_width=True, 
            disabled=save_disabled,
            help=button_help
        ):
            # Save data before processing
            st.session_state._allocation_data = {
                'selected_supplies': selected_supplies,
                'total_selected_standard': total_selected_standard,
                'use_soft': use_soft,
                'allocated_etd': allocated_etd,
                'notes': notes,
                'standard_uom': standard_uom
            }
            st.session_state.allocation_processing = True
            st.rerun()
    
    with col2:
        if st.button(
            "Cancel", 
            use_container_width=True, 
            disabled=st.session_state.allocation_processing
        ):
            reset_modal_state()
            st.session_state.modals['allocation'] = False
            st.session_state.selections['oc_for_allocation'] = None
            st.cache_data.clear()
            st.rerun()
    
    # ============================================================
    # SHOW COMPLETED RESULT (if already done)
    # ============================================================
    if st.session_state.allocation_completed and st.session_state.allocation_result:
        result = st.session_state.allocation_result
        with st.status("✅ Allocation complete!", state="complete", expanded=False):
            st.write(result.get('message', 'Allocation successful'))
            if result.get('allocation_number'):
                st.write(f"📋 Allocation Number: **{result['allocation_number']}**")
            if result.get('email_status'):
                st.write(result['email_status'])
    
    # ============================================================
    # PROCESS ALLOCATION
    # ============================================================
    if st.session_state.allocation_processing and not st.session_state.allocation_completed:
        saved_data = st.session_state.get('_allocation_data', {})
        
        with st.status("Processing allocation...", expanded=True) as status:
            result_data = {
                'success': False, 
                'message': '', 
                'allocation_number': '',
                'email_status': ''
            }
            
            # Step 1: Validate user session again
            status.update(label="🔐 Validating session...", state="running")
            user_id = st.session_state.user.get('id')
            if not user_id:
                status.update(label="❌ Session error", state="error")
                st.error("⚠️ Session error. Please login again.")
                time.sleep(2)
                auth.logout()
                st.switch_page("app.py")
                st.stop()
            
            # Step 2: Validate allocation
            status.update(label="✅ Validating allocation...", state="running")
            errors = validator.validate_create_allocation(
                saved_data.get('selected_supplies', []),
                oc,
                'SOFT' if saved_data.get('use_soft') else 'HARD',
                st.session_state.user['role']
            )
            
            if errors:
                status.update(label="❌ Validation failed", state="error")
                for error in errors:
                    st.error(f"❌ {error}")
                st.session_state.allocation_processing = False
                st.session_state._allocation_data = None
            else:
                # Step 3: Save allocation
                status.update(label="💾 Saving allocation...", state="running")
                
                result = allocation_service.create_allocation(
                    oc_detail_id=oc['ocd_id'],
                    allocations=saved_data.get('selected_supplies', []),
                    mode='SOFT' if saved_data.get('use_soft') else 'HARD',
                    etd=saved_data.get('allocated_etd'),
                    notes=saved_data.get('notes', ''),
                    user_id=user_id
                )
                
                if result['success']:
                    total_qty = saved_data.get('total_selected_standard', 0)
                    std_uom = saved_data.get('standard_uom', 'pcs')
                    
                    result_data['message'] = f"✅ Allocated {format_number(total_qty)} {std_uom} to {oc['oc_number']}"
                    result_data['allocation_number'] = result['allocation_number']
                    st.write(result_data['message'])
                    st.write(f"📋 Allocation Number: **{result['allocation_number']}**")
                    st.write(f"👤 Created by: {st.session_state.user.get('full_name', 'Unknown')}")
                    
                    st.balloons()
                    
                    # Step 4: Send email notification
                    status.update(label="📧 Sending email notification...", state="running")
                    
                    try:
                        actor_info = get_actor_info()
                        
                        email_success, email_msg = email_service.send_allocation_created_email(
                            oc_info=oc,
                            actor_info=actor_info,
                            allocations=saved_data.get('selected_supplies', []),
                            total_qty=total_qty,
                            mode='SOFT' if saved_data.get('use_soft') else 'HARD',
                            etd=saved_data.get('allocated_etd'),
                            allocation_number=result['allocation_number']
                        )
                        
                        if email_success:
                            result_data['email_status'] = "✅ Email notification sent"
                        else:
                            result_data['email_status'] = f"⚠️ Email not sent: {email_msg}"
                        st.write(result_data['email_status'])
                        
                    except Exception as email_error:
                        result_data['email_status'] = f"⚠️ Email error: {str(email_error)}"
                        st.write(result_data['email_status'])
                    
                    # Step 5: Mark as complete (DO NOT auto-close)
                    status.update(label="✅ Allocation complete!", state="complete", expanded=False)
                    
                    result_data['success'] = True
                    st.session_state.allocation_result = result_data
                    st.session_state.allocation_processing = False
                    st.session_state.allocation_completed = True
                    
                    # Rerun to update button states
                    time.sleep(0.5)
                    st.rerun()
                    
                else:
                    error_msg = result.get('error', 'Unknown error')
                    status.update(label="❌ Allocation failed", state="error")
                    st.error(f"❌ {error_msg}")
                    
                    st.session_state.allocation_processing = False
                    st.session_state._allocation_data = None
                    
                    if 'session' in error_msg.lower() or 'user' in error_msg.lower():
                        time.sleep(2)
                        auth.logout()
                        st.switch_page("app.py")
                        st.stop()