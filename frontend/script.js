// ✅ FIXED: Connected to your Live Render Backend
const API_URL = "https://dynamo-ai.onrender.com"; 

// DOM Elements
const chatContainer = document.getElementById('chat-container');
const inputField = document.getElementById('chat-input');
// Select the send button based on the arrow icon we used in index.html
const sendBtn = document.querySelector('button i[data-lucide="arrow-up"]')?.parentElement;

// State
let chatHistory = [];
let sessionId = crypto.randomUUID();

// --- CORE FUNCTION: Send Message ---
async function sendMessage(text) {
    if (!text) return;
    
    // Clear Input immediately
    if (inputField) inputField.value = "";

    // 1. Add User Bubble to UI
    addMessageToUI("user", text);
    
    // 2. Add Loading Indicator
    const loadingId = addMessageToUI("assistant", "Thinking... ⚡");

    // 3. Prepare Payload
    const payload = {
        session_id: sessionId,
        message: text,
        history: chatHistory,
        use_search: true, 
        deep_dive: false,
        analyst_mode: false
    };

    try {
        // 4. Send to Python Backend (Render)
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
            addMessageToUI("assistant", "📊 Chart Data Received: " + JSON.stringify(data.content));
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
        if (loader) loader.innerHTML = `⚠️ <span style="color:red">Error: Backend is sleeping.</span><br><br>Since you are on the Free Tier, Render pauses the server when not used. Please wait 60 seconds and try again.`;
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
    const mainArea = document.getElementById('chat-container'); 
    
    // Hide Greeting if it exists
    const greeting = document.getElementById('greeting');
    if(greeting) greeting.style.display = 'none';

    if (mainArea) {
        mainArea.appendChild(div);
        // Auto scroll to bottom
        mainArea.scrollTop = mainArea.scrollHeight;
    }
    
    return id;
}

function addImageToUI(url) {
    const img = document.createElement('img');
    img.src = url;
    img.className = "rounded-xl shadow-md max-w-md mb-4 border border-gray-200";
    
    const mainArea = document.getElementById('chat-container');
    if (mainArea) {
        mainArea.appendChild(img);
        mainArea.scrollTop = mainArea.scrollHeight;
    }
}

// --- CONNECT HTML BUTTONS TO JS ---

// 1. Enter Key Listener
if (inputField) {
    inputField.addEventListener('keypress', (e) => {
        if (e.key === 'Enter') sendMessage(inputField.value);
    });
}

// 2. Window Functions (For HTML onclick="")
window.sendFromInput = function() {
    if (inputField) sendMessage(inputField.value);
}

window.sendQuickPrompt = function(text) {
    sendMessage(text);
}
