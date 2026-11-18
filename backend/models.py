from typing import List, Optional, Literal, Dict, Any
from pydantic import BaseModel, Field

# Agent Stance
StanceType = Literal["for", "against", "mixed"]

class AgentResponse(BaseModel):
    agent_id: str
    agent_name: str
    stance: StanceType
    key_points: List[str] = Field(
        ...,
        min_length=1,
        description="3 to 5 key points argued by the agent"
    )
    assumptions: List[str] = Field(
        default_factory=list,
        description="Assumptions this argument relies on"
    )
    missing_information: List[str] = Field(
        default_factory=list,
        description="Crucial facts or data missing from the question"
    )
    confidence: int = Field(
        ...,
        ge=0,
        le=10,
        description="Confidence score from 0 to 10"
    )
    best_or_worst_case: Optional[str] = Field(
        None,
        description="Realistic best case (optimist), worst case (pessimist), or projected scenario"
    )

class AgentFailure(BaseModel):
    agent_id: str
    agent_name: str
    error: str

VerdictType = Literal["Recommended", "Not recommended", "Depends"]

class AgreementPoint(BaseModel):
    topic: str
    agents_involved: List[str]

class DisagreementPoint(BaseModel):
    topic: str
    side_a: str
    side_b: str
    stronger_side: str
    reasoning: str

class JudgeVerdict(BaseModel):
    verdict: VerdictType
    score: int = Field(..., ge=0, le=100, description="Confidence/viability score 0 to 100")
    confidence: int = Field(..., ge=0, le=10, description="Judge's confidence in this evaluation")
    summary: str = Field(..., description="Short readable synthesis on top")
    agreements: List[AgreementPoint] = Field(default_factory=list)
    disagreements: List[DisagreementPoint] = Field(default_factory=list)
    influential_agent: str = Field(..., description="Name of the agent whose arguments influenced verdict most and why")
    reasons_for_verdict: List[str] = Field(..., description="Why the judge reached this conclusion")
    conditions_to_change_verdict: List[str] = Field(
        ...,
        description="Key conditions or threshold shifts under which the verdict would change"
    )
    things_to_find_out: List[str] = Field(
        ...,
        description="2 to 3 high-leverage things user should investigate before deciding"
    )

class DecisionSession(BaseModel):
    id: str
    created_at: str
    original_question: str
    neutral_question: str
    selected_agent_ids: List[str]
    agent_outputs: Dict[str, Any]
    verdict: Optional[Dict[str, Any]] = None
    model_config_used: Optional[Dict[str, Any]] = None

class EvaluateRequest(BaseModel):
    question: str
    agent_ids: Optional[List[str]] = Field(default=None, description="2 to 5 agent IDs")
    agent_provider: Optional[str] = "gemini"
    agent_model: Optional[str] = "gemini-1.5-flash"
    judge_provider: Optional[str] = "gemini"
    judge_model: Optional[str] = "gemini-1.5-pro"
