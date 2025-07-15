# pages/3_📧_Email_Notifications.py

import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
from utils.auth import AuthManager
from utils.data_loader import InboundDataLoader
from utils.email_sender import InboundEmailSender
from sqlalchemy import text
import re
import logging

# Setup logging
logger = logging.getLogger(__name__)

# Page config
st.set_page_config(
    page_title="Email Notifications",
    page_icon="📧",
    layout="wide"
)

# Check authentication
auth_manager = AuthManager()
if not auth_manager.check_session():
    st.warning("⚠️ Please login to access this page")
    st.stop()

# Check user role - only allow admin and manager
user_role = st.session_state.get('user_role', '')
if user_role not in ['admin', 'manager', 'procurement_manager']:
    st.error("❌ You don't have permission to access this page")
    st.stop()

# Initialize services
data_loader = InboundDataLoader()
email_sender = InboundEmailSender()

st.title("📧 Email Notifications - Inbound Logistics")
st.markdown("Send purchase order schedules and pending stock-in alerts to relevant teams")
st.markdown("---")

# Helper function for email validation
def validate_email(email):
    """Validate email format"""
    pattern = r'^[\w\.-]+@[\w\.-]+\.\w+$'
    return re.match(pattern, email) is not None

# Get creators list with active POs
@st.cache_data(ttl=300)
def get_creators_list(weeks_ahead=4):
    """Get list of PO creators with active orders"""
    try:
        query = text("""
        SELECT DISTINCT 
            e.id,
            e.keycloak_id,
            CONCAT(e.first_name, ' ', e.last_name) as name,
            e.email,
            COUNT(DISTINCT po.po_number) as active_pos,
            SUM(po.outstanding_arrival_amount_usd) as total_outstanding_value,
            COUNT(DISTINCT CASE WHEN po.vendor_location_type = 'International' THEN po.po_number END) as international_pos,
            e.manager_id,
            m.email as manager_email,
            CONCAT(m.first_name, ' ', m.last_name) as manager_name
        FROM employees e
        LEFT JOIN employees m ON e.manager_id = m.id
        INNER JOIN purchase_order_full_view po ON po.created_by = e.email
        WHERE po.status NOT IN ('COMPLETED')
            AND po.etd >= CURDATE()
            AND po.etd <= DATE_ADD(CURDATE(), INTERVAL :weeks WEEK)
            AND po.pending_standard_arrival_quantity > 0
        GROUP BY e.id, e.keycloak_id, e.first_name, e.last_name, 
                 e.email, e.manager_id, m.email, m.first_name, m.last_name
        ORDER BY name
        """)
        
        engine = data_loader.engine
        with engine.connect() as conn:
            df = pd.read_sql(query, conn, params={'weeks': weeks_ahead})
        return df
    except Exception as e:
        logger.error(f"Error loading creators list: {e}")
        st.error(f"Error loading creators list: {e}")
        return pd.DataFrame()

# Get creators with overdue items
@st.cache_data(ttl=300)
def get_creators_overdue():
    """Get list of creators with overdue POs or pending CAN items"""
    try:
        query = text("""
        WITH overdue_pos AS (
            SELECT 
                e.id,
                e.keycloak_id,
                CONCAT(e.first_name, ' ', e.last_name) as name,
                e.email,
                e.manager_id,
                m.email as manager_email,
                CONCAT(m.first_name, ' ', m.last_name) as manager_name,
                COUNT(DISTINCT po.po_number) as overdue_pos,
                SUM(po.outstanding_arrival_amount_usd) as overdue_value,
                MAX(DATEDIFF(CURDATE(), po.etd)) as max_days_overdue
            FROM employees e
            LEFT JOIN employees m ON e.manager_id = m.id
            INNER JOIN purchase_order_full_view po ON po.created_by = e.email
            WHERE po.etd < CURDATE()
                AND po.status NOT IN ('COMPLETED')
                AND po.pending_standard_arrival_quantity > 0
            GROUP BY e.id, e.keycloak_id, e.first_name, e.last_name, e.email,
                     e.manager_id, m.email, m.first_name, m.last_name
        ),
        pending_cans AS (
            SELECT 
                po.created_by as email,
                COUNT(DISTINCT can.arrival_note_number) as pending_cans,
                SUM(can.pending_value_usd) as pending_can_value,
                MAX(can.days_since_arrival) as max_days_pending
            FROM can_tracking_full_view can
            INNER JOIN purchase_order_full_view po ON can.po_number = po.po_number
            WHERE can.days_since_arrival > 7
                AND can.pending_quantity > 0
            GROUP BY po.created_by
        )
        SELECT 
            op.*,
            COALESCE(pc.pending_cans, 0) as pending_cans,
            COALESCE(pc.pending_can_value, 0) as pending_can_value,
            COALESCE(pc.max_days_pending, 0) as max_days_pending
        FROM overdue_pos op
        LEFT JOIN pending_cans pc ON op.email = pc.email
        WHERE op.overdue_pos > 0 OR pc.pending_cans > 0
        ORDER BY op.overdue_pos DESC, pc.pending_cans DESC
        """)
        
        engine = data_loader.engine
        with engine.connect() as conn:
            df = pd.read_sql(query, conn)
        return df
    except Exception as e:
        logger.error(f"Error loading overdue creators: {e}")
        st.error(f"Error loading overdue creators: {e}")
        return pd.DataFrame()

