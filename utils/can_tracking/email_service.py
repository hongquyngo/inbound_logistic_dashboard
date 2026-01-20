# utils/can_tracking/email_service.py

"""
Email Notification Service for CAN Tracking
Handles email notifications for CAN updates (arrival date, status, warehouse changes)
Supports both single and batch update notifications
"""

import logging
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, date
from typing import Optional, List, TYPE_CHECKING
from utils.config import EMAIL_SENDER, EMAIL_PASSWORD
from sqlalchemy import text
import pytz

# Import shared constants
from utils.can_tracking.constants import STATUS_DISPLAY

if TYPE_CHECKING:
    from utils.can_tracking.pending_changes import CANChange

logger = logging.getLogger(__name__)

# Timezone configuration
VIETNAM_TZ = pytz.timezone('Asia/Ho_Chi_Minh')


class CANEmailService:
    """Service for sending CAN-related email notifications"""
    
    def __init__(self, db_engine=None):
        from utils.db import get_db_engine
        self.engine = db_engine or get_db_engine()
        self.sender_email = EMAIL_SENDER
        self.sender_password = EMAIL_PASSWORD
        self.smtp_server = "smtp.gmail.com"
        self.smtp_port = 587
    
    def get_creator_email(self, arrival_note_number: str) -> Optional[str]:
        """Get creator's email from database"""
        try:
            query = text("""
                SELECT u.email
                FROM arrivals a
                INNER JOIN employees e ON a.created_by = e.keycloak_id
                INNER JOIN users u ON e.id = u.employee_id
                WHERE a.arrival_note_number = :arrival_note_number
                AND a.delete_flag = 0
                AND u.delete_flag = 0
                LIMIT 1
            """)
            
            with self.engine.connect() as conn:
                result = conn.execute(query, {'arrival_note_number': arrival_note_number}).fetchone()
                if result:
                    return result[0]
            return None
            
        except Exception as e:
            logger.error(f"Error getting creator email: {e}", exc_info=True)
            return None
    
    # ========================================================================
    # BATCH UPDATE NOTIFICATION (NEW)
    # ========================================================================
    
    def send_batch_update_notification(
        self,
        creator_email: str,
        changes: List['CANChange'],
        modifier_email: str,
        modifier_name: str
    ) -> bool:
        """
        Send consolidated email notification for multiple CAN updates to a single creator
        
        Args:
            creator_email: Email of the CAN creator
            changes: List of CANChange objects for this creator's CANs
            modifier_email: Email of the person making changes
            modifier_name: Name of the person making changes
            
        Returns:
            bool: True if email sent successfully
        """
        try:
            if not changes:
                return False
            
            # Build recipient list
            to_emails = [creator_email]
            if modifier_email and modifier_email != creator_email:
                to_emails.append(modifier_email)
            
            to_emails = list(set(to_emails))
            cc_emails = ["can.update@prostech.vn"]
            
            # Get current time with timezone
            now_vn = datetime.now(VIETNAM_TZ)
            
            # Build subject
            count = len(changes)
            if count == 1:
                subject = f"📦 CAN Updated - {changes[0].arrival_note_number}"
            else:
                subject = f"📦 CAN Batch Update - {count} items updated"
            
            # Build email body
            body = self._build_batch_email_body(
                changes=changes,
                modifier_name=modifier_name,
                update_time=now_vn
            )
            
            # Send email
            success = self._send_email(
                to_emails=to_emails,
                cc_emails=cc_emails,
                subject=subject,
                body=body
            )
            
            if success:
                logger.info(f"Batch email sent to {creator_email} for {count} CANs")
            else:
                logger.error(f"Failed to send batch email to {creator_email}")
            
            return success
            
        except Exception as e:
            logger.error(f"Error sending batch notification: {e}", exc_info=True)
            return False
    
    def _build_batch_email_body(
        self,
        changes: List['CANChange'],
        modifier_name: str,
        update_time: datetime
    ) -> str:
        """Build HTML email body for batch updates"""
        
        def format_date(d):
            if not d:
                return "Not set"
            if isinstance(d, str):
                try:
                    d = datetime.strptime(d, '%Y-%m-%d')
                except:
                    return d
            return d.strftime("%d %b %Y") if hasattr(d, 'strftime') else str(d)
        
        def format_datetime_with_tz(dt):
            return dt.strftime("%d %b %Y %H:%M:%S %Z")
        
        def format_status(status):
            return STATUS_DISPLAY.get(status, status)
        
        def format_diff(diff):
            if diff is None:
                return ""
            if diff > 0:
                return f'<span style="color: #e74c3c;">(+{diff} days)</span>'
            elif diff < 0:
                return f'<span style="color: #27ae60;">({diff} days)</span>'
            return ""
        
        # Build changes list HTML
        changes_html = ""
        for i, change in enumerate(changes, 1):
            change_items = ""
            
            if change.has_date_change:
                diff = change.date_diff_days
                change_items += f"""
                <li>Date: {format_date(change.original_arrival_date)} → 
                    <strong>{format_date(change.new_arrival_date)}</strong> 
                    {format_diff(diff)}</li>
                """
            
            if change.has_status_change:
                change_items += f"""
                <li>Status: {format_status(change.original_status)} → 
                    <strong>{format_status(change.new_status)}</strong></li>
                """
            
            if change.has_warehouse_change:
                change_items += f"""
                <li>Warehouse: {change.original_warehouse_name} → 
                    <strong>{change.new_warehouse_name}</strong></li>
                """
            
            reason_html = f'<p class="reason">Reason: {change.reason}</p>' if change.reason else ''
            
            changes_html += f"""
            <div class="can-item">
                <h3>{i}. {change.arrival_note_number}</h3>
                <p class="product">{change.product_name}</p>
                <p class="vendor">Vendor: {change.vendor_name}</p>
                <ul class="changes-list">
                    {change_items}
                </ul>
                {reason_html}
            </div>
            """
        
        count = len(changes)
        
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
            margin: 0;
            padding: 0;
        }}
        .container {{
            max-width: 650px;
            margin: 0 auto;
            padding: 20px;
            background-color: #f9f9f9;
        }}
        .header {{
            background: linear-gradient(135deg, #2c3e50 0%, #3498db 100%);
            color: white;
            padding: 25px;
            text-align: center;
            border-radius: 8px 8px 0 0;
        }}
        .header h1 {{
            margin: 0;
            font-size: 24px;
        }}
        .header .count {{
            background: rgba(255,255,255,0.2);
            padding: 5px 15px;
            border-radius: 20px;
            display: inline-block;
            margin-top: 10px;
            font-size: 14px;
        }}
        .content {{
            background-color: white;
            padding: 30px;
            border-radius: 0 0 8px 8px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
        }}
        .summary {{
            background-color: #e8f4f8;
            padding: 15px;
            border-radius: 5px;
            margin-bottom: 20px;
            border-left: 4px solid #3498db;
        }}
        .can-item {{
            border: 1px solid #e0e0e0;
            border-radius: 8px;
            padding: 15px;
            margin-bottom: 15px;
            background-color: #fafafa;
        }}
        .can-item h3 {{
            margin: 0 0 10px 0;
            color: #2c3e50;
            font-size: 16px;
        }}
        .can-item .product {{
            font-weight: 500;
            color: #555;
            margin: 5px 0;
        }}
        .can-item .vendor {{
            color: #777;
            font-size: 13px;
            margin: 5px 0;
        }}
        .changes-list {{
            margin: 10px 0;
            padding-left: 20px;
        }}
        .changes-list li {{
            margin: 5px 0;
            color: #333;
        }}
        .reason {{
            background-color: #fff3cd;
            padding: 8px 12px;
            border-radius: 4px;
            font-size: 13px;
            color: #856404;
            margin-top: 10px;
        }}
        .footer {{
            margin-top: 25px;
            padding-top: 20px;
            border-top: 1px solid #ddd;
            font-size: 12px;
            color: #7f8c8d;
            text-align: center;
        }}
        .modifier-info {{
            background-color: #f0f0f0;
            padding: 12px;
            border-radius: 5px;
            margin-top: 20px;
            font-size: 13px;
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>📦 Container Arrival Note Update</h1>
            <div class="count">{count} CAN{'s' if count > 1 else ''} Updated</div>
        </div>
        
        <div class="content">
            <div class="summary">
                <strong>{count}</strong> Container Arrival Note{'s have' if count > 1 else ' has'} been updated.
                Please review the changes below.
            </div>
            
            {changes_html}
            
            <div class="modifier-info">
                <strong>Updated by:</strong> {modifier_name}<br>
                <strong>Update time:</strong> {format_datetime_with_tz(update_time)}
            </div>
        </div>
        
        <div class="footer">
            <p>This is an automated notification from CAN Tracking System.</p>
            <p>© {date.today().year} Prostech Vietnam. All rights reserved.</p>
        </div>
    </div>
</body>
</html>
"""
        return html
    
    # ========================================================================
    # SINGLE UPDATE NOTIFICATION (ORIGINAL)
    # ========================================================================
    
    def send_can_update_notification(
        self,
        can_line_id: int,
        arrival_note_number: str,
        product_name: str,
        vendor_name: str,
        old_arrival_date: Optional[date],
        new_arrival_date: date,
        old_status: str,
        new_status: str,
        old_warehouse_name: str,
        new_warehouse_name: str,
        modifier_email: str,
        modifier_name: str,
        reason: Optional[str] = None
    ) -> bool:
        """
        Send email notification when a single CAN is updated
        
        Returns:
            bool: True if email sent successfully
        """
        try:
            # Get creator's email
            creator_email = self.get_creator_email(arrival_note_number)
            
            # Build recipient list
            to_emails = []
            if creator_email and creator_email != modifier_email:
                to_emails.append(creator_email)
            if modifier_email:
                to_emails.append(modifier_email)
            
            to_emails = list(set(to_emails))
            
            if not to_emails:
                logger.warning(f"No recipient emails found for CAN {arrival_note_number}")
                return False
            
            cc_emails = ["can.update@prostech.vn"]
            
            # Calculate date difference
            date_diff = (new_arrival_date - old_arrival_date).days if old_arrival_date else None
            
            # Determine what changed
            date_changed = new_arrival_date != old_arrival_date
            status_changed = new_status != old_status
            warehouse_changed = new_warehouse_name != old_warehouse_name
            
            # Build email
            subject = f"📦 CAN Updated - {arrival_note_number}"
            
            now_vn = datetime.now(VIETNAM_TZ)
            
            body = self._build_single_email_body(
                arrival_note_number=arrival_note_number,
                can_line_id=can_line_id,
                product_name=product_name,
                vendor_name=vendor_name,
                old_arrival_date=old_arrival_date,
                new_arrival_date=new_arrival_date,
                old_status=old_status,
                new_status=new_status,
                old_warehouse_name=old_warehouse_name,
                new_warehouse_name=new_warehouse_name,
                date_diff=date_diff,
                date_changed=date_changed,
                status_changed=status_changed,
                warehouse_changed=warehouse_changed,
                modifier_name=modifier_name,
                reason=reason,
                update_time=now_vn
            )
            
            success = self._send_email(
                to_emails=to_emails,
                cc_emails=cc_emails,
                subject=subject,
                body=body
            )
            
            if success:
                logger.info(f"Email sent successfully for CAN {arrival_note_number} to {to_emails}")
            else:
                logger.error(f"Failed to send email for CAN {arrival_note_number}")
            
            return success
            
        except Exception as e:
            logger.error(f"Error sending CAN update notification: {e}", exc_info=True)
            return False
    
    def _build_single_email_body(
        self,
        arrival_note_number: str,
        can_line_id: int,
        product_name: str,
        vendor_name: str,
        old_arrival_date: Optional[date],
        new_arrival_date: date,
        old_status: str,
        new_status: str,
        old_warehouse_name: str,
        new_warehouse_name: str,
        date_diff: Optional[int],
        date_changed: bool,
        status_changed: bool,
        warehouse_changed: bool,
        modifier_name: str,
        reason: Optional[str],
        update_time: datetime
    ) -> str:
        """Build HTML email body for single update"""
        
        def format_date(d):
            return d.strftime("%d %b %Y") if d else "Not set"
        
        def format_datetime_with_tz(dt):
            return dt.strftime("%d %b %Y %H:%M:%S %Z")
        
        def format_diff(diff):
            if diff is None:
                return ""
            if diff > 0:
                return f'<span style="color: #e74c3c;">(+{diff} days)</span>'
            elif diff < 0:
                return f'<span style="color: #27ae60;">({diff} days)</span>'
            return '<span style="color: #95a5a6;">(No change)</span>'
        
        def format_status(status):
            return STATUS_DISPLAY.get(status, status)
        
        # Build changes section
        changes_html = ""
        
        if date_changed:
            changes_html += f"""
            <tr>
                <td class="label">Arrival Date:</td>
                <td class="value">
                    {format_date(old_arrival_date)} → <strong>{format_date(new_arrival_date)}</strong>
                    {format_diff(date_diff)}
                </td>
            </tr>
            """
        
        if status_changed:
            changes_html += f"""
            <tr>
                <td class="label">Status:</td>
                <td class="value">
                    {format_status(old_status)} → <strong>{format_status(new_status)}</strong>
                </td>
            </tr>
            """
        
        if warehouse_changed:
            changes_html += f"""
            <tr>
                <td class="label">Warehouse:</td>
                <td class="value">
                    {old_warehouse_name} → <strong>{new_warehouse_name}</strong>
                </td>
            </tr>
            """
        
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
            background-color: #2c3e50;
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
            border-left: 4px solid #2c3e50;
        }}
        .change-section {{
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
            <h2>📦 Container Arrival Note Update</h2>
        </div>
        
        <div class="content">
            <h3>CAN has been updated:</h3>
            
            <div class="info-section">
                <table>
                    <tr>
                        <td class="label">CAN Number:</td>
                        <td class="value"><strong>{arrival_note_number}</strong></td>
                    </tr>
                    <tr>
                        <td class="label">CAN Line ID:</td>
                        <td class="value">{can_line_id}</td>
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
            
            <h3>📝 Changes:</h3>
            
            <div class="change-section">
                <table>
                    {changes_html}
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
            <p>This is an automated notification from CAN Tracking System.</p>
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
            message = MIMEMultipart("alternative")
            message["Subject"] = subject
            message["From"] = self.sender_email
            message["To"] = ", ".join(to_emails)
            if cc_emails:
                message["Cc"] = ", ".join(cc_emails)
            
            html_part = MIMEText(body, "html")
            message.attach(html_part)
            
            all_recipients = to_emails + cc_emails
            
            with smtplib.SMTP(self.smtp_server, self.smtp_port) as server:
                server.starttls()
                server.login(self.sender_email, self.sender_password)
                server.send_message(message)
            
            logger.info(f"Email sent: {subject} to {all_recipients}")
            return True
            
        except Exception as e:
            logger.error(f"Error sending email: {e}", exc_info=True)
            return False