import logging
import asyncio
import os
from datetime import datetime
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
    metrics
)
from livekit.agents.llm import function_tool
from livekit.agents.voice import MetricsCollectedEvent
from livekit.plugins import google, silero

logger = logging.getLogger("gemini-appointment-agent")
load_dotenv()

class GeminiAppointmentAgent(Agent):
    """AI agent for appointment confirmation using Gemini 2.5 Realtime API."""

    def __init__(self, appointment_details: Optional[Dict[str, Any]] = None) -> None:
        instructions = (
            "You are Farah, a friendly and professional appointment coordinator.\n"
            "You are multilingual and capable of switching from one language to another depending on what the person on the other end would like to speak.\n"
            "CRITICAL LANGUAGE RULES:\n"
            "1. ALWAYS begin the conversation in English, regardless of your language settings\n"
            "2. Continue speaking in English unless the user explicitly requests to speak in another language or starts speaking in another language\n"
            "3. When a user speaks in a different language or indicates they want to speak in a different language, switch to that language and stay in that language for the entire conversation unless they explicitly ask you to change languages again\n"
            "4. Do not switch back and forth between languages\n"
            "Your job is to call patients to confirm appointments, manage walk-in lists, and optimize scheduling."
        )
        self.appointment_details = appointment_details or {
            "date": "Tomorrow at 2:30pm",
            "service": "Consultation",
            "doctor": "Dr. Ahmed",
            "location": "Downtown Medical Center",
            "patient_name": "Andre Pemmelaar"
        }
        instructions += (
            f"\nCurrent appointment details:\n"
            f"- Patient Name: {self.appointment_details['patient_name']}\n"
            f"- Date & Time: {self.appointment_details['date']}\n"
            f"- Service: {self.appointment_details['service']}\n"
            f"- Doctor: {self.appointment_details['doctor']}\n"
            f"- Location: {self.appointment_details['location']}\n"
            f"Please confirm these details and do not change them."
        )

        super().__init__(
            instructions=instructions,
            # Use the beta.realtime API which is what we have
            llm=google.beta.realtime.RealtimeModel(
                model="gemini-2.5-flash-preview-native-audio-dialog",
                voice="Kore",          # Select preferred voice
                # language="en",       # Commented out - not working with our setup
            ),
            vad=silero.VAD.load(),
        )
        
        # Track conversation state
        self.confirmation_status = None
        self.walk_in_preferences = {}
        self.reminder_preferences = {}

    @function_tool
    async def confirm_appointment(self, context: RunContext) -> str:
        """Confirms the appointment when customer agrees."""
        logger.info("Appointment confirmed")
        self.confirmation_status = "confirmed"
        return (
            f"Your appointment is confirmed for {self.appointment_details['date']} for a {self.appointment_details['service']}. "
            "Is there anything else you'd like to ask about your appointment?"
        )

    @function_tool
    async def handle_reschedule_request(self, context: RunContext, urgency: str = "normal") -> str:
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
    async def handle_cancellation(self, context: RunContext, reason: Optional[str] = None) -> str:
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
    logger.info(f"Job received for room: {ctx.room.name if hasattr(ctx, 'room') else 'unknown'}")
    
    # Connect to room
    await ctx.connect()
    logger.info(f"Connected to room: {ctx.room.name}")
    
    appointment_details = {
        "date": "Tomorrow at 2:30pm",
        "service": "Consultation",
        "doctor": "Dr. Ahmed",
        "location": "Downtown Medical Center",
        "patient_name": "Andre Pemmelaar"
    }
    
    session = AgentSession()
    
    # Set up metrics collection
    usage_collector = metrics.UsageCollector()

    @session.on("metrics_collected")
    def _on_metrics_collected(ev: MetricsCollectedEvent):
        metrics.log_metrics(ev.metrics)
        usage_collector.collect(ev.metrics)

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
        room_input_options=RoomInputOptions(),
        room_output_options=RoomOutputOptions(transcription_enabled=True),
    )
    
    # Trigger initial greeting
    await session.generate_reply(instructions=(
        f"Please greet the patient and introduce yourself as Farah from Downtown Medical Center, "
        f"then confirm you're speaking with {appointment_details['patient_name']}."
    ))
    
    # Keep the session alive
    logger.info("Agent active and listening...")
    await asyncio.Event().wait()

if __name__ == "__main__":
    cli.run_app(WorkerOptions(
        entrypoint_fnc=entrypoint, 
        prewarm_fnc=prewarm
    ))