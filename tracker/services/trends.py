from collections import defaultdict
from datetime import timedelta
from decimal import ROUND_HALF_UP, Decimal


def latest_daily_values(rows):
    latest = {}
    for day, value in rows:
        latest[day] = value
    return sorted(latest.items())


def measurement_change_summary(series):
    if not series:
        return {"status": "empty", "start": None, "latest": None, "change": None}
    start = series[0][1]
    latest = series[-1][1]
    if len(series) == 1:
        return {
            "status": "insufficient",
            "start": start,
            "latest": latest,
            "change": None,
        }
    return {
        "status": "ready",
        "start": start,
        "latest": latest,
        "change": (latest - start).quantize(Decimal("0.01")),
    }


def optional_nutrition_average(values):
    present = [value for value in values if value is not None]
    if not present:
        return None
    return (sum(present, Decimal("0")) / len(present)).quantize(Decimal("0.01"))


def weekly_exercise_summary(rows):
    weeks = defaultdict(lambda: {"duration_minutes": 0, "strength_sessions": 0})
    for day, duration_minutes, exercise_type in rows:
        week_start = day - timedelta(days=day.weekday())
        weeks[week_start]["duration_minutes"] += duration_minutes
        if exercise_type == "strength":
            weeks[week_start]["strength_sessions"] += 1
    return [
        {"week_start": week_start, **weeks[week_start]}
        for week_start in sorted(weeks)
    ]


def rounded_percentage(numerator, denominator):
    if not denominator:
        return None
    percentage = (
        Decimal(numerator) * 100 / Decimal(denominator)
    ).quantize(Decimal("1"), rounding=ROUND_HALF_UP)
    return max(0, int(percentage))


def weekly_goal_progress(total, range_days, weekly_goal):
    exact_weekly_average = Decimal(total) * 7 / Decimal(range_days)
    weekly_average = exact_weekly_average.quantize(
        Decimal("0.1"), rounding=ROUND_HALF_UP
    )
    percentage = rounded_percentage(exact_weekly_average, weekly_goal)
    return {
        "status": "ready" if percentage is not None else "no_goal",
        "total": total,
        "weekly_average": weekly_average,
        "goal": weekly_goal,
        "percentage": percentage,
        "bar_percentage": min(percentage, 100) if percentage is not None else None,
    }


def meal_completion_summary(rows, range_days):
    completed = set(rows)
    return {
        "completed_slots": len(completed),
        "total_slots": range_days * 4,
        "recorded_days": len({day for day, _ in completed}),
        "range_days": range_days,
        "percentage": rounded_percentage(len(completed), range_days * 4),
    }


def meal_completion_series(rows, start_date, days):
    meal_types = defaultdict(set)
    for day, meal_type in rows:
        meal_types[day].add(meal_type)
    return [
        {
            "date": start_date + timedelta(days=offset),
            "completed": len(meal_types[start_date + timedelta(days=offset)]),
            "total": 4,
        }
        for offset in range(days)
    ]


def daily_nutrition_series(rows):
    daily = defaultdict(lambda: defaultdict(list))
    fields = ("calories", "protein", "carbohydrates", "fat")
    for day, values in rows:
        for field, value in zip(fields, values):
            daily[day][field].append(value)
    result = {field: [] for field in fields}
    has_any_value = False
    for day in sorted(daily):
        for field in fields:
            present = [value for value in daily[day][field] if value is not None]
            if present:
                has_any_value = True
                total = sum(present, Decimal("0")).quantize(Decimal("0.01"))
                result[field].append((day, total))
    return result if has_any_value else None


def chart_payload(series, title, unit, chart_id):
    rows = [{"label": day.isoformat(), "value": value} for day, value in series]
    if not rows:
        return {
            "id": chart_id,
            "title": title,
            "unit": unit,
            "rows": [],
            "points": [],
            "polyline": "",
        }
    numeric_values = [float(row["value"]) for row in rows]
    minimum = min(numeric_values)
    maximum = max(numeric_values)
    span = maximum - minimum or 1
    denominator = max(len(rows) - 1, 1)
    points = [
        {
            "x": round(5 + index * 90 / denominator, 2),
            "y": round(90 - (value - minimum) * 80 / span, 2),
        }
        for index, value in enumerate(numeric_values)
    ]
    polyline = " ".join(f'{point["x"]},{point["y"]}' for point in points)
    if len(points) < 2:
        polyline = ""
    return {
        "id": chart_id,
        "title": title,
        "unit": unit,
        "rows": rows,
        "points": points,
        "polyline": polyline,
    }
