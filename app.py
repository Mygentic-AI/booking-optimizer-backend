import asyncio
import logging
import json
from datetime import datetime
import aiohttp

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

# Import medical listener and diagnosis throttler
# Import appointment agent instead of medical agents
from appointment_agent import AppointmentOptimizationAgent

# uncomment to enable Krisp background voice/noise cancellation
# from livekit.plugins import noise_cancellation

logger = logging.getLogger("appointment-optimizer")


# Removed diagnosis API functionality - now using appointment optimization

async def fetch_appointment_details(room_name: str) -> dict:
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
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                f"{url}/api/diagnosis/chat",
                params={"message": narrative},
                timeout=aiohttp.ClientTimeout(total=timeout)
            ) as response:
                if response.status == 200:
                    # Parse the server-sent events response
                    text = await response.text()
                    # Extract JSON from SSE format
                    for line in text.split('\n'):
                        if line.startswith('data: '):
                            json_str = line[6:]
                            if json_str.strip():
                                return json.loads(json_str)
                else:
                    logger.error(f"Diagnosis API error: {response.status}")
                    return {"error": f"API returned status {response.status}"}
    except asyncio.TimeoutError:
        logger.error("Diagnosis API timeout")
        return {"error": "API timeout"}
    except Exception as e:
        logger.error(f"Error calling diagnosis API: {e}")
        return {"error": str(e)}

# Conversation logger will be set up per room session

load_dotenv()


class ConversationLogger:
    """Simple conversation logger - creates a new log file for each room session"""
    def __init__(self, room_name: str):
        self.room_name = room_name
        self.conversation = []
        
        # Create a unique log file for this session
        import os
        os.makedirs("logs", exist_ok=True)
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        log_filename = f"logs/conversation_{room_name}_{timestamp}.log"
        
        # Set up logger for this session
        self.session_logger = logging.getLogger(f"conversation_{room_name}_{timestamp}")
        self.session_logger.setLevel(logging.INFO)
        
        # Create file handler
        file_handler = logging.FileHandler(log_filename)
        file_handler.setFormatter(logging.Formatter('%(asctime)s - %(message)s'))
        self.session_logger.addHandler(file_handler)
        
        # Log session start
        self.session_logger.info(f"[session_start] Room: {room_name}")
        logger.info(f"Started new conversation log: {log_filename}")
        
    def log_event(self, event_type: str, content: str, participant: str = ""):
        """Log a conversation event"""
        entry = {
            "timestamp": datetime.now().isoformat(),
            "type": event_type,
            "participant": participant,
            "content": content
        }
        self.conversation.append(entry)
        
        # Log to session-specific file
        self.session_logger.info(f"[{event_type}] {participant}: {content}")
        logger.info(f"[TRANSCRIPT] [{event_type}] {participant}: {content}")
        
    def save_transcript(self):
        """Save conversation transcript"""
        if self.conversation:
            import os
            os.makedirs("transcripts", exist_ok=True)
            
            filename = f"transcripts/transcript_{self.room_name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            with open(filename, 'w') as f:
                json.dump({
                    "room": self.room_name,
                    "conversation": self.conversation
                }, f, indent=2)
            logger.info(f"Saved transcript to {filename}")


class MyAgent(Agent):
    def __init__(self) -> None:
        super().__init__(
            instructions="You are Dr. Aisha Bin Rashid, an experienced physician. Keep responses brief and professional. "
            "\n\nKEY RULES:"
            "\n- Ask ONE question per response"
            "\n- Keep it to 1-2 sentences maximum"
            "\n- Skip lengthy acknowledgments"
            "\n- Listen to the answer before asking the next question"
            "\n- Be conversational but efficient"
            "\n\nSTYLE GUIDE:"
            "\n- Good: 'How long has this been going on?'"
            "\n- Good: 'I see. Any fever with that?'"
            "\n- Good: 'Okay. When does the pain occur?'"
            "\n- Bad: 'I'm so sorry to hear you're experiencing that. It must be difficult.'"
            "\n- Bad: 'Thank you for sharing. Let me ask about...'"
            "\n\nFOCUS: Gather medical information efficiently while maintaining natural conversation flow. One question at a time.",
        )

    async def on_enter(self):
        # when the agent is added to the session, it'll generate a reply
        # according to its instructions
        self.session.generate_reply(
            prompt="Start with: 'What brings you in today?' Nothing more."
        )


