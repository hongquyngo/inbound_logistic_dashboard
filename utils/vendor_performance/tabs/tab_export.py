"""
Export Tab

Handles report generation and export.
"""

import streamlit as st
import pandas as pd
from datetime import datetime
from typing import List

from ..exporters import ExcelExporter


def render(
    vendor_metrics: pd.DataFrame,
    po_data: pd.DataFrame,
    selected_vendor: str
) -> None:
    """
    Render Export Tab
    
    Args:
        vendor_metrics: DataFrame with vendor metrics
        po_data: DataFrame with PO data
        selected_vendor: Selected vendor name
    """
    st.subheader("📄 Export Vendor Report")
    st.markdown("Generate comprehensive vendor report for meetings and negotiations")
    
    if selected_vendor == "All Vendors":
        st.warning("Please select a specific vendor to generate a report")
        return
    
    # Report configuration
    col1, col2 = st.columns(2)
    
    with col1:
        report_format = st.selectbox(
            "Report Format",
            ["Excel (Multi-sheet)", "PDF Report", "PowerPoint Presentation"]
        )
        
        include_sections = st.multiselect(
            "Include Sections",
            [
                "Executive Summary",
                "Performance Metrics",
                "Purchase History",
                "Product Analysis",
                "Payment Analysis",
                "Recommendations"
            ],
            default=["Executive Summary", "Performance Metrics", "Purchase History", "Product Analysis"]
        )
    
    with col2:
        report_period = st.selectbox(
            "Report Period",
            ["Last 3 Months", "Last 6 Months", "Last 12 Months", "Year to Date"]
        )
        
        include_charts = st.checkbox("Include Charts & Visualizations", value=True)
        include_comparisons = st.checkbox("Include Period Comparisons", value=True)
    
    # Generate report button
    if st.button("🚀 Generate Report", type="primary"):
        with st.spinner("Generating vendor report..."):
            _generate_report(
                vendor_metrics,
                po_data,
                selected_vendor,
                report_format,
                include_sections
            )


def _generate_report(
    vendor_metrics: pd.DataFrame,
    po_data: pd.DataFrame,
    vendor_name: str,
    report_format: str,
    sections: List[str]
) -> None:
    """Generate and download report"""
    
    if vendor_metrics.empty:
        st.error("No vendor metrics data available")
        return
    
    vendor_data = vendor_metrics[vendor_metrics['vendor_name'] == vendor_name]
    
    if vendor_data.empty:
        st.error(f"No data found for vendor: {vendor_name}")
        return
    
    vendor_data = vendor_data.iloc[0]
    
    # Get purchase history
    if po_data.empty:
        st.error("No purchase order data found")
        return
    
    vendor_po = po_data[po_data['vendor_name'] == vendor_name]
    
    if vendor_po.empty:
        st.error(f"No purchase orders found for {vendor_name}")
        return
    
    # Prepare data
    history_cols = [
        'po_number', 'po_date', 'etd', 'eta', 'status',
        'total_amount_usd', 'currency', 'payment_term'
    ]
    
    # Add optional columns if they exist
    optional_cols = ['arrival_completion_percent', 'invoice_completion_percent']
    for col in optional_cols:
        if col in vendor_po.columns:
            history_cols.append(col)
    
    existing_cols = [col for col in history_cols if col in vendor_po.columns]
    purchase_history = vendor_po[existing_cols].copy()
    
    # Product analysis
    product_data = vendor_po.groupby(['product_name', 'brand']).agg({
        'standard_quantity': 'sum',
        'total_amount_usd': 'sum',
        'po_line_id': 'count'
    }).reset_index()
    
    if report_format == "Excel (Multi-sheet)":
        try:
            exporter = ExcelExporter()
            excel_file = exporter.export_vendor_report(
                vendor_data=vendor_data,
                vendor_metrics=vendor_metrics,
                purchase_history=purchase_history,
                product_analysis=product_data,
                sections=sections,
                filename=f"vendor_report_{vendor_name}_{datetime.now().strftime('%Y%m%d')}.xlsx"
            )
            
            st.download_button(
                label="📥 Download Excel Report",
                data=excel_file,
                file_name=f"vendor_report_{vendor_name}_{datetime.now().strftime('%Y%m%d')}.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
            
            st.success("✅ Report generated successfully!")
            
        except Exception as e:
            st.error(f"Error generating report: {str(e)}")
    
    elif report_format == "PDF Report":
        st.info("PDF report generation will be implemented in future version")
    
    else:  # PowerPoint
        st.info("PowerPoint presentation generation will be implemented in future version")