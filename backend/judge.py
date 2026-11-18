import json
from typing import List, Dict, Any, Union
from backend.models import AgentResponse, AgentFailure, JudgeVerdict
from backend.llm_router import BaseLLMProvider, LLMProviderError

JUDGE_SYSTEM_PROMPT = """You are the Supreme Judge of the Decision Council.
You receive a neutral decision question and the independent analyses of several Council agents.
Some agents may have failed to respond.

Your duties:
1. WEIGH BY QUALITY, NOT QUANTITY: Do not simply tally votes or take a mathematical average. A single well-grounded risk argument or historical base rate can outweigh three superficial enthusiastic points.
2. SYNTHESIZE HONESTLY: Detail exactly where the agents agree and where they disagree. For each disagreement, clearly declare which side you find stronger and why.
3. INFLUENCE ATTRIBUTION: Name the specific agent whose arguments influenced your verdict most, citing their strongest contribution.
4. FINAL VERDICT & METRICS: Give an honest verdict:
   - "Recommended": The evidence and risk/reward strongly favor proceeding.
   - "Not recommended": The risks, costs, or adverse base rates clearly outweigh benefits.
   - "Depends": The outcome fundamentally relies on personal parameters (e.g. cash runway, skill, risk appetite) that are currently unknown.
   You are explicitly allowed and encouraged to choose "Depends" or express that you do not have enough information. Never flatter or placate the user.
5. CONDITIONS TO CHANGE: Outline the specific conditions under which your verdict would flip.
6. WHAT TO FIND OUT: Give 2 to 3 concrete, high-leverage things the user must discover or verify before deciding.

Return strictly a JSON object matching this schema:
{
  "verdict": "Recommended" | "Not recommended" | "Depends",
  "score": <integer from 0 to 100 representing viability or strength of case>,
  "confidence": <integer from 0 to 10>,
  "summary": "<Short readable 2-3 sentence synthesis on top>",
  "agreements": [
    {
      "topic": "<summary of common ground>",
      "agents_involved": ["Agent Name A", "Agent Name B"]
    }
  ],
  "disagreements": [
    {
      "topic": "<topic of contention>",
      "side_a": "<Stance / argument from first group>",
      "side_b": "<Stance / argument from second group>",
      "stronger_side": "<Which side is more convincing>",
      "reasoning": "<Why that side is stronger>"
    }
  ],
  "influential_agent": "<Agent name and why their analysis tipped the scales>",
  "reasons_for_verdict": [
    "<Primary reason 1>",
    "<Primary reason 2>"
  ],
  "conditions_to_change_verdict": [
    "<Condition 1 under which verdict would change>",
    "<Condition 2 under which verdict would change>"
  ],
  "things_to_find_out": [
    "<Actionable discovery item 1>",
    "<Actionable discovery item 2>"
  ]
}
"""

def build_judge_prompt(
    neutral_question: str,
    agent_results: List[Union[AgentResponse, AgentFailure]]
) -> str:
    prompt = f"### Neutral Proposition to Decide:\n\"{neutral_question}\"\n\n"
    prompt += "### Council Agent Deliberations:\n\n"

    for res in agent_results:
        if isinstance(res, AgentResponse):
            prompt += f"--- AGENT: {res.agent_name} (Stance: {res.stance.upper()}, Confidence: {res.confidence}/10) ---\n"
            prompt += "Key Points:\n"
            for kp in res.key_points:
                prompt += f"  * {kp}\n"
            if res.assumptions:
                prompt += "Assumptions:\n"
                for a in res.assumptions:
                    prompt += f"  - {a}\n"
            if res.missing_information:
                prompt += "Missing Info Identified:\n"
                for mi in res.missing_information:
                    prompt += f"  - {mi}\n"
            if res.best_or_worst_case:
                prompt += f"Projected Case: {res.best_or_worst_case}\n"
            prompt += "\n"
        elif isinstance(res, AgentFailure):
            prompt += f"--- AGENT: {res.agent_name} (FAILED) ---\n"
            prompt += f"Note: This agent encountered a failure and could not report: {res.error}\n\n"
        elif isinstance(res, dict):
            # Dict fallback
            prompt += f"--- AGENT: {res.get('agent_name', 'Unknown')} ---\n"
            prompt += json.dumps(res, indent=2) + "\n\n"

    prompt += "Deliver your final, impartial Judge Verdict in strict JSON format now."
    return prompt

async def run_judge(
    neutral_question: str,
    agent_results: List[Union[AgentResponse, AgentFailure]],
    judge_provider: BaseLLMProvider
) -> JudgeVerdict:
    user_prompt = build_judge_prompt(neutral_question, agent_results)
    
    last_error = ""
    for attempt in range(2):
        try:
            raw_json = await judge_provider.generate_json(user_prompt, system_prompt=JUDGE_SYSTEM_PROMPT)
            return JudgeVerdict.model_validate(raw_json)
        except Exception as e:
            last_error = str(e)

    raise LLMProviderError(f"Judge evaluation failed after retry: {last_error}")
