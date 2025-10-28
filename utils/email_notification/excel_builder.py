# utils/email_notification/excel_builder.py
"""
Excel attachment generation for email notifications
Creates formatted Excel files with PO schedules, alerts, and analytics
"""

import pandas as pd
import io
import logging
from datetime import datetime

logger = logging.getLogger(__name__)


class ExcelBuilder:
    """Generate Excel attachments for email notifications"""
    
    @staticmethod
    def create_po_schedule_excel(po_df, is_custom_recipient=False, date_type='etd'):
        """Create Excel attachment for PO schedule"""
        try:
            if po_df is None or po_df.empty:
                logger.warning("No data to create Excel")
                return None
            
            # Create Excel writer
            output = io.BytesIO()
            
            with pd.ExcelWriter(output, engine='openpyxl') as writer:
                # Select columns for export
                if is_custom_recipient:
                    # More detailed view for custom recipients
                    columns = [
                        'po_number', 'external_ref_number', 'po_date', date_type,
                        'vendor_name', 'vendor_code', 'vendor_type', 'vendor_location_type',
                        'product_name', 'pt_code', 'brand',
                        'buying_quantity', 'buying_uom', 'standard_quantity', 'standard_uom',
                        'pending_standard_arrival_quantity',
                        'purchase_unit_cost', 'currency', 'total_amount', 'total_amount_usd',
                        'outstanding_arrival_amount_usd',
                        'payment_term', 'trade_term',
                        'status', 'arrival_completion_percent',
                        'created_by'
                    ]
                else:
                    # Standard view for vendors
                    columns = [
                        'po_number', 'external_ref_number', 'po_date', date_type,
                        'product_name', 'pt_code', 'brand',
                        'buying_quantity', 'buying_uom', 'standard_quantity', 'standard_uom',
                        'pending_standard_arrival_quantity',
                        'purchase_unit_cost', 'currency', 'total_amount', 'total_amount_usd',
                        'outstanding_arrival_amount_usd',
                        'payment_term', 'trade_term',
                        'status', 'arrival_completion_percent'
                    ]
                
                # Filter columns that exist
                available_columns = [col for col in columns if col in po_df.columns]
                export_df = po_df[available_columns].copy()
                
                # Rename columns for better readability
                column_mapping = {
                    'po_number': 'PO Number',
                    'external_ref_number': 'External Ref',
                    'po_date': 'PO Date',
                    date_type: date_type.upper(),
                    'vendor_name': 'Vendor',
                    'vendor_code': 'Vendor Code',
                    'vendor_type': 'Vendor Type',
                    'vendor_location_type': 'Location Type',
                    'product_name': 'Product',
                    'pt_code': 'PT Code',
                    'brand': 'Brand',
                    'buying_quantity': 'Buying Qty',
                    'buying_uom': 'Buying UOM',
                    'standard_quantity': 'Standard Qty',
                    'standard_uom': 'Standard UOM',
                    'pending_standard_arrival_quantity': 'Pending Qty',
                    'purchase_unit_cost': 'Unit Cost',
                    'currency': 'Currency',
                    'total_amount': 'Total Amount',
                    'total_amount_usd': 'Total USD',
                    'outstanding_arrival_amount_usd': 'Outstanding USD',
                    'payment_term': 'Payment Term',
                    'trade_term': 'Trade Term',
                    'status': 'Status',
                    'arrival_completion_percent': 'Completion %',
                    'created_by': 'Created By'
                }
                
                export_df = export_df.rename(columns=column_mapping)
                
                # Sort by date and vendor
                date_col = date_type.upper()
                if date_col in export_df.columns:
                    sort_cols = [date_col]
                    if 'Vendor' in export_df.columns:
                        sort_cols.append('Vendor')
                    export_df = export_df.sort_values(sort_cols)
                
                # Write main sheet
                export_df.to_excel(writer, sheet_name='PO Schedule', index=False)
                
                # Create summary sheet
                if not export_df.empty and date_col in export_df.columns:
                    # Convert date column to datetime
                    export_df[date_col] = pd.to_datetime(export_df[date_col], errors='coerce')
                    
                    summary_data = []
                    
                    # Overall summary
                    summary_data.append({
                        'Metric': 'Total POs',
                        'Value': export_df['PO Number'].nunique() if 'PO Number' in export_df.columns else 0
                    })
                    
                    if 'Vendor' in export_df.columns:
                        summary_data.append({
                            'Metric': 'Total Vendors',
                            'Value': export_df['Vendor'].nunique()
                        })
                    
                    if 'Pending Qty' in export_df.columns:
                        summary_data.append({
                            'Metric': 'Total Pending Quantity',
                            'Value': f"{export_df['Pending Qty'].sum():,.0f}"
                        })
                    
                    if 'Outstanding USD' in export_df.columns:
                        summary_data.append({
                            'Metric': 'Total Outstanding Value (USD)',
                            'Value': f"${export_df['Outstanding USD'].sum():,.0f}"
                        })
                    
                    # Check for overdue items
                    today = pd.Timestamp.now().normalize()
                    overdue_df = export_df[export_df[date_col] < today]
                    if not overdue_df.empty:
                        summary_data.append({
                            'Metric': '⚠️ Overdue POs',
                            'Value': overdue_df['PO Number'].nunique() if 'PO Number' in overdue_df.columns else 0
                        })
                        if 'Outstanding USD' in overdue_df.columns:
                            summary_data.append({
                                'Metric': '⚠️ Overdue Value (USD)',
                                'Value': f"${overdue_df['Outstanding USD'].sum():,.0f}"
                            })
                    
                    summary_df = pd.DataFrame(summary_data)
                    summary_df.to_excel(writer, sheet_name='Summary', index=False)
                    
                    # Weekly breakdown
                    export_df['Week'] = export_df[date_col].dt.to_period('W').dt.start_time
                    weekly = export_df.groupby('Week').agg({
                        'PO Number': 'nunique',
                        'Pending Qty': 'sum',
                        'Outstanding USD': 'sum'
                    }).reset_index()
                    
                    weekly.columns = ['Week Start', 'PO Count', 'Total Pending Qty', 'Total Outstanding USD']
                    weekly['Week Start'] = pd.to_datetime(weekly['Week Start']).dt.date
                    
                    weekly.to_excel(writer, sheet_name='Weekly Breakdown', index=False)
            
            output.seek(0)
            return output
            
        except Exception as e:
            logger.error(f"Error creating PO schedule Excel: {e}", exc_info=True)
            return None
    
    @staticmethod
    def create_critical_alerts_excel(data_dict, date_type='etd'):
        """Create Excel attachment for critical alerts"""
        try:
            overdue_pos = data_dict.get('overdue_pos', pd.DataFrame())
            pending_stockin = data_dict.get('pending_stockin', pd.DataFrame())
            
            if (overdue_pos.empty or overdue_pos is None) and (pending_stockin.empty or pending_stockin is None):
                logger.warning("No critical data to create Excel")
                return None
            
            output = io.BytesIO()
            
            with pd.ExcelWriter(output, engine='openpyxl') as writer:
                # Overdue POs sheet
                if overdue_pos is not None and not overdue_pos.empty:
                    overdue_columns = [
                        'po_number', 'external_ref_number', 'po_date', date_type,
                        'vendor_name', 'vendor_code',
                        'product_name', 'pt_code', 'brand',
                        'pending_standard_arrival_quantity',
                        'outstanding_arrival_amount_usd',
                        'payment_term', 'trade_term',
                        'status'
                    ]
                    
                    available_cols = [col for col in overdue_columns if col in overdue_pos.columns]
                    overdue_export = overdue_pos[available_cols].copy()
                    
                    # Calculate days overdue
                    if date_type in overdue_export.columns:
                        overdue_export[date_type] = pd.to_datetime(overdue_export[date_type])
                        today = pd.Timestamp.now().normalize()
                        overdue_export['Days Overdue'] = (today - overdue_export[date_type]).dt.days
                        overdue_export = overdue_export.sort_values('Days Overdue', ascending=False)
                    
                    # Rename columns
                    column_mapping = {
                        'po_number': 'PO Number',
                        'external_ref_number': 'External Ref',
                        'po_date': 'PO Date',
                        date_type: f'{date_type.upper()} (Overdue)',
                        'vendor_name': 'Vendor',
                        'vendor_code': 'Vendor Code',
                        'product_name': 'Product',
                        'pt_code': 'PT Code',
                        'brand': 'Brand',
                        'pending_standard_arrival_quantity': 'Pending Qty',
                        'outstanding_arrival_amount_usd': 'Outstanding USD',
                        'payment_term': 'Payment Term',
                        'trade_term': 'Trade Term',
                        'status': 'Status'
                    }
                    
                    overdue_export = overdue_export.rename(columns=column_mapping)
                    overdue_export.to_excel(writer, sheet_name='Overdue POs', index=False)
                
                # Pending stock-in sheet
                if pending_stockin is not None and not pending_stockin.empty:
                    stockin_columns = [
                        'arrival_note_number', 'po_number', 'arrival_date',
                        'vendor_name', 'product_name', 'pt_code',
                        'arrived_quantity', 'pending_quantity',
                        'pending_value_usd', 'days_since_arrival'
                    ]
                    
                    available_cols = [col for col in stockin_columns if col in pending_stockin.columns]
                    stockin_export = pending_stockin[available_cols].copy()
                    
                    # Sort by days pending
                    if 'days_since_arrival' in stockin_export.columns:
                        stockin_export = stockin_export.sort_values('days_since_arrival', ascending=False)
                    
                    # Add urgency flag
                    if 'days_since_arrival' in stockin_export.columns:
                        stockin_export['Urgency'] = stockin_export['days_since_arrival'].apply(
                            lambda x: '🔴 Critical' if x > 14 else '🟡 Urgent' if x > 7 else '⚪ Normal'
                        )
                    
                    # Rename columns
                    column_mapping = {
                        'arrival_note_number': 'CAN Number',
                        'po_number': 'PO Number',
                        'arrival_date': 'Arrival Date',
                        'vendor_name': 'Vendor',
                        'product_name': 'Product',
                        'pt_code': 'PT Code',
                        'arrived_quantity': 'Arrived Qty',
                        'pending_quantity': 'Pending Qty',
                        'pending_value_usd': 'Pending Value USD',
                        'days_since_arrival': 'Days Pending'
                    }
                    
                    stockin_export = stockin_export.rename(columns=column_mapping)
                    stockin_export.to_excel(writer, sheet_name='Pending Stock-in', index=False)
                
                # Summary sheet
                summary_data = []
                
                if overdue_pos is not None and not overdue_pos.empty:
                    summary_data.append({
                        'Category': 'Overdue POs',
                        'Count': len(overdue_pos),
                        'Total Value (USD)': f"${overdue_pos['outstanding_arrival_amount_usd'].sum():,.0f}" if 'outstanding_arrival_amount_usd' in overdue_pos.columns else 'N/A'
                    })
                
                if pending_stockin is not None and not pending_stockin.empty:
                    urgent_count = len(pending_stockin[pending_stockin['days_since_arrival'] > 7]) if 'days_since_arrival' in pending_stockin.columns else 0
                    summary_data.append({
                        'Category': 'Pending Stock-in',
                        'Count': len(pending_stockin),
                        'Total Value (USD)': f"${pending_stockin['pending_value_usd'].sum():,.0f}" if 'pending_value_usd' in pending_stockin.columns else 'N/A'
                    })
                    summary_data.append({
                        'Category': 'Urgent (>7 days)',
                        'Count': urgent_count,
                        'Total Value (USD)': 'See Pending Stock-in tab'
                    })
                
                if summary_data:
                    summary_df = pd.DataFrame(summary_data)
                    summary_df.to_excel(writer, sheet_name='Summary', index=False)
            
            output.seek(0)
            return output
            
        except Exception as e:
            logger.error(f"Error creating critical alerts Excel: {e}", exc_info=True)
            return None
    
    @staticmethod
    def create_pending_stockin_excel(can_df):
        """Create Excel attachment for pending stock-in items"""
        try:
            if can_df is None or can_df.empty:
                logger.warning("No data to create Excel")
                return None
            
            output = io.BytesIO()
            
            with pd.ExcelWriter(output, engine='openpyxl') as writer:
                # Main data sheet
                stockin_columns = [
                    'arrival_note_number', 'po_number', 'arrival_date',
                    'vendor_name', 'vendor_code',
                    'product_name', 'pt_code', 'brand',
                    'arrived_quantity', 'stocked_in_quantity', 'pending_quantity',
                    'unit_cost_usd', 'pending_value_usd',
                    'days_since_arrival', 'warehouse_location'
                ]
                
                available_cols = [col for col in stockin_columns if col in can_df.columns]
                export_df = can_df[available_cols].copy()
                
                # Add urgency classification
                if 'days_since_arrival' in export_df.columns:
                    export_df['Urgency'] = export_df['days_since_arrival'].apply(
                        lambda x: '🔴 Critical' if x > 14 else '🟡 Urgent' if x > 7 else '⚪ Normal'
                    )
                    export_df = export_df.sort_values('days_since_arrival', ascending=False)
                
                # Rename columns
                column_mapping = {
                    'arrival_note_number': 'CAN Number',
                    'po_number': 'PO Number',
                    'arrival_date': 'Arrival Date',
                    'vendor_name': 'Vendor',
                    'vendor_code': 'Vendor Code',
                    'product_name': 'Product',
                    'pt_code': 'PT Code',
                    'brand': 'Brand',
                    'arrived_quantity': 'Arrived Qty',
                    'stocked_in_quantity': 'Stocked In',
                    'pending_quantity': 'Pending Qty',
                    'unit_cost_usd': 'Unit Cost USD',
                    'pending_value_usd': 'Pending Value USD',
                    'days_since_arrival': 'Days Pending',
                    'warehouse_location': 'Location'
                }
                
                export_df = export_df.rename(columns=column_mapping)
                export_df.to_excel(writer, sheet_name='Pending Stock-in', index=False)
                
                # Summary by urgency
                if 'Days Pending' in export_df.columns and 'Urgency' in export_df.columns:
                    urgency_summary = export_df.groupby('Urgency').agg({
                        'CAN Number': 'count',
                        'Pending Qty': 'sum',
                        'Pending Value USD': 'sum',
                        'Days Pending': 'mean'
                    }).reset_index()
                    
                    urgency_summary.columns = ['Urgency', 'Item Count', 'Total Pending Qty', 'Total Value USD', 'Avg Days Pending']
                    urgency_summary.to_excel(writer, sheet_name='Summary by Urgency', index=False)
                
                # Summary by vendor
                if 'Vendor' in export_df.columns:
                    vendor_summary = export_df.groupby('Vendor').agg({
                        'CAN Number': 'count',
                        'Pending Qty': 'sum',
                        'Pending Value USD': 'sum'
                    }).reset_index()
                    
                    vendor_summary.columns = ['Vendor', 'Item Count', 'Total Pending Qty', 'Total Value USD']
                    vendor_summary = vendor_summary.sort_values('Total Value USD', ascending=False)
                    vendor_summary.to_excel(writer, sheet_name='Summary by Vendor', index=False)
            
            output.seek(0)
            return output
            
        except Exception as e:
            logger.error(f"Error creating pending stock-in Excel: {e}", exc_info=True)
            return None
    
    @staticmethod
    def create_customs_clearance_excel(po_df, can_df=None, date_type='etd'):
        """Create Excel attachment for customs clearance"""
        try:
            if (po_df is None or po_df.empty) and (can_df is None or can_df.empty):
                logger.warning("No data to create Excel")
                return None
            
            output = io.BytesIO()
            
            with pd.ExcelWriter(output, engine='openpyxl') as writer:
                # International POs sheet
                if po_df is not None and not po_df.empty:
                    po_columns = [
                        'po_number', 'external_ref_number', 'po_date', date_type,
                        'vendor_name', 'vendor_code', 'vendor_country_name',
                        'product_name', 'pt_code', 'hs_code', 'brand',
                        'pending_standard_arrival_quantity', 'standard_uom',
                        'outstanding_arrival_amount_usd',
                        'trade_term', 'payment_term',
                        'status'
                    ]
                    
                    available_cols = [col for col in po_columns if col in po_df.columns]
                    po_export = po_df[available_cols].copy()
                    
                    # Sort by country and date
                    sort_cols = []
                    if 'vendor_country_name' in po_export.columns:
                        sort_cols.append('vendor_country_name')
                    if date_type in po_export.columns:
                        sort_cols.append(date_type)
                    if sort_cols:
                        po_export = po_export.sort_values(sort_cols)
                    
                    # Rename columns
                    column_mapping = {
                        'po_number': 'PO Number',
                        'external_ref_number': 'External Ref',
                        'po_date': 'PO Date',
                        date_type: date_type.upper(),
                        'vendor_name': 'Vendor',
                        'vendor_code': 'Vendor Code',
                        'vendor_country_name': 'Origin Country',
                        'product_name': 'Product',
                        'pt_code': 'PT Code',
                        'hs_code': 'HS Code',
                        'brand': 'Brand',
                        'pending_standard_arrival_quantity': 'Pending Qty',
                        'standard_uom': 'UOM',
                        'outstanding_arrival_amount_usd': 'Value USD',
                        'trade_term': 'Trade Term',
                        'payment_term': 'Payment Term',
                        'status': 'Status'
                    }
                    
                    po_export = po_export.rename(columns=column_mapping)
                    po_export.to_excel(writer, sheet_name='International POs', index=False)
                    
                    # Summary by country
                    if 'Origin Country' in po_export.columns:
                        country_summary = po_export.groupby('Origin Country').agg({
                            'PO Number': 'count',
                            'Pending Qty': 'sum',
                            'Value USD': 'sum'
                        }).reset_index()
                        
                        country_summary.columns = ['Country', 'PO Count', 'Total Pending Qty', 'Total Value USD']
                        country_summary = country_summary.sort_values('Total Value USD', ascending=False)
                        country_summary.to_excel(writer, sheet_name='Summary by Country', index=False)
                
                # Pending CANs sheet
                if can_df is not None and not can_df.empty:
                    can_columns = [
                        'arrival_note_number', 'po_number', 'arrival_date',
                        'vendor_name', 'vendor_country_name',
                        'product_name', 'pt_code', 'hs_code',
                        'pending_quantity', 'pending_value_usd',
                        'days_since_arrival'
                    ]
                    
                    available_cols = [col for col in can_columns if col in can_df.columns]
                    can_export = can_df[available_cols].copy()
                    
                    # Sort by days pending
                    if 'days_since_arrival' in can_export.columns:
                        can_export = can_export.sort_values('days_since_arrival', ascending=False)
                    
                    # Rename columns
                    column_mapping = {
                        'arrival_note_number': 'CAN Number',
                        'po_number': 'PO Number',
                        'arrival_date': 'Arrival Date',
                        'vendor_name': 'Vendor',
                        'vendor_country_name': 'Origin Country',
                        'product_name': 'Product',
                        'pt_code': 'PT Code',
                        'hs_code': 'HS Code',
                        'pending_quantity': 'Pending Qty',
                        'pending_value_usd': 'Pending Value USD',
                        'days_since_arrival': 'Days Pending'
                    }
                    
                    can_export = can_export.rename(columns=column_mapping)
                    can_export.to_excel(writer, sheet_name='Pending CANs', index=False)
            
            output.seek(0)
            return output
            
        except Exception as e:
            logger.error(f"Error creating customs clearance Excel: {e}", exc_info=True)
            return None