# pages/3_📧_Email_Notifications.py

import streamlit as st
import pandas as pd
from datetime import datetime
import logging

# Import utilities
from utils.auth import AuthManager
from utils.email_notification.data_queries import EmailNotificationQueries
from utils.email_notification.email_coordinator import EmailCoordinator
from utils.email_notification import ui_helpers

# Setup logging
logger = logging.getLogger(__name__)

# ========================
# PAGE CONFIGURATION
# ========================

st.set_page_config(
    page_title="Email Notifications",
    page_icon="📧",
    layout="wide"
)

# ========================
# AUTHENTICATION
# ========================

auth_manager = AuthManager()
if not auth_manager.check_session():
    st.warning("⚠️ Please login to access this page")
    st.stop()

# Check user role - only allow admin, manager, procurement_manager
user_role = st.session_state.get('user_role', '')
if user_role not in ['admin', 'manager', 'procurement_manager']:
    st.error("❌ You don't have permission to access this page")
    st.stop()

# ========================
# INITIALIZE SERVICES
# ========================

queries = EmailNotificationQueries()
coordinator = EmailCoordinator()

# ========================
# PAGE HEADER
# ========================

st.title("📧 Email Notifications - Inbound Logistics")
st.markdown("Send purchase order schedules and pending stock-in alerts to relevant teams")
st.markdown("---")

# ========================
# SESSION STATE
# ========================

ui_helpers.initialize_session_state()

# ========================
# MAIN UI LAYOUT
# ========================

col1, col2 = st.columns([2, 1])

# LEFT COLUMN: Email Settings
with col1:
    settings = ui_helpers.render_email_settings()
    notification_type = settings['notification_type']
    weeks_ahead = settings['weeks_ahead']
    date_type = settings['date_type'].lower()

# RIGHT COLUMN: Quick Info
with col2:
    st.subheader("ℹ️ Quick Info")
    st.info(f"""
    **Current Settings:**
    - Type: {notification_type}
    - Period: {weeks_ahead} week(s)
    - Date: {date_type.upper()}
    """)

st.markdown("---")

# ========================
# RECIPIENT SELECTION
# ========================

st.subheader("📋 Recipient Selection")

# Determine recipient type
recipient_type = ui_helpers.render_recipient_type_selector(notification_type)
st.session_state.recipient_type = recipient_type

recipients = []
selected_vendor_names = []

# Load and display recipients based on type
if recipient_type == 'creators':
    st.markdown("### 📝 Select PO Creators")
    
    # Load appropriate creators based on notification type
    if notification_type == '📅 PO Schedule':
        creators_df = queries.get_creators_list(weeks_ahead, date_type)
    elif notification_type == '🚨 Critical Alerts':
        creators_df = queries.get_creators_overdue(date_type)
    elif notification_type == '📦 Pending Stock-in':
        creators_df = queries.get_creators_with_pending_cans()
    else:
        creators_df = pd.DataFrame()
    
    recipients = ui_helpers.render_creator_selector(creators_df, notification_type)

elif recipient_type == 'vendors':
    st.markdown("### 🏢 Select Vendors")
    
    if notification_type in ['🚨 Critical Alerts', '📦 Pending Stock-in']:
        st.warning("⚠️ Vendor notifications are only available for PO Schedule")
    else:
        vendors_df = queries.get_vendors_with_active_pos(date_type)
        selected_vendor_names, recipients = ui_helpers.render_vendor_selector(vendors_df)

elif recipient_type == 'custom':
    st.markdown("### ✉️ Custom Recipients")
    recipients = ui_helpers.render_custom_recipient_input()

elif recipient_type == 'customs':
    # Customs clearance - fixed recipient
    recipients = [{
        'email': 'custom.clearance@prostech.vn',
        'name': 'Customs Team'
    }]
    st.success(f"📧 Email will be sent to: {recipients[0]['email']}")

st.markdown("---")

# ========================
# CC CONFIGURATION
# ========================

