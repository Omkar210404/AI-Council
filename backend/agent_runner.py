import json
import os
import asyncio
from typing import List, Dict, Any, Union
from backend.models import AgentResponse, AgentFailure
from backend.llm_router import BaseLLMProvider, LLMProviderError

CONFIG_PATH = os.path.join(os.path.dirname(__file__), "agents_config.json")

def load_agents_config() -> List[Dict[str, Any]]:
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        return json.load(f)

def get_agent_config(agent_id: str) -> Dict[str, Any]:
    configs = load_agents_config()
    for cfg in configs:
        if cfg["id"] == agent_id:
            return cfg
    raise ValueError(f"Agent ID '{agent_id}' not found in configuration.")

AGENT_JSON_SCHEMA_INSTRUCTION = """
You MUST return your answer strictly as a JSON object adhering to this schema:
{
  "agent_id": "<your agent id>",
  "agent_name": "<your name>",
  "stance": "for" | "against" | "mixed",
  "key_points": [
    "3 to 5 clear, honest, non-repetitive key points supporting your perspective"
  ],
  "assumptions": [
    "List key assumptions your analysis relies on"
  ],
  "missing_information": [
    "List critical pieces of information missing from the prompt needed for an ideal verdict"
  ],
  "confidence": <integer from 0 to 10>,
  "best_or_worst_case": "Specific realistic scenario or outcome projection"
}
CRITICAL RULES:
- Do NOT hallucinate or invent fake statistics or unverified studies.
- When unsure, explicitly say you are unsure in your key points or missing information.
- Provide honest, grounded, independent thinking.
- Output valid JSON only, without markdown wraps.
"""

async def run_single_agent(
    agent_cfg: Dict[str, Any],
    neutral_question: str,
    provider: BaseLLMProvider,
    timeout_seconds: float = 30.0
) -> Union[AgentResponse, AgentFailure]:
    """
    Executes a single agent with a timeout and one retry upon failure.
    """
    agent_id = agent_cfg["id"]
    agent_name = agent_cfg["name"]
    system_prompt = agent_cfg["system_prompt"] + "\n" + AGENT_JSON_SCHEMA_INSTRUCTION

    user_prompt = f"Topic to evaluate:\n\"{neutral_question}\"\n\nDeliver your independent analysis as {agent_name}."

    last_error = ""
    for attempt in range(2):  # 1 initial + 1 retry
        try:
            # Wrap with timeout
            raw_json = await asyncio.wait_for(
                provider.generate_json(user_prompt, system_prompt=system_prompt),
                timeout=timeout_seconds
            )
            # Ensure agent_id and agent_name are populated
            raw_json["agent_id"] = agent_id
            raw_json["agent_name"] = agent_name
            # Validate with Pydantic
            response = AgentResponse.model_validate(raw_json)
            return response
        except asyncio.TimeoutError:
            last_error = f"Agent {agent_name} timed out after {timeout_seconds}s (attempt {attempt + 1})"
        except Exception as e:
            last_error = f"Agent {agent_name} error: {str(e)}"
        
        await asyncio.sleep(0.5)

    return AgentFailure(agent_id=agent_id, agent_name=agent_name, error=last_error)
