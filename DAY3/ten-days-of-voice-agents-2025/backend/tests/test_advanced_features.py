import pytest
import json
import os
from datetime import datetime, timedelta
from pathlib import Path
import sys

# Add the src directory to Python path
sys.path.insert(0, str(Path(__file__).parent.parent / 'src'))

from agent import Assistant, generate_system_prompt, load_history

# Test file paths
TEST_WELLNESS_LOG = "test_wellness_log.json"
TEST_TASKS_FILE = "test_wellness_tasks.json"
TEST_REMINDERS_FILE = "test_wellness_reminders.json"


@pytest.fixture(autouse=True)
def setup_and_cleanup():
    """Setup and cleanup test files before and after each test."""
    # Cleanup before test
    for file in [TEST_WELLNESS_LOG, TEST_TASKS_FILE, TEST_REMINDERS_FILE]:
        if os.path.exists(file):
            os.remove(file)
    
    # Monkey patch the file paths in agent module
    import agent
    agent.WELLNESS_LOG_PATH = TEST_WELLNESS_LOG
    agent.TASKS_FILE_PATH = TEST_TASKS_FILE
    agent.REMINDERS_FILE_PATH = TEST_REMINDERS_FILE
    
    yield
    
    # Cleanup after test
    for file in [TEST_WELLNESS_LOG, TEST_TASKS_FILE, TEST_REMINDERS_FILE]:
        if os.path.exists(file):
            os.remove(file)


class TestWeeklyReflection:
    """Tests for weekly reflection functionality."""
    
    def test_weekly_reflection_no_history(self):
        """Test weekly reflection with no check-in history."""
        assistant = Assistant(system_prompt="Test")
        result = assistant.get_weekly_reflection()
        assert "No check-in history available" in result
    
    def test_weekly_reflection_with_recent_entries(self):
        """Test weekly reflection with recent check-ins."""
        # Create mock history
        history = [
            {
                "timestamp": datetime.now().isoformat(),
                "mood": "energetic",
                "objectives": "Complete project, Exercise",
                "summary": "User is feeling good"
            },
            {
                "timestamp": (datetime.now() - timedelta(days=2)).isoformat(),
                "mood": "tired",
                "objectives": "Rest, Read a book",
                "summary": "User needs rest"
            },
            {
                "timestamp": (datetime.now() - timedelta(days=5)).isoformat(),
                "mood": "motivated",
                "objectives": "Start new task",
                "summary": "User is motivated"
            }
        ]
        
        with open(TEST_WELLNESS_LOG, "w") as f:
            json.dump(history, f)
        
        assistant = Assistant(system_prompt="Test")
        result = assistant.get_weekly_reflection(days=7)
        
        assert "3 check-ins" in result
        assert "energetic" in result or "tired" in result or "motivated" in result
    
    def test_weekly_reflection_old_entries_filtered(self):
        """Test that old entries are filtered out."""
        history = [
            {
                "timestamp": (datetime.now() - timedelta(days=30)).isoformat(),
                "mood": "old mood",
                "objectives": "old objectives",
                "summary": "old entry"
            }
        ]
        
        with open(TEST_WELLNESS_LOG, "w") as f:
            json.dump(history, f)
        
        assistant = Assistant(system_prompt="Test")
        result = assistant.get_weekly_reflection(days=7)
        
        assert "No check-ins found in the last 7 days" in result


class TestTaskManagement:
    """Tests for task creation, retrieval, and completion."""
    
    def test_create_task(self):
        """Test creating a new task."""
        assistant = Assistant(system_prompt="Test")
        result = assistant.create_task(
            task_title="Complete the project report",
            priority="high"
        )
        
        assert "Task created successfully" in result
        assert "Complete the project report" in result
        assert "high priority" in result
        
        # Verify task was saved
        with open(TEST_TASKS_FILE, "r") as f:
            tasks = json.load(f)
        
        assert len(tasks) == 1
        assert tasks[0]["title"] == "Complete the project report"
        assert tasks[0]["priority"] == "high"
        assert tasks[0]["status"] == "pending"
    
    def test_get_tasks_empty(self):
        """Test retrieving tasks when none exist."""
        assistant = Assistant(system_prompt="Test")
        result = assistant.get_tasks()
        
        assert "No tasks found" in result
    
    def test_get_tasks_with_pending(self):
        """Test retrieving pending tasks."""
        # Create some tasks
        tasks = [
            {
                "id": 1,
                "title": "Task 1",
                "priority": "high",
                "status": "pending",
                "created_at": datetime.now().isoformat()
            },
            {
                "id": 2,
                "title": "Task 2",
                "priority": "medium",
                "status": "pending",
                "created_at": datetime.now().isoformat()
            },
            {
                "id": 3,
                "title": "Task 3",
                "priority": "low",
                "status": "completed",
                "created_at": datetime.now().isoformat()
            }
        ]
        
        with open(TEST_TASKS_FILE, "w") as f:
            json.dump(tasks, f)
        
        assistant = Assistant(system_prompt="Test")
        result = assistant.get_tasks(status_filter="pending")
        
        assert "2 pending task(s)" in result
        assert "Task 1" in result
        assert "Task 2" in result
        assert "Task 3" not in result
    
    def test_get_all_tasks(self):
        """Test retrieving all tasks."""
        tasks = [
            {
                "id": 1,
                "title": "Task 1",
                "priority": "high",
                "status": "pending",
                "created_at": datetime.now().isoformat()
            },
            {
                "id": 2,
                "title": "Task 2",
                "priority": "medium",
                "status": "completed",
                "created_at": datetime.now().isoformat()
            }
        ]
        
        with open(TEST_TASKS_FILE, "w") as f:
            json.dump(tasks, f)
        
        assistant = Assistant(system_prompt="Test")
        result = assistant.get_tasks(status_filter="all")
        
        assert "2 all task(s)" in result
    
    def test_complete_task(self):
        """Test marking a task as completed."""
        # Create a pending task
        tasks = [
            {
                "id": 1,
                "title": "Complete the project report",
                "priority": "high",
                "status": "pending",
                "created_at": datetime.now().isoformat()
            }
        ]
        
        with open(TEST_TASKS_FILE, "w") as f:
            json.dump(tasks, f)
        
        assistant = Assistant(system_prompt="Test")
        result = assistant.complete_task(task_title="project report")
        
        assert "marked as completed" in result
        
        # Verify task status was updated
        with open(TEST_TASKS_FILE, "r") as f:
            tasks = json.load(f)
        
        assert tasks[0]["status"] == "completed"
        assert "completed_at" in tasks[0]
    
    def test_complete_nonexistent_task(self):
        """Test completing a task that doesn't exist."""
        assistant = Assistant(system_prompt="Test")
        result = assistant.complete_task(task_title="nonexistent task")
        
        assert "not found" in result.lower()


