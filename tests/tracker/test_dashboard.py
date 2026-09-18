from datetime import datetime, time, timedelta

import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.utils import timezone

from tracker.models import Exercise, Meal, Measurement


@pytest.mark.django_db
def test_today_marks_recorded_meal_exercise_and_measurements(client, user):
    now = timezone.now()
    Meal.objects.create(
        user=user, meal_type="breakfast", food="鸡蛋", occurred_at=now
    )
    Exercise.objects.create(
        user=user,
        exercise_type="walking",
        duration_minutes=30,
        intensity="easy",
        occurred_at=now,
    )
    Measurement.objects.create(
        user=user, kind="weight", value=70, occurred_at=now
    )
    client.force_login(user)

    response = client.get("/")

    assert response.status_code == 200
    assert response.context["completion"] == {
        "breakfast": True,
        "lunch": False,
        "dinner": False,
        "snack": False,
        "exercise": True,
        "weight": True,
        "waist": False,
    }


@pytest.mark.django_db
def test_today_excludes_records_from_previous_local_day(client, user):
    local_today = timezone.localdate()
    current_timezone = timezone.get_current_timezone()
    previous_day_end = timezone.make_aware(
        datetime.combine(local_today - timedelta(days=1), time(23, 59)),
        current_timezone,
    )
    Meal.objects.create(
        user=user,
        meal_type="breakfast",
        food="昨天的早餐",
        occurred_at=previous_day_end,
    )
    client.force_login(user)

    response = client.get("/")

    assert response.context["completion"]["breakfast"] is False


def test_today_requires_login(client):
    response = client.get("/")

    assert response.status_code == 302
    assert response.url.startswith("/accounts/login/")


@pytest.mark.django_db
def test_history_contains_only_current_users_records(client, user, other_user):
    Meal.objects.create(user=user, meal_type="lunch", food="自己的午餐")
    Meal.objects.create(user=other_user, meal_type="dinner", food="他人的晚餐")
    client.force_login(user)

    response = client.get("/history/")
    content = response.content.decode()

    assert response.status_code == 200
    assert "自己的午餐" in content
    assert "他人的晚餐" not in content


@pytest.mark.django_db
def test_history_date_filter_uses_local_date(client, user):
    today = timezone.localdate()
    Meal.objects.create(user=user, meal_type="lunch", food="今天")
    Meal.objects.create(
        user=user,
        meal_type="lunch",
        food="较早记录",
        occurred_at=timezone.now() - timedelta(days=2),
    )
    client.force_login(user)

    response = client.get("/history/", {"date": today.isoformat()})
    content = response.content.decode()

    assert "今天" in content
    assert "较早记录" not in content


@pytest.mark.django_db
def test_measurement_quick_link_preselects_kind(client, user):
    client.force_login(user)

    response = client.get("/measurements/new/", {"kind": "waist"})

    assert response.status_code == 200
    assert response.context["form"].initial["kind"] == "waist"


@pytest.mark.django_db
def test_history_paginates_by_day_newest_first(client, user):
    now = timezone.now()
    for days_ago in range(8):
        Meal.objects.create(
            user=user,
            meal_type="lunch",
            food=f"第 {days_ago} 天",
            occurred_at=now - timedelta(days=days_ago),
        )
    client.force_login(user)

    first_page = client.get("/history/")
    second_page = client.get("/history/", {"page": 2})

    assert len(first_page.context["page"].object_list) == 7
    assert first_page.context["page"].object_list[0]["date"] == timezone.localdate(now)
    assert len(second_page.context["page"].object_list) == 1


@pytest.mark.django_db
def test_history_paginates_date_keys_in_database(client, user):
    now = timezone.now()
    for days_ago in range(8):
        Meal.objects.create(
            user=user,
            meal_type="lunch",
            food=f"第 {days_ago} 天",
            occurred_at=now - timedelta(days=days_ago),
        )
    client.force_login(user)

    with CaptureQueriesContext(connection) as queries:
        response = client.get("/history/")

    assert response.status_code == 200
    assert any(
        "UNION" in query["sql"].upper() and "LIMIT 7" in query["sql"].upper()
        for query in queries.captured_queries
    )


@pytest.mark.django_db
def test_navigation_links_to_trends_and_profile(client, user):
    client.force_login(user)

    content = client.get("/").content.decode()

    assert 'href="/trends/"' in content
    assert 'href="/me/"' in content
    assert 'aria-disabled="true"' not in content
