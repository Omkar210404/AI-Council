import os
import json
import re
from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
import httpx

class LLMProviderError(Exception):
    """Raised when an LLM provider encounters an error."""
    pass

class LLMNotConfiguredError(LLMProviderError):
    """Raised when required API key or endpoint is missing."""
    pass

def extract_json_from_text(text: str) -> Dict[str, Any]:
    """Helper to cleanly extract JSON even if wrapped in markdown codeblocks."""
    text = text.strip()
    if text.startswith("```json"):
        text = text[len("```json"):].strip()
    elif text.startswith("```"):
        text = text[len("```"):].strip()
    if text.endswith("```"):
        text = text[:-3].strip()
    
    # Try direct parse
    try:
        return json.loads(text)
    except Exception:
        # Try finding outermost { ... }
        match = re.search(r'(\{.*\})', text, re.DOTALL)
        if match:
            return json.loads(match.group(1))
        raise

class BaseLLMProvider(ABC):
    @abstractmethod
    async def generate_json(self, prompt: str, system_prompt: Optional[str] = None) -> Dict[str, Any]:
        """Generate a structured JSON dictionary from prompt."""
        pass

    @abstractmethod
    async def generate_text(self, prompt: str, system_prompt: Optional[str] = None) -> str:
        """Generate raw text response."""
        pass

class GeminiProvider(BaseLLMProvider):
    def __init__(self, api_key: Optional[str] = None, model: str = "gemini-3.8-flash"):
        self.api_key = api_key or os.getenv("GEMINI_API_KEY", "")
        self.model = model or "gemini-3.8-flash"

    async def generate_text(self, prompt: str, system_prompt: Optional[str] = None) -> str:
        if not self.api_key:
            raise LLMNotConfiguredError("Gemini API key is not configured. Please set GEMINI_API_KEY in .env.")
        
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{self.model}:generateContent?key={self.api_key}"
        contents = []
        if system_prompt:
            contents.append({"role": "user", "parts": [{"text": f"System Instructions: {system_prompt}"}]})
            contents.append({"role": "model", "parts": [{"text": "Understood. I will strictly follow these instructions."}]})
        contents.append({"role": "user", "parts": [{"text": prompt}]})

        payload = {
            "contents": contents,
            "generationConfig": {"temperature": 0.2}
        }

        async with httpx.AsyncClient(timeout=45.0) as client:
            resp = await client.post(url, json=payload)
            if resp.status_code != 200:
                raise LLMProviderError(f"Gemini API returned error {resp.status_code}: {resp.text}")
            data = resp.json()
            try:
                return data["candidates"][0]["content"]["parts"][0]["text"]
            except (KeyError, IndexError) as e:
                raise LLMProviderError(f"Unexpected response structure from Gemini: {resp.text}")

    async def generate_json(self, prompt: str, system_prompt: Optional[str] = None) -> Dict[str, Any]:
        json_instruction = "\n\nRespond ONLY with a valid, parseable JSON object matching the requested schema. Do not enclose in backticks or include conversational filler."
        raw = await self.generate_text(prompt + json_instruction, system_prompt=system_prompt)
        try:
            return extract_json_from_text(raw)
        except Exception as e:
            raise LLMProviderError(f"Failed to parse JSON from Gemini response: {raw}") from e

class OpenAIProvider(BaseLLMProvider):
    def __init__(self, api_key: Optional[str] = None, model: str = "gpt-4o-mini", base_url: str = "https://api.openai.com/v1"):
        self.api_key = api_key or os.getenv("OPENAI_API_KEY", "")
        self.model = model or "gpt-4o-mini"
        self.base_url = base_url.rstrip("/")

    async def generate_text(self, prompt: str, system_prompt: Optional[str] = None) -> str:
        if not self.api_key:
            raise LLMNotConfiguredError("OpenAI API key is not configured. Please set OPENAI_API_KEY in .env.")
        
        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        payload = {
            "model": self.model,
            "messages": messages,
            "temperature": 0.2
        }

        async with httpx.AsyncClient(timeout=45.0) as client:
            resp = await client.post(f"{self.base_url}/chat/completions", headers=headers, json=payload)
            if resp.status_code != 200:
                raise LLMProviderError(f"OpenAI API error {resp.status_code}: {resp.text}")
            data = resp.json()
            return data["choices"][0]["message"]["content"]

    async def generate_json(self, prompt: str, system_prompt: Optional[str] = None) -> Dict[str, Any]:
        json_instruction = "\n\nOutput only valid JSON."
        raw = await self.generate_text(prompt + json_instruction, system_prompt=system_prompt)
        return extract_json_from_text(raw)

