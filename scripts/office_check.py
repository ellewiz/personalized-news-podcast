"""Decide whether today is an office day, from Home Assistant calendars.

Two gates, in order:
  1. HA_WORKDAY_CALENDAR (default calendar.workday_calendar) must have an event
     today. It is the workday integration's calendar, so weekends and holidays
     have none. No event means stop, without looking at the second calendar.
  2. HA_CALENDAR (default calendar.master_calendar) is then read for the day's
     events: "office" in a description means run, "WFH" means skip.
Used by publish.sh to only publish on office mornings.

Exit codes (publish.sh keys off these):
  0   office day: run the pipeline
  10  WFH day: skip
  11  no office/WFH event today: skip
  12  not a workday (weekend or holiday): skip
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

OFFICE, WFH, NO_EVENT, NOT_WORKDAY, FAILED = 0, 10, 11, 12, 1


class HALookupError(Exception):
    pass


def fetch_events(base: str, token: str, calendar: str, start: datetime, end: datetime) -> list:
    query = urllib.parse.urlencode({"start": start.isoformat(), "end": end.isoformat()})
    request = urllib.request.Request(
        f"{base}/api/calendars/{calendar}?{query}",
        headers={"Authorization": f"Bearer {token}"},
    )
    try:
        with urllib.request.urlopen(request, timeout=15) as response:
            return json.load(response)
    except (urllib.error.URLError, TimeoutError, ValueError) as exc:
        raise HALookupError(f"Home Assistant lookup of {calendar} failed ({exc})") from exc


def main() -> int:
    base = os.environ.get("HA_URL", "").rstrip("/")
    token = os.environ.get("HA_TOKEN", "")
    calendar = os.environ.get("HA_CALENDAR", "calendar.master_calendar")
    workday_calendar = os.environ.get("HA_WORKDAY_CALENDAR", "calendar.workday_calendar")
    if not base or not token:
        print("Office check: HA_URL and HA_TOKEN must both be set in .env", file=sys.stderr)
        return FAILED

    # Today in the machine's local timezone (the Mac runs on ET).
    start = datetime.now().astimezone().replace(hour=0, minute=0, second=0, microsecond=0)
    end = start + timedelta(days=1)

    try:
        if not fetch_events(base, token, workday_calendar, start, end):
            print(f"Office check: {start.date()} is not a workday, skipping the episode")
            return NOT_WORKDAY
        events = fetch_events(base, token, calendar, start, end)
    except HALookupError as exc:
        print(f"Office check: {exc}", file=sys.stderr)
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
