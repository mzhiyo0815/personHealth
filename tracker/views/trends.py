from datetime import timedelta

from django.contrib.auth.decorators import login_required
from django.shortcuts import render
from django.utils import timezone

from tracker.models import Measurement, UserGoal
from tracker.services.trends import (
    chart_payload,
    daily_nutrition_series,
    latest_value_comparison,
    latest_daily_values,
    meal_completion_summary,
    meal_completion_series,
    measurement_change_summary,
    numeric_comparison,
    weekly_exercise_summary,
    weekly_goal_progress,
)
from tracker.views.dashboard import local_day_bounds


@login_required
def trends(request):
    range_days = 30 if request.GET.get("range") == "30" else 7
    end_date = timezone.localdate()
    start_date = end_date - timedelta(days=range_days - 1)
    previous_start_date = start_date - timedelta(days=range_days)
    start, _ = local_day_bounds(start_date)
    previous_start, _ = local_day_bounds(previous_start_date)
    _, end = local_day_bounds(end_date)

    measurements = request.user.measurements.filter(
        occurred_at__gte=previous_start, occurred_at__lt=end
    ).order_by("occurred_at", "created_at", "pk")
    current_measurement_rows = {
        Measurement.Kind.WEIGHT: [],
        Measurement.Kind.WAIST: [],
    }
    previous_measurement_rows = {
        Measurement.Kind.WEIGHT: [],
        Measurement.Kind.WAIST: [],
    }
    for item in measurements:
        day = timezone.localtime(item.occurred_at).date()
        row = (day, item.value)
        if day >= start_date:
            current_measurement_rows[item.kind].append(row)
        else:
            previous_measurement_rows[item.kind].append(row)
    weight_series = latest_daily_values(
        current_measurement_rows[Measurement.Kind.WEIGHT]
    )
    waist_series = latest_daily_values(
        current_measurement_rows[Measurement.Kind.WAIST]
    )
    previous_weight_series = latest_daily_values(
        previous_measurement_rows[Measurement.Kind.WEIGHT]
    )
    previous_waist_series = latest_daily_values(
        previous_measurement_rows[Measurement.Kind.WAIST]
    )

    exercise_start_date = start_date - timedelta(days=start_date.weekday())
    exercise_query_start, _ = local_day_bounds(
        min(previous_start_date, exercise_start_date)
    )
    exercises = request.user.exercises.filter(
        occurred_at__gte=exercise_query_start, occurred_at__lt=end
    ).order_by("occurred_at", "created_at", "pk")
    exercise_rows = [
        (
            timezone.localtime(item.occurred_at).date(),
            item.duration_minutes,
            item.exercise_type,
        )
        for item in exercises
    ]
    weekly_exercise_rows = [
        row for row in exercise_rows if row[0] >= exercise_start_date
    ]
    current_exercise_rows = [row for row in exercise_rows if row[0] >= start_date]
    previous_exercise_rows = [
        row
        for row in exercise_rows
        if previous_start_date <= row[0] < start_date
    ]

    meals = request.user.meals.filter(
        occurred_at__gte=previous_start, occurred_at__lt=end
    ).order_by("occurred_at")
    current_meal_rows = []
    previous_meal_rows = []
    nutrition_rows = []
    for meal in meals:
        day = timezone.localtime(meal.occurred_at).date()
        row = (day, meal.meal_type)
        if day >= start_date:
            current_meal_rows.append(row)
            nutrition_rows.append(
                (
                    day,
                    (meal.calories, meal.protein, meal.carbohydrates, meal.fat),
                )
            )
        else:
            previous_meal_rows.append(row)
    nutrition_series = daily_nutrition_series(nutrition_rows)

    exercise_summary = weekly_exercise_summary(weekly_exercise_rows)
    for week in exercise_summary:
        week["is_partial"] = week["week_start"] + timedelta(days=6) > end_date
    goal = UserGoal.objects.filter(user=request.user).first() or UserGoal()
    current_meal_summary = meal_completion_summary(current_meal_rows, range_days)
    previous_meal_summary = meal_completion_summary(previous_meal_rows, range_days)
    trend_summary = {
        "weight": measurement_change_summary(weight_series),
        "waist": measurement_change_summary(waist_series),
        "exercise": weekly_goal_progress(
            sum(row[1] for row in current_exercise_rows),
            range_days,
            goal.weekly_exercise_minutes,
        ),
        "strength": weekly_goal_progress(
            sum(row[2] == "strength" for row in current_exercise_rows),
            range_days,
            goal.weekly_strength_sessions,
        ),
        "meals": current_meal_summary,
    }
    period_comparison = {
        "label": f"较前 {range_days} 天",
        "weight": latest_value_comparison(weight_series, previous_weight_series),
        "waist": latest_value_comparison(waist_series, previous_waist_series),
        "exercise": numeric_comparison(
            sum(row[1] for row in current_exercise_rows),
            sum(row[1] for row in previous_exercise_rows),
        ),
        "strength": numeric_comparison(
            sum(row[2] == "strength" for row in current_exercise_rows),
            sum(row[2] == "strength" for row in previous_exercise_rows),
        ),
        "meals": numeric_comparison(
            current_meal_summary["percentage"],
            previous_meal_summary["percentage"],
        ),
    }

    context = {
        "range_days": range_days,
        "weight_series": weight_series,
        "waist_series": waist_series,
        "weight_chart": chart_payload(
            weight_series, "体重趋势", "千克（kg）", "weight"
        ),
        "waist_chart": chart_payload(
            waist_series, "腰围趋势", "厘米（cm）", "waist"
        ),
        "exercise_summary": exercise_summary,
        "meal_completion": meal_completion_series(
            current_meal_rows, start_date, range_days
        ),
        "nutrition_series": nutrition_series,
        "trend_summary": trend_summary,
        "period_comparison": period_comparison,
    }
    if nutrition_series:
        context["nutrition_charts"] = (
            chart_payload(
                nutrition_series["calories"], "热量趋势", "千卡（kcal）", "calories"
            ),
            chart_payload(
                nutrition_series["protein"], "蛋白质趋势", "克（g）", "protein"
            ),
            chart_payload(
                nutrition_series["carbohydrates"],
                "碳水趋势",
                "克（g）",
                "carbohydrates",
            ),
            chart_payload(nutrition_series["fat"], "脂肪趋势", "克（g）", "fat"),
        )
    return render(request, "tracker/trends.html", context)
