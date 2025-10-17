"""
Helper utility functions for the Stash GraphQL Tagger application.
"""
from typing import Optional


def human_size(num_bytes: Optional[int]) -> str:
    """
    Convert bytes -> human readable string (e.g. '1.23 GB').
    Accepts None -> returns 'Unknown'.
    """
    if num_bytes is None:
        return "Unknown"
    try:
        b = float(num_bytes)
    except Exception:
        return "Unknown"
    if b < 0:
        return "Unknown"
    units = ["B", "KB", "MB", "GB", "TB", "PB"]
    idx = 0
    while b >= 1024 and idx < len(units) - 1:
        b /= 1024.0
        idx += 1
    return f"{b:.2f} {units[idx]}"


def human_duration(seconds: Optional[float]) -> str:
    """
    Convert seconds -> human readable duration (e.g. '1h 23m 45s').
    Accepts None -> returns 'Unknown'.
    """
    if seconds is None:
        return "Unknown"
    try:
        total_secs = int(seconds)
    except Exception:
        return "Unknown"
    if total_secs < 0:
        return "Unknown"
    
    hours = total_secs // 3600
    minutes = (total_secs % 3600) // 60
    secs = total_secs % 60
    
    if hours > 0:
        return f"{hours}h {minutes}m {secs}s"
    elif minutes > 0:
        return f"{minutes}m {secs}s"
    else:
        return f"{secs}s"


def parse_duration_input(duration_str: str) -> Optional[int]:
    """
    Parse duration input string to seconds.
    Accepts formats:
    - Raw seconds: "600" -> 600
    - MM:SS: "10:30" -> 630
    - HH:MM:SS: "1:30:45" -> 5445
    Returns None if invalid.
    """
    if not duration_str or not duration_str.strip():
        return None
    
    duration_str = duration_str.strip()
    
    # Check if it's a raw number (seconds)
    if ':' not in duration_str:
        try:
            return int(float(duration_str))
        except ValueError:
            return None
    
    # Parse time format (MM:SS or HH:MM:SS)
    parts = duration_str.split(':')
    try:
        if len(parts) == 2:
            # MM:SS format
            minutes = int(parts[0])
            seconds = int(parts[1])
            return minutes * 60 + seconds
        elif len(parts) == 3:
            # HH:MM:SS format
            hours = int(parts[0])
            minutes = int(parts[1])
            seconds = int(parts[2])
            return hours * 3600 + minutes * 60 + seconds
        else:
            return None
    except ValueError:
        return None


def parse_filesize_input(size_str: str, unit: str) -> Optional[int]:
    """
    Parse file size input and unit to bytes.
    Args:
        size_str: numeric string (e.g., "100", "1.5")
        unit: "B", "KB", "MB", or "GB"
    Returns:
        Size in bytes as integer, or None if invalid
    """
    if not size_str or not size_str.strip():
        return None
    
    try:
        size_value = float(size_str.strip())
    except ValueError:
        return None
    
    # Convert to bytes based on unit
    multipliers = {
        "B": 1,
        "KB": 1024,
        "MB": 1024 * 1024,
        "GB": 1024 * 1024 * 1024
    }
    
    multiplier = multipliers.get(unit, 1)
    return int(size_value * multiplier)