def prewarm(proc: JobProcess):
    proc.userdata["vad"] = silero.VAD.load()


async def entrypoint(ctx: JobContext):
    logger.info(f"[ENTRYPOINT] Job received for room: {ctx.room.name if hasattr(ctx, 'room') else 'unknown'}")
    
    # each log entry will include these fields
    ctx.log_context_fields = {
        "room": ctx.room.name,
    }
    
    # IMPORTANT: Connect to room FIRST before starting session
    await ctx.connect()
    logger.info(f"Connected to room: {ctx.room.name}")
    
    # Initialize conversation logger
    conv_logger = ConversationLogger(ctx.room.name)
    conv_logger.log_event("room_joined", f"Agent joined room {ctx.room.name}", "agent")
    
    # Initialize medical listener agent
    medical_listener = MedicalListenerAgent(session_id=f"{ctx.room.name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}")
    logger.info(f"Medical listener initialized for room: {ctx.room.name}")
    
    # Initialize diagnosis throttler
    diagnosis_throttler = DiagnosisThrottler()
    logger.info("Diagnosis throttler initialized")

    session = AgentSession(
        vad=ctx.proc.userdata["vad"],
        # any combination of STT, LLM, TTS, or realtime API can be used
        llm=openai.LLM(model="gpt-4o-mini"),
        stt=deepgram.STT(model="nova-3", language="multi"),
        tts=openai.TTS(voice="alloy"),
        # use LiveKit's turn detection model
        turn_detection=MultilingualModel(),
    )

    # Add debugging for all session events
    logger.info("Setting up event handlers...")
    
    # Monitor agent state changes
    @session.on("agent_state_changed")
    def on_agent_state_changed(state):
        logger.info(f"[DEBUG] Agent state changed: {state}")
        conv_logger.log_event("debug", f"Agent state: {state}", "system")
    
    # Monitor user state changes
    @session.on("user_state_changed")
    def on_user_state_changed(state):
        logger.info(f"[DEBUG] User state changed: {state}")
        conv_logger.log_event("debug", f"User state: {state}", "system")
    
    # Capture user speech transcriptions
    @session.on("user_input_transcribed")
    def on_user_input_transcribed(event):
        """Capture user speech as it's transcribed"""
        logger.info(f"[DEBUG] user_input_transcribed event fired")
        asyncio.create_task(handle_user_input_transcribed(event))
    
    async def handle_user_input_transcribed(event):
        try:
            logger.info(f"[DEBUG] Processing user transcript: {event}")
            text = event.transcript
            participant = getattr(event.participant, "identity", "user") if hasattr(event, "participant") else "user"
            conv_logger.log_event("user_transcript", text, participant)
            logger.info(f"[TRANSCRIPT] User said: {text}")
        except Exception as e:
            logger.error(f"Error in user_input_transcribed handler: {e}")
            logger.exception(e)

    # Capture finalized conversation items (both user and agent)
    @session.on("conversation_item_added")
    def on_conversation_item_added(event):
        """Capture finalized conversation turns from both user and agent"""
        logger.info(f"[DEBUG] conversation_item_added event fired")
        asyncio.create_task(handle_conversation_item_added(event))
    
    async def handle_conversation_item_added(event):
        try:
            logger.info(f"[DEBUG] Processing conversation item: {event}")
            logger.info(f"[DEBUG] Event attributes: {dir(event)}")
            
            # Try different ways to get content
            item = event.item
            logger.info(f"[DEBUG] Item attributes: {dir(item)}")
            
            # Check for role and text_content as per research
            role = getattr(item, "role", "unknown")
            text_content = getattr(item, "text_content", "")
            
            # Also try other possible attributes
            if not text_content:
                text_content = getattr(item, "content", "")
            if not text_content:
                text_content = getattr(item, "text", "")
                
            participant = "agent" if role == "assistant" else "user"
            
            conv_logger.log_event("conversation", text_content, participant)
            logger.info(f"[TRANSCRIPT] {participant} said: {text_content}")
            
            # Process with medical listener if there's text content
            if text_content:
                conversation_chunk = f"{participant.capitalize()}: {text_content}"
                medical_narrative = await medical_listener.process_input(conversation_chunk)
                logger.info(f"[MEDICAL LISTENER] {medical_narrative}")
                
                # Extract just the narrative part (remove "Medical Summary:\n" prefix)
                if medical_narrative.startswith("Medical Summary:\n"):
                    narrative_text = medical_narrative[17:]
                else:
                    narrative_text = medical_narrative
                
                # Check if we should send for diagnosis
                if narrative_text and len(narrative_text) > 50:  # Basic content check
                    if diagnosis_throttler.should_send_update(narrative_text):
                        logger.info("[DIAGNOSIS] Sending narrative for diagnosis...")
                        
                        # Send to diagnosis API
                        diagnosis_result = await send_narrative_to_diagnosis_api(
                            narrative_text, 
                            diagnosis_throttler.config
                        )
                        
                        # Mark as sent
                        diagnosis_throttler.mark_sent(narrative_text)
                        
                        # Send diagnosis to frontend via data channel
                        if "error" not in diagnosis_result:
                            diagnosis_data = {
                                "type": "diagnosis_update",
                                "narrative": narrative_text,
                                "diagnosis": diagnosis_result.get("diagnosis", []),
                                "follow_up_questions": diagnosis_result.get("follow_up_questions", []),
                                "further_tests": diagnosis_result.get("further_tests", [])
                            }
                            
                            # Send to all participants in the room
                            await ctx.room.local_participant.publish_data(
                                json.dumps(diagnosis_data).encode('utf-8'),
                                topic="diagnosis"
                            )
                            logger.info(f"[DIAGNOSIS] Sent diagnosis update: {len(diagnosis_data['diagnosis'])} diagnoses")
                        else:
                            logger.error(f"[DIAGNOSIS] Error: {diagnosis_result['error']}")
                
        except Exception as e:
            logger.error(f"Error in conversation_item_added handler: {e}")
            logger.exception(e)

    # log metrics as they are emitted, and total usage after session is over
    usage_collector = metrics.UsageCollector()

    @session.on("metrics_collected")
    def _on_metrics_collected(ev: MetricsCollectedEvent):
        metrics.log_metrics(ev.metrics)
        usage_collector.collect(ev.metrics)
        
        # Debug metrics to verify STT activity
        logger.info(f"[DEBUG] Metrics collected: {ev.metrics}")
        if hasattr(ev.metrics, 'metrics') and 'stt_audio_duration' in ev.metrics.metrics:
            logger.info(f"[DEBUG] STT processed {ev.metrics.metrics['stt_audio_duration']}s of audio")
        else:
            logger.info("[DEBUG] No STT activity detected in metrics")

    async def log_usage():
        summary = usage_collector.get_summary()
        logger.info(f"Usage: {summary}")

    # Add transcript saving on shutdown
    async def save_transcript():
        conv_logger.save_transcript()
    
    # Add medical facts summary on shutdown
    async def save_medical_summary():
        logger.info(f"[MEDICAL LISTENER] Final medical facts saved to: {medical_listener.json_file}")
        
    # shutdown callbacks are triggered when the session is over
    ctx.add_shutdown_callback(log_usage)
    ctx.add_shutdown_callback(save_transcript)
    ctx.add_shutdown_callback(save_medical_summary)

    # Log room events
    @ctx.room.on("participant_connected")
    def on_participant_connected(participant):
        conv_logger.log_event("participant_connected", f"{participant.identity} joined", participant.identity)
    
    @ctx.room.on("participant_disconnected")
    def on_participant_disconnected(participant):
        conv_logger.log_event("participant_disconnected", f"{participant.identity} left", participant.identity)

    # Start the session with the agent
    logger.info("Starting agent session...")
    await session.start(
        agent=MyAgent(),
        room=ctx.room,
        room_input_options=RoomInputOptions(
            # uncomment to enable Krisp BVC noise cancellation
            # noise_cancellation=noise_cancellation.BVC(),
        ),
        room_output_options=RoomOutputOptions(transcription_enabled=True),
    )
    logger.info("Agent session started successfully")


if __name__ == "__main__":
    cli.run_app(WorkerOptions(entrypoint_fnc=entrypoint, prewarm_fnc=prewarm))