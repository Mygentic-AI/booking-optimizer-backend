# SIP Telephony Integration Guide

This guide explains how to set up and use SIP telephony with your LiveKit appointment booking agent, allowing the same AI agent to handle both web-based interactions and traditional phone calls.

## Overview

The enhanced SIP agent extends your existing Gemini appointment agent to:
- Accept incoming phone calls through your Telnyx number
- Make outbound appointment confirmation calls
- Automatically detect whether a connection is from web or SIP
- Provide appropriate responses based on the connection type

## Prerequisites

1. **Telnyx Account** with:
   - Verified account (L2 verification completed)
   - Purchased phone number(s)
   - SIP connection configured

2. **LiveKit Cloud** account with:
   - Valid API credentials
   - Project configured

3. **LiveKit CLI** installed:
   ```bash
   # Install LiveKit CLI if not already installed
   curl -sSL https://get.livekit.io/cli | bash
   ```

## Quick Setup

### 1. Configure Telnyx SIP Connection

In your Telnyx Mission Control Portal:

1. Go to **SIP Connections** → Create New Connection
2. **Configuration Tab**:
   - **Connection Name**: LiveKit
   - **Connection Type**: FQDN Connection
   - **Status**: Active

3. **Authentication and Routing Tab**:
   - Add FQDN: `dev-scheduling-ai-fcg41leb.sip.livekit.cloud` (your LiveKit project's SIP endpoint)
   - **Port**: 5060
   - **DNS Record Type**: SRV
   - **Primary FQDN**: Select the FQDN you just added
   - **Outbound Calls Authentication**: 
     - Method: Credentials
     - Username: `andrepemmelaar` (no underscores allowed)
     - Password: Your secure password

4. **Inbound Tab**:
   - **Destination Number Format**: +E.164
   - **SIP Transport Protocol**: UDP
   - **SIP Region**: Europe (or closest to your target)

5. **Outbound Tab**:
   - **Outbound Voice Profile**: Select Default or create one
   - **Localization Country**: Your target country
   - **Caller ID Override**: Your Telnyx number (e.g., +18773893410)
   - **Important**: Do NOT put the destination number here

6. **Numbers Tab**:
   - Assign your purchased Telnyx number(s) to this SIP connection

### 2. Set Up Environment Variables

Add to your `.env` file:
```bash
# Existing LiveKit credentials
LIVEKIT_URL=wss://your-project.livekit.cloud
LIVEKIT_API_KEY=your-api-key
LIVEKIT_API_SECRET=your-api-secret
OPENAI_API_KEY=your-openai-key
```

Create `.env.sip` with your Telnyx credentials:
```bash
TELNYX_SIP_USER=andrepemmelaar  # No underscores!
TELNYX_SIP_PASSWORD=your_password
TELNYX_PHONE_NUMBER=+18773893410  # Your Telnyx number
TELNYX_SIP_SERVER=sip.telnyx.com
```

### 3. Create LiveKit SIP Trunks

```bash
# Create outbound trunk (CRITICAL: include :5060 port!)
lk sip outbound create --name "Telnyx Outbound" \
  --address "sip.telnyx.com:5060" \
  --transport "UDP" \
  --numbers "+18773893410" \
  --auth-user "andrepemmelaar" \
  --auth-pass "your_password"

# Save the returned trunk ID to .env.sip as OUTBOUND_TRUNK_ID

# Create inbound trunk
lk sip inbound create --name "Telnyx Inbound" \
  --numbers "+18773893410"

# Save the returned trunk ID to .env.sip as INBOUND_TRUNK_ID
```

**IMPORTANT**: The `:5060` port in the address is REQUIRED for proper SIP header construction!

## Working Configuration Summary

### Key Requirements for Successful SIP Integration

1. **Telnyx Configuration**:
   - FQDN: Your LiveKit project's SIP endpoint (e.g., `dev-scheduling-ai-fcg41leb.sip.livekit.cloud`)
   - Username: No underscores allowed (e.g., `andrepemmelaar` not `andre_pemmelaar`)
   - Transport: UDP on port 5060

2. **LiveKit Trunk Configuration**:
   - **CRITICAL**: Address must include port: `sip.telnyx.com:5060`
   - Transport: UDP (not AUTO)
   - Authentication: Username without underscores

3. **Agent Dispatch for Outbound Calls**:
   - Must use explicit dispatch via `agent_dispatch.create_dispatch()`
   - Cannot rely on automatic dispatch for programmatically created rooms
   - Agent with `agent_name` parameter requires explicit dispatch

4. **Code Requirements**:
   - Use `ParticipantKind.PARTICIPANT_KIND_SIP` (not `ParticipantKind.SIP`)
   - Accept all rooms with custom `request_fnc` in WorkerOptions
   - Handle job metadata for appointment details

## Usage

### Starting the Enhanced SIP Agent

The enhanced agent handles both web and SIP connections:

```bash
# Start the enhanced SIP agent
make gemini-sip

# Or with auto-reload for development
make gemini-sip-dev
```

### Receiving Inbound Calls

1. Start the agent: `make gemini-sip`
2. Call your Telnyx number: **+1 (720) 573-8374**
3. The agent will:
   - Detect it's a SIP call
   - Look up appointment details by phone number
   - Greet the caller and confirm their appointment
   - Handle DTMF input (press 1 to confirm, 2 to reschedule, 0 for operator)

### Making Outbound Calls

Edit the call list in `outbound_caller.py` with your target numbers and appointment details, then:

```bash
# Make outbound appointment confirmation calls
make outbound-calls
```

The script will:
- Process each number in the list
- Create a room for each call
- Initiate the SIP connection
- Wait 30 seconds between calls

### Testing Web vs SIP Behavior

The agent automatically detects the connection type:

**Web Connection:**
- Uses Arabic language support (ar-XA)
- Provides visual-friendly responses
- Standard web interaction patterns

**SIP Connection:**
- Uses English for better telephony compatibility
- Extra-clear speech patterns
- Handles DTMF input
- Phone-optimized responses

## Features

### DTMF Support

When on a phone call, users can press:
- **1** - Confirm appointment
- **2** - Request reschedule
- **0** - Transfer to operator
- Other digits are acknowledged by the agent

### Automatic Phone Number Lookup

The agent looks up appointment details based on the caller's phone number, providing personalized greetings and information.

### Call State Management

The agent tracks:
- Confirmation status (confirmed, cancelled, rescheduled)
- Walk-in preferences
- Reminder preferences
- Call transfer status

## Managing SIP Configuration

### View Current Trunks

```bash
# List all configured trunks
make list-sip-trunks

# List dispatch rules
make list-sip-dispatch
```

### Update Trunk Configuration

Edit the JSON files in `sip_config/` and re-run:
```bash
lk sip inbound update sip_config/inbound_trunk.json
lk sip outbound update sip_config/outbound_trunk.json
```

## Troubleshooting

### Common Issues

1. **Agent not joining outbound calls**
   - **Solution**: Use explicit agent dispatch when creating rooms
   ```python
   # Create room first
   room = await livekit_api.room.create_room(room_request)
   
   # Then dispatch agent explicitly
   dispatch = await livekit_api.agent_dispatch.create_dispatch(
       api.CreateAgentDispatchRequest(
           agent_name="gemini-sip-agent",
           room=room_name,
           metadata=json.dumps(metadata)
       )
   )
   ```
   - Agents with `agent_name` are not auto-dispatched to programmatically created rooms

2. **"Assignment timeout" errors**
   - Ensure the agent is running: `make gemini-sip`
   - Check LiveKit credentials are correct
   - Verify agent dispatch is configured correctly

3. **Calls not connecting**
   - Verify Telnyx FQDN matches your LiveKit project
   - Check authentication credentials (no underscores in username!)
   - Ensure phone number is associated with SIP connection
   - **CRITICAL**: Include port `:5060` in trunk address

4. **No audio on calls**
   - Ensure agent is properly dispatched to the room
   - Check firewall settings for SIP/RTP ports
   - Verify transport protocol (UDP recommended)
   - Confirm agent is using correct ParticipantKind enum: `PARTICIPANT_KIND_SIP`

### Debug Logging

Enable verbose logging by setting:
```python
logging.basicConfig(level=logging.DEBUG)
```

Check logs for:
- SIP participant detection
- DTMF events
- Call state changes
- Error messages

## Production Considerations

### Security
- Store credentials securely (use environment variables)
- Implement rate limiting for outbound calls
- Add authentication for API endpoints

### Compliance
- Follow TCPA regulations for automated calling
- Implement Do Not Call list checking
- Respect calling time restrictions

### Scaling
- Use connection pooling for database lookups
- Implement call queue management
- Monitor trunk capacity limits

### Monitoring
- Track call success rates
- Monitor audio quality metrics
- Set up alerts for failures

## API Reference

### Key Functions

```python
# Detect SIP participant
is_sip, sip_attrs = detect_sip_participant(participant)

# Access SIP attributes
phone_number = sip_attrs.get('sip.phoneNumber')
trunk_id = sip_attrs.get('sip.trunkID')
call_id = sip_attrs.get('sip.callID')

# Make outbound call
await make_call(phone_number, appointment_details)
```

### Environment Variables

- `LIVEKIT_URL` - LiveKit server URL
- `LIVEKIT_API_KEY` - API key for LiveKit
- `LIVEKIT_API_SECRET` - API secret for LiveKit
- `INBOUND_TRUNK_ID` - ID of inbound SIP trunk
- `OUTBOUND_TRUNK_ID` - ID of outbound SIP trunk

## Next Steps

1. **Database Integration**: Replace mock appointment lookup with real database queries
2. **Call Recording**: Enable call recording for quality assurance
3. **Analytics**: Implement call analytics and reporting
4. **IVR Menu**: Build interactive voice response menus
5. **SMS Integration**: Add SMS confirmations alongside voice calls