# Get creators with pending stock-in items
@st.cache_data(ttl=300)
def get_creators_with_pending_cans():
    """Get list of creators with pending stock-in items"""
    try:
        query = text("""
        SELECT DISTINCT 
            e.id,
            e.keycloak_id,
            CONCAT(e.first_name, ' ', e.last_name) as name,
            e.email,
            COUNT(DISTINCT can.arrival_note_number) as pending_cans,
            SUM(can.pending_quantity) as total_pending_qty,
            SUM(can.pending_value_usd) as total_pending_value,
            MAX(can.days_since_arrival) as max_days_pending,
            COUNT(DISTINCT CASE WHEN can.days_since_arrival > 7 THEN can.arrival_note_number END) as urgent_cans,
            COUNT(DISTINCT CASE WHEN can.days_since_arrival > 14 THEN can.arrival_note_number END) as critical_cans,
            e.manager_id,
            m.email as manager_email,
            CONCAT(m.first_name, ' ', m.last_name) as manager_name
        FROM employees e
        LEFT JOIN employees m ON e.manager_id = m.id
        INNER JOIN purchase_order_full_view po ON po.created_by = e.email
        INNER JOIN can_tracking_full_view can ON can.po_number = po.po_number
        WHERE can.pending_quantity > 0
        GROUP BY e.id, e.keycloak_id, e.first_name, e.last_name, 
                 e.email, e.manager_id, m.email, m.first_name, m.last_name
        ORDER BY urgent_cans DESC, total_pending_value DESC
        """)
        
        engine = data_loader.engine
        with engine.connect() as conn:
            df = pd.read_sql(query, conn)
        return df
    except Exception as e:
        logger.error(f"Error loading creators with pending CANs: {e}")
        st.error(f"Error loading creators with pending CANs: {e}")
        return pd.DataFrame()

# Initialize session state for notification type if not exists
if 'notification_type' not in st.session_state:
    st.session_state.notification_type = '📅 PO Schedule'
if 'weeks_ahead' not in st.session_state:
    st.session_state.weeks_ahead = 4

# Email configuration section
col1, col2 = st.columns([2, 1])

with col2:
    st.subheader("⚙️ Email Settings")
    
    # Notification Type Selection
    notification_type = st.radio(
        "📧 Notification Type",
        ["📅 PO Schedule", "🚨 Critical Alerts", "📦 Pending Stock-in", "🛃 Custom Clearance"],
        index=["📅 PO Schedule", "🚨 Critical Alerts", "📦 Pending Stock-in", "🛃 Custom Clearance"].index(
            st.session_state.notification_type
        ),
        help="""
        PO Schedule: Upcoming arrivals for selected period
        Critical Alerts: Overdue POs and urgent pending CANs
        Pending Stock-in: Items awaiting warehouse processing
        Custom Clearance: International POs for customs team
        """
    )
    
    # Store in session state
    if notification_type != st.session_state.notification_type:
        st.session_state.notification_type = notification_type
        st.rerun()
    
    # Week selection for relevant notification types
    if notification_type in ["📅 PO Schedule", "🛃 Custom Clearance"]:
        weeks_ahead = st.selectbox(
            "📅 Time Period",
            options=[1, 2, 3, 4, 5, 6, 7, 8],
            index=3,  # Default to 4 weeks
            format_func=lambda x: f"{x} week{'s' if x > 1 else ''}",
            help="Select how many weeks ahead to include"
        )
        st.session_state.weeks_ahead = weeks_ahead
    else:
        weeks_ahead = st.session_state.get('weeks_ahead', 4)
    
    # Schedule type
    schedule_type = st.radio(
        "Schedule Type",
        ["Send Now", "Preview Only"],
        index=1
    )
# Continuation of Email_Notifications.py - Part 2

# Now load creators data based on notification type
creators_df = pd.DataFrame()  # Initialize empty
if notification_type == "🚨 Critical Alerts":
    creators_df = get_creators_overdue()
elif notification_type == "📦 Pending Stock-in":
    creators_df = get_creators_with_pending_cans()
elif notification_type != "🛃 Custom Clearance":
    creators_df = get_creators_list(weeks_ahead)

