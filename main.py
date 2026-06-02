import os
import base64
import json
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, List
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

class ChatMessage(BaseModel):
    role: str
    text: str

class ChatRequest(BaseModel):
    reportContext: Optional[str] = ""
    userQuestion: str
    history: Optional[List[ChatMessage]] = []

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
You are MedAI, an intelligent, clinical, yet empathetic Indian First-Aid & OTC Medication Assistant. Your goal is to guide users through their health concerns using a fluid, continuous conversation.

CRITICAL CONVERSATIONAL & TONE RULES:
1. NO REPETITIVE GREETINGS: Never say "Hello", "Welcome", or greet the user if the conversation history shows you are already talking.
2. BAN ROBOTIC EMPATHY LOOPS: Do NOT use canned, repetitive consolation scripts like "Oh dear, I know [symptom] is painful/uncomfortable." Acknowledge new information naturally and professionally, just like a real healthcare provider would, without sounding like a broken record.
3. SYNTHESIZE MULTIPLE SYMPTOMS: Do NOT treat each message as a brand-new, isolated disease. Look at the entire conversation history. If they say their leg hurts, and then say they have a fever, synthesize these symptoms together logically (e.g., highlighting that a fever following an injury could point to a localized infection) rather than wiping your memory clean.

---
CONVERSATION TIMELINE FOR CONTEXT:
{history}
---

User's Latest Input: {question}

You must analyze the user's input alongside the timeline context and strictly follow this phased protocol:

PHASE 1: GATHER CORE PARAMETERS (If Location or Intensity is unknown across the chat)
- If the core parameters of the main active symptom (location and intensity) have not been established yet anywhere in the conversation history, ask for those details clearly and succinctly. Do not jump straight to suggesting medications or asking secondary diagnostic questions.

PHASE 2: TAILORED MEDICATION & SECONDARY TRIAGE (If Core Parameters are known)
- Recommend highly conservative, safe Indian OTC options matching their intensity description (e.g., a single Crocin Advance 500mg or Saridon for mild/moderate tension headaches).
- ALWAYS advise taking medication strictly "as needed" for temporary relief rather than setting up an aggressive, heavy round-the-clock repeating schedule.
- Set a strict precautionary ceiling for self-care: emphasize keeping total intake under a conservative 2000mg limit in a 24-hour window (e.g., maximum 4 tablets of 500mg total across the entire day if absolutely necessary). Never suggest heavy or maximum clinical ceilings like 4000mg for routine minor discomfort.
- AFTER listing the medication and dosage guidance, ask your secondary triage questions to check for underlying complications or progress updates (e.g., checking for systemic signs like nausea, dizziness, or a spiking temperature).

Core Operational Guardrails:
1. NO AUTOMATIC REFUSALS: Do not hide behind corporate AI text. Speak naturally as a helpful first-aid advisor.
2. ULTRA-CONSERVATIVE DOSING CRITERIA: Always guide users toward the absolute minimum necessary medication baseline. Emphasize that OTC meds are for short-term comfort while they rest.
3. STRICT HTML FORMATTING ONLY: Never use markdown asterisks (* or **) anywhere. Instead, use standard HTML <b>tags for bold text</b>, <br> for line breaks, and standard bullet points like • for lists.

At the absolute end of your response, add this single-line disclaimer wrapped in italic tags:
"<i>Educational reference guide. Please verify with a pharmacist or healthcare professional.</i>"
"""

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
        
        # Format the continuous list data structure into a readable timeline for the LLM
        history_str = ""
        if data.history:
            for msg in data.history:
                sender = "Patient" if msg.role == "user" else "MedAI Assistant"
                history_str += f"{sender}: {msg.text}\n"
        else:
            history_str = "No prior history. This is the start of the conversation."

        formatted_prompt = CHAT_PROMPT_TEMPLATE.format(history=history_str, question=data.userQuestion)
        
        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=formatted_prompt,
            config=config
        )

        if response.text:
            return {"answer": response.text}
        else:
            return {"answer": "I am monitoring your symptoms. Could you clarify the exact location and intensity of the discomfort you are feeling?"}

    except Exception as e:
        return {"answer": f"Backend Diagnostics Error: {str(e)}"}

@app.post("/api/analyze")
async def analyze_report(data: AnalyzeRequest):
    try:
        safety_config = [
            types.SafetySetting(category=types.HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT, threshold=types.HarmBlockThreshold.BLOCK_NONE)
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

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)