"""Source-specific SEC acceptance timestamps; never infer a timezone from ISO text."""
import re
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

EASTERN = ZoneInfo("America/New_York")
UTC = timezone.utc
_SUBMISSIONS = re.compile(
    r"[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}"
    r"(?:\.[0-9]{1,6})?(?:Z|[+-][0-9]{2}(?::?[0-5][0-9])?)"
)


def parse_submissions_acceptance(value):
    """Return UTC for explicit ISO Z/offset text; missing is None, invalid raises.

    Naive clocks and fractions beyond database microsecond precision are rejected
    rather than guessed or truncated. Numeric offsets need not be Eastern.
    """
    if value is None or value == "":
        return None
    if not isinstance(value, str) or not _SUBMISSIONS.fullmatch(value):
        raise ValueError("SEC submissions acceptance requires explicit ISO timezone")
    return datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(UTC)


def parse_header_acceptance(value):
    """Convert compact EDGAR Eastern wall time to UTC; reject DST folds/gaps."""
    if not isinstance(value, str) or not re.fullmatch(r"[0-9]{14}", value):
        raise ValueError("SEC header acceptance requires YYYYMMDDHHMMSS")
    naive = datetime.strptime(value, "%Y%m%d%H%M%S")
    instants = set()
    for fold in (0, 1):
        instant = naive.replace(tzinfo=EASTERN, fold=fold).astimezone(UTC)
        if instant.astimezone(EASTERN).replace(tzinfo=None) == naive:
            instants.add(instant)
    if len(instants) != 1:
        raise ValueError("SEC header acceptance is ambiguous or nonexistent Eastern time")
    return instants.pop()
