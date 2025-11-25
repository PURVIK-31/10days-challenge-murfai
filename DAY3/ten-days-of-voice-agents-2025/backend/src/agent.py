import logging
import json
import os
from datetime import datetime, timedelta
from typing import List, Dict, Any

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
    function_tool,
)
from livekit.plugins import murf, silero, google, deepgram, noise_cancellation
from livekit.plugins.turn_detector.multilingual import MultilingualModel

logger = logging.getLogger("agent")

load_dotenv(".env.local")

WELLNESS_LOG_PATH = "wellness_log.json"
TASKS_FILE_PATH = "wellness_tasks.json"
REMINDERS_FILE_PATH = "wellness_reminders.json"

class Assistant(Agent):
    def __init__(self, system_prompt: str) -> None:
        super().__init__(
            instructions=system_prompt,
        )

    @function_tool(description="Log the details of the wellness check-in.")
    def log_checkin(self, mood: str, objectives: str, summary: str):
        """Log the check-in details to the JSON file.
        
        Args:
            mood: The user's self-reported mood
            objectives: The user's stated objectives or intentions for the day  
            summary: A brief agent-generated summary of the conversation
        """
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

    @function_tool(description="Get a weekly reflection summary of mood trends and objectives completion.")
    def get_weekly_reflection(self, days: int = 7):
        """Analyze the wellness log to provide mood trends and goal completion insights.
        
        Args:
            days: Number of days to analyze (default 7)
        """
        logger.info(f"Generating weekly reflection for last {days} days")
        
        try:
            history = load_history()
            if not history:
                return "No check-in history available yet. Complete a few check-ins first to see weekly reflections."
            
            # Filter entries from the last N days
            cutoff_date = datetime.now() - timedelta(days=days)
            recent_entries = []
            
            for entry in history:
                try:
                    entry_date = datetime.fromisoformat(entry.get('timestamp', ''))
                    if entry_date >= cutoff_date:
                        recent_entries.append(entry)
                except (ValueError, TypeError):
                    continue
            
            if not recent_entries:
                return f"No check-ins found in the last {days} days."
            
            # Analyze mood trends
            moods = [entry.get('mood', 'unknown') for entry in recent_entries]
            mood_summary = f"Over the last {days} days, you've had {len(recent_entries)} check-ins. "
            mood_summary += f"Your mood has been: {', '.join(moods[:3])}" + ("..." if len(moods) > 3 else "")
            
            # Analyze objectives
            total_objectives = sum(1 for entry in recent_entries if entry.get('objectives'))
            objectives_summary = f"You set objectives on {total_objectives} out of {len(recent_entries)} days."
            
            return f"{mood_summary}. {objectives_summary}"
            
        except Exception as e:
            logger.error(f"Failed to generate weekly reflection: {e}")
            return "Unable to generate reflection at this time."

    @function_tool(description="Create a task based on user's objectives or goals.")
    def create_task(self, task_title: str, priority: str = "medium"):
        """Create a new task in the task management system.
        
        Args:
            task_title: Title or description of the task
            priority: Priority level: high, medium, or low (default: medium)
        """
        logger.info(f"Creating task: {task_title}")
        
        try:
            # Load existing tasks
            if os.path.exists(TASKS_FILE_PATH):
                with open(TASKS_FILE_PATH, "r") as f:
                    try:
                        tasks = json.load(f)
                    except json.JSONDecodeError:
                        tasks = []
            else:
                tasks = []
            
            # Create new task
            new_task = {
                "id": len(tasks) + 1,
                "title": task_title,
                "priority": priority,
                "status": "pending",
                "created_at": datetime.now().isoformat()
            }
            
            tasks.append(new_task)
            
            # Save tasks
            with open(TASKS_FILE_PATH, "w") as f:
                json.dump(tasks, f, indent=2)
            
            return f"Task created successfully: '{task_title}' with {priority} priority."
            
        except Exception as e:
            logger.error(f"Failed to create task: {e}")
            return "Failed to create task."

    @function_tool(description="Get a list of all tasks or pending tasks.")
    def get_tasks(self, status_filter: str = "pending"):
        """Retrieve tasks from the task management system.
        
        Args:
            status_filter: Filter by status: all, pending, or completed (default: pending)
        """
        logger.info(f"Retrieving {status_filter} tasks")
        
        try:
            if not os.path.exists(TASKS_FILE_PATH):
                return "No tasks found. Create some tasks first!"
            
            with open(TASKS_FILE_PATH, "r") as f:
                tasks = json.load(f)
            
            if not tasks:
                return "No tasks found."
            
            # Filter tasks
            if status_filter != "all":
                tasks = [t for t in tasks if t.get('status') == status_filter]
            
            if not tasks:
                return f"No {status_filter} tasks found."
            
            # Format task list
            task_list = f"You have {len(tasks)} {status_filter} task(s):\n"
            for task in tasks[:5]:  # Limit to 5 tasks to avoid long responses
                task_list += f"- {task.get('title')} ({task.get('priority')} priority)\n"
            
            if len(tasks) > 5:
                task_list += f"...and {len(tasks) - 5} more."
            
            return task_list
            
        except Exception as e:
            logger.error(f"Failed to retrieve tasks: {e}")
            return "Unable to retrieve tasks at this time."

    @function_tool(description="Mark a task as completed.")
    def complete_task(self, task_title: str):
        """Mark a task as completed.
        
        Args:
            task_title: Title of the task to mark as completed
        """
        logger.info(f"Completing task: {task_title}")
        
        try:
            if not os.path.exists(TASKS_FILE_PATH):
                return "No tasks found."
            
            with open(TASKS_FILE_PATH, "r") as f:
                tasks = json.load(f)
            
            # Find and update task
            task_found = False
            for task in tasks:
                if task_title.lower() in task.get('title', '').lower():
                    task['status'] = 'completed'
                    task['completed_at'] = datetime.now().isoformat()
                    task_found = True
                    break
            
            if not task_found:
                return f"Task '{task_title}' not found."
            
            # Save updated tasks
            with open(TASKS_FILE_PATH, "w") as f:
                json.dump(tasks, f, indent=2)
            
            return f"Task '{task_title}' marked as completed!"
            
        except Exception as e:
            logger.error(f"Failed to complete task: {e}")
            return "Failed to complete task."

    @function_tool(description="Create a reminder for a self-care activity or important task.")
    def create_reminder(self, activity: str, time: str):
        """Create a reminder for the user.
        
        Args:
            activity: The activity or task to be reminded about
            time: When the reminder should trigger (e.g., '6 pm', 'tomorrow morning')
        """
        logger.info(f"Creating reminder: {activity} at {time}")
        
        try:
            # Load existing reminders
            if os.path.exists(REMINDERS_FILE_PATH):
                with open(REMINDERS_FILE_PATH, "r") as f:
                    try:
                        reminders = json.load(f)
                    except json.JSONDecodeError:
                        reminders = []
            else:
                reminders = []
            
            # Create new reminder
            new_reminder = {
                "id": len(reminders) + 1,
                "activity": activity,
                "time": time,
                "created_at": datetime.now().isoformat(),
                "status": "active"
            }
            
            reminders.append(new_reminder)
            
            # Save reminders
            with open(REMINDERS_FILE_PATH, "w") as f:
                json.dump(reminders, f, indent=2)
            
            return f"Reminder created: '{activity}' at {time}. I'll help you remember!"
            
        except Exception as e:
            logger.error(f"Failed to create reminder: {e}")
            return "Failed to create reminder."


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
    
    Advanced Features:
    - You can provide weekly reflections by calling `get_weekly_reflection` when users ask about their mood trends or progress.
    - You can create tasks by calling `create_task` when users mention specific goals they want to accomplish.
    - You can retrieve tasks by calling `get_tasks` when users want to see their task list.
    - You can mark tasks complete by calling `complete_task` when users mention completing a goal.
    - You can create reminders by calling `create_reminder` when users mention wanting to remember something at a specific time.
    - Always confirm with the user before creating tasks or reminders.
    
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
