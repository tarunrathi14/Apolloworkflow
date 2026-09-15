# Personal assistant

A Telegram bot that reads your messages, keeps your Google Calendar honest, and
plans your day around what is actually on it.

You text it the way you'd text a person — *"lunch with Rahul Thursday 1pm at
Bandra, and I need to draft the Q4 memo before Friday"* — and it works out what
is an appointment, what is a task, and what is just a nudge. It then tells you
what clashes, what is physically impossible, and what got pushed out of your
protected hours.

## See it work right now

No credentials needed:

```bash
pip install -r requirements.txt
python -m assistant.demo
```

That runs a realistically annoying day through the whole pipeline — capture,
planning, conflict detection, and a confirmable fix.

## What it does

**Captures anything you throw at it.** Claude parses each message into events,
tasks, and reminders, resolving *"tomorrow"* and *"next Thursday"* against your
timezone and inferring sensible durations when you don't give one.

**Finds three kinds of trouble:**

| | | |
|---|---|---|
| 🔴 | **Overlap** | Two things claim the same minutes |
| 🔴 | **Travel** | The gap between two places is smaller than the time to cross it |
| 🟡 | **Deep work** | Something was booked into a window you said to protect |

Severity is about recoverability, not annoyance. Red means the day as scheduled
is *impossible*. Yellow means it's possible but breaks a rule you set.

**Plans the rest around them.** Tasks get fitted into what's genuinely free —
after travel and buffers come out — soonest deadline first. Deep work gets
first claim on your protected blocks, and shallow work is kept out of them
unless nothing else is left.

**Asks before it touches anything.** Every change is a proposal you answer with
`/yes`. Nothing reaches your calendar on a parse alone.

**Knows what isn't yours to move.** An event with other people on it is never
proposed for rescheduling — you get options to take to them instead.

## Setup

```bash
pip install -r requirements.txt
cp config.example.yaml config.yaml   # your hours, deep-work blocks, travel times
cp .env.example .env                 # API keys
```

Then:

1. **Anthropic** — put your key in `.env`.
2. **Telegram** — [@BotFather](https://t.me/botfather) `/newbot` gives you a
   token. `/start` your bot, then read your chat id from
   `https://api.telegram.org/bot<TOKEN>/getUpdates`.
3. **Google Calendar** — create an OAuth desktop client in Google Cloud
   Console, download `credentials.json` into the project root, and run
   `python -c "from assistant.integrations import gcal; gcal.get_service()"`
   once to mint `token.json`.

Run it:

```bash
uvicorn assistant.app:app --host 0.0.0.0 --port 8000
```

Point Telegram at it (the URL must be HTTPS — use your deploy URL, or ngrok
locally):

```bash
python -c "
from assistant.integrations.telegram import TelegramChannel
print(TelegramChannel().set_webhook('https://your-host/telegram/webhook', 'your-secret'))"
```

## Talking to it

| You send | It does |
|---|---|
| anything in plain English | parses it, confirms what it understood |
| `/today` `/tomorrow` | the plan for that day, with fixes for anything broken |
| `/yes <id>` | accepts a proposed change |
| `/no <id>` | declines it |
| `/done <id>` | closes a task |

On its own schedule it sends a 07:00 brief, fires reminders 15 minutes ahead,
and re-checks today and tomorrow every half hour — telling you about each new
conflict exactly once.

## Tuning it

Everything about how you work lives in `config.yaml`, not in code:

```yaml
deep_work:
  - label: Morning maker time
    start: "09:00"
    end: "11:00"
    weekdays: [mon, tue, wed, thu, fri]

travel:
  default_minutes: 30
  routes:
    - from: Office
      to: Client HQ
      minutes: 45
```

## Layout

```
assistant/
  models.py       Event, Task, Reminder, Conflict — the vocabulary
  config.py       your working rules, loaded from config.yaml
  conflicts.py    the three detectors
  planner.py      free-time maths and task placement
  proposals.py    turning a conflict into something you can answer "yes" to
  briefing.py     rendering for a phone screen
  service.py      orchestration — every dependency injected, so it is testable
  store.py        SQLite: tasks, reminders, pending proposals
  nlp/            Claude extraction (schema + prompt)
  integrations/   Google Calendar, Telegram
  app.py          FastAPI webhook
  scheduler.py    the 07:00 brief, reminder sweep, conflict watch
```

## Tests

```bash
python -m pytest tests/ -q
```

105 tests, no network or credentials required — the calendar, channel and LLM
are all injected, so the entire flow runs against fakes.
