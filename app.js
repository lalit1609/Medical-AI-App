const pdfjsLib = window['pdfjs-dist/build/pdf'];
pdfjsLib.GlobalWorkerOptions.workerSrc = 'https://cdnjs.cloudflare.com/ajax/libs/pdf.js/2.16.105/pdf.worker.min.js';

const fileInput = document.getElementById('report-upload');
const fileNameDisplay = document.getElementById('file-name');
const loadingDiv = document.getElementById('loading');
const loadingText = document.getElementById('loading-text');
const resultsDiv = document.getElementById('results');

// Chat DOM Elements
const chatHistory = document.getElementById('chat-history');
const chatInput = document.getElementById('chat-input');
const sendChatBtn = document.getElementById('send-chat-btn');

let currentReportText = ""; 

// Your exact Render web service address integrated perfectly:
const CLOUD_BACKEND_URL = "https://medai-backend-11h5.onrender.com";

fileInput.addEventListener('change', async (event) => {
    const file = event.target.files[0];
    if (!file) return;

    fileNameDisplay.textContent = file.name;
    loadingDiv.classList.remove('hidden');
    resultsDiv.classList.add('hidden');
    
    chatHistory.innerHTML = '<div class="chat-message ai-message">System synced. I have processed the clinical parameters. Ask me any direct or overarching health questions below.</div>';

    try {
        if (file.type === "application/pdf") {
            loadingText.textContent = "Extracting text matrices...";
            const extractedText = await extractTextFromPDF(file);
            loadingText.textContent = "Connecting to MedAI Cloud Base...";
            const aiResponse = await analyzeReportWithAI({ type: 'text', content: extractedText });
            renderResults(aiResponse);
        } else if (file.type.startsWith("image/")) {
            loadingText.textContent = "Scanning visual markers...";
            const base64Data = await convertFileToBase64(file);
            loadingText.textContent = "Connecting to MedAI Cloud Base...";
            const aiResponse = await analyzeReportWithAI({ type: 'image', content: base64Data, mimeType: file.type });
            renderResults(aiResponse);
        } else {
            alert("Unsupported format.");
            loadingDiv.classList.add('hidden');
        }
    } catch (error) {
        console.error(error);
        alert("Execution sync failed.");
        loadingDiv.classList.add('hidden');
    }
});

async function extractTextFromPDF(file) {
    const arrayBuffer = await file.arrayBuffer();
    const pdf = await pdfjsLib.getDocument({ data: arrayBuffer }).promise;
    let fullText = '';
    for (let i = 1; i <= pdf.numPages; i++) {
        const page = await pdf.getPage(i);
        const textContent = await page.getTextContent();
        fullText += textContent.items.map(item => item.str).join(' ') + '\n';
    }
    return fullText;
}

function convertFileToBase64(file) {
    return new Promise((resolve, reject) => {
        const reader = new FileReader();
        reader.readAsDataURL(file);
        reader.onload = () => { resolve(reader.result.split(',')[1]); };
        reader.onerror = error => reject(error);
    });
}

async function analyzeReportWithAI(payload) {
    const response = await fetch(`${CLOUD_BACKEND_URL}/api/analyze`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
    });
    if (!response.ok) throw new Error("Sync failure.");
    return await response.json();
}

function renderResults(data) {
    currentReportText = data.rawReportSummary; 

    document.getElementById('summary-text').textContent = data.rawReportSummary;
    document.getElementById('terms-list').innerHTML = data.terms.map(i => `<li><strong>${i.term}:</strong> ${i.simpleDefinition}</li>`).join('');
    document.getElementById('values-list').innerHTML = data.flaggedValues.map(i => `<li><strong>${i.testName}:</strong> ${i.value} — <em>${i.meaning}</em></li>`).join('');
    document.getElementById('questions-list').innerHTML = data.questions.map(q => `<li>• ${q}</li>`).join('');

    loadingDiv.classList.add('hidden');
    resultsDiv.classList.remove('hidden');
}

async function handleChatSubmission() {
    const question = chatInput.value.trim();
    if (!question) return;

    appendChatMessage(question, 'user-message');
    chatInput.value = "";

    const loadingBubble = appendChatMessage("Analyzing medical dataset and cross-referencing...", 'ai-message');

    try {
        const response = await fetch(`${CLOUD_BACKEND_URL}/api/chat`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                reportContext: currentReportText,
                userQuestion: question
            })
        });
        const result = await response.json();
        
        // FIXED: Changed from .textContent to .innerHTML to render bold tags and line breaks correctly
        loadingBubble.innerHTML = result.answer;
        
    } catch (err) {
        loadingBubble.textContent = "Unable to route message to core model.";
    }
}

function appendChatMessage(text, className) {
    const bubble = document.createElement('div');
    bubble.className = `chat-message ${className}`;
    bubble.textContent = text;
    chatHistory.appendChild(bubble);
    chatHistory.scrollTop = chatHistory.scrollHeight;
    return bubble;
}

sendChatBtn.addEventListener('click', handleChatSubmission);
chatInput.addEventListener('keypress', (e) => { if (e.key === 'Enter') handleChatSubmission(); });