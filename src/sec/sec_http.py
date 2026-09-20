"""Small sequential SEC JSON request boundary shared by the two data clients."""
import time
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime

import requests

from src.sec.sec_client import SEC_HEADERS
from src.sec import production_report as reporting

MIN_REQUEST_INTERVAL = 0.25
MAX_ATTEMPTS = 3
MAX_RETRY_WAIT = 30
_last_request_at = None
_blocked_until = 0.0


def _pace():
    global _last_request_at
    now = time.monotonic()
    cooldown = _blocked_until - now
    if cooldown > MAX_RETRY_WAIT:
        raise requests.HTTPError("SEC shared cooldown exceeds bounded wait")
    if cooldown > 0:
        time.sleep(cooldown)
        now = time.monotonic()
    if _last_request_at is not None:
        wait = MIN_REQUEST_INTERVAL - (now - _last_request_at)
        if wait > 0:
            time.sleep(wait)
    _last_request_at = time.monotonic()


def _retry_wait(response, attempt):
    delay = float(2 ** attempt)
    value = response.headers.get("Retry-After") if response is not None else None
    if value:
        try:
            requested = float(value)
        except ValueError:
            try:
                requested = (parsedate_to_datetime(value) - datetime.now(timezone.utc)).total_seconds()
            except (ValueError, TypeError, OverflowError):
                requested = 0
        delay = max(delay, requested)
    global _blocked_until
    if value:
        _blocked_until = max(_blocked_until, time.monotonic() + delay)
    # Fail rather than retry earlier than a long server-requested cooldown.
    return delay if delay <= MAX_RETRY_WAIT else None


def get_sec_json(url):
    """No stale-cache fallback. Retry only transient HTTP/network failures."""
    for attempt in range(MAX_ATTEMPTS):
        _pace()
        response = None
        try:
            reporting.add("http_requests")
            if attempt:
                reporting.add("retries")
            response = requests.get(url, headers=SEC_HEADERS, timeout=60)
            if response.status_code == 429:
                reporting.add("responses_429")
            elif 500 <= response.status_code <= 599:
                reporting.add("responses_5xx")
            response.raise_for_status()
            reporting.add("successful_requests")
        except (requests.Timeout, requests.ConnectionError, requests.HTTPError) as error:
            if not isinstance(error, requests.HTTPError):
                reporting.add("network_failures")
            delay = _retry_wait(response, attempt)
            if isinstance(error, requests.HTTPError):
                status = response.status_code
                if status != 429 and not 500 <= status <= 599:
                    response.close()
                    raise
            if response is not None:
                response.close()
            if attempt == MAX_ATTEMPTS - 1 or delay is None:
                raise
            time.sleep(delay)
        else:
            try:
                return response.json()
            finally:
                response.close()
