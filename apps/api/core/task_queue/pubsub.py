"""In-memory SSE pub/sub for task events."""

import asyncio
from collections import deque

# In-memory task status tracker (for SSE streams)
# Events per task are capped to bound memory; subscriber lists are cleaned
# on stream close and dropped on task completion.
_task_events: dict[str, deque] = {}
_task_subscribers: dict[str, list[asyncio.Queue]] = {}

# Strong references to running background tasks so the event loop never
# garbage-collects a task mid-run ("Task was destroyed but it is pending").
_running_tasks: set[asyncio.Task] = set()

MAX_EVENTS_PER_TASK = 200


def _publish_event(task_id: str, event: dict):
    """Publish a trace event to all SSE subscribers of this task."""
    if task_id not in _task_events:
        _task_events[task_id] = deque(maxlen=MAX_EVENTS_PER_TASK)
    _task_events[task_id].append(event)

    if task_id in _task_subscribers:
        dead = []
        for q in _task_subscribers[task_id]:
            try:
                q.put_nowait(event)
            except asyncio.QueueFull:
                dead.append(q)
        for q in dead:
            _task_subscribers[task_id].remove(q)


def _drop_task_events(task_id: str):
    """Release the event buffer + subscribers for a finished task."""
    _task_events.pop(task_id, None)
    _task_subscribers.pop(task_id, None)


def subscribe_task(task_id: str) -> asyncio.Queue:
    """Subscribe to live events for a task. Returns an asyncio.Queue."""
    q: asyncio.Queue = asyncio.Queue(maxsize=100)
    if task_id not in _task_subscribers:
        _task_subscribers[task_id] = []
    _task_subscribers[task_id].append(q)
    for event in _task_events.get(task_id, []):
        try:
            q.put_nowait(event)
        except asyncio.QueueFull:
            break
    return q


def unsubscribe_task(task_id: str, q: asyncio.Queue):
    """Remove an SSE subscriber."""
    if task_id in _task_subscribers:
        _task_subscribers[task_id] = [x for x in _task_subscribers[task_id] if x is not q]
