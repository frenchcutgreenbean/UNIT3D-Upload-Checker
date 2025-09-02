#!/usr/bin/env python3
from typing import Dict, Optional
from .base import BaseTracker
from .unit3d_api import UNIT3DTracker
from .fenix_api import FenixTracker


def get_tracker_driver(tracker: str, tracker_info: Dict, settings_manager) -> BaseTracker:
    """
    Factory function to get the appropriate tracker driver instance.
    
    Args:
        tracker: Tracker identifier (e.g., 'beyondhd', 'blutopia')
        tracker_info: The tracker's configuration from tracker_info.json
        settings_manager: The settings manager instance
        
    Returns:
        An instance of the appropriate BaseTracker implementation
    """
    # Get the driver type from tracker_info
    driver_type = tracker_info.get('driver', 'UNIT3D').lower()
    
    # Create the appropriate driver instance
    if driver_type.lower() == 'f3nix':
        return FenixTracker(tracker, tracker_info, settings_manager)
    else:  # Default to UNIT3D
        return UNIT3DTracker(tracker, tracker_info, settings_manager)
