# utils/can_tracking/formatters.py

"""
Formatters Module for CAN Tracking - Batch Update Version
Handles display formatting, pagination, and visual indicators for pending changes
"""

import streamlit as st
import pandas as pd
from datetime import date, datetime
from typing import List, Dict, Any, Optional
from io import BytesIO

from utils.can_tracking.column_config import (
    render_column_selector,
    get_column_display_name
)
from utils.can_tracking.can_editor import (
    render_edit_button,
    render_can_editor_modal,
    render_floating_action_bar,
    render_leave_warning_script,
    is_date_overdue,
    parse_date
)
from utils.can_tracking.pending_changes import get_pending_manager


def render_metrics(can_df: pd.DataFrame, urgent_threshold: int = 7, critical_threshold: int = 14) -> None:
    """
    Render key metrics cards
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
    Render detailed CAN list with column selection and edit functionality
    """
    st.markdown("### 📋 Detailed CAN List")
    
    if can_df.empty:
        st.info("No data to display")
        return
    
    # Column selector
    selected_columns = render_column_selector()
    
    if not selected_columns:
        st.warning("⚠️ No columns selected. Please select columns to display.")
        return
    
    # Store data in session state for fragment access
    st.session_state['_can_df_for_fragment'] = can_df
    st.session_state['_can_selected_columns'] = selected_columns
    st.session_state['_can_data_service'] = data_service
    
    # Render the fragment
    _render_detail_list_fragment()
    
    # Render floating action bar (outside fragment for visibility)
    render_floating_action_bar()
    
    # Render leave warning script
    render_leave_warning_script()


@st.fragment
def _render_detail_list_fragment() -> None:
    """
    Fragment for detail list - reruns independently for pagination and editing
    """
    can_df = st.session_state.get('_can_df_for_fragment')
    selected_columns = st.session_state.get('_can_selected_columns', [])
    data_service = st.session_state.get('_can_data_service')
    
    if can_df is None or can_df.empty:
        st.info("No data to display")
        return
    
    # Summary info with pending changes count
    pending_manager = get_pending_manager()
    pending_count = pending_manager.get_change_count()
    overdue_count = count_overdue_rows(can_df)
    
    col1, col2, col3 = st.columns([2, 2, 2])
    with col1:
        st.caption(f"Showing {len(can_df):,} records")
    with col2:
        if overdue_count > 0:
            st.caption(f"⚠️ {overdue_count} overdue arrivals")
    with col3:
        if pending_count > 0:
            st.caption(f"🟡 {pending_count} pending changes")
    
    # Prepare display dataframe
    display_df = prepare_display_dataframe(can_df, selected_columns)
    
    # Render table with pagination
    render_table_with_actions(display_df, can_df, selected_columns, data_service)
    
    # Editor modal
    if data_service:
        render_can_editor_modal(data_service)
    
    st.markdown("---")
    
    # Legend
    st.caption("""
    **Legend:** 
    ⚠️ = Overdue arrival | 
    🟡 = Has pending changes (not yet applied) | 
    ⚡ = Value modified (staged)
    """)
    
    # Download buttons
    _render_download_buttons(can_df, selected_columns)


