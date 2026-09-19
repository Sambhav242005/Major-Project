"""Re-export shim — backwards compat for `from services.agents import ...`.

Delegates to services.agents package (services/agents/__init__.py).
Kept as thin wrapper so existing imports keep working; package takes precedence.
"""

from services.agents.crud import create_agent, delete_agent, get_agent, list_agents, list_agent_types, update_agent
from services.agents.executor import run_agent
from services.agents.skills import MAX_SKILLS_PER_AGENT, _hydrate_skills
from services.agents.tasks import get_task, list_tasks

__all__ = [
    "list_agents",
    "get_agent",
    "create_agent",
    "update_agent",
    "delete_agent",
    "run_agent",
    "get_task",
    "list_tasks",
    "list_agent_types",
    "_hydrate_skills",
    "MAX_SKILLS_PER_AGENT",
]
