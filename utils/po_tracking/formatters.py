"""
Formatters Module - Updated with Overdue Date Highlighting
Handles display formatting for PO tracking dashboard
"""

import streamlit as st
import pandas as pd
from datetime import date
from typing import List
from utils.po_tracking.column_config import (
    render_column_selector,
    get_column_display_name,
    COLUMN_DEFINITIONS
)
from utils.po_tracking.date_editor import (
    render_edit_button,
    render_date_editor_modal,
    is_date_overdue,
    parse_date
)


def render_metrics(po_df: pd.DataFrame) -> None:
    """
    Render key metrics cards
    
    Args:
        po_df: Purchase order dataframe
    """
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        total_pos = po_df['po_number'].nunique()
        st.metric("Total POs", f"{total_pos:,}")
    
    with col2:
        total_lines = len(po_df)
        st.metric("Total PO Lines", f"{total_lines:,}")
    
    with col3:
        total_value_usd = po_df['total_amount_usd'].sum()
        st.metric("Total Value", f"${total_value_usd:,.0f}")
    
    with col4:
        outstanding_usd = po_df['outstanding_arrival_amount_usd'].sum()
        st.metric("Outstanding Arrival", f"${outstanding_usd:,.0f}")


def render_detail_list(po_df: pd.DataFrame, data_service=None) -> None:
    """
    Render detailed PO list with column selection, edit functionality, and overdue highlighting
    
    Args:
        po_df: Purchase order dataframe
        data_service: PODataService instance for date updates
    """
    st.markdown("### 📋 Detailed PO List")
    
    if po_df.empty:
        st.info("No data to display")
        return
    
    # Render column selector (with expander)
    selected_columns = render_column_selector()
    
    if not selected_columns:
        st.warning("⚠️ No columns selected. Please select columns to display.")
        return
    
    # Show total record count and overdue count
    overdue_count = count_overdue_rows(po_df)
    col1, col2 = st.columns([3, 1])
    with col1:
        st.caption(f"Showing {len(po_df):,} records")
    with col2:
        if overdue_count > 0:
            st.caption(f"⚠️ {overdue_count} overdue ETD/ETA")
    
    # Add Actions column for edit buttons
    display_df = prepare_display_dataframe(po_df, selected_columns)
    
    # Render table with edit buttons and highlighting
    render_table_with_actions(display_df, po_df, selected_columns, data_service)
    
    # Render date editor modal if active
    if data_service:
        render_date_editor_modal(data_service)
    
    # Legend for highlighting
    st.markdown("---")
    st.caption("""
    **Legend:** 
    ⚠️ Warning emoji on date cells = Overdue ETD or ETA (past today)
    """)
    
    # Export buttons
    col1, col2, col3 = st.columns([1, 1, 4])
    
    with col1:
        csv = po_df[selected_columns].to_csv(index=False).encode('utf-8')
        st.download_button(
            label="📥 Download CSV",
            data=csv,
            file_name=f"po_tracking_{pd.Timestamp.now().strftime('%Y%m%d_%H%M%S')}.csv",
            mime="text/csv",
            use_container_width=True
        )
    
    with col2:
        from io import BytesIO
        
        # Create Excel file in memory
        excel_buffer = BytesIO()
        with pd.ExcelWriter(excel_buffer, engine='xlsxwriter') as writer:
            po_df[selected_columns].to_excel(writer, index=False, sheet_name='PO Data')
        
        st.download_button(
            label="📥 Download Excel",
            data=excel_buffer.getvalue(),
            file_name=f"po_tracking_{pd.Timestamp.now().strftime('%Y%m%d_%H%M%S')}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True
        )


def prepare_display_dataframe(po_df: pd.DataFrame, selected_columns: List[str]) -> pd.DataFrame:
    """
    Prepare dataframe for display with selected columns and proper formatting
    
    Args:
        po_df: Full PO dataframe
        selected_columns: List of columns to display
        
    Returns:
        Formatted dataframe for display
    """
    # Filter to selected columns that exist in dataframe
    existing_columns = [col for col in selected_columns if col in po_df.columns]
    display_df = po_df[existing_columns].copy()
    
    # Rename columns to display names
    column_mapping = {
        col: get_column_display_name(col) 
        for col in existing_columns
    }
    display_df = display_df.rename(columns=column_mapping)
    
    # Format numeric columns using vectorized operations
    for col in display_df.columns:
        if 'USD' in col or 'Amount' in col or 'Cost' in col:
            display_df[col] = display_df[col].fillna(0).map('${:,.2f}'.format)
        elif 'Quantity' in col or 'Qty' in col:
            display_df[col] = display_df[col].fillna(0).map('{:,.0f}'.format)
        elif '%' in col or 'Percent' in col:
            display_df[col] = display_df[col].fillna(0).map('{:.1f}%'.format)
    
    return display_df


