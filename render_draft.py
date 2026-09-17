"""
Renders the current schedule.json as the full Mayte-style draft message,
using the same logic as message_generator.py / console.html's JS. Used by
the GitHub Actions workflow to put the complete draft in the ntfy
notification body, so tapping it (no click URL set) copies the whole
message to the clipboard.

An entry's `tag` alone drives Mayte's own dashboard and isn't cleared when
Patrick confirms he's texted her (see sync_calendars.py's docstring) -- so
for THIS message, an entry already marked sentToPatrick is treated as
untagged, even though its raw tag in schedule.json is left alone.

Usage: python render_draft.py
Prints the full message to stdout if there's at least one pending
(tagged, unconfirmed) entry; prints nothing and exits 0 otherwise.
"""

import json
from datetime import date as date_cls

from message_generator import Entry, generate_message

MAYTE_URL = "https://patrickd007.github.io/Mayte-Schedule/"


def _parse_date(iso: str) -> date_cls:
    y, m, d = map(int, iso.split("-"))
    return date_cls(y, m, d)


def load_entries() -> list[Entry]:
    with open("schedule.json") as f:
        data = json.load(f)
    entries = []
    for e in data["entries"]:
        confirmed = e.get("sentToPatrick")
        entries.append(Entry(
            date=_parse_date(e["date"]),
            kind=e["kind"],
            room=e.get("room"),
            tag=None if confirmed else e.get("tag"),
            old_date=_parse_date(e["oldDate"]) if e.get("oldDate") and not confirmed else None,
        ))
    return entries


def main():
    entries = load_entries()
    today = date_cls.today()
    # schedule.json also keeps completed turnovers around (as history for the
    # room calendars) -- exclude those from the actual message the same way
    # index.html's "Upcoming" list does: a real cancellation still shows once
    # even if its date has passed, everything else has to still be upcoming.
    upcoming = [e for e in entries if e.date >= today or e.tag == "cancelled"]
    if not any(e.tag for e in upcoming):
        return
    print(generate_message(upcoming, MAYTE_URL))


if __name__ == "__main__":
    import sys
    if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
        sys.stdout.reconfigure(encoding="utf-8")
    main()
