# Room Conversation Monitoring Agent for LiveKit

Based on your existing agent code and LiveKit's architecture, I'll provide you with code to create a **monitoring agent** that can listen to room conversations in the background and extract information to pass to another agent.

## Core Concept

The monitoring agent will join the same room as your main agent and subscribe to **track events**, **data messages**, and **transcription events** to extract conversation information. It operates as an independent participant that doesn't interfere with the main conversation[1][2].

## Implementation Code

Here's the complete monitoring agent implementation:

### 1. Monitoring Agent Class

```python
import logging
import asyncio
import json
from typing import Dict, List, Any
from dataclasses import dataclass
from datetime import datetime

from dotenv import load_dotenv
from livekit import rtc
from livekit.agents import (
    Agent,
    AgentSession,
    JobContext,
    JobProcess,
    RunContext,
    WorkerOptions,
    cli,
    metrics,
)
from livekit.plugins import deepgram, openai, silero

logger = logging.getLogger("monitoring-agent")
load_dotenv()

@dataclass
class ConversationData:
    """Data structure to hold extracted conversation information"""
    participant_id: str
    message: str
    timestamp: datetime
    message_type: str  # 'audio', 'text', 'transcription'
    meta Dict[str, Any] = None

class ConversationMonitor:
    """Handles conversation data extraction and forwarding"""
    
    def __init__(self, room: rtc.Room):
        self.room = room
        self. []
        self.audio_streams: Dict[str, rtc.AudioStream] = {}
        
    async def process_audio_track(self, track: rtc.Track, participant: rtc.RemoteParticipant):
        """Process audio tracks for transcription and analysis"""
        logger.info(f"Processing audio track from {participant.identity}")
        
        audio_stream = rtc.AudioStream(track)
        self.audio_streams[participant.sid] = audio_stream
        
        try:
            async for event in audio_stream:
                # Here you could add real-time audio processing
                # For example, VAD detection or streaming to STT service
                await self._handle_audio_frame(event.frame, participant)
        except Exception as e:
            logger.error(f"Error processing audio track: {e}")
        finally:
            if participant.sid in self.audio_streams:
                del self.audio_streams[participant.sid]
            await audio_stream.aclose()
    
    async def _handle_audio_frame(self, frame, participant: rtc.RemoteParticipant):
        """Handle individual audio frames - implement your audio processing here"""
        # Add your audio analysis logic here
        # This could include:
        # - Real-time transcription
        # - Sentiment analysis
        # - Keyword detection
        # - Audio quality metrics
        pass
    
    def add_conversation_data(self,  ConversationData):
        """Add conversation data to buffer"""
        self.conversation_buffer.append(data)
        logger.info(f"Added conversation  {data.message_type} from {data.participant_id}")
        
        # Process the data (send to another agent, analyze, store, etc.)
        asyncio.create_task(self._process_conversation_data(data))
    
    async def _process_conversation_data(self,  ConversationData):
        """Process and forward conversation data to another agent or service"""
        try:
            # Here you can implement your data forwarding logic
            # Examples:
            # - Send to another LiveKit room
            # - Post to a webhook
            # - Store in database
            # - Send to another agent via API
            
            processed_data = {
                "participant": data.participant_id,
                "content": data.message,
                "timestamp": data.timestamp.isoformat(),
                "type": data.message_type,
                "metadata": data.metadata or {}
            }
            
            # Example: Send data via room data message to another agent
            await self._forward_to_processing_agent(processed_data)
            
        except Exception as e:
            logger.error(f"Error processing conversation  {e}")
    
    async def _forward_to_processing_agent(self,  Dict[str, Any]):
        """Forward processed data to another agent"""
        try:
            # Send as data message to room (other agents can listen to this)
            data_bytes = json.dumps(data).encode('utf-8')
            await self.room.local_participant.publish_data(
                data_bytes,
                topic="conversation_analysis",  # Topic for filtering
                reliable=True
            )
            logger.info(f"Forwarded data to processing agent: {data['type']}")
        except Exception as e:
            logger.error(f"Error forwarding  {e}")

class MonitoringAgent(Agent):
    """Background monitoring agent that extracts conversation information"""
    
    def __init__(self) -> None:
        super().__init__(
            instructions="You are a silent monitoring agent that observes conversations and extracts relevant information."
        )
        self.monitor = None
    
    async def on_enter(self):
        """Called when agent enters the room"""
        logger.info("Monitoring agent entered the room")
        # Don't generate any replies - this is a silent observer
        pass

async def entrypoint(ctx: JobContext):
    """Entry point for the monitoring agent"""
    
    # Initialize the conversation monitor
    monitor = ConversationMonitor(ctx.room)
    
    # Set up event listeners for room events
    @ctx.room.on("participant_connected")
    def on_participant_connected(participant: rtc.RemoteParticipant):
        logger.info(f"Participant connected: {participant.identity}")
        
        # Add conversation data about participant joining
        data = ConversationData(
            participant_id=participant.identity,
            message=f"Participant {participant.identity} joined the room",
            timestamp=datetime.now(),
            message_type="event",
            metadata={"event_type": "participant_joined"}
        )
        monitor.add_conversation_data(data)
    
    @ctx.room.on("participant_disconnected")
    def on_participant_disconnected(participant: rtc.RemoteParticipant):
        logger.info(f"Participant disconnected: {participant.identity}")
        
        data = ConversationData(
            participant_id=participant.identity,
            message=f"Participant {participant.identity} left the room",
            timestamp=datetime.now(),
            message_type="event",
            metadata={"event_type": "participant_left"}
        )
        monitor.add_conversation_data(data)
    
    @ctx.room.on("track_subscribed")
    def on_track_subscribed(
        track: rtc.Track,
        publication: rtc.RemoteTrackPublication,
        participant: rtc.RemoteParticipant
    ):
        logger.info(f"Track subscribed: {track.kind} from {participant.identity}")
        
        if track.kind == rtc.TrackKind.KIND_AUDIO:
            # Process audio tracks for conversation monitoring
            asyncio.create_task(monitor.process_audio_track(track, participant))
    
    @ctx.room.on("data_received")
    def on_data_received( rtc.DataPacket, participant: rtc.RemoteParticipant):
        """Listen for data messages from other participants/agents"""
        try:
            if data.topic == "transcription":
                # Handle transcription data
                message = data.data.decode('utf-8')
                conv_data = ConversationData(
                    participant_id=participant.identity,
                    message=message,
                    timestamp=datetime.now(),
                    message_type="transcription"
                )
                monitor.add_conversation_data(conv_data)
                
            elif data.topic == "agent_response":
                # Handle agent responses
                message = data.data.decode('utf-8')
                conv_data = ConversationData(
                    participant_id=participant.identity,
                    message=message,
                    timestamp=datetime.now(),
                    message_type="agent_response"
                )
                monitor.add_conversation_data(conv_data)
                
        except Exception as e:
            logger.error(f"Error processing data message: {e}")
    
    # Create agent session for monitoring (without STT/TTS since it's silent)
    session = AgentSession(
        vad=silero.VAD.load(),
        # No LLM, STT, or TTS needed for monitoring
    )
    
    # Connect to room
    await ctx.connect(auto_subscribe=rtc.AutoSubscribe.AUDIO_ONLY)  # Only subscribe to audio
    
    # Start the session with monitoring agent
    await session.start(
        agent=MonitoringAgent(),
        room=ctx.room,
    )
    
    logger.info(f"Monitoring agent connected to room: {ctx.room.name}")

def prewarm(proc: JobProcess):
    """Prewarm function for the monitoring agent worker"""
    proc.userdata["vad"] = silero.VAD.load()

if __name__ == "__main__":
    cli.run_app(WorkerOptions(
        entrypoint_fnc=entrypoint, 
        prewarm_fnc=prewarm,
        agent_name="monitoring-agent"  # Distinguish from your main agent
    ))
```

