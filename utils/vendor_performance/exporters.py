"""
Export Functionality for Vendor Performance Reports

Handles Excel, PDF, and other export formats.
"""

import pandas as pd
import io
import logging
from datetime import datetime
from typing import Dict, List, Any, Optional

logger = logging.getLogger(__name__)


class ExcelExporter:
    """Excel report exporter for vendor performance data"""
    
    @staticmethod
    def export_vendor_report(
        vendor_data: pd.Series,
        vendor_metrics: pd.DataFrame,
        purchase_history: pd.DataFrame,
        product_analysis: pd.DataFrame,
        sections: List[str],
        filename: Optional[str] = None
    ) -> io.BytesIO:
        """
        Export comprehensive vendor report to Excel
        
        Args:
            vendor_data: Single vendor's summary data
            vendor_metrics: All vendor metrics for comparison
            purchase_history: Purchase order history
            product_analysis: Product mix analysis
            sections: List of sections to include
            filename: Output filename (optional)
            
        Returns:
            BytesIO buffer with Excel file
        """
        try:
            output = io.BytesIO()
            
            with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
                workbook = writer.book
                
                # Define formats
                formats = ExcelExporter._create_formats(workbook)
                
                # Create sheets based on selected sections
                if "Executive Summary" in sections:
                    ExcelExporter._create_summary_sheet(
                        writer, vendor_data, formats
                    )
                
                if "Performance Metrics" in sections:
                    ExcelExporter._create_metrics_sheet(
                        writer, vendor_metrics, formats
                    )
                
                if "Purchase History" in sections:
                    ExcelExporter._create_history_sheet(
                        writer, purchase_history, formats
                    )
                
                if "Product Analysis" in sections:
                    ExcelExporter._create_product_sheet(
                        writer, product_analysis, formats
                    )
            
            output.seek(0)
            logger.info(f"Exported vendor report with {len(sections)} sections")
            return output
            
        except Exception as e:
            logger.error(f"Error exporting vendor report: {e}")
            raise
    
    @staticmethod
    def _create_formats(workbook) -> Dict[str, Any]:
        """
        Create Excel cell formats
        
        Args:
            workbook: xlsxwriter workbook object
            
        Returns:
            Dictionary of format objects
        """
        return {
            'header': workbook.add_format({
                'bold': True,
                'bg_color': '#4472C4',
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
        vendor_data: pd.Series,
        formats: Dict[str, Any]
    ) -> None:
        """
        Create executive summary sheet
        
        Args:
            writer: Excel writer object
            vendor_data: Vendor summary data
            formats: Cell formats
        """
        summary_df = pd.DataFrame({
            'Metric': [
                'Vendor Name',
                'Vendor Type',
                'Location Type',
                'Total Purchase Value',
                'Number of POs',
                'On-Time Delivery Rate',
                'Completion Rate',
                'Average Lead Time',
                'Outstanding Amount'
            ],
            'Value': [
                vendor_data.get('vendor_name', 'N/A'),
                vendor_data.get('vendor_type', 'N/A'),
                vendor_data.get('vendor_location_type', 'N/A'),
                f"${vendor_data.get('total_po_value', 0):,.2f}",
                f"{vendor_data.get('total_pos', 0):,}",
                f"{vendor_data.get('on_time_rate', 0):.1f}%",
                f"{vendor_data.get('completion_rate', 0):.1f}%",
                f"{vendor_data.get('avg_lead_time_days', 0):.1f} days",
                f"${vendor_data.get('outstanding_invoices', 0):,.2f}"
            ]
        })
        
        summary_df.to_excel(writer, sheet_name='Summary', index=False)
        
        # Format the sheet
        worksheet = writer.sheets['Summary']
        worksheet.set_column('A:A', 30)
        worksheet.set_column('B:B', 30)
        
        # Apply header format
        for col_num, value in enumerate(summary_df.columns.values):
            worksheet.write(0, col_num, value, formats['header'])
    
    @staticmethod
    def _create_metrics_sheet(
        writer: pd.ExcelWriter,
        vendor_metrics: pd.DataFrame,
        formats: Dict[str, Any]
    ) -> None:
        """
        Create performance metrics sheet
        
        Args:
            writer: Excel writer object
            vendor_metrics: All vendor metrics
            formats: Cell formats
        """
        if vendor_metrics.empty:
            return
        
        # Select key columns
        metrics_cols = [
            'vendor_name', 'vendor_type', 'vendor_location_type',
            'total_pos', 'completed_pos', 'on_time_rate',
            'completion_rate', 'avg_over_delivery_percent',
            'total_po_value', 'outstanding_invoices'
        ]
        
        # Filter existing columns
        existing_cols = [col for col in metrics_cols if col in vendor_metrics.columns]
        metrics_df = vendor_metrics[existing_cols].copy()
        
        metrics_df.to_excel(writer, sheet_name='Performance Metrics', index=False)
        
        # Format the sheet
        worksheet = writer.sheets['Performance Metrics']
        worksheet.set_column('A:Z', 15)
        
        # Apply header format
        for col_num, value in enumerate(metrics_df.columns.values):
            worksheet.write(0, col_num, value, formats['header'])
    
    @staticmethod
    def _create_history_sheet(
        writer: pd.ExcelWriter,
        purchase_history: pd.DataFrame,
        formats: Dict[str, Any]
    ) -> None:
        """
        Create purchase history sheet
        
        Args:
            writer: Excel writer object
            purchase_history: PO history data
            formats: Cell formats
        """
        if purchase_history.empty:
            return
        
        purchase_history.to_excel(writer, sheet_name='Purchase History', index=False)
        
        # Format the sheet
        worksheet = writer.sheets['Purchase History']
        worksheet.set_column('A:Z', 15)
        
        # Apply header format
        for col_num, value in enumerate(purchase_history.columns.values):
            worksheet.write(0, col_num, value, formats['header'])
    
    @staticmethod
    def _create_product_sheet(
        writer: pd.ExcelWriter,
        product_analysis: pd.DataFrame,
        formats: Dict[str, Any]
    ) -> None:
        """
        Create product analysis sheet
        
        Args:
            writer: Excel writer object
            product_analysis: Product mix data
            formats: Cell formats
        """
        if product_analysis.empty:
            return
        
        product_analysis.to_excel(writer, sheet_name='Product Analysis', index=False)
        
        # Format the sheet
        worksheet = writer.sheets['Product Analysis']
        worksheet.set_column('A:Z', 15)
        
        # Apply header format
        for col_num, value in enumerate(product_analysis.columns.values):
            worksheet.write(0, col_num, value, formats['header'])
    
    @staticmethod
    def prepare_export_data(
        vendor_metrics: pd.DataFrame,
        po_data: pd.DataFrame,
        selected_vendor: str
    ) -> Dict[str, pd.DataFrame]:
        """
        Prepare data for export
        
        Args:
            vendor_metrics: Vendor metrics dataframe
            po_data: PO data dataframe
            selected_vendor: Selected vendor name
            
        Returns:
            Dictionary with prepared dataframes
        """
        export_data = {}
        
        # Vendor summary
        if not vendor_metrics.empty and selected_vendor != "All Vendors":
            vendor_data = vendor_metrics[
                vendor_metrics['vendor_name'] == selected_vendor
            ]
            if not vendor_data.empty:
                export_data['vendor_summary'] = vendor_data.iloc[0]
        
        # Purchase history
        if not po_data.empty and selected_vendor != "All Vendors":
            vendor_po = po_data[po_data['vendor_name'] == selected_vendor]
            
            history_cols = [
                'po_number', 'po_date', 'etd', 'eta', 'status',
                'total_amount_usd', 'currency', 'payment_term'
            ]
            existing_cols = [col for col in history_cols if col in vendor_po.columns]
            export_data['purchase_history'] = vendor_po[existing_cols]
        
        # Product analysis
        if not po_data.empty and selected_vendor != "All Vendors":
            vendor_po = po_data[po_data['vendor_name'] == selected_vendor]
            
            product_data = vendor_po.groupby(['product_name', 'brand']).agg({
                'standard_quantity': 'sum',
                'total_amount_usd': 'sum',
                'po_line_id': 'count'
            }).reset_index()
            
            export_data['product_analysis'] = product_data
        
        return export_data