# utils/can_tracking/can_editor.py

"""
CAN Editor Module - Batch Update with Staged Changes
Handles editing of arrival dates, status, and warehouse for CAN lines
Uses staged changes pattern for better UX and batch processing
"""

import streamlit as st
import pandas as pd
from datetime import datetime, date
from typing import Optional, Dict, Any, List, Tuple
import logging
import time

from utils.can_tracking.constants import STATUS_DISPLAY, STATUS_VALUES, STATUS_REVERSE_MAP
from utils.can_tracking.pending_changes import get_pending_manager, CANChange

logger = logging.getLogger(__name__)


# ============================================================================
# TIMING HELPERS
# ============================================================================

def _log_timing(operation: str, start_time: float, extra_info: str = "") -> None:
    """Log timing information for debugging"""
    elapsed = time.time() - start_time
    msg = f"⏱️ {operation}: {elapsed:.3f}s"
    if extra_info:
        msg += f" ({extra_info})"
    logger.info(msg)
    
    if '_timing_logs' not in st.session_state:
        st.session_state._timing_logs = []
    st.session_state._timing_logs.append({
        'operation': operation,
        'elapsed': elapsed,
        'extra': extra_info,
        'timestamp': datetime.now().strftime('%H:%M:%S.%f')[:-3]
    })


# ============================================================================
# EDIT BUTTON & DIALOG
# ============================================================================

def render_edit_button(can_line_id: int, arrival_note_number: str, row_data: Dict[str, Any]) -> None:
    """
    Render edit button for a CAN line with pending indicator
    """
    pending_manager = get_pending_manager()
    has_pending = pending_manager.has_change_for(arrival_note_number)
    
    button_key = f"can_edit_btn_{can_line_id}"
    button_label = "✏️🟡" if has_pending else "✏️"
    button_help = "Edit CAN (has pending changes)" if has_pending else "Edit CAN"
    
    if st.button(button_label, key=button_key, help=button_help, use_container_width=True):
        st.session_state.editing_can_line = can_line_id
        st.session_state.editing_arrival_number = arrival_note_number
        st.session_state.editing_can_data = row_data
        st.rerun(scope="fragment")


