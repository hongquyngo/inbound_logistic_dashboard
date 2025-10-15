"""
ETD/ETA Date Editor Module - Updated with Email Notification
Handles editing of estimated dates for PO lines with email alerts
"""

import streamlit as st
import pandas as pd
from datetime import datetime, date
from typing import Optional, Dict, Any
import logging

logger = logging.getLogger(__name__)


def render_edit_button(po_line_id: int, row_data: Dict[str, Any]) -> None:
    """
    Render edit button for a PO line
    
    Args:
        po_line_id: Purchase order line ID
        row_data: Dictionary containing row data for the PO line
    """
    button_key = f"edit_btn_{po_line_id}"
    
    if st.button("✏️", key=button_key, help="Edit ETD/ETA", use_container_width=True):
        st.session_state.editing_po_line = po_line_id
        st.session_state.editing_row_data = row_data
        st.rerun()


def render_date_editor_modal(data_service) -> None:
    """
    Render modal dialog for editing ETD/ETA dates with email notification
    
    Args:
        data_service: PODataService instance for database operations
    """
    if 'editing_po_line' not in st.session_state:
        return
    
    po_line_id = st.session_state.editing_po_line
    row_data = st.session_state.editing_row_data
    
    @st.dialog(f"✏️ Update ETD/ETA - PO Line #{po_line_id}", width="large")
    def show_editor():
        # Display PO information
        st.markdown("**Purchase Order Information:**")
        
        info_col1, info_col2 = st.columns(2)
        with info_col1:
            st.text(f"PO Number: {row_data.get('po_number', 'N/A')}")
            st.text(f"Product: {row_data.get('product_name', 'N/A')}")
            st.text(f"PT Code: {row_data.get('pt_code', 'N/A')}")
        
        with info_col2:
            st.text(f"Vendor: {row_data.get('vendor_name', 'N/A')}")
            st.text(f"Buying Qty: {row_data.get('buying_quantity', 0)}")
            st.text(f"Status: {row_data.get('status', 'N/A')}")
        
        st.markdown("---")
        
        # Display current dates
        current_etd = row_data.get('etd')
        current_eta = row_data.get('eta')
        
        st.markdown("**Current Dates:**")
        date_info = f"""
        - **Current ETD:** {format_date(current_etd)}
        - **Current ETA:** {format_date(current_eta)}
        """
        st.info(date_info)
        
        st.markdown("**New Dates:**")
        
        # Date inputs
        col1, col2 = st.columns(2)
        
        with col1:
            new_etd = st.date_input(
                "New ETD",
                value=parse_date(current_etd) if current_etd else date.today(),
                key="new_etd_input"
            )
        
        with col2:
            new_eta = st.date_input(
                "New ETA",
                value=parse_date(current_eta) if current_eta else date.today(),
                key="new_eta_input"
            )
        
        # Validation
        if new_etd and new_eta and new_etd > new_eta:
            st.warning("⚠️ Warning: ETD is later than ETA")
        
        # Reason/Notes
        st.markdown("**Reason for Change:** *(Required for email notification)*")
        reason = st.text_area(
            "Reason",
            placeholder="e.g., Vendor delayed shipment due to customs issues",
            height=80,
            label_visibility="collapsed"
        )
        
        # Email notification toggle
        send_email = st.checkbox(
            "📧 Send email notification to creator and CC: po.update@prostech.vn",
            value=True,
            help="Uncheck to update without sending email"
        )
        
        st.markdown("---")
        st.caption("⚠️ This will update adjusted dates only. Original dates remain unchanged for audit trail.")
        
        # Action buttons
        col1, col2, col3 = st.columns([2, 1, 1])
        
        with col2:
            if st.button("Cancel", use_container_width=True):
                close_editor()
                st.rerun()
        
        with col3:
            if st.button("💾 Save Changes", type="primary", use_container_width=True):
                save_date_changes(
                    data_service=data_service,
                    po_line_id=po_line_id,
                    new_etd=new_etd,
                    new_eta=new_eta,
                    reason=reason,
                    old_etd=current_etd,
                    old_eta=current_eta,
                    send_email=send_email,
                    row_data=row_data
                )
    
    show_editor()