with col1:
    st.subheader("📋 Recipient Selection")
    
    # Initialize variables
    selected_creators = []
    custom_recipients = []
    recipient_type = None
    selection_mode = None
    
    # Special handling for Custom Clearance
    if notification_type == "🛃 Custom Clearance":
        st.info(f"📌 Custom Clearance notifications will be sent to the customs team for international shipments in the next {weeks_ahead} weeks")
        
        # Show summary of international shipments
        try:
            intl_summary = data_loader.get_international_shipment_summary(weeks_ahead)
            
            col1_1, col1_2, col1_3, col1_4 = st.columns(4)
            with col1_1:
                st.metric("Purchase Orders", f"{intl_summary.get('po_count', 0):,}")
            with col1_2:
                st.metric("Container Arrivals", f"{intl_summary.get('can_count', 0):,}")
            with col1_3:
                st.metric("Countries", intl_summary.get('total_countries', 0))
            with col1_4:
                st.metric("Total Value", f"${intl_summary.get('total_value', 0)/1000000:.1f}M")
            
            st.caption(f"🔍 Auto-applied filters: International vendors only | Next {weeks_ahead} weeks | Pending items only")
        except Exception as e:
            st.warning("Could not load international shipment summary")
            logger.error(f"Error loading international shipment summary: {e}")
        
        recipient_type = "customs"
    
    else:
        # Creator selection for other notification types
        if not creators_df.empty:
            # Selection mode
            selection_mode = st.radio(
                "Select recipients",
                ["All Creators", "Selected Creators Only", "Custom Recipients"],
                horizontal=True
            )
            
            if selection_mode == "All Creators":
                selected_creators = creators_df['name'].tolist()
                custom_recipients = []
                
                if notification_type == "🚨 Critical Alerts":
                    total_overdue = creators_df['overdue_pos'].sum()
                    total_pending_cans = creators_df['pending_cans'].sum()
                    st.info(f"Will send to {len(selected_creators)} creators with {total_overdue} overdue POs and {total_pending_cans} pending CANs")
                elif notification_type == "📦 Pending Stock-in":
                    total_pending_cans = creators_df['pending_cans'].sum() if 'pending_cans' in creators_df.columns else 0
                    total_urgent = creators_df['urgent_cans'].sum() if 'urgent_cans' in creators_df.columns else 0
                    st.info(f"Will send to {len(selected_creators)} creators with {total_pending_cans} pending CANs ({total_urgent} urgent)")
                else:
                    st.info(f"Will send to all {len(selected_creators)} PO creators")
                    
            elif selection_mode == "Selected Creators Only":
                # Format function based on notification type
                if notification_type == "🚨 Critical Alerts":
                    def format_func(x):
                        creator = creators_df[creators_df['name']==x].iloc[0]
                        return f"{x} (Overdue POs: {creator['overdue_pos']}, Pending CANs: {creator['pending_cans']})"
                elif notification_type == "📦 Pending Stock-in":
                    def format_func(x):
                        creator = creators_df[creators_df['name']==x].iloc[0]
                        urgent = creator.get('urgent_cans', 0)
                        total_value = creator.get('total_pending_value', 0)
                        return f"{x} ({creator['pending_cans']} CANs, {urgent} urgent, ${total_value/1000:.0f}K)"
                else:
                    def format_func(x):
                        creator = creators_df[creators_df['name']==x].iloc[0]
                        return f"{x} ({creator['active_pos']} POs, ${creator['total_outstanding_value']/1000:.0f}K)"
                
                selected_creators = st.multiselect(
                    "Choose PO creators",
                    options=creators_df['name'].tolist(),
                    default=None,
                    format_func=format_func
                )
                custom_recipients = []
                
            else:  # Custom Recipients
                selected_creators = []
                st.markdown("#### Enter Custom Recipients")
                custom_email_text = st.text_area(
                    "Email addresses (one per line)",
                    placeholder="john.doe@prostech.vn\njane.smith@prostech.vn\nprocurement.team@prostech.vn",
                    height=150,
                    help="Enter email addresses of recipients who should receive the notification"
                )
                
                if custom_email_text:
                    # Parse and validate emails
                    custom_emails = [email.strip() for email in custom_email_text.split('\n') if email.strip()]
                    valid_emails = []
                    invalid_emails = []
                    
                    for email in custom_emails:
                        if validate_email(email):
                            valid_emails.append(email)
                        else:
                            invalid_emails.append(email)
                    
                    if invalid_emails:
                        st.error(f"❌ Invalid email addresses: {', '.join(invalid_emails)}")
                    
                    if valid_emails:
                        custom_recipients = valid_emails
                        st.success(f"✅ {len(valid_emails)} valid email addresses")
                        
                        # Display valid emails
                        custom_df = pd.DataFrame({
                            'Email': valid_emails,
                            'Status': ['✅ Valid'] * len(valid_emails)
                        })
                        st.dataframe(custom_df, use_container_width=True, hide_index=True)
                else:
                    custom_recipients = []
            
            # Show selected creators/recipients summary
            if selection_mode != "Custom Recipients" and selected_creators:
                selected_df = creators_df[creators_df['name'].isin(selected_creators)]
                
                if notification_type == "🚨 Critical Alerts":
                    display_df = selected_df[['name', 'email', 'overdue_pos', 'pending_cans', 'max_days_overdue']].copy()
                    display_df.columns = ['Name', 'Email', 'Overdue POs', 'Pending CANs', 'Max Days Overdue']
                elif notification_type == "📦 Pending Stock-in":
                    # Display columns for pending stock-in
                    display_cols = ['name', 'email', 'pending_cans', 'urgent_cans', 'total_pending_value', 'max_days_pending']
                    display_cols = [col for col in display_cols if col in selected_df.columns]
                    display_df = selected_df[display_cols].copy()
                    
                    # Rename columns
                    rename_map = {
                        'name': 'Name',
                        'email': 'Email', 
                        'pending_cans': 'Pending CANs',
                        'urgent_cans': 'Urgent (>7 days)',
                        'total_pending_value': 'Total Value',
                        'max_days_pending': 'Max Days Pending'
                    }
                    display_df.rename(columns=rename_map, inplace=True)
                    
                    # Format value column
                    if 'Total Value' in display_df.columns:
                        display_df['Total Value'] = display_df['Total Value'].apply(lambda x: f"${x/1000:.0f}K")
                else:
                    display_df = selected_df[['name', 'email', 'active_pos', 'total_outstanding_value', 'international_pos']].copy()
                    display_df['total_outstanding_value'] = display_df['total_outstanding_value'].apply(lambda x: f"${x/1000:.0f}K")
                    display_df.columns = ['Name', 'Email', 'Active POs', 'Outstanding Value', 'Intl POs']
                
                st.dataframe(display_df, use_container_width=True, hide_index=True)
            elif selection_mode == "Custom Recipients" and not custom_recipients:
                st.warning("Please enter at least one valid email address")
        else:
            if notification_type == "🚨 Critical Alerts":
                st.warning("No creators with overdue POs or pending CANs found")
            elif notification_type == "📦 Pending Stock-in":
                st.warning("No creators with pending stock-in items found")
            else:
                st.warning("No creators with active POs found")