### 2. Enhanced Data Processing Agent

Here's an example of how another agent could receive and process the extracted 

```python
class DataProcessingAgent(Agent):
    """Agent that receives and processes conversation data from monitoring agent"""
    
    def __init__(self):
        super().__init__(
            instructions="You analyze conversation data and provide insights."
        )
        self.conversation_history = []
    
    async def on_enter(self):
        """Set up data message listener"""
        await self.session.generate_reply(
            prompt="Data processing agent ready to analyze conversations."
        )

async def processing_agent_entrypoint(ctx: JobContext):
    """Entry point for the data processing agent"""
    
    @ctx.room.on("data_received")
    def on_data_received( rtc.DataPacket, participant: rtc.RemoteParticipant):
        if data.topic == "conversation_analysis":
            # Received processed data from monitoring agent
            try:
                analysis_data = json.loads(data.data.decode('utf-8'))
                logger.info(f"Received analysis  {analysis_data}")
                
                # Process the data (sentiment analysis, keyword extraction, etc.)
                asyncio.create_task(process_analysis_data(analysis_data))
                
            except Exception as e:
                logger.error(f"Error processing analysis  {e}")
    
    # Set up processing agent session
    session = AgentSession(
        llm=openai.LLM(model="gpt-4o-mini"),
        vad=silero.VAD.load(),
    )
    
    await ctx.connect()
    await session.start(
        agent=DataProcessingAgent(),
        room=ctx.room,
    )

async def process_analysis_data( Dict[str, Any]):
    """Process the conversation analysis data"""
    # Implement your data processing logic here
    # Examples:
    # - Sentiment analysis
    # - Topic extraction
    # - Intent detection
    # - Compliance checking
    logger.info(f"Processing analysis data for participant: {data['participant']}")
```