if recipients:
    include_managers, additional_cc_emails = ui_helpers.render_cc_configuration(
        recipients, 
        recipient_type
    )
    
    cc_info = {
        'include_managers': include_managers,
        'additional_cc': additional_cc_emails
    }
    
    st.markdown("---")
    
    # ========================
    # PREVIEW
    # ========================
    
    ui_helpers.render_email_preview(
        notification_type,
        recipients,
        settings,
        cc_info
    )
    
    st.markdown("---")
    
    # ========================
    # SEND EMAILS
    # ========================
    
    col1, col2, col3 = st.columns([1, 2, 1])
    
    with col2:
        if st.button("📤 Send Emails", type="primary", use_container_width=True):
            if not recipients:
                st.error("❌ No recipients selected")
            else:
                # Confirm sending
                total_recipients = len(recipients)
                
                with st.spinner(f"Sending emails to {total_recipients} recipient(s)..."):
                    results = []
                    errors = []
                    
                    # Progress tracking
                    progress_bar = st.progress(0)
                    status_text = st.empty()
                    
                    # Send emails
                    for i, recipient in enumerate(recipients, 1):
                        try:
                            # Update progress
                            progress_bar.progress(i / total_recipients)
                            status_text.text(f"Sending {i}/{total_recipients}: {recipient['name']}")
                            
                            # Prepare CC list
                            current_cc_emails = additional_cc_emails.copy()
                            
                            # Add manager to CC if enabled
                            if include_managers and recipient.get('manager_email'):
                                current_cc_emails.append(recipient['manager_email'])
                            
                            # Remove duplicates
                            current_cc_emails = list(set(current_cc_emails)) if current_cc_emails else None
                            
                            # Get data and send based on notification type
                            if notification_type == "📅 PO Schedule":
                                if recipient_type == 'vendors':
                                    po_df = queries.get_vendor_pos(
                                        recipient['vendor_name'],
                                        weeks_ahead,
                                        date_type,
                                        include_overdue=True
                                    )
                                    is_custom = False
                                elif recipient_type == 'custom':
                                    po_df = queries.get_international_pos(weeks_ahead, date_type)
                                    is_custom = True
                                else:  # creators
                                    po_df = queries.get_pos_by_creator(
                                        recipient['email'],
                                        weeks_ahead,
                                        date_type
                                    )
                                    is_custom = False
                                
                                if po_df is not None and not po_df.empty:
                                    success, message = coordinator.send_po_schedule(
                                        recipient['email'],
                                        recipient['name'],
                                        po_df,
                                        cc_emails=current_cc_emails,
                                        is_custom_recipient=is_custom,
                                        weeks_ahead=weeks_ahead,
                                        date_type=date_type
                                    )
                                    
                                    results.append({
                                        'Creator': recipient['name'],
                                        'Email': recipient['email'],
                                        'Status': '✅ Success' if success else '❌ Failed',
                                        'POs': len(po_df),
                                        'Message': message
                                    })
                                else:
                                    results.append({
                                        'Creator': recipient['name'],
                                        'Email': recipient['email'],
                                        'Status': '⚠️ Skipped',
                                        'POs': 0,
                                        'Message': 'No PO data found'
                                    })
                            
                            elif notification_type == "🚨 Critical Alerts":
                                overdue_pos = queries.get_overdue_pos_by_creator(recipient['email'], date_type)
                                pending_cans = queries.get_pending_cans_by_creator(recipient['email'])
                                
                                data_dict = {
                                    'overdue_pos': overdue_pos if overdue_pos is not None else pd.DataFrame(),
                                    'pending_stockin': pending_cans if pending_cans is not None else pd.DataFrame()
                                }
                                
                                if ((overdue_pos is not None and not overdue_pos.empty) or 
                                    (pending_cans is not None and not pending_cans.empty)):
                                    success, message = coordinator.send_critical_alerts(
                                        recipient['email'],
                                        recipient['name'],
                                        data_dict,
                                        cc_emails=current_cc_emails,
                                        date_type=date_type
                                    )
                                    
                                    alert_count = 0
                                    if overdue_pos is not None:
                                        alert_count += len(overdue_pos)
                                    if pending_cans is not None:
                                        alert_count += len(pending_cans)
                                    
                                    results.append({
                                        'Creator': recipient['name'],
                                        'Email': recipient['email'],
                                        'Status': '✅ Success' if success else '❌ Failed',
                                        'Alerts': alert_count,
                                        'Message': message
                                    })
                                else:
                                    results.append({
                                        'Creator': recipient['name'],
                                        'Email': recipient['email'],
                                        'Status': '⚠️ Skipped',
                                        'Alerts': 0,
                                        'Message': 'No critical items found'
                                    })
                            
                            elif notification_type == "📦 Pending Stock-in":
                                can_df = queries.get_pending_cans_by_creator(recipient['email'])
                                
                                if can_df is not None and not can_df.empty:
                                    success, message = coordinator.send_pending_stockin(
                                        recipient['email'],
                                        recipient['name'],
                                        can_df,
                                        cc_emails=current_cc_emails
                                    )
                                    
                                    results.append({
                                        'Creator': recipient['name'],
                                        'Email': recipient['email'],
                                        'Status': '✅ Success' if success else '❌ Failed',
                                        'Items': len(can_df),
                                        'Message': message
                                    })
                                else:
                                    results.append({
                                        'Creator': recipient['name'],
                                        'Email': recipient['email'],
                                        'Status': '⚠️ Skipped',
                                        'Items': 0,
                                        'Message': 'No pending items found'
                                    })
                            
                            elif notification_type == "🛃 Custom Clearance":
                                po_df = queries.get_international_pos(weeks_ahead, date_type)
                                can_df = queries.get_pending_international_cans()
                                
                                success, message = coordinator.send_customs_clearance(
                                    recipient['email'],
                                    recipient['name'],
                                    po_df,
                                    can_df,
                                    cc_emails=current_cc_emails,
                                    weeks_ahead=weeks_ahead,
                                    date_type=date_type
                                )
                                
                                po_count = len(po_df) if po_df is not None and not po_df.empty else 0
                                can_count = len(can_df) if can_df is not None and not can_df.empty else 0
                                
                                results.append({
                                    'Recipient': recipient['name'],
                                    'Email': recipient['email'],
                                    'Status': '✅ Success' if success else '❌ Failed',
                                    'POs': po_count,
                                    'CANs': can_count,
                                    'Message': message
                                })
                        
                        except Exception as e:
                            logger.error(f"Error sending to {recipient['name']}: {e}", exc_info=True)
                            errors.append(f"Error for {recipient['name']}: {str(e)}")
                            results.append({
                                'Creator': recipient['name'],
                                'Email': recipient['email'],
                                'Status': '❌ Error',
                                'Message': str(e)
                            })
                    
                    # Clear progress
                    progress_bar.empty()
                    status_text.empty()
                    
                    # Show results
                    ui_helpers.render_batch_results(results)
                    
                    # Show errors if any
                    if errors:
                        with st.expander("❌ Detailed Errors"):
                            for error in errors:
                                st.error(error)

