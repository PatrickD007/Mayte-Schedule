"""
Read-only companion to sync_calendars.py, meant for the hourly cloud routine.
Fetches the LIVE published schedule.json (public GitHub Pages URL) instead of
a local file, compares it to the 3 real calendar feeds, and just prints what
changed -- it never writes anything anywhere. Applying a detected change is a
separate step (Patrick asks Claude to run sync_calendars.py and push).

Usage: python check_calendars.py <room1_ical_url> <room2_ical_url> <room4_ical_url>
Prints one "NOTE: ..." line per real change found, then a final line:
"CHANGED" or "UNCHANGED". Exit code is always 0.
"""

import json
import sys

sys.path.insert(0, ".")
from sync_calendars import ROOMS, fetch, parse_vevents, sync_room  # noqa: E402

SCHEDULE_URL = "https://raw.githubusercontent.com/PatrickD007/Mayte-Schedule/main/schedule.json"


def main():
    urls = sys.argv[1:4]
    if len(urls) != 3:
        print("Usage: check_calendars.py <room1_url> <room2_url> <room4_url>", file=sys.stderr)
        sys.exit(1)

    data = json.loads(fetch(SCHEDULE_URL))
    entries = data["entries"]

    changed = False
    notes: list[str] = []
    for room, url in zip(ROOMS, urls):
        events = parse_vevents(fetch(url))
        if sync_room(entries, room, events, notes):
            changed = True

    for note in notes:
        print("NOTE: " + note)
    print("CHANGED" if changed else "UNCHANGED")


if __name__ == "__main__":
    main()
