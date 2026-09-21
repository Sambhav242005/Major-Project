"""Agents package — re-exports for backwards compatibility."""

from .crud import create_agent, delete_agent, get_agent, list_agents, list_agent_types, update_agent
from .executor import run_agent
from .skills import MAX_SKILLS_PER_AGENT, _hydrate_skills
from .tasks import get_task, list_tasks

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
