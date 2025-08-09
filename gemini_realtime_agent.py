import logging
import asyncio
import random
import os
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
from pathlib import Path
from dotenv import load_dotenv

from livekit.agents import (
    Agent,
    AgentSession,
    JobContext,
    JobProcess,
    RoomInputOptions,
    RoomOutputOptions,
    RunContext,
    WorkerOptions,
    cli,
    metrics,
)
from livekit.agents.llm import function_tool
from livekit.agents.voice import MetricsCollectedEvent
from livekit.plugins import google, silero

logger = logging.getLogger("gemini-appointment-agent")

load_dotenv()


class GeminiAppointmentAgent(Agent):
    """AI agent for appointment confirmation using Google Gemini Realtime API.
    
    This agent uses Gemini's multimodal realtime capabilities for more natural,
    context-aware conversations with lower latency than traditional pipelines.
    """
    
    def __init__(self, appointment_details: Optional[Dict[str, Any]] = None) -> None:
        # Load prompt from external markdown file
        prompt_path = Path(__file__).parent / "prompts" / "appointment_coordinator.md"
        
        # Check if custom prompt exists, otherwise use default
        if prompt_path.exists():
            with open(prompt_path, 'r') as f:
                instructions = f.read()
            logger.info(f"Loaded prompt from {prompt_path}")
        else:
            # Fallback to basic prompt if file doesn't exist
            instructions = """You are Sarah, a friendly and professional appointment coordinator. 
            Your job is to call patients to confirm appointments, manage walk-in lists, and optimize scheduling.
            Start by greeting the caller and confirming their appointment details."""
            logger.warning(f"Prompt file not found at {prompt_path}, using default prompt")
        
        super().__init__(
            instructions=instructions,
            # Use Gemini's Realtime Model for multimodal, low-latency interactions
            llm=google.beta.realtime.RealtimeModel(
                # Using native audio dialog model for better voice quality
                # model="gemini-2.5-flash-preview-native-audio-dialog",
                model="gemini-2.5-flash",
                voice="Kore",  # Female voice with Arabic accent capability
                # temperature=0.8,  # Higher for more natural variation
            ),
            # Voice Activity Detection for better turn-taking
            vad=silero.VAD.load(),
        )
        
        # Default appointment details for testing
        self.appointment_details = appointment_details or {
            "date": "tomorrow at 2:30 PM",
            "service": "consultation",
            "doctor": "Dr. Ahmed",
            "location": "Downtown Medical Center",
            "patient_name": "there",
        }
        
        # Track conversation state
        self.confirmation_status = None
        self.walk_in_preferences = {}
        self.reminder_preferences = {}
        self.clarification_attempts = 0

    # The Gemini Realtime model handles the greeting automatically based on the instructions
    # No need for an explicit on_enter method as it doesn't support session.say()

    @function_tool
    async def confirm_appointment(
        self, context: RunContext
    ) -> str:
        """Confirms the appointment when customer agrees."""
        logger.info("Appointment confirmed")
        self.confirmation_status = "confirmed"
        
        return (
            "Perfect! I have you confirmed. We'll see you "
            f"{self.appointment_details['date']} for your {self.appointment_details['service']}. "
            "Is there anything else you need to know about your appointment?"
        )

    @function_tool
    async def handle_conditional_confirmation(
        self, context: RunContext,
        condition: str,
        callback_time: Optional[str] = None
    ) -> str:
        """Handles conditional confirmations like 'call me back at 10:30 AM'."""
        logger.info(f"Conditional confirmation: {condition}, callback: {callback_time}")
        self.confirmation_status = "conditional"
        
        if callback_time:
            self.reminder_preferences['callback_time'] = callback_time
            return (
                f"I understand. I'll make a note to call you back "
                f"at {callback_time} to confirm your {self.appointment_details['date']} appointment. "
                "Is that the best number to reach you at?"
            )
        else:
            return (
                "I see you need to confirm later. "
                "What time would be best for me to call you back today?"
            )

    @function_tool
    async def capture_walk_in_availability(
        self, context: RunContext,
        availability_type: str,
        details: str
    ) -> str:
        """Captures walk-in customer availability for same-day openings."""
        logger.info(f"Walk-in availability: {availability_type} - {details}")
        
        self.walk_in_preferences = {
            'type': availability_type,
            'details': details,
            'captured_at': datetime.now().isoformat()
        }
        
        if availability_type == "flexible":
            return (
                f"That's perfect! So you're flexible and just need {details}. "
                "I've added you to our walk-in list. If we have any cancellations today, "
                "we'll call you right away. What's the best number to reach you?"
            )
        elif availability_type == "specific_times":
            return (
                f"Great! So you're available {details}. "
                "I've noted that down. If we get an opening during those times, "
                "we'll give you a call. Should we use this number?"
            )
        else:
            return (
                "Perfect! I've captured your availability. "
                "We'll call you as soon as we have an opening that works for you."
            )

    @function_tool
    async def set_reminder_preferences(
        self, context: RunContext,
        preference_type: str,
        timing: Optional[str] = None
    ) -> str:
        """Sets custom reminder preferences for the patient."""
        logger.info(f"Setting reminder preference: {preference_type} - {timing}")
        
        self.reminder_preferences = {
            'type': preference_type,
            'timing': timing,
            'set_at': datetime.now().isoformat()
        }
        
        if preference_type == "custom_time":
            return (
                f"Absolutely! I've made a note to call you {timing} "
                "before your appointment. We'll make sure to follow that preference."
            )
        elif preference_type == "no_reminder":
            return (
                "Perfect! I've noted that you don't need any more reminders. "
                f"We'll see you {self.appointment_details['date']}. Have a great day!"
            )
        else:
            return (
                "Got it! I've updated your reminder preferences. "
                "Is there anything else I can help you with today?"
            )

    @function_tool
    async def handle_reschedule_request(
        self, context: RunContext,
        urgency: str = "normal"
    ) -> str:
        """Handles rescheduling requests with immediate alternatives."""
        logger.info(f"Reschedule request with urgency: {urgency}")
        self.confirmation_status = "rescheduled"
        
        if urgency == "urgent":
            return (
                "I understand this is urgent. Let me check... "
                "I can see we have an opening later today at 4:30 PM, "
                "or tomorrow morning at 9:00 AM. Which would work better for you?"
            )
        else:
            return (
                "No problem at all! Let me check what we have available. "
                "I can offer you Thursday at 2:00 PM or Friday at 10:30 AM. "
                "Would either of those work?"
            )

    @function_tool
    async def handle_cancellation(
        self, context: RunContext,
        reason: Optional[str] = None
    ) -> str:
        """Handles cancellations and offers to reschedule."""
        logger.info(f"Cancellation request. Reason: {reason}")
        self.confirmation_status = "cancelled"
        
        return (
            "I understand, no problem at all. I'll cancel that appointment for you. "
            "Would you like me to help you find another time that works better, "
            "or would you prefer to call back later?"
        )