def render_can_editor_modal(data_service) -> None:
    """
    Render modal dialog for editing CAN - stages changes instead of saving
    """
    if 'editing_can_line' not in st.session_state:
        return
    
    can_line_id = st.session_state.editing_can_line
    arrival_number = st.session_state.editing_arrival_number
    row_data = st.session_state.editing_can_data
    
    pending_manager = get_pending_manager()
    existing_change = pending_manager.get_change(arrival_number)
    
    @st.dialog(f"✏️ Edit CAN - {arrival_number}", width="large")
    def show_editor():
        # Display CAN information
        st.markdown("**Container Arrival Note Information:**")
        
        info_col1, info_col2 = st.columns(2)
        with info_col1:
            st.text(f"CAN Number: {arrival_number}")
            st.text(f"Product: {row_data.get('product_name', 'N/A')}")
            st.text(f"PT Code: {row_data.get('pt_code', 'N/A')}")
        
        with info_col2:
            st.text(f"Vendor: {row_data.get('vendor', 'N/A')}")
            st.text(f"Warehouse: {row_data.get('warehouse_name', 'N/A')}")
            st.text(f"Pending Qty: {row_data.get('pending_quantity', 0)}")
        
        st.markdown("---")
        
        # Get current/original values
        current_arrival_date = row_data.get('arrival_date')
        current_status = get_status_from_display(row_data.get('can_status', 'pending'))
        current_warehouse_id = row_data.get('warehouse_id')
        
        # If there's an existing staged change, show that as default
        if existing_change:
            st.info("🟡 This CAN has pending changes. Editing will update the staged changes.")
            default_date = parse_date(existing_change.new_arrival_date)
            default_status = existing_change.new_status
            default_warehouse_id = existing_change.new_warehouse_id
            default_reason = existing_change.reason
        else:
            default_date = parse_date(current_arrival_date) if current_arrival_date else date.today()
            default_status = current_status
            default_warehouse_id = current_warehouse_id
            default_reason = ""
        
        # Display current values
        st.markdown("**Current Values (in database):**")
        current_info = f"""
        - **Arrival Date:** {format_date(current_arrival_date)}
        - **Status:** {STATUS_DISPLAY.get(current_status, current_status)}
        - **Warehouse:** {row_data.get('warehouse_name', 'N/A')}
        """
        st.info(current_info)
        
        st.markdown("**New Values:**")
        
        # Input fields
        col1, col2 = st.columns(2)
        
        with col1:
            new_arrival_date = st.date_input(
                "New Arrival Date",
                value=default_date if default_date else date.today(),
                key="new_arrival_date_input"
            )
        
        with col2:
            status_index = STATUS_VALUES.index(default_status) if default_status in STATUS_VALUES else 0
            new_status = st.selectbox(
                "New Status",
                options=STATUS_VALUES,
                format_func=lambda x: STATUS_DISPLAY.get(x, x),
                index=status_index,
                key="new_status_input"
            )
        
        # Warehouse selection
        warehouse_options = data_service.get_warehouse_options()
        warehouse_dict = {w['id']: w['name'] for w in warehouse_options}
        warehouse_ids = list(warehouse_dict.keys())
        
        default_wh_index = warehouse_ids.index(default_warehouse_id) if default_warehouse_id in warehouse_ids else 0
        new_warehouse_id = st.selectbox(
            "New Warehouse",
            options=warehouse_ids,
            format_func=lambda x: warehouse_dict.get(x, 'N/A'),
            index=default_wh_index,
            key="new_warehouse_input"
        )
        
        # Reason/Notes
        st.markdown("**Reason for Change:**")
        reason = st.text_area(
            "Reason",
            value=default_reason,
            placeholder="e.g., Delayed due to customs clearance issues",
            height=80,
            label_visibility="collapsed"
        )
        
        st.markdown("---")
        st.caption("⚠️ Changes will be staged locally. Click **Apply** in the action bar to commit all changes to database.")
        
        # Action buttons
        col1, col2, col3 = st.columns([2, 1, 1])
        
        with col2:
            if existing_change:
                if st.button("🗑️ Remove", use_container_width=True, help="Remove staged changes"):
                    pending_manager.remove_change(arrival_number)
                    close_editor()
                    st.rerun()
        
        with col3:
            if st.button("✓ Stage Changes", type="primary", use_container_width=True):
                stage_can_changes(
                    data_service=data_service,
                    can_line_id=can_line_id,
                    arrival_note_number=arrival_number,
                    new_arrival_date=new_arrival_date,
                    new_status=new_status,
                    new_warehouse_id=new_warehouse_id,
                    new_warehouse_name=warehouse_dict.get(new_warehouse_id, 'N/A'),
                    reason=reason,
                    old_arrival_date=current_arrival_date,
                    old_status=current_status,
                    old_warehouse_id=current_warehouse_id,
                    old_warehouse_name=row_data.get('warehouse_name', 'N/A'),
                    row_data=row_data
                )
    
    show_editor()


def stage_can_changes(
    data_service,
    can_line_id: int,
    arrival_note_number: str,
    new_arrival_date: date,
    new_status: str,
    new_warehouse_id: int,
    new_warehouse_name: str,
    reason: str,
    old_arrival_date: Any,
    old_status: str,
    old_warehouse_id: int,
    old_warehouse_name: str,
    row_data: Dict[str, Any]
) -> None:
    """
    Stage CAN changes for later batch processing
    """
    try:
        old_date = parse_date(old_arrival_date)
        
        date_changed = new_arrival_date != old_date
        status_changed = new_status != old_status
        warehouse_changed = new_warehouse_id != old_warehouse_id
        
        if not (date_changed or status_changed or warehouse_changed):
            st.warning("No changes detected.")
            return
        
        pending_manager = get_pending_manager()
        
        # Stage the change
        pending_manager.stage_change(
            can_line_id=can_line_id,
            arrival_note_number=arrival_note_number,
            original_data={
                'arrival_date': old_date,
                'status': old_status,
                'warehouse_id': old_warehouse_id,
                'warehouse_name': old_warehouse_name
            },
            new_data={
                'arrival_date': new_arrival_date,
                'status': new_status,
                'warehouse_id': new_warehouse_id,
                'warehouse_name': new_warehouse_name
            },
            reason=reason,
            row_data=row_data
        )
        
        # Update local DataFrame for immediate UI feedback
        _update_local_dataframe(
            arrival_note_number=arrival_note_number,
            new_arrival_date=new_arrival_date,
            new_status=new_status,
            new_warehouse_id=new_warehouse_id,
            new_warehouse_name=new_warehouse_name
        )
        
        st.success(f"✓ Changes staged for {arrival_note_number}")
        
        close_editor()
        st.rerun()
        
    except Exception as e:
        logger.error(f"Error staging CAN changes: {e}", exc_info=True)
        st.error(f"⚠️ Error: {str(e)}")


