"""Simulate the conversation flow without connecting to Telegram."""

import asyncio
from datetime import timedelta
from types import SimpleNamespace

import database
import jobs
from handlers import focus, tasks
from utils import utc_now

# --- Small fakes -------------------------------------------------------------


class FakeMessage:
    def __init__(self, text, message_id=1):
        self.text = text
        self.message_id = message_id

    async def reply_text(self, *args, **kwargs):
        # Return a fake sent message so callers can use .message_id.
        return FakeMessage("", message_id=999)


class FakeQuery:
    def __init__(self, data):
        self.data = data
        # A callback query always belongs to a message.
        self.message = FakeMessage("", message_id=50)

    async def answer(self, *args, **kwargs):
        pass

    async def edit_message_text(self, *args, **kwargs):
        pass


class FakeUpdate:
    def __init__(self, data=None, text=None):
        self.callback_query = FakeQuery(data) if data is not None else None
        self.message = FakeMessage(text) if text is not None else None
        self.effective_user = SimpleNamespace(id=42, first_name="Test")
        self.effective_chat = SimpleNamespace(id=42)


class FakeBot:
    def __init__(self):
        self.sent = []
        self.deleted = []

    async def send_message(self, **kwargs):
        self.sent.append(kwargs)

    async def edit_message_text(self, **kwargs):
        self.sent.append({"type": "edit", **kwargs})

    async def delete_message(self, **kwargs):
        self.deleted.append(kwargs)


class FakeJobQueue:
    def __init__(self):
        self.jobs = []

    def run_once(self, callback, when, data=None, **kwargs):
        self.jobs.append({"callback": callback, "when": when, "data": data})

    def run_repeating(self, callback, interval, first=0, name=None, **kwargs):
        self.jobs.append({"callback": callback, "interval": interval, "name": name})


class FakeApplication:
    def __init__(self):
        self.job_queue = FakeJobQueue()


class FakeContext:
    def __init__(self):
        self.user_data = {}
        self.bot = FakeBot()
        self.application = FakeApplication()
        self.job = None


# --- Tests -------------------------------------------------------------------


def test_new_task_quick_flow(mongo_db):
    ctx = FakeContext()

    state = asyncio.run(tasks.start_new_task(FakeUpdate(data="new_task"), ctx))
    assert state == tasks.NT_TITLE

    state = asyncio.run(tasks.receive_title(FakeUpdate(text="Finish report"), ctx))
    assert state == tasks.NT_DEADLINE

    state = asyncio.run(tasks.choose_deadline(FakeUpdate(data="dl_tomorrow_9"), ctx))
    assert state == tasks.NT_ESTIMATE

    state = asyncio.run(tasks.choose_estimate(FakeUpdate(data="est_120"), ctx))
    assert state == tasks.NT_STEPS

    state = asyncio.run(
        tasks.receive_steps(FakeUpdate(text="Write intro\nMake chart"), ctx)
    )
    assert state == tasks.ConversationHandler.END

    task_list = database.get_active_tasks(42)
    assert len(task_list) == 1
    assert task_list[0].title == "Finish report"
    assert task_list[0].estimate_minutes == 120
    assert [s.text for s in database.get_steps(task_list[0].id)] == [
        "Write intro",
        "Make chart",
    ]


def test_new_task_keeps_user_messages(mongo_db):
    """The user's messages stay in the chat; only the bot's message is edited."""
    ctx = FakeContext()

    asyncio.run(tasks.start_new_task(FakeUpdate(data="new_task"), ctx))
    asyncio.run(tasks.receive_title(FakeUpdate(text="Finish report"), ctx))
    asyncio.run(tasks.choose_deadline(FakeUpdate(data="dl_tomorrow_9"), ctx))
    asyncio.run(tasks.choose_estimate(FakeUpdate(data="est_60"), ctx))
    asyncio.run(tasks.receive_steps(FakeUpdate(text="Step 1"), ctx))

    # The user's messages should NOT be deleted.
    assert ctx.bot.deleted == []


def test_new_task_command(mongo_db):
    ctx = FakeContext()

    state = asyncio.run(tasks.new_task_command(FakeUpdate(text="/new"), ctx))
    assert state == tasks.NT_TITLE


