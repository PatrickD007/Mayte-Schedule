"""
Generates the text message sent to Mayte summarizing upcoming room
changeovers, general cleanings (GC), and her days off.

Ground truth for format: sample_message.txt (Patrick's real message format).
Decisions this implements (see PROJECT_PLAN.md):
- Full list every time, sorted chronologically by date.
- Changed lines get a plain-text tag: (NEW), (UPDATE), (CANCELLED).
- (UPDATE) shows old date struck through -> new date, using a universal
  Unicode strikethrough (renders identically on iPhone and Android, unlike
  iMessage-style rich text formatting).
- (CANCELLED) strikes through the whole line.
- The date on every line is the day Mayte's team must be on site
  (checkout/turnover day or GC day), never check-in day.
"""

from dataclasses import dataclass
from datetime import date
from typing import Optional

STRIKE = "̶"  # combining long stroke overlay


def strike(text: str) -> str:
    return "".join(ch + STRIKE for ch in text)


def fmt_date(d: date) -> str:
    return f"{d.month}/{d.day}"


@dataclass
class Entry:
    date: date
    kind: str  # "turnover" | "gc" | "off"
    room: Optional[str] = None  # "1" | "2" | "4", required for "turnover"
    tag: Optional[str] = None  # None | "new" | "update" | "cancelled"
    old_date: Optional[date] = None  # required when tag == "update"

    def label(self) -> str:
        if self.kind == "off":
            return "Mayte Off"
        if self.kind == "gc":
            return "GC"
        return f"#{self.room}"

    def render(self) -> str:
        date_str = fmt_date(self.date)
        line = f"{date_str} {self.label()}"

        if self.tag == "update":
            if not self.old_date:
                raise ValueError("update entries require old_date")
            line = f"{strike(fmt_date(self.old_date))} → {date_str} {self.label()}"
        elif self.tag == "cancelled":
            line = strike(line)

        if self.tag:
            line = f"{line} ({self.tag.upper()})"

        return f"- {line}"

    def sort_key(self):
        return self.date


def room_word(e: Entry) -> str:
    if e.kind == "gc":
        return "General Cleaning"
    if e.kind == "off":
        return "your schedule"
    return f"#{e.room}"


def generate_headline(entries: list[Entry]) -> str:
    changed = [e for e in entries if e.tag]
    if not changed:
        return "Hi Mayte! Here's the schedule:"

    if len(changed) == 1:
        e = changed[0]
        if e.tag == "cancelled":
            return f"Hi Mayte! {room_word(e)}'s reservation was cancelled:"
        if e.tag == "new":
            return (
                f"Hi Mayte! A new reservation for {room_word(e)}:"
                if e.kind == "turnover"
                else f"Hi Mayte! A note about {room_word(e)}:"
            )
        if e.tag == "update" and e.old_date:
            verb = "extended" if e.date > e.old_date else "shortened"
            return f"Hi Mayte! {room_word(e)} {verb} their reservation:"
        return f"Hi Mayte! An update to {room_word(e)}:"

    rooms = sorted({f"#{e.room}" for e in changed if e.kind == "turnover"})
    if len(rooms) == 1:
        return f"Hi Mayte! A few updates to {rooms[0]}:"
    if len(rooms) > 1:
        return f"Hi Mayte! Updates to {', '.join(rooms[:-1])} and {rooms[-1]}:"
    return "Hi Mayte! A few schedule updates:"


def generate_message(entries: list[Entry], dashboard_url: str) -> str:
    ordered = sorted(entries, key=Entry.sort_key)
    lines = [e.render() for e in ordered]
    body = "\n".join(lines)
    return (
        f"{generate_headline(entries)}\n\n"
        "So we have:\n"
        f"{body}\n\n"
        f"Full schedule: {dashboard_url}"
    )


if __name__ == "__main__":
    import sys
    sys.stdout.reconfigure(encoding="utf-8")

    # 1. Fidelity check against the original sample format (no tags).
    baseline = [
        Entry(date(2026, 9, 4), "turnover", room="1"),
        Entry(date(2026, 9, 7), "turnover", room="1"),
        Entry(date(2026, 9, 15), "turnover", room="1"),
        Entry(date(2026, 9, 9), "turnover", room="2"),
        Entry(date(2026, 9, 13), "turnover", room="2"),
        Entry(date(2026, 9, 16), "gc"),
        Entry(date(2026, 9, 30), "gc"),
        Entry(date(2026, 10, 14), "gc"),
        Entry(date(2026, 10, 19), "turnover", room="2"),
        Entry(date(2026, 10, 28), "gc"),
    ]
    print("=== Baseline (matches sample_message.txt) ===")
    print(generate_message(baseline, "https://claude.ai/mayte-schedule-placeholder"))

    # 2. Every tag type exercised.
    print("\n=== With NEW / UPDATE / CANCELLED / Mayte Off ===")
    demo = baseline + [
        Entry(date(2026, 10, 21), "turnover", room="4", tag="new"),
        Entry(date(2026, 9, 17), "turnover", room="1", tag="update", old_date=date(2026, 9, 15)),
        Entry(date(2026, 9, 13), "turnover", room="2", tag="cancelled"),
        Entry(date(2026, 11, 1), "off", tag=None),
    ]
    # remove the un-tagged originals that the update/cancel replace
    demo = [e for e in demo if not (e.date == date(2026, 9, 15) and e.room == "1" and e.tag is None)]
    demo = [e for e in demo if not (e.date == date(2026, 9, 13) and e.room == "2" and e.tag is None)]
    print(generate_message(demo, "https://claude.ai/mayte-schedule-placeholder"))
