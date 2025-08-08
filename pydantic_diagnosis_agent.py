#!/usr/bin/env python3
"""
PydanticAI-based diagnosis agent that processes medical narratives
and returns structured diagnosis information.
"""

import os
from typing import List, Optional, AsyncGenerator
from pydantic import BaseModel, Field
from huggingface_hub import InferenceClient
import json
import logging
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse

# Load environment variables
load_dotenv()

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Create FastAPI app
app = FastAPI()

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3005", "http://localhost:3000", "http://localhost:3001", "http://localhost:3002", "http://localhost:3003"],  # Frontend URLs
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Define Pydantic models for structured output sections
class DiagnosisOutput(BaseModel):
    diagnosis: Optional[List[str]] = Field(default_factory=list, description="List of possible diagnoses")
    follow_up_questions: Optional[List[str]] = Field(default_factory=list, description="Questions to ask the patient")
    further_tests: Optional[List[str]] = Field(default_factory=list, description="Recommended medical tests")

# Initialize Huggingface InferenceClient with Nebius provider
nebius_token = os.environ.get("NEBIUS_TOKEN", "")
hf_token = os.environ.get("HF_TOKEN", "")
api_key = nebius_token or hf_token

logger.info(f"Using token: {'NEBIUS' if nebius_token else 'HF'}... {api_key[:20] if api_key else 'NOT SET'}... (truncated)")

client = InferenceClient(
    provider="nebius",
    token=api_key
)

MODEL_ID = os.environ.get("HUGGINGFACE_MODEL", "aaditya/Llama3-OpenBioLLM-70B:nebius")

# Custom function to call the model and parse response into Pydantic model
def call_medical_agent(narrative: str) -> DiagnosisOutput:
    """
    Process a medical narrative and return structured diagnosis information.
    
    Args:
        narrative: Medical summary text from the conversation
        
    Returns:
        DiagnosisOutput with diagnosis, follow-up questions, and recommended tests
    """
    system_prompt = (
        "You are a medical diagnosis assistant. You will receive a patient narrative containing symptoms and history.\n\n"
        "DIAGNOSIS GUIDELINES:\n"
        "- If you have ANY symptoms with duration and characteristics, provide possible diagnoses\n"
        "- Be proactive - suggest likely conditions based on available information\n"
        "- Include both common and serious conditions that fit the symptoms\n"
        "- Example: chronic diarrhea + gluten triggers = suggest celiac disease, IBS, gluten sensitivity\n\n"
        "ONLY if there's literally NO medical information (just greetings/age):\n"
        "- Provide empty diagnosis array\n"
        "- Focus on gathering initial symptoms\n\n"
        "For ALL other cases, provide:\n"
        "1. Differential diagnoses - List conditions that match the symptoms (even with partial info)\n"
        "2. Follow-up questions - 1-2 questions to refine or confirm diagnosis\n"
        "3. Diagnostic tests - Tests that would confirm your suspected diagnoses\n\n"
        "Format your response as a JSON object with exactly these keys:\n"
        "- \"diagnosis\": array of possible diagnoses based on current symptoms\n"
        "- \"follow_up_questions\": array of 1-2 clarifying questions\n"
        "- \"further_tests\": array of tests to confirm suspected diagnoses\n\n"
        "Be helpful and provide diagnoses when symptoms are described. Respond ONLY with the JSON object."
    )

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": narrative},
    ]

    try:
        # Call the model for chat completion
        completion = client.chat.completions.create(
            model=MODEL_ID,
            messages=messages,
            max_tokens=1024,
            temperature=0.7,
        )

        # Extract the raw JSON string from response
        raw_response = completion.choices[0].message.content.strip()
        logger.info(f"Raw response from model: {raw_response[:200]}...")
        
        # Try to parse as JSON
        try:
            # Clean up the response if needed (remove markdown code blocks)
            if raw_response.startswith("```json"):
                raw_response = raw_response[7:]
            if raw_response.startswith("```"):
                raw_response = raw_response[3:]
            if raw_response.endswith("```"):
                raw_response = raw_response[:-3]
            raw_response = raw_response.strip()
            
            # Parse JSON
            json_data = json.loads(raw_response)
            
            # Create DiagnosisOutput from parsed JSON
            diagnosis_output = DiagnosisOutput(
                diagnosis=json_data.get("diagnosis", []),
                follow_up_questions=json_data.get("follow_up_questions", []),
                further_tests=json_data.get("further_tests", [])
            )
            
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON: {e}")
            logger.error(f"Raw response: {raw_response}")
            # Return empty structure on parse failure
            diagnosis_output = DiagnosisOutput()
            
    except Exception as e:
        logger.error(f"Error calling diagnosis model: {e}")
        # Return empty structure on API failure
        diagnosis_output = DiagnosisOutput()

    # Ensure all fields are lists (not None)
    return DiagnosisOutput(
        diagnosis=diagnosis_output.diagnosis or [],
        follow_up_questions=diagnosis_output.follow_up_questions or [],
        further_tests=diagnosis_output.further_tests or []
    )

async def generate_diagnosis_stream(message: str) -> AsyncGenerator[str, None]:
    """Generate streaming diagnosis response from the agent"""
    try:
        # Get structured diagnosis output
        diagnosis_output = call_medical_agent(message)
        
        # Convert to JSON and stream it
        result = {
            "diagnosis": diagnosis_output.diagnosis,
            "follow_up_questions": diagnosis_output.follow_up_questions,
            "further_tests": diagnosis_output.further_tests
        }
        
        yield f"data: {json.dumps(result)}\n\n"
        
    except Exception as e:
        logger.error(f"Error in diagnosis stream: {e}")
        yield f"data: {json.dumps({'error': str(e)})}\n\n"

@app.get("/api/diagnosis/chat")
async def diagnosis_chat(message: str):
    """Endpoint for diagnosis chat with streaming response"""
    if not message:
        raise HTTPException(status_code=400, detail="Message is required")
    
    logger.info(f"Received diagnosis request: {message[:50]}...")
    
    return StreamingResponse(
        generate_diagnosis_stream(message),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",  # Disable Nginx buffering
        }
    )

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "model": MODEL_ID, "type": "pydantic_diagnosis_agent"}

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("DIAGNOSIS_API_PORT", "8000"))
    logger.info(f"Starting pydantic diagnosis agent on port {port}")
    uvicorn.run(app, host="0.0.0.0", port=port)