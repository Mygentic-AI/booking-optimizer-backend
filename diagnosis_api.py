import os
import asyncio
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from huggingface_hub import InferenceClient
from typing import AsyncGenerator
import logging
import requests
import json

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI()

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3005", "http://localhost:3000", "http://localhost:3001", "http://localhost:3002", "http://localhost:3003"],  # Frontend URLs
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize HuggingFace InferenceClient with Nebius provider
from dotenv import load_dotenv
load_dotenv()

# Try Nebius token first, then fall back to HF token
nebius_token = os.environ.get("NEBIUS_TOKEN", "")
hf_token = os.environ.get("HF_TOKEN", "")
api_key = nebius_token or hf_token

logger.info(f"Using token: {'NEBIUS' if nebius_token else 'HF'}... {api_key[:20] if api_key else 'NOT SET'}... (truncated)")

client = InferenceClient(
    provider="nebius",
    token=api_key
)

MODEL = os.environ.get("HUGGINGFACE_MODEL", "aaditya/Llama3-OpenBioLLM-70B:nebius")

async def generate_diagnosis_stream(message: str) -> AsyncGenerator[str, None]:
    """Generate streaming diagnosis response from HuggingFace model"""
    try:
        # Create chat completion with streaming
        messages = [
            {
                "role": "system", 
                "content": "You are a medical diagnosis assistant. Provide helpful medical information based on symptoms described. Always remind users to consult with a healthcare professional for proper diagnosis and treatment."
            },
            {"role": "user", "content": message}
        ]
        
        # HuggingFace InferenceClient stream
        stream = client.chat.completions.create(
            model=MODEL,
            messages=messages,
            stream=True,
            max_tokens=1024,
            temperature=0.7
        )
        
        # Stream each chunk as Server-Sent Event
        for chunk in stream:
            if chunk.choices and chunk.choices[0].delta.content:
                content = chunk.choices[0].delta.content
                yield f"data: {content}\n\n"
                
    except Exception as e:
        logger.error(f"Error in diagnosis stream: {e}")
        yield f"data: Error: {str(e)}\n\n"

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
    return {"status": "healthy", "model": MODEL}

if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("DIAGNOSIS_API_PORT", "8000"))
    logger.info(f"Starting diagnosis API on port {port}")
    uvicorn.run(app, host="0.0.0.0", port=port)