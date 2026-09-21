"""Tool registry and execution dispatch."""

import json
import logging

logger = logging.getLogger(__name__)

# Tool registry: name -> {name, description, parameters, function}
TOOL_REGISTRY: dict[str, dict] = {}


def register_tool(name: str, description: str, parameters: dict):
    """Decorator to register a tool for agent use."""
    def decorator(func):
        TOOL_REGISTRY[name] = {
            "name": name,
            "description": description,
            "parameters": parameters,
            "function": func,
        }
        return func
    return decorator


async def execute_tool(
    tool_name: str,
    arguments: dict,
    project_id: str = "",
    db=None,
) -> str:
    """Execute a registered tool by name."""
    if tool_name not in TOOL_REGISTRY:
        return json.dumps({"error": f"Unknown tool: {tool_name}"})

    tool = TOOL_REGISTRY[tool_name]
    func = tool["function"]

    reserved = {"project_id", "db"}
    clean_args = {k: v for k, v in (arguments or {}).items() if k not in reserved}

    try:
        result = await func(
            project_id=project_id,
            db=db,
            **clean_args,
        )
        return result
    except Exception as e:
        logger.error(f"Tool execution failed: {tool_name}: {e}")
        return json.dumps({"error": f"Tool {tool_name} failed to execute. Try a different query or argument."})


def get_tool_schemas() -> list[dict]:
    """Get OpenAI-style tool schemas for all registered tools."""
    schemas = []
    for name, tool in TOOL_REGISTRY.items():
        schemas.append({
            "type": "function",
            "function": {
                "name": name,
                "description": tool["description"],
                "parameters": tool["parameters"],
            },
        })
    return schemas
