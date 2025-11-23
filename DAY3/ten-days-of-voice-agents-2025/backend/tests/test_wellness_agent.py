import json
import os
import pytest
from unittest.mock import MagicMock, patch
from datetime import datetime

# Import the functions to test. 
# Note: We might need to adjust imports if agent.py is not easily importable as a module due to global code.
# For this test, we will mock the file operations and test the logic functions if possible.
# Since agent.py has global code that runs on import (load_dotenv), we should be careful.
# However, for unit testing specific functions, we can import them.

from agent import load_history, generate_system_prompt, Assistant, WELLNESS_LOG_PATH

@pytest.fixture
def mock_wellness_log():
    """Fixture to clean up wellness log after tests."""
    if os.path.exists(WELLNESS_LOG_PATH):
        os.remove(WELLNESS_LOG_PATH)
    yield
    if os.path.exists(WELLNESS_LOG_PATH):
        os.remove(WELLNESS_LOG_PATH)

def test_load_history_empty(mock_wellness_log):
    assert load_history() == []

def test_save_and_load_history(mock_wellness_log):
    # Create a dummy assistant to access the tool method
    assistant = Assistant(system_prompt="test")
    
    # Test logging a check-in
    result = assistant.log_checkin(
        mood="Good",
        objectives="Test code",
        summary="User is feeling good and wants to test code."
    )
    
    assert result == "Check-in logged successfully."
    
    # Verify file content
    history = load_history()
    assert len(history) == 1
    assert history[0]["mood"] == "Good"
    assert history[0]["objectives"] == "Test code"
    assert history[0]["summary"] == "User is feeling good and wants to test code."
    assert "timestamp" in history[0]

def test_generate_system_prompt_no_history(mock_wellness_log):
    prompt = generate_system_prompt()
    assert "You are a supportive, grounded Health & Wellness Voice Companion." in prompt
    assert "Context from previous check-in" not in prompt

def test_generate_system_prompt_with_history(mock_wellness_log):
    # Create a history entry
    assistant = Assistant(system_prompt="test")
    assistant.log_checkin(
        mood="Tired",
        objectives="Sleep",
        summary="User was tired."
    )
    
    prompt = generate_system_prompt()
    assert "Context from previous check-in" in prompt
    assert "Previous Mood: Tired" in prompt
    assert "Previous Objectives: Sleep" in prompt