class GroqProvider(OpenAIProvider):
    def __init__(self, api_key: Optional[str] = None, model: str = "llama-3.3-70b-versatile"):
        key = api_key or os.getenv("GROQ_API_KEY", "")
        if not key:
            # We don't raise here, we raise in generate_text if not configured
            pass
        super().__init__(api_key=key, model=model or "llama-3.3-70b-versatile", base_url="https://api.groq.com/openai/v1")

    async def generate_text(self, prompt: str, system_prompt: Optional[str] = None) -> str:
        if not self.api_key:
            raise LLMNotConfiguredError("Groq API key is not configured. Please set GROQ_API_KEY in .env.")
        return await super().generate_text(prompt, system_prompt)

class AnthropicProvider(BaseLLMProvider):
    def __init__(self, api_key: Optional[str] = None, model: str = "claude-3-5-sonnet-20241022"):
        self.api_key = api_key or os.getenv("ANTHROPIC_API_KEY", "")
        self.model = model or "claude-3-5-sonnet-20241022"

    async def generate_text(self, prompt: str, system_prompt: Optional[str] = None) -> str:
        if not self.api_key:
            raise LLMNotConfiguredError("Anthropic API key is not configured. Please set ANTHROPIC_API_KEY in .env.")
        
        headers = {
            "x-api-key": self.api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json"
        }
        payload = {
            "model": self.model,
            "max_tokens": 2048,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.2
        }
        if system_prompt:
            payload["system"] = system_prompt

        async with httpx.AsyncClient(timeout=45.0) as client:
            resp = await client.post("https://api.anthropic.com/v1/messages", headers=headers, json=payload)
            if resp.status_code != 200:
                raise LLMProviderError(f"Anthropic API error {resp.status_code}: {resp.text}")
            data = resp.json()
            return data["content"][0]["text"]

    async def generate_json(self, prompt: str, system_prompt: Optional[str] = None) -> Dict[str, Any]:
        json_prompt = prompt + "\n\nRespond strictly with valid JSON only. Do not add markdown backticks."
        raw = await self.generate_text(json_prompt, system_prompt=system_prompt)
        return extract_json_from_text(raw)

