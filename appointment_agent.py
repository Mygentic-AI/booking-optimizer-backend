import logging
import asyncio
import random
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List
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

logger = logging.getLogger("appointment-agent")

load_dotenv()


class AppointmentOptimizationAgent(Agent):
    """AI agent for appointment confirmation and schedule optimization."""
    
    def __init__(self, appointment_details: Optional[Dict[str, Any]] = None) -> None:
        super().__init__(
            instructions="""You are a friendly, professional AI assistant named Sarah from a medical clinic. 
            Your job is to call patients to confirm appointments, manage walk-in lists, and optimize scheduling.
            
            IMPORTANT CONVERSATIONAL BEHAVIORS:
            - Use natural filler phrases when thinking: "um", "let me see", "one moment"
            - Include acknowledgment sounds when listening: "mm-hmm", "I see", "got it"
            - Vary your responses to avoid sounding scripted
            - Add brief pauses using <break time="0.5s"/> when "looking up" information
            - Speak at a normal, conversational pace
            
            THREE CORE FUNCTIONS:
            1. PROACTIVE CONFIRMATIONS (10 AM - 12 PM for next day):
               - Call to confirm tomorrow's appointments
               - Handle nuanced responses like "check back at 10:30 AM to confirm my 2 PM appointment"
               - Note any special reminder preferences
            
            2. SMART WALK-IN MANAGEMENT:
               - When someone can't get an appointment, capture their flexibility
               - Track "I'm shopping in the mall, 10 minutes notice" type availability
               - Record "Give me an hour's notice, free at these times" preferences
            
            3. PERSONALIZED REMINDERS:
               - Honor custom requests like "Call me 1 hour before"
               - Respect "Don't call again, I'm definitely coming"
               - Track individual preferences for future appointments
            
            CONVERSATION APPROACH:
            - Start with a warm greeting and clearly identify yourself and your purpose
            - Be flexible and capture complex availability patterns
            - If they need to reschedule, offer alternatives immediately
            - Always sound natural and human-like, never robotic
            
            ERROR RECOVERY:
            - If you don't understand, use natural phrases like "Sorry, could you repeat that?"
            - If still unclear after 2 attempts, try rephrasing your question
            - Never give up - keep trying different approaches
            
            Remember: You're helping optimize the clinic's schedule while providing excellent customer service."""
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
        
        # Natural response variations
        self.greetings = [
            "Good {time_of_day}! This is Sarah from {location}.",
            "Hi there! This is Sarah calling from {location}.",
            "Hello! Sarah here from {location}.",
        ]
        
        self.confirmations = [
            "Perfect! I have you confirmed.",
            "Excellent! You're all set.",
            "Great! I've confirmed your appointment.",
            "Wonderful! You're confirmed.",
        ]
        
        self.fillers = [
            "um",
            "let me see",
            "one moment",
            "let me check that",
            "just a second",
        ]

    async def on_enter(self):
        """Called when agent first joins the call."""
        # Small delay to simulate picking up the phone naturally
        await asyncio.sleep(0.8)
        
        # Get time of day for natural greeting
        hour = datetime.now().hour
        time_of_day = "morning" if hour < 12 else "afternoon" if hour < 17 else "evening"
        
        # Choose random greeting template
        greeting_template = random.choice(self.greetings)
        greeting = greeting_template.format(
            time_of_day=time_of_day,
            location=self.appointment_details['location']
        )
        
        # Add appointment confirmation request
        greeting += f""" <break time="0.3s"/> I'm calling to confirm your appointment with {self.appointment_details['doctor']} 
        {self.appointment_details['date']} for your {self.appointment_details['service']}. 
        <break time="0.5s"/> Are you still able to make it?"""
        
        # Use the session to speak the greeting
        await self.session.say(greeting)

    @function_tool
    async def confirm_appointment(
        self, context: RunContext
    ) -> str:
        """Confirms the appointment when customer agrees."""
        logger.info("Appointment confirmed")
        self.confirmation_status = "confirmed"
        
        confirmation = random.choice(self.confirmations)
        return (
            f"{confirmation} <break time='0.3s'/> We'll see you "
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
        
        filler = random.choice(self.fillers)
        
        if callback_time:
            self.reminder_preferences['callback_time'] = callback_time
            return (
                f"{filler}... <break time='0.5s'/> I understand. I'll make a note to call you back "
                f"at {callback_time} to confirm your {self.appointment_details['date']} appointment. "
                "Is that the best number to reach you at?"
            )
        else:
            return (
                f"{filler}... <break time='0.3s'/> I see you need to confirm later. "
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
        
        filler = random.choice(self.fillers)
        
        if availability_type == "flexible":
            return (
                f"{filler}... <break time='0.5s'/> That's perfect! So you're flexible and just need "
                f"{details}. I've added you to our walk-in list. If we have any cancellations today, "
                "we'll call you right away. What's the best number to reach you?"
            )
        elif availability_type == "specific_times":
            return (
                f"Great! <break time='0.3s'/> So you're available {details}. "
                "I've noted that down. If we get an opening during those times, "
                "we'll give you a call. Should we use this number?"
            )
        else:
            return (
                f"{filler}... Perfect! I've captured your availability. "
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
                f"Absolutely! <break time='0.3s'/> I've made a note to call you {timing} "
                "before your appointment. We'll make sure to follow that preference."
            )
        elif preference_type == "no_reminder":
            return (
                "Perfect! <break time='0.3s'/> I've noted that you don't need any more reminders. "
                f"We'll see you {self.appointment_details['date']}. Have a great day!"
            )
        else:
            return (
                f"Got it! <break time='0.3s'/> I've updated your reminder preferences. "
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
        
        filler = random.choice(self.fillers)
        
        if urgency == "urgent":
            return (
                f"I understand this is urgent. <break time='0.3s'/> {filler}... "
                "I can see we have an opening later today at 4:30 PM, "
                "or tomorrow morning at 9:00 AM. Which would work better for you?"
            )
        else:
            return (
                f"No problem at all! <break time='0.3s'/> {filler}... "
                "Let me check what we have available. I can offer you "
                "Thursday at 2:00 PM or Friday at 10:30 AM. Would either of those work?"
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
            "I understand, no problem at all. <break time='0.3s'/> "
            "I'll cancel that appointment for you. Would you like me to help you "
            "find another time that works better, or would you prefer to call back later?"
        )

    @function_tool
    async def clarify_appointment_details(
        self, context: RunContext,
        detail_type: str
    ) -> str:
        """Provides clarification about appointment details."""
        logger.info(f"Clarifying {detail_type}")
        
        filler = random.choice(self.fillers)
        
        if detail_type == "time" or detail_type == "date":
            return f"{filler}... Your appointment is scheduled for {self.appointment_details['date']}."
        elif detail_type == "location":
            return f"Your appointment is at {self.appointment_details['location']}."
        elif detail_type == "service":
            return f"You're scheduled for a {self.appointment_details['service']} with {self.appointment_details['doctor']}."
        elif detail_type == "doctor":
            return f"Your appointment is with {self.appointment_details['doctor']}."
        else:
            return (
                f"{filler}... <break time='0.5s'/> Let me give you all the details. "
                f"You have a {self.appointment_details['service']} "
                f"with {self.appointment_details['doctor']} at {self.appointment_details['location']} "
                f"{self.appointment_details['date']}."
            )

    @function_tool
    async def handle_wrong_person(
        self, context: RunContext,
        requested_person: Optional[str] = None
    ) -> str:
        """Handles when the wrong person answers."""
        logger.info(f"Wrong person answered, looking for: {requested_person}")
        
        if requested_person:
            return (
                f"Oh, I apologize! <break time='0.3s'/> I'm looking for {requested_person}. "
                f"This is Sarah from {self.appointment_details['location']} calling about "
                "their appointment. Are they available?"
            )
        else:
            return (
                "I apologize for the confusion. <break time='0.3s'/> "
                f"I'm calling from {self.appointment_details['location']} about an appointment "
                f"{self.appointment_details['date']}. May I ask who I'm speaking with?"
            )


def prewarm(proc: JobProcess):
    """Preload heavy resources before job assignment."""
    proc.userdata["vad"] = silero.VAD.load()
    logger.info("VAD model preloaded")


async def entrypoint(ctx: JobContext):
    """Main entry point for the appointment optimization agent."""
    ctx.log_context_fields = {
        "room": ctx.room.name,
    }
    
    await ctx.connect()
    logger.info(f"Connected to room: {ctx.room.name}")

    # In production, fetch from database based on room metadata
    appointment_details = {
        "date": "tomorrow at 2:30 PM",
        "service": "consultation",
        "doctor": "Dr. Ahmed",
        "location": "Downtown Medical Center",
        "patient_name": "there",
    }

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

    # Set up metrics collection
    usage_collector = metrics.UsageCollector()

    @session.on("metrics_collected")
    def _on_metrics_collected(ev: MetricsCollectedEvent):
        metrics.log_metrics(ev.metrics)
        usage_collector.collect(ev.metrics)

    async def log_usage():
        summary = usage_collector.get_summary()
        logger.info(f"Usage summary: {summary}")

    ctx.add_shutdown_callback(log_usage)

    @session.on("function_called")
    def on_function_called(ev):
        logger.info(f"Tool called: {ev.function_name} with args: {ev.arguments}")

    # Start the session
    agent = AppointmentOptimizationAgent(appointment_details)
    await session.start(
        agent=agent,
        room=ctx.room,
        room_input_options=RoomInputOptions(),
        room_output_options=RoomOutputOptions(
            transcription_enabled=True
        ),
    )

    # Log final status and captured preferences
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