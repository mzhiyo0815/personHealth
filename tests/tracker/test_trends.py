from datetime import date, datetime, time, timedelta
from decimal import Decimal

import pytest
from django.utils import timezone

from tracker.models import Exercise, Meal, Measurement
from tracker.services.trends import (
    chart_payload,
    latest_daily_values,
    optional_nutrition_average,
    weekly_exercise_summary,
)


def test_latest_measurement_per_day_wins():
    rows = [
        (date(2026, 9, 16), Decimal("88.0")),
        (date(2026, 9, 16), Decimal("87.8")),
        (date(2026, 9, 17), Decimal("87.6")),
    ]

    assert latest_daily_values(rows) == [
        (date(2026, 9, 16), Decimal("87.8")),
        (date(2026, 9, 17), Decimal("87.6")),
    ]


def test_missing_nutrition_does_not_become_zero():
    assert optional_nutrition_average([None, None]) is None
    assert optional_nutrition_average([None, Decimal("100"), Decimal("200")]) == Decimal(
        "150"
    )


def test_weekly_exercise_summary_counts_minutes_and_strength_sessions():
    monday = date(2026, 9, 14)
    rows = [
        (monday, 30, "walking"),
        (monday + timedelta(days=1), 45, "strength"),
        (monday + timedelta(days=2), 20, "strength"),
    ]

    assert weekly_exercise_summary(rows) == [
        {
            "week_start": monday,
            "duration_minutes": 95,
            "strength_sessions": 2,
        }
    ]


def test_chart_with_one_value_does_not_draw_a_trend_line():
    chart = chart_payload(
        [(date(2026, 9, 17), Decimal("70"))], "体重趋势", "kg", "weight"
    )

    assert chart["points"]
    assert chart["polyline"] == ""


@pytest.mark.django_db
@pytest.mark.parametrize("range_value", ("7", "30"))
def test_trends_supports_seven_and_thirty_day_ranges(client, user, range_value):
    Measurement.objects.create(user=user, kind="weight", value=70)
    client.force_login(user)

    response = client.get("/trends/", {"range": range_value})

    assert response.status_code == 200
    assert response.context["range_days"] == int(range_value)
    assert response.context["weight_series"]


@pytest.mark.django_db
def test_trends_hide_nutrition_section_when_all_values_are_blank(client, user):
    Meal.objects.create(user=user, meal_type="breakfast", food="鸡蛋")
    client.force_login(user)

    response = client.get("/trends/")

    assert response.status_code == 200
    assert response.context["nutrition_series"] is None
    assert "营养趋势" not in response.content.decode()


@pytest.mark.django_db
def test_trends_show_all_nutrition_charts_when_values_exist(client, user):
    Meal.objects.create(
        user=user,
        meal_type="lunch",
        food="鸡胸肉和米饭",
        calories=500,
        protein=35,
        carbohydrates=60,
        fat=12,
    )
    client.force_login(user)

    response = client.get("/trends/")
    content = response.content.decode()

    assert response.status_code == 200
    assert "热量趋势" in content
    assert "蛋白质趋势" in content
    assert "碳水趋势" in content
    assert "脂肪趋势" in content


@pytest.mark.django_db
def test_nutrition_trend_sums_meals_for_each_day(client, user):
    Meal.objects.create(
        user=user, meal_type="breakfast", food="早餐", calories=300, protein=20
    )
    Meal.objects.create(
        user=user, meal_type="dinner", food="晚餐", calories=700, protein=40
    )
    client.force_login(user)

    response = client.get("/trends/")

    assert response.context["nutrition_series"]["calories"][0][1] == Decimal(
        "1000.00"
    )
    assert response.context["nutrition_series"]["protein"][0][1] == Decimal(
        "60.00"
    )


@pytest.mark.django_db
def test_weekly_summary_includes_same_week_days_before_range_start(client, user):
    end_date = timezone.localdate()
    range_start = end_date - timedelta(days=6)
    week_start = range_start - timedelta(days=range_start.weekday())
    if week_start == range_start:
        pytest.skip("当前 7 天范围恰好从周一开始")
    occurred_at = timezone.make_aware(
        datetime.combine(week_start, time(12, 0)),
        timezone.get_current_timezone(),
    )
    Exercise.objects.create(
        user=user,
        exercise_type="walking",
        duration_minutes=25,
        intensity="easy",
        occurred_at=occurred_at,
    )
    client.force_login(user)

    response = client.get("/trends/", {"range": "7"})

    assert response.context["exercise_summary"][0]["duration_minutes"] == 25


@pytest.mark.django_db
def test_latest_measurement_breaks_same_time_tie_by_creation_order(client, user):
    occurred_at = timezone.now().replace(second=0, microsecond=0)
    Measurement.objects.create(
        user=user, kind="weight", value=70, occurred_at=occurred_at
    )
    Measurement.objects.create(
        user=user, kind="weight", value=69.5, occurred_at=occurred_at
    )
    client.force_login(user)

    response = client.get("/trends/")

    assert response.context["weight_series"][-1][1] == Decimal("69.50")


@pytest.mark.django_db
def test_trends_exclude_other_users_measurements(client, user, other_user):
    Measurement.objects.create(user=user, kind="weight", value=70)
    Measurement.objects.create(user=other_user, kind="weight", value=99)
    client.force_login(user)

    response = client.get("/trends/")

    assert [value for _, value in response.context["weight_series"]] == [Decimal("70.00")]
