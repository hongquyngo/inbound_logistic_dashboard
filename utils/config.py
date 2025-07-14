# utils/config.py - Configuration management for Outbound Logistics App

import os
import json
import logging
from dotenv import load_dotenv

# Initialize logger
logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)


def is_running_on_streamlit_cloud():
    """Detect if running on Streamlit Cloud"""
    try:
        import streamlit as st
        return "DB_CONFIG" in st.secrets
    except Exception:
        return False


# Detect environment
IS_RUNNING_ON_CLOUD = is_running_on_streamlit_cloud()

# Load configuration based on environment
if IS_RUNNING_ON_CLOUD:
    # Running on Streamlit Cloud
    import streamlit as st
    
    # Database configuration
    DB_CONFIG = dict(st.secrets["DB_CONFIG"])
    
    # API Keys
    EXCHANGE_RATE_API_KEY = st.secrets["API"]["EXCHANGE_RATE_API_KEY"]
    
    # Google Cloud Service Account
    GOOGLE_SERVICE_ACCOUNT_JSON = st.secrets["gcp_service_account"]
    
    # Email configuration
    EMAIL_SENDER = st.secrets["EMAIL"]["EMAIL_SENDER"]
    EMAIL_PASSWORD = st.secrets["EMAIL"]["EMAIL_PASSWORD"]
    
    # Logging
    logger.info("☁️ Running in STREAMLIT CLOUD")
    logger.info(f"✅ DB_CONFIG: {DB_CONFIG}")
    logger.info(f"✅ Exchange API Key (cloud): {len(EXCHANGE_RATE_API_KEY) if EXCHANGE_RATE_API_KEY else 0}")
    logger.info(f"✅ GCP Service Email: {GOOGLE_SERVICE_ACCOUNT_JSON.get('client_email', 'N/A')}")
    logger.info(f"✅ Email Sender: {EMAIL_SENDER}")

else:
    # Running locally
    load_dotenv()
    
    # Database configuration
    DB_CONFIG = {
        "host": os.getenv("DB_HOST", "erp-all-production.cx1uaj6vj8s5.ap-southeast-1.rds.amazonaws.com"),
        "port": int(os.getenv("DB_PORT", "3306")),
        "user": os.getenv("DB_USER", "streamlit_user"),
        "password": os.getenv("DB_PASSWORD"),
        "database": os.getenv("DB_DATABASE", "prostechvn")
    }
    
    # API Keys
    EXCHANGE_RATE_API_KEY = os.getenv("EXCHANGE_RATE_API_KEY")
    
    # Google Cloud Service Account
    GOOGLE_SERVICE_ACCOUNT_JSON = {}
    if os.path.exists("credentials.json"):
        try:
            with open("credentials.json", "r") as f:
                GOOGLE_SERVICE_ACCOUNT_JSON = json.load(f)
        except Exception as e:
            logger.warning(f"Could not load credentials.json: {e}")
    
    # Email configuration
    EMAIL_SENDER = os.getenv("EMAIL_SENDER", "outbound@prostech.vn")
    EMAIL_PASSWORD = os.getenv("EMAIL_PASSWORD", "")
    
    # Logging
    logger.info("💻 Running in LOCAL")
    logger.info(f"✅ DB_CONFIG (local): Host={DB_CONFIG['host']}, Database={DB_CONFIG['database']}")
    logger.info(f"✅ Exchange API Key (local): {len(EXCHANGE_RATE_API_KEY) if EXCHANGE_RATE_API_KEY else 0}")
    logger.info(f"✅ Google Service Account (local): {'Loaded' if GOOGLE_SERVICE_ACCOUNT_JSON else 'Missing'}")
    logger.info(f"✅ Email Sender (local): {EMAIL_SENDER}")
    logger.info(f"✅ Email Password (local): {'Set' if EMAIL_PASSWORD else 'Not Set'}")


# Additional configuration
APP_CONFIG = {
    "SESSION_TIMEOUT_HOURS": 8,
    "MAX_EMAIL_RECIPIENTS": 50,
    "DELIVERY_WEEKS_AHEAD": 4,
    "CACHE_TTL_SECONDS": 300,  # 5 minutes
    "TIMEZONE": "Asia/Ho_Chi_Minh",
}

# Export all configurations
__all__ = [
    'IS_RUNNING_ON_CLOUD',
    'DB_CONFIG',
    'EXCHANGE_RATE_API_KEY',
    'GOOGLE_SERVICE_ACCOUNT_JSON',
    'EMAIL_SENDER',
    'EMAIL_PASSWORD',
    'APP_CONFIG'
]