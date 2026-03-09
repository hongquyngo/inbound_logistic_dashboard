# pages/3_📧_Email_Notifications.py
"""
IMPROVED EMAIL NOTIFICATIONS PAGE
New Features:
1. Buying Legal Entity filter
2. Data preview with row selection before sending
"""

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
    legal_entities = settings.get('legal_entities')

# RIGHT COLUMN: Quick Info
with col2:
    st.subheader("ℹ️ Quick Info")
    
    entity_info = "All Entities" if not legal_entities else f"{len(legal_entities)} Selected"
    
    st.info(f"""
    **Current Settings:**
    - Type: {notification_type}
    - Period: {weeks_ahead} week(s)
    - Date: {date_type.upper()}
    - Entities: {entity_info}
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
        creators_df = queries.get_creators_list(
            weeks_ahead, 
            date_type,
            legal_entities=legal_entities
        )
    elif notification_type == '🚨 Critical Alerts':
        creators_df = queries.get_creators_overdue(
            date_type,
            legal_entities=legal_entities
        )
    elif notification_type == '📦 Pending Stock-in':
        creators_df = queries.get_creators_with_pending_cans(
            legal_entities=legal_entities
        )
    else:
        creators_df = pd.DataFrame()
    
    recipients = ui_helpers.render_creator_selector(creators_df, notification_type)

elif recipient_type == 'vendors':
    st.markdown("### 🏢 Select Vendors")
    
    if notification_type in ['🚨 Critical Alerts', '📦 Pending Stock-in']:
        st.warning("⚠️ Vendor notifications are only available for PO Schedule")
    else:
        vendors_df = queries.get_vendors_with_active_pos(
            date_type,
            legal_entities=legal_entities
        )
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
    # EMAIL PREVIEW SUMMARY
    # ========================
    
    ui_helpers.render_email_preview(
        notification_type,
        recipients,
        settings,
        cc_info
    )
    
    st.markdown("---")
    
    # ========================
    # NEW: DATA PREVIEW WITH SELECTION
    # ========================
    
    ui_helpers.render_data_preview_with_selection(
        queries,
        notification_type,
        recipients,
        settings,
        recipient_type
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
                            
                            # Get selected rows for this recipient
                            recipient_key = f"{recipient['email']}_{notification_type}"
                            selected_row_indices = st.session_state.selected_rows.get(recipient_key, [])
                            
                            # Skip if no rows selected
                            if not selected_row_indices:
                                results.append({
                                    'Creator': recipient['name'],
                                    'Email': recipient['email'],
                                    'Status': '⚠️ Skipped',
                                    'POs': 0,
                                    'Message': 'No data selected'
                                })
                                continue
                            
                            # Get the preview data and filter by selected rows
                            preview_data = st.session_state.preview_data.get(recipient_key)
                            
                            if preview_data is None or preview_data.empty:
                                results.append({
                                    'Creator': recipient['name'],
                                    'Email': recipient['email'],
                                    'Status': '⚠️ Skipped',
                                    'POs': 0,
                                    'Message': 'No data available'
                                })
                                continue
                            
                            # Filter dataframe to only selected rows
                            filtered_data = preview_data.iloc[selected_row_indices].copy()
                            
                            if filtered_data.empty:
                                results.append({
                                    'Creator': recipient['name'],
                                    'Email': recipient['email'],
                                    'Status': '⚠️ Skipped',
                                    'POs': 0,
                                    'Message': 'No data selected'
                                })
                                continue
                            
                            # Prepare CC list
                            current_cc_emails = additional_cc_emails.copy()
                            
                            # Add manager to CC if enabled
                            if include_managers and recipient.get('manager_email'):
                                current_cc_emails.append(recipient['manager_email'])
                            
                            # Remove duplicates
                            current_cc_emails = list(set(current_cc_emails)) if current_cc_emails else None
                            
                            # Send email based on notification type
                            if notification_type == "📅 PO Schedule":
                                is_custom = recipient_type == 'custom'
                                
                                success, message = coordinator.send_po_schedule(
                                    recipient['email'],
                                    recipient['name'],
                                    filtered_data,
                                    cc_emails=current_cc_emails,
                                    is_custom_recipient=is_custom,
                                    weeks_ahead=weeks_ahead,
                                    date_type=date_type
                                )
                                
                                results.append({
                                    'Creator': recipient['name'],
                                    'Email': recipient['email'],
                                    'Status': '✅ Success' if success else '❌ Failed',
                                    'POs': len(filtered_data),
                                    'Message': message
                                })
                            
                            elif notification_type == "🚨 Critical Alerts":
                                success, message = coordinator.send_critical_alert(
                                    recipient['email'],
                                    recipient['name'],
                                    filtered_data,
                                    cc_emails=current_cc_emails,
                                    date_type=date_type
                                )
                                
                                results.append({
                                    'Creator': recipient['name'],
                                    'Email': recipient['email'],
                                    'Status': '✅ Success' if success else '❌ Failed',
                                    'Items': len(filtered_data),
                                    'Message': message
                                })
                            
                            elif notification_type == "📦 Pending Stock-in":
                                success, message = coordinator.send_pending_stockin_alert(
                                    recipient['email'],
                                    recipient['name'],
                                    filtered_data,
                                    cc_emails=current_cc_emails
                                )
                                
                                results.append({
                                    'Creator': recipient['name'],
                                    'Email': recipient['email'],
                                    'Status': '✅ Success' if success else '❌ Failed',
                                    'Items': len(filtered_data),
                                    'Message': message
                                })
                            
                            elif notification_type == "🛃 Custom Clearance":
                                success, message = coordinator.send_customs_clearance(
                                    recipient['email'],
                                    recipient['name'],
                                    filtered_data,
                                    cc_emails=current_cc_emails,
                                    weeks_ahead=weeks_ahead,
                                    date_type=date_type
                                )
                                
                                results.append({
                                    'Recipient': recipient['name'],
                                    'Email': recipient['email'],
                                    'Status': '✅ Success' if success else '❌ Failed',
                                    'POs': len(filtered_data),
                                    'Message': message
                                })
                            
                        except Exception as e:
                            logger.error(f"Error sending email to {recipient['name']}: {e}")
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

# ========================
# FOOTER
# ========================

st.markdown("---")
st.markdown("""
**ℹ️ Tips:**
- Select buying legal entities to filter POs
- Preview and deselect specific rows before sending
- Use CC configuration to include managers or additional recipients
- International POs are automatically flagged for customs clearance
""")