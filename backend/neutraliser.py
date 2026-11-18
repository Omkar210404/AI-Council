import re
from typing import Optional
from backend.llm_router import BaseLLMProvider

NEUTRALISER_SYSTEM_PROMPT = """You are an objective linguistic editor. Your sole job is to rewrite user decision questions into a strictly neutral, unslanted form.
Rules:
1. Strip all leading, biasing, or rhetorical phrasing (e.g. "Is it a good idea to...", "Is X a terrible mistake?", "Why you should never...", "Don't you think I should...").
2. Retain all underlying facts, numbers, dates, budget constraints, or personal details given by the user.
3. Formulate the neutral question in the canonical format: "Evaluate [core proposition or action]: should the user proceed?" or "Evaluate whether [subject] should [action] under [given constraints]."
4. Return ONLY the rewritten neutral question as plain text. Do not add quotes, commentary, preamble, or explanations."""

async def neutralise_question(raw_question: str, llm_provider: Optional[BaseLLMProvider] = None) -> str:
    """
    Rewrites a leading user question into a neutral canonical evaluation form.
    Has robust fallback regex if provider is not configured or fails.
    """
    clean_input = raw_question.strip()
    if not clean_input:
        return "Evaluate the proposal: should the user proceed?"

    if llm_provider:
        try:
            prompt = f"User Question:\n\"{clean_input}\"\n\nNeutralise this question now according to the system instructions."
            rewritten = await llm_provider.generate_text(prompt, system_prompt=NEUTRALISER_SYSTEM_PROMPT)
            rewritten = rewritten.strip(' "\' \n\r')
            if rewritten and len(rewritten) > 5:
                return rewritten
        except Exception:
            # Fall back to algorithmic/regex neutralisation
            pass

    return algorithmic_neutralise(clean_input)

def algorithmic_neutralise(text: str) -> str:
    """
    Deterministic fallback neutraliser that removes common leading affirmative/negative biases.
    """
    cleaned = text.strip()
    # Strip leading bias patterns
    patterns = [
        r'^(is it|is this|is that)\s+a\s+(good|great|bad|terrible|smart|foolish|horrible|fantastic|wise)\s+(idea|choice|move|plan)\s+(to|if|for)\s+',
        r'^(is it|is this)\s+(worth it\s+(to)?|advisable to|dangerous to)\s+',
        r'^(should i|should we|ought i|ought we)\s+(really|honestly)?\s*',
        r'^(why shouldn\'t i|why wouldn\'t i|don\'t you think i should|tell me if i should)\s*',
        r'^(is\s+)',
        r'^(should\s+)'
    ]
    
    extracted = cleaned
    for p in patterns:
        m = re.match(p, extracted, flags=re.IGNORECASE)
        if m:
            extracted = extracted[m.end():]
            break
            
    extracted = extracted.strip(" ?.")
    if not extracted:
        extracted = cleaned.strip(" ?.")

    return f"Evaluate {extracted}: should the user do it?"
