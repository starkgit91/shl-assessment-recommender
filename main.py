import os
import json
import logging
from typing import Optional
from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field
from fastapi.middleware.cors import CORSMiddleware
import httpx

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load the SHL catalog
CATALOG_PATH = os.path.join(os.path.dirname(__file__), "shl_catalog.json")
with open(CATALOG_PATH, "r") as f:
    CATALOG = json.load(f)

# Groq API setup (free tier LLM provider)
GROQ_API_KEY = os.getenv("GROQ_API_KEY", "gsk_test_key")
GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions"

app = FastAPI(title="SHL Assessment Recommender", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class Message(BaseModel):
    role: str = Field(..., description="'user' or 'assistant'")
    content: str


class Recommendation(BaseModel):
    name: str
    url: str
    test_type: str


class ChatRequest(BaseModel):
    messages: list[Message]


class ChatResponse(BaseModel):
    reply: str
    recommendations: list[Recommendation] = []
    end_of_conversation: bool = False


def get_catalog_context() -> str:
    """Generate context from catalog for RAG."""
    assessments_text = []
    for assessment in CATALOG["assessments"]:
        text = f"""
Assessment: {assessment['name']}
Type: {assessment['type']}
Category: {assessment['category']}
Description: {assessment['description']}
Best for: {', '.join(assessment['best_for'])}
Duration: {assessment['test_time']}
URL: {assessment['url']}
"""
        assessments_text.append(text)
    return "\n---\n".join(assessments_text)


def get_llm_response(messages: list[Message], system_prompt: str) -> str:
    """Call Groq LLM API (or fallback to local logic)."""
    try:
        formatted_messages = [
            {"role": msg.role, "content": msg.content} for msg in messages
        ]

        response = httpx.post(
            GROQ_API_URL,
            headers={
                "Authorization": f"Bearer {GROQ_API_KEY}",
                "Content-Type": "application/json",
            },
            json={
                "model": "mixtral-8x7b-32768",
                "messages": [
                    {"role": "system", "content": system_prompt},
                    *formatted_messages,
                ],
                "temperature": 0.7,
                "max_tokens": 500,
            },
            timeout=25,
        )

        if response.status_code == 200:
            data = response.json()
            return data["choices"][0]["message"]["content"].strip()
    except Exception as e:
        logger.warning(f"LLM API call failed: {e}, using fallback logic")

    return fallback_response(messages)


def fallback_response(messages: list[Message]) -> str:
    """Fallback response generation without LLM."""
    user_content = messages[-1].content.lower() if messages else ""

    if len(messages) == 1:
        return "I'd be happy to help you find the right SHL assessment! Could you tell me more about the role you're hiring for? For example, what's the job title or key responsibilities?"

    if any(
        word in user_content
        for word in ["developer", "engineer", "programmer", "coding"]
    ):
        if "java" in user_content:
            return "Great! For a Java developer role, I'd recommend focusing on both technical and cognitive skills. What seniority level are we looking at? (e.g., junior, mid-level, senior)"
        return "I see you need a developer. What technology stack? (e.g., Java, Python, JavaScript, etc.)"

    if any(word in user_content for word in ["sales", "account", "business"]):
        return "Perfect! Sales roles benefit from personality and motivation assessments. What's the seniority level you're hiring for?"

    if any(
        word in user_content for word in ["customer", "support", "service", "help"]
    ):
        return "Customer service roles need strong interpersonal skills. Are you looking at entry-level or more experienced positions?"

    if any(word in user_content for word in ["manager", "leadership", "lead"]):
        return "Leadership assessment is crucial here. What's the team size or span of control for this role?"

    if any(word in user_content for word in ["compare", "difference", "vs"]):
        return "I can help you compare assessments. Based on our conversation, here are the key differences and which might be better suited."

    return "Can you provide more details about the role? What's the job title, primary responsibilities, and seniority level?"


def get_recommendations(
    messages: list[Message], conversation_turn: int
) -> tuple[list[Recommendation], bool]:
    """Extract recommendations from catalog based on conversation context."""
    user_content = " ".join(
        [msg.content.lower() for msg in messages if msg.role == "user"]
    ).lower()

    recommendations = []

    # Match assessments based on keywords and context
    if any(
        word in user_content
        for word in ["java", "python", "javascript", "sql", "programming", "developer"]
    ):
        # Technical roles
        for assessment in CATALOG["assessments"]:
            if any(
                skill in assessment["name"].lower()
                for skill in ["java", "python", "javascript", "sql"]
            ):
                if len(recommendations) < 3:
                    recommendations.append(
                        Recommendation(
                            name=assessment["name"],
                            url=assessment["url"],
                            test_type=assessment["type"],
                        )
                    )

        # Add cognitive ability tests
        for assessment in CATALOG["assessments"]:
            if assessment["type"] == "Ability" and len(recommendations) < 5:
                recommendations.append(
                    Recommendation(
                        name=assessment["name"],
                        url=assessment["url"],
                        test_type=assessment["type"],
                    )
                )

        # Add personality
        if "leadership" in user_content or "senior" in user_content:
            for assessment in CATALOG["assessments"]:
                if "Leadership" in assessment["category"] and len(recommendations) < 6:
                    recommendations.append(
                        Recommendation(
                            name=assessment["name"],
                            url=assessment["url"],
                            test_type=assessment["type"],
                        )
                    )

    elif any(word in user_content for word in ["sales", "account", "business"]):
        # Sales roles
        for assessment in CATALOG["assessments"]:
            if "Sales" in assessment["category"] or "sales" in assessment["name"].lower():
                if len(recommendations) < 2:
                    recommendations.append(
                        Recommendation(
                            name=assessment["name"],
                            url=assessment["url"],
                            test_type=assessment["type"],
                        )
                    )
        # Add personality assessment
        for assessment in CATALOG["assessments"]:
            if assessment["type"] == "Personality" and len(recommendations) < 5:
                recommendations.append(
                    Recommendation(
                        name=assessment["name"],
                        url=assessment["url"],
                        test_type=assessment["type"],
                    )
                )

    elif any(
        word in user_content
        for word in ["customer", "support", "service", "help", "retail"]
    ):
        # Customer service roles
        for assessment in CATALOG["assessments"]:
            if (
                "Customer" in assessment["category"]
                or "customer" in assessment["name"].lower()
            ):
                if len(recommendations) < 3:
                    recommendations.append(
                        Recommendation(
                            name=assessment["name"],
                            url=assessment["url"],
                            test_type=assessment["type"],
                        )
                    )
        for assessment in CATALOG["assessments"]:
            if assessment["type"] == "Personality" and len(recommendations) < 5:
                recommendations.append(
                    Recommendation(
                        name=assessment["name"],
                        url=assessment["url"],
                        test_type=assessment["type"],
                    )
                )

    elif any(word in user_content for word in ["manager", "leadership", "lead", "executive"]):
        # Leadership roles
        for assessment in CATALOG["assessments"]:
            if "Leadership" in assessment["category"]:
                if len(recommendations) < 3:
                    recommendations.append(
                        Recommendation(
                            name=assessment["name"],
                            url=assessment["url"],
                            test_type=assessment["type"],
                        )
                    )
        for assessment in CATALOG["assessments"]:
            if assessment["type"] == "Personality" and len(recommendations) < 6:
                recommendations.append(
                    Recommendation(
                        name=assessment["name"],
                        url=assessment["url"],
                        test_type=assessment["type"],
                    )
                )

    # Deduplicate
    seen = set()
    unique_recs = []
    for rec in recommendations:
        if rec.name not in seen:
            seen.add(rec.name)
            unique_recs.append(rec)

    return unique_recs[:10], len(unique_recs) > 0 and conversation_turn >= 4


@app.get("/", response_class=HTMLResponse)
async def root():
    """Serve the landing page and chat interface."""
    return """
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>SHL Assessment Recommender</title>
        <style>
            * {
                margin: 0;
                padding: 0;
                box-sizing: border-box;
            }
            
            body {
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, sans-serif;
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                min-height: 100vh;
                display: flex;
                flex-direction: column;
            }
            
            header {
                background: rgba(0, 0, 0, 0.1);
                padding: 20px;
                text-align: center;
                color: white;
                border-bottom: 1px solid rgba(255, 255, 255, 0.2);
            }
            
            header h1 {
                font-size: 2.5em;
                margin-bottom: 10px;
            }
            
            header p {
                font-size: 1.1em;
                opacity: 0.9;
            }
            
            .container {
                flex: 1;
                display: flex;
                max-width: 1200px;
                margin: 0 auto;
                width: 100%;
                gap: 20px;
                padding: 20px;
            }
            
            .landing {
                flex: 1;
                background: white;
                border-radius: 12px;
                padding: 40px;
                box-shadow: 0 10px 40px rgba(0, 0, 0, 0.2);
                overflow-y: auto;
            }
            
            .landing h2 {
                color: #667eea;
                margin-bottom: 20px;
                font-size: 1.8em;
            }
            
            .landing p {
                color: #555;
                line-height: 1.8;
                margin-bottom: 15px;
            }
            
            .features {
                display: grid;
                grid-template-columns: 1fr 1fr;
                gap: 20px;
                margin: 30px 0;
            }
            
            .feature {
                background: #f8f9fa;
                padding: 20px;
                border-radius: 8px;
                border-left: 4px solid #667eea;
            }
            
            .feature h3 {
                color: #667eea;
                margin-bottom: 10px;
            }
            
            .feature p {
                font-size: 0.95em;
                color: #666;
            }
            
            .chat-container {
                flex: 1;
                background: white;
                border-radius: 12px;
                display: flex;
                flex-direction: column;
                box-shadow: 0 10px 40px rgba(0, 0, 0, 0.2);
                overflow: hidden;
            }
            
            .chat-header {
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                color: white;
                padding: 20px;
                text-align: center;
            }
            
            .chat-header h3 {
                font-size: 1.3em;
            }
            
            .messages {
                flex: 1;
                overflow-y: auto;
                padding: 20px;
                background: #f8f9fa;
            }
            
            .message {
                margin-bottom: 15px;
                display: flex;
                animation: slideIn 0.3s ease-out;
            }
            
            @keyframes slideIn {
                from {
                    opacity: 0;
                    transform: translateY(10px);
                }
                to {
                    opacity: 1;
                    transform: translateY(0);
                }
            }
            
            .message.user {
                justify-content: flex-end;
            }
            
            .message.assistant {
                justify-content: flex-start;
            }
            
            .message-content {
                max-width: 70%;
                padding: 12px 16px;
                border-radius: 12px;
                word-wrap: break-word;
            }
            
            .message.user .message-content {
                background: #667eea;
                color: white;
                border-bottom-right-radius: 4px;
            }
            
            .message.assistant .message-content {
                background: white;
                color: #333;
                border: 1px solid #ddd;
                border-bottom-left-radius: 4px;
            }
            
            .recommendations {
                margin-top: 10px;
                padding: 10px;
                background: #f0f4ff;
                border-radius: 8px;
                font-size: 0.9em;
            }
            
            .recommendation-item {
                padding: 8px;
                margin: 5px 0;
                background: white;
                border-left: 3px solid #667eea;
                border-radius: 4px;
            }
            
            .recommendation-item strong {
                color: #667eea;
            }
            
            .input-area {
                padding: 20px;
                border-top: 1px solid #ddd;
                display: flex;
                gap: 10px;
            }
            
            .input-area input {
                flex: 1;
                padding: 12px;
                border: 1px solid #ddd;
                border-radius: 8px;
                font-size: 1em;
                font-family: inherit;
            }
            
            .input-area input:focus {
                outline: none;
                border-color: #667eea;
                box-shadow: 0 0 0 3px rgba(102, 126, 234, 0.1);
            }
            
            .input-area button {
                padding: 12px 24px;
                background: #667eea;
                color: white;
                border: none;
                border-radius: 8px;
                cursor: pointer;
                font-weight: 600;
                transition: background 0.3s;
            }
            
            .input-area button:hover {
                background: #764ba2;
            }
            
            .input-area button:disabled {
                background: #ccc;
                cursor: not-allowed;
            }
            
            .loading {
                display: inline-block;
                width: 8px;
                height: 8px;
                background: #667eea;
                border-radius: 50%;
                animation: pulse 1.5s infinite;
                margin-right: 5px;
            }
            
            @keyframes pulse {
                0%, 100% { opacity: 0.3; }
                50% { opacity: 1; }
            }
            
            @media (max-width: 768px) {
                .container {
                    flex-direction: column;
                }
                
                .features {
                    grid-template-columns: 1fr;
                }
                
                header h1 {
                    font-size: 1.8em;
                }
                
                .message-content {
                    max-width: 90%;
                }
            }
        </style>
    </head>
    <body>
        <header>
            <h1>🎯 SHL Assessment Recommender</h1>
            <p>Find the perfect assessment for your hiring needs</p>
        </header>
        
        <div class="container">
            <div class="landing">
                <h2>Welcome to SHL Assessment Recommender</h2>
                <p>
                    Our AI-powered assistant helps you discover the right SHL assessments for your hiring process. 
                    Whether you're looking to evaluate technical skills, leadership potential, or personality traits, 
                    we've got you covered.
                </p>
                
                <h3 style="color: #667eea; margin-top: 30px; margin-bottom: 15px;">How It Works</h3>
                <p>
                    Simply describe the role you're hiring for in the chat on the right. Our AI will ask clarifying 
                    questions to understand your needs and recommend the most suitable SHL assessments from our 
                    comprehensive catalog.
                </p>
                
                <div class="features">
                    <div class="feature">
                        <h3>💼 Role-Based Matching</h3>
                        <p>Get recommendations tailored to specific job titles and responsibilities.</p>
                    </div>
                    <div class="feature">
                        <h3>🧠 Skill Assessment</h3>
                        <p>Evaluate technical, cognitive, and soft skills with precision.</p>
                    </div>
                    <div class="feature">
                        <h3>🎓 Comprehensive Catalog</h3>
                        <p>Access our full range of SHL assessments across all categories.</p>
                    </div>
                    <div class="feature">
                        <h3>⚡ Quick Insights</h3>
                        <p>Get instant recommendations based on your hiring requirements.</p>
                    </div>
                </div>
                
                <h3 style="color: #667eea; margin-top: 30px; margin-bottom: 15px;">Example Queries</h3>
                <ul style="color: #666; line-height: 2;">
                    <li>✓ "I'm hiring a Java developer"</li>
                    <li>✓ "We need a sales manager"</li>
                    <li>✓ "Looking for customer service representatives"</li>
                    <li>✓ "Senior leadership position"</li>
                </ul>
            </div>
            
            <div class="chat-container">
                <div class="chat-header">
                    <h3>💬 Chat with AI Assistant</h3>
                </div>
                
                <div class="messages" id="messages"></div>
                
                <div class="input-area">
                    <input 
                        type="text" 
                        id="messageInput" 
                        placeholder="Describe the role you're hiring for..."
                        autocomplete="off"
                    >
                    <button id="sendBtn" onclick="sendMessage()">Send</button>
                </div>
            </div>
        </div>
        
        <script>
            const messagesDiv = document.getElementById('messages');
            const messageInput = document.getElementById('messageInput');
            const sendBtn = document.getElementById('sendBtn');
            let conversationHistory = [];
            
            // Add initial greeting
            function addInitialMessage() {
                const greeting = "Hello! I'm your SHL Assessment Recommender. I'll help you find the perfect assessment for your hiring needs. What role are you looking to hire for?";
                addMessage(greeting, 'assistant');
            }
            
            function addMessage(content, role, recommendations = []) {
                const messageEl = document.createElement('div');
                messageEl.className = `message ${role}`;
                
                let html = `<div class="message-content">${escapeHtml(content)}`;
                
                if (recommendations && recommendations.length > 0) {
                    html += '<div class="recommendations"><strong>Recommended Assessments:</strong>';
                    recommendations.forEach(rec => {
                        html += `<div class="recommendation-item"><strong>${escapeHtml(rec.name)}</strong> (${escapeHtml(rec.test_type)}) - <a href="${escapeHtml(rec.url)}" target="_blank">View</a></div>`;
                    });
                    html += '</div>';
                }
                
                html += '</div>';
                messageEl.innerHTML = html;
                messagesDiv.appendChild(messageEl);
                messagesDiv.scrollTop = messagesDiv.scrollHeight;
            }
            
            function escapeHtml(text) {
                const div = document.createElement('div');
                div.textContent = text;
                return div.innerHTML;
            }
            
            async function sendMessage() {
                const message = messageInput.value.trim();
                if (!message) return;
                
                // Add user message
                addMessage(message, 'user');
                conversationHistory.push({ role: 'user', content: message });
                
                messageInput.value = '';
                sendBtn.disabled = true;
                
                // Add loading indicator
                const loadingEl = document.createElement('div');
                loadingEl.className = 'message assistant';
                loadingEl.innerHTML = '<div class="message-content"><span class="loading"></span>Thinking...</div>';
                messagesDiv.appendChild(loadingEl);
                messagesDiv.scrollTop = messagesDiv.scrollHeight;
                
                try {
                    const response = await fetch('/chat', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ messages: conversationHistory })
                    });
                    
                    if (!response.ok) throw new Error('Failed to get response');
                    
                    const data = await response.json();
                    
                    // Remove loading indicator
                    loadingEl.remove();
                    
                    // Add assistant message
                    addMessage(data.reply, 'assistant', data.recommendations);
                    conversationHistory.push({ role: 'assistant', content: data.reply });
                    
                } catch (error) {
                    loadingEl.remove();
                    addMessage('Sorry, I encountered an error. Please try again.', 'assistant');
                } finally {
                    sendBtn.disabled = false;
                    messageInput.focus();
                }
            }
            
            // Allow Enter key to send
            messageInput.addEventListener('keypress', (e) => {
                if (e.key === 'Enter' && !e.shiftKey) {
                    e.preventDefault();
                    sendMessage();
                }
            });
            
            // Initialize
            addInitialMessage();
            messageInput.focus();
        </script>
    </body>
    </html>
    """


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "ok"}


