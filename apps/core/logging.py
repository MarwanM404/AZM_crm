"""Log filtering so secrets and PII never reach log output (constitution: Security & Access
Control - no secrets or PII in logs)."""

import logging
import re
from collections.abc import Mapping

SENSITIVE_KEYS = re.compile(
    r"(password|secret|token|api[_-]?key|credit[_-]?card|ssn)", re.IGNORECASE
)
REDACTED = "[REDACTED]"


class SensitiveDataFilter(logging.Filter):
    """Redacts values whose key looks sensitive, wherever the log record carries structured
    data. Applied to every configured handler in settings LOGGING.

    `record.args` is not always a plain tuple of positional values: Python's logging module
    unwraps a single-dict argument (e.g. `logger.info(fmt, {"a": 1})`) into a bare Mapping so
    that `%(key)s`-style formatting works. That shape must be preserved, not flattened into a
    tuple of the dict's keys, or every %(name)s placeholder breaks (this is exactly the shape
    Celery's own task-success logging uses).
    """

    def filter(self, record: logging.LogRecord) -> bool:
        if isinstance(record.msg, str) and SENSITIVE_KEYS.search(record.msg):
            record.msg = self._redact_line(record.msg)

        if isinstance(record.args, Mapping):
            record.args = {
                key: (REDACTED if isinstance(key, str) and SENSITIVE_KEYS.search(key) else value)
                for key, value in record.args.items()
            }
        elif record.args:
            record.args = tuple(
                REDACTED if isinstance(a, str) and SENSITIVE_KEYS.search(a) else a
                for a in record.args
            )
        return True

    @staticmethod
    def _redact_line(message: str) -> str:
        return SENSITIVE_KEYS.sub(REDACTED, message)
