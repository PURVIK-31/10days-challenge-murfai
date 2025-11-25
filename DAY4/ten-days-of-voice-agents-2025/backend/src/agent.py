import json
import logging
from pathlib import Path
from typing import Annotated, Optional

from dotenv import load_dotenv
from livekit.agents import (
    Agent,
    AgentSession,
    JobContext,
    JobProcess,
    MetricsCollectedEvent,
    RoomInputOptions,
    WorkerOptions,
    cli,
    metrics,
    tokenize,
    function_tool,
    RunContext,
)
from livekit.plugins import murf, silero, google, deepgram, noise_cancellation
from livekit.plugins.turn_detector.multilingual import MultilingualModel

logger = logging.getLogger("agent")

load_dotenv(".env.local")


def load_content() -> list[dict]:
    """Load the tutor content from the JSON file."""
    # Path from src/agent.py -> src/ -> backend/ -> shared-data/
    content_path = Path(__file__).parent.parent / "shared-data" / "day4_tutor_content.json"
    try:
        with open(content_path, "r") as f:
            return json.load(f)
    except FileNotFoundError:
        logger.error(f"Content file not found at {content_path}")
        return []
    except json.JSONDecodeError as e:
        logger.error(f"Error parsing JSON content: {e}")
        return []


def get_concept_by_id(concept_id: str) -> Optional[dict]:
    """Get a concept by its ID."""
    content = load_content()
    for concept in content:
        if concept.get("id") == concept_id:
            return concept
    return None


def get_concept_by_title(title: str) -> Optional[dict]:
    """Get a concept by its title (case-insensitive partial match)."""
    content = load_content()
    title_lower = title.lower()
    for concept in content:
        if title_lower in concept.get("title", "").lower():
            return concept
    return None


class OrchestratorAgent(Agent):
    """Orchestrator agent that greets users and routes to learning modes."""
    
    def __init__(self) -> None:
        super().__init__(
            instructions="""You are the orchestrator for an active recall learning coach. 
            Your role is to greet users warmly and help them choose a learning mode.
            
            There are three learning modes available:
            1. **Learn mode** - The agent explains concepts to the user
            2. **Quiz mode** - The agent asks questions to test understanding
            3. **Teach back mode** - The user explains concepts back to the agent
            
            When a user first connects, greet them warmly and explain these three modes. 
            Ask which mode they'd like to try or which concept they want to learn about.
            
            When the user requests a specific mode (e.g., "I want to learn", "quiz me", "let me teach you"), 
            use the appropriate handoff tool to connect them to that mode's agent.
            
            You can also help users switch between modes during their session.
            
            Keep your responses concise and friendly. You're speaking, so avoid complex formatting.""",
        )
    
    @function_tool
    async def handoff_to_learn_mode(
        self,
        context: RunContext,
        concept: Annotated[Optional[str], "The concept to learn about (e.g., 'variables', 'loops'). If not specified, let the agent choose."] = None,
    ) -> str:
        """Hand off to the Learn mode agent. This agent will explain concepts to the user using Matthew's voice.
        
        Args:
            concept: Optional concept ID or title to learn about
        """
        logger.info(f"Handing off to learn mode with concept: {concept}")
        # Store the concept in session state for the learn agent
        context.session_state["mode"] = "learn"
        context.session_state["concept"] = concept
        return f"Switching to learn mode. {'Ready to explain ' + concept + '.' if concept else 'Ready to explain concepts.'}"
    
    @function_tool
    async def handoff_to_quiz_mode(
        self,
        context: RunContext,
        concept: Annotated[Optional[str], "The concept to quiz on (e.g., 'variables', 'loops'). If not specified, let the agent choose."] = None,
    ) -> str:
        """Hand off to the Quiz mode agent. This agent will ask questions using Alicia's voice.
        
        Args:
            concept: Optional concept ID or title to quiz on
        """
        logger.info(f"Handing off to quiz mode with concept: {concept}")
        context.session_state["mode"] = "quiz"
        context.session_state["concept"] = concept
        return f"Switching to quiz mode. {'Ready to quiz you on ' + concept + '.' if concept else 'Ready to quiz you.'}"
    
    @function_tool
    async def handoff_to_teach_back_mode(
        self,
        context: RunContext,
        concept: Annotated[Optional[str], "The concept to teach back (e.g., 'variables', 'loops'). If not specified, let the agent choose."] = None,
    ) -> str:
        """Hand off to the Teach Back mode agent. This agent will ask the user to explain concepts using Ken's voice.
        
        Args:
            concept: Optional concept ID or title to teach back
        """
        logger.info(f"Handing off to teach back mode with concept: {concept}")
        context.session_state["mode"] = "teach_back"
        context.session_state["concept"] = concept
        return f"Switching to teach back mode. {'Ready to listen to your explanation of ' + concept + '.' if concept else 'Ready to listen to your explanations.'}"