def render_table_with_actions(
    display_df: pd.DataFrame, 
    original_df: pd.DataFrame,
    selected_columns: List[str],
    data_service
) -> None:
    """
    Render dataframe with action buttons and overdue highlighting
    
    Args:
        display_df: Formatted dataframe for display
        original_df: Original dataframe with all data
        selected_columns: List of selected columns
        data_service: PODataService instance
    """
    # Initialize pagination state
    if 'page_number' not in st.session_state:
        st.session_state.page_number = 1
    
    rows_per_page = 50
    total_rows = len(display_df)
    total_pages = (total_rows + rows_per_page - 1) // rows_per_page
    
    # Calculate indices for current page
    start_idx = (st.session_state.page_number - 1) * rows_per_page
    end_idx = min(start_idx + rows_per_page, total_rows)
    
    display_df_page = display_df.iloc[start_idx:end_idx]
    original_df_page = original_df.iloc[start_idx:end_idx]
    
    # Create table with container
    with st.container():
        # Header row with sticky effect
        header_cols = st.columns([1] + [3] * len(display_df_page.columns))
        
        with header_cols[0]:
            st.markdown("**Actions**")
        
        for idx, col_name in enumerate(display_df_page.columns):
            with header_cols[idx + 1]:
                st.markdown(f"**{col_name}**")
        
        st.markdown("---")
        
        # Data rows with overdue highlighting
        for idx, (display_idx, row) in enumerate(display_df_page.iterrows()):
            original_row = original_df_page.iloc[idx]
            
            # Normal row container (no special background for overdue)
            st.markdown(
                '<div style="background-color: #ffffff; padding: 10px; border-radius: 5px; border-left: 4px solid #e0e0e0;">',
                unsafe_allow_html=True
            )
            
            row_cols = st.columns([1] + [3] * len(row))
            
            # Action column with edit button
            with row_cols[0]:
                po_line_id = original_row['po_line_id']
                render_edit_button(
                    po_line_id=po_line_id,
                    row_data=original_row.to_dict()
                )
            
            # Data columns with special formatting for overdue dates
            for col_idx, (col_name, value) in enumerate(row.items()):
                with row_cols[col_idx + 1]:
                    # Check if this is a date column and if it's overdue
                    original_col_name = list(display_df_page.columns)[col_idx]
                    is_date_col_overdue = False
                    
                    if col_name in ['ETD', 'ETA']:
                        original_col_key = 'etd' if col_name == 'ETD' else 'eta'
                        if original_col_key in original_row:
                            is_date_col_overdue = is_date_overdue(original_row[original_col_key])
                    
                    # Format display value
                    display_value = str(value) if pd.notna(value) else ""
                    if len(display_value) > 50:
                        display_value = display_value[:47] + "..."
                    
                    # Add warning emoji for overdue dates
                    if is_date_col_overdue:
                        display_value = f"⚠️ {display_value}"
                    
                    st.text(display_value)
            
            st.markdown('</div>', unsafe_allow_html=True)
            st.markdown("")  # Small spacing
    
    # Pagination controls at bottom
    st.markdown("---")
    col1, col2, col3 = st.columns([2, 1, 2])
    
    with col1:
        if st.session_state.page_number > 1:
            if st.button("← Previous", use_container_width=True):
                st.session_state.page_number -= 1
                st.rerun()
    
    with col2:
        st.markdown(
            f"<div style='text-align: center; padding-top: 8px;'>Page {st.session_state.page_number} of {total_pages}</div>", 
            unsafe_allow_html=True
        )
    
    with col3:
        if st.session_state.page_number < total_pages:
            if st.button("Next →", use_container_width=True):
                st.session_state.page_number += 1
                st.rerun()


def row_has_overdue_dates(row: pd.Series) -> bool:
    """
    Check if a row has any overdue ETD or ETA dates
    
    Args:
        row: DataFrame row
        
    Returns:
        bool: True if row has overdue dates
    """
    etd_overdue = False
    eta_overdue = False
    
    if 'etd' in row:
        etd_overdue = is_date_overdue(row['etd'])
    
    if 'eta' in row:
        eta_overdue = is_date_overdue(row['eta'])
    
    return etd_overdue or eta_overdue


def count_overdue_rows(df: pd.DataFrame) -> int:
    """
    Count how many rows have overdue dates
    
    Args:
        df: Purchase order dataframe
        
    Returns:
        int: Count of overdue rows
    """
    if df.empty:
        return 0
    
    overdue_count = 0
    for _, row in df.iterrows():
        if row_has_overdue_dates(row):
            overdue_count += 1
    
    return overdue_count


def render_summary_stats(po_df: pd.DataFrame) -> None:
    """
    Render summary statistics section
    
    Args:
        po_df: Purchase order dataframe
    """
    st.markdown("### 📊 Summary Statistics")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("**By Status:**")
        status_summary = po_df.groupby('status').agg({
            'po_line_id': 'count',
            'total_amount_usd': 'sum'
        }).round(0)
        status_summary.columns = ['Count', 'Total USD']
        st.dataframe(status_summary, use_container_width=True)
    
    with col2:
        st.markdown("**By Vendor Type:**")
        vendor_summary = po_df.groupby('vendor_type').agg({
            'po_line_id': 'count',
            'total_amount_usd': 'sum'
        }).round(0)
        vendor_summary.columns = ['Count', 'Total USD']
        st.dataframe(vendor_summary, use_container_width=True)
    
    st.markdown("---")
    
    # Top vendors
    st.markdown("**Top 10 Vendors by Outstanding Amount:**")
    top_vendors = po_df.groupby('vendor_name').agg({
        'outstanding_arrival_amount_usd': 'sum',
        'po_number': 'nunique'
    }).round(0)
    top_vendors.columns = ['Outstanding USD', 'PO Count']
    top_vendors = top_vendors.sort_values('Outstanding USD', ascending=False).head(10)
    st.dataframe(top_vendors, use_container_width=True)