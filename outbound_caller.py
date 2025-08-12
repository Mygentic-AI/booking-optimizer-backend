#!/usr/bin/env python3
"""
Outbound SIP Calling Script for Appointment Confirmations
"""

import asyncio
import os
import logging
import json
from datetime import datetime
from typing import List, Dict, Any
from dotenv import load_dotenv
from livekit import api

# Load environment variables
load_dotenv()
load_dotenv('.env.sip')

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("outbound-caller")


class OutboundCallManager:
    """Manages outbound appointment confirmation calls."""
    
    def __init__(self):
        self.livekit_api = api.LiveKitAPI(
            url=os.getenv("LIVEKIT_URL"),
            api_key=os.getenv("LIVEKIT_API_KEY"),
            api_secret=os.getenv("LIVEKIT_API_SECRET")
        )
        self.outbound_trunk_id = os.getenv("OUTBOUND_TRUNK_ID")
        
        if not self.outbound_trunk_id:
            raise ValueError("OUTBOUND_TRUNK_ID not found. Please run setup_sip.sh first.")
    
    async def make_call(
        self, 
        phone_number: str, 
        appointment_details: Dict[str, Any]
    ) -> bool:
        """
        Make an outbound call to confirm an appointment.
        
        Args:
            phone_number: The phone number to call (E.164 format)
            appointment_details: Dictionary with appointment information
            
        Returns:
            bool: True if call was initiated successfully
        """
        try:
            # Generate unique room name for this call
            room_name = f"outbound_{phone_number.replace('+', '')}_{int(datetime.now().timestamp())}"
            
            logger.info(f"Initiating call to {phone_number} in room {room_name}")
            
            # Prepare metadata for the agent
            metadata = {
                "type": "outbound_appointment_call",
                "appointment": appointment_details,
                "phone_number": phone_number
            }
            
            # Create the room first
            room_request = api.CreateRoomRequest(
                name=room_name,
                empty_timeout=300,  # 5 minutes
                max_participants=2
            )
            room = await self.livekit_api.room.create_room(room_request)
            logger.info(f"Created room: {room.name}")
            
            # Explicitly dispatch the agent to the room
            dispatch_request = api.CreateAgentDispatchRequest(
                agent_name="gemini-sip-agent",  # Must match the agent_name in enhanced_gemini_sip_agent.py
                room=room_name,
                metadata=json.dumps(metadata)
            )
            dispatch = await self.livekit_api.agent_dispatch.create_dispatch(dispatch_request)
            logger.info(f"Agent dispatched to room: {dispatch.id}")
            
            # Create SIP participant for outbound call
            sip_request = api.CreateSIPParticipantRequest(
                room_name=room_name,
                sip_trunk_id=self.outbound_trunk_id,
                sip_call_to=phone_number,
                participant_identity=f"outbound_{phone_number}",
                participant_name=f"Call to {appointment_details.get('patient_name', 'Patient')}"
            )
            
            sip_participant = await self.livekit_api.sip.create_sip_participant(sip_request)
            logger.info(f"SIP participant created: {sip_participant.participant_id}")
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to initiate call to {phone_number}: {e}")
            return False
    
    async def make_bulk_calls(
        self, 
        call_list: List[Dict[str, Any]],
        delay_between_calls: int = 30
    ):
        """
        Make multiple outbound calls with delays between them.
        
        Args:
            call_list: List of dictionaries with 'phone_number' and 'appointment_details'
            delay_between_calls: Seconds to wait between calls
        """
        successful_calls = 0
        failed_calls = 0
        
        for idx, call_info in enumerate(call_list, 1):
            phone_number = call_info['phone_number']
            appointment_details = call_info['appointment_details']
            
            logger.info(f"Processing call {idx}/{len(call_list)}: {phone_number}")
            
            success = await self.make_call(phone_number, appointment_details)
            
            if success:
                successful_calls += 1
                logger.info(f"✅ Call initiated successfully to {phone_number}")
            else:
                failed_calls += 1
                logger.error(f"❌ Failed to initiate call to {phone_number}")
            
            # Wait before next call (except for the last one)
            if idx < len(call_list):
                logger.info(f"Waiting {delay_between_calls} seconds before next call...")
                await asyncio.sleep(delay_between_calls)
        
        logger.info(f"\n📊 Call Summary:")
        logger.info(f"  Successful: {successful_calls}")
        logger.info(f"  Failed: {failed_calls}")
        logger.info(f"  Total: {len(call_list)}")
    
    async def close(self):
        """Close the API connection."""
        await self.livekit_api.aclose()


async def main():
    """Main function to run outbound calls."""
    
    # Sample appointment confirmations to make
    # In production, this would come from your database
    call_list = [
        {
            "phone_number": "+971585089156",  # Your UAE number
            "appointment_details": {
                "date": "tomorrow at 3:00 PM",
                "service": "consultation",
                "doctor": "Dr. Sarah",
                "location": "Downtown Medical Center",
                "patient_name": "Andre Pemmelaar",
            }
        },
        # Add more appointments here if needed
        # {
        #     "phone_number": "+971XXXXXXXXX",
        #     "appointment_details": {
        #         "date": "Friday at 10:00 AM",
        #         "service": "follow-up",
        #         "doctor": "Dr. Ahmed",
        #         "location": "Downtown Medical Center",
        #         "patient_name": "John Smith",
        #     }
        # },
    ]
    
    manager = OutboundCallManager()
    
    try:
        logger.info("🚀 Starting outbound appointment confirmation calls...")
        logger.info(f"📞 Total calls to make: {len(call_list)}")
        
        await manager.make_bulk_calls(call_list)
        
        logger.info("✅ All calls processed!")
        
    except Exception as e:
        logger.error(f"Error in main: {e}")
    finally:
        await manager.close()


if __name__ == "__main__":
    # Check for required environment variables
    required_vars = [
        "LIVEKIT_URL",
        "LIVEKIT_API_KEY", 
        "LIVEKIT_API_SECRET",
        "OUTBOUND_TRUNK_ID"
    ]
    
    missing_vars = [var for var in required_vars if not os.getenv(var)]
    
    if missing_vars:
        print(f"❌ Missing required environment variables: {', '.join(missing_vars)}")
        print("Please ensure all variables are set in .env and .env.sip files")
        print("Run ./setup_sip.sh to configure SIP trunks first")
        exit(1)
    
    asyncio.run(main())