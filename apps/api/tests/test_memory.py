"""Backward-compat shim — actual tests split into tests/memory/*.py.

Primary split lives in `tests/memory/` (see conftest/test_store/etc.).
This file re-exports so `pytest tests/test_memory.py` and
`from tests.test_memory import ...` keep working.
"""

# Re-export fixtures/helpers
from tests.memory.conftest import AGENT_ID, PROJECT_ID, _make_mock_db, _mock_execute_result

# Re-export test suites (pytest collects these via star-import)
from tests.memory.test_hydration import (
    test_format_memory_context_empty,
    test_format_memory_context_full,
    test_format_memory_context_with_checkpoint,
    test_format_memory_context_with_episodic_memory,
    test_format_memory_context_with_semantic_memory,
    test_format_memory_context_with_working_memory,
    test_hydrate_agent_context_builds_prompt,
    test_hydrate_agent_context_empty_when_no_memories,
)
from tests.memory.test_lifecycle import (
    test_cleanup_expired_removes_old_memories,
    test_delete_memory_removes_row,
    test_delete_memory_returns_false_for_nonexistent,
    test_load_latest_checkpoint_returns_most_recent,
    test_load_latest_checkpoint_returns_none_when_empty,
    test_save_checkpoint_creates_row,
    test_save_checkpoint_without_task_id,
)
from tests.memory.test_retrieve_search import (
    test_retrieve_memories_excludes_expired,
    test_retrieve_memories_filters_by_type,
    test_retrieve_memories_respects_limit,
    test_retrieve_memories_returns_list,
    test_search_memories_cosine_similarity,
    test_search_memories_respects_limit,
    test_search_memories_skips_none_embedding,
)
from tests.memory.test_store import (
    test_store_episodic_with_ttl,
    test_store_memory_creates_row,
    test_store_memory_invalid_type_raises,
    test_store_memory_with_embedding,
    test_store_memory_with_metadata,
    test_store_working_memory_custom_ttl,
    test_store_working_memory_has_expiry,
)
from tests.memory.test_utils import (
    test_cosine_similarity_different_lengths,
    test_cosine_similarity_identical,
    test_cosine_similarity_opposite,
    test_cosine_similarity_orthogonal,
    test_cosine_similarity_zero_vector,
)

__all__ = [
    "AGENT_ID",
    "PROJECT_ID",
    "_make_mock_db",
    "_mock_execute_result",
    "test_cleanup_expired_removes_old_memories",
    "test_cosine_similarity_different_lengths",
    "test_cosine_similarity_identical",
    "test_cosine_similarity_opposite",
    "test_cosine_similarity_orthogonal",
    "test_cosine_similarity_zero_vector",
    "test_delete_memory_removes_row",
    "test_delete_memory_returns_false_for_nonexistent",
    "test_format_memory_context_empty",
    "test_format_memory_context_full",
    "test_format_memory_context_with_checkpoint",
    "test_format_memory_context_with_episodic_memory",
    "test_format_memory_context_with_semantic_memory",
    "test_format_memory_context_with_working_memory",
    "test_hydrate_agent_context_builds_prompt",
    "test_hydrate_agent_context_empty_when_no_memories",
    "test_load_latest_checkpoint_returns_most_recent",
    "test_load_latest_checkpoint_returns_none_when_empty",
    "test_retrieve_memories_excludes_expired",
    "test_retrieve_memories_filters_by_type",
    "test_retrieve_memories_respects_limit",
    "test_retrieve_memories_returns_list",
    "test_save_checkpoint_creates_row",
    "test_save_checkpoint_without_task_id",
    "test_search_memories_cosine_similarity",
    "test_search_memories_respects_limit",
    "test_search_memories_skips_none_embedding",
    "test_store_episodic_with_ttl",
    "test_store_memory_creates_row",
    "test_store_memory_invalid_type_raises",
    "test_store_memory_with_embedding",
    "test_store_memory_with_metadata",
    "test_store_working_memory_custom_ttl",
    "test_store_working_memory_has_expiry",
]
