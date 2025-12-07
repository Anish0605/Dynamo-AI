// ⚠️ IMPORTANT: After deploying the backend to Render, replace this URL!
// Example: const API_URL = "https://dynamo-brain.onrender.com";
const API_URL = "http://localhost:8000"; 

// DOM Elements
const chatContainer = document.getElementById('chat-container');
const inputField = document.getElementById('chat-input');
const sendBtn = document.querySelector('button i[data-lucide="arrow-up"]').parentElement;

// State
let chatHistory = [];
let sessionId = crypto.randomUUID();

// --- CORE FUNCTION: Send Message ---
async function sendMessage(text) {
    if (!text) return;
    
    // Clear Input
    if (inputField) inputField.value = "";

    // 1. Add User Bubble
    addMessageToUI("user", text);
    
    // 2. Add Loading Indicator
    const loadingId = addMessageToUI("assistant", "Thinking... ⚡");

    // 3. Prepare Payload
    const payload = {
        session_id: sessionId,
        message: text,
        history: chatHistory,
        use_search: true, // Default to true, or connect to a toggle
        deep_dive: false,
        analyst_mode: false
    };

    try {
        // 4. Send to Python Backend
        const response = await fetch(`${API_URL}/chat`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(payload)
        });

        if (!response.ok) throw new Error("API Error");

        const data = await response.json();
        
        // Remove Loading
        const loader = document.getElementById(loadingId);
        if (loader) loader.remove();

        // 5. Render Response
        if (data.type === "image") {
            addImageToUI(data.content);
            chatHistory.push({role: "assistant", content: "Generated image: " + data.content});
        } else if (data.type === "chart") {
            addMessageToUI("assistant", "📊 Chart Data Received (Visualization pending implementation)");
            // In a real app, you'd pass data.content to Chart.js here
            chatHistory.push({role: "assistant", content: "Chart generated"});
        } else {
            addMessageToUI("assistant", data.content);
            chatHistory.push({role: "assistant", content: data.content});
        }

        // Add to History
        chatHistory.push({role: "user", content: text});

    } catch (error) {
        console.error(error);
        const loader = document.getElementById(loadingId);
        if (loader) loader.innerText = "⚠️ Error: Could not connect to Dynamo Brain. Is the backend running?";
    }
}

// --- UI HELPERS ---

function addMessageToUI(role, text) {
    const id = "msg-" + Date.now();
    const div = document.createElement('div');
    div.id = id;
    
    // Styling matches index.html (DeepSeek/Grok look)
    if (role === 'user') {
        div.className = "bg-gray-100 text-gray-900 p-4 rounded-2xl mb-4 ml-auto max-w-2xl self-end text-right";
    } else {
        div.className = "bg-white text-gray-900 p-4 rounded-2xl mb-4 mr-auto max-w-3xl self-start border border-gray-100 shadow-sm";
    }
    
    div.innerText = text;
    
    // Append to container
    // We create a wrapper if it doesn't exist to separate the "Greeting" from "Chat"
    let wrapper = document.getElementById('messages-wrapper');
    if (!wrapper) {
        wrapper = document.createElement('div');
        wrapper.id = 'messages-wrapper';
        wrapper.className = "flex flex-col w-full max-w-4xl mx-auto";
        // Hide the greeting logo if chat starts
        const greeting = document.querySelector('.animate-fade-in-up');
        if(greeting) greeting.style.display = 'none';
        
        // Insert wrapper before the input box container
        chatContainer.insertBefore(wrapper, chatContainer.firstChild); 
        // Actually, simpler to just append to main container and ensure flex-col is set
    }
    
    // Simple Append Strategy for now
    // Find the container where messages should go. In index.html, the main area is flex-col.
    // We might need to hide the initial "How can I help you" content.
    const mainArea = document.querySelector('main > div.flex-grow'); 
    if (mainArea) {
        // Clear initial greeting on first message
        if (chatHistory.length === 0) {
            mainArea.innerHTML = ''; 
            mainArea.className = "flex-grow flex flex-col p-4 w-full max-w-4xl mx-auto overflow-y-auto pb-40"; 
        }
        mainArea.appendChild(div);
        mainArea.scrollTop = mainArea.scrollHeight; // Auto scroll
    }
    
    return id;
}

function addImageToUI(url) {
    const img = document.createElement('img');
    img.src = url;
    img.className = "rounded-xl shadow-md max-w-md mb-4 border border-gray-200";
    
    const mainArea = document.querySelector('main > div.flex-grow');
    if (mainArea) {
        mainArea.appendChild(img);
        mainArea.scrollTop = mainArea.scrollHeight;
    }
}

// --- EVENT LISTENERS ---

// 1. Send Button
if (sendBtn) {
    sendBtn.addEventListener('click', () => sendMessage(inputField.value));
}

// 2. Enter Key
if (inputField) {
    inputField.addEventListener('keypress', (e) => {
        if (e.key === 'Enter') sendMessage(inputField.value);
    });
}

// 3. Quick Suggestion Pills (Wait for DOM load)
document.addEventListener('DOMContentLoaded', () => {
    const suggestions = document.querySelectorAll('button span'); // Rough selector for suggestion text
    // Better way: Add onclick="sendQuickPrompt('...')" to HTML buttons in index.html
});

// Helper for HTML onClick events
window.sendQuickPrompt = function(text) {
    sendMessage(text);
}
