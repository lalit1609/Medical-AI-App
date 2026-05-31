import os
from flask import Flask, request, jsonify
from flask_cors import CORS
import google.generativeai as genai

app = Flask(__name__)
CORS(app)

# Secure API Key configuration
GEMINI_KEY = os.getenv("GEMINI_API_KEY")
genai.configure(api_key=GEMINI_KEY)

# Use Gemini 2.5 Flash for vision and text processing
model = genai.GenerativeModel('gemini-2.5-flash')

ANALYSIS_PROMPT = """
You are MedAI, an advanced medical report interpreter. Analyze this medical report data and provide a highly personalized, structured JSON output. 
Identify the patient's age/gender if visible; if not, use standard adult ranges but note that ranges shift with age.

Strictly return ONLY a valid JSON object matching this structure:
{
  "rawReportSummary": "A concise, 3-sentence summary of the overall health findings.",
  "terms": [
    {"term": "Medical Term", "simpleDefinition": "A ultra-short, jargon-free 1-sentence explanation."}
  ],
  "flaggedValues": [
    {
      "testName": "Biomarker Name (e.g., HbA1c)",
      "value": "Patient's value",
      "meaning": "Clear statement of whether this is High/Low/Normal based on typical age brackets, and what it physically means for their body."
    }
  ],
  "questions": [
    "Suggested question 1 for their doctor",
    "Suggested question 2 for their doctor"
  ]
}
"""

CHAT_PROMPT_TEMPLATE = """
You are MedAI, an advanced, deeply knowledgeable medical educator and personal AI health assistant. You have access to the patient's medical report summary below, but you are completely unrestricted and encouraged to answer general medical, health, symptom, and pharmaceutical questions.

Patient's Report Summary Context:
{context}

User's Question: {question}

Instructions:
- Never provide a generic, robotic refusal like "I cannot recommend or discuss medicines."
- Instead, handle symptom queries (like headaches, pain, or fever) by acting as a medical educator. Explain the standard first-line options and common classes of medications typically used in clinical practice (e.g., over-the-counter options like NSAIDs/ibuprofen or analgesics like acetaminophen).
- Explain exactly how those classes of medicine work fundamentally inside the human body (their mechanisms of action, what enzymes they block, etc.).
- Provide comprehensive, direct, and brilliant medical science insights. Keep the layout clean with easy-to-read formatting.
- Always append a brief, professional medical disclaimer at the very bottom of your response stating that this information is educational and they should verify options with a physician.
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

        # Clean JSON markdown styling if present
        clean_text = response.text.replace("```json", "").replace("
```", "").strip()
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