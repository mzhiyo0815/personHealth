from django.contrib.auth.decorators import login_required
from django.shortcuts import render
from django.utils import timezone

from tracker.models import Measurement
from tracker.services.trends import (
    chart_payload,
    daily_nutrition_series,
    latest_daily_values,
    meal_completion_series,
    weekly_exercise_summary,
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

    context = {
        "range_days": range_days,
        "weight_series": weight_series,
        "waist_series": waist_series,
        "weight_chart": chart_payload(weight_series, "体重趋势", "kg", "weight"),
        "waist_chart": chart_payload(waist_series, "腰围趋势", "cm", "waist"),
        "exercise_summary": exercise_summary,
        "meal_completion": meal_completion_series(meal_rows, start_date, range_days),
        "nutrition_series": nutrition_series,
    }
    if nutrition_series:
        context["nutrition_charts"] = (
            chart_payload(
                nutrition_series["calories"], "热量趋势", "kcal", "calories"
            ),
            chart_payload(
                nutrition_series["protein"], "蛋白质趋势", "g", "protein"
            ),
            chart_payload(
                nutrition_series["carbohydrates"], "碳水趋势", "g", "carbohydrates"
            ),
            chart_payload(nutrition_series["fat"], "脂肪趋势", "g", "fat"),
        )
    return render(request, "tracker/trends.html", context)
from datetime import timedelta
