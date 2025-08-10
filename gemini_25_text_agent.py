import asyncio
import logging
import os
from dataclasses import dataclass
from typing import Optional, Dict, Any

from dotenv import load_dotenv
from livekit import agents, rtc
from livekit.agents import (
    Agent, 
    AgentSession, 
    JobContext, 
    WorkerOptions,
    cli,
    function_tool,
    llm
)
from livekit.plugins import google, openai, cartesia
from google.genai.types import Modality

# Load environment variables
load_dotenv()

# Configure logging
logger = logging.getLogger("appointment-agent")
logger.setLevel(logging.INFO)

@dataclass
class AppointmentDetails:
    """Data class to hold appointment information"""
    date: str
    service: str
    doctor: str
    location: str
    patient_name: str
    phone: Optional[str] = None
    email: Optional[str] = None

class AppointmentAgent(Agent):
    """Voice agent for appointment confirmation using Gemini 2.5 with text-only mode"""
    
    def __init__(self, appointment_details: Optional[Dict[str, Any]] = None, patient_name: str = "there"):
        # Default appointment details for testing
        self.appointment_details = appointment_details or {
            "date": "tomorrow at 2:30 PM",
            "service": "consultation",
            "doctor": "Dr. Ahmed",
            "location": "Downtown Medical Center",
            "patient_name": patient_name,
            "phone": "555-0123",
            "email": "patient@example.com"
        }
        
        # System instructions with injected appointment details
        instructions = f"""You are Farah, a friendly and professional appointment coordinator at {self.appointment_details['location']}. 

                        Your primary responsibilities are:
                        1. Confirm appointments with patients
                        2. Manage walk-in lists  
                        3. Optimize scheduling
                        4. Provide excellent customer service

                        Current appointment details:
                        - Patient: {self.appointment_details['patient_name']}
                        - Date: {self.appointment_details['date']}
                        - Service: {self.appointment_details['service']}
                        - Doctor: {self.appointment_details['doctor']}
                        - Location: {self.appointment_details['location']}

                        Guidelines:
                        - Always be warm and professional
                        - Confirm patient identity before discussing appointment details
                        - Offer to reschedule if there are conflicts
                        - Ask about transportation needs or special accommodations
                        - Provide clear instructions about preparation, arrival time, and what to bring
                        - Keep conversations focused but friendly
                        - If the patient needs to cancel or reschedule, gather their preferred alternative times

                        Remember to introduce yourself as Farah from {self.appointment_details['location']} and confirm you're speaking with {self.appointment_details['patient_name']}."""

        super().__init__(instructions=instructions)
        
        # Store session reference for tool functions
        self._session: Optional[AgentSession] = None
        
    def set_session(self, session: AgentSession):
        """Set the session reference for use in tool functions"""
        self._session = session

    @function_tool()
    async def confirm_appointment(self, confirmed: bool, notes: str = "") -> str:
        """
        Confirm or update appointment status
        
        Args:
            confirmed: Whether the patient confirmed the appointment
            notes: Any additional notes about the appointment
        """
        if confirmed:
            return f"Great! Your appointment with {self.appointment_details['doctor']} on {self.appointment_details['date']} is confirmed. We'll send you a reminder. Please arrive 15 minutes early."
        else:
            return "I understand you need to make changes. Let me help you find a better time that works for you."

    @function_tool()
    async def reschedule_appointment(self, preferred_date: str, preferred_time: str) -> str:
        """
        Handle appointment rescheduling
        
        Args:
            preferred_date: Patient's preferred new date
            preferred_time: Patient's preferred new time
        """
        # In a real implementation, this would check availability in a scheduling system
        return f"I'm checking our availability for {preferred_date} at {preferred_time}. I have an opening that day - would you like me to move your appointment from {self.appointment_details['date']} to {preferred_date} at {preferred_time}?"

    @function_tool()
    async def cancel_appointment(self, reason: str = "") -> str:
        """
        Handle appointment cancellation
        
        Args:
            reason: Optional reason for cancellation
        """
        return f"I've cancelled your appointment with {self.appointment_details['doctor']} on {self.appointment_details['date']}. You won't be charged any cancellation fee. Would you like me to put you on our waitlist for any earlier openings, or help you schedule a new appointment for a later date?"

    @function_tool()
    async def get_appointment_details(self) -> str:
        """Get current appointment information"""
        details = f"""Here are your current appointment details:
                        - Date: {self.appointment_details['date']}
                        - Service: {self.appointment_details['service']}
                        - Provider: {self.appointment_details['doctor']}
                        - Location: {self.appointment_details['location']}
                        - Contact: {self.appointment_details.get('phone', 'Not provided')}"""
        return details

    @function_tool()
    async def add_special_requests(self, request: str) -> str:
        """
        Add special requests or accommodations
        
        Args:
            request: Special accommodation or request
        """
        return f"I've noted your request: '{request}'. We'll make sure to accommodate this for your appointment on {self.appointment_details['date']}."