# ============================================================================
# FLOATING ACTION BAR
# ============================================================================

def render_floating_action_bar() -> None:
    """
    Render floating action bar when there are pending changes
    """
    pending_manager = get_pending_manager()
    
    if not pending_manager.has_pending_changes():
        return
    
    count = pending_manager.get_change_count()
    
    # Create a sticky container at the bottom
    st.markdown("""
        <style>
        .pending-bar {
            position: fixed;
            bottom: 0;
            left: 0;
            right: 0;
            background: linear-gradient(90deg, #1e3a5f 0%, #2c5282 100%);
            padding: 12px 24px;
            z-index: 1000;
            display: flex;
            justify-content: space-between;
            align-items: center;
            box-shadow: 0 -4px 12px rgba(0,0,0,0.15);
        }
        .pending-bar-text {
            color: white;
            font-size: 16px;
            font-weight: 500;
        }
        .pending-indicator {
            background: #f6e05e;
            color: #744210;
            padding: 4px 12px;
            border-radius: 20px;
            font-weight: 600;
            margin-right: 12px;
        }
        </style>
    """, unsafe_allow_html=True)
    
    # Use columns for the action bar
    st.markdown("---")
    bar_col1, bar_col2, bar_col3 = st.columns([3, 1, 1])
    
    with bar_col1:
        st.markdown(f"### 🟡 {count} pending change{'s' if count > 1 else ''}")
    
    with bar_col2:
        if st.button("🗑️ Discard All", use_container_width=True, key="discard_all_btn"):
            st.session_state._show_discard_confirm = True
            st.rerun()
    
    with bar_col3:
        if st.button("▶ Apply Changes", type="primary", use_container_width=True, key="apply_all_btn"):
            st.session_state._show_apply_dialog = True
            st.rerun()
    
    # Discard confirmation
    if st.session_state.get('_show_discard_confirm'):
        _render_discard_confirm_dialog()
    
    # Apply dialog
    if st.session_state.get('_show_apply_dialog'):
        _render_apply_dialog()


def _render_discard_confirm_dialog() -> None:
    """Render discard confirmation dialog"""
    
    @st.dialog("🗑️ Discard All Changes?", width="small")
    def confirm_discard():
        pending_manager = get_pending_manager()
        count = pending_manager.get_change_count()
        
        st.warning(f"Are you sure you want to discard all {count} pending changes? This cannot be undone.")
        
        col1, col2 = st.columns(2)
        with col1:
            if st.button("Cancel", use_container_width=True):
                st.session_state._show_discard_confirm = False
                st.rerun()
        
        with col2:
            if st.button("🗑️ Discard", type="primary", use_container_width=True):
                pending_manager.clear_all_changes()
                st.session_state._show_discard_confirm = False
                # Clear local DataFrame changes
                if '_can_df_for_fragment' in st.session_state:
                    del st.session_state['_can_df_for_fragment']
                st.cache_data.clear()
                st.rerun()
    
    confirm_discard()


def _render_apply_dialog() -> None:
    """Render apply/review dialog"""
    
    @st.dialog("📋 Review & Apply Changes", width="large")
    def review_and_apply():
        pending_manager = get_pending_manager()
        changes = pending_manager.get_all_changes()
        
        if not changes:
            st.info("No pending changes to apply.")
            if st.button("Close"):
                st.session_state._show_apply_dialog = False
                st.rerun()
            return
        
        st.markdown(f"### {len(changes)} change{'s' if len(changes) > 1 else ''} to apply")
        
        # List all changes
        for i, (an, change) in enumerate(changes.items(), 1):
            with st.container():
                st.markdown(f"**{i}. {an}**")
                st.caption(f"Product: {change.product_name}")
                
                changes_list = change.get_changes_summary()
                for c in changes_list:
                    st.markdown(f"  • {c}")
                
                if change.reason:
                    st.caption(f"Reason: {change.reason}")
                
                col1, col2 = st.columns([4, 1])
                with col2:
                    if st.button("Remove", key=f"remove_{an}", use_container_width=True):
                        pending_manager.remove_change(an)
                        st.rerun()
                
                st.markdown("---")
        
        # Email info
        st.markdown("**📧 Email Notifications:**")
        st.caption("Each CAN creator will receive an email notification about their CAN updates.")
        st.caption("CC: can.update@prostech.vn")
        
        # Progress area (will be updated during processing)
        progress_placeholder = st.empty()
        status_placeholder = st.empty()
        
        # Action buttons
        col1, col2 = st.columns(2)
        
        with col1:
            if st.button("Cancel", use_container_width=True, key="cancel_apply"):
                st.session_state._show_apply_dialog = False
                st.rerun()
        
        with col2:
            if st.button("✓ Confirm & Apply", type="primary", use_container_width=True, key="confirm_apply"):
                # Process changes
                _process_batch_changes(
                    pending_manager=pending_manager,
                    progress_placeholder=progress_placeholder,
                    status_placeholder=status_placeholder
                )
    
    review_and_apply()


