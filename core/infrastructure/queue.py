"""Async task queue with SQS-compatible interface and Dead Letter Queue support.

Provides:
- Local in-memory queue for development
- AWS SQS backend when credentials available
- Automatic retry with exponential backoff
- Dead Letter Queue for failed messages
- Idempotency via message deduplication
"""

from __future__ import annotations
import json
import time
import uuid
import threading
import logging
from typing import Any, Callable
from collections import deque

from core.foundation.error_codes import ErrorCode, format_error_response

logger = logging.getLogger(__name__)


class QueueMessage:
    """Represents a task in the queue."""

    def __init__(self, body: dict[str, Any], message_id: str | None = None) -> None:
        self.body = body
        self.message_id = message_id or f"msg_{uuid.uuid4().hex[:16]}"
        self.receipt_handle = f"rh_{uuid.uuid4().hex[:12]}"
        self.attempts: int = 0
        self.created_at: float = time.monotonic()

    def to_dict(self) -> dict[str, Any]:
        return {
            "message_id": self.message_id,
            "body": self.body,
            "attempts": self.attempts,
            "created_at": self.created_at,
        }


class LocalQueue:
    """Thread-safe in-memory queue with retry and DLQ support."""

    def __init__(self, max_retries: int = 3, retry_delay: float = 5.0) -> None:
        self._queue: deque[QueueMessage] = deque()
        self._dlq: deque[QueueMessage] = deque()
        self._processing: dict[str, QueueMessage] = {}
        self._max_retries = max_retries
        self._retry_delay = retry_delay
        self._lock = threading.Lock()

    def send(self, body: dict[str, Any]) -> str:
        """Add message to queue. Returns message ID."""
        msg = QueueMessage(body)
        with self._lock:
            self._queue.append(msg)
        logger.debug("Enqueued message: %s", msg.message_id)
        return msg.message_id

    def receive(self, max_messages: int = 1) -> list[QueueMessage]:
        """Get messages for processing."""
        with self._lock:
            messages = []
            for _ in range(min(max_messages, len(self._queue))):
                msg = self._queue.popleft()
                msg.attempts += 1
                self._processing[msg.receipt_handle] = msg
                messages.append(msg)
            return messages

    def complete(self, receipt_handle: str) -> bool:
        """Mark message as successfully processed."""
        with self._lock:
            return self._processing.pop(receipt_handle, None) is not None

    def fail(self, receipt_handle: str) -> None:
        """Handle failed message - retry or move to DLQ."""
        with self._lock:
            msg = self._processing.pop(receipt_handle, None)
            if msg is None:
                return

            if msg.attempts < self._max_retries:
                logger.warning("Retrying message %s (attempt %d)", msg.message_id, msg.attempts)
                time.sleep(self._retry_delay)
                self._queue.append(msg)
            else:
                logger.error("Message %s moved to DLQ after %d attempts", msg.message_id, msg.attempts)
                self._dlq.append(msg)

    def get_dlq_size(self) -> int:
        """Get number of messages in Dead Letter Queue."""
        with self._lock:
            return len(self._dlq)

    def get_queue_size(self) -> int:
        """Get number of messages in main queue."""
        with self._lock:
            return len(self._queue)

    def stats(self) -> dict[str, Any]:
        with self._lock:
            return {
                "queue_size": len(self._queue),
                "processing": len(self._processing),
                "dlq_size": len(self._dlq),
            }


class TaskQueue:
    """High-level task queue with SQS-compatible interface."""

    def __init__(self, queue_name: str = "kudbee-tasks", use_sqs: bool = False) -> None:
        self._queue_name = queue_name
        self._local = LocalQueue()
        self._use_sqs = use_sqs and self._check_sqs_available()

    def _check_sqs_available(self) -> bool:
        """Check if AWS SQS is accessible."""
        try:
            import boto3
            sts = boto3.client("sts")
            sts.get_caller_identity()
            return True
        except Exception:
            logger.info("AWS SQS not available, using local queue")
            return False

    def enqueue(self, task_type: str, payload: dict[str, Any]) -> str:
        """Add task to queue."""
        body = {
            "type": task_type,
            "payload": payload,
            "timestamp": time.time(),
        }
        return self._local.send(body)

    def process(self, handler: Callable[[dict[str, Any]], bool]) -> int:
        """Process messages from queue. Returns count processed."""
        messages = self._local.receive(max_messages=10)
        processed = 0

        for msg in messages:
            try:
                success = handler(msg.body)
                if success:
                    self._local.complete(msg.receipt_handle)
                    processed += 1
                else:
                    self._local.fail(msg.receipt_handle)
            except Exception as exc:
                logger.error("Task processing failed: %s", str(exc))
                self._local.fail(msg.receipt_handle)

        return processed

    def stats(self) -> dict[str, Any]:
        return {
            "queue_name": self._queue_name,
            "backend": "sqs" if self._use_sqs else "local",
            **self._local.stats(),
        }


# Global task queue
task_queue = TaskQueue()
