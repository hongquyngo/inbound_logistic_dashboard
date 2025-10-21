"""
Overview Tab for Vendor Performance

Shows high-level performance summary and comparison views.
"""

import streamlit as st
import pandas as pd
from datetime import datetime
from typing import Optional

from ..calculations import PerformanceCalculator
from ..visualizations import ChartFactory


def render(
    vendor_metrics: pd.DataFrame,
    po_data: pd.DataFrame,
    selected_vendor: str
) -> None:
    """
    Render Overview Tab
    
    Args:
        vendor_metrics: DataFrame with vendor metrics
        po_data: DataFrame with PO data
        selected_vendor: Selected vendor name or "All Vendors"
    """
    st.subheader("📊 Performance Overview")
    
    if vendor_metrics.empty:
        st.warning("No vendor performance data available")
        return
    
    # Calculate performance scores once at the beginning
    calc = PerformanceCalculator()
    vendor_metrics = calc.calculate_performance_score(vendor_metrics)
    
    if selected_vendor == "All Vendors":
        _render_all_vendors(vendor_metrics)
    else:
        _render_single_vendor(vendor_metrics, selected_vendor)
    
    # Performance comparison table
    st.markdown("---")
    _render_performance_table(vendor_metrics, selected_vendor)


def _render_all_vendors(vendor_metrics: pd.DataFrame) -> None:
    """
    Show comparison view for all vendors
    
    Args:
        vendor_metrics: DataFrame with all vendor metrics (already has performance_score)
    """
    # Note: performance_score already calculated in render()
    
    # Overall summary metrics
    st.markdown("### Overall Vendor Performance Summary")
    col1, col2, col3, col4, col5, col6 = st.columns(6)
    
    with col1:
        st.metric(
            "Total Vendors",
            f"{len(vendor_metrics):,}",
            help="Total number of active vendors"
        )
    
    with col2:
        total_po_value = vendor_metrics['total_po_value'].sum()
        st.metric(
            "Total Spend",
            f"${total_po_value/1000000:.1f}M",
            help="Total purchase value across all vendors"
        )
    
    with col3:
        avg_on_time = vendor_metrics['on_time_rate'].mean()
        st.metric(
            "Avg On-Time Rate",
            f"{avg_on_time:.1f}%",
            delta=f"{avg_on_time - 80:.1f}%",
            delta_color="normal" if avg_on_time >= 80 else "inverse"
        )
    
    with col4:
        avg_completion = vendor_metrics['completion_rate'].mean()
        st.metric(
            "Avg Completion",
            f"{avg_completion:.1f}%",
            help="Average PO completion rate"
        )
    
    with col5:
        high_performers = len(vendor_metrics[vendor_metrics['performance_score'] >= 80])
        st.metric(
            "High Performers",
            f"{high_performers}",
            help="Vendors with score ≥ 80%"
        )
    
    with col6:
        total_outstanding = vendor_metrics['outstanding_invoices'].sum()
        st.metric(
            "Total Outstanding",
            f"${total_outstanding/1000000:.1f}M",
            help="Total outstanding invoices"
        )
    
    st.markdown("---")
    
    # Two columns layout for charts
    col1, col2 = st.columns(2)
    
    with col1:
        st.markdown("### Top Performing Vendors")
        
        # Performance matrix scatter plot
        chart_factory = ChartFactory()
        fig_matrix = chart_factory.create_performance_matrix(vendor_metrics, top_n=10)
        st.plotly_chart(fig_matrix, use_container_width=True, config={'displaylogo': False})
    
    with col2:
        st.markdown("### Vendor Distribution by Type")
        
        # Vendor distribution sunburst
        fig_dist = chart_factory.create_vendor_distribution(vendor_metrics)
        st.plotly_chart(fig_dist, use_container_width=True, config={'displaylogo': False})
    
    # Performance distribution
    st.markdown("---")
    st.markdown("### Performance Distribution Analysis")
    
    col1, col2 = st.columns(2)
    
    with col1:
        # Performance score distribution
        fig_score_dist = chart_factory.create_distribution_histogram(
            vendor_metrics,
            'performance_score',
            bins=20,
            title='Vendor Performance Score Distribution'
        )
        st.plotly_chart(fig_score_dist, use_container_width=True, config={'displaylogo': False})
    
    with col2:
        # Lead time box plot
        fig_lead_time = chart_factory.create_box_plot(
            vendor_metrics,
            x_col='vendor_location_type',
            y_col='avg_lead_time_days',
            color_col='vendor_type',
            title='Lead Time Distribution by Vendor Type'
        )
        st.plotly_chart(fig_lead_time, use_container_width=True, config={'displaylogo': False})


