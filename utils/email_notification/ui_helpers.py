# utils/email_notification/ui_helpers.py
"""
UI Helper functions for Email Notification page - IMPROVED VERSION
Added features:
1. Buying Legal Entity filter
2. Data preview with row selection before sending
"""

import streamlit as st
import pandas as pd
import re
from typing import List, Dict, Tuple, Optional
import logging

logger = logging.getLogger(__name__)


# ========================
# VALIDATION HELPERS
# ========================

def validate_email(email: str) -> bool:
    """Validate email format"""
    pattern = r'^[\w\.-]+@[\w\.-]+\.\w+$'
    return re.match(pattern, email) is not None


# ========================
# SESSION STATE MANAGEMENT
# ========================

def initialize_session_state():
    """Initialize session state variables"""
    defaults = {
        'notification_type': '📅 PO Schedule',
        'weeks_ahead': 4,
        'date_type': 'ETD',
        'recipient_type': 'creators',
        'selected_vendors': [],
        'selected_vendor_contacts': [],
        'legal_entities': [],  # NEW: Store selected entities
        'preview_data': {},  # NEW: Store preview data for each recipient
        'selected_rows': {}  # NEW: Store selected rows for each recipient
    }
    
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


# ========================
# EMAIL SETTINGS UI - IMPROVED
# ========================

def render_email_settings() -> Dict:
    """
    Render email settings section with buying legal entity filter
    Returns: Dict with notification_type, weeks_ahead, date_type, legal_entities
    """
    st.subheader("⚙️ Email Settings")
    
    # Notification type selection
    notification_type = st.radio(
        "Select Notification Type",
        ['📅 PO Schedule', '🚨 Critical Alerts', '📦 Pending Stock-in', '🛃 Custom Clearance'],
        index=['📅 PO Schedule', '🚨 Critical Alerts', '📦 Pending Stock-in', '🛃 Custom Clearance'].index(
            st.session_state.notification_type
        ),
        horizontal=True
    )
    
    # Update session state and rerun if changed
    if notification_type != st.session_state.notification_type:
        st.session_state.notification_type = notification_type
        st.rerun()
    
    # Time period and date type (for applicable notification types)
    weeks_ahead = None
    date_type = None
    
    if notification_type in ['📅 PO Schedule', '🛃 Custom Clearance']:
        weeks_ahead = st.selectbox(
            "Time Period",
            [1, 2, 3, 4, 5, 6, 7, 8],
            index=[1, 2, 3, 4, 5, 6, 7, 8].index(st.session_state.weeks_ahead),
            format_func=lambda x: f"Next {x} week{'s' if x > 1 else ''}"
        )
        st.session_state.weeks_ahead = weeks_ahead
        
        date_type = st.radio(
            "Date Type",
            ["ETD", "ETA"],
            index=0 if st.session_state.date_type == "ETD" else 1,
            horizontal=True,
            help="ETD: Estimated Time of Departure | ETA: Estimated Time of Arrival"
        )
        st.session_state.date_type = date_type
    elif notification_type == '🚨 Critical Alerts':
        date_type = st.radio(
            "Date Type for Overdue POs",
            ["ETD", "ETA"],
            index=0 if st.session_state.get('date_type', 'ETD') == "ETD" else 1,
            horizontal=True,
            help="ETD: Estimated Time of Departure | ETA: Estimated Time of Arrival"
        )
        st.session_state.date_type = date_type
    
    # NEW: Buying Legal Entity Filter
    legal_entities = render_legal_entity_filter()
    
    return {
        'notification_type': notification_type,
        'weeks_ahead': weeks_ahead or st.session_state.get('weeks_ahead', 4),
        'date_type': date_type or st.session_state.get('date_type', 'ETD'),
        'legal_entities': legal_entities
    }