class LearnModeAgent(Agent):
    """Agent for Learn mode - explains concepts using Matthew's voice."""
    
    def __init__(self) -> None:
        content = load_content()
        concept_list = ", ".join([c["title"] for c in content])
        
        super().__init__(
            instructions=f"""You are a helpful tutor in Learn mode. Your voice is Matthew.
            
            Your role is to explain programming concepts clearly and engagingly to help users learn.
            
            Available concepts: {concept_list}
            
            When explaining a concept:
            - Use the summary from the content file as your base
            - Explain it in a clear, conversational way
            - Use examples when helpful
            - Keep explanations concise but thorough
            - Be encouraging and supportive
            
            If the user asks about a concept, look it up in the content and explain it using the summary.
            If no specific concept is mentioned, you can suggest concepts or explain the one you think would be most helpful.
            
            The user can switch modes at any time by asking. You can also suggest they try quiz mode or teach back mode after explaining.
            
            Keep responses natural and conversational since you're speaking.""",
        )
    
    @function_tool
    async def get_concept_info(
        self,
        context: RunContext,
        concept_identifier: Annotated[str, "The concept ID or title to look up"],
    ) -> str:
        """Get information about a specific concept from the content file.
        
        Args:
            concept_identifier: The concept ID (e.g., 'variables') or title
        """
        concept = get_concept_by_id(concept_identifier) or get_concept_by_title(concept_identifier)
        if concept:
            return f"Concept: {concept['title']}\nSummary: {concept['summary']}"
        return f"Concept '{concept_identifier}' not found in content."
    
    @function_tool
    async def list_concepts(self, context: RunContext) -> str:
        """List all available concepts."""
        content = load_content()
        concepts = [f"- {c['title']} ({c['id']})" for c in content]
        return "Available concepts:\n" + "\n".join(concepts)
    
    @function_tool
    async def switch_to_quiz_mode(
        self,
        context: RunContext,
        concept: Annotated[Optional[str], "The concept to quiz on"] = None,
    ) -> str:
        """Switch to quiz mode to test understanding."""
        context.session_state["mode"] = "quiz"
        context.session_state["concept"] = concept
        return "Switching to quiz mode."
    
    @function_tool
    async def switch_to_teach_back_mode(
        self,
        context: RunContext,
        concept: Annotated[Optional[str], "The concept to teach back"] = None,
    ) -> str:
        """Switch to teach back mode where the user explains concepts."""
        context.session_state["mode"] = "teach_back"
        context.session_state["concept"] = concept
        return "Switching to teach back mode."


