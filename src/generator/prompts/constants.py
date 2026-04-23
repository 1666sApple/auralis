"""Unified prompt constants for consistent RAG system behavior."""

SCOPE_CONSTRAINT = """
<response_economy enforcement="critical">
  <rule id="answer_only">Answer ONLY what was explicitly asked</rule>
  <rule id="stop_immediately">STOP immediately after answering the question</rule>
  <prohibition>No trailing "For contractors specifically..." sections</prohibition>
  <prohibition>No unsolicited "Contact HR for..." recommendations</prohibition>
  <prohibition>No "Upon receiving reports..." procedural details unless asked</prohibition>
  <prohibition>No information about other employee categories unless asked</prohibition>
</response_economy>
"""

STOPPING_INSTRUCTION = """
**CRITICAL STOPPING RULES:**
1. STOP when you have answered the user's specific question
2. Do NOT add related information that wasn't asked
3. Do NOT mention what you're NOT answering
4. Do NOT add disclaimers unless legally required
5. Do NOT explain your reasoning process to the user
"""

CITATION_INSTRUCTION = """
<citation_protocol>
  <format>[Source: {filename}, Section: {section_name}, Page: {page_number}]</format>
  <rule>Cite sources inline, immediately after the relevant claim</rule>
  <rule>Use exact section names from documents</rule>
  <rule>Include page numbers when available</rule>
</citation_protocol>
"""

FAQ_CONSTRAINT = """
Answer this question in ONE brief sentence maximum.
Examples of good answers:
- "Please contact your HR BGP."
- "Visit https://robi4.sharepoint.com/sites/robiportal"
- "Go to the Life Insurance Portal and submit your application."

DO NOT explain, elaborate, or add context. Just give the direct answer.
"""

RESPONSE_MODES = {
    "concise": {
        "description": "Maximum information density, minimal verbosity",
        "max_tokens": 300,
        "structure": "No headers, bullet points only if listing ≥3 items",
    },
    "detailed": {
        "description": "Comprehensive explanation with context",
        "max_tokens": 800,
        "structure": "Structured with headers if needed",
    },
    "conversational": {
        "description": "Natural, friendly tone",
        "max_tokens": 500,
        "structure": "Flowing prose",
    },
}


def get_scope_constraint() -> str:
    """
    Get the unified scope constraint for prompts.

    Returns:
        Scope constraint string.
    """
    return SCOPE_CONSTRAINT


def get_stopping_instruction() -> str:
    """
    Get the stopping instruction for reasoning methods.

    Returns:
        Stopping instruction string.
    """
    return STOPPING_INSTRUCTION


def get_faq_constraint() -> str:
    """
    Get the ultra-brief constraint for FAQ lookups.

    Returns:
        FAQ constraint string.
    """
    return FAQ_CONSTRAINT


def build_constrained_prompt(
    base_prompt: str,
    include_scope: bool = True,
    include_stopping: bool = True,
    include_citation: bool = False,
) -> str:
    """
    Build a prompt with standardized constraints.

    Args:
        base_prompt: The main prompt content.
        include_scope: Include scope constraint.
        include_stopping: Include stopping instruction.
        include_citation: Include citation instruction.

    Returns:
        Complete prompt with constraints.
    """
    parts = [base_prompt]

    if include_scope:
        parts.append(SCOPE_CONSTRAINT)

    if include_citation:
        parts.append(CITATION_INSTRUCTION)

    if include_stopping:
        parts.append(STOPPING_INSTRUCTION)

    return "\n\n".join(parts)