def save_date_changes(
    data_service,
    po_line_id: int,
    new_etd: date,
    new_eta: date,
    reason: str,
    old_etd: Any,
    old_eta: Any,
    send_email: bool,
    row_data: Dict[str, Any]
) -> None:
    """
    Save ETD/ETA changes to database and send email notification
    
    Args:
        data_service: PODataService instance
        po_line_id: PO line ID to update
        new_etd: New ETD date
        new_eta: New ETA date
        reason: Reason for change
        old_etd: Old ETD for comparison
        old_eta: Old ETA for comparison
        send_email: Whether to send email notification
        row_data: Complete row data for email
    """
    try:
        # Check if dates actually changed
        old_etd_date = parse_date(old_etd)
        old_eta_date = parse_date(old_eta)
        
        if new_etd == old_etd_date and new_eta == old_eta_date:
            st.warning("No changes detected. Dates are the same.")
            return
        
        # Call data service to update
        success = data_service.update_po_line_dates(
            po_line_id=po_line_id,
            adjust_etd=new_etd,
            adjust_eta=new_eta,
            reason=reason
        )
        
        if success:
            # Calculate day differences
            etd_diff = (new_etd - old_etd_date).days if old_etd_date else 0
            eta_diff = (new_eta - old_eta_date).days if old_eta_date else 0
            
            # Show success message
            st.success(f"""
            ✅ ETD/ETA updated successfully for PO Line #{po_line_id}
            - ETD: {format_date(old_etd_date)} → {format_date(new_etd)} ({etd_diff:+d} days)
            - ETA: {format_date(old_eta_date)} → {format_date(new_eta)} ({eta_diff:+d} days)
            """)
            
            # Send email notification if requested
            if send_email:
                try:
                    from utils.po_tracking.email_service import POEmailService
                    
                    email_service = POEmailService()
                    
                    # Get modifier info from session state
                    modifier_email = st.session_state.get('user_email', 'unknown@prostech.vn')
                    modifier_name = st.session_state.get('user_fullname', 'Unknown User')
                    
                    with st.spinner("📧 Sending email notification..."):
                        email_sent = email_service.send_etd_eta_update_notification(
                            po_line_id=po_line_id,
                            po_number=row_data.get('po_number', 'N/A'),
                            product_name=row_data.get('product_name', 'N/A'),
                            vendor_name=row_data.get('vendor_name', 'N/A'),
                            old_etd=old_etd_date,
                            new_etd=new_etd,
                            old_eta=old_eta_date,
                            new_eta=new_eta,
                            modifier_email=modifier_email,
                            modifier_name=modifier_name,
                            reason=reason
                        )
                    
                    if email_sent:
                        st.success("📧 Email notification sent successfully!")
                    else:
                        st.warning("⚠️ Date updated but email notification failed. Please check logs.")
                
                except Exception as e:
                    logger.error(f"Error sending email: {e}", exc_info=True)
                    st.warning(f"⚠️ Date updated but email failed: {str(e)}")
            
            # Clear cache and close editor
            st.cache_data.clear()
            close_editor()
            
            # Rerun to refresh data
            st.rerun()
        else:
            st.error("⚠️ Failed to update dates. Please try again or contact support.")
    
    except Exception as e:
        logger.error(f"Error saving date changes: {e}", exc_info=True)
        st.error(f"⚠️ Error: {str(e)}")


def close_editor() -> None:
    """Close the date editor modal"""
    if 'editing_po_line' in st.session_state:
        del st.session_state.editing_po_line
    if 'editing_row_data' in st.session_state:
        del st.session_state.editing_row_data


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