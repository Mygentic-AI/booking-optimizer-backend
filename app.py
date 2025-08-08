import asyncio
import logging
import json
from datetime import datetime
from typing import Optional, Dict, Any

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
from livekit.plugins import deepgram, openai, silero
from livekit.plugins.turn_detector.multilingual import MultilingualModel

# Import appointment agent
from appointment_agent import AppointmentOptimizationAgent

# uncomment to enable Krisp background voice/noise cancellation
# from livekit.plugins import noise_cancellation

logger = logging.getLogger("appointment-optimizer")

load_dotenv()


async def fetch_appointment_details(room_name: str) -> Dict[str, Any]:
    """
    Fetch appointment details from database or API.
    In production, this would query your appointment system.
    
    Args:
        room_name: Room identifier to fetch appointment for
        
    Returns:
        Appointment details dictionary
    """
    # Mock data for testing - replace with actual database query
    # In production, use room_name to query your appointment system
    return {
        "date": "tomorrow at 2:30 PM",
        "service": "consultation", 
        "doctor": "Dr. Ahmed",
        "location": "Downtown Medical Center",
        "patient_name": "John Smith",
        "patient_phone": "+1234567890"
    }


class CallLogger:
    """Simple call logger - creates a new log file for each appointment confirmation call"""
    def __init__(self, room_name: str):
        self.room_name = room_name
        self.call_log = []
        
        # Create a unique log file for this session
        import os
        os.makedirs("logs", exist_ok=True)
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        log_filename = f"logs/appointment_call_{room_name}_{timestamp}.log"
        
        # Set up logger for this session
        self.session_logger = logging.getLogger(f"appointment_{room_name}_{timestamp}")
        self.session_logger.setLevel(logging.INFO)
        
        # Create file handler
        file_handler = logging.FileHandler(log_filename)
        file_handler.setFormatter(logging.Formatter('%(asctime)s - %(message)s'))
        self.session_logger.addHandler(file_handler)
        
        # Log session start
        self.session_logger.info(f"[session_start] Room: {room_name}")
        logger.info(f"Started new appointment call log: {log_filename}")
        
    def log_event(self, event_type: str, content: str, participant: str = ""):
        """Log a call event"""
        entry = {
            "timestamp": datetime.now().isoformat(),
            "type": event_type,
            "participant": participant,
            "content": content
        }
        self.call_log.append(entry)
        
        # Log to session-specific file
        self.session_logger.info(f"[{event_type}] {participant}: {content}")
        logger.info(f"[CALL LOG] [{event_type}] {participant}: {content}")
        
    def save_call_summary(self):
        """Save call summary with appointment status"""
        if self.call_log:
            import os
            os.makedirs("call_summaries", exist_ok=True)
            
            filename = f"call_summaries/summary_{self.room_name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            with open(filename, 'w') as f:
                json.dump({
                    "room": self.room_name,
                    "call_log": self.call_log
                }, f, indent=2)
            logger.info(f"Saved call summary to {filename}")


def prewarm(proc: JobProcess):
    """Preload heavy resources before job assignment"""
    proc.userdata["vad"] = silero.VAD.load()
    logger.info("VAD model preloaded")