else:
    st.info("👆 Please select recipients above to continue")

# ========================
# HELP SECTION
# ========================

st.markdown("---")

with st.expander("ℹ️ Help & Information"):
    st.markdown(f"""
    ### How to use this page:
    
    1. **Select Notification Type**:
       - **📅 PO Schedule**: Send upcoming arrivals for selected period (1-8 weeks)
       - **🚨 Critical Alerts**: Send overdue POs and urgent pending CANs
       - **📦 Pending Stock-in**: Send pending CAN items awaiting processing
       - **🛃 Custom Clearance**: Send international POs to customs team
    
    2. **Select Time Period** (for PO Schedule & Custom Clearance):
       - Choose how many weeks ahead to include (1-8 weeks)
       - Default is 4 weeks
       - **Select ETD or ETA** as the date basis
    
    3. **Date Type Selection**:
       - **ETD**: Estimated Time of Departure - when goods leave the vendor
       - **ETA**: Estimated Time of Arrival - when goods arrive at warehouse
       - This affects how POs are filtered and sorted
    
    4. **Select Recipients**: 
       - **📝 PO Creators**: Send to PO creators
       - **🏢 Vendors**: Send to vendor contacts (two-step selection)
       - **✉️ Custom Recipients**: Enter any email addresses manually
       - For customs: Automatically sent to custom.clearance@prostech.vn
    
    5. **Configure CC Settings**: 
       - Include managers in CC for creators
       - Add additional CC recipients for any notification type
    
    6. **Preview**: Check the email configuration before sending
    7. **Send**: Confirm and send emails
    
    ### Email Content by Type:
    
    #### 📅 PO Schedule:
    - For creators: POs they created for selected weeks (by ETD/ETA)
    - For vendors: All their POs (overdue + upcoming) based on selected date
    - For custom recipients: All POs for selected weeks
    - Includes Excel attachment with full details
    - Includes calendar integration (.ics file)
    - Includes Google Calendar and Outlook links
    
    #### 🚨 Critical Alerts:
    - For creators: Their overdue POs (by ETD/ETA) and pending CANs
    - For custom recipients: All critical items
    - Not available for vendors
    - Excel attachment with overdue and pending items
    - Sorted by urgency with clear action items
    
    #### 📦 Pending Stock-in:
    - For creators: CANs from their POs
    - For custom recipients: All pending CANs
    - Not available for vendors
    - Categorized by urgency (Critical >14 days, Urgent >7 days, Normal ≤7 days)
    - Excel attachment with summaries by urgency and vendor
    - Calendar reminder for stock-in tasks
    
    #### 🛃 Custom Clearance:
    - International vendor POs only (by ETD/ETA)
    - Includes pending international CANs
    - Grouped by country
    - Customs documentation checklist included
    - Excel attachment with country summaries
    - Calendar events for clearance deadlines
    
    ### Notes:
    - Emails are sent from: inbound@prostech.vn
    - Date filtering supports both ETD and ETA
    - Vendor selection is a two-step process: select vendors first, then their contacts
    - Custom recipients receive general overview (not filtered by creator)
    - All emails can include additional CC recipients
    - Only pending items (not completed) are included
    - All attachments are automatically generated (Excel + Calendar)
    """)

# ========================
# FOOTER
# ========================

st.markdown("---")
st.caption(f"Email Notification System | Last updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")