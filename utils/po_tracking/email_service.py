"""
Email Notification Service for PO Tracking
Handles email notifications for ETD/ETA updates
"""

import logging
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, date
from typing import Optional, List
from utils.config import EMAIL_SENDER, EMAIL_PASSWORD
from sqlalchemy import text
import pytz

logger = logging.getLogger(__name__)

# Timezone configuration
VIETNAM_TZ = pytz.timezone('Asia/Ho_Chi_Minh')


class POEmailService:
    """Service for sending PO-related email notifications"""
    
    def __init__(self, db_engine=None):
        from utils.db import get_db_engine
        self.engine = db_engine or get_db_engine()
        self.sender_email = EMAIL_SENDER
        self.sender_password = EMAIL_PASSWORD
        self.smtp_server = "smtp.gmail.com"
        self.smtp_port = 587
    
    def get_creator_email(self, po_line_id: int) -> Optional[str]:
        """Get creator's email from database"""
        try:
            query = text("""
                SELECT u.email
                FROM product_purchase_orders ppo
                INNER JOIN purchase_orders po ON ppo.purchase_order_id = po.id
                INNER JOIN employees e ON po.created_by = e.keycloak_id
                INNER JOIN users u ON e.id = u.employee_id
                WHERE ppo.id = :po_line_id
                AND ppo.delete_flag = 0
                AND u.delete_flag = 0
                LIMIT 1
            """)
            
            with self.engine.connect() as conn:
                result = conn.execute(query, {'po_line_id': po_line_id}).fetchone()
                if result:
                    return result[0]
            return None
            
        except Exception as e:
            logger.error(f"Error getting creator email: {e}", exc_info=True)
            return None
    
    def send_etd_eta_update_notification(
        self,
        po_line_id: int,
        po_number: str,
        product_name: str,
        vendor_name: str,
        old_etd: Optional[date],
        new_etd: date,
        old_eta: Optional[date],
        new_eta: date,
        modifier_email: str,
        modifier_name: str,
        reason: Optional[str] = None
    ) -> bool:
        """
        Send email notification when ETD/ETA is updated
        
        Args:
            po_line_id: PO line ID
            po_number: PO number
            product_name: Product name
            vendor_name: Vendor name
            old_etd: Old ETD date
            new_etd: New ETD date
            old_eta: Old ETA date
            new_eta: New ETA date
            modifier_email: Email of person who made the change
            modifier_name: Name of person who made the change
            reason: Reason for the change
            
        Returns:
            bool: True if email sent successfully
        """
        try:
            # Get creator's email
            creator_email = self.get_creator_email(po_line_id)
            
            # Build recipient list
            to_emails = []
            if creator_email and creator_email != modifier_email:
                to_emails.append(creator_email)
            if modifier_email:
                to_emails.append(modifier_email)
            
            # Remove duplicates
            to_emails = list(set(to_emails))
            
            if not to_emails:
                logger.warning(f"No recipient emails found for PO line {po_line_id}")
                return False
            
            # CC address
            cc_emails = ["po.update@prostech.vn"]
            
            # Calculate day differences
            etd_diff = (new_etd - old_etd).days if old_etd else None
            eta_diff = (new_eta - old_eta).days if old_eta else None
            
            # Build email
            subject = f"🔔 PO ETD/ETA Updated - {po_number}"
            
            # Get current time with timezone
            now_vn = datetime.now(VIETNAM_TZ)
            
            body = self._build_email_body(
                po_number=po_number,
                po_line_id=po_line_id,
                product_name=product_name,
                vendor_name=vendor_name,
                old_etd=old_etd,
                new_etd=new_etd,
                old_eta=old_eta,
                new_eta=new_eta,
                etd_diff=etd_diff,
                eta_diff=eta_diff,
                modifier_name=modifier_name,
                reason=reason,
                update_time=now_vn  # Pass timezone-aware datetime
            )
            
            # Send email
            success = self._send_email(
                to_emails=to_emails,
                cc_emails=cc_emails,
                subject=subject,
                body=body
            )
            
            if success:
                logger.info(
                    f"Email sent successfully for PO line {po_line_id} to {to_emails}"
                )
            else:
                logger.error(f"Failed to send email for PO line {po_line_id}")
            
            return success
            
        except Exception as e:
            logger.error(f"Error sending ETD/ETA update notification: {e}", exc_info=True)
            return False
    
    def _build_email_body(
        self,
        po_number: str,
        po_line_id: int,
        product_name: str,
        vendor_name: str,
        old_etd: Optional[date],
        new_etd: date,
        old_eta: Optional[date],
        new_eta: date,
        etd_diff: Optional[int],
        eta_diff: Optional[int],
        modifier_name: str,
        reason: Optional[str],
        update_time: datetime  # Timezone-aware datetime
    ) -> str:
        """Build HTML email body"""
        
        def format_date(d):
            return d.strftime("%d %b %Y") if d else "Not set"
        
        def format_datetime_with_tz(dt):
            """Format datetime with timezone info"""
            return dt.strftime("%d %b %Y %H:%M:%S %Z")  # e.g., "15 Oct 2025 09:30:45 ICT"
        
        def format_diff(diff):
            if diff is None:
                return ""
            if diff > 0:
                return f'<span style="color: #e74c3c;">(+{diff} days)</span>'
            elif diff < 0:
                return f'<span style="color: #27ae60;">({diff} days)</span>'
            return '<span style="color: #95a5a6;">(No change)</span>'
        
        html = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <style>
        body {{
            font-family: Arial, sans-serif;
            line-height: 1.6;
            color: #333;
        }}
        .container {{
            max-width: 600px;
            margin: 0 auto;
            padding: 20px;
            background-color: #f9f9f9;
        }}
        .header {{
            background-color: #3498db;
            color: white;
            padding: 20px;
            text-align: center;
            border-radius: 5px 5px 0 0;
        }}
        .content {{
            background-color: white;
            padding: 30px;
            border-radius: 0 0 5px 5px;
        }}
        .info-section {{
            margin: 20px 0;
            padding: 15px;
            background-color: #ecf0f1;
            border-left: 4px solid #3498db;
        }}
        .date-change {{
            margin: 10px 0;
            padding: 10px;
            background-color: #fff3cd;
            border-left: 4px solid #ffc107;
        }}
        .footer {{
            margin-top: 20px;
            padding-top: 20px;
            border-top: 1px solid #ddd;
            font-size: 12px;
            color: #7f8c8d;
            text-align: center;
        }}
        table {{
            width: 100%;
            border-collapse: collapse;
            margin: 10px 0;
        }}
        td {{
            padding: 8px;
            border-bottom: 1px solid #ecf0f1;
        }}
        .label {{
            font-weight: bold;
            width: 40%;
            color: #7f8c8d;
        }}
        .value {{
            color: #2c3e50;
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h2>📦 Purchase Order Date Update</h2>
        </div>
        
        <div class="content">
            <h3>ETD/ETA dates have been updated for:</h3>
            
            <div class="info-section">
                <table>
                    <tr>
                        <td class="label">PO Number:</td>
                        <td class="value"><strong>{po_number}</strong></td>
                    </tr>
                    <tr>
                        <td class="label">PO Line ID:</td>
                        <td class="value">{po_line_id}</td>
                    </tr>
                    <tr>
                        <td class="label">Product:</td>
                        <td class="value">{product_name}</td>
                    </tr>
                    <tr>
                        <td class="label">Vendor:</td>
                        <td class="value">{vendor_name}</td>
                    </tr>
                </table>
            </div>
            
            <h3>📅 Date Changes:</h3>
            
            <div class="date-change">
                <table>
                    <tr>
                        <td class="label">ETD:</td>
                        <td class="value">
                            {format_date(old_etd)} → <strong>{format_date(new_etd)}</strong>
                            {format_diff(etd_diff)}
                        </td>
                    </tr>
                    <tr>
                        <td class="label">ETA:</td>
                        <td class="value">
                            {format_date(old_eta)} → <strong>{format_date(new_eta)}</strong>
                            {format_diff(eta_diff)}
                        </td>
                    </tr>
                </table>
            </div>
            
            {f'''
            <div class="info-section">
                <strong>Reason for Change:</strong><br>
                {reason}
            </div>
            ''' if reason else ''}
            
            <div class="info-section">
                <table>
                    <tr>
                        <td class="label">Updated by:</td>
                        <td class="value">{modifier_name}</td>
                    </tr>
                    <tr>
                        <td class="label">Update time:</td>
                        <td class="value">{format_datetime_with_tz(update_time)}</td>
                    </tr>
                </table>
            </div>
        </div>
        
        <div class="footer">
            <p>This is an automated notification from PO Tracking System.</p>
            <p>© {date.today().year} Prostech Vietnam. All rights reserved.</p>
        </div>
    </div>
</body>
</html>
"""
        return html
    
    def _send_email(
        self,
        to_emails: List[str],
        cc_emails: List[str],
        subject: str,
        body: str
    ) -> bool:
        """Send email via SMTP"""
        try:
            # Create message
            message = MIMEMultipart("alternative")
            message["Subject"] = subject
            message["From"] = self.sender_email
            message["To"] = ", ".join(to_emails)
            if cc_emails:
                message["Cc"] = ", ".join(cc_emails)
            
            # Attach HTML body
            html_part = MIMEText(body, "html")
            message.attach(html_part)
            
            # Combine To and CC for actual sending
            all_recipients = to_emails + cc_emails
            
            # Send email
            with smtplib.SMTP(self.smtp_server, self.smtp_port) as server:
                server.starttls()
                server.login(self.sender_email, self.sender_password)
                server.send_message(message)
            
            logger.info(f"Email sent: {subject} to {all_recipients}")
            return True
            
        except Exception as e:
            logger.error(f"Error sending email: {e}", exc_info=True)
            return False