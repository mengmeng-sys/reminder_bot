"""Tests for the time calculations: latest start, alerts, progress, time left."""

from datetime import datetime, timedelta

from utils import (
    alert_schedule,
    format_duration,
    latest_start_time,
    local_to_utc,
    progress_bar,
    time_left_text,
    to_local,
    urgency_icon,
    utc_now,
)


def test_latest_start_time_subtracts_estimate_and_buffer():
    deadline = datetime(2026, 11, 8, 10, 0)
    # 120 min estimate + 20% buffer (24 min) = 144 min before the deadline.
    assert latest_start_time(deadline, 120) == deadline - timedelta(minutes=144)


def test_latest_start_time_with_round_buffer():
    deadline = datetime(2026, 11, 8, 10, 0)
    # 90 min estimate + 18 min buffer = 108 min.
    assert latest_start_time(deadline, 90) == deadline - timedelta(minutes=108)


def test_alert_schedule():
    deadline = datetime(2026, 11, 8, 10, 0)
    schedule = dict(alert_schedule(deadline, 120))

    assert schedule["day_before"] == deadline - timedelta(days=1)
    assert schedule["3h_before"] == deadline - timedelta(hours=3)
    assert schedule["1h_before"] == deadline - timedelta(hours=1)
    assert schedule["overdue"] == deadline
    assert schedule["latest_start"] == deadline - timedelta(minutes=144)


def test_progress_bar():
    assert progress_bar(0, 0) == "░░░░░░░░░░ 0%"
    assert progress_bar(0, 10) == "░░░░░░░░░░ 0%"
    assert progress_bar(3, 10) == "▓▓▓░░░░░░░ 30%"
    assert progress_bar(10, 10) == "▓▓▓▓▓▓▓▓▓▓ 100%"


def test_time_left_text():
    now = utc_now()
    assert time_left_text(now + timedelta(days=2, hours=1)) == "⏳ 2 days left"
    assert time_left_text(now + timedelta(hours=5, seconds=30)) == "⏳ 5 h left"
    assert time_left_text(now + timedelta(minutes=20, seconds=30)) == "⏳ 20 min left"
    assert time_left_text(now - timedelta(hours=3, seconds=30)) == "⚠️ Overdue by 3 h"


def test_format_duration():
    assert format_duration(30) == "30 min"
    assert format_duration(60) == "1 h"
    assert format_duration(75) == "1 h 15 min"
    assert format_duration(120) == "2 h"


def test_urgency_icon():
    now = utc_now()
    assert urgency_icon(now + timedelta(days=10), 60) == "🟢"
    assert urgency_icon(now + timedelta(days=2), 60) == "🟡"
    # Estimate is longer than the time left -> start now.
    assert urgency_icon(now + timedelta(minutes=30), 60) == "🔴"
    assert urgency_icon(now - timedelta(minutes=1), 60) == "🔴"


def test_timezone_conversion():
    # 07:30 UTC is 14:30 in Cambodia (UTC+7).
    assert to_local(datetime(2026, 11, 5, 7, 30)).strftime("%H:%M") == "14:30"
    assert local_to_utc(datetime(2026, 11, 5).date(), 14, 30) == datetime(
        2026, 11, 5, 7, 30
    )
