import logging
import json
import os
from datetime import datetime
from typing import Annotated

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
    llm,
)
from livekit.plugins import murf, silero, google, deepgram, noise_cancellation
from livekit.plugins.turn_detector.multilingual import MultilingualModel

logger = logging.getLogger("agent")

load_dotenv(".env.local")

WELLNESS_LOG_PATH = "wellness_log.json"

class Assistant(Agent):
    def __init__(self, system_prompt: str) -> None:
        super().__init__(
            instructions=system_prompt,
        )

    @llm.ai_callable(description="Log the details of the wellness check-in.")
    def log_checkin(
        self,
        mood: Annotated[str, llm.TypeInfo(description="The user's self-reported mood")],
        objectives: Annotated[str, llm.TypeInfo(description="The user's stated objectives or intentions for the day")],
        summary: Annotated[str, llm.TypeInfo(description="A brief agent-generated summary of the conversation")]
    ):
        """Log the check-in details to the JSON file."""
        logger.info(f"Logging check-in: Mood={mood}, Objectives={objectives}")
        
        entry = {
            "timestamp": datetime.now().isoformat(),
            "mood": mood,
            "objectives": objectives,
            "summary": summary
        }
        
        try:
            if os.path.exists(WELLNESS_LOG_PATH):
                with open(WELLNESS_LOG_PATH, "r") as f:
                    try:
                        data = json.load(f)
                    except json.JSONDecodeError:
                        data = []
            else:
                data = []
            
            data.append(entry)
            
            with open(WELLNESS_LOG_PATH, "w") as f:
                json.dump(data, f, indent=2)
                
            return "Check-in logged successfully."
        except Exception as e:
            logger.error(f"Failed to log check-in: {e}")
            return "Failed to log check-in."


def load_history() -> list:
    if os.path.exists(WELLNESS_LOG_PATH):
        try:
            with open(WELLNESS_LOG_PATH, "r") as f:
                return json.load(f)
        except json.JSONDecodeError:
            return []
    return []

def generate_system_prompt() -> str:
    history = load_history()
    
    base_prompt = """You are a supportive, grounded Health & Wellness Voice Companion.
    Your goal is to conduct a short daily check-in with the user.
    
    You must:
    1. Ask about their mood and energy levels (e.g., "How are you feeling?", "What's your energy like?").
    2. Ask about their intentions or objectives for the day (e.g., "What are 1-3 things you'd like to get done?", "Any self-care plans?").
    3. Offer simple, realistic, non-medical advice or reflections based on what they say (e.g., "Break that big task into small steps", "Take a 5-minute walk").
    4. Close the check-in by briefly recapping their mood and objectives to confirm you understood.
    5. IMPORTANT: At the end of the conversation, you MUST call the `log_checkin` tool to save the session details.
    
    Guidelines:
    - Be friendly, empathetic, and concise.
    - Avoid medical diagnosis or claims.
    - Keep advice small and actionable.
    - Do not use complex formatting or emojis in your speech.
    - Keep the conversation natural and flowing.
    """
    
    if history:
        last_entry = history[-1]
        context_str = f"\n\nContext from previous check-in ({last_entry.get('timestamp')}):\n"
        context_str += f"- Previous Mood: {last_entry.get('mood')}\n"
        context_str += f"- Previous Objectives: {last_entry.get('objectives')}\n"
        context_str += f"- Previous Summary: {last_entry.get('summary')}\n"
        context_str += "\nUse this context to personalize your greeting (e.g., 'Last time you were feeling... how is it today?')."
        return base_prompt + context_str
    
    return base_prompt


def prewarm(proc: JobProcess):
    proc.userdata["vad"] = silero.VAD.load()


async def entrypoint(ctx: JobContext):
    # Logging setup
    ctx.log_context_fields = {
        "room": ctx.room.name,
    }

    system_prompt = generate_system_prompt()
    logger.info(f"System Prompt: {system_prompt}")

    # Set up a voice AI pipeline
    session = AgentSession(
        stt=deepgram.STT(model="nova-3"),
        llm=google.LLM(
            model="gemini-2.5-flash",
        ),
        tts=murf.TTS(
            voice="en-US-matthew", 
            style="Conversation",
            tokenizer=tokenize.basic.SentenceTokenizer(min_sentence_len=2),
            text_pacing=True
        ),
        turn_detection=MultilingualModel(),
        vad=ctx.proc.userdata["vad"],
        preemptive_generation=True,
    )

    usage_collector = metrics.UsageCollector()

    @session.on("metrics_collected")
    def _on_metrics_collected(ev: MetricsCollectedEvent):
        metrics.log_metrics(ev.metrics)
        usage_collector.collect(ev.metrics)

    async def log_usage():
        summary = usage_collector.get_summary()
        logger.info(f"Usage: {summary}")

    ctx.add_shutdown_callback(log_usage)

    await session.start(
        agent=Assistant(system_prompt=system_prompt),
        room=ctx.room,
        room_input_options=RoomInputOptions(
            noise_cancellation=noise_cancellation.BVC(),
        ),
    )

    await ctx.connect()


if __name__ == "__main__":
    cli.run_app(WorkerOptions(entrypoint_fnc=entrypoint, prewarm_fnc=prewarm))
