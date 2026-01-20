# utils/can_tracking/pending_changes.py

"""
Pending Changes Manager for CAN Tracking
Handles staging, persistence, and batch processing of CAN updates
"""

import streamlit as st
import json
import logging
from datetime import datetime, date
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass, asdict
import hashlib

logger = logging.getLogger(__name__)

# Session state key for pending changes
PENDING_CHANGES_KEY = '_pending_can_changes'
PERSISTENCE_KEY = '_pending_can_changes_json'


@dataclass
class CANChange:
    """Represents a single CAN change"""
    can_line_id: int
    arrival_note_number: str
    product_name: str
    vendor_name: str
    
    # Original values
    original_arrival_date: Optional[str]
    original_status: str
    original_warehouse_id: int
    original_warehouse_name: str
    
    # New values
    new_arrival_date: str
    new_status: str
    new_warehouse_id: int
    new_warehouse_name: str
    
    # Metadata
    reason: str
    staged_at: str
    row_data: Dict[str, Any]
    
    @property
    def has_date_change(self) -> bool:
        return self.original_arrival_date != self.new_arrival_date
    
    @property
    def has_status_change(self) -> bool:
        return self.original_status != self.new_status
    
    @property
    def has_warehouse_change(self) -> bool:
        return self.original_warehouse_id != self.new_warehouse_id
    
    @property
    def date_diff_days(self) -> Optional[int]:
        if not self.has_date_change or not self.original_arrival_date:
            return None
        try:
            old = datetime.strptime(self.original_arrival_date, '%Y-%m-%d').date()
            new = datetime.strptime(self.new_arrival_date, '%Y-%m-%d').date()
            return (new - old).days
        except:
            return None
    
    def get_changes_summary(self) -> List[str]:
        """Get list of change descriptions"""
        changes = []
        if self.has_date_change:
            diff = self.date_diff_days
            diff_str = f" ({diff:+d} days)" if diff is not None else ""
            changes.append(f"Date: {self._format_date(self.original_arrival_date)} → {self._format_date(self.new_arrival_date)}{diff_str}")
        if self.has_status_change:
            changes.append(f"Status: {self._format_status(self.original_status)} → {self._format_status(self.new_status)}")
        if self.has_warehouse_change:
            changes.append(f"Warehouse: {self.original_warehouse_name} → {self.new_warehouse_name}")
        return changes
    
    @staticmethod
    def _format_date(date_str: Optional[str]) -> str:
        if not date_str:
            return "Not set"
        try:
            d = datetime.strptime(date_str, '%Y-%m-%d')
            return d.strftime('%b %d, %Y')
        except:
            return date_str
    
    @staticmethod
    def _format_status(status: str) -> str:
        from utils.can_tracking.constants import STATUS_DISPLAY
        return STATUS_DISPLAY.get(status, status)


