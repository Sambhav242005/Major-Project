"""Re-export shim — backwards compat for `from services.chat import ...`.

Delegates to services.chat package (services/chat/__init__.py).
"""

from services.chat.prompt import SYSTEM_PROMPT, build_entity_context, build_messages, build_user_prompt
from services.chat.retrieval import _expand_via_graph, _format_source_block, _get_entity_context
from services.chat.sessions import create_session, get_session, list_sessions
from services.chat.streaming import send_message

__all__ = [
    "create_session",
    "get_session",
    "list_sessions",
    "_get_entity_context",
    "_expand_via_graph",
    "_format_source_block",
    "SYSTEM_PROMPT",
    "build_entity_context",
    "build_user_prompt",
    "build_messages",
    "send_message",
]