class OllamaProvider(BaseLLMProvider):
    def __init__(self, base_url: Optional[str] = None, model: str = "llama3"):
        self.base_url = (base_url or os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")).rstrip("/")
        self.model = model or "llama3"

    async def generate_text(self, prompt: str, system_prompt: Optional[str] = None) -> str:
        payload = {
            "model": self.model,
            "prompt": prompt,
            "stream": False,
            "options": {"temperature": 0.2}
        }
        if system_prompt:
            payload["system"] = system_prompt

        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                resp = await client.post(f"{self.base_url}/api/generate", json=payload)
                if resp.status_code != 200:
                    raise LLMProviderError(f"Ollama returned status {resp.status_code}: {resp.text}")
                data = resp.json()
                return data.get("response", "")
        except httpx.ConnectError as e:
            raise LLMNotConfiguredError(f"Ollama is not reachable at {self.base_url}. Ensure Ollama is running.") from e

    async def generate_json(self, prompt: str, system_prompt: Optional[str] = None) -> Dict[str, Any]:
        json_prompt = prompt + "\n\nFormat your output strictly as a JSON object."
        raw = await self.generate_text(json_prompt, system_prompt=system_prompt)
        return extract_json_from_text(raw)

class MockLLMProvider(BaseLLMProvider):
    """Deterministic mock provider used for tests, demonstrations, and offline consistency checks."""
    def __init__(self, simulated_stance: str = "mixed", force_error: bool = False):
        self.simulated_stance = simulated_stance
        self.force_error = force_error

    async def generate_text(self, prompt: str, system_prompt: Optional[str] = None) -> str:
        if self.force_error:
            raise LLMProviderError("Simulated LLM connection timeout")
        # If neutraliser prompt
        if "Neutralise this question" in prompt or "neutral version" in prompt.lower():
            # Extract topic cleanly
            m = re.search(r'User Question:\s*"?([^"\n\r]+)"?', prompt)
            q = m.group(1) if m else "the proposal"
            clean_q = re.sub(r'^(is it a good idea to|is it a bad idea to|should i|is|should)\s*', '', q, flags=re.I).strip(" ?")
            return f"Evaluate {clean_q}: should the user proceed?"
        return "Mock plain text response"

    async def generate_json(self, prompt: str, system_prompt: Optional[str] = None) -> Dict[str, Any]:
        if self.force_error:
            raise LLMProviderError("Simulated provider failure during JSON generation")
        
        # Check if this is for the Judge
        if "You are the Judge" in prompt or (system_prompt and "Judge" in system_prompt):
            return {
                "verdict": "Depends",
                "score": 62,
                "confidence": 8,
                "summary": "The decision hinges on user financial runway and risk tolerance. Upsides are credible but downside operational risk requires verification.",
                "agreements": [
                    {
                        "topic": "Market demand exists but requires disciplined execution",
                        "agents_involved": ["Optimist", "Realist"]
                    }
                ],
                "disagreements": [
                    {
                        "topic": "Capital burn and timeline to break-even",
                        "side_a": "Optimist assumes quick traction within 6 months",
                        "side_b": "Pessimist highlights typical 18-month burn rate",
                        "stronger_side": "Pessimist / Realist",
                        "reasoning": "Historical base rates overwhelmingly indicate longer adoption cycles than optimistic initial projections."
                    }
                ],
                "influential_agent": "Realist, because baseline industry survival rates grounded the speculative assumptions.",
                "reasons_for_verdict": [
                    "Strong alignment that execution capability is the deciding bottleneck.",
                    "Downside is manageable if committed capital is capped."
                ],
                "conditions_to_change_verdict": [
                    "If the user has at least 12 months of non-dilutive living expenses saved, verdict upgrades to Recommended.",
                    "If customer commitments cannot be pre-validated, verdict downgrades to Not recommended."
                ],
                "things_to_find_out": [
                    "Interview 5 potential target users to confirm willingness to pay.",
                    "Calculate exact cash reserve threshold and stop-loss criteria."
                ]
            }

        # Otherwise, Agent JSON
        stance = self.simulated_stance
        agent_role = "Council Agent"
        if system_prompt:
            if "Optimist" in system_prompt:
                stance = "for"
                agent_role = "Optimist"
            elif "Pessimist" in system_prompt:
                stance = "against"
                agent_role = "Pessimist"
            elif "Realist" in system_prompt:
                stance = "mixed"
                agent_role = "Realist"
            elif "Risk Analyst" in system_prompt:
                stance = "against"
                agent_role = "Risk Analyst"
            elif "Long-Term Thinker" in system_prompt:
                stance = "mixed"
                agent_role = "Long-Term Thinker"

        return {
            "agent_id": agent_role.lower().replace(" ", "_"),
            "agent_name": agent_role,
            "stance": stance,
            "key_points": [
                f"Core point 1 analyzing viability from {agent_role} perspective.",
                f"Core point 2 examining constraints and direct outcomes.",
                f"Core point 3 evaluating realistic impact on the user's situation."
            ],
            "assumptions": [
                "User has baseline execution capabilities.",
                "Market conditions remain relatively stable over the decision horizon."
            ],
            "missing_information": [
                "Specific financial runway or available capital.",
                "User's alternative fallback options."
            ],
            "confidence": 7,
            "best_or_worst_case": f"Projected scenario evaluated through the lens of {agent_role}."
        }

def get_llm_provider(provider_name: str, model_name: Optional[str] = None) -> BaseLLMProvider:
    name = (provider_name or "gemini").lower()
    if name == "mock":
        return MockLLMProvider()
    elif name == "gemini":
        return GeminiProvider(model=model_name or "gemini-3.8-flash")
    elif name == "openai":
        return OpenAIProvider(model=model_name or "gpt-4o-mini")
    elif name == "groq":
        return GroqProvider(model=model_name or "qwen/qwen3.8-27b")
    elif name == "anthropic":
        return AnthropicProvider(model=model_name or "claude-3-5-sonnet-20241022")
    elif name == "ollama":
        return OllamaProvider(model=model_name or "llama3.2")
    else:
        raise ValueError(f"Unsupported LLM provider: {provider_name}")
