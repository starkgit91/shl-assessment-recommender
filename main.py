import os
import json
import logging
from typing import Optional
from fastapi import FastAPI, HTTPException
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


@app.get("/")
async def root():
    """Root endpoint — welcome message and API overview."""
    return {
        "message": "Welcome to the SHL Assessment Recommender API",
        "title": app.title,
        "version": app.version,
        "endpoints": {
            "/": "GET — This overview",
            "/health": "GET — Service health check",
            "/chat": "POST — Conversational assessment recommender",
            "/docs": "GET — Interactive Swagger UI documentation",
        },
        "usage": (
            "Send a POST request to /chat with a JSON body containing a "
            "'messages' array of {role, content} objects to start a "
            "conversation and receive tailored SHL assessment recommendations."
        ),
    }


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
