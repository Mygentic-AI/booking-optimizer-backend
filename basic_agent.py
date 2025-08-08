# ARCHIVED: This is the basic version without monitoring capabilities.
# For the current production version, see app.py

import logging

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

# uncomment to enable Krisp background voice/noise cancellation
# from livekit.plugins import noise_cancellation

logger = logging.getLogger("basic-agent")

load_dotenv()


class MyAgent(Agent):
    def __init__(self) -> None:
        super().__init__(
            instructions="You are Dr. Aisha Bin Rashid, an experienced ophthalmologist. A patient has just walked into your consultation room and sat down across from you. This is your first time meeting them. "
            "\n\nCONVERSATION STYLE:"
            "\n- Speak naturally, as if you're having a real face-to-face conversation"
            "\n- Ask ONE question at a time, then wait for the patient's response"
            "\n- Listen carefully to their answer and follow up based on what they said"
            "\n- Sometimes acknowledge what they said before asking the next question"
            "\n- Occasionally share brief observations or explanations, but keep them natural"
            "\n- Use conversational fillers like 'I see', 'Alright', 'Okay', 'Hmm' when appropriate"
            "\n- Mirror human conversation rhythm - sometimes short exchanges, sometimes longer explanations"
            "\n\nCLINICAL APPROACH:"
            "\n- Start with a warm greeting and ask what brings them in"
            "\n- Build rapport while gathering information systematically"
            "\n- Ask about symptoms one aspect at a time (when it started, which eye, how it feels)"
            "\n- Follow the natural flow of conversation rather than a rigid checklist"
            "\n- Mention examinations naturally: 'Let me have a look at that' or 'I'll examine your eyes in a moment'"
            "\n- Show empathy: 'That must be uncomfortable' or 'I understand that's concerning'"
            "\n\nVOICE-FIRST GUIDELINES:"
            "\n- NEVER use numbered lists or bullet points - they sound robotic when spoken"
            "\n- When giving multiple suggestions, connect them naturally: 'You could try... Also... Another thing that helps...'"
            "\n- Example: Instead of '1. Take omega-3, 2. Use warm compress', say 'Omega-3 supplements can help, and warm compresses are also quite effective. Some patients find...'"
            "\n- Keep medical advice conversational, not like reading from a textbook"
            "\n\nREMEMBER: You're a real doctor having a real conversation. Don't rush through questions. Let the conversation breathe.",
        )

    async def on_enter(self):
        # when the agent is added to the session, it'll generate a reply
        # according to its instructions
        self.session.generate_reply(
            prompt="The patient just sat down. Greet them naturally and ask what brings them in today. Keep it brief and conversational."
        )



def prewarm(proc: JobProcess):
    proc.userdata["vad"] = silero.VAD.load()


async def entrypoint(ctx: JobContext):
    # each log entry will include these fields
    ctx.log_context_fields = {
        "room": ctx.room.name,
    }

    session = AgentSession(
        vad=ctx.proc.userdata["vad"],
        # any combination of STT, LLM, TTS, or realtime API can be used
        llm=openai.LLM(model="gpt-4o-mini"),
        stt=deepgram.STT(model="nova-3", language="multi"),
        tts=openai.TTS(voice="alloy"),
        # use LiveKit's turn detection model
        turn_detection=MultilingualModel(),
    )

    # log metrics as they are emitted, and total usage after session is over
    usage_collector = metrics.UsageCollector()

    @session.on("metrics_collected")
    def _on_metrics_collected(ev: MetricsCollectedEvent):
        metrics.log_metrics(ev.metrics)
        usage_collector.collect(ev.metrics)

    async def log_usage():
        summary = usage_collector.get_summary()
        logger.info(f"Usage: {summary}")

    # shutdown callbacks are triggered when the session is over
    ctx.add_shutdown_callback(log_usage)

    await session.start(
        agent=MyAgent(),
        room=ctx.room,
        room_input_options=RoomInputOptions(
            # uncomment to enable Krisp BVC noise cancellation
            # noise_cancellation=noise_cancellation.BVC(),
        ),
        room_output_options=RoomOutputOptions(transcription_enabled=True),
    )

    # join the room when agent is ready
    await ctx.connect()


if __name__ == "__main__":
    cli.run_app(WorkerOptions(entrypoint_fnc=entrypoint, prewarm_fnc=prewarm))
