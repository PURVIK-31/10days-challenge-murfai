import logging

import json
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
    function_tool,
    RunContext
)
from livekit.plugins import murf, silero, google, deepgram, noise_cancellation
from livekit.plugins.turn_detector.multilingual import MultilingualModel

logger = logging.getLogger("agent")

load_dotenv(".env.local")


class Assistant(Agent):
    def __init__(self, room) -> None:
        super().__init__(
            instructions="""You are a friendly and efficient barista at "Java Joy", a premium coffee shop.
            Your goal is to take the customer's coffee order.
            
            You must collect the following information for every order:
            1. Drink Type (e.g., Latte, Cappuccino, Americano)
            2. Size (Small, Medium, Large)
            3. Milk Preference (Whole, Skim, Oat, Almond, Soy, None)
            4. Extras (e.g., Vanilla Syrup, Extra Shot, Whipped Cream, None)
            5. Customer Name

            Ask clarifying questions if any information is missing. Be polite and conversational.

            IMPORTANT: Whenever the customer provides or changes any order details (drink, size, milk, extras), you MUST immediately call the "update_order" tool to update the visual display. Do this even if the order is not yet complete.

            Once you have all the details, confirm the order with the customer.
            After confirmation, call the "submit_order" tool to save the order.
            """,
        )
        self.room = room

    @function_tool
    async def update_order(
        self,
        context: RunContext,
        drink_type: Annotated[str, "The type of coffee drink (e.g., Latte, Cappuccino)"],
        size: Annotated[str, "The size of the drink (Small, Medium, Large)"],
        milk: Annotated[str, "The type of milk (Whole, Skim, Oat, Almond, Soy, None)"],
        extras: Annotated[list[str], "List of extras (e.g., Vanilla Syrup, Whipped Cream)"],
    ):
        """
        Update the visual display of the order as the customer speaks. Call this whenever the customer changes or adds details to their order.
        """
        logger.info(f"Updating order preview: {size} {drink_type}")
        order_data = {
            "drinkType": drink_type,
            "size": size,
            "milk": milk,
            "extras": extras,
        }
        
        await self.room.local_participant.publish_data(
            json.dumps(order_data),
            topic="order_update"
        )
        return "Display updated."

    @function_tool
    async def submit_order(
        self,
        context: RunContext,
        drink_type: Annotated[str, "The type of coffee drink (e.g., Latte, Cappuccino)"],
        size: Annotated[str, "The size of the drink (Small, Medium, Large)"],
        milk: Annotated[str, "The type of milk (Whole, Skim, Oat, Almond, Soy, None)"],
        extras: Annotated[list[str], "List of extras (e.g., Vanilla Syrup, Whipped Cream)"],
        name: Annotated[str, "The customer's name"],
    ):
        """
        Submit the completed coffee order. Call this tool ONLY after collecting and confirming all order details.
        """
        logger.info(f"Submitting order for {name}: {size} {drink_type} with {milk} milk and {extras}")

        order_data = {
            "drinkType": drink_type,
            "size": size,
            "milk": milk,
            "extras": extras,
            "name": name,
        }

        try:
            with open("order.json", "w") as f:
                json.dump(order_data, f, indent=2)
            return "Order submitted successfully! Thank you for choosing Java Joy."
        except Exception as e:
            logger.error(f"Failed to save order: {e}")
            return "I'm sorry, there was an issue submitting your order. Please try again."


def prewarm(proc: JobProcess):
    proc.userdata["vad"] = silero.VAD.load()


async def entrypoint(ctx: JobContext):
    # Logging setup
    # Add any other context you want in all log entries here
    ctx.log_context_fields = {
        "room": ctx.room.name,
    }

    # Set up a voice AI pipeline using OpenAI, Cartesia, AssemblyAI, and the LiveKit turn detector
    session = AgentSession(
        # Speech-to-text (STT) is your agent's ears, turning the user's speech into text that the LLM can understand
        # See all available models at https://docs.livekit.io/agents/models/stt/
        stt=deepgram.STT(model="nova-3"),
        # A Large Language Model (LLM) is your agent's brain, processing user input and generating a response
        # See all available models at https://docs.livekit.io/agents/models/llm/
        llm=google.LLM(
            model="gemini-1.5-flash-001",
        ),
        # Text-to-speech (TTS) is your agent's voice, turning the LLM's text into speech that the user can hear
        # See all available models as well as voice selections at https://docs.livekit.io/agents/models/tts/
        tts=murf.TTS(
            voice="en-US-matthew", 
            style="Conversation",
            tokenizer=tokenize.basic.SentenceTokenizer(min_sentence_len=2),
            text_pacing=True
        ),
        # VAD and turn detection are used to determine when the user is speaking and when the agent should respond
        # See more at https://docs.livekit.io/agents/build/turns
        turn_detection=MultilingualModel(),
        vad=ctx.proc.userdata["vad"],
        # allow the LLM to generate a response while waiting for the end of turn
        # See more at https://docs.livekit.io/agents/build/audio/#preemptive-generation
        preemptive_generation=True,
    )

    # To use a realtime model instead of a voice pipeline, use the following session setup instead.
    # (Note: This is for the OpenAI Realtime API. For other providers, see https://docs.livekit.io/agents/models/realtime/))
    # 1. Install livekit-agents[openai]
    # 2. Set OPENAI_API_KEY in .env.local
    # 3. Add `from livekit.plugins import openai` to the top of this file
    # 4. Use the following session setup instead of the version above
    # session = AgentSession(
    #     llm=openai.realtime.RealtimeModel(voice="marin")
    # )

    # Metrics collection, to measure pipeline performance
    # For more information, see https://docs.livekit.io/agents/build/metrics/
    usage_collector = metrics.UsageCollector()

    @session.on("metrics_collected")
    def _on_metrics_collected(ev: MetricsCollectedEvent):
        metrics.log_metrics(ev.metrics)
        usage_collector.collect(ev.metrics)

    async def log_usage():
        summary = usage_collector.get_summary()
        logger.info(f"Usage: {summary}")

    ctx.add_shutdown_callback(log_usage)

    # # Add a virtual avatar to the session, if desired
    # # For other providers, see https://docs.livekit.io/agents/models/avatar/
    # avatar = hedra.AvatarSession(
    #   avatar_id="...",  # See https://docs.livekit.io/agents/models/avatar/plugins/hedra
    # )
    # # Start the avatar and wait for it to join
    # await avatar.start(session, room=ctx.room)

    # Start the session, which initializes the voice pipeline and warms up the models
    await session.start(
        agent=Assistant(ctx.room),
        room=ctx.room,
        room_input_options=RoomInputOptions(
            # For telephony applications, use `BVCTelephony` for best results
            noise_cancellation=noise_cancellation.BVC(),
        ),
    )

    # Join the room and connect to the user
    await ctx.connect()


if __name__ == "__main__":
    cli.run_app(WorkerOptions(entrypoint_fnc=entrypoint, prewarm_fnc=prewarm))