async def entrypoint(ctx: JobContext):
    """Main entry point for the appointment optimization agent"""
    logger.info(f"[ENTRYPOINT] Job received for room: {ctx.room.name if hasattr(ctx, 'room') else 'unknown'}")
    
    # Set context fields for logging
    ctx.log_context_fields = {
        "room": ctx.room.name,
    }
    
    # Connect to room
    await ctx.connect()
    logger.info(f"Connected to room: {ctx.room.name}")
    
    # Initialize call logger
    call_logger = CallLogger(ctx.room.name)
    call_logger.log_event("room_joined", f"Agent joined room {ctx.room.name}", "agent")
    
    # Fetch appointment details (in production, this would query your database)
    appointment_details = await fetch_appointment_details(ctx.room.name)
    logger.info(f"Fetched appointment details: {appointment_details}")
    
    # Create agent session with optimized voice pipeline
    session = AgentSession(
        vad=ctx.proc.userdata["vad"],
        stt=deepgram.STT(
            model="nova-3",
            language="multi",
            smart_format=True,
            punctuate=True,
            interim_results=True,
        ),
        llm=openai.LLM(
            model="gpt-4o-mini",
            temperature=0.8,  # Higher for natural variation
        ),
        tts=openai.TTS(
            voice="nova",  # Most natural female voice
            speed=1.0,
        ),
        turn_detection=MultilingualModel(),
    )

    # Add event handlers for logging
    logger.info("Setting up event handlers...")
    
    # Monitor agent state changes
    @session.on("agent_state_changed")
    def on_agent_state_changed(state):
        logger.info(f"[DEBUG] Agent state changed: {state}")
        call_logger.log_event("debug", f"Agent state: {state}", "system")
    
    # Monitor user state changes
    @session.on("user_state_changed")
    def on_user_state_changed(state):
        logger.info(f"[DEBUG] User state changed: {state}")
        call_logger.log_event("debug", f"User state: {state}", "system")
    
    # Capture user speech transcriptions
    @session.on("user_input_transcribed")
    def on_user_input_transcribed(event):
        """Capture user speech as it's transcribed"""
        asyncio.create_task(handle_user_input_transcribed(event))
    
    async def handle_user_input_transcribed(event):
        try:
            text = event.transcript
            participant = getattr(event.participant, "identity", "user") if hasattr(event, "participant") else "user"
            call_logger.log_event("user_transcript", text, participant)
            logger.info(f"[TRANSCRIPT] User said: {text}")
        except Exception as e:
            logger.error(f"Error in user_input_transcribed handler: {e}")

    # Capture finalized conversation items
    @session.on("conversation_item_added")
    def on_conversation_item_added(event):
        """Capture finalized conversation turns from both user and agent"""
        asyncio.create_task(handle_conversation_item_added(event))
    
    async def handle_conversation_item_added(event):
        try:
            item = event.item
            role = getattr(item, "role", "unknown")
            text_content = getattr(item, "text_content", "")
            
            if not text_content:
                text_content = getattr(item, "content", "")
            if not text_content:
                text_content = getattr(item, "text", "")
                
            participant = "agent" if role == "assistant" else "user"
            
            call_logger.log_event("conversation", text_content, participant)
            logger.info(f"[TRANSCRIPT] {participant} said: {text_content}")
                
        except Exception as e:
            logger.error(f"Error in conversation_item_added handler: {e}")

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

    # Add call summary saving on shutdown
    async def save_call_summary():
        call_logger.save_call_summary()
    
    # Shutdown callbacks
    ctx.add_shutdown_callback(log_usage)
    ctx.add_shutdown_callback(save_call_summary)

    # Log room events
    @ctx.room.on("participant_connected")
    def on_participant_connected(participant):
        call_logger.log_event("participant_connected", f"{participant.identity} joined", participant.identity)
    
    @ctx.room.on("participant_disconnected")
    def on_participant_disconnected(participant):
        call_logger.log_event("participant_disconnected", f"{participant.identity} left", participant.identity)

    # Log function tool usage
    @session.on("function_called")
    def on_function_called(ev):
        logger.info(f"Tool called: {ev.function_name} with args: {ev.arguments}")

    # Start the session with the appointment agent
    logger.info("Starting appointment agent session...")
    agent = AppointmentOptimizationAgent(appointment_details)
    
    await session.start(
        agent=agent,
        room=ctx.room,
        room_input_options=RoomInputOptions(
            # uncomment to enable Krisp BVC noise cancellation
            # noise_cancellation=noise_cancellation.BVC(),
        ),
        room_output_options=RoomOutputOptions(transcription_enabled=True),
    )
    
    # Log final status
    logger.info(f"Call completed. Status: {agent.confirmation_status}")
    if agent.walk_in_preferences:
        logger.info(f"Walk-in preferences: {agent.walk_in_preferences}")
    if agent.reminder_preferences:
        logger.info(f"Reminder preferences: {agent.reminder_preferences}")


if __name__ == "__main__":
    cli.run_app(WorkerOptions(entrypoint_fnc=entrypoint, prewarm_fnc=prewarm))