import logging

from apps.core.logging import SensitiveDataFilter


def test_filter_redacts_message_containing_sensitive_key():
    record = logging.LogRecord("test", logging.INFO, __file__, 1, "user password=hunter2", (), None)
    SensitiveDataFilter().filter(record)
    assert "hunter2" not in record.msg or "[REDACTED]" in record.msg
    assert "password" not in record.msg.lower() or "[REDACTED]" in record.msg


def test_filter_redacts_sensitive_positional_args():
    record = logging.LogRecord(
        "test", logging.INFO, __file__, 1, "value: %s", ("api_key=abc123",), None
    )
    SensitiveDataFilter().filter(record)
    assert record.args[0] == "[REDACTED]"


def test_filter_leaves_ordinary_messages_untouched():
    record = logging.LogRecord("test", logging.INFO, __file__, 1, "ticket created", (), None)
    SensitiveDataFilter().filter(record)
    assert record.msg == "ticket created"