# ============================================================================
# BATCH PROCESSING
# ============================================================================

def _process_batch_changes(
    pending_manager,
    progress_placeholder,
    status_placeholder
) -> None:
    """Process all pending changes in batch"""
    from utils.can_tracking.data_service import CANDataService
    from utils.can_tracking.email_service import CANEmailService
    
    total_start = time.time()
    st.session_state._timing_logs = []
    
    data_service = CANDataService()
    email_service = CANEmailService()
    
    changes = pending_manager.get_all_changes()
    total = len(changes)
    
    results = {
        'success': [],
        'failed': []
    }
    
    # Process each change
    for i, (an, change) in enumerate(changes.items()):
        progress = (i + 1) / total
        progress_placeholder.progress(progress, text=f"Processing {i+1}/{total}...")
        
        t0 = time.time()
        
        try:
            # Update database
            success = data_service.update_can_details(
                arrival_note_number=an,
                adjust_arrival_date=datetime.strptime(change.new_arrival_date, '%Y-%m-%d').date(),
                new_status=change.new_status,
                new_warehouse_id=change.new_warehouse_id,
                reason=change.reason
            )
            
            if success:
                results['success'].append({
                    'an': an,
                    'change': change
                })
                status_placeholder.success(f"✓ {an} updated")
                _log_timing(f"DB Update {an}", t0)
            else:
                results['failed'].append({
                    'an': an,
                    'change': change,
                    'error': 'Database update returned false'
                })
                status_placeholder.error(f"✗ {an} failed")
                
        except Exception as e:
            logger.error(f"Error updating {an}: {e}", exc_info=True)
            results['failed'].append({
                'an': an,
                'change': change,
                'error': str(e)
            })
            status_placeholder.error(f"✗ {an} failed: {str(e)}")
    
    _log_timing("All DB Updates", total_start, f"{len(results['success'])}/{total} successful")
    
    # Send emails grouped by creator
    if results['success']:
        t_email = time.time()
        progress_placeholder.progress(1.0, text="Sending email notifications...")
        
        _send_batch_emails(
            data_service=data_service,
            email_service=email_service,
            successful_changes=results['success'],
            status_placeholder=status_placeholder
        )
        
        _log_timing("All Emails", t_email)
    
    # Clear successful changes from pending
    for item in results['success']:
        pending_manager.remove_change(item['an'])
    
    _log_timing("TOTAL BATCH", total_start)
    
    # Show final summary
    progress_placeholder.empty()
    
    if results['failed']:
        status_placeholder.warning(f"""
        ⚠️ Completed with errors:
        - ✓ {len(results['success'])} successful
        - ✗ {len(results['failed'])} failed
        
        Failed items remain in pending changes.
        """)
    else:
        status_placeholder.success(f"✓ All {len(results['success'])} changes applied successfully!")
    
    # Show timing summary
    _display_timing_summary()
    
    # Add close button
    if st.button("Close", key="close_after_apply"):
        st.session_state._show_apply_dialog = False
        st.cache_data.clear()
        st.rerun()


def _send_batch_emails(
    data_service,
    email_service,
    successful_changes: List[Dict],
    status_placeholder
) -> None:
    """Send emails to creators - one email per creator with their CANs"""
    
    # Group by creator
    by_creator: Dict[str, List] = {}
    
    for item in successful_changes:
        an = item['an']
        change = item['change']
        
        creator_email = email_service.get_creator_email(an)
        if creator_email:
            if creator_email not in by_creator:
                by_creator[creator_email] = []
            by_creator[creator_email].append(item)
    
    # Send email to each creator
    modifier_email = st.session_state.get('user_email', 'unknown@prostech.vn')
    modifier_name = st.session_state.get('user_fullname', 'Unknown User')
    
    for creator_email, items in by_creator.items():
        try:
            t0 = time.time()
            
            # Build consolidated email for this creator
            success = email_service.send_batch_update_notification(
                creator_email=creator_email,
                changes=[item['change'] for item in items],
                modifier_email=modifier_email,
                modifier_name=modifier_name
            )
            
            if success:
                status_placeholder.success(f"📧 Email sent to {creator_email}")
            else:
                status_placeholder.warning(f"⚠️ Email to {creator_email} failed")
            
            _log_timing(f"Email to {creator_email}", t0, f"{len(items)} CANs")
            
        except Exception as e:
            logger.error(f"Error sending email to {creator_email}: {e}")
            status_placeholder.warning(f"⚠️ Email to {creator_email} failed: {str(e)}")


