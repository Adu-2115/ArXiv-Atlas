"""
Structured logging setup.

Emits one JSON object per log line — easy to grep, easy to pipe into a log
aggregator later (Datadog, CloudWatch, etc.) without changing application
code, and still readable directly in a terminal during local development.

Usage elsewhere in the app:
    import logging
    logger = logging.getLogger(__name__)
    logger.info("stage completed", extra={"stage": "find_papers", "duration_ms": 120})
"""
import json
import logging
import sys
import time


class JsonFormatter(logging.Formatter):
    # Standard LogRecord attributes we don't want duplicated under "extra"
    # in the output, since they're already surfaced as top-level fields.
    _RESERVED = {
        "name", "msg", "args", "levelname", "levelno", "pathname", "filename",
        "module", "exc_info", "exc_text", "stack_info", "lineno", "funcName",
        "created", "msecs", "relativeCreated", "thread", "threadName",
        "processName", "process", "message", "asctime", "taskName",
    }

    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "timestamp": time.strftime(
                "%Y-%m-%dT%H:%M:%S", time.localtime(record.created)
            ),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        # Anything passed via logger.info(..., extra={...}) shows up as
        # extra attributes on the record — surface those too.
        for key, value in record.__dict__.items():
            if key not in self._RESERVED and not key.startswith("_"):
                try:
                    json.dumps(value)  # only include JSON-serializable extras
                    payload[key] = value
                except (TypeError, ValueError):
                    payload[key] = str(value)

        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)

        return json.dumps(payload)


def configure_logging(level: int = logging.INFO) -> None:
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())

    root = logging.getLogger()
    root.setLevel(level)
    root.handlers = [handler]  # replace any default handlers (avoid duplicate lines)

    # Quiet down noisy third-party loggers so app logs aren't drowned out.
    for noisy in ("httpx", "httpcore", "urllib3"):
        logging.getLogger(noisy).setLevel(logging.WARNING)
