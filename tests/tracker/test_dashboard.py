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


@pytest.mark.django_db
def test_today_shows_five_most_recent_records_for_current_user(
    client, user, other_user
):
    now = timezone.now()
    own_meals = [
        Meal.objects.create(
            user=user,
            meal_type="lunch",
            food=f"自己的饮食 {index}",
            occurred_at=now - timedelta(minutes=index),
        )
        for index in range(6)
    ]
    own_exercises = [
        Exercise.objects.create(
            user=user,
            exercise_type=f"自己的运动 {index}",
            duration_minutes=20,
            intensity="moderate",
            occurred_at=now - timedelta(minutes=index),
        )
        for index in range(6)
    ]
    other_meal = Meal.objects.create(
        user=other_user, meal_type="dinner", food="他人的饮食", occurred_at=now
    )
    other_exercise = Exercise.objects.create(
        user=other_user,
        exercise_type="他人的运动",
        duration_minutes=30,
        intensity="easy",
        occurred_at=now,
    )
    client.force_login(user)

    response = client.get("/")
    content = response.content.decode()

    assert list(response.context["recent_meals"]) == own_meals[:5]
    assert list(response.context["recent_exercises"]) == own_exercises[:5]
    for record in own_meals[:5] + own_exercises[:5]:
        assert f"?copy={record.pk}" in content
    assert f"?copy={own_meals[5].pk}" not in content
    assert f"?copy={own_exercises[5].pk}" not in content
    assert str(other_meal.pk) not in content
    assert str(other_exercise.pk) not in content


@pytest.mark.django_db
def test_today_shows_recent_record_empty_states(client, user):
    client.force_login(user)

    content = client.get("/").content.decode()

    assert "暂无最近饮食" in content
    assert "暂无最近运动" in content


@pytest.mark.django_db
def test_today_recent_records_show_local_time_and_chinese_exercise_type(client, user):
    occurred_at = timezone.now().replace(second=0, microsecond=0)
    Meal.objects.create(
        user=user,
        meal_type="lunch",
        food="糙米饭",
        occurred_at=occurred_at,
    )
    Exercise.objects.create(
        user=user,
        exercise_type="strength",
        duration_minutes=30,
        intensity="moderate",
        occurred_at=occurred_at,
    )
    client.force_login(user)

    content = client.get("/").content.decode()
    expected_time = timezone.localtime(occurred_at).strftime("%Y年%m月%d日 %H:%M")

    assert content.count(expected_time) == 2
    assert "力量训练：30 分钟" in content
    assert "strength：30 分钟" not in content


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


@pytest.mark.django_db
def test_history_displays_units_for_exercise_weight_and_waist(client, user):
    now = timezone.now()
    Exercise.objects.create(
        user=user,
        exercise_type="walking",
        duration_minutes=30,
        intensity="easy",
        occurred_at=now,
    )
    Measurement.objects.create(
        user=user, kind="weight", value=70.2, occurred_at=now
    )
    Measurement.objects.create(
        user=user, kind="waist", value=82.5, occurred_at=now
    )
    client.force_login(user)

    content = client.get("/history/").content.decode()

    assert "30 分钟" in content
    assert "70.20 千克（kg）" in content
    assert "82.50 厘米（cm）" in content
