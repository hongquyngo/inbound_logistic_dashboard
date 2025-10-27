"""
ETD/ETA Date Editor Module - Enhanced with Bulk Update Support
Handles bulk editing of estimated dates for multiple PO lines with email alerts
"""

import streamlit as st
import pandas as pd
from datetime import datetime, date
from typing import Optional, Dict, Any, List
import logging

logger = logging.getLogger(__name__)


def render_bulk_date_editor_modal(data_service, full_df: pd.DataFrame) -> None:
    """
    Render modal dialog for bulk editing ETD/ETA dates
    
    Args:
        data_service: PODataService instance for database operations
        full_df: Full dataframe with all PO data
    """
    if 'show_bulk_editor' not in st.session_state or not st.session_state.show_bulk_editor:
        return
    
    if 'selected_po_lines' not in st.session_state or not st.session_state.selected_po_lines:
        st.warning("No lines selected for editing")
        return
    
    selected_line_ids = list(st.session_state.selected_po_lines)
    selected_count = len(selected_line_ids)
    
    # Get selected lines data
    selected_lines = full_df[full_df['po_line_id'].isin(selected_line_ids)].copy()
    
    if selected_lines.empty:
        st.warning("Selected lines not found in current data")
        return
    
    @st.dialog(f"✏️ Bulk Update ETD/ETA - {selected_count} Lines", width="large")
    def show_bulk_editor():
        st.markdown(f"**Updating {selected_count} PO line{'s' if selected_count > 1 else ''}**")
        
        # Show summary of affected POs
        affected_pos = selected_lines['po_number'].unique()
        if len(affected_pos) <= 5:
            st.info(f"**Affected POs:** {', '.join(affected_pos)}")
        else:
            st.info(f"**Affected POs:** {len(affected_pos)} different purchase orders")
        
        # Show preview of selected lines (limit to 10)
        st.markdown("**Selected Lines Preview:**")
        preview_df = selected_lines[['po_number', 'product_name', 'pt_code', 'etd', 'eta']].head(10)
        st.dataframe(preview_df, use_container_width=True, hide_index=True)
        
        if selected_count > 10:
            st.caption(f"... and {selected_count - 10} more lines")
        
        st.markdown("---")
        
        # Check for date variations
        unique_etds = selected_lines['etd'].dropna().unique()
        unique_etas = selected_lines['eta'].dropna().unique()
        
        if len(unique_etds) > 1 or len(unique_etas) > 1:
            st.warning(
                f"⚠️ **Note:** Selected lines have different current dates\n\n"
                f"- {len(unique_etds)} different ETD values\n"
                f"- {len(unique_etas)} different ETA values\n\n"
                f"All lines will be updated to the same new dates."
            )
        
        # Date inputs
        st.markdown("**New Dates (will apply to all selected lines):**")
        
        col1, col2 = st.columns(2)
        
        # Get most common or earliest date as default
        default_etd = selected_lines['etd'].min() if not selected_lines['etd'].isna().all() else date.today()
        default_eta = selected_lines['eta'].min() if not selected_lines['eta'].isna().all() else date.today()
        
        with col1:
            new_etd = st.date_input(
                "New ETD",
                value=parse_date(default_etd) if default_etd else date.today(),
                key="bulk_new_etd_input"
            )
        
        with col2:
            new_eta = st.date_input(
                "New ETA",
                value=parse_date(default_eta) if default_eta else date.today(),
                key="bulk_new_eta_input"
            )
        
        # Validation
        if new_etd and new_eta and new_etd > new_eta:
            st.warning("⚠️ Warning: ETD is later than ETA")
        
        # Reason/Notes
        st.markdown("**Reason for Change:** *(Required for email notification)*")
        reason = st.text_area(
            "Reason",
            placeholder="e.g., Vendor confirmed shipment delay due to customs clearance",
            height=100,
            label_visibility="collapsed",
            key="bulk_reason_input"
        )
        
        # Email notification toggle
        send_email = st.checkbox(
            "📧 Send consolidated email notification",
            value=True,
            help="One email will be sent with all changes"
        )
        
        st.markdown("---")
        st.caption("⚠️ This will update adjusted dates only. Original dates remain unchanged for audit trail.")
        
        # Action buttons
        col1, col2, col3 = st.columns([2, 1, 1])
        
        with col2:
            if st.button("Cancel", use_container_width=True):
                close_bulk_editor()
                st.rerun()
        
        with col3:
            if st.button(
                f"💾 Update {selected_count} Line{'s' if selected_count > 1 else ''}",
                type="primary",
                use_container_width=True
            ):
                if not reason or reason.strip() == "":
                    st.error("⚠️ Please provide a reason for the date change")
                else:
                    save_bulk_date_changes(
                        data_service=data_service,
                        selected_lines=selected_lines,
                        new_etd=new_etd,
                        new_eta=new_eta,
                        reason=reason.strip(),
                        send_email=send_email
                    )
    
    show_bulk_editor()


