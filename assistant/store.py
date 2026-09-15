"""SQLite persistence.

Deliberately small: the calendar is the source of truth for events, so this
stores only what Google Calendar cannot — your task backlog, standalone
reminders, and proposals awaiting a yes.
"""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime
from pathlib import Path

from .config import Profile
from .models import Energy, Event, Reminder, Task, TaskStatus

SCHEMA = """
CREATE TABLE IF NOT EXISTS tasks (
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    estimate_minutes INTEGER NOT NULL DEFAULT 30,
    due TEXT,
    priority INTEGER NOT NULL DEFAULT 2,
    energy TEXT NOT NULL DEFAULT 'shallow',
    status TEXT NOT NULL DEFAULT 'open',
    source_note TEXT,
    created_at TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS reminders (
    id TEXT PRIMARY KEY,
    title TEXT NOT NULL,
    remind_at TEXT NOT NULL,
    event_id TEXT,
    task_id TEXT,
    sent INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS proposals (
    id TEXT PRIMARY KEY,
    summary TEXT NOT NULL,
    action TEXT NOT NULL,
    created_at TEXT NOT NULL,
    resolved TEXT
);
CREATE TABLE IF NOT EXISTS seen_conflicts (
    fingerprint TEXT PRIMARY KEY,
    seen_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_reminders_due ON reminders(remind_at, sent);
CREATE INDEX IF NOT EXISTS idx_tasks_status ON tasks(status);
"""


class Store:
    def __init__(self, path: str = "assistant.db"):
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self.conn.executescript(SCHEMA)
        self.conn.commit()

    # --- tasks ---------------------------------------------------------

    def add_task(self, task: Task) -> None:
        self.conn.execute(
            "INSERT OR REPLACE INTO tasks "
            "(id,title,estimate_minutes,due,priority,energy,status,source_note,created_at)"
            " VALUES (?,?,?,?,?,?,?,?,?)",
            (task.id, task.title, task.estimate_minutes,
             task.due.isoformat() if task.due else None,
             task.priority, task.energy.value, task.status.value,
             task.source_note, datetime.now().isoformat()),
        )
        self.conn.commit()

    def open_tasks(self, profile: Profile) -> list[Task]:
        rows = self.conn.execute(
            "SELECT * FROM tasks WHERE status='open' ORDER BY priority, due"
        ).fetchall()
        return [
            Task(
                id=r["id"], title=r["title"],
                estimate_minutes=r["estimate_minutes"],
                due=profile.localize(datetime.fromisoformat(r["due"])) if r["due"] else None,
                priority=r["priority"], energy=Energy(r["energy"]),
                status=TaskStatus(r["status"]), source_note=r["source_note"],
            )
            for r in rows
        ]

    def complete_task(self, task_id: str) -> bool:
        cur = self.conn.execute(
            "UPDATE tasks SET status='done' WHERE id=? AND status='open'", (task_id,)
        )
        self.conn.commit()
        return cur.rowcount > 0

    # --- reminders -----------------------------------------------------

    def add_reminder(self, reminder: Reminder) -> None:
        self.conn.execute(
            "INSERT OR REPLACE INTO reminders (id,title,remind_at,event_id,task_id,sent)"
            " VALUES (?,?,?,?,?,?)",
            (reminder.id, reminder.title, reminder.remind_at.isoformat(),
             reminder.event_id, reminder.task_id, int(reminder.sent)),
        )
        self.conn.commit()

    def due_reminders(self, now: datetime, profile: Profile) -> list[Reminder]:
        rows = self.conn.execute(
            "SELECT * FROM reminders WHERE sent=0 AND remind_at<=? ORDER BY remind_at",
            (now.isoformat(),),
        ).fetchall()
        return [
            Reminder(
                id=r["id"], title=r["title"],
                remind_at=profile.localize(datetime.fromisoformat(r["remind_at"])),
                event_id=r["event_id"], task_id=r["task_id"], sent=False,
            )
            for r in rows
        ]

    def mark_sent(self, reminder_id: str) -> None:
        self.conn.execute("UPDATE reminders SET sent=1 WHERE id=?", (reminder_id,))
        self.conn.commit()

    # --- proposals -----------------------------------------------------

    def save_proposal(self, proposal_id: str, summary: str, action: dict) -> None:
        self.conn.execute(
            "INSERT OR REPLACE INTO proposals (id,summary,action,created_at)"
            " VALUES (?,?,?,?)",
            (proposal_id, summary, json.dumps(action), datetime.now().isoformat()),
        )
        self.conn.commit()

    def take_proposal(self, proposal_id: str) -> dict | None:
        """Fetch an unresolved proposal's action and mark it accepted."""
        row = self.conn.execute(
            "SELECT action FROM proposals WHERE id=? AND resolved IS NULL",
            (proposal_id,),
        ).fetchone()
        if row is None:
            return None
        self.conn.execute(
            "UPDATE proposals SET resolved='accepted' WHERE id=?", (proposal_id,)
        )
        self.conn.commit()
        return json.loads(row["action"])

    def reject_proposal(self, proposal_id: str) -> bool:
        cur = self.conn.execute(
            "UPDATE proposals SET resolved='rejected' WHERE id=? AND resolved IS NULL",
            (proposal_id,),
        )
        self.conn.commit()
        return cur.rowcount > 0

    # --- conflict de-duplication ---------------------------------------

    def is_new_conflict(self, fingerprint: str) -> bool:
        """True the first time a given conflict is seen, False forever after."""
        cur = self.conn.execute(
            "INSERT OR IGNORE INTO seen_conflicts (fingerprint, seen_at) VALUES (?,?)",
            (fingerprint, datetime.now().isoformat()),
        )
        self.conn.commit()
        return cur.rowcount > 0

    def close(self) -> None:
        self.conn.close()
