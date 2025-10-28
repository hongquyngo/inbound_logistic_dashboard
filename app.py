# app.py - Simplified Main Entry Point

import streamlit as st
from datetime import datetime
from utils.auth import AuthManager

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

# Simple CSS styling
st.markdown("""
<style>
    .main-header {
        font-size: 2.5rem;
        font-weight: bold;
        color: #2e7d32;
        text-align: center;
        margin-bottom: 2rem;
    }
    .greeting-card {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        padding: 2rem;
        border-radius: 15px;
        color: white;
        text-align: center;
        box-shadow: 0 4px 6px rgba(0,0,0,0.1);
    }
    .greeting-text {
        font-size: 1.8rem;
        font-weight: 600;
        margin-bottom: 1rem;
    }
    .welcome-message {
        font-size: 1.2rem;
        opacity: 0.9;
    }
</style>
""", unsafe_allow_html=True)

def show_login_page():
    """Display simple login page"""
    st.markdown('<h1 class="main-header">📦 Inbound Logistics Dashboard</h1>', unsafe_allow_html=True)
    
    col1, col2, col3 = st.columns([1, 2, 1])
    
    with col2:
        st.markdown("### 🔐 Login")
        st.markdown("---")
        
        with st.form("login_form"):
            username = st.text_input("Username", placeholder="Enter your username")
            password = st.text_input("Password", type="password", placeholder="Enter your password")
            
            col_btn1, col_btn2 = st.columns(2)
            with col_btn1:
                submit = st.form_submit_button("Login", use_container_width=True, type="primary")
            with col_btn2:
                st.form_submit_button("Clear", use_container_width=True)
            
            if submit:
                if username and password:
                    success, user_info = auth_manager.authenticate(username, password)
                    if success:
                        auth_manager.login(user_info)
                        st.success("✅ Login successful!")
                        st.rerun()
                    else:
                        st.error(f"❌ {user_info.get('error', 'Login failed')}")
                else:
                    st.error("⚠️ Please enter both username and password")

def show_greeting_page():
    """Display greeting page after successful login"""
    # Sidebar
    with st.sidebar:
        st.markdown(f"### 👤 {auth_manager.get_user_display_name()}")
        st.markdown(f"**Role:** {st.session_state.get('user_role', 'User')}")
        st.markdown(f"**Email:** {st.session_state.get('user_email', 'N/A')}")
        
        st.markdown("---")
        
        # Navigation info
        st.info("📌 Use the navigation menu above to access different pages")
        
        st.markdown("---")
        
        # System info
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        st.caption(f"🕐 {current_time}")
        st.caption(f"📱 Version: {APP_VERSION}")
        
        st.markdown("---")
        
        # Logout button
        if st.button("🚪 Logout", use_container_width=True, type="primary"):
            auth_manager.logout()
            st.rerun()
    
    # Main content
    st.markdown('<h1 class="main-header">📦 Inbound Logistics Dashboard</h1>', unsafe_allow_html=True)
    
    # Get time-based greeting
    current_hour = datetime.now().hour
    if current_hour < 12:
        greeting = "Good Morning"
        emoji = "🌅"
    elif current_hour < 18:
        greeting = "Good Afternoon"
        emoji = "☀️"
    else:
        greeting = "Good Evening"
        emoji = "🌙"
    
    # Greeting card
    user_name = auth_manager.get_user_display_name()
    user_role = st.session_state.get('user_role', 'User')
    
    st.markdown(f"""
    <div class="greeting-card">
        <div class="greeting-text">{emoji} {greeting}, {user_name}!</div>
        <div class="welcome-message">Welcome to the Inbound Logistics Dashboard</div>
        <div class="welcome-message" style="font-size: 1rem; margin-top: 1rem;">
            You are logged in as <strong>{user_role}</strong>
        </div>
    </div>
    """, unsafe_allow_html=True)
    
    st.markdown("---")
    
    # Quick info section
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.info("""
        **📊 Dashboard Pages**
        
        Navigate using the sidebar menu to access:
        - PO Tracking
        - CAN Tracking
        - Email Notifications
        - Vendor Performance
        """)
    
    with col2:
        st.success("""
        **✨ Quick Actions**
        
        Common tasks:
        - Track purchase orders
        - Monitor container arrivals
        - Send email notifications
        - Analyze vendor performance
        """)
    
    with col3:
        st.warning("""
        **💡 Tips**
        
        - Use filters to find specific data
        - Export reports as needed
        - Set up email alerts
        - Check vendor metrics regularly
        """)
    
    st.markdown("---")
    
    # Additional info
    st.markdown("### 📌 Getting Started")
    
    with st.expander("ℹ️ How to use this system", expanded=False):
        st.markdown("""
        **Navigation:**
        1. Use the sidebar menu to access different pages
        2. Each page has specific functionality for tracking and management
        3. Most pages include filters and export options
        
        **Common Workflows:**
        - **PO Tracking:** Monitor purchase order status and delivery schedules
        - **CAN Tracking:** Track container arrival notes and pending stock-ins
        - **Email Notifications:** Send scheduled updates to vendors and team
        - **Vendor Performance:** Analyze vendor metrics and delivery performance
        
        **Need Help?**
        Contact the supply chain team or system administrator for assistance.
        """)
    
    # Footer
    st.markdown("---")
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.markdown(
            f"<div style='text-align: center; color: #666;'>"
            f"<small>© 2024 Prostech Asia - Inbound Logistics System v{APP_VERSION}</small>"
            f"</div>",
            unsafe_allow_html=True
        )

def main():
    """Main application entry point"""
    if not auth_manager.check_session():
        show_login_page()
    else:
        show_greeting_page()

if __name__ == "__main__":
    main()