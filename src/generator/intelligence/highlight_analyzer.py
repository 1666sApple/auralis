"""
generator/intelligence/highlight_analyzer.py
===========================================
Uses AWS Bedrock to semantically segment headlines and assign visual styling (highlighting, scaling).
"""

from typing import List, Dict, Any
import re
import json
from src.generator.bedrock.bedrock_client import BedrockClient
from src.shared.logger.logger_config import get_logger

logger = get_logger(__name__)

class HighlightAnalyzer:
    """
    Analyzes telco offer components using LLM to return structured poppy styling metadata.
    """
    
    def __init__(self, bedrock_client: BedrockClient):
        self.client = bedrock_client
        self._cache: Dict[str, Any] = {}
        
    def clear_cache(self):
        self._cache = {}

    async def analyze_full_ad(self, offer_info: Dict[str, Any]) -> Dict[str, List[Dict[str, Any]]]:
        """
        Unified analysis of Headline, Subline, and Offer Details.
        Returns a mapping of segments for each component.
        """
        brand = offer_info.get("brand", "airtel").lower()

        headline = offer_info.get("headline", "")
        subline = offer_info.get("subline", "")
        details_list = offer_info.get("details", [])
        details_str = " | ".join(details_list)
        
        # system_prompt = (
        system_prompt = (
            
            "## ROLE: EXTREMELY STRICT Marketing Typography JSON Generator.\n"
            "## OUTPUT RULES:\n"
            "1. START YOUR RESPONSE WITH '{'.\n"
            "2. END YOUR RESPONSE WITH '}'.\n"
            "3. NO reasoning. NO markdown blocks. NO preamble.\n"
            "4. OUTPUT ONLY THE RAW JSON OBJECT.\n\n"
            # THE STYLING SYSTEM (Poppy - Airtel Brand Colors):\n
            "1. CORE OFFERS: Digits in the core offer MUST scale to 1.75x and highlight: true. Units should be skipped.\n"
            "2. CLEVER MARKETING: Validity within a offer should be 0.75x if the validity is not the key selling point like validity less than 15 days. Here highlight: false.\n"
            "3. HOOK WORDS: Key emotional terms (Music, Gaming, Nonstop, Cinema, Power, লিমিটলেস) scale to 1.25x and highlight: true.\n"
            "4. COLOR STRATEGY: \n"
            "   - highlight: true (Numeric/Large) -> YELLOW\n"
            "   - highlight: true (Hook Words/Small) -> WHITE\n"
            "   - highlight: false -> Standard White\n\n"
            "## MANDATORY KEYS (One list of segments per key):\n"
            "- headline\n"
            "- subline\n"
            "- offer_badge\n\n"
            "## INPUTS:\n"
            f"- Headline: {headline}\n"
            f"- Subline: {subline}\n"
            f"- Offer: {details_str}\n"
        )
        
        user_prompt = "GENERATE STYLING JSON NOW. JSON ONLY. NO REASONING."
        
        try:
            # USE USER-SPECIFIC MODEL FOR STYLING
            target_model = "global.anthropic.claude-haiku-4-5-20251001-v1:0"
            
            response, _ = self.client.invoke_llm(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                temperature=0.0,
                max_tokens=2000, # Increased to prevent truncation
                model_id=target_model
            )

            
            # CRITICAL: Log the FULL raw response
            logger.info(f"--- [RAW LLM RESPONSE START] ---\n{response}\n--- [RAW LLM RESPONSE END] ---")

            
            # 1. Clean the response
            clean_response = self._sanitize_json(response)
            
            try:
                result = json.loads(clean_response)
                # Basic key validation
                if not isinstance(result, dict) or "headline" not in result:
                    raise ValueError("Incomplete Styling Map.")
                return result
            except (json.JSONDecodeError, ValueError) as je:
                logger.warning(f"Styling JSON parse failed. Using Regex Safety Net. Error: {je}")
                return self._fallback_tagging(offer_info)
            
        except Exception as e:
            logger.error(f"Full ad analysis failed: {e}")
            return self._fallback_tagging(offer_info)

    def _fallback_tagging(self, offer_info: Dict[str, Any]) -> Dict[str, List[Dict[str, Any]]]:
        """Safety block: Uses regex to identify numbers and units if LLM fails."""
        result = {"headline": [], "subline": [], "offer_badge": []}
        
        # BN Digits: \u09E6-\u09EF
        # Units: GB, MB, Taka, Tk, টাকা, টাকায়, দিন, days, জিবি, এমবি
        pattern = re.compile(r'([\d\u09E6-\u09EF]+(?:\s*(?:GB|MB|Taka|Tk|টাকা|টাকায়|দিন|days|জিবি|এমবি))?)', re.IGNORECASE)
        
        def segment_text(text: str, is_offer: bool = False) -> List[Dict[str, Any]]:
            if not text: return []
            segs = []
            last = 0
            for m in pattern.finditer(text) or []:
                if m.start() > last:
                    segs.append({"text": text[last:m.start()], "highlight": False, "scale": 1.0})
                
                # Digit/Unit Match
                snippet = m.group(0)
                segs.append({
                    "text": snippet, 
                    "highlight": True, 
                    "scale": 2.2 if is_offer or any(c.isdigit() or '\u09E6' <= c <= '\u09EF' for c in snippet) else 1.4
                })
                last = m.end()
            if last < len(text):
                segs.append({"text": text[last:], "highlight": False, "scale": 1.0})
            return segs

        # Robust fallback: prioritize actual content keys
        h_text = offer_info.get("headline") or offer_info.get("headline_bn", "")
        s_text = offer_info.get("subline") or offer_info.get("subline_bn", "")
        
        result["headline"] = segment_text(h_text)
        result["subline"] = segment_text(s_text)
        
        details = " | ".join(filter(None, offer_info.get("details", [])))
        result["offer_badge"] = segment_text(details, is_offer=True)
        return result



    def _sanitize_json(self, text: str) -> str:
        """The most aggressive JSON extractor possible."""
        if not text:
            return "{}"
            
        # 1. KILL THINKING BLOCKS FIRST (Regex-First approach)
        # Wipe out anything between <think> tags or reasoning blocks
        import re
        text = re.sub(r'<(think|reasoning)>.*?</\1>', '', text, flags=re.DOTALL | re.IGNORECASE)
        
        # 2. Strip markdown code fences
        text = text.replace("```json", "").replace("```", "").strip()
        
        # 3. Find first { and last } - ignore EVERYTHING outside
        start_idx = text.find('{')
        end_idx = text.rfind('}')
        
        if start_idx != -1 and end_idx != -1:
            clean_json = text[start_idx : end_idx + 1]
            return clean_json
        
        return "{}"







    # Backward compatibility stub - keep existing segment_headline
    def segment_headline(self, text: str, offer_info: Dict[str, str] = None) -> List[Dict[str, Any]]:

        """
        Segment a headline and assign highlight/scale to each segment via LLM.
        Returns a list of dicts: [{"text": "...", "highlight": bool, "scale": float}]
        """
        if not text or len(text.strip()) < 2:
            return []
            
        if text in self._cache:
            return self._cache[text]
            
        context_str = ""
        if offer_info:
            context_str = (
                f"Context: This is a '{offer_info.get('brand', 'telecom')}' offer for "
                f"{offer_info.get('data_gb', 'N/A')} data, priced at {offer_info.get('price', 'N/A')} "
                f"with {offer_info.get('validity', 'N/A')} validity.\n"
            )

        system_prompt = (
            "You are a marketing typography expert for a telecom operator in Bangladesh.\n"
            "Your task is to break a Bengali or English headline into meaningful segments for visual impact.\n\n"
            f"{context_str}"
            "STYLING RULES:\n"
            "1. IDENTIFY core offer components: Digits (e.g., 3, 59, 7, ৩, ৫৯, ৭), Data Units (GB, MB, জিবি), "
            "Price units (Tk, Taka, টাকা, টাকায়), and Validity terms (7 days, সাত দিন).\n"
            "2. For THESE core components, set 'highlight': true AND 'scale': 2.0 (MUST be exactly 2.0 for massive impact).\n"
            "3. For other semi-important keywords (e.g., 'Internet', 'Music', 'অফার'), set 'highlight': true, 'scale': 1.2.\n"
            "4. For all other filler text, set 'highlight': false, 'scale': 1.0.\n"
            "5. Ensure the 'text' fields combine to form the EXACT input headline, including all spaces and punctuation.\n\n"
            "OUTPUT FORMAT:\n"
            "Return ONLY a JSON array. Example: [{\"text\": \"৩ জিবি \", \"highlight\": true, \"scale\": 2.0}, ...]"
        )

        
        user_prompt = f"Headline: {text}"
        
        try:
            # Use a low temperature for deterministic JSON output
            response, _ = self.client.invoke_llm(
                system_prompt=system_prompt,
                user_prompt=user_prompt,
                temperature=0.1,
                max_tokens=200
            )
            
            # Clean response for JSON parsing
            clean_response = response.strip()
            
            # Robust extraction of the first [ to the last ]
            # This handles <think>, markdown, preamble, and other LLM 'chatter'
            start_idx = clean_response.find('[')
            end_idx = clean_response.rfind(']')
            
            if start_idx != -1 and end_idx != -1 and end_idx > start_idx:
                clean_response = clean_response[start_idx : end_idx + 1]
            
            # Robust empty check
            if not clean_response or clean_response == "[]":
                logger.warning(f"LLM returned empty or trivial response: {response}")
                return []
                
            try:
                segments = json.loads(clean_response)
            except json.JSONDecodeError as je:
                logger.error(f"JSON Decode Error for '{clean_response}': {je}")
                # Fallback: simple regex search if the clean_response is still messy
                return []

            
            # Basic validation
            if not isinstance(segments, list):

                logger.warning(f"LLM returned non-list for segmentation: {segments}")
                return []
                
            logger.info(f"LLM Segmented: '{text}' -> {len(segments)} segments")
            self._cache[text] = segments
            return segments
            
        except Exception as e:
            logger.error(f"Headline segmentation failed: {e}")
            return []

    # Backward compatibility stub
    def analyze(self, text: str, offer_info: Dict[str, str] = None) -> List[str]:
        """Legacy method: returns a simple list of highlight words."""
        segments = self.segment_headline(text, offer_info)
        return [s["text"].strip() for s in segments if s.get("highlight")]
