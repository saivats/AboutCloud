"""
Structured Logging Configuration

JSON-formatted logging with tenant IDs, request IDs, and timing context.
"""

import logging
import json
import time
import uuid
from typing import Dict, Optional, Any
from datetime import datetime
from dataclasses import dataclass, field


class JSONFormatter(logging.Formatter):
    """
    JSON log formatter for structured logging.

    Output format:
    {"timestamp": "...", "level": "...", "message": "...", "tenant_id": "...", ...}
    """

    def format(self, record: logging.LogRecord) -> str:
        log_entry = {
            "timestamp": datetime.utcnow().isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }

        # Add extra fields
        if hasattr(record, "tenant_id"):
            log_entry["tenant_id"] = record.tenant_id
        if hasattr(record, "request_id"):
            log_entry["request_id"] = record.request_id
        if hasattr(record, "duration_ms"):
            log_entry["duration_ms"] = record.duration_ms

        # Merge any extra dict
        for key, value in getattr(record, "__dict__", {}).items():
            if key not in (
                "name", "msg", "args", "created", "filename", "funcName",
                "levelname", "levelno", "lineno", "module", "msecs",
                "pathname", "process", "processName", "relativeCreated",
                "stack_info", "thread", "threadName", "exc_info", "exc_text",
                "message", "taskName",
            ):
                log_entry[key] = value

        return json.dumps(log_entry, default=str)


def get_logger(name: str = "aboutcloud") -> logging.Logger:
    """
    Get a configured logger with JSON formatting.

    Args:
        name: Logger name

    Returns:
        Configured logger instance
    """
    logger = logging.getLogger(f"aboutcloud.{name}")

    if not logger.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(JSONFormatter())
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)

    return logger


def log_request(
    logger: logging.Logger,
    endpoint: str,
    tenant_id: str,
    extra: Optional[Dict[str, Any]] = None,
) -> str:
    """
    Log an API request with a generated request ID.

    Args:
        logger: Logger instance
        endpoint: API endpoint being called
        tenant_id: Tenant making the request
        extra: Additional context

    Returns:
        Generated request_id
    """
    request_id = str(uuid.uuid4())[:8]

    logger.info(
        f"Request: {endpoint}",
        extra={
            "request_id": request_id,
            "tenant_id": tenant_id,
            **(extra or {}),
        },
    )

    return request_id


@dataclass
class PipelineMetrics:
    """
    Operational metrics for the pipeline.

    Tracks ingestion rate, detection latency, error rate, and query latency.
    """
    ingestion_count: int = 0
    detection_count: int = 0
    query_count: int = 0
    error_count: int = 0

    ingestion_total_ms: float = 0.0
    detection_total_ms: float = 0.0
    query_total_ms: float = 0.0

    _start_times: Dict[str, float] = field(default_factory=dict)

    def start_timer(self, operation: str) -> str:
        """Start a timer for an operation. Returns timer_id."""
        timer_id = f"{operation}_{uuid.uuid4().hex[:8]}"
        self._start_times[timer_id] = time.perf_counter()
        return timer_id

    def stop_timer(self, timer_id: str) -> float:
        """Stop a timer and record the duration. Returns duration_ms."""
        start = self._start_times.pop(timer_id, None)
        if start is None:
            return 0.0

        duration_ms = (time.perf_counter() - start) * 1000.0

        if timer_id.startswith("ingestion"):
            self.ingestion_count += 1
            self.ingestion_total_ms += duration_ms
        elif timer_id.startswith("detection"):
            self.detection_count += 1
            self.detection_total_ms += duration_ms
        elif timer_id.startswith("query"):
            self.query_count += 1
            self.query_total_ms += duration_ms

        return duration_ms

    def record_error(self):
        """Record an error."""
        self.error_count += 1

    @property
    def avg_ingestion_ms(self) -> float:
        return self.ingestion_total_ms / self.ingestion_count if self.ingestion_count else 0.0

    @property
    def avg_detection_ms(self) -> float:
        return self.detection_total_ms / self.detection_count if self.detection_count else 0.0

    @property
    def avg_query_ms(self) -> float:
        return self.query_total_ms / self.query_count if self.query_count else 0.0

    @property
    def error_rate(self) -> float:
        total = self.ingestion_count + self.detection_count + self.query_count
        return self.error_count / total if total else 0.0

    def summary(self) -> Dict:
        """Get metrics summary."""
        return {
            "ingestion_count": self.ingestion_count,
            "detection_count": self.detection_count,
            "query_count": self.query_count,
            "error_count": self.error_count,
            "avg_ingestion_ms": round(self.avg_ingestion_ms, 2),
            "avg_detection_ms": round(self.avg_detection_ms, 2),
            "avg_query_ms": round(self.avg_query_ms, 2),
            "error_rate": round(self.error_rate, 4),
        }


# Global pipeline metrics
_pipeline_metrics = PipelineMetrics()


def get_pipeline_metrics() -> PipelineMetrics:
    """Get the global pipeline metrics instance."""
    return _pipeline_metrics