def test_new_task_calendar_flow(mongo_db):
    ctx = FakeContext()

    asyncio.run(tasks.start_new_task(FakeUpdate(data="new_task"), ctx))
    asyncio.run(tasks.receive_title(FakeUpdate(text="Call mom"), ctx))

    state = asyncio.run(tasks.choose_deadline(FakeUpdate(data="dl_pick"), ctx))
    assert state == tasks.NT_DAY

    state = asyncio.run(tasks.choose_day(FakeUpdate(data="cal_day:2026:11:5"), ctx))
    assert state == tasks.NT_HOUR

    state = asyncio.run(
        tasks.choose_hour(FakeUpdate(data="cal_hour:2026:11:5:14"), ctx)
    )
    assert state == tasks.NT_MINUTE

    state = asyncio.run(
        tasks.choose_minute(FakeUpdate(data="cal_min:2026:11:5:14:30"), ctx)
    )
    assert state == tasks.NT_ESTIMATE

    asyncio.run(tasks.choose_estimate(FakeUpdate(data="est_60"), ctx))
    asyncio.run(tasks.skip_steps(FakeUpdate(data="steps_skip"), ctx))

    task_list = database.get_active_tasks(42)
    # 14:30 Cambodia time = 07:30 UTC.
    assert task_list[0].deadline_utc.hour == 7
    assert task_list[0].deadline_utc.minute == 30


def test_cancel_flow(mongo_db):
    ctx = FakeContext()

    asyncio.run(tasks.start_new_task(FakeUpdate(data="new_task"), ctx))
    state = asyncio.run(tasks.cancel(FakeUpdate(data="cancel"), ctx))
    assert state == tasks.ConversationHandler.END
    assert database.get_active_tasks(42) == []


def test_empty_task_is_rejected(mongo_db):
    ctx = FakeContext()

    asyncio.run(tasks.start_new_task(FakeUpdate(data="new_task"), ctx))
    state = asyncio.run(tasks.receive_title(FakeUpdate(text="   "), ctx))

    assert state == tasks.NT_TITLE


def test_cancel_via_command(mongo_db):
    ctx = FakeContext()

    asyncio.run(tasks.start_new_task(FakeUpdate(data="new_task"), ctx))
    state = asyncio.run(tasks.cancel(FakeUpdate(text="/cancel"), ctx))

    assert state == tasks.ConversationHandler.END
    assert database.get_active_tasks(42) == []


def test_finish_next_step_completes_task(mongo_db):
    ctx = FakeContext()

    task_id = database.add_task(42, "Test", utc_now() + timedelta(days=1), 60)
    database.add_step(task_id, "Only step")

    asyncio.run(
        tasks.finish_next_step(FakeUpdate(data=f"task_finish_step:{task_id}"), ctx)
    )

    assert database.get_task(task_id).status == "done"


def test_focus_without_a_task(mongo_db):
    ctx = FakeContext()

    asyncio.run(focus.focus_pick_task(FakeUpdate(data="focus_none"), ctx))
    asyncio.run(focus.focus_pick_length(FakeUpdate(data="focus_len:0:15"), ctx))

    session = database.get_running_session(42)
    assert session is not None
    assert session.task_id is None
    assert session.minutes == 15


def test_focus_start_and_stop(mongo_db):
    ctx = FakeContext()

    task_id = database.add_task(42, "Test", utc_now() + timedelta(days=1), 60)

    asyncio.run(focus.focus_pick_task(FakeUpdate(data=f"focus_task:{task_id}"), ctx))
    asyncio.run(focus.focus_pick_length(FakeUpdate(data=f"focus_len:{task_id}:25"), ctx))

    session = database.get_running_session(42)
    assert session is not None
    assert session.minutes == 25
    assert len(ctx.application.job_queue.jobs) == 2  # halfway + end

    asyncio.run(focus.focus_stop(FakeUpdate(data=f"focus_stop:{session.id}"), ctx))
    assert database.get_running_session(42) is None


def test_alert_checker_sends_only_most_urgent(mongo_db):
    ctx = FakeContext()

    task_id = database.add_task(42, "Test", utc_now() - timedelta(hours=1), 60)
    database.add_alert(task_id, "day_before", utc_now() - timedelta(days=1))
    database.add_alert(task_id, "1h_before", utc_now() - timedelta(hours=1))
    database.add_alert(task_id, "overdue", utc_now() - timedelta(minutes=30))

    asyncio.run(jobs.alert_checker(ctx))

    # Only one message was sent, and it is the most urgent one.
    assert len(ctx.bot.sent) == 1
    assert "Overdue" in ctx.bot.sent[0]["text"]
    # All due alerts are now marked as sent.
    assert database.get_due_alerts(utc_now()) == []


def test_alert_checker_skips_done_tasks(mongo_db):
    ctx = FakeContext()

    task_id = database.add_task(42, "Test", utc_now() - timedelta(hours=1), 60)
    database.add_alert(task_id, "overdue", utc_now() - timedelta(minutes=30))
    database.mark_task_done(task_id)

    asyncio.run(jobs.alert_checker(ctx))

    assert ctx.bot.sent == []
    assert database.get_due_alerts(utc_now()) == []
