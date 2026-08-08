"""Agent pipeline — lightweight LangGraph-style agent execution with traces."""

import json
import logging
import time
from datetime import datetime
from typing import Any, AsyncGenerator

from pipelines.llm_client import chat_completion_stream, chat_completion
from core.security_utils import sanitize_for_llm, detect_injection

logger = logging.getLogger(__name__)

# Agent type definitions
AGENT_TYPES = {
    "summarizer": {
        "name": "Document Summarizer",
        "description": "Summarizes documents and extracts key points",
        "system_prompt": (
            "You are a document summarizer. Given a document or chunk of text, "
            "provide a concise summary highlighting the key points, entities, "
            "and relationships mentioned. Be factual and precise."
        ),
    },
    "extractor": {
        "name": "Entity Extractor",
        "description": "Extracts entities and relationships from text",
        "system_prompt": (
            "You are an entity extraction specialist. Given text, extract all "
            "named entities (people, organizations, locations, concepts, events) "
            "and the relationships between them. Format as JSON with entities "
            "and relationships arrays."
        ),
    },
    "qa": {
        "name": "Q&A Agent",
        "description": "Answers questions based on the knowledge base",
        "system_prompt": (
            "You are a knowledge base Q&A agent. Answer questions using only "
            "the provided context. If the context doesn't contain enough "
            "information, say so. Cite your sources when possible."
        ),
    },
    "reviewer": {
        "name": "Content Reviewer",
        "description": "Reviews and quality-scores content",
        "system_prompt": (
            "You are a content quality reviewer. Analyze the given text for "
            "accuracy, completeness, and clarity. Provide a quality score "
            "(1-10) and specific feedback on what could be improved."
        ),
    },
}


def get_agent_type_info(agent_type: str) -> dict:
    """Get info about an agent type."""
    return AGENT_TYPES.get(agent_type, {
        "name": agent_type,
        "description": f"Custom agent type: {agent_type}",
        "system_prompt": f"You are a {agent_type} agent. Process the input and provide useful output.",
    })


async def execute_agent(
    agent_type: str,
    config: dict,
    input_data: dict,
) -> AsyncGenerator[dict, None]:
    """Execute an agent and yield trace events.

    Yields dicts with:
      - step: current step name
      - status: "running" | "completed" | "error"
      - output: step output (if completed)
      - error: error message (if error)
    """
    type_info = get_agent_type_info(agent_type)
    system_prompt = config.get("system_prompt", type_info["system_prompt"])

    # Sanitize input (check only user-provided data, not memory context)
    clean_input = {k: v for k, v in input_data.items() if not k.startswith("_")}
    user_input = sanitize_for_llm(json.dumps(clean_input, default=str))

    if detect_injection(user_input):
        logger.warning(f"Prompt injection attempt blocked in agent {agent_type}")
        yield {
            "step": "initialize",
            "status": "error",
            "error": "Input rejected: potential prompt injection detected",
            "timestamp": datetime.utcnow().isoformat(),
        }
        return

    start_time = time.time()

    # Step 1: Initialize
    yield {
        "step": "initialize",
        "status": "running",
        "timestamp": datetime.utcnow().isoformat(),
    }

    # Step 2: Build prompt
    messages = [
        {"role": "system", "content": system_prompt},
    ]

    # Inject memory context if present (from memory hydration)
    memory_context = input_data.get("_memory_context")
    if memory_context:
        messages.append({
            "role": "system",
            "content": (
                "You have the following memory from past interactions. "
                "Use it to inform your response, but do not repeat it back to the user.\n\n"
                f"{memory_context}"
            ),
        })

    # Add context if provided
    if "context" in input_data:
        messages.append({
            "role": "system",
            "content": f"Additional context:\n{input_data['context']}",
        })

    # Add user message
    messages.append({"role": "user", "content": user_input})

    yield {
        "step": "prompt_built",
        "status": "completed",
        "output": f"Messages prepared: {len(messages)} messages",
        "timestamp": datetime.utcnow().isoformat(),
    }

    # Step 3: Execute LLM
    yield {
        "step": "llm_execution",
        "status": "running",
        "timestamp": datetime.utcnow().isoformat(),
    }

    try:
        # Use chat_completion for non-streaming (simpler for agents)
        full_response = ""
        async for chunk in chat_completion_stream(messages, model=config.get("model")):
            if isinstance(chunk, dict) and "content" in chunk:
                full_response += chunk["content"]
            elif isinstance(chunk, str):
                full_response += chunk

        elapsed = time.time() - start_time

        yield {
            "step": "llm_execution",
            "status": "completed",
            "output": full_response,
            "elapsed_seconds": round(elapsed, 2),
            "timestamp": datetime.utcnow().isoformat(),
        }

    except Exception as e:
        logger.error(f"Agent LLM execution failed: {e}")
        yield {
            "step": "llm_execution",
            "status": "error",
            "error": str(e),
            "timestamp": datetime.utcnow().isoformat(),
        }
        return

    # Step 4: Post-process (parse JSON if extractor type)
    yield {
        "step": "post_process",
        "status": "running",
        "timestamp": datetime.utcnow().isoformat(),
    }

    result = {"response": full_response}

    if agent_type == "extractor":
        # Try to parse JSON from response
        try:
            # Find JSON in response
            start = full_response.find("{")
            end = full_response.rfind("}") + 1
            if start >= 0 and end > start:
                parsed = json.loads(full_response[start:end])
                result["entities"] = parsed.get("entities", [])
                result["relationships"] = parsed.get("relationships", [])
        except json.JSONDecodeError:
            result["parse_error"] = "Could not parse JSON from response"

    elif agent_type == "reviewer":
        # Try to extract score
        try:
            start = full_response.find("Score:")
            if start < 0:
                start = full_response.find("score:")
            if start >= 0:
                score_text = full_response[start:start+50]
                score_num = "".join(c for c in score_text.split()[1] if c.isdigit())
                result["score"] = int(score_num) if score_num else None
        except (IndexError, ValueError):
            result["score"] = None

    yield {
        "step": "post_process",
        "status": "completed",
        "output": result,
        "total_elapsed_seconds": round(time.time() - start_time, 2),
        "timestamp": datetime.utcnow().isoformat(),
    }
