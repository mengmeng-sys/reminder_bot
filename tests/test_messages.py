"""Tests for the text templates: task card, steps and progress."""

from datetime import timedelta

from database import Step, Task
from messages import steps_text, task_card
from utils import utc_now


def make_task(**kwargs) -> Task:
    defaults = {
        "id": 1,
        "chat_id": 1,
        "title": "Finish report",
        "deadline_utc": utc_now() + timedelta(days=2),
        "estimate_minutes": 120,
        "status": "active",
        "created_at": utc_now(),
        "completed_at": None,
        "focus_minutes": 75,
    }
    defaults.update(kwargs)
    return Task(**defaults)


def make_step(
    id: int = 1,
    task_id: int = 1,
    position: int = 1,
    text: str = "Write the introduction",
    is_done: bool = False,
    done_at=None,
) -> Step:
    return Step(
        id=id,
        task_id=task_id,
        position=position,
        text=text,
        is_done=is_done,
        done_at=done_at,
    )


def test_task_card_escapes_html():
    text = task_card(make_task(title="<b>Hack</b>"), [])
    assert "&lt;b&gt;Hack&lt;/b&gt;" in text
    assert "<b>Hack</b>" not in text


def test_task_card_without_steps():
    text = task_card(make_task(), [])
    assert "No steps yet" in text
    assert "Estimate: 2 h" in text
    assert "Focus: 1 h 15 min" in text


def test_task_card_progress_and_next_step():
    steps = [
        make_step(1, is_done=True),
        make_step(2, is_done=True),
        make_step(3, text="Make the chart", is_done=False),
    ]
    text = task_card(make_task(), steps)
    assert "▓▓▓▓▓▓▓░░░ 67%" in text
    assert "2/3 steps" in text
    assert "Next step: Make the chart" in text


def test_steps_text_shows_marks():
    steps = [
        make_step(1, text="First", is_done=True),
        make_step(2, text="Second", is_done=False),
    ]
    text = steps_text(make_task(), steps)
    # Finished steps are shown with a strikethrough.
    assert "☑ 1. <s>First</s>" in text
    assert "☐ 2. Second" in text


def test_steps_text_empty():
    text = steps_text(make_task(), [])
    assert "No steps yet" in text