class QuizModeAgent(Agent):
    """Agent for Quiz mode - asks questions using Alicia's voice."""
    
    def __init__(self) -> None:
        content = load_content()
        concept_list = ", ".join([c["title"] for c in content])
        
        super().__init__(
            instructions=f"""You are a quiz coach in Quiz mode. Your voice is Alicia.
            
            Your role is to ask questions about programming concepts to test the user's understanding.
            
            Available concepts: {concept_list}
            
            When quizzing:
            - Use the sample questions from the content file as inspiration
            - Ask clear, focused questions
            - Provide encouraging feedback on answers
            - If the user struggles, offer hints or suggest reviewing in learn mode
            - Keep questions appropriate for the concept level
            
            If a specific concept is mentioned, focus your questions on that concept.
            Otherwise, you can quiz on any available concept.
            
            The user can switch modes at any time. After a few questions, you might suggest trying teach back mode.
            
            Keep responses natural and conversational since you're speaking.""",
        )
    
    @function_tool
    async def get_concept_question(
        self,
        context: RunContext,
        concept_identifier: Annotated[str, "The concept ID or title to get a question for"],
    ) -> str:
        """Get a sample question for a specific concept.
        
        Args:
            concept_identifier: The concept ID (e.g., 'variables') or title
        """
        concept = get_concept_by_id(concept_identifier) or get_concept_by_title(concept_identifier)
        if concept:
            return f"Sample question for {concept['title']}: {concept.get('sample_question', 'No sample question available.')}"
        return f"Concept '{concept_identifier}' not found."
    
    @function_tool
    async def switch_to_learn_mode(
        self,
        context: RunContext,
        concept: Annotated[Optional[str], "The concept to learn about"] = None,
    ) -> str:
        """Switch to learn mode to review concepts."""
        context.session_state["mode"] = "learn"
        context.session_state["concept"] = concept
        return "Switching to learn mode."
    
    @function_tool
    async def switch_to_teach_back_mode(
        self,
        context: RunContext,
        concept: Annotated[Optional[str], "The concept to teach back"] = None,
    ) -> str:
        """Switch to teach back mode where the user explains concepts."""
        context.session_state["mode"] = "teach_back"
        context.session_state["concept"] = concept
        return "Switching to teach back mode."


class TeachBackModeAgent(Agent):
    """Agent for Teach Back mode - asks user to explain concepts using Ken's voice."""
    
    def __init__(self) -> None:
        content = load_content()
        concept_list = ", ".join([c["title"] for c in content])
        
        super().__init__(
            instructions=f"""You are a learning coach in Teach Back mode. Your voice is Ken.
            
            Your role is to ask users to explain programming concepts back to you, which helps them learn through active recall.
            
            Available concepts: {concept_list}
            
            When in teach back mode:
            - Ask the user to explain a concept in their own words
            - Listen actively to their explanation
            - Provide qualitative feedback on their explanation
            - Point out what they got right and what might need clarification
            - Be encouraging and supportive
            - If they struggle, suggest reviewing in learn mode first
            
            If a specific concept is mentioned, ask them to explain that concept.
            Otherwise, you can choose a concept or let them pick.
            
            The user can switch modes at any time. After they explain, you might suggest trying quiz mode to test their knowledge.
            
            Keep responses natural and conversational since you're speaking.""",
        )
    
    @function_tool
    async def get_concept_summary(
        self,
        context: RunContext,
        concept_identifier: Annotated[str, "The concept ID or title to get the summary for"],
    ) -> str:
        """Get the summary of a concept to help evaluate the user's explanation.
        
        Args:
            concept_identifier: The concept ID (e.g., 'variables') or title
        """
        concept = get_concept_by_id(concept_identifier) or get_concept_by_title(concept_identifier)
        if concept:
            return f"Summary for {concept['title']}: {concept['summary']}"
        return f"Concept '{concept_identifier}' not found."
    
    @function_tool
    async def switch_to_learn_mode(
        self,
        context: RunContext,
        concept: Annotated[Optional[str], "The concept to learn about"] = None,
    ) -> str:
        """Switch to learn mode to review concepts."""
        context.session_state["mode"] = "learn"
        context.session_state["concept"] = concept
        return "Switching to learn mode."
    
    @function_tool
    async def switch_to_quiz_mode(
        self,
        context: RunContext,
        concept: Annotated[Optional[str], "The concept to quiz on"] = None,
    ) -> str:
        """Switch to quiz mode to test understanding."""
        context.session_state["mode"] = "quiz"
        context.session_state["concept"] = concept
        return "Switching to quiz mode."