def render_legal_entity_filter() -> Optional[List[str]]:
    """
    NEW FUNCTION: Render legal entity filter
    Returns: List of selected entities or None for all
    """
    st.markdown("---")
    st.markdown("**🏢 Legal Entity Filter**")
    
    # Get available entities from database
    from utils.email_notification.data_queries import EmailNotificationQueries
    queries = EmailNotificationQueries()
    entities_df = queries.get_legal_entities()
    
    if entities_df.empty:
        st.warning("⚠️ No buying legal entities found")
        return None
    
    entity_options = ['All Entities'] + entities_df['legal_entity'].tolist()
    
    # Filter selection
    filter_mode = st.radio(
        "Select Filter Mode",
        ["All Entities", "Specific Entities"],
        horizontal=True,
        key="entity_filter_mode"
    )
    
    if filter_mode == "All Entities":
        st.info(f"📊 Including all {len(entities_df)} legal entities")
        return None  # None means all entities
    else:
        selected_entities = st.multiselect(
            "Select Legal Entities",
            options=entities_df['legal_entity'].tolist(),
            default=st.session_state.get('legal_entities', []),
            key="entity_multiselect"
        )
        
        if selected_entities:
            st.session_state.legal_entities = selected_entities
            st.success(f"✅ Selected {len(selected_entities)} entit{'y' if len(selected_entities) == 1 else 'ies'}")
            
            # Show summary of selected entities
            with st.expander("📋 Selected Entities"):
                for entity in selected_entities:
                    st.text(f"  • {entity}")
            
            return selected_entities
        else:
            st.warning("⚠️ Please select at least one entity")
            return []


def render_recipient_type_selector(notification_type: str) -> str:
    """
    Render recipient type selector
    Returns: recipient type ('creators', 'vendors', 'custom', 'customs')
    """
    if notification_type == '🛃 Custom Clearance':
        st.info("📧 Customs clearance emails will be sent to: custom.clearance@prostech.vn")
        return 'customs'
    
    recipient_type = st.radio(
        "Send to:",
        ['📝 PO Creators', '🏢 Vendors', '✉️ Custom Recipients'],
        index=['creators', 'vendors', 'custom'].index(st.session_state.get('recipient_type', 'creators')),
        format_func=lambda x: x,
        horizontal=True
    )
    
    # Map display to internal value
    type_mapping = {
        '📝 PO Creators': 'creators',
        '🏢 Vendors': 'vendors',
        '✉️ Custom Recipients': 'custom'
    }
    
    return type_mapping[recipient_type]


# ========================
# RECIPIENT SELECTION UI
# ========================

def render_creator_selector(creators_df: pd.DataFrame, notification_type: str) -> List[Dict]:
    """
    Render creator selection interface
    Returns: List of selected creator dicts with 'email', 'name' keys
    """
    if creators_df.empty:
        st.warning(f"No creators found for {notification_type}")
        return []
    
    st.write(f"**Available Creators ({len(creators_df)}):**")
    
    # Add metrics based on notification type
    if notification_type == '📅 PO Schedule':
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Total POs", creators_df['active_pos'].sum())
        with col2:
            st.metric("Total Value", f"${creators_df['total_outstanding_value'].sum():,.0f}")
        with col3:
            st.metric("International POs", creators_df['international_pos'].sum())
    elif notification_type == '🚨 Critical Alerts':
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Overdue POs", creators_df['overdue_pos'].sum())
        with col2:
            st.metric("Pending CANs", creators_df['pending_cans'].sum())
        with col3:
            st.metric("Total Value", f"${(creators_df['overdue_value'].sum() + creators_df['pending_can_value'].sum()):,.0f}")
    elif notification_type == '📦 Pending Stock-in':
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Pending Items", creators_df['pending_cans'].sum())
        with col2:
            st.metric("Urgent Items", creators_df['urgent_cans'].sum())
        with col3:
            st.metric("Total Value", f"${creators_df['total_pending_value'].sum():,.0f}")
    
    # Selection interface
    select_all = st.checkbox("Select All Creators", key=f"select_all_creators_{notification_type}")
    
    if select_all:
        selected_indices = list(range(len(creators_df)))
    else:
        selected_indices = st.multiselect(
            "Select Creators",
            options=list(range(len(creators_df))),
            format_func=lambda i: f"{creators_df.iloc[i]['name']} ({creators_df.iloc[i]['email']})",
            key=f"creator_selector_{notification_type}"
        )
    
    # Convert to list of dicts
    selected_creators = []
    for idx in selected_indices:
        selected_creators.append({
            'email': creators_df.iloc[idx]['email'],
            'name': creators_df.iloc[idx]['name'],
            'manager_email': creators_df.iloc[idx].get('manager_email'),
            'manager_name': creators_df.iloc[idx].get('manager_name')
        })
    
    return selected_creators


