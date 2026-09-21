from datetime import date, datetime, time, timedelta
from decimal import Decimal

import pytest
from django.utils import timezone

from tracker.models import Exercise, Meal, Measurement
from tracker.services.trends import (
    chart_payload,
    latest_daily_values,
    meal_completion_summary,
    measurement_change_summary,
    optional_nutrition_average,
    weekly_exercise_summary,
    weekly_goal_progress,
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


def test_measurement_change_summary_handles_empty_and_single_point():
    assert measurement_change_summary([]) == {
        "status": "empty",
        "start": None,
        "latest": None,
        "change": None,
    }
    assert measurement_change_summary(
        [(date(2026, 9, 21), Decimal("70.20"))]
    ) == {
        "status": "insufficient",
        "start": Decimal("70.20"),
        "latest": Decimal("70.20"),
        "change": None,
    }


@pytest.mark.parametrize(
    ("start", "latest", "expected"),
    (
        ("70.00", "69.50", "-0.50"),
        ("70.00", "70.40", "0.40"),
        ("70.00", "70.00", "0.00"),
    ),
)
def test_measurement_change_summary_calculates_period_delta(
    start, latest, expected
):
    result = measurement_change_summary(
        [
            (date(2026, 9, 20), Decimal(start)),
            (date(2026, 9, 21), Decimal(latest)),
        ]
    )

    assert result["status"] == "ready"
    assert result["change"] == Decimal(expected)

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


def test_weekly_goal_progress_normalizes_selected_range():
    seven_days = weekly_goal_progress(90, 7, 150)
    thirty_days = weekly_goal_progress(300, 30, 150)

    assert seven_days == {
        "status": "ready",
        "total": 90,
        "weekly_average": Decimal("90.0"),
        "goal": 150,
        "percentage": 60,
        "bar_percentage": 60,
    }
    assert thirty_days["weekly_average"] == Decimal("70.0")
    assert thirty_days["percentage"] == 47


def test_weekly_goal_progress_handles_zero_goal_and_caps_bar():
    no_goal = weekly_goal_progress(14, 7, 0)
    over_goal = weekly_goal_progress(300, 7, 150)

    assert no_goal["status"] == "no_goal"
    assert no_goal["percentage"] is None
    assert no_goal["bar_percentage"] is None
    assert over_goal["percentage"] == 200
    assert over_goal["bar_percentage"] == 100


def test_meal_completion_summary_deduplicates_daily_meal_types():
    day = date(2026, 9, 21)

    result = meal_completion_summary(
        [(day, "breakfast"), (day, "breakfast"), (day, "lunch")], 7
    )

    assert result == {
        "completed_slots": 2,
        "total_slots": 28,
        "recorded_days": 1,
        "range_days": 7,
        "percentage": 7,
    }

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
    assert "千卡（kcal）" in content
    assert "克（g）" in content


@pytest.mark.django_db
def test_measurement_trends_display_chinese_units(client, user):
    Measurement.objects.create(user=user, kind="weight", value=70)
    Measurement.objects.create(user=user, kind="waist", value=82)
    client.force_login(user)

    content = client.get("/trends/").content.decode()

    assert "千克（kg）" in content
    assert "厘米（cm）" in content


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
