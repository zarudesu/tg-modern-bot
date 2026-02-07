"""
Tests for Plane API data models — PlaneTask computed properties.

Source: app/integrations/plane/models.py
"""

import pytest
from datetime import datetime, timezone, timedelta

from app.integrations.plane.models import PlaneTask


class TestPlaneTaskOverdue:
    """Tests for PlaneTask.is_overdue property."""

    def test_overdue_with_past_date(self, plane_task_factory):
        yesterday = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()
        task = plane_task_factory(target_date=yesterday)
        assert task.is_overdue is True

    def test_not_overdue_with_future_date(self, plane_task_factory):
        tomorrow = (datetime.now(timezone.utc) + timedelta(days=1)).isoformat()
        task = plane_task_factory(target_date=tomorrow)
        assert task.is_overdue is False

    def test_not_overdue_without_date(self, plane_task_factory):
        task = plane_task_factory(target_date=None)
        assert task.is_overdue is False

    def test_not_overdue_with_empty_string(self, plane_task_factory):
        task = plane_task_factory(target_date="")
        assert task.is_overdue is False


class TestPlaneTaskDueToday:
    """Tests for PlaneTask.is_due_today property."""

    def test_due_today(self, plane_task_factory):
        today = datetime.now(timezone.utc).isoformat()
        task = plane_task_factory(target_date=today)
        assert task.is_due_today is True

    def test_not_due_today_past(self, plane_task_factory):
        yesterday = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()
        task = plane_task_factory(target_date=yesterday)
        assert task.is_due_today is False

    def test_not_due_today_future(self, plane_task_factory):
        tomorrow = (datetime.now(timezone.utc) + timedelta(days=1)).isoformat()
        task = plane_task_factory(target_date=tomorrow)
        assert task.is_due_today is False

    def test_not_due_today_no_date(self, plane_task_factory):
        task = plane_task_factory(target_date=None)
        assert task.is_due_today is False


class TestPlaneTaskPriorityEmoji:
    """Tests for PlaneTask.priority_emoji property."""

    @pytest.mark.parametrize(
        "priority,expected_emoji",
        [
            ("urgent", "\U0001f534"),   # red circle
            ("high", "\U0001f7e0"),     # orange circle
            ("medium", "\U0001f7e1"),   # yellow circle
            ("low", "\U0001f7e2"),      # green circle
            ("none", "\u26aa"),         # white circle
        ],
    )
    def test_priority_emoji(self, plane_task_factory, priority, expected_emoji):
        task = plane_task_factory(priority=priority)
        assert task.priority_emoji == expected_emoji

    def test_priority_emoji_none_value(self, plane_task_factory):
        task = plane_task_factory(priority=None)
        assert task.priority_emoji == "\u26aa"  # white circle (default)

    def test_priority_emoji_unknown(self, plane_task_factory):
        task = plane_task_factory(priority="unknown_value")
        assert task.priority_emoji == "\u26aa"  # white circle (fallback)


class TestPlaneTaskStateEmoji:
    """Tests for PlaneTask.state_emoji property."""

    @pytest.mark.parametrize(
        "state_name,expected_emoji",
        [
            ("Done", "\u2705"),               # checkmark
            ("Completed", "\u2705"),
            ("In Progress", "\U0001f504"),     # arrows
            ("Started", "\U0001f504"),
            ("In Review", "\U0001f440"),        # eyes
            ("Backlog", "\U0001f4cb"),          # clipboard
            ("Todo", "\U0001f4cc"),             # pushpin (default)
        ],
    )
    def test_state_emoji(self, plane_task_factory, state_name, expected_emoji):
        task = plane_task_factory(state_name=state_name)
        assert task.state_emoji == expected_emoji


class TestPlaneTaskStateResolution:
    """Tests for PlaneTask.get_state_name() method."""

    def test_state_name_from_detail(self, plane_task_factory):
        task = plane_task_factory(
            state_name="fallback",
            state_detail={"name": "In Progress", "group": "started"},
        )
        assert task.get_state_name() == "In Progress"

    def test_state_name_fallback_no_detail(self, plane_task_factory):
        task = plane_task_factory(state_name="Backlog", state_detail=None)
        assert task.get_state_name() == "Backlog"

    def test_state_name_fallback_empty_detail(self, plane_task_factory):
        task = plane_task_factory(state_name="Backlog", state_detail={})
        assert task.get_state_name() == "Backlog"


class TestPlaneTaskUrl:
    """Tests for PlaneTask.task_url property."""

    def test_task_url_format(self):
        task = PlaneTask(
            id="issue-456",
            name="Test",
            state="s1",
            project="proj-123",
        )
        assert task.task_url == "https://plane.hhivp.com/projects/proj-123/issues/issue-456"
