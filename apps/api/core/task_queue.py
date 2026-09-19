"""Shim for backward compatibility — re-exports from core.task_queue package."""

try:
    from core.task_queue.pubsub import (  # noqa: F401
        MAX_EVENTS_PER_TASK,
        _drop_task_events,
        _publish_event,
        _running_tasks,
        _task_events,
        _task_subscribers,
        subscribe_task,
        unsubscribe_task,
    )
    from core.task_queue.executor import start_agent_task  # noqa: F401
except Exception:  # pragma: no cover
    pass

__all__ = [
    "MAX_EVENTS_PER_TASK",
    "_drop_task_events",
    "_publish_event",
    "_running_tasks",
    "_task_events",
    "_task_subscribers",
    "start_agent_task",
    "subscribe_task",
    "unsubscribe_task",
]
