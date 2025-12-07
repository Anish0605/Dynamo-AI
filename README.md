⚡ Dynamo AI Platform"Power Your Curiosity."Dynamo AI is a professional-grade Research Operating System. It combines a high-performance FastAPI backend (The Brain) with a sleek, responsive HTML/JS frontend (The Face).Unlike simple scripts, this platform is architected for scale, separating the user interface from the logic engine to allow for independent deployment and maximum speed.🏗️ ArchitectureThe system is built on a Headless Architecture:graph TD
    User((User)) -->|Visits| Frontend[🖥️ Frontend (HTML/JS)]
    Frontend -->|Sends Request| Backend[🧠 Backend API (FastAPI)]
    
    subgraph Cloud Brain
    Backend -->|Inference| Groq[⚡ Groq LPU (Llama 3)]
    Backend -->|Search| Tavily[🌐 Tavily Search]
    Backend -->|Image Gen| Pollinations[🎨 Pollinations AI]
    end
    
    Groq -->|JSON Response| Backend
    Backend -->|JSON Data| Frontend
    Frontend -->|Renders UI| User
🚀 Features⚡ Hyper-Fast Inference: Powered by Groq's LPU for near-instant AI responses.🌐 Live Web Search: Autonomous agentic search via Tavily API.🎙️ Voice Mode: Real-time speech-to-text using Whisper v3.👁️ Dynamo Vision: Multimodal image analysis using Llama 3.2 Vision.🎨 Image Generation: Integrated AI art generation.📊 Analyst Mode: Structured JSON output for generating data visualizations.🛠️ Tech StackBackend (The Brain)Framework: FastAPI (Python)Server: UvicornAI Models: Llama-3.3-70b-versatile, Llama-3.2-11b-visionSearch: Tavily APIFrontend (The Face)Core: HTML5, Vanilla JavaScriptStyling: Tailwind CSS (via CDN)Icons: Lucide Icons⚡ Quick Start Guide1. Backend Setup (Python)Navigate to the backend folder and install dependencies:cd backend
pip install -r requirements.txt
Set your API keys (Mac/Linux):export GROQ_API_KEY="your_key_here"
export TAVILY_API_KEY="your_key_here"
Run the server locally:uvicorn main:app --reload
Your API is now running at http://localhost:80002. Frontend Setup (Web)Open frontend/script.js.Ensure API_URL is set to your local server:const API_URL = "http://localhost:8000";
Open frontend/index.html in your browser.Start chatting!🌍 Deployment GuideBackend (Render)Push this repo to GitHub.Create a new Web Service on Render.Connect your repo.Root Directory: backendBuild Command: pip install -r requirements.txtStart Command: `uvicorn main:app --host
