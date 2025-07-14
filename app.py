# app.py - Main Inbound Logistics Dashboard

import streamlit as st
from datetime import datetime, timedelta
import pandas as pd
from utils.auth import AuthManager
from utils.data_loader import InboundDataLoader
import plotly.graph_objects as go
import plotly.express as px
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Page config
st.set_page_config(
    page_title="Inbound Logistics Dashboard",
    page_icon="📦",
    layout="wide",
    initial_sidebar_state="expanded"
)

# App version
APP_VERSION = "1.0.0"

# Initialize auth manager
auth_manager = AuthManager()

# CSS styling
st.markdown("""
<style>
    .main-header {
        font-size: 2.5rem;
        font-weight: bold;
        color: #2e7d32;
        text-align: center;
        margin-bottom: 2rem;
    }
    .kpi-card {
        background-color: #f0f2f6;
        padding: 1.5rem;
        border-radius: 10px;
        text-align: center;
        box-shadow: 0 2px 4px rgba(0,0,0,0.1);
    }
    .kpi-value {
        font-size: 2rem;
        font-weight: bold;
        color: #2e7d32;
    }
    .kpi-label {
        font-size: 1rem;
        color: #666;
        margin-top: 0.5rem;
    }
    .alert-card {
        background-color: #fff3cd;
        border: 1px solid #ffeeba;
        color: #856404;
        padding: 1rem;
        border-radius: 5px;
        margin: 1rem 0;
    }
    .urgent-alert {
        background-color: #f8d7da;
        border: 1px solid #f5c6cb;
        color: #721c24;
    }
    .status-overdue {
        color: #d32f2f;
        font-weight: bold;
    }
    .status-pending {
        color: #f57c00;
        font-weight: bold;
    }
    .status-completed {
        color: #388e3c;
    }
</style>
""", unsafe_allow_html=True)

def show_login_page():
    """Display login page"""
    st.markdown('<h1 class="main-header">📦 Inbound Logistics Dashboard</h1>', unsafe_allow_html=True)
    
    col1, col2, col3 = st.columns([1, 2, 1])
    
    with col2:
        with st.form("login_form"):
            st.subheader("🔐 Login")
            username = st.text_input("Username", placeholder="Enter your username")
            password = st.text_input("Password", type="password", placeholder="Enter your password")
            
            if st.form_submit_button("Login", use_container_width=True, type="primary"):
                if username and password:
                    success, user_info = auth_manager.authenticate(username, password)
                    if success:
                        auth_manager.login(user_info)
                        st.success("✅ Login successful!")
                        st.rerun()
                    else:
                        st.error(f"❌ {user_info.get('error', 'Login failed')}")
                else:
                    st.error("Please enter both username and password")

