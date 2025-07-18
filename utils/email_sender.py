# utils/email_sender.py - Email sending module for inbound logistics

import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
import pandas as pd
from datetime import datetime, timedelta
import logging
import io
import os
from typing import List, Dict, Optional, Tuple
from utils.calendar_utils import InboundCalendarGenerator
from utils.config import EMAIL_SENDER, EMAIL_PASSWORD

logger = logging.getLogger(__name__)


class InboundEmailSender:
    """Handle email notifications for inbound logistics"""
    
    def __init__(self, smtp_host: str = None, smtp_port: int = None):
        """Initialize email sender with SMTP configuration"""
        self.smtp_host = smtp_host or os.getenv("SMTP_HOST", "smtp.gmail.com")
        self.smtp_port = smtp_port or int(os.getenv("SMTP_PORT", "587"))
        self.sender_email = EMAIL_SENDER or os.getenv("EMAIL_SENDER", "inbound@prostech.vn")
        self.sender_password = EMAIL_PASSWORD or os.getenv("EMAIL_PASSWORD", "")
        
        logger.info(f"Email sender initialized with: {self.sender_email} via {self.smtp_host}:{self.smtp_port}")
    
    def send_po_schedule_email(self, recipient_email: str, recipient_name: str, 
                              po_df: pd.DataFrame, cc_emails: List[str] = None,
                              is_custom_recipient: bool = False, weeks_ahead: int = 4,
                              date_type: str = 'etd') -> Tuple[bool, str]:
        """Send PO schedule email to recipient"""
        try:
            if not self._validate_config():
                return False, "Email configuration missing"
            
            # Validate input data
            if po_df is None or po_df.empty:
                logger.warning(f"No PO data for {recipient_email}")
                return False, "No PO data available"
            
            # Create message
            msg = MIMEMultipart('alternative')
            
            # Subject line with weeks and date type
            date_type_upper = date_type.upper()
            if is_custom_recipient:
                msg['Subject'] = f"Purchase Order Schedule - Next {weeks_ahead} Week{'s' if weeks_ahead > 1 else ''} (by {date_type_upper}) - Overview"
            else:
                msg['Subject'] = f"Your Purchase Order Schedule - Next {weeks_ahead} Week{'s' if weeks_ahead > 1 else ''} (by {date_type_upper}) - {recipient_name}"
            
            msg['From'] = self.sender_email
            msg['To'] = recipient_email
            
            if cc_emails:
                msg['Cc'] = ', '.join(cc_emails)
            
            # Create HTML content with error handling
            try:
                html_content = self._create_po_schedule_html(po_df, recipient_name, is_custom_recipient, weeks_ahead, date_type)
                html_part = MIMEText(html_content, 'html')
                msg.attach(html_part)
            except Exception as e:
                logger.error(f"Error creating HTML content: {e}", exc_info=True)
                return False, f"Error creating HTML content: {str(e)}"
            
            # Create Excel attachment with better error handling
            try:
                excel_data = self._create_po_schedule_excel(po_df, is_custom_recipient, date_type)
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
                calendar_gen = InboundCalendarGenerator()
                ics_content = calendar_gen.create_po_schedule_ics(po_df, self.sender_email, date_type)
                
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
    
    def send_critical_alerts_email(self, recipient_email: str, recipient_name: str,
                                  data_dict: Dict, cc_emails: List[str] = None,
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
                html_content = self._create_critical_alerts_html(data_dict, recipient_name, is_custom_recipient, date_type)
                html_part = MIMEText(html_content, 'html')
                msg.attach(html_part)
            except Exception as e:
                logger.error(f"Error creating HTML content: {e}", exc_info=True)
                return False, f"Error creating HTML content: {str(e)}"
            
            # Create Excel attachment
            try:
                excel_data = self._create_critical_alerts_excel(data_dict, date_type)
                if excel_data:
                    excel_part = MIMEBase('application', 'vnd.openxmlformats-officedocument.spreadsheetml.sheet')
                    excel_part.set_payload(excel_data.read())
                    encoders.encode_base64(excel_part)
                    
                    filename = f"critical_alerts_{datetime.now().strftime('%Y%m%d')}.xlsx"
                    excel_part.add_header('Content-Disposition', f'attachment; filename="{filename}"')
                    msg.attach(excel_part)
            except Exception as e:
                logger.error(f"Error creating Excel attachment: {e}")
            
            # Create ICS calendar attachment for critical alerts
            try:
                calendar_gen = InboundCalendarGenerator()
                ics_content = calendar_gen.create_critical_alerts_ics(
                    overdue_pos, 
                    pending_stockin, 
                    self.sender_email,
                    date_type
                )
                
                if ics_content:
                    ics_part = MIMEBase('text', 'calendar')
                    ics_part.set_payload(ics_content.encode('utf-8'))
                    encoders.encode_base64(ics_part)
                    ics_part.add_header(
                        'Content-Disposition',
                        f'attachment; filename="critical_alerts_{datetime.now().strftime("%Y%m%d")}.ics"'
                    )
                    msg.attach(ics_part)
            except Exception as e:
                logger.warning(f"Error creating calendar attachment: {e}")
            
            # Send email
            return self._send_email(msg, recipient_email, cc_emails)
            
        except Exception as e:
            logger.error(f"Error sending critical alerts: {e}", exc_info=True)
            return False, str(e)
    
    def send_pending_stockin_email(self, recipient_email: str, recipient_name: str,
                                  can_df: pd.DataFrame, cc_emails: List[str] = None,
                                  is_custom_recipient: bool = False) -> Tuple[bool, str]:
        """Send pending stock-in notification email"""
        try:
            if not self._validate_config():
                return False, "Email configuration missing"
            
            # Validate input data
            if can_df is None or can_df.empty:
                logger.warning(f"No pending stock-in data for {recipient_email}")
                return False, "No pending stock-in items found"
            
            # Create message
            msg = MIMEMultipart('alternative')
            
            urgent_items = len(can_df[can_df['days_since_arrival'] > 7])
            
            if is_custom_recipient:
                msg['Subject'] = f"📦 Pending Stock-in Report - {urgent_items} Urgent Items"
            else:
                msg['Subject'] = f"📦 Your Pending Stock-in Report - {urgent_items} Urgent Items"
            
            msg['From'] = self.sender_email
            msg['To'] = recipient_email
            
            if cc_emails:
                msg['Cc'] = ', '.join(cc_emails)
            
            # Create HTML content
            try:
                html_content = self._create_pending_stockin_html(can_df, recipient_name, is_custom_recipient)
                html_part = MIMEText(html_content, 'html')
                msg.attach(html_part)
            except Exception as e:
                logger.error(f"Error creating HTML content: {e}", exc_info=True)
                return False, f"Error creating HTML content: {str(e)}"
            
            # Create Excel attachment
            try:
                excel_data = self._create_pending_stockin_excel(can_df)
                if excel_data:
                    excel_part = MIMEBase('application', 'vnd.openxmlformats-officedocument.spreadsheetml.sheet')
                    excel_part.set_payload(excel_data.read())
                    encoders.encode_base64(excel_part)
                    
                    filename = f"pending_stockin_{datetime.now().strftime('%Y%m%d')}.xlsx"
                    excel_part.add_header('Content-Disposition', f'attachment; filename="{filename}"')
                    msg.attach(excel_part)
            except Exception as e:
                logger.error(f"Error creating Excel attachment: {e}")
            
            # Create calendar reminder
            try:
                calendar_gen = InboundCalendarGenerator()
                ics_content = calendar_gen.create_stockin_reminder_ics(can_df, self.sender_email)
                
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
                logger.warning(f"Error creating calendar attachment: {e}")
            
            # Send email
            return self._send_email(msg, recipient_email, cc_emails)
            
        except Exception as e:
            logger.error(f"Error sending pending stock-in email: {e}", exc_info=True)
            return False, str(e)
    
    def send_customs_clearance_email(self, recipient_email: str, po_df: pd.DataFrame,
                                    can_df: pd.DataFrame = None, cc_emails: List[str] = None, 
                                    weeks_ahead: int = 4, date_type: str = 'etd') -> Tuple[bool, str]:
        """Send international PO schedule and CAN arrivals to customs team"""
        try:
            if not self._validate_config():
                return False, "Email configuration missing"
            
            # Validate that at least one dataset has data
            if (po_df is None or po_df.empty) and (can_df is None or can_df.empty):
                logger.warning("No international shipments found")
                return False, "No international shipments found"
            
            # Create message
            msg = MIMEMultipart('alternative')
            
            # Count by country
            countries = po_df['vendor_country_name'].nunique() if not po_df.empty else 0
            total_pos = po_df['po_number'].nunique() if not po_df.empty else 0
            total_cans = can_df['arrival_note_number'].nunique() if can_df is not None and not can_df.empty else 0
            
            subject_parts = []
            if total_pos > 0:
                subject_parts.append(f"{total_pos} POs")
            if total_cans > 0:
                subject_parts.append(f"{total_cans} Arrivals")
            
            date_type_upper = date_type.upper()
            msg['Subject'] = f"🛃 International Shipments - {' & '.join(subject_parts)} from {countries} Countries - Next {weeks_ahead} Week{'s' if weeks_ahead > 1 else ''} (by {date_type_upper})"
            msg['From'] = self.sender_email
            msg['To'] = recipient_email
            
            if cc_emails:
                msg['Cc'] = ', '.join(cc_emails)
            
            # Create HTML content
            try:
                html_content = self._create_customs_clearance_html(po_df, can_df, weeks_ahead, date_type)
                html_part = MIMEText(html_content, 'html')
                msg.attach(html_part)
            except Exception as e:
                logger.error(f"Error creating HTML content: {e}", exc_info=True)
                return False, f"Error creating HTML content: {str(e)}"
            
            # Create Excel attachment
            try:
                excel_data = self._create_customs_excel(po_df, can_df, date_type)
                if excel_data:
                    excel_part = MIMEBase('application', 'vnd.openxmlformats-officedocument.spreadsheetml.sheet')
                    excel_part.set_payload(excel_data.read())
                    encoders.encode_base64(excel_part)
                    
                    filename = f"international_shipments_{datetime.now().strftime('%Y%m%d')}.xlsx"
                    excel_part.add_header('Content-Disposition', f'attachment; filename="{filename}"')
                    msg.attach(excel_part)
            except Exception as e:
                logger.error(f"Error creating Excel attachment: {e}")
            
            # Create ICS calendar attachment
            try:
                calendar_gen = InboundCalendarGenerator()
                ics_content = calendar_gen.create_customs_clearance_ics(
                    po_df,
                    can_df,
                    self.sender_email,
                    weeks_ahead=weeks_ahead,
                    date_type=date_type
                )
                
                if ics_content:
                    ics_part = MIMEBase('text', 'calendar')
                    ics_part.set_payload(ics_content.encode('utf-8'))
                    encoders.encode_base64(ics_part)
                    ics_part.add_header(
                        'Content-Disposition',
                        f'attachment; filename="customs_clearance_{datetime.now().strftime("%Y%m%d")}.ics"'
                    )
                    msg.attach(ics_part)
            except Exception as e:
                logger.warning(f"Error creating calendar attachment: {e}")
            
            # Send email
            return self._send_email(msg, recipient_email, cc_emails)
            
        except Exception as e:
            logger.error(f"Error sending customs email: {e}", exc_info=True)
            return False, str(e)
    

    def send_vendor_po_schedule(self, vendor_email: str, vendor_name: str,
                            po_df: pd.DataFrame, cc_emails: List[str] = None,
                            weeks_ahead: int = 4, include_overdue: bool = True,
                            contact_name: str = None, date_type: str = 'etd') -> Tuple[bool, str]:
        """Send PO schedule to vendor including overdue and upcoming POs"""
        try:
            if not self._validate_config():
                return False, "Email configuration missing"
            
            if po_df is None or po_df.empty:
                return False, "No PO data available"
            
            # Separate overdue and upcoming POs
            po_df[date_type] = pd.to_datetime(po_df[date_type])
            today = datetime.now().date()
            
            overdue_pos = po_df[po_df[date_type].dt.date < today] if include_overdue else pd.DataFrame()
            upcoming_pos = po_df[po_df[date_type].dt.date >= today]
            
            # Count statistics
            overdue_count = overdue_pos['po_number'].nunique() if not overdue_pos.empty else 0
            upcoming_count = upcoming_pos['po_number'].nunique() if not upcoming_pos.empty else 0
            
            # Create message
            msg = MIMEMultipart('alternative')
            
            # Dynamic subject based on content and date type
            date_type_upper = date_type.upper()
            if overdue_count > 0 and upcoming_count > 0:
                msg['Subject'] = f"🚨 Purchase Order Update - {vendor_name} - {overdue_count} Overdue + {upcoming_count} Upcoming POs (by {date_type_upper})"
            elif overdue_count > 0:
                msg['Subject'] = f"🚨 URGENT: {overdue_count} Overdue Purchase Orders - {vendor_name} (by {date_type_upper})"
            else:
                msg['Subject'] = f"Purchase Order Schedule - {vendor_name} - Next {weeks_ahead} Week{'s' if weeks_ahead > 1 else ''} (by {date_type_upper})"
            
            msg['From'] = self.sender_email
            msg['To'] = vendor_email
            
            if cc_emails:
                msg['Cc'] = ', '.join(cc_emails)
            
            # Create vendor-specific HTML content
            html_content = self._create_vendor_po_schedule_html(
                po_df, 
                vendor_name, 
                weeks_ahead,
                include_overdue=include_overdue,
                overdue_count=overdue_count,
                upcoming_count=upcoming_count,
                contact_name=contact_name,
                date_type=date_type
            )
            html_part = MIMEText(html_content, 'html')
            msg.attach(html_part)
            
            # CREATE AND ATTACH EXCEL FILE
            try:
                excel_data = self._create_vendor_po_excel(
                    po_df,
                    vendor_name,
                    include_overdue=include_overdue,
                    date_type=date_type
                )
                if excel_data:
                    excel_part = MIMEBase('application', 'vnd.openxmlformats-officedocument.spreadsheetml.sheet')
                    excel_part.set_payload(excel_data.read())
                    encoders.encode_base64(excel_part)
                    
                    filename = f"po_schedule_{vendor_name.replace(' ', '_')}_{datetime.now().strftime('%Y%m%d')}.xlsx"
                    excel_part.add_header('Content-Disposition', f'attachment; filename="{filename}"')
                    msg.attach(excel_part)
                    logger.info(f"Excel attachment added: {filename}")
                else:
                    logger.warning("Excel data creation returned None")
            except Exception as e:
                logger.error(f"Error creating Excel attachment: {e}", exc_info=True)
            
            # Add ICS calendar attachment if there are upcoming POs
            if not upcoming_pos.empty:
                try:
                    calendar_gen = InboundCalendarGenerator()
                    ics_content = calendar_gen.create_po_schedule_ics(upcoming_pos, self.sender_email, date_type)
                    
                    if ics_content:
                        ics_part = MIMEBase('text', 'calendar')
                        ics_part.set_payload(ics_content.encode('utf-8'))
                        encoders.encode_base64(ics_part)
                        ics_part.add_header(
                            'Content-Disposition',
                            f'attachment; filename="po_schedule_{vendor_name.replace(" ", "_")}_{datetime.now().strftime("%Y%m%d")}.ics"'
                        )
                        msg.attach(ics_part)
                        logger.info("ICS attachment added")
                except Exception as e:
                    logger.warning(f"Error creating calendar attachment for vendor: {e}")
            
            return self._send_email(msg, vendor_email, cc_emails)
            
        except Exception as e:
            logger.error(f"Error sending vendor PO schedule: {e}", exc_info=True)
            return False, str(e)


    # Private helper methods
    def _validate_config(self) -> bool:
        """Validate email configuration"""
        if not self.sender_email or not self.sender_password:
            logger.error("Email configuration missing. Please set EMAIL_SENDER and EMAIL_PASSWORD.")
            return False
        return True
    
    def _send_email(self, msg: MIMEMultipart, recipient_email: str, 
                   cc_emails: List[str] = None) -> Tuple[bool, str]:
        """Send email via SMTP"""
        try:
            logger.info(f"Sending email to {recipient_email}...")
            
            with smtplib.SMTP(self.smtp_host, self.smtp_port) as server:
                server.starttls()
                server.login(self.sender_email, self.sender_password)
                
                recipients = [recipient_email]
                if cc_emails:
                    recipients.extend(cc_emails)
                
                server.sendmail(self.sender_email, recipients, msg.as_string())
            
            logger.info(f"Email sent successfully to {recipient_email}")
            return True, "Email sent successfully"
            
        except smtplib.SMTPAuthenticationError:
            error_msg = "Email authentication failed. Please check your email credentials."
            logger.error(error_msg)
            return False, error_msg
        except smtplib.SMTPException as e:
            error_msg = f"SMTP error: {str(e)}"
            logger.error(error_msg)
            return False, error_msg
        except Exception as e:
            logger.error(f"Error sending email: {e}")
            return False, str(e)
    
    def _create_po_schedule_html(self, po_df: pd.DataFrame, recipient_name: str, 
                                is_custom_recipient: bool = False, weeks_ahead: int = 4,
                                date_type: str = 'etd') -> str:
        """Create HTML content for PO schedule email"""
        # Prepare data
        po_df[date_type] = pd.to_datetime(po_df[date_type])
        po_df['week_start'] = po_df[date_type] - pd.to_timedelta(po_df[date_type].dt.dayofweek, unit='D')
        po_df['week_end'] = po_df['week_start'] + timedelta(days=6)
        po_df['week_key'] = po_df['week_start'].dt.strftime('%Y-%m-%d')
        po_df['week'] = po_df[date_type].dt.isocalendar().week
        
        # Calculate summary
        total_pos = po_df['po_number'].nunique()
        total_vendors = po_df['vendor_name'].nunique()
        total_value = po_df['outstanding_arrival_amount_usd'].sum()
        overdue_pos = po_df[po_df[date_type].dt.date < datetime.now().date()]['po_number'].nunique()
        
        # Greeting based on recipient type
        date_type_upper = date_type.upper()
        if is_custom_recipient:
            greeting = f"Dear {recipient_name},"
            intro = f"Please find below the purchase order arrival schedule for the next {weeks_ahead} week{'s' if weeks_ahead > 1 else ''} based on {date_type_upper}."
        else:
            greeting = f"Dear {recipient_name},"
            intro = f"Please find below your purchase order arrival schedule for the next {weeks_ahead} week{'s' if weeks_ahead > 1 else ''} based on {date_type_upper}. These are the POs you have created that are expected to arrive soon."
        
        html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <style>
                body {{
                    font-family: Arial, sans-serif;
                    line-height: 1.6;
                    color: #333;
                    margin: 0;
                    padding: 0;
                }}
                .header {{
                    background-color: #2e7d32;
                    color: white;
                    padding: 20px;
                    text-align: center;
                }}
                .content {{
                    padding: 20px;
                }}
                .summary-section {{
                    background-color: #f5f5f5;
                    border-radius: 5px;
                    padding: 20px;
                    margin: 20px 0;
                }}
                .week-section {{
                    margin-bottom: 30px;
                    border: 1px solid #ddd;
                    border-radius: 5px;
                    padding: 15px;
                }}
                .week-header {{
                    background-color: #e8f5e9;
                    padding: 10px;
                    margin: -15px -15px 15px -15px;
                    border-radius: 5px 5px 0 0;
                    font-weight: bold;
                }}
                table {{
                    width: 100%;
                    border-collapse: collapse;
                    margin-top: 10px;
                }}
                th, td {{
                    padding: 8px;
                    text-align: left;
                    border-bottom: 1px solid #ddd;
                }}
                th {{
                    background-color: #f8f9fa;
                    font-weight: bold;
                }}
                .overdue {{
                    color: #d32f2f;
                    font-weight: bold;
                }}
                .warning {{
                    background-color: #fff3cd;
                    color: #856404;
                    padding: 10px;
                    border-radius: 5px;
                    margin: 10px 0;
                }}
                .footer {{
                    margin-top: 30px;
                    padding: 20px;
                    background-color: #f8f9fa;
                    text-align: center;
                    font-size: 12px;
                    color: #666;
                }}
            </style>
        </head>
        <body>
            <div class="header">
                <h1>📦 Purchase Order Schedule</h1>
                <p>Upcoming Arrivals - Next {weeks_ahead} Week{'s' if weeks_ahead > 1 else ''} (by {date_type_upper})</p>
            </div>
            
            <div class="content">
                <p>{greeting}</p>
                <p>{intro}</p>
                
                <div class="summary-section">
                    <h3>📊 Summary Overview</h3>
                    <table width="100%" cellpadding="0" cellspacing="0" border="0">
                        <tr>
                            <td width="25%" align="center" style="padding: 15px;">
                                <table width="100%" cellpadding="0" cellspacing="0" border="0" style="background-color: white; border-radius: 5px; box-shadow: 0 2px 4px rgba(0,0,0,0.1);">
                                    <tr>
                                        <td align="center" style="padding: 15px;">
                                            <div style="font-size: 28px; font-weight: bold; color: #2e7d32;">{total_pos}</div>
                                            <div style="font-size: 14px; color: #666; margin-top: 5px;">Purchase Orders</div>
                                        </td>
                                    </tr>
                                </table>
                            </td>
                            <td width="25%" align="center" style="padding: 15px;">
                                <table width="100%" cellpadding="0" cellspacing="0" border="0" style="background-color: white; border-radius: 5px; box-shadow: 0 2px 4px rgba(0,0,0,0.1);">
                                    <tr>
                                        <td align="center" style="padding: 15px;">
                                            <div style="font-size: 28px; font-weight: bold; color: #2e7d32;">{total_vendors}</div>
                                            <div style="font-size: 14px; color: #666; margin-top: 5px;">Vendors</div>
                                        </td>
                                    </tr>
                                </table>
                            </td>
                            <td width="25%" align="center" style="padding: 15px;">
                                <table width="100%" cellpadding="0" cellspacing="0" border="0" style="background-color: white; border-radius: 5px; box-shadow: 0 2px 4px rgba(0,0,0,0.1);">
                                    <tr>
                                        <td align="center" style="padding: 15px;">
                                            <div style="font-size: 28px; font-weight: bold; color: #2e7d32;">${total_value/1000:.0f}K</div>
                                            <div style="font-size: 14px; color: #666; margin-top: 5px;">Total Value (USD)</div>
                                        </td>
                                    </tr>
                                </table>
                            </td>
                            <td width="25%" align="center" style="padding: 15px;">
                                <table width="100%" cellpadding="0" cellspacing="0" border="0" style="background-color: white; border-radius: 5px; box-shadow: 0 2px 4px rgba(0,0,0,0.1);">
                                    <tr>
                                        <td align="center" style="padding: 15px;">
                                            <div style="font-size: 28px; font-weight: bold; color: #d32f2f;">{overdue_pos}</div>
                                            <div style="font-size: 14px; color: #666; margin-top: 5px;">Overdue POs ({date_type_upper})</div>
                                        </td>
                                    </tr>
                                </table>
                            </td>
                        </tr>
                    </table>
                </div>
        """
        
        # Add warning if overdue POs exist
        if overdue_pos > 0:
            html += f"""
                <div class="warning">
                    <strong>⚠️ Attention:</strong> {overdue_pos} purchase orders are overdue based on {date_type_upper}. 
                    Please follow up with vendors immediately.
                </div>
            """
        
        # Group by week
        for week_key, week_df in po_df.groupby('week_key', sort=True):
            week_start = week_df['week_start'].iloc[0]
            week_end = week_df['week_end'].iloc[0]
            week_number = week_df['week'].iloc[0]
            
            # Week statistics
            week_pos = week_df['po_number'].nunique()
            week_value = week_df['outstanding_arrival_amount_usd'].sum()
            week_qty = week_df['pending_standard_arrival_quantity'].sum()
            
            html += f"""
                <div class="week-section">
                    <div class="week-header">
                        Week {week_number} ({week_start.strftime('%b %d')} - {week_end.strftime('%b %d, %Y')})
                        <span style="float: right; font-size: 14px;">
                            {week_pos} POs | ${week_value/1000:.0f}K | {week_qty:,.0f} units
                        </span>
                    </div>
                    <table>
                        <tr>
                            <th width="90">{date_type_upper}</th>
                            <th width="100">PO Number</th>
                            <th width="180">Vendor</th>
                            <th width="80">PT Code</th>
                            <th width="140">Product</th>
                            <th width="80">Pending Qty</th>
                            <th width="100">Value (USD)</th>
                            <th width="80">Status</th>
                        </tr>
            """
            
            # Sort by date and vendor
            week_sorted = week_df.sort_values([date_type, 'vendor_name', 'po_number'])
            
            for _, row in week_sorted.iterrows():
                date_class = 'overdue' if row[date_type].date() < datetime.now().date() else ''
                
                html += f"""
                        <tr>
                            <td class="{date_class}">{row[date_type].strftime('%b %d')}</td>
                            <td>{row['po_number']}</td>
                            <td>{row['vendor_name']}</td>
                            <td>{row['pt_code']}</td>
                            <td>{row['product_name']}</td>
                            <td>{row['pending_standard_arrival_quantity']:,.0f}</td>
                            <td>${row['outstanding_arrival_amount_usd']:,.0f}</td>
                            <td>{row['status'].replace('_', ' ').title()}</td>
                        </tr>
                """
            
            html += """
                    </table>
                </div>
            """
        
        # Add calendar buttons
        try:
            calendar_gen = InboundCalendarGenerator()
            google_cal_links = calendar_gen.create_google_calendar_links(po_df, date_type)
            outlook_cal_links = calendar_gen.create_outlook_calendar_links(po_df, date_type)
        except Exception as e:
            logger.warning(f"Error creating calendar links: {e}")
            google_cal_links = None
            outlook_cal_links = None
        
        # Show calendar links only if available
        if google_cal_links and outlook_cal_links:
            html += f"""
                <div style="margin: 40px 0; border: 1px solid #ddd; border-radius: 8px; padding: 25px; background-color: #fafafa;">
                    <h3 style="margin-top: 0; color: #333;">📅 Add to Your Calendar</h3>
                    <p style="color: #666; margin-bottom: 25px;">Click below to add individual PO arrival dates (by {date_type_upper}) to your calendar:</p>
                    
                    <div style="background-color: white; padding: 20px; border-radius: 5px; box-shadow: 0 1px 3px rgba(0,0,0,0.1);">
            """
            
            # Add individual date links (show first 5)
            for i, gcal_link in enumerate(google_cal_links[:5]):
                date_str = gcal_link['date'].strftime('%b %d')
                is_urgent = gcal_link.get('is_urgent', False)
                date_style = 'color: #d32f2f; font-weight: bold;' if is_urgent else 'font-weight: bold;'
                
                html += f"""
                        <div style="margin: 15px 0; padding: 10px 0; border-bottom: 1px solid #eee;">
                            <span style="{date_style} display: inline-block; width: 80px;">{date_str}:</span>
                            <a href="{gcal_link['link']}" target="_blank" 
                               style="margin: 0 15px; color: #4285f4; text-decoration: none; font-weight: 500;">
                               📅 Google Calendar
                            </a>
                            <a href="{outlook_cal_links[i]['link']}" target="_blank" 
                               style="margin: 0 15px; color: #0078d4; text-decoration: none; font-weight: 500;">
                               📅 Outlook
                            </a>
                        </div>
                """
            
            if len(google_cal_links) > 5:
                html += f"""
                        <div style="margin-top: 20px; padding-top: 15px; border-top: 1px solid #eee; text-align: center;">
                            <p style="font-style: italic; color: #999; margin: 0;">
                                ... and {len(google_cal_links) - 5} more dates
                            </p>
                        </div>
                """
            
            html += """
                    </div>
                    
                    <p style="margin-top: 20px; margin-bottom: 0; color: #666; font-size: 14px; text-align: center;">
                        Or download the attached .ics file to import all dates into any calendar application
                    </p>
                </div>
            """
        
        # Add action items
        html += f"""
            <div style="margin-top: 20px; padding: 15px; background-color: #e3f2fd; border-radius: 5px;">
                <h4>📋 Action Items:</h4>
                <ul>
                    <li>Review and confirm {date_type_upper}s with vendors</li>
                    <li>Prepare warehouse space for incoming goods</li>
                    <li>Ensure all import documentation is ready</li>
                    <li>Coordinate quality inspection schedules</li>
                </ul>
            </div>
            
            <div class="footer">
                <p>This is an automated email from Inbound Logistics System</p>
                <p>For questions, please contact: <a href="mailto:inbound@prostech.vn">inbound@prostech.vn</a></p>
            </div>
        </div>
        </body>
        </html>
        """
        
        return html
    
    # Excel creation methods
    def _create_po_schedule_excel(self, po_df: pd.DataFrame, is_custom_recipient: bool = False, 
                                  date_type: str = 'etd') -> Optional[io.BytesIO]:
        """Create Excel attachment for PO schedule with better error handling"""
        output = io.BytesIO()
        
        try:
            if po_df is None or po_df.empty:
                logger.warning("Empty DataFrame provided to create Excel")
                return None
            
            # Check for required columns
            required_cols = ['vendor_name', 'po_number', 'pending_standard_arrival_quantity', 
                           'outstanding_arrival_amount_usd', date_type]
            
            missing_cols = [col for col in required_cols if col not in po_df.columns]
            if missing_cols:
                logger.error(f"Missing required columns: {missing_cols}")
                # Try to continue with available columns
                po_df = po_df[[col for col in po_df.columns if col in required_cols]]
            
            with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                # Sheet 1: PO Details
                po_df.to_excel(writer, sheet_name='PO Details', index=False)
                
                # Sheet 2: Summary by Vendor (only if columns exist)
                if all(col in po_df.columns for col in ['vendor_name', 'po_number', 
                       'pending_standard_arrival_quantity', 'outstanding_arrival_amount_usd']):
                    vendor_summary = po_df.groupby('vendor_name').agg({
                        'po_number': 'nunique',
                        'pending_standard_arrival_quantity': 'sum',
                        'outstanding_arrival_amount_usd': 'sum'
                    }).reset_index()
                    vendor_summary.columns = ['Vendor', 'PO Count', 'Pending Quantity', 'Outstanding Value USD']
                    vendor_summary.to_excel(writer, sheet_name='Vendor Summary', index=False)
                
                # Sheet 3: Weekly Timeline (only if date column exists)
                if date_type in po_df.columns:
                    po_df_copy = po_df.copy()
                    po_df_copy[date_type] = pd.to_datetime(po_df_copy[date_type], errors='coerce')
                    po_df_copy = po_df_copy.dropna(subset=[date_type])  # Remove invalid dates
                    
                    if not po_df_copy.empty:
                        po_df_copy['week'] = po_df_copy[date_type].dt.to_period('W').dt.start_time
                        
                        # Check which columns are available for aggregation
                        agg_dict = {}
                        if 'po_number' in po_df_copy.columns:
                            agg_dict['po_number'] = 'nunique'
                        if 'pending_standard_arrival_quantity' in po_df_copy.columns:
                            agg_dict['pending_standard_arrival_quantity'] = 'sum'
                        if 'outstanding_arrival_amount_usd' in po_df_copy.columns:
                            agg_dict['outstanding_arrival_amount_usd'] = 'sum'
                        
                        if agg_dict:
                            weekly_summary = po_df_copy.groupby('week').agg(agg_dict).reset_index()
                            
                            # Rename columns based on what's available
                            rename_dict = {'week': 'Week Starting'}
                            if 'po_number' in agg_dict:
                                rename_dict['po_number'] = 'PO Count'
                            if 'pending_standard_arrival_quantity' in agg_dict:
                                rename_dict['pending_standard_arrival_quantity'] = 'Total Quantity'
                            if 'outstanding_arrival_amount_usd' in agg_dict:
                                rename_dict['outstanding_arrival_amount_usd'] = 'Total Value USD'
                            
                            weekly_summary.rename(columns=rename_dict, inplace=True)
                            weekly_summary.to_excel(writer, sheet_name='Weekly Timeline', index=False)
                
                # Add formatting
                workbook = writer.book
                header_format = workbook.add_format({
                    'bold': True,
                    'bg_color': '#2e7d32',
                    'font_color': 'white',
                    'border': 1
                })
                
                # Apply header formatting to all sheets
                for sheet_name in writer.sheets:
                    worksheet = writer.sheets[sheet_name]
                    worksheet.set_column(0, 20, 15)  # Default column width
                    worksheet.freeze_panes(1, 0)  # Freeze header row
            
            output.seek(0)
            return output
            
        except Exception as e:
            logger.error(f"Error creating PO schedule Excel: {e}", exc_info=True)
            return None
    
    def _create_critical_alerts_excel(self, data_dict: Dict, date_type: str = 'etd') -> Optional[io.BytesIO]:
        """Create Excel attachment for critical alerts"""
        output = io.BytesIO()
        
        try:
            with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                # Sheet 1: Overdue POs
                if 'overdue_pos' in data_dict and not data_dict['overdue_pos'].empty:
                    # Rename column if it exists
                    overdue_df = data_dict['overdue_pos'].copy()
                    if f'original_{date_type}' in overdue_df.columns:
                        overdue_df = overdue_df.rename(columns={f'original_{date_type}': f'{date_type.upper()}'})
                    overdue_df.to_excel(writer, sheet_name=f'Overdue POs ({date_type.upper()})', index=False)
                
                # Sheet 2: Pending Stock-in
                if 'pending_stockin' in data_dict and not data_dict['pending_stockin'].empty:
                    data_dict['pending_stockin'].to_excel(writer, sheet_name='Pending Stock-in', index=False)
                
                # Add formatting
                workbook = writer.book
                header_format = workbook.add_format({
                    'bold': True,
                    'bg_color': '#d32f2f',
                    'font_color': 'white',
                    'border': 1
                })
                
                # Apply formatting
                for sheet_name in writer.sheets:
                    worksheet = writer.sheets[sheet_name]
                    worksheet.set_column(0, 20, 15)
                    worksheet.freeze_panes(1, 0)
            
            output.seek(0)
            return output
            
        except Exception as e:
            logger.error(f"Error creating critical alerts Excel: {e}", exc_info=True)
            return None
    
    def _create_pending_stockin_excel(self, can_df: pd.DataFrame) -> Optional[io.BytesIO]:
        """Create Excel attachment for pending stock-in"""
        output = io.BytesIO()
        
        try:
            if can_df is None or can_df.empty:
                logger.warning("Empty DataFrame provided for pending stock-in Excel")
                return None
                
            with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                # Sheet 1: All pending items
                can_df.to_excel(writer, sheet_name='All Pending Items', index=False)
                
                # Sheet 2: Summary by age
                can_df['days_category'] = pd.cut(can_df['days_since_arrival'], 
                                                bins=[0, 3, 7, 14, float('inf')],
                                                labels=['0-3 days', '4-7 days', '8-14 days', '> 14 days'])
                
                age_summary = can_df.groupby('days_category').agg({
                    'arrival_note_number': 'count',
                    'pending_quantity': 'sum',
                    'pending_value_usd': 'sum'
                }).reset_index()
                age_summary.columns = ['Days Category', 'Item Count', 'Total Quantity', 'Total Value USD']
                age_summary.to_excel(writer, sheet_name='Age Summary', index=False)
                
                # Sheet 3: Vendor Summary
                if 'vendor' in can_df.columns:
                    vendor_summary = can_df.groupby('vendor').agg({
                        'arrival_note_number': 'nunique',
                        'can_line_id': 'count',
                        'pending_quantity': 'sum',
                        'pending_value_usd': 'sum',
                        'days_since_arrival': 'mean'
                    }).reset_index()
                    vendor_summary.columns = ['Vendor', 'CAN Count', 'Line Items', 'Total Quantity', 
                                            'Total Value USD', 'Avg Days Pending']
                    vendor_summary.to_excel(writer, sheet_name='Vendor Summary', index=False)
                
                # Add formatting
                workbook = writer.book
                header_format = workbook.add_format({
                    'bold': True,
                    'bg_color': '#f57c00',
                    'font_color': 'white',
                    'border': 1
                })
                
                # Apply formatting
                for sheet_name in writer.sheets:
                    worksheet = writer.sheets[sheet_name]
                    worksheet.set_column(0, 20, 15)
                    worksheet.freeze_panes(1, 0)
            
            output.seek(0)
            return output
            
        except Exception as e:
            logger.error(f"Error creating pending stock-in Excel: {e}", exc_info=True)
            return None
    
    def _create_customs_excel(self, po_df: pd.DataFrame, can_df: pd.DataFrame = None,
                              date_type: str = 'etd') -> Optional[io.BytesIO]:
        """Create Excel for customs clearance"""
        output = io.BytesIO()
        
        try:
            with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                # Sheet 1: Summary by Country
                if not po_df.empty:
                    country_summary = po_df.groupby('vendor_country_name').agg({
                        'po_number': 'nunique',
                        'vendor_name': 'nunique',
                        'pending_standard_arrival_quantity': 'sum',
                        'outstanding_arrival_amount_usd': 'sum'
                    }).reset_index()
                    country_summary.columns = ['Country', 'PO Count', 'Vendors', 'Total Quantity', 'Total Value USD']
                    country_summary.to_excel(writer, sheet_name='Country Summary', index=False)
                
                # Sheet 2: PO Details
                if not po_df.empty:
                    po_df.to_excel(writer, sheet_name=f'PO Details ({date_type.upper()})', index=False)
                
                # Sheet 3: CAN Arrivals
                if can_df is not None and not can_df.empty:
                    can_df.to_excel(writer, sheet_name='CAN Arrivals', index=False)
                    
                    # Sheet 4: CAN Summary by Date
                    can_summary = can_df.groupby(['arrival_date', 'vendor_country_name']).agg({
                        'arrival_note_number': 'nunique',
                        'vendor': 'nunique',
                        'pending_quantity': 'sum',
                        'pending_value_usd': 'sum'
                    }).reset_index()
                    can_summary.columns = ['Arrival Date', 'Country', 'CAN Count', 'Vendors', 'Total Quantity', 'Total Value USD']
                    can_summary.to_excel(writer, sheet_name='CAN Summary', index=False)
                
                # Sheet 5: Combined Timeline
                timeline_data = []
                
                # Add PO data to timeline
                if not po_df.empty:
                    po_timeline = po_df.groupby([date_type, 'vendor_country_name']).agg({
                        'po_number': 'nunique',
                        'outstanding_arrival_amount_usd': 'sum'
                    }).reset_index()
                    po_timeline['Type'] = f'PO {date_type.upper()}'
                    po_timeline.columns = ['Date', 'Country', 'Count', 'Value USD', 'Type']
                    timeline_data.append(po_timeline)
                
                # Add CAN data to timeline
                if can_df is not None and not can_df.empty:
                    can_timeline = can_df.groupby(['arrival_date', 'vendor_country_name']).agg({
                        'arrival_note_number': 'nunique',
                        'pending_value_usd': 'sum'
                    }).reset_index()
                    can_timeline['Type'] = 'CAN Arrival'
                    can_timeline.columns = ['Date', 'Country', 'Count', 'Value USD', 'Type']
                    timeline_data.append(can_timeline)
                
                if timeline_data:
                    combined_timeline = pd.concat(timeline_data, ignore_index=True)
                    combined_timeline = combined_timeline.sort_values(['Date', 'Type', 'Country'])
                    combined_timeline.to_excel(writer, sheet_name='Combined Timeline', index=False)
                
                # Add formatting
                workbook = writer.book
                header_format = workbook.add_format({
                    'bold': True,
                    'bg_color': '#00796b',
                    'font_color': 'white',
                    'border': 1
                })
                
                # Apply formatting
                for sheet_name in writer.sheets:
                    worksheet = writer.sheets[sheet_name]
                    worksheet.set_column(0, 20, 15)
                    worksheet.freeze_panes(1, 0)
            
            output.seek(0)
            return output
            
        except Exception as e:
            logger.error(f"Error creating customs Excel: {e}", exc_info=True)
            return None
    

    def _create_vendor_po_excel(self, po_df: pd.DataFrame, vendor_name: str, 
                            include_overdue: bool = True, date_type: str = 'etd') -> Optional[io.BytesIO]:
        """Create Excel attachment for vendor with separate sheets for overdue and upcoming"""
        output = io.BytesIO()
        
        try:
            if po_df is None or po_df.empty:
                return None
            
            # Make a copy to avoid modifying original
            po_df = po_df.copy()
            
            # Separate overdue and upcoming
            po_df[date_type] = pd.to_datetime(po_df[date_type])
            today = datetime.now().date()
            
            overdue_pos = po_df[po_df[date_type].dt.date < today].copy() if include_overdue else pd.DataFrame()
            upcoming_pos = po_df[po_df[date_type].dt.date >= today].copy()
            
            with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                # Sheet 1: Summary
                summary_data = {
                    'Metric': ['Total POs', 'Overdue POs', 'Upcoming POs', 'Total Value USD', 
                            'Overdue Value USD', 'Upcoming Value USD'],
                    'Value': [
                        po_df['po_number'].nunique(),
                        overdue_pos['po_number'].nunique() if not overdue_pos.empty else 0,
                        upcoming_pos['po_number'].nunique() if not upcoming_pos.empty else 0,
                        po_df['outstanding_arrival_amount_usd'].sum(),
                        overdue_pos['outstanding_arrival_amount_usd'].sum() if not overdue_pos.empty else 0,
                        upcoming_pos['outstanding_arrival_amount_usd'].sum() if not upcoming_pos.empty else 0
                    ]
                }
                summary_df = pd.DataFrame(summary_data)
                summary_df.to_excel(writer, sheet_name='Summary', index=False)
                
                # Sheet 2: Overdue POs (if any)
                if include_overdue and not overdue_pos.empty:
                    # Calculate days_overdue
                    overdue_pos['days_overdue'] = overdue_pos[date_type].apply(
                        lambda x: (today - x.date()).days
                    )
                    overdue_pos = overdue_pos.sort_values('days_overdue', ascending=False)
                    
                    # Select relevant columns
                    overdue_columns = []
                    column_mapping = {}
                    
                    if date_type in overdue_pos.columns:
                        overdue_columns.append(date_type)
                        column_mapping[date_type] = date_type.upper()
                    
                    if 'days_overdue' in overdue_pos.columns:
                        overdue_columns.append('days_overdue')
                        column_mapping['days_overdue'] = 'Days Overdue'
                    
                    if 'po_number' in overdue_pos.columns:
                        overdue_columns.append('po_number')
                        column_mapping['po_number'] = 'PO Number'
                    
                    if 'pt_code' in overdue_pos.columns:
                        overdue_columns.append('pt_code')
                        column_mapping['pt_code'] = 'PT Code'
                    
                    if 'product_name' in overdue_pos.columns:
                        overdue_columns.append('product_name')
                        column_mapping['product_name'] = 'Product'
                    
                    if 'pending_standard_arrival_quantity' in overdue_pos.columns:
                        overdue_columns.append('pending_standard_arrival_quantity')
                        column_mapping['pending_standard_arrival_quantity'] = 'Outstanding Qty'
                    
                    if 'outstanding_arrival_amount_usd' in overdue_pos.columns:
                        overdue_columns.append('outstanding_arrival_amount_usd')
                        column_mapping['outstanding_arrival_amount_usd'] = 'Value USD'
                    
                    if 'payment_term' in overdue_pos.columns:
                        overdue_columns.append('payment_term')
                        column_mapping['payment_term'] = 'Payment Terms'
                    
                    if 'status' in overdue_pos.columns:
                        overdue_columns.append('status')
                        column_mapping['status'] = 'Status'
                    
                    overdue_export = overdue_pos[overdue_columns].copy()
                    overdue_export.rename(columns=column_mapping, inplace=True)
                    overdue_export.to_excel(writer, sheet_name=f'Overdue POs ({date_type.upper()})', index=False)
                
                # Sheet 3: Upcoming POs
                if not upcoming_pos.empty:
                    # Calculate days_until_etd/eta
                    upcoming_pos['days_until_date'] = upcoming_pos[date_type].apply(
                        lambda x: (x.date() - today).days
                    )
                    upcoming_pos = upcoming_pos.sort_values(date_type)
                    
                    # Select relevant columns
                    upcoming_columns = []
                    column_mapping = {}
                    
                    if date_type in upcoming_pos.columns:
                        upcoming_columns.append(date_type)
                        column_mapping[date_type] = date_type.upper()
                    
                    if 'days_until_date' in upcoming_pos.columns:
                        upcoming_columns.append('days_until_date')
                        column_mapping['days_until_date'] = f'Days Until {date_type.upper()}'
                    
                    if 'po_number' in upcoming_pos.columns:
                        upcoming_columns.append('po_number')
                        column_mapping['po_number'] = 'PO Number'
                    
                    if 'pt_code' in upcoming_pos.columns:
                        upcoming_columns.append('pt_code')
                        column_mapping['pt_code'] = 'PT Code'
                    
                    if 'product_name' in upcoming_pos.columns:
                        upcoming_columns.append('product_name')
                        column_mapping['product_name'] = 'Product'
                    
                    if 'pending_standard_arrival_quantity' in upcoming_pos.columns:
                        upcoming_columns.append('pending_standard_arrival_quantity')
                        column_mapping['pending_standard_arrival_quantity'] = 'Outstanding Qty'
                    
                    if 'outstanding_arrival_amount_usd' in upcoming_pos.columns:
                        upcoming_columns.append('outstanding_arrival_amount_usd')
                        column_mapping['outstanding_arrival_amount_usd'] = 'Value USD'
                    
                    if 'trade_term' in upcoming_pos.columns:
                        upcoming_columns.append('trade_term')
                        column_mapping['trade_term'] = 'Trade Terms'
                    
                    if 'status' in upcoming_pos.columns:
                        upcoming_columns.append('status')
                        column_mapping['status'] = 'Status'
                    
                    upcoming_export = upcoming_pos[upcoming_columns].copy()
                    upcoming_export.rename(columns=column_mapping, inplace=True)
                    upcoming_export.to_excel(writer, sheet_name=f'Upcoming POs ({date_type.upper()})', index=False)
                
                # Sheet 4: All PO Details
                all_columns = []
                column_mapping = {}
                
                # Check which columns exist
                available_columns = {
                    'po_number': 'PO Number',
                    'po_date': 'PO Date',
                    date_type: date_type.upper(),
                    'vendor_name': 'Vendor',
                    'product_name': 'Product',
                    'pt_code': 'PT Code',
                    'brand': 'Brand',
                    'pending_standard_arrival_quantity': 'Outstanding Qty',
                    'outstanding_arrival_amount_usd': 'Value USD',
                    'payment_term': 'Payment Terms',
                    'trade_term': 'Trade Terms',
                    'status': 'Status'
                }
                
                # Add ETA if we're using ETD and vice versa
                if date_type == 'etd' and 'eta' in po_df.columns:
                    available_columns['eta'] = 'ETA'
                elif date_type == 'eta' and 'etd' in po_df.columns:
                    available_columns['etd'] = 'ETD'
                
                for col, display_name in available_columns.items():
                    if col in po_df.columns:
                        all_columns.append(col)
                        column_mapping[col] = display_name
                
                all_export = po_df[all_columns].copy()
                all_export.rename(columns=column_mapping, inplace=True)
                all_export.to_excel(writer, sheet_name='All PO Details', index=False)
                
                # Add formatting
                workbook = writer.book
                
                # Format for headers
                header_format = workbook.add_format({
                    'bold': True,
                    'bg_color': '#2e7d32',
                    'font_color': 'white',
                    'border': 1
                })
                
                # Apply formatting
                for sheet_name in writer.sheets:
                    worksheet = writer.sheets[sheet_name]
                    worksheet.set_column(0, 20, 15)
                    worksheet.freeze_panes(1, 0)
            
            output.seek(0)
            return output
            
        except Exception as e:
            logger.error(f"Error creating vendor PO Excel: {e}", exc_info=True)
            return None


    def _create_critical_alerts_html(self, data_dict: Dict, recipient_name: str,
                                    is_custom_recipient: bool = False, date_type: str = 'etd') -> str:
        """Create HTML content for critical alerts email"""
        overdue_pos = data_dict.get('overdue_pos', pd.DataFrame())
        pending_stockin = data_dict.get('pending_stockin', pd.DataFrame())
        
        # Calculate totals
        total_overdue = len(overdue_pos) if not overdue_pos.empty else 0
        total_pending = len(pending_stockin) if not pending_stockin.empty else 0
        max_days_overdue = overdue_pos['days_overdue'].max() if not overdue_pos.empty and 'days_overdue' in overdue_pos.columns else 0
        max_days_pending = pending_stockin['days_since_arrival'].max() if not pending_stockin.empty else 0
        
        # Greeting based on recipient type
        date_type_upper = date_type.upper()
        if is_custom_recipient:
            greeting = f"Dear {recipient_name},"
            intro = "The following items require immediate attention:"
        else:
            greeting = f"Dear {recipient_name},"
            intro = "The following items from your purchase orders require immediate attention:"
        
        html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <style>
                body {{
                    font-family: Arial, sans-serif;
                    line-height: 1.6;
                    color: #333;
                    margin: 0;
                    padding: 0;
                }}
                .header {{
                    background-color: #d32f2f;
                    color: white;
                    padding: 20px;
                    text-align: center;
                }}
                .content {{
                    padding: 20px;
                }}
                .alert-box {{
                    background-color: #ffebee;
                    border: 2px solid #ef5350;
                    border-radius: 5px;
                    padding: 15px;
                    margin: 20px 0;
                }}
                .section-header {{
                    background-color: #f5f5f5;
                    padding: 10px;
                    margin: 20px 0 10px 0;
                    border-left: 4px solid #d32f2f;
                    font-weight: bold;
                    font-size: 18px;
                }}
                table {{
                    width: 100%;
                    border-collapse: collapse;
                    margin-top: 10px;
                }}
                th, td {{
                    padding: 8px;
                    text-align: left;
                    border-bottom: 1px solid #ddd;
                }}
                th {{
                    background-color: #f8f9fa;
                    font-weight: bold;
                }}
                .overdue-row {{
                    background-color: #ffcccb;
                }}
                .days-overdue {{
                    color: #d32f2f;
                    font-weight: bold;
                }}
                .action-box {{
                    background-color: #e3f2fd;
                    border: 1px solid #2196f3;
                    border-radius: 5px;
                    padding: 15px;
                    margin: 20px 0;
                }}
                .footer {{
                    margin-top: 30px;
                    padding: 20px;
                    background-color: #f8f9fa;
                    text-align: center;
                    font-size: 12px;
                    color: #666;
                }}
            </style>
        </head>
        <body>
            <div class="header">
                <h1>🚨 CRITICAL INBOUND ALERTS</h1>
                <p>Immediate Action Required</p>
            </div>
            
            <div class="content">
                <p>{greeting}</p>
                
                <div class="alert-box">
                    <strong>⚠️ CRITICAL ISSUES DETECTED:</strong><br>
                    {intro}<br>
                    • {total_overdue} Overdue Purchase Orders (by {date_type_upper})<br>
                    • {total_pending} Items Pending Stock-in > 7 days
                </div>
                
                <table width="100%" cellpadding="0" cellspacing="0" border="0" style="background-color: #f5f5f5; border-radius: 5px; padding: 20px; margin: 20px 0;">
                    <tr>
                        <td width="25%" align="center" style="padding: 15px;">
                            <table width="100%" cellpadding="0" cellspacing="0" border="0" style="background-color: white; border-radius: 5px; box-shadow: 0 2px 4px rgba(0,0,0,0.1);">
                                <tr>
                                    <td align="center" style="padding: 15px;">
                                        <div style="font-size: 32px; font-weight: bold; color: #d32f2f;">{total_overdue}</div>
                                        <div style="font-size: 14px; color: #666; margin-top: 5px;">Overdue POs ({date_type_upper})</div>
                                    </td>
                                </tr>
                            </table>
                        </td>
                        <td width="25%" align="center" style="padding: 15px;">
                            <table width="100%" cellpadding="0" cellspacing="0" border="0" style="background-color: white; border-radius: 5px; box-shadow: 0 2px 4px rgba(0,0,0,0.1);">
                                <tr>
                                    <td align="center" style="padding: 15px;">
                                        <div style="font-size: 32px; font-weight: bold; color: #d32f2f;">{total_pending}</div>
                                        <div style="font-size: 14px; color: #666; margin-top: 5px;">Pending Stock-in</div>
                                    </td>
                                </tr>
                            </table>
                        </td>
                        <td width="25%" align="center" style="padding: 15px;">
                            <table width="100%" cellpadding="0" cellspacing="0" border="0" style="background-color: white; border-radius: 5px; box-shadow: 0 2px 4px rgba(0,0,0,0.1);">
                                <tr>
                                    <td align="center" style="padding: 15px;">
                                        <div style="font-size: 32px; font-weight: bold; color: #d32f2f;">{int(max_days_overdue)}</div>
                                        <div style="font-size: 14px; color: #666; margin-top: 5px;">Max Days Overdue</div>
                                    </td>
                                </tr>
                            </table>
                        </td>
                        <td width="25%" align="center" style="padding: 15px;">
                            <table width="100%" cellpadding="0" cellspacing="0" border="0" style="background-color: white; border-radius: 5px; box-shadow: 0 2px 4px rgba(0,0,0,0.1);">
                                <tr>
                                    <td align="center" style="padding: 15px;">
                                        <div style="font-size: 32px; font-weight: bold; color: #d32f2f;">{int(max_days_pending)}</div>
                                        <div style="font-size: 14px; color: #666; margin-top: 5px;">Max Days Pending</div>
                                    </td>
                                </tr>
                            </table>
                        </td>
                    </tr>
                </table>
        """
        
        # Overdue POs Section
        if not overdue_pos.empty:
            html += f"""
                <div class="section-header">🔴 OVERDUE PURCHASE ORDERS (by {date_type_upper})</div>
                <p>These POs have passed their {date_type_upper} and require immediate vendor follow-up:</p>
                <table>
                    <tr>
                        <th width="100">PO Number</th>
                        <th width="180">Vendor</th>
                        <th width="90">Original {date_type_upper}</th>
                        <th width="80">Days Overdue</th>
                        <th width="120">Products</th>
                        <th width="100">Value (USD)</th>
                    </tr>
            """
            
            for _, row in overdue_pos.iterrows():
                # Get the date column name
                date_col = f'original_{date_type}' if f'original_{date_type}' in row else date_type
                
                html += f"""
                    <tr class="overdue-row">
                        <td>{row['po_number']}</td>
                        <td>{row['vendor_name']}</td>
                        <td>{row[date_col] if date_col in row else 'N/A'}</td>
                        <td class="days-overdue">{row['days_overdue']} days</td>
                        <td>{str(row['products'])[:50]}...</td>
                        <td>${row['outstanding_value']:,.0f}</td>
                    </tr>
                """
            
            html += "</table>"
        
        # Pending Stock-in Section
        if not pending_stockin.empty:
            html += """
                <div class="section-header">📦 PENDING STOCK-IN (> 7 DAYS)</div>
                <p>These items have arrived but not been stocked in for over 7 days:</p>
                <table>
                    <tr>
                        <th width="120">CAN Number</th>
                        <th width="150">Vendor</th>
                        <th width="150">Product</th>
                        <th width="80">PT Code</th>
                        <th width="80">Pending Qty</th>
                        <th width="80">Days Pending</th>
                    </tr>
            """
            
            top_pending = pending_stockin.nlargest(10, 'days_since_arrival')
            for _, row in top_pending.iterrows():
                html += f"""
                    <tr>
                        <td>{row['arrival_note_number']}</td>
                        <td>{row['vendor']}</td>
                        <td>{row['product_name']}</td>
                        <td>{row['pt_code']}</td>
                        <td>{row['pending_quantity']:,.0f}</td>
                        <td class="days-overdue">{row['days_since_arrival']} days</td>
                    </tr>
                """
            
            html += "</table>"
        
        # Action Items
        html += f"""
            <div class="action-box">
                <h4>📋 Required Actions:</h4>
                <ol>
                    <li><strong>Overdue POs:</strong> Contact vendors immediately for updated {date_type_upper}s</li>
                    <li><strong>Pending Stock-in:</strong> Prioritize warehouse processing for aged items</li>
                    <li><strong>Escalation:</strong> Items overdue > 14 days should be escalated to management</li>
                </ol>
                
                <div style="margin: 20px 0; padding: 15px; background-color: #fff3cd; border: 1px solid #ffeeba; border-radius: 5px;">
                    <h4 style="margin-top: 0;">📅 Calendar Reminder</h4>
                    <p>An urgent calendar event has been created for today at 9:00 AM.</p>
                    <p style="margin-bottom: 0;">Import the attached .ics file to receive alerts about these critical issues.</p>
                </div>
                
                <p><strong>Procurement Team Contact:</strong><br>
                📧 Email: procurement@prostech.vn<br>
                📞 Phone: +84 33 476273</p>
            </div>
            
            <div class="footer">
                <p>This is an automated urgent alert from Inbound Logistics System</p>
                <p>Please take immediate action on the items listed above</p>
                <p>For questions, contact: <a href="mailto:inbound@prostech.vn">inbound@prostech.vn</a></p>
            </div>
        </div>
        </body>
        </html>
        """
        
        return html
    
    def _create_pending_stockin_html(self, can_df: pd.DataFrame, recipient_name: str,
                                    is_custom_recipient: bool = False) -> str:
        """Create HTML content for pending stock-in notification"""
        # Group by status
        can_df['days_category'] = pd.cut(can_df['days_since_arrival'], 
                                         bins=[0, 3, 7, 14, float('inf')],
                                         labels=['0-3 days', '4-7 days', '8-14 days', '> 14 days'])
        
        # Calculate summary
        total_items = len(can_df)
        total_value = can_df['pending_value_usd'].sum()
        avg_days = can_df['days_since_arrival'].mean()
        critical_items = len(can_df[can_df['days_since_arrival'] > 14])
        
        # Greeting based on recipient type
        if is_custom_recipient:
            greeting = f"Dear {recipient_name},"
            intro = "Please find below the list of items pending stock-in at our warehouses."
        else:
            greeting = f"Dear {recipient_name},"
            intro = "Please find below the list of items from your purchase orders that are pending stock-in at our warehouses."
        
        html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <style>
                body {{
                    font-family: Arial, sans-serif;
                    line-height: 1.6;
                    color: #333;
                    margin: 0;
                    padding: 0;
                }}
                .header {{
                    background-color: #f57c00;
                    color: white;
                    padding: 20px;
                    text-align: center;
                }}
                .content {{
                    padding: 20px;
                }}
                .summary-box {{
                    background-color: #fff3e0;
                    border: 1px solid #ffb74d;
                    border-radius: 5px;
                    padding: 15px;
                    margin: 20px 0;
                }}
                .category-section {{
                    margin: 20px 0;
                }}
                .category-header {{
                    background-color: #f5f5f5;
                    padding: 10px;
                    border-left: 4px solid #f57c00;
                    font-weight: bold;
                    margin-bottom: 10px;
                }}
                table {{
                    width: 100%;
                    border-collapse: collapse;
                    margin-top: 10px;
                }}
                th, td {{
                    padding: 8px;
                    text-align: left;
                    border-bottom: 1px solid #ddd;
                }}
                th {{
                    background-color: #f8f9fa;
                    font-weight: bold;
                }}
                .urgent {{
                    background-color: #ffcccb;
                }}
                .warning {{
                    background-color: #ffe4b5;
                }}
                .footer {{
                    margin-top: 30px;
                    padding: 20px;
                    background-color: #f8f9fa;
                    text-align: center;
                    font-size: 12px;
                    color: #666;
                }}
            </style>
        </head>
        <body>
            <div class="header">
                <h1>📦 Pending Stock-in Report</h1>
                <p>Items Awaiting Warehouse Processing</p>
            </div>
            
            <div class="content">
                <p>{greeting}</p>
                <p>{intro} Priority should be given to items pending for more than 7 days.</p>
                
                <div class="summary-box">
                    <h3>📊 Summary</h3>
                    <p>
                    • Total Pending Items: <strong>{total_items}</strong><br>
                    • Total Pending Value: <strong>${total_value:,.0f}</strong><br>
                    • Average Days Pending: <strong>{avg_days:.1f} days</strong><br>
                    • Critical Items (>14 days): <strong>{critical_items}</strong>
                    </p>
                </div>
        """
        
        # Group by days category
        for category in ['> 14 days', '8-14 days', '4-7 days', '0-3 days']:
            category_df = can_df[can_df['days_category'] == category]
            
            if not category_df.empty:
                row_class = 'urgent' if category == '> 14 days' else 'warning' if category == '8-14 days' else ''
                
                html += f"""
                    <div class="category-section">
                        <div class="category-header">
                            {category} ({len(category_df)} items, ${category_df['pending_value_usd'].sum():,.0f})
                        </div>
                        <table>
                            <tr>
                                <th width="120">CAN Number</th>
                                <th width="90">Arrival Date</th>
                                <th width="150">Vendor</th>
                                <th width="150">Product</th>
                                <th width="80">PT Code</th>
                                <th width="100">Pending Qty</th>
                                <th width="100">Value (USD)</th>
                                <th width="80">Status</th>
                            </tr>
                """
                
                # Sort by days pending descending
                category_sorted = category_df.sort_values('days_since_arrival', ascending=False).head(20)
                
                for _, row in category_sorted.iterrows():
                    html += f"""
                            <tr class="{row_class}">
                                <td>{row['arrival_note_number']}</td>
                                <td>{row['arrival_date']}</td>
                                <td>{row['vendor']}</td>
                                <td>{row['product_name']}</td>
                                <td>{row['pt_code']}</td>
                                <td>{row['pending_quantity']:,.0f}</td>
                                <td>${row['pending_value_usd']:,.0f}</td>
                                <td>{row['can_status']}</td>
                            </tr>
                    """
                
                html += "</table></div>"
        
        # Add calendar reminder
        html += """
            <div style="margin: 40px 0; border: 1px solid #ddd; border-radius: 8px; padding: 25px; background-color: #fafafa;">
                <h3 style="margin-top: 0; color: #333;">📅 Set Processing Reminders</h3>
                <div style="background-color: white; padding: 20px; border-radius: 5px; box-shadow: 0 1px 3px rgba(0,0,0,0.1);">
                    <p style="margin: 0 0 15px 0;">The attached .ics calendar file contains a daily reminder for processing pending stock-in items.</p>
                    <p style="margin: 0 0 20px 0;">Import it to your calendar to receive automatic alerts about urgent items requiring attention.</p>
                    
                    <div style="padding: 15px; background-color: #e8f5e9; border-radius: 5px;">
                        <p style="margin: 0 0 10px 0;"><strong>Reminder Schedule:</strong></p>
                        <ul style="margin: 0; padding-left: 20px;">
                            <li style="margin-bottom: 5px;">⏰ Daily at 8:30 AM - Review pending items</li>
                            <li>🔔 Alert 15 minutes before - Prepare for processing</li>
                        </ul>
                    </div>
                </div>
            </div>
        """
        
        # Add recommendations
        html += """
            <div style="margin-top: 20px; padding: 15px; background-color: #e8f5e9; border-radius: 5px;">
                <h4>📋 Recommendations:</h4>
                <ul>
                    <li><strong>Priority 1:</strong> Process all items pending > 14 days immediately</li>
                    <li><strong>Priority 2:</strong> Schedule items pending 8-14 days for this week</li>
                    <li><strong>Space Planning:</strong> Review warehouse capacity for incoming items</li>
                    <li><strong>Documentation:</strong> Ensure all customs and QC documents are complete</li>
                </ul>
            </div>
            
            <div class="footer">
                <p>This is an automated report from Inbound Logistics System</p>
                <p>Generated on: {datetime.now().strftime('%Y-%m-%d %H:%M')}</p>
                <p>For questions, contact: <a href="mailto:inbound@prostech.vn">inbound@prostech.vn</a></p>
            </div>
        </div>
        </body>
        </html>
        """.format(datetime=datetime)
        
        return html
    
    def _create_customs_clearance_html(self, po_df: pd.DataFrame, can_df: pd.DataFrame = None, 
                                       weeks_ahead: int = 4, date_type: str = 'etd') -> str:
        """Create HTML for customs clearance email"""
        # Process PO data
        if not po_df.empty:
            po_df[date_type] = pd.to_datetime(po_df[date_type])
        
        # Process CAN data
        if can_df is not None and not can_df.empty:
            can_df['arrival_date'] = pd.to_datetime(can_df['arrival_date'])
        
        # Summary stats
        total_pos = po_df['po_number'].nunique() if not po_df.empty else 0
        total_vendors = po_df['vendor_name'].nunique() if not po_df.empty else 0
        po_value = po_df['outstanding_arrival_amount_usd'].sum() if not po_df.empty else 0
        countries = po_df['vendor_country_name'].nunique() if not po_df.empty else 0
        
        total_cans = 0
        can_value = 0
        if can_df is not None and not can_df.empty:
            total_cans = can_df['arrival_note_number'].nunique()
            can_value = can_df['pending_value_usd'].sum()
            # Add countries from CAN if any new ones
            can_countries = can_df['vendor_country_name'].nunique()
            if can_countries > countries:
                countries = can_countries
        
        total_value = po_value + can_value
        date_type_upper = date_type.upper()
        
        html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <style>
                body {{
                    font-family: Arial, sans-serif;
                    line-height: 1.6;
                    color: #333;
                    margin: 0;
                    padding: 0;
                }}
                .header {{
                    background-color: #00796b;
                    color: white;
                    padding: 20px;
                    text-align: center;
                }}
                .content {{
                    padding: 20px;
                }}
                .summary-section {{
                    background-color: #f5f5f5;
                    border-radius: 5px;
                    padding: 20px;
                    margin: 20px 0;
                }}
                .section-divider {{
                    margin: 40px 0;
                    text-align: center;
                }}
                .section-divider h2 {{
                    display: inline-block;
                    background-color: #00796b;
                    color: white;
                    padding: 10px 30px;
                    border-radius: 5px;
                    margin: 0;
                }}
                .country-section {{
                    margin: 30px 0;
                    border: 1px solid #ddd;
                    border-radius: 5px;
                    padding: 15px;
                }}
                .country-header {{
                    background-color: #e0f2f1;
                    padding: 12px;
                    margin: -15px -15px 15px -15px;
                    border-radius: 5px 5px 0 0;
                    font-weight: bold;
                    font-size: 18px;
                }}
                .date-section {{
                    margin: 30px 0;
                    border: 1px solid #ddd;
                    border-radius: 5px;
                    padding: 15px;
                }}
                .date-header {{
                    background-color: #e8f5e9;
                    padding: 12px;
                    margin: -15px -15px 15px -15px;
                    border-radius: 5px 5px 0 0;
                    font-weight: bold;
                    font-size: 16px;
                }}
                table {{
                    width: 100%;
                    border-collapse: collapse;
                    margin-top: 10px;
                }}
                th, td {{
                    padding: 8px;
                    text-align: left;
                    border-bottom: 1px solid #ddd;
                }}
                th {{
                    background-color: #f8f9fa;
                    font-weight: bold;
                }}
                .info-box {{
                    background-color: #e3f2fd;
                    border: 1px solid #2196f3;
                    border-radius: 5px;
                    padding: 15px;
                    margin: 20px 0;
                }}
                .footer {{
                    margin-top: 30px;
                    padding: 20px;
                    background-color: #f8f9fa;
                    text-align: center;
                    font-size: 12px;
                    color: #666;
                }}
            </style>
        </head>
        <body>
            <div class="header">
                <h1>🛃 International Shipments</h1>
                <p>Customs Clearance Schedule & Arrivals (by {date_type_upper})</p>
            </div>
            
            <div class="content">
                <p>Dear Customs Clearance Team,</p>
                <p>Please find below the international shipments requiring customs clearance for the next {weeks_ahead} week{'s' if weeks_ahead > 1 else ''} based on {date_type_upper}.</p>
                
                <div class="summary-section">
                    <h3>📊 Summary Overview</h3>
                    <table width="100%" cellpadding="0" cellspacing="0" border="0">
                        <tr>
                            <td width="25%" align="center" style="padding: 15px;">
                                <table width="100%" cellpadding="0" cellspacing="0" border="0" style="background-color: white; border-radius: 5px; box-shadow: 0 2px 4px rgba(0,0,0,0.1);">
                                    <tr>
                                        <td align="center" style="padding: 15px;">
                                            <div style="font-size: 28px; font-weight: bold; color: #00796b;">{total_pos}</div>
                                            <div style="font-size: 14px; color: #666; margin-top: 5px;">Purchase Orders</div>
                                        </td>
                                    </tr>
                                </table>
                            </td>
                            <td width="25%" align="center" style="padding: 15px;">
                                <table width="100%" cellpadding="0" cellspacing="0" border="0" style="background-color: white; border-radius: 5px; box-shadow: 0 2px 4px rgba(0,0,0,0.1);">
                                    <tr>
                                        <td align="center" style="padding: 15px;">
                                            <div style="font-size: 28px; font-weight: bold; color: #00796b;">{total_cans}</div>
                                            <div style="font-size: 14px; color: #666; margin-top: 5px;">Arrivals (CANs)</div>
                                        </td>
                                    </tr>
                                </table>
                            </td>
                            <td width="25%" align="center" style="padding: 15px;">
                                <table width="100%" cellpadding="0" cellspacing="0" border="0" style="background-color: white; border-radius: 5px; box-shadow: 0 2px 4px rgba(0,0,0,0.1);">
                                    <tr>
                                        <td align="center" style="padding: 15px;">
                                            <div style="font-size: 28px; font-weight: bold; color: #00796b;">{countries}</div>
                                            <div style="font-size: 14px; color: #666; margin-top: 5px;">Countries</div>
                                        </td>
                                    </tr>
                                </table>
                            </td>
                            <td width="25%" align="center" style="padding: 15px;">
                                <table width="100%" cellpadding="0" cellspacing="0" border="0" style="background-color: white; border-radius: 5px; box-shadow: 0 2px 4px rgba(0,0,0,0.1);">
                                    <tr>
                                        <td align="center" style="padding: 15px;">
                                            <div style="font-size: 28px; font-weight: bold; color: #00796b;">${total_value/1000000:.1f}M</div>
                                            <div style="font-size: 14px; color: #666; margin-top: 5px;">Total Value (USD)</div>
                                        </td>
                                    </tr>
                                </table>
                            </td>
                        </tr>
                    </table>
                </div>
        """
        
        # Section 1: PO Schedule
        if not po_df.empty:
            html += f"""
                <div class="section-divider">
                    <h2>📅 Purchase Order {date_type_upper} Schedule</h2>
                </div>
            """
            
            # Group by country
            for country, country_df in po_df.groupby('vendor_country_name'):
                country_pos = country_df['po_number'].nunique()
                country_value = country_df['outstanding_arrival_amount_usd'].sum()
                
                html += f"""
                    <div class="country-section">
                        <div class="country-header">
                            🌍 {country} ({country_pos} POs, ${country_value/1000:.0f}K)
                        </div>
                        <table>
                            <tr>
                                <th>{date_type_upper}</th>
                                <th>PO Number</th>
                                <th>Vendor</th>
                                <th>PT Code</th>
                                <th>Product</th>
                                <th>Quantity</th>
                                <th>Value (USD)</th>
                                <th>Payment Terms</th>
                            </tr>
                """
                
                # Sort by date
                country_sorted = country_df.sort_values([date_type, 'po_number'])
                
                for _, row in country_sorted.iterrows():
                    html += f"""
                            <tr>
                                <td>{row[date_type].strftime('%b %d')}</td>
                                <td>{row['po_number']}</td>
                                <td>{row['vendor_name']}</td>
                                <td>{row['pt_code']}</td>
                                <td>{row['product_name']}</td>
                                <td>{row['pending_standard_arrival_quantity']:,.0f}</td>
                                <td>${row['outstanding_arrival_amount_usd']:,.0f}</td>
                                <td>{row['payment_term']}</td>
                            </tr>
                    """
                
                html += """
                        </table>
                    </div>
                """
        
        # Section 2: Container Arrivals
        if can_df is not None and not can_df.empty:
            html += """
                <div class="section-divider">
                    <h2>📦 Container Arrivals (CANs)</h2>
                </div>
            """
            
            # Group by arrival date
            can_df['arrival_week'] = can_df['arrival_date'].dt.to_period('W').dt.start_time
            
            for week, week_df in can_df.groupby('arrival_week'):
                week_start = week
                week_end = week + timedelta(days=6)
                week_cans = week_df['arrival_note_number'].nunique()
                week_value = week_df['pending_value_usd'].sum()
                
                html += f"""
                    <div class="date-section">
                        <div class="date-header">
                            📅 Week: {week_start.strftime('%b %d')} - {week_end.strftime('%b %d, %Y')} 
                            ({week_cans} CANs, ${week_value/1000:.0f}K)
                        </div>
                """
                
                # Group by arrival date within week
                for arrival_date, date_df in week_df.groupby(week_df['arrival_date'].dt.date):
                    html += f"""
                        <p style="font-weight: bold; margin-top: 15px;">
                            Arrival Date: {arrival_date.strftime('%B %d, %Y')}
                        </p>
                        <table>
                            <tr>
                                <th width="120">CAN Number</th>
                                <th width="100">PO Number</th>
                                <th width="150">Vendor</th>
                                <th width="100">Country</th>
                                <th width="150">Product</th>
                                <th width="80">PT Code</th>
                                <th width="100">Quantity</th>
                                <th width="100">Value (USD)</th>
                                <th width="80">Status</th>
                            </tr>
                    """
                    
                    for _, row in date_df.iterrows():
                        html += f"""
                            <tr>
                                <td>{row['arrival_note_number']}</td>
                                <td>{row['po_number']}</td>
                                <td>{row['vendor']}</td>
                                <td>{row['vendor_country_name']}</td>
                                <td>{row['product_name']}</td>
                                <td>{row['pt_code']}</td>
                                <td>{row['pending_quantity']:,.0f}</td>
                                <td>${row['pending_value_usd']:,.0f}</td>
                                <td>{row['can_status']}</td>
                            </tr>
                        """
                    
                    html += "</table>"
                
                html += "</div>"
        
        # Add calendar information with links
        try:
            calendar_gen = InboundCalendarGenerator()
            google_links = calendar_gen.create_customs_google_calendar_links(po_df, can_df, date_type)
            outlook_links = calendar_gen.create_customs_outlook_calendar_links(po_df, can_df, date_type)
        except Exception as e:
            logger.warning(f"Error creating calendar links: {e}")
            google_links = None
            outlook_links = None
        
        if google_links and outlook_links:
            html += """
                <div style="margin: 40px 0; border: 1px solid #ddd; border-radius: 8px; padding: 25px; background-color: #fafafa;">
                    <h3 style="margin-top: 0; color: #333;">📅 Customs Calendar Events</h3>
                    <p style="color: #666; margin-bottom: 20px;">Click below to add customs clearance events to your calendar:</p>
                    
                    <div style="background-color: white; padding: 20px; border-radius: 5px; box-shadow: 0 1px 3px rgba(0,0,0,0.1);">
            """
            
            # Show first 5 calendar links
            for i, g_link in enumerate(google_links[:5]):
                o_link = outlook_links[i] if i < len(outlook_links) else None
                date_str = g_link['date'].strftime('%b %d')
                event_type = g_link['type']
                country = g_link['country']
                
                type_emoji = "📅" if event_type == "PO" else "📦"
                type_text = f"PO {date_type_upper}" if event_type == "PO" else "CAN Arrival"
                
                html += f"""
                        <div style="margin: 15px 0; padding: 10px 0; border-bottom: 1px solid #eee;">
                            <span style="font-weight: bold; display: inline-block; width: 80px;">{date_str}:</span>
                            <span style="color: #666; font-size: 14px;">{type_emoji} {type_text} - {country}</span>
                            <div style="margin-top: 5px; margin-left: 80px;">
                                <a href="{g_link['link']}" target="_blank" 
                                   style="margin-right: 15px; color: #4285f4; text-decoration: none; font-weight: 500;">
                                   📅 Google Calendar
                                </a>
                """
                
                if o_link:
                    html += f"""
                                <a href="{o_link['link']}" target="_blank" 
                                   style="color: #0078d4; text-decoration: none; font-weight: 500;">
                                   📅 Outlook
                                </a>
                    """
                
                html += """
                            </div>
                        </div>
                """
            
            if len(google_links) > 5:
                html += f"""
                        <div style="margin-top: 20px; padding-top: 15px; border-top: 1px solid #eee; text-align: center;">
                            <p style="font-style: italic; color: #999; margin: 0;">
                                ... and {len(google_links) - 5} more events
                            </p>
                        </div>
                """
            
            html += f"""
                        <div style="margin-top: 20px; padding: 15px; background-color: #e0f2f1; border-radius: 5px;">
                            <p style="margin: 0 0 10px 0;"><strong>Event Types:</strong></p>
                            <ul style="margin: 0; padding-left: 20px;">
                                <li style="margin-bottom: 5px;">📅 PO {date_type_upper} - Morning events (8:00 AM - 12:00 PM)</li>
                                <li style="margin-bottom: 5px;">📦 CAN Arrivals - Afternoon events (2:00 PM - 4:00 PM)</li>
                                <li>⏰ Reminders set 1 day before for preparation</li>
                            </ul>
                        </div>
                    </div>
                    
                    <p style="margin-top: 20px; margin-bottom: 0; color: #666; font-size: 14px; text-align: center;">
                        Or download the attached .ics file to import all customs events into any calendar application
                    </p>
                </div>
            """
        else:
            # If no calendar links available
            html += """
                <div style="margin: 40px 0; border: 1px solid #ddd; border-radius: 8px; padding: 25px; background-color: #fafafa;">
                    <h3 style="margin-top: 0; color: #333;">📅 Calendar Integration</h3>
                    <p style="color: #666; margin-bottom: 0;">
                        Download the attached .ics file to import customs clearance events into your calendar application.
                    </p>
                </div>
            """
        
        # Add customs documentation reminder
        html += """
            <div class="info-box">
                <h4>📋 Required Documentation:</h4>
                <table width="100%" cellpadding="0" cellspacing="0" border="0">
                    <tr>
                        <td width="50%" valign="top">
                            <strong>For Purchase Orders:</strong>
                            <ul>
                                <li>Commercial Invoice</li>
                                <li>Packing List</li>
                                <li>Bill of Lading / Airway Bill</li>
                                <li>Certificate of Origin</li>
                                <li>Import License (if applicable)</li>
                            </ul>
                        </td>
                        <td width="50%" valign="top">
                            <strong>For Container Arrivals:</strong>
                            <ul>
                                <li>Container Arrival Note</li>
                                <li>Customs Declaration Form</li>
                                <li>Phytosanitary Certificate (if applicable)</li>
                                <li>Quality Certificate</li>
                                <li>Duty Payment Receipt</li>
                            </ul>
                        </td>
                    </tr>
                </table>
            </div>
            
            <div class="footer">
                <p>This is an automated email from Inbound Logistics System</p>
                <p>For questions, contact: <a href="mailto:inbound@prostech.vn">inbound@prostech.vn</a></p>
            </div>
        </div>
        </body>
        </html>
        """
        
        return html
    

    def _create_vendor_po_schedule_html(self, po_df: pd.DataFrame, vendor_name: str, 
                                weeks_ahead: int = 4, include_overdue: bool = True,
                                overdue_count: int = 0, upcoming_count: int = 0,
                                contact_name: str = None, date_type: str = 'etd') -> str:
        """Create HTML content specifically for vendors with overdue and upcoming sections"""
        # Process data
        po_df[date_type] = pd.to_datetime(po_df[date_type])
        today = datetime.now().date()
        
        # Separate overdue and upcoming
        overdue_pos = po_df[po_df[date_type].dt.date < today] if include_overdue else pd.DataFrame()
        upcoming_pos = po_df[po_df[date_type].dt.date >= today]
        
        # Calculate totals
        total_pos = po_df['po_number'].nunique()
        total_items = len(po_df)
        total_value = po_df['outstanding_arrival_amount_usd'].sum()
        
        # Greeting
        if contact_name:
            greeting = f"Dear {contact_name},"
        else:
            greeting = f"Dear {vendor_name} Team,"
        
        date_type_upper = date_type.upper()
        
        # KHỞI TẠO BIẾN HTML
        html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <style>
                body {{
                    font-family: Arial, sans-serif;
                    line-height: 1.6;
                    color: #333;
                    margin: 0;
                    padding: 0;
                }}
                .header {{
                    background-color: #2e7d32;
                    color: white;
                    padding: 20px;
                    text-align: center;
                }}
                .content {{
                    padding: 20px;
                }}
                .summary-section {{
                    background-color: #f5f5f5;
                    border-radius: 5px;
                    padding: 20px;
                    margin: 20px 0;
                }}
                .overdue-section {{
                    border: 2px solid #d32f2f;
                    border-radius: 5px;
                    padding: 15px;
                    margin: 20px 0;
                    background-color: #ffebee;
                }}
                .upcoming-section {{
                    border: 1px solid #2e7d32;
                    border-radius: 5px;
                    padding: 15px;
                    margin: 20px 0;
                }}
                .section-header {{
                    font-weight: bold;
                    font-size: 18px;
                    margin-bottom: 10px;
                }}
                .overdue-header {{
                    color: #d32f2f;
                }}
                .upcoming-header {{
                    color: #2e7d32;
                }}
                table {{
                    width: 100%;
                    border-collapse: collapse;
                    margin-top: 10px;
                }}
                th, td {{
                    padding: 8px;
                    text-align: left;
                    border-bottom: 1px solid #ddd;
                }}
                th {{
                    background-color: #f8f9fa;
                    font-weight: bold;
                }}
                .overdue {{
                    color: #d32f2f;
                    font-weight: bold;
                }}
                .footer {{
                    margin-top: 30px;
                    padding: 20px;
                    background-color: #f8f9fa;
                    text-align: center;
                    font-size: 12px;
                    color: #666;
                }}
            </style>
        </head>
        <body>
            <div class="header">
                <h1>📦 Purchase Order Schedule</h1>
                <p>Delivery Schedule for {vendor_name} (by {date_type_upper})</p>
            </div>
            
            <div class="content">
                <p>{greeting}</p>
                <p>Please find below the status of our purchase orders with our company.</p>
                
                <div class="summary-section">
                    <h3>📊 Summary</h3>
                    <table width="100%" cellpadding="0" cellspacing="0" border="0">
                        <tr>
                            <td width="25%" align="center" style="padding: 15px;">
                                <div style="font-size: 24px; font-weight: bold;">{total_pos}</div>
                                <div style="font-size: 14px; color: #666;">Total POs</div>
                            </td>
                            <td width="25%" align="center" style="padding: 15px;">
                                <div style="font-size: 24px; font-weight: bold; color: #d32f2f;">{overdue_count}</div>
                                <div style="font-size: 14px; color: #666;">Overdue POs ({date_type_upper})</div>
                            </td>
                            <td width="25%" align="center" style="padding: 15px;">
                                <div style="font-size: 24px; font-weight: bold; color: #2e7d32;">{upcoming_count}</div>
                                <div style="font-size: 14px; color: #666;">Upcoming POs</div>
                            </td>
                            <td width="25%" align="center" style="padding: 15px;">
                                <div style="font-size: 24px; font-weight: bold;">${total_value:,.0f}</div>
                                <div style="font-size: 14px; color: #666;">Total Value</div>
                            </td>
                        </tr>
                    </table>
                </div>
        """
        
        # Overdue POs section
        if include_overdue and not overdue_pos.empty:
            overdue_value = overdue_pos['outstanding_arrival_amount_usd'].sum()
            
            html += f"""
                <div class="overdue-section">
                    <div class="section-header overdue-header">
                        🚨 OVERDUE PURCHASE ORDERS ({overdue_count} POs, ${overdue_value:,.0f})
                    </div>
                    <p style="color: #d32f2f; margin: 10px 0;">
                        The following purchase orders have passed their {date_type_upper}. Please update us on their status immediately.
                    </p>
                    <table>
                        <tr>
                            <th>{date_type_upper}</th>
                            <th>Days Overdue</th>
                            <th>PO Number</th>
                            <th>PT Code</th>
                            <th>Product</th>
                            <th>Outstanding Qty</th>
                            <th>Value (USD)</th>
                            <th>Payment Terms</th>
                        </tr>
            """
            
            # Sort by days overdue (most overdue first)
            overdue_sorted = overdue_pos.copy()
            overdue_sorted['days_overdue'] = overdue_sorted[date_type].apply(
                lambda x: (today - x.date()).days
            )
            overdue_sorted = overdue_sorted.sort_values('days_overdue', ascending=False)
            
            for _, row in overdue_sorted.iterrows():
                days_overdue = row['days_overdue']
                
                html += f"""
                        <tr>
                            <td class="overdue">{row[date_type].strftime('%b %d, %Y')}</td>
                            <td class="overdue">{days_overdue} days</td>
                            <td>{row['po_number']}</td>
                            <td>{row['pt_code']}</td>
                            <td>{row['product_name']}</td>
                            <td>{row['pending_standard_arrival_quantity']:,.0f}</td>
                            <td>${row['outstanding_arrival_amount_usd']:,.0f}</td>
                            <td>{row['payment_term']}</td>
                        </tr>
                """
            
            html += f"""
                    </table>
                    <p style="margin-top: 15px; font-weight: bold; color: #d32f2f;">
                        ⚠️ Action Required: Please provide updated {date_type_upper}s and shipment status for all overdue items.
                    </p>
                </div>
            """
        
        # Upcoming POs section
        if not upcoming_pos.empty:
            upcoming_value = upcoming_pos['outstanding_arrival_amount_usd'].sum()
            
            html += f"""
                <div class="upcoming-section">
                    <div class="section-header upcoming-header">
                        📅 UPCOMING DELIVERIES - Next {weeks_ahead} Week{'s' if weeks_ahead > 1 else ''} ({upcoming_count} POs, ${upcoming_value:,.0f})
                    </div>
                    <table>
                        <tr>
                            <th>{date_type_upper}</th>
                            <th>Days Until {date_type_upper}</th>
                            <th>PO Number</th>
                            <th>PT Code</th>
                            <th>Product</th>
                            <th>Outstanding Qty</th>
                            <th>Value (USD)</th>
                            <th>Trade Terms</th>
                        </tr>
            """
            
            # Sort by date (nearest first)
            upcoming_sorted = upcoming_pos.sort_values(date_type)
            
            for _, row in upcoming_sorted.iterrows():
                days_until = (row[date_type].date() - today).days
                
                html += f"""
                        <tr>
                            <td>{row[date_type].strftime('%b %d, %Y')}</td>
                            <td>{days_until} days</td>
                            <td>{row['po_number']}</td>
                            <td>{row['pt_code']}</td>
                            <td>{row['product_name']}</td>
                            <td>{row['pending_standard_arrival_quantity']:,.0f}</td>
                            <td>${row['outstanding_arrival_amount_usd']:,.0f}</td>
                            <td>{row['trade_term']}</td>
                        </tr>
                """
            
            html += """
                    </table>
                </div>
            """
        # Add Google Calendar links
        if not upcoming_pos.empty:
            try:
                calendar_gen = InboundCalendarGenerator()
                google_cal_links = calendar_gen.create_google_calendar_links(upcoming_pos, date_type)
                outlook_cal_links = calendar_gen.create_outlook_calendar_links(upcoming_pos, date_type)
            except Exception as e:
                logger.warning(f"Error creating calendar links: {e}")
                google_cal_links = None
                outlook_cal_links = None
            
            # Show calendar links only if available
            if google_cal_links and outlook_cal_links:
                html += f"""
                    <div style="margin: 40px 0; border: 1px solid #ddd; border-radius: 8px; padding: 25px; background-color: #fafafa;">
                        <h3 style="margin-top: 0; color: #333;">📅 Add to Your Calendar</h3>
                        <p style="color: #666; margin-bottom: 25px;">Click below to add individual PO arrival dates (by {date_type_upper}) to your calendar:</p>
                        
                        <div style="background-color: white; padding: 20px; border-radius: 5px; box-shadow: 0 1px 3px rgba(0,0,0,0.1);">
                """
                
                # Add individual date links (show first 5)
                for i, gcal_link in enumerate(google_cal_links[:5]):
                    date_str = gcal_link['date'].strftime('%b %d')
                    is_urgent = gcal_link.get('is_urgent', False)
                    date_style = 'color: #d32f2f; font-weight: bold;' if is_urgent else 'font-weight: bold;'
                    
                    html += f"""
                            <div style="margin: 15px 0; padding: 10px 0; border-bottom: 1px solid #eee;">
                                <span style="{date_style} display: inline-block; width: 80px;">{date_str}:</span>
                                <a href="{gcal_link['link']}" target="_blank" 
                                style="margin: 0 15px; color: #4285f4; text-decoration: none; font-weight: 500;">
                                📅 Google Calendar
                                </a>
                                <a href="{outlook_cal_links[i]['link']}" target="_blank" 
                                style="margin: 0 15px; color: #0078d4; text-decoration: none; font-weight: 500;">
                                📅 Outlook
                                </a>
                            </div>
                    """
                
                if len(google_cal_links) > 5:
                    html += f"""
                            <div style="margin-top: 20px; padding-top: 15px; border-top: 1px solid #eee; text-align: center;">
                                <p style="font-style: italic; color: #999; margin: 0;">
                                    ... and {len(google_cal_links) - 5} more dates
                                </p>
                            </div>
                    """
                
                html += """
                        </div>
                        
                        <p style="margin-top: 20px; margin-bottom: 0; color: #666; font-size: 14px; text-align: center;">
                            Or download the attached .ics file to import all dates into any calendar application
                        </p>
                    </div>
                """
        


        # Add important reminders
        html += f"""
                <div style="margin-top: 30px; padding: 15px; background-color: #e3f2fd; border-radius: 5px;">
                    <h4>📋 Important Reminders:</h4>
                    <ul>
                        <li><strong>Overdue POs:</strong> Please update {date_type_upper}s and provide shipping status immediately</li>
                        <li><strong>Documentation:</strong> Ensure all shipping documents are prepared in advance</li>
                        <li><strong>Quality Certificates:</strong> Must accompany each shipment</li>
                        <li><strong>{date_type_upper} Changes:</strong> Notify us at least 3 days before original {date_type_upper}</li>
                        <li><strong>Contact:</strong> For any questions, reach our procurement team</li>
                    </ul>
                </div>
                
                <div class="footer">
                    <p>This is an automated email from Prostech Inbound Logistics</p>
                    <p>For questions, please contact: <a href="mailto:procurement@prostech.vn">procurement@prostech.vn</a></p>
                    <p>Phone: +84 33 476273</p>
                </div>
            </div>
        </body>
        </html>
        """
        
        return html