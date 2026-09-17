"""
Run this when Patrick tells Claude he's texted Mayte an update.

Marks whatever's currently pending (tagged, unconfirmed) as sent: sets
sentToPatrick on those entries -- so they stop appearing in Patrick's own
future drafts -- and logs the exact message text to history.json. Mayte's
dashboard is untouched by this: her page reads the raw `tag` directly, not
sentToPatrick (see sync_calendars.py's docstring for the full two-stage
lifecycle).

Per Patrick's rule that Mayte should only ever see the LAST communicated
update highlighted, this also immediately settles (see sync_calendars.py's
settle_entry) any OTHER entry that was already sentToPatrick from an
earlier confirmation -- it's been superseded by this newer one, so it's no
longer "the last thing she was told," and its highlight comes down now
rather than waiting for its date to pass.

Usage: python mark_sent.py
Prints the message that was marked as sent, or a note if nothing was
pending. Run from the repo root (schedule.json alongside this file).
"""

import json
from datetime import date as date_cls
from datetime import datetime, timezone

from render_draft import render
from sync_calendars import settle_entry


def main():
    with open("schedule.json") as f:
        data = json.load(f)
    entries = data["entries"]

    pending_ids = {e["id"] for e in entries if e.get("tag") and not e.get("sentToPatrick")}
    if not pending_ids:
        print("Nothing pending -- no unconfirmed tagged entries to mark as sent.")
        return

    message = render(entries)  # capture the exact text before mutating anything

    for e in list(entries):
        if e["id"] in pending_ids:
            e["sentToPatrick"] = True
        elif e.get("kind") == "turnover" and e.get("tag") and e.get("sentToPatrick"):
            settle_entry(e, entries)

    today = date_cls.today()
    data["entries"] = entries
    data["updatedAt"] = f"{today.isoformat()}T00:00:00Z"
    with open("schedule.json", "w") as f:
        json.dump(data, f, indent=2)
        f.write("\n")

    try:
        with open("history.json") as f:
            history = json.load(f)
    except FileNotFoundError:
        history = {"sent": []}
    sent_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    history["sent"].append({"sentAt": sent_at, "text": message})
    with open("history.json", "w") as f:
        json.dump(history, f, indent=2)
        f.write("\n")

    print(message)


if __name__ == "__main__":
    import sys
    if sys.stdout.encoding and sys.stdout.encoding.lower() != "utf-8":
        sys.stdout.reconfigure(encoding="utf-8")
    main()
