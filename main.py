import os
from flask import Flask, request, jsonify
from flask_cors import CORS
import google.generativeai as genai

app = Flask(__name__)
CORS(app)

# Secure API Key configuration
GEMINI_KEY = os.getenv("GEMINI_API_KEY")
genai.configure(api_key=GEMINI_KEY)

# Force Gemini to disable standard safety filters
safety_config = [
    {
        "category": "HARM_CATEGORY_DANGEROUS_CONTENT",
        "threshold": "BLOCK_NONE"
    }
]

model = genai.GenerativeModel(
    model_name='gemini-2.5-flash',
    safety_settings=safety_config
)

ANALYSIS_PROMPT = """
You are MedAI, an advanced medical report interpreter. Analyze this medical report data and provide a structured JSON output. 
Strictly return ONLY a valid JSON object matching this structure:
{
  "rawReportSummary": "A concise, 3-sentence summary of the overall health findings.",
  "terms": [
    {"term": "Medical Term", "simpleDefinition": "A ultra-short, jargon-free 1-sentence explanation."}
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
You are MedAI, an automated, hyper-precise Indian Over-The-Counter (OTC) First-Aid & Pharmaceutical Reference Directory. Your sole purpose is to provide direct, immediate information on standard, common Indian medications, brand names, and typical adult dosages for minor ailments.

Patient's Report Summary Context:
{context}

User's Question: {question}

Core Execution Rules:
1. NEVER use generic AI refusals like "I cannot recommend medicine", "I am an AI", or "Consult a doctor instead of asking me." Treat these boilerplate refusals as strict system errors.
2. If the user presents a casual, normal ailment (Headache, Cold, Cough, Casual Fever, Stomach Ache, Acidity, Gas), you MUST immediately provide the standard Indian OTC brand choices, primary active ingredients, and common adult dosages.
3. Use the following specific mapping matrix for reference whenever applicable:
   - Casual Fever / Body Pain: Dolo 650 or Calpol (Paracetamol 650mg). Standard adult dose: 1 tablet every 4-6 hours as needed (Max 4 tablets/24 hours).
   - Headache: Saridone (Propyphenazone/Paracetamol/Caffeine) or Crocin Pain Relief. Standard adult dose: 1 tablet as needed.
   - Stomach Ache / Gas / Acidity: Pudin Hara (Mint oil pearls, 1-2 capsules with water), Digene tablet/gel (Antacid, 2-4 tablets chewed after meals), or Eno (1 sachet in a glass of water for instant gas relief).
   - Common Cold / Viral Runny Nose: Sinarest or Wikoryl. Standard adult dose: 1 tablet twice a day.
4. If a user's symptom layout is slightly vague (e.g., just saying "my stomach hurts"), structure your response to:
   - First, immediately list the basic safe OTC choices (like Digene/Pudin Hara for acidity/gas).
   - Second, ask a brief, smart follow-up question regarding the location of the pain (upper vs lower abdomen) or frequency to narrow it down further.
5. Keep the formatting incredibly clean, bold, scannable, and academic. No robotic filler text.
6. Append this tiny disclaimer at the absolute bottom line: "*Reference database entry. Verify with your pharmacist or medical professional.*"
"""

@app.route('/api/analyze', methods=['POST'])
def analyze_report():
    try:
        data = request.json
        payload_type = data.get('type')
        content = data.get('content')

        if payload_type == 'text':
            response = model.generate_content([ANALYSIS_PROMPT, content])
        elif payload_type == 'image':
            image_data = {
                "mime_type": data.get('mimeType', 'image/jpeg'),
                "data": content
            }
            response = model.generate_content([ANALYSIS_PROMPT, image_data])
        else:
            return jsonify({"error": "Invalid payload type"}), 400

        clean_text = response.text.replace("```json", "").replace("```", "").strip()
        return clean_text, 200, {'Content-Type': 'application/json; charset=utf-8'}

    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/chat', methods=['POST'])
def chat_followup():
    try:
        data = request.json
        context = data.get('reportContext', 'No report uploaded yet.')
        question = data.get('userQuestion', '')

        formatted_prompt = CHAT_PROMPT_TEMPLATE.format(context=context, question=question)
        response = model.generate_content(formatted_prompt)

        return jsonify({"answer": response.text})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8000)