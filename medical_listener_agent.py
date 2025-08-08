#!/usr/bin/env python3
"""
Basic Medical Listener Agent
Minimal implementation - just receives text and responds
"""

import os
import asyncio
import json
import logging
from datetime import datetime
from openai import AsyncOpenAI
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class MedicalListenerAgent:
    def __init__(self, session_id=None):
        # Initialize OpenAI client
        self.client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        
        # Initialize medical narrative
        self.medical_narrative = ""
        
        # Session ID for logging
        self.session_id = session_id or datetime.now().strftime('%Y%m%d_%H%M%S')
        
        # Create logs directory if it doesn't exist
        os.makedirs("logs", exist_ok=True)
        os.makedirs("medical_extracts", exist_ok=True)
        
        # Set up session-specific log file
        self.log_file = f"logs/medical_listener_{self.session_id}.log"
        self.json_file = f"medical_extracts/facts_{self.session_id}.json"
        
        # Log session start
        self._log_to_file(f"Session started: {self.session_id}")
        logger.info(f"Medical listener session started: {self.session_id}")
        
        # System prompt for narrative building
        self.system_prompt = """You are a medical listening AI assistant. 
Your role is to maintain a medical summary of the patient's condition based on doctor-patient conversations.
Update the summary with new relevant medical information while maintaining a coherent narrative.
Keep the summary concise but comprehensive, focusing on symptoms, duration, triggers, and relevant medical history.
Use clear, short sentences."""
    
    async def process_input(self, text: str) -> str:
        """
        Process input text and update the medical narrative
        """
        try:
            # Log the conversation chunk
            self._log_to_file(f"[INPUT] {text}")
            
            # Create prompt to update narrative
            update_prompt = f"""Current medical summary:
{self.medical_narrative if self.medical_narrative else "No medical information yet."}

New conversation:
{text}

Update the medical summary to include any new relevant medical information from this conversation. 
Keep sentences short and clear. Avoid repetition.
If no new medical information is present, return the current summary unchanged.
Focus on: patient demographics, symptoms, duration, triggers, medical history, medications, and relevant context."""

            response = await self.client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": self.system_prompt},
                    {"role": "user", "content": update_prompt}
                ],
                temperature=0.3,  # Lower temperature for consistency
                max_tokens=300  # Original value for complete summaries
            )
            
            # Get the updated narrative
            updated_narrative = response.choices[0].message.content.strip()
            
            # Check if narrative was actually updated
            if updated_narrative and updated_narrative != self.medical_narrative:
                self._log_to_file(f"[NARRATIVE UPDATED]")
                self.medical_narrative = updated_narrative
            else:
                self._log_to_file(f"[NO NEW MEDICAL INFO]")
            
            # Log current narrative state
            self._log_to_file(f"[CURRENT NARRATIVE] {self.medical_narrative}")
            
            # Save to JSON
            self._save_narrative_to_json()
            
            return f"Medical Summary:\n{self.medical_narrative}"
            
        except Exception as e:
            error_msg = f"Error: {str(e)}"
            self._log_to_file(f"[ERROR] {error_msg}")
            logger.error(error_msg)
            return error_msg
    
    def _log_to_file(self, message: str):
        """Write to session-specific log file"""
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        with open(self.log_file, 'a') as f:
            f.write(f"{timestamp} - {message}\n")
    
    def _save_narrative_to_json(self):
        """Save medical narrative to JSON file"""
        data = {
            "session_id": self.session_id,
            "timestamp": datetime.now().isoformat(),
            "medical_summary": self.medical_narrative,
            "word_count": len(self.medical_narrative.split()) if self.medical_narrative else 0
        }
        with open(self.json_file, 'w') as f:
            json.dump(data, f, indent=2)
    
    def reset(self):
        """Reset medical narrative for a new conversation"""
        self._log_to_file("Session reset")
        self.medical_narrative = ""

async def test_agent():
    """
    Simple test function to verify the agent works
    """
    print("Starting Medical Listener Agent Test...")
    
    # Create agent with specific session ID for testing
    session_id = f"test_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    agent = MedicalListenerAgent(session_id=session_id)
    
    print(f"Session ID: {session_id}")
    print(f"Log file: {agent.log_file}")
    print(f"JSON file: {agent.json_file}")
    
    # Test cases - doctor-patient conversation snippets
    test_inputs = [
        "Doctor: Good morning, what brings you in today? Patient: Hi doctor, I've been having this chest pain for about 3 days now.",
        "Doctor: I see. Are you taking any medications? Patient: Yes, I take metoprolol, I think it's 50mg once a day.",
        "Patient: Oh, I should mention I'm allergic to penicillin. I get a rash when I take it. Doctor: Good to know, I'll make a note.",
        "Doctor: Let me check your blood pressure. Okay, it's reading 140 over 90, which is a bit elevated.",
        "Patient: The pain gets worse when I climb stairs or walk fast. Doctor: How would you rate the pain? Patient: Maybe 7 out of 10."
    ]
    
    for i, test_input in enumerate(test_inputs, 1):
        print(f"\n{'='*60}")
        print(f"Conversation chunk {i}:")
        print(f"Input: {test_input}")
        response = await agent.process_input(test_input)
        print(f"\nOutput: {response}")
    
    print(f"\n{'='*60}")
    print(f"Test complete! Check the output files:")
    print(f"- Log file: {agent.log_file}")
    print(f"- JSON file: {agent.json_file}")

if __name__ == "__main__":
    # Run the test
    asyncio.run(test_agent())