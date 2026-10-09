"""Decide whether today is an office day, from a Home Assistant calendar.

Looks at today's events on HA_CALENDAR (default calendar.master_calendar) and
reads each event's description: "office" means run, "WFH" means skip. Used by
publish.sh to only publish on office mornings.

Exit codes (publish.sh keys off these):
  0   office day: run the pipeline
  10  WFH day: skip
  11  no office/WFH event today: skip
  1   lookup failed or the calendar contradicts itself: skip and alert

Reads HA_URL and HA_TOKEN (a long-lived access token) from the environment.
"""
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta

OFFICE, WFH, NO_EVENT, FAILED = 0, 10, 11, 1


def main() -> int:
    base = os.environ.get("HA_URL", "").rstrip("/")
    token = os.environ.get("HA_TOKEN", "")
    calendar = os.environ.get("HA_CALENDAR", "calendar.master_calendar")
    if not base or not token:
        print("Office check: HA_URL and HA_TOKEN must both be set in .env", file=sys.stderr)
        return FAILED

    # Today in the machine's local timezone (the Mac runs on ET).
    start = datetime.now().astimezone().replace(hour=0, minute=0, second=0, microsecond=0)
    end = start + timedelta(days=1)
    query = urllib.parse.urlencode({"start": start.isoformat(), "end": end.isoformat()})
    request = urllib.request.Request(
        f"{base}/api/calendars/{calendar}?{query}",
        headers={"Authorization": f"Bearer {token}"},
    )
    try:
        with urllib.request.urlopen(request, timeout=15) as response:
            events = json.load(response)
    except (urllib.error.URLError, TimeoutError, ValueError) as exc:
        print(f"Office check: Home Assistant lookup failed ({exc})", file=sys.stderr)
        return FAILED

    descriptions = [(e.get("description") or "").lower() for e in events]
    office = any("office" in d for d in descriptions)
    wfh = any("wfh" in d for d in descriptions)

    if office and wfh:
        print("Office check: today has both an office and a WFH event", file=sys.stderr)
        return FAILED
    if office:
        print(f"Office check: {start.date()} is an office day")
        return OFFICE
    if wfh:
        print(f"Office check: {start.date()} is a WFH day, skipping the episode")
        return WFH
    print(f"Office check: no office/WFH event on {start.date()}, skipping the episode")
    return NO_EVENT


if __name__ == "__main__":
    sys.exit(main())