def save_bulk_date_changes(
    data_service,
    selected_lines: pd.DataFrame,
    new_etd: date,
    new_eta: date,
    reason: str,
    send_email: bool
) -> None:
    """
    Save bulk ETD/ETA changes to database and send consolidated email
    
    Args:
        data_service: PODataService instance
        selected_lines: DataFrame of selected lines
        new_etd: New ETD date
        new_eta: New ETA date
        reason: Reason for change
        send_email: Whether to send email notification
    """
    try:
        line_ids = selected_lines['po_line_id'].tolist()
        
        with st.spinner(f"Updating {len(line_ids)} lines..."):
            # Progress bar
            progress_bar = st.progress(0)
            
            # Call bulk update method
            success = data_service.bulk_update_po_line_dates(
                po_line_ids=line_ids,
                adjust_etd=new_etd,
                adjust_eta=new_eta,
                reason=reason
            )
            
            progress_bar.progress(100)
        
        if success:
            st.success(f"✅ Successfully updated {len(line_ids)} PO lines!")
            
            # Send consolidated email if requested
            if send_email:
                try:
                    from utils.po_tracking.email_service import POEmailService
                    
                    email_service = POEmailService()
                    
                    # Get modifier info
                    modifier_email = st.session_state.get('user_email', 'unknown@prostech.vn')
                    modifier_name = st.session_state.get('user_fullname', 'Unknown User')
                    
                    with st.spinner("📧 Sending email notification..."):
                        # Prepare line details for email
                        line_details = []
                        for _, row in selected_lines.iterrows():
                            line_details.append({
                                'po_line_id': row['po_line_id'],
                                'po_number': row['po_number'],
                                'product_name': row['product_name'],
                                'pt_code': row.get('pt_code', 'N/A'),
                                'vendor_name': row['vendor_name'],
                                'old_etd': parse_date(row['etd']),
                                'old_eta': parse_date(row['eta'])
                            })
                        
                        email_sent = email_service.send_bulk_etd_eta_update_notification(
                            line_details=line_details,
                            new_etd=new_etd,
                            new_eta=new_eta,
                            modifier_email=modifier_email,
                            modifier_name=modifier_name,
                            reason=reason
                        )
                    
                    if email_sent:
                        st.success("📧 Email notification sent successfully!")
                    else:
                        st.warning("⚠️ Dates updated but email notification failed. Please check logs.")
                
                except Exception as e:
                    logger.error(f"Error sending bulk email: {e}", exc_info=True)
                    st.warning(f"⚠️ Dates updated but email failed: {str(e)}")
            
            # Clear cache and selections
            st.cache_data.clear()
            st.session_state.selected_po_lines = set()
            st.session_state.select_all_checked = False
            close_bulk_editor()
            
            # Rerun to refresh data
            st.rerun()
        else:
            st.error("⚠️ Failed to update dates. Please try again or contact support.")
    
    except Exception as e:
        logger.error(f"Error saving bulk date changes: {e}", exc_info=True)
        st.error(f"⚠️ Error: {str(e)}")


def close_bulk_editor() -> None:
    """Close the bulk date editor modal"""
    if 'show_bulk_editor' in st.session_state:
        st.session_state.show_bulk_editor = False


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