def _display_timing_summary() -> None:
    """Display timing summary in an expander"""
    timing_logs = st.session_state.get('_timing_logs', [])
    if timing_logs:
        with st.expander("⏱️ Performance Timing", expanded=False):
            for log in timing_logs:
                color = "🟢" if log['elapsed'] < 0.5 else "🟡" if log['elapsed'] < 1.0 else "🔴"
                extra = f" - {log['extra']}" if log['extra'] else ""
                st.text(f"{color} {log['operation']}: {log['elapsed']:.3f}s{extra}")


# ============================================================================
# LOCAL DATAFRAME UPDATE
# ============================================================================

def _update_local_dataframe(
    arrival_note_number: str,
    new_arrival_date: date,
    new_status: str,
    new_warehouse_id: int,
    new_warehouse_name: Optional[str] = None
) -> None:
    """
    Update the local DataFrame in session state for immediate UI feedback
    """
    try:
        df = st.session_state.get('_can_df_for_fragment')
        if df is None:
            return
        
        mask = df['arrival_note_number'] == arrival_note_number
        
        if mask.any():
            df.loc[mask, 'arrival_date'] = new_arrival_date
            df.loc[mask, 'can_status'] = new_status
            df.loc[mask, 'warehouse_id'] = new_warehouse_id
            if new_warehouse_name:
                df.loc[mask, 'warehouse_name'] = new_warehouse_name
            
            today = date.today()
            df.loc[mask, 'days_since_arrival'] = (today - new_arrival_date).days
            
            st.session_state['_can_df_for_fragment'] = df
            
    except Exception as e:
        logger.warning(f"Could not update local DataFrame: {e}")


# ============================================================================
# UTILITY FUNCTIONS
# ============================================================================

def close_editor() -> None:
    """Close the CAN editor modal"""
    for key in ['editing_can_line', 'editing_arrival_number', 'editing_can_data']:
        if key in st.session_state:
            del st.session_state[key]


def format_date(date_value: Any) -> str:
    """Format date for display"""
    if date_value is None or pd.isna(date_value):
        return "Not set"
    
    if isinstance(date_value, str):
        try:
            date_value = datetime.strptime(date_value, "%Y-%m-%d").date()
        except:
            return str(date_value)
    
    if isinstance(date_value, (datetime, pd.Timestamp)):
        date_value = date_value.date()
    
    if isinstance(date_value, date):
        return date_value.strftime("%b %d, %Y")
    
    return str(date_value)


def parse_date(date_value: Any) -> Optional[date]:
    """Parse various date formats to date object"""
    if date_value is None or pd.isna(date_value):
        return None
    
    if isinstance(date_value, date) and not isinstance(date_value, datetime):
        return date_value
    
    if isinstance(date_value, (datetime, pd.Timestamp)):
        return date_value.date()
    
    if isinstance(date_value, str):
        try:
            return datetime.strptime(date_value, "%Y-%m-%d").date()
        except:
            try:
                return pd.to_datetime(date_value).date()
            except:
                return None
    
    return None


def is_date_overdue(date_value: Any) -> bool:
    """Check if a date is overdue (past today)"""
    parsed_date = parse_date(date_value)
    if parsed_date is None:
        return False
    return parsed_date < date.today()


def get_status_from_display(display_status: str) -> str:
    """Convert display status back to database status"""
    return STATUS_REVERSE_MAP.get(display_status, 'REQUEST_STATUS')


# ============================================================================
# PAGE LEAVE WARNING
# ============================================================================

def render_leave_warning_script() -> None:
    """Render JavaScript for warning user when leaving page with pending changes"""
    pending_manager = get_pending_manager()
    
    if pending_manager.has_pending_changes():
        st.markdown("""
            <script>
            window.onbeforeunload = function() {
                return "You have pending changes that haven't been applied. Are you sure you want to leave?";
            };
            </script>
        """, unsafe_allow_html=True)
    else:
        # Clear the warning if no pending changes
        st.markdown("""
            <script>
            window.onbeforeunload = null;
            </script>
        """, unsafe_allow_html=True)