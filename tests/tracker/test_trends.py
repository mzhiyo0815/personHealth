from datetime import date, datetime, time, timedelta
from decimal import Decimal

import pytest
from django.utils import timezone

from tracker.models import Exercise, Meal, Measurement, UserGoal
from tracker.services.trends import (
    chart_payload,
    latest_value_comparison,
    latest_daily_values,
    meal_completion_summary,
    measurement_change_summary,
    numeric_comparison,
    optional_nutrition_average,
    weekly_exercise_summary,
    weekly_goal_progress,
)


def local_noon(day):
    return timezone.make_aware(
        datetime.combine(day, time(12, 0)), timezone.get_current_timezone()
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


def test_latest_value_comparison_uses_each_period_latest_value():
    previous = [
        (date(2026, 9, 7), Decimal("71.00")),
        (date(2026, 9, 14), Decimal("70.50")),
    ]
    current = [
        (date(2026, 9, 15), Decimal("70.20")),
        (date(2026, 9, 21), Decimal("69.80")),
    ]

    assert latest_value_comparison(current, previous) == {
        "status": "ready",
        "current": Decimal("69.80"),
        "previous": Decimal("70.50"),
        "change": Decimal("-0.70"),
    }


@pytest.mark.parametrize(
    ("current", "previous"),
    (
        ([], []),
        ([(date(2026, 9, 21), Decimal("70"))], []),
        ([], [(date(2026, 9, 14), Decimal("70"))]),
    ),
)
def test_latest_value_comparison_requires_both_periods(current, previous):
    assert latest_value_comparison(current, previous)["status"] == "insufficient"


def test_numeric_comparison_handles_integer_and_decimal_values():
    assert numeric_comparison(90, 60) == {
        "current": 90,
        "previous": 60,
        "change": 30,
    }
    assert numeric_comparison(7, 14) == {
        "current": 7,
        "previous": 14,
        "change": -7,
    }
    assert numeric_comparison(
        Decimal("12.345"), Decimal("10.001"), Decimal("0.01")
    ) == {
        "current": Decimal("12.35"),
        "previous": Decimal("10.00"),
        "change": Decimal("2.35"),
    }

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


def test_weekly_goal_progress_uses_exact_average_for_percentage():
    result = weekly_goal_progress(1, 30, 1)

    assert result["weekly_average"] == Decimal("0.2")
    assert result["percentage"] == 23


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


@pytest.mark.django_db
def test_trend_summary_uses_current_users_records_and_goals(
    client, user, other_user
):
    now = timezone.now()
    UserGoal.objects.create(
        user=user,
        weekly_exercise_minutes=180,
        weekly_strength_sessions=3,
    )
    for exercise_type in ("walking", "strength", "strength"):
        Exercise.objects.create(
            user=user,
            exercise_type=exercise_type,
            duration_minutes=30,
            intensity="moderate",
            occurred_at=now,
        )
    Meal.objects.create(
        user=user, meal_type="breakfast", food="早餐", occurred_at=now
    )
    Meal.objects.create(
        user=user,
        meal_type="dinner",
        food="晚餐",
        occurred_at=now - timedelta(days=1),
    )
    Measurement.objects.create(
        user=user,
        kind="weight",
        value=70,
        occurred_at=now - timedelta(days=1),
    )
    Measurement.objects.create(
        user=user, kind="weight", value=69.5, occurred_at=now
    )
    Exercise.objects.create(
        user=other_user,
        exercise_type="strength",
        duration_minutes=600,
        intensity="hard",
        occurred_at=now,
    )
    Meal.objects.create(
        user=other_user, meal_type="lunch", food="他人的午餐", occurred_at=now
    )
    client.force_login(user)

    response = client.get("/trends/", {"range": "7"})
    summary = response.context["trend_summary"]

    assert summary["weight"]["change"] == Decimal("-0.50")
    assert summary["exercise"]["total"] == 90
    assert summary["exercise"]["goal"] == 180
    assert summary["strength"]["total"] == 2
    assert summary["strength"]["goal"] == 3
    assert summary["meals"]["recorded_days"] == 2
    assert summary["meals"]["completed_slots"] == 2


@pytest.mark.django_db
def test_trend_summary_respects_selected_range(client, user):
    now = timezone.now()
    Exercise.objects.create(
        user=user,
        exercise_type="walking",
        duration_minutes=30,
        intensity="easy",
        occurred_at=now,
    )
    Exercise.objects.create(
        user=user,
        exercise_type="walking",
        duration_minutes=70,
        intensity="easy",
        occurred_at=now - timedelta(days=10),
    )
    client.force_login(user)

    seven_day = client.get("/trends/", {"range": "7"})
    thirty_day = client.get("/trends/", {"range": "30"})

    assert seven_day.context["trend_summary"]["exercise"]["total"] == 30
    assert thirty_day.context["trend_summary"]["exercise"]["total"] == 100


@pytest.mark.django_db
def test_trend_summary_uses_default_goals_without_creating_row(client, user):
    client.force_login(user)

    response = client.get("/trends/")
    summary = response.context["trend_summary"]

    assert summary["exercise"]["goal"] == 150
    assert summary["strength"]["goal"] == 2
    assert not UserGoal.objects.filter(user=user).exists()


@pytest.mark.django_db
def test_trends_render_period_summary_cards(client, user):
    now = timezone.now()
    Measurement.objects.create(
        user=user,
        kind="weight",
        value=70,
        occurred_at=now - timedelta(days=1),
    )
    Measurement.objects.create(
        user=user, kind="weight", value=69.5, occurred_at=now
    )
    Exercise.objects.create(
        user=user,
        exercise_type="walking",
        duration_minutes=90,
        intensity="moderate",
        occurred_at=now,
    )
    Meal.objects.create(
        user=user, meal_type="breakfast", food="早餐", occurred_at=now
    )
    Meal.objects.create(
        user=user,
        meal_type="dinner",
        food="晚餐",
        occurred_at=now - timedelta(days=1),
    )
    client.force_login(user)

    content = client.get("/trends/", {"range": "7"}).content.decode()

    assert "本期摘要" in content
    assert "体重变化" in content
    assert "-0.50 千克（kg）" in content
    assert "腰围变化" in content
    assert "每周平均 90.0 分钟" in content
    assert "目标 150 分钟" in content
    assert "力量训练目标" in content
    assert "7 天中记录了 2 天" in content


@pytest.mark.django_db
def test_trends_render_empty_and_insufficient_summary_states(client, user):
    Measurement.objects.create(user=user, kind="weight", value=70)
    client.force_login(user)

    content = client.get("/trends/").content.decode()

    assert "至少需要 2 天数据" in content
    assert "暂无数据" in content
    assert "0%" in content


@pytest.mark.django_db
def test_previous_period_comparison_uses_equal_owner_scoped_periods(
    client, user, other_user
):
    today = timezone.localdate()
    current_start = today - timedelta(days=6)
    previous_start = current_start - timedelta(days=7)
    before_previous = previous_start - timedelta(days=1)

    Measurement.objects.create(
        user=user,
        kind="weight",
        value=70.5,
        occurred_at=local_noon(previous_start),
    )
    Measurement.objects.create(
        user=user,
        kind="weight",
        value=69.8,
        occurred_at=local_noon(today),
    )
    Measurement.objects.create(
        user=user,
        kind="waist",
        value=82,
        occurred_at=local_noon(today),
    )
    Measurement.objects.create(
        user=other_user,
        kind="weight",
        value=200,
        occurred_at=local_noon(today),
    )

    Exercise.objects.create(
        user=user,
        exercise_type="strength",
        duration_minutes=60,
        intensity="moderate",
        occurred_at=local_noon(previous_start),
    )
    for exercise_type in ("walking", "strength", "strength"):
        Exercise.objects.create(
            user=user,
            exercise_type=exercise_type,
            duration_minutes=30,
            intensity="moderate",
            occurred_at=local_noon(current_start),
        )
    Exercise.objects.create(
        user=user,
        exercise_type="strength",
        duration_minutes=999,
        intensity="hard",
        occurred_at=local_noon(before_previous),
    )
    Exercise.objects.create(
        user=other_user,
        exercise_type="strength",
        duration_minutes=500,
        intensity="hard",
        occurred_at=local_noon(today),
    )

    Meal.objects.create(
        user=user,
        meal_type="breakfast",
        food="上期早餐",
        occurred_at=local_noon(previous_start),
    )
    Meal.objects.create(
        user=user,
        meal_type="breakfast",
        food="本期早餐",
        occurred_at=local_noon(current_start),
    )
    Meal.objects.create(
        user=user,
        meal_type="dinner",
        food="本期晚餐",
        occurred_at=local_noon(today),
    )
    Meal.objects.create(
        user=other_user,
        meal_type="lunch",
        food="他人的午餐",
        occurred_at=local_noon(today),
    )
    client.force_login(user)

    response = client.get("/trends/", {"range": "7"})
    comparison = response.context["period_comparison"]

    assert comparison["label"] == "较前 7 天"
    assert comparison["weight"] == {
        "status": "ready",
        "current": Decimal("69.80"),
        "previous": Decimal("70.50"),
        "change": Decimal("-0.70"),
    }
    assert comparison["waist"]["status"] == "insufficient"
    assert comparison["exercise"] == {"current": 90, "previous": 60, "change": 30}
    assert comparison["strength"] == {"current": 2, "previous": 1, "change": 1}
    assert comparison["meals"] == {"current": 7, "previous": 4, "change": 3}
    assert response.context["trend_summary"]["exercise"]["total"] == 90
    assert [value for _, value in response.context["weight_series"]] == [
        Decimal("69.80")
    ]


@pytest.mark.django_db
def test_previous_period_comparison_changes_with_selected_range(client, user):
    today = timezone.localdate()
    Exercise.objects.create(
        user=user,
        exercise_type="walking",
        duration_minutes=30,
        intensity="easy",
        occurred_at=local_noon(today),
    )
    Exercise.objects.create(
        user=user,
        exercise_type="walking",
        duration_minutes=70,
        intensity="easy",
        occurred_at=local_noon(today - timedelta(days=20)),
    )
    Exercise.objects.create(
        user=user,
        exercise_type="walking",
        duration_minutes=100,
        intensity="easy",
        occurred_at=local_noon(today - timedelta(days=40)),
    )
    client.force_login(user)

    seven_day = client.get("/trends/", {"range": "7"})
    thirty_day = client.get("/trends/", {"range": "30"})

    assert seven_day.context["period_comparison"]["exercise"] == {
        "current": 30,
        "previous": 0,
        "change": 30,
    }
    assert thirty_day.context["period_comparison"]["label"] == "较前 30 天"
    assert thirty_day.context["period_comparison"]["exercise"] == {
        "current": 100,
        "previous": 100,
        "change": 0,
    }