class PendingChangesManager:
    """Manages pending CAN changes with persistence support"""
    
    def __init__(self):
        self._init_state()
    
    def _init_state(self) -> None:
        """Initialize session state for pending changes"""
        if PENDING_CHANGES_KEY not in st.session_state:
            # Try to restore from persistence
            restored = self._restore_from_persistence()
            st.session_state[PENDING_CHANGES_KEY] = restored if restored else {}
    
    def _restore_from_persistence(self) -> Optional[Dict[str, CANChange]]:
        """Restore pending changes from browser localStorage via query params"""
        try:
            # Check if there's persisted data in query params
            params = st.query_params
            if 'pending_changes' in params:
                json_str = params['pending_changes']
                data = json.loads(json_str)
                
                # Convert dict back to CANChange objects
                changes = {}
                for an, change_dict in data.items():
                    changes[an] = CANChange(**change_dict)
                
                logger.info(f"Restored {len(changes)} pending changes from persistence")
                return changes
        except Exception as e:
            logger.warning(f"Could not restore pending changes: {e}")
        return None
    
    def _persist_changes(self) -> None:
        """Persist pending changes to query params (survives refresh)"""
        try:
            changes = self.get_all_changes()
            if changes:
                # Convert to JSON-serializable format
                data = {}
                for an, change in changes.items():
                    change_dict = asdict(change)
                    # Ensure row_data is serializable
                    change_dict['row_data'] = self._make_serializable(change_dict['row_data'])
                    data[an] = change_dict
                
                json_str = json.dumps(data)
                
                # Only persist if not too large (URL limit ~2000 chars)
                if len(json_str) < 1500:
                    st.query_params['pending_changes'] = json_str
                else:
                    # Too large, remove from query params
                    if 'pending_changes' in st.query_params:
                        del st.query_params['pending_changes']
                    logger.warning("Pending changes too large to persist in URL")
            else:
                # No changes, clear persistence
                if 'pending_changes' in st.query_params:
                    del st.query_params['pending_changes']
        except Exception as e:
            logger.warning(f"Could not persist pending changes: {e}")
    
    def _make_serializable(self, obj: Any) -> Any:
        """Convert object to JSON-serializable format"""
        if isinstance(obj, dict):
            return {k: self._make_serializable(v) for k, v in obj.items()}
        elif isinstance(obj, (list, tuple)):
            return [self._make_serializable(v) for v in obj]
        elif isinstance(obj, (date, datetime)):
            return obj.isoformat()
        elif hasattr(obj, '__dict__'):
            return str(obj)
        else:
            try:
                json.dumps(obj)
                return obj
            except:
                return str(obj)
    
    def stage_change(
        self,
        can_line_id: int,
        arrival_note_number: str,
        original_data: Dict[str, Any],
        new_data: Dict[str, Any],
        reason: str,
        row_data: Dict[str, Any]
    ) -> None:
        """Stage a change for later batch processing"""
        
        change = CANChange(
            can_line_id=can_line_id,
            arrival_note_number=arrival_note_number,
            product_name=row_data.get('product_name', 'N/A'),
            vendor_name=row_data.get('vendor', 'N/A'),
            
            original_arrival_date=self._date_to_str(original_data.get('arrival_date')),
            original_status=original_data.get('status', 'REQUEST_STATUS'),
            original_warehouse_id=original_data.get('warehouse_id', 0),
            original_warehouse_name=original_data.get('warehouse_name', 'N/A'),
            
            new_arrival_date=self._date_to_str(new_data.get('arrival_date')),
            new_status=new_data.get('status', 'REQUEST_STATUS'),
            new_warehouse_id=new_data.get('warehouse_id', 0),
            new_warehouse_name=new_data.get('warehouse_name', 'N/A'),
            
            reason=reason,
            staged_at=datetime.now().isoformat(),
            row_data=self._make_serializable(row_data)
        )
        
        st.session_state[PENDING_CHANGES_KEY][arrival_note_number] = change
        self._persist_changes()
        
        logger.info(f"Staged change for CAN {arrival_note_number}")
    
    def _date_to_str(self, date_val: Any) -> Optional[str]:
        """Convert date to string format"""
        if date_val is None:
            return None
        if isinstance(date_val, str):
            return date_val
        if isinstance(date_val, (date, datetime)):
            return date_val.strftime('%Y-%m-%d')
        return str(date_val)
    
    def remove_change(self, arrival_note_number: str) -> bool:
        """Remove a staged change"""
        if arrival_note_number in st.session_state[PENDING_CHANGES_KEY]:
            del st.session_state[PENDING_CHANGES_KEY][arrival_note_number]
            self._persist_changes()
            logger.info(f"Removed staged change for CAN {arrival_note_number}")
            return True
        return False
    
    def get_change(self, arrival_note_number: str) -> Optional[CANChange]:
        """Get a specific staged change"""
        return st.session_state[PENDING_CHANGES_KEY].get(arrival_note_number)
    
    def get_all_changes(self) -> Dict[str, CANChange]:
        """Get all staged changes"""
        return st.session_state.get(PENDING_CHANGES_KEY, {})
    
    def get_change_count(self) -> int:
        """Get number of pending changes"""
        return len(st.session_state.get(PENDING_CHANGES_KEY, {}))
    
    def has_pending_changes(self) -> bool:
        """Check if there are any pending changes"""
        return self.get_change_count() > 0
    
    def has_change_for(self, arrival_note_number: str) -> bool:
        """Check if a specific CAN has pending changes"""
        return arrival_note_number in st.session_state.get(PENDING_CHANGES_KEY, {})
    
    def clear_all_changes(self) -> None:
        """Clear all pending changes"""
        st.session_state[PENDING_CHANGES_KEY] = {}
        self._persist_changes()
        logger.info("Cleared all pending changes")
    
    def get_changes_by_creator(self, data_service) -> Dict[str, List[CANChange]]:
        """Group changes by creator email for email notifications"""
        changes = self.get_all_changes()
        by_creator: Dict[str, List[CANChange]] = {}
        
        for an, change in changes.items():
            creator_email = data_service.get_creator_email(an)
            if creator_email:
                if creator_email not in by_creator:
                    by_creator[creator_email] = []
                by_creator[creator_email].append(change)
        
        return by_creator


def get_pending_manager() -> PendingChangesManager:
    """Get or create the pending changes manager"""
    if '_pending_manager' not in st.session_state:
        st.session_state._pending_manager = PendingChangesManager()
    return st.session_state._pending_manager