def _render_single_vendor(vendor_metrics: pd.DataFrame, vendor_name: str) -> None:
    """
    Show detailed view for one vendor
    
    Args:
        vendor_metrics: DataFrame with vendor metrics (already has performance_score)
        vendor_name: Name of vendor to display
    """
    vendor_data = vendor_metrics[vendor_metrics['vendor_name'] == vendor_name]
    
    if vendor_data.empty:
        st.warning(f"No data found for vendor: {vendor_name}")
        return
    
    vendor_data = vendor_data.iloc[0]
    
    # Get performance score (already calculated)
    calc = PerformanceCalculator()
    performance_score = vendor_data.get('performance_score', 0)
    
    # Key metrics
    st.markdown("### Key Performance Metrics")
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric(
            "Total Purchase Value",
            f"${vendor_data.get('total_po_value', 0):,.0f}",
            help="Total value of all POs in the period"
        )
    
    with col2:
        on_time_rate = vendor_data.get('on_time_rate', 0)
        st.metric(
            "On-Time Delivery",
            f"{on_time_rate:.1f}%",
            delta=f"{on_time_rate - 80:.1f}%",
            delta_color="normal" if on_time_rate >= 80 else "inverse"
        )
    
    with col3:
        completion_rate = vendor_data.get('completion_rate', 0)
        st.metric(
            "Completion Rate",
            f"{completion_rate:.1f}%",
            help="Percentage of POs fully completed"
        )
    
    with col4:
        tier = calc.assign_performance_tier(performance_score)
        st.metric(
            "Performance Score",
            f"{performance_score:.1f}%",
            help="Overall performance score (weighted)"
        )
        st.caption(tier)
    
    # Additional metrics
    st.markdown("---")
    st.markdown("### Additional Metrics")
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric("Total POs", f"{vendor_data.get('total_pos', 0):,}")
    
    with col2:
        st.metric("Completed POs", f"{vendor_data.get('completed_pos', 0):,}")
    
    with col3:
        st.metric("Over Deliveries", f"{vendor_data.get('over_delivery_pos', 0):,}")
    
    with col4:
        st.metric(
            "Outstanding Amount",
            f"${vendor_data.get('outstanding_invoices', 0):,.0f}"
        )


