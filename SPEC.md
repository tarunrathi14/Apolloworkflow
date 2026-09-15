# Design decisions and roadmap

## Decisions taken

| Question | Choice | Why it mattered |
|---|---|---|
| Interface | Telegram bot, behind a `Channel` protocol | Free, no Meta business verification, working in minutes. WhatsApp's 24-hour window rule would have blocked proactive reminders without pre-approved templates — the exact feature you wanted most. The protocol means swapping to WhatsApp later is one new class. |
| Source of truth | Google Calendar | Everything lands on your phone and is visible to anyone who shares your calendar. SQLite holds only what Calendar can't: the task backlog, standalone reminders, pending proposals. |
| Autonomy | Propose, you confirm | Nothing reaches your calendar on a parse alone. A misread time is a message you ignore, not a client meeting that moved. |
| Your rules | Deep-work blocks + real travel time | Both are modelled as first-class conflict types, not soft warnings. |
| Stack | Python + FastAPI, APScheduler, SQLite | Always-on so reminders fire with your laptop shut. SQLite because this is a single-user tool; swapping to Postgres is a connection string. |

## What is built

The full core loop: capture → conflicts → day plan → proposal → confirm → write.

Design choices worth knowing about:

**Movability is inferred, not asked.** An event with other attendees is never
proposed for rescheduling. This one rule is what stops the assistant suggesting
you move a client call around your own admin block.

**Severity means recoverability.** CRITICAL is a day that cannot physically
happen (two immovable events overlapping; a drive that doesn't fit). WARNING is
a day that works but breaks a rule you set. This is what lets the 07:00 brief
lead with the thing that will actually hurt.

**Conflicts have stable fingerprints.** Built from the kind plus the events'
ids and times, so the half-hourly watcher tells you about each problem exactly
once — but tells you again if you move something and it still clashes.

**A fix never creates a new problem.** Proposed moves skip your protected
blocks, so resolving an overlap can't silently create a deep-work violation.

**Buffers and travel are subtracted before tasks are placed.** "Free time" means
time you can actually use, not gaps between calendar entries.

## What is next

You asked for two more things. Both build cleanly on what's here:

### Meeting prep and post-meeting capture

- **Before:** on each calendar event with external attendees, search Gmail and
  Drive for the last thread and any attached doc, and send a short brief 30
  minutes ahead. The Gmail and Drive connectors are already available.
- **After:** pull the Plaud transcript for the meeting's time window, extract
  action items with the same structured-output approach `nlp/extract.py`
  already uses, and drop them into the task backlog tagged with their source.

The extraction schema already carries `source_note` on `Task` for exactly this.

### Task and commitment tracking

- The backlog, priorities and deadlines exist today.
- What's missing is **promise detection**: scanning your sent mail for
  commitments you made ("I'll send that by Friday") and turning them into
  tasks. This is the same extraction pattern pointed at a different input, and
  it is the highest-leverage piece left — it catches the things that get
  dropped precisely because they were never written down.

### Smaller things worth doing

- **Real travel times.** `Profile.travel_minutes` is one function; swapping the
  static matrix for a Maps Distance Matrix call with time-of-day traffic is a
  contained change.
- **Recurring events** are read correctly from Calendar (`singleEvents=True`)
  but the planner treats each instance independently. Fine for now.
- **Multi-day planning.** The planner is per-day; when a task can't fit today it
  is reported rather than rolled forward. Rolling it into tomorrow's plan is a
  natural next step.
- **Inline buttons.** The webhook already handles `callback_query`, so the
  `/yes <id>` commands can become tappable Yes/No buttons.

## Things you should decide as you use it

These didn't need answers to build, but will shape how it feels:

1. **Reminder lead time** is 15 minutes for everything. In-person events
   probably want travel-time-aware leads instead.
2. **The 07:00 brief** may be the wrong hour for you. One line in
   `scheduler.py`.
3. **Task estimates come from Claude's guess.** Once you've used it a while,
   comparing estimates against what actually happened would let it calibrate.
4. **Weekly review** — you didn't pick it for v1. Worth revisiting once there
   is a few weeks of history to review.
