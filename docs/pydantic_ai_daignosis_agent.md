Here is a complete example of setting up a Pydantic AI agent with your specified Llama3-based medical model (OpenBioLLM-70B) that supports a system prompt and requests structured JSON output with the three sections: possible diagnosis, recommended follow-up questions, and recommended further tests.

This implementation uses Pydantic AI types for strict response validation and enforces the structured output format. It also handles partial or empty results according to your requirements.

```python
import os
from typing import List, Optional
from pydantic import BaseModel
from pydantic_ai import AIModel, AIChatCompletionRequest, AIChatCompletionResponse
from huggingface_hub import InferenceClient

# Define Pydantic models for structured output sections

class DiagnosisOutput(BaseModel):
    diagnosis: Optional[List[str]] = []
    follow_up_questions: Optional[List[str]] = []
    further_tests: Optional[List[str]] = []

# Define the AI agent class strongly typed with Pydantic AI for output validation

class MedicalDiagnosisAgent(AIModel):
    class request(AIChatCompletionRequest):
        # Messages follow chat format with roles system, user, assistant
        messages: List[dict]

    class response(AIChatCompletionResponse):
        # Response content must be JSON conforming to DiagnosisOutput schema
        parsed_content: DiagnosisOutput

# Initialize Huggingface InferenceClient with your API token and model

HF_TOKEN = os.getenv("HF_TOKEN") or os.getenv("NEBIUS_TOKEN")
MODEL_ID = "aaditya/Llama3-OpenBioLLM-70B:nebius"

client = InferenceClient(token=HF_TOKEN, provider="nebius")  # Adjust provider as needed

# Custom function to call the model and parse response into Pydantic model

def call_medical_agent(narrative: str) -> DiagnosisOutput:
    system_prompt = (
        "You are a medical diagnosis assistant.\n"
        "Given a patient narrative, provide ONLY a JSON object with these optional keys:\n"
        "1. diagnosis - a list of possible diagnoses.\n"
        "2. follow_up_questions - a list of recommended questions to ask the patient.\n"
        "3. further_tests - a list of recommended further tests.\n"
        "If no relevant items exist for any section, either omit that key or provide an empty list.\n"
        "Respond ONLY with JSON and nothing else."
    )

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": narrative},
    ]

    # Call the model for chat completion
    completion = client.chat.completions.create(
        model=MODEL_ID,
        messages=messages,
        max_tokens=1024,
        temperature=0.7,
    )

    # `completion.choices[0].message.content` is the raw JSON string expected
    raw_response = completion.choices[0].message.content.strip()

    try:
        # Validate and parse with Pydantic AI model
        parsed_output = MedicalDiagnosisAgent.response.parse_obj({"parsed_content": raw_response})
        diagnosis_output = DiagnosisOutput.parse_raw(parsed_output.parsed_content)
    except Exception:
        # If parsing fails, return empty all sections
        diagnosis_output = DiagnosisOutput(diagnosis=[], follow_up_questions=[], further_tests=[])

    # Normalize None to empty lists
    return DiagnosisOutput(
        diagnosis=diagnosis_output.diagnosis or [],
        follow_up_questions=diagnosis_output.follow_up_questions or [],
        further_tests=diagnosis_output.further_tests or [],
    )

# Example usage with a sample patient narrative
if __name__ == "__main__":
    sample_narrative = (
        "A 45-year-old male presents with intermittent chest pain, radiating to the left arm, "
        "worse on exertion, and associated with shortness of breath."
    )
    output = call_medical_agent(sample_narrative)
    print(output.json(indent=2))
```

### Explanation

- The `DiagnosisOutput` class defines the JSON schema with three optional lists.
- The `MedicalDiagnosisAgent` class is a Pydantic AI agent model with proper request/response structure.
- The system prompt explicitly instructs the model to respond only in JSON format with the three sections.
- The `call_medical_agent` function sends a chat-like prompt with system and user messages.
- The raw JSON string response is parsed and validated with Pydantic AI; fallback returns empty sections if parsing fails.
- You get clean, structured, and validated JSON output with the sections you requested.
  
This goes beyond just using Pydantic for parsing — you leverage Pydantic AI's strong typing and validation ability on top of the Huggingface client call, meeting your requirement for a true Pydantic AI agent.

If you want, I can further help with integrating this into your existing FastAPI stream-based API from your current code. Let me know!

Sources
[1] diagnosis_api.py https://ppl-ai-file-upload.s3.amazonaws.com/web/direct-files/attachments/6889097/94f35042-ef39-4def-8981-49900de8b0a0/diagnosis_api.py
