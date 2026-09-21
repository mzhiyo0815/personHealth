from datetime import timedelta

from django.contrib.auth.decorators import login_required
from django.shortcuts import render
from django.utils import timezone

from tracker.models import Measurement, UserGoal
from tracker.services.trends import (
    chart_payload,
    daily_nutrition_series,
    latest_daily_values,
    meal_completion_summary,
    meal_completion_series,
    measurement_change_summary,
    weekly_exercise_summary,
    weekly_goal_progress,
)
from tracker.views.dashboard import local_day_bounds


@login_required
def trends(request):
    range_days = 30 if request.GET.get("range") == "30" else 7
    end_date = timezone.localdate()
    start_date = end_date - timedelta(days=range_days - 1)
    start, _ = local_day_bounds(start_date)
    _, end = local_day_bounds(end_date)

    measurements = request.user.measurements.filter(
        occurred_at__gte=start, occurred_at__lt=end
    ).order_by("occurred_at", "created_at", "pk")
    measurement_rows = {Measurement.Kind.WEIGHT: [], Measurement.Kind.WAIST: []}
    for item in measurements:
        measurement_rows[item.kind].append(
            (timezone.localtime(item.occurred_at).date(), item.value)
        )
    weight_series = latest_daily_values(measurement_rows[Measurement.Kind.WEIGHT])
    waist_series = latest_daily_values(measurement_rows[Measurement.Kind.WAIST])

    exercise_start_date = start_date - timedelta(days=start_date.weekday())
    exercise_start, _ = local_day_bounds(exercise_start_date)
    exercises = request.user.exercises.filter(
        occurred_at__gte=exercise_start, occurred_at__lt=end
    ).order_by("occurred_at", "created_at", "pk")
    exercise_rows = [
        (
            timezone.localtime(item.occurred_at).date(),
            item.duration_minutes,
            item.exercise_type,
        )
        for item in exercises
    ]

    meals = request.user.meals.filter(
        occurred_at__gte=start, occurred_at__lt=end
    ).order_by("occurred_at")
    meal_rows = []
    nutrition_rows = []
    for meal in meals:
        day = timezone.localtime(meal.occurred_at).date()
        meal_rows.append((day, meal.meal_type))
        nutrition_rows.append(
            (
                day,
                (meal.calories, meal.protein, meal.carbohydrates, meal.fat),
            )
        )
    nutrition_series = daily_nutrition_series(nutrition_rows)

    exercise_summary = weekly_exercise_summary(exercise_rows)
    for week in exercise_summary:
        week["is_partial"] = week["week_start"] + timedelta(days=6) > end_date
    range_exercise_rows = [row for row in exercise_rows if row[0] >= start_date]
    goal = UserGoal.objects.filter(user=request.user).first() or UserGoal()
    trend_summary = {
        "weight": measurement_change_summary(weight_series),
        "waist": measurement_change_summary(waist_series),
        "exercise": weekly_goal_progress(
            sum(row[1] for row in range_exercise_rows),
            range_days,
            goal.weekly_exercise_minutes,
        ),
        "strength": weekly_goal_progress(
            sum(row[2] == "strength" for row in range_exercise_rows),
            range_days,
            goal.weekly_strength_sessions,
        ),
        "meals": meal_completion_summary(meal_rows, range_days),
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
        "meal_completion": meal_completion_series(meal_rows, start_date, range_days),
        "nutrition_series": nutrition_series,
        "trend_summary": trend_summary,
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