def render_vendor_selector(vendors_df: pd.DataFrame) -> Tuple[List[str], List[Dict]]:
    """
    Render two-step vendor selection interface
    Returns: (selected_vendor_names, selected_vendor_contacts)
    """
    if vendors_df.empty:
        st.warning("No vendors with active POs found")
        return [], []
    
    st.write(f"**Available Vendors ({len(vendors_df)}):**")
    
    # Step 1: Select vendors
    st.markdown("**Step 1: Select Vendors**")
    select_all_vendors = st.checkbox("Select All Vendors", key="select_all_vendors")
    
    if select_all_vendors:
        selected_vendor_names = vendors_df['vendor_name'].unique().tolist()
    else:
        selected_vendor_names = st.multiselect(
            "Choose vendors",
            options=vendors_df['vendor_name'].unique().tolist(),
            default=st.session_state.get('selected_vendors', []),
            key="vendor_selector"
        )
    
    st.session_state.selected_vendors = selected_vendor_names
    
    selected_contacts = []
    
    # Step 2: Select contacts for selected vendors
    if selected_vendor_names:
        st.markdown("**Step 2: Select Contacts**")
        contacts_df = vendors_df[vendors_df['vendor_name'].isin(selected_vendor_names)]
        
        st.info(f"📧 Found {len(contacts_df)} contact(s) from {len(selected_vendor_names)} vendor(s)")
        
        select_all_contacts = st.checkbox("Select All Contacts", key="select_all_contacts")
        
        if select_all_contacts:
            selected_contact_indices = list(range(len(contacts_df)))
        else:
            selected_contact_indices = st.multiselect(
                "Choose specific contacts",
                options=list(range(len(contacts_df))),
                format_func=lambda i: f"{contacts_df.iloc[i]['vendor_name']} - {contacts_df.iloc[i]['contact_name']} ({contacts_df.iloc[i]['vendor_email']})",
                key="vendor_contacts_selector"
            )
        
        # Convert to list of dicts
        for idx in selected_contact_indices:
            contact = contacts_df.iloc[idx]
            selected_contacts.append({
                'email': contact['vendor_email'],
                'name': contact['contact_name'],
                'vendor_name': contact['vendor_name']
            })
    
    return selected_vendor_names, selected_contacts


def render_custom_recipient_input() -> List[Dict]:
    """
    Render custom recipient input interface
    Returns: List of custom recipient dicts with 'email', 'name' keys
    """
    st.markdown("**Enter Custom Recipients:**")
    
    custom_emails_input = st.text_area(
        "Email addresses (one per line)",
        placeholder="example1@company.com\nexample2@company.com",
        height=100,
        key="custom_emails_input"
    )
    
    custom_recipients = []
    
    if custom_emails_input:
        emails = [email.strip() for email in custom_emails_input.split('\n') if email.strip()]
        
        # Validate emails
        valid_emails = []
        invalid_emails = []
        
        for email in emails:
            if validate_email(email):
                valid_emails.append(email)
                custom_recipients.append({
                    'email': email,
                    'name': email.split('@')[0]  # Use email prefix as name
                })
            else:
                invalid_emails.append(email)
        
        if valid_emails:
            st.success(f"✅ {len(valid_emails)} valid email(s)")
        
        if invalid_emails:
            st.error(f"❌ Invalid email(s): {', '.join(invalid_emails)}")
    
    return custom_recipients


# ========================
# CC CONFIGURATION UI
# ========================

