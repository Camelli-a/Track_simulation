from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from app.communication.message_bus import MessageBus

logger = logging.getLogger(__name__)

_bus: Optional[MessageBus] = None


def get_message_bus() -> MessageBus:
    """Return a lazily started MessageBus publisher for backend-originated messages."""

    global _bus
    if _bus is None:
        _bus = MessageBus()
        _bus.start()
    return _bus


def publish_module_message(topic: str, data: Dict[str, Any]) -> bool:
    """Publish a message to the ZMQ module bus.

    Returns False instead of raising so REST endpoints can still acknowledge the
    command locally when the broker is not running during frontend-only demos.
    """

    try:
        get_message_bus().publish(topic, data)
    except Exception:
        logger.exception("Failed to publish module message %s", topic)
        return False
    return True
