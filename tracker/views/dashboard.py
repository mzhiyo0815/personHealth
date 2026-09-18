from datetime import datetime, time, timedelta

from django.contrib.auth.decorators import login_required
from django.shortcuts import render
from django.utils import timezone

from tracker.models import Measurement


def local_day_bounds(day):
    current_timezone = timezone.get_current_timezone()
    start = timezone.make_aware(datetime.combine(day, time.min), current_timezone)
    end = timezone.make_aware(
        datetime.combine(day + timedelta(days=1), time.min), current_timezone
    )
    return start, end


@login_required
def today(request):
    local_today = timezone.localdate()
    start, end = local_day_bounds(local_today)
    meals = request.user.meals.filter(occurred_at__gte=start, occurred_at__lt=end)
    meal_types = set(meals.values_list("meal_type", flat=True))
    measurements = request.user.measurements.filter(
        occurred_at__gte=start, occurred_at__lt=end
    )
    measurement_types = set(measurements.values_list("kind", flat=True))
    completion = {
        "breakfast": "breakfast" in meal_types,
        "lunch": "lunch" in meal_types,
        "dinner": "dinner" in meal_types,
        "snack": "snack" in meal_types,
        "exercise": request.user.exercises.filter(
            occurred_at__gte=start, occurred_at__lt=end
        ).exists(),
        "weight": Measurement.Kind.WEIGHT in measurement_types,
        "waist": Measurement.Kind.WAIST in measurement_types,
    }
    return render(
        request,
        "tracker/today.html",
        {"today": local_today, "completion": completion},
    )
