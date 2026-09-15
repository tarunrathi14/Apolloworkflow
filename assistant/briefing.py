"""Rendering a plan as something readable on a phone.

Telegram renders a useful subset of HTML, which survives odd characters in
meeting titles better than Markdown does.
"""

from __future__ import annotations

import html
from datetime import datetime

from .models import Conflict, DayPlan, Severity
from .proposals import Proposal

_ICON = {
    "event": "📅",
    "task": "✍️",
    "travel": "🚗",
    "deep_work": "🧠",
}
_SEVERITY_ICON = {
    Severity.CRITICAL: "🔴",
    Severity.WARNING: "🟡",
    Severity.INFO: "🔵",
}


def _t(dt: datetime) -> str:
    return dt.strftime("%H:%M")


def _e(text: str) -> str:
    return html.escape(text, quote=False)


def render_conflicts(conflicts: list[Conflict]) -> str:
    if not conflicts:
        return "✅ No clashes."
    lines = [f"<b>{len(conflicts)} thing(s) to look at</b>"]
    for c in conflicts:
        lines.append(f"{_SEVERITY_ICON[c.severity]} {_e(c.message)}")
    return "\n".join(lines)


def render_proposals(proposals: list[Proposal]) -> str:
    if not proposals:
        return ""
    lines = ["", "<b>Suggested fixes</b>"]
    for p in proposals:
        if p.action.get("op") == "none":
            # Nothing to accept — give the options instead of a dead button.
            lines.append(f"• {_e(p.summary)}")
            if p.alternatives:
                lines.append("  " + " · ".join(_e(a) for a in p.alternatives[:3]))
        else:
            lines.append(f"• {_e(p.summary)}  <code>/yes {p.id}</code>")
    return "\n".join(lines)


def render_day(plan: DayPlan, greeting: str | None = None) -> str:
    """The daily brief: what is happening, what is wrong, what did not fit."""
    lines: list[str] = []
    header = greeting or f"<b>{plan.date:%A %d %B}</b>"
    lines.append(header)

    # A protected block on its own is not a commitment — the day is still free.
    committed = [i for i in plan.items if i.kind != "deep_work"]
    if not committed:
        lines.append("\nNothing scheduled. The whole day is yours.")
    else:
        lines.append("")
        for item in plan.items:
            icon = _ICON.get(item.kind, "•")
            row = f"{icon} <b>{_t(item.start)}–{_t(item.end)}</b>  {_e(item.title)}"
            if item.note:
                row += f"  <i>({_e(item.note)})</i>"
            lines.append(row)

    hours, minutes = divmod(plan.free_minutes, 60)
    lines.append(f"\n<i>{hours}h {minutes:02d}m unbooked.</i>")

    if plan.conflicts:
        lines.append("")
        lines.append(render_conflicts(plan.conflicts))

    if plan.unplaced:
        lines.append("")
        lines.append("<b>Did not fit today</b>")
        for task, why in plan.unplaced:
            lines.append(f"• {_e(task.title)} — <i>{_e(why)}</i>")

    return "\n".join(lines)


def render_capture(events, tasks, reminders, clarification: str | None = None) -> str:
    """Confirmation of what the assistant understood from your message."""
    if not (events or tasks or reminders):
        return clarification or "I could not find anything schedulable in that."

    lines = ["<b>Got it</b>"]
    for e in events:
        loc = f" at {_e(e.location)}" if e.location else ""
        lines.append(f"📅 {_e(e.title)} — {e.start:%a %d %b} {_t(e.start)}–{_t(e.end)}{loc}")
    for t in tasks:
        due = f", due {t.due:%a %d %b}" if t.due else ""
        lines.append(f"✍️ {_e(t.title)} — {t.estimate_minutes}m, {t.energy.value}{due}")
    for r in reminders:
        lines.append(f"⏰ {_e(r.title)} — {r.remind_at:%a %d %b} {_t(r.remind_at)}")

    if clarification:
        lines.append(f"\n❓ {_e(clarification)}")
    return "\n".join(lines)
