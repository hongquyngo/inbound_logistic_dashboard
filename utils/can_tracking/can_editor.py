# utils/can_tracking/can_editor.py

"""
CAN Editor Module - Updated with Email Notification
Handles editing of arrival dates, status, and warehouse for CAN lines
"""

import streamlit as st
import pandas as pd
from datetime import datetime, date
from typing import Optional, Dict, Any
import logging

# Import shared constants
from utils.can_tracking.constants import STATUS_DISPLAY, STATUS_VALUES, STATUS_REVERSE_MAP

logger = logging.getLogger(__name__)


def render_edit_button(can_line_id: int, arrival_note_number: str, row_data: Dict[str, Any]) -> None:
    """
    Render edit button for a CAN line
    
    Args:
        can_line_id: CAN line ID
        arrival_note_number: CAN number
        row_data: Dictionary containing row data
    """
    button_key = f"can_edit_btn_{can_line_id}"
    
    if st.button("✏️", key=button_key, help="Edit CAN", use_container_width=True):
        st.session_state.editing_can_line = can_line_id
        st.session_state.editing_arrival_number = arrival_note_number
        st.session_state.editing_can_data = row_data
        st.rerun()


def render_can_editor_modal(data_service) -> None:
    """
    Render modal dialog for editing CAN arrival date, status, and warehouse
    
    Args:
        data_service: CANDataService instance for database operations
    """
    if 'editing_can_line' not in st.session_state:
        return
    
    can_line_id = st.session_state.editing_can_line
    arrival_number = st.session_state.editing_arrival_number
    row_data = st.session_state.editing_can_data
    
    @st.dialog(f"✏️ Update CAN - {arrival_number}", width="large")
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
        
        # Get current values
        current_arrival_date = row_data.get('arrival_date')
        current_status = get_status_from_display(row_data.get('can_status', 'pending'))
        current_warehouse_id = row_data.get('warehouse_id')
        
        # Display current values
        st.markdown("**Current Values:**")
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
                value=parse_date(current_arrival_date) if current_arrival_date else date.today(),
                key="new_arrival_date_input"
            )
        
        with col2:
            new_status = st.selectbox(
                "New Status",
                options=STATUS_VALUES,
                format_func=lambda x: STATUS_DISPLAY.get(x, x),
                index=STATUS_VALUES.index(current_status) if current_status in STATUS_VALUES else 0,
                key="new_status_input"
            )
        
        # Warehouse selection
        warehouse_options = data_service.get_warehouse_options()
        warehouse_dict = {w['id']: w['name'] for w in warehouse_options}
        
        new_warehouse_id = st.selectbox(
            "New Warehouse",
            options=list(warehouse_dict.keys()),
            format_func=lambda x: warehouse_dict.get(x, 'N/A'),
            index=list(warehouse_dict.keys()).index(current_warehouse_id) if current_warehouse_id in warehouse_dict else 0,
            key="new_warehouse_input"
        )
        
        # Reason/Notes
        st.markdown("**Reason for Change:** *(Required for email notification)*")
        reason = st.text_area(
            "Reason",
            placeholder="e.g., Delayed due to customs clearance issues",
            height=80,
            label_visibility="collapsed"
        )
        
        # Email notification toggle
        send_email = st.checkbox(
            "📧 Send email notification to creator and CC: can.update@prostech.vn",
            value=True,
            help="Uncheck to update without sending email"
        )
        
        st.markdown("---")
        st.caption("⚠️ This will update adjusted arrival date. Original date remains unchanged for audit trail.")
        
        # Action buttons
        col1, col2, col3 = st.columns([2, 1, 1])
        
        with col2:
            if st.button("Cancel", use_container_width=True):
                close_editor()
                st.rerun()
        
        with col3:
            if st.button("💾 Save Changes", type="primary", use_container_width=True):
                save_can_changes(
                    data_service=data_service,
                    can_line_id=can_line_id,
                    arrival_note_number=arrival_number,
                    new_arrival_date=new_arrival_date,
                    new_status=new_status,
                    new_warehouse_id=new_warehouse_id,
                    reason=reason,
                    old_arrival_date=current_arrival_date,
                    old_status=current_status,
                    old_warehouse_id=current_warehouse_id,
                    send_email=send_email,
                    row_data=row_data
                )
    
    show_editor()


