import json
import logging
import os
import uuid
from contextvars import ContextVar, Token
from datetime import datetime, timezone
from typing import Any

_request_id_ctx: ContextVar[str] = ContextVar("request_id", default="-")

_LOG_RECORD_STANDARD_ATTRS = {
    "args",
    "asctime",
    "created",
    "exc_info",
    "exc_text",
    "filename",
    "funcName",
    "levelname",
    "levelno",
    "lineno",
    "module",
    "msecs",
    "message",
    "msg",
    "name",
    "pathname",
    "process",
    "processName",
    "relativeCreated",
    "stack_info",
    "thread",
    "threadName",
}


def generate_request_id() -> str:
    return uuid.uuid4().hex


def get_request_id() -> str:
    return _request_id_ctx.get()


def set_request_id(request_id: str) -> Token:
    return _request_id_ctx.set(request_id)


def reset_request_id(token: Token) -> None:
    _request_id_ctx.reset(token)


class JsonLogFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "request_id": get_request_id(),
        }

        for key, value in record.__dict__.items():
            if key in _LOG_RECORD_STANDARD_ATTRS:
                continue
            if isinstance(value, (str, int, float, bool)) or value is None:
                payload[key] = value
            else:
                payload[key] = str(value)

        if record.exc_info:
            payload["exc_info"] = self.formatException(record.exc_info)

        return json.dumps(payload, ensure_ascii=True)


def configure_logging() -> None:
    level = os.getenv("LOG_LEVEL", "INFO").upper()
    root_logger = logging.getLogger()
    root_logger.setLevel(level)

    if root_logger.handlers:
        for handler in root_logger.handlers:
            handler.setFormatter(JsonLogFormatter())
            handler.setLevel(level)
        return

    handler = logging.StreamHandler()
    handler.setLevel(level)
    handler.setFormatter(JsonLogFormatter())
    root_logger.addHandler(handler)
