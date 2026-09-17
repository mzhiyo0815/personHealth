import pytest
from django.core.cache import caches


@pytest.fixture(autouse=True)
def use_isolated_rate_limit_cache(settings):
    settings.RATELIMIT_USE_CACHE = "test"
    cache = caches["test"]
    cache.clear()
    yield
    cache.clear()
