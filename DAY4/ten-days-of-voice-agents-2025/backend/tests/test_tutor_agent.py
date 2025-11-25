import pytest
import json
from pathlib import Path
from livekit.agents import AgentSession, inference, llm

# Import the actual implementation
import sys
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from agent import TutorAgent, load_content


def _llm() -> llm.LLM:
    return inference.LLM(model="openai/gpt-4.1-mini")


@pytest.mark.asyncio
async def test_content_loading() -> None:
    """Test that the tutor content loads correctly from JSON file."""
    content_path = Path(__file__).parent.parent / "shared-data" / "day4_tutor_content.json"
    
    # Verify file exists
    assert content_path.exists(), f"Content file not found at {content_path}"
    
    # Load and verify content structure
    with open(content_path, "r") as f:
        content = json.load(f)
    
    assert isinstance(content, list), "Content should be a list"
    assert len(content) > 0, "Content should not be empty"
    
    # Verify each concept has required fields
    for concept in content:
        assert "id" in concept, "Each concept must have an id"
        assert "title" in concept, "Each concept must have a title"
        assert "summary" in concept, "Each concept must have a summary"
        assert "sample_question" in concept, "Each concept must have a sample_question"
        
    # Verify specific concepts exist
    concept_ids = [c["id"] for c in content]
    assert "variables" in concept_ids, "Content should include 'variables' concept"
    assert "loops" in concept_ids, "Content should include 'loops' concept"


@pytest.mark.asyncio
async def test_tutor_greets_and_offers_modes() -> None:
    """Evaluation of tutor agent's greeting and mode explanation."""
    async with (
        _llm() as llm,
        AgentSession(llm=llm) as session,
    ):
        await session.start(TutorAgent())

        # Run an agent turn following the user's initial connection
        result = await session.run(user_input="Hello")

        # Evaluate the agent's response for greeting and mode options
        await (
            result.expect.next_event()
            .is_message(role="assistant")
            .judge(
                llm,
                intent="""
                Greets the user warmly and explains that this is an active recall coach or tutoring system.
                
                Must mention or explain the three available learning modes:
                - Learn mode (or similar) where concepts are explained
                - Quiz mode (or similar) where the user is asked questions
                - Teach back mode (or similar) where the user explains concepts
                
                May ask which mode the user prefers or is interested in.
                """,
            )
        )


@pytest.mark.asyncio
async def test_switch_to_learn_mode() -> None:
    """Test switching to learn mode."""
    async with (
        _llm() as llm,
        AgentSession(llm=llm) as session,
    ):
        await session.start(TutorAgent())

        # User requests learn mode
        result = await session.run(user_input="I want to learn about variables")

        # Should have at least one message and potentially a mode switch
        # The agent should either explain or indicate it's switching to learn mode
        await (
            result.expect.next_event()
            .is_message(role="assistant")
            .judge(
                llm,
                intent="""
                Responds to the user's request to learn about variables.
                
                The response should either:
                - Start explaining the concept of variables
                - Indicate that it's switching to learn mode
                - Acknowledge the request positively
                """,
            )
        )


@pytest.mark.asyncio
async def test_switch_to_quiz_mode() -> None:
    """Test switching to quiz mode."""
    async with (
        _llm() as llm,
        AgentSession(llm=llm) as session,
    ):
        await session.start(TutorAgent())

        # User requests quiz mode
        result = await session.run(user_input="I want to be quizzed on loops")

        # Should respond appropriately to quiz request
        await (
            result.expect.next_event()
            .is_message(role="assistant")
            .judge(
                llm,
                intent="""
                Responds to the user's request to be quizzed.
                
                The response should either:
                - Ask a question about loops
                - Indicate switching to quiz mode
                - Acknowledge the quiz request positively
                """,
            )
        )


@pytest.mark.asyncio
async def test_switch_to_teach_back_mode() -> None:
    """Test switching to teach back mode."""
    async with (
        _llm() as llm,
        AgentSession(llm=llm) as session,
    ):
        await session.start(TutorAgent())

        # User requests teach back mode
        result = await session.run(user_input="I want to teach you about functions")

        # Should respond appropriately to teach back request
        await (
            result.expect.next_event()
            .is_message(role="assistant")
            .judge(
                llm,
                intent="""
                Responds to the user's request to explain or teach back a concept.
                
                The response should either:
                - Ask the user to explain functions
                - Indicate switching to teach back mode
                - Acknowledge the request positively and prepare to listen
                """,
            )
        )


@pytest.mark.asyncio
async def test_mode_switching() -> None:
    """Test switching between different learning modes in a session."""
    async with (
        _llm() as llm,
        AgentSession(llm=llm) as session,
    ):
        await session.start(TutorAgent())

        # Start with learning
        result1 = await session.run(user_input="Teach me about conditionals")
        await result1.expect.next_event().is_message(role="assistant")

        # Switch to quiz mode
        result2 = await session.run(user_input="Now quiz me on it")
        await (
            result2.expect.next_event()
            .is_message(role="assistant")
            .judge(
                llm,
                intent="Asks a question about conditionals or confirms switching to quiz mode",
            )
        )

        # Switch to teach back mode
        result3 = await session.run(user_input="Let me explain it back to you")
        await (
            result3.expect.next_event()
            .is_message(role="assistant")
            .judge(
                llm,
                intent="Asks the user to explain or confirms readiness to listen to the user's explanation",
            )
        )
