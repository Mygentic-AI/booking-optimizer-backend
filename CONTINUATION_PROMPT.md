# Continuation Prompt: Fix Agent Audio Connection for SIP Calls

## Current Status
We have successfully configured LiveKit SIP integration with Telnyx. Outbound calls now work - the phone rings when we call +971585089156 from our Telnyx number +18773893410. However, there's complete silence on the call because the agent isn't properly connecting to handle the audio stream.

## What's Working
1. **Telnyx Configuration**: ✅ Properly configured with FQDN `dev-scheduling-ai-fcg41leb.sip.livekit.cloud`
2. **LiveKit Outbound Trunk**: ✅ Created with `sip.telnyx.com:5060` using UDP transport
3. **Authentication**: ✅ Username `andrepemmelaar` (no underscore) with correct password
4. **SIP Headers**: ✅ Fixed by using port 5060 in address field
5. **Phone Rings**: ✅ Call successfully reaches +971585089156

## The Problem
The enhanced_gemini_sip_agent.py is running but not joining the outbound call rooms. When outbound_caller.py creates a room like `outbound_971585089156_1755005294`, the agent doesn't receive the job request to join and handle the conversation.

## Key Files and Current Configuration

### Working Trunk IDs (.env.sip)
```
INBOUND_TRUNK_ID=ST_ckKBtMAADLR2
OUTBOUND_TRUNK_ID=ST_TbZRH2bgJ8Kz
TELNYX_SIP_USER=andrepemmelaar
TELNYX_PHONE_NUMBER=+18773893410
```

### Current Agent (enhanced_gemini_sip_agent.py)
- Runs with: `make gemini-sip` or `python enhanced_gemini_sip_agent.py dev`
- Configured to detect SIP vs web participants
- Uses English for SIP calls, Arabic for web
- Has function tools for appointment management
- Currently running but not receiving job requests for outbound rooms

### Outbound Caller (outbound_caller.py)
- Creates room with name pattern: `outbound_{phone_number}_{timestamp}`
- Successfully creates SIP participant
- Call connects (phone rings) but no audio

## Debug Information
When running the agent, it shows:
```
2025-08-12 17:18:40,861 - INFO livekit.agents - registered worker {"id": "AW_yxipukUXMVCU", "url": "wss://dev-scheduling-ai-fcg41leb.livekit.cloud", "region": "UAE", "protocol": 16}
```

But when outbound_caller.py creates a room and SIP participant:
```
INFO:outbound-caller:Created room: outbound_971585089156_1755005294
INFO:outbound-caller:SIP participant created: PA_hjq9RNDscK4p
```

The agent never logs receiving a job for this room.

## What Needs to Be Fixed

### Option 1: Agent Job Assignment
The agent might need to be configured to accept jobs for rooms with pattern `outbound_*`. Currently it might only be listening for specific room names.

### Option 2: Room Configuration
The outbound_caller.py might need to create rooms with specific metadata or configuration that triggers agent assignment.

### Option 3: Agent Registration
The agent might need to register with a specific agent name that matches dispatch rules or room requirements.

## Next Steps
1. Debug why the agent isn't receiving job requests for outbound call rooms
2. Ensure the agent properly joins the room when a SIP participant is created
3. Test that audio flows correctly once the agent joins
4. Verify the Gemini realtime model works with SIP audio streams

## Testing Commands
```bash
# Terminal 1: Start the agent
make gemini-sip

# Terminal 2: Make an outbound call
python outbound_caller.py

# Expected: Phone rings AND agent speaks when answered
# Current: Phone rings but silence when answered
```

## Additional Context
- The agent uses Gemini 2.0 Flash Live model with Kore voice
- Appointment details are hardcoded for testing
- The system worked previously with 11labs agent (different implementation)
- All SIP configuration is correct as evidenced by the phone ringing

Please help fix the agent so it properly joins outbound call rooms and handles the audio conversation.