# CC settings section (back in col2)
with col2:
    cc_emails = []
    
    if notification_type == "🛃 Custom Clearance":
        # Default recipient for customs
        default_recipient = st.text_input(
            "Primary Recipient",
            value="custom.clearance@prostech.vn",
            disabled=True,
            help="Default email for customs clearance team"
        )
    else:
        # CC to managers for creator notifications
        include_cc = st.checkbox("Include CC to managers", value=True)
        
        if include_cc and selected_creators and not creators_df.empty and selection_mode != "Custom Recipients":
            # Get unique manager emails from selected creators
            selected_df = creators_df[creators_df['name'].isin(selected_creators)]
            
            # Check if manager_email column exists
            if 'manager_email' in selected_df.columns:
                manager_emails = selected_df[selected_df['manager_email'].notna()]['manager_email'].unique().tolist()
                
                if manager_emails:
                    st.info(f"Managers will be CC'd: {', '.join(manager_emails)}")
                    cc_emails.extend(manager_emails)
            else:
                if notification_type == "🚨 Critical Alerts":
                    st.info("Manager CC not available for Critical Alerts. You can add managers manually below.")
    
    # Additional CC emails
    st.markdown("#### Additional CC Recipients")
    additional_cc = st.text_area(
        "CC Email addresses (one per line)",
        placeholder="manager@prostech.vn\nlogistics.manager@prostech.vn",
        help="Add any additional recipients for CC",
        height=100
    )
    
    if additional_cc:
        additional_emails = [email.strip() for email in additional_cc.split('\n') if email.strip()]
        valid_cc = []
        invalid_cc = []
        
        for email in additional_emails:
            if validate_email(email):
                valid_cc.append(email)
            else:
                invalid_cc.append(email)
        
        if invalid_cc:
            st.warning(f"⚠️ Invalid CC emails will be skipped: {', '.join(invalid_cc)}")
        
        if valid_cc:
            cc_emails.extend(valid_cc)
    
    # Remove duplicates from CC
    cc_emails = list(dict.fromkeys(cc_emails))
    
    if cc_emails:
        st.caption(f"Total CC recipients: {len(cc_emails)}")

st.markdown("---")

# Continuation of Email_Notifications.py - Part 3

# Preview section
if notification_type == "🛃 Custom Clearance":
    if st.button("👁️ Preview Email Content", type="secondary"):
        with st.spinner("Generating customs clearance preview..."):
            try:
                # Get international POs
                po_filters = {
                    'etd_from': datetime.now().date(),
                    'etd_to': datetime.now().date() + timedelta(weeks=weeks_ahead)
                }
                intl_pos = data_loader.load_po_data_for_customs(po_filters)
                
                # Get international CANs
                can_filters = {
                    'arrival_date_from': datetime.now().date(),
                    'arrival_date_to': datetime.now().date() + timedelta(weeks=weeks_ahead)
                }
                intl_cans = data_loader.load_can_data_for_customs(can_filters)
                
                if intl_pos is not None and (not intl_pos.empty or (intl_cans is not None and not intl_cans.empty)):
                    st.subheader("📧 Preview - Custom Clearance Schedule")
                    
                    # Tab view for POs and CANs
                    tab1, tab2 = st.tabs(["📅 Purchase Orders ETD", "📦 Container Arrivals"])
                    
                    with tab1:
                        if intl_pos is not None and not intl_pos.empty:
                            # Group by country
                            country_summary = intl_pos.groupby('vendor_country_name').agg({
                                'po_number': 'nunique',
                                'vendor_name': 'nunique',
                                'outstanding_arrival_amount_usd': 'sum'
                            }).reset_index()
                            
                            st.markdown("#### PO Summary by Country")
                            country_summary.columns = ['Country', 'PO Count', 'Vendors', 'Value USD']
                            country_summary['Value USD'] = country_summary['Value USD'].apply(lambda x: f"${x:,.0f}")
                            st.dataframe(country_summary, use_container_width=True, hide_index=True)
                            
                            # Show sample POs
                            st.markdown("#### Sample International POs (First 10)")
                            display_cols = ['etd', 'po_number', 'vendor_name', 'vendor_country_name', 
                                        'pt_code', 'product_name', 'pending_standard_arrival_quantity', 
                                        'outstanding_arrival_amount_usd']
                            display_df = intl_pos.head(10)[display_cols]
                            st.dataframe(display_df, use_container_width=True, hide_index=True)
                            
                            st.caption(f"Total {len(intl_pos)} international PO lines")
                        else:
                            st.info("No international POs found for the selected period")
                    
                    with tab2:
                        if intl_cans is not None and not intl_cans.empty:
                            # Group by arrival date
                            date_summary = intl_cans.groupby(['arrival_date', 'vendor_country_name']).agg({
                                'arrival_note_number': 'nunique',
                                'vendor': 'nunique',
                                'pending_value_usd': 'sum'
                            }).reset_index()
                            
                            st.markdown("#### CAN Summary by Arrival Date")
                            date_summary.columns = ['Arrival Date', 'Country', 'CAN Count', 'Vendors', 'Value USD']
                            date_summary['Value USD'] = date_summary['Value USD'].apply(lambda x: f"${x:,.0f}")
                            st.dataframe(date_summary, use_container_width=True, hide_index=True)
                            
                            # Show sample CANs
                            st.markdown("#### Sample Container Arrivals (First 10)")
                            display_cols = ['arrival_date', 'arrival_note_number', 'vendor', 'vendor_country_name',
                                        'pt_code', 'product_name', 'pending_quantity', 'pending_value_usd']
                            display_df = intl_cans.head(10)[display_cols]
                            st.dataframe(display_df, use_container_width=True, hide_index=True)
                            
                            st.caption(f"Total {len(intl_cans)} international CAN lines")
                        else:
                            st.info("No international container arrivals found for the selected period")
                else:
                    st.warning(f"No international shipments found for the next {weeks_ahead} weeks")
            except Exception as e:
                st.error(f"Error generating preview: {str(e)}")
                logger.error(f"Error in customs preview: {e}")

