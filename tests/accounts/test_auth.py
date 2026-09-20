import pytest
from django.contrib import admin
from django.contrib.auth import get_user_model
from django.urls import reverse

from accounts.forms import PhoneAuthenticationForm, RegistrationForm


@pytest.mark.django_db
def test_phone_registration_hashes_password(client):
    response = client.post(
        "/accounts/register/",
        {
            "phone": "13800138000",
            "password1": "safe-pass-123",
            "password2": "safe-pass-123",
        },
    )

    assert response.status_code == 302
    user = get_user_model().objects.get(phone="13800138000")
    assert user.check_password("safe-pass-123")
    assert user.password != "safe-pass-123"


@pytest.mark.django_db
def test_password_shorter_than_eight_is_rejected(client):
    response = client.post(
        "/accounts/register/",
        {
            "phone": "13800138000",
            "password1": "1234567",
            "password2": "1234567",
        },
    )

    assert response.status_code == 200
    assert "至少 8 位" in response.content.decode()


def test_registration_explains_phone_is_not_verified(client):
    response = client.get("/accounts/register/")

    assert response.status_code == 200
    assert "手机号不会经过短信验证，仅作为登录账号标识" in response.content.decode()


def test_account_forms_use_chinese_password_labels():
    registration = RegistrationForm()
    login = PhoneAuthenticationForm()

    assert registration.fields["password1"].label == "密码"
    assert registration.fields["password2"].label == "确认密码"
    assert "至少 8 位" in registration.fields["password1"].help_text
    assert login.fields["password"].label == "密码"


@pytest.mark.django_db
def test_registration_normalizes_phone_before_uniqueness_check(client):
    get_user_model().objects.create_user(
        phone="13800138000", password="safe-pass-123"
    )

    response = client.post(
        "/accounts/register/",
        {
            "phone": "138-0013-8000",
            "password1": "another-pass-123",
            "password2": "another-pass-123",
        },
    )

    assert response.status_code == 200
    assert get_user_model().objects.count() == 1
    assert "已存在" in response.content.decode()


@pytest.mark.django_db
def test_registration_rejects_non_phone_identifier(client):
    response = client.post(
        "/accounts/register/",
        {
            "phone": "not-a-phone",
            "password1": "safe-pass-123",
            "password2": "safe-pass-123",
        },
    )

    assert response.status_code == 200
    assert not get_user_model().objects.exists()
    assert "有效的手机号" in response.content.decode()


@pytest.mark.django_db
def test_registration_accepts_plus_and_twenty_digits(client):
    phone = "+" + "1" * 20

    response = client.post(
        "/accounts/register/",
        {
            "phone": phone,
            "password1": "safe-pass-123",
            "password2": "safe-pass-123",
        },
    )

    assert response.status_code == 302
    assert get_user_model().objects.filter(phone=phone).exists()


@pytest.mark.django_db
def test_user_can_log_in_with_phone_and_password(client):
    user = get_user_model().objects.create_user(
        phone="13800138000", password="safe-pass-123"
    )

    response = client.post(
        "/accounts/login/",
        {"username": user.phone, "password": "safe-pass-123"},
    )

    assert response.status_code == 302
    assert client.session["_auth_user_id"] == str(user.pk)


@pytest.mark.django_db
def test_login_error_does_not_reveal_whether_phone_exists(client):
    get_user_model().objects.create_user(
        phone="13800138000", password="safe-pass-123"
    )

    unknown_response = client.post(
        "/accounts/login/",
        {"username": "13900139000", "password": "wrong-pass"},
    )
    wrong_password_response = client.post(
        "/accounts/login/",
        {"username": "13800138000", "password": "wrong-pass"},
    )

    generic_error = "手机号或密码不正确，请重试。"
    assert generic_error in unknown_response.content.decode()
    assert generic_error in wrong_password_response.content.decode()


@pytest.mark.django_db
def test_logout_post_clears_authenticated_session(client):
    user = get_user_model().objects.create_user(
        phone="13800138000", password="safe-pass-123"
    )
    client.force_login(user)

    response = client.post("/accounts/logout/")

    assert response.status_code == 302
    assert "_auth_user_id" not in client.session


@pytest.mark.django_db
def test_sixth_login_attempt_is_rate_limited(client):
    for _ in range(5):
        response = client.post(
            "/accounts/login/",
            {"username": "13800138000", "password": "wrong-pass"},
        )
        assert response.status_code == 200

    response = client.post(
        "/accounts/login/",
        {"username": "13800138000", "password": "wrong-pass"},
    )

    assert response.status_code == 403


@pytest.mark.django_db
def test_sixth_registration_attempt_is_rate_limited(client):
    invalid_registration = {
        "phone": "not-a-phone",
        "password1": "safe-pass-123",
        "password2": "safe-pass-123",
    }
    for _ in range(5):
        response = client.post("/accounts/register/", invalid_registration)
        assert response.status_code == 200

    response = client.post("/accounts/register/", invalid_registration)

    assert response.status_code == 403


@pytest.mark.django_db
def test_login_rate_limit_is_separated_by_ip(client):
    invalid_login = {"username": "13800138000", "password": "wrong-pass"}

    for _ in range(5):
        assert (
            client.post(
                "/accounts/login/",
                invalid_login,
                REMOTE_ADDR="192.0.2.1",
            ).status_code
            == 200
        )

    response = client.post(
        "/accounts/login/",
        invalid_login,
        REMOTE_ADDR="192.0.2.2",
    )

    assert response.status_code == 200


def test_rate_limit_default_uses_shared_redis_cache(settings):
    assert "django_ratelimit" in settings.INSTALLED_APPS
    assert settings.CACHES["default"]["BACKEND"] == (
        "django_redis.cache.RedisCache"
    )


def test_user_is_registered_for_admin_password_reset(client):
    assert admin.site.is_registered(get_user_model())
    assert client.get("/admin/").status_code == 302


@pytest.mark.django_db
def test_admin_can_reset_user_password(client):
    admin_user = get_user_model().objects.create_superuser(
        phone="13800138000", password="admin-pass-123"
    )
    user = get_user_model().objects.create_user(
        phone="13900139000", password="old-pass-123"
    )
    client.force_login(admin_user)

    response = client.post(
        reverse("admin:auth_user_password_change", args=[user.pk]),
        {"password1": "new-safe-pass-123", "password2": "new-safe-pass-123"},
    )

    assert response.status_code == 302
    user.refresh_from_db()
    assert user.check_password("new-safe-pass-123")
