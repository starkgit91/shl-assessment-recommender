"""
Evaluation module for SHL Assessment Recommender system.
Tests recommendation quality, schema compliance, and behavior patterns.
"""
import json
from typing import Dict, List, Tuple
from pydantic import BaseModel


class ConversationTrace:
    """Represents a conversation trace with expected outcomes."""

    def __init__(self, persona: str, facts: Dict, expected_shortlist: List[str]):
        self.persona = persona
        self.facts = facts
        self.expected_shortlist = expected_shortlist


# Sample conversation traces for testing
TEST_TRACES = [
    ConversationTrace(
        persona="Tech Recruiter for Java Developer",
        facts={
            "role": "Java Developer",
            "seniority": "mid-level",
            "skills": ["Java", "stakeholder communication", "problem-solving"],
            "team_size": 10,
            "industry": "fintech",
        },
        expected_shortlist=["Java Programming", "CAPP", "OPQ32r", "CriticalReasoning"],
    ),
    ConversationTrace(
        persona="Sales Manager Hiring",
        facts={
            "role": "Sales Representative",
            "seniority": "entry-level",
            "skills": ["customer interaction", "communication", "persuasion"],
            "industry": "retail",
        },
        expected_shortlist=["Sales Aptitude", "Customer Service Aptitude", "OPQ32r"],
    ),
    ConversationTrace(
        persona="HR Manager for Leadership",
        facts={
            "role": "Engineering Manager",
            "seniority": "senior",
            "skills": ["team leadership", "technical background", "coaching"],
            "team_size": 15,
        },
        expected_shortlist=[
            "Leadership Potential Indicator",
            "OPQ32r",
            "Coaching Ability",
            "EQ Assessment",
        ],
    ),
]


def calculate_recall_at_k(
    recommended: List[str], expected: List[str], k: int = 10
) -> float:
    """
    Calculate Recall@K metric.
    
    Recall@K = (Number of relevant items in top K) / (Total relevant items)
    """
    if not expected:
        return 1.0
    
    relevant_in_top_k = sum(
        1 for item in recommended[:k] if item in expected
    )
    return relevant_in_top_k / len(expected)


def evaluate_schema_compliance(response_dict: Dict) -> Tuple[bool, List[str]]:
    """
    Check if response complies with required schema.
    
    Required fields:
    - reply (str)
    - recommendations (list of {name, url, test_type})
    - end_of_conversation (bool)
    """
    errors = []
    
    if "reply" not in response_dict:
        errors.append("Missing 'reply' field")
    elif not isinstance(response_dict["reply"], str):
        errors.append("'reply' must be a string")
    
    if "recommendations" not in response_dict:
        errors.append("Missing 'recommendations' field")
    elif not isinstance(response_dict["recommendations"], list):
        errors.append("'recommendations' must be a list")
    else:
        for idx, rec in enumerate(response_dict["recommendations"]):
            if not isinstance(rec, dict):
                errors.append(f"Recommendation {idx} is not a dict")
                continue
            
            required_fields = {"name", "url", "test_type"}
            for field in required_fields:
                if field not in rec:
                    errors.append(
                        f"Recommendation {idx} missing required field: {field}"
                    )
    
    if "end_of_conversation" not in response_dict:
        errors.append("Missing 'end_of_conversation' field")
    elif not isinstance(response_dict["end_of_conversation"], bool):
        errors.append("'end_of_conversation' must be a boolean")
    
    return len(errors) == 0, errors


def evaluate_recommendations_bounds(recommendations: List) -> Tuple[bool, str]:
    """Verify recommendations count is within 1-10 when provided."""
    if len(recommendations) == 0:
        return True, "No recommendations (acceptable when gathering context)"
    
    if len(recommendations) > 10:
        return False, f"Too many recommendations: {len(recommendations)} > 10"
    
    return True, f"Valid: {len(recommendations)} recommendations"


def evaluate_no_hallucinations(response_dict: Dict, catalog_names: List[str]) -> Tuple[bool, str]:
    """Check if recommendations are from catalog only."""
    for rec in response_dict.get("recommendations", []):
        if rec.get("name") not in catalog_names:
            return False, f"Hallucinated assessment: {rec.get('name')}"
    
    return True, "All recommendations from catalog"


def evaluate_turn_cap(turn_count: int) -> Tuple[bool, str]:
    """Verify conversation doesn't exceed 8 turns."""
    if turn_count > 8:
        return False, f"Exceeded turn limit: {turn_count} > 8"
    return True, f"Valid: {turn_count} turns"


class EvaluationReport:
    """Generates comprehensive evaluation report."""
    
    def __init__(self):
        self.schema_scores = []
        self.recall_scores = []
        self.hallucination_scores = []
        self.turn_cap_scores = []
        self.behavior_probes = []
    
    def add_conversation_result(
        self,
        response_dict: Dict,
        recommended_names: List[str],
        expected_names: List[str],
        turns: int,
        catalog_names: List[str],
    ):
        """Add evaluation results for a single conversation."""
        # Schema compliance
        schema_ok, schema_errors = evaluate_schema_compliance(response_dict)
        self.schema_scores.append((schema_ok, schema_errors))
        
        # Recommendations bounds
        bounds_ok, bounds_msg = evaluate_recommendations_bounds(
            response_dict.get("recommendations", [])
        )
        
        # Hallucination check
        halluc_ok, halluc_msg = evaluate_no_hallucinations(
            response_dict, catalog_names
        )
        self.hallucination_scores.append(halluc_ok)
        
        # Turn cap
        turn_ok, turn_msg = evaluate_turn_cap(turns)
        self.turn_cap_scores.append(turn_ok)
        
        # Recall@10
        if recommended_names:
            recall = calculate_recall_at_k(recommended_names, expected_names, k=10)
            self.recall_scores.append(recall)
    
    def get_summary(self) -> Dict:
        """Get evaluation summary statistics."""
        schema_pass_rate = (
            sum(1 for ok, _ in self.schema_scores if ok) / len(self.schema_scores)
            if self.schema_scores
            else 0
        )
        halluc_pass_rate = (
            sum(self.hallucination_scores) / len(self.hallucination_scores)
            if self.hallucination_scores
            else 0
        )
        turn_pass_rate = (
            sum(self.turn_cap_scores) / len(self.turn_cap_scores)
            if self.turn_cap_scores
            else 0
        )
        mean_recall = (
            sum(self.recall_scores) / len(self.recall_scores)
            if self.recall_scores
            else 0
        )
        
        return {
            "hard_evals": {
                "schema_compliance": schema_pass_rate,
                "no_hallucinations": halluc_pass_rate,
                "turn_cap_compliance": turn_pass_rate,
            },
            "recall_at_10": mean_recall,
            "total_conversations_evaluated": len(self.schema_scores),
        }


if __name__ == "__main__":
    # Example usage
    report = EvaluationReport()
    print("Evaluation module loaded. Use with API for testing.")
