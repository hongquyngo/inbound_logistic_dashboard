# utils/can_tracking/formatters.py

"""
Formatters Module for CAN Tracking
Handles display formatting, pagination, and edit buttons
"""

import streamlit as st
import pandas as pd
from datetime import date, datetime
from typing import List, Dict, Any
from utils.can_tracking.column_config import (
    render_column_selector,
    get_column_display_name
)
from utils.can_tracking.can_editor import (
    render_edit_button,
    render_can_editor_modal,
    is_date_overdue,
    parse_date
)


def render_metrics(can_df: pd.DataFrame, urgent_threshold: int = 7, critical_threshold: int = 14) -> None:
    """
    Render key metrics cards
    
    Args:
        can_df: CAN dataframe
        urgent_threshold: Days threshold for urgent items
        critical_threshold: Days threshold for critical items
    """
    pending_df = can_df[can_df['pending_quantity'] > 0]
    
    col1, col2, col3, col4, col5, col6 = st.columns(6)
    
    with col1:
        total_items = len(can_df)
        pending_items = len(pending_df)
        st.metric(
            "Total Items",
            f"{total_items:,}",
            delta=f"{pending_items} pending" if pending_items > 0 else "All completed"
        )
    
    with col2:
        arrived_value = can_df['landed_cost_usd'].sum()
        pending_value = pending_df['pending_value_usd'].sum()
        st.metric(
            "Total Arrived Value",
            f"${arrived_value/1000:.0f}K",
            delta=f"${pending_value/1000:.0f}K pending" if pending_value > 0 else None
        )
    
    with col3:
        urgent_items = len(pending_df[pending_df['days_since_arrival'] > urgent_threshold])
        st.metric(
            f"Urgent Items (>{urgent_threshold}d)",
            f"{urgent_items:,}",
            delta_color="inverse" if urgent_items > 0 else "off"
        )
    
    with col4:
        critical_items = len(pending_df[pending_df['days_since_arrival'] > critical_threshold])
        st.metric(
            f"Critical Items (>{critical_threshold}d)",
            f"{critical_items:,}",
            delta_color="inverse" if critical_items > 0 else "off"
        )
    
    with col5:
        avg_days_all = can_df['days_since_arrival'].mean()
        avg_days_pending = pending_df['days_since_arrival'].mean() if len(pending_df) > 0 else 0
        st.metric(
            "Avg Days Since Arrival",
            f"{avg_days_all:.1f}",
            delta=f"{avg_days_pending:.1f} for pending" if avg_days_pending > 0 else None
        )
    
    with col6:
        unique_cans = can_df['arrival_note_number'].nunique()
        completed_cans = can_df[can_df['pending_quantity'] == 0]['arrival_note_number'].nunique()
        st.metric(
            "Total CANs",
            f"{unique_cans:,}",
            delta=f"{completed_cans} completed" if completed_cans > 0 else None
        )


def render_detail_list(can_df: pd.DataFrame, data_service=None) -> None:
    """
    Render detailed CAN list with column selection, edit functionality, and overdue highlighting
    
    Args:
        can_df: CAN dataframe
        data_service: CANDataService instance for updates
    """
    st.markdown("### 📋 Detailed CAN List")
    
    if can_df.empty:
        st.info("No data to display")
        return
    
    # Render column selector
    selected_columns = render_column_selector()
    
    if not selected_columns:
        st.warning("⚠️ No columns selected. Please select columns to display.")
        return
    
    # Show total record count and overdue count
    overdue_count = count_overdue_rows(can_df)
    col1, col2 = st.columns([3, 1])
    with col1:
        st.caption(f"Showing {len(can_df):,} records")
    with col2:
        if overdue_count > 0:
            st.caption(f"⚠️ {overdue_count} overdue arrivals")
    
    # Prepare display dataframe
    display_df = prepare_display_dataframe(can_df, selected_columns)
    
    # Render table with edit buttons and highlighting
    render_table_with_actions(display_df, can_df, selected_columns, data_service)
    
    # Render editor modal if active
    if data_service:
        render_can_editor_modal(data_service)
    
    # Legend
    st.markdown("---")
    st.caption("""
    **Legend:** 
    ⚠️ Warning emoji on date cells = Overdue arrival (past today)
    """)
    
    # Export buttons
    col1, col2, col3 = st.columns([1, 1, 4])
    
    with col1:
        csv = can_df[selected_columns].to_csv(index=False).encode('utf-8')
        st.download_button(
            label="📥 Download CSV",
            data=csv,
            file_name=f"can_tracking_{pd.Timestamp.now().strftime('%Y%m%d_%H%M%S')}.csv",
            mime="text/csv",
            use_container_width=True
        )
    
    with col2:
        from io import BytesIO
        
        excel_buffer = BytesIO()
        with pd.ExcelWriter(excel_buffer, engine='xlsxwriter') as writer:
            can_df[selected_columns].to_excel(writer, index=False, sheet_name='CAN Data')
        
        st.download_button(
            label="📥 Download Excel",
            data=excel_buffer.getvalue(),
            file_name=f"can_tracking_{pd.Timestamp.now().strftime('%Y%m%d_%H%M%S')}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True
        )