async def entrypoint(ctx: agents.JobContext):
    """Main entrypoint for the voice agent using Gemini 2.5 with text-only mode and separate TTS"""
    
    # Patient name can be customized - this could come from context or be set dynamically
    patient_name = os.getenv("PATIENT_NAME", "there")  # Default to "there" as requested
    
    # Appointment details can be injected here - could come from database, API, etc.
    appointment_details = {
        "date": os.getenv("APPOINTMENT_DATE", "tomorrow at 2:30 PM"),
        "service": os.getenv("APPOINTMENT_SERVICE", "consultation"),
        "doctor": os.getenv("APPOINTMENT_DOCTOR", "Dr. Ahmed"),
        "location": os.getenv("APPOINTMENT_LOCATION", "Downtown Medical Center"),
        "patient_name": patient_name,
        "phone": os.getenv("PATIENT_PHONE", "555-0123"),
        "email": os.getenv("PATIENT_EMAIL", "patient@example.com")
    }

    logger.info(f"Starting appointment agent for patient: {patient_name}")
    logger.info(f"Appointment details: {appointment_details}")

    # Create the appointment agent with custom details
    agent = AppointmentAgent(appointment_details=appointment_details, patient_name=patient_name)

    # Option 1: Use Gemini 2.5 Flash (standard model) with pipeline
    # This uses the regular Gemini API, not the Live API
    session = AgentSession(
        # Use standard Gemini 2.5 Flash model
        llm=google.LLM(
            model="gemini-2.5-flash",  # Standard Gemini 2.5 model
            temperature=0.7,
        ),
        # Use OpenAI TTS for voice output (or switch to Cartesia, Eleven Labs, etc.)
        tts=openai.TTS(
            model="tts-1",
            voice="nova",  # Female voice similar to Kora
            speed=1.0,
        ),
        # Use Google STT for speech input
        stt=google.STT(
            model="short",  # or "long" for better accuracy
            language="en-US",
        ),
    )
    
    # Alternative Option 2: Use Gemini Live API in text-only mode with separate TTS
    # Uncomment this section if you want to try text-only mode with Live API
    """
    session = AgentSession(
        # Use Gemini Live API but with text-only responses
        llm=google.beta.realtime.RealtimeModel(
            model="gemini-2.0-flash-exp",  # Live API model
            modalities=[Modality.TEXT],  # Text-only output
            temperature=0.7,
            instructions=agent.instructions,
        ),
        # Use a separate TTS provider for voice output
        tts=openai.TTS(
            model="tts-1",
            voice="nova",  # Female voice
            speed=1.0,
        ),
    )
    """
    
    # Set session reference in agent for tool functions
    agent.set_session(session)

    # Connect to the room
    await ctx.connect()

    # Start the session
    await session.start(
        room=ctx.room,
        agent=agent,
    )

    # Initial greeting with injected patient name
    greeting_instructions = f"Greet the caller professionally, introduce yourself as Farah from {appointment_details['location']}, and confirm you're speaking with {appointment_details['patient_name']}."
    
    await session.generate_reply(
        instructions=greeting_instructions
    )

    logger.info("Appointment confirmation agent is now running")

def set_patient_details(patient_name: str, appointment_details: Optional[Dict[str, Any]] = None):
    """
    Helper function to set patient details before running the agent
    This allows for dynamic injection of patient information
    """
    os.environ["PATIENT_NAME"] = patient_name
    
    if appointment_details:
        for key, value in appointment_details.items():
            env_key = f"APPOINTMENT_{key.upper()}" if key != "patient_name" else "PATIENT_NAME"
            if key == "phone":
                env_key = "PATIENT_PHONE" 
            elif key == "email":
                env_key = "PATIENT_EMAIL"
            os.environ[env_key] = str(value)

# Example of how to use the agent with custom patient details
def run_agent_for_patient(patient_name: str, appointment_details: Optional[Dict[str, Any]] = None):
    """
    Convenience function to run the agent with specific patient details
    
    Args:
        patient_name: Name of the patient to confirm appointment with
        appointment_details: Dictionary containing appointment information
    """
    # Set environment variables for this patient
    set_patient_details(patient_name, appointment_details)
    
    # Run the agent
    opts = agents.WorkerOptions(entrypoint_fnc=entrypoint)
    agents.cli.run_app(opts)

if __name__ == "__main__":
    # Example usage with default settings
    # You can customize these before running
    
    # Example 1: Default patient
    # agents.cli.run_app(agents.WorkerOptions(entrypoint_fnc=entrypoint))
    
    # Example 2: Specific patient with custom details
    custom_appointment = {
        "date": "Friday at 3:00 PM", 
        "service": "annual checkup",
        "doctor": "Dr. Sarah Johnson",
        "location": "Downtown Medical Center",
        "patient_name": "John Smith",
        "phone": "555-0987",
        "email": "john.smith@email.com"
    }
    
    run_agent_for_patient("John Smith", custom_appointment)