def render_cc_configuration(recipients: List[Dict], recipient_type: str) -> Tuple[bool, List[str]]:
    """
    Render CC configuration interface
    Returns: (include_managers, additional_cc_emails)
    """
    st.subheader("📧 CC Configuration")
    
    include_managers = False
    
    # Manager CC option (only for creators)
    if recipient_type == 'creators':
        include_managers = st.checkbox(
            "Include managers in CC",
            value=False,
            help="Manager emails will be added to CC for each creator"
        )
        
        if include_managers:
            managers_with_email = [r for r in recipients if r.get('manager_email')]
            if managers_with_email:
                st.info(f"📧 {len(set([r['manager_email'] for r in managers_with_email]))} manager(s) will be included in CC")
            else:
                st.warning("⚠️ No managers with email found")
    
    # Additional CC emails
    st.markdown("**Additional CC Recipients (optional):**")
    additional_cc_input = st.text_area(
        "Email addresses (one per line)",
        placeholder="cc1@company.com\ncc2@company.com",
        height=80,
        key="additional_cc_input"
    )
    
    additional_cc_emails = []
    
    if additional_cc_input:
        emails = [email.strip() for email in additional_cc_input.split('\n') if email.strip()]
        
        valid_cc = []
        invalid_cc = []
        
        for email in emails:
            if validate_email(email):
                valid_cc.append(email)
                additional_cc_emails.append(email)
            else:
                invalid_cc.append(email)
        
        if valid_cc:
            st.success(f"✅ {len(valid_cc)} CC email(s) will be added")
        
        if invalid_cc:
            st.error(f"❌ Invalid CC email(s): {', '.join(invalid_cc)}")
    
    return include_managers, additional_cc_emails


# ========================
# DATA PREVIEW UI - NEW IMPROVED VERSION
# ========================

def render_data_preview_with_selection(
    queries,
    notification_type: str,
    recipients: List[Dict],
    settings: Dict,
    recipient_type: str
):
    """
    NEW FUNCTION: Render data preview with row selection capability
    Shows actual PO data that will be sent and allows users to deselect rows
    """
    st.subheader("📊 Data Preview & Selection")
    
    if not recipients:
        st.warning("⚠️ No recipients selected")
        return
    
    st.info("💡 Preview the data that will be sent to each recipient. Uncheck rows you don't want to include.")
    
    # Fetch and preview data for each recipient
    for idx, recipient in enumerate(recipients):
        with st.expander(
            f"📧 {recipient['name']} ({recipient['email']})",
            expanded=(idx == 0)  # Expand first recipient by default
        ):
            # Fetch data based on notification type
            if notification_type == "📅 PO Schedule":
                df = fetch_preview_data_po_schedule(
                    queries, recipient, settings, recipient_type
                )
            elif notification_type == "🚨 Critical Alerts":
                df = fetch_preview_data_critical_alerts(
                    queries, recipient, settings, recipient_type
                )
            elif notification_type == "📦 Pending Stock-in":
                df = fetch_preview_data_pending_stockin(
                    queries, recipient, settings
                )
            else:
                df = pd.DataFrame()
            
            if df is not None and not df.empty:
                # Store preview data in session state
                recipient_key = f"{recipient['email']}_{notification_type}"
                st.session_state.preview_data[recipient_key] = df
                
                # Show summary metrics
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.metric("Total Rows", len(df))
                with col2:
                    if 'outstanding_arrival_amount_usd' in df.columns:
                        st.metric("Total Value", f"${df['outstanding_arrival_amount_usd'].sum():,.0f}")
                with col3:
                    unique_pos = df['po_number'].nunique() if 'po_number' in df.columns else 0
                    st.metric("Unique POs", unique_pos)
                
                # Data selection interface
                st.markdown("**Select rows to include in email:**")
                
                # Initialize selected rows if not exists
                if recipient_key not in st.session_state.selected_rows:
                    st.session_state.selected_rows[recipient_key] = list(range(len(df)))
                
                # Select/Deselect all for this recipient
                col_a, col_b = st.columns(2)
                with col_a:
                    if st.button(f"✅ Select All", key=f"select_all_{recipient_key}"):
                        st.session_state.selected_rows[recipient_key] = list(range(len(df)))
                        st.rerun()
                with col_b:
                    if st.button(f"❌ Deselect All", key=f"deselect_all_{recipient_key}"):
                        st.session_state.selected_rows[recipient_key] = []
                        st.rerun()
                
                # Display editable dataframe with selection
                display_df = df.copy()
                
                # Add selection column
                display_df.insert(0, '✓', False)
                for idx_row in st.session_state.selected_rows[recipient_key]:
                    if idx_row < len(display_df):
                        display_df.loc[idx_row, '✓'] = True
                
                # Show only key columns for preview
                preview_columns = get_preview_columns(notification_type, display_df.columns)
                
                # Use data editor for row selection
                edited_df = st.data_editor(
                    display_df[['✓'] + preview_columns],
                    hide_index=False,
                    use_container_width=True,
                    disabled=[col for col in preview_columns],  # Only checkbox is editable
                    key=f"data_editor_{recipient_key}"
                )
                
                # Update selected rows based on checkbox
                st.session_state.selected_rows[recipient_key] = [
                    i for i in range(len(edited_df)) if edited_df.loc[i, '✓']
                ]
                
                selected_count = len(st.session_state.selected_rows[recipient_key])
                if selected_count == 0:
                    st.warning(f"⚠️ No rows selected - email will NOT be sent to {recipient['name']}")
                else:
                    st.success(f"✅ {selected_count} row(s) selected for email")
            else:
                st.warning(f"⚠️ No data found for {recipient['name']}")
                st.session_state.selected_rows[f"{recipient['email']}_{notification_type}"] = []


