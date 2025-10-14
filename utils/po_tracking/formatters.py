"""
Formatting and Display Functions
Pure functions for data formatting and UI rendering
"""

import streamlit as st
import pandas as pd
from datetime import datetime
from typing import List


def format_currency(value: float) -> str:
    """Format number as USD currency"""
    return f"${value:,.2f}"


def format_product_display(pt_code: str, name: str, package_size: str, brand: str) -> str:
    """Format product display: PT001 | Product Name | 500ml (Brand)"""
    package = package_size if package_size else 'N/A'
    brand_name = brand if brand else 'No Brand'
    return f"{pt_code} | {name} | {package} ({brand_name})"


def render_metrics(po_df: pd.DataFrame):
    """Display 6 metric cards"""
    col1, col2, col3, col4, col5, col6 = st.columns(6)
    
    with col1:
        total_pos = po_df['po_number'].nunique()
        st.metric("Total POs", f"{total_pos:,}")
    
    with col2:
        total_lines = len(po_df)
        st.metric("Total Lines", f"{total_lines:,}")
    
    with col3:
        total_value = po_df['total_amount_usd'].sum()
        st.metric("Total Value", f"${total_value/1000000:.1f}M")
    
    with col4:
        outstanding_value = po_df['outstanding_arrival_amount_usd'].sum()
        st.metric("Outstanding", f"${outstanding_value/1000000:.1f}M")
    
    with col5:
        overdue_count = len(po_df[po_df['etd'] < datetime.now().date()])
        st.metric("Overdue Items", f"{overdue_count:,}", delta_color="inverse")
    
    with col6:
        avg_completion = po_df['arrival_completion_percent'].mean()
        st.metric("Avg Completion", f"{avg_completion:.1f}%")


def render_detail_list(po_df: pd.DataFrame):
    """Render the detailed list tab with styling"""
    st.subheader("📋 Detailed PO List")
    
    # Default columns
    default_columns = [
        'po_number', 'vendor_name', 'vendor_location_type',
        'po_date', 'etd', 'eta', 'pt_code', 'product_name', 
        'buying_quantity', 'pending_standard_arrival_quantity',
        'arrival_completion_percent', 'outstanding_arrival_amount_usd',
        'status', 'created_by'
    ]
    
    # Column selection
    display_columns = st.multiselect(
        "Select columns to display",
        options=po_df.columns.tolist(),
        default=[col for col in default_columns if col in po_df.columns]
    )
    
    if not display_columns:
        st.warning("Please select at least one column to display")
        return
    
    # Prepare display dataframe
    display_df = po_df[display_columns].copy()
    
    # Format date columns
    date_columns = ['po_date', 'etd', 'eta', 'last_invoice_date']
    for col in date_columns:
        if col in display_df.columns:
            display_df[col] = pd.to_datetime(display_df[col]).dt.strftime('%Y-%m-%d')
    
    # Apply styling
    styled_df = apply_conditional_styling(display_df)
    
    # Display dataframe
    st.dataframe(
        styled_df,
        use_container_width=True,
        height=600,
        hide_index=True
    )
    
    # Summary statistics
    st.markdown("---")
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric("Total Rows", f"{len(display_df):,}")
    
    with col2:
        if 'outstanding_arrival_amount_usd' in display_df.columns:
            total_outstanding = display_df['outstanding_arrival_amount_usd'].sum()
            st.metric("Total Outstanding", f"${total_outstanding:,.2f}")
    
    with col3:
        if 'arrival_completion_percent' in display_df.columns:
            avg_completion = display_df['arrival_completion_percent'].mean()
            st.metric("Avg Completion", f"{avg_completion:.1f}%")
    
    with col4:
        if 'etd' in display_df.columns:
            today = datetime.now().date()
            overdue_count = 0
            for etd in display_df['etd']:
                try:
                    if pd.notna(etd) and pd.to_datetime(etd).date() < today:
                        overdue_count += 1
                except:
                    pass
            st.metric("Overdue Items", f"{overdue_count:,}", delta_color="inverse")
    
    # Export button
    csv = display_df.to_csv(index=False).encode('utf-8')
    st.download_button(
        label="📥 Download Detailed List",
        data=csv,
        file_name=f"po_detailed_list_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
        mime='text/csv'
    )
    
    # Help text
    with st.expander("ℹ️ Column Formatting Guide"):
        st.markdown("""
        **Color Coding:**
        - **Status Colors**: 
          - 🟢 Green = Completed
          - 🟡 Yellow = Pending
          - 🟠 Orange = Pending Invoicing
          - 🔴 Red = Over Delivered
        - **Completion %**: 
          - Red (< 30%) → Orange (30-70%) → Green (70-99%) → Blue (100%+)
        - **Dates**: Red & Bold = Overdue
        - **Vendor Location**: Red & Bold = International
        - **Outstanding Amounts**: Gradient from Yellow to Red (higher = darker)
        
        **Number Formats:**
        - Quantities: Thousand separators, no decimals
        - Percentages: One decimal place
        - USD Amounts: $ symbol with 2 decimal places
        - Exchange Rates: 4 decimal places
        
        **Product Format:** PT_CODE | Product Name | Package Size (Brand)
        """)