def _render_download_buttons(can_df: pd.DataFrame, selected_columns: List[str]) -> None:
    """Render download buttons for CSV and Excel"""
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
    """
    existing_columns = [col for col in selected_columns if col in can_df.columns]
    display_df = can_df[existing_columns].copy()
    
    column_mapping = {
        col: get_column_display_name(col) 
        for col in existing_columns
    }
    display_df = display_df.rename(columns=column_mapping)
    
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
    Render dataframe with action buttons, overdue highlighting, and pending indicators
    """
    pending_manager = get_pending_manager()
    
    # Initialize pagination
    if 'can_page_number' not in st.session_state:
        st.session_state.can_page_number = 1
    
    rows_per_page = 50
    total_rows = len(display_df)
    total_pages = max(1, (total_rows + rows_per_page - 1) // rows_per_page)
    
    if st.session_state.can_page_number > total_pages:
        st.session_state.can_page_number = total_pages
    
    start_idx = (st.session_state.can_page_number - 1) * rows_per_page
    end_idx = min(start_idx + rows_per_page, total_rows)
    
    display_df_page = display_df.iloc[start_idx:end_idx]
    original_df_page = original_df.iloc[start_idx:end_idx]
    
    # Render table rows
    _render_table_rows(display_df_page, original_df_page, data_service, pending_manager)
    
    # Pagination controls
    _render_pagination_controls(total_pages)


def _render_table_rows(
    display_df_page: pd.DataFrame,
    original_df_page: pd.DataFrame,
    data_service,
    pending_manager
) -> None:
    """Render table rows with action buttons and visual indicators"""
    
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
            arrival_note_number = original_row['arrival_note_number']
            
            # Check if this row has pending changes
            has_pending = pending_manager.has_change_for(arrival_note_number)
            pending_change = pending_manager.get_change(arrival_note_number) if has_pending else None
            
            # Row styling based on pending status
            row_cols = st.columns([1] + [3] * len(row))
            
            # Action button
            with row_cols[0]:
                can_line_id = original_row['can_line_id']
                render_edit_button(
                    can_line_id=can_line_id,
                    arrival_note_number=arrival_note_number,
                    row_data=original_row.to_dict()
                )
            
            # Data cells
            for col_idx, (col_name, value) in enumerate(row.items()):
                with row_cols[col_idx + 1]:
                    display_value = str(value) if pd.notna(value) else ""
                    
                    # Check for overdue
                    is_overdue = False
                    if col_name == 'Arrival Date' and 'arrival_date' in original_row:
                        is_overdue = is_date_overdue(original_row['arrival_date'])
                    
                    # Check if this cell was modified in pending change
                    is_modified = False
                    if has_pending and pending_change:
                        if col_name == 'Arrival Date' and pending_change.has_date_change:
                            is_modified = True
                            # Show new value from pending change
                            display_value = pending_change._format_date(pending_change.new_arrival_date)
                        elif col_name == 'CAN Status' and pending_change.has_status_change:
                            is_modified = True
                            display_value = pending_change._format_status(pending_change.new_status)
                        elif col_name == 'Warehouse' and pending_change.has_warehouse_change:
                            is_modified = True
                            display_value = pending_change.new_warehouse_name
                    
                    # Truncate long values
                    if len(display_value) > 50:
                        display_value = display_value[:47] + "..."
                    
                    # Add indicators
                    prefix = ""
                    if is_overdue:
                        prefix += "⚠️ "
                    if is_modified:
                        prefix += "⚡"
                    
                    st.text(f"{prefix}{display_value}")
            
            if idx < len(display_df_page) - 1:
                st.markdown("")


def _render_pagination_controls(total_pages: int) -> None:
    """Render pagination controls"""
    st.divider()
    col1, col2, col3 = st.columns([2, 1, 2])
    
    with col1:
        if st.session_state.can_page_number > 1:
            if st.button("← Previous", use_container_width=True, key="can_prev_frag"):
                st.session_state.can_page_number -= 1
                st.rerun(scope="fragment")
    
    with col2:
        st.markdown(
            f"<div style='text-align: center; padding-top: 8px;'>Page {st.session_state.can_page_number} of {total_pages}</div>",
            unsafe_allow_html=True
        )
    
    with col3:
        if st.session_state.can_page_number < total_pages:
            if st.button("Next →", use_container_width=True, key="can_next_frag"):
                st.session_state.can_page_number += 1
                st.rerun(scope="fragment")


def row_has_overdue_dates(row: pd.Series) -> bool:
    """Check if a row has overdue arrival date"""
    if 'arrival_date' in row:
        return is_date_overdue(row['arrival_date'])
    return False


def count_overdue_rows(df: pd.DataFrame) -> int:
    """Count how many rows have overdue dates - vectorized for performance"""
    if df.empty or 'arrival_date' not in df.columns:
        return 0
    
    today = date.today()
    arrival_dates = pd.to_datetime(df['arrival_date'], errors='coerce').dt.date
    return (arrival_dates < today).sum()