def prewarm(proc: JobProcess):
    proc.userdata["vad"] = silero.VAD.load()


def get_tts_for_mode(mode: Optional[str]) -> murf.TTS:
    """Get the appropriate TTS voice for the given mode."""
    voice_map = {
        "learn": "en-US-matthew",  # Matthew for learn mode
        "quiz": "en-US-alicia",    # Alicia for quiz mode
        "teach_back": "en-US-ken", # Ken for teach back mode
    }
    voice = voice_map.get(mode, "en-US-matthew")  # Default to Matthew
    
    return murf.TTS(
        voice=voice,
        style="Conversation",
        tokenizer=tokenize.basic.SentenceTokenizer(min_sentence_len=2),
        text_pacing=True,
    )


class TutorAgent(Agent):
    """Unified agent that handles all three learning modes with dynamic voice switching."""
    
    def __init__(self, session: Optional[AgentSession] = None) -> None:
        content = load_content()
        concept_list = ", ".join([c["title"] for c in content])
        
        super().__init__(
            instructions=f"""You are an active recall learning coach. You help users learn programming concepts through three modes:
            
            1. **Learn mode** (Matthew's voice) - You explain concepts clearly using the summaries from the content file
            2. **Quiz mode** (Alicia's voice) - You ask questions to test understanding, using sample questions as inspiration
            3. **Teach back mode** (Ken's voice) - You ask users to explain concepts back to you and provide qualitative feedback
            
            Available concepts: {concept_list}
            
            **When a user first connects:**
            - Greet them warmly
            - Explain that you're an active recall learning coach
            - Explain the three learning modes (learn, quiz, teach back)
            - Ask which mode they'd like to try or which concept they want to learn about
            
            **In Learn mode (Matthew's voice):**
            - Explain concepts clearly using the summary from the content file
            - Use examples when helpful
            - Be encouraging and supportive
            - After explaining, you might suggest trying quiz mode or teach back mode
            
            **In Quiz mode (Alicia's voice):**
            - Ask questions about concepts, using sample questions as inspiration
            - Provide encouraging feedback on answers
            - If the user struggles, offer hints or suggest reviewing in learn mode
            - After a few questions, you might suggest trying teach back mode
            
            **In Teach back mode (Ken's voice):**
            - Ask users to explain concepts in their own words
            - Listen actively and provide qualitative feedback
            - Point out what they got right and what might need clarification
            - Be encouraging and supportive
            - If they struggle, suggest reviewing in learn mode first
            
            **Mode switching:**
            - Users can switch modes at any time by asking (e.g., "switch to quiz mode", "let me learn about variables", "quiz me on loops", "I want to teach you about functions")
            - When the user requests a mode change, you MUST call the switch_mode tool immediately
            - The switch_mode tool will automatically change the voice
            - Always acknowledge the mode switch clearly in your response
            
            **Detecting mode requests:**
            - "learn", "teach me", "explain" → learn mode
            - "quiz", "test me", "ask me questions" → quiz mode
            - "teach back", "let me explain", "I'll teach you" → teach back mode
            
            **Using content:**
            - Use get_concept_info to look up concept details when needed - this is especially important in learn mode
            - Use list_concepts to show available concepts
            - In learn mode, always use get_concept_info to get the summary before explaining
            
            Keep all responses natural and conversational since you're speaking. Avoid complex formatting.""",
        )
        self._session = session
        self._current_mode = None
        self._current_concept = None
    
    def set_session(self, session: AgentSession):
        """Set the session reference for TTS voice switching."""
        self._session = session
    
    @function_tool
    async def switch_mode(
        self,
        context: RunContext,
        mode: Annotated[str, "The mode to switch to: 'learn', 'quiz', or 'teach_back'"],
        concept: Annotated[Optional[str], "Optional concept to focus on"] = None,
    ) -> str:
        """Switch to a different learning mode. This will change the agent's voice and behavior.
        
        Args:
            mode: The mode to switch to ('learn', 'quiz', or 'teach_back')
            concept: Optional concept to focus on
        """
        if mode not in ["learn", "quiz", "teach_back"]:
            return f"Invalid mode: {mode}. Must be 'learn', 'quiz', or 'teach_back'."
        
        # Store mode in agent's internal state instead of context.session_state
        self._current_mode = mode
        self._current_concept = concept
        
        # Update TTS voice if session is available
        voice_updated = False
        if self._session and hasattr(self._session, 'tts'):
            try:
                new_tts = get_tts_for_mode(mode)
                # Try to update the TTS voice
                # Note: This may require LiveKit to support dynamic TTS updates
                self._session.tts = new_tts
                logger.info(f"Switched TTS voice to {new_tts.voice} for {mode} mode")
                voice_updated = True
            except Exception as e:
                logger.warning(f"Could not update TTS voice: {e}. Voice switching may not be supported.")
        
        mode_names = {
            "learn": "Learn mode with Matthew's voice",
            "quiz": "Quiz mode with Alicia's voice",
            "teach_back": "Teach back mode with Ken's voice",
        }
        
        result = f"Switched to {mode_names.get(mode, mode)}."
        if concept:
            result += f" Ready to focus on {concept}."
        if not voice_updated:
            result += " Note: Voice change may take effect on next response."
        
        return result
    
    @function_tool
    async def get_concept_info(
        self,
        context: RunContext,
        concept_identifier: Annotated[str, "The concept ID or title to look up"],
    ) -> str:
        """Get information about a specific concept from the content file.
        
        Args:
            concept_identifier: The concept ID (e.g., 'variables') or title
        """
        concept = get_concept_by_id(concept_identifier) or get_concept_by_title(concept_identifier)
        if concept:
            return f"Concept: {concept['title']}\nSummary: {concept['summary']}\nSample Question: {concept.get('sample_question', 'N/A')}"
        return f"Concept '{concept_identifier}' not found."
    
    @function_tool
    async def list_concepts(self, context: RunContext) -> str:
        """List all available concepts."""
        content = load_content()
        concepts = [f"- {c['title']} ({c['id']})" for c in content]
        return "Available concepts:\n" + "\n".join(concepts)


