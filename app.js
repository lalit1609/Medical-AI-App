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

// Global state tracking to remember context for the follow-up prompt bar
let currentReportText = ""; 

fileInput.addEventListener('change', async (event) => {
    const file = event.target.files[0];
    if (!file) return;

    fileNameDisplay.textContent = file.name;
    loadingDiv.classList.remove('hidden');
    resultsDiv.classList.add('hidden');
    
    // Clear old chat logs
    chatHistory.innerHTML = '<div class="chat-message ai-message">I\'ve parsed your report. Ask me anything about these results!</div>';

    try {
        if (file.type === "application/pdf") {
            loadingText.textContent = "Extracting text from PDF report...";
            const extractedText = await extractTextFromPDF(file);
            loadingText.textContent = "Consulting MedAI Medical Engine...";
            const aiResponse = await analyzeReportWithAI({ type: 'text', content: extractedText });
            renderResults(aiResponse);
        } else if (file.type.startsWith("image/")) {
            loadingText.textContent = "Reading image data via computer vision...";
            const base64Data = await convertFileToBase64(file);
            loadingText.textContent = "Consulting MedAI Visual Medical Engine...";
            const aiResponse = await analyzeReportWithAI({ type: 'image', content: base64Data, mimeType: file.type });
            renderResults(aiResponse);
        } else {
            alert("Unsupported format. Please select an image file or a PDF.");
            loadingDiv.classList.add('hidden');
        }
    } catch (error) {
        console.error(error);
        alert("Processing failed. Make sure your Python server is running!");
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
        reader.onload = () => {
            // Trim off the 'data:image/png;base64,' meta indicator prefix string
            const base64String = reader.result.split(',')[1];
            resolve(base64String);
        };
        reader.onerror = error => reject(error);
    });
}

async function analyzeReportWithAI(payload) {
    const response = await fetch('http://127.0.0.1:8000/api/analyze', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload)
    });
    if (!response.ok) throw new Error("Backend connection issue.");
    return await response.json();
}

function renderResults(data) {
    currentReportText = data.rawReportSummary; // Save context for chat

    document.getElementById('terms-list').innerHTML = data.terms.map(i => `<li><strong>${i.term}:</strong> ${i.simpleDefinition}</li>`).join('');
    document.getElementById('values-list').innerHTML = data.flaggedValues.map(i => `<li><strong>${i.testName}:</strong> ${i.value} <em>(${i.meaning})</em></li>`).join('');
    document.getElementById('questions-list').innerHTML = data.questions.map(q => `<li>${q}</li>`).join('');

    loadingDiv.classList.add('hidden');
    resultsDiv.classList.remove('hidden');
}

// Interactive Follow-up Chat System Execution
async function handleChatSubmission() {
    const question = chatInput.value.trim();
    if (!question) return;

    // Append user message immediately to the UI bubble track
    appendChatMessage(question, 'user-message');
    chatInput.value = "";

    // Append a temporary loading bubble placeholder
    const loadingBubble = appendChatMessage("Thinking...", 'ai-message');

    try {
        const response = await fetch('http://127.0.0.1:8000/api/chat', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                reportContext: currentReportText,
                userQuestion: question
            })
        });
        const result = await response.json();
        loadingBubble.textContent = result.answer;
    } catch (err) {
        loadingBubble.textContent = "Error: Couldn't connect to MedAI to process the message.";
    }
    chatHistory.scrollTop = chatHistory.scrollHeight;
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