import json
import logging
import os
import subprocess
import sys


def production_settings(script):
    environment = os.environ.copy()
    environment.update(
        {
            "DJANGO_ENV": "production",
            "SECRET_KEY": "test-only-production-secret-key-with-32-characters",
            "DATABASE_URL": "sqlite:////tmp/health-production-settings.sqlite3",
            "CACHE_URL": "redis://127.0.0.1:6379/15",
            "ALLOWED_HOSTS": "health.example.com",
            "CSRF_TRUSTED_ORIGINS": "https://health.example.com",
        }
    )
    return subprocess.run(
        [sys.executable, "-c", script],
        cwd=os.getcwd(),
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )


def test_production_requires_https_and_secure_cookies():
    result = production_settings(
        "from django.conf import settings; "
        "assert settings.DEBUG is False; "
        "assert settings.SECURE_SSL_REDIRECT is True; "
        "assert settings.SESSION_COOKIE_SECURE is True; "
        "assert settings.CSRF_COOKIE_SECURE is True"
    )

    assert result.returncode == 0, result.stderr


def test_production_uses_whitenoise_and_database_health_checks():
    result = production_settings(
        "from django.conf import settings; "
        "assert 'whitenoise.middleware.WhiteNoiseMiddleware' in settings.MIDDLEWARE; "
        "assert settings.STORAGES['staticfiles']['BACKEND'].endswith('CompressedManifestStaticFilesStorage'); "
        "assert settings.DATABASES['default']['CONN_HEALTH_CHECKS'] is True; "
        "assert settings.STATIC_ROOT.name == 'staticfiles'"
    )

    assert result.returncode == 0, result.stderr


def test_production_requires_secret_key():
    environment = os.environ.copy()
    environment.update({"DJANGO_ENV": "production"})
    environment.pop("SECRET_KEY", None)

    result = subprocess.run(
        [sys.executable, "-c", "import config.settings"],
        cwd=os.getcwd(),
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode != 0
    assert "SECRET_KEY" in result.stderr


def test_production_requires_cache_url_and_fails_closed():
    environment = os.environ.copy()
    environment.update(
        {
            "DJANGO_ENV": "production",
            "SECRET_KEY": "test-only-production-secret-key-with-32-characters",
            "DATABASE_URL": "sqlite:////tmp/health-production-settings.sqlite3",
        }
    )
    environment.pop("CACHE_URL", None)

    result = subprocess.run(
        [sys.executable, "-c", "import config.settings"],
        cwd=os.getcwd(),
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode != 0
    assert "CACHE_URL" in result.stderr

    configured = production_settings(
        "from django.conf import settings; "
        "assert settings.RATELIMIT_FAIL_OPEN is False"
    )
    assert configured.returncode == 0, configured.stderr


def test_gunicorn_logs_are_structured_without_sensitive_headers():
    config = (os.path.join(os.getcwd(), "gunicorn.conf.py"))
    assert os.path.exists(config)
    content = open(config, encoding="utf-8").read()

    assert "logconfig_dict" in content
    assert "access_log_format" in content
    assert "%(U)s" in content
    assert "%(q)s" not in content
    assert "authorization" not in content.lower()
    assert "cookie" not in content.lower()
    assert 'logger_class = "config.gunicorn_logger.SafeLogger"' in content


def test_access_log_path_escapes_log_injection_characters():
    from config.gunicorn_logger import JsonFormatter, sanitize_log_value

    malicious_path = '/bad"\r\nfake=entry'
    rendered = f'path="{sanitize_log_value(malicious_path)}"'

    assert "\r" not in rendered
    assert "\n" not in rendered
    assert rendered == 'path="/bad\\"\\u000d\\u000afake=entry"'

    record = logging.LogRecord(
        "gunicorn.access", logging.INFO, "", 0, rendered, (), None
    )
    payload = json.loads(JsonFormatter().format(record))
    assert payload["message"] == rendered


def test_login_post_logs_do_not_include_secrets(client, caplog, settings, db):
    settings.RATELIMIT_USE_CACHE = "test"
    password = "private-login-password"

    response = client.post(
        "/accounts/login/",
        {"phone": "13800138000", "password": password},
        HTTP_AUTHORIZATION="Bearer private-auth-token",
        HTTP_COOKIE="sessionid=private-session-cookie",
    )

    assert response.status_code == 200
    log_output = caplog.text.lower()
    assert password not in log_output
    assert "private-auth-token" not in log_output
    assert "private-session-cookie" not in log_output