def prewarm(proc: JobProcess):
    """Preload heavy resources before job assignment."""
    proc.userdata["vad"] = silero.VAD.load()
    logger.info("VAD model preloaded")


async def entrypoint(ctx: JobContext):
    """Main entry point for the Gemini appointment agent."""
    logger.info(f"[ENTRYPOINT] Job received for room: {ctx.room.name if hasattr(ctx, 'room') else 'unknown'}")
    
    # Set context fields for logging
    ctx.log_context_fields = {
        "room": ctx.room.name,
    }
    
    # Connect to room
    await ctx.connect()
    logger.info(f"Connected to room: {ctx.room.name}")
    
    # In production, fetch from database based on room metadata
    appointment_details = {
        "date": "tomorrow at 2:30 PM",
        "service": "consultation",
        "doctor": "Dr. Ahmed",
        "location": "Downtown Medical Center",
        "patient_name": "Andre Pemmelaar",  # Will be injected from database later
    }

    # Create agent session - Gemini Realtime handles the voice pipeline internally
    session = AgentSession()
    
    # Set up metrics collection
    usage_collector = metrics.UsageCollector()

    @session.on("metrics_collected")
    def _on_metrics_collected(ev: MetricsCollectedEvent):
        metrics.log_metrics(ev.metrics)
        usage_collector.collect(ev.metrics)
        logger.info(f"[DEBUG] Metrics collected: {ev.metrics}")

    async def log_usage():
        summary = usage_collector.get_summary()
        logger.info(f"Usage: {summary}")

    ctx.add_shutdown_callback(log_usage)

    @session.on("function_called")
    def on_function_called(ev):
        logger.info(f"Tool called: {ev.function_name} with args: {ev.arguments}")

    # Start the session with Gemini agent
    logger.info("Starting Gemini appointment agent session...")
    agent = GeminiAppointmentAgent(appointment_details)
    
    await session.start(
        agent=agent,
        room=ctx.room,
        # Enable video if you want to use Gemini's multimodal capabilities
        room_input_options=RoomInputOptions(
            # video_enabled=True,  # Uncomment for video support
        ),
        room_output_options=RoomOutputOptions(
            transcription_enabled=True
        ),
    )
    
    # Trigger the proactive greeting after session starts
    logger.info("Triggering agent greeting...")
    # Use the patient name from appointment details
    patient_name = appointment_details.get("patient_name", "the patient")
    
    await session.generate_reply(
        instructions=f"Greet the caller professionally, introduce yourself as Farah from Downtown Medical Center, and confirm you're speaking with {patient_name}."
    )
    
    # Log final status
    logger.info(f"Call completed. Status: {agent.confirmation_status}")
    if agent.walk_in_preferences:
        logger.info(f"Walk-in preferences: {agent.walk_in_preferences}")
    if agent.reminder_preferences:
        logger.info(f"Reminder preferences: {agent.reminder_preferences}")


if __name__ == "__main__":
    cli.run_app(WorkerOptions(
        entrypoint_fnc=entrypoint,
        prewarm_fnc=prewarm
    ))