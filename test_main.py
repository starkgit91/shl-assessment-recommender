"""
Test suite for SHL Assessment Recommender API.
"""
import pytest
import json
from fastapi.testclient import TestClient
from main import app, CATALOG

client = TestClient(app)


def test_health_check():
    """Test /health endpoint."""
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"


def test_chat_empty_messages():
    """Test /chat with empty messages."""
    response = client.post("/chat", json={"messages": []})
    assert response.status_code == 400


def test_chat_single_message():
    """Test /chat with single user message."""
    response = client.post(
        "/chat",
        json={
            "messages": [
                {"role": "user", "content": "I need an assessment for a Java developer"}
            ]
        },
    )
    assert response.status_code == 200
    data = response.json()

    # Verify schema
    assert "reply" in data
    assert "recommendations" in data
    assert "end_of_conversation" in data
    assert isinstance(data["reply"], str)
    assert isinstance(data["recommendations"], list)
    assert isinstance(data["end_of_conversation"], bool)


def test_chat_multiple_turns():
    """Test multi-turn conversation."""
    messages = [
        {"role": "user", "content": "I'm hiring a Java developer"},
        {"role": "assistant", "content": "What seniority level?"},
        {"role": "user", "content": "Mid-level, around 4 years experience"},
    ]

    response = client.post("/chat", json={"messages": messages})
    assert response.status_code == 200
    data = response.json()

    # Should have recommendations by turn 3
    assert "reply" in data
    assert isinstance(data["recommendations"], list)


def test_chat_recommendations_from_catalog():
    """Test that recommendations are from catalog only."""
    messages = [
        {"role": "user", "content": "I need a Java developer"},
        {"role": "assistant", "content": "What level?"},
        {"role": "user", "content": "Senior level"},
        {"role": "assistant", "content": "Any other requirements?"},
        {
            "role": "user",
            "content": "Good problem-solving and communication skills",
        },
    ]

    response = client.post("/chat", json={"messages": messages})
    assert response.status_code == 200
    data = response.json()

    catalog_names = {a["name"] for a in CATALOG["assessments"]}

    for rec in data["recommendations"]:
        assert rec["name"] in catalog_names, f"{rec['name']} not in catalog"
        assert rec["url"].startswith("https://www.shl.com")
        assert rec["test_type"] in ["Personality", "Ability", "Technical Skill"]


def test_chat_recommendations_within_bounds():
    """Test that recommendations are 1-10 when provided."""
    messages = [
        {"role": "user", "content": "Hiring multiple positions"},
        {"role": "assistant", "content": "What kind of roles?"},
        {"role": "user", "content": "Sales, marketing, and customer service"},
        {"role": "assistant", "content": "Any specific requirements?"},
        {"role": "user", "content": "Entry to mid-level positions"},
    ]

    response = client.post("/chat", json={"messages": messages})
    assert response.status_code == 200
    data = response.json()

    recs = data["recommendations"]
    if len(recs) > 0:
        assert len(recs) <= 10, f"Too many recommendations: {len(recs)}"


def test_chat_turn_limit():
    """Test that turn limit is enforced."""
    # Create 9 turns (exceeds limit of 8)
    messages = [
        {"role": "user", "content": f"Turn {i}"} for i in range(1, 10)
    ]

    response = client.post("/chat", json={"messages": messages})
    assert response.status_code == 400


def test_chat_schema_compliance():
    """Test response schema compliance."""
    response = client.post(
        "/chat",
        json={
            "messages": [
                {
                    "role": "user",
                    "content": "I need to hire a software engineer",
                }
            ]
        },
    )
    assert response.status_code == 200
    data = response.json()

    # Check all required fields
    assert "reply" in data and isinstance(data["reply"], str)
    assert "recommendations" in data and isinstance(data["recommendations"], list)
    assert "end_of_conversation" in data and isinstance(
        data["end_of_conversation"], bool
    )

    # Check recommendation structure
    for rec in data["recommendations"]:
        assert "name" in rec
        assert "url" in rec
        assert "test_type" in rec
        assert isinstance(rec["name"], str)
        assert isinstance(rec["url"], str)
        assert isinstance(rec["test_type"], str)


def test_vague_query_no_recommendations():
    """Test that vague queries don't immediately recommend."""
    response = client.post(
        "/chat",
        json={"messages": [{"role": "user", "content": "I need an assessment"}]},
    )
    assert response.status_code == 200
    data = response.json()

    # Vague query should have no recommendations on first turn
    assert len(data["recommendations"]) == 0


def test_comparison_request():
    """Test comparison between assessments."""
    messages = [
        {"role": "user", "content": "I'm hiring a Java developer"},
        {
            "role": "assistant",
            "content": "What about personality assessments?",
        },
        {"role": "user", "content": "What's the difference between OPQ32r and EQ?"},
    ]

    response = client.post("/chat", json={"messages": messages})
    assert response.status_code == 200
    data = response.json()

    assert "reply" in data
    # Comparison queries may or may not have recommendations


def test_off_topic_request():
    """Test that off-topic requests are handled."""
    messages = [
        {
            "role": "user",
            "content": "Can you help me with general hiring advice not related to SHL?",
        }
    ]

    response = client.post("/chat", json={"messages": messages})
    assert response.status_code == 200
    data = response.json()

    assert "reply" in data
    # Should have empty recommendations for off-topic
    assert len(data["recommendations"]) == 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