elif (selected_creators or custom_recipients) and st.button("👁️ Preview Email Content", type="secondary"):
    with st.spinner("Generating preview..."):
        try:
            # Determine preview recipient
            if custom_recipients:
                # For custom recipients, show general preview
                preview_email = custom_recipients[0]
                preview_name = preview_email.split('@')[0].title()
                
                st.subheader(f"📧 Preview for Custom Recipients")
                st.caption(f"Sample preview for: {preview_email}")
                
                # Get data based on notification type
                if notification_type == "📅 PO Schedule":
                    filters = {
                        'etd_from': datetime.now().date(),
                        'etd_to': datetime.now().date() + timedelta(weeks=weeks_ahead)
                    }
                    preview_df = data_loader.load_po_data(filters)
                    
                    if preview_df is not None and not preview_df.empty:
                        col1, col2, col3, col4 = st.columns(4)
                        with col1:
                            st.metric("Total POs", preview_df['po_number'].nunique())
                        with col2:
                            st.metric("Vendors", preview_df['vendor_name'].nunique())
                        with col3:
                            st.metric("Total Value", f"${preview_df['outstanding_arrival_amount_usd'].sum()/1000000:.1f}M")
                        with col4:
                            overdue = preview_df[pd.to_datetime(preview_df['etd']) < datetime.now()]
                            st.metric("Overdue", len(overdue))
                        
                        st.info(f"Note: Custom recipients will receive a general PO schedule overview for the next {weeks_ahead} weeks")
                        
                        # Show sample POs
                        st.markdown("#### Sample POs (First 10)")
                        display_cols = ['etd', 'po_number', 'vendor_name', 'pt_code', 'product_name', 
                                      'pending_standard_arrival_quantity', 'outstanding_arrival_amount_usd']
                        st.dataframe(preview_df.head(10)[display_cols], use_container_width=True, hide_index=True)
                    else:
                        st.warning("No PO data found for preview")
                        
                elif notification_type == "🚨 Critical Alerts":
                    # Get all critical items
                    overdue_pos = data_loader.get_overdue_pos()
                    pending_cans = data_loader.load_can_pending_data({'min_days_pending': 7})
                    
                    col1, col2 = st.columns(2)
                    with col1:
                        st.metric("Overdue POs", len(overdue_pos) if overdue_pos is not None and not overdue_pos.empty else 0)
                    with col2:
                        st.metric("Pending CANs > 7 days", len(pending_cans) if pending_cans is not None and not pending_cans.empty else 0)
                    
                    if overdue_pos is not None and not overdue_pos.empty:
                        st.markdown("#### Overdue Purchase Orders (First 5)")
                        st.dataframe(overdue_pos.head(5), use_container_width=True, hide_index=True)
                    
                    if pending_cans is not None and not pending_cans.empty:
                        st.markdown("#### Pending Stock-in Items (First 5)")
                        display_cols = ['arrival_note_number', 'vendor', 'product_name', 'pt_code', 
                                      'pending_quantity', 'days_since_arrival']
                        st.dataframe(pending_cans.head(5)[display_cols], use_container_width=True, hide_index=True)
                        
                elif notification_type == "📦 Pending Stock-in":
                    # Get all pending CANs
                    pending_df = data_loader.load_can_pending_data()
                    
                    if pending_df is not None and not pending_df.empty:
                        # Summary by urgency
                        pending_df['urgency'] = pd.cut(pending_df['days_since_arrival'], 
                                                      bins=[0, 3, 7, 14, float('inf')],
                                                      labels=['Low', 'Medium', 'High', 'Critical'])
                        
                        urgency_summary = pending_df['urgency'].value_counts()
                        
                        col1, col2, col3, col4 = st.columns(4)
                        with col1:
                            st.metric("Total Items", len(pending_df))
                        with col2:
                            st.metric("Critical (>14 days)", urgency_summary.get('Critical', 0))
                        with col3:
                            st.metric("High (8-14 days)", urgency_summary.get('High', 0))
                        with col4:
                            st.metric("Total Value", f"${pending_df['pending_value_usd'].sum()/1000:.0f}K")
                        
                        # Show sample items
                        st.markdown("#### Sample Pending Items (First 10)")
                        display_cols = ['arrival_note_number', 'vendor', 'product_name',
                                       'pt_code', 'pending_quantity', 'days_since_arrival']
                        st.dataframe(pending_df.head(10)[display_cols], use_container_width=True, hide_index=True)
                    else:
                        st.warning("No pending stock-in items found")
                        
            else:
                # For selected creators, show creator-specific preview
                if not creators_df.empty and selected_creators:
                    preview_creator = creators_df[creators_df['name'] == selected_creators[0]].iloc[0]
                    preview_email = preview_creator['email']
                    preview_name = preview_creator['name']
                    
                    st.subheader(f"📧 Preview for {preview_name}")
                    
                    if notification_type == "📅 PO Schedule":
                        filters = {
                            'created_by': preview_email,
                            'etd_from': datetime.now().date(),
                            'etd_to': datetime.now().date() + timedelta(weeks=weeks_ahead)
                        }
                        preview_df = data_loader.load_po_data(filters)
                        
                        if preview_df is not None and not preview_df.empty:
                            col1, col2, col3, col4 = st.columns(4)
                            with col1:
                                st.metric("POs", preview_df['po_number'].nunique())
                            with col2:
                                st.metric("Vendors", preview_df['vendor_name'].nunique())
                            with col3:
                                st.metric("Value", f"${preview_df['outstanding_arrival_amount_usd'].sum()/1000:.0f}K")
                            with col4:
                                overdue = preview_df[pd.to_datetime(preview_df['etd']) < datetime.now()]
                                st.metric("Overdue", len(overdue))
                            
                            # Show sample POs
                            st.markdown("#### Sample POs")
                            display_cols = ['etd', 'po_number', 'vendor_name', 'pt_code', 'product_name', 
                                          'pending_standard_arrival_quantity', 'outstanding_arrival_amount_usd']
                            st.dataframe(preview_df.head(5)[display_cols], use_container_width=True, hide_index=True)
                        else:
                            st.info("No POs found for this creator")
                        
                    elif notification_type == "🚨 Critical Alerts":
                        overdue_pos = data_loader.get_overdue_pos_by_creator(preview_email)
                        pending_cans = data_loader.get_pending_cans_by_creator(preview_email)
                        
                        col1, col2 = st.columns(2)
                        with col1:
                            st.metric("Overdue POs", len(overdue_pos) if overdue_pos is not None and not overdue_pos.empty else 0)
                        with col2:
                            st.metric("Pending CANs > 7 days", len(pending_cans) if pending_cans is not None and not pending_cans.empty else 0)
                        
                        if overdue_pos is not None and not overdue_pos.empty:
                            st.markdown("#### Overdue Purchase Orders")
                            st.dataframe(overdue_pos.head(5), use_container_width=True, hide_index=True)
                        
                        if pending_cans is not None and not pending_cans.empty:
                            st.markdown("#### Pending Stock-in Items")
                            display_cols = ['arrival_note_number', 'vendor', 'product_name', 'pt_code', 
                                          'pending_quantity', 'days_since_arrival']
                            st.dataframe(pending_cans.head(5)[display_cols], use_container_width=True, hide_index=True)
                            
                    elif notification_type == "📦 Pending Stock-in":
                        preview_df = data_loader.get_pending_cans_by_creator(preview_email)
                        
                        if preview_df is not None and not preview_df.empty:
                            # Summary
                            preview_df['urgency'] = pd.cut(preview_df['days_since_arrival'], 
                                                          bins=[0, 3, 7, 14, float('inf')],
                                                          labels=['Low', 'Medium', 'High', 'Critical'])
                            
                            urgency_summary = preview_df['urgency'].value_counts()
                            
                            col1, col2, col3, col4 = st.columns(4)
                            with col1:
                                st.metric("Total Items", len(preview_df))
                            with col2:
                                st.metric("Critical", urgency_summary.get('Critical', 0))
                            with col3:
                                st.metric("High", urgency_summary.get('High', 0))
                            with col4:
                                st.metric("Value", f"${preview_df['pending_value_usd'].sum()/1000:.0f}K")
                            
                            # Show items
                            st.markdown("#### Sample Pending Items")
                            display_cols = ['arrival_note_number', 'vendor', 'product_name',
                                          'pt_code', 'pending_quantity', 'days_since_arrival']
                            st.dataframe(preview_df.head(10)[display_cols], use_container_width=True, hide_index=True)
                        else:
                            st.info("No pending stock-in items for this creator")
                else:
                    st.warning("No creator selected or creator data not available")
                    
        except Exception as e:
            st.error(f"Error generating preview: {str(e)}")
            logger.error(f"Error in preview: {e}", exc_info=True)


