import os
import base64
import json
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional
from google import genai
from google.genai import types
import uvicorn

app = FastAPI()

# Enable CORS for frontend asset delivery mapping
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize the Google GenAI SDK client
GEMINI_KEY = os.getenv("GEMINI_API_KEY")
client = genai.Client(api_key=GEMINI_KEY)

class AnalyzeRequest(BaseModel):
    type: str
    content: str
    mimeType: Optional[str] = "image/jpeg"

class ChatRequest(BaseModel):
    reportContext: Optional[str] = ""
    userQuestion: str

ANALYSIS_PROMPT = """
You are MedAI, an advanced medical report interpreter. Analyze this medical report data and provide a structured JSON output. 
Strictly return ONLY a valid JSON object matching this structure:
{
  "rawReportSummary": "A concise, 3-sentence summary of the overall health findings.",
  "terms": [
    {"term": "Medical Term", "simpleDefinition": "A ultra-short jargon-free 1-sentence explanation."}
  ],
  "flaggedValues": [
    {
      "testName": "Biomarker Name",
      "value": "Patient's value",
      "meaning": "Clear statement of whether this is High/Low/Normal."
    }
  ],
  "questions": [
    "Suggested question 1 for their doctor",
    "Suggested question 2 for their doctor"
  ]
}
"""

CHAT_PROMPT_TEMPLATE = """
You are MedAI, an intelligent, empathetic, and highly capable Indian First-Aid & OTC Medication Assistant. Your purpose is to evaluate the user's specific symptoms or questions dynamically and have an intelligent, tailored medical conversation.

User's Input: {question}

Core Directives for Dynamic Reasoning:
1. NO AUTOMATIC REFUSALS: Do not hide behind corporate AI boilerplate text ("I cannot give medical advice", "As an AI...", etc.). You are fully permitted to discuss common minor ailments and standard Indian first-aid options.
2. DYNAMIC EVALUATION: Listen carefully to the user's unique situation. Think about what they are actually describing. Treat each user as an individual case with different needs, severity levels, and contexts.
3. CONVERSATIONAL TRIAGE: Ask highly relevant, smart follow-up questions tailored to their specific complaint (e.g., inquiring about the exact location of a headache, the frequency of a stomach ache, or accompanying symptoms like nausea or fever) to better narrow down what might be going on.
4. INTELLIGENT OTC GUIDANCE: Based on your dynamic analysis of their situation, naturally suggest common, safe Indian OTC remedies if appropriate (e.g., Saridon, Dolo 650, Calpol, Digene, Pudin Hara, Eno, Sinarest, Wikoryl). Explain *why* a specific option fits their context, along with standard adult precautions and typical usage.
5. PRESENTATION: Keep your tone balanced—professional, reassuring, and practical. Use clean markdown formatting (bolding, lists) to ensure key points are easily scannable.

At the absolute end of your response, add this single-line disclaimer:
"*Educational reference guide. Please verify with a pharmacist or healthcare professional.*"
"""

@app.post("/api/analyze")
async def analyze_report(data: AnalyzeRequest):
    try:
        safety_config = [
            types.SafetySetting(
                category=types.HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT,
                threshold=types.HarmBlockThreshold.BLOCK_NONE,
            )
        ]
        
        config = types.GenerateContentConfig(
            safety_settings=safety_config,
            response_mime_type="application/json"
        )

        if data.type == 'text':
            response = client.models.generate_content(
                model='gemini-2.5-flash',
                contents=[ANALYSIS_PROMPT, data.content],
                config=config
            )
        elif data.type == 'image':
            b64_str = data.content
            if "," in b64_str:
                b64_str = b64_str.split(",")[1]
            image_bytes = base64.b64decode(b64_str)
            
            image_part = types.Part.from_bytes(
                data=image_bytes,
                mime_type=data.mimeType or "image/jpeg"
            )
            
            response = client.models.generate_content(
                model='gemini-2.5-flash',
                contents=[ANALYSIS_PROMPT, image_part],
                config=config
            )
        else:
            raise HTTPException(status_code=400, detail="Invalid payload structure type")

        clean_text = response.text.replace("```json", "").replace("```", "").strip()
        return json.loads(clean_text)

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/chat")
async def chat_followup(data: ChatRequest):
    try:
        safety_config = [
            types.SafetySetting(
                category=types.HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT,
                threshold=types.HarmBlockThreshold.BLOCK_NONE,
            )
        ]
        
        config = types.GenerateContentConfig(safety_settings=safety_config)
        formatted_prompt = CHAT_PROMPT_TEMPLATE.format(question=data.userQuestion)
        
        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=formatted_prompt,
            config=config
        )

        return {"answer": response.text}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)