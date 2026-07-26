"""Project-wide timezone configuration.

All datetime operations should use :data:`TZ` (Asia/Shanghai) instead of
bare ``datetime.now()`` to avoid implicit-system-timezone bugs.
"""

from datetime import datetime, timedelta, timezone

# ── Project timezone: Asia / Shanghai (UTC+8) ────────────────────────────
TZ = timezone(timedelta(hours=8))
TZ_NAME = "Asia/Shanghai"
UTC_OFFSET = "+08:00"


def now() -> datetime:
    """Current moment in the project timezone (Asia/Shanghai)."""
    return datetime.now(TZ)


def today() -> str:
    """Today's date string (YYYY-MM-DD) in the project timezone."""
    return now().strftime("%Y-%m-%d")


def today_range() -> tuple[str, str]:
    """(start_of_day, end_of_day) in the project timezone.

    Both values are formatted as ``YYYY-MM-DD HH:MM:SS``.
    """
    t = now()
    return (t.strftime("%Y-%m-%d 00:00:00"), t.strftime("%Y-%m-%d 23:59:59"))


def as_local(dt: datetime) -> datetime:
    """Convert a timezone-aware datetime to the project timezone."""
    if dt.tzinfo is None:
        # Treat naive as UTC (database default)
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(TZ)


def make_aware_naive(dt: datetime) -> datetime:
    """Attach project timezone to a naive datetime."""
    if dt.tzinfo is not None:
        return dt
    return dt.replace(tzinfo=TZ)
