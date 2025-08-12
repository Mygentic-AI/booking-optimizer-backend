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

1. Go to **SIP Connections**
2. Create or edit your SIP connection with these settings:
   - **Connection Type**: FQDN
   - **FQDN**: `your-project-id.sip.livekit.cloud` (get from LiveKit dashboard)
   - **Authentication**: Credentials
   - **Username**: `andre_pemmelaar` (your username)
   - **Password**: Your SIP password
   - **Transport**: TCP (recommended)
   - **Inbound Destination**: +E.164 format

3. Associate your phone number(s) with this SIP connection

### 2. Set Up Environment Variables

Add to your `.env` file:
```bash
# Existing LiveKit credentials
LIVEKIT_URL=wss://your-project.livekit.cloud
LIVEKIT_API_KEY=your-api-key
LIVEKIT_API_SECRET=your-api-secret
OPENAI_API_KEY=your-openai-key
```

The SIP credentials are already in `.env.sip`:
```bash
TELNYX_SIP_USER=andre_pemmelaar
TELNYX_SIP_PASSWORD=d5vw3nQNWAjgD7X3kJ
TELNYX_PHONE_NUMBER=+17205738374
```

### 3. Run Setup Script

```bash
# Make the setup script executable and run it
make setup-sip
```

This will:
- Create inbound and outbound SIP trunks in LiveKit
- Configure dispatch rules for incoming calls
- Save trunk IDs to `.env.sip`

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

1. **"Assignment timeout" errors**
   - Ensure the agent is running: `make gemini-sip`
   - Check LiveKit credentials are correct
   - Verify dispatch rules are configured

2. **Calls not connecting**
   - Verify Telnyx FQDN matches your LiveKit project
   - Check authentication credentials
   - Ensure phone number is associated with SIP connection

3. **No audio on calls**
   - Check firewall settings for SIP/RTP ports
   - Verify transport protocol (TCP vs UDP)
   - Test with a different phone number

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