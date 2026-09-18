import pytest
from django.contrib.auth import get_user_model


@pytest.fixture
def user(db):
    return get_user_model().objects.create_user(
        phone="13800138000", password="safe-pass-123"
    )


@pytest.fixture
def other_user(db):
    return get_user_model().objects.create_user(
        phone="13900139000", password="safe-pass-123"
    )
