import logging
import asyncio
import os
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List
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
    AutoSubscribe,
    cli,
    metrics,
)
from livekit.agents.llm import function_tool
from livekit.agents.voice import MetricsCollectedEvent
from livekit.plugins import google, silero
from livekit import rtc, api

logger = logging.getLogger("enhanced-gemini-sip-agent")

# Load environment variables
load_dotenv()

class EnhancedGeminiSIPAgent(Agent):
    """Enhanced Gemini agent with SIP telephony support."""
    
    def __init__(
        self, 
        appointment_details: Optional[Dict[str, Any]] = None,
        is_sip_connection: bool = False,
        sip_participant_attrs: Optional[Dict[str, str]] = None
    ) -> None:
        # Load prompt from external markdown file
        prompt_path = Path(__file__).parent / "prompts" / "appointment_coordinator.md"
        
        if prompt_path.exists():
            with open(prompt_path, 'r') as f:
                instructions = f.read()
            logger.info(f"Loaded prompt from {prompt_path}")
        else:
            # Fallback prompt if file doesn't exist
            instructions = """You are Farah, a friendly and professional appointment coordinator. 
            Your job is to call patients to confirm appointments, manage walk-in lists, and optimize scheduling.
            Start by greeting the caller and confirming their appointment details."""
            logger.warning(f"Prompt file not found at {prompt_path}, using default prompt")
        
        # Inject appointment details
        self.appointment_details = appointment_details or {
            "date": "tomorrow at 2:30 PM",
            "service": "consultation",
            "doctor": "Dr. Ahmed",
            "location": "Downtown Medical Center",
            "patient_name": "there",
        }
        
        # Store connection type and SIP attributes
        self.is_sip_connection = is_sip_connection
        self.sip_attrs = sip_participant_attrs or {}
        
        # Modify instructions based on connection type
        if is_sip_connection:
            instructions += f"""
## Connection Context:
- This is a telephone call through SIP
- Caller's phone number: {self.sip_attrs.get('sip.phoneNumber', 'Unknown')}
- Call ID: {self.sip_attrs.get('sip.callID', 'Unknown')}

## Telephony Behavior:
- Be extra clear in speech as audio quality may vary
- Confirm information by repeating important details
- Ask for verbal confirmation rather than visual cues
- Handle potential line noise or connection issues gracefully
"""
        else:
            instructions += """
## Connection Context:
- This is a web-based interaction
- User can see visual elements and typed responses
- Standard web interaction patterns apply
"""
        
        instructions += f"""
## Current Appointment Details:
- Patient Name: {self.appointment_details['patient_name']}
- Date and Time: {self.appointment_details['date']}
- Service: {self.appointment_details['service']}
- Doctor: {self.appointment_details['doctor']}
- Location: {self.appointment_details['location']}

You are calling to confirm THIS SPECIFIC appointment. Do not make up different dates or times."""
        
        # Initialize parent Agent class with appropriate language for connection type
        super().__init__(
            instructions=instructions,
            llm=google.beta.realtime.RealtimeModel(
                model="gemini-2.0-flash-live-001",
                voice="Kore",
                # Use English for SIP calls for better compatibility, Arabic for web
                language="en-US" if is_sip_connection else "ar-XA",
                temperature=0.8,
            ),
            vad=silero.VAD.load(),
        )
        
        # Track conversation state
        self.confirmation_status = None
        self.walk_in_preferences = {}
        self.reminder_preferences = {}
        self.clarification_attempts = 0

    @function_tool
    async def confirm_appointment(
        self, 
        context: RunContext
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
        self, 
        context: RunContext,
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
        self, 
        context: RunContext,
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
        self, 
        context: RunContext,
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
        self, 
        context: RunContext,
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
        self, 
        context: RunContext,
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


def detect_sip_participant(participant: rtc.RemoteParticipant) -> tuple[bool, Dict[str, str]]:
    """Detect if participant is from SIP and extract attributes."""
    is_sip = participant.kind == rtc.ParticipantKind.SIP
    sip_attrs = {}
    
    if is_sip:
        # Extract SIP-specific attributes
        for key, value in participant.attributes.items():
            if key.startswith("sip."):
                sip_attrs[key] = value
    
    return is_sip, sip_attrs


def get_appointment_by_phone(phone_number: str) -> Dict[str, Any]:
    """
    Look up appointment details by phone number.
    Replace this with your actual database lookup logic.
    """
    # Mock implementation - replace with real database lookup
    mock_appointments = {
        "+1234567890": {
            "date": "tomorrow at 2:30 PM",
            "service": "consultation",
            "doctor": "Dr. Ahmed",
            "location": "Downtown Medical Center",
            "patient_name": "John Smith",
        },
        "+971585089156": {  # Your number from the image
            "date": "tomorrow at 3:00 PM",
            "service": "follow-up consultation",
            "doctor": "Dr. Sarah",
            "location": "Downtown Medical Center",
            "patient_name": "Andre Pemmelaar",
        }
    }
    
    return mock_appointments.get(phone_number, {
        "date": "your upcoming appointment",
        "service": "consultation",
        "doctor": "one of our doctors",
        "location": "our medical center",
        "patient_name": "there",
    })


def prewarm(proc: JobProcess):
    """Preload heavy resources before job assignment."""
    proc.userdata["vad"] = silero.VAD.load()
    logger.info("VAD model preloaded")


async def entrypoint(ctx: JobContext):
    """Enhanced entrypoint supporting both web and SIP connections."""
    logger.info(f"[ENTRYPOINT] Job received for room: {ctx.room.name if hasattr(ctx, 'room') else 'unknown'}")
    
    # Set context fields for logging
    ctx.log_context_fields = {
        "room": ctx.room.name,
    }
    
    # Connect to room with audio-only subscription for SIP compatibility
    await ctx.connect(auto_subscribe=AutoSubscribe.AUDIO_ONLY)
    logger.info(f"Connected to room: {ctx.room.name}")
    
    # Wait for a participant to join
    participant = await ctx.wait_for_participant()
    
    # Detect if this is a SIP connection
    is_sip, sip_attrs = detect_sip_participant(participant)
    
    logger.info(f"Participant joined: {participant.identity}, SIP: {is_sip}")
    if is_sip:
        logger.info(f"SIP attributes: {sip_attrs}")
    
    # Determine appointment details based on connection type
    if is_sip and 'sip.phoneNumber' in sip_attrs:
        # Look up appointment by phone number for SIP calls
        appointment_details = get_appointment_by_phone(sip_attrs['sip.phoneNumber'])
        logger.info(f"Loaded appointment for phone: {sip_attrs['sip.phoneNumber']}")
    else:
        # Default appointment details for web connections
        appointment_details = {
            "date": "tomorrow at 2:30 PM",
            "service": "consultation",
            "doctor": "Dr. Ahmed",
            "location": "Downtown Medical Center",
            "patient_name": "Andre Pemmelaar",
        }
    
    # Create agent session
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
    
    # Set up error handling
    @session.on("error")
    def handle_error(event):
        logger.error(f"Session error: {event.error}")
        if is_sip:
            # For SIP calls, try to gracefully handle errors
            asyncio.create_task(session.generate_reply(
                instructions="I apologize, there seems to be a technical issue. Please call us back or we'll try reaching you again shortly."
            ))
    
    # Setup DTMF handling for SIP connections
    if is_sip:
        @ctx.room.on("sip_dtmf_received")
        def handle_dtmf(dtmf_event: rtc.SipDTMF):
            """Handle DTMF signals from SIP participants."""
            logger.info(f"DTMF received: {dtmf_event.digit} from {dtmf_event.participant.identity}")
            
            # Handle common DTMF patterns
            digit = dtmf_event.digit
            if digit == "1":
                asyncio.create_task(session.generate_reply(
                    instructions="The caller pressed 1. Confirm their appointment."
                ))
            elif digit == "2":
                asyncio.create_task(session.generate_reply(
                    instructions="The caller pressed 2. Offer to reschedule their appointment."
                ))
            elif digit == "0":
                asyncio.create_task(session.generate_reply(
                    instructions="The caller pressed 0. Offer to transfer them to an operator."
                ))
    
    # Create enhanced agent with SIP support
    logger.info("Starting Enhanced Gemini SIP agent session...")
    agent = EnhancedGeminiSIPAgent(
        appointment_details=appointment_details,
        is_sip_connection=is_sip,
        sip_participant_attrs=sip_attrs
    )
    
    await session.start(
        agent=agent,
        room=ctx.room,
        room_input_options=RoomInputOptions(
            # video_enabled=False for SIP compatibility
        ),
        room_output_options=RoomOutputOptions(
            transcription_enabled=True
        ),
    )
    
    # Generate appropriate greeting based on connection type
    patient_name = appointment_details.get("patient_name", "the patient")
    
    if is_sip:
        caller_number = sip_attrs.get('sip.phoneNumber', 'this number')
        greeting_instruction = f"""
        Greet the caller professionally as Farah from Downtown Medical Center.
        Confirm you're speaking with {patient_name} and that you're calling about their appointment.
        Be warm but efficient since this is a phone call.
        """
    else:
        greeting_instruction = f"""
        Greet the caller professionally, introduce yourself as Farah from Downtown Medical Center, 
        and confirm you're speaking with {patient_name}.
        """
    
    await session.generate_reply(instructions=greeting_instruction)
    
    # Keep the session alive
    await asyncio.Event().wait()
    
    # Log final status
    logger.info(f"Call completed. Status: {agent.confirmation_status}")
    if agent.walk_in_preferences:
        logger.info(f"Walk-in preferences: {agent.walk_in_preferences}")
    if agent.reminder_preferences:
        logger.info(f"Reminder preferences: {agent.reminder_preferences}")


if __name__ == "__main__":
    cli.run_app(WorkerOptions(
        entrypoint_fnc=entrypoint,
        prewarm_fnc=prewarm,
        # Set explicit agent name for dispatch targeting
        agent_name="gemini-sip-agent"
    ))