## Key Features of This Implementation

### Room Event Monitoring
The monitoring agent listens to key room events including participant connections, track subscriptions, and data messages[3][4].

### Audio Track Processing
It subscribes to audio tracks from all participants and can process them in real-time for transcription or analysis[5][6].

### Data Message Forwarding
Extracted information is forwarded to other agents using LiveKit's data message system with specific topics for filtering[7].

### Silent Operation
The monitoring agent operates silently without interfering with the main conversation[1].

### Extensible Design
The `ConversationMonitor` class can be extended to add more sophisticated analysis like sentiment detection, keyword extraction, or compliance monitoring[8].

## Running the Monitoring Agent

1. **Deploy as separate worker**: Run this as a separate agent worker with a different `agent_name`
2. **Room targeting**: Configure it to join the same rooms as your main agent
3. **Resource management**: It only subscribes to audio tracks to minimize resource usage[5]

This implementation provides a foundation for monitoring LiveKit room conversations and can be extended based on your specific requirements for data extraction and processing[9][10].

Sources
[1] LiveKit Agents https://docs.livekit.io/agents/
[2] Rooms, participants, and tracks | LiveKit Docs https://docs.livekit.io/home/get-started/api-primitives/
[3] Handling events - LiveKit Docs https://docs.livekit.io/home/client/events/
[4] RoomEvent https://docs.livekit.io/reference/client-sdk-android/livekit-android-sdk/io.livekit.android.events/-room-event/index.html
[5] Receiving and publishing tracks - LiveKit Docs https://docs.livekit.io/agents/v0/build/tracks/
[6] Issue: track_subscribed Event Not Triggering for Outbound SIP Calls ... https://github.com/livekit/agents/issues/2157
[7] Realtime text & data - LiveKit Docs https://docs.livekit.io/home/client/data/
[8] Tool definition and use - LiveKit Docs https://docs.livekit.io/agents/build/tools/
[9] GitHub - livekit-examples/realtime-room-monitor https://github.com/livekit-examples/realtime-room-monitor
[10] Logs, metrics, and telemetry | LiveKit Docs https://docs.livekit.io/agents/build/metrics/
[11] basic_agent.py https://ppl-ai-file-upload.s3.amazonaws.com/web/direct-files/attachments/6889097/8fe71724-424a-4008-90d7-32bff9804c1e/basic_agent.py
[12] AI Avatar Agent with LiveKit + Beyond Presence - YouTube https://www.youtube.com/watch?v=Z-TqnHHgCE4
[13] Managing rooms - LiveKit Docs https://docs.livekit.io/home/server/managing-rooms/
[14] How To Build Your First AI Voice Agent On LiveKit - YouTube https://www.youtube.com/watch?v=rYJb-YIeS1M
[15] A simple example to have a LiveKit Agent answer a SIP call - GitHub https://github.com/livekit-examples/livekit-sip-agent-example
[16] livekit/agents: A powerful framework for building realtime voice AI ... https://github.com/livekit/agents
[17] Workflows | LiveKit Docs https://docs.livekit.io/agents/build/workflows/
[18] Python agent won't connect to Livekit room. : r/code - Reddit https://www.reddit.com/r/code/comments/1i0w38j/python_agent_wont_connect_to_livekit_room/
[19] Agent monitoring · Issue #843 · livekit/agents - GitHub https://github.com/livekit/agents/issues/843
[20] How to build an MCP voice agent with OpenAI and LiveKit Agents https://webflow.assemblyai.com/blog/mcp-voice-agent-openai-livekit
[21] How to deploy LiveKit Agents on Modal https://modal.com/blog/livekit-modal
[22] Agent speech and audio - LiveKit Docs https://docs.livekit.io/agents/build/audio/
[23] How to build a LiveKit app with real-time Speech-to-Text - AssemblyAI https://www.assemblyai.com/blog/livekit-realtime-speech-to-text
[24] How to set an end time for a LiveKit room and send a warning ... https://stackoverflow.com/questions/79559263/how-to-set-an-end-time-for-a-livekit-room-and-send-a-warning-message-1-minute-be
[25] AI voice agents | LiveKit Docs https://docs.livekit.io/agents/v0/voice-agent/
[26] LiveKit的agent介绍 https://blog.csdn.net/xsgnzb/article/details/141938915
[27] livekit/agents-playground - GitHub https://github.com/livekit/agents-playground
[28] Room class Room https://pub.dev/documentation/livekit_client_custom/latest/livekit_client_custom/Room-class.html
[29] Subscribing to tracks - LiveKit Docs https://docs.livekit.io/home/client/tracks/subscribe/
[30] Question about manual subscription of tracks via backend if ... - GitHub https://github.com/livekit/livekit/issues/3446
[31] LiveKit SDK - Maxim Docs https://www.getmaxim.ai/docs/sdk/python/integrations/livekit/livekit
[32] events.ts - livekit/client-sdk-js - GitHub https://github.com/livekit/client-sdk-js/blob/main/src/room/events.ts
[33] Class Participant https://docs.livekit.io/reference/client-sdk-js/classes/Participant.html
[34] Inside a session | LiveKit Docs https://docs.livekit.io/agents/v0/build/session/
[35] Managing participants | LiveKit Docs https://docs.livekit.io/home/server/managing-participants/
[36] LocalParticipant class https://pub.dev/documentation/livekit_client_custom/latest/livekit_client_custom/LocalParticipant-class.html
[37] Observability and Monitoring for LiveKit AI Agents Using Prometheus and Grafana https://webrtc.ventures/2025/07/observability-and-monitoring-for-livekit-ai-agents-using-prometheus-and-grafana/
[38] Room class Room https://pub.dev/documentation/livekit_client/latest/livekit_client/Room-class.html
[39] Exploring AI-Driven Mock Technical Interviews on Student ... - arXiv https://arxiv.org/html/2506.16542v1
[40] "could not find participant" when a participant quickly reconnects ... https://github.com/livekit/server-sdk-go/issues/451
[41] LiveKit real-time and server SDKs for Python - GitHub https://github.com/livekit/python-sdks
[42] noice-com/livekit-python-sdks: Python SDK for LiveKit - GitHub https://github.com/noice-com/livekit-python-sdks
[43] livekit_client_custom library https://pub.dev/documentation/livekit_client_custom/latest/livekit_client_custom/
[44] livekit.rtc.room API documentation https://docs.livekit.io/reference/python/livekit/rtc/room.html
[45] livekit-client https://www.npmjs.com/package/livekit-client/v/0.18.4-RC8?activeTab=readme
[46] livekit-protocol on Pypi https://libraries.io/pypi/livekit-protocol/1.0.3
[47] Realtime media | LiveKit Docs https://docs.livekit.io/home/client/tracks/
[48] npm:livekit-client | Skypack https://www.skypack.dev/view/livekit-client
[49] GitHub - Presence-AI/livekit-python-sdks: LiveKit real-time and server SDKs for Python https://github.com/Presence-AI/livekit-python-sdks
[50] Build an AI agent with LiveKit for real-time Speech-to-Text - YouTube https://www.youtube.com/watch?v=A400nCCZlK4
[51] livekit-api on Pypi https://libraries.io/pypi/livekit-api
[52] atyenoria/livekit-whisper-transcribe - GitHub https://github.com/atyenoria/livekit-whisper-transcribe
[53] GitHub - G-structure/agents3: agents v3 https://github.com/G-structure/agents3
[54] LLM/TTS transcription #1979 - livekit/agents - GitHub https://github.com/livekit/agents/issues/1979
[55] GitHub - jakerobers/livekit-agents: Build real-time multimodal AI applications 🤖🎙️📹 https://github.com/jakerobers/livekit-agents
[56] Is there a way to transcribe audio from multiple participant LiveKit Community #ask-ai https://www.linen.dev/s/livekit-users/t/28933484/is-there-a-way-to-transcribe-audio-from-multiple-participant
[57] Agent not getting track of participant if participant joins from ... - GitHub https://github.com/livekit/livekit/issues/3239
[58] is it possibel to collect the transcription during the call LiveKit Community #ask-ai https://www.linen.dev/s/livekit-users/t/26934774/is-it-possibel-to-collect-the-transcription-during-the-call-
[59] Capturing metrics | LiveKit Docs https://docs.livekit.io/agents/ops/logging/
[60] Recording agent sessions | LiveKit Docs https://docs.livekit.io/agents/v0/build/record/
[61] Transcriptions - LiveKit Docs https://docs.livekit.io/agents/v0/voice-agent/transcriptions/
[62] How to Build a Video Conferencing Application with LiveKit and ... https://symbl.ai/developers/blog/how-to-build-a-video-conferencing-application-with-livekit-and-symbl-ai/
[63] JobRequest- req.room.metadata is null in livekit-agents==0.8.9 and ... https://github.com/livekit/agents/issues/713