def prepare_display_dataframe(can_df: pd.DataFrame, selected_columns: List[str]) -> pd.DataFrame:
    """
    Prepare dataframe for display with selected columns and proper formatting
    
    Args:
        can_df: Full CAN dataframe
        selected_columns: List of columns to display
        
    Returns:
        Formatted dataframe for display
    """
    existing_columns = [col for col in selected_columns if col in can_df.columns]
    display_df = can_df[existing_columns].copy()
    
    # Rename columns to display names
    column_mapping = {
        col: get_column_display_name(col) 
        for col in existing_columns
    }
    display_df = display_df.rename(columns=column_mapping)
    
    # Format numeric columns
    for col in display_df.columns:
        if 'USD' in col or 'Cost' in col or 'Value' in col:
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
        data_service: CANDataService instance
    """
    # Initialize pagination
    if 'can_page_number' not in st.session_state:
        st.session_state.can_page_number = 1
    
    rows_per_page = 50
    total_rows = len(display_df)
    total_pages = (total_rows + rows_per_page - 1) // rows_per_page
    
    # Calculate indices for current page
    start_idx = (st.session_state.can_page_number - 1) * rows_per_page
    end_idx = min(start_idx + rows_per_page, total_rows)
    
    display_df_page = display_df.iloc[start_idx:end_idx]
    original_df_page = original_df.iloc[start_idx:end_idx]
    
    # Create table
    with st.container():
        # Header row
        header_cols = st.columns([1] + [3] * len(display_df_page.columns))
        
        with header_cols[0]:
            st.markdown("**Actions**")
        
        for idx, col_name in enumerate(display_df_page.columns):
            with header_cols[idx + 1]:
                st.markdown(f"**{col_name}**")
        
        st.divider()
        
        # Data rows
        for idx, (display_idx, row) in enumerate(display_df_page.iterrows()):
            original_row = original_df_page.iloc[idx]
            
            row_cols = st.columns([1] + [3] * len(row))
            
            # Action column with edit button
            with row_cols[0]:
                can_line_id = original_row['can_line_id']
                arrival_note_number = original_row['arrival_note_number']
                render_edit_button(
                    can_line_id=can_line_id,
                    arrival_note_number=arrival_note_number,
                    row_data=original_row.to_dict()
                )
            
            # Data columns
            for col_idx, (col_name, value) in enumerate(row.items()):
                with row_cols[col_idx + 1]:
                    # Check if arrival date is overdue
                    is_date_col_overdue = False
                    
                    if col_name == 'Arrival Date':
                        if 'arrival_date' in original_row:
                            is_date_col_overdue = is_date_overdue(original_row['arrival_date'])
                    
                    # Format display value
                    display_value = str(value) if pd.notna(value) else ""
                    if len(display_value) > 50:
                        display_value = display_value[:47] + "..."
                    
                    # Add warning emoji for overdue dates
                    if is_date_col_overdue:
                        display_value = f"⚠️ {display_value}"
                    
                    st.text(display_value)
            
            # Simple spacing between rows
            if idx < len(display_df_page) - 1:
                st.markdown("")
    
    # Pagination controls
    st.divider()
    col1, col2, col3 = st.columns([2, 1, 2])
    
    with col1:
        if st.session_state.can_page_number > 1:
            if st.button("← Previous", use_container_width=True, key="can_prev"):
                st.session_state.can_page_number -= 1
                st.rerun()
    
    with col2:
        st.markdown(
            f"<div style='text-align: center; padding-top: 8px;'>Page {st.session_state.can_page_number} of {total_pages}</div>",
            unsafe_allow_html=True
        )
    
    with col3:
        if st.session_state.can_page_number < total_pages:
            if st.button("Next →", use_container_width=True, key="can_next"):
                st.session_state.can_page_number += 1
                st.rerun()

def row_has_overdue_dates(row: pd.Series) -> bool:
    """Check if a row has overdue arrival date"""
    if 'arrival_date' in row:
        return is_date_overdue(row['arrival_date'])
    return False


def count_overdue_rows(df: pd.DataFrame) -> int:
    """Count how many rows have overdue dates"""
    if df.empty:
        return 0
    
    overdue_count = 0
    for _, row in df.iterrows():
        if row_has_overdue_dates(row):
            overdue_count += 1
    
    return overdue_count