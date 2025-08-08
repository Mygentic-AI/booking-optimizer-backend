# AI Medical Consultation Platform Backend

LiveKit voice agents for simulating and monitoring doctor-patient conversations with intelligent medical information extraction.

## 🚀 Quick Start

### Prerequisites
- Python 3.11.x (specifically 3.11, not 3.12+)
- LiveKit Cloud account and credentials
- OpenAI API key
- Virtual environment (venv)

### Setup

1. **Create and activate virtual environment:**
```bash
python3.11 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

2. **Install dependencies:**
```bash
make install
# or
pip install -r requirements.txt
```

3. **Configure environment variables:**
Create a `.env` file with:
```env
LIVEKIT_URL=wss://your-project.livekit.cloud
LIVEKIT_API_KEY=your-api-key
LIVEKIT_API_SECRET=your-api-secret
OPENAI_API_KEY=your-openai-key
```

## Running the Agent

### Option 1: Using the start script (Recommended)
```bash
./start_agent.sh  # Automatically stops old agents and starts new one
```

### Option 2: Using make commands
```bash
make run   # Production mode (stops old agents first)
make dev   # Development mode with auto-reload
make stop  # Stop all running agents
```

### Option 3: Manual start
```bash
python app.py dev
```

## Running the Diagnosis API

The diagnosis API is required for the diagnosis panel in the frontend to work:

### Start the Structured Diagnosis API
```bash
# In a separate terminal, with venv activated:
make pydantic-diagnosis-dev    # Runs on port 8000 with auto-reload

# This starts the structured JSON diagnosis service that the frontend expects
```

**Important Notes:**
- Use `make pydantic-diagnosis-dev` NOT `make diagnosis-api-dev`
- The `pydantic-diagnosis` version returns structured JSON (diagnosis, follow_up_questions, further_tests)
- The `diagnosis-api` version returns plain text streaming and won't work with the frontend
- The service runs on port 8000 by default
- CORS is configured for ports 3000, 3001, 3002, 3003, and 3005

## 📁 Project Structure

```
backend/
├── app.py                      # Main agent with conversation monitoring
├── basic_agent.py             # Archived - original version without monitoring
├── diagnosis_api.py           # Plain text streaming diagnosis API (not used by frontend)
├── pydantic_diagnosis_agent.py # Structured JSON diagnosis API (use this one!)
├── medical_extractor_agent.py # (Planned) Medical information extraction agent
├── start_agent.sh             # Startup script for clean agent management
├── Makefile                   # Common commands and tasks
├── requirements.txt           # Python dependencies
├── logs/                      # Log files directory
│   ├── agent.log             # Runtime logs
│   └── conversation_*.log    # Per-session conversation transcripts
├── transcripts/              # Saved conversation transcripts (JSON)
└── tests/                    # Test files
```

## 🎯 Architecture Overview

### Testing Infrastructure
The system uses an AI doctor agent to simulate real doctor-patient conversations for testing purposes:
- **AI Doctor**: Dr. Aisha Bin Rashid (ophthalmologist persona)
- **Purpose**: Testers act as patients to generate realistic medical conversations
- **Benefit**: No need for real doctors during development and testing

### Core Components

#### 1. Voice Agent (app.py)
- Simulates a doctor for testing conversation monitoring
- Natural conversation flow with medical expertise
- Voice-first design optimized for spoken interactions

#### 2. Conversation Monitoring
- Real-time transcript capture of doctor-patient conversations
- Per-session log files: `conversation_{room}_{timestamp}.log`
- Captures both partial and final transcriptions
- Foundation for feeding data to diagnostic systems

#### 3. Medical Information Extractor (In Development)
- **Purpose**: Intelligent extraction of medical information from conversation streams
- **Input**: Streaming conversation events
- **Processing**: LLM-based extraction of symptoms, complaints, medical history
- **Output**: Structured medical information ready for diagnosis
- **Status**: Being developed as standalone component first

#### 4. Diagnosis API (diagnosis_api.py)
- FastAPI service using Llama3-OpenBioLLM-70B model
- Provides streaming diagnosis responses
- Endpoint: `/api/diagnosis/chat`
- Currently standalone, will be integrated with extractor

### Voice Pipeline
- **Speech-to-Text**: Deepgram (nova-3 model) with multilingual support
- **Language Model**: OpenAI GPT-4 (gpt-4o-mini)
- **Text-to-Speech**: OpenAI TTS (alloy voice)
- **Voice Activity Detection**: Silero VAD
- **Turn Detection**: Multilingual model

### Process Management
- Automatic cleanup of old agent processes
- Prevents multiple agents from conflicting
- Clean startup/shutdown procedures
- Background process support

## 🚧 Development Approach

### Phased Implementation
We're building this system incrementally to ensure each component works perfectly before integration:

1. **Phase 1**: ✅ Conversation Monitoring - Capture doctor-patient conversations
2. **Phase 2**: 🔄 Medical Extractor Agent - Standalone LLM agent for information extraction
3. **Phase 3**: 🔮 Integration - Connect extractor to conversation stream
4. **Phase 4**: 🔮 Diagnosis Pipeline - Connect extractor to diagnosis API

### Current Phase: Medical Extractor Agent
- Building as independent component first
- No coupling to existing systems initially
- Focus on streaming input/output capabilities
- LLM-based medical information extraction

## 🛠️ Development

### Common Commands
```bash
make lint      # Run code linting with ruff
make format    # Format code with ruff
make test      # Run tests with pytest
make clean     # Clean cache files
make stop      # Stop all running agents
```

### Debugging
- Check `logs/agent.log` for runtime issues
- Individual conversation logs in `logs/conversation_*.log`
- Use `tail -f logs/agent.log` to monitor in real-time

### Monitoring Conversations
Each session creates a detailed log with:
- Session start/end times
- User speech (real-time and final transcriptions)
- Agent responses
- State transitions
- System events

Example log entry:
```
2025-07-26 13:23:58,297 - [user_transcript] user: Are you there?
2025-07-26 13:23:58,902 - [conversation] user: Are you there?
2025-07-26 13:24:06,893 - [conversation] agent: Yes, I'm here! How can I help you today?
```

## 🚨 Important Notes

1. **Python Version**: Must use Python 3.11.x (not 3.12+)
2. **Virtual Environment**: Always activate venv before running
3. **Process Management**: Use provided scripts to avoid zombie processes
4. **Logs**: Check logs directory for debugging information

## 🐛 Troubleshooting

### Agent won't start
```bash
make stop          # Stop all agents
./start_agent.sh   # Clean start
```

### No conversation logs appearing
- Verify agent is receiving job requests in `logs/agent.log`
- Check LiveKit credentials are correct
- Ensure you're connected to the correct LiveKit project

### Multiple agents running
```bash
pkill -f "python.*app.py"
pkill -f "multiprocessing.*spawn"
make run
```

### Assignment timeout errors
- This usually means another agent is already handling the room
- Run `make stop` and try again

## 📄 License

See parent repository for license information.