async def entrypoint(ctx: JobContext):
    # Logging setup
    ctx.log_context_fields = {
        "room": ctx.room.name,
    }

    # Create the unified tutor agent
    tutor_agent = TutorAgent()
    
    # Set up initial voice AI pipeline (start with Matthew's voice for orchestrator)
    session = AgentSession(
        stt=deepgram.STT(model="nova-3"),
        llm=google.LLM(model="gemini-2.5-flash"),
        tts=get_tts_for_mode(None),  # Start with default (Matthew)
        turn_detection=MultilingualModel(),
        vad=ctx.proc.userdata["vad"],
        preemptive_generation=True,
    )

    # Give the agent access to the session for TTS switching
    tutor_agent.set_session(session)

    # Metrics collection
    usage_collector = metrics.UsageCollector()

    @session.on("metrics_collected")
    def _on_metrics_collected(ev: MetricsCollectedEvent):
        metrics.log_metrics(ev.metrics)
        usage_collector.collect(ev.metrics)

    async def log_usage():
        summary = usage_collector.get_summary()
        logger.info(f"Usage: {summary}")

    ctx.add_shutdown_callback(log_usage)

    # Start the session
    await session.start(
        agent=tutor_agent,
        room=ctx.room,
        room_input_options=RoomInputOptions(
            noise_cancellation=noise_cancellation.BVC(),
        ),
    )

    # Join the room and connect to the user
    await ctx.connect()


if __name__ == "__main__":
    cli.run_app(WorkerOptions(entrypoint_fnc=entrypoint, prewarm_fnc=prewarm))
