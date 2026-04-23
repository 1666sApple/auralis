"""
JSON Helper Utilities.
Provides robust extraction and parsing of JSON from LLM outputs.
"""

import json
import re
from typing import Optional, Any, Tuple
from src.shared.logger.logger_config import get_logger

logger = get_logger(__name__)

def extract_json_from_text(text: str) -> str:
    """
    Extracts the first valid JSON object from a string.
    Handles:
    - Markdown code blocks (```json ... ```)
    - Raw JSON strings
    - Nested braces correctly (ignoring braces inside strings)
    
    Returns:
        The extracted JSON string.
        
    Raises:
        ValueError: If no JSON-like structure is found.
    """
    text = text.strip()

    # 1. Try Markdown Code Blocks (Prioritize ```json)
    json_block_match = re.search(r"```json\s*([\s\S]*?)\s*```", text, re.IGNORECASE)
    if json_block_match:
        content = json_block_match.group(1).strip()
        if content.startswith("{") or content.startswith("["):
            return content

    # 2. Try Generic Code Blocks (Verify content looks like JSON)
    generic_block_match = re.search(r"```\s*([\s\S]*?)\s*```", text)
    if generic_block_match:
        content = generic_block_match.group(1).strip()
        if content.startswith("{") or content.startswith("["):
            return content

    # 3. Extract using balanced braces (respecting strings)
    extracted = _extract_balanced_json(text)
    if extracted:
        return extracted
    
    # 4. Fallback: Simple substring (greedy)
    # Only if it actually looks like JSON
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1 and end > start:
        potential = text[start:end+1]
        if potential.count("{") == potential.count("}"):
             return potential

    raise ValueError("No JSON object found in text.")

def safe_parse_json(text: str) -> Tuple[Optional[Any], Optional[str]]:
    """
    Attempts to parse JSON from text safely, with repair attempts.
    
    Returns:
        (parsed_data, error_message)
    """
    json_str = ""
    try:
        json_str = extract_json_from_text(text)
        data = json.loads(json_str)
        return data, None
    except ValueError as e:
        # If extraction failed completely, return error
        if "No JSON object found" in str(e):
            return None, str(e)
        
        # If extraction succeeded but strict parsing failed, try repair
        try:
            repaired_str = _repair_json(json_str)
            data = json.loads(repaired_str)
            logger.info("JSON successfully repaired and parsed.")
            return data, None
        except Exception as repair_error:
            # Log the failed JSON for debugging
            logger.error(
                f"JSON Parsing Failed.\n"
                f"Error: {e}\n"
                f"Repair Failed: {repair_error}\n"
                f"Failed JSON content:\n{json_str}\n"
                f"Repaired attempt:\n{repaired_str}"
            )

            print("="*100)
            print(f"Failed JSON content:\n{json_str}\n")
            print(f"Repaired attempt:\n{repaired_str}")
            print("="*100)
            
            # Return original error with snippet
            return None, f"Parse failed: {e}. Repair failed: {repair_error}"
    except Exception as e:
         return None, str(e)

def _repair_json(json_str: str) -> str:
    """
    Attempt to fix common JSON syntax errors from LLMs.
    """
    # 1. Fix trailing commas (e.g. "key": "value", } -> "key": "value" })
    new_str = re.sub(r",\s*([\]}])", r"\1", json_str)
    
    # 2. Escape real newlines inside strings.
    # We use a regex to find string literals and replace \n inside them.
    # Pattern: " ( [^"\\] OR \\. )* "
    def replace_newlines_in_string(match):
        # Escape newlines and tabs inside the string content
        content = match.group(0)
        return content.replace('\n', '\\n').replace('\t', '\\t').replace('\r', '')

    new_str = re.sub(
        r'("(?:[^"\\]|\\.)*")', 
        replace_newlines_in_string, 
        new_str, 
        flags=re.DOTALL
    )
    
    return new_str

def _extract_balanced_json(text: str) -> Optional[str]:
    """
    Extracts the first outermost JSON object {...} correctly handling strings.
    """
    start_idx = text.find("{")
    if start_idx == -1:
        return None
        
    stack = []
    in_string = False
    escape = False
    
    # Iterate starting from the first open brace
    for i in range(start_idx, len(text)):
        char = text[i]
        
        if in_string:
            if escape:
                escape = False
            elif char == "\\":
                escape = True
            elif char == '"':
                in_string = False
            continue
            
        # Not in string
        if char == '"':
            in_string = True
        elif char == "{":
            stack.append("{")
        elif char == "}":
            if not stack:
                # Should not happen if we started at a brace, but safety check
                return None
            stack.pop()
            if not stack:
                # Found the matching closing brace
                return text[start_idx:i+1]
                
    return None # unclosed or truncated
