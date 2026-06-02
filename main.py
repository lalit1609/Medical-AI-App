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

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/api/health")
async def health_check():
    return {"status": "active", "message": "Server is awake"}

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

# FIXED PROMPT: Switches completely to standard HTML tags for layout structure
CHAT_PROMPT_TEMPLATE = """
You are MedAI, an intelligent, empathetic Indian First-Aid & OTC Medication Assistant. Your goal is to guide users through minor ailments using a comfortable, step-by-step triage conversation so you do not overwhelm them with too many questions at once.

User's Input: {question}

You must analyze the user's input and strictly follow this phased protocol:

PHASE 1: GATHER CORE PARAMETERS (If Location or Intensity is missing)
- If the user mentions a symptom (like a headache, stomach ache, body pain) but has NOT yet clearly specified BOTH the exact location and the intensity, you must ask ONLY for those two details.
- Provide a brief, comforting acknowledgment, and then ask for the intensity and location clearly. Do not suggest specific medications, dosages, or ask about secondary symptoms in this phase.

PHASE 2: TAILORED MEDICATION & SECONDARY TRIAGE (If Location and Intensity are known)
- If the user's input contains or answers both the location and intensity of the pain, proceed to give tailored relief options.
- Recommend standard, safe Indian OTC options matching their intensity description (e.g., Saridon for mild/moderate localized tension headaches; Crocin Pain Relief or Dolo 650 for generalized body aches/fevers; Digene/Pudin Hara for acidity) with precise adult guidelines.
- AFTER listing the medication and dosage, ask your secondary triage questions to check for underlying complications (e.g., "To ensure it's nothing serious, are you also running a fever, feeling nauseous, or experiencing any dizziness?").

Core Operational Guardrails:
1. NO AUTOMATIC REFUSALS: Do not hide behind corporate AI text. Speak naturally as a helpful first-aid advisor.
2. STRICT HTML FORMATTING ONLY: Never use markdown asterisks (* or **) anywhere. Instead, use standard HTML <b>tags for bold text</b>, <br> for line breaks, and standard bullet points like • for lists. Ensure the response flows elegantly.

At the absolute end of your response, add this single-line disclaimer wrapped in italic tags:
"<i>Educational reference guide. Please verify with a pharmacist or healthcare professional.</i>"
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
            return {"error": "Invalid payload structure type"}

        clean_text = response.text.strip()
        return json.loads(clean_text)

    except Exception as e:
        return {"rawReportSummary": f"Analysis Diagnostics Error: {str(e)}", "terms": [], "flaggedValues": [], "questions": []}

@app.post("/api/chat")
async def chat_followup(data: ChatRequest):
    try:
        safety_config = [
            types.SafetySetting(category=types.HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT, threshold=types.HarmBlockThreshold.BLOCK_NONE),
            types.SafetySetting(category=types.HarmCategory.HARM_CATEGORY_HATE_SPEECH, threshold=types.HarmBlockThreshold.BLOCK_NONE),
            types.SafetySetting(category=types.HarmCategory.HARM_CATEGORY_HARASSMENT, threshold=types.HarmBlockThreshold.BLOCK_NONE),
            types.SafetySetting(category=types.HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT, threshold=types.HarmBlockThreshold.BLOCK_NONE),
        ]
        
        config = types.GenerateContentConfig(safety_settings=safety_config)
        formatted_prompt = CHAT_PROMPT_TEMPLATE.format(question=data.userQuestion)
        
        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=formatted_prompt,
            config=config
        )

        if response.text:
            return {"answer": response.text}
        else:
            return {"answer": "I understand you're feeling unwell. To help you better with first-aid information, could you tell me exactly where the pain is located and how intense it feels?"}

    except Exception as e:
        return {"answer": f"Backend Diagnostics Error: {str(e)}"}

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)