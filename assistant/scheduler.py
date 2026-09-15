"""Background jobs: the morning brief, reminder delivery, and conflict watching.

Times are local to your profile timezone. The reminder sweep runs every minute,
which is the resolution the whole reminder system is built around.
"""

from __future__ import annotations

import logging

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

from .service import Assistant

log = logging.getLogger(__name__)


def start_scheduler(assistant: Assistant) -> BackgroundScheduler:
    tz = assistant.profile.tz
    scheduler = BackgroundScheduler(timezone=tz)

    def safely(fn, name):
        def wrapped():
            try:
                fn()
            except Exception:
                log.exception("scheduled job %s failed", name)
        return wrapped

    # Every minute: anything due goes out.
    scheduler.add_job(
        safely(assistant.dispatch_reminders, "reminders"),
        CronTrigger(minute="*", timezone=tz),
        id="reminders", max_instances=1, coalesce=True,
    )

    # 07:00 daily: here is your day.
    scheduler.add_job(
        safely(assistant.send_brief, "morning_brief"),
        CronTrigger(hour=7, minute=0, timezone=tz),
        id="morning_brief", max_instances=1,
    )

    # Every 30 minutes during waking hours: has anything broken since?
    scheduler.add_job(
        safely(assistant.watch_for_conflicts, "conflict_watch"),
        CronTrigger(minute="0,30", hour="7-22", timezone=tz),
        id="conflict_watch", max_instances=1, coalesce=True,
    )

    scheduler.start()
    log.info("scheduler started (%s)", assistant.profile.timezone)
    return scheduler