def show_main_dashboard():
    """Display main dashboard"""
    # Sidebar
    with st.sidebar:
        st.markdown(f"### 👤 {auth_manager.get_user_display_name()}")
        st.markdown(f"**Role:** {st.session_state.get('user_role', 'N/A')}")
        st.markdown("---")
        
        # Navigation info
        st.info("📌 Use the navigation menu above to access different sections")
        
        # App version
        st.caption(f"Version: {APP_VERSION}")
        
        st.markdown("---")
        if st.button("🚪 Logout", use_container_width=True):
            auth_manager.logout()
            st.rerun()
    
    # Main content
    st.markdown('<h1 class="main-header">📦 Inbound Logistics Dashboard</h1>', unsafe_allow_html=True)
    
    # Load data
    data_loader = InboundDataLoader()
    
    try:
        with st.spinner("Loading inbound data..."):
            # Load PO data
            po_df = data_loader.load_po_data()
            # Load CAN pending data
            can_df = data_loader.load_can_pending_data()
        
        if po_df is not None and not po_df.empty:
            # Date calculations
            today = datetime.now().date()
            week_start = today - timedelta(days=today.weekday())
            week_end = week_start + timedelta(days=6)
            
            # Filter data for calculations
            # Pending POs
            pending_pos = po_df[po_df['status'].isin(['PENDING', 'IN_PROCESS'])]
            
            # Overdue POs (ETD passed but not completed)
            po_df['etd'] = pd.to_datetime(po_df['etd'])
            overdue_pos = po_df[(po_df['etd'].dt.date < today) & 
                               (po_df['status'] != 'COMPLETED')]
            
            # This week arrivals
            this_week_arrivals = po_df[(po_df['etd'].dt.date >= week_start) & 
                                      (po_df['etd'].dt.date <= week_end)]
            
            # Pending stock-in from CAN
            if can_df is not None and not can_df.empty:
                pending_stockin_value = can_df['pending_value_usd'].sum()
                overdue_stockin = can_df[can_df['days_since_arrival'] > 7]
            else:
                pending_stockin_value = 0
                overdue_stockin = pd.DataFrame()
            
            # KPI Cards
            col1, col2, col3, col4, col5 = st.columns(5)
            
            with col1:
                st.markdown(f"""
                <div class="kpi-card">
                    <div class="kpi-value">{len(pending_pos):,}</div>
                    <div class="kpi-label">Pending POs</div>
                </div>
                """, unsafe_allow_html=True)
            
            with col2:
                st.markdown(f"""
                <div class="kpi-card">
                    <div class="kpi-value" style="color: #ff4444;">{len(overdue_pos):,}</div>
                    <div class="kpi-label">Overdue POs</div>
                </div>
                """, unsafe_allow_html=True)
            
            with col3:
                total_outstanding = po_df['outstanding_arrival_amount_usd'].sum()
                st.markdown(f"""
                <div class="kpi-card">
                    <div class="kpi-value">${total_outstanding/1000000:.1f}M</div>
                    <div class="kpi-label">In-Transit Value</div>
                </div>
                """, unsafe_allow_html=True)
            
            with col4:
                if can_df is not None and not can_df.empty:
                    pending_items = len(can_df)
                else:
                    pending_items = 0
                st.markdown(f"""
                <div class="kpi-card">
                    <div class="kpi-value" style="color: #f39c12;">{pending_items:,}</div>
                    <div class="kpi-label">Pending Stock-in</div>
                </div>
                """, unsafe_allow_html=True)
            
            with col5:
                st.markdown(f"""
                <div class="kpi-card">
                    <div class="kpi-value">{len(this_week_arrivals):,}</div>
                    <div class="kpi-label">This Week ETDs</div>
                </div>
                """, unsafe_allow_html=True)
            
            st.markdown("---")
            
            # Alert Section
            alerts = []
            
            if len(overdue_pos) > 0:
                alerts.append(f"⚠️ **{len(overdue_pos)} POs are overdue** - Please follow up with vendors")
            
            if len(overdue_stockin) > 0:
                alerts.append(f"📦 **{len(overdue_stockin)} CAN items pending stock-in > 7 days** - Coordinate with warehouse team")
            
            # Check for over-delivered POs
            over_delivered = po_df[po_df['is_over_delivered'] == 'Y']
            if len(over_delivered) > 0:
                alerts.append(f"📈 **{len(over_delivered)} POs with over-delivery** - Review and approve excess quantities")
            
            if alerts:
                alert_class = "urgent-alert" if len(overdue_pos) > 0 else "alert-card"
                st.markdown(f"""
                <div class="{alert_class}">
                    <h4>⚠️ Attention Required</h4>
                    {'<br>'.join(alerts)}
                </div>
                """, unsafe_allow_html=True)
            
            # Charts Section
            col1, col2 = st.columns(2)
            
            with col1:
                st.subheader("📊 PO Status Distribution")
                status_counts = po_df['status'].value_counts()
                
                # Map status to display names
                status_map = {
                    'COMPLETED': 'Completed',
                    'IN_PROCESS': 'In Process',
                    'PENDING': 'Pending',
                    'PENDING_INVOICING': 'Pending Invoice',
                    'PENDING_RECEIPT': 'Pending Receipt',
                    'OVER_DELIVERED': 'Over Delivered'
                }
                status_counts.index = status_counts.index.map(lambda x: status_map.get(x, x))
                
                fig1 = go.Figure(data=[
                    go.Bar(
                        x=status_counts.index,
                        y=status_counts.values,
                        marker_color=['#2ecc71' if 'Completed' in x else 
                                    '#3498db' if 'In Process' in x else
                                    '#f39c12' if 'Pending' in x else
                                    '#e74c3c' if 'Over' in x else
                                    '#95a5a6' for x in status_counts.index]
                    )
                ])
                fig1.update_layout(
                    xaxis_title="Status",
                    yaxis_title="Count",
                    showlegend=False,
                    height=300
                )
                st.plotly_chart(fig1, use_container_width=True)
            
            with col2:
                st.subheader("⏱️ Arrival Timeline (Next 30 days)")
                # Future arrivals
                future_arrivals = po_df[po_df['etd'].dt.date >= today].copy()
                future_arrivals = future_arrivals[future_arrivals['etd'].dt.date <= today + timedelta(days=30)]
                
                if not future_arrivals.empty:
                    # Group by week
                    future_arrivals['week'] = future_arrivals['etd'].dt.to_period('W').dt.start_time
                    weekly_arrivals = future_arrivals.groupby('week').agg({
                        'po_line_id': 'count',
                        'total_amount_usd': 'sum'
                    }).reset_index()
                    
                    fig2 = go.Figure()
                    fig2.add_trace(go.Bar(
                        x=weekly_arrivals['week'],
                        y=weekly_arrivals['po_line_id'],
                        name='PO Lines',
                        yaxis='y',
                        marker_color='#3498db'
                    ))
                    fig2.add_trace(go.Scatter(
                        x=weekly_arrivals['week'],
                        y=weekly_arrivals['total_amount_usd'],
                        name='Value (USD)',
                        yaxis='y2',
                        line=dict(color='#e74c3c', width=3)
                    ))
                    
                    fig2.update_layout(
                        xaxis_title="Week",
                        yaxis=dict(title="PO Lines", side="left"),
                        yaxis2=dict(title="Value (USD)", overlaying="y", side="right"),
                        height=300,
                        hovermode='x unified'
                    )
                    st.plotly_chart(fig2, use_container_width=True)
                else:
                    st.info("No upcoming arrivals in the next 30 days")
            
            # Vendor Performance Section
            st.markdown("---")
            st.subheader("🏭 Top Vendors by Open PO Value")
            
            # Get top vendors by outstanding value
            vendor_summary = po_df[po_df['status'] != 'COMPLETED'].groupby('vendor_name').agg({
                'po_line_id': 'count',
                'outstanding_arrival_amount_usd': 'sum',
                'is_over_delivered': lambda x: (x == 'Y').sum()
            }).reset_index()
            vendor_summary.columns = ['Vendor', 'Open POs', 'Outstanding Value (USD)', 'Over Deliveries']
            vendor_summary = vendor_summary.sort_values('Outstanding Value (USD)', ascending=False).head(10)
            
            # Format the dataframe
            vendor_summary['Outstanding Value (USD)'] = vendor_summary['Outstanding Value (USD)'].apply(lambda x: f"${x:,.0f}")
            
            st.dataframe(
                vendor_summary,
                use_container_width=True,
                hide_index=True
            )
            
            # Pending Stock-in Summary
            if can_df is not None and not can_df.empty:
                st.markdown("---")
                st.subheader("📦 Pending Stock-in Summary")
                
                col1, col2, col3 = st.columns(3)
                
                with col1:
                    st.metric("Total Pending Items", f"{len(can_df):,}")
                
                with col2:
                    st.metric("Pending Value", f"${pending_stockin_value:,.0f}")
                
                with col3:
                    avg_days = can_df['days_since_arrival'].mean()
                    st.metric("Avg Days Pending", f"{avg_days:.1f}")
                
                # Show top pending items
                st.markdown("#### ⏰ Longest Pending Items")
                top_pending = can_df.nlargest(5, 'days_since_arrival')[[
                    'arrival_note_number', 'vendor', 'product_name', 'pt_code',
                    'pending_quantity', 'days_since_arrival', 'can_status'
                ]].copy()
                
                top_pending['days_since_arrival'] = top_pending['days_since_arrival'].apply(lambda x: f"{x} days")
                
                # Apply conditional formatting
                def highlight_overdue(row):
                    if int(row['days_since_arrival'].split()[0]) > 7:
                        return ['background-color: #ffcccb'] * len(row)
                    elif int(row['days_since_arrival'].split()[0]) > 3:
                        return ['background-color: #ffe4b5'] * len(row)
                    return [''] * len(row)
                
                styled_df = top_pending.style.apply(highlight_overdue, axis=1)
                st.dataframe(styled_df, use_container_width=True, hide_index=True)
            
        else:
            st.warning("No purchase order data available")
            
    except Exception as e:
        st.error(f"Error loading data: {str(e)}")
        logger.error(f"Dashboard error: {e}")

def main():
    """Main application entry point"""
    # Check authentication
    if not auth_manager.check_session():
        show_login_page()
    else:
        show_main_dashboard()

if __name__ == "__main__":
    main()