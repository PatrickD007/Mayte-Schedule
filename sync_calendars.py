"""
Pulls the 3 Airbnb calendar (iCal) feeds, diffs them against schedule.json,
and updates schedule.json with any new/moved/cancelled turnovers. Also
ensures General Cleaning (GC) entries exist on their fixed 14-day rule.

Usage: python sync_calendars.py <room1_ical_url> <room2_ical_url> <room4_ical_url>
Exit code 0 with "CHANGED" on the last stdout line if schedule.json was modified,
"UNCHANGED" otherwise. Run from the repo root (schedule.json alongside this file).

Rules (see PROJECT_PLAN.md for full context):
- The date on a turnover entry is the checkout day (DTEND of a "Reserved" VEVENT)
  -- the day Mayte's team must be on site. Only SUMMARY:Reserved events count;
  "Airbnb (Not available)" blocks are host-side and not real bookings.
- A UID newly seen -> add as tag "new".
- A UID's checkout date changes:
    - if it's already tagged "new" or "update", just move its date (Mayte hasn't
      been told any version of it yet, or oldDate is already anchored correctly)
    - otherwise (already-sent baseline) -> tag "update", oldDate = previous date
- A previously-seen UID disappears from the feed:
    - if its checkout date has already passed -> delete outright; Airbnb's feed
      naturally drops completed stays, this isn't a real cancellation
    - if it was tagged "new" (never sent) -> delete outright, nothing to tell Mayte
    - otherwise -> tag "cancelled" (kept so it shows once in the next draft)
- GC entries are generated on a fixed 14-day cadence anchored at 2026-09-16,
  untagged (not "news"), extended automatically ~2 months ahead of today.
"""

import json
import re
import subprocess
import sys
from datetime import date, timedelta

GC_ANCHOR = date(2026, 9, 16)
GC_INTERVAL_DAYS = 14
GC_HORIZON_DAYS = 75  # keep GC entries populated roughly this far ahead

ROOMS = ["1", "2", "4"]


def fmt(iso: str) -> str:
    y, m, d = iso.split("-")
    return f"{int(m)}/{int(d)}"


def fetch(url: str) -> str:
    # Uses curl (not urllib) because some sandboxed environments enforce an
    # outbound network policy via proxy env vars that urllib doesn't pick up
    # the same way curl does.
    result = subprocess.run(
        ["curl", "-s", "--fail", "--max-time", "20", url],
        capture_output=True, text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(f"fetch failed for {url}: curl exit {result.returncode}: {result.stderr.strip()}")
    return result.stdout


def parse_vevents(ics_text: str):
    events = []
    for block in ics_text.split("BEGIN:VEVENT")[1:]:
        block = block.split("END:VEVENT")[0]

        def field(name):
            m = re.search(rf"^{name}(?:;[^:\n]*)?:(.+)$", block, re.MULTILINE)
            return m.group(1).strip() if m else None

        summary = field("SUMMARY")
        uid = field("UID")
        dtstart = field("DTSTART")
        dtend = field("DTEND")
        if not (summary and uid and dtstart and dtend) or summary != "Reserved":
            continue

        def to_iso(raw):
            return date(int(raw[:4]), int(raw[4:6]), int(raw[6:8])).isoformat()

        events.append({"uid": uid, "checkin": to_iso(dtstart), "checkout": to_iso(dtend)})
    return events


def ensure_gc_entries(entries: list[dict], today: date):
    existing_dates = {e["date"] for e in entries if e["kind"] == "gc"}
    d = GC_ANCHOR
    horizon = today + timedelta(days=GC_HORIZON_DAYS)
    changed = False
    while d <= horizon:
        iso = d.isoformat()
        if d >= today - timedelta(days=1) and iso not in existing_dates:
            entries.append({
                "id": f"{iso}-gc", "date": iso, "kind": "gc", "room": None,
                "tag": None, "oldDate": None, "icalUid": None,
            })
            changed = True
        d += timedelta(days=GC_INTERVAL_DAYS)
    return changed


def sync_room(entries: list[dict], room: str, feed_events: list[dict], notes: list[str], today: date) -> bool:
    changed = False
    seen_uids = {e["uid"] for e in feed_events}
    by_uid = {e.get("icalUid"): e for e in entries if e.get("icalUid") and e["room"] == room}

    for fe in feed_events:
        existing = by_uid.get(fe["uid"])
        if existing is None:
            entries.append({
                "id": f"{fe['checkout']}-r{room}-{fe['uid'][:8]}", "date": fe["checkout"],
                "checkIn": fe["checkin"],
                "kind": "turnover", "room": room, "tag": "new", "oldDate": None,
                "icalUid": fe["uid"],
            })
            changed = True
            notes.append(f"Room {room}: new booking, checkout {fmt(fe['checkout'])}")
            continue

        if existing.get("checkIn") != fe["checkin"]:
            # Check-in shifting alone doesn't affect Mayte's cleaning schedule,
            # so it's not NOTE-worthy -- just keep the calendar view accurate.
            existing["checkIn"] = fe["checkin"]
            changed = True

        if existing["date"] != fe["checkout"]:
            if existing["tag"] in ("new", "update"):
                existing["date"] = fe["checkout"]
            else:
                existing["oldDate"] = existing["date"]
                existing["date"] = fe["checkout"]
                existing["tag"] = "update"
            changed = True
            notes.append(f"Room {room}: checkout moved to {fmt(fe['checkout'])}")

    for e in list(entries):
        if e["room"] != room or e["kind"] != "turnover" or not e.get("icalUid"):
            continue
        if e["icalUid"] in seen_uids:
            continue
        if e["date"] < today.isoformat():
            # Checkout day already passed -- Airbnb's own feed drops completed
            # stays on its own, so a disappearance here isn't a real cancellation.
            entries.remove(e)
            changed = True
            continue
        if e["tag"] == "new":
            entries.remove(e)
            changed = True
        elif e["tag"] != "cancelled":
            e["tag"] = "cancelled"
            changed = True
            notes.append(f"Room {room}: cancelled (was {fmt(e['date'])})")

    return changed


def main():
    urls = sys.argv[1:4]
    if len(urls) != 3:
        print("Usage: sync_calendars.py <room1_url> <room2_url> <room4_url>", file=sys.stderr)
        sys.exit(1)

    with open("schedule.json") as f:
        data = json.load(f)
    entries = data["entries"]

    changed = False
    notes: list[str] = []
    today = date.today()
    for room, url in zip(ROOMS, urls):
        events = parse_vevents(fetch(url))
        if sync_room(entries, room, events, notes, today):
            changed = True
    if ensure_gc_entries(entries, today):
        changed = True

    if changed:
        data["entries"] = entries
        data["updatedAt"] = f"{today.isoformat()}T00:00:00Z"
        with open("schedule.json", "w") as f:
            json.dump(data, f, indent=2)
            f.write("\n")

    for note in notes:
        print("NOTE: " + note)
    print("CHANGED" if changed else "UNCHANGED")


if __name__ == "__main__":
    main()
