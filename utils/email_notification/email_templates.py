# utils/email_notification/email_templates.py
"""
HTML email template generation for email notifications
Creates formatted, professional email content with styles and data tables
"""

import pandas as pd
from datetime import datetime, timedelta
import logging
from utils.email_notification.calendar_builder import CalendarBuilder

logger = logging.getLogger(__name__)


class EmailTemplates:
    """Generate HTML email content for various notification types"""
    
    # ========================
    # BASE STYLES
    # ========================
    
    @staticmethod
    def _get_base_styles():
        """Get base CSS styles for email templates"""
        return """
        <style>
            body {
                font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
                line-height: 1.6;
                color: #333;
                max-width: 900px;
                margin: 0 auto;
                padding: 20px;
                background-color: #f5f5f5;
            }
            .container {
                background-color: white;
                padding: 30px;
                border-radius: 8px;
                box-shadow: 0 2px 4px rgba(0,0,0,0.1);
            }
            .header {
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                color: white;
                padding: 25px;
                border-radius: 8px 8px 0 0;
                margin: -30px -30px 30px -30px;
            }
            .header h1 {
                margin: 0;
                font-size: 24px;
            }
            .section-header {
                background-color: #f8f9fa;
                padding: 12px 15px;
                border-left: 4px solid #667eea;
                margin: 25px 0 15px 0;
                font-weight: bold;
                font-size: 16px;
            }
            .overdue-header {
                background-color: #ffebee;
                border-left-color: #d32f2f;
                color: #d32f2f;
            }
            .upcoming-header {
                background-color: #e8f5e9;
                border-left-color: #4caf50;
                color: #2e7d32;
            }
            table {
                width: 100%;
                border-collapse: collapse;
                margin: 15px 0;
                font-size: 14px;
            }
            th {
                background-color: #f8f9fa;
                padding: 12px 8px;
                text-align: left;
                font-weight: 600;
                border-bottom: 2px solid #dee2e6;
            }
            td {
                padding: 10px 8px;
                border-bottom: 1px solid #dee2e6;
            }
            tr:hover {
                background-color: #f8f9fa;
            }
            .overdue {
                color: #d32f2f;
                font-weight: bold;
            }
            .urgent {
                color: #f57c00;
                font-weight: bold;
            }
            .footer {
                margin-top: 30px;
                padding-top: 20px;
                border-top: 1px solid #dee2e6;
                text-align: center;
                color: #6c757d;
                font-size: 12px;
            }
            .footer a {
                color: #667eea;
                text-decoration: none;
            }
            .summary-box {
                background-color: #f8f9fa;
                padding: 15px;
                border-radius: 5px;
                margin: 15px 0;
            }
            .upcoming-section {
                margin-top: 30px;
            }
        </style>
        """
    
    # ========================
    # PO SCHEDULE EMAIL
    # ========================
    
    @staticmethod
    def create_po_schedule_html(po_df, recipient_name, is_custom_recipient=False, 
                                weeks_ahead=4, date_type='etd'):
        """Create HTML content for PO schedule email"""
        try:
            if po_df is None or po_df.empty:
                return "<html><body><p>No PO data available</p></body></html>"
            
            # Ensure date column is datetime
            po_df[date_type] = pd.to_datetime(po_df[date_type], errors='coerce')
            po_df = po_df.dropna(subset=[date_type])
            
            date_type_upper = date_type.upper()
            today = datetime.now().date()
            
            # Separate overdue and upcoming POs
            overdue_pos = po_df[po_df[date_type].dt.date < today].copy()
            upcoming_pos = po_df[po_df[date_type].dt.date >= today].copy()
            
            # Calculate metrics
            overdue_count = len(overdue_pos)
            upcoming_count = len(upcoming_pos)
            
            # Start HTML
            html = f"""
            <html>
            <head>
                {EmailTemplates._get_base_styles()}
            </head>
            <body>
                <div class="container">
                    <div class="header">
                        <h1>📅 Purchase Order Schedule</h1>
                        <p style="margin: 5px 0 0 0;">{'Overview Report' if is_custom_recipient else f'For: {recipient_name}'}</p>
                    </div>
            """
            
            # Greeting
            if is_custom_recipient:
                html += f"""
                    <p>Hello Team,</p>
                    <p>Here is the purchase order schedule for the next {weeks_ahead} week{'s' if weeks_ahead > 1 else ''} based on <strong>{date_type_upper}</strong> dates:</p>
                """
            else:
                html += f"""
                    <p>Hello {recipient_name},</p>
                    <p>This is your purchase order schedule for the next {weeks_ahead} week{'s' if weeks_ahead > 1 else ''} based on <strong>{date_type_upper}</strong> dates:</p>
                """
            
            # Summary box
            total_value = po_df['outstanding_arrival_amount_usd'].sum()
            vendor_count = po_df['vendor_name'].nunique() if 'vendor_name' in po_df.columns else 0
            
            html += f"""
                <div class="summary-box">
                    <strong>📊 Summary:</strong><br>
                    Total POs: {len(po_df)} | Vendors: {vendor_count} | Total Value: ${total_value:,.0f}
                    {'<br><span class="overdue">⚠️ ' + str(overdue_count) + ' Overdue POs</span>' if overdue_count > 0 else ''}
                </div>
            """
            
            # Overdue POs section
            if not overdue_pos.empty:
                overdue_value = overdue_pos['outstanding_arrival_amount_usd'].sum()
                
                html += f"""
                    <div class="section-header overdue-header">
                        ⚠️ OVERDUE DELIVERIES ({overdue_count} POs, ${overdue_value:,.0f})
                    </div>
                    <table>
                        <tr>
                            <th>{date_type_upper}</th>
                            <th>Days Overdue</th>
                            <th>PO Number</th>
                            <th>PT Code</th>
                            <th>Product</th>
                            <th>Outstanding Qty</th>
                            <th>Value (USD)</th>
                            <th>Payment Term</th>
                        </tr>
                """
                
                # Add days overdue column
                overdue_sorted = overdue_pos.copy()
                overdue_sorted['days_overdue'] = overdue_sorted[date_type].apply(
                    lambda x: (today - x.date()).days if pd.notna(x) else 0
                )
                overdue_sorted = overdue_sorted.sort_values('days_overdue', ascending=False)
                
                for _, row in overdue_sorted.iterrows():
                    days_overdue = row['days_overdue']
                    
                    html += f"""
                        <tr>
                            <td class="overdue">{row[date_type].strftime('%b %d, %Y')}</td>
                            <td class="overdue">{days_overdue} days</td>
                            <td>{row['po_number']}</td>
                            <td>{row.get('pt_code', 'N/A')}</td>
                            <td>{row.get('product_name', 'N/A')}</td>
                            <td>{row.get('pending_standard_arrival_quantity', 0):,.0f}</td>
                            <td>${row.get('outstanding_arrival_amount_usd', 0):,.0f}</td>
                            <td>{row.get('payment_term', 'N/A')}</td>
                        </tr>
                    """
                
                html += f"""
                    </table>
                    <p style="margin-top: 15px; font-weight: bold; color: #d32f2f;">
                        ⚠️ Action Required: Please provide updated {date_type_upper}s and shipment status for all overdue items.
                    </p>
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
                            <td>{row.get('pt_code', 'N/A')}</td>
                            <td>{row.get('product_name', 'N/A')}</td>
                            <td>{row.get('pending_standard_arrival_quantity', 0):,.0f}</td>
                            <td>${row.get('outstanding_arrival_amount_usd', 0):,.0f}</td>
                            <td>{row.get('trade_term', 'N/A')}</td>
                        </tr>
                    """
                
                html += """
                    </table>
                </div>
                """
            
            # Add calendar links if there are upcoming POs
            if not upcoming_pos.empty:
                try:
                    calendar_gen = CalendarBuilder()
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
            
            # Important reminders
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
            
        except Exception as e:
            logger.error(f"Error creating PO schedule HTML: {e}", exc_info=True)
            return f"<html><body><p>Error creating email content: {str(e)}</p></body></html>"
    
    # ========================
    # CRITICAL ALERTS EMAIL
    # ========================
    
    @staticmethod
    def create_critical_alerts_html(data_dict, recipient_name, is_custom_recipient=False, date_type='etd'):
        """Create HTML content for critical alerts email"""
        try:
            overdue_pos = data_dict.get('overdue_pos', pd.DataFrame())
            pending_stockin = data_dict.get('pending_stockin', pd.DataFrame())
            
            date_type_upper = date_type.upper()
            today = datetime.now().date()
            
            # Count items
            overdue_count = len(overdue_pos) if not overdue_pos.empty else 0
            pending_count = len(pending_stockin) if not pending_stockin.empty else 0
            
            # Start HTML
            html = f"""
            <html>
            <head>
                {EmailTemplates._get_base_styles()}
            </head>
            <body>
                <div class="container">
                    <div class="header" style="background: linear-gradient(135deg, #d32f2f 0%, #c62828 100%);">
                        <h1>🚨 URGENT: Critical Alerts</h1>
                        <p style="margin: 5px 0 0 0;">{'Overview Report' if is_custom_recipient else f'For: {recipient_name}'}</p>
                    </div>
            """
            
            # Greeting
            if is_custom_recipient:
                html += """
                    <p><strong>Hello Team,</strong></p>
                    <p style="color: #d32f2f; font-weight: bold;">This is an urgent alert for items requiring immediate attention:</p>
                """
            else:
                html += f"""
                    <p><strong>Hello {recipient_name},</strong></p>
                    <p style="color: #d32f2f; font-weight: bold;">This is an urgent alert for items under your responsibility requiring immediate attention:</p>
                """
            
            # Summary
            html += f"""
                <div class="summary-box" style="background-color: #ffebee; border-left: 4px solid #d32f2f;">
                    <strong>🔔 Alert Summary:</strong><br>
                    <span style="color: #d32f2f; font-weight: bold;">
                        {overdue_count} Overdue POs (by {date_type_upper}) | {pending_count} Pending Stock-in Items
                    </span>
                </div>
            """
            
            # Overdue POs section
            if not overdue_pos.empty:
                overdue_value = overdue_pos['outstanding_arrival_amount_usd'].sum()
                
                # Calculate max days overdue
                overdue_pos[date_type] = pd.to_datetime(overdue_pos[date_type])
                overdue_pos['days_overdue'] = overdue_pos[date_type].apply(
                    lambda x: (datetime.now().date() - x.date()).days if pd.notna(x) else 0
                )
                max_days_overdue = overdue_pos['days_overdue'].max()
                
                html += f"""
                    <div class="section-header overdue-header">
                        ⚠️ OVERDUE PURCHASE ORDERS ({overdue_count} POs)
                    </div>
                    <p style="color: #d32f2f; font-weight: bold;">
                        Total Value: ${overdue_value:,.0f} | Maximum overdue: {max_days_overdue} days
                    </p>
                    <table>
                        <tr>
                            <th>{date_type_upper}</th>
                            <th>Days Overdue</th>
                            <th>PO Number</th>
                            <th>Vendor</th>
                            <th>Product</th>
                            <th>Pending Qty</th>
                            <th>Value (USD)</th>
                        </tr>
                """
                
                # Sort by days overdue (most critical first)
                overdue_sorted = overdue_pos.sort_values('days_overdue', ascending=False)
                
                for _, row in overdue_sorted.iterrows():
                    days_overdue = row['days_overdue']
                    urgency_class = "overdue" if days_overdue > 7 else "urgent"
                    
                    html += f"""
                        <tr>
                            <td class="{urgency_class}">{row[date_type].strftime('%b %d, %Y')}</td>
                            <td class="{urgency_class}">{days_overdue} days</td>
                            <td>{row['po_number']}</td>
                            <td>{row.get('vendor_name', 'N/A')}</td>
                            <td>{row.get('product_name', 'N/A')}</td>
                            <td>{row.get('pending_standard_arrival_quantity', 0):,.0f}</td>
                            <td>${row.get('outstanding_arrival_amount_usd', 0):,.0f}</td>
                        </tr>
                    """
                
                html += """
                    </table>
                    <p style="margin-top: 15px; padding: 10px; background-color: #ffebee; border-radius: 5px;">
                        <strong style="color: #d32f2f;">⚠️ IMMEDIATE ACTION REQUIRED:</strong><br>
                        1. Contact vendors immediately to get updated delivery status<br>
                        2. Update ETDs/ETAs in the system<br>
                        3. Notify relevant stakeholders of any delays
                    </p>
                """
            
            # Pending stock-in section
            if not pending_stockin.empty:
                pending_value = pending_stockin['pending_value_usd'].sum()
                
                # Categorize by urgency
                urgent_items = pending_stockin[pending_stockin['days_since_arrival'] > 7]
                critical_items = pending_stockin[pending_stockin['days_since_arrival'] > 14]
                
                html += f"""
                    <div class="section-header" style="background-color: #fff3e0; border-left-color: #f57c00; color: #f57c00;">
                        📦 PENDING STOCK-IN ITEMS ({pending_count} items)
                    </div>
                    <p style="color: #f57c00; font-weight: bold;">
                        Total Value: ${pending_value:,.0f} | 
                        Urgent (>7 days): {len(urgent_items)} | 
                        Critical (>14 days): {len(critical_items)}
                    </p>
                    <table>
                        <tr>
                            <th>CAN Number</th>
                            <th>PO Number</th>
                            <th>Product</th>
                            <th>Vendor</th>
                            <th>Arrival Date</th>
                            <th>Days Pending</th>
                            <th>Pending Qty</th>
                            <th>Value (USD)</th>
                        </tr>
                """
                
                # Sort by days pending (most critical first)
                pending_sorted = pending_stockin.sort_values('days_since_arrival', ascending=False)
                
                for _, row in pending_sorted.iterrows():
                    days_pending = row['days_since_arrival']
                    urgency_class = "overdue" if days_pending > 14 else "urgent" if days_pending > 7 else ""
                    urgency_icon = "🔴" if days_pending > 14 else "🟡" if days_pending > 7 else "⚪"
                    
                    html += f"""
                        <tr>
                            <td>{urgency_icon} {row['arrival_note_number']}</td>
                            <td>{row.get('po_number', 'N/A')}</td>
                            <td>{row.get('product_name', 'N/A')}</td>
                            <td>{row.get('vendor_name', 'N/A')}</td>
                            <td>{pd.to_datetime(row['arrival_date']).strftime('%b %d, %Y')}</td>
                            <td class="{urgency_class}">{days_pending} days</td>
                            <td>{row.get('pending_quantity', 0):,.0f}</td>
                            <td>${row.get('pending_value_usd', 0):,.0f}</td>
                        </tr>
                    """
                
                html += """
                    </table>
                    <p style="margin-top: 15px; padding: 10px; background-color: #fff3e0; border-radius: 5px;">
                        <strong style="color: #f57c00;">⚠️ ACTION REQUIRED:</strong><br>
                        1. Prioritize items pending >14 days (Critical)<br>
                        2. Complete stock-in processing for items >7 days (Urgent)<br>
                        3. Coordinate with warehouse team for immediate processing
                    </p>
                """
            
            # Footer
            html += """
                <div style="margin-top: 30px; padding: 15px; background-color: #e3f2fd; border-radius: 5px;">
                    <h4>📋 Next Steps:</h4>
                    <ol>
                        <li>Review all items flagged in this alert</li>
                        <li>Take immediate corrective action</li>
                        <li>Update system with current status</li>
                        <li>Escalate if vendor/warehouse support is needed</li>
                    </ol>
                </div>
                
                <div class="footer">
                    <p>This is an automated urgent alert from Prostech Inbound Logistics</p>
                    <p>For immediate support: <a href="mailto:procurement@prostech.vn">procurement@prostech.vn</a></p>
                    <p>Phone: +84 33 476273</p>
                </div>
            </div>
        </body>
        </html>
            """
            
            return html
            
        except Exception as e:
            logger.error(f"Error creating critical alerts HTML: {e}", exc_info=True)
            return f"<html><body><p>Error creating email content: {str(e)}</p></body></html>"
    
    # ========================
    # PENDING STOCK-IN EMAIL
    # ========================
    
    @staticmethod
    def create_pending_stockin_html(can_df, recipient_name, is_custom_recipient=False):
        """Create HTML content for pending stock-in email"""
        try:
            if can_df is None or can_df.empty:
                return "<html><body><p>No pending stock-in data available</p></body></html>"
            
            # Categorize by urgency
            critical_items = can_df[can_df['days_since_arrival'] > 14]
            urgent_items = can_df[can_df['days_since_arrival'] > 7]
            normal_items = can_df[can_df['days_since_arrival'] <= 7]
            
            total_value = can_df['pending_value_usd'].sum()
            
            # Start HTML
            html = f"""
            <html>
            <head>
                {EmailTemplates._get_base_styles()}
            </head>
            <body>
                <div class="container">
                    <div class="header" style="background: linear-gradient(135deg, #f57c00 0%, #ef6c00 100%);">
                        <h1>📦 Pending Stock-in Items</h1>
                        <p style="margin: 5px 0 0 0;">{'Overview Report' if is_custom_recipient else f'For: {recipient_name}'}</p>
                    </div>
            """
            
            # Greeting
            if is_custom_recipient:
                html += """
                    <p>Hello Team,</p>
                    <p>The following items have arrived but are pending stock-in processing:</p>
                """
            else:
                html += f"""
                    <p>Hello {recipient_name},</p>
                    <p>The following items from your purchase orders have arrived but are pending stock-in processing:</p>
                """
            
            # Summary
            html += f"""
                <div class="summary-box">
                    <strong>📊 Summary:</strong><br>
                    Total Items: {len(can_df)} | Total Value: ${total_value:,.0f}<br>
                    <span style="color: #d32f2f; font-weight: bold;">🔴 Critical (>14 days): {len(critical_items)}</span> | 
                    <span style="color: #f57c00; font-weight: bold;">🟡 Urgent (>7 days): {len(urgent_items)}</span> | 
                    <span>⚪ Normal (≤7 days): {len(normal_items)}</span>
                </div>
            """
            
            # Critical items
            if not critical_items.empty:
                critical_value = critical_items['pending_value_usd'].sum()
                
                html += f"""
                    <div class="section-header overdue-header">
                        🔴 CRITICAL - Pending >14 Days ({len(critical_items)} items, ${critical_value:,.0f})
                    </div>
                    <table>
                        <tr>
                            <th>CAN Number</th>
                            <th>PO Number</th>
                            <th>Product</th>
                            <th>Arrival Date</th>
                            <th>Days Pending</th>
                            <th>Pending Qty</th>
                            <th>Value (USD)</th>
                        </tr>
                """
                
                critical_sorted = critical_items.sort_values('days_since_arrival', ascending=False)
                
                for _, row in critical_sorted.iterrows():
                    html += f"""
                        <tr>
                            <td class="overdue">{row['arrival_note_number']}</td>
                            <td>{row.get('po_number', 'N/A')}</td>
                            <td>{row.get('product_name', 'N/A')}</td>
                            <td>{pd.to_datetime(row['arrival_date']).strftime('%b %d, %Y')}</td>
                            <td class="overdue">{row['days_since_arrival']} days</td>
                            <td>{row.get('pending_quantity', 0):,.0f}</td>
                            <td>${row.get('pending_value_usd', 0):,.0f}</td>
                        </tr>
                    """
                
                html += """
                    </table>
                """
            
            # Urgent items
            if not urgent_items.empty:
                urgent_value = urgent_items['pending_value_usd'].sum()
                
                html += f"""
                    <div class="section-header" style="background-color: #fff3e0; border-left-color: #f57c00; color: #f57c00;">
                        🟡 URGENT - Pending 8-14 Days ({len(urgent_items)} items, ${urgent_value:,.0f})
                    </div>
                    <table>
                        <tr>
                            <th>CAN Number</th>
                            <th>PO Number</th>
                            <th>Product</th>
                            <th>Arrival Date</th>
                            <th>Days Pending</th>
                            <th>Pending Qty</th>
                            <th>Value (USD)</th>
                        </tr>
                """
                
                urgent_sorted = urgent_items.sort_values('days_since_arrival', ascending=False)
                
                for _, row in urgent_sorted.iterrows():
                    html += f"""
                        <tr>
                            <td class="urgent">{row['arrival_note_number']}</td>
                            <td>{row.get('po_number', 'N/A')}</td>
                            <td>{row.get('product_name', 'N/A')}</td>
                            <td>{pd.to_datetime(row['arrival_date']).strftime('%b %d, %Y')}</td>
                            <td class="urgent">{row['days_since_arrival']} days</td>
                            <td>{row.get('pending_quantity', 0):,.0f}</td>
                            <td>${row.get('pending_value_usd', 0):,.0f}</td>
                        </tr>
                    """
                
                html += """
                    </table>
                """
            
            # Normal items
            if not normal_items.empty:
                normal_value = normal_items['pending_value_usd'].sum()
                
                html += f"""
                    <div class="section-header upcoming-header">
                        ⚪ NORMAL - Pending ≤7 Days ({len(normal_items)} items, ${normal_value:,.0f})
                    </div>
                    <table>
                        <tr>
                            <th>CAN Number</th>
                            <th>PO Number</th>
                            <th>Product</th>
                            <th>Arrival Date</th>
                            <th>Days Pending</th>
                            <th>Pending Qty</th>
                            <th>Value (USD)</th>
                        </tr>
                """
                
                normal_sorted = normal_items.sort_values('days_since_arrival', ascending=False)
                
                for _, row in normal_sorted.iterrows():
                    html += f"""
                        <tr>
                            <td>{row['arrival_note_number']}</td>
                            <td>{row.get('po_number', 'N/A')}</td>
                            <td>{row.get('product_name', 'N/A')}</td>
                            <td>{pd.to_datetime(row['arrival_date']).strftime('%b %d, %Y')}</td>
                            <td>{row['days_since_arrival']} days</td>
                            <td>{row.get('pending_quantity', 0):,.0f}</td>
                            <td>${row.get('pending_value_usd', 0):,.0f}</td>
                        </tr>
                    """
                
                html += """
                    </table>
                """
            
            # Action items
            html += """
                <div style="margin-top: 30px; padding: 15px; background-color: #e3f2fd; border-radius: 5px;">
                    <h4>📋 Required Actions:</h4>
                    <ol>
                        <li><strong>Critical Items (>14 days):</strong> Process immediately - highest priority</li>
                        <li><strong>Urgent Items (8-14 days):</strong> Schedule processing within 2 business days</li>
                        <li><strong>Normal Items (≤7 days):</strong> Process within standard timeline</li>
                        <li>Coordinate with warehouse team for QC inspection and stock-in</li>
                        <li>Update system immediately after stock-in completion</li>
                    </ol>
                </div>
                
                <div class="footer">
                    <p>This is an automated notification from Prostech Inbound Logistics</p>
                    <p>For questions: <a href="mailto:procurement@prostech.vn">procurement@prostech.vn</a></p>
                    <p>Phone: +84 33 476273</p>
                </div>
            </div>
        </body>
        </html>
            """
            
            return html
            
        except Exception as e:
            logger.error(f"Error creating pending stock-in HTML: {e}", exc_info=True)
            return f"<html><body><p>Error creating email content: {str(e)}</p></body></html>"
    
    # ========================
    # CUSTOMS CLEARANCE EMAIL
    # ========================
    
    @staticmethod
    def create_customs_clearance_html(po_df, can_df, weeks_ahead=4, date_type='etd'):
        """Create HTML content for customs clearance email"""
        try:
            date_type_upper = date_type.upper()
            
            # Count items
            po_count = len(po_df) if po_df is not None and not po_df.empty else 0
            can_count = len(can_df) if can_df is not None and not can_df.empty else 0
            
            # Start HTML
            html = f"""
            <html>
            <head>
                {EmailTemplates._get_base_styles()}
            </head>
            <body>
                <div class="container">
                    <div class="header" style="background: linear-gradient(135deg, #1976d2 0%, #1565c0 100%);">
                        <h1>🛃 Customs Clearance Schedule</h1>
                        <p style="margin: 5px 0 0 0;">International Shipments - Next {weeks_ahead} Week{'s' if weeks_ahead > 1 else ''}</p>
                    </div>
            """
            
            # Greeting
            html += f"""
                <p>Hello Customs Team,</p>
                <p>Here are the international shipments requiring customs clearance for the next {weeks_ahead} week{'s' if weeks_ahead > 1 else ''} (based on <strong>{date_type_upper}</strong>):</p>
            """
            
            # Summary
            total_po_value = po_df['outstanding_arrival_amount_usd'].sum() if po_df is not None and not po_df.empty else 0
            total_can_value = can_df['pending_value_usd'].sum() if can_df is not None and not can_df.empty else 0
            
            html += f"""
                <div class="summary-box">
                    <strong>📊 Summary:</strong><br>
                    Upcoming POs: {po_count} (${total_po_value:,.0f}) | 
                    Pending CANs: {can_count} (${total_can_value:,.0f})
                </div>
            """
            
            # International POs section
            if po_df is not None and not po_df.empty:
                po_df[date_type] = pd.to_datetime(po_df[date_type])
                
                # Group by country
                countries = po_df.groupby('vendor_country_name')
                
                html += f"""
                    <div class="section-header upcoming-header">
                        📦 UPCOMING INTERNATIONAL POs (by {date_type_upper})
                    </div>
                """
                
                for country, country_df in countries:
                    country_value = country_df['outstanding_arrival_amount_usd'].sum()
                    country_po_count = country_df['po_number'].nunique()
                    
                    html += f"""
                        <h3 style="color: #1976d2; margin: 20px 0 10px 0;">
                            🌍 {country} ({country_po_count} POs, ${country_value:,.0f})
                        </h3>
                        <table>
                            <tr>
                                <th>{date_type_upper}</th>
                                <th>PO Number</th>
                                <th>Vendor</th>
                                <th>Product</th>
                                <th>HS Code</th>
                                <th>Qty</th>
                                <th>Value (USD)</th>
                                <th>Trade Term</th>
                            </tr>
                    """
                    
                    country_sorted = country_df.sort_values(date_type)
                    
                    for _, row in country_sorted.iterrows():
                        html += f"""
                            <tr>
                                <td>{row[date_type].strftime('%b %d, %Y')}</td>
                                <td>{row['po_number']}</td>
                                <td>{row.get('vendor_name', 'N/A')}</td>
                                <td>{row.get('product_name', 'N/A')}</td>
                                <td>{row.get('hs_code', 'N/A')}</td>
                                <td>{row.get('pending_standard_arrival_quantity', 0):,.0f}</td>
                                <td>${row.get('outstanding_arrival_amount_usd', 0):,.0f}</td>
                                <td>{row.get('trade_term', 'N/A')}</td>
                            </tr>
                        """
                    
                    html += """
                        </table>
                    """
            
            # Pending CANs section
            if can_df is not None and not can_df.empty:
                html += """
                    <div class="section-header" style="background-color: #fff3e0; border-left-color: #f57c00; color: #f57c00;">
                        📦 PENDING CONTAINER ARRIVALS (Need Clearance)
                    </div>
                    <table>
                        <tr>
                            <th>CAN Number</th>
                            <th>Arrival Date</th>
                            <th>Days Pending</th>
                            <th>Country</th>
                            <th>Product</th>
                            <th>HS Code</th>
                            <th>Qty</th>
                            <th>Value (USD)</th>
                        </tr>
                """
                
                can_df['arrival_date'] = pd.to_datetime(can_df['arrival_date'])
                can_sorted = can_df.sort_values('days_since_arrival', ascending=False)
                
                for _, row in can_sorted.iterrows():
                    urgency_class = "overdue" if row['days_since_arrival'] > 7 else ""
                    
                    html += f"""
                        <tr>
                            <td class="{urgency_class}">{row['arrival_note_number']}</td>
                            <td>{row['arrival_date'].strftime('%b %d, %Y')}</td>
                            <td class="{urgency_class}">{row['days_since_arrival']} days</td>
                            <td>{row.get('vendor_country_name', 'N/A')}</td>
                            <td>{row.get('product_name', 'N/A')}</td>
                            <td>{row.get('hs_code', 'N/A')}</td>
                            <td>{row.get('pending_quantity', 0):,.0f}</td>
                            <td>${row.get('pending_value_usd', 0):,.0f}</td>
                        </tr>
                    """
                
                html += """
                    </table>
                """
            
            # Required documents checklist
            html += """
                <div style="margin-top: 30px; padding: 15px; background-color: #e3f2fd; border-radius: 5px;">
                    <h4>📋 Required Documents Checklist:</h4>
                    <ul>
                        <li><strong>Commercial Invoice:</strong> Original + copies</li>
                        <li><strong>Packing List:</strong> Detailed item breakdown</li>
                        <li><strong>Bill of Lading / Airway Bill:</strong> Original shipping documents</li>
                        <li><strong>Certificate of Origin:</strong> Form D/E as applicable</li>
                        <li><strong>Quality/Safety Certificates:</strong> Product-specific certifications</li>
                        <li><strong>Import License:</strong> If required for specific products</li>
                        <li><strong>Insurance Certificate:</strong> For CIF/CIP shipments</li>
                    </ul>
                </div>
                
                <div style="margin-top: 20px; padding: 15px; background-color: #fff3e0; border-radius: 5px;">
                    <h4>⚠️ Important Notes:</h4>
                    <ul>
                        <li>Ensure all documents are complete before arrival</li>
                        <li>Coordinate with shipping agent for container pickup</li>
                        <li>Schedule customs inspection in advance</li>
                        <li>Prepare VAT/duty payment as per trade terms</li>
                    </ul>
                </div>
                
                <div class="footer">
                    <p>This is an automated notification from Prostech Inbound Logistics</p>
                    <p>For questions: <a href="mailto:customs@prostech.vn">customs@prostech.vn</a></p>
                    <p>Phone: +84 33 476273</p>
                </div>
            </div>
        </body>
        </html>
            """
            
            return html
            
        except Exception as e:
            logger.error(f"Error creating customs clearance HTML: {e}", exc_info=True)
            return f"<html><body><p>Error creating email content: {str(e)}</p></body></html>"