def save_can_changes(
    data_service,
    can_line_id: int,
    arrival_note_number: str,
    new_arrival_date: date,
    new_status: str,
    new_warehouse_id: int,
    reason: str,
    old_arrival_date: Any,
    old_status: str,
    old_warehouse_id: int,
    send_email: bool,
    row_data: Dict[str, Any]
) -> None:
    """
    Save CAN changes to database and send email notification
    """
    try:
        # Check if anything changed
        old_date = parse_date(old_arrival_date)
        
        date_changed = new_arrival_date != old_date
        status_changed = new_status != old_status
        warehouse_changed = new_warehouse_id != old_warehouse_id
        
        if not (date_changed or status_changed or warehouse_changed):
            st.warning("No changes detected.")
            return
        
        # Update database
        success = data_service.update_can_details(
            arrival_note_number=arrival_note_number,
            adjust_arrival_date=new_arrival_date,
            new_status=new_status,
            new_warehouse_id=new_warehouse_id,
            reason=reason
        )
        
        if success:
            changes_summary = []
            if date_changed:
                date_diff = (new_arrival_date - old_date).days if old_date else 0
                changes_summary.append(f"Date: {format_date(old_date)} → {format_date(new_arrival_date)} ({date_diff:+d} days)")
            if status_changed:
                changes_summary.append(f"Status: {STATUS_DISPLAY.get(old_status, old_status)} → {STATUS_DISPLAY.get(new_status, new_status)}")
            if warehouse_changed:
                old_wh_name = row_data.get('warehouse_name', 'N/A')
                new_wh_name = data_service.get_warehouse_name(new_warehouse_id)
                changes_summary.append(f"Warehouse: {old_wh_name} → {new_wh_name}")
            
            st.success(f"""
            ✅ CAN updated successfully - {arrival_note_number}
            
            Changes:
            """ + "\n".join(f"- {change}" for change in changes_summary))
            
            # Send email notification if requested
            if send_email:
                try:
                    from utils.can_tracking.email_service import CANEmailService
                    
                    email_service = CANEmailService()
                    
                    modifier_email = st.session_state.get('user_email', 'unknown@prostech.vn')
                    modifier_name = st.session_state.get('user_fullname', 'Unknown User')
                    
                    with st.spinner("📧 Sending email notification..."):
                        email_sent = email_service.send_can_update_notification(
                            can_line_id=can_line_id,
                            arrival_note_number=arrival_note_number,
                            product_name=row_data.get('product_name', 'N/A'),
                            vendor_name=row_data.get('vendor', 'N/A'),
                            old_arrival_date=old_date,
                            new_arrival_date=new_arrival_date,
                            old_status=old_status,
                            new_status=new_status,
                            old_warehouse_name=row_data.get('warehouse_name', 'N/A'),
                            new_warehouse_name=data_service.get_warehouse_name(new_warehouse_id),
                            modifier_email=modifier_email,
                            modifier_name=modifier_name,
                            reason=reason
                        )
                    
                    if email_sent:
                        st.success("📧 Email notification sent successfully!")
                    else:
                        st.warning("⚠️ CAN updated but email notification failed. Please check logs.")
                
                except Exception as e:
                    logger.error(f"Error sending email: {e}", exc_info=True)
                    st.warning(f"⚠️ CAN updated but email failed: {str(e)}")
            
            # Clear cache and close editor
            st.cache_data.clear()
            close_editor()
            st.rerun()
        else:
            st.error("⚠️ Failed to update CAN. Please try again or contact support.")
    
    except Exception as e:
        logger.error(f"Error saving CAN changes: {e}", exc_info=True)
        st.error(f"⚠️ Error: {str(e)}")


def close_editor() -> None:
    """Close the CAN editor modal"""
    if 'editing_can_line' in st.session_state:
        del st.session_state.editing_can_line
    if 'editing_arrival_number' in st.session_state:
        del st.session_state.editing_arrival_number
    if 'editing_can_data' in st.session_state:
        del st.session_state.editing_can_data


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
    
    if isinstance(date_value, date):
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