# Continuation of Email_Notifications.py - Part 4 (Final)

# Send emails section
if ((notification_type == "🛃 Custom Clearance" or selected_creators or custom_recipients) 
    and schedule_type == "Send Now"):
    
    st.markdown("---")
    st.subheader("📤 Send Emails")
    
    # Warning message based on notification type
    if notification_type == "🛃 Custom Clearance":
        st.warning(f"⚠️ You are about to send international PO schedule ({weeks_ahead} weeks) to custom.clearance@prostech.vn")
        if cc_emails:
            st.info(f"CC: {', '.join(cc_emails)}")
    elif custom_recipients:
        period_info = f" ({weeks_ahead} weeks)" if notification_type == "📅 PO Schedule" else ""
        st.warning(f"⚠️ You are about to send {notification_type}{period_info} emails to {len(custom_recipients)} custom recipients")
        if cc_emails:
            st.info(f"CC: {', '.join(cc_emails)}")
    elif selected_creators:
        if notification_type == "🚨 Critical Alerts":
            st.warning(f"⚠️ You are about to send CRITICAL ALERT emails to {len(selected_creators)} creators about overdue items")
        else:
            period_info = f" ({weeks_ahead} weeks)" if notification_type == "📅 PO Schedule" else ""
            st.warning(f"⚠️ You are about to send {notification_type}{period_info} emails to {len(selected_creators)} creators")
        if cc_emails:
            st.info(f"CC: {', '.join(cc_emails)}")
    
    confirm = st.checkbox("I confirm to send these emails")
    
    if confirm and st.button("🚀 Send Emails Now", type="primary"):
        # Progress bar
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        # Collect results
        results = []
        errors = []
        
        if notification_type == "🛃 Custom Clearance":
            # Send single email to customs team
            status_text.text("Sending customs clearance schedule...")
            
            try:
                # Get international POs
                po_filters = {
                    'etd_from': datetime.now().date(),
                    'etd_to': datetime.now().date() + timedelta(weeks=weeks_ahead)
                }
                intl_pos = data_loader.load_po_data_for_customs(po_filters)
                
                # Get international CANs
                can_filters = {
                    'arrival_date_from': datetime.now().date(),
                    'arrival_date_to': datetime.now().date() + timedelta(weeks=weeks_ahead)
                }
                intl_cans = data_loader.load_can_data_for_customs(can_filters)
                
                if (intl_pos is not None and not intl_pos.empty) or (intl_cans is not None and not intl_cans.empty):
                    success, message = email_sender.send_customs_clearance_email(
                        "custom.clearance@prostech.vn",
                        intl_pos if intl_pos is not None else pd.DataFrame(),
                        intl_cans if intl_cans is not None else pd.DataFrame(),
                        cc_emails=cc_emails if cc_emails else None,
                        weeks_ahead=weeks_ahead
                    )
                    
                    results.append({
                        'Recipient': 'Custom Clearance Team',
                        'Email': 'custom.clearance@prostech.vn',
                        'Status': '✅ Success' if success else '❌ Failed',
                        'POs': intl_pos['po_number'].nunique() if intl_pos is not None and not intl_pos.empty else 0,
                        'CANs': intl_cans['arrival_note_number'].nunique() if intl_cans is not None and not intl_cans.empty else 0,
                        'Message': message
                    })
                else:
                    results.append({
                        'Recipient': 'Custom Clearance Team',
                        'Email': 'custom.clearance@prostech.vn',
                        'Status': '⚠️ Skipped',
                        'POs': 0,
                        'CANs': 0,
                        'Message': 'No international shipments found'
                    })
                    
            except Exception as e:
                errors.append(f"Error sending customs email: {str(e)}")
                results.append({
                    'Recipient': 'Custom Clearance Team',
                    'Email': 'custom.clearance@prostech.vn',
                    'Status': '❌ Error',
                    'POs': 0,
                    'CANs': 0,
                    'Message': str(e)
                })
            
            progress_bar.progress(1.0)
            
        elif custom_recipients:
            # Send to custom recipients
            for idx, email in enumerate(custom_recipients):
                progress = (idx + 1) / len(custom_recipients)
                progress_bar.progress(progress)
                status_text.text(f"Sending to {email}... ({idx+1}/{len(custom_recipients)})")
                
                try:
                    recipient_name = email.split('@')[0].title()
                    
                    if notification_type == "📅 PO Schedule":
                        filters = {
                            'etd_from': datetime.now().date(),
                            'etd_to': datetime.now().date() + timedelta(weeks=weeks_ahead)
                        }
                        po_df = data_loader.load_po_data(filters)
                        
                        if po_df is not None and not po_df.empty:
                            success, message = email_sender.send_po_schedule_email(
                                email,
                                recipient_name,
                                po_df,
                                cc_emails=cc_emails,
                                is_custom_recipient=True,
                                weeks_ahead=weeks_ahead
                            )
                            
                            results.append({
                                'Recipient': recipient_name,
                                'Email': email,
                                'Status': '✅ Success' if success else '❌ Failed',
                                'POs': po_df['po_number'].nunique(),
                                'Message': message
                            })
                        else:
                            results.append({
                                'Recipient': recipient_name,
                                'Email': email,
                                'Status': '⚠️ Skipped',
                                'POs': 0,
                                'Message': 'No POs found'
                            })
                            
                    elif notification_type == "🚨 Critical Alerts":
                        overdue_pos = data_loader.get_overdue_pos()
                        pending_cans = data_loader.load_can_pending_data({'min_days_pending': 7})
                        
                        data_dict = {
                            'overdue_pos': overdue_pos if overdue_pos is not None else pd.DataFrame(),
                            'pending_stockin': pending_cans if pending_cans is not None else pd.DataFrame()
                        }
                        
                        if (overdue_pos is not None and not overdue_pos.empty) or (pending_cans is not None and not pending_cans.empty):
                            success, message = email_sender.send_critical_alerts_email(
                                email,
                                recipient_name,
                                data_dict,
                                cc_emails=cc_emails,
                                is_custom_recipient=True
                            )
                            
                            items_count = 0
                            if overdue_pos is not None:
                                items_count += len(overdue_pos)
                            if pending_cans is not None:
                                items_count += len(pending_cans)
                                
                            results.append({
                                'Recipient': recipient_name,
                                'Email': email,
                                'Status': '✅ Success' if success else '❌ Failed',
                                'Alerts': items_count,
                                'Message': message
                            })
                        else:
                            results.append({
                                'Recipient': recipient_name,
                                'Email': email,
                                'Status': '⚠️ Skipped',
                                'Alerts': 0,
                                'Message': 'No critical items found'
                            })
                            
                    elif notification_type == "📦 Pending Stock-in":
                        can_df = data_loader.load_can_pending_data()
                        
                        if can_df is not None and not can_df.empty:
                            success, message = email_sender.send_pending_stockin_email(
                                email,
                                recipient_name,
                                can_df,
                                cc_emails=cc_emails,
                                is_custom_recipient=True
                            )
                            
                            results.append({
                                'Recipient': recipient_name,
                                'Email': email,
                                'Status': '✅ Success' if success else '❌ Failed',
                                'Items': len(can_df),
                                'Message': message
                            })
                        else:
                            results.append({
                                'Recipient': recipient_name,
                                'Email': email,
                                'Status': '⚠️ Skipped',
                                'Items': 0,
                                'Message': 'No pending items found'
                            })
                        
                except Exception as e:
                    errors.append(f"Error for {email}: {str(e)}")
                    results.append({
                        'Recipient': email.split('@')[0].title(),
                        'Email': email,
                        'Status': '❌ Error',
                        'Items': 0,
                        'Message': str(e)
                    })
                    
        else:
            # Send to selected creators
            for idx, creator_name in enumerate(selected_creators):
                progress = (idx + 1) / len(selected_creators)
                progress_bar.progress(progress)
                status_text.text(f"Sending to {creator_name}... ({idx+1}/{len(selected_creators)})")
                
                try:
                    # Get creator info
                    creator_info = creators_df[creators_df['name'] == creator_name].iloc[0]
                    
                    # Check if we should include CC based on selection mode
                    current_cc_emails = cc_emails if selection_mode != "Custom Recipients" and include_cc else cc_emails
                    
                    # Get data based on notification type
                    if notification_type == "📅 PO Schedule":
                        filters = {
                            'created_by': creator_info['email'],
                            'etd_from': datetime.now().date(),
                            'etd_to': datetime.now().date() + timedelta(weeks=weeks_ahead)
                        }
                        po_df = data_loader.load_po_data(filters)
                        
                        # Validate data before sending
                        if po_df is None:
                            logger.error(f"load_po_data returned None for {creator_info['email']}")
                            results.append({
                                'Creator': creator_name,
                                'Email': creator_info['email'],
                                'Status': '❌ Error',
                                'POs': 0,
                                'Message': 'Failed to load PO data'
                            })
                            continue
                            
                        if po_df.empty:
                            results.append({
                                'Creator': creator_name,
                                'Email': creator_info['email'],
                                'Status': '⚠️ Skipped',
                                'POs': 0,
                                'Message': 'No POs found'
                            })
                            continue
                        
                        success, message = email_sender.send_po_schedule_email(
                            creator_info['email'],
                            creator_name,
                            po_df,
                            cc_emails=current_cc_emails,
                            weeks_ahead=weeks_ahead
                        )
                        
                        results.append({
                            'Creator': creator_name,
                            'Email': creator_info['email'],
                            'Status': '✅ Success' if success else '❌ Failed',
                            'POs': po_df['po_number'].nunique(),
                            'Message': message
                        })
                            
                    elif notification_type == "🚨 Critical Alerts":
                        overdue_pos = data_loader.get_overdue_pos_by_creator(creator_info['email'])
                        pending_cans = data_loader.get_pending_cans_by_creator(creator_info['email'])
                        
                        data_dict = {
                            'overdue_pos': overdue_pos if overdue_pos is not None else pd.DataFrame(),
                            'pending_stockin': pending_cans if pending_cans is not None else pd.DataFrame()
                        }
                        
                        if ((overdue_pos is not None and not overdue_pos.empty) or 
                            (pending_cans is not None and not pending_cans.empty)):
                            success, message = email_sender.send_critical_alerts_email(
                                creator_info['email'],
                                creator_name,
                                data_dict,
                                cc_emails=current_cc_emails
                            )
                            
                            alert_count = 0
                            if overdue_pos is not None:
                                alert_count += len(overdue_pos)
                            if pending_cans is not None:
                                alert_count += len(pending_cans)
                                
                            results.append({
                                'Creator': creator_name,
                                'Email': creator_info['email'],
                                'Status': '✅ Success' if success else '❌ Failed',
                                'Alerts': alert_count,
                                'Message': message
                            })
                        else:
                            results.append({
                                'Creator': creator_name,
                                'Email': creator_info['email'],
                                'Status': '⚠️ Skipped',
                                'Alerts': 0,
                                'Message': 'No critical items found'
                            })
                            
                    elif notification_type == "📦 Pending Stock-in":
                        can_df = data_loader.get_pending_cans_by_creator(creator_info['email'])
                        
                        if can_df is not None and not can_df.empty:
                            success, message = email_sender.send_pending_stockin_email(
                                creator_info['email'],
                                creator_name,
                                can_df,
                                cc_emails=current_cc_emails
                            )
                            
                            results.append({
                                'Creator': creator_name,
                                'Email': creator_info['email'],
                                'Status': '✅ Success' if success else '❌ Failed',
                                'Items': len(can_df),
                                'Message': message
                            })
                        else:
                            results.append({
                                'Creator': creator_name,
                                'Email': creator_info['email'],
                                'Status': '⚠️ Skipped',
                                'Items': 0,
                                'Message': 'No pending items found'
                            })
                        
                except Exception as e:
                    errors.append(f"Error for {creator_name}: {str(e)}")
                    results.append({
                        'Creator': creator_name,
                        'Email': 'N/A',
                        'Status': '❌ Error',
                        'Items': 0,
                        'Message': str(e)
                    })
        
        # Clear progress
        progress_bar.empty()
        status_text.empty()
        
        # Show results
        st.success(f"✅ Email process completed!")
        
        # Results summary
        results_df = pd.DataFrame(results)
        
        col1, col2, col3 = st.columns(3)
        with col1:
            success_count = len(results_df[results_df['Status'] == '✅ Success'])
            st.metric("Successful", success_count)
        with col2:
            failed_count = len(results_df[results_df['Status'] == '❌ Failed'])
            st.metric("Failed", failed_count)
        with col3:
            skipped_count = len(results_df[results_df['Status'] == '⚠️ Skipped'])
            st.metric("Skipped", skipped_count)
        
        # Detailed results
        st.dataframe(results_df, use_container_width=True, hide_index=True)
        
        # Show errors if any
        if errors:
            with st.expander("❌ Error Details"):
                for error in errors:
                    st.error(error)

