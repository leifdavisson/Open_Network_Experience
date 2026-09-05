from datetime import datetime, timezone
from typing import Optional, List, Dict, Any

def parse_iso_timestamp(ts_str: Optional[str]) -> Optional[int]:
    """Parses ISO8601 datetime string to UTC epoch timestamp."""
    if not ts_str or ts_str.startswith("0001-01-01"):
        return None
    try:
        dt = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
        return int(dt.timestamp())
    except Exception:
        return None

def format_timestamp_hm(t_val: int) -> str:
    """Formats an epoch timestamp to HH:MM:SS."""
    return datetime.fromtimestamp(t_val, timezone.utc).strftime("%H:%M:%S") if t_val > 0 else "Never"

def paginate(items: List[Any], skip: int = 0, limit: int = 100) -> Dict[str, Any]:
    """Helper for pagination responses."""
    total = len(items)
    paginated = items[skip : skip + limit]
    return {
        "items": paginated,
        "total": total,
        "skip": skip,
        "limit": limit
    }
