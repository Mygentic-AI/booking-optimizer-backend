#!/bin/bash

# SIP Setup Script for LiveKit with Telnyx
# This script configures the SIP trunks and dispatch rules

echo "Setting up SIP integration with Telnyx..."

# Check if lk CLI is installed
if ! command -v lk &> /dev/null; then
    echo "Error: LiveKit CLI (lk) is not installed."
    echo "Please install it first: https://docs.livekit.io/cli/"
    exit 1
fi

# Source environment variables
if [ -f .env ]; then
    export $(cat .env | grep -v '^#' | xargs)
fi

if [ -f .env.sip ]; then
    export $(cat .env.sip | grep -v '^#' | xargs)
fi

# Check for required environment variables
if [ -z "$LIVEKIT_API_KEY" ] || [ -z "$LIVEKIT_API_SECRET" ] || [ -z "$LIVEKIT_URL" ]; then
    echo "Error: Missing LiveKit credentials in .env file"
    echo "Please ensure LIVEKIT_API_KEY, LIVEKIT_API_SECRET, and LIVEKIT_URL are set"
    exit 1
fi

echo "1. Creating inbound trunk..."
INBOUND_RESPONSE=$(lk sip inbound create sip_config/inbound_trunk.json 2>&1)
if [ $? -eq 0 ]; then
    INBOUND_TRUNK_ID=$(echo "$INBOUND_RESPONSE" | grep -oE 'ST_[a-zA-Z0-9]+')
    echo "   Inbound trunk created: $INBOUND_TRUNK_ID"
    
    # Update .env.sip with the trunk ID
    sed -i.bak "s/INBOUND_TRUNK_ID=.*/INBOUND_TRUNK_ID=$INBOUND_TRUNK_ID/" .env.sip
else
    echo "   Error creating inbound trunk: $INBOUND_RESPONSE"
    exit 1
fi

echo "2. Creating outbound trunk..."
OUTBOUND_RESPONSE=$(lk sip outbound create sip_config/outbound_trunk.json 2>&1)
if [ $? -eq 0 ]; then
    OUTBOUND_TRUNK_ID=$(echo "$OUTBOUND_RESPONSE" | grep -oE 'ST_[a-zA-Z0-9]+')
    echo "   Outbound trunk created: $OUTBOUND_TRUNK_ID"
    
    # Update .env.sip with the trunk ID
    sed -i.bak "s/OUTBOUND_TRUNK_ID=.*/OUTBOUND_TRUNK_ID=$OUTBOUND_TRUNK_ID/" .env.sip
else
    echo "   Error creating outbound trunk: $OUTBOUND_RESPONSE"
    exit 1
fi

echo "3. Updating dispatch rule with trunk ID..."
# Update the dispatch rule JSON with the actual trunk ID
sed "s/WILL_BE_REPLACED_WITH_ACTUAL_TRUNK_ID/$INBOUND_TRUNK_ID/g" sip_config/dispatch_rule.json > sip_config/dispatch_rule_configured.json

echo "4. Creating dispatch rule..."
DISPATCH_RESPONSE=$(lk sip dispatch create sip_config/dispatch_rule_configured.json 2>&1)
if [ $? -eq 0 ]; then
    echo "   Dispatch rule created successfully"
else
    echo "   Error creating dispatch rule: $DISPATCH_RESPONSE"
    exit 1
fi

echo ""
echo "✅ SIP Setup Complete!"
echo ""
echo "Important Configuration in Telnyx Portal:"
echo "1. Go to your Telnyx SIP Connection settings"
echo "2. Set the SIP URI to: $(echo $LIVEKIT_URL | sed 's/wss:\/\///' | sed 's/livekit.cloud/.sip.livekit.cloud/')"
echo "3. Ensure Authentication is set to: Credentials"
echo "4. Username: andre_pemmelaar"
echo "5. Transport: TCP or UDP (TCP recommended)"
echo ""
echo "Trunk IDs saved to .env.sip:"
echo "  Inbound Trunk: $INBOUND_TRUNK_ID"
echo "  Outbound Trunk: $OUTBOUND_TRUNK_ID"
echo ""
echo "To test inbound calls:"
echo "  1. Start the enhanced SIP agent: python enhanced_gemini_sip_agent.py dev"
echo "  2. Call your Telnyx number: +17205738374"
echo ""
echo "To make outbound calls:"
echo "  Run: python outbound_caller.py"