# Help section
with st.expander("ℹ️ Help & Information"):
    st.markdown("""
    ### How to use this page:
    
    1. **Select Notification Type**:
       - **📅 PO Schedule**: Send upcoming arrivals for selected period (1-8 weeks)
       - **🚨 Critical Alerts**: Send overdue POs and urgent pending CANs
       - **📦 Pending Stock-in**: Send pending CAN items awaiting processing
       - **🛃 Custom Clearance**: Send international POs to customs team
    
    2. **Select Time Period** (for PO Schedule & Custom Clearance):
       - Choose how many weeks ahead to include (1-8 weeks)
       - Default is 4 weeks
    
    3. **Select Recipients**: 
       - **All Creators**: Send to all PO creators
       - **Selected Creators Only**: Choose specific creators
       - **Custom Recipients**: Enter any email addresses manually
       - For customs: Automatically sent to custom.clearance@prostech.vn
    
    4. **Configure CC Settings**: 
       - Include managers in CC (automatic detection for creators)
       - Add additional CC recipients for any notification type
    
    5. **Preview**: Check the email content before sending
    6. **Send**: Confirm and send emails
    
    ### Email Content by Type:
    
    #### 📅 PO Schedule:
    - For creators: POs they created for selected weeks
    - For custom recipients: All POs for selected weeks
    - Grouped by week and vendor
    - Excel attachment with full details
    - Calendar integration (.ics file)
    
    #### 🚨 Critical Alerts:
    - For creators: Their overdue POs and pending CANs
    - For custom recipients: All critical items
    - Sorted by urgency
    - Clear action items
    
    #### 📦 Pending Stock-in:
    - For creators: CANs from their POs
    - For custom recipients: All pending CANs
    - Categorized by days pending
    - Priority recommendations
    
    #### 🛃 Custom Clearance:
    - International vendor POs only
    - Grouped by country
    - Customs documentation checklist
    
    ### Notes:
    - Emails are sent from: inbound@prostech.vn
    - Custom recipients receive general overview (not filtered by creator)
    - All emails can include additional CC recipients
    - Only pending items (not completed) are included
    """)

# Footer
st.markdown("---")
st.caption(f"Email Notification System | Last updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")