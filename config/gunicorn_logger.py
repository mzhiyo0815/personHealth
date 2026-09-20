import json
import logging

from gunicorn.glogging import Logger


def sanitize_log_value(value):
    escaped = []
    for character in str(value):
        codepoint = ord(character)
        if character == "\\":
            escaped.append("\\\\")
        elif character == '"':
            escaped.append('\\"')
        elif codepoint < 32 or codepoint == 127 or character in {"\u2028", "\u2029"}:
            escaped.append(f"\\u{codepoint:04x}")
        else:
            escaped.append(character)
    return "".join(escaped)


class JsonFormatter(logging.Formatter):
    def format(self, record):
        payload = {
            "timestamp": self.formatTime(record, "%Y-%m-%dT%H:%M:%S%z"),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False)


class SafeLogger(Logger):
    def atoms(self, resp, req, environ, request_time):
        return {
            key: sanitize_log_value(value) if isinstance(value, str) else value
            for key, value in super().atoms(resp, req, environ, request_time).items()
        }
