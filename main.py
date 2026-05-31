from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional
from google import genai
from google.genai import types
import json
import os # This lets Python read safe background variables from the cloud

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # Allows your mobile app to connect from anywhere in the world
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class DocumentPayload(BaseModel):
    type: str
    content: str
    mimeType: Optional[str] = None

class ChatPayload(BaseModel):
    reportContext: str
    userQuestion: str

# This grabs your key secretly from the cloud settings instead of hardcoding it
GEMINI_KEY = os.getenv("GEMINI_API_KEY")
client = genai.Client(api_key=GEMINI_KEY)

@app.get("/")
def home():
    return {"status": "MedAI Engine Online"}

@app.post("/api/analyze")
async def analyze_document(payload: DocumentPayload):
    try:
        if payload.type == 'image':
            doc_input = types.Part.from_bytes(
                data=payload.content.encode('utf-8'),
                mime_type=payload.mimeType or "image/jpeg"
            )
        else:
            doc_input = payload.content

        prompt = """
        You are an expert medical assistant named MedAI. Analyze the provided clinical documentation context.
        Return a strict, valid JSON object containing exactly the structural properties listed below.
        Do not prepend markdown formatting, do not wrap in code blocks (like ```json), just output the raw JSON string.

        {
          "terms": [
            {"term": "Example Jargon", "simpleDefinition": "Clear plain explanation"}
          ],
          "flaggedValues": [
            {"testName": "Example Biomarker", "value": "120 (High/Low)", "meaning": "Simplified summary implication"}
          ],
          "questions": [
             "Smart clarifying diagnostic conversation prompt 1"
          ],
          "rawReportSummary": "A concise comprehensive text summary explaining what this report is about overall."
        }
        """

        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=[doc_input, prompt]
        )

        clean_text = response.text.replace("```json", "").replace("```", "").strip()
        return json.loads(clean_text)

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/chat")
async def process_chat_followup(payload: ChatPayload):
    try:
        prompt = f"""
        You are MedAI, an empathetic and supportive medical assistant designed to clear up confusion about lab work.
        Keep answers highly understandable, warm, and avoid complex medical jargon.
        
        The baseline context of the user's report is: {payload.reportContext}
        
        The user is confused or has a follow-up question. Answer it directly and simply based on their report details:
        Question: {payload.userQuestion}
        """

        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=prompt
        )
        return {"answer": response.text.strip()}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# This automatically listens to the dynamic port the cloud server gives us
if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run("main:app", host="0.0.0.0", port=port)