def fetch_preview_data_po_schedule(queries, recipient, settings, recipient_type):
    """Fetch PO schedule data for preview"""
    weeks_ahead = settings['weeks_ahead']
    date_type = settings['date_type'].lower()
    legal_entities = settings.get('legal_entities')
    
    if recipient_type == 'vendors':
        df = queries.get_vendor_pos(
            recipient['vendor_name'],
            weeks_ahead,
            date_type,
            include_overdue=True,
            legal_entities=legal_entities
        )
    elif recipient_type == 'custom':
        df = queries.get_international_pos(
            weeks_ahead,
            date_type,
            legal_entities=legal_entities
        )
    else:  # creators
        df = queries.get_pos_by_creator(
            recipient['email'],
            weeks_ahead,
            date_type,
            legal_entities=legal_entities
        )
    
    return df


def fetch_preview_data_critical_alerts(queries, recipient, settings, recipient_type):
    """Fetch critical alerts data for preview"""
    date_type = settings['date_type'].lower()
    legal_entities = settings.get('legal_entities')
    
    if recipient_type == 'creators':
        overdue_df = queries.get_overdue_pos_by_creator(
            recipient['email'],
            date_type,
            legal_entities=legal_entities
        )
        pending_can_df = queries.get_pending_cans_by_creator(
            recipient['email'],
            legal_entities=legal_entities
        )
        
        # Combine both dataframes
        if overdue_df is not None and not overdue_df.empty:
            return overdue_df
        elif pending_can_df is not None and not pending_can_df.empty:
            return pending_can_df
    
    return pd.DataFrame()


def fetch_preview_data_pending_stockin(queries, recipient, settings):
    """Fetch pending stock-in data for preview"""
    legal_entities = settings.get('legal_entities')
    
    df = queries.get_pending_cans_by_creator(
        recipient['email'],
        legal_entities=legal_entities
    )
    
    return df