def _render_performance_table(
    vendor_metrics: pd.DataFrame,
    selected_vendor: str
) -> None:
    """
    Display performance comparison table
    
    Args:
        vendor_metrics: DataFrame with vendor metrics (already has performance_score)
        selected_vendor: Selected vendor name
    """
    st.markdown("### Vendor Performance Metrics")
    
    if vendor_metrics.empty:
        st.info("No vendor metrics to display")
        return
    
    # Note: performance_score already calculated in render()
    # Just need to add tier
    calc = PerformanceCalculator()
    display_metrics = vendor_metrics.copy()
    
    # Add performance tier
    display_metrics['performance_tier'] = display_metrics['performance_score'].apply(
        calc.assign_performance_tier
    )
    
    # Select display columns
    display_cols = [
        'vendor_name', 'vendor_type', 'vendor_location_type',
        'total_pos', 'completed_pos', 'on_time_rate',
        'completion_rate', 'avg_over_delivery_percent',
        'total_po_value', 'outstanding_invoices',
        'performance_score', 'performance_tier'
    ]
    
    # Filter existing columns
    existing_cols = [col for col in display_cols if col in display_metrics.columns]
    display_df = display_metrics[existing_cols].copy()
    
    # Rename columns for display
    column_mapping = {
        'vendor_name': 'Vendor',
        'vendor_type': 'Type',
        'vendor_location_type': 'Location',
        'total_pos': 'Total POs',
        'completed_pos': 'Completed',
        'on_time_rate': 'On-Time %',
        'completion_rate': 'Completion %',
        'avg_over_delivery_percent': 'Avg Over %',
        'total_po_value': 'Total Value',
        'outstanding_invoices': 'Outstanding',
        'performance_score': 'Score',
        'performance_tier': 'Tier'
    }
    display_df.rename(columns=column_mapping, inplace=True)
    
    # Format numeric columns
    if 'Total Value' in display_df.columns:
        display_df['Total Value'] = display_df['Total Value'].apply(lambda x: f"${x:,.0f}")
    if 'Outstanding' in display_df.columns:
        display_df['Outstanding'] = display_df['Outstanding'].apply(lambda x: f"${x:,.0f}")
    
    # Sort by performance score
    if 'Score' in display_df.columns:
        display_df = display_df.sort_values('Score', ascending=False)
    
    # Display options
    col1, col2, col3 = st.columns([1, 1, 2])
    
    with col1:
        show_all = st.checkbox("Show All Vendors", value=False)
        if not show_all:
            num_vendors = st.slider("Number of Vendors", 10, 50, 20)
            display_df = display_df.head(num_vendors)
    
    with col2:
        if 'Tier' in display_df.columns:
            filter_tier = st.multiselect(
                "Filter by Tier",
                options=['⭐ Excellent', '✅ Good', '⚠️ Fair', '❌ Poor'],
                default=None
            )
            if filter_tier:
                display_df = display_df[display_df['Tier'].isin(filter_tier)]
    
    with col3:
        # Export button
        csv = display_df.to_csv(index=False).encode('utf-8')
        st.download_button(
            label="📥 Download Performance Metrics",
            data=csv,
            file_name=f"vendor_performance_metrics_{datetime.now().strftime('%Y%m%d')}.csv",
            mime='text/csv'
        )
    
    # Display the dataframe
    st.dataframe(
        display_df,
        use_container_width=True,
        height=600,
        hide_index=True
    )
    
    # Summary statistics
    st.markdown("---")
    st.markdown("#### Performance Summary Statistics")
    
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        if 'Tier' in display_df.columns:
            tier_dist = display_df['Tier'].value_counts()
            st.markdown("**Tier Distribution**")
            for tier, count in tier_dist.items():
                st.write(f"{tier}: {count}")
    
    with col2:
        st.markdown("**Average Metrics**")
        if 'on_time_rate' in vendor_metrics.columns:
            st.write(f"On-Time: {vendor_metrics['on_time_rate'].mean():.1f}%")
        if 'completion_rate' in vendor_metrics.columns:
            st.write(f"Completion: {vendor_metrics['completion_rate'].mean():.1f}%")
        if 'avg_lead_time_days' in vendor_metrics.columns:
            st.write(f"Lead Time: {vendor_metrics['avg_lead_time_days'].mean():.1f} days")
    
    with col3:
        st.markdown("**By Location**")
        if 'vendor_location_type' in vendor_metrics.columns and 'performance_score' in vendor_metrics.columns:
            location_avg = vendor_metrics.groupby('vendor_location_type')['performance_score'].mean()
            for loc, avg in location_avg.items():
                st.write(f"{loc}: {avg:.1f}%")
    
    with col4:
        st.markdown("**By Type**")
        if 'vendor_type' in vendor_metrics.columns and 'performance_score' in vendor_metrics.columns:
            type_avg = vendor_metrics.groupby('vendor_type')['performance_score'].mean()
            for vtype, avg in type_avg.items():
                st.write(f"{vtype}: {avg:.1f}%")