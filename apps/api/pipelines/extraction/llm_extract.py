"""LLM-based entity and relationship extraction."""

import json
import logging

from core.config import settings

logger = logging.getLogger(__name__)

EXTRACT_PROMPT = """You are an entity and relationship extractor. Given a text passage, extract:

1. **Entities**: People, organizations, concepts, locations, dates mentioned in the text.
2. **Relationships**: Connections between extracted entities (e.g., "works_at", "located_in", "mentions").

Return ONLY valid JSON in this format:
{{
  "entities": [
    {{"name": "Entity Name", "type": "person|organization|concept|location|date", "description": "Brief description"}}
  ],
  "relationships": [
    {{"source": "Entity A Name", "target": "Entity B Name", "relation_type": "relationship_name", "description": "Brief description"}}
  ]
}}

Rules:
- Only extract entities that appear in the text
- Keep entity names consistent (use the full name, not abbreviations)
- Relationships must reference two entities from the entities list
- type must be one of: person, organization, concept, location, date
- Be precise — do not hallucinate entities or relationships not in the text

Text:
{text}"""


async def _llm_extract(text: str) -> dict:
    """Call LLM to extract entities and relationships from text.

    Returns {"entities": [...], "relationships": [...]}. On any failure
    returns empty lists — the caller falls back to co-occurrence edges so
    the graph stays connected even if the LLM errors out.
    """
    prompt = EXTRACT_PROMPT.format(text=text[:8000])
    messages = [
        {"role": "system", "content": "You are an expert entity extractor. Output only valid JSON."},
        {"role": "user", "content": prompt},
    ]
    try:
        # Resolve chat_completion via shim to honor test patches on
        # pipelines.entity_extraction.chat_completion
        try:
            from pipelines.entity_extraction import chat_completion as _chat
        except Exception:
            from pipelines.llm_client import chat_completion as _chat
        response = await _chat(
            messages=messages,
            model=settings.LLM_EXTRACT_MODEL,
            temperature=0.1,
            max_tokens=2000,
        )
        return _parse_llm_response(response)
    except Exception as e:
        logger.warning(f"LLM extraction failed (falling back to co-occurrence): {e}")
        return {"entities": [], "relationships": []}


def _parse_llm_response(response: str) -> dict:
    """Parse LLM JSON response defensively — strip code fences/markdown."""
    text = response.strip()
    if text.startswith("```"):
        text = text.split("```")[1] if "```" in text[3:] else text
        text = text.strip()
        if text.startswith("json"):
            text = text[4:].strip()
    try:
        result = json.loads(text)
    except json.JSONDecodeError:
        start = text.find("{")
        end = text.rfind("}")
        if start != -1 and end > start:
            try:
                result = json.loads(text[start: end + 1])
            except json.JSONDecodeError:
                logger.warning("LLM returned unparseable JSON")
                return {"entities": [], "relationships": []}
        else:
            logger.warning("LLM returned no JSON object")
            return {"entities": [], "relationships": []}
    return {
        "entities": result.get("entities", []),
        "relationships": result.get("relationships", []),
    }
