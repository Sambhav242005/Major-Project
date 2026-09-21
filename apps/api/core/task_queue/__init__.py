"""Task queue package — re-exports for backward compatibility."""

from .executor import start_agent_task
from .pubsub import (
    MAX_EVENTS_PER_TASK,
    _drop_task_events,
    _publish_event,
    _running_tasks,
    _task_events,
    _task_subscribers,
    subscribe_task,
    unsubscribe_task,
)

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
