"""
Export Functionality for Vendor Performance Reports - Refactored

Simplified export focused on key metrics:
- Executive summary
- Financial metrics
- Product analysis
"""

import pandas as pd
import io
import logging
from datetime import datetime
from typing import List, Optional

from .exceptions import ExportError
from .constants import format_currency, format_percentage

logger = logging.getLogger(__name__)


class ExcelExporter:
    """Simplified Excel report exporter"""
    
    @staticmethod
    def export_vendor_report(
        vendor_summary: pd.Series,
        po_data: pd.DataFrame,
        product_data: pd.DataFrame,
        sections: List[str],
        filename: Optional[str] = None
    ) -> io.BytesIO:
        """
        Export comprehensive vendor report to Excel
        
        Args:
            vendor_summary: Vendor summary data
            po_data: Purchase order data
            product_data: Product analysis data
            sections: Sections to include
            filename: Output filename
            
        Returns:
            BytesIO buffer with Excel file
            
        Raises:
            ExportError: If export fails
        """
        try:
            output = io.BytesIO()
            
            with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                workbook = writer.book
                formats = ExcelExporter._create_formats(workbook)
                
                # Create sheets based on selected sections
                if "Executive Summary" in sections:
                    ExcelExporter._create_summary_sheet(
                        writer, vendor_summary, formats
                    )
                
                if "Financial Metrics" in sections:
                    ExcelExporter._create_financial_sheet(
                        writer, po_data, formats
                    )
                
                if "Purchase History" in sections:
                    ExcelExporter._create_history_sheet(
                        writer, po_data, formats
                    )
                
                if "Product Analysis" in sections:
                    ExcelExporter._create_product_sheet(
                        writer, product_data, formats
                    )
            
            output.seek(0)
            logger.info(f"Exported report with {len(sections)} sections")
            return output
            
        except Exception as e:
            logger.error(f"Error exporting report: {e}", exc_info=True)
            raise ExportError("Failed to export vendor report", {'error': str(e)})
    
    @staticmethod
    def _create_formats(workbook) -> dict:
        """Create Excel cell formats"""
        return {
            'header': workbook.add_format({
                'bold': True,
                'bg_color': '#3498db',
                'font_color': 'white',
                'align': 'center',
                'valign': 'vcenter',
                'border': 1
            }),
            'title': workbook.add_format({
                'bold': True,
                'font_size': 14,
                'align': 'left'
            }),
            'subtitle': workbook.add_format({
                'bold': True,
                'font_size': 12,
                'bg_color': '#ecf0f1'
            }),
            'currency': workbook.add_format({
                'num_format': '$#,##0.00'
            }),
            'percent': workbook.add_format({
                'num_format': '0.0%'
            }),
            'date': workbook.add_format({
                'num_format': 'yyyy-mm-dd'
            }),
            'number': workbook.add_format({
                'num_format': '#,##0'
            }),
            'good': workbook.add_format({
                'bg_color': '#C6EFCE',
                'font_color': '#006100'
            }),
            'warning': workbook.add_format({
                'bg_color': '#FFEB9C',
                'font_color': '#9C6500'
            }),
            'bad': workbook.add_format({
                'bg_color': '#FFC7CE',
                'font_color': '#9C0006'
            })
        }
    
    @staticmethod
    def _create_summary_sheet(
        writer: pd.ExcelWriter,
        vendor_summary: pd.Series,
        formats: dict
    ) -> None:
        """
        Create executive summary sheet
        
        Args:
            writer: Excel writer
            vendor_summary: Vendor summary data
            formats: Cell formats
        """
        # Prepare summary data
        summary_data = {
            'Metric': [
                'Vendor Name',
                'Vendor Code',
                'Vendor Type',
                'Location Type',
                '',
                'Financial Performance',
                'Total Order Entry Value',
                'Total Invoiced Value',
                'Pending Delivery',
                'Conversion Rate',
                '',
                'Order Statistics',
                'Total Purchase Orders',
                'Average PO Value',
                'First Order Date',
                'Last Order Date'
            ],
            'Value': [
                vendor_summary.get('vendor_name', 'N/A'),
                vendor_summary.get('vendor_code', 'N/A'),
                vendor_summary.get('vendor_type', 'N/A'),
                vendor_summary.get('vendor_location_type', 'N/A'),
                '',
                '',
                format_currency(vendor_summary.get('total_order_value', 0)),
                format_currency(vendor_summary.get('total_invoiced_value', 0)),
                format_currency(vendor_summary.get('pending_delivery_value', 0)),
                format_percentage(vendor_summary.get('conversion_rate', 0)),
                '',
                '',
                f"{vendor_summary.get('total_pos', 0):,.0f}",
                format_currency(vendor_summary.get('avg_po_value', 0)),
                str(vendor_summary.get('first_po_date', 'N/A'))[:10],
                str(vendor_summary.get('last_po_date', 'N/A'))[:10]
            ]
        }
        
        summary_df = pd.DataFrame(summary_data)
        summary_df.to_excel(writer, sheet_name='Executive Summary', index=False)
        
        # Format the sheet
        worksheet = writer.sheets['Executive Summary']
        worksheet.set_column('A:A', 30)
        worksheet.set_column('B:B', 40)
        
        # Apply header format
        for col_num, value in enumerate(summary_df.columns.values):
            worksheet.write(0, col_num, value, formats['header'])
        
        # Apply section headers (rows with empty values)
        for row_num in [5, 11]:
            worksheet.write(row_num + 1, 0, summary_df.iloc[row_num, 0], formats['subtitle'])
    
    @staticmethod
    def _create_financial_sheet(
        writer: pd.ExcelWriter,
        po_data: pd.DataFrame,
        formats: dict
    ) -> None:
        """
        Create financial metrics sheet
        
        Args:
            writer: Excel writer
            po_data: PO data
            formats: Cell formats
        """
        if po_data.empty:
            return
        
        # Aggregate by month
        po_data['month'] = pd.to_datetime(po_data['po_date']).dt.to_period('M').dt.start_time
        
        financial_summary = po_data.groupby('month').agg({
            'po_number': 'nunique',
            'total_order_value_usd': 'sum',
            'invoiced_amount_usd': 'sum',
            'pending_delivery_usd': 'sum'
        }).reset_index()
        
        # Calculate conversion rate
        financial_summary['conversion_rate'] = (
            financial_summary['invoiced_amount_usd'] / 
            financial_summary['total_order_value_usd'] * 100
        ).round(1)
        
        # Rename columns
        financial_summary.columns = [
            'Month', 'PO Count', 'Order Entry Value', 
            'Invoiced Value', 'Pending Delivery', 'Conversion %'
        ]
        
        # Export
        financial_summary.to_excel(writer, sheet_name='Financial Metrics', index=False)
        
        # Format
        worksheet = writer.sheets['Financial Metrics']
        worksheet.set_column('A:A', 12)
        worksheet.set_column('B:F', 18)
        
        # Apply header format
        for col_num, value in enumerate(financial_summary.columns.values):
            worksheet.write(0, col_num, value, formats['header'])
    
    @staticmethod
    def _create_history_sheet(
        writer: pd.ExcelWriter,
        po_data: pd.DataFrame,
        formats: dict
    ) -> None:
        """
        Create purchase history sheet
        
        Args:
            writer: Excel writer
            po_data: PO data
            formats: Cell formats
        """
        if po_data.empty:
            return
        
        # Select relevant columns
        history_cols = [
            'po_number', 'po_date', 'product_name', 'brand',
            'standard_quantity', 'total_order_value_usd',
            'invoiced_amount_usd', 'pending_delivery_usd',
            'status', 'payment_term'
        ]
        
        existing_cols = [col for col in history_cols if col in po_data.columns]
        history_df = po_data[existing_cols].copy()
        
        # Rename for clarity
        rename_map = {
            'po_number': 'PO Number',
            'po_date': 'PO Date',
            'product_name': 'Product',
            'brand': 'Brand',
            'standard_quantity': 'Quantity',
            'total_order_value_usd': 'Order Value',
            'invoiced_amount_usd': 'Invoiced',
            'pending_delivery_usd': 'Pending',
            'status': 'Status',
            'payment_term': 'Payment Terms'
        }
        history_df.rename(columns=rename_map, inplace=True)
        
        # Sort by date
        if 'PO Date' in history_df.columns:
            history_df = history_df.sort_values('PO Date', ascending=False)
        
        # Export
        history_df.to_excel(writer, sheet_name='Purchase History', index=False)
        
        # Format
        worksheet = writer.sheets['Purchase History']
        worksheet.set_column('A:J', 15)
        
        # Apply header format
        for col_num, value in enumerate(history_df.columns.values):
            worksheet.write(0, col_num, value, formats['header'])
    
    @staticmethod
    def _create_product_sheet(
        writer: pd.ExcelWriter,
        product_data: pd.DataFrame,
        formats: dict
    ) -> None:
        """
        Create product analysis sheet
        
        Args:
            writer: Excel writer
            product_data: Product data
            formats: Cell formats
        """
        if product_data.empty:
            return
        
        # Select and rename columns
        product_df = product_data.copy()
        
        # Export
        product_df.to_excel(writer, sheet_name='Product Analysis', index=False)
        
        # Format
        worksheet = writer.sheets['Product Analysis']
        worksheet.set_column('A:Z', 15)
        
        # Apply header format
        for col_num, value in enumerate(product_df.columns.values):
            worksheet.write(0, col_num, value, formats['header'])


class CSVExporter:
    """CSV data exporter"""
    
    @staticmethod
    def export_vendor_data(
        vendor_summary: pd.DataFrame,
        po_data: pd.DataFrame
    ) -> io.BytesIO:
        """
        Export vendor data as CSV
        
        Args:
            vendor_summary: Vendor summary
            po_data: PO data
            
        Returns:
            CSV data as BytesIO
        """
        try:
            output = io.BytesIO()
            
            # Combine data if needed
            if not po_data.empty:
                csv_data = po_data.to_csv(index=False)
            elif not vendor_summary.empty:
                csv_data = vendor_summary.to_csv(index=False)
            else:
                csv_data = "No data available"
            
            output.write(csv_data.encode('utf-8'))
            output.seek(0)
            
            return output
            
        except Exception as e:
            logger.error(f"Error exporting CSV: {e}")
            raise ExportError("Failed to export CSV", {'error': str(e)})