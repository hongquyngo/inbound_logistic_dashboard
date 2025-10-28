# utils/email_notification/calendar_builder.py
"""
Calendar integration for email notifications
Generates ICS files and calendar links (Google Calendar, Outlook) for PO schedules and events
"""

from datetime import datetime, timedelta
import uuid
import pandas as pd
import urllib.parse
import logging

logger = logging.getLogger(__name__)


class CalendarBuilder:
    """Generate calendar files and links for inbound logistics events"""
    
    # ========================
    # ICS FILE GENERATION
    # ========================
    
    @staticmethod
    def create_po_schedule_ics(po_df, organizer_email, date_type='etd'):
        """Create ICS content for PO arrival schedule based on ETD or ETA"""
        try:
            # ICS header
            ics_content = """BEGIN:VCALENDAR
VERSION:2.0
PRODID:-//Inbound Logistics//PO Schedule//EN
CALSCALE:GREGORIAN
METHOD:REQUEST
"""
            
            # Check if DataFrame is valid
            if po_df is None or po_df.empty:
                ics_content += "END:VCALENDAR"
                return ics_content
            
            # Ensure date column exists
            if date_type not in po_df.columns:
                logger.warning(f"Date column '{date_type}' not found in DataFrame")
                ics_content += "END:VCALENDAR"
                return ics_content
            
            # Group POs by date
            po_df[date_type] = pd.to_datetime(po_df[date_type])
            grouped = po_df.groupby(po_df[date_type].dt.date)
            
            date_type_upper = date_type.upper()
            
            # Create events for each date
            for date_value, date_df in grouped:
                # Generate unique ID
                uid = str(uuid.uuid4())
                
                # Current timestamp
                now = datetime.utcnow().strftime('%Y%m%dT%H%M%SZ')
                
                # Set event time: 9:00 AM - 5:00 PM local time
                # Convert to UTC (assuming Vietnam timezone GMT+7)
                start_datetime = datetime.combine(date_value, datetime.min.time()).replace(hour=9, minute=0) - timedelta(hours=7)
                end_datetime = start_datetime + timedelta(hours=8)
                
                # Format for ICS
                dtstart = start_datetime.strftime('%Y%m%dT%H%M%SZ')
                dtend = end_datetime.strftime('%Y%m%dT%H%M%SZ')
                
                # Create summary and description
                po_count = date_df['po_number'].nunique()
                vendor_count = date_df['vendor_name'].nunique()
                total_value = date_df['outstanding_arrival_amount_usd'].sum()
                
                # Check for overdue items
                is_overdue = date_value < datetime.now().date()
                status_indicator = " ⚠️ OVERDUE" if is_overdue else ""
                
                summary = f"📦 PO Arrivals ({po_count}){status_indicator} - {date_value.strftime('%b %d')} ({date_type_upper})"
                
                description = f"Purchase Order Arrivals for {date_value.strftime('%B %d, %Y')} based on {date_type_upper}\\n\\n"
                description += f"Total POs: {po_count}\\n"
                description += f"Vendors: {vendor_count}\\n"
                description += f"Total Value: ${total_value:,.0f}\\n"
                
                if is_overdue:
                    days_overdue = (datetime.now().date() - date_value).days
                    description += f"\\n⚠️ OVERDUE by {days_overdue} days!\\n"
                
                description += "\\nPURCHASE ORDERS:\\n"
                
                # Group by vendor for description
                for vendor, vendor_df in date_df.groupby('vendor_name'):
                    vendor_value = vendor_df['outstanding_arrival_amount_usd'].sum()
                    description += f"\\n• {vendor} (${vendor_value:,.0f})\\n"
                    
                    # List POs and products
                    for _, po in vendor_df.iterrows():
                        description += f"  - PO #{po['po_number']}: {po['pt_code']} {po['product_name']}\\n"
                        description += f"    Qty: {po['pending_standard_arrival_quantity']:,.0f} | ${po['outstanding_arrival_amount_usd']:,.0f}\\n"
                
                # Add checklist
                description += "\\n📋 CHECKLIST:\\n"
                description += f"- Confirm arrival with vendor ({date_type_upper} based)\\n"
                description += "- Prepare warehouse space\\n"
                description += "- Arrange QC inspection\\n"
                description += "- Prepare import documents\\n"
                
                # Get vendor list for location
                vendors = date_df['vendor_name'].unique()
                location_str = "; ".join(vendors[:3])
                if len(vendors) > 3:
                    location_str += f" and {len(vendors)-3} more"
                
                # Set alarm - earlier for overdue items
                alarm_minutes = 60 if is_overdue else 30
                
                # Add event to ICS
                ics_content += f"""BEGIN:VEVENT
UID:{uid}@inbound.prostech.vn
DTSTAMP:{now}
ORGANIZER;CN=Inbound Logistics:mailto:{organizer_email}
DTSTART:{dtstart}
DTEND:{dtend}
SUMMARY:{summary}
DESCRIPTION:{description}
LOCATION:Vendors: {location_str}
STATUS:CONFIRMED
SEQUENCE:0
TRANSP:OPAQUE
BEGIN:VALARM
TRIGGER:-PT{alarm_minutes}M
ACTION:DISPLAY
DESCRIPTION:PO arrival reminder - Check with vendors{' URGENTLY!' if is_overdue else ''}
END:VALARM
END:VEVENT
"""
            
            # ICS footer
            ics_content += "END:VCALENDAR"
            
            return ics_content
            
        except Exception as e:
            logger.error(f"Error creating PO schedule ICS: {e}")
            # Return minimal valid ICS
            return """BEGIN:VCALENDAR
VERSION:2.0
PRODID:-//Inbound Logistics//PO Schedule//EN
END:VCALENDAR"""
    
    @staticmethod
    def create_stockin_reminder_ics(can_df, organizer_email):
        """Create ICS content for pending stock-in reminders"""
        try:
            # ICS header
            ics_content = """BEGIN:VCALENDAR
VERSION:2.0
PRODID:-//Inbound Logistics//Stock-in Reminder//EN
CALSCALE:GREGORIAN
METHOD:REQUEST
"""
            
            if can_df is None or can_df.empty:
                ics_content += "END:VCALENDAR"
                return ics_content
            
            # Create a single event for today with all pending items
            uid = str(uuid.uuid4())
            now = datetime.utcnow()
            
            # Set event for today at 8:30 AM - 10:30 AM local time
            today = datetime.now().date()
            start_datetime = datetime.combine(today, datetime.min.time()).replace(hour=8, minute=30) - timedelta(hours=7)
            end_datetime = start_datetime + timedelta(hours=2)
            
            dtstart = start_datetime.strftime('%Y%m%dT%H%M%SZ')
            dtend = end_datetime.strftime('%Y%m%dT%H%M%SZ')
            dtstamp = now.strftime('%Y%m%dT%H%M%SZ')
            
            # Count urgent items
            urgent_count = len(can_df[can_df['days_since_arrival'] > 7])
            critical_count = len(can_df[can_df['days_since_arrival'] > 14])
            total_value = can_df['pending_value_usd'].sum()
            
            summary = f"📦 Pending Stock-in: {len(can_df)} items (🔴 {urgent_count} urgent)"
            
            description = f"PENDING STOCK-IN ITEMS\\n\\n"
            description += f"Total Items: {len(can_df)}\\n"
            description += f"Urgent (>7 days): {urgent_count}\\n"
            description += f"Critical (>14 days): {critical_count}\\n"
            description += f"Total Value: ${total_value:,.0f}\\n\\n"
            
            description += "ITEMS BY URGENCY:\\n\\n"
            
            # Sort by days pending
            can_sorted = can_df.sort_values('days_since_arrival', ascending=False)
            
            for _, can in can_sorted.head(10).iterrows():
                urgency = "🔴 CRITICAL" if can['days_since_arrival'] > 14 else "🟡 URGENT" if can['days_since_arrival'] > 7 else "⚪ Normal"
                description += f"{urgency}\\n"
                description += f"CAN #{can['arrival_note_number']} - PO #{can['po_number']}\\n"
                description += f"Product: {can.get('product_name', 'N/A')}\\n"
                description += f"Days Pending: {can['days_since_arrival']}\\n"
                description += f"Qty: {can['pending_quantity']:,.0f}\\n\\n"
            
            if len(can_df) > 10:
                description += f"... and {len(can_df) - 10} more items\\n\\n"
            
            description += "⚠️ ACTION REQUIRED: Process pending stock-in items immediately\\n"
            
            # Add event to ICS
            ics_content += f"""BEGIN:VEVENT
UID:{uid}@inbound.prostech.vn
DTSTAMP:{dtstamp}
ORGANIZER;CN=Inbound Logistics:mailto:{organizer_email}
DTSTART:{dtstart}
DTEND:{dtend}
SUMMARY:{summary}
DESCRIPTION:{description}
LOCATION:Warehouse
STATUS:CONFIRMED
SEQUENCE:0
TRANSP:OPAQUE
PRIORITY:1
BEGIN:VALARM
TRIGGER:-PT15M
ACTION:DISPLAY
DESCRIPTION:Pending stock-in items - Process immediately!
END:VALARM
END:VEVENT
"""
            
            # ICS footer
            ics_content += "END:VCALENDAR"
            
            return ics_content
            
        except Exception as e:
            logger.error(f"Error creating stock-in reminder ICS: {e}")
            return """BEGIN:VCALENDAR
VERSION:2.0
PRODID:-//Inbound Logistics//Stock-in Reminder//EN
END:VCALENDAR"""
    
    @staticmethod
    def create_customs_ics(po_df, can_df, organizer_email, date_type='etd'):
        """Create ICS content for customs clearance events"""
        try:
            # ICS header
            ics_content = """BEGIN:VCALENDAR
VERSION:2.0
PRODID:-//Inbound Logistics//Customs Clearance//EN
CALSCALE:GREGORIAN
METHOD:REQUEST
"""
            
            date_type_upper = date_type.upper()
            
            # Process PO events
            if po_df is not None and not po_df.empty:
                po_df[date_type] = pd.to_datetime(po_df[date_type])
                
                # Group by date and country
                if 'vendor_country_name' in po_df.columns:
                    grouped = po_df.groupby([po_df[date_type].dt.date, 'vendor_country_name'])
                    
                    for (date_value, country), group_df in grouped:
                        uid = str(uuid.uuid4())
                        now = datetime.utcnow().strftime('%Y%m%dT%H%M%SZ')
                        
                        # Set event time: 8:00 AM - 12:00 PM
                        start_datetime = datetime.combine(date_value, datetime.min.time()).replace(hour=8, minute=0) - timedelta(hours=7)
                        end_datetime = start_datetime + timedelta(hours=4)
                        
                        dtstart = start_datetime.strftime('%Y%m%dT%H%M%SZ')
                        dtend = end_datetime.strftime('%Y%m%dT%H%M%SZ')
                        
                        po_count = group_df['po_number'].nunique()
                        total_value = group_df['outstanding_arrival_amount_usd'].sum()
                        
                        summary = f"🛃 Customs: {po_count} POs from {country} ({date_type_upper})"
                        
                        description = f"CUSTOMS CLEARANCE - {country}\\n\\n"
                        description += f"{date_type_upper}: {date_value.strftime('%B %d, %Y')}\\n"
                        description += f"Total POs: {po_count}\\n"
                        description += f"Total Value: ${total_value:,.0f}\\n\\n"
                        description += "REQUIRED DOCUMENTS:\\n"
                        description += "- Commercial Invoice\\n"
                        description += "- Packing List\\n"
                        description += "- Certificate of Origin\\n"
                        description += "- Bill of Lading\\n"
                        description += "- Quality Certificates\\n\\n"
                        description += "PURCHASE ORDERS:\\n"
                        
                        for _, po in group_df.iterrows():
                            description += f"- PO #{po['po_number']}: {po.get('product_name', 'N/A')}\\n"
                        
                        ics_content += f"""BEGIN:VEVENT
UID:{uid}@inbound.prostech.vn
DTSTAMP:{now}
ORGANIZER;CN=Customs Team:mailto:{organizer_email}
DTSTART:{dtstart}
DTEND:{dtend}
SUMMARY:{summary}
DESCRIPTION:{description}
LOCATION:Customs Office - {country}
STATUS:CONFIRMED
SEQUENCE:0
TRANSP:OPAQUE
BEGIN:VALARM
TRIGGER:-PT1440M
ACTION:DISPLAY
DESCRIPTION:Customs clearance tomorrow - Prepare documents
END:VALARM
END:VEVENT
"""
            
            # Process CAN events
            if can_df is not None and not can_df.empty:
                can_df['arrival_date'] = pd.to_datetime(can_df['arrival_date'])
                
                if 'vendor_country_name' in can_df.columns:
                    grouped = can_df.groupby([can_df['arrival_date'].dt.date, 'vendor_country_name'])
                    
                    for (arrival_date, country), group_df in grouped:
                        uid = str(uuid.uuid4())
                        now = datetime.utcnow().strftime('%Y%m%dT%H%M%SZ')
                        
                        # Set event time: 2:00 PM - 4:00 PM
                        start_datetime = datetime.combine(arrival_date, datetime.min.time()).replace(hour=14, minute=0) - timedelta(hours=7)
                        end_datetime = start_datetime + timedelta(hours=2)
                        
                        dtstart = start_datetime.strftime('%Y%m%dT%H%M%SZ')
                        dtend = end_datetime.strftime('%Y%m%dT%H%M%SZ')
                        
                        can_count = group_df['arrival_note_number'].nunique()
                        total_value = group_df['pending_value_usd'].sum()
                        
                        summary = f"🛃 Customs: {can_count} CANs from {country}"
                        
                        description = f"CONTAINER ARRIVAL CLEARANCE - {country}\\n\\n"
                        description += f"Arrival Date: {arrival_date.strftime('%B %d, %Y')}\\n"
                        description += f"Total CANs: {can_count}\\n"
                        description += f"Total Value: ${total_value:,.0f}\\n\\n"
                        description += "REQUIRED DOCUMENTS:\\n"
                        description += "- Container Arrival Note\\n"
                        description += "- Customs Declaration\\n"
                        description += "- Quality Certificate\\n"
                        
                        ics_content += f"""BEGIN:VEVENT
UID:{uid}@inbound.prostech.vn
DTSTAMP:{now}
ORGANIZER;CN=Customs Team:mailto:{organizer_email}
DTSTART:{dtstart}
DTEND:{dtend}
SUMMARY:{summary}
DESCRIPTION:{description}
LOCATION:Customs Office - {country}
STATUS:CONFIRMED
SEQUENCE:0
TRANSP:OPAQUE
BEGIN:VALARM
TRIGGER:-PT120M
ACTION:DISPLAY
DESCRIPTION:Container arrival clearance - Prepare documents
END:VALARM
END:VEVENT
"""
            
            # ICS footer
            ics_content += "END:VCALENDAR"
            
            return ics_content
            
        except Exception as e:
            logger.error(f"Error creating customs ICS: {e}")
            return """BEGIN:VCALENDAR
VERSION:2.0
PRODID:-//Inbound Logistics//Customs Clearance//EN
END:VCALENDAR"""
    
    # ========================
    # GOOGLE CALENDAR LINKS
    # ========================
    
    @staticmethod
    def create_google_calendar_links(po_df, date_type='etd'):
        """Create Google Calendar add links for each PO date"""
        links = []
        
        try:
            if po_df is None or po_df.empty:
                return links
            
            # Ensure date column is datetime
            po_df[date_type] = pd.to_datetime(po_df[date_type], errors='coerce')
            po_df = po_df.dropna(subset=[date_type])
            
            # Group by date
            grouped = po_df.groupby(po_df[date_type].dt.date)
            
            date_type_upper = date_type.upper()
            
            for date_value, date_df in grouped:
                # Create event details
                start_dt = datetime.combine(date_value, datetime.min.time()).replace(hour=9, minute=0)
                end_dt = start_dt.replace(hour=17, minute=0)
                
                # Format for Google Calendar
                start_str = start_dt.strftime('%Y%m%dT%H%M%S')
                end_str = end_dt.strftime('%Y%m%dT%H%M%S')
                
                po_count = date_df['po_number'].nunique()
                vendor_count = date_df['vendor_name'].nunique()
                total_value = date_df['outstanding_arrival_amount_usd'].sum()
                
                is_overdue = date_value < datetime.now().date()
                status_indicator = " ⚠️ OVERDUE" if is_overdue else ""
                
                title = f"📦 PO Arrivals ({po_count}){status_indicator} - {date_value.strftime('%b %d')} ({date_type_upper})"
                
                details = f"Purchase Order Arrivals for {date_value.strftime('%B %d, %Y')} based on {date_type_upper}\n\n"
                details += f"Total POs: {po_count}\n"
                details += f"Vendors: {vendor_count}\n"
                details += f"Total Value: ${total_value:,.0f}\n\n"
                
                if is_overdue:
                    days_overdue = (datetime.now().date() - date_value).days
                    details += f"⚠️ OVERDUE by {days_overdue} days!\n\n"
                
                details += f"PURCHASE ORDERS ({date_type_upper} based):\n"
                
                for _, po in date_df.head(5).iterrows():
                    details += f"\n• {po['vendor_name']}\n"
                    details += f"  PO #{po['po_number']}: {po.get('pt_code', 'N/A')} {po.get('product_name', 'N/A')}\n"
                    details += f"  Qty: {po.get('pending_standard_arrival_quantity', 0):,.0f}\n"
                
                if len(date_df) > 5:
                    details += f"\n... and {len(date_df) - 5} more POs\n"
                
                # Get vendor list for location
                vendors = date_df['vendor_name'].unique()
                location_str = "; ".join(vendors[:3])
                if len(vendors) > 3:
                    location_str += f" +{len(vendors)-3} more"
                
                # URL encode the parameters
                params = {
                    'action': 'TEMPLATE',
                    'text': title,
                    'dates': f"{start_str}/{end_str}",
                    'details': details,
                    'location': f"Vendors: {location_str}"
                }
                
                base_url = 'https://calendar.google.com/calendar/render'
                link = f"{base_url}?{urllib.parse.urlencode(params)}"
                
                links.append({
                    'date': date_value,
                    'link': link,
                    'count': po_count,
                    'is_urgent': is_overdue
                })
            
            return links
            
        except Exception as e:
            logger.error(f"Error creating Google Calendar links: {e}", exc_info=True)
            return []
    
    @staticmethod
    def create_customs_google_calendar_links(po_df, can_df=None, date_type='etd'):
        """Create Google Calendar links for customs clearance events"""
        links = []
        
        try:
            date_type_upper = date_type.upper()
            
            # Process POs
            if po_df is not None and not po_df.empty:
                po_df[date_type] = pd.to_datetime(po_df[date_type], errors='coerce')
                po_df = po_df.dropna(subset=[date_type])
                
                if 'vendor_country_name' in po_df.columns:
                    grouped = po_df.groupby([po_df[date_type].dt.date, 'vendor_country_name'])
                    
                    for (date_value, country), group_df in grouped:
                        start_dt = datetime.combine(date_value, datetime.min.time()).replace(hour=8, minute=0)
                        end_dt = start_dt.replace(hour=12, minute=0)
                        
                        start_str = start_dt.strftime('%Y%m%dT%H%M%S')
                        end_str = end_dt.strftime('%Y%m%dT%H%M%S')
                        
                        po_count = group_df['po_number'].nunique()
                        total_value = group_df['outstanding_arrival_amount_usd'].sum()
                        
                        title = f"🛃 Customs: {po_count} POs from {country} ({date_type_upper})"
                        
                        details = f"CUSTOMS CLEARANCE - {country}\n\n"
                        details += f"{date_type_upper}: {date_value.strftime('%B %d, %Y')}\n"
                        details += f"Total POs: {po_count}\n"
                        details += f"Total Value: ${total_value:,.0f}\n\n"
                        details += "REQUIRED DOCUMENTS:\n"
                        details += "- Commercial Invoice\n"
                        details += "- Packing List\n"
                        details += "- Certificate of Origin\n"
                        details += "- Bill of Lading\n"
                        
                        params = {
                            'action': 'TEMPLATE',
                            'text': title,
                            'dates': f"{start_str}/{end_str}",
                            'details': details,
                            'location': f"Customs Office - {country}"
                        }
                        
                        base_url = 'https://calendar.google.com/calendar/render'
                        link = f"{base_url}?{urllib.parse.urlencode(params)}"
                        
                        links.append({
                            'date': date_value,
                            'country': country,
                            'link': link,
                            'count': po_count,
                            'type': 'PO'
                        })
            
            # Process CANs
            if can_df is not None and not can_df.empty:
                can_df['arrival_date'] = pd.to_datetime(can_df['arrival_date'], errors='coerce')
                can_df = can_df.dropna(subset=['arrival_date'])
                
                if 'vendor_country_name' in can_df.columns:
                    grouped = can_df.groupby([can_df['arrival_date'].dt.date, 'vendor_country_name'])
                    
                    for (arrival_date, country), group_df in grouped:
                        start_dt = datetime.combine(arrival_date, datetime.min.time()).replace(hour=14, minute=0)
                        end_dt = start_dt.replace(hour=16, minute=0)
                        
                        start_str = start_dt.strftime('%Y%m%dT%H%M%S')
                        end_str = end_dt.strftime('%Y%m%dT%H%M%S')
                        
                        can_count = group_df['arrival_note_number'].nunique()
                        total_value = group_df['pending_value_usd'].sum()
                        
                        title = f"🛃 Customs: {can_count} CANs from {country}"
                        
                        details = f"CONTAINER ARRIVAL CLEARANCE - {country}\n\n"
                        details += f"Arrival Date: {arrival_date.strftime('%B %d, %Y')}\n"
                        details += f"Total CANs: {can_count}\n"
                        details += f"Total Value: ${total_value:,.0f}\n\n"
                        details += "REQUIRED DOCUMENTS:\n"
                        details += "- Container Arrival Note\n"
                        details += "- Customs Declaration\n"
                        details += "- Quality Certificate\n"
                        
                        params = {
                            'action': 'TEMPLATE',
                            'text': title,
                            'dates': f"{start_str}/{end_str}",
                            'details': details,
                            'location': f"Customs Office - {country}"
                        }
                        
                        base_url = 'https://calendar.google.com/calendar/render'
                        link = f"{base_url}?{urllib.parse.urlencode(params)}"
                        
                        links.append({
                            'date': arrival_date,
                            'country': country,
                            'link': link,
                            'count': can_count,
                            'type': 'CAN'
                        })
            
            return sorted(links, key=lambda x: x['date'])
            
        except Exception as e:
            logger.error(f"Error creating customs Google Calendar links: {e}", exc_info=True)
            return []
    
    # ========================
    # OUTLOOK CALENDAR LINKS
    # ========================
    
    @staticmethod
    def create_outlook_calendar_links(po_df, date_type='etd'):
        """Create Outlook Calendar add links for each PO date"""
        links = []
        
        try:
            if po_df is None or po_df.empty:
                return links
            
            po_df[date_type] = pd.to_datetime(po_df[date_type], errors='coerce')
            po_df = po_df.dropna(subset=[date_type])
            
            grouped = po_df.groupby(po_df[date_type].dt.date)
            
            date_type_upper = date_type.upper()
            
            for date_value, date_df in grouped:
                start_dt = datetime.combine(date_value, datetime.min.time()).replace(hour=9, minute=0)
                end_dt = start_dt.replace(hour=17, minute=0)
                
                startdt = start_dt.strftime('%Y-%m-%dT%H:%M:%S')
                enddt = end_dt.strftime('%Y-%m-%dT%H:%M:%S')
                
                po_count = date_df['po_number'].nunique()
                vendor_count = date_df['vendor_name'].nunique()
                total_value = date_df['outstanding_arrival_amount_usd'].sum()
                
                is_overdue = date_value < datetime.now().date()
                status_indicator = " ⚠️ OVERDUE" if is_overdue else ""
                
                subject = f"📦 PO Arrivals ({po_count}){status_indicator} - {date_value.strftime('%b %d')} ({date_type_upper})"
                
                body = f"Purchase Order Arrivals for {date_value.strftime('%B %d, %Y')} based on {date_type_upper}<br><br>"
                body += f"Total POs: {po_count}<br>"
                body += f"Vendors: {vendor_count}<br>"
                body += f"Total Value: ${total_value:,.0f}<br>"
                
                if is_overdue:
                    days_overdue = (datetime.now().date() - date_value).days
                    body += f"<br><strong style='color:red'>⚠️ OVERDUE by {days_overdue} days!</strong><br>"
                
                body += f"<br>PURCHASE ORDERS ({date_type_upper} based):<br>"
                
                for _, po in date_df.head(5).iterrows():
                    body += f"<br>• {po['vendor_name']}<br>"
                    body += f"  PO #{po['po_number']}: {po.get('pt_code', 'N/A')} {po.get('product_name', 'N/A')}<br>"
                    body += f"  Qty: {po.get('pending_standard_arrival_quantity', 0):,.0f}<br>"
                
                if len(date_df) > 5:
                    body += f"<br>... and {len(date_df) - 5} more POs<br>"
                
                vendors = date_df['vendor_name'].unique()
                location_str = "; ".join(vendors[:3])
                if len(vendors) > 3:
                    location_str += f" +{len(vendors)-3} more"
                
                params = {
                    'subject': subject,
                    'startdt': startdt,
                    'enddt': enddt,
                    'body': body,
                    'location': f"Vendors: {location_str}"
                }
                
                base_url = 'https://outlook.live.com/calendar/0/deeplink/compose'
                link = f"{base_url}?{urllib.parse.urlencode(params)}"
                
                links.append({
                    'date': date_value,
                    'link': link,
                    'count': po_count,
                    'is_urgent': is_overdue
                })
            
            return links
            
        except Exception as e:
            logger.error(f"Error creating Outlook Calendar links: {e}", exc_info=True)
            return []
    
    @staticmethod
    def create_customs_outlook_calendar_links(po_df, can_df=None, date_type='etd'):
        """Create Outlook Calendar links for customs clearance events"""
        links = []
        
        try:
            date_type_upper = date_type.upper()
            
            # Process POs
            if po_df is not None and not po_df.empty:
                po_df[date_type] = pd.to_datetime(po_df[date_type], errors='coerce')
                po_df = po_df.dropna(subset=[date_type])
                
                if 'vendor_country_name' in po_df.columns:
                    grouped = po_df.groupby([po_df[date_type].dt.date, 'vendor_country_name'])
                    
                    for (date_value, country), group_df in grouped:
                        start_dt = datetime.combine(date_value, datetime.min.time()).replace(hour=8, minute=0)
                        end_dt = start_dt.replace(hour=12, minute=0)
                        
                        startdt = start_dt.strftime('%Y-%m-%dT%H:%M:%S')
                        enddt = end_dt.strftime('%Y-%m-%dT%H:%M:%S')
                        
                        po_count = group_df['po_number'].nunique()
                        total_value = group_df['outstanding_arrival_amount_usd'].sum()
                        
                        subject = f"🛃 Customs: {po_count} POs from {country} ({date_type_upper})"
                        
                        body = f"<h3>CUSTOMS CLEARANCE - {country}</h3>"
                        body += f"<p><strong>{date_type_upper}:</strong> {date_value.strftime('%B %d, %Y')}</p>"
                        body += f"<p><strong>Total POs:</strong> {po_count}<br>"
                        body += f"<strong>Total Value:</strong> ${total_value:,.0f}</p>"
                        body += "<h4>REQUIRED DOCUMENTS:</h4>"
                        body += "<ul>"
                        body += "<li>Commercial Invoice</li>"
                        body += "<li>Packing List</li>"
                        body += "<li>Certificate of Origin</li>"
                        body += "<li>Bill of Lading</li>"
                        body += "</ul>"
                        
                        params = {
                            'subject': subject,
                            'startdt': startdt,
                            'enddt': enddt,
                            'body': body,
                            'location': f"Customs Office - {country}"
                        }
                        
                        base_url = 'https://outlook.live.com/calendar/0/deeplink/compose'
                        link = f"{base_url}?{urllib.parse.urlencode(params)}"
                        
                        links.append({
                            'date': date_value,
                            'country': country,
                            'link': link,
                            'count': po_count,
                            'type': 'PO'
                        })
            
            # Process CANs
            if can_df is not None and not can_df.empty:
                can_df['arrival_date'] = pd.to_datetime(can_df['arrival_date'], errors='coerce')
                can_df = can_df.dropna(subset=['arrival_date'])
                
                if 'vendor_country_name' in can_df.columns:
                    grouped = can_df.groupby([can_df['arrival_date'].dt.date, 'vendor_country_name'])
                    
                    for (arrival_date, country), group_df in grouped:
                        start_dt = datetime.combine(arrival_date, datetime.min.time()).replace(hour=14, minute=0)
                        end_dt = start_dt.replace(hour=16, minute=0)
                        
                        startdt = start_dt.strftime('%Y-%m-%dT%H:%M:%S')
                        enddt = end_dt.strftime('%Y-%m-%dT%H:%M:%S')
                        
                        can_count = group_df['arrival_note_number'].nunique()
                        total_value = group_df['pending_value_usd'].sum()
                        
                        subject = f"🛃 Customs: {can_count} CANs from {country}"
                        
                        body = f"<h3>CONTAINER ARRIVAL CLEARANCE - {country}</h3>"
                        body += f"<p><strong>Arrival Date:</strong> {arrival_date.strftime('%B %d, %Y')}</p>"
                        body += f"<p><strong>Total CANs:</strong> {can_count}<br>"
                        body += f"<strong>Total Value:</strong> ${total_value:,.0f}</p>"
                        body += "<h4>REQUIRED DOCUMENTS:</h4>"
                        body += "<ul>"
                        body += "<li>Container Arrival Note</li>"
                        body += "<li>Customs Declaration</li>"
                        body += "<li>Quality Certificate</li>"
                        body += "</ul>"
                        
                        params = {
                            'subject': subject,
                            'startdt': startdt,
                            'enddt': enddt,
                            'body': body,
                            'location': f"Customs Office - {country}"
                        }
                        
                        base_url = 'https://outlook.live.com/calendar/0/deeplink/compose'
                        link = f"{base_url}?{urllib.parse.urlencode(params)}"
                        
                        links.append({
                            'date': arrival_date,
                            'country': country,
                            'link': link,
                            'count': can_count,
                            'type': 'CAN'
                        })
            
            return sorted(links, key=lambda x: x['date'])
            
        except Exception as e:
            logger.error(f"Error creating customs Outlook Calendar links: {e}", exc_info=True)
            return []