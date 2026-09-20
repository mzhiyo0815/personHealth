import os


bind = f"0.0.0.0:{os.environ.get('PORT', '8000')}"
workers = int(os.environ.get("WEB_CONCURRENCY", "3"))
logger_class = "config.gunicorn_logger.SafeLogger"
accesslog = "-"
errorlog = "-"
access_log_format = (
    'remote="%(h)s" method="%(m)s" path="%(U)s" protocol="%(H)s" '
    'status=%(s)s bytes=%(B)s duration_us=%(D)s'
)
logconfig_dict = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "structured": {
            "()": "config.gunicorn_logger.JsonFormatter",
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "structured",
            "stream": "ext://sys.stdout",
        },
    },
    "loggers": {
        "gunicorn.error": {
            "handlers": ["console"],
            "level": "INFO",
            "propagate": False,
        },
        "gunicorn.access": {
            "handlers": ["console"],
            "level": "INFO",
            "propagate": False,
        },
    },
    "root": {"handlers": ["console"], "level": "INFO"},
}
