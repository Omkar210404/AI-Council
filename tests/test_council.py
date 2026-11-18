import pytest
import asyncio
from backend.models import AgentResponse, AgentFailure, JudgeVerdict
from backend.neutraliser import neutralise_question, algorithmic_neutralise
from backend.llm_router import MockLLMProvider, extract_json_from_text
from backend.agent_runner import run_single_agent
from backend.judge import build_judge_prompt, run_judge

# 1. Tests for Neutraliser
@pytest.mark.asyncio
async def test_algorithmic_neutraliser():
    q1 = "Is it a good idea to quit my job?"
    res1 = algorithmic_neutralise(q1)
    assert "quit my job" in res1
    assert "good idea" not in res1.lower()
    assert res1.startswith("Evaluate ")

    q2 = "Is it a terrible idea to invest in crypto?"
    res2 = algorithmic_neutralise(q2)
    assert "invest in crypto" in res2
    assert "terrible" not in res2.lower()

    q3 = "Should I buy a second house?"
    res3 = algorithmic_neutralise(q3)
    assert "buy a second house" in res3

@pytest.mark.asyncio
async def test_llm_neutraliser_with_mock():
    mock_provider = MockLLMProvider()
    q = "Is it a good idea to expand our factory into Europe?"
    neut = await neutralise_question(q, mock_provider)
    assert "Evaluate" in neut
    assert "good idea" not in neut.lower()

# 2. Tests for JSON Extraction & Model Validation
def test_extract_json_markdown():
    wrapped = "```json\n{\"stance\": \"for\", \"confidence\": 9}\n```"
    parsed = extract_json_from_text(wrapped)
    assert parsed["stance"] == "for"
    assert parsed["confidence"] == 9

def test_agent_response_validation():
    valid_data = {
        "agent_id": "optimist",
        "agent_name": "Optimist",
        "stance": "for",
        "key_points": ["Strong growth vector", "First mover upside", "Talent availability"],
        "assumptions": ["Market remains solvent"],
        "missing_information": ["Exact budget limits"],
        "confidence": 8,
        "best_or_worst_case": "Doubling revenue in year 2"
    }
    model = AgentResponse.model_validate(valid_data)
    assert model.stance == "for"
    assert len(model.key_points) == 3
    assert model.confidence == 8

def test_judge_verdict_validation():
    valid_judge = {
        "verdict": "Depends",
        "score": 65,
        "confidence": 8,
        "summary": "Viable provided risk buffers exist.",
        "agreements": [{"topic": "Market demand is clear", "agents_involved": ["Optimist", "Realist"]}],
        "disagreements": [
            {
                "topic": "Runway duration",
                "side_a": "Optimist predicts fast break-even",
                "side_b": "Pessimist expects slow ramp",
                "stronger_side": "Pessimist",
                "reasoning": "Historical base rates suggest longer sales cycles."
            }
        ],
        "influential_agent": "Realist, due to baseline survival figures",
        "reasons_for_verdict": ["High execution dependency"],
        "conditions_to_change_verdict": ["Pre-signed customer contracts"],
        "things_to_find_out": ["Customer willingness to pay"]
    }
    verdict = JudgeVerdict.model_validate(valid_judge)
    assert verdict.verdict == "Depends"
    assert verdict.score == 65
    assert len(verdict.disagreements) == 1

# 3. Tests for Agent Execution & Failure Handling
@pytest.mark.asyncio
async def test_agent_runner_success():
    mock_provider = MockLLMProvider(simulated_stance="for")
    cfg = {
        "id": "optimist",
        "name": "Optimist",
        "system_prompt": "You are Optimist."
    }
    result = await run_single_agent(cfg, "Evaluate project launch", mock_provider)
    assert isinstance(result, AgentResponse)
    assert result.agent_id == "optimist"
    assert result.stance == "for"

@pytest.mark.asyncio
async def test_agent_runner_failure_handling():
    error_provider = MockLLMProvider(force_error=True)
    cfg = {
        "id": "pessimist",
        "name": "Pessimist",
        "system_prompt": "You are Pessimist."
    }
    result = await run_single_agent(cfg, "Evaluate project launch", error_provider, timeout_seconds=2.0)
    assert isinstance(result, AgentFailure)
    assert result.agent_id == "pessimist"
    assert "error" in result.error.lower() or "failure" in result.error.lower()

# 4. Tests for Judge Input Builder with Mixed Results (Success + Failure)
def test_judge_prompt_builder():
    agent_ok = AgentResponse(
        agent_id="optimist",
        agent_name="Optimist",
        stance="for",
        key_points=["Point 1", "Point 2"],
        confidence=8
    )
    agent_fail = AgentFailure(
        agent_id="risk_analyst",
        agent_name="Risk Analyst",
        error="Connection reset by peer"
    )
    prompt = build_judge_prompt("Evaluate opening new branch", [agent_ok, agent_fail])
    assert "Evaluate opening new branch" in prompt
    assert "AGENT: Optimist" in prompt
    assert "AGENT: Risk Analyst (FAILED)" in prompt
    assert "Connection reset by peer" in prompt

@pytest.mark.asyncio
async def test_judge_runner_with_mock():
    mock_provider = MockLLMProvider()
    agent_ok = AgentResponse(
        agent_id="optimist",
        agent_name="Optimist",
        stance="for",
        key_points=["Solid upside"],
        confidence=8
    )
    verdict = await run_judge("Evaluate expansion", [agent_ok], mock_provider)
    assert isinstance(verdict, JudgeVerdict)
    assert verdict.verdict in ["Recommended", "Not recommended", "Depends"]
    assert 0 <= verdict.score <= 100
