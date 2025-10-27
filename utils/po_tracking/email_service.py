"""
Email Notification Service for PO Tracking - Enhanced with Bulk Updates
Handles email notifications for single and bulk ETD/ETA updates
"""

import logging
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, date
from typing import Optional, List, Dict, Any
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
    
    def get_creator_emails(self, po_line_ids: List[int]) -> List[str]:
        """
        Get unique creator emails for multiple PO lines
        
        Args:
            po_line_ids: List of PO line IDs
            
        Returns:
            List of unique creator emails
        """
        try:
            placeholders = ', '.join([f':id{i}' for i in range(len(po_line_ids))])
            
            query = text(f"""
                SELECT DISTINCT u.email
                FROM product_purchase_orders ppo
                INNER JOIN purchase_orders po ON ppo.purchase_order_id = po.id
                INNER JOIN employees e ON po.created_by = e.keycloak_id
                INNER JOIN users u ON e.id = u.employee_id
                WHERE ppo.id IN ({placeholders})
                AND ppo.delete_flag = 0
                AND u.delete_flag = 0
            """)
            
            params = {f'id{i}': line_id for i, line_id in enumerate(po_line_ids)}
            
            with self.engine.connect() as conn:
                result = conn.execute(query, params)
                emails = [row[0] for row in result if row[0]]
            
            return emails
            
        except Exception as e:
            logger.error(f"Error getting creator emails: {e}", exc_info=True)
            return []
    
    def send_bulk_etd_eta_update_notification(
        self,
        line_details: List[Dict[str, Any]],
        new_etd: date,
        new_eta: date,
        modifier_email: str,
        modifier_name: str,
        reason: Optional[str] = None
    ) -> bool:
        """
        Send consolidated email notification for bulk ETD/ETA updates
        
        Args:
            line_details: List of dicts with line info (po_line_id, po_number, product_name, etc.)
            new_etd: New ETD date
            new_eta: New ETA date
            modifier_email: Email of person who made the change
            modifier_name: Name of person who made the change
            reason: Reason for the change
            
        Returns:
            bool: True if email sent successfully
        """
        try:
            # Get unique creator emails
            po_line_ids = [detail['po_line_id'] for detail in line_details]
            creator_emails = self.get_creator_emails(po_line_ids)
            
            # Build recipient list
            to_emails = list(set(creator_emails + [modifier_email]))
            
            if not to_emails:
                logger.warning(f"No recipient emails found for bulk update of {len(line_details)} lines")
                return False
            
            # CC address
            cc_emails = ["po.update@prostech.vn"]
            
            # Get affected PO numbers
            affected_pos = list(set([detail['po_number'] for detail in line_details]))
            
            # Build email
            subject = f"📦 Bulk ETD/ETA Update - {len(line_details)} lines in {len(affected_pos)} PO(s)"
            
            # Get current time with timezone
            now_vn = datetime.now(VIETNAM_TZ)
            
            body = self._build_bulk_email_body(
                line_details=line_details,
                new_etd=new_etd,
                new_eta=new_eta,
                modifier_name=modifier_name,
                reason=reason,
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
                logger.info(
                    f"Bulk email sent for {len(line_details)} lines to {to_emails}"
                )
            else:
                logger.error(f"Failed to send bulk email for {len(line_details)} lines")
            
            return success
            
        except Exception as e:
            logger.error(f"Error sending bulk ETD/ETA update notification: {e}", exc_info=True)
            return False
    
    def _build_bulk_email_body(
        self,
        line_details: List[Dict[str, Any]],
        new_etd: date,
        new_eta: date,
        modifier_name: str,
        reason: Optional[str],
        update_time: datetime
    ) -> str:
        """Build HTML email body for bulk updates"""
        
        def format_date(d):
            return d.strftime("%d %b %Y") if d else "Not set"
        
        def format_datetime_with_tz(dt):
            return dt.strftime("%d %b %Y %H:%M:%S %Z")
        
        def calc_diff(old_date, new_date):
            if old_date and new_date:
                diff = (new_date - old_date).days
                if diff > 0:
                    return f'<span style="color: #e74c3c;">(+{diff} days)</span>'
                elif diff < 0:
                    return f'<span style="color: #27ae60;">({diff} days)</span>'
                return '<span style="color: #95a5a6;">(No change)</span>'
            return ''
        
        # Group by PO for better organization
        lines_by_po = {}
        for detail in line_details:
            po_num = detail['po_number']
            if po_num not in lines_by_po:
                lines_by_po[po_num] = []
            lines_by_po[po_num].append(detail)
        
        # Build line items HTML
        lines_html = ""
        for po_num, lines in sorted(lines_by_po.items()):
            lines_html += f"""
            <div style="margin: 15px 0; padding: 15px; background-color: #f8f9fa; border-left: 4px solid #3498db;">
                <strong style="color: #2c3e50;">PO: {po_num}</strong> ({len(lines)} line{'s' if len(lines) > 1 else ''})
                <table style="width: 100%; margin-top: 10px; font-size: 13px;">
                    <tr style="background-color: #e9ecef;">
                        <th style="padding: 8px; text-align: left;">Line ID</th>
                        <th style="padding: 8px; text-align: left;">Product</th>
                        <th style="padding: 8px; text-align: left;">PT Code</th>
                        <th style="padding: 8px; text-align: left;">Old ETD</th>
                        <th style="padding: 8px; text-align: left;">Old ETA</th>
                    </tr>
            """
            
            for line in lines:
                lines_html += f"""
                    <tr style="border-bottom: 1px solid #dee2e6;">
                        <td style="padding: 8px;">#{line['po_line_id']}</td>
                        <td style="padding: 8px;">{line['product_name']}</td>
                        <td style="padding: 8px;">{line['pt_code']}</td>
                        <td style="padding: 8px;">{format_date(line.get('old_etd'))}</td>
                        <td style="padding: 8px;">{format_date(line.get('old_eta'))}</td>
                    </tr>
                """
            
            lines_html += """
                </table>
            </div>
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
            max-width: 800px;
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
        .summary-box {{
            margin: 20px 0;
            padding: 20px;
            background-color: #fff3cd;
            border-left: 4px solid #ffc107;
            border-radius: 4px;
        }}
        .date-change {{
            margin: 20px 0;
            padding: 15px;
            background-color: #d4edda;
            border-left: 4px solid #28a745;
            border-radius: 4px;
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
        }}
        th {{
            background-color: #f8f9fa;
            font-weight: bold;
            padding: 10px;
            text-align: left;
        }}
        .highlight {{
            font-weight: bold;
            color: #2c3e50;
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h2>📦 Bulk Purchase Order Date Update</h2>
            <p style="margin: 5px 0;">ETD/ETA dates have been updated for multiple PO lines</p>
        </div>
        
        <div class="content">
            <div class="summary-box">
                <h3 style="margin-top: 0;">📋 Update Summary</h3>
                <table style="font-size: 14px;">
                    <tr>
                        <td style="padding: 5px; width: 40%; color: #7f8c8d;">Total Lines Updated:</td>
                        <td style="padding: 5px;"><strong>{len(line_details)}</strong></td>
                    </tr>
                    <tr>
                        <td style="padding: 5px; color: #7f8c8d;">Affected POs:</td>
                        <td style="padding: 5px;"><strong>{len(lines_by_po)}</strong></td>
                    </tr>
                    <tr>
                        <td style="padding: 5px; color: #7f8c8d;">PO Numbers:</td>
                        <td style="padding: 5px;">{', '.join(sorted(lines_by_po.keys()))}</td>
                    </tr>
                </table>
            </div>
            
            <div class="date-change">
                <h3 style="margin-top: 0;">📅 New Dates (applied to all lines)</h3>
                <table style="font-size: 15px;">
                    <tr>
                        <td style="padding: 8px; width: 30%;">New ETD:</td>
                        <td style="padding: 8px;"><strong>{format_date(new_etd)}</strong></td>
                    </tr>
                    <tr>
                        <td style="padding: 8px;">New ETA:</td>
                        <td style="padding: 8px;"><strong>{format_date(new_eta)}</strong></td>
                    </tr>
                </table>
            </div>
            
            {f'''
            <div style="margin: 20px 0; padding: 15px; background-color: #e7f3ff; border-left: 4px solid #2196F3;">
                <strong>💬 Reason for Change:</strong><br>
                <p style="margin: 10px 0;">{reason}</p>
            </div>
            ''' if reason else ''}
            
            <h3>📦 Affected PO Lines:</h3>
            {lines_html}
            
            <div style="margin: 20px 0; padding: 15px; background-color: #ecf0f1;">
                <table style="font-size: 13px;">
                    <tr>
                        <td style="padding: 5px; width: 30%; color: #7f8c8d;">Updated by:</td>
                        <td style="padding: 5px;"><strong>{modifier_name}</strong></td>
                    </tr>
                    <tr>
                        <td style="padding: 5px; color: #7f8c8d;">Update time:</td>
                        <td style="padding: 5px;">{format_datetime_with_tz(update_time)}</td>
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