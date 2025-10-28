# utils/email_notification/email_coordinator.py
"""
Email coordinator for inbound logistics notifications
Orchestrates email sending with HTML content, Excel attachments, and calendar files
"""

import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
import pandas as pd
from datetime import datetime
import logging
import os
from typing import List, Tuple

from utils.config import EMAIL_SENDER, EMAIL_PASSWORD
from utils.email_notification.email_templates import EmailTemplates
from utils.email_notification.excel_builder import ExcelBuilder
from utils.email_notification.calendar_builder import CalendarBuilder

logger = logging.getLogger(__name__)


class EmailCoordinator:
    """Coordinate email notification workflow"""
    
    def __init__(self, smtp_host: str = None, smtp_port: int = None):
        """Initialize email coordinator with SMTP configuration"""
        self.smtp_host = smtp_host or os.getenv("SMTP_HOST", "smtp.gmail.com")
        self.smtp_port = smtp_port or int(os.getenv("SMTP_PORT", "587"))
        self.sender_email = EMAIL_SENDER or os.getenv("EMAIL_SENDER", "inbound@prostech.vn")
        self.sender_password = EMAIL_PASSWORD or os.getenv("EMAIL_PASSWORD", "")
        
        # Initialize builders
        self.template_builder = EmailTemplates()
        self.excel_builder = ExcelBuilder()
        self.calendar_builder = CalendarBuilder()
        
        logger.info(f"Email coordinator initialized with: {self.sender_email} via {self.smtp_host}:{self.smtp_port}")
    
    # ========================
    # VALIDATION
    # ========================
    
    def _validate_config(self) -> bool:
        """Validate email configuration"""
        if not self.sender_email or not self.sender_password:
            logger.error("Email credentials not configured")
            return False
        return True
    
    # ========================
    # CORE SMTP SENDING
    # ========================
    
    def _send_email(self, msg: MIMEMultipart, recipient_email: str, 
                   cc_emails: List[str] = None) -> Tuple[bool, str]:
        """Send email via SMTP"""
        try:
            # Prepare recipient list
            recipients = [recipient_email]
            if cc_emails:
                recipients.extend(cc_emails)
            
            # Connect and send
            with smtplib.SMTP(self.smtp_host, self.smtp_port) as server:
                server.starttls()
                server.login(self.sender_email, self.sender_password)
                server.send_message(msg)
            
            logger.info(f"Email sent successfully to {recipient_email}")
            return True, "Email sent successfully"
            
        except smtplib.SMTPAuthenticationError:
            error_msg = "SMTP authentication failed - check credentials"
            logger.error(error_msg)
            return False, error_msg
        except smtplib.SMTPException as e:
            error_msg = f"SMTP error: {str(e)}"
            logger.error(error_msg)
            return False, error_msg
        except Exception as e:
            error_msg = f"Unexpected error sending email: {str(e)}"
            logger.error(error_msg, exc_info=True)
            return False, error_msg
    
    # ========================
    # PO SCHEDULE EMAIL
    # ========================
    
    def send_po_schedule(self, recipient_email: str, recipient_name: str,
                        po_df: pd.DataFrame, cc_emails: List[str] = None,
                        is_custom_recipient: bool = False, weeks_ahead: int = 4,
                        date_type: str = 'etd') -> Tuple[bool, str]:
        """Send PO schedule email with Excel and calendar attachments"""
        try:
            if not self._validate_config():
                return False, "Email configuration missing"
            
            # Validate input data
            if po_df is None or po_df.empty:
                logger.warning(f"No PO data for {recipient_email}")
                return False, "No PO data available"
            
            # Create message
            msg = MIMEMultipart('alternative')
            
            # Subject line
            date_type_upper = date_type.upper()
            if is_custom_recipient:
                msg['Subject'] = f"Purchase Order Schedule - Next {weeks_ahead} Week{'s' if weeks_ahead > 1 else ''} (by {date_type_upper}) - Overview"
            else:
                msg['Subject'] = f"Your Purchase Order Schedule - Next {weeks_ahead} Week{'s' if weeks_ahead > 1 else ''} (by {date_type_upper}) - {recipient_name}"
            
            msg['From'] = self.sender_email
            msg['To'] = recipient_email
            
            if cc_emails:
                msg['Cc'] = ', '.join(cc_emails)
            
            # Create HTML content
            try:
                html_content = self.template_builder.create_po_schedule_html(
                    po_df, recipient_name, is_custom_recipient, weeks_ahead, date_type
                )
                html_part = MIMEText(html_content, 'html')
                msg.attach(html_part)
            except Exception as e:
                logger.error(f"Error creating HTML content: {e}", exc_info=True)
                return False, f"Error creating HTML content: {str(e)}"
            
            # Create Excel attachment
            try:
                excel_data = self.excel_builder.create_po_schedule_excel(po_df, is_custom_recipient, date_type)
                if excel_data:
                    excel_part = MIMEBase('application', 'vnd.openxmlformats-officedocument.spreadsheetml.sheet')
                    excel_part.set_payload(excel_data.read())
                    encoders.encode_base64(excel_part)
                    
                    filename = f"po_schedule_{recipient_name.replace(' ', '_')}_{datetime.now().strftime('%Y%m%d')}.xlsx"
                    excel_part.add_header('Content-Disposition', f'attachment; filename="{filename}"')
                    msg.attach(excel_part)
                else:
                    logger.warning("Excel attachment creation returned None")
            except Exception as e:
                logger.error(f"Error creating Excel attachment: {e}", exc_info=True)
                # Continue without Excel attachment
            
            # Create calendar attachment
            try:
                ics_content = self.calendar_builder.create_po_schedule_ics(po_df, self.sender_email, date_type)
                
                if ics_content:
                    ics_part = MIMEBase('text', 'calendar')
                    ics_part.set_payload(ics_content.encode('utf-8'))
                    encoders.encode_base64(ics_part)
                    ics_part.add_header(
                        'Content-Disposition',
                        f'attachment; filename="po_schedule_{datetime.now().strftime("%Y%m%d")}.ics"'
                    )
                    msg.attach(ics_part)
            except Exception as e:
                logger.warning(f"Error creating calendar attachment: {e}")
                # Continue without calendar attachment
            
            # Send email
            return self._send_email(msg, recipient_email, cc_emails)
            
        except Exception as e:
            logger.error(f"Error sending PO schedule email: {e}", exc_info=True)
            return False, str(e)
    
    # ========================
    # CRITICAL ALERTS EMAIL
    # ========================
    
    def send_critical_alerts(self, recipient_email: str, recipient_name: str,
                            data_dict: dict, cc_emails: List[str] = None,
                            is_custom_recipient: bool = False,
                            date_type: str = 'etd') -> Tuple[bool, str]:
        """Send critical alerts email"""
        try:
            if not self._validate_config():
                return False, "Email configuration missing"
            
            # Extract data
            overdue_pos = data_dict.get('overdue_pos', pd.DataFrame())
            pending_stockin = data_dict.get('pending_stockin', pd.DataFrame())
            
            # Validate that at least one dataset has data
            if (overdue_pos.empty or overdue_pos is None) and (pending_stockin.empty or pending_stockin is None):
                logger.warning(f"No critical data for {recipient_email}")
                return False, "No critical items found"
            
            # Create message
            msg = MIMEMultipart('alternative')
            
            # Count critical items
            overdue_count = len(overdue_pos) if not overdue_pos.empty else 0
            pending_count = len(pending_stockin) if not pending_stockin.empty else 0
            
            date_type_upper = date_type.upper()
            if is_custom_recipient:
                msg['Subject'] = f"🚨 URGENT: {overdue_count} Overdue POs (by {date_type_upper}) & {pending_count} Pending Stock-ins"
            else:
                msg['Subject'] = f"🚨 URGENT: Your {overdue_count} Overdue POs (by {date_type_upper}) & {pending_count} Pending Stock-ins"
            
            msg['From'] = self.sender_email
            msg['To'] = recipient_email
            
            if cc_emails:
                msg['Cc'] = ', '.join(cc_emails)
            
            # Create HTML content
            try:
                html_content = self.template_builder.create_critical_alerts_html(
                    data_dict, recipient_name, is_custom_recipient, date_type
                )
                html_part = MIMEText(html_content, 'html')
                msg.attach(html_part)
            except Exception as e:
                logger.error(f"Error creating HTML content: {e}", exc_info=True)
                return False, f"Error creating HTML content: {str(e)}"
            
            # Create Excel attachment
            try:
                excel_data = self.excel_builder.create_critical_alerts_excel(data_dict, date_type)
                if excel_data:
                    excel_part = MIMEBase('application', 'vnd.openxmlformats-officedocument.spreadsheetml.sheet')
                    excel_part.set_payload(excel_data.read())
                    encoders.encode_base64(excel_part)
                    
                    filename = f"critical_alerts_{recipient_name.replace(' ', '_')}_{datetime.now().strftime('%Y%m%d')}.xlsx"
                    excel_part.add_header('Content-Disposition', f'attachment; filename="{filename}"')
                    msg.attach(excel_part)
            except Exception as e:
                logger.error(f"Error creating Excel attachment: {e}", exc_info=True)
                # Continue without Excel
            
            # Send email
            return self._send_email(msg, recipient_email, cc_emails)
            
        except Exception as e:
            logger.error(f"Error sending critical alerts email: {e}", exc_info=True)
            return False, str(e)
    
    # ========================
    # PENDING STOCK-IN EMAIL
    # ========================
    
    def send_pending_stockin(self, recipient_email: str, recipient_name: str,
                            can_df: pd.DataFrame, cc_emails: List[str] = None,
                            is_custom_recipient: bool = False) -> Tuple[bool, str]:
        """Send pending stock-in email"""
        try:
            if not self._validate_config():
                return False, "Email configuration missing"
            
            # Validate input data
            if can_df is None or can_df.empty:
                logger.warning(f"No pending stock-in data for {recipient_email}")
                return False, "No pending stock-in data available"
            
            # Create message
            msg = MIMEMultipart('alternative')
            
            # Count items by urgency
            critical_count = len(can_df[can_df['days_since_arrival'] > 14])
            urgent_count = len(can_df[can_df['days_since_arrival'] > 7])
            
            if is_custom_recipient:
                msg['Subject'] = f"Pending Stock-in Items: {len(can_df)} items ({critical_count} critical)"
            else:
                msg['Subject'] = f"Your Pending Stock-in Items: {len(can_df)} items ({critical_count} critical)"
            
            msg['From'] = self.sender_email
            msg['To'] = recipient_email
            
            if cc_emails:
                msg['Cc'] = ', '.join(cc_emails)
            
            # Create HTML content
            try:
                html_content = self.template_builder.create_pending_stockin_html(
                    can_df, recipient_name, is_custom_recipient
                )
                html_part = MIMEText(html_content, 'html')
                msg.attach(html_part)
            except Exception as e:
                logger.error(f"Error creating HTML content: {e}", exc_info=True)
                return False, f"Error creating HTML content: {str(e)}"
            
            # Create Excel attachment
            try:
                excel_data = self.excel_builder.create_pending_stockin_excel(can_df)
                if excel_data:
                    excel_part = MIMEBase('application', 'vnd.openxmlformats-officedocument.spreadsheetml.sheet')
                    excel_part.set_payload(excel_data.read())
                    encoders.encode_base64(excel_part)
                    
                    filename = f"pending_stockin_{recipient_name.replace(' ', '_')}_{datetime.now().strftime('%Y%m%d')}.xlsx"
                    excel_part.add_header('Content-Disposition', f'attachment; filename="{filename}"')
                    msg.attach(excel_part)
            except Exception as e:
                logger.error(f"Error creating Excel attachment: {e}", exc_info=True)
                # Continue without Excel
            
            # Create calendar reminder
            try:
                ics_content = self.calendar_builder.create_stockin_reminder_ics(can_df, self.sender_email)
                
                if ics_content:
                    ics_part = MIMEBase('text', 'calendar')
                    ics_part.set_payload(ics_content.encode('utf-8'))
                    encoders.encode_base64(ics_part)
                    ics_part.add_header(
                        'Content-Disposition',
                        f'attachment; filename="stockin_reminder_{datetime.now().strftime("%Y%m%d")}.ics"'
                    )
                    msg.attach(ics_part)
            except Exception as e:
                logger.warning(f"Error creating calendar reminder: {e}")
                # Continue without calendar
            
            # Send email
            return self._send_email(msg, recipient_email, cc_emails)
            
        except Exception as e:
            logger.error(f"Error sending pending stock-in email: {e}", exc_info=True)
            return False, str(e)
    
    # ========================
    # CUSTOMS CLEARANCE EMAIL
    # ========================
    
    def send_customs_clearance(self, recipient_email: str, recipient_name: str,
                               po_df: pd.DataFrame, can_df: pd.DataFrame = None,
                               cc_emails: List[str] = None, weeks_ahead: int = 4,
                               date_type: str = 'etd') -> Tuple[bool, str]:
        """Send customs clearance email"""
        try:
            if not self._validate_config():
                return False, "Email configuration missing"
            
            # Validate input data
            if (po_df is None or po_df.empty) and (can_df is None or can_df.empty):
                logger.warning(f"No customs clearance data for {recipient_email}")
                return False, "No customs clearance data available"
            
            # Create message
            msg = MIMEMultipart('alternative')
            
            date_type_upper = date_type.upper()
            msg['Subject'] = f"Customs Clearance Schedule - Next {weeks_ahead} Week{'s' if weeks_ahead > 1 else ''} (by {date_type_upper})"
            msg['From'] = self.sender_email
            msg['To'] = recipient_email
            
            if cc_emails:
                msg['Cc'] = ', '.join(cc_emails)
            
            # Create HTML content
            try:
                html_content = self.template_builder.create_customs_clearance_html(
                    po_df, can_df, weeks_ahead, date_type
                )
                html_part = MIMEText(html_content, 'html')
                msg.attach(html_part)
            except Exception as e:
                logger.error(f"Error creating HTML content: {e}", exc_info=True)
                return False, f"Error creating HTML content: {str(e)}"
            
            # Create Excel attachment
            try:
                excel_data = self.excel_builder.create_customs_clearance_excel(po_df, can_df, date_type)
                if excel_data:
                    excel_part = MIMEBase('application', 'vnd.openxmlformats-officedocument.spreadsheetml.sheet')
                    excel_part.set_payload(excel_data.read())
                    encoders.encode_base64(excel_part)
                    
                    filename = f"customs_clearance_{datetime.now().strftime('%Y%m%d')}.xlsx"
                    excel_part.add_header('Content-Disposition', f'attachment; filename="{filename}"')
                    msg.attach(excel_part)
            except Exception as e:
                logger.error(f"Error creating Excel attachment: {e}", exc_info=True)
                # Continue without Excel
            
            # Create calendar attachment
            try:
                ics_content = self.calendar_builder.create_customs_ics(po_df, can_df, self.sender_email, date_type)
                
                if ics_content:
                    ics_part = MIMEBase('text', 'calendar')
                    ics_part.set_payload(ics_content.encode('utf-8'))
                    encoders.encode_base64(ics_part)
                    ics_part.add_header(
                        'Content-Disposition',
                        f'attachment; filename="customs_schedule_{datetime.now().strftime("%Y%m%d")}.ics"'
                    )
                    msg.attach(ics_part)
            except Exception as e:
                logger.warning(f"Error creating calendar attachment: {e}")
                # Continue without calendar
            
            # Send email
            return self._send_email(msg, recipient_email, cc_emails)
            
        except Exception as e:
            logger.error(f"Error sending customs clearance email: {e}", exc_info=True)
            return False, str(e)
    
    # ========================
    # BATCH SENDING HELPER
    # ========================
    
    def send_batch(self, email_type: str, recipients: List[dict], 
                   data_getter_fn, **kwargs) -> List[dict]:
        """
        Helper method for batch email sending
        
        Args:
            email_type: Type of email ('po_schedule', 'critical_alerts', 'pending_stockin', 'customs')
            recipients: List of recipient dicts with 'email', 'name' keys
            data_getter_fn: Function to get data for each recipient
            **kwargs: Additional parameters to pass to send functions
            
        Returns:
            List of result dicts with 'recipient', 'success', 'message' keys
        """
        results = []
        
        for recipient in recipients:
            try:
                # Get data for this recipient
                data = data_getter_fn(recipient)
                
                # Select appropriate send method
                if email_type == 'po_schedule':
                    success, message = self.send_po_schedule(
                        recipient['email'],
                        recipient['name'],
                        data,
                        **kwargs
                    )
                elif email_type == 'critical_alerts':
                    success, message = self.send_critical_alerts(
                        recipient['email'],
                        recipient['name'],
                        data,
                        **kwargs
                    )
                elif email_type == 'pending_stockin':
                    success, message = self.send_pending_stockin(
                        recipient['email'],
                        recipient['name'],
                        data,
                        **kwargs
                    )
                elif email_type == 'customs':
                    success, message = self.send_customs_clearance(
                        recipient['email'],
                        recipient['name'],
                        data.get('po_df'),
                        data.get('can_df'),
                        **kwargs
                    )
                else:
                    success = False
                    message = f"Unknown email type: {email_type}"
                
                results.append({
                    'recipient': recipient['name'],
                    'email': recipient['email'],
                    'success': success,
                    'message': message
                })
                
            except Exception as e:
                logger.error(f"Error sending to {recipient['name']}: {e}", exc_info=True)
                results.append({
                    'recipient': recipient['name'],
                    'email': recipient['email'],
                    'success': False,
                    'message': str(e)
                })
        
        return results