def apply_conditional_styling(df: pd.DataFrame) -> pd.DataFrame.style:
    """Apply all conditional styling to dataframe"""
    
    # Define format dictionary for numeric columns
    format_dict = {}
    
    # Format quantity columns (no decimals)
    quantity_columns = [
        'buying_quantity', 'standard_quantity', 
        'pending_standard_arrival_quantity', 'total_standard_arrived_quantity',
        'pending_buying_invoiced_quantity', 'total_buying_invoiced_quantity',
        'moq', 'spq'
    ]
    for col in quantity_columns:
        if col in df.columns:
            format_dict[col] = '{:,.0f}'
    
    # Format percentage columns (1 decimal)
    percent_columns = [
        'arrival_completion_percent', 'invoice_completion_percent',
        'vat_gst_percent'
    ]
    for col in percent_columns:
        if col in df.columns:
            format_dict[col] = '{:.1f}%'
    
    # Format currency columns
    currency_columns = [
        'purchase_unit_cost', 'standard_unit_cost',
        'total_amount', 'total_amount_usd',
        'outstanding_arrival_amount_usd', 'outstanding_invoiced_amount_usd',
        'invoiced_amount_usd', 'arrival_amount_usd'
    ]
    for col in currency_columns:
        if col in df.columns:
            if 'usd' in col.lower():
                format_dict[col] = '${:,.2f}'
            else:
                format_dict[col] = '{:,.2f}'
    
    # Format exchange rate columns (4 decimals)
    if 'usd_exchange_rate' in df.columns:
        format_dict['usd_exchange_rate'] = '{:.4f}'
    
    # Create styled dataframe
    styled_df = df.style.format(format_dict)
    
    # Apply row-wise highlighting based on status
    if 'status' in df.columns:
        styled_df = styled_df.apply(highlight_status, axis=1)
    
    # Apply column-specific highlighting
    if 'vendor_location_type' in df.columns:
        styled_df = styled_df.map(
            highlight_vendor_location, 
            subset=['vendor_location_type']
        )
    
    if 'arrival_completion_percent' in df.columns:
        styled_df = styled_df.map(
            highlight_completion,
            subset=['arrival_completion_percent']
        )
    
    if 'invoice_completion_percent' in df.columns:
        styled_df = styled_df.map(
            highlight_completion,
            subset=['invoice_completion_percent']
        )
    
    if 'is_over_delivered' in df.columns:
        styled_df = styled_df.map(
            highlight_over_delivered,
            subset=['is_over_delivered']
        )
    
    # Apply date highlighting
    for col in ['etd', 'eta']:
        if col in df.columns:
            styled_df = styled_df.map(
                lambda val: highlight_overdue(val, col),
                subset=[col]
            )
    
    # Add gradient for outstanding amounts
    amount_cols = [col for col in ['outstanding_arrival_amount_usd', 'outstanding_invoiced_amount_usd'] 
                   if col in df.columns]
    if amount_cols:
        styled_df = styled_df.background_gradient(
            subset=amount_cols,
            cmap='YlOrRd',
            vmin=0
        )
    
    return styled_df


# Styling helper functions
def highlight_status(row):
    """Highlight entire row based on status"""
    if row.get('status') == 'COMPLETED':
        return ['background-color: #d4f8d4'] * len(row)
    elif row.get('status') == 'OVER_DELIVERED':
        return ['background-color: #ffcccb'] * len(row)
    elif row.get('status') == 'PENDING':
        return ['background-color: #fff3cd'] * len(row)
    elif row.get('status') == 'PENDING_INVOICING':
        return ['background-color: #ffe4b5'] * len(row)
    return [''] * len(row)


def highlight_overdue(val, col_name):
    """Highlight overdue dates"""
    if col_name in ['etd', 'eta'] and pd.notna(val):
        try:
            date_val = pd.to_datetime(val)
            if date_val.date() < datetime.now().date():
                return 'color: red; font-weight: bold'
        except:
            pass
    return ''


def highlight_completion(val):
    """Color code completion percentage"""
    if pd.isna(val):
        return ''
    try:
        num_val = float(str(val).replace('%', ''))
        if num_val < 30:
            return 'color: #dc3545; font-weight: bold'
        elif num_val < 70:
            return 'color: #fd7e14; font-weight: bold'
        elif num_val < 100:
            return 'color: #198754'
        else:
            return 'color: #0d6efd; font-weight: bold'
    except:
        return ''


def highlight_vendor_location(val):
    """Highlight international vendors"""
    if val == 'International':
        return 'color: #dc3545; font-weight: bold'
    return ''


def highlight_over_delivered(val):
    """Highlight over-delivered items"""
    if val == 'Y':
        return 'background-color: #ffb3ba; font-weight: bold'
    return ''