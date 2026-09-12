"""
Timezone utilities for the News Intelligence Agent.

All internal timestamps are stored in UTC.
Display timestamps are converted to user's local timezone (PKT).
"""

from datetime import datetime, timezone, timedelta
from config.settings import USER_TIMEZONE


# Pakistan Standard Time offset (UTC+5)
_PKT_OFFSET = timedelta(hours=5)
_PKT_TZ = timezone(_PKT_OFFSET)


def now_utc() -> datetime:
    """Get current time in UTC."""
    return datetime.now(timezone.utc)


def now_utc_iso() -> str:
    """Get current UTC time as ISO 8601 string."""
    return datetime.now(timezone.utc).isoformat()


def now_local() -> datetime:
    """Get current time in user's local timezone (PKT)."""
    return datetime.now(_PKT_TZ)


def now_local_formatted() -> str:
    """Get current local time as a human-readable string.

    Returns:
        e.g., 'September 9, 2026 — 2:48 AM PKT'
    """
    local = now_local()
    return local.strftime("%B %d, %Y — %I:%M %p PKT")


def utc_to_local(utc_dt: datetime) -> datetime:
    """Convert a UTC datetime to user's local timezone."""
    if utc_dt.tzinfo is None:
        utc_dt = utc_dt.replace(tzinfo=timezone.utc)
    return utc_dt.astimezone(_PKT_TZ)


def utc_to_local_str(utc_dt: datetime) -> str:
    """Convert UTC datetime to local formatted string."""
    local = utc_to_local(utc_dt)
    return local.strftime("%B %d, %Y — %I:%M %p PKT")


def parse_to_utc(date_string: str) -> datetime:
    """Parse a date string from any common format into UTC datetime.

    Handles:
    - ISO 8601 (2026-09-09T12:00:00Z)
    - RFC 2822 (Mon, 09 Sep 2026 12:00:00 +0000) — common in RSS
    - Various other formats

    Args:
        date_string: Raw date string from an article source.

    Returns:
        UTC datetime. Falls back to current UTC time if parsing fails.
    """
    if not date_string:
        return now_utc()

    # Try standard ISO format first
    for fmt in [
        "%Y-%m-%dT%H:%M:%SZ",
        "%Y-%m-%dT%H:%M:%S%z",
        "%Y-%m-%dT%H:%M:%S.%fZ",
        "%Y-%m-%dT%H:%M:%S.%f%z",
        "%Y-%m-%d %H:%M:%S",
        "%a, %d %b %Y %H:%M:%S %z",       # RFC 2822 with timezone
        "%a, %d %b %Y %H:%M:%S %Z",       # RFC 2822 with tz name
        "%a, %d %b %Y %H:%M:%S",          # RFC 2822 no timezone
        "%d %b %Y %H:%M:%S %z",
        "%Y-%m-%d",
    ]:
        try:
            dt = datetime.strptime(date_string.strip(), fmt)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt.astimezone(timezone.utc)
        except ValueError:
            continue

    # Last resort: try dateutil-style parsing
    try:
        # Handle common RSS date quirks
        cleaned = date_string.strip()
        # Remove day name prefix if present (e.g., "Mon, ")
        if "," in cleaned:
            cleaned = cleaned.split(",", 1)[1].strip()
        dt = datetime.strptime(cleaned, "%d %b %Y %H:%M:%S %z")
        return dt.astimezone(timezone.utc)
    except (ValueError, IndexError):
        pass

    # Fallback: return current time
    return now_utc()


def hours_ago(hours: int) -> datetime:
    """Get UTC datetime for N hours ago.

    Used for time-range queries like 'top 5 from last 6 hours'.
    """
    return now_utc() - timedelta(hours=hours)


def minutes_since(dt: datetime) -> float:
    """Calculate minutes elapsed since a given UTC datetime."""
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    delta = now_utc() - dt
    return delta.total_seconds() / 60


def hours_since(dt: datetime) -> float:
    """Calculate hours elapsed since a given UTC datetime."""
    return minutes_since(dt) / 60


def format_relative_time(dt: datetime) -> str:
    """Format a datetime as relative time string.

    Returns:
        e.g., '3 minutes ago', '2 hours ago', '1 day ago'
    """
    mins = minutes_since(dt)

    if mins < 1:
        return "just now"
    elif mins < 60:
        return f"{int(mins)} minute{'s' if int(mins) != 1 else ''} ago"
    elif mins < 1440:  # 24 hours
        hours = int(mins / 60)
        return f"{hours} hour{'s' if hours != 1 else ''} ago"
    else:
        days = int(mins / 1440)
        return f"{days} day{'s' if days != 1 else ''} ago"