def get_preview_columns(notification_type: str, available_columns: List[str]) -> List[str]:
    """Get relevant columns to display in preview based on notification type"""
    
    # Define key columns for each notification type (matching purchase_order_full_view schema)
    if notification_type == "📅 PO Schedule":
        key_cols = [
            'po_number', 'vendor_name', 'legal_entity',
            'etd', 'eta', 'pt_code', 'product_name',
            'pending_standard_arrival_quantity', 'standard_uom',
            'outstanding_arrival_amount_usd', 'status'
        ]
    elif notification_type == "🚨 Critical Alerts":
        key_cols = [
            'po_number', 'vendor_name', 'legal_entity',
            'etd', 'eta', 'pt_code',
            'pending_standard_arrival_quantity',
            'outstanding_arrival_amount_usd'
        ]
    elif notification_type == "📦 Pending Stock-in":
        key_cols = [
            'arrival_note_number', 'po_number', 'vendor_name',
            'legal_entity', 'pt_code',
            'pending_quantity', 'pending_value_usd',
            'days_since_arrival', 'arrival_date'
        ]
    else:
        key_cols = []
    
    # Return only columns that exist in the dataframe
    return [col for col in key_cols if col in available_columns]


# ========================
# EMAIL PREVIEW & SUMMARY UI
# ========================

def render_email_preview(notification_type: str, recipients: List[Dict], 
                        settings: Dict, cc_info: Dict):
    """Render email preview and summary - SIMPLIFIED VERSION (old preview)"""
    st.subheader("📧 Email Summary")
    
    if not recipients:
        st.warning("⚠️ No recipients selected")
        return
    
    # Summary
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.metric("Recipients", len(recipients))
    
    with col2:
        if cc_info['include_managers']:
            managers_count = len(set([r.get('manager_email') for r in recipients if r.get('manager_email')]))
            cc_count = managers_count + len(cc_info['additional_cc'])
        else:
            cc_count = len(cc_info['additional_cc'])
        st.metric("CC Recipients", cc_count)
    
    with col3:
        st.metric("Total Emails", len(recipients))
    
    # Email details
    with st.expander("📋 Email Details"):
        st.markdown(f"**Type:** {notification_type}")
        
        if settings.get('weeks_ahead'):
            st.markdown(f"**Period:** Next {settings['weeks_ahead']} week(s)")
        
        if settings.get('date_type'):
            st.markdown(f"**Date Type:** {settings['date_type']}")
        
        if settings.get('legal_entities'):
            st.markdown(f"**Legal Entities:** {', '.join(settings['legal_entities'])}")
        else:
            st.markdown(f"**Legal Entities:** All")
        
        st.markdown("**Recipients:**")
        for i, recipient in enumerate(recipients[:5], 1):
            st.text(f"  {i}. {recipient['name']} ({recipient['email']})")
        
        if len(recipients) > 5:
            st.text(f"  ... and {len(recipients) - 5} more")
        
        if cc_info['additional_cc']:
            st.markdown("**Additional CC:**")
            for cc_email in cc_info['additional_cc']:
                st.text(f"  • {cc_email}")


# ========================
# BATCH PROCESSING UI
# ========================

def render_batch_progress(current: int, total: int, recipient_name: str):
    """Render progress bar and status for batch email sending"""
    progress = current / total
    st.progress(progress)
    st.text(f"Sending email {current}/{total}: {recipient_name}")


def render_batch_results(results: List[Dict]):
    """Render results summary after batch sending"""
    st.success("✅ Email process completed!")
    
    results_df = pd.DataFrame(results)
    
    # Summary metrics
    col1, col2, col3 = st.columns(3)
    
    with col1:
        success_count = len([r for r in results if r.get('Status') == '✅ Success'])
        st.metric("Successful", success_count)
    
    with col2:
        failed_count = len([r for r in results if r.get('Status') == '❌ Failed'])
        st.metric("Failed", failed_count)
    
    with col3:
        skipped_count = len([r for r in results if r.get('Status') == '⚠️ Skipped'])
        st.metric("Skipped", skipped_count)
    
    # Detailed results table
    st.dataframe(results_df, use_container_width=True, hide_index=True)
    
    # Show errors if any
    errors = [r for r in results if r.get('Status') in ['❌ Failed', '❌ Error']]
    if errors:
        with st.expander("❌ Error Details"):
            for error in errors:
                st.error(f"{error.get('Creator', error.get('Email'))}: {error.get('Message')}")