@app.post("/chat")
async def chat(request: ChatRequest) -> ChatResponse:
    """Main chat endpoint for conversational recommendations."""
    if not request.messages:
        raise HTTPException(status_code=400, detail="Messages cannot be empty")

    if len(request.messages) > 8:
        raise HTTPException(
            status_code=400, detail="Conversation exceeds 8 turns limit"
        )

    conversation_turn = len(request.messages)

    # Build system prompt with catalog context
    system_prompt = f"""You are a helpful SHL Assessment Recommender AI assistant. Your job is to help hiring managers and recruiters find the right SHL assessment for their role.

IMPORTANT RULES:
1. Only recommend assessments from the SHL catalog provided.
2. Start by understanding the role - ask clarifying questions about job title, responsibilities, seniority level, and key skills.
3. Once you have enough context (typically after 3-4 turns), provide 1-10 tailored assessment recommendations.
4. You can compare assessments if asked - use catalog data only.
5. Refuse off-topic requests like general hiring advice, legal questions, or non-SHL topics.
6. Be conversational and helpful, but concise.

SHL CATALOG:
{get_catalog_context()}

CONVERSATION HISTORY:
{json.dumps([msg.model_dump() for msg in request.messages], indent=2)}

Respond naturally to continue the conversation. If you have enough information and confidence in recommendations, provide them now."""

    # Get LLM response
    reply = get_llm_response(request.messages, system_prompt)

    # Get recommendations based on context
    recommendations, should_end = get_recommendations(request.messages, conversation_turn)

    # Check for off-topic or refusal signals
    if any(
        phrase in reply.lower()
        for phrase in ["can't help", "not sure", "i'm not able", "outside my scope"]
    ):
        recommendations = []
        should_end = False

    return ChatResponse(
        reply=reply,
        recommendations=recommendations,
        end_of_conversation=should_end and len(recommendations) > 0,
    )


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)