class TestReminders:
    """Tests for reminder creation."""
    
    def test_create_reminder(self):
        """Test creating a reminder."""
        assistant = Assistant(system_prompt="Test")
        result = assistant.create_reminder(
            activity="Go for a walk",
            time="6 pm"
        )
        
        assert "Reminder created" in result
        assert "Go for a walk" in result
        assert "6 pm" in result
        
        # Verify reminder was saved
        with open(TEST_REMINDERS_FILE, "r") as f:
            reminders = json.load(f)
        
        assert len(reminders) == 1
        assert reminders[0]["activity"] == "Go for a walk"
        assert reminders[0]["time"] == "6 pm"
        assert reminders[0]["status"] == "active"
    
    def test_create_multiple_reminders(self):
        """Test creating multiple reminders."""
        assistant = Assistant(system_prompt="Test")
        
        assistant.create_reminder(activity="Morning meditation", time="8 am")
        assistant.create_reminder(activity="Evening walk", time="7 pm")
        
        with open(TEST_REMINDERS_FILE, "r") as f:
            reminders = json.load(f)
        
        assert len(reminders) == 2
        assert reminders[0]["activity"] == "Morning meditation"
        assert reminders[1]["activity"] == "Evening walk"


class TestSystemPromptGeneration:
    """Tests for system prompt generation with context."""
    
    def test_system_prompt_with_no_history(self):
        """Test system prompt generation with no history."""
        prompt = generate_system_prompt()
        
        assert "Health & Wellness Voice Companion" in prompt
        assert "ask about their mood" in prompt.lower()
        assert "weekly reflection" in prompt.lower()
        assert "create tasks" in prompt.lower()
        assert "Previous" not in prompt  # No previous context
    
    def test_system_prompt_with_history(self):
        """Test system prompt generation with previous check-ins."""
        history = [
            {
                "timestamp": datetime.now().isoformat(),
                "mood": "stressed",
                "objectives": "Finish project deadline",
                "summary": "User is stressed about deadline"
            }
        ]
        
        with open(TEST_WELLNESS_LOG, "w") as f:
            json.dump(history, f)
        
        prompt = generate_system_prompt()
        
        assert "Previous Mood: stressed" in prompt
        assert "Previous Objectives: Finish project deadline" in prompt
        assert "Use this context" in prompt


class TestIntegration:
    """Integration tests for complete workflows."""
    
    def test_complete_wellness_workflow(self):
        """Test a complete workflow: check-in, create tasks, reflection."""
        assistant = Assistant(system_prompt="Test")
        
        # Step 1: Log a check-in
        checkin_result = assistant.log_checkin(
            mood="energetic",
            objectives="Exercise, Complete report, Call friend",
            summary="User is feeling good and has clear goals"
        )
        assert "successfully" in checkin_result
        
        # Step 2: Create tasks from objectives
        task1 = assistant.create_task("Exercise for 30 minutes", "high")
        task2 = assistant.create_task("Complete project report", "high")
        task3 = assistant.create_task("Call friend", "medium")
        
        assert "Task created successfully" in task1
        assert "Task created successfully" in task2
        assert "Task created successfully" in task3
        
        # Step 3: Get tasks
        tasks = assistant.get_tasks()
        assert "3 pending task(s)" in tasks
        
        # Step 4: Complete a task
        complete = assistant.complete_task("Exercise")
        assert "marked as completed" in complete
        
        # Step 5: Create a reminder
        reminder = assistant.create_reminder("Take a break", "3 pm")
        assert "Reminder created" in reminder
        
        # Step 6: Get weekly reflection
        reflection = assistant.get_weekly_reflection()
        assert "1 check-ins" in reflection
        assert "energetic" in reflection


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
